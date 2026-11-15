FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 EMBED_BACKEND=bm25 STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
COPY requirements.txt requirements-reco.txt ./
RUN pip install -r requirements.txt -r requirements-reco.txt
COPY . .
EXPOSE 8000 8501
