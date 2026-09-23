from .core import create_app
from .router import router
from .mastering import router as mastering_router, MasteringAPI, MasteringBoundaryMiddleware


def create_review_app(mastering_api: MasteringAPI | None = None):
    instance = create_app(routers=[router, mastering_router])
    instance.state.mastering_api = mastering_api
    instance.add_middleware(MasteringBoundaryMiddleware)
    return instance


app = create_review_app()
