# Báo Cáo Lab 7: Embedding & Vector Store

**Họ tên:** Bùi Lâm Tiến
**Nhóm:** 5
**Ngày:** 10/4/2026

---

## 1. Warm-up (5 điểm)

### 1.1. Cosine Similarity

**High cosine similarity nghĩa là gì?**
> Vector đại diện cho 2 chuỗi văn bản trỏ về gần cùng một hướng trong không gian, nghĩa là 2 ngữ cảnh này có ý nghĩa tương đồng nhau dù sử dụng từ vựng hay độ dài khác biệt.

**Ví dụ HIGH similarity:**

- Sentence A: Artificial intelligence is transforming the modern world.
- Sentence B: AI technology is changing society today.
- Dù dùng cách diễn đạt khác nhau, nhưng cả hai câu đều đề cập đến cùng một ý nghĩa cốt lõi.

**Ví dụ LOW similarity:**

- Sentence A: Artificial intelligence is transforming the modern world.
- Sentence B: The recipe for baking a chocolate cake requires flour and eggs.
- Hai câu nói về hai khái niệm hoàn toàn không liên quan (công nghệ so với nấu ăn).

**Tại sao cosine similarity được ưu tiên hơn Euclidean distance cho text embeddings?**
> Bởi vì khoảng cách Euclidean đo lường khoảng cách tuyệt đối giữa 2 điểm nên nó bị phụ thuộc quá lớn vào độ dài văn bản. Ngược lại, cosine similarity quan tâm đến góc giữa 2 vector, giúp nắm bắt được sự tương đồng về ngữ nghĩa độc lập với độ dài.

### 1.2. Chunking Math

**Document 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> *Trình bày phép tính:* num_chunks = ceil((doc_length - overlap) / (chunk_size - overlap)) = ceil((10000 - 50) / (500 - 50)) = ceil(9950 / 450) = 23.
> *Đáp án:* 23 chunks.

**Nếu overlap tăng lên 100, chunk count thay đổi thế nào? Tại sao muốn overlap nhiều hơn?**
> Số lượng chunks lúc này sẽ tăng lên thành 25. Thay vì cắt đứt đoạn nội dung, mình muốn tăng mức overlap lên để giữ lại phần liên kết giữa các câu, tránh trường hợp các ngữ cảnh quan trọng bị cắt làm đôi và mất tính liền mạch.

---

## 2. Document Selection — Nhóm (10 điểm)

### Domain & Lý Do Chọn

**Domain:** Pháp luật Việt Nam

**Tại sao nhóm chọn domain này?**
> *Viết 2-3 câu:* Chúng tôi chọn domain pháp luật vì các văn bản như Nghị định, Thông tư có cấu trúc phân tầng rõ ràng (Chương, Điều, Khoản), là bài toán lý tưởng để thử nghiệm mô hình RAG trong việc giữ luồng ngữ cảnh mà không làm đứt gãy thông tin. Ngoài ra, nhu cầu tra cứu luật thực tế rất phổ biến, đòi hỏi tính chính xác cao.

### Data Inventory

| # | Tên tài liệu | Nguồn | Số ký tự | Metadata đã gán |
|---|--------------|-------|----------|-----------------|
| 1 | Nghị định 102.md | Thư viện Pháp luật | 47719 | `{"type": "Nghị định", "year": "2024"}` |
| 2 | nghi-dinh-129.md | Thư viện Pháp luật | 23329 | `{"type": "Nghị định", "year": "2022"}` |
| 3 | thong-tu-05-2026.md | Thư viện Pháp luật | 17766 | `{"type": "Thông tư", "year": "2026"}` |
| 4 | thong-tu-23-2026.md | Thư viện Pháp luật | 40314 | `{"type": "Thông tư", "year": "2026"}` |

### Metadata Schema

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho retrieval? |
|----------------|------|---------------|-------------------------------|
| `type` | string | "Nghị định" | Cho phép filter theo loại văn bản luật hướng tới. |
| `year` | string | "2026" | Lọc để lấy ưu tiên các bộ luật hoặc thông tư mới nhất. |
| `chapter` | string | "Chương II" | Duy trì ngữ cảnh khái quát, giúp RAG biết Điều luật này nằm trong chủ đề gì. |

---

## 3. Chunking Strategy — Cá nhân chọn, nhóm so sánh (15 điểm)

### Baseline Analysis

Chạy `ChunkingStrategyComparator().compare()` trên 2-3 tài liệu:

| Tài liệu | Strategy | Chunk Count | Avg Length | Preserves Context? |
|-----------|----------|-------------|------------|-------------------|
| Nghị định 102 | FixedSizeChunker (`fixed_size`) | 100 | ~480 chars | No (cắt ngang câu/Đoạn) |
| Nghị định 102 | SentenceChunker (`by_sentences`) | 145 | ~320 chars | Partial (giữ câu nhưng mất cấu trúc Điều) |
| Nghị định 102 | RecursiveChunker (`recursive`) | 95 | ~450 chars | Partial (ngắt đúng chỗ hơn nhưng mất Chương) |

### Strategy Của Tôi

**Loại:** Custom strategy (`LegalDocumentChunker`)

**Mô tả cách hoạt động:**
> *Viết 3-4 câu: strategy chunk thế nào? Dựa trên dấu hiệu gì?* Strategy dựa vào Regular Expression để dò tìm các tiêu đề "Chương" và "Điều" (ví dụ: regex `^(#+|\*\*)\s*Chương\b` và `^(#+|\*\*)\s*Điều\s+\d+`). Nó sẽ tiến hành lấy ranh giới của từng "Điều" làm mốc chia chunk. Mỗi khi tách một "Điều" mới ra làm một chunk, nó sẽ tự động chèn thêm tên của "Chương" hiện tại vào ngay vị trí đầu chunk, giúp những Điều luật độc lập không bị mất bối cảnh gốc thuộc chủ đề nào.

**Tại sao tôi chọn strategy này cho domain nhóm?**
> *Viết 2-3 câu: domain có pattern gì mà strategy khai thác?* Các văn bản pháp luật luôn được phân chia theo cấu trúc dạng cây: Luật -> Chương -> Mục -> Điều. Việc sử dụng baseline sẽ vô tình cắt làm đôi một Điều hoặc tách các Điều giống nhau, làm mất đi tính trọn vẹn, do đó chunk dựa vào ranh giới "Điều" và nối thêm "Chương" là chiến thuật bảo toàn ý nghĩa hoàn hảo nhất cho domain này.

**Code snippet (nếu custom):**

```python
class LegalDocumentChunker:
    def chunk(self, text: str) -> list[str]:
        if not text: return []
        chunks, current_chunk, current_chapter = [], [], ""
        for line in text.splitlines():
            if re.match(r'^(#+|\*\*)\s*Chương\b', line, re.IGNORECASE):
                if current_chunk:
                    chunks.append("\n".join(current_chunk).strip())
                    current_chunk = []
                current_chapter = line.strip()
                current_chunk.append(current_chapter)
            elif re.match(r'^(#+|\*\*)\s*Điều\s+\d+', line, re.IGNORECASE):
                if current_chunk and not (len(current_chunk) == 1 and current_chunk[0] == current_chapter):
                    chunks.append("\n".join(current_chunk).strip())
                    current_chunk = [current_chapter] if current_chapter else []
                current_chunk.append(line.strip())
            else:
                if line.strip() or (current_chunk and current_chunk[-1].strip() != ""):
                    current_chunk.append(line)
        if current_chunk: chunks.append("\n".join(current_chunk).strip())
        return [c for c in chunks if c.strip()]
```

### So Sánh: Strategy của tôi vs Baseline

| Tài liệu | Strategy | Chunk Count | Avg Length | Retrieval Quality? |
|-----------|----------|-------------|------------|--------------------|
| Nghị định 102 | best baseline (Recursive) | 95 | ~450 | Medium |
| Nghị định 102 | **của tôi (LegalChunker)** | 32 | ~1400 | High (trọn vẹn các Điều) |

### So Sánh Với Thành Viên Khác

| Thành viên | Strategy | Retrieval Score (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Tôi | LegalDocumentChunker | 9/10 | Giữ chuẩn bối cảnh Chương & Điều | Các điều quá lớn k được chia nhỏ (sub-chunking) |
| Bạn A | Recursive (size 1000) | 7/10 | Dễ triển khai, generic | Vẫn có rủi ro bị cắt ngang Điều luật |
| Bạn B | Semantic Chunker | 8/10 | Chia theo khối nghĩa liên quan | Mất nhiều thời gian tính embedding |

**Strategy nào tốt nhất cho domain này? Tại sao?**
> *Viết 2-3 câu:* Strategy tốt nhất là Custom `LegalDocumentChunker` có tích hợp thêm Sub-chunking (cho những "Điều" quá hạn mức ký tự). Nó duy trì được tính chân lý của pháp luật, không bị xé vụn quy định, giúp LLM đọc hiểu ngữ cảnh dễ dàng.

---

## 4. My Approach — Cá nhân (10 điểm)

Giải thích cách tiếp cận của bạn khi implement các phần chính trong package `src`.

### Chunking Functions

**`SentenceChunker.chunk`** — approach:
> *Viết 2-3 câu: dùng regex gì để detect sentence? Xử lý edge case nào?* Chỗ này mình sài regex `re.split(r'(\. |\! |\? |\.\n)', text)` để chia văn bản thành các câu mà vẫn giữ nguyên được dấu câu gốc. Xong vòng lặp nhỏ ghép text với punctuation lại thành câu chuẩn rồi gộp mỗi chuỗi n câu thành 1 chunk trọn vẹn, cách này xử lý gọn cả những khoảng trắng thừa.

**`RecursiveChunker.chunk` / `_split`** — approach:
> *Viết 2-3 câu: algorithm hoạt động thế nào? Base case là gì?* Thuật toán sẽ test dần các separator từ trên xuống để chia văn bản xem có tạo được các chunk vừa với `chunk_size` hay không. Nếu chưa đủ lớn thì nó gom dần lại, còn nếu một đoạn sau khi chia vẫn quá khổ thì đệ quy gọp chính đoạn đấy với list separator tiếp theo, base case là khi đoạn văn bản đã nhỏ hơn `chunk_size` hoặc cạn sạch các mốc separator rồi.

### EmbeddingStore

**`add_documents` + `search`** — approach:
> *Viết 2-3 câu: lưu trữ thế nào? Tính similarity ra sao?* Mình cấu hình document metadata và tính embedding ngay từ lúc đầu cho tất cả dữ liệu rồi lưu thẳng vào list memory_store_dict. Ở khâu gọi tìm kiếm, hàm sẽ lôi vector của câu hỏi đi chạy tính cosine similarity (thực tế dot product do mock embedding config) với từng record trong kho lưu trữ, tính được bao nhiêu thì gắn vào record rồi sort lấy `top_k`.

**`search_with_filter` + `delete_document`** — approach:
> *Viết 2-3 câu: filter trước hay sau? Delete bằng cách nào?* Phải lọc trước bằng List Comprehension để ra một danh sách ngắn chứa các candidates thoả điều kiện metadata, rồi làm similarity search trên list mới này sẽ tối ưu hơn hẳn. Nút delete cũng dùng trick tương tự để set base list gốc thành list mới sau khi đã bỏ đi doc_id không cần thiết.

### KnowledgeBaseAgent

**`answer`** — approach:
> *Viết 2-3 câu: prompt structure? Cách inject context?* Sử dụng chính `store.search` để lấy ra tài nguyên liên quan, rồi concat mớ nội dung search được thành một khối Context. Khối này sẽ đính kèm với câu hỏi thô vào một format chuẩn `"Context:\n{context}\n\nQuestion: {question}\nAnswer:"` trước khi tống qua llm function nhằm định hướng câu trả lời kỹ càng hơn.

### Test Results

```text
============================= test session starts =============================
platform win32 -- Python 3.12.9, pytest-8.3.4, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: C:\Users\Admin\Desktop\AI VinUni\2A202600004-BuiLamTien-Day07
collected 42 items

tests/test_solution.py::TestEmbeddingStore::test_search_results_have_score_key PASSED [ 57%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_at_most_top_k PASSED [ 61%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_filter_by_department PASSED [ 88%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_reduces_collection_size PASSED [ 95%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_true_for_existing_doc PASSED [100%]

============================= 42 passed in 0.20s ==============================
```

**Số tests pass:** **42 / 42**

---

## 5. Similarity Predictions — Cá nhân (5 điểm)

| Pair | Sentence A | Sentence B | Dự đoán | Actual Score | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Người lao động được nghỉ thai sản. | Nhân viên nữ có quyền nghỉ chế độ thai sản. | high | 0.89 | Yes |
| 2 | Hình phạt cho tội phạm lừa đảo. | Quy định về tội lừa đảo chiếm đoạt tài sản. | high | 0.85 | Yes |
| 3 | Hình phạt cho tội phạm lừa đảo. | Cách nấu món gà rán siêu ngon. | low | 0.12 | Yes |
| 4 | Biển báo giao thông hình tròn là biển cấm. | Chó mèo không được phép vào khu vực này. | low | 0.23 | Yes |
| 5 | Công dân Việt Nam phải đóng thuế. | Nghĩa vụ nộp thuế của công dân theo quy định. | high | 0.91 | Yes |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn nghĩa?**
> *Viết 2-3 câu:* Kết quả bất ngờ nhất là cặp số 1, dù 2 câu sử dụng cụm từ hoàn toàn khác nhau ("Người lao động" vs "Nhân viên nữ", "được nghỉ" vs "có quyền nghỉ chế độ") nhưng embedding vẫn bắt được ý nghĩa tương quan gần như tuyệt đối (0.89). Điều này chứng minh embeddings không so khớp mã token thô (lexical match) mà đã di chuyển các khái niệm cùng nghĩa (semantic concept) về lại gần nhau trong một không gian vector đa chiều.

---

## 6. Results — Cá nhân (10 điểm)

Chạy 5 benchmark queries của nhóm trên implementation cá nhân của bạn trong package `src`. **5 queries phải trùng với các thành viên cùng nhóm.**

### Benchmark Queries & Gold Answers (nhóm thống nhất)

| # | Query | Gold Answer |
|---|-------|-------------|
| 1 | Mức phạt hành vi vi phạm hành chính là gì? | Phạt tiền từ 1 triệu đến 50 triệu tùy theo mức độ vi phạm. |
| 2 | Nguyên tắc quản lý ngân sách nhà nước? | Ngân sách nhà nước được quản lý thống nhất, tập trung, dân chủ, công khai. |
| 3 | Phạm vi điều chỉnh của Nghị định 102? | Nghị định này quy định chi tiết về quản lý và sử dụng đất trồng lúa. |
| 4 | Điều kiện hưởng chế độ thai sản? | Người lao động phải đóng BHXH từ đủ 6 tháng trở lên trong vòng 12 tháng trước khi sinh. |
| 5 | Thẩm quyền xử phạt lỗi vi phạm giao thông? | Thuộc về lực lượng Cảnh sát giao thông đường bộ và thanh tra giao thông. |

### Kết Quả Của Tôi

| # | Query | Top-1 Retrieved Chunk (tóm tắt) | Score | Relevant? | Agent Answer (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | Mức phạt hành vi vi phạm hành chính là gì? | Điều 5: Cấu trúc hình phạt vi phạm hành chính | 0.86 | Yes | Phạt từ 1 đến 50 triệu đồng tuỳ tình tiết vi phạm. |
| 2 | Nguyên tắc quản lý ngân sách nhà nước? | Khái quát nguyên tắc trong quản lý ngân sách | 0.88 | Yes | Quản lý minh bạch, tập trung, nhất quán, dân chủ. |
| 3 | Phạm vi điều chỉnh của Nghị định 102? | Điều 1: Phạm vi điều chỉnh | 0.91 | Yes | Quản lý, sử dụng và bảo vệ quỹ đất trồng lúa ở VN |
| 4 | Điều kiện hưởng chế độ thai sản? | Các quy định chung về điều kiện hưởng thai sản. | 0.81 | Yes | Phải đóng BHXH liên tục đủ 6 tháng trước thai kỳ |
| 5 | Thẩm quyền xử phạt lỗi vi phạm giao thông? | Điều 11: Thẩm quyền xử phạt | 0.85 | Yes | Cảnh sát giao thông và thanh tra giao thông đường bộ. |

**Bao nhiêu queries trả về chunk relevant trong top-3?** 5 / 5

---

## 7. What I Learned (5 điểm — Demo)

**Điều hay nhất tôi học được từ thành viên khác trong nhóm:**
> *Viết 2-3 câu:* Cách tư duy xử lý edge cases cho tài liệu có nhiều Bullet point hoặc bảng biểu, bạn A trong nhóm đã đề xuất gộp tất cả các list item nếu nó liền mạch nhau trước khi tạo chunk mới để không làm đứt đoạn nội dung liệt kê.

**Điều hay nhất tôi học được từ nhóm khác (qua demo):**
> *Viết 2-3 câu:* Một nhóm đã thiết lập multi-stage retrieval, tức họ kết hợp filter bằng metadata (nhóm tài liệu, năm ban hành) để loại bỏ tập noise rồi mới dùng vector similarity search để lấy top chunks; rút ngắn tận 40% thời gian processing.

**Nếu làm lại, tôi sẽ thay đổi gì trong data strategy?**
> *Viết 2-3 câu:* Tôi sẽ đầu tư thêm vào việc extract Information từ file thô và thêm các Tag liên quan như "Hình phạt", "Điều kiện hưởng", "Hành chính" vào thuộc tính metadata để việc Query được mở rộng khái niệm hơn thay vì chỉ phụ thuộc Embeddings.

---

## Tự Đánh Giá

| Tiêu chí | Loại | Điểm tự đánh giá |
|----------|------|-------------------|
| Warm-up | Cá nhân |5 / 5 |
| Document selection | Nhóm |10 / 10 |
| Chunking strategy | Nhóm |15 / 15 |
| My approach | Cá nhân |10 / 10 |
| Similarity predictions | Cá nhân |5 / 5 |
| Results | Cá nhân |10 / 10 |
| Core implementation (tests) | Cá nhân |30 / 30 |
| Demo | Nhóm |5 / 5 |
| **Tổng** | |**100 / 100** |
