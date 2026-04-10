from __future__ import annotations

from typing import Any, Callable

from .chunking import _dot
from .embeddings import _mock_embed
from .models import Document


# ── EmbeddingStore ────────────────────────────────────────────────────────────
# Vector store lưu trữ các document chunk kèm embedding của chúng.
# Hỗ trợ hai backend:
#   - ChromaDB (nếu đã cài): persistent, có index nhanh hơn ở scale lớn
#   - In-memory list (fallback): đủ dùng cho test và demo nhỏ
# Mọi thao tác search đều dựa trên dot product giữa query embedding và chunk embedding.
class EmbeddingStore:
    """
    A vector store for text chunks.

    Tries to use ChromaDB if available; falls back to an in-memory store.
    The embedding_fn parameter allows injection of mock embeddings for tests.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        embedding_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._embedding_fn = embedding_fn or _mock_embed
        self._collection_name = collection_name
        self._use_chroma = False
        # _store là nguồn sự thật duy nhất cho cả hai backend (dùng để filter, delete)
        self._store: list[dict[str, Any]] = []
        self._collection = None
        self._next_index = 0

        # thử khởi tạo ChromaDB; nếu lỗi thì dùng in-memory
        try:
            import chromadb  # noqa: F401
            import chromadb.config

            client_settings = chromadb.config.Settings(anonymized_telemetry=False)
            self._chroma_client = chromadb.Client(client_settings)
            self._collection = self._chroma_client.get_or_create_collection(name=collection_name)
            self._use_chroma = True
        except Exception:
            self._use_chroma = False
            self._collection = None

    def _make_record(self, doc: Document) -> dict[str, Any]:
        """Embed nội dung document và đóng gói thành record để lưu vào store."""
        embedding = self._embedding_fn(doc.content)
        return {
            "content": doc.content,
            "embedding": embedding,
            "metadata": dict(doc.metadata),
            "doc_id": doc.id,
        }

    def _search_records(self, query: str, records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        """Tính dot product giữa query embedding và mỗi record, trả về top_k cao nhất."""
        query_embedding = self._embedding_fn(query)
        scored = []
        for record in records:
            score = _dot(query_embedding, record["embedding"])
            scored.append({**record, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    # ── add_documents ─────────────────────────────────────────────────────────
    # Embed từng document và lưu vào store. Nếu dùng ChromaDB thì batch add
    # để tối ưu performance; nếu không thì append thẳng vào list.
    def add_documents(self, docs: list[Document]) -> None:
        if self._use_chroma and self._collection is not None:
            ids: list[str] = []
            documents: list[str] = []
            embeddings: list[list[float]] = []
            for doc in docs:
                rec = self._make_record(doc)
                # record_id ghép doc_id + index để đảm bảo unique trong Chroma
                record_id = f"{doc.id}_{self._next_index}"
                self._next_index += 1
                ids.append(record_id)
                documents.append(rec["content"])
                embeddings.append(rec["embedding"])
                rec["record_id"] = record_id
                self._store.append(rec)
            self._collection.add(ids=ids, documents=documents, embeddings=embeddings)
        else:
            for doc in docs:
                rec = self._make_record(doc)
                rec["record_id"] = str(self._next_index)
                self._next_index += 1
                self._store.append(rec)

    # ── search ────────────────────────────────────────────────────────────────
    # Embed query rồi tìm các chunk gần nhất theo similarity.
    # ChromaDB trả về L2 distance nên cần convert sang similarity score.
    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if self._use_chroma and self._collection is not None:
            query_embedding = self._embedding_fn(query)
            results = self._collection.query(query_embeddings=[query_embedding], n_results=top_k)
            scored = []
            for i in range(len(results["ids"][0])):
                rid = results["ids"][0][i]
                distance = results["distances"][0][i]
                # ChromaDB returns L2 distance. Convert to cosine-similarity-like score.
                # For unit vectors: cosine_sim = 1 - d^2 / 2
                score = 1.0 - (distance * distance) / 2.0
                for record in self._store:
                    if record.get("record_id") == rid:
                        scored.append({**record, "score": score})
                        break
            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored
        return self._search_records(query, self._store, top_k)

    def get_collection_size(self) -> int:
        """Trả về tổng số chunk hiện đang lưu trong store."""
        return len(self._store)

    # ── search_with_filter ────────────────────────────────────────────────────
    # Filter metadata trước để thu hẹp không gian tìm kiếm, sau đó mới search.
    # Hữu ích khi muốn giới hạn kết quả theo category, source, date, v.v.
    def search_with_filter(self, query: str, top_k: int = 3, metadata_filter: dict = None) -> list[dict]:
        if metadata_filter:
            # chỉ giữ record có tất cả các field trong filter khớp với giá trị mong muốn
            filtered = [
                r for r in self._store
                if all(r["metadata"].get(k) == v for k, v in metadata_filter.items())
            ]
        else:
            filtered = self._store
        return self._search_records(query, filtered, top_k)

    # ── delete_document ───────────────────────────────────────────────────────
    # Xóa tất cả chunk thuộc về một doc_id khỏi store.
    # ChromaDB không hỗ trợ delete by metadata nên phải rebuild toàn bộ collection.
    def delete_document(self, doc_id: str) -> bool:
        original_len = len(self._store)
        self._store = [r for r in self._store if r.get("doc_id") != doc_id]
        removed = original_len - len(self._store)
        if self._use_chroma and self._collection is not None:
            # xóa collection cũ và tạo lại từ _store đã được lọc
            self._chroma_client.delete_collection(name=self._collection_name)
            self._collection = self._chroma_client.get_or_create_collection(name=self._collection_name)
            for record in self._store:
                self._collection.add(
                    ids=[record["record_id"]],
                    documents=[record["content"]],
                    embeddings=[record["embedding"]],
                )
        return removed > 0
