import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from controllers.CRUD_Operations.question_lo_links import get_links_by_question
from controllers.CRUD_Operations.questions import get_question_by_id
from helpers.db import get_db
from services.embedding_service import embed_text
from stores.vector.vector_store import VectorStoreService
from routes.schemes.recommended_questions import RecommendationRequest

rec_questions_router = APIRouter(
    prefix="/api/v1/recommendations",
    tags=["recommendations"]
)

@rec_questions_router.post("/questions")
async def recommend_question(
    payload: RecommendationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Find top-K question recommendations for a search query using vector similarity"""
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty.",
        )

    try:
        query_embedding = await embed_text(payload.query)
        vector_store = VectorStoreService()
        search_result = vector_store.search(query_embedding=query_embedding, top_k=payload.top_k)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector search failed: {exc}",
        )

    ids = search_result.get("ids", [[]])[0]
    distances = search_result.get("distances", [[]])[0]
    metadatas = search_result.get("metadatas", [[]])[0]

    recommendations = []
    for i, q_id_str in enumerate(ids):
        distance = distances[i] if i < len(distances) else 0.0
        similarity_score = 1.0 / (1.0 + float(distance))

        meta = metadatas[i] if i < len(metadatas) else {}

        question_text = meta.get("question_text", "")
        difficulty = meta.get("difficulty", payload.difficulty or "")
        lo_ids = meta.get("lo_ids", [])

        if not question_text:
            try:
                q_uuid = uuid.UUID(q_id_str)
                orm_q = await get_question_by_id(db, q_uuid)
                if orm_q:
                    question_text = orm_q.question_text
                    difficulty = orm_q.difficulty
                    links = await get_links_by_question(db, orm_q.id)
                    lo_ids = [str(link.lo_id) for link in links]
            except Exception:
                pass

        if payload.difficulty and difficulty and difficulty != payload.difficulty:
            continue

        recommendations.append({
            "question_id": q_id_str,
            "question_text": question_text,
            "similarity_score": round(similarity_score, 4),
            "difficulty": difficulty,
            "learning_outcome_ids": lo_ids,
        })

    return {
        "query": payload.query,
        "recommendations": recommendations,
    }