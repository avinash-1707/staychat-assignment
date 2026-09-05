from __future__ import annotations

from datetime import date
import logging
import os

from flask import Flask, jsonify, request
from pydantic import ValidationError
from dotenv import load_dotenv

from agent.config import load_inventory
from agent.llm import BasicInterpreter, GeminiInterpreter, MessageInterpreter
from agent.service import BookingService, InterpreterUnavailable
from agent.state import InMemorySessionRepository
from agent.validation import RequestValidationError, validate_chat_payload


def create_app(
    *,
    interpreter: MessageInterpreter | None = None,
    today: date | None = None,
    repository: InMemorySessionRepository | None = None,
) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    inventory = load_inventory(os.path.join(os.path.dirname(__file__), "inventory.json"))
    business_date = today or _business_date()
    active_interpreter = interpreter or _runtime_interpreter()
    service = BookingService(inventory, active_interpreter, repository or InMemorySessionRepository(), business_date)
    app.config["booking_service"] = service

    @app.post("/chat")
    def chat():
        try:
            session_id, message = validate_chat_payload(request.get_json(silent=True))
            return jsonify(service.chat(session_id, message))
        except RequestValidationError as exc:
            return error("invalid_request", str(exc), 400)
        except InterpreterUnavailable:
            app.logger.exception("Interpreter unavailable")
            return error("interpreter_unavailable", "The language service is temporarily unavailable", 503)
        except ValidationError:
            app.logger.exception("Invalid interpreter result")
            return error("interpreter_unavailable", "The language service returned an invalid response", 503)

    return app


def error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _business_date() -> date:
    configured = os.getenv("BUSINESS_DATE")
    if configured:
        return date.fromisoformat(configured)
    return date.today()


def _runtime_interpreter() -> MessageInterpreter:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return GeminiInterpreter(key, os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    logging.getLogger(__name__).warning("GEMINI_API_KEY is unset; using limited local interpreter")
    return BasicInterpreter()


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG") == "true")
