from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from finchart_api.http.deps import CurrentAccount, ServicesDep
from finchart_api.infra.sqlite import FileStorage

router = APIRouter(tags=["images"])


@router.get("/images/{path:path}")
async def image(path: str, account: CurrentAccount, services: ServicesDep) -> FileResponse:
    file = FileStorage(services.db.images_dir, account.id).file_for(path)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "image not found")
    # Content-addressed paths never change, so the browser may cache privately for a long time.
    return FileResponse(
        file,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )
