import importlib.util
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

HAS_ONNXRUNTIME = importlib.util.find_spec("onnxruntime") is not None
HAS_TRANSFORMERS = importlib.util.find_spec("transformers") is not None

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
        --panel: #111b2e;
        --panel-2: #172742;
        --line: rgba(148, 163, 184, 0.22);
        --text: #edf4ff;
        --muted: #a7bad9;
        --brand: #7aa2ff;
        --brand-2: #6ee7c8;
        --success: #67e8a7;
        --warning: #fbbf24;
        --danger: #f87171;
        --shadow: rgba(0,0,0,0.25);
    }
    .stApp {
        background: linear-gradient(180deg, #0a1120 0%, #0f172a 100%);
        color: var(--text);
    }
    div[data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.98);
        border-right: 1px solid var(--line);
    }
    .block-container {
        padding-top: 1.1rem;
        padding-bottom: 2rem;
    }
    .title {
        font-size: 2.7rem;
        font-weight: 800;
        letter-spacing: -0.06em;
        margin: 0;
    }
    .subtitle {
        color: var(--muted);
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }
    .status-box {
        background: rgba(122, 162, 255, 0.08);
        border: 1px solid rgba(122, 162, 255, 0.28);
        border-radius: 14px;
        padding: 0.8rem 1rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(180deg, rgba(17, 27, 46, 0.95), rgba(23, 39, 66, 0.9));
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 0.9rem 1rem;
        min-height: 100px;
        box-shadow: 0 8px 22px var(--shadow);
    }
    .metric-label {
        color: var(--muted);
        font-size: 0.72rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .metric-value {
        font-size: 1.7rem;
        font-weight: 700;
        margin-top: 0.35rem;
    }
    .section-card {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 10px 28px var(--shadow);
    }
    [data-testid="stTabs"] { margin-top: 0.8rem; }
    [data-baseweb="tab-list"] { gap: 0.4rem; }
    [data-baseweb="tab"] { background: rgba(15, 23, 42, 0.8); border: 1px solid var(--line); border-radius: 12px 12px 0 0; }
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


def detect_runtime_backend() -> str:
    if HAS_ONNXRUNTIME:
        return "ONNX Runtime"
    if ensure_ollama_running():
        return "Ollama"
    return "Unavailable"


def render_status_banner() -> None:
    backend = detect_runtime_backend()
    if backend == "ONNX Runtime":
        st.markdown(
            """
            <div class="status-box"><strong>System status:</strong> ONNX Runtime is available and ready for local inference inside Streamlit.</div>
            """,
            unsafe_allow_html=True,
        )
    elif backend == "Ollama":
        st.markdown(
            """
            <div class="status-box"><strong>System status:</strong> Ollama is online and ready for local model inference.</div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.warning("No local inference backend is available yet. Install ONNX Runtime or start Ollama before using model-driven features.")


def call_model_backend(model_name: str, prompt: str, timeout: int = 120, max_tokens: int | None = None):
    """Streamlit-first model call that prefers ONNX Runtime and falls back to Ollama cleanly."""
    if model_name and model_name.lower().startswith("onnx"):
        if not HAS_ONNXRUNTIME:
            return "ONNX Runtime is not installed in this environment. Install onnxruntime to use the ONNX backend."
        try:
            from transformers import pipeline
            pipe = pipeline("text-generation", model=model_name, device=-1)
            text = pipe(prompt, max_new_tokens=max_tokens or 200, do_sample=True)[0]["generated_text"]
            return text
        except Exception as exc:
            return f"ONNX inference failed: {exc}"

    if ensure_ollama_running():
        return generate_text(model_name, prompt, timeout=timeout, max_tokens=max_tokens)

    if HAS_TRANSFORMERS:
        try:
            from transformers import pipeline
            pipe = pipeline("text-generation", model="distilgpt2", device=-1)
            text = pipe(prompt, max_new_tokens=max_tokens or 200, do_sample=True)[0]["generated_text"]
            return text
        except Exception as exc:
            return f"Local fallback model failed: {exc}"

    return "No inference backend is available. Install ONNX Runtime or start Ollama and then retry."


def build_dataset_from_topic(topic: str, selected_model: str | None = None, dataset_name: str | None = None):
    if not topic.strip():
        st.warning("Please enter a topic first.")
        return None

    with st.spinner("Researching and assembling a dataset..."):
        text, urls = research(topic.strip(), min_chars=300)

    if not text:
        st.warning("No research content was collected for this topic.")
        return None

    text_blocks = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not text_blocks:
        text_blocks = [text.strip()]

    documents = []
    for idx, block in enumerate(text_blocks[:8], 1):
        cleaned = block[:2500]
        if len(cleaned) < 120:
            continue
        documents.append({
            "keyword": f"{topic.lower().replace(' ', '_')}_{idx}",
            "topic": topic,
            "text": cleaned,
            "source_url": urls[idx - 1] if idx - 1 < len(urls) else "research-generated",
        })

    if not documents:
        st.warning("The collected text was too short to make a dataset.")
        return None

    dataset_label = dataset_name or f"{topic.strip().lower().replace(' ', '_')}_dataset"
    result = verify_and_commit(documents, dataset_label, topic, model_name=selected_model)
    st.success(f"Dataset created successfully: {result}")
    return result


def main() -> None:
    st.markdown('<div class="title">🧠 Obscuro Ominous</div>', unsafe_allow_html=True)
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

    backend_name = detect_runtime_backend()
    metric_cols = st.columns(4)
    metric_cols[0].markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Available models</div>
            <div class="metric-value">{len(models)}</div>
        </div>
    """, unsafe_allow_html=True)
    metric_cols[1].markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Selected backend</div>
            <div class="metric-value">{backend_name}</div>
        </div>
    """, unsafe_allow_html=True)
    metric_cols[2].markdown("""
        <div class="metric-card">
            <div class="metric-label">Mode</div>
            <div class="metric-value">Local</div>
        </div>
    """, unsafe_allow_html=True)
    metric_cols[3].markdown("""
        <div class="metric-card">
            <div class="metric-label">Workflow</div>
            <div class="metric-value">Web</div>
        </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs(["Research", "Chat", "Datasets", "Models"])

    with tabs[0]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Research hub")
        topic = st.text_input("Search topic", value="medical virology", placeholder="Example: virology research corpus")
        research_col, action_col = st.columns([3, 1])
        with research_col:
            search_btn = st.button("Run research", use_container_width=True)
        with action_col:
            st.caption("Quality-first source collection")

        if search_btn:
            with st.spinner("Searching across sources..."):
                try:
                    text, urls = research(topic, min_chars=300)
                except Exception as exc:
                    st.error(f"Research failed: {exc}")
                    text, urls = "", []

            if not text:
                st.warning("No usable data was found for that topic.")
            else:
                st.success(f"Collected {len(text):,} characters from {len(urls)} visited source(s).")
                st.write("Visited URLs")
                st.json(urls[:10])
                st.text_area("Research result", text[:6000], height=300)

                if st.button("Create dataset from this research", use_container_width=True):
                    selected_model = default_model if default_model else None
                    build_dataset_from_topic(topic, selected_model=selected_model)
        st.markdown('</div>', unsafe_allow_html=True)

    with tabs[1]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Local chat")
        if not models:
            st.info("No Ollama models are available yet. Pull a model in the Models tab.")
        else:
            selected_model = st.selectbox("Model", models, index=models.index(default_model) if default_model in models else 0)
            prompt = st.text_area("Prompt", value="Give me a concise summary of medical virology in 5 bullet points.", height=135)
            if st.button("Send prompt", use_container_width=True):
                with st.spinner("Generating response..."):
                    try:
                        response = call_model_backend(selected_model, prompt, timeout=120)
                    except Exception as exc:
                        st.error(f"Model call failed: {exc}")
                        response = ""
                if response:
                    st.code(response, language="text")
        st.markdown('</div>', unsafe_allow_html=True)

    with tabs[2]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Dataset tools")
        if not models:
            st.info("Add a model first before validating and committing a dataset.")
        else:
            selected_model = st.selectbox("Verification model", models, key="dataset_model")
        dataset_name = st.text_input("Dataset name", value="medical_virology_dataset")
        topic = st.text_input("Dataset topic", value="Medical virology", key="dataset_topic")
        raw_docs = st.text_area("Paste documents", value="Sample document one.\n\nSample document two.\n\nSample document three.", height=220)

        col_manual, col_auto = st.columns(2)
        with col_manual:
            if st.button("Verify and commit dataset", use_container_width=True):
                paragraphs = [p.strip() for p in raw_docs.split("\n\n") if p.strip()]
                documents = [{"keyword": f"doc_{idx + 1}", "topic": topic, "text": paragraph} for idx, paragraph in enumerate(paragraphs)]
                if not documents:
                    st.warning("Please enter at least one document before committing.")
                else:
                    with st.spinner("Verifying and saving dataset..."):
                        result = verify_and_commit(documents, dataset_name, topic, model_name=selected_model if models else None)
                    st.success(f"Dataset result: {result}")
        with col_auto:
            if st.button("Auto-generate dataset", use_container_width=True):
                build_dataset_from_topic(topic, selected_model=selected_model if models else None, dataset_name=dataset_name)
        st.markdown('</div>', unsafe_allow_html=True)

    with tabs[3]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Model management")
        model_name = st.text_input("Model name to pull", value="llama3.1")
        if st.button("Pull model", use_container_width=True):
            with st.spinner(f"Pulling {model_name}..."):
                try:
                    ok = pull_model(model_name)
                except Exception as exc:
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
