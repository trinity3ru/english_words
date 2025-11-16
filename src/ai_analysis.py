"""
Модуль для AI-анализа ответов пользователей на английские фразы.

Использует OpenAI API для оценки качества ответов и определения баллов.
Система баллов: 0.0-1.0 с шагом 0.1 (11-балльная шкала).

ВАЖНО: Система оценки сфокусирована на понимании СМЫСЛА фразы, а не на грамматике.
Грамматические и пунктуационные ошибки НЕ влияют на оценку - цель запомнить фразу.

Приоритеты оценки:
- Понимание смысла (60% веса) - ГЛАВНОЕ!
- Точность перевода ключевых слов (30% веса)
- Стилистические различия (10% веса) - синонимы допустимы
- Грамматика (0% веса) - НЕ влияет на оценку
- Пунктуация (0% веса) - НЕ влияет на оценку
"""

import os
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# Загружаем переменные окружения
load_dotenv()

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# region Константы системы баллов
SCORE_LEVELS = {
    0.0: "неправильно",
    0.1: "очень плохо",
    0.2: "плохо", 
    0.3: "почти неправильно",
    0.4: "слабо",
    0.5: "частично правильно",
    0.6: "неплохо",
    0.7: "почти правильно",
    0.8: "хорошо",
    0.9: "очень хорошо",
    1.0: "правильно"
}

# Весовые коэффициенты для разных типов ошибок
# ВАЖНО: Грамматика и пунктуация НЕ влияют на оценку - цель запомнить фразу, а не писать идеально
ERROR_WEIGHTS = {
    'meaning': 0.6,      # Потеря смысла - самый важный фактор (увеличено)
    'key_words': 0.3,    # Неправильный перевод ключевых слов
    'grammar': 0.0,      # Грамматические ошибки НЕ влияют на оценку
    'punctuation': 0.0,  # Пунктуация НЕ влияет на оценку
    'style': 0.1         # Стилистические различия (синонимы допустимы)
}

# Пороги для мягкой нормализации
SOFT_THRESHOLDS = {
    0.0: (0.0, 0.1),     # 0.0-0.1 → 0.0
    0.1: (0.11, 0.2),    # 0.11-0.2 → 0.1
    0.2: (0.21, 0.3),    # 0.21-0.3 → 0.2
    0.3: (0.31, 0.4),    # 0.31-0.4 → 0.3
    0.4: (0.41, 0.5),    # 0.41-0.5 → 0.4
    0.5: (0.51, 0.6),    # 0.51-0.6 → 0.5
    0.6: (0.61, 0.7),    # 0.61-0.7 → 0.6
    0.7: (0.71, 0.8),    # 0.71-0.8 → 0.7
    0.8: (0.81, 0.9),    # 0.81-0.9 → 0.8
    0.9: (0.91, 0.95),   # 0.91-0.95 → 0.9
    1.0: (0.96, 1.0)     # 0.96-1.0 → 1.0
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
        
        # Создаем клиент OpenAI один раз при инициализации
        self.client = OpenAI(api_key=self.api_key)
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
            
            # Отправляем запрос к OpenAI (используем клиент из __init__)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Более стабильная и мягкая оценка
                max_tokens=500
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
            
            # Отправляем запрос к OpenAI (используем клиент из __init__)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_reverse_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Более стабильная и мягкая оценка
                max_tokens=500
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
ВАЖНО: Используй мягкую систему оценки с фокусом на понимание СМЫСЛА фразы.

ЦЕЛЬ ОЦЕНКИ: Проверить, запомнил ли человек фразу и понял ли её смысл.
ГРАММАТИКА И ПУНКТУАЦИЯ НЕ ВЛИЯЮТ НА ОЦЕНКУ - это не экзамен по грамматике!

Оцени ответ по 11-балльной шкале (0.0-1.0 с шагом 0.1):
- 0.0: Полностью неправильный перевод, смысл не понят
- 0.1-0.2: Очень плохо, смысл почти не понят
- 0.3-0.4: Плохо, есть серьезные ошибки в понимании
- 0.5-0.6: Частично правильно, смысл понят наполовину
- 0.7-0.8: Хорошо, смысл понят правильно
- 0.9-1.0: Отлично, смысл понят полностью (даже если есть грамматические/пунктуационные ошибки)

АНАЛИЗИРУЙ ТОЛЬКО ВАЖНЫЕ ОШИБКИ:

1. СМЫСЛОВЫЕ ОШИБКИ (вес 60% - ГЛАВНОЕ!):
   - Полная потеря смысла
   - Искажение основного значения
   - Неправильная интерпретация контекста

2. ЛЕКСИЧЕСКИЕ ОШИБКИ (вес 30%):
   - Неправильный перевод ключевых слов
   - Использование неточных синонимов (если они искажают смысл)
   - Пропуск важных слов, меняющих смысл

3. ГРАММАТИЧЕСКИЕ ОШИБКИ (вес 0% - НЕ ВЛИЯЮТ НА ОЦЕНКУ):
   - НЕ снижай балл за грамматические ошибки
   - НЕ снижай балл за неправильное время глагола
   - НЕ снижай балл за ошибки в согласовании
   - НЕ снижай балл за неправильный порядок слов
   - Указывай их в error_analysis только для информации

4. ПУНКТУАЦИОННЫЕ ОШИБКИ (вес 0% - НЕ ВЛИЯЮТ НА ОЦЕНКУ):
   - НЕ снижай балл за отсутствие точек, запятых
   - НЕ снижай балл за неправильные знаки препинания
   - Указывай их в error_analysis только для информации

5. СТИЛИСТИЧЕСКИЕ ОТЛИЧИЯ (вес 10% - допустимы):
   - Различия в стиле - это нормально
   - Использование синонимов - это хорошо
   - Естественные перефразировки - это отлично

Верни ответ в формате JSON:
{
    "score": число от 0.0 до 1.0 (с шагом 0.1),
    "feedback": "подробный комментарий о понимании смысла",
    "confidence": число от 0 до 1,
    "error_analysis": {
        "meaning_errors": ["описание смысловых ошибок"],
        "lexical_errors": ["описание лексических ошибок"],
        "grammar_errors": ["описание грамматических ошибок"],
        "punctuation_errors": ["описание пунктуационных ошибок"],
        "style_differences": ["описание стилистических отличий"]
    },
    "suggestions": ["конкретные предложения по исправлению ошибок"],
    "alternatives": ["2-3 альтернативных формулировки исходной фразы на целевом языке"],
    "usage_examples": ["1-2 коротких примера использования этой фразы в предложениях (целевой язык)"],
    "mini_dialogue": ["2-4 реплики простого диалога с использованием фразы (целевой язык)"],
    "note": "краткая заметка по употреблению, коллокациям или типичным ошибкам"
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
ВАЖНО: Используй мягкую систему оценки с фокусом на понимание СМЫСЛА фразы для перевода на английский.

ЦЕЛЬ ОЦЕНКИ: Проверить, запомнил ли человек фразу и понял ли её смысл.
ГРАММАТИКА И ПУНКТУАЦИЯ НЕ ВЛИЯЮТ НА ОЦЕНКУ - это не экзамен по грамматике!

Оцени ответ по 11-балльной шкале (0.0-1.0 с шагом 0.1):
- 0.0: Полностью неправильный перевод, смысл не понят
- 0.1-0.2: Очень плохо, смысл почти не понят
- 0.3-0.4: Плохо, есть серьезные ошибки в понимании
- 0.5-0.6: Частично правильно, смысл понят наполовину
- 0.7-0.8: Хорошо, смысл понят правильно
- 0.9-1.0: Отлично, смысл понят полностью (даже если есть грамматические/пунктуационные ошибки)

АНАЛИЗИРУЙ ТОЛЬКО ВАЖНЫЕ ОШИБКИ:

1. СМЫСЛОВЫЕ ОШИБКИ (вес 60% - ГЛАВНОЕ!):
   - Полная потеря смысла
   - Искажение основного значения
   - Неправильная интерпретация контекста

2. ЛЕКСИЧЕСКИЕ ОШИБКИ (вес 30%):
   - Неправильный перевод ключевых слов
   - Использование неточных синонимов (если они искажают смысл)
   - Пропуск важных слов, меняющих смысл

3. ГРАММАТИЧЕСКИЕ ОШИБКИ (вес 0% - НЕ ВЛИЯЮТ НА ОЦЕНКУ):
   - НЕ снижай балл за грамматические ошибки
   - НЕ снижай балл за неправильное время глагола
   - НЕ снижай балл за ошибки в согласовании
   - НЕ снижай балл за неправильный порядок слов
   - НЕ снижай балл за отсутствие артиклей (a/an/the)
   - Указывай их в error_analysis только для информации

4. ПУНКТУАЦИОННЫЕ ОШИБКИ (вес 0% - НЕ ВЛИЯЮТ НА ОЦЕНКУ):
   - НЕ снижай балл за отсутствие точек, запятых
   - НЕ снижай балл за неправильные знаки препинания
   - Указывай их в error_analysis только для информации

5. СТИЛИСТИЧЕСКИЕ ОТЛИЧИЯ (вес 10% - допустимы):
   - Различия в стиле - это нормально
   - Использование синонимов - это хорошо
   - Естественные перефразировки - это отлично

Верни ответ в формате JSON:
{
    "score": число от 0.0 до 1.0 (с шагом 0.1),
    "feedback": "подробный комментарий о понимании смысла",
    "confidence": число от 0 до 1,
    "error_analysis": {
        "meaning_errors": ["описание смысловых ошибок"],
        "lexical_errors": ["описание лексических ошибок"],
        "grammar_errors": ["описание грамматических ошибок"],
        "punctuation_errors": ["описание пунктуационных ошибок"],
        "style_differences": ["описание стилистических отличий"]
    },
    "suggestions": ["конкретные предложения по исправлению ошибок"],
    "alternatives": ["2-3 альтернативных способа выразить мысль (англ.)"],
    "usage_examples": ["1-2 коротких примера на англ."],
    "mini_dialogue": ["2-4 реплики на англ."],
    "note": "краткая заметка по употреблению"
}
"""
        return prompt
    
    def _get_system_prompt(self) -> str:
        """Возвращает системный промпт для OpenAI."""
        return """Ты - эксперт по английскому языку, который анализирует ответы студентов на перевод фраз.

Твоя главная задача - оценить, насколько правильно студент понял СМЫСЛ фразы и запомнил её.

ВАЖНО: Цель обучения - ЗАПОМНИТЬ фразу, а не писать идеально грамматически.
ГРАММАТИКА И ПУНКТУАЦИЯ НЕ ВЛИЯЮТ НА ОЦЕНКУ - это не экзамен по грамматике!

ПРИОРИТЕТЫ ОЦЕНКИ (по важности):
1. Понимание основного смысла фразы (60% веса) - ГЛАВНОЕ!
2. Точность перевода ключевых слов (30% веса)
3. Стилистические различия (10% веса) - синонимы допустимы
4. Грамматическая корректность (0% веса) - НЕ влияет на оценку
5. Пунктуация (0% веса) - НЕ влияет на оценку

ИСПОЛЬЗУЙ 11-БАЛЛЬНУЮ ШКАЛУ (0.0-1.0 с шагом 0.1):
- 0.0-0.2: Серьезные ошибки в понимании смысла
- 0.3-0.4: Частичное понимание с ошибками
- 0.5-0.6: Смысл понят наполовину
- 0.7-0.8: Хорошее понимание (даже с грамматическими ошибками)
- 0.9-1.0: Отличное понимание (даже с грамматическими ошибками)

АНАЛИЗИРУЙ ТОЛЬКО ВАЖНЫЕ ОШИБКИ:
- Смысловые ошибки: полная потеря или искажение смысла - ВАЖНО!
- Лексические ошибки: неправильный перевод ключевых слов - ВАЖНО!
- Грамматические ошибки: НЕ снижай балл, только указывай в error_analysis для информации
- Пунктуационные ошибки: НЕ снижай балл, только указывай в error_analysis для информации
- Стилистические отличия: синонимы и перефразировки - это хорошо!

БУДЬ МЯГКИМ И СПРАВЕДЛИВЫМ:
- Если смысл понят правильно, ставь высокий балл (0.8-1.0) даже с грамматическими ошибками
- За похожие переводы снижай балл минимально (0.1-0.2)
- За ошибку в 1 слове снижай балл умеренно (0.2-0.3)
- НЕ снижай балл за отсутствие точки, запятой, неправильное время глагола
- НЕ снижай балл за грамматические ошибки - цель запомнить фразу, а не писать идеально

Давай конкретные советы по исправлению ошибок, а не общие рекомендации."""
    
    def _get_reverse_system_prompt(self) -> str:
        """Возвращает системный промпт для обратного анализа."""
        return """Ты - эксперт по английскому языку, который анализирует ответы студентов на перевод фраз с русского на английский.

Твоя главная задача - оценить, насколько правильно студент понял СМЫСЛ фразы и запомнил её.

ВАЖНО: Цель обучения - ЗАПОМНИТЬ фразу, а не писать идеально грамматически.
ГРАММАТИКА И ПУНКТУАЦИЯ НЕ ВЛИЯЮТ НА ОЦЕНКУ - это не экзамен по грамматике!

ПРИОРИТЕТЫ ОЦЕНКИ (по важности):
1. Понимание основного смысла фразы (60% веса) - ГЛАВНОЕ!
2. Точность перевода ключевых слов (30% веса)
3. Стилистические различия (10% веса) - синонимы допустимы
4. Грамматическая корректность (0% веса) - НЕ влияет на оценку
5. Пунктуация (0% веса) - НЕ влияет на оценку

ИСПОЛЬЗУЙ 11-БАЛЛЬНУЮ ШКАЛУ (0.0-1.0 с шагом 0.1):
- 0.0-0.2: Серьезные ошибки в понимании смысла
- 0.3-0.4: Частичное понимание с ошибками
- 0.5-0.6: Смысл понят наполовину
- 0.7-0.8: Хорошее понимание (даже с грамматическими ошибками)
- 0.9-1.0: Отличное понимание (даже с грамматическими ошибками)

АНАЛИЗИРУЙ ТОЛЬКО ВАЖНЫЕ ОШИБКИ:
- Смысловые ошибки: полная потеря или искажение смысла - ВАЖНО!
- Лексические ошибки: неправильный перевод ключевых слов - ВАЖНО!
- Грамматические ошибки: НЕ снижай балл, только указывай в error_analysis для информации
- Пунктуационные ошибки: НЕ снижай балл, только указывай в error_analysis для информации
- Стилистические отличия: синонимы и перефразировки - это хорошо!

БУДЬ МЯГКИМ И СПРАВЕДЛИВЫМ:
- Если смысл понят правильно, ставь высокий балл (0.8-1.0) даже с грамматическими ошибками
- За похожие переводы снижай балл минимально (0.1-0.2)
- За ошибку в 1 слове снижай балл умеренно (0.2-0.3)
- НЕ снижай балл за отсутствие точки, запятой, неправильное время глагола
- НЕ снижай балл за отсутствие артиклей (a/an/the)
- НЕ снижай балл за грамматические ошибки - цель запомнить фразу, а не писать идеально

Давай конкретные советы по исправлению ошибок, а не общие рекомендации."""
    
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
                    'error_analysis': result.get('error_analysis', {
                        'meaning_errors': [],
                        'lexical_errors': [],
                        'grammar_errors': [],
                        'punctuation_errors': [],
                        'style_differences': []
                    }),
                    'suggestions': result.get('suggestions', []),
                    'alternatives': result.get('alternatives', [])[:3],
                    'usage_examples': result.get('usage_examples', [])[:2],
                    'mini_dialogue': result.get('mini_dialogue', [])[:4],
                    'note': result.get('note', '').strip()
                }
            else:
                raise ValueError("JSON не найден в ответе")
                
        except Exception as e:
            logger.warning(f"Ошибка парсинга ответа AI: {e}")
            return self._get_fallback_analysis("", "")
    
    def _normalize_score(self, score: float) -> float:
        """
        Нормализует score к ближайшему допустимому значению с мягкой системой.
        
        Args:
            score: Исходный score от AI (0.0-1.0)
            
        Returns:
            Нормализованный score (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
        """
        logger.info(f"[START_FUNCTION][_normalize_score] Нормализация score: {score}")
        
        # Проверяем, является ли score уже допустимым значением
        if score in SCORE_LEVELS:
            logger.info(f"[_normalize_score] Score {score} уже в допустимых значениях")
            return score
        
        # Используем мягкие пороговые диапазоны для нормализации
        for normalized_score, (min_val, max_val) in SOFT_THRESHOLDS.items():
            if min_val <= score <= max_val:
                logger.info(f"[_normalize_score] Score {score} нормализован к {normalized_score} ({SCORE_LEVELS[normalized_score]})")
                logger.info(f"[END_FUNCTION][_normalize_score] Результат: {normalized_score}")
                return normalized_score
        
        # Если score выходит за пределы (0.0-1.0), ограничиваем
        if score < 0.0:
            logger.warning(f"[_normalize_score] Score {score} меньше 0, устанавливаем 0.0")
            return 0.0
        elif score > 1.0:
            logger.warning(f"[_normalize_score] Score {score} больше 1, устанавливаем 1.0")
            return 1.0
        
        # Fallback (не должно происходить)
        logger.warning(f"[_normalize_score] Неожиданный score {score}, возвращаем 0.5")
        return 0.5
    
    def _get_fallback_analysis(self, user_answer: str, correct_answer: str) -> Dict[str, any]:
        """Возвращает улучшенную оценку в случае ошибки AI."""
        user_lower = user_answer.lower().strip()
        correct_lower = correct_answer.lower().strip()
        
        # Улучшенный анализ
        if user_lower == correct_lower:
            score = 1.0
            feedback = "Правильный перевод!"
            error_analysis = {
                'meaning_errors': [],
                'lexical_errors': [],
                'grammar_errors': [],
                'punctuation_errors': [],
                'style_differences': []
            }
        else:
            # Анализируем различия
            user_words = set(user_lower.split())
            correct_words = set(correct_lower.split())
            
            common_words = user_words.intersection(correct_words)
            total_words = len(correct_words)
            common_ratio = len(common_words) / total_words if total_words > 0 else 0
            
            # Определяем тип ошибок
            meaning_errors = []
            lexical_errors = []
            grammar_errors = []  # Только для информации, не влияет на оценку
            punctuation_errors = []  # Только для информации, не влияет на оценку
            style_differences = []
            
            # Пунктуация НЕ влияет на оценку - только для информации
            # (убрана проверка пунктуации)
            
            # Проверяем лексические различия
            if common_ratio < 0.5:
                meaning_errors.append("Значительные различия в понимании смысла")
            elif common_ratio < 0.8:
                lexical_errors.append("Некоторые ключевые слова переведены неправильно")
            else:
                style_differences.append("Незначительные стилистические различия")
            
            # Определяем балл на основе анализа
            if common_ratio >= 0.9:
                score = 0.9
                feedback = "Отличный перевод с незначительными отличиями"
            elif common_ratio >= 0.7:
                score = 0.7
                feedback = "Хороший перевод с небольшими ошибками"
            elif common_ratio >= 0.5:
                score = 0.5
                feedback = "Частично правильный перевод"
            elif common_ratio >= 0.3:
                score = 0.3
                feedback = "Перевод с серьезными ошибками"
            else:
                score = 0.1
                feedback = "Неправильный перевод"
            
            error_analysis = {
                'meaning_errors': meaning_errors,
                'lexical_errors': lexical_errors,
                'grammar_errors': grammar_errors,
                'punctuation_errors': punctuation_errors,
                'style_differences': style_differences
            }
        
        return {
            'score': score,
            'feedback': feedback,
            'confidence': 0.6,
            'error_analysis': error_analysis,
            'suggestions': ['Проверьте правильность перевода'],
            'alternatives': [],
            'usage_examples': [],
            'mini_dialogue': [],
            'note': ''
        }
    
    def _get_fallback_reverse_analysis(self, user_answer: str, correct_answer: str) -> Dict[str, any]:
        """Возвращает улучшенную оценку в случае ошибки AI для обратного анализа."""
        user_lower = user_answer.lower().strip()
        correct_lower = correct_answer.lower().strip()
        
        # Улучшенный анализ для английского языка
        if user_lower == correct_lower:
            score = 1.0
            feedback = "Правильный перевод!"
            error_analysis = {
                'meaning_errors': [],
                'lexical_errors': [],
                'grammar_errors': [],
                'punctuation_errors': [],
                'style_differences': []
            }
        else:
            # Анализируем различия
            user_words = set(user_lower.split())
            correct_words = set(correct_lower.split())
            
            common_words = user_words.intersection(correct_words)
            total_words = len(correct_words)
            common_ratio = len(common_words) / total_words if total_words > 0 else 0
            
            # Определяем тип ошибок
            meaning_errors = []
            lexical_errors = []
            grammar_errors = []  # Только для информации, не влияет на оценку
            punctuation_errors = []  # Только для информации, не влияет на оценку
            style_differences = []
            
            # Грамматика НЕ влияет на оценку - только для информации
            # (убрана проверка артиклей)
            
            # Пунктуация НЕ влияет на оценку - только для информации
            # (убрана проверка пунктуации)
            
            # Проверяем лексические различия
            if common_ratio < 0.5:
                meaning_errors.append("Значительные различия в понимании смысла")
            elif common_ratio < 0.8:
                lexical_errors.append("Некоторые ключевые слова переведены неправильно")
            else:
                style_differences.append("Незначительные стилистические различия")
            
            # Определяем балл на основе анализа
            if common_ratio >= 0.9:
                score = 0.9
                feedback = "Отличный перевод с незначительными отличиями"
            elif common_ratio >= 0.7:
                score = 0.7
                feedback = "Хороший перевод с небольшими ошибками"
            elif common_ratio >= 0.5:
                score = 0.5
                feedback = "Частично правильный перевод"
            elif common_ratio >= 0.3:
                score = 0.3
                feedback = "Перевод с серьезными ошибками"
            else:
                score = 0.1
                feedback = "Неправильный перевод"
            
            error_analysis = {
                'meaning_errors': meaning_errors,
                'lexical_errors': lexical_errors,
                'grammar_errors': grammar_errors,
                'punctuation_errors': punctuation_errors,
                'style_differences': style_differences
            }
        
        return {
            'score': score,
            'feedback': feedback,
            'confidence': 0.6,
            'error_analysis': error_analysis,
            'suggestions': ['Проверьте правильность перевода'],
            'alternatives': [],
            'usage_examples': [],
            'mini_dialogue': [],
            'note': ''
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
            
            # Используем клиент из __init__
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты - опытный преподаватель английского языка."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
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
            # Используем клиент из __init__
            response = self.client.chat.completions.create(
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
