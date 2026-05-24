import logging

import httpx

from config import CHAIN_BLACKLIST, TULA_REGION_ID, TWOGIS_API_KEY

logger = logging.getLogger(__name__)

API_URL = "https://catalog.api.2gis.com/3.0/items"


def _is_chain(name: str) -> bool:
    lowered = name.lower()
    for chain in CHAIN_BLACKLIST:
        if chain in lowered:
            return True
    return False


def _extract_contacts(item: dict) -> dict:
    phones = []
    website = None
    vk = None
    instagram = None
    telegram = None

    for contact_group in item.get("contact_groups", []) or []:
        for contact in contact_group.get("contacts", []) or []:
            ctype = contact.get("type")
            value = contact.get("value") or ""
            url = contact.get("url") or ""
            text = contact.get("text") or value

            if ctype == "phone" and value:
                phones.append(value)
            elif ctype == "website" and (url or value):
                if not website:
                    website = url or value
            elif ctype == "vkontakte":
                vk = url or value or text
                if vk and not vk.startswith("http"):
                    vk = f"https://vk.com/{vk.lstrip('@/')}"
            elif ctype == "instagram":
                instagram = url or value or text
            elif ctype == "telegram":
                telegram = url or value or text
                if telegram and not telegram.startswith("http"):
                    telegram = f"https://t.me/{telegram.lstrip('@/')}"

    return {
        "phones": phones,
        "website": website,
        "vk": vk,
        "instagram": instagram,
        "telegram": telegram,
    }


def _address_from_item(item: dict) -> str:
    full = item.get("full_address_name") or item.get("address_name")
    if full:
        return full
    addr = item.get("address")
    if isinstance(addr, dict):
        return addr.get("name") or "—"
    if isinstance(addr, str):
        return addr
    return "—"


async def search_businesses(query: str, page: int = 1, page_size: int = 20) -> list[dict]:
    if not TWOGIS_API_KEY:
        raise RuntimeError("TWOGIS_API_KEY не задан")

    params = {
        "q": query,
        "region_id": TULA_REGION_ID,
        "page": page,
        "page_size": min(page_size, 50),
        "fields": "items.point,items.contact_groups,items.adm_div,items.full_address_name,items.rubrics,items.flags",
        "key": TWOGIS_API_KEY,
        "locale": "ru_RU",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(API_URL, params=params)
        if resp.status_code != 200:
            logger.error("2GIS error %s: %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"2GIS API вернул {resp.status_code}")
        data = resp.json()

    result_block = data.get("result") or {}
    items = result_block.get("items") or []

    parsed = []
    for it in items:
        name = it.get("name") or ""
        if not name:
            continue
        if _is_chain(name):
            continue
        contacts = _extract_contacts(it)
        parsed.append({
            "id": it.get("id") or it.get("org", {}).get("id") if isinstance(it.get("org"), dict) else it.get("id"),
            "name": name,
            "address": _address_from_item(it),
            "phones": contacts["phones"],
            "website": contacts["website"],
            "vk": contacts["vk"],
            "telegram": contacts["telegram"],
            "instagram": contacts["instagram"],
            "rubrics": [r.get("name") for r in (it.get("rubrics") or []) if r.get("name")],
        })
    return parsed


async def collect_small_business(query: str, limit: int = 30) -> list[dict]:
    """Собирает несколько страниц 2ГИС, отфильтровав сети."""
    collected: list[dict] = []
    page = 1
    while len(collected) < limit and page <= 5:
        try:
            batch = await search_businesses(query, page=page, page_size=20)
        except Exception as e:
            logger.exception("Ошибка парсера 2ГИС: %s", e)
            if collected:
                break
            raise
        if not batch:
            break
        collected.extend(batch)
        page += 1
    # дедуп по имя+адрес
    seen = set()
    unique = []
    for b in collected:
        key = (b["name"].lower(), b["address"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(b)
    return unique[:limit]
