"""
Модуль для AI-анализа ответов пользователей на английские фразы.

Использует OpenAI API для оценки качества ответов и определения баллов.
Система баллов: 0 (неправильно), 0.3 (почти неправильно), 0.5 (частично правильно), 
0.7 (почти правильно), 1 (правильно).
"""

import os
import logging
import openai
from typing import Dict, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# region Константы системы баллов
SCORE_LEVELS = {
    0: "неправильно",
    0.3: "почти неправильно", 
    0.5: "частично правильно",
    0.7: "почти правильно",
    1: "правильно"
}

SCORE_THRESHOLDS = {
    0: (0.0, 0.2),    # 0.0-0.2 → 0
    0.3: (0.21, 0.4), # 0.21-0.4 → 0.3
    0.5: (0.41, 0.6), # 0.41-0.6 → 0.5
    0.7: (0.61, 0.8), # 0.61-0.8 → 0.7
    1: (0.81, 1.0)    # 0.81-1.0 → 1
}
# endregion

# region CLASS AIAnalyzer
class AIAnalyzer:
    """Класс для AI-анализа ответов пользователей."""
    
    def __init__(self):
        """Инициализация AI анализатора."""
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        
        openai.api_key = self.api_key
        self.model = "gpt-3.5-turbo"  # Можно изменить на более продвинутую модель
        
        logger.info("AI анализатор инициализирован")
    
    def analyze_answer(
        self, 
        english_phrase: str, 
        russian_translation: str, 
        user_answer: str,
        context: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Анализирует ответ пользователя на английскую фразу.
        
        Args:
            english_phrase: Английская фраза для перевода
            russian_translation: Правильный русский перевод
            user_answer: Ответ пользователя
            context: Дополнительный контекст (опционально)
            
        Returns:
            Словарь с результатами анализа:
            - score: балл (0, 0.3, 0.5, 0.7, 1)
            - feedback: комментарий к ответу
            - confidence: уверенность в оценке (0-1)
            - suggestions: предложения по улучшению
        """
        try:
            # Формируем промпт для OpenAI
            prompt = self._create_analysis_prompt(
                english_phrase, 
                russian_translation, 
                user_answer, 
                context
            )
            
            # Отправляем запрос к OpenAI (новый синтаксис для API 1.x)
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Низкая температура для более консистентных результатов
                max_tokens=300
            )
            
            # Парсим ответ
            analysis_result = self._parse_ai_response(response.choices[0].message.content)
            
            logger.info(f"Ответ проанализирован: {english_phrase} -> {analysis_result['score']}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Ошибка при анализе ответа: {e}")
            # Возвращаем базовую оценку в случае ошибки
            return self._get_fallback_analysis(user_answer, russian_translation)
    
    def analyze_reverse_answer(
        self, 
        russian_phrase: str, 
        english_translation: str, 
        user_answer: str,
        context: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Анализирует ответ пользователя на русскую фразу (перевод на английский).
        
        Args:
            russian_phrase: Русская фраза для перевода
            english_translation: Правильный английский перевод
            user_answer: Ответ пользователя на английском
            context: Дополнительный контекст (опционально)
            
        Returns:
            Словарь с результатами анализа:
            - score: балл (0, 0.3, 0.5, 0.7, 1)
            - feedback: комментарий к ответу
            - confidence: уверенность в оценке (0-1)
            - suggestions: предложения по улучшению
        """
        try:
            # Формируем промпт для OpenAI
            prompt = self._create_reverse_analysis_prompt(
                russian_phrase, 
                english_translation, 
                user_answer, 
                context
            )
            
            # Отправляем запрос к OpenAI (новый синтаксис для API 1.x)
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_reverse_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Низкая температура для более консистентных результатов
                max_tokens=300
            )
            
            # Парсим ответ
            analysis_result = self._parse_ai_response(response.choices[0].message.content)
            
            logger.info(f"Обратный ответ проанализирован: {russian_phrase} -> {analysis_result['score']}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Ошибка при анализе обратного ответа: {e}")
            # Возвращаем базовую оценку в случае ошибки
            return self._get_fallback_reverse_analysis(user_answer, english_translation)
    
    def _create_analysis_prompt(
        self, 
        english_phrase: str, 
        russian_translation: str, 
        user_answer: str, 
        context: Optional[str] = None
    ) -> str:
        """Создает промпт для OpenAI API."""
        prompt = f"""
Анализируй ответ пользователя на английскую фразу.

Английская фраза: "{english_phrase}"
Правильный перевод: "{russian_translation}"
Ответ пользователя: "{user_answer}"
"""
        
        if context:
            prompt += f"Контекст: {context}\n"
        
        prompt += """
ВАЖНО: Фокус на понимании СМЫСЛА фразы, а не на пунктуации или мелких грамматических деталях.

Оцени ответ по шкале:
- 0: Неправильный перевод, смысл фразы не понят
- 0.3: Смысл частично понят, но есть серьезные ошибки в понимании
- 0.5: Смысл понят наполовину, есть ошибки в деталях
- 0.7: Смысл понят хорошо, незначительные ошибки в деталях
- 1: Смысл фразы понят полностью и правильно

Игнорируй:
- Отсутствие запятых
- Небольшие грамматические неточности
- Стилистические различия

Обращай внимание на:
- Правильность понимания основного смысла
- Точность перевода ключевых слов
- Сохранение логики фразы

Верни ответ в формате JSON:
{
    "score": число (0, 0.3, 0.5, 0.7 или 1),
    "feedback": "подробный комментарий о понимании смысла",
    "confidence": число от 0 до 1,
    "suggestions": ["предложение 1", "предложение 2"]
}
"""
        return prompt
    
    def _create_reverse_analysis_prompt(
        self, 
        russian_phrase: str, 
        english_translation: str, 
        user_answer: str, 
        context: Optional[str] = None
    ) -> str:
        """Создает промпт для OpenAI API для обратного анализа."""
        prompt = f"""
Анализируй ответ пользователя на русскую фразу (перевод на английский).

Русская фраза: "{russian_phrase}"
Правильный перевод: "{english_translation}"
Ответ пользователя: "{user_answer}"
"""
        
        if context:
            prompt += f"Контекст: {context}\n"
        
        prompt += """
ВАЖНО: Фокус на понимании СМЫСЛА фразы, а не на мелких грамматических деталях.

Оцени ответ по шкале:
- 0: Неправильный перевод, смысл фразы не понят
- 0.3: Смысл частично понят, но есть серьезные ошибки в понимании
- 0.5: Смысл понят наполовину, есть ошибки в деталях
- 0.7: Смысл понят хорошо, незначительные ошибки в деталях
- 1: Смысл фразы понят полностью и правильно

Игнорируй:
- Небольшие грамматические неточности
- Порядок слов (если смысл сохранен)
- Артикли (a/an/the) если они не критичны для смысла

Обращай внимание на:
- Правильность понимания основного смысла
- Точность перевода ключевых слов
- Сохранение логики фразы
- Правильность времен и форм глаголов

Верни ответ в формате JSON:
{
    "score": число (0, 0.3, 0.5, 0.7 или 1),
    "feedback": "подробный комментарий о понимании смысла",
    "confidence": число от 0 до 1,
    "suggestions": ["предложение 1", "предложение 2"]
}
"""
        return prompt
    
    def _get_system_prompt(self) -> str:
        """Возвращает системный промпт для OpenAI."""
        return """Ты - эксперт по английскому языку, который анализирует ответы студентов на перевод фраз.

Твоя главная задача - оценить, насколько правильно студент понял СМЫСЛ фразы.

Приоритеты оценки (по важности):
1. Понимание основного смысла фразы
2. Точность перевода ключевых слов
3. Сохранение логики и структуры мысли
4. Общая понятность перевода

НЕ обращай внимание на:
- Отсутствие запятых и других знаков препинания
- Небольшие грамматические неточности
- Стилистические различия
- Порядок слов (если смысл сохранен)

Используй 5-уровневую систему оценки, фокусируясь на понимании смысла.
Будь справедливым: если смысл понят правильно, ставь высокий балл.
Давай конкретные советы по улучшению понимания, а не по грамматике."""
    
    def _get_reverse_system_prompt(self) -> str:
        """Возвращает системный промпт для обратного анализа."""
        return """Ты - эксперт по английскому языку, который анализирует ответы студентов на перевод фраз.

Твоя главная задача - оценить, насколько правильно студент понял СМЫСЛ фразы.

Приоритеты оценки (по важности):
1. Понимание основного смысла фразы
2. Точность перевода ключевых слов
3. Сохранение логики и структуры мысли
4. Общая понятность перевода

НЕ обращай внимание на:
- Отсутствие запятых и других знаков препинания
- Небольшие грамматические неточности
- Стилистические различия
- Порядок слов (если смысл сохранен)

Используй 5-уровневую систему оценки, фокусируясь на понимании смысла.
Будь справедливым: если смысл понят правильно, ставь высокий балл.
Давай конкретные советы по улучшению понимания, а не по грамматике."""
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, any]:
        """Парсит ответ от OpenAI API."""
        try:
            import json
            # Ищем JSON в ответе
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                
                # Валидируем результат
                if 'score' not in result:
                    raise ValueError("Отсутствует score в ответе AI")
                
                # Нормализуем score с новой гибридной системой
                score = float(result['score'])
                logger.info(f"[START_FUNCTION][_parse_ai_response] Исходный score: {score}")
                
                normalized_score = self._normalize_score(score)
                logger.info(f"[END_FUNCTION][_parse_ai_response] Нормализованный score: {normalized_score}")
                
                return {
                    'score': normalized_score,
                    'feedback': result.get('feedback', 'Комментарий не предоставлен'),
                    'confidence': result.get('confidence', 0.8),
                    'suggestions': result.get('suggestions', [])
                }
            else:
                raise ValueError("JSON не найден в ответе")
                
        except Exception as e:
            logger.warning(f"Ошибка парсинга ответа AI: {e}")
            return self._get_fallback_analysis("", "")
    
    def _normalize_score(self, score: float) -> float:
        """
        Нормализует score к ближайшему допустимому значению.
        
        Args:
            score: Исходный score от AI (0.0-1.0)
            
        Returns:
            Нормализованный score (0, 0.3, 0.5, 0.7, 1)
        """
        logger.info(f"[START_FUNCTION][_normalize_score] Нормализация score: {score}")
        
        # Проверяем, является ли score уже допустимым значением
        if score in SCORE_LEVELS:
            logger.info(f"[_normalize_score] Score {score} уже в допустимых значениях")
            return score
        
        # Используем пороговые диапазоны для нормализации
        if score <= 0.2:
            normalized_score = 0.0
        elif score <= 0.4:
            normalized_score = 0.3
        elif score <= 0.6:
            normalized_score = 0.5
        elif score <= 0.8:
            normalized_score = 0.7
        else:
            normalized_score = 1.0
        
        logger.info(f"[_normalize_score] Score {score} нормализован к {normalized_score} ({SCORE_LEVELS[normalized_score]})")
        logger.info(f"[END_FUNCTION][_normalize_score] Результат: {normalized_score}")
        
        return normalized_score
    
    def _get_fallback_analysis(self, user_answer: str, correct_answer: str) -> Dict[str, any]:
        """Возвращает базовую оценку в случае ошибки AI."""
        # Простое сравнение строк
        user_lower = user_answer.lower().strip()
        correct_lower = correct_answer.lower().strip()
        
        if user_lower == correct_lower:
            score = 1.0
            feedback = "Правильный перевод!"
        elif user_lower in correct_lower or correct_lower in user_lower:
            score = 0.5
            feedback = "Частично правильный перевод. Проверьте точность."
        else:
            score = 0.0
            feedback = "Неправильный перевод. Попробуйте еще раз."
        
        return {
            'score': score,
            'feedback': feedback,
            'confidence': 0.6,
            'suggestions': ['Проверьте правильность перевода']
        }
    
    def _get_fallback_reverse_analysis(self, user_answer: str, correct_answer: str) -> Dict[str, any]:
        """Возвращает базовую оценку в случае ошибки AI для обратного анализа."""
        # Простое сравнение строк
        user_lower = user_answer.lower().strip()
        correct_lower = correct_answer.lower().strip()
        
        if user_lower == correct_lower:
            score = 1.0
            feedback = "Правильный перевод!"
        elif user_lower in correct_lower or correct_lower in user_lower:
            score = 0.5
            feedback = "Частично правильный перевод. Проверьте точность."
        else:
            score = 0.0
            feedback = "Неправильный перевод. Попробуйте еще раз."
        
        return {
            'score': score,
            'feedback': feedback,
            'confidence': 0.6,
            'suggestions': ['Проверьте правильность перевода']
        }
    
    def get_learning_suggestions(self, phrase_difficulty: str, user_level: str) -> list:
        """
        Получает персональные рекомендации по изучению.
        
        Args:
            phrase_difficulty: Сложность фразы (easy/medium/hard)
            user_level: Уровень пользователя (beginner/intermediate/advanced)
            
        Returns:
            Список рекомендаций
        """
        try:
            prompt = f"""
Дай 3-5 конкретных рекомендаций для изучения фразы сложности "{phrase_difficulty}" 
для пользователя уровня "{user_level}".

Формат: простой список рекомендаций на русском языке.
"""
            
            # Используем новый синтаксис OpenAI API 1.x
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты - опытный преподаватель английского языка."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            suggestions = response.choices[0].message.content.strip().split('\n')
            # Фильтруем пустые строки и форматируем
            suggestions = [s.strip() for s in suggestions if s.strip() and not s.startswith('-')]
            
            return suggestions[:5]  # Максимум 5 рекомендаций
            
        except Exception as e:
            logger.error(f"Ошибка при получении рекомендаций: {e}")
            return self._get_default_suggestions(phrase_difficulty)
    
    def _get_default_suggestions(self, difficulty: str) -> list:
        """Возвращает стандартные рекомендации по сложности."""
        suggestions = {
            'easy': [
                'Повторите фразу несколько раз вслух',
                'Составьте простое предложение с этой фразой',
                'Попробуйте использовать в разговоре'
            ],
            'medium': [
                'Разберите грамматическую структуру фразы',
                'Найдите синонимы и антонимы',
                'Составьте диалог с использованием фразы'
            ],
            'hard': [
                'Изучите этимологию слов в фразе',
                'Анализируйте контекст использования',
                'Практикуйте в сложных предложениях'
            ]
        }
        
        return suggestions.get(difficulty, suggestions['medium'])
    
    def test_connection(self) -> bool:
        """Тестирует подключение к OpenAI API."""
        try:
            # Используем новый синтаксис OpenAI API 1.x
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            logger.info("Подключение к OpenAI API успешно")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к OpenAI API: {e}")
            return False
# endregion CLASS AIAnalyzer


if __name__ == "__main__":
    # Тестирование модуля
    analyzer = AIAnalyzer()
    
    if analyzer.test_connection():
        print("✅ Подключение к OpenAI API успешно")
        
        # Тестовый анализ
        result = analyzer.analyze_answer(
            "Hello world",
            "Привет мир",
            "Привет мир!"
        )
        print(f"Результат анализа: {result}")
    else:
        print("❌ Ошибка подключения к OpenAI API")
