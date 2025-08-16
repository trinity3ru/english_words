"""
Скрипт для миграции базы данных с добавлением новых столбцов для системы прогресса.
"""

import sqlite3
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Мигрирует базу данных, добавляя новые столбцы для системы прогресса."""
    db_path = "english_learning.db"
    
    print("🔄 Начинаем миграцию базы данных...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Проверяем существующие столбцы в таблице phrases
            cursor.execute("PRAGMA table_info(phrases)")
            columns = [column[1] for column in cursor.fetchall()]
            print(f"📋 Существующие столбцы: {columns}")
            
            # Добавляем столбец is_learned если его нет
            if 'is_learned' not in columns:
                print("➕ Добавляем столбец 'is_learned'...")
                cursor.execute("ALTER TABLE phrases ADD COLUMN is_learned BOOLEAN DEFAULT 0")
                print("✅ Столбец 'is_learned' добавлен")
            else:
                print("✅ Столбец 'is_learned' уже существует")
            
            # Добавляем столбец total_progress_score если его нет
            if 'total_progress_score' not in columns:
                print("➕ Добавляем столбец 'total_progress_score'...")
                cursor.execute("ALTER TABLE phrases ADD COLUMN total_progress_score REAL DEFAULT 0.0")
                print("✅ Столбец 'total_progress_score' добавлен")
            else:
                print("✅ Столбец 'total_progress_score' уже существует")
            
            # Обновляем существующие записи
            print("🔄 Обновляем существующие записи...")
            
            # Устанавливаем is_learned = 0 для всех существующих фраз
            cursor.execute("UPDATE phrases SET is_learned = 0 WHERE is_learned IS NULL")
            
            # Устанавливаем total_progress_score = 0.0 для всех существующих фраз
            cursor.execute("UPDATE phrases SET total_progress_score = 0.0 WHERE total_progress_score IS NULL")
            
            # Получаем количество обновленных записей
            updated_rows = cursor.rowcount
            print(f"✅ Обновлено {updated_rows} записей")
            
            # Проверяем финальную структуру
            cursor.execute("PRAGMA table_info(phrases)")
            final_columns = [column[1] for column in cursor.fetchall()]
            print(f"📋 Финальная структура таблицы: {final_columns}")
            
            # Получаем статистику
            cursor.execute("SELECT COUNT(*) FROM phrases")
            total_phrases = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM phrases WHERE is_learned = 1")
            learned_phrases = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM phrases WHERE is_learned = 0")
            active_phrases = cursor.fetchone()[0]
            
            print(f"\n📊 Статистика после миграции:")
            print(f"  Всего фраз: {total_phrases}")
            print(f"  Изучено: {learned_phrases}")
            print(f"  Активно изучается: {active_phrases}")
            
            conn.commit()
            print("✅ Миграция завершена успешно!")
            
    except sqlite3.Error as e:
        print(f"❌ Ошибка миграции: {e}")
        raise
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        raise

if __name__ == "__main__":
    migrate_database()
