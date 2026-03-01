FROM python:3.11-slim
WORKDIR /app

# Install dependencies from root requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy full project (backend needs ai/, core/, simulator/, etc.)
COPY . /app

EXPOSE 8000
CMD ["python", "main.py", "--continuous"]
