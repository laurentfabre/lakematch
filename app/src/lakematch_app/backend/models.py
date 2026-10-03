from typing import Literal

from pydantic import BaseModel, Field

from .. import __version__


class VersionOut(BaseModel):
    version: str

    @classmethod
    def from_metadata(cls):
        return cls(version=__version__)


class SessionOut(BaseModel):
    reviewer: str
    source: str
    label_store: str
    app_version: str


class FieldOut(BaseModel):
    name: str
    left: str | None = None
    right: str | None = None
    same: bool


class QueueItemOut(BaseModel):
    rank: int
    l_id: str
    r_id: str
    p: float
    threshold: float
    distance: float
    queue_reason: str
    llm_label: str | None = None
    llm_p_same: float | None = None
    linked: bool
    impact: int | None = None
    cand_score: float | None = None
    cand_rank: int | None = None
    model_version: str
    run_id: str
    fields: list[FieldOut]


class NextOut(BaseModel):
    items: list[QueueItemOut]


class LabelIn(BaseModel):
    l_id: str = Field(min_length=1)
    r_id: str = Field(min_length=1)
    decision: Literal["match", "no_match", "unsure"]
    reason: str = Field(min_length=1, max_length=500)


class RetractIn(BaseModel):
    l_id: str = Field(min_length=1)
    r_id: str = Field(min_length=1)
    reason: str = ""


class LabelOut(BaseModel):
    l_id: str
    r_id: str
    decision: str
    is_match: float | None = None
    reviewer: str
    labelled_at: str
    model_version: str | None = None
    p: float | None = None
    threshold: float | None = None
    reason: str
    queue_reason: str | None = None
    llm_label: str | None = None
    run_id: str | None = None
    label_id: str


class LabelsOut(BaseModel):
    labels: list[LabelOut]


class LabelStatsOut(BaseModel):
    events: int
    retracted: int
    current: dict[str, int]
    by_reviewer: dict[str, int]
    complete_provenance: int


class AgreementOut(BaseModel):
    pairs: int
    agree: int
    rate: float | None = None
    confusion: dict[str, int]
    llm_unsure_on_labelled: int
    llm_opinions_in_queue: int


class ModelVersionOut(BaseModel):
    model_version: str
    run_id: str | None = None
    created_at: str | None = None
    threshold: float | None = None
    evaluation: str | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    label_source: str | None = None
    app_labels_used: int | None = None
    labels_train: int | None = None
    human_labelled: int
    human_precision: float | None = None
    human_recall: float | None = None


class QueueDepthOut(BaseModel):
    total: int
    pending: int
    labelled: int
    pending_by_reason: dict[str, int]
    total_by_reason: dict[str, int]
    model_version: str | None = None


class QuarantineRunOut(BaseModel):
    run_id: str
    model_version: str
    created_at: str | None = None
    left: int
    right: int


class QuarantineOut(BaseModel):
    latest: QuarantineRunOut | None = None
    history: list[QuarantineRunOut]


class StatsOut(BaseModel):
    labels: LabelStatsOut
    agreement: AgreementOut
    model_versions: list[ModelVersionOut]
    queue: QueueDepthOut
    quarantine: QuarantineOut


class GenieConfigOut(BaseModel):
    enabled: bool
    space_id: str | None = None
    auth: str


class GenieAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None


class GenieAnswerOut(BaseModel):
    asked_as: str
    auth: str
    conversation_id: str | None = None
    status: str | None = None
    sql: str | None = None
    text: str | None = None
    columns: list[str]
    rows: list[list[str | None]]
    error: str | None = None
