# Document Summarizer Web

A simple web app that lets you choose an AI provider, upload a document, and get a summary.

## Features
- Select provider: OpenAI, Claude, Gemini, or custom
- Upload `.txt`, `.pdf`, or `.docx` files
- Extract text from the uploaded document
- Generate a concise summary in Vietnamese

## Tech Stack
- FastAPI
- Jinja2 templates
- Python libraries for PDF and DOCX processing

## Quick Start

1. Create and activate a virtual environment
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Run the app
   ```bash
   uvicorn app:app --reload
   ```

4. Open the browser at
   ```text
   http://127.0.0.1:8000
   ```

## Notes
- For OpenAI, provide an API key in the form.
- If the provider is not configured correctly, the app returns a fallback summary based on the extracted text.
