import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OMINOUS_PATH = ROOT / "Ominous"
if str(OMINOUS_PATH) not in sys.path:
    sys.path.insert(0, str(OMINOUS_PATH))

from pipeline.dataset_store import verify_and_commit
from pipeline.model_manager import generate_text, list_local_models, pull_model, ensure_ollama_running
from pipeline.research_browser import research

st.set_page_config(
    page_title="Obscuro Ominous",
    page_icon="🧠",
    layout="wide",
)

st.markdown(
    """
    <style>
    :root {
        --bg: #0b1020;
        --panel: #121a2b;
        --panel-2: #17233b;
        --line: rgba(148, 163, 184, 0.18);
        --text: #e5eefb;
        --muted: #9fb0d0;
        --brand: #7c9cff;
        --brand-2: #73f0d1;
        --success: #5ee6a8;
        --warning: #fbbf24;
        --danger: #f87171;
    }

    .stApp {
        background: linear-gradient(180deg, #0b1020 0%, #111827 100%);
        color: var(--text);
    }

    div[data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.95);
        border-right: 1px solid var(--line);
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    .headline {
        font-size: 2.55rem;
        font-weight: 800;
        letter-spacing: -0.06em;
        margin-bottom: 0.2rem;
    }

    .subtitle {
        color: var(--muted);
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }

    .status-box {
        background: rgba(124, 156, 255, 0.08);
        border: 1px solid rgba(124, 156, 255, 0.22);
        border-radius: 16px;
        padding: 0.9rem 1rem;
        margin-bottom: 1rem;
    }

    .metric-card {
        background: linear-gradient(180deg, rgba(18, 26, 43, 0.96), rgba(23, 35, 59, 0.9));
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 0.85rem 1rem;
        height: 100%;
    }

    .metric-label {
        color: var(--muted);
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .metric-value {
        font-size: 1.7rem;
        font-weight: 700;
        color: var(--text);
        margin-top: 0.35rem;
    }

    .section-card {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
    }

    .small-note {
        color: var(--muted);
        font-size: 0.8rem;
    }

    [data-testid="stTabs"] {
        margin-top: 0.7rem;
    }

    [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }

    [data-baseweb="tab"] {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid var(--line);
        border-radius: 12px 12px 0 0;
        padding: 0.5rem 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def get_models() -> list[str]:
    try:
        return list_local_models()
    except Exception:
        return []


def pick_model(default: str | None = None) -> str | None:
    models = get_models()
    if not models:
        return None
    if default in models:
        return default
    return models[0]


def render_status_banner() -> None:
    ollama_ready = ensure_ollama_running()
    if ollama_ready:
        st.markdown(
            """
            <div class="status-box">
                <strong>System status:</strong> Ollama is online and ready for local model inference.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.warning("Ollama is not running. Start Ollama locally before using model-driven features.")


def main() -> None:
    st.markdown('<div class="headline">🧠 Obscuro Ominous</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Agentic data workflow, model tooling, and browser-based orchestration</div>', unsafe_allow_html=True)

    render_status_banner()

    with st.sidebar:
        st.header("Workspace")
        st.caption("Project root")
        st.code(str(ROOT))

        if st.button("Refresh model list", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    models = get_models()
    default_model = pick_model()

    metric_cols = st.columns(4)
    metric_cols[0].markdown(
        """
        <div class="metric-card">
            <div class="metric-label">Available models</div>
            <div class="metric-value">{}</div>
        </div>
        """.format(len(models)),
        unsafe_allow_html=True,
    )
    metric_cols[1].markdown(
        """
        <div class="metric-card">
            <div class="metric-label">Selected backend</div>
            <div class="metric-value">Ollama</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    metric_cols[2].markdown(
        """
        <div class="metric-card">
            <div class="metric-label">Mode</div>
            <div class="metric-value">Local</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    metric_cols[3].markdown(
        """
        <div class="metric-card">
            <div class="metric-label">Workflow</div>
            <div class="metric-value">Web</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["Research", "Chat", "Datasets", "Models"])

    with tabs[0]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Research hub")
        topic = st.text_input("Search topic", value="medical virology", placeholder="Example: virology research corpus")
        col1, col2 = st.columns([3, 1])
        with col1:
            search_btn = st.button("Run research", use_container_width=True)
        with col2:
            st.caption("Quality-first source collection")
        if search_btn:
            with st.spinner("Searching and collecting source material..."):
                try:
                    text, urls = research(topic, min_chars=300)
                except Exception as exc:  # pragma: no cover - UI safety
                    st.error(f"Research failed: {exc}")
                    text, urls = "", []

            if not text:
                st.warning("No usable data was found for that topic.")
            else:
                st.success(f"Collected {len(text):,} characters from {len(urls)} visited source(s).")
                st.write("Visited URLs")
                st.json(urls[:10])
                st.text_area("Research result", text[:4000], height=300)
        st.markdown('</div>', unsafe_allow_html=True)

    with tabs[1]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Local chat")
        if not models:
            st.info("No Ollama models are available yet. Pull a model in the Models tab.")
        else:
            selected_model = st.selectbox(
                "Model",
                models,
                index=models.index(default_model) if default_model in models else 0,
            )
            prompt = st.text_area(
                "Prompt",
                value="Give me a concise summary of medical virology in 5 bullet points.",
                height=135,
            )
            if st.button("Send prompt", use_container_width=True):
                with st.spinner("Generating response..."):
                    try:
                        response = generate_text(selected_model, prompt, timeout=120)
                    except Exception as exc:  # pragma: no cover - UI safety
                        st.error(f"Model call failed: {exc}")
                        response = ""
                if response:
                    st.code(response, language="text")
        st.markdown('</div>', unsafe_allow_html=True)

    with tabs[2]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Dataset commit")
        if not models:
            st.info("Add a model first before validating and committing a dataset.")
        else:
            selected_model = st.selectbox("Verification model", models, key="dataset_model")
            dataset_name = st.text_input("Dataset name", value="medical_virology_dataset")
            topic = st.text_input("Dataset topic", value="Medical virology")
            raw_docs = st.text_area(
                "Paste documents",
                value="Sample document one.\n\nSample document two.\n\nSample document three.",
                height=220,
            )
            if st.button("Verify and commit dataset", use_container_width=True):
                paragraphs = [p.strip() for p in raw_docs.split("\n\n") if p.strip()]
                documents = [
                    {"keyword": f"doc_{index + 1}", "topic": topic, "text": paragraph}
                    for index, paragraph in enumerate(paragraphs)
                ]
                if not documents:
                    st.warning("Please enter at least one document before committing.")
                else:
                    with st.spinner("Verifying and saving dataset..."):
                        result = verify_and_commit(documents, dataset_name, topic, model_name=selected_model)
                    st.success(f"Dataset result: {result}")
        st.markdown('</div>', unsafe_allow_html=True)

    with tabs[3]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Model management")
        model_name = st.text_input("Model name to pull", value="llama3.1")
        if st.button("Pull model", use_container_width=True):
            with st.spinner(f"Pulling {model_name}..."):
                try:
                    ok = pull_model(model_name)
                except Exception as exc:  # pragma: no cover - UI safety
                    st.error(f"Pull failed: {exc}")
                    ok = False
            if ok:
                st.success(f"Model {model_name} was pulled successfully.")
                st.cache_data.clear()
                st.rerun()

        st.write("Available models")
        if models:
            st.json(models)
        else:
            st.info("No models detected yet.")
        st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
