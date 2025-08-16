"""
Файл: config.py

Назначение:
    Конфигурация для AI-системы изучения английского языка.
    Содержит все настройки, API ключи и параметры системы.

Основные компоненты:
    - Настройки Telegram бота
    - Конфигурация OpenAI API
    - Параметры Google Sheets
    - Настройки базы данных
    - Временные параметры уведомлений
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# region Константы проекта
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / "database.db"
LOGS_PATH = PROJECT_ROOT / "logs"
# endregion

# region Настройки Telegram бота
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")  # ID пользователя для уведомлений
# endregion

# region Настройки OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4"  # Модель для анализа ответов
OPENAI_MAX_TOKENS = 1000
# endregion

# region Настройки Google Sheets
GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
GOOGLE_SHEETS_RANGE = "english!A:E"  # Диапазон с данными
# endregion

# region Настройки базы данных
DATABASE_NAME = "english_learning.db"
# endregion

# region Настройки уведомлений
NOTIFICATION_TIMES = ["08:00", "18:00"]  # Время отправки уведомлений
SYNC_INTERVAL_HOURS = 24  # Интервал синхронизации с Google Sheets (часы)
# endregion

# region Настройки системы баллов
MAX_SCORE = 3  # Максимальный балл для выученной фразы
PARTIAL_SCORE = 0.5  # Балл за частично правильный ответ

# Новая гибридная система баллов
SCORE_LEVELS = {
    0: "неправильно",
    0.3: "почти неправильно", 
    0.5: "частично правильно",
    0.7: "почти правильно",
    1: "правильно"
}

# Пороговые значения для нормализации score
SCORE_THRESHOLDS = {
    0: (0.0, 0.2),    # 0.0-0.2 → 0
    0.3: (0.21, 0.4), # 0.21-0.4 → 0.3
    0.5: (0.41, 0.6), # 0.41-0.6 → 0.5
    0.7: (0.61, 0.8), # 0.61-0.8 → 0.7
    1: (0.81, 1.0)    # 0.81-1.0 → 1
}
# endregion

# region Настройки логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# endregion

def validate_config():
    """
    Проверяет корректность конфигурации.
    
    Returns:
        bool: True если конфигурация корректна
        
    Raises:
        ValueError: Если отсутствуют обязательные параметры
    """
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_USER_ID", 
        "OPENAI_API_KEY",
        "GOOGLE_SHEETS_CREDENTIALS_FILE",
        "GOOGLE_SHEETS_SPREADSHEET_ID"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    
    return True
