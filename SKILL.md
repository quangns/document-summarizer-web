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
- Mỗi khi thực hiện thay đổi code, phải cập nhật file `know-how.md` để lưu lại cách xử lý đã làm.
- Mỗi lần code phải đọc lại skill này và file `know-how.md` trước khi bắt đầu.
- Viết code tối thiểu; nếu thư viện đã có sẵn thì ưu tiên dùng thư viện đó thay vì tự triển khai lại.

## Khi nào nên dùng

Dùng skill này khi người dùng muốn một phiên bản thân thiện hơn so với chạy script dòng lệnh, cụ thể là:

- Cần giao diện web để upload file.
- Muốn chọn provider/model từ UI thay vì sửa config thủ công.
- Muốn xem danh sách model available theo provider để chọn.
- Muốn kéo thả tài liệu trực tiếp lên vùng upload.
- Cần xem kết quả tóm tắt ngay trên trình duyệt.

## Luồng làm việc

### 1. Chọn công nghệ

Ưu tiên một stack đơn giản và dễ triển khai:

- Backend: FastAPI hoặc Flask.
- Frontend: HTML + CSS + JavaScript thuần, hoặc React nếu cần giao diện phức tạp hơn.
- Lưu trữ cấu hình: file `config.json` hoặc biến môi trường.

### 2. Thiết kế giao diện web

Trang web nên có các thành phần sau:

- Dropdown chọn provider.
- Dropdown chọn model theo provider.
- Nút tải danh sách model live từ provider bằng API key/base URL hiện nhập.
- Ô nhập model custom khi người dùng chọn `Custom...`.
- Input API key, có thể để trống nếu backend đã cấu hình biến môi trường.
- Input base URL cho provider custom/openai-compatible.
- Vùng upload file hỗ trợ cả bấm chọn lẫn kéo thả.
- Nút `Tóm tắt`.
- Khu vực hiển thị trạng thái xử lý, nội dung tóm tắt và lỗi rõ ràng.

### 3. Xây dựng backend

Tạo API để nhận file và cấu hình provider:

- `POST /summarize`
  - Nhận `provider`, `model`, `api_key`, `base_url`, `file`.
  - Trích xuất văn bản từ file.
  - Nếu tài liệu ngắn, tạo tóm tắt trực tiếp bằng một prompt có khung rõ ràng.
- Nếu tài liệu dài, chia tài liệu thành nhiều đoạn, tóm tắt từng đoạn, rồi hợp nhất thành bản tóm tắt cuối.
- Nếu tài liệu có mục lục hoặc các tiêu đề phần rõ như `Chương/Phần/Thiên/Hồi/Mục/...`, ưu tiên chia theo các phần đó trước khi chia theo độ dài.
  - Trả kết quả về frontend.

- `POST /models`
  - Nhận `provider`, `api_key`, `base_url`.
  - Nếu chưa có API key, trả danh sách model mặc định theo provider.
  - Nếu có API key, tải danh sách model live từ provider:
    - OpenAI/custom: gọi endpoint OpenAI-compatible `/models`.
    - Claude: gọi Anthropic Models API.
    - Gemini: gọi Gemini Models API và ưu tiên model hỗ trợ `generateContent`.

### 4. Xử lý upload file

Hỗ trợ các định dạng:

- `.txt`: đọc trực tiếp nội dung.
- `.pdf`: trích xuất text từ từng trang.
- `.docx`: đọc văn bản từ paragraph và table cell.

Nếu định dạng không được hỗ trợ, trả lỗi rõ ràng cho người dùng.

### 5. Tích hợp AI provider

Backend cần hỗ trợ nhiều provider khác nhau:

- OpenAI.
- Claude.
- Gemini.
- Custom/openai-compatible.

Cách làm:

- Dùng một module chung để gọi AI.
- Lấy thông tin provider/model/api key/base URL từ form hoặc config.
- Gửi prompt tóm tắt và nhận kết quả.
- Với custom provider, dùng API tương thích OpenAI khi có thể.

### 6. Tạo khung tóm tắt

Không chỉ yêu cầu "tóm tắt ngắn gọn". Cần ép đầu ra theo khung rõ ràng để giảm phụ thuộc vào việc model có tự hiểu đúng hay không.

Khung gợi ý:

- `Tổng quan tài liệu`
- `Các ý chính trọng tâm`
- `Ý chính theo từng phần hoặc từng nhóm nội dung`
- `Số liệu, mốc thời gian, tên riêng và chi tiết cụ thể`
- `Kết luận, đề xuất, rủi ro hoặc việc cần làm tiếp`

Quy tắc:

- Độ dài bản tóm tắt phải tương xứng với độ dài tài liệu.
- Không được làm ngắn quá mức nếu tài liệu chứa nhiều ý.
- Không suy đoán thông tin không có trong nguồn.
- Ưu tiên giữ số liệu, mốc thời gian, tên riêng và kết luận rõ ràng.
- Với tài liệu dài, dùng chiến lược nhiều bước:
  1. Tìm cấu trúc phần từ mục lục hoặc heading như `Chương/Phần/Thiên/Hồi/...`.
  2. Tóm tắt từng phần theo khung rút gọn.
  3. Hợp nhất các phần thành bản tóm tắt cuối theo khung đầy đủ.

### 7. Hiển thị kết quả

Sau khi xử lý xong, frontend nên hiển thị:

- Bản tóm tắt chính.
- Tên file và số ký tự đã trích xuất.
- Nút sao chép nhanh nội dung tóm tắt.
- Nút xuất bản tóm tắt thành file nếu người dùng muốn lưu lại.
- Thông báo nếu tài liệu quá dài hoặc cần tách đoạn trước khi tóm tắt.
- Lỗi upload, lỗi API key, lỗi provider/model không hỗ trợ.

## Cấu trúc đề xuất cho dự án

- `app.py` hoặc `main.py`: khởi chạy web app.
- `templates/`: giao diện HTML.
- `static/`: CSS/JS.
- `utils/extract.py`: trích xuất nội dung từ file.
- `utils/ai_client.py`: gọi provider AI, chia đoạn tài liệu và tải danh sách model.
- `utils/ai_client.py`: gọi provider AI, nhận diện mục lục/tiêu đề phần, chia tài liệu theo phần và tải danh sách model.
- `config.json` hoặc `.env`: lưu thông tin cấu hình.
- `know-how.md`: ghi lại quyết định, cách xử lý lỗi và mẹo đã áp dụng.

## Quy tắc làm việc khi code

- Trước khi bắt đầu, đọc lại skill này và file `know-how.md`.
- Nếu đã có thư viện hỗ trợ xử lý PDF, DOCX, upload file hoặc gọi AI, ưu tiên dùng thư viện đó.
- Không viết lại logic đã có sẵn nếu có thể dùng library hiện có.
- Khi hoàn thành một phần việc, cập nhật `know-how.md` bằng những gì đã làm và lưu ý để lần sau dùng lại.

## Tiêu chí chất lượng

- Giao diện phải dễ dùng, không đòi hỏi người dùng sửa code.
- Upload file phải hoạt động với các định dạng phổ biến.
- Vùng upload phải hỗ trợ kéo thả thực sự, không chỉ hiển thị chữ hướng dẫn.
- Người dùng có thể đổi provider/model trực tiếp từ giao diện.
- Người dùng có thể xem và tải danh sách model available để chọn.
- Kết quả tóm tắt phải giữ đủ ý chính, không quá ngắn và không phụ thuộc hoàn toàn vào khả năng tự suy luận của model.
- Khi tài liệu có cấu trúc phần rõ ràng, bản tóm tắt phải bám theo cấu trúc đó thay vì cắt cơ học theo số ký tự.
- Trường hợp lỗi phải hiện thông báo rõ ràng.

## Đầu ra mong muốn

Khi hoàn thành, skill nên tạo ra một ứng dụng web có các tính năng:

- Chọn provider.
- Chọn model từ dropdown hoặc nhập model custom.
- Tải danh sách model live từ provider khi có API key.
- Nhập API key/base URL nếu cần.
- Upload file bằng chọn file hoặc kéo thả.
- Xử lý và tóm tắt nội dung theo khung có cấu trúc.
- Với tài liệu dài, dùng tóm tắt nhiều bước để giữ đủ ý.
- Với tài liệu có mục lục hoặc heading phần, dùng chính cấu trúc đó để chia phần và tóm tắt.
- Hiển thị kết quả trên màn hình.
- Cho phép sao chép hoặc xuất file từ khu vực kết quả.

## Gợi ý triển khai nhanh

Nếu cần triển khai nhanh, ưu tiên:

- FastAPI + HTML/JS.
- Endpoint `/summarize`.
- Endpoint `/models`.
- Một giao diện tối giản nhưng đầy đủ chức năng.
- Pipeline tóm tắt hai tầng cho tài liệu dài: `chunk summary -> final synthesis`.
