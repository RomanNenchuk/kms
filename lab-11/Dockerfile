FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp \
    HF_HOME=/models \
    TOKENIZERS_PARALLELISM=false

# кеш моделей HuggingFace доступний будь-якому uid (контейнер працює від твого uid)
RUN mkdir -p /models && chmod 777 /models

WORKDIR /app
COPY requirements.txt .
# CPU-версія torch (без CUDA): образ значно менший
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt

EXPOSE 8000
CMD ["sleep", "infinity"]
