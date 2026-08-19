from typing import Optional
from fastapi import HTTPException, Depends, Request, Header
from app.config import Settings, get_settings


def get_rag(request: Request):
    return request.app.state.rag


def get_executer(request: Request):
    return request.app.state.executer


def verify_api_key(
    x_api_key: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
):
    if settings.API_KEY and (x_api_key is None or x_api_key != settings.API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True
