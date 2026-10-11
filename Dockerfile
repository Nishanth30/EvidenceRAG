FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 MPLCONFIGDIR=/tmp/matplotlib HF_HOME=/app/data/models
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
COPY app app
COPY frontend frontend
COPY .streamlit .streamlit
COPY evaluation evaluation
COPY sample_documents sample_documents
COPY scripts scripts
RUN useradd --create-home appuser && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000 8501
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
