from typing import Any
from pydantic import BaseModel

class NewsFeedResponse(BaseModel):
    company_id: str
    company_name: str
    target_role: str
    total_events: int
    critical_events_count: int
    events: list[dict[str, Any]]
