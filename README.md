# AI Document Summarizer

Ứng dụng web tóm tắt tài liệu (.txt, .pdf, .docx) sử dụng AI, hỗ trợ nhiều provider và tự động chia nhỏ theo context window của model.

## Tính năng

- Hỗ trợ nhiều AI provider: OpenAI, Claude, Gemini, Custom (OpenAI-compatible)
- Tải danh sách model trực tiếp từ provider bằng API key
- Kéo thả file hoặc chọn file .txt / .pdf / .docx
- **Context-aware chunking**: tự động tính kích thước chunk dựa trên context window của model đang dùng
- **3-level summarization**: chunk → section synthesis → final synthesis, giữ đủ ý cho tài liệu dài
- Phát hiện cấu trúc tài liệu (Chương/Phần/Hồi/Mục/...) từ mục lục hoặc heading
- Luôn phản hồi bằng tiếng Việt có dấu nếu văn bản nguồn là tiếng Việt
- Sao chép kết quả hoặc xuất file `.md`

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

Hoặc double-click file `start.bat`.

Mở trình duyệt tại **http://127.0.0.1:9000**

## Hướng dẫn sử dụng

1. Chọn **AI Provider** (OpenAI / Claude / Gemini / Custom)
2. (Tùy chọn) Bấm **Tải model** để lấy danh sách model trực tiếp từ provider
3. Chọn **Model**, hoặc chọn `Custom...` để nhập tay
4. Nhập **API Key**
5. Với Custom provider, nhập thêm **Base URL**
6. Kéo thả hoặc chọn file tài liệu
7. Bấm **Tóm tắt** và chờ kết quả
8. Dùng nút **Sao chép** hoặc **Xuất file** (`.md`)

## Provider & Model mặc định

| Provider | Model mặc định | Context window |
|----------|---------------|----------------|
| OpenAI | gpt-5.4-mini | 128K tokens |
| Claude | claude-haiku-4-5 | 200K tokens |
| Gemini | gemini-3.5-flash | 1M tokens |
| Custom | gpt-5.4-mini | 128K tokens |

Với model có context lớn (GPT-4.1 1M, Gemini 2.5-Flash 1M), chunk được chia lớn hơn, giảm số lần gọi API và giữ ngữ cảnh tốt hơn.

## API endpoints

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/` | GET | Giao diện web |
| `/models` | POST | Lấy danh sách model (mặc định hoặc live) |
| `/summarize` | POST | Gửi file + cấu hình, nhận bản tóm tắt |

## Cấu trúc project

```
├── app.py                  # FastAPI server
├── start.bat               # Script chạy nhanh (Windows)
├── requirements.txt
├── utils/
│   ├── ai_client.py        # AI provider calls, chunking, summarization pipeline
│   └── extract.py          # Trích xuất text từ file
├── templates/
│   └── index.html          # Giao diện người dùng
└── static/
    ├── app.js              # Frontend logic
    └── styles.css          # Styles
```

## Ghi chú

- API key có thể nhập trên form hoặc đặt qua biến môi trường (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `CUSTOM_AI_API_KEY`)
- Giới hạn file upload: 15MB
- Giới hạn ký tự đầu vào: 1.000.000 ký tự (đủ cho hầu hết tài liệu)
- Request timeout: 600 giây
