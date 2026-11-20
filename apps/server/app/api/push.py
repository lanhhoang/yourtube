"""Web Push key and subscription endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.db import get_session
from app.schemas import PushKey, PushSubscriptionDelete, PushSubscriptionIn
from app.services import push as push_service

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/key")
def get_key() -> PushKey:
    keys = push_service.load_vapid_keys(app_settings.data_dir, app_settings)
    return PushKey(public_key=keys.public_key)


@router.post("/subscriptions", status_code=204)
def subscribe(
    body: PushSubscriptionIn,
    session: Session = Depends(get_session),
    user_agent: str | None = Header(default=None),
) -> Response:
    push_service.upsert_subscription(
        session, body.endpoint, body.keys.p256dh, body.keys.auth, user_agent
    )
    return Response(status_code=204)


@router.delete("/subscriptions", status_code=204)
def unsubscribe(body: PushSubscriptionDelete, session: Session = Depends(get_session)) -> Response:
    push_service.delete_subscription(session, body.endpoint)
    return Response(status_code=204)
