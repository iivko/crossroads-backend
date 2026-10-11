import pytest

from mcp_server.config import Configuration, ConfigurationError

TOKEN = "am_" + "x" * 54


@pytest.mark.parametrize("host", ["10.1.2.3", "172.16.1.2", "172.31.255.254", "192.168.68.109"])
def test_lan_requires_explicit_opt_in(host):
    url = f"http://{host}:8100/api/v1"
    with pytest.raises(ConfigurationError):
        Configuration(url, "ws-buyer", TOKEN)
    assert Configuration(url, "ws-buyer", TOKEN, allow_lan_http=True).api_url == url


@pytest.mark.parametrize(
    "host", ["example.com", "8.8.8.8", "169.254.169.254", "172.32.0.1", "100.64.0.1", "0.0.0.0", "[fd00::1]"]
)
def test_opt_in_rejects_other_insecure_destinations(host):
    with pytest.raises(ConfigurationError):
        Configuration(f"http://{host}:8100/api/v1", "ws-buyer", TOKEN, allow_lan_http=True)


def test_environment_opt_in_never_exposes_token(monkeypatch):
    monkeypatch.setenv("NEOPACT_MCP_API_URL", "http://192.168.68.109:8100/api/v1")
    monkeypatch.setenv("NEOPACT_MCP_WORKSPACE", "ws-buyer")
    monkeypatch.setenv("NEOPACT_MCP_TOKEN", TOKEN)
    monkeypatch.setenv("NEOPACT_MCP_ALLOW_LAN_HTTP", "false")
    with pytest.raises(ConfigurationError):
        Configuration.from_environment()
    monkeypatch.setenv("NEOPACT_MCP_ALLOW_LAN_HTTP", "true")
    assert Configuration.from_environment().allow_lan_http
    assert TOKEN not in repr(Configuration.from_environment())
