from __future__ import annotations


class RequestValidationError(ValueError):
    pass


def validate_chat_payload(body: object) -> tuple[str, str]:
    if not isinstance(body, dict):
        raise RequestValidationError("request body must be a JSON object")
    session_id = body.get("session_id")
    message = body.get("message")
    if not isinstance(session_id, str) or not session_id.strip():
        raise RequestValidationError("session_id must be a non-empty string")
    if len(session_id) > 128:
        raise RequestValidationError("session_id must be at most 128 characters")
    if not isinstance(message, str) or not message.strip():
        raise RequestValidationError("message must be a non-empty string")
    if len(message) > 2000:
        raise RequestValidationError("message must be at most 2000 characters")
    return session_id.strip(), message.strip()
