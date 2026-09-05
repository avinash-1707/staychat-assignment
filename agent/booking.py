from __future__ import annotations

from itertools import product

from agent.schemas import BookingState, Inventory, Recommendation, RoomRecommendation, RoomType


def build_recommendations(state: BookingState, inventory: Inventory) -> list[Recommendation]:
    if state.check_in is None or state.check_out is None or state.adults is None:
        return []
    people = state.adults + len(state.children)
    billable_people = state.adults + sum(child.age is not None and child.age >= 5 for child in state.children)
    eligible = [room for room in inventory.rooms if state.ac_preference == "ANY" or (room.ac if state.ac_preference == "AC" else not room.ac)]
    if not eligible or people <= 0:
        return []
    candidates: list[tuple[tuple[object, ...], Recommendation]] = []
    ranges = [range(room.available_rooms + 1) for room in eligible]
    nights = (state.check_out - state.check_in).days
    for counts in product(*ranges):
        room_count = sum(counts)
        if room_count == 0 or (state.requested_rooms is not None and room_count != state.requested_rooms):
            continue
        capacity = sum(room.max_occupancy * count for room, count in zip(eligible, counts))
        if capacity < people:
            continue
        extras = _cheapest_extra_beds(eligible, counts, billable_people)
        if extras is None:
            continue
        rooms: list[RoomRecommendation] = []
        nightly_paise = 0
        lexical: list[str] = []
        for room, count, extra_beds in zip(eligible, counts, extras):
            if not count:
                continue
            rooms.append(RoomRecommendation(type=room.type, quantity=count, extra_beds=extra_beds))
            # Prices are stored and calculated as integer paise; inventory values are whole INR demo rates.
            nightly_paise += count * room.base_price * 100 + extra_beds * room.extra_bed_price * 100
            lexical.extend([room.type] * count)
        recommendation = Recommendation(
            id="", rooms=rooms, nightly_price=nightly_paise // 100, nights=nights,
            total_price=(nightly_paise * nights) // 100, currency=inventory.currency,
            total_capacity=capacity, unused_capacity=capacity - people,
        )
        rank = (room_count if state.requested_rooms is None else 0, capacity - people, sum(extras), recommendation.total_price, tuple(sorted(lexical)))
        candidates.append((rank, recommendation))
    candidates.sort(key=lambda item: item[0])
    result: list[Recommendation] = []
    seen: set[tuple[tuple[str, int, int], ...]] = set()
    for _, recommendation in candidates:
        key = tuple((room.type, room.quantity, room.extra_beds) for room in recommendation.rooms)
        if key not in seen:
            seen.add(key)
            recommendation.id = f"rec-{len(result) + 1}"
            result.append(recommendation)
        if len(result) == 3:
            break
    return result


def _cheapest_extra_beds(rooms: list[RoomType], counts: tuple[int, ...], billable_people: int) -> list[int] | None:
    slots: list[tuple[int, int]] = []
    for index, (room, count) in enumerate(zip(rooms, counts)):
        for _ in range(count):
            slots.extend((0, index) for _ in range(room.base_occupancy))
            slots.extend((room.extra_bed_price * 100, index) for _ in range(room.max_occupancy - room.base_occupancy))
    if len(slots) < billable_people:
        return None
    slots.sort()
    extras = [0] * len(rooms)
    for cost, index in slots[:billable_people]:
        if cost:
            extras[index] += 1
    return extras
