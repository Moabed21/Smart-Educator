from fastapi import FastAPI, APIRouter

dataset_router= APIRouter(
    prefix="/api/v1/dataset",
    tags=["dataset"]
)

@dataset_router.post("/generate")
async def generate():
    pass

@dataset_router.post("/evaluate")
async def evaluate():
    pass

@dataset_router.get("/export")
async def export():
    pass
