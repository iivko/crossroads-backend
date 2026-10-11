"""Prompt generation is private, role-scoped and has no business side effects."""

import pytest
from response_helpers import response_data
from sqlalchemy import func, select
from test_marketplace import BASE, browser, data_request, launch, user

from market import service
from market.models import Event, PurchaseRequest, Room, Workspace


@pytest.mark.parametrize("account,role", [("buyer", "buyer"), ("forma", "seller")])
def test_prompt_uses_authenticated_role_without_credentials_or_private_data(client, account, role):
    headers = user(client, account, agent=True)
    response = client.post(BASE + "/agent/prompt", headers=headers, json={"objective": "Prioritize delivery"})
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"agent_prompt", "status_code"}
    value = response_data(response)
    assert value["role"] == role
    assert value["workspace_id"] == ("ws-buyer" if role == "buyer" else "ws-forma")
    assert value["poll_interval_seconds"] == 20
    assert value["mode"] == "start"
    prompt = value["prompt"]
    assert "Prioritize delivery" in prompt
    assert headers["Authorization"].split()[1] not in prompt
    assert "8300" not in prompt and "700000" not in prompt
    assert "act immediately" in prompt and "wait_for_updates" in prompt
    assert "Both humans still approve" in prompt
    assert "20 seconds" in prompt
    if role == "seller":
        assert "minimum, not the opening ask or target" in prompt
        assert "create_request\nand launch_request" not in prompt
    else:
        assert "private budget is a ceiling" in prompt


def test_prompt_requires_read_scope_and_browser_csrf(client):
    owner = user(client, "buyer")
    issued = response_data(
        client.post(
            BASE + "/credentials",
            headers=owner,
            json={"name": "Catalogue only", "scopes": ["catalogue:read"]},
        )
    )
    assert client.post(BASE + "/agent/prompt", json={}).status_code == 401
    assert (
        client.post(
            BASE + "/agent/prompt", headers={"Authorization": "Bearer " + issued["token"]}, json={}
        ).status_code
        == 403
    )
    with browser("buyer") as b:
        csrf = b.headers.pop("X-CSRF-Token")
        assert b.post(BASE + "/agent/prompt", json={}).status_code == 403
        b.headers["X-CSRF-Token"] = csrf
        assert b.post(BASE + "/agent/prompt", json={}).status_code == 200


def test_prompt_validates_targets_and_keeps_other_workspaces_private(system):
    client, factory = system
    buyer, seller, outsider = user(client, "buyer"), user(client, "forma"), user(client, "atelier")
    request_id, rooms = launch(client, buyer)
    room_id = next(r["id"] for r in rooms if r["product_id"] == "prod-forma")
    for headers in (buyer, seller):
        response = client.post(
            BASE + "/agent/prompt", headers=headers, json={"room_id": room_id, "mode": "resume"}
        )
        assert response.status_code == 200
        assert response_data(response)["mode"] == "resume"
        assert room_id in response_data(response)["prompt"]
    assert client.post(BASE + "/agent/prompt", headers=outsider, json={"room_id": room_id}).status_code == 404
    assert (
        client.post(BASE + "/agent/prompt", headers=seller, json={"request_id": request_id}).status_code
        == 403
    )
    assert (
        client.post(BASE + "/agent/prompt", headers=buyer, json={"request_id": request_id}).status_code == 200
    )
    with factory() as db:
        db.add(Workspace(id="private-buyer", name="Private buyer", role="buyer"))
        db.flush()
        db.add(PurchaseRequest(id="private-request", workspace_id="private-buyer", data=data_request()))
        db.commit()
    for payload in ({"request_id": "private-request"}, {"room_id": "does-not-exist"}):
        assert client.post(BASE + "/agent/prompt", headers=buyer, json=payload).status_code == 404
    for payload in (
        {"room_id": room_id, "request_id": request_id},
        {"role": "seller"},
        {"workspace_id": "ws-forma"},
        {"room_id": "../credentials"},
        {"objective": "x" * 2001},
        {"mode": "run_forever"},
    ):
        assert client.post(BASE + "/agent/prompt", headers=buyer, json=payload).status_code == 422


def test_prompt_generation_does_not_mutate_or_embed_saved_context(system, monkeypatch):
    client, factory = system
    owner = user(client, "buyer")
    request_id, _ = launch(client, owner)
    issued = response_data(
        client.post(
            BASE + "/credentials",
            headers=owner,
            json={"name": "Read-only prompt", "scopes": ["negotiations:read"]},
        )
    )
    headers = {"Authorization": "Bearer " + issued["token"]}

    def snapshot():
        with factory() as db:
            return [
                db.scalar(select(func.count()).select_from(model)) for model in (Event, PurchaseRequest, Room)
            ]

    def no_mutations(*args):
        pytest.fail("Pure prompt generation must not use the writer dependency")

    monkeypatch.setattr(service, "mutation", no_mutations)
    before = snapshot()
    payload = {"request_id": request_id, "objective": "Please improve the deposit", "mode": "resume"}
    first = client.post(BASE + "/agent/prompt", headers=headers, json=payload)
    second = client.post(BASE + "/agent/prompt", headers=headers, json=payload)
    assert first.status_code == 200 and second.json() == first.json()
    assert snapshot() == before
    prompt = response_data(first)["prompt"]
    assert "Secret maximum is" not in prompt
    assert "700000" not in prompt
    assert "Resume from current server state" in prompt
    assert "get_purchase_request(...).negotiations" in prompt
    assert "After every wait, refresh the request" in prompt
    assert "room ID, run, offer ID/version" in prompt
