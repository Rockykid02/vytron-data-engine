FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DATABASE_PATH=/app/data/vytron.db UPLOAD_DIR=/app/data/uploads
RUN mkdir -p /app/data/uploads
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
