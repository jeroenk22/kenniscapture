"""Streamlit kenniscapture tool — Tabblad 1: Kenniscapture | Tabblad 2: Kennisbank."""
import logging
import os

import httpx
import streamlit as st

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("kenniscapture_ui")

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Kenniscapture",
    page_icon="📝",
    layout="wide",
)


# === Hulpfuncties ===

def _api(method: str, path: str, **kwargs) -> dict:
    """Roep de FastAPI backend aan."""
    url = f"{API_BASE}{path}"
    try:
        resp = httpx.request(method, url, timeout=120.0, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        st.error("❌ Kan backend niet bereiken. Zorg dat de FastAPI server draait op poort 8000.")
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
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_session()


# === Voortgang ophalen ===
@st.cache_data(ttl=5)
def _get_completion() -> dict:
    return _api("GET", "/api/completion") or {}


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
        for uploaded_file in uploaded_files:
            with st.spinner(f"Analyseren: {uploaded_file.name}..."):
                result = _api(
                    "POST",
                    "/api/upload-document",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
                )
                if result:
                    if result.get("already_processed"):
                        st.info(f"ℹ️ {uploaded_file.name} was al eerder verwerkt.")
                    else:
                        st.success(
                            f"✅ {uploaded_file.name} geanalyseerd — "
                            f"contracttype: **{result.get('contract_type', '?')}** | "
                            f"{len(result.get('detected_topics', []))} topics gevonden"
                        )
                    st.session_state.upload_result = result
                    st.session_state.current_document = result
                    st.session_state.current_question = None

    # Vraag-antwoord sectie
    if st.session_state.current_document:
        doc = st.session_state.current_document
        st.divider()
        st.subheader("💬 Vragen beantwoorden")

        # Laad volgende vraag als er geen huidige is
        if not st.session_state.current_question:
            detected_topics = [
                t.get("topic", "") for t in doc.get("detected_topics", [])
            ]
            passage = ""
            if doc.get("detected_topics"):
                passage = doc["detected_topics"][0].get("passage", "")

            with st.spinner("Volgende vraag ophalen..."):
                question_data = _api(
                    "POST",
                    "/api/generate-question",
                    json={
                        "document_id": doc.get("document_id", 0),
                        "contract_type": doc.get("contract_type", "anders"),
                        "detected_topics": detected_topics,
                        "source_passage": passage,
                        "source_file": doc.get("filename", ""),
                    },
                )
                if question_data and question_data.get("has_question"):
                    st.session_state.current_question = question_data
                else:
                    st.success("🎉 Alle vragen voor dit document zijn beantwoord!")
                    st.session_state.current_question = None

        if st.session_state.current_question:
            q = st.session_state.current_question

            # Toon gevonden passage
            if q.get("source_passage"):
                st.info(
                    f"📄 **Gevonden in contract** ({q.get('source_file', '')}):\n\n"
                    f'*"{q["source_passage"]}"*'
                )

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
