from datetime import date

from agent.booking import build_recommendations
from agent.schemas import BookingState, Child


def state(**overrides):
    values = {"check_in": date(2026, 9, 15), "check_out": date(2026, 9, 17), "adults": 4, "children": [], "ac_preference": "AC"}
    values.update(overrides)
    return BookingState(**values)


def test_pricing_and_requested_room_count(inventory):
    recommendations = build_recommendations(state(requested_rooms=2), inventory)
    assert 1 <= len(recommendations) <= 3
    first = recommendations[0]
    assert sum(room.quantity for room in first.rooms) == 2
    assert all(room.type != "Standard Non-AC" for room in first.rooms)
    assert first.nights == 2
    assert first.total_price == first.nightly_price * 2
    assert first.nightly_price == 5000


def test_children_count_for_capacity_and_billable_extra_beds(inventory):
    free_child = build_recommendations(state(adults=2, children=[Child(4)], ac_preference="NON_AC"), inventory)[0]
    billable_child = build_recommendations(state(adults=2, children=[Child(5)], ac_preference="NON_AC"), inventory)[0]
    assert free_child.total_capacity >= 3
    assert free_child.rooms[0].extra_beds == 0
    assert free_child.nightly_price == 1500
    assert billable_child.rooms[0].extra_beds == 1
    assert billable_child.nightly_price == 2000


def test_ranking_is_stable_deduplicated_and_bounded(inventory):
    recommendations = build_recommendations(state(adults=7, ac_preference="ANY"), inventory)
    assert len(recommendations) == len({item.id for item in recommendations}) <= 3
    assert recommendations == build_recommendations(state(adults=7, ac_preference="ANY"), inventory)
    assert recommendations == sorted(recommendations, key=lambda item: (sum(room.quantity for room in item.rooms), item.unused_capacity, sum(room.extra_beds for room in item.rooms), item.total_price, tuple(room.type for room in item.rooms)))


def test_impossible_requested_rooms_and_party_return_no_combination(inventory):
    assert build_recommendations(state(adults=10, requested_rooms=1), inventory) == []
    assert build_recommendations(state(adults=55, ac_preference="ANY"), inventory) == []
