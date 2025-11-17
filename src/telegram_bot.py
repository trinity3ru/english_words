"""
Файл: telegram_bot.py

Назначение:
    Основной модуль Telegram бота для изучения английских фраз с AI-анализом ответов.
    Обеспечивает взаимодействие с пользователем, получение фраз из базы данных,
    анализ ответов через AI и ведение статистики прогресса.
    Код написан для aiogram версии 3.x.

Основные компоненты:

Классы:
    - EnglishLearningBot: Основной класс бота с асинхронными обработчиками команд и сообщений.

Функции:
    - start_command(message): Асинхронный обработчик команды /start с приветствием.
    - help_command(message): Асинхронный обработчик команды /help с описанием функций.
    - phrase_command(message): Асинхронный обработчик команды /phrase для получения новой фразы.
    - reverse_command(message): Асинхронный обработчик команды /reverse для получения русской фразы.
    - sync_command(message): Асинхронный обработчик команды /sync для синхронизации с Google Sheets.
    - auto_command(message): Асинхронный обработчик команды /auto для управления автоматической отправкой.
    - handle_answer(message): Асинхронный обработчик ответов пользователя с AI-анализом.
    - get_random_phrase(): Получает случайную фразу из базы данных.
    - save_user_answer(phrase_id, user_answer, ai_score): Сохраняет ответ пользователя и оценку AI.
    - auto_send_phrase(user_id): Автоматически отправляет случайную фразу пользователю.
    - auto_sync_google_sheets(): Автоматически синхронизирует фразы с Google Sheets.
    - stats_command(message): Показывает статистику изучения фраз.
    - start_auto_send_task(bot): Запускает фоновую задачу автоматических задач.
    - _get_score_emoji(score): Возвращает эмодзи в зависимости от оценки.

Константы:
    - BOT_COMMANDS: Список доступных команд бота.
    - AUTO_SEND_INTERVAL_HOURS: Интервал автоматической отправки в часах (20).
    - AUTO_SEND_ENABLED: Флаг включения автоматической отправки по умолчанию.
    - AUTO_SYNC_INTERVAL_HOURS: Интервал автоматической синхронизации в часах (6).
    - AUTO_SYNC_ENABLED: Флаг включения автоматической синхронизации по умолчанию.
    - WELCOME_MESSAGE: Приветственное сообщение для новых пользователей.
    - HELP_MESSAGE: Справочное сообщение с описанием функций.

Зависимости:
    - aiogram>=3.0.0
    - src.database
    - src.ai_analysis
    - config.config
    - logging
    - asyncio
"""

# region Импорты
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Set
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
from src.database import DatabaseManager
from src.ai_analysis import AIAnalyzer
from src.google_sync import GoogleSheetsSync
from config.config import TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, GOOGLE_SHEETS_CREDENTIALS_FILE, GOOGLE_SHEETS_SPREADSHEET_ID

# Отладочная информация
print(f"[DEBUG] GOOGLE_SHEETS_CREDENTIALS_FILE: {GOOGLE_SHEETS_CREDENTIALS_FILE}")
print(f"[DEBUG] GOOGLE_SHEETS_SPREADSHEET_ID: {GOOGLE_SHEETS_SPREADSHEET_ID}")
print(f"[DEBUG] TELEGRAM_BOT_TOKEN: {TELEGRAM_BOT_TOKEN}")
print(f"[DEBUG] OPENAI_API_KEY: {OPENAI_API_KEY}")
# endregion

# region Константы
BOT_COMMANDS = [
    ("start", "Начать работу с ботом"),
    ("help", "Показать справку"),
    ("phrase", "Получить новую фразу для изучения"),
    ("reverse", "Получить русскую фразу для перевода на английский"),
    ("sync", "Синхронизировать фразы с Google Sheets"),
    ("auto", "Включить/выключить автоматическую отправку фраз"),
    ("stats", "Показать статистику изучения"),
    ("interval", "Изменить интервал авто-отправки (часы)")
]

# Настройки автоматической отправки
AUTO_SEND_INTERVAL_HOURS = 20  # Интервал в часах
AUTO_SEND_ENABLED = True  # По умолчанию включено

# Настройки автоматической синхронизации
AUTO_SYNC_INTERVAL_HOURS = 6  # Интервал синхронизации с Google Sheets
AUTO_SYNC_ENABLED = True  # По умолчанию включено

WELCOME_MESSAGE = """
🎓 Добро пожаловать в AI-систему изучения английского языка!

Я помогу вам изучать английские фразы с помощью искусственного интеллекта.

📚 Доступные команды:
/start - Начать работу
/help - Показать справку  
/phrase - Получить новую фразу

Начните с команды /phrase, чтобы получить первую фразу для изучения!
"""

HELP_MESSAGE = """
🤖 Справка по командам бота:

/start - Начать работу с ботом
/help - Показать эту справку
/phrase - Получить новую английскую фразу
/reverse - Получить русскую фразу для перевода на английский
/sync - Синхронизировать фразы с Google Sheets
/auto - Включить/выключить автоматическую отправку фраз
/interval - Показать или задать интервал авто-отправки (в часах)

💡 Как это работает:
1. Используйте /sync для загрузки фраз из Google Sheets
2. Используйте /phrase для получения английской фразы
3. Используйте /reverse для получения русской фразы
4. Отправьте свой перевод или ответ
5. AI проанализирует ваш ответ и даст оценку
6. Ваш прогресс сохраняется в базе данных

🔄 Автоматические функции:
• **Отправка фраз:** каждые 20 часов бот случайно отправляет фразу
• **Синхронизация:** каждые 6 часов бот обновляет фразы из Google Sheets
• **Уведомления:** бот сообщает о новых фразах автоматически
• **Чередование:** английские и русские фразы для разнообразия

📊 **Команды управления:**
• `/stats` - показать статистику изучения
• `/sync` - обновить фразы из Google Sheets
• `/auto` - включить/выключить автоматическую отправку

🎯 Цель: выучить как можно больше фраз и улучшить свой английский!
"""
# endregion

# region Класс EnglishLearningBot
class EnglishLearningBot:
    """
    Основной класс Telegram бота для изучения английского языка.
    
    Обеспечивает:
    - Обработку команд пользователя
    - Получение фраз из базы данных
    - AI-анализ ответов пользователя
    - Сохранение прогресса и статистики
    """
    
    def __init__(self):
        """Инициализирует бота и его компоненты."""
        self.logger = logging.getLogger(__name__)
        self.logger.info("[START_FUNCTION][__init__] Инициализация EnglishLearningBot")
        
        # Инициализируем компоненты
        self.database = DatabaseManager()
        self.ai_analyzer = AIAnalyzer()
        
        # Словарь для хранения ожидаемых ответов пользователей (кэш)
        # user_id -> {phrase_id, english_phrase, russian_translation, exercise_type}
        # exercise_type: 'translate_to_russian' или 'translate_to_english'
        # Состояние также сохраняется в БД для восстановления после перезапуска
        self.expected_answers = {}
        
        # Загружаем ожидаемые ответы из БД при старте
        self._load_expected_answers_from_db()
        
        # Настройки автоматической отправки
        self.auto_send_enabled = AUTO_SEND_ENABLED
        self.auto_send_interval = timedelta(hours=AUTO_SEND_INTERVAL_HOURS)
        self.last_auto_send = {}  # user_id -> datetime последней отправки
        self.auto_send_task = None  # Задача автоматической отправки
        
        # Настройки автоматической синхронизации
        self.auto_sync_enabled = AUTO_SYNC_ENABLED
        self.auto_sync_interval = timedelta(hours=AUTO_SYNC_INTERVAL_HOURS)
        self.last_auto_sync = None  # datetime последней синхронизации
        self.auto_sync_task = None  # Задача автоматической синхронизации
        
        self.logger.info("[END_FUNCTION][__init__] EnglishLearningBot инициализирован")
    
    # region FUNCTION _load_expected_answers_from_db
    def _load_expected_answers_from_db(self) -> None:
        """Загружает ожидаемые ответы из БД при старте бота."""
        self.logger.info("[START_FUNCTION][_load_expected_answers_from_db] Загрузка ожидаемых ответов из БД")
        try:
            # Загружаем все ожидаемые ответы из БД
            with sqlite3.connect(self.database.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, phrase_id, english_phrase, russian_translation, exercise_type FROM user_expected_answers")
                rows = cursor.fetchall()
                
                for row in rows:
                    user_id, phrase_id, english_phrase, russian_translation, exercise_type = row
                    self.expected_answers[user_id] = {
                        'phrase_id': phrase_id,
                        'english_phrase': english_phrase,
                        'russian_translation': russian_translation,
                        'exercise_type': exercise_type
                    }
                
                self.logger.info(f"[END_FUNCTION][_load_expected_answers_from_db] Загружено {len(self.expected_answers)} ожидаемых ответов")
        except Exception as e:
            self.logger.error(f"[ERROR][_load_expected_answers_from_db] Ошибка загрузки: {e}")
    # endregion FUNCTION _load_expected_answers_from_db
    
    # endregion FUNCTION __init__
    
    # region FUNCTION start_command
    # CONTRACT
    # Args:
    #   - message: Сообщение от пользователя с командой /start.
    # Returns:
    #   - None
    # Side Effects:
    #   - Отправляет приветственное сообщение пользователю.
    # Raises:
    #   - None
    # Tests:
    #   - message с командой /start: должен отправить WELCOME_MESSAGE.
    
    async def start_command(self, message: Message) -> None:
        """Обрабатывает команду /start - приветствие пользователя."""
        self.logger.info(f"[START_FUNCTION][start_command] Команда /start от пользователя {message.from_user.id}")
        
        await message.answer(WELCOME_MESSAGE, parse_mode='Markdown')
        
        self.logger.info(f"[END_FUNCTION][start_command] Приветствие отправлено пользователю {message.from_user.id}")
    
    # endregion FUNCTION start_command
    
    # region FUNCTION help_command
    # CONTRACT
    # Args:
    #   - message: Сообщение от пользователя с командой /help.
    # Returns:
    #   - None
    # Side Effects:
    #   - Отправляет справочное сообщение пользователю.
    # Raises:
    #   - None
    # Tests:
    #   - message с командой /help: должен отправить HELP_MESSAGE.
    
    async def help_command(self, message: Message) -> None:
        """Обрабатывает команду /help - показывает справку по командам."""
        self.logger.info(f"[START_FUNCTION][help_command] Команда /help от пользователя {message.from_user.id}")
        
        await message.answer(HELP_MESSAGE, parse_mode='Markdown')
        
        self.logger.info(f"[END_FUNCTION][help_command] Справка отправлена пользователю {message.from_user.id}")
    
    # endregion FUNCTION help_command
    
    # region FUNCTION phrase_command
    # CONTRACT
    # Args:
    #   - message: Сообщение от пользователя с командой /phrase.
    # Returns:
    #   - None
    # Side Effects:
    #   - Получает случайную фразу из базы данных.
    #   - Сохраняет ожидаемый ответ в self.expected_answers.
    #   - Отправляет фразу пользователю для изучения.
    # Raises:
    #   - None
    # Tests:
    #   - message с командой /phrase: должен получить фразу и отправить её пользователю.
    
    async def phrase_command(self, message: Message) -> None:
        """Обрабатывает команду /phrase - получает новую фразу для изучения."""
        user_id = message.from_user.id
        self.logger.info(f"[START_FUNCTION][phrase_command] Команда /phrase от пользователя {user_id}")
        
        # Получаем случайную фразу из базы данных
        phrase_data = self.get_random_phrase()
        
        if not phrase_data:
            await message.answer("❌ К сожалению, не удалось получить фразу. Попробуйте позже.")
            self.logger.warning(f"[WARNING][phrase_command] Не удалось получить фразу для пользователя {user_id}")
            return
        
        phrase_id, english_phrase, russian_translation = phrase_data
        
        # Сохраняем ожидаемый ответ
        self.expected_answers[user_id] = {
            'phrase_id': phrase_id,
            'english_phrase': english_phrase,
            'russian_translation': russian_translation,
            'exercise_type': 'translate_to_russian'
        }
        # Сохраняем в БД для восстановления после перезапуска
        try:
            self.database.save_expected_answer(
                user_id=user_id,
                phrase_id=phrase_id,
                english_phrase=english_phrase,
                russian_translation=russian_translation,
                exercise_type='translate_to_russian'
            )
        except Exception as e:
            self.logger.error(f"[ERROR][phrase_command] Ошибка сохранения ожидаемого ответа в БД: {e}")
        
        # Формируем сообщение с фразой
        message_text = f"🇬🇧 **Новая фраза для изучения:**\n\n{english_phrase}\n\n💡 **Переведите эту фразу на русский язык**"
        
        await message.answer(message_text)
        
        self.logger.info(f"[END_FUNCTION][phrase_command] Фраза {phrase_id} отправлена пользователю {user_id}")
    
    # endregion FUNCTION phrase_command
    
    # region FUNCTION reverse_command
    # CONTRACT
    # Args:
    #   - message: Сообщение от пользователя с командой /reverse.
    # Returns:
    #   - None
    # Side Effects:
    #   - Получает случайную фразу из базы данных.
    #   - Сохраняет ожидаемый ответ в self.expected_answers.
    #   - Отправляет русскую фразу пользователю для перевода на английский.
    # Raises:
    #   - None
    # Tests:
    #   - message с командой /reverse: должен получить фразу и отправить её пользователю.
    
    async def reverse_command(self, message: Message) -> None:
        """Обрабатывает команду /reverse - получает русскую фразу для перевода на английский."""
        user_id = message.from_user.id
        self.logger.info(f"[START_FUNCTION][reverse_command] Команда /reverse от пользователя {user_id}")
        
        # Получаем случайную фразу из базы данных
        phrase_data = self.get_random_phrase()
        
        if not phrase_data:
            await message.answer("❌ К сожалению, не удалось получить фразу. Попробуйте позже.")
            self.logger.warning(f"[WARNING][reverse_command] Не удалось получить фразу для пользователя {user_id}")
            return
        
        phrase_id, english_phrase, russian_translation = phrase_data
        
        # Сохраняем ожидаемый ответ (обратное упражнение)
        self.expected_answers[user_id] = {
            'phrase_id': phrase_id,
            'english_phrase': english_phrase,
            'russian_translation': russian_translation,
            'exercise_type': 'translate_to_english'
        }
        # Сохраняем в БД для восстановления после перезапуска
        try:
            self.database.save_expected_answer(
                user_id=user_id,
                phrase_id=phrase_id,
                english_phrase=english_phrase,
                russian_translation=russian_translation,
                exercise_type='translate_to_english'
            )
        except Exception as e:
            self.logger.error(f"[ERROR][reverse_command] Ошибка сохранения ожидаемого ответа в БД: {e}")
        
        # Формируем сообщение с русской фразой
        message_text = f"🇷🇺 **Переведите на английский язык:**\n\n{russian_translation}\n\n💡 **Напишите перевод на английском языке**"
        
        await message.answer(message_text)
        
        self.logger.info(f"[END_FUNCTION][reverse_command] Русская фраза {phrase_id} отправлена пользователю {user_id}")
    
    # endregion FUNCTION reverse_command
    
    # region FUNCTION sync_command
    # CONTRACT
    # Args:
    #   - message: Сообщение от пользователя с командой /sync.
    # Returns:
    #   - None
    # Side Effects:
    #   - Синхронизирует фразы с Google Sheets.
    #   - Обновляет базу данных.
    # Raises:
    #   - None
    # Tests:
    #   - message с командой /sync: должен выполнить синхронизацию.
    
    async def sync_command(self, message: Message) -> None:
        """Обрабатывает команду /sync - синхронизирует фразы с Google Sheets."""
        user_id = message.from_user.id
        self.logger.info(f"[START_FUNCTION][sync_command] Команда /sync от пользователя {user_id}")
        
        try:
            # Отправляем сообщение о начале синхронизации
            await message.answer("🔄 Начинаю синхронизацию с Google Sheets...")
            
            # Проверяем наличие необходимых настроек
            if not GOOGLE_SHEETS_CREDENTIALS_FILE or not GOOGLE_SHEETS_SPREADSHEET_ID:
                await message.answer("❌ Ошибка: не настроена интеграция с Google Sheets")
                self.logger.error("[ERROR][sync_command] Отсутствуют настройки Google Sheets")
                return
            
            # Создаем синхронизатор
            sync = GoogleSheetsSync(
                credentials_path=GOOGLE_SHEETS_CREDENTIALS_FILE,
                spreadsheet_id=GOOGLE_SHEETS_SPREADSHEET_ID,
                database_manager=self.database
            )
            
            # Получаем статус до синхронизации
            status_before = sync.get_sync_status()
            
            # Выполняем синхронизацию
            result = sync.full_sync()
            
            # Получаем статус после синхронизации
            status_after = sync.get_sync_status()
            
            # Формируем отчет
            report = f"""✅ **Синхронизация завершена!**

📊 **Результаты:**
• Добавлено новых фраз: {result['added']}
• Обновлено фраз: {result['updated']}
• Ошибок: {result['errors']}
• Всего обработано: {result['total']}

📈 **Статус:**
• Фраз в Google Sheets: {status_after['sheets_count']}
• Фраз в базе данных: {status_after['database_count']}
• Синхронизация: {status_after['sync_percentage']}%

🎯 Теперь используйте /phrase для получения фраз!"""
            
            await message.answer(report, parse_mode='Markdown')
            
            self.logger.info(f"[END_FUNCTION][sync_command] Синхронизация завершена для пользователя {user_id}")
            
        except Exception as e:
            error_msg = f"❌ Ошибка синхронизации: {str(e)}"
            await message.answer(error_msg)
            self.logger.error(f"[ERROR][sync_command] Ошибка синхронизации для пользователя {user_id}: {e}")
    
    # endregion FUNCTION sync_command
    
    # region FUNCTION auto_command
    # CONTRACT
    # Args:
    #   - message: Сообщение от пользователя с командой /auto.
    # Returns:
    #   - None
    # Side Effects:
    #   - Переключает состояние автоматической отправки для пользователя.
    # Raises:
    #   - None
    # Tests:
    #   - message с командой /auto: должен переключить состояние и отправить подтверждение.
    
    async def auto_command(self, message: Message) -> None:
        """Обрабатывает команду /auto - переключает автоматическую отправку фраз."""
        user_id = message.from_user.id
        self.logger.info(f"[START_FUNCTION][auto_command] Команда /auto от пользователя {user_id}")
        
        # Переключаем состояние для пользователя
        if user_id not in self.last_auto_send:
            # Первый раз - включаем автоматическую отправку
            self.last_auto_send[user_id] = datetime.now()
            self.auto_send_enabled = True
            status = "включена"
            next_send = datetime.now() + self.auto_send_interval
        else:
            # Переключаем состояние
            if self.auto_send_enabled:
                self.auto_send_enabled = False
                status = "отключена"
                next_send = "не планируется"
            else:
                self.auto_send_enabled = True
                self.last_auto_send[user_id] = datetime.now()
                status = "включена"
                next_send = datetime.now() + self.auto_send_interval
        
        # Формируем сообщение
        if self.auto_send_enabled:
            current_hours = int(self.auto_send_interval.total_seconds() // 3600)
            message_text = f"""🔄 **Автоматическая отправка {status}!**

⏰ **Интервал:** каждые {current_hours} часов
📅 **Следующая отправка:** {next_send.strftime('%d.%m.%Y в %H:%M') if isinstance(next_send, datetime) else next_send}

💡 Бот будет случайно отправлять фразы для регулярной практики.
🎯 Используйте /auto снова, чтобы отключить."""
        else:
            message_text = f"""🔄 **Автоматическая отправка {status}!**

💡 Бот больше не будет автоматически отправлять фразы.
🎯 Используйте /auto снова, чтобы включить."""
        
        await message.answer(message_text, parse_mode='Markdown')
        
        self.logger.info(f"[END_FUNCTION][auto_command] Автоматическая отправка {status} для пользователя {user_id}")
    
    # endregion FUNCTION auto_command

    # region FUNCTION interval_command
    # CONTRACT
    # Args:
    #   - message: Сообщение от пользователя с командой /interval [часы?].
    # Returns:
    #   - None
    # Side Effects:
    #   - Обновляет self.auto_send_interval и сообщает текущее/новое значение.
    # Raises:
    #   - None
    # Tests:
    #   - "/interval": показать текущий интервал.
    #   - "/interval 12": установить 12 часов, показать следующую отправку.
    #   - "/interval 0"/"/interval abc": вернуть сообщение об ошибке.

    async def interval_command(self, message: Message) -> None:
        """Показывает или устанавливает интервал авто-отправки в часах."""
        self.logger.info(f"[START_FUNCTION][interval_command] Команда /interval от пользователя {message.from_user.id}")

        text = message.text.strip() if message.text else "/interval"
        parts = text.split(maxsplit=1)

        if len(parts) == 1:
            # Показать текущее значение
            current_hours = int(self.auto_send_interval.total_seconds() // 3600)
            await message.answer(
                f"⏰ Текущий интервал авто-отправки: {current_hours} часов.\n"
                f"Изменить: используйте `/interval <часы>`, например `/interval 12`.",
                parse_mode='Markdown'
            )
            self.logger.info(f"[END_FUNCTION][interval_command] Показан текущий интервал: {current_hours} ч")
            return

        # Установка нового значения
        arg = parts[1].strip()
        try:
            new_hours = int(arg)
        except ValueError:
            await message.answer("❌ Неверный формат. Укажите целое число часов, например: `/interval 12`.", parse_mode='Markdown')
            self.logger.warning(f"[WARNING][interval_command] Невалидный аргумент: {arg}")
            return

        if new_hours < 1 or new_hours > 168:
            await message.answer("❌ Интервал должен быть от 1 до 168 часов.", parse_mode='Markdown')
            self.logger.warning(f"[WARNING][interval_command] Часы вне диапазона: {new_hours}")
            return

        # Применяем новое значение
        self.auto_send_interval = timedelta(hours=new_hours)

        # Определяем следующую отправку
        user_id = message.from_user.id
        if self.auto_send_enabled:
            if user_id not in self.last_auto_send:
                next_send_text = "включите авто-отправку командой /auto"
            else:
                next_send_time = self.last_auto_send[user_id] + self.auto_send_interval
                next_send_text = next_send_time.strftime('%d.%m.%Y в %H:%M')
        else:
            next_send_text = "авто-отправка отключена (/auto)"

        await message.answer(
            f"✅ Интервал авто-отправки установлен: {new_hours} часов.\n"
            f"📅 Следующая отправка: {next_send_text}",
            parse_mode='Markdown'
        )

        self.logger.info(f"[END_FUNCTION][interval_command] Установлен интервал: {new_hours} ч")
    # endregion FUNCTION interval_command
    
    # region FUNCTION stats_command
    # CONTRACT
    # Args:
    #   - message: Сообщение от пользователя
    # Returns:
    #   - None
    # Side Effects:
    #   - Отправляет статистику изучения пользователю
    # Raises:
    #   - None
    # Tests:
    #   - Команда /stats: должен показать статистику изучения
    
    async def stats_command(self, message: Message) -> None:
        """Обрабатывает команду /stats - показывает статистику изучения."""
        user_id = message.from_user.id
        self.logger.info(f"[START_FUNCTION][stats_command] Команда /stats от пользователя {user_id}")
        
        try:
            # Получаем статистику изученных фраз
            stats = self.database.get_learned_phrases_stats()
            
            # Формируем сообщение со статистикой
            stats_message = f"""📊 **Статистика изучения английского языка**

📚 **Общая информация:**
• Всего фраз в базе: {stats['total_phrases']}
• Изучено фраз: {stats['learned_phrases']} ✅
• Активно изучается: {stats['active_phrases']} 📖

📈 **Прогресс:**
• Процент изучения: **{stats['learning_percentage']}%**
• Средний балл изученных: {stats['avg_learned_score']}

🎯 **Цель:** достичь 100% изучения всех фраз!

💡 **Совет:** используйте команды /phrase и /reverse для регулярной практики."""
            
            await message.answer(stats_message, parse_mode='Markdown')
            
            self.logger.info(f"[END_FUNCTION][stats_command] Статистика отправлена пользователю {user_id}")
            
        except Exception as e:
            error_message = "❌ Ошибка при получении статистики. Попробуйте позже."
            await message.answer(error_message)
            self.logger.error(f"[ERROR][stats_command] Ошибка получения статистики: {e}")
    
    # endregion FUNCTION stats_command
    
    # region FUNCTION handle_answer
    # CONTRACT
    # Args:
    #   - message: Сообщение от пользователя с ответом на фразу.
    # Returns:
    #   - None
    # Side Effects:
    #   - Анализирует ответ пользователя через AI.
    #   - Сохраняет результат в базу данных.
    #   - Отправляет фидбек пользователю.
    # Raises:
    #   - None
    # Tests:
    #   - message с ответом: должен проанализировать через AI и отправить фидбек.
    
    async def handle_answer(self, message: Message) -> None:
        """Обрабатывает ответ пользователя на фразу."""
        user_id = message.from_user.id
        user_answer = message.text
        
        self.logger.info(f"[START_FUNCTION][handle_answer] Ответ от пользователя {user_id}: {user_answer}")
        
        # Проверяем, есть ли ожидаемый ответ для этого пользователя
        # Сначала проверяем кэш, если нет - загружаем из БД
        if user_id not in self.expected_answers:
            expected_data = self.database.get_expected_answer(user_id)
            if expected_data:
                self.expected_answers[user_id] = expected_data
            else:
                await message.answer("💡 Сначала получите фразу командой /phrase или /reverse!")
                self.logger.info(f"[INFO][handle_answer] Пользователь {user_id} пытается ответить без получения фразы")
                return
        
        # Получаем данные о фразе
        expected_data = self.expected_answers[user_id]
        phrase_id = expected_data['phrase_id']
        english_phrase = expected_data['english_phrase']
        russian_translation = expected_data['russian_translation']
        exercise_type = expected_data.get('exercise_type', 'translate_to_russian')
        
        # Анализируем ответ через AI
        try:
            if exercise_type == 'translate_to_english':
                # Обратное упражнение: русский -> английский
                ai_score = self.ai_analyzer.analyze_reverse_answer(
                    russian_phrase=russian_translation,
                    english_translation=english_phrase,
                    user_answer=user_answer
                )
            else:
                # Обычное упражнение: английский -> русский
                ai_score = self.ai_analyzer.analyze_answer(
                    english_phrase=english_phrase,
                    russian_translation=russian_translation,
                    user_answer=user_answer
                )
            
            # Сохраняем ответ пользователя
            self.save_user_answer(phrase_id, user_answer, ai_score['score'])
            
            # Формируем сообщение с результатом
            score_emoji = self._get_score_emoji(ai_score['score'])
            score_feedback = ai_score.get('feedback', 'Комментарий не предоставлен')

            # Правильный вариант (если ответ не идеален)
            correct_variant = None
            if ai_score.get('score', 0.0) < 1.0:
                if exercise_type == 'translate_to_english':
                    correct_variant = english_phrase
                else:
                    correct_variant = russian_translation

            # Детальный анализ ошибок
            error_analysis = ai_score.get('error_analysis', {})
            meaning_errors = error_analysis.get('meaning_errors', [])
            lexical_errors = error_analysis.get('lexical_errors', [])
            grammar_errors = error_analysis.get('grammar_errors', [])
            punctuation_errors = error_analysis.get('punctuation_errors', [])
            style_differences = error_analysis.get('style_differences', [])

            # Доп. материалы от AI
            alternatives = ai_score.get('alternatives', [])[:3]
            usage_examples = ai_score.get('usage_examples', [])[:2]
            mini_dialogue = ai_score.get('mini_dialogue', [])[:4]
            note = ai_score.get('note', '').strip()
            suggestions = ai_score.get('suggestions', [])
            
            # Определяем команду для следующего упражнения
            next_command = "/reverse" if exercise_type == 'translate_to_russian' else "/phrase"
            next_command_text = "русской фразы" if exercise_type == 'translate_to_russian' else "английской фразы"
            
            # Сборка сообщения
            parts = []
            parts.append(f"{score_emoji} **Результат анализа:**\n\n📝 **Ваш ответ:** {user_answer}\n🎯 **Оценка:** {ai_score['score']:.1f}/1.0\n💡 **Комментарий:** {score_feedback}")
            
            # Детальный анализ ошибок (только если есть ошибки)
            if any([meaning_errors, lexical_errors, grammar_errors, punctuation_errors, style_differences]):
                parts.append("🔍 **Детальный анализ ошибок:**")
                
                if meaning_errors:
                    meaning_block = "\n".join([f"- {e}" for e in meaning_errors])
                    parts.append(f"🎯 **Смысловые ошибки:**\n{meaning_block}")
                
                if lexical_errors:
                    lexical_block = "\n".join([f"- {e}" for e in lexical_errors])
                    parts.append(f"📚 **Лексические ошибки:**\n{lexical_block}")
                
                if grammar_errors:
                    grammar_block = "\n".join([f"- {e}" for e in grammar_errors])
                    parts.append(f"📝 **Грамматические ошибки:**\n{grammar_block}")
                
                if punctuation_errors:
                    punct_block = "\n".join([f"- {e}" for e in punctuation_errors])
                    parts.append(f"✏️ **Пунктуационные ошибки:**\n{punct_block}")
                
                if style_differences:
                    style_block = "\n".join([f"- {e}" for e in style_differences])
                    parts.append(f"🎨 **Стилистические отличия:**\n{style_block}")
            
            if correct_variant:
                parts.append(f"✅ **Правильный вариант:** {correct_variant}")
            if alternatives:
                alt_block = "\n".join([f"- {a}" for a in alternatives])
                parts.append(f"🔄 **Как ещё можно сказать:**\n{alt_block}")
            if usage_examples:
                ex_block = "\n".join([f"- {e}" for e in usage_examples])
                parts.append(f"✍️ **Примеры использования:**\n{ex_block}")
            if mini_dialogue:
                dlg_block = "\n".join([f"- {d}" for d in mini_dialogue])
                parts.append(f"🗣 **Мини-диалог:**\n{dlg_block}")
            if note:
                parts.append(f"ℹ️ **Заметка:** {note}")
            if suggestions:
                sug_block = "\n".join([f"- {s}" for s in suggestions])
                parts.append(f"🧩 **Подсказки:**\n{sug_block}")
            parts.append(f"\n🔁 Используйте {next_command} для получения новой {next_command_text}!")
            result_message = "\n\n".join(parts)
            
            await message.answer(result_message, parse_mode='Markdown')
            
            # Очищаем ожидаемый ответ
            del self.expected_answers[user_id]
            
            self.logger.info(f"[END_FUNCTION][handle_answer] Ответ пользователя {user_id} проанализирован, оценка: {ai_score}")
            
        except Exception as e:
            self.logger.error(f"[ERROR][handle_answer] Ошибка при анализе ответа пользователя {user_id}: {e}")
            await message.answer("❌ Произошла ошибка при анализе вашего ответа. Попробуйте еще раз.")
    
    # endregion FUNCTION handle_answer
    
    # region FUNCTION get_random_phrase
    # CONTRACT
    # Args:
    #   - None
    # Returns:
    #   - Optional[Tuple[int, str, str]]: (phrase_id, english_phrase, russian_translation) или None.
    # Side Effects:
    #   - Выполняет запрос к базе данных.
    # Raises:
    #   - None
    # Tests:
    #   - База данных доступна: должен вернуть кортеж с данными фразы.
    #   - База данных недоступна: должен вернуть None.
    
    def get_random_phrase(self) -> Optional[Tuple[int, str, str]]:
        """
        Получает случайную фразу из базы данных с учетом приоритета новых фраз.
        
        Новые фразы (недавно добавленные) имеют больший приоритет,
        но старые фразы тоже показываются для повторения.
        """
        self.logger.info("[START_FUNCTION][get_random_phrase] Получение взвешенной случайной фразы из базы данных")
        
        try:
            # Используем взвешенный выбор с приоритетом новых фраз
            # user_id = 1 (для одного пользователя)
            user_id = 1
            
            # Пробуем использовать взвешенный выбор
            result = self.database.get_weighted_random_phrase(
                user_id=user_id,
                new_phrase_priority=3.0,  # Новые фразы в 3 раза чаще
                decay_days=30  # Приоритет затухает за 30 дней
            )
            
            if result:
                phrase_id, english_phrase, russian_translation = result
                self.logger.info(f"[END_FUNCTION][get_random_phrase] Получена взвешенная фраза {phrase_id}: {english_phrase}")
                return phrase_id, english_phrase, russian_translation
            
            # Fallback: если взвешенный выбор не сработал, используем обычный
            self.logger.warning("[WARNING][get_random_phrase] Взвешенный выбор не дал результата, используем обычный")
            phrases = self.database.get_all_phrases()
            
            if not phrases:
                self.logger.warning("[WARNING][get_random_phrase] В базе данных нет фраз")
                return None
            
            # Выбираем случайную фразу
            random_phrase = random.choice(phrases)
            phrase_id = random_phrase['id']
            english_phrase = random_phrase['phrase']  # english_text
            russian_translation = random_phrase.get('context', '')  # russian_text
            
            self.logger.info(f"[END_FUNCTION][get_random_phrase] Получена случайная фраза {phrase_id}: {english_phrase}")
            return phrase_id, english_phrase, russian_translation
            
        except Exception as e:
            self.logger.error(f"[ERROR][get_random_phrase] Ошибка при получении фразы: {e}")
            return None
    
    # endregion FUNCTION get_random_phrase
    
    # region FUNCTION save_user_answer
    # CONTRACT
    # Args:
    #   - phrase_id: ID фразы в базе данных.
    #   - user_answer: Ответ пользователя.
    #   - ai_score: Оценка AI (от 0.0 до 1.0).
    # Returns:
    #   - None
    # Side Effects:
    #   - Сохраняет ответ пользователя и оценку в базу данных.
    # Raises:
    #   - None
    # Tests:
    #   - Валидные данные: должны быть сохранены в базу данных.
    
    def save_user_answer(self, phrase_id: int, user_answer: str, ai_score: float) -> None:
        """Сохраняет ответ пользователя и оценку AI в базу данных."""
        self.logger.info(f"[START_FUNCTION][save_user_answer] Сохранение ответа пользователя для фразы {phrase_id}")
        
        try:
            # Используем существующий метод update_progress
            # Пока что используем user_id = 1 (для одного пользователя)
            user_id = 1
            is_learned = self.database.update_progress(user_id, phrase_id, ai_score, user_answer)
            
            if is_learned:
                self.logger.info(f"[INFO][save_user_answer] Фраза {phrase_id} выучена!")
            
            # Обновляем прогресс изучения фразы
            try:
                from config.config import LEARNED_SCORE_THRESHOLD
                
                # ПРОГРЕСС ОБНОВЛЯЕТСЯ В _update_google_sheets_progress
                # Убираем дублирующий вызов update_phrase_progress
                # became_learned = self.database.update_phrase_progress(phrase_id, ai_score)
                
                # Проверяем, стала ли фраза изученной (после обновления в Google Sheets)
                # Это будет сделано в _update_google_sheets_progress
                
            except Exception as e:
                self.logger.error(f"[ERROR][save_user_answer] Ошибка обновления прогресса фразы: {e}")
            
            # 🔄 НОВАЯ ФУНКЦИЯ: Записываем балл в Google Sheets в реальном времени
            try:
                self._update_google_sheets_progress(phrase_id, ai_score)
                self.logger.info(f"[INFO][save_user_answer] Балл {ai_score} записан в Google Sheets для фразы {phrase_id}")
            except Exception as e:
                self.logger.error(f"[ERROR][save_user_answer] Ошибка записи в Google Sheets: {e}")
            
            self.logger.info(f"[END_FUNCTION][save_user_answer] Ответ пользователя для фразы {phrase_id} сохранен")
            
        except Exception as e:
            self.logger.error(f"[ERROR][save_user_answer] Ошибка при сохранении ответа: {e}")
    
    # endregion FUNCTION save_user_answer
    
    # region FUNCTION _update_google_sheets_progress
    # CONTRACT
    # Args:
    #   - phrase_id: ID фразы для обновления
    #   - ai_score: Балл AI (от 0.0 до 1.0)
    # Returns:
    #   - None
    # Side Effects:
    #   - Обновляет столбец Progress в Google Sheets
    # Raises:
    #   - Exception: при ошибке работы с Google Sheets
    # Tests:
    #   - phrase_id валидный, ai_score корректный: должен обновить Google Sheets
    
    def _update_google_sheets_progress(self, phrase_id: int, ai_score: float) -> None:
        """Обновляет прогресс фразы в Google Sheets в реальном времени."""
        try:
            # Импортируем Google Sync только при необходимости
            from src.google_sync import GoogleSheetsSync
            from config.config import GOOGLE_SHEETS_CREDENTIALS_FILE, GOOGLE_SHEETS_SPREADSHEET_ID
            
            # Создаем экземпляр синхронизации с учетными данными
            google_sync = GoogleSheetsSync(
                credentials_path=GOOGLE_SHEETS_CREDENTIALS_FILE,
                spreadsheet_id=GOOGLE_SHEETS_SPREADSHEET_ID
            )
            
            # Получаем текущий прогресс фразы из БД
            current_progress = self.database.get_phrase_progress(phrase_id)
            
            # Добавляем новый балл к текущему прогрессу
            new_total_progress = current_progress + ai_score
            
            # ОБНОВЛЯЕМ ЛОКАЛЬНУЮ БД (вместо дублирующего вызова выше)
            became_learned = self.database.update_phrase_progress(phrase_id, ai_score)
            
            if became_learned:
                self.logger.info(f"[INFO][_update_google_sheets_progress] Фраза {phrase_id} достигла порога изучения!")
            
            # Обновляем Google Sheets
            google_sync.update_phrase_progress_in_sheets(phrase_id, new_total_progress)
            
            self.logger.info(f"[INFO][_update_google_sheets_progress] Google Sheets обновлен: фраза {phrase_id}, прогресс: {new_total_progress}")
            
        except ImportError:
            self.logger.warning("[WARNING][_update_google_sheets_progress] Google Sheets API недоступен")
        except Exception as e:
            self.logger.error(f"[ERROR][_update_google_sheets_progress] Ошибка обновления Google Sheets: {e}")
            raise e
    
    # endregion FUNCTION _update_google_sheets_progress
    
    # region FUNCTION _get_score_emoji
    # CONTRACT
    # Args:
    #   - score: Оценка AI (от 0.0 до 1.0).
    # Returns:
    #   - str: Эмодзи в зависимости от оценки.
    # Side Effects:
    #   - None
    # Raises:
    #   - None
    # Tests:
    #   - score=0.0: должен вернуть "❌".
    #   - score=0.3: должен вернуть "😐".
    #   - score=0.5: должен вернуть "🙂".
    #   - score=0.7: должен вернуть "😊".
    #   - score=1.0: должен вернуть "🎉".
    
    def _get_score_emoji(self, score: float) -> str:
        """Возвращает эмодзи в зависимости от оценки AI."""
        if score == 0.0:
            return "❌"
        elif score <= 0.2:
            return "😞"
        elif score <= 0.4:
            return "😐"
        elif score <= 0.6:
            return "🙂"
        elif score <= 0.8:
            return "😊"
        elif score <= 0.9:
            return "😄"
        else:
            return "🎉"
    
    # endregion FUNCTION _get_score_emoji
    
    # region FUNCTION auto_send_phrase
    # CONTRACT
    # Args:
    #   - user_id: ID пользователя для отправки фразы.
    # Returns:
    #   - None
    # Side Effects:
    #   - Отправляет случайную фразу пользователю.
    #   - Обновляет время последней отправки.
    # Raises:
    #   - None
    # Tests:
    #   - user_id валидный: должен отправить фразу и обновить время.
    
    async def auto_send_phrase(self, user_id: int) -> None:
        """Автоматически отправляет случайную фразу пользователю."""
        try:
            # Проверяем, включена ли автоматическая отправка
            if not self.auto_send_enabled:
                return
            
            # Проверяем, прошло ли достаточно времени
            if user_id in self.last_auto_send:
                time_since_last = datetime.now() - self.last_auto_send[user_id]
                if time_since_last < self.auto_send_interval:
                    return
            
            # Получаем случайную фразу
            phrase_data = self.get_random_phrase()
            if not phrase_data:
                return
            
            phrase_id, english_phrase, russian_translation = phrase_data
            
            # Случайно выбираем тип упражнения
            exercise_type = random.choice(['translate_to_russian', 'translate_to_english'])
            
            # Сохраняем ожидаемый ответ
            self.expected_answers[user_id] = {
                'phrase_id': phrase_id,
                'english_phrase': english_phrase,
                'russian_translation': russian_translation,
                'exercise_type': exercise_type
            }
            
            # Формируем сообщение в зависимости от типа упражнения
            if exercise_type == 'translate_to_russian':
                message_text = f"""🔄 **Автоматическая фраза для изучения:**

🇬🇧 **Переведите на русский язык:**

{english_phrase}

💡 **Напишите перевод на русском языке**"""
            else:
                message_text = f"""🔄 **Автоматическая фраза для изучения:**

🇷🇺 **Переведите на английский язык:**

{russian_translation}

💡 **Напишите перевод на английском языке**"""
            
            # Отправляем сообщение (используем bot для отправки)
            # Для этого нужно передать bot в метод
            if hasattr(self, 'bot'):
                await self.bot.send_message(user_id, message_text, parse_mode='Markdown')
            
            # Обновляем время последней отправки
            self.last_auto_send[user_id] = datetime.now()
            
            self.logger.info(f"[INFO][auto_send_phrase] Автоматическая фраза {phrase_id} отправлена пользователю {user_id}")
            
        except Exception as e:
            self.logger.error(f"[ERROR][auto_send_phrase] Ошибка при автоматической отправке пользователю {user_id}: {e}")
    
    # endregion FUNCTION auto_send_phrase
    
    # region FUNCTION auto_sync_google_sheets
    # CONTRACT
    # Args:
    #   - None
    # Returns:
    #   - None
    # Side Effects:
    #   - Синхронизирует фразы с Google Sheets.
    #   - Обновляет время последней синхронизации.
    #   - Уведомляет пользователей о новых фразах.
    # Raises:
    #   - None
    # Tests:
    #   - Google Sheets доступен: должен синхронизировать и уведомить.
    
    async def auto_sync_google_sheets(self) -> None:
        """Автоматически синхронизирует фразы с Google Sheets."""
        try:
            # Проверяем, включена ли автоматическая синхронизация
            if not self.auto_sync_enabled:
                return
            
            # Проверяем, прошло ли достаточно времени
            if self.last_auto_sync:
                time_since_last = datetime.now() - self.last_auto_sync
                if time_since_last < self.auto_sync_interval:
                    return
            
            self.logger.info("[INFO][auto_sync_google_sheets] Начинаю автоматическую синхронизацию с Google Sheets")
            
            # Проверяем наличие необходимых настроек
            if not GOOGLE_SHEETS_CREDENTIALS_FILE or not GOOGLE_SHEETS_SPREADSHEET_ID:
                self.logger.warning("[WARNING][auto_sync_google_sheets] Отсутствуют настройки Google Sheets")
                return
            
            # Создаем синхронизатор
            sync = GoogleSheetsSync(
                credentials_path=GOOGLE_SHEETS_CREDENTIALS_FILE,
                spreadsheet_id=GOOGLE_SHEETS_SPREADSHEET_ID,
                database_manager=self.database
            )
            
            # Получаем статус до синхронизации
            status_before = sync.get_sync_status()
            phrases_before = status_before.get('database_count', 0)  # Безопасное получение значения
            
            # Выполняем синхронизацию
            result = sync.full_sync()
            
            # Получаем статус после синхронизации
            status_after = sync.get_sync_status()
            phrases_after = status_after.get('database_count', 0)  # Безопасное получение значения
            
            # Обновляем время последней синхронизации
            self.last_auto_sync = datetime.now()
            
            # Проверяем, есть ли новые фразы
            new_phrases = phrases_after - phrases_before
            
            if new_phrases > 0:
                # Уведомляем всех активных пользователей о новых фразах
                notification_message = f"""🔄 **Автоматическая синхронизация завершена!**

📊 **Новые фразы:** +{new_phrases}
📈 **Всего фраз в базе:** {phrases_after}
⏰ **Время синхронизации:** {self.last_auto_sync.strftime('%d.%m.%Y в %H:%M')}

🎯 Теперь бот может использовать новые фразы для упражнений!"""
                
                # Отправляем уведомление всем активным пользователям
                for user_id in list(self.last_auto_send.keys()):
                    try:
                        if hasattr(self, 'bot'):
                            await self.bot.send_message(user_id, notification_message, parse_mode='Markdown')
                    except Exception as e:
                        self.logger.error(f"[ERROR][auto_sync_google_sheets] Ошибка отправки уведомления пользователю {user_id}: {e}")
                
                self.logger.info(f"[INFO][auto_sync_google_sheets] Синхронизация завершена, добавлено {new_phrases} новых фраз")
            else:
                self.logger.info("[INFO][auto_sync_google_sheets] Синхронизация завершена, новых фраз не найдено")
            
        except Exception as e:
            self.logger.error(f"[ERROR][auto_sync_google_sheets] Ошибка при автоматической синхронизации: {e}")
    
    # endregion FUNCTION auto_sync_google_sheets
    
    # region FUNCTION start_auto_send_task
    # CONTRACT
    # Args:
    #   - bot: Экземпляр Bot для отправки сообщений.
    # Returns:
    #   - None
    # Side Effects:
    #   - Запускает фоновую задачу автоматической отправки.
    # Raises:
    #   - None
    # Tests:
    #   - bot валидный: должен запустить фоновую задачу.
    
    def start_auto_send_task(self, bot: Bot) -> None:
        """Запускает фоновую задачу автоматической отправки фраз и синхронизации."""
        self.bot = bot  # Сохраняем ссылку на bot для отправки сообщений
        
        async def auto_tasks_loop():
            """Основной цикл автоматических задач."""
            while True:
                try:
                    # Автоматическая синхронизация с Google Sheets
                    await self.auto_sync_google_sheets()
                    
                    # Автоматическая отправка фраз пользователям
                    for user_id in list(self.last_auto_send.keys()):
                        await self.auto_send_phrase(user_id)
                    
                    # Ждем 1 час перед следующей проверкой
                    await asyncio.sleep(3600)  # 1 час
                    
                except Exception as e:
                    self.logger.error(f"[ERROR][auto_tasks_loop] Ошибка в цикле автоматических задач: {e}")
                    await asyncio.sleep(3600)  # Ждем час при ошибке
        
        # Запускаем фоновую задачу в отдельном цикле событий
        try:
            loop = asyncio.get_event_loop()
            self.auto_send_task = loop.create_task(auto_tasks_loop())
            self.logger.info("[INFO][start_auto_send_task] Задача автоматической отправки запущена")
        except RuntimeError:
            # Если цикл событий не запущен, создаем новый
            self.auto_send_task = asyncio.create_task(auto_tasks_loop())
            self.logger.info("[INFO][start_auto_send_task] Задача автоматической отправки запущена в новом цикле")
    
    # endregion FUNCTION start_auto_send_task
    
    # region FUNCTION setup_handlers
    # CONTRACT
    # Args:
    #   - dp: Экземпляр Dispatcher для настройки обработчиков.
    # Returns:
    #   - None
    # Side Effects:
    #   - Регистрирует все обработчики команд и сообщений в диспетчере.
    # Raises:
    #   - None
    # Tests:
    #   - dp с валидными обработчиками: должны быть зарегистрированы.
    
    def setup_handlers(self, dp: Dispatcher) -> None:
        """Настраивает обработчики команд и сообщений для бота."""
        self.logger.info("[START_FUNCTION][setup_handlers] Настройка обработчиков для бота")
        
        # Регистрируем обработчики команд
        dp.message.register(self.start_command, Command("start"))
        dp.message.register(self.help_command, Command("help"))
        dp.message.register(self.phrase_command, Command("phrase"))
        dp.message.register(self.reverse_command, Command("reverse")) # Регистрируем обработчик для команды /reverse
        dp.message.register(self.sync_command, Command("sync")) # Регистрируем обработчик для команды /sync
        dp.message.register(self.auto_command, Command("auto")) # Регистрируем обработчик для команды /auto
        dp.message.register(self.stats_command, Command("stats")) # Регистрируем обработчик для команды /stats
        dp.message.register(self.interval_command, Command("interval")) # Регистрируем обработчик для команды /interval
        
        # Регистрируем обработчик текстовых сообщений (ответы пользователя)
        dp.message.register(self.handle_answer, F.text)
        
        self.logger.info("[END_FUNCTION][setup_handlers] Обработчики настроены")
    
    # endregion FUNCTION setup_handlers

# endregion Класс EnglishLearningBot

# region Функция создания и запуска бота
async def create_and_run_bot() -> None:
    """Создает и запускает Telegram бота."""
    logging.info("[START_FUNCTION][create_and_run_bot] Создание и запуск Telegram бота")
    
    try:
        # Создаем экземпляры бота и диспетчера
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        dp = Dispatcher()
        
        # Создаем экземпляр бота
        english_bot = EnglishLearningBot()
        
        # Настраиваем обработчики
        english_bot.setup_handlers(dp)
        
        # Запускаем автоматическую отправку фраз
        english_bot.start_auto_send_task(bot)
        
        # Запускаем бота с обработкой исключений для предотвращения падений
        try:
            await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
        except KeyboardInterrupt:
            logging.info("[INFO][create_and_run_bot] Бот остановлен пользователем")
        except Exception as e:
            logging.error(f"[ERROR][create_and_run_bot] Критическая ошибка в polling: {e}")
            import traceback
            logging.error(f"[ERROR][create_and_run_bot] Traceback: {traceback.format_exc()}")
            raise
        
        logging.info("[END_FUNCTION][create_and_run_bot] Бот успешно запущен")
        
    except Exception as e:
        logging.error(f"[ERROR][create_and_run_bot] Ошибка запуска бота: {e}")
        import traceback
        logging.error(f"[ERROR][create_and_run_bot] Traceback: {traceback.format_exc()}")
        raise

# endregion Функция создания и запуска бота

# region Точка входа
if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запуск бота
    import asyncio
    asyncio.run(create_and_run_bot())
# endregion
