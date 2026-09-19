from __future__ import annotations

import asyncio
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.agent.prompt import load_templates
from app.api.deps import AppContainer
from app.conversation.service import CancellationToken
from app.data.models import Provenance

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ToolCallResponse(BaseModel):
    name: str
    result_kind: str
    duration_ms: float


class ChatResponse(BaseModel):
    conversation_id: str
    text: str
    outcome: Literal["answer", "clarify", "unanswerable", "refuse", "error"]
    provenance: list[Provenance] = Field(default_factory=list)
    tool_calls: list[ToolCallResponse] = Field(default_factory=list)
    latency_ms: float


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def _set_session_cookie(response: Response, container: AppContainer, conversation_id: str) -> None:
    settings = container.settings
    response.set_cookie(
        key=settings.session_cookie_name,
        value=conversation_id,
        httponly=True,
        samesite=settings.session_cookie_samesite,
        secure=settings.session_cookie_secure,
        max_age=settings.conversation_ttl_seconds,
    )


def _chat_response(turn: Any) -> ChatResponse:
    answer = turn.answer
    return ChatResponse(
        conversation_id=turn.conversation_id,
        text=answer.text,
        outcome=answer.outcome,
        provenance=answer.provenance,
        tool_calls=[
            ToolCallResponse(
                name=trace.name,
                result_kind=trace.result_kind,
                duration_ms=trace.duration_ms,
            )
            for trace in answer.tool_calls
        ],
        latency_ms=turn.latency_ms,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    response: Response,
    container: Annotated[AppContainer, Depends(get_container)],
) -> ChatResponse:
    settings = container.settings
    conversation_id = request.cookies.get(settings.session_cookie_name)
    cancellation = CancellationToken()
    try:
        turn = await asyncio.wait_for(
            asyncio.to_thread(
                container.service.handle_message,
                conversation_id,
                body.message,
                cancellation,
            ),
            timeout=settings.api_request_timeout_seconds,
        )
    except TimeoutError:
        cancellation.cancel()
        timeout_text = load_templates()["timeout"].replace("{{ attempted }}", "none")
        resolved_id = conversation_id or container.store.create().id
        _set_session_cookie(response, container, resolved_id)
        return ChatResponse(
            conversation_id=resolved_id,
            text=timeout_text,
            outcome="error",
            provenance=[],
            tool_calls=[],
            latency_ms=settings.api_request_timeout_seconds * 1000,
        )
    _set_session_cookie(response, container, turn.conversation_id)
    return _chat_response(turn)


@router.post("/conversations/reset")
def reset_conversation(
    request: Request,
    response: Response,
    container: Annotated[AppContainer, Depends(get_container)],
) -> dict[str, str]:
    settings = container.settings
    conversation_id = request.cookies.get(settings.session_cookie_name)
    fresh_id = container.service.reset(conversation_id)
    assert fresh_id is not None
    _set_session_cookie(response, container, fresh_id)
    return {"conversation_id": fresh_id}
