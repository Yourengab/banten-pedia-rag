# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── OS dependencies (untuk pypdf, python-docx, dll) ───────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ──────────────────────────────────────────────────────────
# Set WORKDIR ke /code/app supaya import relatif (from config import ...) tetap jalan
WORKDIR /code

# ── Install Python dependencies ────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy app source ────────────────────────────────────────────────────────────
COPY app/ ./app/

# ── Set PYTHONPATH supaya import relatif di main.py tetap jalan ───────────────
ENV PYTHONPATH=/code/app

# ── HuggingFace Spaces wajib pakai port 7860 ──────────────────────────────────
EXPOSE 7860

# ── Run FastAPI dengan uvicorn ─────────────────────────────────────────────────
# main:app karena PYTHONPATH sudah menunjuk ke /code/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
