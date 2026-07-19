from fastapi import FastAPI, Depends, APIRouter


training_pairs_router = APIRouter(
    prefix="/api/v1/training-pairs",
    tags=["training-pairs"]
    )


@training_pairs_router.post("/build")
async def build_training_pairs():
    pass
