"""Explicit process configuration; credentials never enter tool arguments."""

import os
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    pass


def private_ipv4(hostname):
    try:
        address = IPv4Address(hostname)
    except ValueError:
        return False
    return any(
        address in IPv4Network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    )


@dataclass(frozen=True)
class Configuration:
    api_url: str
    workspace_id: str
    token: str = field(repr=False)
    allow_lan_http: bool = False

    def __post_init__(self):
        parsed = urlsplit(self.api_url)
        loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        trusted_lan = self.allow_lan_http and private_ipv4(parsed.hostname)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or (parsed.scheme != "https" and not loopback and not trusted_lan)
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") != "/api/v1"
        ):
            raise ConfigurationError(
                "NEOPACT_MCP_API_URL must be an HTTPS /api/v1 URL. HTTP is allowed on loopback, "
                "or a private IPv4 address with NEOPACT_MCP_ALLOW_LAN_HTTP=true for a trusted LAN demo."
            )
        if (
            not self.workspace_id
            or len(self.workspace_id) > 100
            or any(c.isspace() for c in self.workspace_id)
        ):
            raise ConfigurationError("Set NEOPACT_MCP_WORKSPACE to one workspace ID.")
        if (
            not self.token.startswith("am_")
            or not 40 <= len(self.token) <= 200
            or any(c.isspace() for c in self.token)
        ):
            raise ConfigurationError("Set NEOPACT_MCP_TOKEN to a restricted workspace agent credential.")

    @classmethod
    def from_environment(cls):
        return cls(
            api_url=os.environ.get("NEOPACT_MCP_API_URL", ""),
            workspace_id=os.environ.get("NEOPACT_MCP_WORKSPACE", ""),
            token=os.environ.get("NEOPACT_MCP_TOKEN", ""),
            allow_lan_http=os.environ.get("NEOPACT_MCP_ALLOW_LAN_HTTP", "").strip().lower() == "true",
        )
