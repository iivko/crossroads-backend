#!/usr/bin/env python3
"""Exercise two real chat accounts and their separate MCP credentials without model calls.

Run from backend: uv run python chat/tests/smoke.py --chat-url http://LAN_IP:3080
The demo password is read from NEOPACT_DEMO_PASSWORD, or prompted without echo.
Creates only disposable chat accounts and one-day, read-only marketplace credentials.
Cleanup removes those chat accounts and revokes every credential it created.
"""

import argparse
import getpass
import os
import secrets
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from urllib.parse import urlsplit

import httpx


class CheckFailed(RuntimeError):
    """Only deliberately credential-free diagnostics may reach the console."""


def check(condition, message):
    if not condition:
        raise CheckFailed(message)


def request(client, method, path, *, allow_failure=False, **kwargs):
    response = client.request(method, path, **kwargs)
    if not allow_failure:
        check(response.is_success, f"{method} {path}: HTTP {response.status_code}")
    if not response.content:
        return response, {}
    try:
        data = response.json()
    except ValueError:
        raise CheckFailed(f"{method} {path}: expected JSON") from None
    return response, data


def resource(data):
    check(isinstance(data, dict), "Marketplace returned an invalid resource envelope")
    keys = set(data) - {"status_code"}
    check(len(keys) == 1, "Marketplace returned an invalid resource envelope")
    return data[keys.pop()]


def names_in(value):
    """Accept tool arrays or a server-name-keyed tools response from LibreChat."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "name" and isinstance(item, str):
                yield item
            yield from names_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from names_in(item)


def set_credentials(chat, token, workspace):
    request(
        chat,
        "POST",
        "/api/user/plugins",
        json={
            "pluginKey": "mcp_neopact",
            "action": "install",
            "isEntityTool": True,
            "auth": {"NEOPACT_WORKSPACE": workspace, "NEOPACT_TOKEN": token},
        },
    )


def initialize(chat, expected=True):
    response, data = request(chat, "POST", "/api/mcp/neopact/reinitialize", allow_failure=True)
    success = response.is_success and data.get("success") is True
    check(
        success is expected, "Neopact initialization unexpectedly " + ("succeeded" if success else "failed")
    )
    check(not data.get("oauthRequired"), "Neopact unexpectedly requested OAuth")


def verify_tools(chat):
    _, data = request(chat, "GET", "/api/mcp/tools")
    names = list(names_in(data))
    for expected in ("get_instructions", "search_catalogue", "get_inbox", "get_orders"):
        check(any(expected in name for name in names), f"MCP discovery omitted {expected}")
    check(not any("approve_order" in name for name in names), "Unexpected order approval tool")


def verify_connected(chat):
    _, data = request(chat, "GET", "/api/mcp/connection/status/neopact")
    check(
        data.get("connectionStatus") == "connected", "Another user's credential change broke this connection"
    )


def run(args):
    password = os.environ.get("NEOPACT_DEMO_PASSWORD") or getpass.getpass("Marketplace demo password: ")
    cleanup_failures = []

    def cleanup(label, fn):
        try:
            fn()
        except Exception:
            cleanup_failures.append(label)
            print(f"WARN: cleanup failed for {label}", file=sys.stderr)

    with ExitStack() as clients, ExitStack() as cleanup_tasks:
        chat_users = []
        credentials = []
        run_id = secrets.token_hex(6)
        for index, market_email in enumerate((args.buyer_email, args.seller_email)):
            market = clients.enter_context(
                httpx.Client(
                    base_url=args.market_url.rstrip("/") + "/",
                    timeout=30,
                    trust_env=False,
                )
            )
            _, login = request(
                market, "POST", "auth/token", json={"email": market_email, "password": password}
            )
            market.headers["Authorization"] = "Bearer " + resource(login)["token"]
            cleanup_tasks.callback(
                cleanup,
                f"marketplace login {index}",
                lambda client=market: request(client, "POST", "auth/logout"),
            )
            _, issued = request(
                market,
                "POST",
                "credentials",
                json={
                    "name": f"Chat smoke {run_id} {index}",
                    "scopes": ["catalogue:read", "images:read", "negotiations:read", "orders:read"],
                    "expires_days": 1,
                },
            )
            credential = resource(issued)
            credentials.append(credential)
            cleanup_tasks.callback(
                cleanup,
                f"marketplace agent {index}",
                lambda client=market, key=credential["id"]: request(client, "DELETE", "credentials/" + key),
            )

            chat = clients.enter_context(
                httpx.Client(
                    base_url=args.chat_url,
                    timeout=120,
                    trust_env=False,
                    headers={"Origin": args.chat_url.rstrip("/")},
                )
            )
            chat_password = secrets.token_urlsafe(30) + "Aa1!"
            email = f"chat-smoke-{run_id}-{index}@example.test"
            request(
                chat,
                "POST",
                "/api/auth/register",
                json={
                    "name": f"Chat smoke {index}",
                    "username": f"smoke{run_id}{index}",
                    "email": email,
                    "password": chat_password,
                    "confirm_password": chat_password,
                },
            )
            _, login = request(
                chat, "POST", "/api/auth/login", json={"email": email, "password": chat_password}
            )
            check(isinstance(login.get("token"), str), "Chat login did not return a session token")
            chat.headers["Authorization"] = "Bearer " + login["token"]
            cleanup_tasks.callback(
                cleanup,
                f"disposable chat account {email}",
                lambda client=chat: request(client, "DELETE", "/api/user/delete"),
            )
            chat_users.append(chat)

        check(
            credentials[0]["workspace_id"] != credentials[1]["workspace_id"],
            "Smoke test needs two distinct marketplace workspaces",
        )
        for chat, credential in zip(chat_users, credentials):
            set_credentials(chat, credential["token"], credential["workspace_id"])

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(initialize, chat_users))
        for chat in chat_users:
            verify_tools(chat)
        print("PASS: two separate chat accounts discover the Neopact MCP tools without OAuth")

        # The mismatched pair must fail even while the second user's valid session is alive.
        set_credentials(chat_users[0], credentials[0]["token"], credentials[1]["workspace_id"])
        initialize(chat_users[0], expected=False)
        verify_connected(chat_users[1])
        verify_tools(chat_users[1])
        print("PASS: a buyer credential cannot initialize in the seller workspace; seller stays connected")

        set_credentials(chat_users[0], credentials[0]["token"], credentials[0]["workspace_id"])
        initialize(chat_users[0])
        verify_tools(chat_users[0])
        print("PASS: replacing credentials reconnects only that account")

    check(not cleanup_failures, "Cleanup failed for: " + ", ".join(cleanup_failures))
    print("PASS: disposable chat accounts removed; marketplace credentials and sessions revoked")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chat-url", required=True)
    parser.add_argument("--market-url", default="http://127.0.0.1:8100/api/v1")
    parser.add_argument("--buyer-email", default="buyer@demo.local")
    parser.add_argument("--seller-email", default="forma@demo.local")
    args = parser.parse_args()
    for url in (args.chat_url, args.market_url):
        parsed = urlsplit(url)
        check(
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment,
            "Use a plain HTTP(S) URL without credentials or query parameters",
        )
    run(args)


if __name__ == "__main__":
    try:
        main()
    except CheckFailed as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # HTTP errors can contain request details. Never print their repr or traceback.
        print(f"FAIL: {type(exc).__name__}; credentials and request bodies omitted", file=sys.stderr)
        sys.exit(1)
