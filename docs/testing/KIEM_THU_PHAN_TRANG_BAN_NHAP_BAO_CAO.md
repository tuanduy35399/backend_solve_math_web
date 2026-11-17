# Kiểm thử kho học liệu, lưu nháp và báo cáo — 10/11/2026

## Thay đổi

- Kho học liệu có 10/20/50 dòng/trang; API phân trang trên máy chủ, chỉ trả các trường của bảng. Tìm kiếm tiếng Việt bằng casefold và bộ lọc chạy trước khi phân trang, giữ nguyên quyền truy cập.
- Danh mục chung dùng phản hồi brief không có corpus_metadata; mở sửa hoặc đọc bài mới tải phần chi tiết. Danh mục chung vẫn chứa tên, công thức và nội dung ngắn để các màn hình khác sử dụng.
- Bộ lọc Xuất bản và Duyệt nội dung độc lập, có thể kết hợp; cả hai lựa chọn đầu ghi Tất cả. Chưa có ghi nhận duyệt được tính vào chưa duyệt.
- Bút chì tải bản đầy đủ rồi cuộn đến khung sửa, focus tên học liệu. Đổi trang cuộn lại đầu bảng.
- Nguồn tham khảo chưa điền đủ được giữ trong bản nháp. URL đã nhập vẫn phải hợp lệ; khi xuất bản, nguồn phải đầy đủ. Nguồn trống trong nháp được giữ thứ tự để lỗi máy chủ chỉ đúng dòng.
- API lỗi lồng nhau hiển thị nhãn trường và số nguồn; có lỗi dưới ô, khung thông báo lâu dài và liên kết focus ô sai. Nội dung chưa lưu được giữ; không hiện [object Object].
- Công cụ chuẩn bị bài dạy có mô tả dành cho giáo viên. Worker agent giữ hai tool gốc search_web/make_report của repo planning, trả mã lỗi kiểm soát thay vì lộ traceback/credentials.

## Kết quả thực thi

| Kiểm tra | Kết quả |
|---|---|
| `manage.py test learning --noinput` | 61/61 đạt, 25,354 giây; DB tạm; RAG tắt/provider mock |
| `manage.py test learning.test_research_errors --noinput` | 3/3 đạt; gateway lỗi, timeout và không lộ lỗi provider thô |
| `npm test` | 41/41 đạt |
| `npm run build` | Đạt |
| `scripts/verify_stack.py --corpus` | 15/15 live đạt, 38,7 giây; DB/tài khoản tạm, không gọi AI trả phí |
| Live tập trung sau bổ sung nhãn/công cụ giáo viên | 3/3 đạt, 10,5 giây; phân trang + lọc + scroll sửa, lưu nháp/lỗi nguồn, nhãn Tất cả và thông báo gateway |
| Playwright demo | 21/21 đạt, khoảng 1,3 phút; bao gồm biên tập bài, nguồn sai, lỗi lưu trữ và responsive |

## Kịch bản mới

1. Từ 94 bài, trang 1 có 10 dòng; trang 2 đổi nội dung; trang 10 có 4 dòng. Chọn bài cuối, bấm sửa, xác nhận tên được focus và khung sửa cách mép trên khoảng 20 px.
2. Tìm Pythagore trả cả bài thường và bài đảo. Duyệt một bài, lọc đã duyệt chỉ có bài đó; kết hợp Bản nháp trả rỗng; lọc chưa duyệt trả bài còn lại. Đổi điều kiện tìm đưa về trang 1.
3. Lưu nháp khi nguồn chỉ có tên, tải lại vẫn còn tên nguồn. Nhập URL sai, lưu lỗi chỉ rõ Nguồn tham khảo → 1 → Đường dẫn; bấm lỗi focus đúng URL; nội dung bài không mất. Sửa URL hợp lệ rồi lưu thành công.
4. Giáo viên thấy tiêu đề Công cụ chuẩn bị bài dạy, hai nhãn Xuất bản/Duyệt nội dung đều có lựa chọn Tất cả. Phản hồi gateway 503 fixture được hiện bằng thông báo cụ thể.
5. Backend: phân trang ổn định, trường lớn không nằm trong bảng/brief; tìm kiếm Đ/đ; lọc duyệt đối với metadata trống; học sinh không dò được bản nháp riêng qua search, brief hoặc detail; xuất bản không nhận nguồn thiếu trường.

## Chẩn đoán và kiểm tra báo cáo thật

Lỗi người dùng gặp được tái hiện: gateway local cổng 20128 chưa lắng nghe, HTTP client báo Connection refused; worker dừng với OpenAIConnectionError. Đã chạy 9router theo chỉ dẫn người dùng, bind loopback, không cập nhật package. Cổng 20128 đã lắng nghe.

Đã gọi lại create_report cho chủ đề Tính chất và dấu hiệu hình vuông bằng gateway/model và Tavily thật: worker tạo báo cáo 4.259 ký tự, 20 mục nguồn tìm kiếm (không khẳng định là 20 URL duy nhất). Chạy trong thư mục tạm, không ghi báo cáo kiểm thử vào DB người dùng. Không phải đánh giá chất lượng học thuật hoặc độ đúng của mọi nguồn.

Log: data/material-pagination-backend-tests.log, data/research-error-tests.log, data/material-pagination-browser-tests.log, data/material-pagination-focused-tests.log và data/report-recheck.log. Ảnh ở docs/images/material-pagination.png, material-editor-scroll.png, story-draft-errors.png, teacher-report-error.png. UI lỗi báo cáo dùng fixture; worker báo cáo được chạy thật riêng.

Qwen vẫn chưa triển khai GPU; lượt này không nghiệm thu chat giải toán thật. Camera/cảm ứng dùng Chromium mô phỏng, chưa chạy thiết bị thật.
