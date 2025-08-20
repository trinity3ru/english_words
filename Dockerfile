FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Установка curl для инсталляции uv
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Установка uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"

WORKDIR /app

# Устанавливаем зависимости через uv
COPY requirements.txt ./
RUN uv pip install --system -r requirements.txt

# Копируем проект
COPY . .

# Переменная по умолчанию (можно переопределить через docker run / compose)
ENV GOOGLE_SHEETS_CREDENTIALS_FILE=/app/credentials.json

# Запуск бота (через uv)
CMD ["uv", "run", "-m", "src.telegram_bot"]



