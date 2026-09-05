from __future__ import annotations

from agent.schemas import Inventory


def answer_policy(topics: list[str], inventory: Inventory) -> str | None:
    if not topics:
        return None
    topic = topics[0]
    if topic == "early_check_in":
        return f"Early check-in is {inventory.policies['early_check_in']}."
    if topic == "cancellation":
        return f"Cancellation is {inventory.policies['cancellation']}."
    if topic == "check_in_time":
        return f"Check-in time is {inventory.check_in_time}."
    if topic == "check_out_time":
        return f"Check-out time is {inventory.check_out_time}."
    return "The provided hotel details do not confirm that facility or policy."
