"""Draft to OLX advert body.

Body shape per POST /adverts in the official spec (https://developer.olx.ua/swagger/v2/partner_api.yaml,
read 2026-09-20): `attributes` items are `{code, value}` or `{code, values: [...]}`, `images` are
`[{url}]`, `contact.name` and `location.city_id` are required.
"""

from pydantic import JsonValue

from agora.draft import ListingDraft


def advert_body(draft: ListingDraft, image_urls: list[str]) -> dict[str, JsonValue]:
    contact: dict[str, JsonValue] = {"name": draft.contact_name}
    if draft.contact_phone:
        contact["phone"] = draft.contact_phone
    location: dict[str, JsonValue] = {"city_id": draft.city_id}
    if draft.district_id is not None:
        location["district_id"] = draft.district_id
    attributes: list[JsonValue] = []
    for code, value in sorted(draft.attributes.items()):
        if isinstance(value, list):
            attributes.append({"code": code, "values": list(value)})
        else:
            attributes.append({"code": code, "value": value})
    body: dict[str, JsonValue] = {
        "title": draft.title,
        "description": draft.description,
        "category_id": draft.category_id,
        "advertiser_type": draft.advertiser_type,
        "contact": contact,
        "location": location,
        "attributes": attributes,
    }
    if draft.price is not None:
        body["price"] = {
            "value": draft.price.value,
            "currency": draft.price.currency,
            "negotiable": draft.price.negotiable,
            "trade": draft.price.trade,
        }
    if image_urls:
        body["images"] = [{"url": url} for url in image_urls]
    return body
