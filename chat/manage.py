#!/usr/bin/env python3
"""Start the separate LAN chat stack without touching marketplace data."""

import argparse
import ipaddress
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def private_ipv4(value):
    address = ipaddress.IPv4Address(value)
    if not any(address in ipaddress.IPv4Network(net) for net in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"
    )):
        raise ValueError("Choose this computer's private LAN IPv4 address.")
    return str(address)


def detect_lan_ip():
    result = subprocess.run(["ip", "-4", "route", "get", "1.1.1.1"],
                            check=True, capture_output=True, text=True).stdout.split()
    return private_ipv4(result[result.index("src") + 1])


def configure(lan_ip, port):
    target = ROOT / ".env"
    source = target if target.exists() else ROOT / ".env.example"
    settings = {}
    for line in source.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            settings[key] = value
    chosen_ip = private_ipv4(lan_ip or settings.get("LAN_BIND_IP") or detect_lan_ip())
    chosen_port = port or int(settings.get("CHAT_PORT", "3080"))
    if not 1024 <= chosen_port <= 65535:
        raise ValueError("Choose a port between 1024 and 65535.")
    # Only first-run auto-detection uses the local interface, not the example IP.
    if not target.exists() and not lan_ip:
        chosen_ip = detect_lan_ip()
    settings.update({
        "LAN_BIND_IP": chosen_ip,
        "CHAT_PORT": str(chosen_port),
        "DOMAIN_CLIENT": f"http://{chosen_ip}:{chosen_port}",
        "DOMAIN_SERVER": f"http://{chosen_ip}:{chosen_port}",
        "NEOPACT_MCP_API_URL": f"http://{chosen_ip}:8100/api/v1",
        "HELP_AND_FAQ_URL": f"http://{chosen_ip}:{chosen_port}/neopact/start.html",
    })
    for key, size in (("CREDS_KEY", 32), ("CREDS_IV", 16),
                      ("JWT_SECRET", 48), ("JWT_REFRESH_SECRET", 48)):
        if not settings.get(key):
            settings[key] = secrets.token_hex(size)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write("# Private local configuration. Keep encryption keys with database backups.\n")
        handle.write("".join(f"{key}={value}\n" for key, value in settings.items()))
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "stop", "status", "logs", "configure"])
    parser.add_argument("--lan-ip")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    if args.command in {"configure", "start"}:
        settings = configure(args.lan_ip, args.port)
    elif not (ROOT / ".env").exists():
        parser.error("Run configure or start first.")
    command = ["docker", "compose", "--project-directory", str(ROOT),
               "--env-file", str(ROOT / ".env"), "-f", str(ROOT / "compose.yaml")]
    if args.command == "configure":
        print(f"Configured {settings['DOMAIN_CLIENT']}; private keys saved in chat/.env.")
        return
    actions = {
        "start": ["up", "-d", "--build", "--wait", "--wait-timeout", "180"],
        "stop": ["stop"], "status": ["ps"], "logs": ["logs", "--tail", "60", "chat"],
    }
    environment = os.environ.copy()
    for key in ("COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "COMPOSE_PROFILES"):
        environment.pop(key, None)
    subprocess.run(command + actions[args.command], check=True, env=environment)
    if args.command == "start":
        print(f"Chat: {settings['DOMAIN_CLIENT']}\nSetup: {settings['HELP_AND_FAQ_URL']}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"Chat setup failed: {exc}", file=sys.stderr)
        sys.exit(1)
