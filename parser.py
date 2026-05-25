import asyncio
import logging

import httpx

from config import CHAIN_BLACKLIST

logger = logging.getLogger(__name__)

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]

HTTP_HEADERS = {
    "User-Agent": "TulaSmallBizBot/1.0 (Telegram bot for small business search; contact via Telegram)",
    "Accept": "application/json",
    "Accept-Language": "ru,en;q=0.8",
}

CATEGORY_QUERIES = {
    "салон красоты": '["shop"~"beauty|hairdresser"]',
    "стоматология": '["amenity"="dentist"]',
    "кафе": '["amenity"~"cafe|restaurant|bar"]',
    "фитнес клуб": '["leisure"~"fitness_centre|sports_centre"]',
    "автосервис": '["shop"~"car_repair|tyres"]',
    "репетитор": '["amenity"~"language_school|training|college"]',
    "цветы магазин": '["shop"="florist"]',
    "магазин одежды": '["shop"="clothes"]',
}

TULA_BBOX = "(54.10,37.40,54.30,37.80)"


def _is_chain(name: str) -> bool:
    lowered = name.lower()
    for chain in CHAIN_BLACKLIST:
        if chain in lowered:
            return True
    return False


def _build_query(tag_filter: str) -> str:
    return (
        "[out:json][timeout:25];"
        "("
        f"node{tag_filter}{TULA_BBOX};"
        f"way{tag_filter}{TULA_BBOX};"
        f"relation{tag_filter}{TULA_BBOX};"
        ");"
        "out center tags;"
    )


def _extract_from_element(el: dict) -> dict | None:
    tags = el.get("tags") or {}
    name = tags.get("name") or tags.get("name:ru") or ""
    if not name:
        return None
    if _is_chain(name):
        return None

    phones = []
    phone = tags.get("phone") or tags.get("contact:phone")
    if phone:
        phones = [p.strip() for p in phone.split(";") if p.strip()]

    address_parts = []
    if tags.get("addr:street"):
        address_parts.append(tags["addr:street"])
    if tags.get("addr:housenumber"):
        address_parts.append(tags["addr:housenumber"])
    address = ", ".join(address_parts) if address_parts else "Тула"

    website = tags.get("website") or tags.get("contact:website")
    vk = tags.get("contact:vk")
    instagram = tags.get("contact:instagram")
    telegram = tags.get("contact:telegram")

    if vk and not vk.startswith("http"):
        vk = f"https://vk.com/{vk.lstrip('@/')}"
    if telegram and not telegram.startswith("http"):
        telegram = f"https://t.me/{telegram.lstrip('@/')}"

    return {
        "id": str(el.get("id", "")),
        "name": name,
        "address": address,
        "phones": phones,
        "website": website,
        "vk": vk,
        "instagram": instagram,
        "telegram": telegram,
        "rubrics": [],
    }


async def _fetch_overpass(overpass_query: str) -> dict:
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=30.0, headers=HTTP_HEADERS, follow_redirects=True) as client:
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                resp = await client.post(endpoint, data={"data": overpass_query})
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception as e:
                        last_error = RuntimeError(
                            f"Не-JSON ответ от {endpoint}: {resp.text[:200]}"
                        )
                        logger.warning("Overpass %s вернул не JSON: %s", endpoint, e)
                        continue
                if resp.status_code in (429, 504):
                    logger.warning("Overpass %s загружен (%s), пробую следующий", endpoint, resp.status_code)
                    last_error = RuntimeError(f"{endpoint} вернул {resp.status_code}")
                    await asyncio.sleep(0.5)
                    continue
                logger.warning(
                    "Overpass %s вернул %s: %s",
                    endpoint, resp.status_code, resp.text[:200],
                )
                last_error = RuntimeError(f"{endpoint} вернул {resp.status_code}")
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                logger.warning("Overpass %s недоступен: %s", endpoint, e)
                last_error = e
    raise RuntimeError(f"Все Overpass-инстансы недоступны: {last_error}")


def _resolve_filter(query: str) -> str:
    tag_filter = CATEGORY_QUERIES.get(query)
    if tag_filter:
        return tag_filter
    safe = query.replace('"', '\\"')
    return f'["name"~"{safe}",i]'


async def search_businesses(query: str, page: int = 1, page_size: int = 20) -> list[dict]:
    tag_filter = _resolve_filter(query)
    overpass_query = _build_query(tag_filter)

    data = await _fetch_overpass(overpass_query)
    elements = data.get("elements") or []

    parsed = []
    for el in elements:
        item = _extract_from_element(el)
        if item:
            parsed.append(item)

    start = (page - 1) * page_size
    return parsed[start:start + page_size]


async def collect_small_business(query: str, limit: int = 30) -> list[dict]:
    tag_filter = _resolve_filter(query)
    overpass_query = _build_query(tag_filter)

    data = await _fetch_overpass(overpass_query)
    elements = data.get("elements") or []

    seen = set()
    unique: list[dict] = []
    for el in elements:
        item = _extract_from_element(el)
        if not item:
            continue
        key = (item["name"].lower(), item["address"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break

    return unique
