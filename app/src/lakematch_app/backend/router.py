from typing import Annotated

from fastapi import HTTPException, Query

from . import review, stores
from .core import Dependencies, create_router
from .models import LabelIn, LabelOut, LabelsOut, NextOut, RetractIn, SessionOut, StatsOut, VersionOut
from .settings import settings

router = create_router()


def _reviewer(headers) -> str:
    """Databricks Apps: the signed-in user, set by the platform's proxy. Laptop: LAKEMATCH_APP_LOCAL_USER or the OS
    user."""
    return headers.user_email or headers.user_name or settings().local_reviewer()


def _stores():
    try:
        return stores.build(settings())
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/version", response_model=VersionOut, operation_id="version")
async def version():
    return VersionOut.from_metadata()


@router.get("/session", response_model=SessionOut, operation_id="session")
def session(headers: Dependencies.Headers):
    source, store = _stores()
    return SessionOut(reviewer=_reviewer(headers), source=source.describe(), label_store=store.describe(),
                      app_version=VersionOut.from_metadata().version)


@router.get("/queue/next", response_model=NextOut, operation_id="nextPairs")
def next_pairs(skip: Annotated[list[str] | None, Query()] = None, n: Annotated[int, Query(ge=1, le=20)] = 3):
    """The next `n` pairs to review, in queue order, without the labelled ones and those named in `skip`
    ("l_id|r_id", the pairs this browser tab skipped)."""
    source, store = _stores()
    skipped = {(s.split("|", 1)[0], s.split("|", 1)[1]) for s in (skip or []) if "|" in s}
    return NextOut(items=review.next_items(source, store, skipped, n))


@router.post("/labels", response_model=LabelOut, operation_id="addLabel")
def add_label(body: LabelIn, headers: Dependencies.Headers):
    source, store = _stores()
    try:
        return review.label(source, store, l_id=body.l_id, r_id=body.r_id, decision=body.decision,
                            reason=body.reason, reviewer=_reviewer(headers))
    except review.NotQueued as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/labels/retract", response_model=LabelOut, operation_id="retractLabel")
def retract_label(body: RetractIn, headers: Dependencies.Headers):
    source, store = _stores()
    try:
        return review.retract(source, store, l_id=body.l_id, r_id=body.r_id, reviewer=_reviewer(headers),
                              reason=body.reason)
    except review.NothingToUndo as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/labels", response_model=LabelsOut, operation_id="listLabels")
def list_labels(limit: Annotated[int, Query(ge=1, le=1000)] = 100):
    """The latest label rows, newest first, with their provenance."""
    _, store = _stores()
    rows = sorted(store.events(), key=lambda e: (e["labelled_at"], e["label_id"]), reverse=True)[:limit]
    return LabelsOut(labels=rows)


@router.get("/stats", response_model=StatsOut, operation_id="stats")
def get_stats():
    source, store = _stores()
    return review.stats(source, store)
