from __future__ import annotations

from copy import deepcopy
from datetime import date

from agent.booking import build_recommendations
from agent.dates import resolve_dates
from agent.dialogue import has_booking_context, merge_updates, missing_question, recommendation_reply, selected_recommendation
from agent.llm import MessageInterpreter
from agent.policy import answer_policy
from agent.schemas import Inventory, Recommendation, public_state
from agent.state import SessionRecord, SessionRepository


class InterpreterUnavailable(Exception):
    pass


class BookingService:
    def __init__(self, inventory: Inventory, interpreter: MessageInterpreter, repository: SessionRepository, today: date) -> None:
        self.inventory = inventory
        self.interpreter = interpreter
        self.repository = repository
        self.today = today

    def chat(self, session_id: str, message: str) -> dict[str, object]:
        return self.repository.transact(session_id, lambda record: self._chat_turn(session_id, message, record))

    def _chat_turn(self, session_id: str, message: str, record: SessionRecord) -> dict[str, object]:
        state = record.state
        interpretation = self.interpreter.interpret(message, deepcopy(state), self.today)
        changed, merge_error = merge_updates(state, interpretation)
        date_error = None
        if interpretation.date_expressions or interpretation.explicit_dates:
            resolved = resolve_dates(interpretation.date_expressions, interpretation.explicit_dates, self.today)
            if resolved.error:
                date_error = resolved.error
            else:
                if resolved.check_in and resolved.check_in != state.check_in:
                    state.check_in = resolved.check_in
                    changed = True
                if resolved.check_out and resolved.check_out != state.check_out:
                    state.check_out = resolved.check_out
                    changed = True
        if changed:
            state.selected_recommendation_id = None
            state.status = "gathering"
            record.recommendations = []
        if merge_error or date_error:
            reply = merge_error or date_error or "Please provide valid booking details."
            return self._payload(session_id, record, reply, [])
        policy_reply = answer_policy(interpretation.general_question_topics, self.inventory)
        if policy_reply and not changed:
            suffix = " I can continue with your booking details." if has_booking_context(state) else ""
            return self._payload(session_id, record, policy_reply + suffix, record.recommendations if state.status == "recommending" else [])
        missing = missing_question(state)
        if missing:
            state.status = "gathering"
            record.recommendations = []
            return self._payload(session_id, record, policy_reply + " " + missing if policy_reply else missing, [])
        recommendations = build_recommendations(state, self.inventory)
        if not recommendations:
            state.status = "gathering"
            record.recommendations = []
            return self._payload(session_id, record, "No configured room combination fits this request. Please try a different room count or contact the hotel.", [])
        record.recommendations = recommendations
        selection = selected_recommendation(interpretation, recommendations)
        if selection:
            state.selected_recommendation_id = selection.id
        if interpretation.confirmation:
            if not selection and len(recommendations) == 1:
                selection = recommendations[0]
                state.selected_recommendation_id = selection.id
            if selection:
                state.status = "confirmed"
                return self._payload(session_id, record, f"Your request for {selection.id} is confirmed for hotel follow-up.", [selection])
            state.status = "recommending"
            return self._payload(session_id, record, "Please tell me which option you would like to book.", recommendations)
        state.status = "recommending"
        reply = policy_reply or recommendation_reply(state, recommendations)
        return self._payload(session_id, record, reply, recommendations)

    def _payload(self, session_id: str, record: SessionRecord, reply: str, recommendations: list[Recommendation]) -> dict[str, object]:
        return {"session_id": session_id, "reply": reply.strip(), "status": record.state.status, "state": public_state(record.state), "recommendations": [item.model_dump() for item in recommendations], "meta": {"hotel_id": self.inventory.hotel_id, "inventory_mode": "static_demo"}}
