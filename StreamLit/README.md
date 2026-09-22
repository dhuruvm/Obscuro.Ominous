# StreamLit UI

This folder contains the browser-first interface for the Obscuro Ominous toolkit.

## Run locally

From the repository root:

```bash
python -m pip install -r Ominous/requirements.txt
streamlit run StreamLit/app.py
```

The app is designed to run as a Streamlit-only experience. It prefers ONNX Runtime for local inference and falls back to Ollama automatically when available. The browser workflow covers research, dataset generation, verification, and model usage without requiring the terminal-only CLI path.

