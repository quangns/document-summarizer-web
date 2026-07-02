from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from utils.ai_client import AIClientError, list_available_models, summarize_text
from utils.extract import ExtractError, extract_text_from_upload


app = FastAPI(title="Web tóm tắt tài liệu")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/summarize")
async def summarize(
    provider: str = Form(...),
    model: str = Form(""),
    api_key: str = Form(""),
    base_url: str = Form(""),
    file: UploadFile = File(...),
):
    try:
        text = await extract_text_from_upload(file)
        summary = await summarize_text(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            text=text,
        )
    except ExtractError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "filename": file.filename,
        "characters": len(text),
        "summary": summary,
    }


@app.post("/models")
async def models(
    provider: str = Form(...),
    api_key: str = Form(""),
    base_url: str = Form(""),
):
    try:
        return await list_available_models(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
        )
    except AIClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
