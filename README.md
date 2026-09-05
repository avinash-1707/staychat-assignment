# StayChat Booking Agent

A small Flask booking conversation service for the static demo hotel **Hotel Sahu**. `POST /chat` accepts a guest message and session ID, returning JSON with its reply, normalized state, status, and up to three priced room combinations.

## Run

Python 3.11+ is required. From a clean clone:

```bash
cp .env.example .env
python -m pip install -r requirements.txt
python app.py
```

Set `GEMINI_API_KEY` in `.env` to use Gemini 2.5 Flash. Without it the app uses a deliberately limited local English/Hinglish parser, suitable for the included demo patterns but not a replacement for Gemini. Run tests with `pytest -q`.

```bash
curl -X POST http://127.0.0.1:5000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"guest-123","message":"2 rooms, 15th to 17th, 4 adults, AC"}'
```

```json
{"session_id":"guest-123","status":"recommending","state":{"check_in":"2026-09-15","check_out":"2026-09-17","adults":4,"children":[],"requested_rooms":2,"ac_preference":"AC","special_requests":[],"selected_recommendation_id":null},"recommendations":[{"id":"rec-1","nightly_price":5000,"nights":2,"total_price":10000,"currency":"INR"}]}
```

Invalid JSON and invalid fields return `400` as `{"error":{"code":"invalid_request","message":"..."}}`. A failed language provider returns a safe `503` and never exposes its output or credentials.

## Architecture

- `app.py` validates the HTTP boundary and delegates each chat turn to `BookingService`.
- `agent/llm.py` is a thin Gemini `gemini-2.5-flash` adapter behind an injectable interpreter interface.
- Gemini calls use a 10-second timeout and at most two attempts; provider failures become safe `503` responses.
- Gemini extracts candidate language facts only; its JSON is schema-validated before use.
- `agent/state.py` persists typed session state in a lock-protected in-memory repository.
- `agent/dialogue.py` owns validated state merges, follow-up priority, selection, and deterministic reply rendering.
- `agent/validation.py` owns HTTP payload validation, leaving the Flask route as transport only.
- `agent/dates.py` resolves dates against an injected business date.
- `agent/booking.py` deterministically enumerates capacity-valid combinations, allocations, prices, and rankings.
- `agent/policy.py` answers only facts configured in `inventory.json`.
- Python, not Gemini, decides missing details, dates, occupancy, prices, options, and confirmation status.

State merges only explicit updates; omitted facts remain. Changed dates, party data, room count, or AC preference invalidate a prior selection. A recommendation is `recommending`; it becomes `confirmed` only after an unambiguous selection plus affirmative booking intent. A bare `yes` only confirms when there is exactly one option.

## Rules And Assumptions

- `tomorrow` and `kal` mean the injected business date plus one day. A single arrival date defaults to one night. “This weekend” is the next Saturday/Sunday; on Saturday it asks for exact dates.
- Children under five count toward physical capacity but not billable extra beds. A stated total such as “7 people, 2 kids aged 4 and 6” means five adults plus those two children. Unknown child ages are requested before a quote because they can change price.
- If a room count is requested it is exact. Otherwise rank valid combinations by fewest rooms, least unused capacity, fewest billable extra beds, lowest total price, then lexical room type.
- Prices and `available_rooms` in `inventory.json` are explicit demo assumptions added because the supplied task data omitted live price and PMS availability. There is no real-time availability or booking handoff.
- Early check-in, cancellation, and times come directly from inventory. Unlisted facilities or policies, such as a pool, are described as unconfirmed rather than guessed. Special requests are recorded but remain subject to hotel confirmation.

## Reproducible Test Transcripts

Conversation tests use business date `2026-09-05`.

1. Guest: “Room available for tomorrow?” → check-in `2026-09-06`, check-out `2026-09-07`, `gathering`, asks for party count.
2. Guest: “2 rooms, 15th to 17th, 4 adults, AC” → `recommending`, exactly two AC rooms per option, two-night deterministic totals.
3. Guest: “kal ke liye room chahiye, 3 log hain” → `recommending`, `ANY` AC preference, no needless AC question.
4. Guest: “AC room chahiye”; then “15th to 17th, 4 adults”; then “non-AC me kya rate hai” → preference becomes `NON_AC`, only Standard Non-AC options remain.
5. Guest: “We are 7 people, 2 kids aged 4 and 6, need rooms this weekend”; then “2026-09-12 to 2026-09-13” → Saturday ambiguity is clarified; state has five adults and child ages 4 and 6, with capacity-valid options.
6. Guest starts “two people tomorrow”; then asks “Do you have a swimming pool?” → response says supplied hotel details do not confirm a pool and retains the booking state.

## Limitations And Next Steps

This is static demo inventory, not a PMS/channel-manager integration. Sessions are in-memory, there is no payment, authentication, rate limiting, or real booking creation. With another week: Redis-backed sessions, PMS availability and handoff, authenticated/rate-limited API access, structured observability, multilingual evaluation, and production retry/timeout telemetry.
