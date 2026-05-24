import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import CATEGORIES, PAGE_SIZE
from generator import (
    generate_bot_prompt,
    generate_call_script,
    generate_site_prompt,
    generate_telegram_message,
    generate_vk_message,
)
from keyboards import (
    BTN_FIND,
    BTN_HELP,
    BTN_SETTINGS,
    business_actions_kb,
    business_list_kb,
    categories_kb,
    main_menu,
    retry_kb,
)
from parser import search_business

logger = logging.getLogger(__name__)
router = Router()

MAX_MSG = 4000


class Flow(StatesGroup):
    main = State()
    categories = State()
    listing = State()
    business = State()


async def _send_long(message: Message, text: str) -> None:
    if not text:
        await message.answer("Пустой ответ от модели. Попробуйте ещё раз.")
        return
    for i in range(0, len(text), MAX_MSG):
        await message.answer(text[i : i + MAX_MSG])


def _format_business(biz: dict) -> str:
    parts = [f"<b>{biz['name']}</b>"]
    if biz.get("address"):
        parts.append(f"📍 {biz['address']}")
    if biz.get("phone"):
        parts.append(f"📞 {biz['phone']}")
    if biz.get("website"):
        parts.append(f"🌐 {biz['website']}")
    if biz.get("vk"):
        parts.append(f"VK: {biz['vk']}")
    if biz.get("telegram"):
        parts.append(f"TG: {biz['telegram']}")
    return "\n".join(parts)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Flow.main)
    await message.answer(
        "Привет! Я помогу найти клиентов малого бизнеса в Туле через 2ГИС "
        "и сгенерирую под них холодные сообщения и промпты для разработки.\n\n"
        "Выбирай действие на клавиатуре ниже 👇",
        reply_markup=main_menu(),
    )


@router.message(F.text == BTN_FIND)
async def on_find(message: Message, state: FSMContext) -> None:
    await state.set_state(Flow.categories)
    await message.answer(
        "Выбери категорию малого бизнеса:",
        reply_markup=categories_kb(),
    )


@router.message(F.text == BTN_HELP)
async def on_help(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>Как пользоваться</b>\n\n"
        "1. Жми «🔍 Найти клиентов»\n"
        "2. Выбери категорию\n"
        "3. Тапай по бизнесу из списка\n"
        "4. Получай холодные сообщения и промпты для разработки\n\n"
        "Бот ищет только малый бизнес в Туле и отфильтровывает "
        "сетевые компании."
    )


@router.message(F.text == BTN_SETTINGS)
async def on_settings(message: Message) -> None:
    await message.answer(
        "⚙️ Настройки\n\n"
        "Город: Тула (фиксированно)\n"
        "Размер страницы: 5\n"
        "Модель LLM: deepseek/deepseek-chat через OpenRouter\n\n"
        "В этой версии настройки не меняются."
    )


@router.callback_query(F.data.startswith("cat:"))
async def on_category(call: CallbackQuery, state: FSMContext) -> None:
    cat_key = call.data.split(":", 1)[1]
    cat = CATEGORIES.get(cat_key)
    if not cat:
        await call.answer("Категория не найдена", show_alert=True)
        return

    await call.answer()
    await call.message.edit_text(f"Ищу: {cat['label']}…")

    try:
        businesses = await search_business(cat["query"], page=1, page_size=30)
    except Exception as e:
        logger.exception("2gis error: %s", e)
        await call.message.edit_text(
            "❌ 2ГИС не отвечает. Попробуй ещё раз.",
            reply_markup=retry_kb(f"cat:{cat_key}"),
        )
        return

    if not businesses:
        await call.message.edit_text(
            "Ничего не нашлось по этой категории. Попробуй другую.",
            reply_markup=categories_kb(),
        )
        return

    for biz in businesses:
        biz["category_label"] = cat["label"]

    await state.update_data(
        businesses=businesses,
        category_key=cat_key,
        offset=0,
    )
    await state.set_state(Flow.listing)

    await call.message.edit_text(
        f"<b>{cat['label']}</b>\nНайдено: {len(businesses)}\n\nВыбери бизнес:",
        reply_markup=business_list_kb(
            businesses, 0, PAGE_SIZE, cat_key, len(businesses)
        ),
    )


@router.callback_query(F.data.startswith("more:"))
async def on_more(call: CallbackQuery, state: FSMContext) -> None:
    start = int(call.data.split(":", 1)[1])
    data = await state.get_data()
    businesses = data.get("businesses", [])
    cat_key = data.get("category_key", "")

    if not businesses:
        await call.answer("Список пуст, начни заново", show_alert=True)
        return

    if start >= len(businesses):
        await call.answer("Больше нет результатов", show_alert=True)
        return

    await call.answer()
    await state.update_data(offset=start)

    cat = CATEGORIES.get(cat_key, {})
    label = cat.get("label", "Результаты")

    await call.message.edit_text(
        f"<b>{label}</b>\nПоказано {start + min(PAGE_SIZE, len(businesses) - start)} из {len(businesses)}\n\nВыбери бизнес:",
        reply_markup=business_list_kb(
            businesses, start, PAGE_SIZE, cat_key, len(businesses)
        ),
    )


@router.callback_query(F.data == "back:cats")
async def on_back_cats(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(Flow.categories)
    await call.message.edit_text(
        "Выбери категорию малого бизнеса:",
        reply_markup=categories_kb(),
    )


@router.callback_query(F.data == "back:list")
async def on_back_list(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    businesses = data.get("businesses", [])
    cat_key = data.get("category_key", "")
    offset = data.get("offset", 0)

    if not businesses:
        await call.answer()
        await state.set_state(Flow.categories)
        await call.message.edit_text(
            "Список пуст. Выбери категорию:",
            reply_markup=categories_kb(),
        )
        return

    await call.answer()
    await state.set_state(Flow.listing)
    cat = CATEGORIES.get(cat_key, {})
    label = cat.get("label", "Результаты")
    await call.message.edit_text(
        f"<b>{label}</b>\nНайдено: {len(businesses)}\n\nВыбери бизнес:",
        reply_markup=business_list_kb(
            businesses, offset, PAGE_SIZE, cat_key, len(businesses)
        ),
    )


@router.callback_query(F.data.startswith("biz:"))
async def on_business(call: CallbackQuery, state: FSMContext) -> None:
    idx = int(call.data.split(":", 1)[1])
    data = await state.get_data()
    businesses = data.get("businesses", [])

    if idx >= len(businesses):
        await call.answer("Бизнес не найден", show_alert=True)
        return

    biz = businesses[idx]
    await state.set_state(Flow.business)
    await state.update_data(current_index=idx)
    await call.answer()

    await call.message.edit_text(
        _format_business(biz),
        reply_markup=business_actions_kb(idx),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data.startswith("act:"))
async def on_action(call: CallbackQuery, state: FSMContext) -> None:
    _, action, idx_str = call.data.split(":", 2)
    idx = int(idx_str)
    data = await state.get_data()
    businesses = data.get("businesses", [])

    if idx >= len(businesses):
        await call.answer("Бизнес не найден", show_alert=True)
        return

    biz = businesses[idx]
    await call.answer("Генерирую…")

    try:
        if action == "vk":
            text = await generate_vk_message(biz)
            header = "💬 <b>Сообщение для VK</b>"
        elif action == "tg":
            text = await generate_telegram_message(biz)
            header = "✈️ <b>Сообщение для Telegram</b>"
        elif action == "call":
            text = await generate_call_script(biz)
            header = "📞 <b>Скрипт звонка</b>"
        elif action == "bot":
            text = await generate_bot_prompt(biz)
            header = "🤖 <b>Промпт для Telegram-бота</b>"
        elif action == "site":
            text = await generate_site_prompt(biz)
            header = "🌐 <b>Промпт для сайта</b>"
        else:
            await call.message.answer("Неизвестное действие")
            return
    except Exception as e:
        logger.exception("generation error: %s", e)
        await call.message.answer(
            "❌ Не удалось сгенерировать. Попробуй ещё раз.",
            reply_markup=business_actions_kb(idx),
        )
        return

    await call.message.answer(header)
    await _send_long(call.message, text)
    await call.message.answer(
        f"📋 Бизнес: <b>{biz['name']}</b>",
        reply_markup=business_actions_kb(idx),
    )


@router.message()
async def fallback(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Пользуйся кнопками ниже 👇",
        reply_markup=main_menu(),
    )
