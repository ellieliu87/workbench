"""Workspace router - returns the default analytical views for a business function."""
from fastapi import APIRouter, Depends, HTTPException

from models.schemas import WorkspaceData
from routers.auth import get_current_user
from services.workspace_data import get_workspace

router = APIRouter()


@router.get("/{function_id}", response_model=WorkspaceData)
async def get_function_workspace(
    function_id: str,
    _: str = Depends(get_current_user),
):
    data = get_workspace(function_id)
    if not data:
        raise HTTPException(status_code=404, detail="Workspace not found for this function")
    return data
