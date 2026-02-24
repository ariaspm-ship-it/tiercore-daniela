FROM python:3.11-slim
WORKDIR /app

# Copiar requerimientos e instalar
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar código
COPY backend /app

# Exponer y ejecutar
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
