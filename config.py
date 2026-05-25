import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

PAGE_SIZE = 5

CATEGORIES = {
    "beauty": {"label": "💅 Салоны красоты", "query": "салон красоты"},
    "dental": {"label": "🦷 Стоматологии", "query": "стоматология"},
    "cafe": {"label": "☕ Кафе", "query": "кафе"},
    "fitness": {"label": "🏋️ Фитнес", "query": "фитнес клуб"},
    "auto": {"label": "🔧 Автосервисы", "query": "автосервис"},
    "tutor": {"label": "📚 Репетиторы", "query": "репетитор"},
    "flowers": {"label": "💐 Цветы", "query": "цветы магазин"},
    "shop": {"label": "🛍 Магазины одежды", "query": "магазин одежды"},
}

CHAIN_BLACKLIST = {
    "spar", "лента", "магнит", "пятёрочка", "пятерочка", "перекрёсток",
    "перекресток", "ашан", "metro", "метро кэш", "окей", "о'кей", "billa",
    "карусель", "дикси", "мираторг", "красное и белое", "вкусвилл",
    "леруа мерлен", "икеа", "ozon", "вайлдберриз", "wildberries",
    "сбер", "сбербанк", "втб", "альфа", "тинькофф", "т-банк", "мтс",
    "билайн", "мегафон", "yota", "теле2", "ростелеком",
    "burger king", "kfc", "макдональдс", "вкусно и точка", "subway",
    "papa john", "papa johns", "domino", "ростикс", "крошка картошка",
    "теремок", "шоколадница", "starbucks", "костас", "кофе хауз",
    "lush", "л'этуаль", "летуаль", "рив гош", "иль де ботэ",
    "fix price", "светофор", "магнит косметик", "подружка",
    "h&m", "zara", "uniqlo", "bershka", "pull&bear", "mango",
    "decathlon", "спортмастер", "intersport",
    "м.видео", "мвидео", "эльдорадо", "ситилинк", "dns", "днс",
    "детский мир", "детмир",
    "yves rocher", "ив роше", "oriflame",
    "евросеть", "связной",
    "автомир", "автоваз", "fit service", "fit сервис",
    "shell", "лукойл", "роснефть", "газпромнефть", "газпром", "татнефть",
    "новатэк",
    "л'окситан", "loccitane",
    "samsung", "apple store", "re:store", "restore",
    "tom tailor", "gloria jeans", "глория джинс",
    "детский сад", "школа №",
}
