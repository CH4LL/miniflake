from __future__ import annotations

from app.llm.types import Message, OpaqueBlock


def history_for_llm(messages: list[Message], *, window_turns: int) -> list[Message]:
    turns = _split_turns(messages)
    if len(turns) > window_turns:
        turns = turns[-window_turns:]
    rendered: list[Message] = []
    for index, turn in enumerate(turns):
        is_current_turn = index == len(turns) - 1
        for message in turn:
            rendered.append(_render_message(message, keep_thinking=is_current_turn))
    return rendered


def _split_turns(messages: list[Message]) -> list[list[Message]]:
    turns: list[list[Message]] = []
    current: list[Message] = []
    for message in messages:
        if message.role == "user" and current:
            turns.append(current)
            current = [message]
        else:
            current.append(message)
    if current:
        turns.append(current)
    return turns


def _render_message(message: Message, *, keep_thinking: bool) -> Message:
    if keep_thinking:
        return message.model_copy(deep=True)
    filtered = [block for block in message.content if not isinstance(block, OpaqueBlock)]
    return Message(role=message.role, content=filtered)
