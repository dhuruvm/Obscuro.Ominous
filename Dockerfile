FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=10000

WORKDIR /app

COPY Ominous/requirements.txt ./Ominous/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r ./Ominous/requirements.txt

COPY Ominous ./Ominous
COPY StreamLit ./StreamLit
COPY Agent.md ./Agent.md
COPY Upgrade.md ./Upgrade.md
COPY work.txt ./work.txt

EXPOSE 10000

CMD ["streamlit", "run", "StreamLit/app.py", "--server.address", "0.0.0.0", "--server.port", "10000", "--server.headless", "true"]
