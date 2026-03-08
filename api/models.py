from pydantic import BaseModel
from datetime import date, datetime


class ChangeEntry(BaseModel):
    period: str
    substantive: int
    non_substantive: int
    removals: int


class AgencySummary(BaseModel):
    slug: str
    name: str
    short_name: str | None
    word_count: int | None = None
    checksum: str | None = None
    computed_at: datetime | None = None


class AgencyDetail(AgencySummary):
    checksum_changed: bool | None = None
    word_count_change: int | None = None
    current_data_date: date | None = None
    previous_data_date: date | None = None
    change_history: list[ChangeEntry] = []


class PipelineStatus(BaseModel):
    last_run_at: datetime | None = None
    titles_processed: int = 0
    agencies_with_metrics: int = 0
