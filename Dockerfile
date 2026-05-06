FROM python:3.11-slim

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ui/ ui/
COPY services/ services/
COPY models/ models/
COPY repositories/ repositories/
COPY utils/ utils/
COPY security/ security/
COPY config/ config/
COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "ui/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
