from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from finchart_api.backup import last_success
from finchart_api.http.deps import ServicesDep

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    last_backup: datetime | None


@router.get("/health")
def health(services: ServicesDep) -> HealthResponse:
    return HealthResponse(status="ok", last_backup=last_success(services.settings.data_dir))
