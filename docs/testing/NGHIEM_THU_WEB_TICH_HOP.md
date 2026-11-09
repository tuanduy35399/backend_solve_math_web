# Nghiệm thu web tích hợp — 09/11/2026

## Phạm vi và cách kiểm tra

Rà soát độc lập phần Django/DRF, FastAPI và React/Vite sau bổ sung corpus, duyệt nội dung, đồ thị thực thể và kiểm tra dịch vụ. Ưu tiên phân quyền, nguồn bằng chứng, trạng thái dịch vụ trung thực và tránh hồi quy. Chỉ ghi kết quả đã quan sát; không coi build thành công là bằng chứng toàn bộ luồng trình duyệt hoạt động.

Lượt QA này dùng database kiểm thử tạm do Django tạo và hủy, `RAG_ENABLED=false`, mock cho nhà cung cấp và Neo4j trong các test liên quan. Không tải checkpoint Qwen, không gọi sinh nội dung/tìm nguồn trả phí, không sửa SQLite/Neo4j/Chroma thật. Không chạy Playwright đồng thời với tác vụ tích hợp của người triển khai.

## Kịch bản và kết quả độc lập

| Mã | Kịch bản / kết quả mong đợi | Bằng chứng và kết quả |
|---|---|---|
| REG-01 | Hồi quy tài khoản, vai trò, học liệu, hội thoại, quiz, hạn mức | **Đạt:** lượt cuối `manage.py test learning --noinput`, **50/50** test trong 24,254 giây; DB tạm đã hủy. Các lượt trước 47/47 cũng đạt |
| REV-01 | Học sinh không được duyệt bài; giáo viên không sửa bài riêng của người khác | **Đạt:** test API trả 403 |
| REV-02 | Duyệt bài lưu người/thời điểm; sửa nội dung hủy trạng thái duyệt cũ | **Đạt:** duyệt rồi PATCH nội dung trả `cho-giao-vien-duyet` |
| EXT-01 | Loại quan hệ thiếu trích dẫn nguyên văn; giữ ID thực thể ổn định | **Đạt với đầu ra model mock:** câu bằng chứng ngoài bài bị loại; khác hoa/thường và khoảng trắng cho cùng ID |
| EXT-02 | Chạy lại lệnh trích xuất dùng cache, không gọi model lần nữa | **Đạt với model/Neo4j mock:** hai lượt chỉ gọi extractor một lần |
| EXT-03 | Sửa escape LaTeX sai cú pháp nhưng vẫn kiểm bằng chứng, từ chối JSON rỗng, ẩn graph khác hash nguồn | **Đạt:** 3 regression test mới được QA đọc và chạy lại trong bộ 50 test; dùng schema thật với model/Neo4j mock |
| ACL-01 | Học sinh không được dò cấu hình máy chủ | **Đạt:** POST `/api/v1/system/check` trả 403 và không chạy probe |
| ACL-02 | Bài chưa xuất bản không được đọc đồ thị | **Đạt:** GET `/api/v1/rag/graph` trả 404 trước khi gọi graph adapter |
| COR-01 | Nhập lặp không ghi đè bài giáo viên; dry-run không lưu; chặn trùng ID và chu kỳ | **Đạt:** các test corpus nằm trong 50 test backend |
| COR-02 | Kiểm tra Markdown, hash, liên kết, nguồn, đồ thị và ví dụ số học | **Đạt:** 88 bài, 55 bản ghi nguồn, 151 cạnh không chu kỳ, 33 kiểm tra số học; không kết nối DB hoặc nhà cung cấp |
| SYS-01 | Phân biệt thiếu cấu hình, đúng model, sai model, `/models` không hỗ trợ, HTTP401 và lỗi kết nối | **Đạt với HTTP mock:** 6/6 nhánh; không POST sinh nội dung, không phản chiếu khóa giả vào thông báo |
| STALE-01 | Graph hash cũ/legacy không trả bằng chứng; hash đúng trả graph; RAG từ chối index cũ và lấy metadata hiện tại | **Đạt với adapter/ORM mock:** 6/6 nhánh độc lập sau bản sửa, gồm tiên quyết nằm ngoài top context hợp nhất; không kết nối DB/index/model thật |
| REV-03 | Sửa ghi chú giữ nguồn bài corpus; bài mới có nguồn mặc định; cho lưu bài không có công thức | **Đạt với hàm lưu và API mock:** 2/2 kịch bản, nguồn có sẵn không bị ghi đè và công thức rỗng không chặn lưu; chưa thay thế kiểm tra form trên trình duyệt |
| FE-01 | Logic frontend hiện có không hồi quy | **Đạt:** `npm test`, 16/16 test trong 3 tệp |
| FE-02 | Frontend đóng gói production | **Đạt:** `npm run build`, Vite hoàn tất |
| SRC-01 | Khoảng trắng và patch backend hợp lệ | **Đạt:** `git diff --check` không có lỗi |

Các test trích xuất không chứng minh model luôn gán đúng ý nghĩa quan hệ. Có đoạn trích nguyên văn là điều kiện kiểm chứng nguồn, chưa thay thế giáo viên xác nhận tính đúng toán học.

## Bằng chứng tích hợp của người triển khai

Phần này tách khỏi số kiểm tra độc lập trên. Người triển khai đã chạy `scripts/verify_live_ai.py --generate --research` bằng SQLite/tài khoản tạm và truy vấn Neo4j/Chroma thật. QA đọc mã script, artifact `data/live-ai-verification.json` và kiểm tra độ dài tệp báo cáo tương ứng, không chạy lại model hoặc tìm kiếm.

| Luồng | Kết quả ghi trong artifact |
|---|---|
| API RAG thật qua FastAPI | 4 bài lớp 6–9; số context lần lượt 7, 8, 8, 8 |
| API đồ thị trích xuất thật | 6 thực thể, 5 quan hệ, `origin=llm_extraction` |
| Sinh học liệu thật qua provider `openai` | 4 câu quiz, 2 bài tự luận; lưu thành công; API chấm phía máy chủ trả 200 |
| Agent nghiên cứu thật | 20 nguồn, báo cáo 6.391 ký tự; lưu thành công; độ dài tệp khớp artifact |
| Trình duyệt | Người triển khai báo 7 kịch bản live và 21 demo đạt; test live đã có sửa nguồn/duyệt rồi tải lại và xem graph bằng fixture mock |

Các thời gian trong artifact chỉ là quan sát của vài lượt API, có cả khởi động tài nguyên; không dùng để kết luận đạt NFR độ trễ. HTTP 200 khi chấm không chứng minh đáp án AI đúng. Số nguồn và độ dài báo cáo không thay thế kiểm định nguồn/toán học. Đồ thị trên trình duyệt dùng fixture mock; bằng chứng graph thật ở đây là lượt API riêng. Chưa chốt số bài của pipeline trích xuất toàn corpus đang chạy.

## Phát hiện khi rà soát

1. **Chỉ mục/đồ thị có thể cũ sau sửa bài — đã sửa:** đã bổ sung fingerprint nguồn. QA độc lập xác nhận graph hash cũ/legacy trả rỗng và thông báo trích xuất lại, RAG hash cũ bị từ chối, context và các hàng tiên quyết dùng nội dung/nguồn/trạng thái duyệt hiện tại từ Django. Đạt 6/6 nhánh mock. Còn cần xác nhận luồng đồng bộ/trích xuất lại với dịch vụ thật.
2. **Mất nguồn khi sửa bài corpus — đã sửa:** `frontend/src/pages/Educator.jsx`, hàm `save`, giữ nguồn của bài đang sửa và chỉ dùng nguồn mặc định khi chưa có nguồn; form có trường “Nguồn đối chiếu”. Hai kịch bản hàm lưu với API mock đạt, frontend 16/16 unit test và build chạy lại đều đạt.
3. **Giới hạn biên tập:** ví dụ mở rộng nằm trong `corpus_metadata.sections` chỉ đọc qua API; trình soạn thảo web hiện sửa tiêu đề, nội dung chính, công thức và ghi chú. Muốn sửa ví dụ mở rộng cần quy trình cập nhật corpus riêng. Không coi thao tác duyệt trên web là đã chỉnh sửa hoặc nghiệm thu mọi phần của 88 bài.

## Phần chưa nghiệm thu trong lượt QA độc lập

- Agent QA chưa tự chạy trình duyệt. Bản cập nhật test của người triển khai đã bao phủ giữ nguồn/duyệt rồi tải lại và graph fixture; chưa có căn cứ từ lượt QA này cho admin bấm kiểm tra dịch vụ, chuyển giữa hai graph, graph rỗng/lỗi và toàn bộ các trạng thái mobile của graph mới.
- Neo4j/Chroma/BGE-M3 thật, trích xuất model thật, RRF, sinh quiz và agent: có bằng chứng tích hợp của người triển khai ở mục trên, agent QA không gọi lại để tránh xung đột hoặc lặp chi phí. Bằng chứng corpus trước nằm trong `KIEM_THU_CORPUS_OFFLINE.md`; không cộng thành số test độc lập của đợt này.
- Qwen checkpoint `duydotpy/qwen3_5_4B_VLM_finetune_solve_geomath_16bit`: chưa chạy vì máy không có GPU phù hợp và người dùng chọn chỉ hoàn thiện web cùng hướng dẫn triển khai. `/models` đạt chỉ xác nhận endpoint/model được liệt kê; cần thử văn bản, ảnh, JSON contract và hội thoại nhiều lượt trên máy GPU riêng theo `docs/QWEN_DEPLOYMENT.md`.
- Chưa đánh giá độ đúng Socratic/toán học, chất lượng nhận ảnh, chống ảo giác, chất lượng truy xuất theo benchmark, độ trễ, tải hoặc toàn bộ tiêu chí SRS. Chưa có căn cứ tuyên bố các mục này đạt.

## Lệnh tái kiểm tra

Backend:

```bash
cd /home/duypy/Documents/MySource/backend_solve_math_web
RAG_ENABLED=false .venv/bin/python manage.py test learning --noinput
.venv/bin/python scripts/validate_geometry_corpus.py
git diff --check
```

Frontend:

```bash
cd /home/duypy/Documents/MySource/solve_math_vlm/frontend
npm test
npm run build
```

Kết luận tại thời điểm ghi: 50 test backend, 16 test frontend, build và các kiểm tra độc lập bổ sung đều đạt; hai lỗi đã sửa đã được tái kiểm tra. Artifact của người triển khai cung cấp thêm bằng chứng RAG, graph, sinh học liệu và agent thật cùng các luồng trình duyệt đã nêu. Chưa chốt pipeline trích xuất toàn corpus; các tiêu chí GPU, chất lượng mô hình, hiệu năng và các trạng thái trình duyệt chưa được bao phủ vẫn để mở.


## Bổ sung bằng chứng pipeline và dịch vụ thật từ primary

Đây là bằng chứng primary chạy sau phần rà độc lập; QA đã đối chiếu artifact API trước khi tổng kết, không tự gọi model lại.

- `data/live-ai-verification.json`: 4 request API RAG thật; đồ thị API thật; sinh 4 câu quiz/2 bài tập, lưu và chấm HTTP200 trong DB/tài khoản tạm; agent nghiên cứu lưu báo cáo 6391 ký tự cùng 20 mục kết quả nguồn tìm kiếm. Số nguồn không đồng nghĩa mọi URL được trích dẫn trong báo cáo hoặc là 20 nguồn duy nhất.
- `data/extraction-verification.json`: đủ 88 bài trích xuất, 450 thực thể, 526 quan hệ. 0 bằng chứng nguồn không khớp trong quan hệ được lưu; 25 quan hệ đã loại. Trạng thái mọi quan hệ tự động vẫn là chờ duyệt.
- Lượt phát lại 88 cache dùng 0 lần gọi model, chỉ MERGE dữ liệu đã trích xuất để xác nhận tiếp tục/idempotency.
- Primary browser live 7/7 và demo21/21 đạt. Đồ thị trên browser live là fixture mô phỏng; endpoint Neo thật được kiểm chứng riêng. Kịch bản live còn kiểm tra sửa bài không làm mất nguồn, duyệt nội dung và reload.
- Sample RAG API đầu tiên (cold) 9447 ms; ba request sau 555/365/268 ms. Chỉ là mẫu nhỏ trên máy hiện tại; không xem như đạt SLO 800 ms hay kiểm thử tải.
- Giữ 100 lượt/ngày cho sinh học liệu toàn hệ thống. Index offline dùng giới hạn riêng theo lần chạy và không trừ quota này.

Chưa nghiệm thu Qwen thật, GPU, chất lượng toán học/sư phạm hay 60 FPS theo SRS. Tác giả chọn hoàn thiện web + hướng dẫn triển khai trước khi có máy GPU.
