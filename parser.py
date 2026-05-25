import logging
import httpx
from config import CHAIN_BLACKLIST

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

CATEGORY_QUERIES = {
    "салон красоты": '["shop"~"beauty|hairdresser"]',
    "стоматология": '["amenity"="dentist"]',
    "кафе": '["amenity"~"cafe|restaurant|bar"]',
    "фитнес клуб": '["leisure"~"fitness_centre|sports_centre"]',
    "автосервис": '["shop"~"car_repair|tyres"]',
    "репетитор": '["amenity"="school"]["name"~"курс|репетит",i]',
    "цветы магазин": '["shop"="florist"]',
    "магазин одежды": '["shop"="clothes"]',
}

TULA_BBOX = "(54.1,37.4,54.3,37.8)"

def _is_chain(name: str) -> bool:
    lowered = name.lower()
    for chain in CHAIN_BLACKLIST:
        if chain in lowered:
            return True
    return False

def _build_query(tag_filter: str) -> str:
    return f"""
[out:json][timeout:25];
(
  node{tag_filter}{TULA_BBOX};
  way{tag_filter}{TULA_BBOX};
);
out body;
"""

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
        phones = [p.strip() for p in phone.split(";")]

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

async def search_businesses(query: str, page: int = 1, page_size: int = 20) -> list[dict]:
    tag_filter = CATEGORY_QUERIES.get(query)
    if not tag_filter:
        tag_filter = f'["name"~"{query}",i]'

    overpass_query = _build_query(tag_filter)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(OVERPASS_URL, data={"data": overpass_query})
        if resp.status_code != 200:
            logger.error("Overpass error %s: %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Overpass API вернул {resp.status_code}")
        data = resp.json()

    elements = data.get("elements") or []
    parsed = []
    for el in elements:
        item = _extract_from_element(el)
        if item:
            parsed.append(item)

    start = (page - 1) * page_size
    return parsed[start:start + page_size]

async def collect_small_business(query: str, limit: int = 30) -> list[dict]:
    tag_filter = CATEGORY_QUERIES.get(query)
    if not tag_filter:
        tag_filter = f'["name"~"{query}",i]'

    overpass_query = _build_query(tag_filter)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(OVERPASS_URL, data={"data": overpass_query})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.exception("Ошибка Overpass: %s", e)
        raise

    elements = data.get("elements") or []
    seen = set()
    unique = []
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