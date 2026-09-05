from agent.schemas import Interpretation
from conftest import app_for


def post(client, message, session="guest"):
    response = client.post("/chat", json={"session_id": session, "message": message})
    assert response.status_code == 200
    return response.get_json()


def test_missing_information_transcript():
    app = app_for([Interpretation(intent="booking_update", date_expressions=["tomorrow"])])
    body = post(app.test_client(), "Room available for tomorrow?")
    assert body["status"] == "gathering"
    assert body["state"]["check_in"] == "2026-09-06"
    assert body["state"]["check_out"] == "2026-09-07"
    assert body["recommendations"] == []
    assert "adults" in body["reply"]


def test_immediate_recommendation_transcript():
    app = app_for([Interpretation(intent="booking_update", updates={"requested_rooms": 2, "adults": 4, "ac_preference": "AC"}, date_expressions=["15th to 17th"])])
    body = post(app.test_client(), "2 rooms, 15th to 17th, 4 adults, AC")
    assert body["status"] == "recommending"
    assert 1 <= len(body["recommendations"]) <= 3
    assert all(sum(room["quantity"] for room in rec["rooms"]) == 2 for rec in body["recommendations"])
    assert all(all("AC" in room["type"] and "Non-AC" not in room["type"] for room in rec["rooms"]) for rec in body["recommendations"])
    assert all(rec["total_price"] == rec["nightly_price"] * 2 for rec in body["recommendations"])


def test_hinglish_transcript_does_not_require_ac_choice():
    app = app_for([Interpretation(intent="booking_update", updates={"adults": 3}, date_expressions=["kal"])])
    body = post(app.test_client(), "kal ke liye room chahiye, 3 log hain")
    assert body["status"] == "recommending"
    assert body["state"]["ac_preference"] == "ANY"
    assert body["state"]["check_in"] == "2026-09-06"


def test_correction_replaces_ac_and_discards_stale_selection():
    app = app_for([
        Interpretation(updates={"ac_preference": "AC"}),
        Interpretation(updates={"adults": 4}, date_expressions=["15th to 17th"]),
        Interpretation(intent="booking_update", updates={"ac_preference": "NON_AC"}),
    ])
    client = app.test_client()
    post(client, "AC room chahiye")
    post(client, "15th to 17th, 4 adults")
    body = post(client, "non-AC me kya rate hai")
    assert body["state"]["ac_preference"] == "NON_AC"
    assert body["state"]["selected_recommendation_id"] is None
    assert all(room["type"] == "Standard Non-AC" for rec in body["recommendations"] for room in rec["rooms"])


def test_occupancy_children_and_weekend_clarification_transcript():
    app = app_for([
        Interpretation(updates={"adults": 5, "children": [4, 6]}, date_expressions=["this weekend"]),
        Interpretation(date_expressions=["2026-09-12 to 2026-09-13"]),
    ])
    client = app.test_client()
    first = post(client, "We are 7 people, 2 kids aged 4 and 6, need rooms this weekend")
    assert "ambiguous" in first["reply"]
    body = post(client, "2026-09-12 to 2026-09-13")
    assert body["state"]["adults"] == 5
    assert [child["age"] for child in body["state"]["children"]] == [4, 6]
    assert all(rec["total_capacity"] >= 7 for rec in body["recommendations"])


def test_grounded_interruption_preserves_booking_state():
    app = app_for([
        Interpretation(updates={"adults": 2}, date_expressions=["tomorrow"]),
        Interpretation(intent="general_question", general_question_topics=["pool"]),
    ])
    client = app.test_client()
    post(client, "two people tomorrow")
    body = post(client, "Do you have a swimming pool?")
    assert "do not confirm" in body["reply"]
    assert body["state"]["check_in"] == "2026-09-06"
    assert body["state"]["adults"] == 2


def test_confirmation_requires_selection_when_multiple_and_confirms_option():
    app = app_for([
        Interpretation(updates={"adults": 4}, date_expressions=["15th to 17th"]),
        Interpretation(intent="confirmation", confirmation=True),
        Interpretation(intent="confirmation", confirmation=True, selected_option_number=1),
    ])
    client = app.test_client()
    post(client, "4 adults, 15th to 17th")
    ambiguous = post(client, "yes")
    confirmed = post(client, "confirm option 1")
    assert ambiguous["status"] == "recommending"
    assert "which option" in ambiguous["reply"]
    assert confirmed["status"] == "confirmed"
    assert len(confirmed["recommendations"]) == 1
