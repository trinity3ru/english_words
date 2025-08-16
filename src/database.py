"""
Файл: database.py

Назначение:
    Модуль для работы с SQLite базой данных AI-системы изучения английского языка.
    Содержит функции для создания таблиц, управления фразами, прогрессом пользователя
    и аналитикой обучения.

Основные компоненты:

Классы:
    - DatabaseManager: Основной класс для управления БД

Функции:
    - create_tables(): Создает все необходимые таблицы
    - add_phrase(): Добавляет новую фразу в БД
    - get_random_phrase(): Получает случайную фразу для изучения
    - update_progress(): Обновляет прогресс пользователя
    - get_statistics(): Получает статистику обучения
    - get_learning_progress(): Получает прогресс по конкретной фразе

Константы:
    - DATABASE_NAME: Имя файла базы данных
    - MAX_SCORE: Максимальный балл для выученной фразы
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import random

# region Константы
DATABASE_NAME = "english_learning.db"
MAX_SCORE = 3
PARTIAL_SCORE = 0.5
# endregion

# region Настройка логирования
logger = logging.getLogger(__name__)
# endregion

class DatabaseManager:
    """
    Менеджер базы данных для системы изучения английского языка.
    
    Отвечает за:
    - Создание и управление таблицами
    - CRUD операции с фразами и прогрессом
    - Аналитику и статистику обучения
    """
    
    def __init__(self, db_path: str = DATABASE_NAME):
        """
        Инициализация менеджера БД.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.connection = None
        logger.info(f"[START_FUNCTION][__init__] Инициализация БД: {db_path}")
        
        # Создаем таблицы при инициализации
        self.create_tables()
        logger.info(f"[END_FUNCTION][__init__] БД инициализирована")
    
    # region FUNCTION create_tables
    # CONTRACT
    # Args:
    #   - None
    # Returns:
    #   - None
    # Side Effects:
    #   - Создает файл БД и таблицы если они не существуют
    # Raises:
    #   - sqlite3.Error: при ошибках создания таблиц
    # Tests:
    #   - При первом запуске: создаются все таблицы
    #   - При повторном запуске: таблицы остаются без изменений
    
    def create_tables(self) -> None:
        """Создает все необходимые таблицы в базе данных."""
        logger.info("[START_FUNCTION][create_tables] Создание таблиц БД")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Таблица фраз
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS phrases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        english_text TEXT NOT NULL UNIQUE,
                        russian_text TEXT NOT NULL,
                        difficulty TEXT DEFAULT 'medium',
                        context TEXT DEFAULT '',
                        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                """)
                
                # Таблица прогресса пользователя
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_progress (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        phrase_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        current_score REAL DEFAULT 0,
                        attempts INTEGER DEFAULT 0,
                        last_attempt TIMESTAMP,
                        status TEXT DEFAULT 'learning',
                        FOREIGN KEY (phrase_id) REFERENCES phrases (id)
                    )
                """)
                
                # Таблица истории ответов
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS answer_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        phrase_id INTEGER NOT NULL,
                        user_answer TEXT NOT NULL,
                        ai_score REAL NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (phrase_id) REFERENCES phrases (id)
                    )
                """)
                
                # Таблица статистики
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        total_phrases INTEGER DEFAULT 0,
                        learned_phrases INTEGER DEFAULT 0,
                        learning_rate REAL DEFAULT 0.0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info("[END_FUNCTION][create_tables] Таблицы созданы успешно")
                
        except sqlite3.Error as e:
            logger.error(f"[ERROR][create_tables] Ошибка создания таблиц: {e}")
            raise
    # endregion FUNCTION create_tables
    
    # region FUNCTION add_phrase
    # CONTRACT
    # Args:
    #   - english_text: Английский текст фразы
    #   - russian_text: Русский перевод фразы
    #   - difficulty: Уровень сложности (easy/medium/hard)
    # Returns:
    #   - int: ID добавленной фразы
    # Side Effects:
    #   - Добавляет запись в таблицу phrases
    # Raises:
    #   - sqlite3.IntegrityError: если фраза уже существует
    # Tests:
    #   - english_text="Hello", russian_text="Привет": возвращает ID > 0
    #   - english_text="Hello", russian_text="Привет" (повторно): IntegrityError
    
    def add_phrase(self, english_text: str, russian_text: str, difficulty: str = "medium") -> int:
        """
        Добавляет новую фразу в базу данных.
        
        Args:
            english_text: Английский текст фразы
            russian_text: Русский перевод фразы
            difficulty: Уровень сложности (easy/medium/hard)
            
        Returns:
            ID добавленной фразы
            
        Raises:
            sqlite3.IntegrityError: Если фраза уже существует
        """
        logger.info(f"[START_FUNCTION][add_phrase] Добавление фразы: {english_text[:30]}...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO phrases (english_text, russian_text, difficulty)
                    VALUES (?, ?, ?)
                """, (english_text, russian_text, difficulty))
                
                phrase_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"[END_FUNCTION][add_phrase] Фраза добавлена с ID: {phrase_id}")
                return phrase_id
                
        except sqlite3.IntegrityError as e:
            logger.warning(f"[WARNING][add_phrase] Фраза уже существует: {english_text}")
            raise
        except sqlite3.Error as e:
            logger.error(f"[ERROR][add_phrase] Ошибка добавления фразы: {e}")
            raise
    # endregion FUNCTION add_phrase
    
    # region FUNCTION get_random_phrase
    # CONTRACT
    # Args:
    #   - user_id: ID пользователя
    # Returns:
    #   - Optional[Tuple]: (phrase_id, english_text, russian_text) или None
    # Side Effects:
    #   - Нет
    # Raises:
    #   - sqlite3.Error: при ошибках запроса к БД
    # Tests:
    #   - user_id=1: возвращает фразу для изучения
    #   - user_id=1 (все фразы выучены): возвращает None
    
    def get_random_phrase(self, user_id: int) -> Optional[Tuple[int, str, str]]:
        """
        Получает случайную фразу для изучения пользователем.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Кортеж (phrase_id, english_text, russian_text) или None
        """
        logger.info(f"[START_FUNCTION][get_random_phrase] Поиск фразы для пользователя {user_id}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Получаем фразы, которые пользователь еще не выучил
                cursor.execute("""
                    SELECT p.id, p.english_text, p.russian_text
                    FROM phrases p
                    LEFT JOIN user_progress up ON p.id = up.phrase_id AND up.user_id = ?
                    WHERE p.is_active = 1
                    AND (up.status IS NULL OR up.status != 'learned')
                    AND (up.current_score IS NULL OR up.current_score < ?)
                    ORDER BY RANDOM()
                    LIMIT 1
                """, (user_id, MAX_SCORE))
                
                result = cursor.fetchone()
                
                if result:
                    logger.info(f"[END_FUNCTION][get_random_phrase] Найдена фраза ID: {result[0]}")
                    return result
                else:
                    logger.info(f"[END_FUNCTION][get_random_phrase] Фразы для изучения не найдены")
                    return None
                    
        except sqlite3.Error as e:
            logger.error(f"[ERROR][get_random_phrase] Ошибка получения фразы: {e}")
            raise
    # endregion FUNCTION get_random_phrase
    
    # region FUNCTION update_progress
    # CONTRACT
    # Args:
    #   - user_id: ID пользователя
    #   - phrase_id: ID фразы
    #   - ai_score: Балл от AI (0, 0.5, 1)
    #   - user_answer: Ответ пользователя
    # Returns:
    #   - bool: True если фраза выучена
    # Side Effects:
    #   - Обновляет таблицы user_progress, answer_history
    #   - Может изменить статус фразы на 'learned'
    # Raises:
    #   - sqlite3.Error: при ошибках обновления БД
    # Tests:
    #   - ai_score=1, current_score=2: фраза становится выученной
    #   - ai_score=0: балл не изменяется
    
    def update_progress(self, user_id: int, phrase_id: int, ai_score: float, user_answer: str) -> bool:
        """
        Обновляет прогресс пользователя по фразе.
        
        Args:
            user_id: ID пользователя
            phrase_id: ID фразы
            ai_score: Балл от AI (0, 0.5, 1)
            user_answer: Ответ пользователя
            
        Returns:
            True если фраза выучена (достигнут MAX_SCORE)
        """
        logger.info(f"[START_FUNCTION][update_progress] Обновление прогресса: user={user_id}, phrase={phrase_id}, score={ai_score}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Добавляем запись в историю ответов
                cursor.execute("""
                    INSERT INTO answer_history (user_id, phrase_id, user_answer, ai_score)
                    VALUES (?, ?, ?, ?)
                """, (user_id, phrase_id, user_answer, ai_score))
                
                # Получаем текущий прогресс
                cursor.execute("""
                    SELECT current_score, attempts FROM user_progress
                    WHERE user_id = ? AND phrase_id = ?
                """, (user_id, phrase_id))
                
                progress = cursor.fetchone()
                
                if progress:
                    current_score, attempts = progress
                    new_score = min(current_score + ai_score, MAX_SCORE)
                    new_attempts = attempts + 1
                    
                    # Обновляем прогресс
                    cursor.execute("""
                        UPDATE user_progress
                        SET current_score = ?, attempts = ?, last_attempt = CURRENT_TIMESTAMP,
                            status = CASE WHEN ? >= ? THEN 'learned' ELSE 'learning' END
                        WHERE user_id = ? AND phrase_id = ?
                    """, (new_score, new_attempts, new_score, MAX_SCORE, user_id, phrase_id))
                else:
                    # Создаем новую запись прогресса
                    new_score = ai_score
                    new_attempts = 1
                    status = 'learned' if ai_score >= MAX_SCORE else 'learning'
                    
                    cursor.execute("""
                        INSERT INTO user_progress (user_id, phrase_id, current_score, attempts, last_attempt, status)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                    """, (user_id, phrase_id, new_score, new_attempts, status))
                
                conn.commit()
                
                is_learned = new_score >= MAX_SCORE
                logger.info(f"[END_FUNCTION][update_progress] Прогресс обновлен: score={new_score}, learned={is_learned}")
                return is_learned
                
        except sqlite3.Error as e:
            logger.error(f"[ERROR][update_progress] Ошибка обновления прогресса: {e}")
            raise
    # endregion FUNCTION update_progress
    
    # region FUNCTION get_statistics
    # CONTRACT
    # Args:
    #   - user_id: ID пользователя
    # Returns:
    #   - Dict: Статистика обучения пользователя
    # Side Effects:
    #   - Нет
    # Raises:
    #   - sqlite3.Error: при ошибках запроса к БД
    # Tests:
    #   - user_id=1: возвращает словарь со статистикой
    #   - user_id=999: возвращает пустую статистику
    
    def get_statistics(self, user_id: int) -> Dict:
        """
        Получает статистику обучения пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь со статистикой
        """
        logger.info(f"[START_FUNCTION][get_statistics] Получение статистики для пользователя {user_id}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общая статистика
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT p.id) as total_phrases,
                        COUNT(CASE WHEN up.status = 'learned' THEN 1 END) as learned_phrases,
                        AVG(up.current_score) as avg_score
                    FROM phrases p
                    LEFT JOIN user_progress up ON p.id = up.phrase_id AND up.user_id = ?
                    WHERE p.is_active = 1
                """, (user_id,))
                
                stats = cursor.fetchone()
                
                if stats and stats[0]:
                    total_phrases, learned_phrases, avg_score = stats
                    learning_rate = (learned_phrases / total_phrases * 100) if total_phrases > 0 else 0
                    
                    result = {
                        'total_phrases': total_phrases,
                        'learned_phrases': learned_phrases,
                        'learning_rate': round(learning_rate, 2),
                        'avg_score': round(avg_score or 0, 2)
                    }
                else:
                    result = {
                        'total_phrases': 0,
                        'learned_phrases': 0,
                        'learning_rate': 0.0,
                        'avg_score': 0.0
                    }
                
                logger.info(f"[END_FUNCTION][get_statistics] Статистика получена: {result}")
                return result
                
        except sqlite3.Error as e:
            logger.error(f"[ERROR][get_statistics] Ошибка получения статистики: {e}")
            raise
    # endregion FUNCTION get_statistics
    
    # region FUNCTION get_learning_progress
    # CONTRACT
    # Args:
    #   - user_id: ID пользователя
    #   - phrase_id: ID фразы
    # Returns:
    #   - Optional[Dict]: Прогресс по фразе или None
    # Side Effects:
    #   - Нет
    # Raises:
    #   - sqlite3.Error: при ошибках запроса к БД
    # Tests:
    #   - user_id=1, phrase_id=1: возвращает прогресс по фразе
    #   - user_id=1, phrase_id=999: возвращает None
    
    def get_learning_progress(self, user_id: int, phrase_id: int) -> Optional[Dict]:
        """
        Получает прогресс пользователя по конкретной фразе.
        
        Args:
            user_id: ID пользователя
            phrase_id: ID фразы
            
        Returns:
            Словарь с прогрессом или None
        """
        logger.info(f"[START_FUNCTION][get_learning_progress] Получение прогресса: user={user_id}, phrase={phrase_id}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        up.current_score,
                        up.attempts,
                        up.last_attempt,
                        up.status,
                        p.english_text,
                        p.russian_text
                    FROM user_progress up
                    JOIN phrases p ON up.phrase_id = p.id
                    WHERE up.user_id = ? AND up.phrase_id = ?
                """, (user_id, phrase_id))
                
                result = cursor.fetchone()
                
                if result:
                    progress = {
                        'current_score': result[0],
                        'attempts': result[1],
                        'last_attempt': result[2],
                        'status': result[3],
                        'english_text': result[4],
                        'russian_text': result[5]
                    }
                    
                    logger.info(f"[END_FUNCTION][get_learning_progress] Прогресс получен: {progress}")
                    return progress
                else:
                    logger.info(f"[END_FUNCTION][get_learning_progress] Прогресс не найден")
                    return None
                    
        except sqlite3.Error as e:
            logger.error(f"[ERROR][get_learning_progress] Ошибка получения прогресса: {e}")
            raise
    # endregion FUNCTION get_learning_progress
    
    # region FUNCTION get_all_phrases
    # CONTRACT
    # Args:
    #   - None
    # Returns:
    #   - List[Dict]: Список всех активных фраз
    # Side Effects:
    #   - Нет
    # Raises:
    #   - sqlite3.Error: при ошибках запроса к БД
    # Tests:
    #   - БД содержит фразы: возвращает список фраз
    #   - БД пуста: возвращает пустой список
    
    def get_all_phrases(self) -> List[Dict]:
        """
        Получает все активные фразы из базы данных.
        
        Returns:
            Список словарей с информацией о фразах
        """
        logger.info("[START_FUNCTION][get_all_phrases] Получение всех активных фраз")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, english_text, russian_text, difficulty
                    FROM phrases
                    WHERE is_active = 1
                    ORDER BY id
                """)
                
                results = cursor.fetchall()
                
                phrases = []
                for row in results:
                    phrase = {
                        'id': row[0],
                        'phrase': row[1],  # english_text
                        'context': row[2] if row[2] else ''  # russian_text
                    }
                    phrases.append(phrase)
                
                logger.info(f"[END_FUNCTION][get_all_phrases] Получено {len(phrases)} фраз")
                return phrases
                
        except sqlite3.Error as e:
            logger.error(f"[ERROR][get_all_phrases] Ошибка получения фраз: {e}")
            raise
    # endregion FUNCTION get_all_phrases
    
    def close(self):
        """Закрывает соединение с базой данных."""
        if self.connection:
            self.connection.close()
            logger.info("[INFO] Соединение с БД закрыто")
