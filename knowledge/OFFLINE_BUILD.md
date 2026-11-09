# Xây đồ thị và chỉ mục hình học offline

## Đã chạy trên máy ngày 09/11/2026

- Django: 88 bài mới + 6 bài mẫu = 94 bài đã xuất bản, 154 quan hệ tiên quyết.
- Neo4j: 94 nút bài học `:Concept:MindGeoConcept`, 154 cạnh tiên quyết biên soạn.
- Chroma: 94 tài liệu, vector BGE-M3 1024 chiều, lưu trong `data/chroma/`.
- Kiểm tra truy xuất thật trên bài lớp 6, 7, 8, 9: đạt cả 4 bài.
- Đồng bộ lại: tái sử dụng 94 embedding, không sinh bản ghi trùng. Đã kiểm chứng chạy với cache model, không cần Hugging Face online.

Đây là đồ thị **tiên quyết từ metadata do biên soạn đề xuất**, không phải đồ thị thực thể do LLM tự trích xuất. Hướng cạnh: kiến thức nền → kiến thức cần nền đó. Các bài và 151 cạnh nguồn vẫn chờ giáo viên duyệt. `--publish` chỉ cho phép dùng học liệu trong ứng dụng và RAG, không đổi trạng thái thẩm định.

Giữ nguyên ba module đang tái sử dụng từ `hybridRAG_paper`: BGE-M3, ChromaStore và HybridSearch/RRF. Không chạy pipeline đồ thị pháp luật nguyên bản cho dữ liệu toán. Các bài mẫu cũ được giữ nguyên.

## Chạy lại trên máy hiện tại

```bash
cd /home/duypy/Documents/MySource/backend_solve_math_web
.venv/bin/python manage.py import_geometry_corpus --publish --dry-run
.venv/bin/python manage.py import_geometry_corpus --publish
.venv/bin/python manage.py sync_geometry_index --verify
```

Lệnh đầu kiểm tra rồi hoàn tác giao dịch. Lệnh nhập mặc định tạo bản nháp nếu không có `--publish`. Chạy lại sẽ giữ các bài đã nhập cùng hash, kể cả ghi chú giáo viên đã sửa; mã trùng có nguồn/hash khác sẽ báo lỗi và hoàn tác toàn bộ. Các quan hệ đề xuất được nhập bổ sung, không xóa quan hệ riêng đã có; kiểm tra chu kỳ trên cả dữ liệu cũ và mới.

Nếu sửa Markdown, cần cập nhật metadata/hash manifest và rà nội dung. Importer sẽ từ chối tự ghi đè bài có hash cũ; cần xử lý bản chỉnh sửa có chủ đích. Đây là lựa chọn để bảo vệ nội dung giáo viên, không phải công cụ tự cập nhật mọi phiên bản corpus.

Đồng bộ chỉ lấy bài đã xuất bản, giữ namespace `MindGeoConcept` và collection cấu hình cho ứng dụng. Nó loại mục đã bỏ xuất bản khỏi chỉ mục này. Không dùng chung collection với dữ liệu dự án khác.

Kết quả kiểm chứng máy đọc được: `data/index-build-report.json`. Nhật ký lần đầu: `data/index-build.log`; lần kiểm chứng hoàn toàn bằng cache: `data/index-verify-offline.log`. Thư mục `data/` không đưa lên Git.

## Cấu hình đang dùng

```dotenv
RAG_ENABLED=true
RAG_MODEL_OFFLINE=true
RAG_EMBED_MAX_LENGTH=2048
RAG_CPU_THREADS=2
CHROMA_DB_PATH=./data/chroma
CHROMA_COLLECTION=mindgeo_geometry
```

`RAG_MODEL_OFFLINE=true` chỉ nạp trọng số/tokenizer đã tải vào cache. Khi cài máy mới, đặt false cho lần tải đầu. Neo4j phải đang chạy; bước này không cần Qwen, Gemini, OpenAI hay Tavily. Model sinh bài tập và gia sư Qwen là hai cấu hình độc lập với việc dựng chỉ mục.

BGE-M3 chạy CPU, batch 1, giới hạn 2048 token để phù hợp laptop. Lệnh đồng bộ kiểm tra trước độ dài từng bài, báo lỗi nếu vượt giới hạn thay vì âm thầm cắt nội dung. Hash nội dung và cấu hình độ dài giúp tái sử dụng embedding không đổi. Adapter tắt luồng chuyển trọng số sang safetensors từ xa của Transformers; dùng trọng số gốc, không sửa repo nguồn.

## Xem đồ thị trong Neo4j Browser

Mở <http://localhost:7474>, đăng nhập bằng thông tin Neo4j của bạn rồi chạy:

```cypher
MATCH (a:MindGeoConcept)-[r:PREREQUISITE_OF]->(b:MindGeoConcept)
RETURN a, r, b LIMIT 200;
```

Chỉ xem bài Pythagore và nền tảng trực tiếp:

```cypher
MATCH (n:MindGeoConcept {id:'g8-pythagore'})
OPTIONAL MATCH (p:MindGeoConcept)-[r:PREREQUISITE_OF]->(n)
RETURN p, r, n;
```

## Cài môi trường mới

```bash
uv pip install --python .venv/bin/python torch --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv/bin/python -r requirements-ai.txt
.venv/bin/python manage.py migrate
```

Chọn bản CPU theo [hướng dẫn PyTorch](https://pytorch.org/get-started/locally/). Sau đó cấu hình Neo4j, clone nguồn bằng script hiện có, tải BGE-M3 lần đầu và chạy ba lệnh nhập/đồng bộ ở trên. Không đưa khóa, mật khẩu hoặc thư mục model vào frontend.


## Pipeline trích xuất LLM đã hoàn tất

Ngày 09/11/2026, đã gọi gateway Gemini tương thích OpenAI để trích xuất **88/88 bài**, tạo **450 thực thể và 526 quan hệ**. Schema gồm Topic, Concept, Theorem, Formula, Example; nhãn chung `MindGeoEntity`. Có thêm các quan hệ MENTIONS nối bài học tới thực thể. Con số 526 không tính 154 cạnh tiên quyết thủ công hoặc MENTIONS.

Đã loại 25 quan hệ thiếu đoạn nguồn khớp nguyên văn. Toàn bộ 526 quan hệ được giữ đều qua kiểm tra bằng chứng nguồn; điều này không tự chứng minh mọi liên hệ toán học đúng. Chúng vẫn mang `review_status=cho-giao-vien-duyet`. Không nhập thẳng quan hệ LLM vào DAG tiên quyết do giáo viên quản lý.

```bash
.venv/bin/python manage.py extract_geometry_graph --dry-run
.venv/bin/python manage.py extract_geometry_graph --rpm 10 --max-calls 100
```

Cache và checkpoint JSON nằm tại `data/geometry-extraction/`. Lượt kiểm chứng cuối tái nạp 88 cache, **0 lần gọi model**. `--force` yêu cầu trích xuất lại, có gọi API. Hạn mức offline theo `--max-calls`, không trừ hạn mức 100 lượt sinh bài/quiz hằng ngày của web. Lỗi mạng/quota máy cung cấp được thử lại tối đa một lần; JSON rỗng không được biến thành đồ thị giả. Escape LaTeX sai cú pháp JSON chỉ được sửa escape, sau đó vẫn phải qua schema và kiểm tra bằng chứng.

```cypher
MATCH (d:MindGeoConcept {id:'g8-pythagore'})-[:MENTIONS]->(e:MindGeoEntity)
OPTIONAL MATCH (e)-[r]->(other:MindGeoEntity)
WHERE r.source_concept_id=d.id
RETURN d,e,r,other;
```

Frontend có nút “Xem đồ thị model trích xuất” trong bài học. Hình và bảng bằng chứng đọc từ API có xác thực. Sửa nội dung làm fingerprint không còn khớp: API không hiển thị đồ thị cũ; cần đồng bộ và chạy trích xuất lại. RAG dùng fingerprint Neo/Chroma để chặn chỉ mục đã cũ và lấy trạng thái duyệt hiện tại từ Django.

Bằng chứng: `data/extraction-verification.json`, `data/geometry-extraction/full-run.json`, `data/extraction-cache-verification.log`. Adapter dùng SchemaLLMPathExtractor như GraphBuilder nguồn, giữ nguyên file repo ngoài và tái sử dụng RateLimiter; schema toán và cách lưu theo từng bài nằm trong `integrations/geometry_extraction.py`.

Đã sửa lộ trình theo lớp: bỏ cạnh mẫu sides (9) → pythagoras (8), kiểm tra toàn bộ cạnh không còn nguồn lớp cao hơn đích. Neo4j đã đồng bộ 154 cạnh; 94 embedding được tái sử dụng, đồ thị LLM được giữ nguyên.
