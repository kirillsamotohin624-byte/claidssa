import logging

from openai import AsyncOpenAI

from config import OPENROUTER_API_KEY

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


SALES_SYSTEM_PROMPT = (
    "Ты опытный продажник для IT-фрилансера из Тулы. Пиши короткие живые сообщения "
    "для малого бизнеса. Без шаблонных фраз. Без \"Здравствуйте меня зовут\". "
    "Сразу к боли бизнеса. Для VK и Telegram — максимум 4 предложения. "
    "Для звонка — скрипт из 5 предложений: вступление, суть, вопрос."
)

DEV_SYSTEM_PROMPT = (
    "Ты опытный разработчик. Генерируй детальные промпты для создания "
    "Telegram-ботов (Python + aiogram 3.x + SQLite) и сайтов-визиток (один HTML файл). "
    "Промпт должен содержать все данные о бизнесе, полный список функций "
    "и технический стек. Код на выходе должен быть готов к запуску без доработок."
)

MODEL = "deepseek/deepseek-chat"


async def _chat(system: str, user: str) -> str:
    client = _get_client()
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def _business_brief(business: dict) -> str:
    parts = [
        f"Название: {business.get('name', '—')}",
        f"Категория: {', '.join(business.get('rubrics') or []) or '—'}",
        f"Адрес: {business.get('address', '—')}",
    ]
    phones = business.get("phones") or []
    if phones:
        parts.append(f"Телефоны: {', '.join(phones)}")
    if business.get("website"):
        parts.append(f"Сайт: {business['website']}")
    if business.get("vk"):
        parts.append(f"VK: {business['vk']}")
    if business.get("telegram"):
        parts.append(f"Telegram: {business['telegram']}")
    return "\n".join(parts)


async def gen_vk_message(business: dict) -> str:
    prompt = (
        "Напиши холодное сообщение для ВКонтакте этому бизнесу. "
        "Я — IT-фрилансер из Тулы, делаю Telegram-ботов и сайты-визитки. "
        "Цель — заинтересовать на бесплатный созвон. Максимум 4 предложения, "
        "обращение на 'вы', без приветствий-шаблонов, сразу про конкретную пользу для них.\n\n"
        f"Данные бизнеса:\n{_business_brief(business)}"
    )
    return await _chat(SALES_SYSTEM_PROMPT, prompt)


async def gen_telegram_message(business: dict) -> str:
    prompt = (
        "Напиши холодное сообщение в Telegram этому бизнесу. "
        "Я — IT-фрилансер из Тулы, делаю Telegram-ботов и сайты-визитки. "
        "Чуть более неформально чем для VK. Максимум 4 предложения. "
        "Без шаблонных приветствий, сразу к делу — что им это даст.\n\n"
        f"Данные бизнеса:\n{_business_brief(business)}"
    )
    return await _chat(SALES_SYSTEM_PROMPT, prompt)


async def gen_call_script(business: dict) -> str:
    prompt = (
        "Напиши скрипт холодного звонка владельцу или администратору. "
        "Я — IT-фрилансер из Тулы, делаю Telegram-ботов и сайты-визитки. "
        "Ровно 5 предложений: 1) вступление с именем, 2) откуда взял контакт, "
        "3) суть предложения с конкретной выгодой именно для них, "
        "4) короткий пример что я могу сделать, 5) вопрос-закрытие "
        "(удобно ли обсудить 5 минут).\n\n"
        f"Данные бизнеса:\n{_business_brief(business)}"
    )
    return await _chat(SALES_SYSTEM_PROMPT, prompt)


async def gen_bot_prompt(business: dict) -> str:
    prompt = (
        "Сгенерируй очень подробный промпт для нейросети, по которому она напишет "
        "готовый к запуску Telegram-бот для этого бизнеса. "
        "Стек: Python 3.11, aiogram 3.x, SQLite, python-dotenv. "
        "В промпте обязательно: данные бизнеса, целевая аудитория, полный список фич "
        "(меню, услуги, цены, запись, FAQ, контакты, админ-уведомления), "
        "структура БД, структура файлов проекта, обработка ошибок, .env переменные, "
        "инструкция по деплою на Railway. Промпт должен быть таким, чтобы по нему "
        "код запускался без правок.\n\n"
        f"Данные бизнеса:\n{_business_brief(business)}"
    )
    return await _chat(DEV_SYSTEM_PROMPT, prompt)


async def gen_site_prompt(business: dict) -> str:
    prompt = (
        "Сгенерируй очень подробный промпт для нейросети, по которому она напишет "
        "готовый сайт-визитку этого бизнеса в виде ОДНОГО index.html файла "
        "(HTML + встроенный CSS + минимальный JS, без бэкенда). "
        "В промпте обязательно: данные бизнеса, целевая аудитория, "
        "структура секций (hero, услуги, преимущества, отзывы, контакты, форма заявки), "
        "цветовая палитра под нишу, мобильная адаптивность, SEO-теги, "
        "Open Graph, favicon-заглушка, плавный скролл, кнопки соцсетей, "
        "ссылка на 2ГИС-карту. Сайт должен открываться двойным кликом без сборки.\n\n"
        f"Данные бизнеса:\n{_business_brief(business)}"
    )
    return await _chat(DEV_SYSTEM_PROMPT, prompt)
