# Kiểm thử giao diện học tập — 09/11/2026

> Cập nhật sau lượt kiểm thử bên dưới: đã bỏ chức năng Giãn & gỡ rối theo yêu cầu người dùng. Các kết quả UI-03 và số test dưới đây mô tả phiên bản trước khi bỏ; xem đợt kiểm tra bổ sung ở cuối tài liệu.

## Phạm vi

Bản đồ ô vuông kéo thả, bộ lọc lớp, nút Giãn & gỡ rối, Markdown/công thức, camera di động và sidebar thu gọn/ẩn hiện. Đây là lượt kiểm thử của agent triển khai; báo cáo QA độc lập trước đó nằm ở NGHIEM_THU_WEB_TICH_HOP.md.

## Kết quả đã chạy

| Lệnh | Kết quả | Phạm vi |
|---|---|---|
| `npm test` | 32/32 đạt | Sắp xếp dữ liệu, chống chồng ô, kéo ô ghim, giảm giao cắt, Markdown và LaTeX; hồi quy câu chuyện |
| `npm run build` | Đạt | Build Vite production |
| `npm run test:e2e -- --project=demo` | 21/21 đạt, 2 phút | Hình học, ảnh, quiz, lịch sử, biên tập, phân quyền demo, responsive và các kiểm tra axe trong bộ test |
| `.venv/bin/python scripts/verify_stack.py --corpus` | 11/11 đạt, 43,3 giây | React → proxy → Django/FastAPI → SQLite tạm; corpus 94 bài; provider được tắt/mock ở ca cần AI |
| `npm audit --omit=dev --audit-level=moderate` | 0 lỗ hổng được báo | Dependencies production tại thời điểm chạy |

## Kịch bản mới

| Mã | Thao tác | Kết quả đã xác nhận |
|---|---|---|
| UI-01 | Hồ sơ lớp 6 → Bản đồ; chuyển tất cả/lớp 7 | Mặc định đúng lớp, lớp 6 có 17 bài; chọn tất cả có lớp 6–9; có nhãn lớp và chi tiết bài |
| UI-02 | Chọn bài bằng danh sách; kéo ô, zoom, Vừa khung, Bài đang chọn | Chọn đúng bài, đổi tọa độ thật, đổi tỷ lệ nhìn; các ô vuông không chồng nhau sau ổn định |
| UI-03 | Giãn & gỡ rối | Bố trí mới có khoảng cách; kiểm thử logic xác nhận số giao cắt đoạn nối không tăng với bộ dữ liệu thử. Không cam kết đồ thị bất kỳ có thể hết mọi giao cắt |
| UI-04 | Desktop, desktop thu nhỏ và trình duyệt mobile có touch | Chụp ảnh ẩn trên desktop kể cả cửa sổ hẹp, hiện trên mobile touch; tải ảnh vẫn hiện |
| UI-05 | Học sinh tìm kiến thức nền và tạo nội dung với phản hồi fixture | Không thấy BGE-M3/Chroma/Neo4j/RRF hoặc nút đồ thị trích xuất; Markdown đậm/danh sách và công thức nội dòng/riêng dòng hiển thị đúng |
| UI-06 | Admin ở 1280×640 → Ẩn thanh bên → tải lại → Hiện thanh bên | Sidebar vừa chiều cao, không còn khối trang trí lớn, thanh cuộn menu được ẩn; phần nội dung mở rộng; lựa chọn ẩn được nhớ |
| UI-07 | Chuyển 390×844 → mở/đóng menu | Nút menu điện thoại hoạt động, không bị lựa chọn ẩn desktop khóa mất menu |

## Điều chỉnh bộ kiểm thử

Các ca đăng nhập liên tiếp cùng dùng IP loopback nên đã chạm giới hạn 10 lượt/phút. Harness nay tạo settings và DummyCache chỉ trong thư mục/tiến trình QA tạm, tránh throttle làm sai lệch kiểm thử giao diện. Giới hạn đăng nhập của ứng dụng thật không bị đổi; bộ E2E này không nghiệm thu throttle. Dịch vụ QA được dọn theo process group để không để lại Vite con.

## Bằng chứng và giới hạn

- Log live: `data/latest-ui-live-tests.log`.
- Ảnh đã xem trực quan: `docs/images/sidebar-gon.png`, `sidebar-an.png`, `ban-do-lop7-desktop.png`, `ban-do-lop6-mobile.png`, `noi-dung-markdown.png`.
- DB kiểm thử riêng, không ghi tài khoản/bài thử vào DB làm việc; không gọi sinh nội dung trả phí trong lượt này.
- Phản hồi Markdown được fixture để kiểm tra hiển thị, không phải đánh giá độ đúng toán của Gemini. Công thức cũ không có dấu phân cách toán vẫn là văn bản thường.
- Camera/gesture dùng Chromium mô phỏng; chưa kiểm tra thiết bị camera thật, Safari hoặc Firefox.
- Qwen vẫn chờ GPU/endpoint của tác giả; không nghiệm thu chat/nhận ảnh thật.

## Bổ sung: bỏ Giãn & gỡ rối theo yêu cầu

Đã xóa nút, trạng thái xử lý và thuật toán thử nhiều bố trí/giao cắt chỉ dùng cho nút này. Đã cập nhật user guide, kịch bản sử dụng và ảnh bản đồ.

- `npm test`: 31/31 đạt; bỏ một test của chức năng đã xóa.
- `npm run build`: đạt.
- `scripts/verify_stack.py --corpus --grep 'free graph filters grades'`: 1/1 đạt, 12,9 giây; xác nhận không có nút, chọn lớp/bài, kéo ô, thu phóng, vừa khung và giao diện mobile.
- Log: `data/remove-untangle-browser-tests.log`.

## Bổ sung 10/11/2026: ngày giờ, tìm kiếm và hồ sơ theo vai trò

- Ngày cập nhật học liệu dùng `DD/MM/YYYY · HH:mm`, theo múi giờ Việt Nam; giữ tương thích ngày demo dạng DD/MM/YYYY.
- Chuyển vòng focus của tìm kiếm ra khung bao cả biểu tượng và ô nhập; không còn vòng viền riêng lệch bên trong.
- Hồ sơ giáo viên/quản trị viên không hiện lớp đang học hoặc nút xuất/xóa dữ liệu học tập. Sidebar ghi đúng vai trò, không hiện badge kiến thức cần ôn; bảng quản trị chỉ hiện lớp cho học sinh. Lưu tên staff không gửi trường grade.
- `npm test`: 36/36 đạt; gồm ngày ISO với microseconds, chuyển múi giờ qua ngày mới, ngày demo và ngày thiếu/sai.
- `npm run build`: đạt.
- Live E2E tập trung: 4/4 đạt trong 9,1 giây; học sinh đăng ký/lưu hồ sơ, ngày & focus tìm học liệu, giáo viên và quản trị viên lưu tên/tải lại, kiểm tra không tràn ngang mobile.
- Các lượt E2E dùng DB và tài khoản QA tạm, không ghi dữ liệu thử vào DB làm việc, không gọi AI. Log: `data/role-date-ui-tests.log`.
- Đã xem ảnh desktop: `docs/images/tim-kiem-ngay-cap-nhat.png`, `cai-dat-giao-vien.png`, `cai-dat-quan-tri.png`.

Hồi quy demo tập trung: 2/2 đạt trong 4,9 giây (biên soạn học liệu/quan hệ và responsive các trang ở 390/320 px, gồm Cài đặt).
