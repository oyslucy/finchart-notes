from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from finchart_api.domain.cards import delete_board
from finchart_api.http.deps import UserDataDep
from finchart_api.http.schemas import BoardIn, BoardOut

router = APIRouter(prefix="/boards", tags=["boards"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_board(body: BoardIn, data: UserDataDep) -> BoardOut:
    board = await data.boards.create(body.title)
    return BoardOut.model_validate(board.model_dump())


@router.get("")
async def list_boards(data: UserDataDep) -> list[BoardOut]:
    return [BoardOut.model_validate(b.model_dump()) for b in await data.boards.list_all()]


@router.patch("/{board_id}")
async def rename_board(board_id: UUID, body: BoardIn, data: UserDataDep) -> BoardOut:
    board = await data.boards.rename(board_id, body.title)
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "board not found")
    return BoardOut.model_validate(board.model_dump())


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_board(board_id: UUID, data: UserDataDep) -> Response:
    if not await delete_board(data, board_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "board not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
