# Kịch bản sử dụng MindGeoTutorAI

Team DuyPy · 09/11/2026

Đây là các kịch bản thao tác để sử dụng hoặc trình diễn sản phẩm; không phải tuyên bố đã nghiệm thu mọi câu trả lời của AI. Xem [User guide](USER_GUIDE.md) cho thao tác chi tiết.

## SC-01 — Học sinh lớp 6 tìm đúng kiến thức của mình

**Mục tiêu:** xem và ôn bài lớp 6 mà không bị dẫn sang kiến thức lớp 7 bắt buộc.

**Chuẩn bị:** tài khoản học sinh, hồ sơ đặt lớp 6, corpus đã xuất bản.

1. Đăng nhập → Bản đồ kiến thức.
2. Xác nhận **Lớp đang xem = Lớp 6**; các ô hiện lớp 6.
3. Chọn bài **Trung điểm của đoạn thẳng**.
4. Đọc mục **Cần nắm trước**, mở bài nền được liệt kê rồi quay lại bài trung điểm.
5. Bấm **Ôn kiến thức này** để đọc phát biểu và ví dụ.
6. Kéo một ô vuông và kéo nền; dùng **Vừa khung** rồi **Bài đang chọn** để điều chỉnh vùng nhìn.
7. Chọn **Tất cả các lớp**, xem nhãn lớp và chiều mũi tên; chọn lại lớp 6 khi ôn. Vị trí ô không phải thứ tự học.
8. Trên máy tính, bấm **Ẩn thanh bên**, tải lại trang rồi bấm **Hiện thanh bên** để kiểm tra menu vẫn mở lại được.

**Kết quả mong đợi:** lớp không trộn ngẫu nhiên, chỉ quan hệ thật có mũi tên. Chọn xem trước lớp 7 không trở thành điều kiện phải học cho lớp 6.

## SC-02 — Dùng quiz tìm phần cần củng cố

**Mục tiêu:** kiểm tra kiến thức, xem giải thích và ôn lại đúng bài.

**Chuẩn bị:** học sinh đã học chủ đề tương ứng; có bộ quiz biên soạn sẵn.

1. Ôn tập & trắc nghiệm → Trắc nghiệm chẩn đoán.
2. Chọn bộ tam giác vuông, bấm Bắt đầu 4 câu hỏi.
3. Trả lời đủ câu hỏi, có thể cố ý chọn sai một câu khi trình diễn.
4. Nộp bài → xem điểm và giải thích.
5. Ở câu sai, bấm **Ôn kiến thức này**.
6. Mở **Kết quả của bạn** rồi tải lại trang để kiểm tra kết quả vẫn còn.

**Kết quả mong đợi:** máy chủ chấm điểm và lưu kết quả. Bài được mở theo đúng lớp của nó; việc ghi nhận cần ôn không được diễn giải thành đánh giá năng lực tuyệt đối.

## SC-03 — Tạo bài tập và quiz mới bằng Gemini

**Mục tiêu:** luyện thêm từ một bài cụ thể trong cơ sở dữ liệu.

**Chuẩn bị:** gateway Gemini, Neo4j/Chroma và chỉ mục đã sẵn sàng; còn hạn mức sinh học liệu.

1. Tủ kiến thức → chọn lớp 8 → bài Định lý Pythagore.
2. Bấm **Tìm kiến thức tiên quyết**; đối chiếu danh sách kiến thức nền.
3. Bấm **Tạo bài tập & quiz từ học liệu** và chờ kết quả.
4. Đọc tóm tắt, tự giải bài; chỉ mở gợi ý khi cần.
5. Bấm **Làm quiz vừa tạo**, làm đủ câu rồi nộp.
6. Mở quiz đã lưu để tiếp tục sau đó.

**Kết quả mong đợi:** có tóm tắt, bài tự luyện và quiz dựa trên ngữ cảnh truy xuất; câu hỏi riêng tư theo tài khoản và chấm tại máy chủ. Giáo viên cần đối chiếu đáp án AI.

**Nhánh lỗi:** nếu chỉ mục cũ/hết hạn mức/nhà cung cấp lỗi, ứng dụng báo rõ; không đổi sang quiz mẫu rồi gắn nhãn là quiz mới sinh.

## SC-04 — Chọn đề trên laptop và điện thoại

**Mục tiêu:** có ảnh đề rõ, đúng chiều trước khi gửi.

1. Trên laptop: xác nhận chỉ có **Tải ảnh lên**, không có nút Chụp ảnh; chọn JPG hoặc kéo thả vào vùng ảnh.
2. Trên thiết bị di động cảm ứng: bấm **Chụp ảnh** hoặc tải ảnh sẵn có. Cách mở camera tùy trình duyệt.
3. Xoay ảnh/cắt vùng chứa đề, bổ sung câu hỏi.
4. Chưa cấu hình Qwen: gửi thử sẽ báo chưa sẵn sàng và giữ đầu vào.

**Kết quả mong đợi:** không kích hoạt webcam laptop; ảnh chọn được chưa bị coi là đã được AI phân tích. Nếu ảnh không hợp lệ, có thông báo để chọn lại.

## SC-05 — Học Socratic khi đã có máy chạy Qwen

**Chỉ thực hiện khi:** endpoint Qwen thật đã được triển khai và kiểm tra theo QWEN_DEPLOYMENT.md. Hiện kịch bản này đang chờ GPU.

1. Nhập đề: “Cho tam giác ABC vuông tại A, AB = 3 cm, AC = 4 cm. Em cần tìm BC.”
2. Gửi đề; quan sát câu hỏi gợi mở thay vì chờ đáp án cuối được đưa ngay.
3. Trả lời cạnh huyền là BC, tiếp tục giải theo từng câu hỏi.
4. Nếu trả lời sai, đọc gợi ý và liên kết ôn tập.
5. Quan sát hình khi model cung cấp được cấu hình phù hợp.
6. Kết thúc phiên, mở Lịch sử học tập để tiếp tục hoặc xem lại.

**Tiêu chí đánh giá bởi giáo viên:** nhận diện đúng dữ kiện, hướng dẫn Socratic, nhận xét bước làm hợp lý và không bịa hình/số đo. Kịch bản không mặc định đã đạt chỉ vì endpoint trả JSON.

## SC-06 — Giáo viên sửa, duyệt và đồng bộ một bài

**Mục tiêu:** học sinh đọc được nội dung đã cập nhật, giữ được nguồn đối chiếu.

1. Kho học liệu → tìm bài trên toàn kho, chọn trang hoặc kết hợp bộ lọc xuất bản/duyệt → bấm biểu tượng bút chì. Trang tự cuộn đến trình sửa và tập trung vào tên học liệu.
2. Kiểm tra lớp, phát biểu, công thức, ghi chú và nguồn.
3. Sửa ghi chú, lưu và mở lại để xác nhận URL nguồn không bị mất.
4. Đối chiếu nội dung rồi bấm dấu kiểm **Duyệt nội dung …**.
5. Bấm **Thử đồng bộ chỉ mục**.
6. Mở bài ở Tủ kiến thức, kiểm tra nội dung và trạng thái duyệt.
7. Nếu xem đồ thị model mà nguồn đã thay đổi, thực hiện lại bước trích xuất offline theo hướng dẫn; không dùng bằng chứng cũ.

**Kết quả mong đợi:** sửa nội dung làm mất nhãn duyệt cũ cho tới khi duyệt lại. Chỉ mục stale bị báo cần đồng bộ; không âm thầm sinh bài từ nội dung cũ.

## SC-07 — Giáo viên thiết lập một quan hệ đúng hướng

**Mục tiêu:** mô tả kiến thức nền, không tạo lộ trình bắt học vượt lớp.

1. Kho học liệu → Quan hệ tiên quyết.
2. Chọn bài nền lớp 6 làm nguồn và bài phụ thuộc lớp 7 làm đích, chỉ thêm nếu có căn cứ sư phạm.
3. Thử thêm trùng: hệ thống từ chối.
4. Thử chọn nguồn lớp 7 → đích lớp 6: hệ thống từ chối quan hệ ngược lớp.
5. Với các bài cùng lớp, thử tạo cạnh khép kín vòng lặp: hệ thống từ chối.
6. Đồng bộ chỉ mục và quan sát bản đồ.

**Kết quả mong đợi:** các mũi tên phản ánh quan hệ được lưu, không phải thứ tự ô trong giao diện. Muốn đổi lớp một bài mà làm cạnh hiện có trở thành ngược lớp, phải điều chỉnh quan hệ trước.

## SC-08 — Giáo viên nghiên cứu nguồn bổ trợ

**Mục tiêu:** có báo cáo tham khảo kèm nguồn, chưa tự xuất bản vào corpus.

1. Trong Kho học liệu, chọn một bài đã xuất bản.
2. Bấm **Tìm nguồn web & lập báo cáo**.
3. Đọc báo cáo, mở các URL nguồn và đối chiếu nội dung.
4. Tải báo cáo Markdown; mở **Báo cáo đã lưu** để xem lại.

**Kết quả mong đợi:** báo cáo được lưu theo quyền tài khoản. Các kết quả tìm kiếm không đồng nghĩa mọi nguồn đều được báo cáo sử dụng hoặc đã được giáo viên duyệt.

## SC-09 — Quản trị viên kiểm tra dịch vụ và hạn mức

1. Mô hình & hệ thống → **Kiểm tra kết nối**.
2. Phân biệt “đã khai báo cấu hình” với kết quả kiểm tra trực tiếp.
3. Xác nhận hạn mức sinh học liệu là **100 lượt/ngày toàn hệ thống**.
4. Nếu đổi vai trò một tài khoản, yêu cầu tài khoản đó đăng nhập lại.
5. Đăng ký checkpoint/metrics khi đã có kết quả huấn luyện bên ngoài.

**Kết quả mong đợi:** kiểm tra kết nối không gọi sinh nội dung; có checkpoint chưa đồng nghĩa đang phục vụ Qwen. Đồ thị offline không trừ hạn mức sinh học liệu của web.

## Gợi ý trình diễn niên luận khi chưa có GPU

Thực hiện SC-01 → SC-02 → SC-03 → SC-06 → SC-08 → SC-09. Dùng SC-04 để giải thích nhập ảnh và thông báo Qwen chưa sẵn sàng. Giới thiệu SC-05 là phần chờ hạ tầng, không đóng vai một cuộc hội thoại mẫu rồi trình bày thành kết quả của checkpoint thật.
