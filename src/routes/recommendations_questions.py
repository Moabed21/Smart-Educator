"""FastAPI Router for Question Recommendations & Semantic Search.

Finds top-K most pedagogically relevant questions matching a search query
or student weakness concept using ChromaDB vector similarity search.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from crud.question_lo_links import get_links_by_question
from crud.questions import get_question_by_id
from helpers.db import get_db
from services.embedding_service import embed_text
from services.vector_store import VectorStoreService
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
    """
    Find top-K question recommendations for a search query using vector similarity.
    
    EXPLANATION OF THE VECTOR SEARCH & RECOMMENDATION FLOW:
    1. Validation: Ensures the search query is not blank.
    2. Embedding Generation (Google Gemini):
       - Converts natural language query (e.g. "Newton's second law acceleration")
         into a 3072-dimensional vector embedding via services/embedding_service.py.
    3. ChromaDB Nearest-Neighbor Query:
       - Queries collection `"questions"` for the top-K nearest question vectors.
       - Returns matched question IDs, vector distances, and embedded metadata.
    4. Distance-to-Similarity Conversion:
       - Transforms raw distance metric into an intuitive similarity score: 1.0 / (1.0 + distance).
    5. Database Hydration & Difficulty Filtering:
       - If metadata is incomplete in ChromaDB, queries PostgreSQL for full question text and LO links.
       - Filters by difficulty if requested by the client.
    6. Returns structured list of recommended questions ordered by relevance.
    """
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty.",
        )

    try:
        # Generate 3072-dim query embedding using Gemini Embeddings API (cached in Redis)
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

        # If ChromaDB metadata did not contain full text, hydrate from PostgreSQL
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

        # Apply difficulty filter if client specified one
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