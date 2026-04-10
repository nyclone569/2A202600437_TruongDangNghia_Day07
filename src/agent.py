from typing import Callable

from .store import EmbeddingStore


# ── KnowledgeBaseAgent ────────────────────────────────────────────────────────
# Implement pattern RAG (Retrieval-Augmented Generation):
#   1. Dùng EmbeddingStore để tìm các chunk liên quan đến câu hỏi
#   2. Ghép các chunk đó thành context trong prompt
#   3. Gọi LLM để sinh câu trả lời dựa trên context đó
#
# Lý do dùng RAG: LLM không biết tài liệu nội bộ của chúng ta, nhưng nếu cung cấp
# đúng đoạn văn bản liên quan vào prompt thì LLM có thể trả lời chính xác.
class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self._store = store
        # llm_fn được inject từ ngoài vào để dễ test (có thể dùng mock thay vì gọi API thật)
        self._llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        # bước 1: retrieve — lấy top_k chunk gần nhất với câu hỏi
        results = self._store.search(question, top_k=top_k)

        # bước 2: format context — thêm doc_id vào mỗi chunk để LLM biết nguồn gốc
        context_chunks = []
        for r in results:
            chunk_text = r.get("content", "")
            doc_id = r.get("doc_id", "")
            context_chunks.append(f"[Doc: {doc_id}] {chunk_text}")
        context = "\n\n".join(context_chunks)

        # bước 3: build prompt — đặt context trước câu hỏi để LLM ưu tiên dùng thông tin đó
        prompt = (
            "You are a helpful assistant. Use the following context to answer the question.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )
        return self._llm_fn(prompt)
