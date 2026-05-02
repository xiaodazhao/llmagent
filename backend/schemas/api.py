from pydantic import BaseModel


class DailyReportRequest(BaseModel):
    date: str  # YYYY-MM-DD


class TimeWindowRequest(BaseModel):
    start_time: str
    end_time: str


class AgentRequest(BaseModel):
    query: str
    date: str | None = None
    use_llm: bool = False
    verbose: bool = False


class EvidenceImportRequest(BaseModel):
    paths: list[str]
    source_type: str | None = None
    dry_run: bool = False
    replace_existing: bool = False
    recursive: bool = False
