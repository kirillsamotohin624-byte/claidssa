import logging
import re
from typing import Optional

import httpx

from config import CHAIN_BLACKLIST, CITY, TWOGIS_API_KEY

logger = logging.getLogger(__name__)

TWOGIS_URL = "https://catalog.api.2gis.com/3.0/items"


def _is_chain(name: str) -> bool:
    low = name.lower()
    return any(brand in low for brand in CHAIN_BLACKLIST)


def _extract_phone(contact_groups: list) -> Optional[str]:
    for group in contact_groups or []:
        for contact in group.get("contacts", []):
            if contact.get("type") == "phone":
                val = contact.get("value") or contact.get("text")
                if val:
                    return val
    return None


def _extract_website(contact_groups: list) -> Optional[str]:
    for group in contact_groups or []:
        for contact in group.get("contacts", []):
            if contact.get("type") == "website":
                val = contact.get("url") or contact.get("value") or contact.get("text")
                if val:
                    return val
    return None


def _extract_vk(contact_groups: list) -> Optional[str]:
    for group in contact_groups or []:
        for contact in group.get("contacts", []):
            t = contact.get("type", "")
            val = (
                contact.get("url")
                or contact.get("value")
                or contact.get("text")
                or ""
            )
            if "vk.com" in val.lower() or t == "vkontakte":
                if not val.startswith("http"):
                    val = "https://" + val.lstrip("/")
                return val
    return None


def _extract_telegram(contact_groups: list) -> Optional[str]:
    for group in contact_groups or []:
        for contact in group.get("contacts", []):
            t = contact.get("type", "")
            val = (
                contact.get("url")
                or contact.get("value")
                or contact.get("text")
                or ""
            )
            if "t.me" in val.lower() or "telegram" in t.lower():
                if not val.startswith("http"):
                    val = "https://" + val.lstrip("/")
                return val
    return None


async def search_business(query: str, page: int = 1, page_size: int = 20) -> list[dict]:
    if not TWOGIS_API_KEY:
        raise RuntimeError("TWOGIS_API_KEY не задан")

    params = {
        "q": f"{query} {CITY}",
        "city": CITY,
        "fields": "items.point,items.contact_groups,items.address,items.full_name,items.adm_div,items.org,items.external_content",
        "key": TWOGIS_API_KEY,
        "page": page,
        "page_size": page_size,
    }

    async with httpx.AsyncClient(timeout=20.0) as session:
        resp = await session.get(TWOGIS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("result", {}).get("items", [])
    businesses: list[dict] = []
    seen = set()

    for it in items:
        name = it.get("name") or it.get("full_name") or ""
        if not name:
            continue
        if _is_chain(name):
            continue

        addr = it.get("address_name") or it.get("address", {}).get("name") or ""
        contact_groups = it.get("contact_groups") or []

        phone = _extract_phone(contact_groups)
        website = _extract_website(contact_groups)
        vk = _extract_vk(contact_groups)
        tg = _extract_telegram(contact_groups)

        key = (name.lower(), addr.lower())
        if key in seen:
            continue
        seen.add(key)

        businesses.append(
            {
                "id": it.get("id", ""),
                "name": name,
                "address": addr,
                "phone": phone,
                "website": website,
                "vk": vk,
                "telegram": tg,
            }
        )

    return businesses
