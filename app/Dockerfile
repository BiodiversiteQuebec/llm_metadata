FROM python:3.12-slim

WORKDIR /llm_metadata

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/llm_metadata/src

RUN pip install --upgrade pip && \
    pip install \
        streamlit \
        pandas \
        openpyxl \
        pydantic \
        rapidfuzz \
        streamlit-lexical

EXPOSE 8501

CMD ["streamlit", "run", "app/app_eval_viewer.py", "--server.address=0.0.0.0", "--server.port=8501"]