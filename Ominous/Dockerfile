FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY pyproject.toml requirements.txt setup.py ./
COPY cli.py reader.py generate_dummy.py ./
COPY pipeline ./pipeline
COPY io_module ./io_module
COPY workers ./workers
COPY datasets ./datasets

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

ENTRYPOINT ["python", "cli.py"]
CMD []
