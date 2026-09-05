from app import create_app
from agent.llm import BasicInterpreter
from agent.policy import answer_policy
from agent.schemas import Interpretation
from conftest import FIXED_TODAY, app_for


def test_invalid_api_requests_have_stable_errors():
    app = app_for([])
    client = app.test_client()
    cases = [
        (None, "request body must be a JSON object"),
        ({"message": "hi"}, "session_id must be a non-empty string"),
        ({"session_id": "x", "message": " "}, "message must be a non-empty string"),
        ({"session_id": "x" * 129, "message": "hi"}, "session_id must be at most 128 characters"),
        ({"session_id": "x", "message": "x" * 2001}, "message must be at most 2000 characters"),
    ]
    for payload, expected in cases:
        response = client.post("/chat", json=payload)
        assert response.status_code == 400
        assert response.get_json()["error"]["message"] == expected


def test_sessions_are_isolated():
    app = app_for([
        Interpretation(updates={"adults": 2}, date_expressions=["tomorrow"]),
        Interpretation(updates={"adults": 4}, date_expressions=["tomorrow"]),
    ])
    client = app.test_client()
    one = client.post("/chat", json={"session_id": "one", "message": "two tomorrow"}).get_json()
    two = client.post("/chat", json={"session_id": "two", "message": "four tomorrow"}).get_json()
    assert one["state"]["adults"] == 2
    assert two["state"]["adults"] == 4


class BrokenInterpreter:
    def interpret(self, message, state, today):
        from agent.service import InterpreterUnavailable
        raise InterpreterUnavailable()


def test_provider_failure_is_safe():
    app = create_app(interpreter=BrokenInterpreter(), today=FIXED_TODAY)
    response = app.test_client().post("/chat", json={"session_id": "x", "message": "hello"})
    assert response.status_code == 503
    assert response.get_json() == {"error": {"code": "interpreter_unavailable", "message": "The language service is temporarily unavailable"}}


def test_local_fallback_extracts_only_basic_explicit_hinglish_facts():
    interpretation = BasicInterpreter().interpret("kal ke liye 2 rooms, 4 log, non-AC", None, FIXED_TODAY)
    assert interpretation.date_expressions
    assert interpretation.updates == {"ac_preference": "NON_AC", "requested_rooms": 2, "adults": 4}


def test_policy_answers_are_inventory_grounded(inventory):
    assert answer_policy(["early_check_in"], inventory) == "Early check-in is subject to availability, chargeable."
    assert answer_policy(["pool"], inventory) == "The provided hotel details do not confirm that facility or policy."
