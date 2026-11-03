from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Board(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    created_at: datetime


class Card(BaseModel):
    id: UUID
    board_id: UUID
    owner_id: UUID
    position: int
    image_path: str
    thumb_path: str
    image_sha256: str
    title: str
    chart_type: str
    period: str | None
    takeaways: list[str]
    interpretation: str
    caveats: list[str]
    user_note: str | None
    model: str
    created_at: datetime


class NewCard(BaseModel):
    board_id: UUID
    owner_id: UUID
    position: int
    image_path: str
    thumb_path: str
    image_sha256: str
    title: str
    chart_type: str
    period: str | None
    takeaways: list[str]
    interpretation: str
    caveats: list[str]
    model: str
    raw_response: dict[str, object]


class CardPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    period: str | None = None
    takeaways: list[str] | None = Field(default=None, max_length=3)
    interpretation: str | None = None
    caveats: list[str] | None = Field(default=None, max_length=2)
    user_note: str | None = None
