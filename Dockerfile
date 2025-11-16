FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Устанавливаем зависимости (этот слой кэшируется если requirements.txt не изменился)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Копируем проект (этот слой пересобирается только при изменении кода)
COPY . .

# Переменная по умолчанию (можно переопределить через docker run / compose)
ENV GOOGLE_SHEETS_CREDENTIALS_FILE=/app/credentials.json

# Запуск бота
CMD ["python", "-m", "src.telegram_bot"]



