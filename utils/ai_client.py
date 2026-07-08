from __future__ import annotations

import asyncio
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import httpx

CONCURRENCY_LIMIT = 2
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0


MAX_INPUT_CHARS = 1_000_000
DIRECT_SUMMARY_THRESHOLD = 12_000
TOC_SCAN_CHARS = 12_000
REQUEST_TIMEOUT = 600

MODEL_CONTEXT_WINDOWS: dict[str, dict[str, int]] = {
    "openai": {
        "gpt-5.5": 131072,
        "gpt-5.4": 131072,
        "gpt-5.4-mini": 131072,
        "gpt-5.4-nano": 131072,
        "gpt-4.1": 1_048_576,
        "gpt-4.1-mini": 1_048_576,
        "*": 131072,
    },
    "claude": {
        "claude-fable-5": 200_000,
        "claude-opus-4-8": 200_000,
        "claude-sonnet-5": 200_000,
        "claude-haiku-4-5": 200_000,
        "*": 200_000,
    },
    "gemini": {
        "gemini-3.5-flash": 1_048_576,
        "gemini-3.1-pro": 1_048_576,
        "gemini-2.5-flash": 1_048_576,
        "gemini-2.5-pro": 1_048_576,
        "*": 1_048_576,
    },
    "custom": {"*": 131_072},
}

MAX_OUTPUT_TOKENS: dict[str, int] = {
    "openai": 8192,
    "claude": 8192,
    "gemini": 8192,
    "custom": 8192,
}
PROMPT_OVERHEAD_TOKENS = 1500


def _max_input_chars(provider: str, model: str) -> int:
    model_map = MODEL_CONTEXT_WINDOWS.get(provider, {})
    context = model_map.get(model) or model_map.get("*", 131072)
    max_output = MAX_OUTPUT_TOKENS.get(provider, 8192)
    available_tokens = context - max_output - PROMPT_OVERHEAD_TOKENS
    return max(available_tokens * 4, 4000)


SECTION_KEYWORDS = (
    "chuong",
    "phuong",
    "phan",
    "thien",
    "hoi",
    "quyen",
    "muc",
    "chapter",
    "part",
    "section",
    "book",
)
HEADING_RE = re.compile(
    r"^(chuong|phuong|phan|thien|hoi|quyen|muc|chapter|part|section|book)\s+"
    r"([0-9ivxlcdm]+|mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi)\b",
    re.IGNORECASE,
)

DEFAULT_MODELS = {
    "openai": "gpt-5.4-mini",
    "claude": "claude-haiku-4-5",
    "gemini": "gemini-3.5-flash",
    "custom": "gpt-5.4-mini",
}

DEFAULT_MODEL_OPTIONS = {
    "openai": [
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-4.1",
        "gpt-4.1-mini",
    ],
    "claude": [
        "claude-fable-5",
        "claude-opus-4-8",
        "claude-sonnet-5",
        "claude-haiku-4-5",
        "claude-3-5-haiku-latest",
    ],
    "gemini": [
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-3.1-pro",
        "gemini-3-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
    ],
    "custom": [
        "gpt-5.4-mini",
        "gpt-4.1-mini",
        "llama-3.1-8b-instruct",
    ],
}


@dataclass
class SectionChunk:
    title: str
    content: str


class AIClientError(Exception):
    """Raised when an AI provider request fails."""


async def list_available_models(
    provider: str, api_key: str, base_url: str
) -> dict[str, Any]:
    provider = provider.strip().lower()
    api_key = api_key.strip() or _api_key_from_env(provider)
    base_url = base_url.strip().rstrip("/")

    if provider not in DEFAULT_MODELS:
        raise AIClientError("Provider chưa được hỗ trợ.")

    if not api_key:
        return {"source": "default", "models": DEFAULT_MODEL_OPTIONS[provider]}

    if provider == "openai":
        models = await _list_openai_compatible_models(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
        )
    elif provider == "claude":
        models = await _list_claude_models(api_key=api_key)
    elif provider == "gemini":
        models = await _list_gemini_models(api_key=api_key)
    else:
        if not base_url:
            raise AIClientError("Provider custom cần base URL để tải danh sách model.")
        models = await _list_openai_compatible_models(
            api_key=api_key, base_url=base_url
        )

    return {"source": "live", "models": models or DEFAULT_MODEL_OPTIONS[provider]}


async def summarize_text(
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    text: str,
) -> str:
    provider = provider.strip().lower()
    model = model.strip() or DEFAULT_MODELS.get(provider, "")
    api_key = api_key.strip() or _api_key_from_env(provider)
    base_url = base_url.strip().rstrip("/")

    if provider not in DEFAULT_MODELS:
        raise AIClientError("Provider chưa được hỗ trợ.")
    if not model:
        raise AIClientError("Vui lòng nhập model.")
    if not api_key:
        raise AIClientError(
            "Vui lòng nhập API key hoặc cấu hình biến môi trường tương ứng."
        )
    if provider == "custom" and not base_url:
        raise AIClientError("Provider custom cần base URL.")

    normalized_text = _normalize_text(text)
    source_text = normalized_text[:MAX_INPUT_CHARS]
    truncated = len(normalized_text) > MAX_INPUT_CHARS

    max_chars = _max_input_chars(provider, model)

    # Nếu toàn bộ văn bản vừa context → 1 API call duy nhất, không chunk
    if len(source_text) <= max_chars * 0.8:
        prompt = _build_direct_summary_prompt(source_text, truncated=truncated)
        return await _call_with_retry(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            prompt=prompt,
        )

    chunks = _split_into_chunks(source_text, max_chars)

    # Level 1 + 2: summarize sections concurrently, synthesize sub-chunks if needed
    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def _call(prompt: str) -> str:
        async with sem:
            return await _call_with_retry(
                provider=provider, model=model, api_key=api_key,
                base_url=base_url, prompt=prompt,
            )

    async def _summarize_one(chunk: SectionChunk) -> tuple[str, str]:
        if len(chunk.content) <= max_chars:
            prompt = _build_chunk_summary_prompt(
                chunk=chunk, chunk_index=0, total_chunks=len(chunks),
                truncated=truncated,
            )
            summary = await _call(prompt)
            return (chunk.title, summary)

        # Level 2: split large section into sub-chunks
        sub_chunks = _split_large_section(chunk.title, chunk.content, max_chars)
        sub_tasks = []
        for sub in sub_chunks:
            p = _build_chunk_summary_prompt(
                chunk=sub, chunk_index=0, total_chunks=len(sub_chunks),
                truncated=truncated,
            )
            sub_tasks.append(_call(p))

        sub_summaries = await asyncio.gather(*sub_tasks)
        synth_prompt = _build_sub_section_synthesis_prompt(chunk.title, sub_summaries)
        merged = await _call(synth_prompt)
        return (chunk.title, merged)

    results = await asyncio.gather(*[_summarize_one(c) for c in chunks])
    section_summaries = list(results)

    # Level 3: synthesize all section summaries into final
    final_prompt = _build_final_summary_prompt(
        chunk_notes=[s for _, s in section_summaries],
        section_titles=[t for t, _ in section_summaries],
        original_length=len(source_text),
        truncated=truncated,
    )
    return await _call_with_retry(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        prompt=final_prompt,
    )


def export_to_md(
    filename: str,
    final_summary: str,
    section_summaries: list[tuple[str, str]],
    char_count: int,
) -> str:
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = [
        f"# Tóm tắt tài liệu: {filename}",
        "",
        f"- **File gốc:** {filename}",
        f"- **Số ký tự:** {char_count:,}",
        f"- **Ngày tạo:** {timestamp}",
        "",
        "---",
        "",
        "## Tổng hợp",
        "",
        final_summary,
        "",
        "---",
        "",
        "## Tóm tắt chi tiết từng phần",
        "",
    ]
    for title, summary in section_summaries:
        lines.append(f"### {title}")
        lines.append("")
        lines.append(summary)
        lines.append("")

    return "\n".join(lines)


def _api_key_from_env(provider: str) -> str:
    names = {
        "openai": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "custom": "CUSTOM_AI_API_KEY",
    }
    return os.getenv(names.get(provider, ""), "")


def _normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _split_into_chunks(text: str, target_chars: int) -> list[SectionChunk]:
    section_chunks = _split_by_sections(text, target_chars)
    if section_chunks:
        return section_chunks
    return _split_by_length(text, target_chars)


def _split_by_sections(text: str, target_chars: int) -> list[SectionChunk]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) < 6:
        return []

    toc_titles, toc_end_line_index = _extract_toc_titles(lines)
    sections = _build_sections_from_titles(lines, toc_titles, toc_end_line_index)
    if not sections:
        sections = _build_sections_from_detected_headings(
            lines,
            start_index=toc_end_line_index if toc_titles else 0,
        )

    if len(sections) < 2:
        return []

    expanded: list[SectionChunk] = []
    for title, content in sections:
        content = content.strip()
        if not content:
            continue
        if len(content) <= target_chars:
            expanded.append(SectionChunk(title=title, content=content))
            continue
        expanded.extend(_split_large_section(title, content, target_chars))

    return expanded if len(expanded) >= 2 else []


def _split_by_length(text: str, target_chars: int) -> list[SectionChunk]:
    if len(text) <= target_chars:
        return [SectionChunk(title="Toan bo tai lieu", content=text)]

    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    if not blocks:
        return [SectionChunk(title="Toan bo tai lieu", content=text)]

    chunks: list[SectionChunk] = []
    current: list[str] = []
    current_len = 0

    for block in blocks:
        block_len = len(block) + 2
        if current and current_len + block_len > target_chars:
            chunks.append(
                SectionChunk(
                    title=f"Cum noi dung {len(chunks) + 1}",
                    content="\n\n".join(current),
                )
            )
            current = [block]
            current_len = len(block)
            continue

        if block_len > target_chars:
            if current:
                chunks.append(
                    SectionChunk(
                        title=f"Cum noi dung {len(chunks) + 1}",
                        content="\n\n".join(current),
                    )
                )
                current = []
                current_len = 0

            chunks.extend(
                _split_large_section(
                    f"Cum noi dung {len(chunks) + 1}", block, target_chars
                )
            )
            continue

        current.append(block)
        current_len += block_len

    if current:
        chunks.append(
            SectionChunk(
                title=f"Cum noi dung {len(chunks) + 1}",
                content="\n\n".join(current),
            )
        )

    return chunks or [SectionChunk(title="Toan bo tai lieu", content=text)]


def _extract_toc_titles(lines: list[str]) -> tuple[list[str], int]:
    titles: list[str] = []
    scan_limit = min(len(lines), 220)
    toc_end_line_index = 0
    last_toc_line_index = -1
    scanned_chars = 0

    for index, line in enumerate(lines[:scan_limit]):
        scanned_chars += len(line)
        if scanned_chars > TOC_SCAN_CHARS:
            break

        cleaned = _clean_toc_line(line)
        if not cleaned:
            continue
        if _looks_like_heading(cleaned) and _looks_like_toc_entry(line):
            titles.append(cleaned)
            last_toc_line_index = index

    titles = _dedupe_preserve_order(titles)
    if len(titles) < 3:
        return [], 0

    toc_end_line_index = last_toc_line_index + 1
    return titles, toc_end_line_index


def _build_sections_from_titles(
    lines: list[str],
    toc_titles: list[str],
    toc_end_line_index: int,
) -> list[tuple[str, str]]:
    if not toc_titles:
        return []

    normalized_toc = [_normalize_for_match(title) for title in toc_titles]
    matches: list[tuple[int, str]] = []

    for line_index in range(toc_end_line_index, len(lines)):
        normalized_line = _normalize_for_match(lines[line_index])
        if not normalized_line:
            continue
        for title, normalized_title in zip(toc_titles, normalized_toc):
            if normalized_line == normalized_title or normalized_line.startswith(
                normalized_title
            ):
                if matches and matches[-1][1] == title:
                    break
                matches.append((line_index, title))
                break

    if len(matches) < 2:
        return []
    return _materialize_sections(lines, matches)


def _build_sections_from_detected_headings(
    lines: list[str],
    start_index: int = 0,
) -> list[tuple[str, str]]:
    matches: list[tuple[int, str]] = []
    for index in range(start_index, len(lines)):
        line = lines[index]
        if _looks_like_heading(line):
            if matches and matches[-1][1] == line:
                continue
            matches.append((index, line))

    if len(matches) < 2:
        return []
    return _materialize_sections(lines, matches)


def _materialize_sections(
    lines: list[str], matches: list[tuple[int, str]]
) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for idx, (start_line, title) in enumerate(matches):
        end_line = matches[idx + 1][0] if idx + 1 < len(matches) else len(lines)
        section_lines = lines[start_line:end_line]
        content = "\n".join(section_lines).strip()
        if content:
            sections.append((title, content))
    return sections


def _split_large_section(
    title: str, content: str, target_chars: int
) -> list[SectionChunk]:
    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
    if not blocks:
        blocks = [content]

    chunks: list[SectionChunk] = []
    current: list[str] = []
    current_len = 0
    part_index = 1

    for block in blocks:
        block_len = len(block) + 2
        if current and current_len + block_len > target_chars:
            chunks.append(
                SectionChunk(
                    title=f"{title} - phan {part_index}",
                    content="\n\n".join(current),
                )
            )
            current = [block]
            current_len = len(block)
            part_index += 1
            continue

        if block_len > target_chars:
            if current:
                chunks.append(
                    SectionChunk(
                        title=f"{title} - phan {part_index}",
                        content="\n\n".join(current),
                    )
                )
                current = []
                current_len = 0
                part_index += 1

            start = 0
            while start < len(block):
                end = min(start + target_chars, len(block))
                chunks.append(
                    SectionChunk(
                        title=f"{title} - phan {part_index}",
                        content=block[start:end].strip(),
                    )
                )
                start = end
                part_index += 1
            continue

        current.append(block)
        current_len += block_len

    if current:
        chunks.append(
            SectionChunk(
                title=f"{title} - phan {part_index}",
                content="\n\n".join(current),
            )
        )

    return chunks


def _clean_toc_line(line: str) -> str:
    if not any(keyword in _normalize_for_match(line) for keyword in SECTION_KEYWORDS):
        return ""
    cleaned = re.sub(r"[.\-_·•]{2,}\s*\d+\s*$", "", line).strip()
    cleaned = re.sub(r"\s+\d+\s*$", "", cleaned).strip()
    return cleaned


def _looks_like_toc_entry(line: str) -> bool:
    stripped = line.strip()
    return bool(
        re.search(r"[.\-_·•]{2,}\s*\d+\s*$", stripped)
        or re.search(r"\s+\d+\s*$", stripped)
    )


def _looks_like_heading(line: str) -> bool:
    normalized = _normalize_for_match(line)
    if len(normalized) > 160:
        return False
    return bool(HEADING_RE.match(normalized))


def _normalize_for_match(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    ascii_text = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    ascii_text = ascii_text.replace("đ", "d").replace("Đ", "D")
    ascii_text = re.sub(r"\s+", " ", ascii_text).strip().lower()
    return ascii_text


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = _normalize_for_match(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _build_direct_summary_prompt(text: str, truncated: bool) -> str:
    note = ""
    if truncated:
        note = "\nLuu y: tai lieu goc dai hon gioi han xu ly nen chi phan dau da duoc dung de tao ban tom tat."

    return f"""Ban la tro ly chuyen tom tat tai lieu dai theo huong day du y, khong tom tat qua ngan.
Muc tieu la giu lai hau het y chinh quan trong thay vi chi viet vai cau tong quan.{note}

Hay tao ban tom tat bang tieng Viet theo dung khung sau:

1. Tong quan tai lieu
- 1 doan ngan neu chu de, boi canh va muc dich chinh.

2. Cac y chinh trong tam
- Liet ke 6-12 gach dau dong, moi y 1-2 cau.
- Giu cac luan diem, phat hien, quyet dinh, quy trinh hoac ket luan quan trong.

3. Y quan trong theo tung phan hoac tung nhom noi dung
- Gom cac y lien quan lai theo cum noi dung.
- Neu tai lieu co cau truc ro rang, phan anh lai cau truc do.

4. So lieu, moc thoi gian, ten rieng va chi tiet cu the
- Chi neu nhung chi tiet thuc su xuat hien trong tai lieu.

5. Ket luan, de xuat, rui ro hoac viec can lam tiep
- Neu tai lieu khong co muc nay, ghi ro la khong thay neu ro.

Quy tac:
- Khong suy doan.
- Khong bo sot y chi vi muon ngan.
- Do dai ban tom tat phai tuong xung voi luong thong tin cua tai lieu.
- Neu tai lieu chua nhieu y nho, uu tien liet ke ro tung y.

Tai lieu:
\"\"\"
{text}
\"\"\""""


def _build_chunk_summary_prompt(
    chunk: SectionChunk,
    chunk_index: int,
    total_chunks: int,
    truncated: bool,
) -> str:
    note = ""
    if truncated:
        note = "\nLuu y: toan bo tai lieu goc da bi cat bot theo gioi han xu ly truoc khi chia doan."

    return f"""Ban dang doc phan {chunk_index}/{total_chunks} cua mot tai lieu dai.{note}
Tieu de phan nay: {chunk.title}

Hay trich xuat day du y quan trong trong rieng phan nay, khong viet qua ngan.

Tra loi bang tieng Viet voi dung khung sau:

1. Tieu de hoac vai tro cua phan nay
- 1-2 cau.

2. Y chinh trong phan
- 5-10 gach dau dong.
- Moi y nen cu the, giu so lieu, ten rieng, hanh dong hoac ket luan neu co.

3. Chi tiet quan trong
- So lieu, thoi gian, ten nguoi, ten to chuc, thuat ngu, dieu kien, ngoai le.

4. Diem can noi voi cac phan khac
- Nhung diem co ve la ket luan, phu thuoc, tranh luan hoac hanh dong tiep theo.

Noi dung phan:
\"\"\"
{chunk.content}
\"\"\""""


def _build_sub_section_synthesis_prompt(title: str, sub_summaries: list[str]) -> str:
    parts = "\n\n".join(f"### Phần {i + 1}\n{s}" for i, s in enumerate(sub_summaries))
    return f"""Ban dang tong hop cac phan nho cung mot muc '{title}' trong tai lieu.

Hay hop nhat chung lai thanh mot ban tom tat thong nhat cho rieng muc nay, theo khung:

1. Y chinh cua muc {title}
2. Cac chi tiet quan trong (so lieu, ten rieng, thoi gian)
3. Ket luan hoac diem noi bat

Cac phan nho:
{parts}

Tra loi bang tieng Viet co day du dau."""


def _build_final_summary_prompt(
    chunk_notes: list[str],
    section_titles: list[str],
    original_length: int,
    truncated: bool,
) -> str:
    note = ""
    if truncated:
        note = "\nLuu y: tai lieu da bi cat o gioi han xu ly, vi vay chi tong hop tren phan noi dung da duoc doc."

    merged_notes = "\n\n".join(chunk_notes)
    section_overview = "\n".join(f"- {title}" for title in section_titles)
    return f"""Ban se hop nhat cac ghi chu tom tat cua nhieu phan trong cung mot tai lieu dai.{note}
Tai lieu nguon co khoang {original_length} ky tu va da duoc chia thanh {len(chunk_notes)} phan.

Cac phan da nhan dien:
{section_overview}

Hay tao ban tom tat cuoi cung bang tieng Viet theo dung khung sau:

1. Tong quan tai lieu
- 1 doan mo ta chu de, muc tieu, boi canh.

2. Cac y chinh trong tam
- Liet ke 8-16 gach dau dong.
- Moi y can du cu the de nguoi doc khong phai quay lai tai lieu goc moi hieu duoc y chinh.

3. Y chinh theo tung phan
- Dung cac phan da nhan dien lam khung chinh neu phu hop.
- Moi phan co tieu de ngan va cac y ben duoi.

4. So lieu, moc thoi gian, ten rieng va chi tiet dang chu y
- Chi giu lai cac chi tiet thuc su quan trong.

5. Ket luan, de xuat, rui ro hoac viec can lam tiep
- Neu khong thay, ghi ro la khong thay neu ro.

Quy tac:
- Hop nhat cac y trung nhau nhung khong lam mat thong tin.
- Khong tao them thong tin moi.
- Uu tien do day du va ro rang hon viec viet that ngan.
- Neu tai lieu co nhieu phan, dung gom tat ca thanh mot doan ngan.

Ghi chu tu cac phan:
\"\"\"
{merged_notes}
\"\"\""""


async def _call_with_retry(
    provider: str, model: str, api_key: str, base_url: str, prompt: str,
) -> str:
    last_error = ""
    for attempt in range(MAX_RETRIES):
        try:
            return await _generate_summary(
                provider=provider, model=model, api_key=api_key,
                base_url=base_url, prompt=prompt,
            )
        except AIClientError as exc:
            msg = str(exc).lower()
            last_error = str(exc)
            is_rate = any(k in msg for k in (
                "high demand", "rate limit", "too many", "429", "503",
                "capacity", "overloaded", "try again", "quota exceeded",
                "quota", "retry", "resource exhausted", "limit",
            ))
            if not is_rate or attempt == MAX_RETRIES - 1:
                raise
            # Parse "retry in Xs" từ error message (Gemini gửi exact time)
            import re
            m = re.search(r"retry in\s+([\d.]+)\s*s", str(exc), re.IGNORECASE)
            delay = float(m.group(1)) + 1 if m else RETRY_BASE_DELAY * (2 ** attempt)
            print(f"  API busy (lần {attempt+1}), đợi {delay:.0f}s...")
            await asyncio.sleep(delay)
    raise AIClientError(f"Quá tải sau {MAX_RETRIES} lần thử: {last_error}")


async def _generate_summary(
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    prompt: str,
) -> str:
    if provider == "openai":
        return await _call_openai_responses(api_key=api_key, model=model, prompt=prompt)
    if provider == "claude":
        return await _call_claude(api_key=api_key, model=model, prompt=prompt)
    if provider == "gemini":
        return await _call_gemini(api_key=api_key, model=model, prompt=prompt)
    return await _call_openai_compatible(
        api_key=api_key,
        model=model,
        prompt=prompt,
        base_url=base_url,
    )


async def _call_openai_compatible(
    api_key: str, model: str, prompt: str, base_url: str
) -> str:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Ban tom tat tai lieu chinh xac, ro rang va day du y.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    data = await _post_json(
        url=f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        payload=payload,
    )

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise AIClientError("Provider tra ve du lieu khong dung dinh dang.") from exc


async def _call_openai_responses(api_key: str, model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": "Ban tom tat tai lieu chinh xac, ro rang va day du y.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    data = await _post_json(
        url="https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}"},
        payload=payload,
    )

    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    try:
        parts = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts).strip()
    except AttributeError as exc:
        raise AIClientError("OpenAI tra ve du lieu khong dung dinh dang.") from exc

    raise AIClientError("OpenAI khong tra ve noi dung tom tat.")


async def _call_claude(api_key: str, model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "max_tokens": 2400,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }
    data = await _post_json(
        url="https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        payload=payload,
    )

    try:
        parts = data["content"]
        return "\n".join(
            part["text"] for part in parts if part.get("type") == "text"
        ).strip()
    except (KeyError, TypeError) as exc:
        raise AIClientError("Claude tra ve du lieu khong dung dinh dang.") from exc


async def _call_gemini(api_key: str, model: str, prompt: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    data = await _post_json(
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        headers={},
        payload=payload,
    )

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise AIClientError("Gemini tra ve du lieu khong dung dinh dang.") from exc


async def _list_openai_compatible_models(api_key: str, base_url: str) -> list[str]:
    data = await _get_json(
        url=f"{base_url}/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    raw_models = data.get("data", [])
    ids = [
        item.get("id")
        for item in raw_models
        if isinstance(item, dict) and item.get("id")
    ]
    return _sort_model_ids(ids)


async def _list_claude_models(api_key: str) -> list[str]:
    data = await _get_json(
        url="https://api.anthropic.com/v1/models?limit=100",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    raw_models = data.get("data", [])
    ids = [
        item.get("id")
        for item in raw_models
        if isinstance(item, dict) and item.get("id")
    ]
    return _sort_model_ids(ids)


async def _list_gemini_models(api_key: str) -> list[str]:
    data = await _get_json(
        url=f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        headers={},
    )
    raw_models = data.get("models", [])
    ids = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        methods = item.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        name = str(item.get("name", "")).removeprefix("models/")
        if name:
            ids.append(name)
    return _sort_model_ids(ids)


async def _post_json(
    url: str, headers: dict[str, str], payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise AIClientError(f"Khong ket noi duoc toi AI provider: {exc}") from exc

    if response.status_code >= 400:
        raise AIClientError(_provider_error_message(response))

    try:
        return response.json()
    except ValueError as exc:
        raise AIClientError("Provider khong tra ve JSON hop le.") from exc


def _provider_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"Provider bao loi HTTP {response.status_code}."

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("type")
            if message:
                return str(message)
        if isinstance(error, str):
            return error

    return f"Provider bao loi HTTP {response.status_code}."


async def _get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise AIClientError(f"Khong ket noi duoc toi AI provider: {exc}") from exc

    if response.status_code >= 400:
        raise AIClientError(_provider_error_message(response))

    try:
        return response.json()
    except ValueError as exc:
        raise AIClientError("Provider khong tra ve JSON hop le.") from exc


def _sort_model_ids(model_ids: list[str]) -> list[str]:
    unique = sorted({model_id for model_id in model_ids if model_id})
    preferred_keywords = (
        "gpt",
        "claude",
        "gemini",
        "llama",
        "mistral",
        "qwen",
        "deepseek",
    )
    text_models = [
        model_id
        for model_id in unique
        if any(keyword in model_id.lower() for keyword in preferred_keywords)
    ]
    return text_models or unique
