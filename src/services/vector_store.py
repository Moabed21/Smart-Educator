import logging
import chromadb
from helpers.config import get_settings

logger = logging.getLogger("server.vector_store")


class VectorStoreService:
    def __init__(self):
        self._settings = get_settings()
        self._client: chromadb.HttpClient | None = None
        self._collection = None

    def _get_collection(self):
        """Lazily connects to ChromaDB on first use instead of at module import time."""
        if self._collection is None:
            if self._client is None:
                self._client = chromadb.HttpClient(
                    host=self._settings.CHROMA_HOST,
                    port=self._settings.CHROMA_PORT,
                )
            self._collection = self._client.get_or_create_collection(
                name=self._settings.CHROMA_COLLECTION_NAME
            )
        return self._collection

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
        if not ids:
            return
        collection = self._get_collection()
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(self, query_embedding: list[float], top_k: int = 5) -> dict:
        """
        Find the top_k questions whose embeddings are closest in meaning
        to the given query embedding.
        """
        collection = self._get_collection()
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

    def ping(self) -> bool:
        """Checks if ChromaDB server is reachable and responsive."""
        try:
            if self._client is None:
                self._client = chromadb.HttpClient(
                    host=self._settings.CHROMA_HOST,
                    port=self._settings.CHROMA_PORT,
                )
            return self._client.heartbeat() > 0
        except Exception as exc:
            logger.warning("ChromaDB heartbeat check failed: %s", exc)
            return False