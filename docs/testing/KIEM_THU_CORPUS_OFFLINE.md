# Kiểm thử nhập corpus và dựng đồ thị — 09/11/2026

## Mục tiêu và môi trường

Kiểm tra dữ liệu Markdown được nhập đúng, không ghi đè nội dung giáo viên, không sinh cạnh vòng lặp; sau đó kiểm tra Neo4j/Chroma thật và luồng đọc bài/quiz trên giao diện.

Python 3.14.4; Django/DRF + FastAPI; Chroma 1.5.9, Neo4j Python driver 6.4.1; PyTorch 2.15.0+cpu; Sentence Transformers 6.2.0; BGE-M3. Truy xuất hợp nhất dùng module RRF của repo nguồn. Các phiên bản ghi từ môi trường đã chạy, không phải số liệu hiệu năng.

## Kế hoạch và kịch bản

| Mã | Thao tác | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|
| COR-01 | Kiểm tra corpus, hash, nguồn, liên kết và cạnh | 88 bài, 151 cạnh hợp lệ, không chu kỳ | Đạt; thêm 33 kiểm tra số học đạt |
| COR-02 | Nhập `--publish --dry-run` vào DB kiểm thử | Không lưu bài hoặc cạnh nào | Đạt |
| COR-03 | Nhập corpus hai lần, sửa ghi chú giữa hai lần | Chỉ 88 bài mới; giữ 6 bài mẫu, không ghi đè ghi chú | Đạt; tổng 94 bài, 155 cạnh |
| COR-04 | Cho mã nguồn trùng một bài riêng | Báo lỗi, hoàn tác toàn bộ lượt nhập | Đạt |
| COR-05 | Tạo cạnh cũ ngược chiều cạnh đề xuất | Phát hiện chu kỳ, không xuất bản bản nháp | Đạt |
| COR-06 | Gửi metadata giả qua API tạo học liệu | Cho phép `general`, không cho ghi metadata nguồn | Đạt |
| COR-07 | Nạp tài nguyên khi bật RAG rồi đổi sang tắt | Báo chưa bật, không tái sử dụng cache để vượt cấu hình | Đạt |
| IDX-01 | Đồng bộ BGE-M3/Chroma/Neo4j thật | ID và tập cạnh khớp Django | Đạt: 94 nút, 155 cạnh, 94 vector 1024 chiều |
| IDX-02 | Đồng bộ lại với model trong cache, bật offline | Không tính lại embedding không đổi; tiến trình kết thúc thành công | Đạt: 0 mới, 94 tái sử dụng; exit 0 |
| IDX-03 | Truy xuất bài mỗi lớp 6–9 | Có nội dung, đủ tiên quyết trực tiếp, mã hợp lệ và nguồn | Đạt 4/4 bài |
| WEB-01 | Mở bài Pythagore nhập từ Markdown | Hiện phát biểu, công thức, ví dụ đúng và dấu chờ duyệt | Đạt |
| WEB-02 | Làm quiz fixture thuộc nhóm `general` | Hiển thị tên nhóm đúng, chấm 1/1, lưu kết quả, không lỗi JS | Đạt |
| WEB-03 | Mở bản đồ với toàn bộ corpus | Hiển thị 94 nút | Đạt |
| WEB-04 | Mở bài trên viewport 390×844 | Không tràn ngang; danh sách cuộn riêng, bài đọc không bị đẩy xuống hàng nghìn px | Đạt |
| REG-01 | Chạy kiểm thử tài khoản, phân quyền, học liệu, quiz và quota cũ | Không hồi quy | Đạt |

## Lệnh và bằng chứng

```bash
python3 scripts/validate_geometry_corpus.py
RAG_ENABLED=false .venv/bin/python manage.py test learning --verbosity 1
.venv/bin/python manage.py sync_geometry_index --verify
.venv/bin/python scripts/verify_stack.py --corpus
```

- Backend: **39/39** test đạt, gồm 6 test mới cho importer/metadata và cấu hình cache; dùng database kiểm thử, tắt RAG trong môi trường test để không nạp kết nối thật.
- Frontend: **16/16** unit test đạt; `npm run build` đạt.
- Trình duyệt: **7/7** kịch bản đạt; `verify_stack.py --corpus` dùng SQLite và tài khoản QA tạm, dọn tiến trình sau khi xong. Không chỉnh quota/tài khoản thật. RAG được tắt có chủ đích trong bộ trình duyệt để kiểm tra lỗi thiếu cấu hình; quiz mới là fixture được gắn `qa-fixture`, không giả lập thành kết quả Gemini.
- Chỉ mục thật: `data/index-build-report.json`, `data/index-verify-offline.log`. Các bài kiểm chứng: `g6-trung-diem` (3 tiên quyết/7 context), `g7-tam-giac-can` (13/8), `g8-pythagore` (11/8), `g9-tiep-tuyen` (20/8).
- Ảnh giao diện mobile: frontend `.qa/corpus-mobile.png`.
- SQLite được sao lưu trước migration/nhập trong `data/backups/`.

Lần chạy đầu đã ghi đủ chỉ mục nhưng tiến trình chưa thoát do luồng chuyển safetensors tự động của Transformers. Đã tắt chuyển đổi từ xa trong adapter và đóng client sau lệnh CLI. Lần kiểm chứng cuối bằng cache hoàn tất với exit 0.

## Giới hạn

Chưa kiểm thử trả lời Qwen local, sinh bài/quiz Gemini thật, Tavily hay báo cáo agent trong đợt này; không gọi API trả phí. Kiểm thử truy xuất thật gọi adapter, còn kiểm thử trình duyệt dùng RAG tắt và quiz fixture; không diễn giải thành bằng chứng một lượt truy xuất thật qua UI. Chưa đo tải/độ trễ hoặc chất lượng truy xuất trên bộ benchmark. Kiểm tra cấu trúc, số học và chạy được không thay thế giáo viên thẩm định toàn bộ 88 bài cùng 151 cạnh đề xuất.
