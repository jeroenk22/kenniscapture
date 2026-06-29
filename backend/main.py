"""FastAPI backend voor Kenniscapture systeem."""
import hashlib
import json
import logging
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "../uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
async def startup() -> None:
    database.init_db()
    _log.info("Database geinitialiseerd — API klaar")


# === Request modellen ===

class GenerateQuestionRequest(BaseModel):
    document_id: int
    contract_type: str
    detected_topics: list[str]
    source_passage: str
    source_file: str


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
        topics = json.loads(existing["extracted_topics"] or "[]")
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
        raise HTTPException(status_code=400, detail="Alleen .docx en .pdf bestanden worden ondersteund")

    tmp_path = UPLOAD_DIR / f"{file_hash}{suffix}"
    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(content)

    try:
        if suffix == ".docx":
            text, passages = document_parser.parse_docx(tmp_path)
        else:
            text, passages = document_parser.parse_pdf(tmp_path)
    except Exception as exc:
        _log.warning("Document parsing mislukt voor %s: %s", file.filename, exc, exc_info=True)
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


@app.post("/api/generate-question")
async def generate_question(req: GenerateQuestionRequest):
    next_topic = knowledge_engine.get_next_question_topic(
        req.contract_type, req.detected_topics
    )
    if not next_topic:
        return {"has_question": False}

    asked = database.get_asked_questions(req.contract_type, next_topic["topic"])
    asked_list = [q["question"] for q in asked]

    try:
        result = await ollama_client.generate_question(
            contract_type=req.contract_type,
            passage=req.source_passage,
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
        "source_passage": req.source_passage,
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


@app.get("/api/knowledge-bank")
async def get_knowledge_bank():
    chunks = database.get_all_chunks()
    open_topics = knowledge_engine.get_open_topics()
    return {"chunks": chunks, "open_topics": open_topics}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    chunks = database.get_all_chunks()
    knowledge_str = "\n\n".join(
        f"[{c['topic_label']} | Bron: {c['source_file']}]\n"
        f"V: {c['question']}\nA: {c['answer']}"
        for c in chunks[:20]
    )

    try:
        result = await ollama_client.chat(
            message=req.message,
            history=req.conversation_history,
            knowledge_chunks=knowledge_str,
        )
    except Exception as exc:
        _log.warning("Chat mislukt: %s", exc, exc_info=True)
        result = {
            "answer": "Er is een fout opgetreden. Controleer of Ollama draait op localhost:11434.",
            "sources": [],
        }

    return result
