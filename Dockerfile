FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY pycore ./pycore
COPY backend ./backend
COPY docs/tag-taxonomy.json ./docs/tag-taxonomy.json
COPY --from=frontend /app/frontend/dist ./frontend/dist
WORKDIR /app/backend
ENV PYTHONPATH=/app
EXPOSE 8099
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8099", "--proxy-headers", "--forwarded-allow-ips", "*"]
