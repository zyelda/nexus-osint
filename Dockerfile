FROM node:20-slim AS frontend

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY berkas ./berkas
COPY app.py ./
COPY --from=frontend /app/frontend/dist ./frontend/dist

RUN useradd --create-home --shell /usr/sbin/nologin berkas \
    && mkdir -p /data/uploads \
    && chown -R berkas:berkas /data /app

ENV FLASK_ENV=production \
    DATABASE_URL=sqlite:////data/berkas.db \
    UPLOAD_FOLDER=/data/uploads \
    HOST=0.0.0.0 \
    PORT=5000

USER berkas
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/v1/health', timeout=4)"

CMD ["gunicorn", "--workers", "2", "--threads", "8", "--timeout", "120", "--bind", "0.0.0.0:5000", "app:app"]
