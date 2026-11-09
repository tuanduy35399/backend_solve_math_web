# Chạy checkpoint Qwen của Team DuyPy

## Tình trạng hiện tại

Đã kiểm tra metadata repo công khai:
<https://huggingface.co/duydotpy/qwen3_5_4B_VLM_finetune_solve_geomath_16bit>.

- Kiến trúc `Qwen3_5ForConditionalGeneration`, model type `qwen3_5`.
- Repo có processor, tokenizer, chat template và hai shard safetensors; không chỉ có LoRA adapter.
- Tổng trọng số theo index: **9.319.737.856 byte** (~8,68 GiB). Đây là dung lượng trọng số, không phải tổng VRAM để chạy.
- Repo xuất phát từ `unsloth/Qwen3.5-4B`, text config ghi bfloat16 và Transformers 5.2.0.
- Laptop đang dùng chỉ phát hiện Intel Iris Xe; chưa thấy NVIDIA GPU. Theo lựa chọn của tác giả, chưa tải/chạy checkpoint 9 GB trên laptop. Web giữ thông báo Qwen chưa cấu hình, không chuyển chat sang Gemini.

Đưa checkpoint lên Hugging Face là lưu model; chưa tự tạo endpoint suy luận. Cần máy GPU tự vận hành và mạng kết nối tới backend. Cấu hình dưới đây là hướng dẫn chuẩn bị, **chưa được chạy nghiệm thu trên GPU**.

## 1. Chuẩn bị máy GPU riêng

Trên máy GPU Linux có CUDA/driver phù hợp, tạo môi trường Python riêng cho vLLM theo [hướng dẫn GPU của vLLM](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/). Không cài vLLM vào `.venv` CPU đang chạy BGE-M3 của web; vLLM có yêu cầu riêng với PyTorch/CUDA.

```bash
uv venv --python 3.12 .venv-qwen
uv pip install --python .venv-qwen/bin/python vllm
```

Chọn phiên bản vLLM hỗ trợ `Qwen3_5ForConditionalGeneration` trong [danh sách model hỗ trợ](https://docs.vllm.ai/en/latest/models/supported_models/). Bộ nhớ cần lớn hơn riêng trọng số: còn ảnh, activation, KV cache và tiến trình phục vụ. Kiểm tra log khởi động trên GPU thật; nếu thiếu bộ nhớ, giảm context/concurrency trước khi cân nhắc chuyển đổi model. Không tự đổi checkpoint niên luận thành model khác.

## 2. Phục vụ bằng giao thức tương thích OpenAI

Tạo một khóa riêng cho endpoint Qwen và lưu vào file môi trường chỉ trên máy GPU. Khóa này độc lập với khóa Gemini. Ví dụ biến `QWEN_SERVE_KEY` đã được thiết lập trên máy GPU:

```bash
.venv-qwen/bin/vllm serve duydotpy/qwen3_5_4B_VLM_finetune_solve_geomath_16bit \
  --served-model-name mindgeo-qwen \
  --host 127.0.0.1 \
  --port 8080 \
  --dtype auto \
  --max-model-len 16384 \
  --max-num-seqs 1 \
  --gpu-memory-utilization 0.9 \
  --limit-mm-per-prompt '{"image":1}' \
  --api-key "$QWEN_SERVE_KEY"
```

Đây là lệnh khởi đầu theo [vLLM serve](https://docs.vllm.ai/en/stable/cli/serve/), cần điều chỉnh context theo GPU thật. Không dùng `--language-model-only` vì luồng gia sư có ảnh. Không cần `--trust-remote-code` cho kiến trúc đã được hỗ trợ sẵn.

Nếu model không được nhận diện, đối chiếu phiên bản vLLM/Transformers và [tài liệu Qwen3.5](https://huggingface.co/docs/transformers/model_doc/qwen3_5), không sửa tên kiến trúc trong `config.json` để ép chạy.

## 3. Nối máy GPU với backend

Nếu chạy cùng máy: `QWEN_BASE_URL=http://127.0.0.1:8080/v1`.

Nếu máy GPU khác nhưng truy cập được qua SSH, giữ server bind loopback và mở tunnel từ laptop chạy backend:

```bash
ssh -N -L 8080:127.0.0.1:8080 TEN_DANG_NHAP@DIA_CHI_MAY_GPU
```

Điền trên laptop, trong `backend_solve_math_web/.env`:

```dotenv
QWEN_BASE_URL=http://127.0.0.1:8080/v1
QWEN_MODEL=mindgeo-qwen
QWEN_API_KEY=KHOA_RIENG_CUA_ENDPOINT_QWEN
AI_TIMEOUT_SECONDS=90
```

Hugging Face repo URL không phải `QWEN_BASE_URL`. Nếu dùng máy GPU có URL riêng, base URL phải là gốc API phục vụ `/chat/completions`, thường kết thúc `/v1`. Ảnh/chat chỉ đi tới endpoint Qwen này; sinh học liệu dùng `OPENAI_*` riêng.

## 4. Kiểm tra trước khi dùng giao diện

```bash
cd /home/duypy/Documents/MySource/backend_solve_math_web
.venv/bin/python scripts/check_qwen.py
.venv/bin/python scripts/check_qwen.py --infer
```

Để thử ảnh do bạn chọn, thêm `--infer --image /duong/dan/de-bai.png`. Script chỉ dùng `QWEN_*`, không gửi dữ liệu sang Gemini. Kiểm tra `/models` đạt không đủ chứng minh xử lý ảnh: cần chạy cả ảnh thật, JSON contract, nội dung toán và tương tác nhiều lượt.

Backend yêu cầu một JSON theo `TutorResponse` trong `ai_service/providers.py`: `text`, `math`, `highlight`, `geometry`, `correct`, `concept`, `done`. Hình chưa xác định phải là null; chỉ hỗ trợ tam giác vuông, lăng trụ đáy tam giác vuông và hình cầu. Tên hình/công thức không được suy ra bằng cách đổi sang model khác khi có lỗi.

Sau khi kiểm tra script, khởi động lại Django + FastAPI, đăng nhập web, gửi đề văn bản rồi gửi ảnh. Đối chiếu AC-01/03/05 trong SRS. Bản kiểm tra schema không nghiệm thu độ chính xác Socratic, chống ảo giác hoặc NFR độ trễ; các mục đó cần dữ liệu đánh giá và GPU thực.
