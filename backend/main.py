"""FastAPI backend voor Kenniscapture systeem."""

import asyncio
import hashlib
import html
import json
import logging
import os
import re
import urllib.parse
import uuid
from pathlib import Path

import mammoth
import aiofiles
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

import database
import document_parser
import knowledge_engine
import ollama_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
_log = logging.getLogger("app.main")

app = FastAPI(title="Kenniscapture API", version="1.0.0")

# Sta alleen bekende origins toe — uitbreidbaar via CORS_ORIGINS env var
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
]
_extra = os.getenv("CORS_ORIGINS", "")
_allowed_origins = _default_origins + [
    o.strip() for o in _extra.split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "../uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
async def startup() -> None:
    database.init_db()
    _log.info("Database geinitialiseerd — Ollama model voorladen...")
    try:
        await ollama_client._ollama_request("ping")
        _log.info("Ollama model geladen — API klaar")
    except Exception as exc:
        _log.warning("Ollama warmup mislukt (niet fataal): %s", exc)


# === Request modellen ===


class GenerateQuestionRequest(BaseModel):
    document_id: int
    contract_type: str
    detected_topics: list[str]
    source_passage: str
    source_file: str
    passages_by_topic: dict[str, str] = {}


class SaveAnswerRequest(BaseModel):
    question_id: str
    question: str
    answer: str
    topic: str
    contract_type: str
    source_file: str
    source_passage: str
    source_page: int | None = None


class SkipQuestionRequest(BaseModel):
    question_id: str
    reason: str  # "straks" | "niet_relevant"


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict[str, str]]


# === Endpoints ===


@app.post("/api/upload-document")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    existing = database.get_processed_document(file_hash)
    if existing:
        try:
            topics = json.loads(existing["extracted_topics"] or "[]")
        except json.JSONDecodeError:
            _log.warning("Corrupt extracted_topics voor %s", existing.get("filename"))
            topics = []
        _log.info("Document al verwerkt: %s", file.filename)
        return {
            "document_id": existing["id"],
            "filename": existing["filename"],
            "contract_type": existing["contract_type"],
            "file_hash": file_hash,
            "already_processed": True,
            "extracted_text_preview": "",
            "detected_topics": topics,
        }

    suffix = Path(file.filename or "upload.pdf").suffix.lower()
    if suffix not in {".docx", ".pdf"}:
        raise HTTPException(
            status_code=400, detail="Alleen .docx en .pdf bestanden worden ondersteund"
        )

    tmp_path = UPLOAD_DIR / f"{file_hash}{suffix}"
    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(content)

    try:
        if suffix == ".docx":
            text, passages = document_parser.parse_docx(tmp_path)
        else:
            text, passages = document_parser.parse_pdf(tmp_path)
    except Exception as exc:
        _log.warning(
            "Document parsing mislukt voor %s: %s", file.filename, exc, exc_info=True
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    all_topics = database.get_all_topics()
    topics_list = [t["topic"] for t in all_topics]

    try:
        analysis = await ollama_client.analyze_document(text[:5000], topics_list)
    except Exception as exc:
        _log.warning("Ollama analyse mislukt: %s", exc, exc_info=True)
        analysis = {"contract_type": "anders", "detected_topics": []}

    contract_type = analysis.get("contract_type", "anders")
    detected = analysis.get("detected_topics", [])

    # Voeg paginanummers toe vanuit de parsing
    for item in detected:
        passage_text = item.get("passage", "")
        for p in passages:
            if passage_text and passage_text[:50] in p.get("text", ""):
                item["page"] = p.get("page")
                break

    doc_id = database.save_processed_document(
        filename=file.filename or "upload",
        file_hash=file_hash,
        contract_type=contract_type,
        page_count=len(passages),
        extracted_topics=json.dumps(detected),
    )

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "contract_type": contract_type,
        "file_hash": file_hash,
        "already_processed": False,
        "extracted_text_preview": text[:500],
        "detected_topics": [
            {
                "topic": item.get("topic", ""),
                "topic_label": database.get_topic_label(item.get("topic", "")),
                "passage": item.get("passage", ""),
                "page": item.get("page"),
            }
            for item in detected
        ],
    }


@app.post("/api/parse-document")
async def parse_document(file: UploadFile = File(...)):
    """Fase 1: upload + tekst extraheren. Geen Ollama."""
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    existing = database.get_processed_document(file_hash)
    if existing:
        try:
            topics = json.loads(existing["extracted_topics"] or "[]")
        except json.JSONDecodeError:
            _log.warning("Corrupt extracted_topics voor %s", existing.get("filename"))
            topics = []
        return {
            "doc_id": existing["id"],
            "filename": existing["filename"],
            "file_hash": file_hash,
            "already_processed": True,
            "contract_type": existing["contract_type"],
            "detected_topics": [
                {
                    "topic": item.get("topic", ""),
                    "topic_label": database.get_topic_label(item.get("topic", "")),
                    "passage": item.get("passage", ""),
                    "page": item.get("page"),
                }
                for item in topics
            ],
        }

    suffix = Path(file.filename or "upload.pdf").suffix.lower()
    if suffix not in {".docx", ".pdf"}:
        raise HTTPException(
            status_code=400, detail="Alleen .docx en .pdf bestanden worden ondersteund"
        )

    tmp_path = UPLOAD_DIR / f"{file_hash}{suffix}"
    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(content)

    try:
        if suffix == ".docx":
            _, passages = document_parser.parse_docx(tmp_path)
        else:
            _, passages = document_parser.parse_pdf(tmp_path)
    except Exception as exc:
        _log.warning("Parsing mislukt voor %s: %s", file.filename, exc, exc_info=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    doc_id = database.save_document_stub(
        filename=file.filename or "upload",
        file_hash=file_hash,
        page_count=len(passages),
    )
    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "file_hash": file_hash,
        "already_processed": False,
    }


@app.post("/api/analyze-document/{doc_id}")
async def analyze_document_endpoint(doc_id: int):
    """Fase 2: Ollama analyse op al geüpload document."""
    doc = database.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document niet gevonden")

    suffix = Path(doc["filename"]).suffix.lower()
    tmp_path = UPLOAD_DIR / f"{doc['file_hash']}{suffix}"
    if not tmp_path.exists():
        raise HTTPException(
            status_code=404, detail="Bestand niet meer aanwezig op disk"
        )

    try:
        if suffix == ".docx":
            text, passages = document_parser.parse_docx(tmp_path)
        else:
            text, passages = document_parser.parse_pdf(tmp_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    all_topics = database.get_all_topics()
    topics_list = [t["topic"] for t in all_topics]

    try:
        analysis = await ollama_client.analyze_document(text[:5000], topics_list)
    except Exception as exc:
        _log.warning("Ollama analyse mislukt: %s", exc, exc_info=True)
        analysis = {"contract_type": "anders", "detected_topics": []}

    contract_type = analysis.get("contract_type", "anders")
    detected = analysis.get("detected_topics", [])

    for item in detected:
        passage_text = item.get("passage", "")
        for p in passages:
            if passage_text and passage_text[:50] in p.get("text", ""):
                item["page"] = p.get("page")
                break

    database.update_document_analysis(
        doc_id=doc_id,
        contract_type=contract_type,
        extracted_topics=json.dumps(detected),
    )

    return {
        "doc_id": doc_id,
        "contract_type": contract_type,
        "detected_topics": [
            {
                "topic": item.get("topic", ""),
                "topic_label": database.get_topic_label(item.get("topic", "")),
                "passage": item.get("passage", ""),
                "page": item.get("page"),
            }
            for item in detected
        ],
    }


@app.post("/api/generate-question")
async def generate_question(req: GenerateQuestionRequest):
    next_topic = knowledge_engine.get_next_question_topic(
        req.contract_type, req.detected_topics
    )
    if not next_topic:
        return {"has_question": False}

    # Gebruik de passage die bij dit specifieke topic hoort
    passage = req.passages_by_topic.get(next_topic["topic"], req.source_passage)

    asked = database.get_asked_questions(req.contract_type, next_topic["topic"])
    asked_list = [q["question"] for q in asked]

    try:
        result = await ollama_client.generate_question(
            contract_type=req.contract_type,
            passage=passage,
            topic_label=next_topic["topic_label"],
            asked_questions=asked_list,
        )
        question_text = result.get("question", "")
    except Exception as exc:
        _log.warning("Vraag generatie mislukt: %s", exc, exc_info=True)
        question_text = f"Kun je meer vertellen over: {next_topic['topic_label']}?"

    question_id = f"q_{uuid.uuid4().hex[:8]}"
    question_hash = hashlib.md5(question_text.lower().strip().encode()).hexdigest()

    database.save_asked_question(
        contract_type=req.contract_type,
        topic=next_topic["topic"],
        question=question_text,
        question_hash=question_hash,
    )

    return {
        "question_id": question_id,
        "question": question_text,
        "topic": next_topic["topic"],
        "topic_label": next_topic["topic_label"],
        "source_passage": passage,
        "source_file": req.source_file,
        "source_page": None,
        "has_question": True,
    }


@app.post("/api/save-answer")
async def save_answer(req: SaveAnswerRequest):
    chunk_id = database.save_knowledge_chunk(
        contract_type=req.contract_type,
        topic=req.topic,
        topic_label=database.get_topic_label(req.topic),
        question=req.question,
        answer=req.answer,
        source_file=req.source_file,
        source_passage=req.source_passage,
        source_page=req.source_page,
    )
    database.mark_question_answered(req.question_id)
    completion = knowledge_engine.calculate_completion()
    return {"chunk_id": chunk_id, "completion": completion}


@app.post("/api/skip-question")
async def skip_question(req: SkipQuestionRequest):
    if req.reason == "niet_relevant":
        database.mark_question_irrelevant(req.question_id)
    else:
        database.mark_question_skipped(req.question_id)
    return {"status": "ok"}


@app.get("/api/completion")
async def get_completion():
    return knowledge_engine.calculate_completion()


@app.get("/api/documents")
async def get_documents():
    docs = database.get_all_processed_documents()
    result = []
    for doc in docs:
        try:
            topics = json.loads(doc.get("extracted_topics") or "[]")
        except json.JSONDecodeError:
            _log.warning(
                "Corrupt extracted_topics voor document %s", doc.get("filename")
            )
            topics = []
        result.append(
            {
                "id": doc["id"],
                "filename": doc["filename"],
                "contract_type": doc["contract_type"] or "anders",
                "detected_topics": [
                    {
                        "topic": t.get("topic", ""),
                        "topic_label": database.get_topic_label(t.get("topic", "")),
                        "passage": t.get("passage", ""),
                        "page": t.get("page"),
                    }
                    for t in topics
                    if t.get("topic")
                ],
            }
        )
    return {"documents": result}


@app.get("/api/knowledge-bank")
async def get_knowledge_bank():
    chunks = database.get_all_chunks()
    open_topics = knowledge_engine.get_open_topics()
    return {"chunks": chunks, "open_topics": open_topics}


@app.post("/api/reset")
async def reset():
    database.reset_knowledge_bank()
    _log.info("Kennisbank gereset")
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    chunks = database.get_all_chunks()
    used_chunks = chunks[:20]

    knowledge_str = "\n\n".join(
        f"[{c['topic_label']} | Bron: {c['source_file']}"
        + (f" (pagina {c['source_page']})" if c.get("source_page") else "")
        + f"]\nV: {c['question']}\nA: {c['answer']}"
        for c in used_chunks
    )

    async def event_stream():
        full_text = ""
        try:
            async for token in ollama_client.chat_stream(
                message=req.message,
                history=req.conversation_history,
                knowledge_chunks=knowledge_str,
            ):
                full_text += token
                yield f"data: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0)
        except Exception as exc:
            _log.warning("Chat stream mislukt: %s", exc, exc_info=True)
            error_msg = "Er is een fout opgetreden. Controleer of Ollama draait op localhost:11434."
            yield f"data: {json.dumps({'token': error_msg})}\n\n"
            full_text = error_msg

        # Zoek de meest relevante chunks op basis van trefwoorden in het antwoord
        answer_words = {w.lower() for w in full_text.split() if len(w) > 4}
        seen_keys: set[str] = set()
        scored: list[tuple[int, dict]] = []
        for chunk in used_chunks:
            topic_words = set((chunk.get("topic_label") or "").lower().split())
            q_words = set((chunk.get("question") or "").lower().split())
            a_words = set((chunk.get("answer") or "").lower().split())
            matches = len(answer_words & (topic_words | q_words | a_words))
            scored.append((matches, chunk))
        scored.sort(key=lambda x: -x[0])

        sources = []
        for _, chunk in scored[:5]:
            key = f"{chunk.get('source_file')}|{chunk.get('topic_label')}"
            if key not in seen_keys:
                seen_keys.add(key)
                sources.append(
                    {
                        "file": chunk.get("source_file", ""),
                        "topic_label": chunk.get("topic_label", ""),
                        "passage": chunk.get("source_passage", ""),
                        "page": chunk.get("source_page"),
                    }
                )

        yield f"data: {json.dumps({'done': True, 'sources': sources})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/download/{filename:path}")
async def download_file(filename: str):
    doc = database.get_document_by_filename(filename)
    if not doc:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden in database")
    suffix = Path(doc["filename"]).suffix.lower()
    file_path = UPLOAD_DIR / f"{doc['file_hash']}{suffix}"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Bestand niet meer aanwezig op disk"
        )
    # Sanitize bestandsnaam voor Content-Disposition header (RFC 6266)
    safe_name = re.sub(r'["\r\n\\]', "", filename)
    encoded_name = urllib.parse.quote(filename)
    if suffix == ".pdf":
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox",
            },
        )
    if suffix == ".docx":
        try:
            with open(file_path, "rb") as f:
                result = mammoth.convert_to_html(f)
            html_body = result.value
        except Exception as exc:
            _log.warning("DOCX→HTML conversie mislukt voor %s: %s", filename, exc)
            raise HTTPException(
                status_code=422, detail="Bestand kan niet worden weergegeven"
            ) from exc
        escaped_name = html.escape(filename)
        html_page = f"""<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <title>{escaped_name}</title>
  <style>
    body {{ font-family: Calibri, Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 24px; line-height: 1.6; color: #222; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
    td, th {{ border: 1px solid #ccc; padding: 6px 10px; }}
    h1, h2, h3 {{ color: #1a1a2e; }}
    p {{ margin: 0.5em 0; }}
  </style>
</head>
<body>
  <h2 style="color:#666;font-size:0.9em;border-bottom:1px solid #eee;padding-bottom:8px">{escaped_name}</h2>
  {html_body}
</body>
</html>"""
        return HTMLResponse(
            content=html_page,
            headers={
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'none'",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            },
        )
    return FileResponse(
        path=file_path,
        headers={
            "Content-Disposition": f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}",
            "X-Content-Type-Options": "nosniff",
        },
    )
