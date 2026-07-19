from fastapi import FastAPI, Depends, APIRouter

rec_questions_router = APIRouter(
    prefix="/api/v1/recommendations",
    tags=["recommendations"]
)

@rec_questions_router.post("/questions")
async def recommend_question():
    pass