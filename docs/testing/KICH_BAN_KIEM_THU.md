# Kịch bản kiểm thử MindGeoTutorAI

Ngày: 09/11/2026. Các bước có tài khoản, dữ liệu hoặc ghi cơ sở dữ liệu phải thực hiện trên môi trường QA tạm do `scripts/verify_stack.py` tạo. Không dùng database làm việc hoặc khóa dịch vụ thật cho các ca tự động dưới đây. Kết quả thực thi được ghi riêng trong `KET_QUA_KIEM_THU.md`.

## Tài khoản và dữ liệu nghiệp vụ

| Mã | Tiền điều kiện và bước thực hiện | Kết quả mong đợi | Kiểm tra tự động |
|---|---|---|---|
| TC-01 | Chưa đăng nhập; đăng ký tên mới, mật khẩu hợp lệ, tên hiển thị và lớp | Tạo học sinh, đăng nhập được, không có quyền giáo viên/admin | `live.spec.js`: registration; `test_public_registration_cannot_escalate` |
| TC-02 | Gửi API đăng ký kèm `role=admin` | HTTP 400; không cấp quyền cao hơn | `test_public_registration_cannot_escalate` |
| TC-03 | Đăng nhập bằng tài khoản QA; đăng xuất; dùng lại token cũ gọi FastAPI | Đăng nhập đúng; logout thu hồi token; yêu cầu cũ nhận 401 | `test_authentication_and_logout_revocation`; E2E login/logout |
| TC-04 | Đổi tên/lớp tại Cài đặt; tải lại; thử PATCH vai trò qua API hồ sơ | Tên/lớp lưu máy chủ; đổi vai trò bị từ chối | `test_profile_cannot_escalate`; E2E profile persistence |
| TC-05 | Học sinh gọi API học liệu ghi, thống kê, user admin, đồng bộ RAG, agent báo cáo | Các API trả 403; việc ẩn nút không phải bằng chứng duy nhất | `test_student_denied_teacher_and_admin_operations` |
| TC-06 | Giáo viên tạo học liệu, chọn xuất bản, lưu, tải lại, xóa và xác nhận | Có bản ghi thật sau reload; xóa thành công trên server | E2E teacher CRUD |
| TC-07 | Giáo viên B mở/sửa/xóa học liệu đã xuất bản của giáo viên A | Đọc được bản xuất bản; sửa/xóa nhận 403; dữ liệu không đổi | `test_teacher_cannot_write_other_teacher_material` |
| TC-08 | Học sinh hoặc giáo viên khác mở học liệu nháp | Nhận 404, không lộ nội dung nháp | `test_drafts_hidden_and_material_ownership`; `test_draft_is_hidden_from_other_teacher` |
| TC-09 | POST học liệu hợp lệ nhưng mã `id` trùng mã hiện có | HTTP 400 thông báo trùng; không ghi đè và không lỗi 500 | `test_duplicate_material_id_is_validation_error` |
| TC-10 | Thêm quan hệ đã tồn tại; thêm cạnh ngược tạo chu kỳ; thêm/xóa một quan hệ hợp lệ | Chặn trùng và chu kỳ; lưu/xóa quan hệ hợp lệ | `test_prerequisite_cycle_and_duplicate_denied`; hồi quy demo graph |
| TC-11 | Mở/sửa/gửi tiếp phiên học thuộc tài khoản khác | HTTP 404; không trả ảnh hoặc hội thoại của người khác | `test_sessions_are_private`; `test_geometry_sync_ownership_and_locked_facts` |
| TC-12 | Xóa dữ liệu học tập của tài khoản A, trong khi B có phiên học | Dữ liệu A được dọn; phiên học B còn nguyên | `test_clear_learning_does_not_delete_other_users` |
| TC-13 | Admin đổi vai trò/khóa tài khoản khác; thử đổi chính tài khoản đang dùng | Thay đổi hợp lệ áp dụng; token cũ bị thu hồi; không tự làm mất quyền quản trị tại đây | `test_admin_changes_role_and_revokes_tokens`; E2E admin |
| TC-14 | Khóa tài khoản rồi dùng token FastAPI cũ | HTTP 401 trước khi gọi model | `test_disabled_user_cannot_use_fastapi_token` |
| TC-15 | Admin thay hạn mức sinh học liệu, reload; đặt hạn mức và gọi quá giới hạn trong test | Hạn mức lưu máy chủ; vượt hạn mức bị chặn trước provider | E2E admin quota; `test_daily_quota_is_enforced_before_provider` |

## Luồng chat Qwen và hình học

| Mã | Tiền điều kiện và bước thực hiện | Kết quả mong đợi | Kiểm tra tự động |
|---|---|---|---|
| TC-16 | Chưa cấu hình Qwen; nhập đề rồi gửi | Thông báo chưa cấu hình; giữ ô đề; không gọi cloud và không lưu chat giả | E2E missing Qwen; `test_missing_local_model_does_not_call_cloud_or_persist_fake_chat` |
| TC-17 | Gửi file văn bản gắn MIME PNG; gửi ảnh PNG đúng | Ảnh giả nhận 422; ảnh đúng được chuyển tới hàm provider nội bộ | `test_photo_validation_checks_bytes`; `test_valid_photo_goes_only_to_local_provider` (provider mock) |
| TC-18 | Trên trình duyệt chọn ảnh, xoay/cắt và xem trước | Ảnh hợp lệ có preview; kích thước đổi đúng; file không hỗ trợ có lỗi | Hồi quy demo image editor; chưa chứng minh nhận diện ảnh bằng Qwen |
| TC-19 | Qwen mock trả câu hỏi đầu; trả nhận xét sai cho lượt sau | Lưu hội thoại đúng thứ tự, không nhầm chủ tài khoản; ghi nhận lỗi khái niệm | `test_qwen_turn_persists_and_records_gap` (mock) |
| TC-20 | Provider mock trả lỗi hoặc JSON không hợp lệ chứa chuỗi nhạy cảm | HTTP 502 an toàn; không lưu phản hồi giả hoặc lộ chuỗi lỗi provider | `test_bad_model_response_does_not_save` |
| TC-21 | Gửi tiếp một phiên đã hoàn thành | HTTP 409; không gọi model | `test_closed_session_cannot_accept_more_turns` |
| TC-22 | Đồng bộ hình khi phiên đang làm; đồng bộ phiên khác chủ; gửi bán kính 0, âm hoặc quá giới hạn | Giữ dữ kiện đề, chặn sai chủ, chặn tham số không hợp lệ | `test_geometry_sync_ownership_and_locked_facts`; `test_invalid_geometry_parameters_rejected` |
| TC-23 | Đổi tham số, xoay/phóng, kéo đỉnh, xuất SVG trong workspace | Hình và đại lượng cập nhật; SVG tải được; không tràn màn hình | Hồi quy demo geometry; E2E mobile live |
| TC-24 | Khi có Qwen thật: gửi tập ảnh và yêu cầu “Giải giúp em bài này”, rồi trả lời sai một bước | Nhận diện ký hiệu đúng, hỏi gợi mở, nhận xét đúng về toán; không tiết lộ ngay đáp án cuối | BLOCKED trong đợt này; cần bộ đề/đáp án giáo viên duyệt và checkpoint thật |

## Quiz và model bên ngoài

| Mã | Tiền điều kiện và bước thực hiện | Kết quả mong đợi | Kiểm tra tự động |
|---|---|---|---|
| TC-25 | Tải quiz trước nộp; gửi đáp án với `score` tự khai khác kết quả thật | Không có trường đáp án/giải thích trước nộp; server tự tính điểm | `test_quiz_answers_are_hidden_then_scored_on_server` |
| TC-26 | Nộp thiếu đáp án, chuỗi thay số, bool hoặc chỉ số ngoài phạm vi | HTTP 400; không tạo lượt làm lỗi | `test_invalid_quiz_answers_rejected` |
| TC-27 | Làm quiz 3/4 đúng; tải lại kết quả; mở bản đồ; làm lại đúng hết | Lưu 3/4 trên server, ghi lỗi khái niệm; lượt đúng sau giải quyết gap tương ứng | E2E quiz/gaps; `test_quiz_answers_are_hidden_then_scored_on_server` |
| TC-28 | Tài khoản B mở/nộp quiz sinh riêng cho A | Nhận 404; không đọc/nộp quiz của người khác | `test_generated_quiz_is_private`; `test_private_quiz_not_submittable_by_another_student` |
| TC-29 | Chưa bật RAG; giáo viên bấm đồng bộ, học sinh phân tích khái niệm | Thông báo cấu hình thiếu rõ ràng; không gắn nhãn dữ liệu tĩnh là RAG thật | E2E teacher sync; `test_rag_unconfigured_is_explicit` |
| TC-30 | Dùng các node kiểm soát được cho hai kênh vector/graph rồi gọi HybridSearch gốc | Hợp nhất đúng node chung, tăng thứ hạng theo RRF; không sửa mã nguồn thuật toán | `test_upstream_rrf_combines_shared_nodes` dùng module thật, không truy vấn DB thật |
| TC-31 | Mock truy xuất và sinh nội dung, gửi kèm trường nhận diện/chat thừa trong request | Provider chỉ nhận gói ngữ cảnh học thuật; quiz/exercises lưu đúng người dùng | `test_recommendation_uses_academic_context_only` |
| TC-32 | Chọn lần lượt Gemini/OpenAI; chặn HTTP bằng mock, kiểm tra request body | Payload có học liệu nhưng không có sentinel tên học sinh, ảnh hoặc hội thoại | `test_external_generation_payload_excludes_student_fields_for_both_providers` |
| TC-33 | Khi có kho thật: câu sai về lượng giác, truy xuất Chroma/Neo4j sau đồng bộ | Chunk liên quan và tiên quyết đúng; khái niệm nháp không lọt vào kết quả | BLOCKED: chưa chạy BGE-M3/Chroma/Neo4j thật trong đợt QA |
| TC-34 | Khi có provider: sinh tóm tắt, bài tập và quiz từ kết quả TC-33 | JSON hợp lệ, nguồn truy xuất rõ; giáo viên đối chiếu đáp án và đơn vị | BLOCKED: không gọi provider có phí; mock không thay thế việc kiểm định toán học |
| TC-35 | Giáo viên yêu cầu nghiên cứu nguồn web/lập báo cáo; học sinh thử gọi API cùng chức năng | Chặn học sinh; khi cấu hình đủ, báo cáo có nguồn thật, lưu và tải Markdown được | Quyền API đã kiểm tra; pipeline Tavily/model/make_report thật BLOCKED |

## Nội dung bổ sung và giao diện

| Mã | Bước thực hiện | Kết quả mong đợi | Kiểm tra tự động |
|---|---|---|---|
| TC-36 | Soạn nháp/xem trước/xuất bản/gỡ/xóa câu chuyện; đổi tác giả và vai trò demo | Luồng cũ hoạt động, form kiểm tra nguồn/công thức, bảo vệ dữ liệu chưa lưu | Hồi quy demo stories và story-authoring |
| TC-37 | API giáo viên gửi bài xuất bản có `paragraphs=[1]`, title kiểu object, sources null | HTTP 400; không lưu record làm hỏng trình đọc | `test_malformed_published_story_is_rejected` |
| TC-38 | Mở trang live trên điện thoại; học sinh vào URL giáo viên/admin trực tiếp | Không tràn ngang; trang từ chối quyền phù hợp; không có bộ chọn tự nâng vai trò | E2E student screens/mobile |
| TC-39 | Chạy axe và kiểm tra responsive cho workspace, thư viện và biên tập demo | Không có vi phạm trong tập quy tắc axe được chạy; nội dung/nút nằm trong viewport | Hồi quy demo, không thay thế audit toàn diện WCAG |
| TC-40 | Admin đăng ký metadata checkpoint đã huấn luyện | Chỉ lưu phương pháp/đường dẫn/metrics; không giả tiến độ GPU hoặc xem đó là đã train | `test_training_metadata_is_admin_only_and_does_not_launch_training`; thực thi LoRA/KD/GRPO thật BLOCKED |
| TC-41 | Đo độ trễ Qwen, truy xuất Hybrid RAG và FPS trên phần cứng đích | Đạt ngưỡng SRS cùng số đo, cấu hình máy và bộ dữ liệu ghi nhận | NOT RUN; thời gian chạy unit/E2E không phải số đo NFR này |

## Đối chiếu SRS

| Yêu cầu | Kịch bản | Phạm vi xác nhận trong đợt này |
|---|---|---|
| FR-01, FR-02 | TC-16 đến TC-18 | Form, giữ nội dung khi lỗi, xử lý/cắt/xoay ảnh demo và kiểm tra bytes phía server; chưa nhận diện ảnh thật |
| FR-03 | TC-19, TC-20, TC-23 | Schema, lưu/hiển thị hội thoại và công thức với mock/demo |
| FR-04 | TC-17, TC-24 | Ranh giới gọi Qwen đã kiểm tra; chất lượng VLM thật còn chờ |
| FR-05, FR-06 | TC-19, TC-20, TC-24 | Lưu bước và gap với mock; chưa nghiệm thu suy luận toán của model thật |
| FR-07, FR-08, FR-09 | TC-22, TC-23 | UI tương tác và đồng bộ được kiểm tra ở phạm vi API/demo; FPS chưa đo |
| FR-10, FR-11 | TC-29, TC-33 | Thiếu cấu hình được báo rõ; chưa chạy hai DB/embedding thật |
| FR-12 | TC-30, TC-33 | Thuật toán RRF gốc đạt test kiểm soát; toàn pipeline còn chờ |
| FR-13 | TC-25 đến TC-28, TC-31, TC-32, TC-34 | Chấm/lưu quiz và ranh giới privacy đạt; sinh/đúng toán thật còn chờ |
| FR-14, FR-15, FR-16 | TC-40 | Không chạy train; metadata không được xem là bằng chứng LoRA/KD/GRPO |
| AC-01, AC-05 | TC-24 | BLOCKED cho model thật |
| AC-02 | TC-22, TC-23 | PARTIAL: thao tác/hình học demo/API; chưa đo hiệu năng máy đích |
| AC-03 | TC-30, TC-33 | PARTIAL: RRF thật; retrieval đầy đủ BLOCKED |
| AC-04 | TC-31, TC-32, TC-34 | PARTIAL: adapter/privacy mock; sinh học liệu thật BLOCKED |
| AC-06 | TC-16 | Kiểm tra trực tiếp không có Qwen và không fallback cloud |
| AC-07 | TC-31, TC-32, TC-33 | Payload đã kiểm tra bằng mock; retrieval thật còn chờ |
| AC-08 | TC-02 đến TC-15, TC-25 đến TC-28 | Kiểm tra quyền, dữ liệu theo tài khoản và chấm tại server |
| AC-09 | Tài liệu kết quả | Phân biệt test thật, mock, phần blocked và NFR chưa đo |
| AC-10 | TC-40 | Xác nhận giao diện không train giả; huấn luyện thật chưa chạy |
