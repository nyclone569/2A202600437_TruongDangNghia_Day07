from __future__ import annotations

import math
import re


# ── FixedSizeChunker ──────────────────────────────────────────────────────────
# Cắt text thành các đoạn đều nhau theo số ký tự.
# overlap cho phép hai chunk liên tiếp chia sẻ một số ký tự để tránh mất ngữ cảnh
# ở ranh giới. Đây là chiến lược đơn giản nhất và dễ kiểm soát chunk count nhất.
class FixedSizeChunker:
    """
    Split text into fixed-size chunks with optional overlap.

    Rules:
        - Each chunk is at most chunk_size characters long.
        - Consecutive chunks share overlap characters.
        - The last chunk contains whatever remains.
        - If text is shorter than chunk_size, return [text].
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        # step = khoảng cách di chuyển cửa sổ mỗi vòng lặp (nhỏ hơn chunk_size đúng bằng overlap)
        step = self.chunk_size - self.overlap
        chunks: list[str] = []
        for start in range(0, len(text), step):
            chunk = text[start : start + self.chunk_size]
            chunks.append(chunk)
            # dừng sớm khi đã lấy hết text, tránh thêm chunk rỗng
            if start + self.chunk_size >= len(text):
                break
        return chunks


# ── SentenceChunker ───────────────────────────────────────────────────────────
# Cắt theo ranh giới câu thay vì ký tự, giữ nguyên ý nghĩa mỗi câu.
# Phù hợp với văn bản thông thường nơi mỗi câu là một đơn vị ngữ nghĩa độc lập.
class SentenceChunker:
    """
    Split text into chunks of at most max_sentences_per_chunk sentences.

    Sentence detection: split on ". ", "! ", "? " or ".\n".
    Strip extra whitespace from each chunk.
    """

    def __init__(self, max_sentences_per_chunk: int = 3) -> None:
        # đảm bảo ít nhất 1 câu/chunk, tránh giá trị âm hoặc 0
        self.max_sentences_per_chunk = max(1, max_sentences_per_chunk)

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        # tách câu dựa trên dấu kết thúc câu theo sau bởi khoảng trắng
        sentences = re.split(r'[.!?]\s', text)
        chunks = []
        # gom từng nhóm max_sentences_per_chunk câu thành một chunk
        for i in range(0, len(sentences), self.max_sentences_per_chunk):
            chunk = ' '.join(sentences[i:i + self.max_sentences_per_chunk])
            if chunk.strip():
                chunks.append(chunk.strip())
        return chunks


# ── RecursiveChunker ──────────────────────────────────────────────────────────
# Cắt đệ quy, ưu tiên cắt ở ranh giới tự nhiên nhất trước (đoạn văn → dòng → câu → từ).
# Nếu một phần vẫn còn quá lớn sau khi cắt, tiếp tục đệ quy với separator cấp thấp hơn.
# Đây là chiến lược linh hoạt nhất, bảo toàn cấu trúc tốt hơn FixedSizeChunker.
class RecursiveChunker:
    """
    Recursively split text using separators in priority order.

    Default separator priority:
        ["\n\n", "\n", ". ", " ", ""]
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(self, separators: list[str] | None = None, chunk_size: int = 500) -> None:
        self.separators = self.DEFAULT_SEPARATORS if separators is None else list(separators)
        self.chunk_size = chunk_size

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]
        # tìm separator phù hợp nhất (ưu tiên cao nhất) có mặt trong text
        for i, separator in enumerate(self.separators):
            if separator in text:
                return self._split(text, self.separators[i:])
        return [text]

    def _split(self, current_text: str, remaining_separators: list[str]) -> list[str]:
        # base case: text đã nhỏ đủ hoặc hết separator để thử
        if not current_text:
            return []
        if len(current_text) <= self.chunk_size:
            return [current_text]
        if not remaining_separators:
            return [current_text]

        separator = remaining_separators[0]
        if separator and separator in current_text:
            parts = current_text.split(separator)
            result: list[str] = []
            for part in parts:
                if part:
                    # mỗi phần con lại tiếp tục đệ quy với các separator còn lại
                    result.extend(self._split(part, remaining_separators[1:]))
            return result
        else:
            # separator hiện tại không tìm thấy, thử separator tiếp theo
            return self._split(current_text, remaining_separators[1:])


# ── Cosine Similarity ─────────────────────────────────────────────────────────
# Đo độ tương đồng ngữ nghĩa giữa hai vector embedding bằng góc giữa chúng.
# Giá trị 1.0 = giống hệt nhau, 0.0 = không liên quan, -1.0 = đối lập.

def _dot(a: list[float], b: list[float]) -> float:
    """Tích vô hướng (dot product) của hai vector."""
    return sum(x * y for x, y in zip(a, b))


def compute_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    cosine_similarity = dot(a, b) / (||a|| * ||b||)

    Returns 0.0 if either vector has zero magnitude.
    """
    norm_a = math.sqrt(_dot(vec_a, vec_a))
    norm_b = math.sqrt(_dot(vec_b, vec_b))
    # tránh chia cho 0 khi vector là zero vector
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return _dot(vec_a, vec_b) / (norm_a * norm_b)


# ── ChunkingStrategyComparator ────────────────────────────────────────────────
# Chạy cả ba chiến lược trên cùng một đoạn text và trả về thống kê để so sánh.
# Giúp đánh giá strategy nào phù hợp nhất cho từng loại tài liệu.
class ChunkingStrategyComparator:
    """Run all built-in chunking strategies and compare their results."""

    def compare(self, text: str, chunk_size: int = 200) -> dict:
        fixed_size_chunker = FixedSizeChunker(chunk_size=chunk_size)
        sentence_chunker = SentenceChunker(max_sentences_per_chunk=3)
        recursive_chunker = RecursiveChunker(separators=["\n\n", "\n", ". ", " ", ""], chunk_size=chunk_size)

        fixed_chunks = fixed_size_chunker.chunk(text)
        sentence_chunks = sentence_chunker.chunk(text)
        recursive_chunks = recursive_chunker.chunk(text)

        def stats(chunks: list[str]) -> dict:
            lengths = [len(c) for c in chunks]
            return {
                "count": len(chunks),
                "avg_length": sum(lengths) / len(lengths) if lengths else 0.0,
                "chunks": chunks,
            }

        return {
            "fixed_size": stats(fixed_chunks),
            "by_sentences": stats(sentence_chunks),
            "recursive": stats(recursive_chunks),
        }
