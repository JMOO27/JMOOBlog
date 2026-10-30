from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


class _TimestampedModel(BaseModel):
    """Keep database timestamps in UTC; format dates only when displaying them."""

    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        # SQLite CURRENT_TIMESTAMP stores UTC without a timezone suffix.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Topic(_TimestampedModel):
    """A named collection of posts whose identity survives title changes."""

    id: int = Field(gt=0)
    title: str
    description: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A topic title cannot be empty or whitespace-only.")
        return value


class BlogPost(_TimestampedModel):
    """A post belongs to exactly one topic, referenced by its stable ID."""

    id: int = Field(gt=0)
    topic_id: int = Field(gt=0)
    title: str
    content: str
    description: str | None = None
