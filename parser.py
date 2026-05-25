import logging
import httpx
from config import CHAIN_BLACKLIST, YANDEX_API_KEY

logger = logging.getLogger(__name__)

YANDEX_URL = "https://search-maps.yandex.ru/v1/"

def _is_chain(name: str) -> bool:
    lowered = name.lower()
    for chain in CHAIN_BLACKLIST:
        if chain in lowered:
            return True
    return False

def _extract_contacts(feature: dict) -> dict:
    props = feature.get("properties", {})
    phones = []
    website = None
    
    company_meta = props.get("CompanyMetaData", {})
    
    for phone in company_meta.get("Phones", []):
        number = phone.get("formatted") or phone.get("number")
        if number:
            phones.append(number)
    
    website = company_meta.get("url")
    
    return {
        "phones": phones,
        "website": website,
        "vk": None,
        "instagram": None,
        "telegram": None,
    }

async def search_businesses(query: str, page: int = 1, page_size: int = 20) -> list[dict]:
    if not YANDEX_API_KEY:
        raise RuntimeError("YANDEX_API_KEY не задан")

    params = {
        "apikey": YANDEX_API_KEY,
        "text": f"{query} Тула",
        "lang": "ru_RU",
        "type": "biz",
        "results": min(page_size, 50),
        "skip": (page - 1) * page_size,
        "ll": "37.6173,54.1961",
        "spn": "0.5,0.5",
        "rspn": 1,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(YANDEX_URL, params=params)
        if resp.status_code != 200:
            logger.error("Yandex error %s: %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Yandex API вернул {resp.status_code}")
        data = resp.json()

    features = data.get("features") or []
    
    parsed = []
    for feature in features:
        props = feature.get("properties", {})
        company = props.get("CompanyMetaData", {})
        
        name = company.get("name") or props.get("name") or ""
        if not name:
            continue
        if _is_chain(name):
            continue
            
        address = company.get("address") or props.get("description") or "—"
        contacts = _extract_contacts(feature)
        
        parsed.append({
            "id": company.get("id") or name,
            "name": name,
            "address": address,
            "phones": contacts["phones"],
            "website": contacts["website"],
            "vk": None,
            "instagram": None,
            "telegram": None,
            "rubrics": [c.get("name") for c in company.get("Categories", []) if c.get("name")],
        })
    
    return parsed

async def collect_small_business(query: str, limit: int = 30) -> list[dict]:
    collected: list[dict] = []
    page = 1
    while len(collected) < limit and page <= 5:
        try:
            batch = await search_businesses(query, page=page, page_size=20)
        except Exception as e:
            logger.exception("Ошибка парсера Яндекс: %s", e)
            if collected:
                break
            raise
        if not batch:
            break
        collected.extend(batch)
        page += 1

    seen = set()
    unique = []
    for b in collected:
        key = (b["name"].lower(), b["address"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(b)
    return unique[:limit]