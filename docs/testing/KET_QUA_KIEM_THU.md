# Kết quả kiểm thử MindGeoTutorAI

Ngày thực hiện: 09/11/2026. Agent QA đã chạy kiểm thử độc lập trên database tạm và thông báo lỗi cho agent triển khai để sửa. Các kiểm tra ứng dụng trong đợt này đạt sau khi sửa lỗi mã học liệu trùng. Chưa đủ căn cứ nghiệm thu các yêu cầu cần Qwen, kho Hybrid RAG, provider ngoài hoặc GPU thật.

## Kết quả thực thi

| Lệnh | Kết quả | Phạm vi và giới hạn |
|---|---|---|
| `.venv/bin/python manage.py check` | PASS, không có lỗi hệ thống | Kiểm tra cấu hình Django; không phải kiểm tra kết nối AI |
| `.venv/bin/python manage.py test learning -v 1` | PASS 33/33, khoảng 25 giây | 21 ca ban đầu và 12 ca QA độc lập; SQLite test riêng; provider được mock ở ca cần AI |
| `.venv/bin/python scripts/verify_stack.py` | PASS 6/6 E2E live | Trình duyệt → Vite proxy → Django/FastAPI → SQLite tạm thật; provider chưa cấu hình |
| `npm test` | PASS 16/16, 3 file test | Logic frontend, câu chuyện và authoring |
| `npm run build` | PASS | Frontend production build thành công |
| `npm run test:e2e -- --project=demo` | PASS 21/21, khoảng 1,4 phút | Hồi quy bản demo, thao tác hình học, ảnh, quiz, lịch sử, câu chuyện, responsive và các tập quy tắc axe trong test |

Tổng cộng 76 ca tự động đạt trong các nhóm trên; số này không bao gồm `manage.py check` hay build và không có nghĩa toàn bộ SRS đã được nghiệm thu. Thời gian chạy bộ test không phải số đo hiệu năng model, độ trễ truy xuất hoặc FPS.

Database làm việc không được dùng để kiểm thử ghi. Script E2E tạo tài khoản giả với mật khẩu ngẫu nhiên, vô hiệu hóa khóa AI trong tiến trình con, rồi dọn dịch vụ và database tạm. Không đọc/in khóa `.env`, không gọi Gemini/OpenAI/Tavily có phí hoặc truy vấn Neo4j của người dùng.

## Những hành vi đã xác nhận

- Đăng ký công khai chỉ tạo học sinh; không nâng vai trò bằng payload đăng ký hoặc cập nhật hồ sơ. Đăng xuất/đổi vai trò thu hồi token; tài khoản bị khóa không sử dụng FastAPI được.
- Người dùng không đọc hoặc gửi tiếp phiên/quiz riêng của tài khoản khác. Xóa dữ liệu học tập của một người không xóa dữ liệu người khác.
- Chấm quiz tại máy chủ, không tin điểm client tự khai; đáp án và giải thích được ẩn trước khi nộp; các chỉ số/bool/chuỗi đáp án không hợp lệ bị từ chối. Điểm và gap còn sau tải lại.
- Giáo viên tạo/xuất bản/xóa học liệu trên server; học liệu nháp không lộ cho người khác; giáo viên không sửa/xóa học liệu của giáo viên khác. Quan hệ trùng hoặc gây chu kỳ bị chặn.
- Khi thiếu Qwen, có thông báo rõ, đề đang nhập được giữ, không lưu phản hồi gia sư giả và không fallback sang cloud. Ảnh giả bị chặn theo bytes; ảnh hợp lệ được chuyển tới provider nội bộ mock.
- Với HTTP mock cho cả Gemini và OpenAI, request chỉ chứa ngữ cảnh học thuật được chọn; các sentinel tên học sinh, ảnh và hội thoại ngoài gói context không xuất hiện trong payload.
- Thuật toán `HybridSearch`/RRF được nạp trực tiếp từ repo gốc và cho kết quả đúng trên node thử kiểm soát. Đây không phải kiểm thử Chroma, Neo4j hay BGE-M3 thật.
- Bài viết nháp hợp lệ có thể lưu, xuất bản và đọc theo quyền; bài sai cấu trúc hoặc URL nguồn `javascript:` bị từ chối mà không ghi đè nội dung hợp lệ.
- Metadata checkpoint chỉ dành cho admin, kiểm tra metrics JSON và không khởi chạy tiến trình huấn luyện. Không coi bản ghi metadata là model đã huấn luyện.
- Workspace live hiển thị đúng ở desktop 1440×1000 và mobile 390×844; kiểm tra không tràn ngang. Ảnh đã được xem để kiểm tra bố cục, không chỉ dựa vào build. Mobile screenshot chờ bootstrap và transition sidebar hoàn tất.

## Lỗi phát hiện và kiểm tra lại

| Mã | Tái hiện và tác động | Xử lý và kết quả cuối |
|---|---|---|
| BUG-01 | Giáo viên POST `/api/v1/materials/` với mã `id=trig` đã có và các trường còn lại hợp lệ. Máy chủ trả 500 do trùng khóa thay vì lỗi validation 400; bản gốc không bị ghi đè. | Agent triển khai thêm `UniqueValidator` cho trường id. `test_duplicate_material_id_is_validation_error` và bộ backend 33/33 đã chạy lại PASS. Đã đóng. |
| TEST-01 | E2E giáo viên chờ `getByLabel('Trạng thái', exact:true)` nên hết thời gian trước khi lưu form. | Lỗi định vị trong test; đổi sang select trạng thái nằm trong form học liệu. Live E2E chạy lại 6/6 PASS. |
| TEST-02 | Screenshot ngay sau điều hướng/đổi viewport có thể bắt khung đăng nhập tạm hoặc sidebar đang chuyển động. | Bổ sung chờ `.app-shell`, font và sidebar ra khỏi viewport trước ảnh mobile; không xem khung chuyển tiếp là bằng chứng lỗi mất đăng nhập. |

Không còn lỗi chức năng đã xác nhận đang mở trong các kịch bản thực thi của đợt này. Đây không phải tuyên bố ứng dụng không còn lỗi ngoài phạm vi kiểm tra.

## Phần chưa nghiệm thu

| Thành phần | Trạng thái | Việc còn cần làm |
|---|---|---|
| Qwen thật — FR-04 đến FR-06, AC-01/AC-05 | BLOCKED | Chưa có máy chủ model local. Kiểm định ảnh, ký hiệu, nhận xét toán, Socratic và việc không tiết lộ đáp án bằng tập đề giáo viên duyệt |
| BGE-M3/Chroma/Neo4j — FR-10/FR-11, phần đầy đủ FR-12/AC-03 | BLOCKED | Cài phần AI tùy chọn, chạy dịch vụ, nhập/đồng bộ học liệu và đối chiếu chunk/tiên quyết thật; chưa tải model embedding trong QA |
| Sinh học liệu ngoài — FR-13/AC-04 | BLOCKED cho provider thật | HTTP/payload, lưu và chấm được kiểm tra bằng mock/quiz biên soạn sẵn; chưa xác nhận chất lượng tóm tắt/bài tập/đáp án do Gemini hoặc OpenAI sinh thật |
| Agent web/report | BLOCKED cho pipeline thật | Quyền API được kiểm tra; chưa chạy vòng agent/Tavily/model và tạo báo cáo nguồn thực |
| LoRA/KD/GRPO — FR-14 đến FR-16 | BLOCKED cho huấn luyện | Chưa chạy notebook/GPU hoặc kiểm định checkpoint; chỉ kiểm thử metadata |
| NFR độ trễ, FPS, chi phí và tải | NOT RUN | Chưa đo Qwen ≤ 2,5 giây, retrieval ≤ 800 ms, hình học 60 FPS hoặc tải đồng thời trên phần cứng đích |
| Safari/Firefox, camera và cảm ứng thiết bị thật | NOT RUN | Chrome headless không chứng minh tương thích đầy đủ trên các thiết bị/trình duyệt này |

## Mã nguồn và bằng chứng

Hai checkout nguồn giữ nguyên phần code đã theo dõi: `git diff --stat` không có thay đổi. Revision được đối chiếu:

- `hybrid_graph_rag`: `97e35e9370465293d07c0b85273fbe06c928340c`.
- `ai_agent_game_maker_plan`: `c25184e37fc661e04a5d9deb14edde8af46e1159`.

Các test độc lập nằm ở `learning/test_qa.py`. Kế hoạch và ma trận 41 kịch bản/FR/AC nằm trong hai tài liệu cùng thư mục. Ảnh QA nằm tại `solve_math_vlm/frontend/.qa/live-desktop.png`, `.qa/live-mobile.png` và `.qa/demo-review/`; đây là bằng chứng nội bộ không đưa vào Git. Các helper chụp ảnh hồi quy đã đổi từ `.impeccable/review` sang `.qa/demo-review` để không ghi đè ảnh baseline được theo dõi.

Có cảnh báo không làm hỏng test về Starlette TestClient/httpx và biến màu terminal. Không có lỗi runtime frontend được ghi nhận trong các E2E live đã chạy. Không suy diễn các cảnh báo này thành kết quả kiểm thử AI.
