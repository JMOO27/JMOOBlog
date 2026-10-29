from datetime import datetime, timezone
from pydantic import BaseModel, field_validator

class BlogEntry(BaseModel):
    blog_id: int
    blog_type: str # will either be blog or project
    title: str
    content: str
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        # SQLite CURRENT_TIMESTAMP stores UTC without a timezone suffix.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
