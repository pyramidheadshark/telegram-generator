"""LLM-based declension service for job titles via OpenRouter API."""

import os
import time
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_declension_cache: dict[str, str] = {}


def decline_job_title_llm(position: str) -> str:
    if not position:
        return ""
    
    if position in _declension_cache:
        return _declension_cache[position]
    
    if not OPENROUTER_API_KEY:
        return _fallback_decline(position)
    
    prompt = f"""Поставь должность в дательный падеж. Ответь ТОЛЬКО результатом, без объяснений.

Примеры:
- Министр → Министру
- Директор департамента → Директору департамента
- Заместитель Председателя Правительства → Заместителю Председателя Правительства
- Министр финансов Российской Федерации → Министру финансов Российской Федерации
- Директор департамента национальной платёжной системы → Директору департамента национальной платёжной системы
- Руководитель Федеральной службы → Руководителю Федеральной службы

Должность: {position}
Ответ:"""

    # Try up to 3 times with exponential backoff
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://telegram-generator.ru.tuna.am",
                        "X-Title": "Telegram Generator",
                    },
                    json={
                        "model": "openai/gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 100,
                        "temperature": 0.0,
                    },
                )
                
                if response.status_code == 429:
                    # Rate limited - wait and retry
                    time.sleep(2 ** attempt)
                    continue
                    
                response.raise_for_status()
                data = response.json()
                
                result = data["choices"][0]["message"]["content"].strip().strip('"\'')
                _declension_cache[position] = result
                
                return result
                
        except httpx.TimeoutException:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            print(f"LLM declension timeout after {attempt + 1} attempts")
            return _fallback_decline(position)
            
        except Exception as e:
            print(f"LLM declension error: {e}")
            return _fallback_decline(position)
    
    return _fallback_decline(position)


def _fallback_decline(position: str) -> str:
    """Simple fallback for common positions when LLM unavailable."""
    if not position:
        return ""
    
    common_positions = {
        "министр": "министру",
        "директор": "директору",
        "заместитель": "заместителю",
        "руководитель": "руководителю",
        "председатель": "председателю",
        "начальник": "начальнику",
        "первый заместитель": "первому заместителю",
    }
    
    position_lower = position.lower()
    for nom, dat in common_positions.items():
        if position_lower == nom:
            if position.isupper():
                return dat.upper()
            elif position[0].isupper():
                return dat.capitalize()
            return dat
    
    return position


def clear_cache() -> None:
    """Clear the declension cache."""
    global _declension_cache
    _declension_cache = {}
