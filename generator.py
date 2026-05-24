import logging

from openai import AsyncOpenAI

from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    SYSTEM_PROMPT_COLD,
    SYSTEM_PROMPT_DEV,
)

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY не задан")
        _client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
    return _client


async def _generate(system_prompt: str, user_prompt: str) -> str:
    client = _get_client()
    response = await client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""


def _business_summary(biz: dict) -> str:
    lines = [f"Название: {biz.get('name', '—')}"]
    if biz.get("address"):
        lines.append(f"Адрес: {biz['address']}")
    if biz.get("phone"):
        lines.append(f"Телефон: {biz['phone']}")
    if biz.get("website"):
        lines.append(f"Сайт: {biz['website']}")
    if biz.get("vk"):
        lines.append(f"VK: {biz['vk']}")
    if biz.get("telegram"):
        lines.append(f"Telegram: {biz['telegram']}")
    if biz.get("category_label"):
        lines.append(f"Категория: {biz['category_label']}")
    return "\n".join(lines)


async def generate_vk_message(biz: dict) -> str:
    prompt = (
        "Напиши короткое холодное сообщение во ВКонтакте для этого бизнеса. "
        "Я IT-фрилансер из Тулы, делаю сайты, чат-ботов и автоматизацию. "
        "Максимум 4 предложения, живо, без шаблонов.\n\n"
        f"Данные бизнеса:\n{_business_summary(biz)}"
    )
    return await _generate(SYSTEM_PROMPT_COLD, prompt)


async def generate_telegram_message(biz: dict) -> str:
    prompt = (
        "Напиши короткое холодное сообщение в Telegram для этого бизнеса. "
        "Я IT-фрилансер из Тулы, делаю сайты, чат-ботов и автоматизацию. "
        "Максимум 4 предложения, живо, без шаблонов.\n\n"
        f"Данные бизнеса:\n{_business_summary(biz)}"
    )
    return await _generate(SYSTEM_PROMPT_COLD, prompt)


async def generate_call_script(biz: dict) -> str:
    prompt = (
        "Напиши скрипт холодного звонка для этого бизнеса. "
        "Ровно 5 предложений: вступление, суть, вопрос. "
        "Я IT-фрилансер из Тулы, делаю сайты, чат-ботов и автоматизацию.\n\n"
        f"Данные бизнеса:\n{_business_summary(biz)}"
    )
    return await _generate(SYSTEM_PROMPT_COLD, prompt)


async def generate_bot_prompt(biz: dict) -> str:
    prompt = (
        "Сгенерируй детальный промпт для разработки Telegram-бота "
        "под этот конкретный бизнес. Стек: Python 3.11 + aiogram 3.x + SQLite. "
        "Включи все данные о бизнесе, продумай функции, которые ему реально "
        "нужны (запись, меню, акции, поддержка и т.п.), и опиши техническое "
        "задание подробно. Результат — готовый промпт для другого LLM, "
        "который сразу напишет код без доработок.\n\n"
        f"Данные бизнеса:\n{_business_summary(biz)}"
    )
    return await _generate(SYSTEM_PROMPT_DEV, prompt)


async def generate_site_prompt(biz: dict) -> str:
    prompt = (
        "Сгенерируй детальный промпт для разработки сайта-визитки "
        "(один HTML файл, инлайн CSS/JS) под этот конкретный бизнес. "
        "Включи все данные о бизнесе, продумай разделы (hero, услуги, "
        "цены, отзывы, контакты, форма заявки), дизайн и стек. "
        "Результат — готовый промпт для другого LLM, который сразу "
        "напишет HTML без доработок.\n\n"
        f"Данные бизнеса:\n{_business_summary(biz)}"
    )
    return await _generate(SYSTEM_PROMPT_DEV, prompt)
