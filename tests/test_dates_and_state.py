from datetime import date

from agent.dates import resolve_dates
from agent.schemas import Interpretation
from conftest import FIXED_TODAY, app_for


def test_relative_and_one_night_date_rules():
    tomorrow = resolve_dates(["kal ke liye"], {}, FIXED_TODAY)
    assert tomorrow.check_in == date(2026, 9, 6)
    assert tomorrow.check_out == date(2026, 9, 7)
    single = resolve_dates([], {"check_in": "2026-09-15"}, FIXED_TODAY)
    assert single.check_out == date(2026, 9, 16)


def test_date_validation_and_leap_days():
    assert "valid calendar" in resolve_dates([], {"check_in": "2026-02-29"}, FIXED_TODAY).error
    assert "before today" in resolve_dates([], {"check_in": "2026-09-04"}, FIXED_TODAY).error
    assert "after check-in" in resolve_dates([], {"check_in": "2026-09-10", "check_out": "2026-09-10"}, FIXED_TODAY).error
    assert resolve_dates([], {"check_in": "2028-02-29"}, FIXED_TODAY).check_in == date(2028, 2, 29)


def test_explicit_facts_replace_but_omitted_facts_persist():
    app = app_for([
        Interpretation(updates={"adults": 3, "ac_preference": "AC"}, explicit_dates={"check_in": "2026-09-15", "check_out": "2026-09-17"}),
        Interpretation(updates={"adults": 4, "requested_rooms": 2, "ac_preference": "NON_AC"}),
    ])
    client = app.test_client()
    first = client.post("/chat", json={"session_id": "same", "message": "first"}).get_json()
    second = client.post("/chat", json={"session_id": "same", "message": "actually four"}).get_json()
    assert first["state"]["ac_preference"] == "AC"
    assert second["state"]["check_in"] == "2026-09-15"
    assert second["state"]["adults"] == 4
    assert second["state"]["requested_rooms"] == 2
    assert second["state"]["ac_preference"] == "NON_AC"
