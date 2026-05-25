import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import CATEGORIES, PAGE_SIZE
from generator import (
    gen_bot_prompt,
    gen_call_script,
    gen_site_prompt,
    gen_telegram_message,
    gen_vk_message,
)
from keyboards import (
    back_to_business_kb,
    business_actions_kb,
    businesses_kb,
    categories_kb,
    main_menu_kb,
    retry_kb,
)
from parser import collect_small_business

logger = logging.getLogger(__name__)
router = Router()

MAX_TG_LEN = 4096


class Flow(StatesGroup):
    main = State()
    pick_category = State()
    browse_list = State()
    business = State()


def _format_business_card(b: dict) -> str:
    lines = [f"<b>{b['name']}</b>"]
    if b.get("rubrics"):
        lines.append(f"🏷 {', '.join(b['rubrics'][:3])}")
    lines.append(f"📍 {b.get('address', '—')}")
    phones = b.get("phones") or []
    if phones:
        lines.append("📞 " + ", ".join(phones))
    if b.get("website"):
        lines.append(f"🌐 {b['website']}")
    if b.get("vk"):
        lines.append(f"🔵 VK: {b['vk']}")
    if b.get("telegram"):
        lines.append(f"✈️ Telegram: {b['telegram']}")
    if b.get("instagram"):
        lines.append(f"📷 Instagram: {b['instagram']}")
    return "\n".join(lines)


async def _send_long(message_or_cb, text: str, **kwargs):
    target = message_or_cb.message if isinstance(message_or_cb, CallbackQuery) else message_or_cb
    if len(text) <= MAX_TG_LEN:
        await target.answer(text, **kwargs)
        return
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= MAX_TG_LEN:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n", 0, MAX_TG_LEN)
        if cut < 1000:
            cut = MAX_TG_LEN
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
    for i, ch in enumerate(chunks):
        if i == len(chunks) - 1:
            await target.answer(ch, **kwargs)
        else:
            await target.answer(ch)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Flow.main)
    await message.answer(
        "Привет! Я помогу найти малый бизнес в Туле для холодных продаж.\n\n"
        "Нажми <b>🔍 Найти клиентов</b>, чтобы начать.",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == "🔍 Найти клиентов")
async def find_clients(message: Message, state: FSMContext):
    await state.set_state(Flow.pick_category)
    await message.answer("Выбери категорию бизнеса:", reply_markup=categories_kb())


@router.message(F.text == "ℹ️ Помощь")
async def help_msg(message: Message):
    await message.answer(
        "<b>Как пользоваться:</b>\n\n"
        "1. Жми 🔍 Найти клиентов\n"
        "2. Выбери категорию\n"
        "3. Из списка выбери бизнес\n"
        "4. Получи готовое холодное сообщение или промпт для разработки\n\n"
        "Бот ищет только малый бизнес в Туле через OpenStreetMap, сети отфильтровываются.\n"
        "Тексты генерируются ИИ через OpenRouter.",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == "⚙️ Настройки")
async def settings_msg(message: Message):
    await message.answer(
        "<b>Настройки</b>\n\n"
        "Город: Тула\n"
        "Размер страницы: 5 бизнесов\n"
        "Модель ИИ: deepseek/deepseek-chat (через OpenRouter)\n\n"
        "Изменить параметры можно в config.py и .env.",
        reply_markup=main_menu_kb(),
    )


async def _load_and_show(callback: CallbackQuery, state: FSMContext, category: str):
    meta = CATEGORIES.get(category)
    if not meta:
        await callback.answer("Неизвестная категория", show_alert=True)
        return

    await callback.message.edit_text(f"⏳ Ищу: {meta['label']}…")

    try:
        businesses = await collect_small_business(meta["query"], limit=30)
    except Exception as e:
        logger.exception("Ошибка поиска: %s", e)
        await callback.message.edit_text(
            "⚠️ Источник данных (OpenStreetMap) не отвечает. Попробуй ещё раз.",
            reply_markup=retry_kb(category),
        )
        return

    if not businesses:
        await callback.message.edit_text(
            "Ничего не нашлось по этой категории 😕",
            reply_markup=retry_kb(category),
        )
        return

    await state.update_data(
        category=category,
        businesses=businesses,
        shown=PAGE_SIZE,
    )
    await state.set_state(Flow.browse_list)

    await callback.message.edit_text(
        f"<b>{meta['label']}</b>\n"
        f"Найдено: {len(businesses)}. Выбери бизнес:",
        reply_markup=businesses_kb(businesses, PAGE_SIZE, category),
    )


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":", 1)[1]
    await callback.answer()
    await _load_and_show(callback, state, category)


@router.callback_query(F.data.startswith("more:"))
async def cb_more(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    businesses = data.get("businesses") or []
    shown = data.get("shown") or PAGE_SIZE
    category = data.get("category") or callback.data.split(":", 1)[1]

    new_shown = min(shown + PAGE_SIZE, len(businesses))
    await state.update_data(shown=new_shown)
    await callback.answer()

    meta = CATEGORIES.get(category, {"label": "Бизнес"})
    await callback.message.edit_text(
        f"<b>{meta['label']}</b>\n"
        f"Показано: {new_shown} из {len(businesses)}. Выбери бизнес:",
        reply_markup=businesses_kb(businesses, new_shown, category),
    )


@router.callback_query(F.data == "back:cats")
async def cb_back_cats(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.pick_category)
    await callback.answer()
    await callback.message.edit_text("Выбери категорию бизнеса:", reply_markup=categories_kb())


@router.callback_query(F.data == "back:list")
async def cb_back_list(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    businesses = data.get("businesses") or []
    shown = data.get("shown") or PAGE_SIZE
    category = data.get("category")
    if not businesses or not category:
        await state.set_state(Flow.pick_category)
        await callback.message.edit_text("Выбери категорию бизнеса:", reply_markup=categories_kb())
        await callback.answer()
        return

    await state.set_state(Flow.browse_list)
    meta = CATEGORIES.get(category, {"label": "Бизнес"})
    await callback.answer()
    await callback.message.edit_text(
        f"<b>{meta['label']}</b>\n"
        f"Показано: {shown} из {len(businesses)}. Выбери бизнес:",
        reply_markup=businesses_kb(businesses, shown, category),
    )


@router.callback_query(F.data.startswith("biz:"))
async def cb_business(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    businesses = data.get("businesses") or []
    if idx >= len(businesses):
        await callback.answer("Бизнес не найден", show_alert=True)
        return

    await state.set_state(Flow.business)
    await state.update_data(current_idx=idx)
    b = businesses[idx]
    await callback.answer()
    await callback.message.edit_text(
        _format_business_card(b),
        reply_markup=business_actions_kb(idx),
        disable_web_page_preview=True,
    )


ACTION_GENERATORS = {
    "vk": (gen_vk_message, "💬 <b>Сообщение для VK</b>"),
    "tg": (gen_telegram_message, "✈️ <b>Сообщение для Telegram</b>"),
    "call": (gen_call_script, "📞 <b>Скрипт звонка</b>"),
    "bot": (gen_bot_prompt, "🤖 <b>Промпт для бота</b>"),
    "site": (gen_site_prompt, "🌐 <b>Промпт для сайта</b>"),
}


@router.callback_query(F.data.startswith("act:"))
async def cb_action(callback: CallbackQuery, state: FSMContext):
    _, action, idx_str = callback.data.split(":", 2)
    idx = int(idx_str)
    data = await state.get_data()
    businesses = data.get("businesses") or []
    if idx >= len(businesses):
        await callback.answer("Бизнес не найден", show_alert=True)
        return

    gen_fn, header = ACTION_GENERATORS.get(action, (None, None))
    if gen_fn is None:
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    business = businesses[idx]
    await callback.answer("⏳ Генерирую…")

    try:
        text = await gen_fn(business)
    except Exception as e:
        logger.exception("Ошибка генерации: %s", e)
        await callback.message.answer(
            f"⚠️ Не удалось сгенерировать: {e}",
            reply_markup=back_to_business_kb(idx),
        )
        return

    full = f"{header}\n<i>{business['name']}</i>\n\n{text}"
    await _send_long(callback, full, reply_markup=back_to_business_kb(idx), disable_web_page_preview=True)


@router.message()
async def fallback(message: Message, state: FSMContext):
    await message.answer(
        "Используй кнопки внизу 👇",
        reply_markup=main_menu_kb(),
    )
