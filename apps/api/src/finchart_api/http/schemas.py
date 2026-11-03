from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from finchart_api.domain.models import Card


class BoardIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class BoardOut(BaseModel):
    id: UUID
    title: str
    created_at: datetime


class CardOut(BaseModel):
    id: UUID
    board_id: UUID
    position: int
    title: str
    chart_type: str
    period: str | None
    takeaways: list[str]
    interpretation: str
    caveats: list[str]
    user_note: str | None
    model: str
    created_at: datetime
    image_url: str | None
    thumb_url: str | None

    @classmethod
    def from_card(cls, card: Card, urls: dict[str, str]) -> "CardOut":
        return cls(
            **card.model_dump(include=set(cls.model_fields) - {"image_url", "thumb_url"}),
            image_url=urls.get(card.image_path),
            thumb_url=urls.get(card.thumb_path),
        )


class CardCreateOut(BaseModel):
    card: CardOut
    duplicate: bool


class OrderIn(BaseModel):
    card_ids: list[UUID]
