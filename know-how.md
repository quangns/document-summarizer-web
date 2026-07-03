# Know-how

## 2026-07-02

- Dựng app web tóm tắt tài liệu bằng FastAPI để giữ cấu trúc gọn và dễ chạy.
- Giao diện dùng HTML/CSS/JavaScript thuần, gọi `POST /summarize` bằng `FormData`.
- Backend nhận `provider`, `model`, `api_key`, `base_url` và `file`.
- Tách trích xuất file vào `utils/extract.py`; hỗ trợ `.txt`, `.pdf`, `.docx`.
- Dùng thư viện có sẵn cho định dạng tài liệu: `pypdf` cho PDF và `python-docx` cho DOCX.
- Tách gọi AI vào `utils/ai_client.py`; hỗ trợ OpenAI, Claude, Gemini và custom OpenAI-compatible.
- API key có thể nhập từ UI hoặc lấy từ biến môi trường: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `CUSTOM_AI_API_KEY`.
- Giới hạn file upload 15 MB và giới hạn văn bản gửi sang AI ở 60.000 ký tự để tránh request quá lớn.
- Đã kiểm tra `python -m compileall app.py utils`, import app, trang chủ HTTP 200 và endpoint upload bằng `TestClient` với hàm AI giả.
- Cập nhật UI chọn model thành dropdown theo provider, có tùy chọn `Custom...` và nút `Tải model` để gọi live danh sách model qua `/models`.
- Endpoint `/models` trả danh sách mặc định khi chưa có API key; nếu có key thì gọi OpenAI-compatible `/models`, Anthropic `/v1/models`, hoặc Gemini `v1beta/models`.
- Provider OpenAI dùng Responses API `/v1/responses` để phù hợp hơn với các model mới; custom/openai-compatible vẫn dùng `/chat/completions`.
- Vùng upload đã có drag-and-drop thật sự bằng cách bắt `dragenter/dragover/drop`, gán file dropped vào `input[type=file]`, và thêm trạng thái highlight `is-dragover`.
- Pipeline tóm tắt không còn chỉ dựa vào một prompt ngắn. Với tài liệu ngắn thì dùng prompt có khung cố định; với tài liệu dài thì chia đoạn, tóm tắt từng đoạn, rồi hợp nhất thành bản cuối để giữ đủ ý hơn.
- Khung tóm tắt hiện ưu tiên các mục: tổng quan, ý chính trọng tâm, ý theo từng phần, số liệu/tên riêng/mốc thời gian, và kết luận hoặc việc cần làm tiếp.
- Bổ sung chia tài liệu theo cấu trúc trước khi chia theo độ dài: ưu tiên đọc các dòng giống mục lục ở phần đầu, nhận diện tiêu đề như `Chương`, `Phần`, `Thiên`, `Hồi`, `Mục`, `Chapter`, `Part`, `Section`, rồi dùng các tiêu đề đó để cắt thân tài liệu.
- Nếu không tìm được mục lục hợp lệ, hệ thống fallback sang nhận diện heading trực tiếp trong nội dung; chỉ khi vẫn không đủ cấu trúc mới chia theo cụm độ dài.
- Prompt tóm tắt từng đoạn và prompt tổng hợp cuối đều đã nhận thêm tên phần để bản tóm tắt bám đúng cấu trúc tài liệu hơn.
- Khu vực kết quả hiện có thêm `Sao chép` vào clipboard và `Xuất file` `.txt`; cả hai nút chỉ bật khi đã có bản tóm tắt thật sự.

## 2026-07-03

- Thay `CHUNK_TARGET_CHARS` cố định (10K) bằng `_max_input_chars()` động dựa trên context window của model.
- Thêm `MODEL_CONTEXT_WINDOWS` map: gpt-4.1/gpt-4.1-mini 1M, claude 200K, gemini 1M, openai/default 128K.
- Công thức: `available_chars = (context_window - max_output_tokens - 1500) * 4`.
- Chuyển pipeline từ 2 tầng lên 3 tầng: sub-chunk summary → section synthesis → final synthesis.
- Khi section > context window, được chia thành sub-chunk vừa khít, tóm tắt từng cái, rồi tổng hợp lại bằng `_build_sub_section_synthesis_prompt()` trước khi đưa vào tổng hợp cuối.
- Thêm `export_to_md()` xuất kết quả ra markdown với header (tên file, số ký tự, ngày tạo), phần tổng hợp và tóm tắt chi tiết từng phần.
- Cập nhật SKILL.md sections 8, 9, 10 tương ứng.
