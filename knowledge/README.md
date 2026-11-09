# Học liệu hình học lớp 6 đến lớp 9

Bộ khởi đầu ngày 09/11/2026 gồm **88 bài Markdown** được biên soạn bằng cách đối chiếu **55 trang lý thuyết công khai của VietJack**. Phát biểu toán được diễn giải lại; ví dụ, lỗi thường gặp và câu hỏi Socratic được tự biên soạn. Các bài đang ở trạng thái **chờ giáo viên duyệt**, không phải sách giáo khoa chính thức hoặc bộ đã nghiệm thu đầy đủ chương trình.

Phạm vi lớp/chủ đề tham chiếu cách sắp xếp của học liệu Kết nối tri thức theo CTGDPT 2018. Lớp 6 có khái niệm, tính chất trực quan và công thức nền tảng, không gọi chung tất cả là định lý. Pythagore đặt ở lớp 8; lượng giác, đường tròn và hình cầu ở lớp 9. Hình lăng trụ đứng đặt ở lớp 7. Một số hệ quả/chiều đảo có ghi chú bổ sung, bài diện tích tam giác lớp 7 được ghi là ôn tập kiến thức nền.

## Nội dung

| Lớp | Số bài | Nhóm chủ đề |
|---|---:|---|
| 6 | 17 | Điểm, tia, đoạn thẳng, trung điểm, góc, nhận dạng hình, diện tích, đối xứng |
| 7 | 25 | Song song, tam giác bằng nhau, tam giác cân, bất đẳng thức, đồng quy, hình hộp và lăng trụ đứng |
| 8 | 22 | Tứ giác, Thalès, phân giác, đường trung bình, đồng dạng, Pythagore, hình chóp đều |
| 9 | 24 | Lượng giác, đường tròn, cung/quạt, tiếp tuyến, nội/ngoại tiếp, đa giác đều, phép quay, trụ/nón/cầu |

Xem [mục lục từng bài](INDEX.md). Trong `markdown/`, mỗi bài có một mã kiến thức riêng và các phần phát biểu, điều kiện, công thức LaTeX, ví dụ có lời giải ngắn, lỗi thường gặp, câu hỏi gợi mở, tiên quyết và nguồn đối chiếu.

## Nguồn và cách thu thập

- Lấy danh sách bài từ mục lý thuyết Toán 6/7/8/9 Kết nối tri thức công khai trên `vietjack.com`.
- Truy cập trực tiếp 55 URL bài học; tất cả nhận HTTP 200 ở lần lấy dữ liệu ban đầu. `sources.json` ghi URL yêu cầu/thực tế, tiêu đề trang, ngày truy cập và SHA-256 HTML của từng nguồn.
- Không dùng nguồn yêu cầu đăng nhập hoặc vượt chặn truy cập. Các tệp đính kèm chương trình Toán trên hai website trường học trả 403 nên không được tính là tài liệu đã đọc/nguồn xác nhận nội dung.
- Không lưu bài viết HTML đầy đủ hoặc ảnh sách vào bộ học liệu. Loại nội dung quảng cáo, điều hướng, lời mời mua khóa học. Công thức có thể nằm trong ảnh nên không coi thao tác bỏ thẻ HTML là một bản chuyển đổi toán học chính xác.
- Dùng các sự kiện/định nghĩa/công thức toán học để biên soạn bản tóm tắt mới. Ví dụ không sao chép đề bài trên nguồn. Kiểm tra lại điều kiện, đơn vị và số liệu; không kế thừa máy móc lỗi trình bày từ trang web.
- Trạng thái HTTP và hash chỉ là bằng chứng đã lấy trang, không chứng minh trang luôn đúng hoặc là bằng chứng giáo viên đã thẩm định.

Các nguồn giữ quyền đối với bài viết, hình ảnh và cách trình bày gốc của họ. Bộ này không tuyên bố cấp phép lại toàn bộ nội dung nguồn.

## Dữ liệu để dùng cho RAG

- `manifest.json`: 88 bài, vị trí file, metadata, nguồn và SHA-256 nội dung Markdown.
- `sources.json`: nhật ký 55 nguồn web đã truy cập.
- `graph-proposal.json`: 88 nút và 151 cạnh `PREREQUISITE_OF` **đề xuất bằng biên tập**, không phải đồ thị đã được nguồn công bố hoặc LLM trích xuất tự động. Cạnh hướng từ kiến thức nền đến kiến thức cần nền đó.
- Frontmatter mỗi bài dùng một đối tượng JSON nằm giữa hai dòng `---`; đây cũng là cú pháp YAML hợp lệ. Có thể đọc trực tiếp bằng thư viện chuẩn Python mà không thêm thư viện YAML.

**Đã nhập và dựng chỉ mục offline ngày 09/11/2026.** Lệnh `import_geometry_corpus` đọc các bài trong manifest, kiểm tra hash, metadata và chu kỳ trước khi nhập; không nhập README/INDEX như bài học. Adapter vẫn lấy học liệu đã xuất bản trong Django. Bộ nạp Markdown gốc trong repo ngoài không bị sửa.

Kết quả: 88 bài mới và 151 quan hệ; cộng 6 bài mẫu và 3 quan hệ cũ là **94 bài, 154 quan hệ**. Neo4j và Chroma đã được kiểm chứng khớp Django. Xem [hướng dẫn chạy offline](OFFLINE_BUILD.md) và [kết quả kiểm thử](../docs/testing/KIEM_THU_CORPUS_OFFLINE.md).

`formula_latex`, `document_type`, mã kiến thức và tiên quyết đã tách riêng để bộ nạp không phải suy đoán từ tiêu đề. Nhiều chủ đề không thuộc ba hình tương tác hiện có; không gán tùy tiện mọi bài thành tam giác hoặc hình cầu chỉ để khớp giao diện.

Các bài nhập dùng nhóm `general` (Kiến thức hình học). Metadata và các phần nội dung bổ sung được giữ trong `Material.corpus_metadata`, chỉ đọc qua API. Xuất bản để thử RAG không đồng nghĩa đã được giáo viên thẩm định: `review_status=cho-giao-vien-duyet` vẫn có trong Django, Neo4j, Chroma và hiển thị ở trang đọc bài.

## Kiểm tra bộ học liệu

Từ thư mục backend:

```bash
python3 scripts/validate_geometry_corpus.py
```

Lệnh kiểm tra số file, frontmatter, hash, nguồn, liên kết nội bộ, quan hệ tiên quyết không chu kỳ và các ví dụ tính toán có dữ kiện kiểm tra. Không gọi AI, Neo4j hoặc Chroma.

Kiểm tra lại khả năng truy cập nguồn khi cần:

```bash
python3 scripts/check_geometry_sources.py --report /tmp/mindgeo-source-check.json
```

Đây là thao tác đọc các URL nguồn, không chạy lại biên soạn nội dung, không ghi đè Markdown hoặc dùng API key.

## Giáo viên cần đối chiếu

Rà lại quy ước hình thang/hình thang cân, các chiều đảo, phạm vi định lý theo bộ sách được trường chọn, đơn vị và cách dùng kí hiệu. Liên kết tiên quyết là lộ trình sư phạm đề xuất, không phải điều kiện duy nhất để chứng minh. Điều chỉnh metadata và cập nhật hash manifest sau khi chỉnh sửa; giữ lại nguồn và lịch sử biên tập. Các bài toán mới sinh từ corpus vẫn cần kiểm định toán học riêng.

## Kết quả kiểm tra ngày 09/11/2026

- 88/88 file có metadata, đủ các phần nội dung và nguồn đối chiếu.
- 55/55 nguồn ban đầu trả HTTP 200; đã ghi hash HTML và ngày truy cập. Hai nguồn được chạy lại bằng script kiểm tra nguồn cũng trả HTTP 200.
- 151 cạnh tiên quyết tham chiếu tới các mã có thật, không trùng và không tạo chu kỳ; liên kết Markdown giữa các bài hợp lệ.
- 88/88 công thức render được bằng KaTeX hiện có của frontend.
- 33 phép tính đối chiếu ví dụ đạt kiểm tra số học.

Các kiểm tra này chưa thay thế việc giáo viên rà toàn bộ phát biểu, phạm vi chương trình, ví dụ và lộ trình tiên quyết. Không có model hoặc cơ sở dữ liệu bên ngoài được gọi trong bước kiểm tra corpus.

## Đồ thị LLM bổ sung

Đã hoàn tất trích xuất 88 bài thành 450 thực thể và 526 quan hệ có bằng chứng (25 quan hệ bị loại). Các node này mang nhãn MindGeoEntity và tách khỏi 94 node bài học/154 cạnh tiên quyết. Đã kiểm chứng chạy lại 88 cache không gọi model. Chi tiết tại [OFFLINE_BUILD.md](OFFLINE_BUILD.md); các quan hệ LLM vẫn chờ giáo viên duyệt.

Bổ sung 09/11/2026: đã bỏ cạnh dữ liệu mẫu sides lớp 9 → pythagoras lớp 8 vì đi ngược lớp. Giữ nguyên 151 cạnh của corpus; tổng hiện tại 154 cạnh tiên quyết.
