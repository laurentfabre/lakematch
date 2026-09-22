# Modified for lakematch on 2026-09-20 from the APX 0.3.8 scaffold.
from typing import Annotated, Literal
from uuid import UUID
import os
from fastapi import Depends, HTTPException, Query, Request
from .core import Dependencies, create_router
from .models import PairOut, ReviewIn, ReviewOut, SessionOut, SnapshotOut, StatsOut
from .store import Conflict, DeltaStore, SQLiteStore, Store
from . import golden_demo

router = create_router()


def get_store(config: Dependencies.Config, request: Request):
    store = (SQLiteStore(config.database) if config.store == "sqlite" else
             DeltaStore(request.app.state.workspace_client, config.warehouse_id, config.schema_name))
    try:
        yield store
    finally:
        store.close()


Storage = Annotated[Store, Depends(get_store)]


def get_actor(config: Dependencies.Config, headers: Dependencies.Headers):
    if not os.environ.get("DATABRICKS_APP_NAME"):
        if config.store == "sqlite":
            return config.local_user
        raise HTTPException(401, "Delta reviews require a deployed Databricks Apps session")
    # Identity headers are supplied by the Databricks Apps authenticated proxy.
    if not headers.user_id or not headers.user_name:
        raise HTTPException(401, "An authenticated Databricks Apps session is required")
    return headers.user_name


Actor = Annotated[str, Depends(get_actor)]


def get_demo():
    try:
        return golden_demo.read_demo()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "The packaged company demo is unavailable. Rebuild the app to restore it.") from exc


Demo = Annotated[golden_demo.DemoBundle, Depends(get_demo)]


@router.get("/demo/golden-records", response_model=golden_demo.DemoCatalogOut, operation_id="goldenDemoCatalog")
def golden_demo_catalog(demo: Demo, actor: Actor):
    return golden_demo.catalog(demo)


@router.get("/demo/golden-records/{master_id}", response_model=golden_demo.DemoDetailOut, operation_id="goldenDemoDetail")
def golden_demo_detail(master_id: UUID, demo: Demo, actor: Actor, publication: Literal["first", "second"] = "second"):
    result = golden_demo.detail(demo, str(master_id), publication)
    if result is None:
        raise HTTPException(404, "Company is not in this synthetic demo")
    return result


@router.get("/session", response_model=SessionOut, operation_id="session")
def session(config: Dependencies.Config, actor: Actor):
    return SessionOut(user=actor, storage=config.store, genie_enabled=config.genie_enabled)


@router.get("/queue", response_model=list[PairOut], operation_id="reviewQueue")
def queue(store: Storage, actor: Actor, limit: int = Query(20, ge=1, le=100)):
    return store.queue(limit)


@router.post("/reviews", response_model=ReviewOut, operation_id="saveReview")
def review(body: ReviewIn, store: Storage, actor: Actor):
    try:
        return store.review(body, actor)
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/reviews", response_model=list[ReviewOut], operation_id="reviewHistory")
def history(store: Storage, actor: Actor):
    return store.reviews()


@router.get("/statistics", response_model=StatsOut, operation_id="reviewStats")
def statistics(store: Storage, actor: Actor):
    return store.stats()


@router.get("/training-labels", response_model=SnapshotOut, operation_id="trainingLabels")
def training_labels(store: Storage, actor: Actor):
    try:
        return store.snapshot()
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
