"""Streamlit kenniscapture tool — Tabblad 1: Kenniscapture | Tabblad 2: Kennisbank."""
import logging
import os
import time
from pathlib import Path

import httpx
import streamlit as st

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("kenniscapture_ui")

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Kenniscapture — Ten Brinke",
    page_icon="📝",
    layout="wide",
)

# === Header met logo ===
_logo_path = Path(__file__).parent / "assets" / "tenbrinke-logo.png"
_col_logo, _col_title = st.columns([1, 6])
with _col_logo:
    if _logo_path.exists():
        st.image(str(_logo_path), width=80)
with _col_title:
    st.markdown("## Kenniscapture Systeem")
    st.caption("Kennisoverdracht · Ten Brinke")

st.divider()


# === Hulpfuncties ===

def _backend_bereikbaar() -> bool:
    try:
        httpx.get(f"{API_BASE}/docs", timeout=2.0)
        return True
    except Exception:
        return False


def _api(method: str, path: str, **kwargs) -> dict:
    """Roep de FastAPI backend aan."""
    url = f"{API_BASE}{path}"
    try:
        resp = httpx.request(method, url, timeout=600.0, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        st.error("❌ Kan backend niet bereiken. Herstart via ./start.sh")
        return {}
    except Exception as exc:
        st.error(f"❌ API fout: {exc}")
        return {}


def _init_session():
    defaults = {
        "current_document": None,
        "current_question": None,
        "pending_questions": [],
        "upload_result": None,
        "upload_queue": [],       # lijst van {name, data, type} wachtend op analyse
        "upload_results": [],     # afgeronde resultaten om te tonen
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_session()

# === Wacht tot backend klaar is ===
_MAX_WACHT = 90

if "backend_start" not in st.session_state:
    st.session_state.backend_start = time.time()

if not _backend_bereikbaar():
    verstreken = time.time() - st.session_state.backend_start
    if verstreken > _MAX_WACHT:
        st.error("❌ Backend niet bereikbaar na 90 seconden. Controleer of `./start.sh` correct draait.")
        st.stop()
    else:
        restant = int(_MAX_WACHT - verstreken)
        with st.spinner(f"⏳ Services starten op... ({restant}s)"):
            time.sleep(2)
        st.rerun()
else:
    st.session_state.pop("backend_start", None)


# === Voortgang ophalen ===
@st.cache_data(ttl=5)
def _get_completion() -> dict:
    return _api("GET", "/api/completion") or {}


# === Sidebar ===
with st.sidebar:
    st.markdown("### ⚙️ Beheer")
    st.divider()
    st.markdown("**Kennisbank resetten**")
    st.caption("Verwijdert alle antwoorden, vragen en verwerkte documenten.")
    if st.button("🗑️ Reset kennisbank", type="secondary", use_container_width=True):
        st.session_state["reset_confirm"] = True

    if st.session_state.get("reset_confirm"):
        st.warning("Weet je het zeker? Dit verwijdert **alles**.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Ja, reset", use_container_width=True):
                result = _api("POST", "/api/reset")
                if result:
                    st.session_state.clear()
                    _get_completion.clear()
                    st.success("✅ Kennisbank gereset.")
                    st.rerun()
        with col2:
            if st.button("❌ Annuleer", use_container_width=True):
                st.session_state["reset_confirm"] = False
                st.rerun()


# === Tabbladen ===
tab1, tab2 = st.tabs(["📝 Kenniscapture", "📚 Kennisbank"])


# =============================================================
# TABBLAD 1 — Kenniscapture
# =============================================================
with tab1:
    st.title("📝 Kenniscapture")
    st.caption("Leg je kennis vast door contracten te uploaden en vragen te beantwoorden.")

    # Voortgangsoverzicht
    completion = _get_completion()
    if completion:
        overall = completion.get("overall", 0.0)
        st.progress(overall, text=f"**Totale voortgang: {overall * 100:.0f}%**")

        by_type = completion.get("by_contract_type", {})
        if by_type:
            cols = st.columns(len(by_type))
            for col, (ct, data) in zip(cols, by_type.items()):
                with col:
                    pct = data.get("percentage", 0) * 100
                    covered = data.get("covered", 0)
                    total = data.get("total", 0)
                    st.metric(
                        label=ct.upper(),
                        value=f"{pct:.0f}%",
                        delta=f"{covered}/{total} topics",
                    )

    st.divider()

    # Document upload
    st.subheader("📄 Document uploaden")
    uploaded_files = st.file_uploader(
        "Upload contracten (Word of PDF)",
        type=["docx", "pdf"],
        accept_multiple_files=True,
        key="file_uploader",
    )

    if uploaded_files and st.button("📤 Analyseer documenten", type="primary"):
        st.session_state.upload_queue = [
            {"name": f.name, "data": f.getvalue(), "type": f.type}
            for f in uploaded_files
        ]
        st.session_state.upload_results = []
        st.rerun()

    # Toon eerdere resultaten
    for res in st.session_state.upload_results:
        if res.get("skipped"):
            st.info(f"ℹ️ {res['filename']} was al eerder verwerkt.")
        elif res.get("warning"):
            st.warning(res["warning"])
        else:
            st.success(
                f"✅ {res['filename']} geanalyseerd — "
                f"contracttype: **{res.get('contract_type', '?')}** | "
                f"{len(res.get('detected_topics', []))} topics gevonden"
            )

    # Verwerk één document per rerun uit de queue
    if st.session_state.upload_queue:
        item = st.session_state.upload_queue[0]
        total = len(st.session_state.upload_queue) + len(st.session_state.upload_results)
        done = len(st.session_state.upload_results)

        st.markdown(f"**Verwerken {done + 1}/{total}: {item['name']}**")
        prog = st.progress(0)
        status = st.empty()

        # Fase 1 — upload + tekst extraheren
        status.caption("📤 Bestand uploaden en tekst extraheren...")
        prog.progress(15)
        parse_result = _api(
            "POST",
            "/api/parse-document",
            files={"file": (item["name"], item["data"], item["type"])},
        )

        if not parse_result:
            prog.progress(100)
            st.session_state.upload_results.append({"filename": item["name"], "warning": f"⚠️ {item['name']}: upload mislukt."})
            st.session_state.upload_queue.pop(0)
            st.rerun()

        prog.progress(40)
        already_done = parse_result.get("already_processed") and parse_result.get("detected_topics")

        if already_done:
            prog.progress(100)
            result = {
                "filename": parse_result["filename"],
                "document_id": parse_result["doc_id"],
                "contract_type": parse_result.get("contract_type"),
                "detected_topics": parse_result.get("detected_topics", []),
                "skipped": True,
            }
            st.session_state.current_document = result
            st.session_state.current_question = None
        else:
            # Fase 2 — Ollama analyse
            status.caption("🤖 AI herkent contracttype en topics — even geduld...")
            prog.progress(45)
            analysis = _api("POST", f"/api/analyze-document/{parse_result['doc_id']}")

            if not analysis or not analysis.get("detected_topics"):
                prog.progress(100)
                st.session_state.upload_results.append({
                    "filename": item["name"],
                    "warning": f"⚠️ {item['name']}: analyse onvolledig. Upload opnieuw om te herproberen.",
                })
                st.session_state.upload_queue.pop(0)
                st.rerun()

            prog.progress(100)
            result = {
                "filename": parse_result["filename"],
                "document_id": parse_result["doc_id"],
                "contract_type": analysis.get("contract_type", "anders"),
                "detected_topics": analysis.get("detected_topics", []),
            }
            st.session_state.current_document = result
            st.session_state.current_question = None

        st.session_state.upload_results.append(result)
        st.session_state.upload_queue.pop(0)
        st.rerun()

    # Automatisch doorgaan met eerder document als sessie leeg is
    if (
        not st.session_state.current_document
        and not st.session_state.upload_queue
        and not st.session_state.upload_results
    ):
        docs_data = _api("GET", "/api/documents")
        docs = docs_data.get("documents", [])
        if docs:
            # Meest recente document (al gesorteerd op processed_at DESC)
            latest = docs[0]
            if latest.get("detected_topics"):
                st.session_state.current_document = {
                    "filename": latest["filename"],
                    "document_id": latest["id"],
                    "contract_type": latest["contract_type"],
                    "detected_topics": latest["detected_topics"],
                }
                st.rerun()

    # Vraag-antwoord sectie
    if st.session_state.current_document:
        doc = st.session_state.current_document
        st.divider()
        st.subheader("💬 Vragen beantwoorden")

        # Laad volgende vraag als er geen huidige is
        if not st.session_state.current_question:
            detected_topics_full = doc.get("detected_topics", [])
            detected_topic_keys = [t.get("topic", "") for t in detected_topics_full]
            # Passages per topic zodat de backend de juiste kan opzoeken
            passages_by_topic = {
                t.get("topic", ""): t.get("passage", "")
                for t in detected_topics_full
            }

            with st.spinner("Volgende vraag ophalen..."):
                question_data = _api(
                    "POST",
                    "/api/generate-question",
                    json={
                        "document_id": doc.get("document_id", 0),
                        "contract_type": doc.get("contract_type", "anders"),
                        "detected_topics": detected_topic_keys,
                        "source_passage": "",
                        "passages_by_topic": passages_by_topic,
                        "source_file": doc.get("filename", ""),
                    },
                )
                if question_data and question_data.get("has_question"):
                    st.session_state.current_question = question_data
                else:
                    st.success(f"🎉 Alle vragen voor **{doc.get('filename', 'dit document')}** zijn beantwoord!")
                    st.session_state.current_document = None
                    st.session_state.current_question = None
                    # Controleer of er nog andere documenten zijn met openstaande vragen
                    docs_data = _api("GET", "/api/documents")
                    remaining = [
                        d for d in docs_data.get("documents", [])
                        if d["filename"] != doc.get("filename") and d.get("detected_topics")
                    ]
                    if remaining:
                        next_doc = remaining[0]
                        st.info(f"📄 Doorgaan met vragen voor **{next_doc['filename']}**...")
                        st.session_state.current_document = {
                            "filename": next_doc["filename"],
                            "document_id": next_doc["id"],
                            "contract_type": next_doc["contract_type"],
                            "detected_topics": next_doc["detected_topics"],
                        }
                        st.rerun()

        if st.session_state.current_question:
            q = st.session_state.current_question

            # Altijd bronverwijzing tonen
            source_file = q.get("source_file", "")
            source_page = q.get("source_page")
            source_passage = q.get("source_passage", "")

            if source_passage:
                page_label = f" · pagina {source_page}" if source_page else ""
                st.info(
                    f"📄 **Gevonden in:** {source_file}{page_label}\n\n"
                    f'*"{source_passage}"*'
                )
            elif source_file:
                st.caption(f"📄 Vraag gebaseerd op: **{source_file}** — onderwerp: {q.get('topic_label', '')}")
            else:
                st.caption(f"📄 Algemene kennisbankvraag — onderwerp: {q.get('topic_label', '')}")

            # Vraagkaart
            st.markdown(f"### {q.get('topic_label', 'Vraag')}")
            st.markdown(f"**{q.get('question', '')}**")

            # Antwoordveld
            answer = st.text_area(
                "Jouw antwoord:",
                placeholder="Beschrijf je beslislogica...",
                height=120,
                key=f"answer_{q.get('question_id', 'q')}",
            )

            # Actieknoppen
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 Opslaan", type="primary", use_container_width=True):
                    if not answer.strip():
                        st.warning("Vul eerst een antwoord in.")
                    else:
                        result = _api(
                            "POST",
                            "/api/save-answer",
                            json={
                                "question_id": q.get("question_id", ""),
                                "question": q.get("question", ""),
                                "answer": answer,
                                "topic": q.get("topic", ""),
                                "contract_type": doc.get("contract_type", ""),
                                "source_file": q.get("source_file", ""),
                                "source_passage": q.get("source_passage", ""),
                                "source_page": q.get("source_page"),
                            },
                        )
                        if result:
                            st.success("✅ Antwoord opgeslagen!")
                            st.session_state.current_question = None
                            _get_completion.clear()
                            st.rerun()

            with col2:
                if st.button("⏰ Straks", use_container_width=True):
                    _api(
                        "POST",
                        "/api/skip-question",
                        json={"question_id": q.get("question_id", ""), "reason": "straks"},
                    )
                    st.session_state.current_question = None
                    st.rerun()

            with col3:
                if st.button("🚫 Niet relevant", use_container_width=True):
                    _api(
                        "POST",
                        "/api/skip-question",
                        json={"question_id": q.get("question_id", ""), "reason": "niet_relevant"},
                    )
                    st.session_state.current_question = None
                    st.rerun()


# =============================================================
# TABBLAD 2 — Kennisbank
# =============================================================
with tab2:
    st.title("📚 Kennisbank")
    st.caption("Overzicht van alle vastgelegde kennis en open topics.")

    kb_data = _api("GET", "/api/knowledge-bank")
    chunks = kb_data.get("chunks", [])
    open_topics = kb_data.get("open_topics", [])

    # Metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Gedekte kennisblokken", len(chunks))
    with col2:
        st.metric("❓ Open topics", len(open_topics))

    st.divider()

    # Gedekte vs open per contracttype
    left, right = st.columns(2)

    with left:
        st.subheader("✅ Vastgelegde kennis")
        filter_type = st.selectbox(
            "Filter op contracttype",
            options=["Alle"] + sorted({c.get("contract_type", "") for c in chunks}),
            key="kb_filter",
        )
        filtered = chunks if filter_type == "Alle" else [
            c for c in chunks if c.get("contract_type") == filter_type
        ]
        for chunk in filtered:
            with st.expander(
                f"✅ {chunk.get('topic_label', chunk.get('topic', '?'))} "
                f"— {chunk.get('contract_type', '?')}"
            ):
                st.markdown(f"**V:** {chunk.get('question', '')}")
                st.markdown(f"**A:** {chunk.get('answer', '')}")
                if chunk.get("source_passage"):
                    st.caption(f"Bron: {chunk.get('source_file', '')} — *\"{chunk['source_passage'][:200]}\"*")

    with right:
        st.subheader("❓ Open topics")
        for topic in open_topics:
            st.markdown(
                f"🔴 **{topic.get('topic_label', '?')}** "
                f"({topic.get('contract_type', '?')}) "
                f"— prioriteit {topic.get('priority', '?')}"
            )

    # Volledige tabel
    if chunks:
        st.divider()
        st.subheader("📊 Alle kennisblokken")
        import pandas as pd
        df = pd.DataFrame([
            {
                "Type": c.get("contract_type", ""),
                "Onderwerp": c.get("topic_label", ""),
                "Vraag": c.get("question", "")[:80] + "..." if len(c.get("question", "")) > 80 else c.get("question", ""),
                "Bron": c.get("source_file", ""),
                "Datum": c.get("created_at", "")[:10],
            }
            for c in chunks
        ])
        st.dataframe(df, use_container_width=True)
