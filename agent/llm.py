from __future__ import annotations

from datetime import date
import json
import re
from typing import Protocol

from agent.schemas import BookingState, Interpretation, public_state


SYSTEM_PROMPT = """You are the language-interpretation component of a hotel booking system. You do not run the booking system and you do not make business decisions.

Your sole job is to return one JSON object matching the supplied interpretation schema for the guest's latest message. Understand English and Hinglish. Extract only facts explicitly stated or unambiguously implied by the guest. The current normalized booking state and application's current date are provided as context.

Never calculate prices, choose rooms, decide availability, decide missing fields, change booking status, invent a hotel policy/facility, or write a guest-facing answer. For a correction, place only new explicit values in updates. Omitted means no update. Return JSON only with intent, updates, date_expressions, explicit_dates, clear_fields, general_question_topics, selected_option_number, selected_room_description, confirmation, and ambiguities."""


class MessageInterpreter(Protocol):
    def interpret(self, message: str, state: BookingState, today: date) -> Interpretation: ...


class GeminiInterpreter:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def interpret(self, message: str, state: BookingState, today: date) -> Interpretation:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.api_key)
            context = {"today": today.isoformat(), "state": public_state(state)}
            response = client.models.generate_content(
                model=self.model,
                contents=f"{SYSTEM_PROMPT}\nSchema: {json.dumps(Interpretation.model_json_schema())}\nContext: {json.dumps(context)}\nGuest: {message}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                    http_options=types.HttpOptions(
                        timeout=10_000,
                        retry_options=types.HttpRetryOptions(attempts=2),
                    ),
                ),
            )
            text = (response.text or "").strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
            return Interpretation.model_validate_json(text)
        except Exception as exc:
            from agent.service import InterpreterUnavailable
            raise InterpreterUnavailable() from exc


class BasicInterpreter:
    """Small offline parser; Gemini is the production multilingual interpreter."""

    def interpret(self, message: str, state: BookingState, today: date) -> Interpretation:
        text = message.lower()
        updates: dict[str, object] = {}
        date_expressions: list[str] = []
        if any(value in text for value in ("tomorrow", "kal", "this weekend")) or re.search(r"\b\d{1,2}(?:st|nd|rd|th)?\s*(?:to|-)\s*\d", text) or re.search(r"\b\d{4}-\d{2}-\d{2}\b", text):
            date_expressions.append(message)
        if "non-ac" in text or "non ac" in text:
            updates["ac_preference"] = "NON_AC"
        elif re.search(r"\bac\b", text):
            updates["ac_preference"] = "AC"
        room_match = re.search(r"\b(\d+)\s*rooms?\b", text)
        if room_match:
            updates["requested_rooms"] = int(room_match.group(1))
        child_ages = _child_ages(text)
        total_match = re.search(r"\b(\d+)\s*(?:people|persons?|log)\b", text)
        adult_match = re.search(r"\b(\d+)\s*adults?\b", text)
        if child_ages:
            updates["children"] = child_ages
            if total_match:
                updates["adults"] = int(total_match.group(1)) - len(child_ages)
        if adult_match:
            updates["adults"] = int(adult_match.group(1))
        elif total_match and not child_ages:
            updates["adults"] = int(total_match.group(1))
        if "late check-in" in text or "late check in" in text:
            updates["special_requests"] = ["late check-in"]
        topics = _topics(text)
        option_match = re.search(r"(?:option|rec)[ -]?(\d)\b", text)
        confirmation = bool(re.search(r"\b(confirm|book|yes|haan|ha)\b", text)) and not bool(re.search(r"\b(rate|price|kya rate)\b", text))
        if confirmation and option_match:
            intent = "confirmation"
        elif topics:
            intent = "general_question"
        elif option_match:
            intent = "selection"
        elif updates or date_expressions:
            intent = "booking_update"
        elif re.search(r"\b(hello|hi|namaste)\b", text):
            intent = "greeting"
        else:
            intent = "unclear"
        return Interpretation(intent=intent, updates=updates, date_expressions=date_expressions, general_question_topics=topics, selected_option_number=int(option_match.group(1)) if option_match else None, confirmation=confirmation)


def _child_ages(text: str) -> list[int | None]:
    match = re.search(r"(\d+)\s*(?:kids?|children)(?:\s+aged)?\s+([\d ,and]+)", text)
    if match:
        ages = [int(value) for value in re.findall(r"\d+", match.group(2))]
        return ages[: int(match.group(1))] + [None] * max(0, int(match.group(1)) - len(ages))
    match = re.search(r"(\d+)\s*(?:kids?|children)\b", text)
    return [None] * int(match.group(1)) if match else []


def _topics(text: str) -> list[str]:
    rules = {"early check": "early_check_in", "cancellation": "cancellation", "cancel": "cancellation", "swimming pool": "pool", "pool": "pool", "check-in time": "check_in_time", "check in time": "check_in_time", "check-out time": "check_out_time", "check out time": "check_out_time", "taxi": "taxi", "parking": "parking", "pet": "pet_policy", "meal": "meals"}
    return [topic for phrase, topic in rules.items() if phrase in text][:1]
