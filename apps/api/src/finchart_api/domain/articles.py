"""News PDFs: stored as uploaded, then translated paragraph by paragraph in the background."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from finchart_api.domain.cards import DailyQuotaExceededError, DailyUsage, start_of_day
from finchart_api.imaging import sha256_hex

log = logging.getLogger("finchart.articles")

ArticleStatus = Literal["pending", "done", "failed"]
# Shown to the user as a reason; "interrupted" means the server restarted mid-translation.
FailureCode = Literal["too_long", "unreadable", "failed", "interrupted"]


class Paragraph(BaseModel):
    kind: Literal["heading", "paragraph"] = Field(
        description="heading for a section heading inside the article, paragraph otherwise"
    )
    original: str = Field(description="The paragraph exactly as written in the article")
    translated: str = Field(
        description="Natural Korean translation; empty when the article is already Korean"
    )


class ArticleTranslation(BaseModel):
    """What the model returns for one PDF."""

    language: str = Field(description="ISO 639-1 code of the article's language, e.g. en, ja")
    title: str = Field(description="The headline as written in the article")
    title_ko: str = Field(description="The headline in Korean")
    source: str | None = Field(description="Publication name, e.g. Reuters, if shown")
    published: str | None = Field(description="Publication date as YYYY-MM-DD, if shown")
    summary: list[str] = Field(description="Up to three one-sentence Korean key points")
    paragraphs: list[Paragraph] = Field(description="The article body in reading order")


class Article(BaseModel):
    id: UUID
    owner_id: UUID
    filename: str
    pdf_path: str
    pdf_sha256: str
    page_count: int
    status: ArticleStatus
    error: FailureCode | None
    language: str | None
    title: str | None
    title_ko: str | None
    source: str | None
    published: str | None
    summary: list[str]
    paragraphs: list[Paragraph]
    model: str | None
    created_at: datetime
    pinned_at: datetime | None = None


@dataclass(frozen=True)
class TranslationResult:
    translation: ArticleTranslation
    model: str


class TranslatorError(Exception):
    def __init__(self, code: FailureCode) -> None:
        super().__init__(code)
        self.code: FailureCode = code


class Translator(Protocol):
    async def translate(self, pdf: bytes) -> TranslationResult: ...


class DuplicateArticleError(Exception):
    pass


class ArticleNotFoundError(LookupError):
    pass


class ArticleRepository(Protocol):
    async def insert_pending(
        self, filename: str, pdf_path: str, sha256: str, page_count: int
    ) -> Article: ...
    async def find_by_sha(self, sha256: str) -> Article | None: ...
    async def get(self, article_id: UUID) -> Article | None: ...
    async def list(self, query: str, limit: int) -> list[Article]: ...
    async def restart(self, article_id: UUID) -> Article | None: ...
    async def complete(
        self, article_id: UUID, translation: ArticleTranslation, model: str
    ) -> Article | None: ...
    async def set_pinned(self, article_id: UUID, pinned: bool) -> Article | None: ...
    async def fail(self, article_id: UUID, code: FailureCode) -> Article | None: ...
    async def delete(self, article_id: UUID) -> Article | None: ...
    async def translations_since(self, since: datetime) -> int: ...


class ArticleFiles(Protocol):
    async def upload(self, path: str, data: bytes, content_type: str) -> None: ...
    async def read(self, path: str) -> bytes | None: ...
    async def remove(self, paths: list[str]) -> None: ...


@dataclass(frozen=True)
class ArticleData:
    owner_id: UUID
    articles: ArticleRepository
    files: ArticleFiles


@dataclass(frozen=True)
class ArticleSubmission:
    article: Article
    duplicate: bool


async def translation_usage(data: ArticleData, daily_quota: int) -> DailyUsage:
    start = start_of_day()
    used = await data.articles.translations_since(start)
    return DailyUsage(limit=daily_quota, used=used, resets_at=start + timedelta(days=1))


async def _ensure_quota(data: ArticleData, daily_quota: int) -> None:
    if (await translation_usage(data, daily_quota)).remaining <= 0:
        raise DailyQuotaExceededError(daily_quota)


async def submit_article(
    data: ArticleData, pdf: bytes, filename: str, page_count: int, daily_quota: int
) -> ArticleSubmission:
    """Stores the PDF and a pending article; the caller runs translate_article next."""
    sha = sha256_hex(pdf)
    existing = await data.articles.find_by_sha(sha)
    if existing is not None:
        return ArticleSubmission(article=existing, duplicate=True)
    await _ensure_quota(data, daily_quota)
    path = f"{data.owner_id}/articles/{sha}.pdf"
    await data.files.upload(path, pdf, "application/pdf")
    name = filename.strip()[:200] or "article.pdf"
    try:
        article = await data.articles.insert_pending(name, path, sha, page_count)
    except DuplicateArticleError:
        winner = await data.articles.find_by_sha(sha)
        if winner is None:
            raise
        return ArticleSubmission(article=winner, duplicate=True)
    return ArticleSubmission(article=article, duplicate=False)


async def retry_article(data: ArticleData, article_id: UUID, daily_quota: int) -> Article:
    article = await data.articles.get(article_id)
    if article is None:
        raise ArticleNotFoundError(article_id)
    if article.status != "failed":
        return article
    await _ensure_quota(data, daily_quota)
    restarted = await data.articles.restart(article_id)
    if restarted is None:
        raise ArticleNotFoundError(article_id)
    return restarted


async def translate_article(
    data: ArticleData, translator: Translator, article_id: UUID
) -> Article | None:
    """Runs one pending translation to done or failed. Never raises for model failures."""
    article = await data.articles.get(article_id)
    if article is None or article.status != "pending":
        return article
    pdf = await data.files.read(article.pdf_path)
    if pdf is None:
        return await data.articles.fail(article_id, "unreadable")
    try:
        result = await translator.translate(pdf)
    except TranslatorError as exc:
        log.warning(
            "translation failed for %s: %s (cause: %r)", article_id, exc.code, exc.__cause__
        )
        return await data.articles.fail(article_id, exc.code)
    except Exception:
        log.exception("translation crashed for %s", article_id)
        return await data.articles.fail(article_id, "failed")
    return await data.articles.complete(article_id, _tidy(result.translation), result.model)


def _tidy(t: ArticleTranslation) -> ArticleTranslation:
    paragraphs = [p for p in t.paragraphs if p.original.strip()]
    return t.model_copy(update={"summary": t.summary[:3], "paragraphs": paragraphs})


async def delete_article(data: ArticleData, article_id: UUID) -> bool:
    article = await data.articles.delete(article_id)
    if article is None:
        return False
    await data.files.remove([article.pdf_path])
    return True
