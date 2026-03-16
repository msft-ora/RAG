FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    odbc-mssqlserver17 \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
