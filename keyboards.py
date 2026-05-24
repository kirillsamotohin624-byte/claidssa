from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import CATEGORIES, PAGE_SIZE


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти клиентов")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def categories_kb() -> InlineKeyboardMarkup:
    items = list(CATEGORIES.items())
    rows: list[list[InlineKeyboardButton]] = []
    # сетка 2 в ряд (получится 2x4 при 8 категориях)
    for i in range(0, len(items), 2):
        row = []
        for key, meta in items[i:i + 2]:
            row.append(InlineKeyboardButton(text=meta["label"], callback_data=f"cat:{key}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def businesses_kb(businesses: list[dict], shown: int, category: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, b in enumerate(businesses[:shown]):
        title = b["name"]
        if len(title) > 55:
            title = title[:54] + "…"
        rows.append([InlineKeyboardButton(text=title, callback_data=f"biz:{idx}")])

    if shown < len(businesses):
        rows.append([InlineKeyboardButton(text=f"Ещё {PAGE_SIZE} →", callback_data=f"more:{category}")])

    rows.append([InlineKeyboardButton(text="◀️ К категориям", callback_data="back:cats")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def business_actions_kb(idx: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="💬 Написать в VK", callback_data=f"act:vk:{idx}"),
            InlineKeyboardButton(text="✈️ Написать в Telegram", callback_data=f"act:tg:{idx}"),
        ],
        [
            InlineKeyboardButton(text="📞 Скрипт звонка", callback_data=f"act:call:{idx}"),
        ],
        [
            InlineKeyboardButton(text="🤖 Промпт для бота", callback_data=f"act:bot:{idx}"),
            InlineKeyboardButton(text="🌐 Промпт для сайта", callback_data=f"act:site:{idx}"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back:list"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def retry_kb(category: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"cat:{category}")],
        [InlineKeyboardButton(text="◀️ К категориям", callback_data="back:cats")],
    ])


def back_to_business_kb(idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к бизнесу", callback_data=f"biz:{idx}")],
        [InlineKeyboardButton(text="📋 К списку", callback_data="back:list")],
    ])
