# Tula Smallbiz Bot

Telegram-бот для поиска клиентов малого бизнеса в Туле. Парсит 2ГИС, фильтрует сетевые компании и генерирует холодные сообщения и промпты на разработку через OpenRouter (deepseek/deepseek-chat).

## Возможности

- 🔍 Поиск малого бизнеса по 8 категориям: салоны красоты, стоматологии, кафе, фитнес, автосервисы, репетиторы, цветы, магазины одежды.
- 🚫 Автофильтр федеральных сетей (Spar, Лента, Магнит, Пятёрочка, KFC, DNS, Сбер и т. д.).
- 💬 Генерация холодных сообщений для VK и Telegram.
- 📞 Скрипт холодного звонка.
- 🤖 Промпт для нейросети — сгенерировать Telegram-бота под этот бизнес.
- 🌐 Промпт для нейросети — сгенерировать одностраничный сайт-визитку под этот бизнес.
- 🎛 Только кнопочный интерфейс, никаких команд. Постоянная reply-клавиатура + inline-меню.

## Стек

- Python 3.11
- aiogram 3.x (FSM, MemoryStorage)
- httpx (запросы к 2ГИС)
- openai SDK (через OpenRouter)
- python-dotenv

## Структура

```
main.py            # точка входа, polling
handlers.py        # роутер, FSM, обработчики сообщений и колбэков
keyboards.py       # все клавиатуры (reply + inline)
parser.py          # парсер 2ГИС, фильтр сетевиков
generator.py       # генерация текстов через OpenRouter
config.py          # переменные окружения, категории, чёрный список сетей
requirements.txt
.env.example
Procfile           # для Railway
runtime.txt        # python-3.11.9
```

## Где брать ключи

### 1. BOT_TOKEN — у [@BotFather](https://t.me/BotFather)

1. Открой Telegram, найди `@BotFather`.
2. Отправь `/newbot`.
3. Введи имя бота (например, *Tula Clients Bot*).
4. Введи username (заканчивается на `bot`, например `tula_clients_bot`).
5. BotFather пришлёт строку вида `123456789:ABC-DEF...` — это `BOT_TOKEN`.

### 2. TWOGIS_API_KEY — бесплатный на 2ГИС

1. Зайди на [https://dev.2gis.ru/](https://dev.2gis.ru/) (личный кабинет разработчика 2ГИС).
2. Зарегистрируйся → подтверди email.
3. В разделе **Ключи API** → **Создать ключ** → выбери продукт **Places API / Catalog API** (`catalog.api.2gis.com`).
4. Скопируй полученный ключ — это `TWOGIS_API_KEY`.

> Бесплатный тариф даёт лимит запросов в день — для бота с парой пользователей хватает с запасом.

### 3. OPENROUTER_API_KEY — на openrouter.ai

1. Зайди на [https://openrouter.ai/](https://openrouter.ai/).
2. Войди через Google / GitHub.
3. **Keys** → **Create Key** → дай имя → скопируй `sk-or-...` — это `OPENROUTER_API_KEY`.
4. (Опционально) Закинь несколько долларов на баланс — модель `deepseek/deepseek-chat` стоит копейки.

## Запуск локально

```bash
git clone <repo-url>
cd <repo>

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# отредактируй .env, вставь свои ключи

python main.py
```

Открой бота в Telegram и нажми **Start**.

## Деплой на Railway

1. Залей этот репозиторий на GitHub.
2. Открой [https://railway.app/](https://railway.app/) → **New Project** → **Deploy from GitHub repo**.
3. Выбери репозиторий, Railway сам определит Python и установит зависимости из `requirements.txt`.
4. Открой проект → **Variables** → добавь:
   - `BOT_TOKEN`
   - `TWOGIS_API_KEY`
   - `OPENROUTER_API_KEY`
5. **Settings → Deploy → Start Command**: `python main.py` (или Railway возьмёт из `Procfile`).
6. **Settings → Networking**: бот работает по long-polling, публичный порт **не нужен** — Railway сам поднимет worker-процесс.
7. **Deploy** → дождись зелёного статуса → пиши боту в Telegram.

### Если Railway пишет «No start command»

Открой **Settings → Deploy → Custom Start Command** и поставь:

```
python main.py
```

## Логика фильтрации

`config.py → CHAIN_BLACKLIST` — список ключевых слов. Если название бизнеса из 2ГИС содержит любое из них (без учёта регистра), бизнес отбрасывается. Это отсекает сети: ритейл, банки, телеком, фастфуд, АЗС, электронику и т. п. Список можно расширять.

## Лицензия

MIT
