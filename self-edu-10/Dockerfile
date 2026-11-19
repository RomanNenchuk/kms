# Альтернатива venv (не обов'язково). Не тестувалось у цьому середовищі.
FROM python:3.12-slim
WORKDIR /app
ENV HF_HOME=/hf-cache PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "src/run_experiment.py", "--with-baseline"]
