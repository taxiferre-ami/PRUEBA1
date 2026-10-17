FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend

WORKDIR /app/backend

# Esto nos muestra qué archivos hay y el contenido de main.py
RUN ls -la && echo "----- CONTENIDO DE main.py -----" && cat main.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
