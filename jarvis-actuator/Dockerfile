FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ACTUATOR_HOST=0.0.0.0 \
    ACTUATOR_PORT=8090

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    python3-tk \
    tk \
    xclip \
    xsel \
    scrot \
    libx11-6 \
    libxext6 \
    libxi6 \
    libxtst6 \
    libxrandr2 \
    libsm6 \
    libice6 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY src ./src

RUN mkdir -p /app/screenshots /app/audit

EXPOSE 8090

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8090"]
