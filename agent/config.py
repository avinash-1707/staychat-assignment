from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from agent.schemas import Inventory


def load_inventory(path: str | Path) -> Inventory:
    """Fail startup rather than serving malformed hotel facts."""
    try:
        inventory = Inventory.model_validate(json.loads(Path(path).read_text()))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError("inventory.json is invalid") from exc
    if not inventory.rooms or any(room.max_occupancy < room.base_occupancy for room in inventory.rooms):
        raise RuntimeError("inventory.json has invalid room occupancy")
    return inventory
