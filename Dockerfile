# ============================================================
# Cookie Pool — Selenium Grid + noVNC 人工登录账号池
# Multi-stage: Node builds the React SPA, Python serves it + API
# ============================================================

# ── Stage 1: Build React SPA ──
FROM node:22-alpine AS frontend-builder

WORKDIR /build

COPY frontend-react/package.json frontend-react/package-lock.json* ./
RUN npm install --include=dev

COPY frontend-react/ ./
RUN npm run build

# ── Stage 2: Python runtime ──
FROM python:3.12-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .
COPY --from=frontend-builder /build/dist /app/frontend/dist

ENV FRONTEND_DIR=/app/frontend/dist

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]