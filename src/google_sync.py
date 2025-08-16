"""
Модуль: google_sync.py

Назначение:
    Интеграция с Google Sheets API для синхронизации фраз
    с локальной SQLite базой данных.
    
Функции:
    - Чтение фраз из Google Sheets (включая столбец Progress)
    - Синхронизация с SQLite БД с учетом прогресса изучения
    - Обработка изменений в таблице
    - Автоматическое исключение изученных фраз (3+ баллов)
"""

import os
import json
import logging
import sqlite3
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .database import DatabaseManager

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleSheetsSync:
    """Класс для синхронизации с Google Sheets."""
    
    def __init__(self, credentials_path: str = None, spreadsheet_id: str = None, database_manager: DatabaseManager = None):
        """
        Инициализация синхронизатора.
        
        Args:
            credentials_path: Путь к JSON-файлу с учетными данными (опционально)
            spreadsheet_id: ID таблицы Google Sheets (опционально)
            database_manager: Менеджер базы данных SQLite (опционально)
        """
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        self.database_manager = database_manager
        self.service = None
        
        # Настройка аутентификации только если указаны учетные данные
        if credentials_path and spreadsheet_id:
            self._setup_authentication()
    
    def _setup_authentication(self) -> None:
        """Настройка аутентификации для Google Sheets API."""
        try:
            # Загружаем учетные данные из JSON-файла
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly', 'https://www.googleapis.com/auth/spreadsheets']
            )
            
            # Создаем сервис для работы с Google Sheets
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Аутентификация Google Sheets API успешно настроена")
            
        except Exception as e:
            logger.error(f"Ошибка настройки аутентификации: {e}")
            raise
    
    def get_phrases_from_sheets(self, range_name: str = "english!A:E") -> List[Dict]:
        """
        Получение фраз из Google Sheets.
        
        Args:
            range_name: Диапазон ячеек для чтения (по умолчанию вкладка 'english' включая столбец E)
            
        Returns:
            Список словарей с данными фраз
        """
        try:
            # Читаем данные из таблицы
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                logger.warning("В таблице не найдено данных")
                return []
            
            # Обрабатываем заголовки
            headers = values[0]
            logger.info(f"Найдено {len(values) - 1} строк с данными")
            
            # Преобразуем данные в список словарей
            phrases = []
            for i, row in enumerate(values[1:], start=2):  # Начинаем с 2-й строки
                if len(row) >= 3:  # Минимум: дата, английский текст, перевод
                    phrase_data = {
                        'row_number': i,
                        'date': row[0] if len(row) > 0 else None,
                        'english_text': row[1].strip() if len(row) > 1 else None,  # Убираем лишние символы
                        'russian_text': row[2].strip() if len(row) > 2 else None,  # Убираем лишние символы
                        'example': row[3].strip() if len(row) > 3 else None,  # Убираем лишние символы
                        'progress': row[4] if len(row) > 4 else None
                    }
                    
                    # Обрабатываем прогресс из столбца E
                    if phrase_data['progress']:
                        try:
                            # Пытаемся преобразовать прогресс в число
                            progress_value = float(phrase_data['progress'])
                            phrase_data['progress_score'] = progress_value
                        except (ValueError, TypeError):
                            # Если не число, устанавливаем 0
                            phrase_data['progress_score'] = 0.0
                    else:
                        phrase_data['progress_score'] = 0.0
                    
                    # Проверяем, что основные поля заполнены
                    if phrase_data['english_text'] and phrase_data['russian_text']:
                        phrases.append(phrase_data)
                    else:
                        logger.warning(f"Строка {i}: пропущена - неполные данные")
            
            logger.info(f"Обработано {len(phrases)} валидных фраз")
            return phrases
            
        except HttpError as e:
            logger.error(f"Ошибка Google Sheets API: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка чтения данных: {e}")
            raise
    
    def sync_phrases_to_database(self, phrases: List[Dict]) -> Tuple[int, int, int]:
        """
        Синхронизация фраз с базой данных SQLite.
        
        Args:
            phrases: Список фраз из Google Sheets
            
        Returns:
            Кортеж (добавлено, обновлено, ошибок)
        """
        added_count = 0
        updated_count = 0
        error_count = 0
        
        for phrase_data in phrases:
            try:
                english_text = phrase_data['english_text'].strip()
                russian_text = phrase_data['russian_text'].strip()
                
                # Определяем сложность на основе длины текста
                difficulty = self._determine_difficulty(english_text)
                
                # Проверяем, существует ли фраза в БД
                existing_phrase = self._find_existing_phrase(english_text)
                
                if existing_phrase:
                    # Обновляем существующую фразу
                    self._update_existing_phrase(existing_phrase['id'], russian_text, difficulty)
                    updated_count += 1
                    logger.debug(f"Обновлена фраза: {english_text}")
                else:
                    # Добавляем новую фразу напрямую в БД
                    phrase_id = self._add_phrase_to_db(english_text, russian_text, difficulty)
                    added_count += 1
                    logger.debug(f"Добавлена новая фраза (ID: {phrase_id}): {english_text}")
                
                # Обновляем прогресс фразы из Google Sheets
                if phrase_data.get('progress_score', 0) > 0:
                    try:
                        phrase_id = existing_phrase['id'] if existing_phrase else phrase_id
                        self._update_phrase_progress_in_db(phrase_id, phrase_data['progress_score'])
                        logger.debug(f"Обновлен прогресс фразы {phrase_id}: {phrase_data['progress_score']}")
                    except Exception as e:
                        logger.warning(f"Не удалось обновить прогресс фразы {english_text}: {e}")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Ошибка обработки фразы '{phrase_data.get('english_text', 'N/A')}': {e}")
        
        logger.info(f"Синхронизация завершена: добавлено {added_count}, обновлено {updated_count}, ошибок {error_count}")
        return added_count, updated_count, error_count
    
    def _determine_difficulty(self, english_text: str) -> str:
        """
        Определение сложности фразы на основе длины и содержания.
        
        Args:
            english_text: Английский текст фразы
            
        Returns:
            Строка сложности: 'easy', 'medium', 'hard'
        """
        word_count = len(english_text.split())
        
        if word_count <= 3:
            return 'easy'
        elif word_count <= 8:
            return 'medium'
        else:
            return 'hard'
    
    def _find_existing_phrase(self, english_text: str) -> Optional[Dict]:
        """
        Поиск существующей фразы в базе данных.
        
        Args:
            english_text: Английский текст для поиска
            
        Returns:
            Словарь с данными фразы или None
        """
        try:
            # Простой поиск по точному совпадению
            # В будущем можно улучшить поиск (например, игнорировать регистр)
            from config.config import DATABASE_PATH
            db_path = DATABASE_PATH
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, english_text, russian_text, difficulty FROM phrases WHERE english_text = ?",
                    (english_text,)
                )
                result = cursor.fetchone()
                
                if result:
                    return {
                        'id': result[0],
                        'english_text': result[1],
                        'russian_text': result[2],
                        'difficulty': result[3]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Ошибка поиска фразы: {e}")
            return None
    
    def _update_existing_phrase(self, phrase_id: int, russian_text: str, difficulty: str) -> None:
        """
        Обновление существующей фразы в базе данных.
        
        Args:
            phrase_id: ID фразы для обновления
            russian_text: Новый русский перевод
            difficulty: Новая сложность
        """
        try:
            from config.config import DATABASE_PATH
            db_path = DATABASE_PATH
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE phrases SET russian_text = ?, difficulty = ? WHERE id = ?",
                    (russian_text, difficulty, phrase_id)
                )
                
        except Exception as e:
            logger.error(f"Ошибка обновления фразы {phrase_id}: {e}")
            raise
    
    def full_sync(self) -> Dict[str, int]:
        """
        Полная синхронизация фраз из Google Sheets в базу данных.
        
        Returns:
            Словарь с результатами синхронизации
        """
        logger.info("Начинаем полную синхронизацию с Google Sheets")
        
        try:
            # Получаем фразы из Google Sheets с листа english
            phrases = self.get_phrases_from_sheets("english!A:E")
            
            if not phrases:
                logger.warning("Нет фраз для синхронизации")
                return {'added': 0, 'updated': 0, 'errors': 0, 'total': 0}
            
            # Синхронизируем с базой данных
            added, updated, errors = self.sync_phrases_to_database(phrases)
            
            result = {
                'added': added,
                'updated': updated,
                'errors': errors,
                'total': len(phrases)
            }
            
            logger.info(f"Синхронизация завершена успешно: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка полной синхронизации: {e}")
            raise
    
    def get_sync_status(self) -> Dict[str, any]:
        """
        Получение статуса синхронизации.
        
        Returns:
            Словарь со статусом синхронизации
        """
        try:
            # Получаем количество фраз в Google Sheets с листа english
            sheets_phrases = self.get_phrases_from_sheets("english!A:E")
            sheets_count = len(sheets_phrases)
            
            # Получаем количество фраз в базе данных напрямую
            from config.config import DATABASE_PATH
            db_path = DATABASE_PATH
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM phrases")
                db_count = cursor.fetchone()[0]
            
            # Вычисляем процент синхронизации
            sync_percentage = (db_count / sheets_count * 100) if sheets_count > 0 else 0
            
            return {
                'sheets_count': sheets_count,
                'database_count': db_count,
                'sync_percentage': round(sync_percentage, 2),
                'last_sync': datetime.now().isoformat(),
                'status': 'synced' if sync_percentage >= 95 else 'needs_sync'
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статуса синхронизации: {e}")
            # Возвращаем безопасный результат с ошибкой
            return {
                'sheets_count': 0,
                'database_count': 0,
                'sync_percentage': 0.0,
                'last_sync': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e)
            }

    def update_phrase_progress_in_sheets(self, phrase_id: int, new_progress: float) -> None:
        """
        Обновляет прогресс фразы в Google Sheets в реальном времени.
        
        Args:
            phrase_id: ID фразы для обновления
            new_progress: Новый общий прогресс фразы
        """
        logger.info(f"[START_FUNCTION][update_phrase_progress_in_sheets] Обновление прогресса фразы {phrase_id} в Google Sheets: {new_progress}")
        
        try:
            # Используем переменные окружения
            from config.config import GOOGLE_SHEETS_CREDENTIALS_FILE, GOOGLE_SHEETS_SPREADSHEET_ID
            
            credentials_path = GOOGLE_SHEETS_CREDENTIALS_FILE
            spreadsheet_id = GOOGLE_SHEETS_SPREADSHEET_ID
            
            # Отладочная информация
            logger.info(f"[DEBUG] credentials_path: {credentials_path}")
            logger.info(f"[DEBUG] spreadsheet_id: {spreadsheet_id}")
            
            # Если сервис не настроен, настраиваем его
            if not self.service:
                self.credentials_path = credentials_path
                self.spreadsheet_id = spreadsheet_id
                self._setup_authentication()
            
            # Получаем данные фразы из БД для поиска в Google Sheets
            phrase_data = self._get_phrase_by_id(phrase_id)
            if not phrase_data:
                logger.warning(f"[WARNING][update_phrase_progress_in_sheets] Фраза {phrase_id} не найдена в БД")
                return
            
            # Получаем все фразы из Google Sheets
            sheets_phrases = self.get_phrases_from_sheets("english!A:E")
            
            logger.info(f"[DEBUG] Найдено {len(sheets_phrases)} фраз в Google Sheets")
            logger.info(f"[DEBUG] Ищем фразу: '{phrase_data['english_text'][:50]}...'")
            
            # Ищем соответствующую фразу в Google Sheets
            target_row = None
            for i, phrase in enumerate(sheets_phrases):
                if phrase.get('english_text') == phrase_data['english_text']:
                    target_row = i + 2  # +2 потому что Google Sheets начинается с 1, а мы с 0
                    logger.info(f"[DEBUG] Найдена фраза в строке {target_row}")
                    break
            
            if target_row is None:
                logger.warning(f"[WARNING][update_phrase_progress_in_sheets] Фраза '{phrase_data['english_text']}' не найдена в Google Sheets")
                # Выводим первые 3 фразы для отладки
                logger.info(f"[DEBUG] Первые 3 фразы в Google Sheets:")
                for i, p in enumerate(sheets_phrases[:3]):
                    logger.info(f"[DEBUG] {i+1}: {p.get('english_text', 'N/A')[:50]}...")
                return
            
            # Обновляем прогресс в Google Sheets (столбец E, индекс 4)
            # Формируем диапазон для обновления (вкладка english, столбец E, строка target_row)
            range_name = f"english!E{target_row}"
            
            logger.info(f"[DEBUG] Обновляем диапазон: {range_name} значением: {new_progress}")
            logger.info(f"[DEBUG] Записываем на лист 'english', столбец E, строка {target_row}")
            
            # Обновляем значение
            update_result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body={'values': [[new_progress]]}
            ).execute()
            
            logger.info(f"[DEBUG] Результат обновления: {update_result}")
            logger.info(f"[END_FUNCTION][update_phrase_progress_in_sheets] Google Sheets обновлен: лист 'english', строка {target_row}, столбец E, прогресс {new_progress}")
            
        except Exception as e:
            logger.error(f"[ERROR][update_phrase_progress_in_sheets] Ошибка обновления Google Sheets: {e}")
            raise e
    
    def _get_phrase_by_id(self, phrase_id: int) -> Optional[Dict]:
        """
        Получает данные фразы по ID из базы данных.
        
        Args:
            phrase_id: ID фразы
            
        Returns:
            Словарь с данными фразы или None
        """
        try:
            # Используем тот же путь к БД что и в других методах
            from config.config import DATABASE_PATH
            db_path = DATABASE_PATH
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, english_text, russian_text, difficulty
                    FROM phrases
                    WHERE id = ?
                """, (phrase_id,))
                
                result = cursor.fetchone()
                
                if result:
                    return {
                        'id': result[0],
                        'english_text': result[1],
                        'russian_text': result[2],
                        'difficulty': result[3]
                    }
                return None
                
        except Exception as e:
            logger.error(f"[ERROR][_get_phrase_by_id] Ошибка получения фразы {phrase_id}: {e}")
            return None

    def _update_phrase_progress_in_db(self, phrase_id: int, progress_score: float) -> None:
        """
        Обновляет прогресс фразы в базе данных.
        
        Args:
            phrase_id: ID фразы
            progress_score: Новый прогресс
        """
        try:
            from config.config import DATABASE_PATH
            db_path = DATABASE_PATH
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE phrases 
                    SET total_progress_score = ?, is_learned = ?
                    WHERE id = ?
                """, (progress_score, progress_score >= 3.0, phrase_id))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Ошибка обновления прогресса фразы {phrase_id}: {e}")
            raise
    
    def _add_phrase_to_db(self, english_text: str, russian_text: str, difficulty: str) -> int:
        """
        Добавляет новую фразу в базу данных.
        
        Args:
            english_text: Английский текст
            russian_text: Русский перевод
            difficulty: Сложность
            
        Returns:
            ID добавленной фразы
        """
        try:
            from config.config import DATABASE_PATH
            db_path = DATABASE_PATH
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO phrases (english_text, russian_text, difficulty, total_progress_score, is_learned)
                    VALUES (?, ?, ?, 0.0, 0)
                """, (english_text, russian_text, difficulty))
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"Ошибка добавления фразы: {e}")
            raise


def main():
    """Тестовая функция для проверки работы модуля."""
    try:
        # Используем переменные окружения
        from config.config import GOOGLE_SHEETS_CREDENTIALS_FILE, GOOGLE_SHEETS_SPREADSHEET_ID
        
        credentials_path = GOOGLE_SHEETS_CREDENTIALS_FILE
        spreadsheet_id = GOOGLE_SHEETS_SPREADSHEET_ID
        
        # Создаем менеджер базы данных
        db_manager = DatabaseManager()
        
        # Создаем синхронизатор
        sync = GoogleSheetsSync(credentials_path, spreadsheet_id, db_manager)
        
        # Получаем статус синхронизации
        status = sync.get_sync_status()
        print(f"Статус синхронизации: {status}")
        
        # Выполняем полную синхронизацию
        result = sync.full_sync()
        print(f"Результат синхронизации: {result}")
        
        # Получаем обновленный статус
        new_status = sync.get_sync_status()
        print(f"Новый статус: {new_status}")
        
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        if 'db_manager' in locals():
            db_manager.close()


if __name__ == "__main__":
    main()
