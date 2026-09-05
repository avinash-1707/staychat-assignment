from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class RoomType(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    ac: bool
    base_occupancy: int = Field(ge=1)
    max_occupancy: int = Field(ge=1)
    base_price: int = Field(ge=0)
    extra_bed_price: int = Field(ge=0)
    available_rooms: int = Field(ge=0)


class Inventory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hotel_id: str
    hotel_name: str
    currency: str
    check_in_time: str
    check_out_time: str
    rooms: List[RoomType]
    policies: Dict[str, Union[str, bool]]


@dataclass
class Child:
    age: Optional[int] = None


@dataclass
class BookingState:
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    adults: Optional[int] = None
    children: List[Child] = field(default_factory=list)
    requested_rooms: Optional[int] = None
    ac_preference: Literal["AC", "NON_AC", "ANY"] = "ANY"
    special_requests: List[str] = field(default_factory=list)
    selected_recommendation_id: Optional[str] = None
    status: Literal["gathering", "recommending", "confirmed"] = "gathering"


class Interpretation(BaseModel):
    """Untrusted candidate facts; absent update keys intentionally mean no change."""

    model_config = ConfigDict(extra="forbid")
    intent: Literal["booking_update", "option_question", "selection", "confirmation", "general_question", "greeting", "unclear"] = "unclear"
    updates: Dict[str, object] = Field(default_factory=dict)
    date_expressions: List[str] = Field(default_factory=list)
    explicit_dates: Dict[str, Optional[str]] = Field(default_factory=dict)
    clear_fields: List[str] = Field(default_factory=list)
    general_question_topics: List[str] = Field(default_factory=list)
    selected_option_number: Optional[int] = Field(default=None, ge=1, le=3)
    selected_room_description: Optional[str] = None
    confirmation: bool = False
    ambiguities: List[str] = Field(default_factory=list)


class RoomRecommendation(BaseModel):
    type: str
    quantity: int
    extra_beds: int


class Recommendation(BaseModel):
    id: str
    rooms: List[RoomRecommendation]
    nightly_price: int
    nights: int
    total_price: int
    currency: str
    total_capacity: int
    unused_capacity: int


def public_state(state: BookingState) -> dict[str, object]:
    return {
        "check_in": state.check_in.isoformat() if state.check_in else None,
        "check_out": state.check_out.isoformat() if state.check_out else None,
        "adults": state.adults,
        "children": [{"age": child.age} for child in state.children],
        "requested_rooms": state.requested_rooms,
        "ac_preference": state.ac_preference,
        "special_requests": state.special_requests,
        "selected_recommendation_id": state.selected_recommendation_id,
    }
