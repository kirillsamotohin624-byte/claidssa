from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import CATEGORIES

BTN_FIND = "🔍 Найти клиентов"
BTN_SETTINGS = "⚙️ Настройки"
BTN_HELP = "ℹ️ Помощь"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_FIND)],
            [KeyboardButton(text=BTN_SETTINGS), KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def categories_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, meta in CATEGORIES.items():
        builder.button(text=meta["label"], callback_data=f"cat:{key}")
    builder.adjust(2)
    return builder.as_markup()


def business_list_kb(
    businesses: list[dict],
    start: int,
    page_size: int,
    category_key: str,
    total_loaded: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    end = min(start + page_size, total_loaded)
    for i in range(start, end):
        biz = businesses[i]
        builder.button(text=biz["name"][:60], callback_data=f"biz:{i}")
    builder.adjust(1)

    nav_row = []
    if end < total_loaded or end == total_loaded:
        nav_row.append(
            InlineKeyboardButton(text="Ещё 5 →", callback_data=f"more:{end}")
        )
    nav_row.append(
        InlineKeyboardButton(text="◀️ К категориям", callback_data="back:cats")
    )
    builder.row(*nav_row)
    return builder.as_markup()


def business_actions_kb(index: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Написать в VK", callback_data=f"act:vk:{index}")
    builder.button(text="✈️ Написать в Telegram", callback_data=f"act:tg:{index}")
    builder.button(text="📞 Скрипт звонка", callback_data=f"act:call:{index}")
    builder.button(text="🤖 Промпт для бота", callback_data=f"act:bot:{index}")
    builder.button(text="🌐 Промпт для сайта", callback_data=f"act:site:{index}")
    builder.button(text="◀️ Назад к списку", callback_data="back:list")
    builder.adjust(1)
    return builder.as_markup()


def retry_kb(action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Попробовать снова", callback_data=action)
    builder.button(text="◀️ В меню", callback_data="back:cats")
    builder.adjust(1)
    return builder.as_markup()
