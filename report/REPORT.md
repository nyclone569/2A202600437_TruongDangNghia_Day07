# Báo Cáo Lab 7: Embedding & Vector Store

**Họ tên:** Trương Đăng Nghĩa
**Nhóm:** Nhóm 5
**Ngày:** 10/04/2026

---

## 1. Warm-up (5 điểm)

### Cosine Similarity (Ex 1.1)

**High cosine similarity nghĩa là gì?**
> Hai text chunk có cosine similarity cao nghĩa là chúng "nói về cùng một chủ đề" — embedding của chúng chỉ về cùng một hướng trong không gian vector. Không cần dùng từ giống nhau, miễn là ý nghĩa tương đương thì điểm sẽ gần 1.

**Ví dụ HIGH similarity:**
- Sentence A: "How do I reset my password?"
- Sentence B: "Steps to change your login password."
- Hai câu cùng hỏi về đổi mật khẩu nên embedding khá gần nhau.

**Ví dụ LOW similarity:**
- Sentence A: "The cake recipe requires flour and sugar."
- Sentence B: "How to configure a Linux firewall."
- Một câu về nấu ăn, một câu về hệ thống — hoàn toàn khác nhau, embedding cách xa.

**Tại sao cosine similarity tốt hơn Euclidean distance cho text embeddings?**
> Cosine similarity chỉ nhìn vào góc giữa 2 vector, bỏ qua độ dài. Hai câu một ngắn một dài nhưng cùng nghĩa vẫn ra điểm cao. Còn Euclidean distance tính cả khoảng cách tuyệt đối nên bị ảnh hưởng bởi độ dài câu, dễ cho kết quả sai. Thêm nữa, hầu hết embedding model tạo ra vector có độ dài gần bằng nhau, nên cosine là thước đo phù hợp hơn.

### Chunking Math (Ex 1.2)

**Document 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> Dùng công thức: `num_chunks = ceil((doc_length - overlap) / (chunk_size - overlap))`
> `= ceil((10000 - 50) / (500 - 50)) = ceil(9950 / 450) = ceil(22.11) = **23 chunks**`

**Nếu overlap tăng lên 100, chunk count thay đổi thế nào? Tại sao muốn overlap nhiều hơn?**
> `= ceil((10000 - 100) / (500 - 100)) = ceil(9900 / 400) = ceil(24.75) = **25 chunks**`
>
> Overlap tăng thì chunk count cũng tăng (từ 23 lên 25). Lý do muốn overlap nhiều hơn là để tránh bị mất thông tin ở ranh giới giữa các chunk — ví dụ một câu bị cắt đôi sẽ vẫn xuất hiện đầy đủ ở chunk kế tiếp. Nhược điểm là tốn thêm bộ nhớ và compute.

---

## 2. Document Selection — Nhóm (10 điểm)

### Domain & Lý Do Chọn

**Domain:** Văn bản pháp lý Việt Nam (Vietnamese Legal Documents)

**Tại sao nhóm chọn domain này?**
> Văn bản pháp lý Việt Nam có cấu trúc phân cấp rất rõ ràng (Chương → Điều → Khoản → Điểm), tạo điều kiện thuận lợi để thử nghiệm các chiến lược chunking khác nhau. Người dùng thực tế thường hỏi về một điều khoản cụ thể — ví dụ "mức phạt tối đa khi vi phạm biên giới là bao nhiêu?" — đòi hỏi retrieval phải chính xác, không bị mất ngữ cảnh khi cắt chunk. Ngoài ra bộ tài liệu này đa dạng về loại (Luật, Nghị định, Thông tư, Quy định Đảng) và thời gian (2021–2026), cho phép kiểm tra khả năng metadata filtering theo `doc_type` và `issued_year`.

### Data Inventory

| # | Tên tài liệu | Nguồn | Số ký tự | Metadata đã gán |
|---|--------------|-------|----------|-----------------|
| 1 | 1.md | Thư viện pháp luật | 36,219 | `doc_type=nghị_định`, `issued_year=2021` |
| 2 | 2.md | Thư viện pháp luật | 17,512 | `doc_type=nghị_định`, `issued_year=2026` |
| 3 | 3.txt | Thư viện pháp luật | 49,163 | `doc_type=luật`, `issued_year=2025` |
| 4 | 4.txt | Thư viện pháp luật | 29,375 | `doc_type=thông_tư`, `issued_year=2026` |
| 5 | 5.md | Thư viện pháp luật | 40,621 | `doc_type=nghị_định`, `issued_year=2026` |
| 6 | 6.md | Thư viện pháp luật | 13,407 | `doc_type=thông_tư`, `issued_year=2026` |
| 7 | 7.md | Thư viện pháp luật | 52,266 | `doc_type=quy_định_đảng`, `issued_year=2026` |

### Metadata Schema

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho retrieval? |
|----------------|------|---------------|-------------------------------|
| `doc_type` | string | `"nghị_định"`, `"luật"`, `"thông_tư"`, `"quy_định_đảng"` | Cho phép filter chỉ lấy văn bản đúng loại — ví dụ câu hỏi về "mức phạt" chỉ cần search trong `nghị_định`, không cần quét `luật` hay `quy_định_đảng`. |
| `issued_year` | int | `2021`, `2025`, `2026` | Hỗ trợ filter theo thời gian, ưu tiên văn bản mới nhất khi có văn bản cũ đã bị sửa đổi, hoặc giới hạn phạm vi tìm kiếm theo kỳ hiệu lực. |

---

## 3. Chunking Strategy — Cá nhân chọn, nhóm so sánh (15 điểm)

### Baseline Analysis

Chạy `ChunkingStrategyComparator().compare()` trên 2-3 tài liệu:

| Tài liệu | Strategy | Chunk Count | Avg Length | Preserves Context? |
|-----------|----------|-------------|------------|-------------------|
| 6.md | FixedSizeChunker (`fixed_size`) | 30 | ~496 | Không — cắt giữa điều khoản, mất ranh giới nguyên tắc |
| 6.md | SentenceChunker (`by_sentences`) | 27 | ~493 | Khá — nhóm 3 câu nhưng đôi khi cắt giữa một mục có nhiều điểm liệt kê |
| 6.md | RecursiveChunker (`recursive`) | 91 | ~146 | Tốt nhất — tôn trọng ranh giới đoạn văn, mỗi chunk là 1 tiểu mục hoàn chỉnh |

> **Nhận xét:** FixedSizeChunker cho chunk count thấp nhất nhưng mỗi chunk thường bị cắt ngang giữa một điều khoản. SentenceChunker cho kết quả tương tự FixedSize vì văn bản pháp lý ít dùng dấu câu kết thúc câu chuẩn. RecursiveChunker tạo ra nhiều chunk nhỏ hơn nhưng mỗi chunk là một nguyên tắc/điểm hoàn chỉnh — phù hợp nhất với cấu trúc pháp lý phân cấp.

### Strategy Của Tôi

**Loại:** RecursiveChunker (built-in, không custom)

**Mô tả cách hoạt động:**
> RecursiveChunker thử cắt văn bản theo danh sách separator theo thứ tự ưu tiên: `["\n\n", "\n", ". ", " ", ""]`. Với mỗi đoạn text, nó tìm separator có ưu tiên cao nhất hiện diện trong đoạn đó rồi tách ra. Nếu đoạn con vẫn còn lớn hơn `chunk_size`, nó tiếp tục đệ quy với các separator cấp thấp hơn cho đến khi chunk đạt kích thước yêu cầu. Cách này đảm bảo không phá vỡ đoạn văn khi vẫn còn cách cắt tự nhiên hơn ở cấp thô.

**Tại sao tôi chọn strategy này cho domain nhóm?**
> Văn bản pháp lý Việt Nam có cấu trúc phân cấp đặc trưng: hai dòng trống (`\n\n`) thường đánh dấu ranh giới giữa các Điều hoặc các Chương, một dòng mới (`\n`) phân tách Khoản và Điểm. RecursiveChunker khai thác đúng pattern này — nó ưu tiên cắt ở `\n\n` trước, tức là giữ nguyên mỗi Điều/Khoản như một chunk, chỉ xuống cấp `\n` khi cần. Kết quả là mỗi chunk chứa một điều khoản hoàn chỉnh, giúp retrieval trả về đúng context pháp lý khi người dùng hỏi về một quy định cụ thể.

**Code snippet (nếu custom):**
```python
# Paste implementation here
```

### So Sánh: Strategy của tôi vs Baseline

| Tài liệu | Strategy | Chunk Count | Avg Length | Retrieval Quality? |
|-----------|----------|-------------|------------|--------------------|
| 6.md | SentenceChunker (best baseline) | 27 | ~493 | Trung bình — chunk dài hơn, giữ câu hoàn chỉnh nhưng đôi khi cắt giữa điểm liệt kê |
| 6.md | **RecursiveChunker (của tôi)** | **91** | **~146** | **Tốt nhất** — mỗi chunk là 1 tiểu mục/điểm hoàn chỉnh, tôn trọng ranh giới `\n\n` |

### So Sánh Với Thành Viên Khác

| Thành viên | Strategy | Chunk Count | Avg Length | Retrieval Score (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|-------------|------------|----------------------|-----------|----------|
| Tôi (Trương Đăng Nghĩa) | RecursiveChunker (built-in) | 91 | ~146 | 6/10 | Không cần code thêm, tự nhận diện ranh giới `\n\n`, chunk granular | Chunk ngắn (~146 chars) dễ thiếu context; không phân biệt ranh giới Chương/Điều |
| Bùi Lâm Tiến | LegalDocumentChunker (custom) | 32 | ~1,400 | 9/10 | Bảo toàn nguyên vẹn từng Điều; tự chèn tiêu đề Chương vào đầu mỗi chunk | Điều quá dài không được sub-chunk; regex chỉ hiệu quả với Markdown format chuẩn |
| Bùi Thế Công | FixedSizeChunker (`size=500, overlap=50`) | 30 | ~495 | 4/10 | Đơn giản nhất, chunk size nhất quán, dễ kiểm soát số lượng chunk | Cắt ngang câu và Điều luật mà không có ranh giới tự nhiên; overlap chỉ giảm mất mát một phần nhỏ |

**Strategy nào tốt nhất cho domain này? Tại sao?**
> `LegalDocumentChunker` của Bùi Lâm Tiến phù hợp hơn với văn bản pháp lý Việt Nam vì mỗi "Điều" là đơn vị ngữ nghĩa tự nhiên — người dùng hỏi về quy định cụ thể cần đọc cả Điều đó nguyên vẹn, không phải mảnh bị cắt ngẫu nhiên. RecursiveChunker của tôi tạo chunk nhỏ nhưng dễ mất context khi một Điều dài bị tách thành nhiều phần. Tuy nhiên RecursiveChunker linh hoạt hơn với những văn bản không theo format Markdown chuẩn — đây là trade-off đáng cân nhắc tùy bộ dữ liệu.

---

## 4. My Approach — Cá nhân (10 điểm)

Giải thích cách tiếp cận của bạn khi implement các phần chính trong package `src`.

### Chunking Functions

**`SentenceChunker.chunk`** — approach:
> Tôi dùng `re.split(r'[.!?]\s', text)` để tách câu — pattern này bắt dấu chấm, chấm than, chấm hỏi theo sau bởi khoảng trắng, khá đủ cho văn bản tiếng Việt thông thường. Edge case cần xử lý là câu cuối cùng của đoạn thường không có khoảng trắng sau dấu chấm nên sẽ không bị split mất — cái này là may mắn chứ không phải cố ý. Sau khi có danh sách câu, tôi gom từng nhóm `max_sentences_per_chunk` câu lại bằng `' '.join(...)` rồi strip whitespace để ra chunk sạch.

**`RecursiveChunker.chunk` / `_split`** — approach:
> Ý tưởng chính là "thử separator thô trước, nếu không đủ thì mới xuống cấp mịn hơn". Hàm `chunk` duyệt qua danh sách `["\n\n", "\n", ". ", " ", ""]` để tìm separator đầu tiên có mặt trong text, rồi giao cho `_split` xử lý đệ quy. Base case của `_split` có ba điều kiện: text rỗng, text đã vừa chunk_size, hoặc hết separator để thử — trong cả ba trường hợp đều trả về ngay. Điều tôi thích ở approach này là nó không bao giờ cắt giữa một đoạn văn nếu vẫn còn cách cắt tự nhiên hơn.

### EmbeddingStore

**`add_documents` + `search`** — approach:
> Tôi chọn lưu trữ bằng in-memory list `_store` — đơn giản, đủ dùng, dễ test. Mỗi record là một dict gồm `content`, `embedding` (vector float), `metadata`, `doc_id` và `record_id`. Khi search, tôi embed query rồi tính dot product với embedding của từng record trong `_store`, sort theo điểm giảm dần và trả về top_k. Store cũng thử khởi tạo ChromaDB nếu cài đặt, nhưng `_store` luôn là nguồn sự thật duy nhất vì ChromaDB không hỗ trợ đủ các thao tác metadata filter và delete mà bài yêu cầu.

**`search_with_filter` + `delete_document`** — approach:
> Với `search_with_filter`, tôi filter metadata *trước* khi search để thu hẹp không gian tìm kiếm — dùng list comprehension kiểm tra từng record xem có thỏa mãn tất cả điều kiện `k/v` trong `metadata_filter` không. Làm vậy nhanh hơn là search toàn bộ rồi filter sau. Với `delete_document`, tôi dùng list comprehension để loại bỏ mọi record có `doc_id` khớp khỏi `_store`; nếu đang dùng ChromaDB thì phải xóa và rebuild lại toàn bộ collection vì Chroma không hỗ trợ delete by metadata — đây là tradeoff chấp nhận được ở scale nhỏ.

### KnowledgeBaseAgent

**`answer`** — approach:
> Tôi dùng RAG pattern cổ điển gồm 3 bước: retrieve, format context, generate. Cụ thể: gọi `store.search(question, top_k=3)` lấy các chunk liên quan; format mỗi chunk thành `[Doc: {doc_id}] {content}` rồi nối bằng `\n\n` để LLM biết ranh giới giữa các đoạn; cuối cùng build prompt theo cấu trúc `Context → Question → Answer:` và gọi `llm_fn`. Tôi để `doc_id` trong context để LLM có thể cite nguồn nếu cần — cái này không bắt buộc nhưng giúp câu trả lời đáng tin hơn.

### Test Results

```
# Paste output of: pytest tests/ -v
=============================================================== test session starts ================================================================
platform win32 -- Python 3.13.12, pytest-9.0.2, pluggy-1.5.0 -- C:\Users\Admin\miniconda3\python.exe
cachedir: .pytest_cache
rootdir: D:\Projects\AI Thuc Chien\assignments\2A202600437_TruongDangNghia_Day07
plugins: anyio-4.10.0, langsmith-0.7.25
collected 42 items                                                                                                                                  

tests/test_solution.py::TestProjectStructure::test_root_main_entrypoint_exists PASSED                                                         [  2%] 
tests/test_solution.py::TestProjectStructure::test_src_package_exists PASSED                                                                  [  4%] 
tests/test_solution.py::TestClassBasedInterfaces::test_chunker_classes_exist PASSED                                                           [  7%] 
tests/test_solution.py::TestClassBasedInterfaces::test_mock_embedder_exists PASSED                                                            [  9%] 
tests/test_solution.py::TestFixedSizeChunker::test_chunks_respect_size PASSED                                                                 [ 11%] 
tests/test_solution.py::TestFixedSizeChunker::test_correct_number_of_chunks_no_overlap PASSED                                                 [ 14%] 
tests/test_solution.py::TestFixedSizeChunker::test_empty_text_returns_empty_list PASSED                                                       [ 16%] 
tests/test_solution.py::TestFixedSizeChunker::test_no_overlap_no_shared_content PASSED                                                        [ 19%] 
tests/test_solution.py::TestFixedSizeChunker::test_overlap_creates_shared_content PASSED                                                      [ 21%] 
tests/test_solution.py::TestFixedSizeChunker::test_returns_list PASSED                                                                        [ 23%] 
tests/test_solution.py::TestFixedSizeChunker::test_single_chunk_if_text_shorter PASSED                                                        [ 26%] 
tests/test_solution.py::TestSentenceChunker::test_chunks_are_strings PASSED                                                                   [ 28%] 
tests/test_solution.py::TestSentenceChunker::test_respects_max_sentences PASSED                                                               [ 30%] 
tests/test_solution.py::TestSentenceChunker::test_returns_list PASSED                                                                         [ 33%] 
tests/test_solution.py::TestSentenceChunker::test_single_sentence_max_gives_many_chunks PASSED                                                [ 35%] 
tests/test_solution.py::TestRecursiveChunker::test_chunks_within_size_when_possible PASSED                                                    [ 38%] 
tests/test_solution.py::TestRecursiveChunker::test_empty_separators_falls_back_gracefully PASSED                                              [ 40%] 
tests/test_solution.py::TestRecursiveChunker::test_handles_double_newline_separator PASSED                                                    [ 42%] 
tests/test_solution.py::TestRecursiveChunker::test_returns_list PASSED                                                                        [ 45%] 
tests/test_solution.py::TestEmbeddingStore::test_add_documents_increases_size PASSED                                                          [ 47%]
tests/test_solution.py::TestEmbeddingStore::test_add_more_increases_further PASSED                                                            [ 50%] 
tests/test_solution.py::TestEmbeddingStore::test_initial_size_is_zero PASSED                                                                  [ 52%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_content_key PASSED                                                       [ 54%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_score_key PASSED                                                         [ 57%] 
tests/test_solution.py::TestEmbeddingStore::test_search_results_sorted_by_score_descending PASSED                                             [ 59%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_at_most_top_k PASSED                                                          [ 61%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_list PASSED                                                                   [ 64%] 
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_non_empty PASSED                                                                  [ 66%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_returns_string PASSED                                                             [ 69%]
tests/test_solution.py::TestComputeSimilarity::test_identical_vectors_return_1 PASSED                                                         [ 71%] 
tests/test_solution.py::TestComputeSimilarity::test_opposite_vectors_return_minus_1 PASSED                                                    [ 73%] 
tests/test_solution.py::TestComputeSimilarity::test_orthogonal_vectors_return_0 PASSED                                                        [ 76%] 
tests/test_solution.py::TestComputeSimilarity::test_zero_vector_returns_0 PASSED                                                              [ 78%] 
tests/test_solution.py::TestCompareChunkingStrategies::test_counts_are_positive PASSED                                                        [ 80%] 
tests/test_solution.py::TestCompareChunkingStrategies::test_each_strategy_has_count_and_avg_length PASSED                                     [ 83%] 
tests/test_solution.py::TestCompareChunkingStrategies::test_returns_three_strategies PASSED                                                   [ 85%] 
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_filter_by_department PASSED                                                  [ 88%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_no_filter_returns_all_candidates PASSED                                      [ 90%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_returns_at_most_top_k PASSED                                                 [ 92%] 
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_reduces_collection_size PASSED                                          [ 95%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_false_for_nonexistent_doc PASSED                                [ 97%] 
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_true_for_existing_doc PASSED                                    [100%]

================================================================ 42 passed in 1.70s ================================================================ 
```

**Số tests pass:** 42 / 42

---

## 5. Similarity Predictions — Cá nhân (5 điểm)

| Pair | Sentence A | Sentence B | Dự đoán | Actual Score | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | "Mức phạt tiền tối đa đối với cá nhân là 75 triệu đồng." | "Cá nhân vi phạm bị phạt không quá 75 triệu đồng." | high | 0.0089 | Sai |
| 2 | "Hệ thống trí tuệ nhân tạo phải bảo đảm an toàn, độ tin cậy." | "AI system must ensure safety and reliability." | high | -0.0402 | Sai |
| 3 | "Giáo viên hạng I phải có bằng thạc sĩ trở lên." | "Dự toán ngân sách được lập bằng đồng Việt Nam quy đổi ra đô la Mỹ." | low | -0.0339 | Sai |
| 4 | "Cán bộ đảng viên phải giữ vững bản lĩnh chính trị." | "Đảng viên cần kiên định lập trường tư tưởng của Đảng." | high | -0.0059 | Sai |
| 5 | "Hóa đơn điện tử phải ghi đầy đủ các nội dung bắt buộc." | "Biên giới quốc gia cần được bảo vệ nghiêm ngặt." | low | -0.2264 | Đúng |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn nghĩa?**
> Bất ngờ nhất là Pair 1 và Pair 4 — hai câu gần như đồng nghĩa hoàn toàn nhưng similarity đều gần 0, không phản ánh chút nào sự tương đồng về nghĩa. Lý do là implementation đang dùng `MockEmbedder` — embedding được tạo từ hash MD5 của chuỗi ký tự, xử lý text như một dãy byte ngẫu nhiên, không có khái niệm "ngữ nghĩa". Điều này cho thấy embedding tốt (như sentence-transformers hay OpenAI) thực sự cần được train trên dữ liệu lớn để học được mối quan hệ ngữ nghĩa giữa các từ — không thể "giả" bằng hash function.

---

## 6. Results — Cá nhân (10 điểm)

Chạy 5 benchmark queries của nhóm trên implementation cá nhân của bạn trong package `src`. **5 queries phải trùng với các thành viên cùng nhóm.**

### Benchmark Queries & Gold Answers (nhóm thống nhất)

| # | Query | Gold Answer |
|---|-------|-------------|
| 1 | Tiêu chuẩn về trình độ đào tạo, bồi dưỡng đối với giáo viên hạng I | Có bằng thạc sĩ trở lên thuộc ngành đào tạo giáo viên hoặc có bằng thạc sĩ trở lên chuyên ngành phù hợp với môn học giảng dạy và có chứng chỉ nghiệp vụ sư phạm đối với giáo viên trung học phổ thông. Có chứng chỉ bồi dưỡng chuẩn nghề nghiệp giáo viên cơ sở giáo dục thường xuyên. |
| 2 | Xử lý vi phạm QUY ĐỊNH VỀ CÔNG TÁC CHÍNH TRỊ, TƯ TƯỞNG TRONG ĐẢNG như thế nào? | 1. Tổ chức đảng, cán bộ, đảng viên vi phạm Quy định này, tùy theo tính chất, mức độ và hậu quả phải bị xem xét, xử lý kỷ luật theo quy định của Đảng và pháp luật của Nhà nước. 2. Người đứng đầu cấp ủy, tổ chức đảng, cơ quan, đơn vị nếu để xảy ra vi phạm nghiêm trọng, kéo dài trong lĩnh vực công tác chính trị, tư tưởng phải chịu trách nhiệm hoặc trách nhiệm liên đới và bị xem xét xử lý theo quy định của Đảng. |
| 3 | Theo Thông tư 05/2026/TT-BKHCN, khi hệ thống trí tuệ nhân tạo bị tấn công đầu độc dữ liệu, tổ chức/cá nhân cần thực hiện những biện pháp gì? | Bảo đảm an ninh của hệ thống trí tuệ nhân tạo: Tổ chức, cá nhân áp dụng biện pháp bảo vệ phù hợp để phòng ngừa, phát hiện, ngăn chặn và ứng phó với các hành vi xâm nhập, chiếm quyền điều khiển, đầu độc dữ liệu, đầu độc mô hình, tấn công đối nghịch, khai thác lỗ hổng, rò rỉ dữ liệu và lạm dụng hệ thống trí tuệ nhân tạo; bảo đảm tính bí mật, toàn vẹn và sẵn sàng của dữ liệu, mô hình, thuật toán và hạ tầng liên quan.
|
| 4 | Những hành vi nào bị nghiêm cấm trong hoạt động trí tuệ nhân tạo theo Luật AI 2025? | Luật nghiêm cấm việc lợi dụng hệ thống AI để vi phạm pháp luật ; sử dụng yếu tố giả mạo để lừa dối hoặc thao túng hành vi con người ; lợi dụng điểm yếu của nhóm người dễ bị tổn thương ; tạo ra nội dung giả mạo gây nguy hại đến an ninh quốc gia ; và thu thập dữ liệu trái phép để phát triển hệ thống AI.
 |
| 5 | Theo Nghị định 129/2026/NĐ-CP, dự toán ngân sách hàng năm của các Cơ quan Việt Nam ở nước ngoài được lập bằng đồng tiền nào và căn cứ vào tỷ giá tại thời điểm nào?|Dự toán được lập bằng đồng Việt Nam quy đổi ra đô la Mỹ theo tỷ giá hạch toán tháng 6 năm hiện hành do Bộ Tài chính quy định. |
| 6 | Cơ quan nhà nước sử dụng hệ thống trí tuệ nhân tạo có được để hệ thống tự động đưa ra quyết định cuối cùng không?
| Bảo đảm quyết định cuối cùng thuộc thẩm quyền của con người theo quy định của pháp luật; hệ thống trí tuệ nhân tạo không thay thế trách nhiệm của người ra quyết định.|

### Kết Quả Của Tôi

> **Lưu ý:** Kết quả dùng `MockEmbedder` (hash MD5, không semantic). Score phản ánh tương đồng ngẫu nhiên theo hash, không theo nghĩa — đây là giới hạn của mock embedding trong lab.

| # | Query | Top-1 Retrieved Chunk (tóm tắt) | Score | Relevant? | Agent Answer (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | Tiêu chuẩn trình độ giáo viên hạng I | Chunk từ **7.md** (QĐ 19 về công tác Đảng) | 0.277 | Không | Không trả lời được — context sai tài liệu |
| 2 | Xử lý vi phạm công tác chính trị, tư tưởng | Chunk từ **1.md** (NĐ 102 về xử phạt thuế) | 0.195 | Không | Không trả lời được — context sai tài liệu |
| 3 | AI bị tấn công đầu độc dữ liệu, cần làm gì? | Chunk từ **3.txt** (Luật AI, điều về đánh giá phù hợp) | 0.199 | Gần — cùng domain AI nhưng sai văn bản | Trả lời chung về AI, thiếu nội dung TT 05/2026 |
| 4 | Hành vi bị nghiêm cấm trong AI (Luật AI 2025) | Chunk từ **3.txt** (Luật AI, điều về chính sách quyền tiếp cận) | 0.434 | Đúng tài liệu | Trả lời liên quan Luật AI, đúng nguồn |
| 5 | Dự toán ngân sách Cơ quan VN ở nước ngoài | Chunk từ **7.md** (QĐ 19 về công tác Đảng) | 0.288 | Không | Không trả lời được — context sai tài liệu |

**Bao nhiêu queries trả về chunk relevant trong top-3?** 1 / 5

> **Phân tích:** Chỉ Q4 tìm đúng tài liệu (3.txt — Luật AI 2025). Nguyên nhân chính: `MockEmbedder` hash MD5 không capture semantic — query và chunk liên quan có vector hoàn toàn độc lập nhau. Nếu dùng model thật như `sentence-transformers` với Vietnamese model, tôi kỳ vọng ít nhất 4/5 queries sẽ tìm đúng tài liệu nguồn.

---

## 7. What I Learned (5 điểm — Demo)

**Điều hay nhất tôi học được từ thành viên khác trong nhóm:**
> Bùi Lâm Tiến dùng `LegalDocumentChunker` — một strategy tôi không nghĩ đến — là tách chunk đúng tại ranh giới "Điều" bằng regex, đồng thời tự động chèn tiêu đề "Chương" hiện tại vào đầu mỗi chunk con. Cái hay là mỗi chunk ra về sau hoàn toàn độc lập mà vẫn có đủ bối cảnh ("Chương mấy, Điều mấy nói về gì"), LLM không cần đoán context. Tôi trước đó chỉ nghĩ đến cắt theo size hay dấu câu, chưa nghĩ đến việc khai thác cấu trúc phân cấp của chính văn bản làm mốc chia.

**Điều hay nhất tôi học được từ nhóm khác (qua demo):**
> Nhóm 10 làm domain **AI & RAG Technical Documentation** — tài liệu kỹ thuật tiếng Anh gồm blog, docs, project specs. Họ dùng metadata `category` với các giá trị như `"technical"`, `"code_ui"`, `"process"` để pre-filter theo *mục đích sử dụng* của tài liệu, thay vì theo hình thức văn bản như nhóm mình. Điều tôi thấy hay nhất là **Parent-Child Strategy** trong `KnowledgeBaseAgent`: retrieve chunk nhỏ để match chính xác query, nhưng khi build context cho LLM thì inject nội dung của chunk *cha* đầy đủ — điều này giúp họ đạt 5/5 queries với score 1.0, trong khi nhóm mình chỉ đạt 1/5 vì chunk FixedSize bị cắt ngang làm mất context. Đây là kỹ thuật tôi muốn thử nhất nếu có thêm thời gian.

**Nếu làm lại, tôi sẽ thay đổi gì trong data strategy?**
> Thứ nhất, tôi sẽ dùng real embedding model ngay từ đầu thay vì MockEmbedder — dù chậm hơn nhưng kết quả retrieval sẽ có ý nghĩa thực sự, không phải random. Thứ hai, tôi sẽ thêm metadata ở cấp chunk thay vì chỉ cấp tài liệu — ví dụ `article_number` ("Điều 5"), `chapter` ("Chương II") để filter cực kỳ chính xác khi người dùng hỏi về một điều khoản cụ thể. Cuối cùng, tôi sẽ thêm ít nhất 2-3 tài liệu từ các domain khác nhau để kiểm tra xem metadata filtering có thực sự loại bỏ được nhiễu không.

---

## Tự Đánh Giá

| Tiêu chí | Loại | Điểm tự đánh giá |
|----------|------|-------------------|
| Warm-up | Cá nhân | 5 / 5 |
| Document selection | Nhóm | 9 / 10 |
| Chunking strategy | Nhóm | 13 / 15 |
| My approach | Cá nhân | 9 / 10 |
| Similarity predictions | Cá nhân | 4 / 5 |
| Results | Cá nhân | 7 / 10 |
| Core implementation (tests) | Cá nhân | 30 / 30 |
| Demo | Nhóm | 0 / 5 |
| **Tổng** | | **76 / 100** |
