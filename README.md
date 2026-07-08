# AI Document Summarizer

Ứng dụng web tóm tắt tài liệu (.txt, .pdf, .docx) sử dụng AI, hỗ trợ nhiều provider.

## Tính năng

- Hỗ trợ OpenAI, Claude, Gemini, Custom (OpenAI-compatible)
- Tải danh sách model trực tiếp từ provider bằng API key
- Kéo thả hoặc chọn file .txt / .pdf / .docx
- **Single-call ưu tiên**: nếu tài liệu vừa context window → 1 API call duy nhất, không chunk
- **Context-aware chunking**: nếu tài liệu > 80% context, tự động chia nhỏ vừa khít
- **Xử lý song song**: các chunk được gọi AI đồng thời (tối đa 2 luồng)
- **Retry thông minh**: exponential backoff + parse "retry in Xs" từ Gemini
- Phát hiện cấu trúc tài liệu (Chương/Phần/Hồi/...) từ mục lục hoặc heading
- Luôn phản hồi tiếng Việt có dấu nếu văn bản nguồn là tiếng Việt
- Sao chép kết quả hoặc xuất file `.md` (client-side, không gọi lại API)

## Yêu cầu

- Python 3.10+

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Chạy

```bash
python app.py
```

Hoặc double-click `start.bat`. Mở **http://127.0.0.1:9000**

## Hướng dẫn sử dụng

1. Chọn **AI Provider** (OpenAI / Claude / Gemini / Custom)
2. (Tùy chọn) Bấm **Tải model** để lấy danh sách model live
3. Chọn **Model**, hoặc chọn `Custom...` để nhập tay
4. Nhập **API Key**
5. Với Custom provider, nhập thêm **Base URL**
6. Kéo thả hoặc chọn file
7. Bấm **Tóm tắt**
8. Dùng **Sao chép** hoặc **Xuất file** (`.md`)

## Luồng xử lý

```
Tài liệu vào → trích xuất text → kiểm tra độ dài so với context window
  │
  ├─ Nếu ≤ 80% context → 1 prompt duy nhất → tóm tắt đầy đủ
  │
  └─ Nếu > 80% context → chia chunk theo cấu trúc/độ dài
       → gửi song song (tối đa 2 luồng) → tổng hợp → kết quả
```

Khi API bận: tự động retry tới 5 lần (2s → 4s → 8s → 16s → 32s), parse retry time từ Gemini.

## Provider & Context

| Provider | Model mặc định | Context | Tài liệu tối đa (1 call) |
|----------|---------------|---------|------------------------|
| OpenAI | gpt-5.4-mini | 128K tokens | ~388K ký tự |
| Claude | claude-haiku-4-5 | 200K tokens | ~609K ký tự |
| Gemini | gemini-3.5-flash | 1M tokens | ~3.3M ký tự |
| Custom | gpt-5.4-mini | 128K tokens | ~388K ký tự |

## API endpoints

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/` | GET | Giao diện web |
| `/models` | POST | Lấy danh sách model |
| `/summarize` | POST | Gửi file + cấu hình, nhận JSON `{filename, characters, summary}` |

## Cấu trúc project

```
├── app.py                  # FastAPI server
├── start.bat               # Quick start (Windows)
├── requirements.txt
├── utils/
│   ├── ai_client.py        # AI calls, chunking, retry, model listing
│   └── extract.py          # Text extraction (.txt/.pdf/.docx)
├── templates/
│   └── index.html          # UI
├── static/
│   ├── app.js              # Frontend + client-side .md export
│   └── styles.css
├── SKILL.md                # Skill documentation
└── know-how.md             # Development log
```

## Ghi chú

- API key có thể nhập trên form hoặc đặt qua env: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `CUSTOM_AI_API_KEY`
- Giới hạn file: 15MB
- Giới hạn ký tự đầu vào: 1.000.000
- Timeout: 600 giây (đủ cho tài liệu lớn)
