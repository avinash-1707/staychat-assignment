from __future__ import annotations

from agent.schemas import BookingState, Child, Interpretation, Recommendation


def merge_updates(state: BookingState, interpretation: Interpretation) -> tuple[bool, str | None]:
    """Apply only explicit, validated candidate facts from the interpreter."""
    changed = False
    for field in interpretation.clear_fields:
        if field in {"check_in", "check_out", "adults", "requested_rooms", "selected_recommendation_id"} and getattr(state, field) is not None:
            setattr(state, field, None)
            changed = True
        elif field == "children" and state.children:
            state.children = []
            changed = True
    for field, value in interpretation.updates.items():
        if field == "adults":
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 54:
                return changed, "Please provide a valid adult or party count."
        elif field == "requested_rooms":
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 15:
                return changed, "Please provide a valid number of rooms."
        elif field == "ac_preference":
            if value not in {"AC", "NON_AC", "ANY"}:
                return changed, "Please specify AC, non-AC, or any room type."
        elif field == "children":
            if not isinstance(value, list) or len(value) > 20:
                return changed, "Please provide valid child ages."
            children: list[Child] = []
            for age in value:
                if age is not None and (not isinstance(age, int) or isinstance(age, bool) or not 0 <= age <= 17):
                    return changed, "Please provide child ages between 0 and 17."
                children.append(Child(age))
            value = children
        elif field == "special_requests":
            if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                return changed, "Please provide a valid special request."
            value = list(dict.fromkeys(state.special_requests + [item.strip() for item in value]))
        else:
            continue
        if getattr(state, field) != value:
            setattr(state, field, value)
            changed = True
    return changed, None


def missing_question(state: BookingState) -> str | None:
    if state.check_in is None:
        return "What is your check-in date?"
    if state.adults is None:
        return "How many adults or total guests will be staying?"
    if any(child.age is None for child in state.children):
        return "How old are the children? Their ages can affect the quote."
    if state.check_out is None:
        return "What is your check-out date?"
    return None


def selected_recommendation(interpretation: Interpretation, recommendations: list[Recommendation]) -> Recommendation | None:
    if interpretation.selected_option_number and interpretation.selected_option_number <= len(recommendations):
        return recommendations[interpretation.selected_option_number - 1]
    if interpretation.selected_room_description:
        needle = interpretation.selected_room_description.lower()
        matches = [item for item in recommendations if any(needle in room.type.lower() for room in item.rooms)]
        if len(matches) == 1:
            return matches[0]
    return None


def recommendation_reply(state: BookingState, recommendations: list[Recommendation]) -> str:
    first = recommendations[0]
    rooms = ", ".join(f"{room.quantity} x {room.type}" for room in first.rooms)
    return f"For {state.check_in:%d %b} to {state.check_out:%d %b}, I recommend {rooms}. Total: Rs. {first.total_price:,} for {first.nights} night(s). Would you like to book this option?"


def has_booking_context(state: BookingState) -> bool:
    return any((state.check_in, state.adults is not None, state.requested_rooms is not None, state.children))
