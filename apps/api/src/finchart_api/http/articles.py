import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from finchart_api.domain.articles import (
    Article,
    ArticleData,
    ArticleNotFoundError,
    Translator,
    delete_article,
    retry_article,
    submit_article,
    translate_article,
    translation_usage,
)
from finchart_api.domain.cards import DailyQuotaExceededError
from finchart_api.domain.uploads import (
    TooManyPagesError,
    UnsupportedPdfError,
    UploadTooLargeError,
    validate_pdf_upload,
)
from finchart_api.http.deps import CurrentAccount, ServicesDep
from finchart_api.http.schemas import (
    ArticleOut,
    ArticlePatch,
    ArticleSubmitOut,
    ArticleSummaryOut,
    QuotaOut,
)
from finchart_api.infra.sqlite import Database, FileStorage, sqlite_article_data

router = APIRouter(tags=["articles"])
logger = logging.getLogger("uvicorn.error")

LIST_LIMIT = 200


def get_translator(services: ServicesDep) -> Translator:
    if services.translator is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "translation_disabled")
    return services.translator


TranslatorDep = Annotated[Translator, Depends(get_translator)]


def get_article_data(services: ServicesDep, account: CurrentAccount) -> ArticleData:
    return sqlite_article_data(services.db, account.id)


ArticleDataDep = Annotated[ArticleData, Depends(get_article_data)]


async def run_translation(db: Database, translator: Translator, article: Article) -> None:
    """Background task: owns its data access, since the request is gone by now."""
    await translate_article(sqlite_article_data(db, article.owner_id), translator, article.id)


def _out(article: Article) -> ArticleOut:
    return ArticleOut.from_article(article)


@router.get("/articles/quota")
async def get_translation_quota(services: ServicesDep, data: ArticleDataDep) -> QuotaOut:
    usage = await translation_usage(data, services.settings.daily_translations_per_user)
    return QuotaOut(
        limit=usage.limit, used=usage.used, remaining=usage.remaining, resets_at=usage.resets_at
    )


@router.post("/articles", status_code=status.HTTP_202_ACCEPTED)
async def upload_article(
    pdf: Annotated[UploadFile, File()],
    account: CurrentAccount,
    services: ServicesDep,
    translator: TranslatorDep,
    data: ArticleDataDep,
    background: BackgroundTasks,
    response: Response,
) -> ArticleSubmitOut:
    settings = services.settings
    if not services.upload_limiter.allow(str(account.id)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many uploads, retry shortly")
    if pdf.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "only pdf")
    content = await pdf.read(settings.max_pdf_bytes + 1)
    try:
        pages = validate_pdf_upload(content, settings.max_pdf_bytes, settings.max_pdf_pages)
        result = await submit_article(
            data, content, pdf.filename or "", pages, settings.daily_translations_per_user
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "pdf too large") from exc
    except UnsupportedPdfError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unreadable_pdf") from exc
    except TooManyPagesError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "too_many_pages") from exc
    except DailyQuotaExceededError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "daily_quota") from exc
    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    else:
        background.add_task(run_translation, services.db, translator, result.article)
    return ArticleSubmitOut(article=_out(result.article), duplicate=result.duplicate)


@router.get("/articles")
async def list_articles(data: ArticleDataDep, q: str = "") -> list[ArticleSummaryOut]:
    articles = await data.articles.list(q.strip()[:100], LIST_LIMIT)
    return [ArticleSummaryOut.from_article(a) for a in articles]


@router.get("/articles/{article_id}")
async def get_article(article_id: UUID, data: ArticleDataDep) -> ArticleOut:
    article = await data.articles.get(article_id)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "article not found")
    return _out(article)


@router.patch("/articles/{article_id}")
async def update_article(article_id: UUID, body: ArticlePatch, data: ArticleDataDep) -> ArticleOut:
    article = await data.articles.set_pinned(article_id, body.pinned)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "article not found")
    return _out(article)


@router.post("/articles/{article_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry(
    article_id: UUID,
    services: ServicesDep,
    translator: TranslatorDep,
    data: ArticleDataDep,
    background: BackgroundTasks,
) -> ArticleOut:
    try:
        article = await retry_article(
            data, article_id, services.settings.daily_translations_per_user
        )
    except ArticleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "article not found") from exc
    except DailyQuotaExceededError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "daily_quota") from exc
    if article.status == "pending":
        background.add_task(run_translation, services.db, translator, article)
    return _out(article)


@router.get("/articles/{article_id}/pdf")
async def article_pdf(
    article_id: UUID, account: CurrentAccount, services: ServicesDep, data: ArticleDataDep
) -> FileResponse:
    article = await data.articles.get(article_id)
    file = (
        FileStorage(services.db.images_dir, account.id).file_for(article.pdf_path)
        if article
        else None
    )
    if article is None or file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "article not found")
    return FileResponse(
        file,
        media_type="application/pdf",
        filename=article.filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_article(article_id: UUID, data: ArticleDataDep) -> Response:
    if not await delete_article(data, article_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "article not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
