from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import calendar
import re


@dataclass
class DateResolution:
    check_in: date | None = None
    check_out: date | None = None
    error: str | None = None


MONTHS = {name.lower(): number for number, name in enumerate(calendar.month_abbr) if name}
MONTHS.update({name.lower(): number for number, name in enumerate(calendar.month_name) if name})


def resolve_dates(expressions: list[str], explicit: dict[str, str | None], today: date) -> DateResolution:
    """Resolve only simple, documented forms against the injected business date."""
    parsed_explicit: dict[str, date] = {}
    for field in ("check_in", "check_out"):
        raw = explicit.get(field)
        if raw:
            try:
                parsed_explicit[field] = date.fromisoformat(raw)
            except ValueError:
                return DateResolution(error="Please provide valid calendar dates in YYYY-MM-DD format.")
    if parsed_explicit:
        check_in = parsed_explicit.get("check_in")
        check_out = parsed_explicit.get("check_out")
        if check_in and not check_out:
            check_out = check_in + timedelta(days=1)
        return _validate(check_in, check_out, today)
    text = " ".join(expressions).lower().strip()
    if not text:
        return DateResolution()
    if "tomorrow" in text or re.search(r"\bkal\b", text):
        return DateResolution(today + timedelta(days=1), today + timedelta(days=2))
    if "this weekend" in text:
        if today.weekday() == 5:
            return DateResolution(error="Please share your check-in and check-out dates; same-day weekend stays are ambiguous.")
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        check_in = today + timedelta(days=days_until_saturday)
        return DateResolution(check_in, check_in + timedelta(days=1))
    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if iso_dates:
        try:
            dates = [date.fromisoformat(value) for value in iso_dates]
        except ValueError:
            return DateResolution(error="Please provide valid calendar dates.")
        return _validate(dates[0], dates[1] if len(dates) > 1 else dates[0] + timedelta(days=1), today)
    range_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(MONTHS) + r")\s*(?:to|-)+\s*(\d{1,2})(?:st|nd|rd|th)?(?:\s+(" + "|".join(MONTHS) + r"))?", text)
    if range_match:
        start_day, start_month, end_day, end_month = range_match.groups()
        return _month_range(int(start_day), MONTHS[start_month], int(end_day), MONTHS[end_month] or MONTHS[start_month], today)
    day_range = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:to|-)\s*(\d{1,2})(?:st|nd|rd|th)?\b", text)
    if day_range:
        return _month_range(int(day_range.group(1)), today.month, int(day_range.group(2)), today.month, today)
    single = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(MONTHS) + r")\b", text)
    if single:
        return _month_range(int(single.group(1)), MONTHS[single.group(2)], None, None, today)
    if re.search(r"\d", text):
        return DateResolution(error="Please share valid check-in and check-out dates.")
    return DateResolution()


def _month_range(start_day: int, start_month: int, end_day: int | None, end_month: int | None, today: date) -> DateResolution:
    for year in range(today.year, today.year + 3):
        try:
            check_in = date(year, start_month, start_day)
            check_out = date(year, end_month, end_day) if end_day and end_month else check_in + timedelta(days=1)
        except ValueError:
            return DateResolution(error="Please provide valid calendar dates.")
        if check_out <= check_in:
            return DateResolution(error="Check-out must be after check-in. Please provide the month and year.")
        if check_in >= today:
            return DateResolution(check_in, check_out)
    return DateResolution(error="Please provide a future check-in date including the year.")


def _validate(check_in: date | None, check_out: date | None, today: date) -> DateResolution:
    if not check_in:
        return DateResolution(error="Please provide a check-in date.")
    if check_in < today:
        return DateResolution(error="Check-in cannot be before today. Please provide future dates.")
    if not check_out or check_out <= check_in:
        return DateResolution(error="Check-out must be after check-in.")
    return DateResolution(check_in, check_out)
