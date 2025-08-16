"""
Модуль: google_sync.py

Назначение:
    Интеграция с Google Sheets API для синхронизации фраз
    с локальной SQLite базой данных.
    
Функции:
    - Чтение фраз из Google Sheets
    - Синхронизация с SQLite БД
    - Обработка изменений в таблице
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
    
    def __init__(self, credentials_path: str, spreadsheet_id: str, database_manager: DatabaseManager):
        """
        Инициализация синхронизатора.
        
        Args:
            credentials_path: Путь к JSON-файлу с учетными данными
            spreadsheet_id: ID таблицы Google Sheets
            database_manager: Менеджер базы данных SQLite
        """
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        self.database_manager = database_manager
        self.service = None
        
        # Настройка аутентификации
        self._setup_authentication()
    
    def _setup_authentication(self) -> None:
        """Настройка аутентификации для Google Sheets API."""
        try:
            # Загружаем учетные данные из JSON-файла
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )
            
            # Создаем сервис для работы с Google Sheets
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Аутентификация Google Sheets API успешно настроена")
            
        except Exception as e:
            logger.error(f"Ошибка настройки аутентификации: {e}")
            raise
    
    def get_phrases_from_sheets(self, range_name: str = "english!A:D") -> List[Dict]:
        """
        Получение фраз из Google Sheets.
        
        Args:
            range_name: Диапазон ячеек для чтения (по умолчанию вкладка 'english')
            
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
                        'english_text': row[1] if len(row) > 1 else None,
                        'russian_text': row[2] if len(row) > 2 else None,
                        'example': row[3] if len(row) > 3 else None,
                        'progress': row[4] if len(row) > 4 else None
                    }
                    
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
                    # Добавляем новую фразу
                    phrase_id = self.database_manager.add_phrase(
                        english_text=english_text,
                        russian_text=russian_text,
                        difficulty=difficulty
                    )
                    added_count += 1
                    logger.debug(f"Добавлена новая фраза (ID: {phrase_id}): {english_text}")
                    
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
            with sqlite3.connect(self.database_manager.db_path) as conn:
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
            with sqlite3.connect(self.database_manager.db_path) as conn:
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
            # Получаем фразы из Google Sheets
            phrases = self.get_phrases_from_sheets()
            
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
            # Получаем количество фраз в Google Sheets
            sheets_phrases = self.get_phrases_from_sheets()
            sheets_count = len(sheets_phrases)
            
            # Получаем количество фраз в базе данных
            db_stats = self.database_manager.get_statistics(user_id=1)
            db_count = db_stats['total_phrases']
            
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
            return {
                'error': str(e),
                'status': 'error'
            }


def main():
    """Тестовая функция для проверки работы модуля."""
    try:
        # Путь к JSON-файлу с учетными данными
        credentials_path = "python-datalens-f6500fa9f949.json"
        
        # ID таблицы Google Sheets
        spreadsheet_id = "1asOMYirFTteYzP8ffMob3u3IGZryiMoeD7OQSbm0_iw"
        
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
