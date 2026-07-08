---
name: doc-summarizer-web
description: "Use when you need to build a web app that lets a user choose an AI provider/model, upload a document, and get a structured summary from the uploaded file."
---

# Skill: Web tóm tắt tài liệu

## Mục đích

Skill này hướng dẫn tạo một ứng dụng web cho phép người dùng:

- Chọn provider AI như OpenAI, Claude, Gemini hoặc custom/openai-compatible.
- Chọn model từ danh sách có sẵn theo provider.
- Tải danh sách model live từ provider khi người dùng nhập API key.
- Nhập model custom khi model mong muốn chưa có trong danh sách.
- Tải lên file tài liệu `.txt`, `.pdf`, `.docx` bằng bấm chọn hoặc kéo thả.
- Nhận kết quả tóm tắt trực tiếp trên giao diện web.

## Ràng buộc bắt buộc

- Luôn phản hồi bằng tiếng Việt có dấu.
- Mỗi khi thực hiện thay đổi code, phải cập nhật file `know-how.md`.
- Mỗi lần code phải đọc lại skill này và file `know-how.md` trước khi bắt đầu.
- Viết code tối thiểu; ưu tiên thư viện có sẵn.

## Kiến trúc xử lý tóm tắt

Luồng xử lý chính trong `utils/ai_client.py`:

### Bước 1: Xác định context khả dụng

```python
def _max_input_chars(provider: str, model: str) -> int:
    context = MODEL_CONTEXT_WINDOWS[provider].get(model, 131072)
    available_tokens = context - max_output_tokens - prompt_overhead
    return available_tokens * 4  # 1 token ≈ 4 ký tự
```

### Bước 2: Quyết định chiến lược

```
Nếu toàn bộ văn bản ≤ 80% context window
  → 1 API call duy nhất (direct summary prompt)
  → Không chunk, không chia phần

Nếu văn bản > 80% context window
  → Chia theo cấu trúc (Chương/Phần/Hồi/...) hoặc theo độ dài
  → Gửi tất cả chunk song song (asyncio.gather, tối đa 2 luồng)
  → Tổng hợp các chunk summary → bản cuối
```

### Bước 3: Xử lý lỗi API

```python
async def _call_with_retry(...):
    for attempt in range(5):
        try:
            return await _generate_summary(...)
        except AIClientError as exc:
            if not is_rate_limit_error(exc) or attempt == 4:
                raise
            delay = parse_retry_after(exc) or base_delay * 2^attempt
            await asyncio.sleep(delay)
```

- Tự động parse `"retry in Xs"` từ error message của Gemini
- Exponential backoff: 2s → 4s → 8s → 16s → 32s
- Keywords phát hiện rate limit: quota, rate limit, high demand, retry, resource exhausted, 429, 503

### Bước 4: Export .md (client-side)

File `.md` được tạo hoàn toàn ở frontend (JavaScript), không gọi backend:

```javascript
const md = [
  `# Tóm tắt tài liệu: ${filename}`,
  `- **Số ký tự:** ${chars}`,
  `- **Ngày tạo:** ${timestamp}`,
  "---",
  output.textContent,  // summary đã hiển thị
].join("\n");
```

## Cấu trúc project

```
├── app.py                  # FastAPI server, 3 endpoints: GET /, POST /summarize, POST /models
├── start.bat               # Double-click để chạy
├── requirements.txt
├── utils/
│   ├── ai_client.py        # AI calls, context-aware chunking, retry, model listing
│   └── extract.py          # Trích xuất text từ .txt/.pdf/.docx
├── templates/
│   └── index.html
├── static/
│   ├── app.js              # Frontend logic, client-side .md export
│   └── styles.css
└── know-how.md
```

## API endpoints

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/` | GET | Giao diện web |
| `/models` | POST | Lấy danh sách model (default hoặc live từ provider) |
| `/summarize` | POST | Nhận file + cấu hình, trả JSON `{filename, characters, summary}` |

## Provider & Context

| Provider | Context window | Max input chars (available) |
|----------|---------------|----------------------------|
| OpenAI (gpt-4.1, gpt-4.1-mini) | 1.048.576 tokens | ~4.1M ký tự |
| OpenAI (gpt-5.x) | 131.072 tokens | ~485K ký tự |
| Claude (sonnet, haiku, opus) | 200.000 tokens | ~761K ký tự |
| Gemini (2.5, 3.5) | 1.048.576 tokens | ~4.1M ký tự |
| Custom | 131.072 tokens (mặc định) | ~485K ký tự |

## Quy tắc code

- Trước khi bắt đầu, đọc lại skill này và `know-how.md`.
- Nếu đã có thư viện hỗ trợ xử lý PDF, DOCX, upload hoặc gọi AI, ưu tiên dùng thư viện đó.
- Khi hoàn thành, cập nhật `know-how.md`.
