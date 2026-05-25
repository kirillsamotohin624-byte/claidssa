import asyncio
import logging
import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from config import CHAIN_BLACKLIST

logger = logging.getLogger(__name__)

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]

OVERPASS_HEADERS = {
    "User-Agent": "TulaSmallBizBot/1.0 (Telegram bot for small business search; contact via Telegram)",
    "Accept": "application/json",
    "Accept-Language": "ru,en;q=0.8",
}

DDG_URL = "https://html.duckduckgo.com/html/"
DDG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TulaBot/1.0)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru,en;q=0.8",
}

ENRICH_DELAY_SECONDS = 1.0
ENRICH_MAX_BUSINESSES = 15

PHONE_REGEX = re.compile(
    r"(?:\+7|8)[\s\-\(\)]{0,2}\d{3,4}[\s\-\(\)]{0,2}\d{2,3}[\s\-]{0,2}\d{2,3}[\s\-]{0,2}\d{2}"
)

URL_REGEX = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)

URL_DOMAIN_BLACKLIST = (
    "duckduckgo.com",
    "google.com",
    "yandex.ru",
    "yandex.com",
    "bing.com",
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "twitter.com",
    "x.com",
    "wikipedia.org",
    "wikimapia.org",
    "2gis.ru",
    "2gis.com",
    "zoon.ru",
    "yell.ru",
    "spr.ru",
    "flamp.ru",
    "yandex.com.tr",
    "vk.com",
    "ok.ru",
    "t.me",
    "telegram.org",
    "instagram.com",
)


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
    async with httpx.AsyncClient(timeout=30.0, headers=OVERPASS_HEADERS, follow_redirects=True) as client:
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
                    logger.warning("Overpass %s загружен (%s)", endpoint, resp.status_code)
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


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return raw.strip()
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if digits.startswith("7") and len(digits) == 11:
        return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return raw.strip()


def _unwrap_ddg_url(href: str) -> str | None:
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg")
        if uddg:
            return unquote(uddg[0])
        return None
    if parsed.scheme in ("http", "https"):
        return href
    return None


def _is_blacklisted_url(url: str) -> bool:
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return True
    if not netloc:
        return True
    netloc = netloc.removeprefix("www.")
    for bad in URL_DOMAIN_BLACKLIST:
        if netloc == bad or netloc.endswith("." + bad):
            return True
    return False


def _extract_phones_from_html(html: str) -> list[str]:
    found = []
    seen = set()
    for match in PHONE_REGEX.findall(html):
        cleaned = _clean_phone(match)
        key = re.sub(r"\D", "", cleaned)
        if len(key) < 10:
            continue
        if key in seen:
            continue
        seen.add(key)
        found.append(cleaned)
        if len(found) >= 3:
            break
    return found


def _extract_website_from_soup(soup: BeautifulSoup) -> str | None:
    for anchor in soup.select("a.result__url, a.result__a"):
        href = anchor.get("href") or ""
        url = _unwrap_ddg_url(href)
        if not url:
            text = anchor.get_text(" ", strip=True)
            if text:
                if not text.startswith("http"):
                    text = "https://" + text
                url = text
        if not url:
            continue
        if _is_blacklisted_url(url):
            continue
        return url

    for anchor in soup.find_all("a", href=True):
        url = _unwrap_ddg_url(anchor["href"])
        if not url:
            continue
        if _is_blacklisted_url(url):
            continue
        return url
    return None


async def _enrich_one(client: httpx.AsyncClient, business: dict) -> None:
    name = business.get("name") or ""
    if not name:
        return
    query = f"{name} Тула телефон сайт"
    try:
        resp = await client.get(DDG_URL, params={"q": query}, headers=DDG_HEADERS)
        if resp.status_code != 200:
            logger.info("DDG ответил %s для %r", resp.status_code, name)
            return
        html = resp.text
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.info("DDG недоступен для %r: %s", name, e)
        return
    except Exception as e:
        logger.info("DDG ошибка для %r: %s", name, e)
        return

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.info("Не удалось распарсить DDG для %r: %s", name, e)
            return

    if not business.get("phones"):
        phones = _extract_phones_from_html(html)
        if phones:
            business["phones"] = phones

    if not business.get("website"):
        website = _extract_website_from_soup(soup)
        if website:
            business["website"] = website


async def _enrich_via_duckduckgo(businesses: list[dict]) -> list[dict]:
    targets = [b for b in businesses if not b.get("phones") or not b.get("website")]
    if not targets:
        return businesses
    targets = targets[:ENRICH_MAX_BUSINESSES]

    async with httpx.AsyncClient(timeout=15.0, headers=DDG_HEADERS, follow_redirects=True) as client:
        for i, business in enumerate(targets):
            try:
                await _enrich_one(client, business)
            except Exception as e:
                logger.info("Сбой обогащения для %r: %s", business.get("name"), e)
            if i < len(targets) - 1:
                await asyncio.sleep(ENRICH_DELAY_SECONDS)
    return businesses


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

    try:
        await _enrich_via_duckduckgo(unique)
    except Exception as e:
        logger.warning("Ошибка обогащения через DuckDuckGo: %s", e)

    return unique
