# Optional chat integration — work in progress

This directory preserves an unfinished LibreChat integration. It is not runnable yet and is not part of the working marketplace Docker Compose stack. The dashboard's Connections prompts work independently of it; see [agent prompt setup](../docs/AGENT_PROMPTS.md).

The scaffold contains a separate Compose project and MongoDB storage, a local configuration helper, provider/MCP configuration, brand assets and a proposed smoke check. Each chat user would supply their own model key and workspace-bound agent credential.

## Missing pieces

- `chat/Dockerfile`, referenced by `compose.yaml`, has not been implemented. `manage.py start` cannot build the chat service.
- `branding/public/neopact/start.html`, referenced by the help URL, has not been created.
- Image build, chat startup, provider configuration, per-user MCP isolation and the smoke check still require end-to-end validation.

Python syntax and Compose configuration have been checked. Those checks do not establish that the chat application runs. The existing marketplace API, dashboard, PostgreSQL and MinIO continue to use the parent Compose project.

## Local configuration

`.env.example` contains placeholders and an illustrative LAN address. On first configuration, `manage.py` detects the host's private IPv4 address unless `--lan-ip` is supplied, and creates private encryption/session keys in the ignored `chat/.env`. Never commit that file, user model keys, marketplace tokens or runtime data. Preserve encryption keys with any future chat database backup.

The included font license files accompany the copied brand assets. Complete and validate the missing pieces before treating this directory as an installation guide.
