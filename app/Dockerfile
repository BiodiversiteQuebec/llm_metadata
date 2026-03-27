FROM python:3.12-slim

WORKDIR /llm_metadata

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/llm_metadata/src

COPY pyproject.toml README.md /llm_metadata/
COPY src /llm_metadata/src
COPY app/requirements.txt /llm_metadata/app/requirements.txt

RUN pip install --upgrade pip && \
    pip install -r app/requirements.txt

EXPOSE 8501

CMD ["streamlit", "run", "src/llm_metadata/app/app_eval_viewer.py", "--server.address=0.0.0.0", "--server.port=8501"]