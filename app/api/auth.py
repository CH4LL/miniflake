from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.api.errors import error_response
from app.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    passphrase: str


class SessionResponse(BaseModel):
    auth_required: bool
    authenticated: bool


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def sign_token(secret: str, *, now: float | None = None) -> str:
    issued_at = int(now if now is not None else time.time())
    payload = json.dumps({"iat": issued_at, "nonce": secrets.token_hex(16)}, separators=(",", ":"))
    payload_b64 = _b64url_encode(payload.encode("utf-8"))
    signature = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{payload_b64}.{_b64url_encode(signature)}"


def verify_token(
    token: str,
    secret: str,
    *,
    max_age_seconds: int,
    now: float | None = None,
) -> bool:
    if not token or "." not in token:
        return False
    payload_b64, signature_b64 = token.split(".", 1)
    expected_sig = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    try:
        actual_sig = _b64url_decode(signature_b64)
    except (ValueError, TypeError):
        return False
    if not hmac.compare_digest(expected_sig, actual_sig):
        return False
    try:
        payload = json.loads(_b64url_decode(payload_b64))
        issued_at = int(payload["iat"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False
    current = now if now is not None else time.time()
    return current - issued_at <= max_age_seconds


def verify_passphrase(candidate: str, expected: str | None) -> bool:
    if expected is None:
        return False
    return secrets.compare_digest(candidate, expected)


class DemoAuth:
    def __init__(
        self,
        settings: Settings,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._enabled = settings.demo_auth_enabled
        if self._enabled:
            if not settings.demo_passphrase:
                raise RuntimeError("DEMO_PASSPHRASE is required when DEMO_AUTH_ENABLED=true")
            if not settings.auth_signing_secret:
                raise RuntimeError("AUTH_SIGNING_SECRET is required when DEMO_AUTH_ENABLED=true")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def cookie_name(self) -> str:
        return self._settings.auth_cookie_name

    def sign_cookie(self) -> str:
        return sign_token(self._settings.auth_signing_secret, now=self._clock())

    def is_authenticated(self, token: str | None) -> bool:
        if not self._enabled:
            return True
        if not token:
            return False
        return verify_token(
            token,
            self._settings.auth_signing_secret,
            max_age_seconds=self._settings.auth_cookie_max_age_seconds,
            now=self._clock(),
        )

    def verify_passphrase(self, candidate: str) -> bool:
        return verify_passphrase(candidate, self._settings.demo_passphrase)

    def set_auth_cookie(self, response: Response) -> None:
        response.set_cookie(
            key=self._settings.auth_cookie_name,
            value=self.sign_cookie(),
            httponly=True,
            samesite=self._settings.session_cookie_samesite,
            secure=self._settings.session_cookie_secure,
            max_age=self._settings.auth_cookie_max_age_seconds,
        )


def get_demo_auth(request: Request) -> DemoAuth:
    return request.app.state.demo_auth


def install_auth_middleware(app, auth: DemoAuth) -> None:
    protected_prefixes = ("/api/chat", "/api/conversations/")

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if not auth.enabled:
            return await call_next(request)
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in protected_prefixes):
            return await call_next(request)
        token = request.cookies.get(auth.cookie_name)
        if not auth.is_authenticated(token):
            return error_response(
                request,
                status_code=401,
                code="unauthorized",
                message="Authentication required",
            )
        return await call_next(request)


@router.get("/session", response_model=SessionResponse)
def session_status(
    request: Request,
    auth: Annotated[DemoAuth, Depends(get_demo_auth)],
) -> SessionResponse:
    token = request.cookies.get(auth.cookie_name)
    return SessionResponse(
        auth_required=auth.enabled,
        authenticated=auth.is_authenticated(token),
    )


@router.post("/login", response_model=None)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth: Annotated[DemoAuth, Depends(get_demo_auth)],
):
    if not auth.enabled:
        return {"status": "ok"}
    if not auth.verify_passphrase(body.passphrase):
        client_host = request.client.host if request.client else "unknown"
        logger.warning("Failed login attempt from %s", client_host)
        return error_response(
            request,
            status_code=401,
            code="unauthorized",
            message="Invalid passphrase",
        )
    auth.set_auth_cookie(response)
    return {"status": "ok"}
