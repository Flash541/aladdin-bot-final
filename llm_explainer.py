# llm_explainer.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None

def get_explanation(context: dict) -> str:
    """Генерирует человекопонятное объяснение на основе контекста анализа."""
    if not client:
        return "Explanation feature is unavailable (OpenAI API key is missing)."

    # --- Собираем промпт для GPT ---
    system_prompt = (
        "You are Aladdin, a professional crypto trading analyst. Your task is to explain the rationale "
        "behind a trade signal in a clear, structured, and educational manner. "
        "Explain the contributing factors. Be neutral and objective. "
        "NEVER promise profits or give direct financial advice. Always include a disclaimer."
    )
    
    # Формируем текст на основе контекста
    user_prompt_parts = [
        f"The analysis for this chart resulted in a '{context.get('final_view', 'N/A')}' view. Here are the key factors my engine considered:\n"
    ]
    if 'trend' in context:
        user_prompt_parts.append(f"- **Trend:** The short-term trend is currently **{context['trend']}**.")
    if 'rsi' in context:
        user_prompt_parts.append(f"- **Momentum (RSI):** The RSI is at **{context['rsi']}**. Values above 55 suggest bullish momentum, while values below 45 suggest bearish momentum.")
    if 'volume' in context:
        user_prompt_parts.append(f"- **Volume:** Trading volume is currently **{context['volume']}** compared to the recent average.")
    if 'news_score' in context and context['news_score'] != 0:
        news_sentiment = "Positive" if context['news_score'] > 0 else "Negative"
        user_prompt_parts.append(f"- **News Sentiment:** The recent news background is generally **{news_sentiment}** (Score: {context['news_score']:.2f}).")

    user_prompt_parts.append("\nPlease synthesize these factors into a 2-paragraph explanation. Start with a summary of the signal, then detail the reasons. Conclude with a risk warning.")
    
    user_prompt = "\n".join(user_prompt_parts)

    try:
        print("--- Sending context to OpenAI for explanation ---")
        completion = client.chat.completions.create(
            model="gpt-4o", # Используем более умную модель для качественных текстов
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5
        )
        explanation = completion.choices[0].message.content
        return explanation
    except Exception as e:
        print(f"Error getting explanation from LLM: {e}")
        return "An error occurred while generating the explanation."