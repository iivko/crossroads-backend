from uuid import uuid4

import pytest
from response_helpers import response_data
from test_marketplace import BASE, launch, user


@pytest.mark.parametrize("category", ["desks", "cabinets", "laptops", "headphones"])
def test_non_chair_catalogue_and_matching_preserve_category_and_visibility(client, category):
    seller, buyer = user(client, "nord", True), user(client, "buyer", True)
    categories = response_data(client.get(BASE + "/categories", headers=buyer))
    assert {item["id"] for item in categories} == {"chairs", "desks", "cabinets", "laptops", "headphones"}
    material = "mixed" if category in {"laptops", "headphones"} else "wood"
    payload = {
        "name": f"Office {category}",
        "sku": f"NORD-{category}",
        "category": category,
        "attributes": {"material": material, "stackable": False, "color": "Natural"},
        "unit_price": 20000,
        "delivery_charge": 2500,
        "lead_days": 3,
        "destinations": ["Sofia"],
        "stock": 10,
        "published": False,
    }
    created = client.post(BASE + "/products", headers=seller, json=payload)
    assert created.status_code == 201, created.text
    product = response_data(created)
    pid = product["id"]
    assert product["category"] == category
    other_category = {
        "desks": "cabinets",
        "cabinets": "desks",
        "laptops": "headphones",
        "headphones": "laptops",
    }[category]
    other = client.post(
        BASE + "/products",
        headers={**seller, "Idempotency-Key": str(uuid4())},
        json={**payload, "sku": "OTHER-01", "category": other_category, "published": True},
    )
    assert other.status_code == 201, other.text

    def catalogue(headers, **params):
        response = client.get(BASE + "/products", headers=headers, params=params)
        assert response.status_code == 200, response.text
        return response_data(response)

    assert catalogue(buyer, category=category)["total"] == 0
    assert catalogue(seller, category=category, own=True)["items"][0]["id"] == pid
    published = client.put(
        BASE + f"/products/{pid}",
        headers=seller,
        json={**payload, "published": True, "expected_version": product["version"]},
    )
    assert published.status_code == 200, published.text
    assert response_data(published)["category"] == category
    assert catalogue(buyer, category=category)["items"][0]["id"] == pid
    assert catalogue(buyer, category="chairs")["total"] == 3
    assert catalogue(buyer, category=category, q="Office", material=material)["total"] == 1

    rid, rooms = launch(client, buyer, category=category, quantity=2, material=material, stackable=False)
    assert [room["product_id"] for room in rooms] == [pid]
    matches = response_data(client.get(BASE + f"/requests/{rid}/matches", headers=buyer))
    assert all("Category does not match" in m["reasons"] for m in matches if m["product_id"] != pid)
    context = client.get(BASE + f"/negotiations/{rooms[0]['id']}/context", headers=seller)
    assert context.status_code == 200, context.text
    assert response_data(context)["request"]["category"] == category

    invalid = client.post(
        BASE + "/products",
        headers={**seller, "Idempotency-Key": str(uuid4())},
        json={**payload, "category": "unsupported"},
    )
    assert invalid.status_code == 422
