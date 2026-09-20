# Modified for lakematch on 2026-09-20 from the APX 0.3.8 scaffold.
"""Review contracts. User, time and model provenance are assigned by the server."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["match", "no_match", "unsure"]


class PairOut(BaseModel):
    pair_id: str
    a_id: str
    b_id: str
    left: dict[str, str | None]
    right: dict[str, str | None]
    probability: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    model_version: str
    llm_decision: Decision | None = None
    impact: int = Field(default=2, ge=2)


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{8,80}$")
    pair_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_version: str = Field(min_length=1, max_length=200)
    decision: Decision
    reason: str = Field(min_length=1, max_length=1000)


class ReviewOut(ReviewIn):
    a_id: str
    b_id: str
    user: str
    reviewed_at: str


class SessionOut(BaseModel):
    user: str
    storage: Literal["sqlite", "delta"]
    genie_enabled: bool


class EvaluationOut(BaseModel):
    model_version: str
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    sample_size: int = Field(gt=0)
    context: str


class StatsOut(BaseModel):
    queue_depth: int
    reviewed: int
    match: int
    no_match: int
    unsure: int
    quarantine: int | None
    llm_compared: int
    llm_agreement: float | None
    evaluations: list[EvaluationOut]


class LabelOut(BaseModel):
    a_id: str
    b_id: str
    label: int


class SnapshotOut(BaseModel):
    labels: list[LabelOut]
    reviews: list[ReviewOut]
    label_set_sha256: str
    excluded_unsure: int
