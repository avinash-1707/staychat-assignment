from __future__ import annotations

from datetime import date

import pytest

from agent.config import load_inventory
from agent.schemas import Interpretation
from agent.state import InMemorySessionRepository
from app import create_app


FIXED_TODAY = date(2026, 9, 5)


class ScriptedInterpreter:
    """Offline interpreter fixture that drives the real service path."""

    def __init__(self, interpretations: list[Interpretation]) -> None:
        self.interpretations = interpretations

    def interpret(self, message, state, today):
        assert self.interpretations, f"Unexpected message: {message}"
        return self.interpretations.pop(0)


@pytest.fixture
def inventory():
    return load_inventory("inventory.json")


@pytest.fixture
def repository():
    return InMemorySessionRepository()


def app_for(interpretations: list[Interpretation], repository: InMemorySessionRepository | None = None):
    app = create_app(interpreter=ScriptedInterpreter(interpretations), today=FIXED_TODAY, repository=repository)
    app.config.update(TESTING=True)
    return app
