import chromadb
from helpers.config import get_settings

settings = get_settings()

# Single shared client for the whole app lifetime — connects to the
# ChromaDB container over HTTP (host/port from .env).
_client = chromadb.HttpClient(
    host=settings.CHROMA_HOST,
    port=settings.CHROMA_PORT,
)

# One collection holds all question embeddings + their metadata.
_collection = _client.get_or_create_collection(name="questions")


class VectorStoreService:
    def upsert_questions(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """
        Insert or update question embeddings in the vector store.
        - ids: question_id for each question (as strings)
        - embeddings: the embedding vector for each question
        - metadatas: extra info per question (difficulty, lo_ids, subject...)
        """
        _collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(self, query_embedding: list[float], top_k: int = 5) -> dict:
        """
        Find the top_k questions whose embeddings are closest in meaning
        to the given query embedding.
        """
        return _collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )