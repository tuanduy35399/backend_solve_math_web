# MindGeoTutorAI backend

Backend niên luận dùng Django REST Framework cho tài khoản/dữ liệu học tập và FastAPI cho suy luận Qwen, Hybrid RAG và sinh học liệu. Frontend React nằm ở repo cạnh bên `solve_math_vlm/frontend`.

## Hai luồng AI

1. **Chat giải toán:** React → FastAPI → Qwen do nhóm huấn luyện. Ảnh, đề bài và hội thoại chỉ đi tới máy chủ Qwen cấu hình bởi người vận hành. Thiếu model local trả `503`, không tự chuyển sang Gemini/OpenAI và không sinh câu trả lời giả.
2. **Tạo học liệu:** Kiến thức toán đã xuất bản trong Django → BGE-M3/Chroma + quan hệ Neo4j → hợp nhất RRF → model bên ngoài (Gemini hoặc OpenAI/tương thích OpenAI) → tóm tắt, bài tập và quiz. Model bên ngoài chỉ nhận ngữ cảnh học thuật. Bộ câu hỏi và bài tập được lưu trong Django; điểm quiz tính tại máy chủ.

Luồng nghiên cứu web dành riêng cho giáo viên/quản trị viên: agent tìm tài liệu bổ trợ và tạo báo cáo Markdown có nguồn. Báo cáo chưa được coi là học liệu đã duyệt và không tự nhập vào kho toán.

## Chạy cục bộ

Python 3.12–3.14 cho backend cơ bản. Các thư viện ML/GPU cần phiên bản Python tương thích với PyTorch trên máy triển khai; nên dùng môi trường AI riêng nếu máy chủ hiện tại chưa có GPU.

```bash
cd /home/duypy/Documents/MySource/backend_solve_math_web
python3 -m venv .venv
# Dùng uv hoặc .venv/bin/python -m pip tương đương.
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env  # chỉ chạy khi CHƯA có .env, không ghi đè cấu hình đã nhập
.venv/bin/python scripts/clone_sources.py
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_learning
.venv/bin/python scripts/run_dev.py
```

Django chạy tại `http://127.0.0.1:8000`, FastAPI tại `http://127.0.0.1:8001` (OpenAPI `/docs`). Script `run_dev.py` dừng cả hai bằng Ctrl+C. Không có tài khoản mặc định hay mật khẩu hardcode.

```bash
cd /home/duypy/Documents/MySource/solve_math_vlm/frontend
npm install
npm run dev
```

Mở `http://127.0.0.1:5173`, đăng ký tài khoản học sinh. Tạo quản trị bằng `.venv/bin/python manage.py createsuperuser`; hoặc cấp quyền cho tài khoản đã đăng ký bằng `.venv/bin/python manage.py set_role TEN_DANG_NHAP educator` (`admin` để cấp quyền quản trị). Sau khi đổi vai trò phải đăng nhập lại. Superuser luôn được nhận diện là admin. Đăng ký công khai và cập nhật hồ sơ không cho tự nâng quyền.

SQLite lưu dữ liệu phát triển trong `db.sqlite3`; `DATABASE_PATH` cho phép chọn DB khác, đặc biệt khi kiểm thử. Chạy migrate chỉ thêm schema; seed không ghi đè học liệu đã sửa. Tránh đưa DB, `.env`, hoặc dữ liệu người dùng lên Git. Repo ban đầu đã theo dõi DB/bytecode; `.gitignore` chỉ ngăn các tệp mới, không tự bỏ theo dõi các tệp cũ.

## Cấu hình dịch vụ

Điền `.env` ở backend; không đưa khóa vào biến Vite. Khởi động lại cả hai backend sau khi thay `.env`. Trạng thái “đã khai báo cấu hình” trên màn hình quản trị không có nghĩa là đã kiểm tra kết nối từ xa.

| Nhóm | Biến | Ý nghĩa |
|---|---|---|
| Qwen | `QWEN_BASE_URL`, `QWEN_MODEL`, tùy chọn `QWEN_API_KEY` | Endpoint tự vận hành có `/chat/completions`; base URL thường kết thúc `/v1` |
| Sinh học liệu | `CONTENT_PROVIDER=gemini` hoặc `openai` | Chọn model bên ngoài |
| Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` | Sinh tóm tắt, bài tập, quiz; không dùng cho chat |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL`, tùy chọn `OPENAI_BASE_URL` | Dùng cho sinh học liệu nếu chọn openai; đồng thời là model agent nghiên cứu |
| Neo4j | `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` | Đồ thị kiến thức toán; adapter quản lý nhãn `MindGeoConcept` |
| Chroma | `CHROMA_DB_PATH`, `CHROMA_COLLECTION` | Collection chuyên biệt cho học liệu này; không dùng collection của dự án khác |
| Hybrid RAG | `RAG_ENABLED=true` | Chỉ bật sau khi cài thư viện AI và chuẩn bị Neo4j |
| Nghiên cứu web | `TAVILY_API_KEY` và cấu hình OpenAI phía trên | Agent giữ cấu trúc create_agent/ChatOpenAI/tools của repo nguồn |
| Hạn mức | `GEMINI_DAILY_LIMIT` | Giá trị khởi tạo hạn mức sinh nội dung, áp dụng cả hai nhà cung cấp; admin có thể sửa trong DB |

```bash
uv pip install --python .venv/bin/python -r requirements-ai.txt
```

Đây là nhóm thư viện tùy chọn, có thể tải PyTorch và nhiều dữ liệu. Lần đồng bộ đầu tiên còn phải tải trọng số `BAAI/bge-m3`; không có sẵn trong mã nguồn. Cấu hình Neo4j, bật RAG, khởi động lại backend, đăng nhập giáo viên rồi bấm **Thử đồng bộ chỉ mục** trong Kho học liệu. Thao tác thực hiện embedding và cập nhật collection/đồ thị thật. Sau khi sửa/xóa học liệu hoặc quan hệ, cần đồng bộ lại. Nếu một kênh lỗi, API báo chưa sẵn sàng thay vì gắn nhãn Hybrid RAG cho kết quả chỉ từ dữ liệu mẫu.

`QWEN_BASE_URL` dành riêng model do nhóm vận hành, không trỏ sang API trả phí để giả lập Qwen. Phản hồi model cần JSON theo schema trong `ai_service/providers.py`: `text`, `math`, `highlight`, `geometry`, `correct`, `concept`, `done`. Không yêu cầu xuất suy nghĩ nội bộ. Hình hỗ trợ tam giác vuông, lăng trụ và hình cầu; hình không xác định được sẽ không tự bịa sơ đồ.

## Nguồn được tái sử dụng

Hai repo đã clone vào `external/` ở máy này. Không sửa mã nguồn gốc; `external/` bị Git bỏ qua để tránh nhập cả DB, ảnh, dữ liệu nghiên cứu và lịch sử Git vào repo niên luận. `scripts/clone_sources.py` clone lại đúng revision ghi trong `integrations/sources.json` trên máy khác.

- [hybrid_graph_rag](https://github.com/tuanduy35399/hybrid_graph_rag/tree/97e35e9370465293d07c0b85273fbe06c928340c): adapter `integrations/geometry_rag.py` gọi trực tiếp `BGE_M3_Embedding`, `ChromaStore`, `HybridSearch.merge` từ `hybridRAG_paper`. Schema Neo4j hình học viết ở lớp kết nối thay cho schema/prompt pháp luật của repo gốc. Không chạy `api/main.py` gốc vì nó khởi tạo miền pháp luật và tham chiếu module database không có trong checkout.
- [ai_agent_game_maker_plan](https://github.com/tuanduy35399/ai_agent_game_maker_plan/tree/c25184e37fc661e04a5d9deb14edde8af46e1159): worker giữ cách dùng `create_agent`, `ChatOpenAI`, gọi trực tiếp tool `search_web`, `make_report` từ `tools.py`. Mỗi lần chạy dùng thư mục tạm riêng, cố định tên file báo cáo, sau đó lưu nội dung vào Django. Không chạy vòng lặp CLI hoặc dùng `thread_id=1` chung cho mọi người. Tool cào URL tùy ý được giữ nguyên ở repo gốc nhưng không đưa vào endpoint web.

Các lớp kết nối chỉ thay phần miền nghiệp vụ, xác thực, vòng đời HTTP, lưu dữ liệu và đường dẫn báo cáo cần thiết cho ứng dụng nhiều người dùng.

## API chính

Dùng header `Authorization: Token TOKEN` cho cả hai backend. Đăng xuất/khóa tài khoản/đổi vai trò thu hồi token. HTTPS và reverse proxy cùng origin cần được cấu hình khi triển khai thật; Vite proxy chỉ phục vụ phát triển.

| Backend | Endpoint | Chức năng |
|---|---|---|
| Django | `POST /api/v1/auth/register/`, `login/`, `logout/` | Đăng ký, đăng nhập, đăng xuất |
| Django | `GET/PATCH /api/v1/auth/me/` | Hồ sơ cá nhân |
| Django | `GET/PATCH /api/v1/users/` | Admin quản lý vai trò/trạng thái |
| Django | `/api/v1/materials/`, `/edges/` | Học liệu và quan hệ có kiểm tra vòng lặp |
| Django | `/api/v1/sessions/`, `/gaps/`, `/attempts/` | Dữ liệu học tập theo tài khoản |
| Django | `/api/v1/quizzes/`, `/<uuid>/`, `/<uuid>/submit/` | Danh sách, đề không lộ đáp án, chấm điểm |
| Django | `/api/v1/stories/`, `/reports/` | Bài viết và báo cáo nghiên cứu |
| Django | `/api/v1/statistics/` | Thống kê tổng hợp cho giáo viên |
| Django | `/api/v1/configuration/`, `/training/` | Hạn mức và đăng ký checkpoint cho admin |
| Django | `DELETE /api/v1/learning-data/` | Xóa dữ liệu học tập của chính tài khoản |
| FastAPI | `POST /api/v1/tutor/socratic-ask` | Multipart `prompt_question`, `photo`, `session_id` |
| FastAPI | `POST /api/v1/rag/analyze-gap`, `/rag/sync` | Truy xuất và đồng bộ Hybrid RAG |
| FastAPI | `POST /api/v1/recommend/quiz-summary` | Sinh học liệu từ `concept_id` đã xuất bản |
| FastAPI | `POST /api/v1/research/report` | Agent lập báo cáo cho giáo viên/admin |
| FastAPI | `POST /api/v1/Geometry2D/sync` | Lưu khám phá hình học sau khi hoàn thành bài |
| FastAPI | `GET /api/v1/system/status` | Trạng thái cấu hình cho admin |

Hai tiến trình dùng chung Django ORM/model và DB; FastAPI không tạo một hệ tài khoản hay bảng người dùng khác. Ảnh được kiểm tra cả byte ảnh, định dạng và giới hạn dung lượng. Chat lỗi không lưu câu trả lời giả. Các lượt hội thoại dùng version để từ chối ghi đè khi hai cửa sổ gửi cùng một phiên.

## Huấn luyện và điều kiện nghiệm thu

FR-14/15/16 tiếp tục dùng các notebook có sẵn bên `solve_math_vlm`: `Model_Solve_Math_Qwen3_5_(4B)_Vision.ipynb`, `Knowledge_Black_box_Distillation.ipynb`, `Model_Qwen3_5_(4B)_Vision_GRPO.ipynb`. Chạy ở môi trường GPU phù hợp, tự đánh giá checkpoint rồi đăng ký đường dẫn/metrics trong trang quản trị. Trang quản trị không chạy huấn luyện hoặc hiển thị phần trăm giả. Đăng ký checkpoint không tự triển khai nó thành endpoint; người vận hành vẫn cần phục vụ model và cấu hình Qwen.

Chưa thể nghiệm thu nhận diện ảnh thật, tính đúng đắn mọi phản hồi, GRPO chống ảo giác, độ trễ Qwen ≤2.5s, RAG ≤800ms hoặc 60 FPS nếu chưa đo với hạ tầng/model thật. Kiểm tra JSON không thay thế đánh giá sư phạm và toán học.

## Kiểm thử

```bash
uv pip install --python .venv/bin/python -r requirements-test.txt
.venv/bin/python manage.py test learning -v 1
.venv/bin/python scripts/verify_stack.py
```

`verify_stack.py` tạo SQLite/tài khoản tạm, chạy Django:18000 + FastAPI:18001 + Vite:5180, vô hiệu hóa khóa model trong các tiến trình thử nghiệm và dọn sau khi xong. Không dùng dữ liệu học sinh thật hoặc gọi dịch vụ AI trả phí. Cần frontend nằm cạnh repo này; đặt `MINDGEO_FRONTEND` nếu đường dẫn khác. Chrome được tự tìm, có thể đặt `CHROME_PATH`.

Frontend: `npm test`, `npm run build`, `npm run test:e2e -- --project=demo` cho hồi quy bản mẫu. Chế độ live được kiểm tra qua script stack bên trên. Tài liệu của agent độc lập nằm ở `docs/testing/` và phân biệt kết quả thật, mock và các bước cần hạ tầng bên ngoài.
