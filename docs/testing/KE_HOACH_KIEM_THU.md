# Kế hoạch kiểm thử MindGeoTutorAI

Ngày lập: 09/11/2026. Người thực hiện: agent kiểm thử độc lập với agent triển khai. Tài liệu áp dụng cho frontend React/Vite trong `solve_math_vlm/frontend`, backend Django REST/FastAPI trong `backend_solve_math_web`, SRS v1.1 và yêu cầu bổ sung của chủ đề tài.

Mục tiêu là kiểm tra các luồng sử dụng, dữ liệu và quyền truy cập sau khi nối backend. Báo cáo phân biệt rõ kiểm thử ứng dụng thật qua HTTP/trình duyệt, kiểm thử logic bằng mock và phần chưa thể nghiệm thu khi thiếu hạ tầng AI. Không dùng số lượng test đạt để kết luận chất lượng toán học của model đã được chứng minh.

## Phạm vi

- Đăng ký học sinh, đăng nhập/đăng xuất, cập nhật hồ sơ, phân quyền giáo viên/quản trị viên và thu hồi token.
- Gửi văn bản/ảnh tới nhánh chat Qwen, xử lý thiếu cấu hình, lưu phiên học, cô lập dữ liệu theo tài khoản và đồng bộ hình học.
- Quiz biên soạn sẵn: tải câu hỏi không lộ đáp án, chấm tại máy chủ, lưu kết quả và cập nhật lỗ hổng kiến thức.
- Học liệu: tạo, xuất bản, sửa/xóa theo quyền; quan hệ tiên quyết không trùng hoặc tạo vòng lặp; bản đồ kiến thức và thống kê.
- Ranh giới Hybrid RAG, model sinh học liệu bên ngoài, agent nghiên cứu và giới hạn số lượt gọi.
- Giao diện desktop/mobile, thao tác hình học và hồi quy các luồng cũ trong chế độ demo.

Huấn luyện LoRA/KD/GRPO, độ đúng của Qwen thật, truy xuất BGE-M3/Chroma/Neo4j thật, gọi Gemini/OpenAI/Tavily thật và tải lớn nằm trong đợt nghiệm thu tích hợp tiếp theo. Các thành phần này cần trọng số, dịch vụ, bộ dữ liệu nghiệm thu và cấu hình phù hợp; không được thay bằng mock rồi ghi kết quả đạt cho model thật.

## Môi trường và dữ liệu

Dùng Python của `.venv` backend, Chrome headless và bộ công cụ có sẵn của dự án. `scripts/verify_stack.py` tạo SQLite tạm, migrate, thêm học liệu/quiz seed và ba tài khoản QA có mật khẩu ngẫu nhiên. Các cổng kiểm thử là Django `18000`, FastAPI `18001`, frontend `5180`. Script vô hiệu hóa khóa AI trong môi trường tiến trình con và dọn dịch vụ/database sau khi chạy.

Kiểm thử Django dùng database test riêng. Chế độ demo dùng frontend `5174` và bộ nhớ trình duyệt riêng theo test. Không ghi vào database làm việc `db.sqlite3`, không đọc/in giá trị trong `.env`, không gọi dịch vụ có phí hoặc cơ sở dữ liệu Neo4j của người dùng.

Dữ liệu thử bao gồm câu hỏi hình học ngắn, ảnh PNG tạo tại chỗ, file giả ảnh, tài khoản khác chủ sở hữu, câu trả lời quiz đúng/sai, quan hệ ngược gây chu kỳ và JSON không hợp lệ. Dữ liệu nguồn học sinh thật không được dùng làm fixture.

## Cách chạy

Từ backend:

```bash
.venv/bin/python manage.py test learning -v 1
.venv/bin/python scripts/verify_stack.py
```

Từ frontend:

```bash
npm test
npm run build
npm run test:e2e -- --project=demo
```

`learning/tests.py` bao phủ API, lưu trữ, quyền truy cập và provider mock. `learning/test_qa.py` bổ sung các trường hợp đầu vào và quyền sở hữu do agent QA chọn độc lập. `tests/live.spec.js` đi qua frontend, proxy, Django/FastAPI và SQLite thật trên môi trường tạm. Các test còn lại trong `tests/` kiểm tra hồi quy bản demo, không chứng minh tích hợp AI.

## Thứ tự và tiêu chí

1. Chạy kiểm tra backend, unit frontend và build để phát hiện lỗi nền tảng.
2. Chạy E2E live trên database tạm; xác nhận dữ liệu còn sau tải lại và lỗi không làm mất nội dung đang nhập.
3. Kiểm thử đầu vào/đặc quyền bằng API trực tiếp; không dựa vào việc nút bị ẩn ở giao diện.
4. Chạy hồi quy demo, xem ảnh chụp và kiểm tra màn hình nhỏ; phân biệt lỗi test selector với lỗi chức năng.
5. Ghi lại lỗi với bước tái hiện, kỳ vọng và thực tế; agent triển khai sửa, QA chạy lại phạm vi liên quan.
6. Khi có hạ tầng AI, chạy các kịch bản tích hợp còn chờ bằng dữ liệu toán đã được giáo viên xác nhận.

Điều kiện hoàn tất đợt ứng dụng: các luồng cốt lõi nêu trên đạt; không còn lỗi mở khiến mất dữ liệu, nâng quyền hoặc truy cập dữ liệu người khác; lỗi cấu hình được hiển thị rõ; báo cáo có kết quả thực tế và phần chưa chạy. Chỉ nghiệm thu toàn bộ SRS khi các AC cần model và cơ sở tri thức thật cũng đạt.

## Quy ước kết quả

| Trạng thái | Ý nghĩa |
|---|---|
| PASS | Đã thực thi và quan sát đúng kỳ vọng trong phạm vi ghi rõ |
| FAIL | Đã thực thi và khác kỳ vọng; có bước tái hiện |
| BLOCKED | Chưa thể chạy do thiếu cấu hình, model hoặc dịch vụ bắt buộc |
| NOT RUN | Chưa thực hiện phép đo/kịch bản; không suy diễn kết quả |
| PARTIAL | Một phần đã kiểm tra; phần còn lại được chỉ rõ |

## Kiểm thử nghiệm thu khi dịch vụ sẵn sàng

- Qwen: chạy tập đề ảnh/văn bản có đáp án kiểm định; đánh giá nhận diện ký hiệu, câu hỏi gợi mở đầu tiên, nhận xét lỗi và số trường hợp tiết lộ đáp án ngay. Đo thời gian đến phản hồi đầu tiên, không suy từ thời gian mock.
- Hybrid RAG: nhập kho học liệu có nguồn, đồng bộ chỉ mục, thử câu sai định lý có tiên quyết biết trước; đối chiếu từng nút Neo4j và chunk Chroma được trả về. Đo truy xuất ở trạng thái lạnh/ấm.
- Sinh bài tập/quiz: kiểm tra payload chỉ có ngữ cảnh học thuật, không có PII/ảnh/chat; gọi provider đã chọn; giáo viên đối chiếu nội dung và đáp án; kiểm tra hạn mức và lỗi provider.
- Agent báo cáo: kiểm tra nguồn thực, báo cáo Markdown tải được, quyền xem báo cáo và việc nguồn web chưa kiểm chứng không tự nhập vào kho kiến thức.
- Huấn luyện: chạy notebook LoRA/KD/GRPO trên phần cứng phù hợp; lưu cấu hình, seed, tập đánh giá, checkpoint và metrics. Đăng ký metadata trên web không thay thế bằng chứng chạy huấn luyện.
- Phi chức năng: đo các ngưỡng SRS (phản hồi Qwen ≤ 2,5 giây, truy xuất ≤ 800 ms, tương tác hình học 60 FPS) với máy và bộ dữ liệu được ghi nhận; thử Safari/Firefox và thiết bị cảm ứng thật nếu nằm trong phạm vi nghiệm thu.
