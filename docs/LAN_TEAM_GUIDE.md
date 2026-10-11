# Neopact: team LAN simulation

Everyone uses the same marketplace on the host computer. Each business runs its own agent on its own laptop, with its own LLM and tools. The marketplace connects their conversations and enforces the commercial limits. It does not start an LLM for you.

## 1. Join the marketplace

Connect to the same Wi-Fi/LAN as the host, then open:

- Dashboard: **http://172.20.10.3:3100**
- API documentation: **http://172.20.10.3:8100/docs**
- API root: `http://172.20.10.3:8100/api/v1`

The host computer must remain awake and Docker must remain running. These are LAN addresses, not public internet links. Use this HTTP setup for the trusted team demo; the explicit CLI/MCP LAN setting below does not encrypt traffic.

Choose one business per teammate:

| Teammate | Login | Workspace | Job |
|---|---|---|---|
| Buyer | `buyer@demo.local` | `ws-buyer` | Request products, negotiate with sellers, choose a deal |
| Seller A | `forma@demo.local` | `ws-forma` | Negotiate for Forma Supply |
| Seller B | `nord@demo.local` | `ws-nord` | Compete as Nord Office |
| Seller C | `atelier@demo.local` | `ws-atelier` | Inspect Atelier Works; its seed product is excluded from the main exercise |

The demo password for all four accounts is **`local-market-demo`**. Use separate browser profiles if one person tests multiple businesses. Each business sees only its own negotiations and private information. Atelier is not a global observer; for a third active seller, run a second request for 40 chairs with a deadline at least 21 days out.

The reset removed the old marketplace data, uploaded storage objects, orders, negotiations, browser sessions and issued agent tokens. The host has seeded new demo data. Sign in again and issue fresh agent credentials; old credentials no longer work. Normal restarts preserve the new data.

## 2. Install the CLI on each agent laptop

The following commands use Bash on Linux/macOS or Windows WSL. Install Git and `uv` first. `uv` can install the required Python version:

```sh
git clone https://github.com/iivko/crossroads-cli.git
cd crossroads-cli
uv python install 3.12
uv sync --frozen
uv tool install .
export PATH="$HOME/.local/bin:$PATH"
market --help
```

If you already have the checkout, use `git pull --ff-only`, then refresh the installed executable with `uv tool install --force --reinstall-package crossroads-market-cli .`.

In every CLI/agent terminal using the LAN, set:

```sh
export MARKET_API_URL='http://172.20.10.3:8100'
export MARKET_ALLOW_LAN_HTTP=true
```

`MARKET_ALLOW_LAN_HTTP=true` is an explicit opt-in for private IPv4 LAN addresses. Without it, the CLI requires HTTPS for remote connections. Global options precede the command group; for example, `market --profile owner products list`.

## 3. Give each agent its own restricted credential

The simplest route is the dashboard:

1. Sign in as your own business.
2. Open **Connections**.
3. Give your connection a recognizable name, such as `Maya laptop buyer`.
4. Enable **Allow agent trading** before creating it. Read-only credentials cannot submit offers or create requests.
5. Check the backend API address is `http://172.20.10.3:8100/api/v1` and enable **Allow HTTP on this trusted LAN**. This is required for the LAN HTTP endpoint, including when you intend to use the issued token with the CLI.
6. Click **Create connection**. Save the token privately; it is returned only once.

The buyer token receives buyer request and negotiation permissions. A seller trading token receives its own product and negotiation permissions. Neither can change policies, issue more credentials or approve an order. The dashboard's seller trading token does not include image upload permission; use the owner CLI or the separate seller-agent credential described below for uploads.

On the agent laptop, open a fresh Bash terminal and supply only that business's token:

```sh
export MARKET_API_URL='http://172.20.10.3:8100'
export MARKET_ALLOW_LAN_HTTP=true
export MARKET_WORKSPACE='ws-buyer'  # Seller A: ws-forma; Seller B: ws-nord
export MARKET_CONFIG="$HOME/.config/neopact-agent/config.json"
read -r -s -p 'Agent token: ' MARKET_TOKEN
printf '\n'
export MARKET_TOKEN
market auth whoami --json
market agent instructions --json
market agent inbox --json
```

Verify `kind` is `agent` and that the reported role/workspace matches your business. Start your chosen local LLM agent from this terminal so it inherits the environment, or set the same variables in its protected runtime environment. Do not put the token in the prompt or a shared transcript. Each runtime needs shell/CLI tool access. Reading pictures additionally needs an image-reading tool and a vision-capable model.

Keep human passwords, browser sessions and owner CLI profiles outside the agent's accessible environment. Separate CLI config files avoid accidental profile reuse; they do not sandbox a model with full filesystem access. Use a separate OS account/container when you need enforced runtime isolation.

## 4. Human owners: inspect or configure your private rules

Do this in a separate human-operated terminal, not the terminal used to launch your LLM:

```sh
export MARKET_API_URL='http://172.20.10.3:8100'
export MARKET_ALLOW_LAN_HTTP=true
export MARKET_CONFIG="$HOME/.config/neopact-owner/config.json"
unset MARKET_TOKEN MARKET_WORKSPACE
market --profile owner auth login --email forma@demo.local
market --profile owner workspace use ws-forma
market --profile owner rules show --product prod-forma --json
```

Enter `local-market-demo` at the password prompt. Buyer and Nord owners substitute their email/workspace. The buyer runs `rules show` without `--product`; Nord uses `--product prod-nord`.

For the primary exercise, the seeded rules already work. The Forma asking price is €95/chair, with a private €83 floor, 30% minimum deposit and discount eligibility from 50 chairs. Nord asks €110/chair, with a €99 floor and 50% minimum deposit. Do not give an opposing agent the other business's rules. These fixture values are listed here for the human demo organizers. Give each LLM only its role prompt, its own reviewed request/brief and the protocol docs; do not feed it this whole organizer guide.

To change a floor, inspect `rules show` first. Save this example as `seller-rules.json`, replacing `expected_version` with the returned `version`, then apply it before starting negotiations:

```json
{
  "expected_version": 1,
  "rules": {
    "min_unit_price": 8300,
    "max_discount_percent": 20,
    "min_deposit_percent": 30,
    "discount_min_quantity": 50
  }
}
```

```sh
market --profile owner rules apply --product prod-forma --file seller-rules.json --json
```

Amounts are integer EUR cents: `8300` is €83. The seller seeks a better price above its effective floor; the floor is not its automatic quote. The effective floor also includes discount and minimum-quantity rules. Product rules cannot relax workspace rules. Rule/product/gallery changes invalidate affected current offers and approvals.

If you need a seller agent with image upload capability, the human owner can issue it from the CLI checkout:

```sh
umask 077
market --profile owner credentials create --file examples/seller-agent.json --json > "$HOME/seller-agent-credential.json"
```

The output file contains a secret. Transfer only to that seller's private runtime and remove it when no longer needed. For negotiation only, use `examples/seller-negotiator.json`. The buyer equivalent is `examples/buyer-agent.json`.

## 5. Main exercise: one buyer, two competing sellers

Use the seeded catalogue so everyone starts with a reproducible case:

- Buyer needs **80 polypropylene stackable chairs in Sofia**, by **14 days from today**.
- Buyer private limit: **€9,000 including delivery**, at most **60% deposit**. Try to achieve less; this is a ceiling, not a target offer.
- Forma can supply 80; its seed delivery charge is €240 and lead time is 12 days.
- Nord can supply 80; its seed delivery charge is €160 and lead time is 8 days.
- Atelier has only 45 and a 21-day lead time, so matching gives concrete exclusion reasons.

The buyer agent/terminal first inspects the catalogue and actual image files:

```sh
market products list --material polypropylene --destination Sofia --json
market products show prod-forma --json
market products images read prod-forma --all --output-dir ./private-images/forma --json
market products images read prod-nord --all --output-dir ./private-images/nord --json
```

Open the returned image paths with your agent's image tool. The seeded pictures are demo illustrations. A JSON caption/manifest alone is not visual inspection.

The buyer creates one reviewed request. From the CLI checkout, generate a valid date without editing a stale example:

```sh
umask 077
uv run python - <<'PY' > team-request.json
from datetime import date, timedelta
import json
print(json.dumps({
    "title": "Team demo: 80 office chairs",
    "description": "Private buyer objective: equip our office and preserve cash.",
    "quantity": 80,
    "material": "polypropylene",
    "stackable": True,
    "destination": "Sofia",
    "latest_delivery": (date.today() + timedelta(days=14)).isoformat(),
    "max_total": 900000,
    "max_deposit_percent": 60,
    "preference": "lower_deposit"
}, indent=2))
PY
market requests create --file team-request.json --idempotency-key team-chairs-request-001 --json
```

Copy the returned `id` into `REQUEST_ID`:

```sh
export REQUEST_ID='PASTE_RETURNED_REQUEST_ID'
market requests launch "$REQUEST_ID" --idempotency-key team-chairs-launch-001 --json
market requests matches "$REQUEST_ID" --json
market requests show "$REQUEST_ID" --json
```

This opens separate rooms for the eligible products. Save the correct room IDs from the response. Seller A sees only its own rooms; Seller B cannot inspect Seller A's private conversation. Do not reuse these idempotency keys for a different new request; choose `002`, `003`, etc. for later exercises. On an uncertain retry of the same operation, retain the same key and exact payload.

Only one buyer should create this exercise request. If your LLM creates it for you, skip the manual creation rather than creating a duplicate.

## 6. Give agents meaningful business goals, then start them

Open a separate agent session on each participating laptop. Give the buyer [the buyer prompt](LAN_BUYER_PROMPT.md), and each seller [the seller prompt](LAN_SELLER_PROMPT.md). Point it at the CLI's `docs/AGENT_GUIDE.md` and `docs/CONVERSATION.md`. Tell it the actual request/room ID and its owner's goal. Use your own selected model/provider; there is no mandatory provider key in the marketplace.

For an MCP-connected client, use **Connections → Set up your negotiator** instead: enter the objective, select the inbox or an existing target, generate and copy the prompt into your own AI session. See [MCP setup below](#9-optional-connect-an-mcp-capable-local-agent-host). Each agent starts eligible negotiations immediately and checks for replies/new rooms every 20 seconds while the session stays active. It does not ask before routine offers or questions; it reports a suitable agreement for your final dashboard approval. The prompt editor also generates a resume prompt for reopening a session without duplicating work. Full details: [agent prompt guide](AGENT_PROMPTS.md).

Private buyer example: “Reduce the deposit while keeping the total within the reviewed budget. We must receive all 80 chairs by the deadline.”

Private seller example: “Protect margin and try to obtain a higher unit price. A larger deposit is helpful, but read our hard rules and discuss feasible tradeoffs.”

For durable goals, the human owner can save a private room brief before starting the agents:

```sh
market --profile owner negotiations context ROOM_ID --json
market --profile owner negotiations brief get ROOM_ID --json
```

Save `private-brief.json` with the current room version and returned brief version. A new brief normally has version 0:

```json
{
  "expected_version": 1,
  "expected_brief_version": 0,
  "goals": "Preserve cash. Prefer a lower deposit within our hard budget.",
  "shareable_needs": "All 80 chairs must arrive by our opening date. A smaller upfront payment would help.",
  "requirements": [
    {"id":"full-quantity","label":"All 80 chairs","kind":"hard","field":"quantity","operator":"eq","value":80,"shareable":true,"resolution":"open"},
    {"id":"cash-flow","label":"Prefer a deposit of 30% or less","kind":"preference","field":"deposit_percent","operator":"lte","value":30,"shareable":true,"resolution":"open"}
  ]
}
```

```sh
market --profile owner negotiations brief set ROOM_ID --file private-brief.json --idempotency-key team-buyer-brief-001 --json
```

Use current versions, not the illustrative `1`. Repeat for each relevant room with distinct keys. A seller sets its own brief using its own goals, not the buyer's document. Private `goals` stay on your side; `shareable_needs` and requirements marked `shareable:true` are public to the counterparty. Do not include private budgets/floors in shared fields. Brief edits start a new run and invalidate offers, claims and approvals, so set them before agents begin or tell the agents to refresh afterwards.

Each agent follows this loop:

```sh
market agent inbox --json
market negotiations context ROOM_ID --json
market negotiations messages ROOM_ID --json
market agent claim ROOM_ID --json
```

It acts only when context permits it, using the claim's current `expected_version` and `claim_token`. A public message file looks like this; substitute current values:

```json
{
  "expected_version": 3,
  "claim_token": "REPLACE_WITH_CURRENT_CLAIM_TOKEN",
  "message": "Would a smaller deposit be possible if we confirm all 80 chairs together?",
  "purpose": "question",
  "image_ids": []
}
```

```sh
market negotiations say ROOM_ID --file question.json --idempotency-key unique-question-001 --json
```

A successful message consumes the claim and passes the turn. The other agent responds, then they exchange exact offers through `negotiations act`. For example, a Forma quote can use the following shape; its price is an example, not an instruction to surrender to that amount:

```json
{
  "type": "propose",
  "expected_version": 5,
  "claim_token": "REPLACE_WITH_CURRENT_CLAIM_TOKEN",
  "terms": {"unit_price": 9500,"quantity": 80,"delivery_date": "REPLACE_WITH_VALID_YYYY-MM-DD","deposit_percent": 30},
  "message": "We can supply all 80 chairs with a 30% deposit.",
  "purpose": "explanation"
}
```

```sh
market negotiations act ROOM_ID --file offer.json --idempotency-key unique-offer-001 --json
```

The delivery date must be between the product's current lead time and the request deadline. `propose`, `counter` and `revise` have different allowed states; choose from the latest `allowed_actions`. Never reuse a consumed claim. The API computes `unit_price × quantity + delivery_charge` and validates your own role's rules; accepting and final approval require both sides' constraints to pass.

To accept the counterparty's exact current offer, use an `accept` action with the current claim/version and its exact `offer_id`. This requests human approval; it is not an order. Message prose never creates contract terms or changes the product's delivery charge. Unverified promises such as warranties are not guaranteed by chat.

## 7. Watch, steer and approve

Both businesses open their **Negotiations** view in the dashboard. They can follow the conversation, current terms and history. A terminal view is also available:

```sh
market negotiations messages ROOM_ID --watch --timeout 300 --interval 2 --text
market agent watch --timeout 300 --interval 20 --jsonl
```

These commands observe; they do not start a model. Agents must keep their runtime active or resume it to process new turns.

To try another tactic, use **Negotiate more** and enter private instructions to your own agent. It starts a fresh bounded attempt and invalidates the previous offer's approvals. The runtime must read the new context and include the pending instruction's ID as `guidance_id` in its next successful action. Guidance cannot waive hard rules. If a runtime stops or its watch expires, tell it to resume the existing room; do not create a new request just to resume.

The buyer compares suppliers:

```sh
market requests compare "$REQUEST_ID" --json
market approvals status ROOM_ID --json
```

Agree on the preferred seller, then:

1. Buyer opens **Approvals**, reviews the exact total, deposit, delivery date, quantity and evidence, and approves that offer.
2. The chosen seller independently reviews and approves the same exact offer.
3. Both open **Orders** or run `market orders list --json`.

Only both approvals create the order and decrement stock. The first approval waits for the other business. Agents and ordinary CLI credentials cannot approve for a human. The buyer should approve only the intended winning deal. This records a demo order; it does not charge a card or fulfill delivery.

## 8. Try the uploaded chair or your own gallery

The host has separately restored the photographed chair under Forma Supply at a **€140 asking price, stock 8**, with a private **€100 minimum**. This follows the seller strategy: the original €100 is the minimum, and the agent tries to negotiate higher. It is separate from `prod-forma` and the 80-chair exercise. Select its real ID rather than guessing:

```sh
market products list --q 'woven' --json
market products show PRODUCT_ID --json
market products images list PRODUCT_ID --json
market products images read PRODUCT_ID --all --output-dir ./private-images/dining-chair --json
```

For a new eight-chair request, copy its reviewed material, stackability, destination and lead time from `products show`; choose a total budget that includes delivery. The restored listing uses `material:"fabric"`, `stackable:false`, a 12-day lead time, Sofia/Plovdiv coverage and a €240 delivery charge per order. Its seller deposit minimum is 20%. Eight chairs at the €100 floor cost **€1,040 total**; at the €140 asking price they cost **€1,360 total**. The seller negotiates between feasible outcomes; the floor is not an automatic quote. Product material descriptions are demonstration assumptions, not a certification inferred from the photograph.

Forma's human owner can upload more photos from its own laptop:

```sh
export MARKET_MEDIA_ROOT="$HOME/Downloads"
market --profile owner products images upload PRODUCT_ID "$HOME/Downloads/front.jpg" "$HOME/Downloads/side.jpg" --json
market --profile owner products images list PRODUCT_ID --json
market --profile owner products images cover PRODUCT_ID READY_IMAGE_ID --json
```

Use actual local filenames. The host's `/home/master/Downloads/stol.jpg` path is not present on a teammate's laptop. JPEG/PNG/WebP files are processed asynchronously; wait for `ready` before reading or selecting a cover. Maximums are 10 active images/product, 10 MB/file and 25 million pixels/file. Image uploads need `images:write`; a negotiation-only credential intentionally lacks it.

## 9. Optional: connect an MCP-capable local agent host

The CLI is sufficient. If your agent host prefers MCP, run the backend's MCP adapter locally on your laptop, pointing at the same LAN API. This requires no local database or Docker stack:

```sh
git clone https://github.com/iivko/crossroads-backend.git
cd crossroads-backend
uv sync --frozen --extra mcp
export NEOPACT_MCP_API_URL='http://172.20.10.3:8100/api/v1'
export NEOPACT_MCP_ALLOW_LAN_HTTP=true
export NEOPACT_MCP_WORKSPACE='ws-buyer'  # Use your own workspace
read -r -s -p 'Agent token: ' NEOPACT_MCP_TOKEN
printf '\n'
export NEOPACT_MCP_TOKEN
```

Configure your local MCP host to launch `uv --directory /ABSOLUTE/PATH/crossroads-backend run --extra mcp python -m mcp_server` and securely pass those four variables to the process. For a compatible JSON host, the nonsecret portion looks like:

```json
{
  "mcpServers": {
    "neopact": {
      "command": "uv",
      "args": ["--directory","/ABSOLUTE/PATH/crossroads-backend","run","--extra","mcp","python","-m","mcp_server"],
      "env": {
        "NEOPACT_MCP_API_URL": "http://172.20.10.3:8100/api/v1",
        "NEOPACT_MCP_ALLOW_LAN_HTTP": "true",
        "NEOPACT_MCP_WORKSPACE": "ws-buyer"
      }
    }
  }
}
```

Supply `NEOPACT_MCP_TOKEN` through the host's private environment/secret mechanism. Desktop applications may not inherit terminal variables; follow the repository's `mcp_server/README.md` for a private launcher. Replace the absolute path and workspace. In the dashboard's Connections setup, check the editable API address points to `http://172.20.10.3:8100/api/v1`, enable **Allow HTTP on this trusted LAN**, and use the backend clone's absolute path on your own laptop. The generated configuration then contains the LAN setting. Your teammate's laptop must not use the host computer's checkout path.

Call `get_instructions`, `get_inbox` and `search_catalogue` to confirm it is connected. The MCP adapter uses the same role rules and does not run an LLM. Its `get_product_images` returns metadata only; use the image-reading CLI and your model's image tool to inspect real bytes. This is a local stdio MCP server, not a hosted ChatGPT/Claude web connector.

Then paste the prompt generated in **Connections → Set up your negotiator**, or retrieve the MCP prompt `neopact_negotiator` in a client that supports prompts. Its `wait_for_updates` tool provides the 20-second wait; your AI client must keep executing the loop. After updating this backend checkout, restart its local MCP connection so the new prompt and tools are discovered. No teammate needs to install a local database or a hosted model worker.

## 10. Troubleshooting and another round

| Symptom | What to do |
|---|---|
| Teammate cannot open dashboard | Use `172.20.10.3`, not `localhost`; join the same non-guest LAN; check VPN/client isolation, host sleep and host firewall. The operator must allow inbound TCP 3100 and 8100 from the local network. |
| `insecure_url` | Update CLI, set `MARKET_ALLOW_LAN_HTTP=true`, and use the exact private IPv4 address. MCP has its own opt-in. |
| Unauthorized after reset | Sign in again and issue a new credential. Verify the token belongs to the intended business. |
| Permission denied | Check `auth whoami`; read-only tokens cannot negotiate. Use an owner for policies/credential issuance, an appropriate seller token for image writes, and a human browser for approvals. |
| Stale version, wrong turn or expired claim | Read current context, reconsider the action and obtain a fresh claim when your turn is available. Do not blindly replay old model decisions against a new version. |
| Ambiguous network failure on a write | Preserve the original payload and idempotency key; retry the same operation before creating a new mutation. |
| No conversation appears | The platform has no built-in provider. Start/resume both external agents; inspect their own inboxes and runtime errors. |
| A room requests human review | Read the private question and respond with dashboard guidance. Change a hard requirement separately if the owner actually intends to change it. |
| Image remains pending | The host checks the media worker. Do not repeatedly upload the same successful file. |
| No supplier matches | Read `requests matches`; check stock, material, stackability, destination and lead time. |

After an order, stock has changed. For another exercise, choose new request/idempotency keys and verify remaining inventory. Ask the operator for a deliberate reset only when the team wants to discard all current negotiations and orders.

## 11. Host operations

The current host is already configured and running. Teammates do not run Docker, PostgreSQL or MinIO locally. On the host, run from the backend checkout:

```sh
docker compose ps
docker compose logs --tail=60 api worker
# Resume after a normal stop; keeps all current data:
docker compose up -d
```

The ignored backend `.env` selects `compose.yaml:compose.lan.yaml` through `COMPOSE_FILE`. Its relevant nonsecret LAN settings are:

```dotenv
COMPOSE_FILE=compose.yaml:compose.lan.yaml
LAN_BIND_IP=172.20.10.3
FRONTEND_URL=http://172.20.10.3:3100
ALLOWED_ORIGINS=http://localhost:3100,http://127.0.0.1:3100,http://172.20.10.3:3100
COOKIE_SECURE=false
```

`FRONTEND_URL` makes CLI/agent approval links open the LAN dashboard. Password login is used here; provider identity callbacks require HTTPS outside loopback.

The override adds the exact LAN interface on ports 3100 and 8100 while retaining localhost access. PostgreSQL 55433 and MinIO 9100/9101 stay bound to localhost. Use a trusted LAN with demo accounts; do not forward router ports. Google/ChatGPT website identity sign-in remains unconfigured, and the one-click local preview remains disabled on LAN. Both are separate from using your own LLM through CLI/MCP.

If DHCP changes the host address, update `LAN_BIND_IP`, `FRONTEND_URL` and the exact dashboard origin in `ALLOWED_ORIGINS`, run `docker compose up -d --force-recreate api worker frontend`, and give teammates the new dashboard/API URLs. Their CLI/MCP environments need that new address too. Reserve the host's address in your router when convenient.

For more businesses, the host operator can create a separate role-bound account without sharing another team's login:

```sh
docker compose exec api python -m market.manage add-user \
  --email teammate@example.test --name 'Team Buyer' \
  --workspace 'Team Procurement' --role buyer
```

This prompts privately for a password. Use `--role seller` for a supplier. New sellers must create products and owners should review rules before trading. The demo-only reset command refuses databases containing these additional accounts; full volume removal would delete them too. Do not reset while teammates are trading. A paired database/storage backup was taken before this initial reset.

References: [CLI commands](https://github.com/iivko/crossroads-cli/blob/main/docs/COMMANDS.md), [agent procedure](https://github.com/iivko/crossroads-cli/blob/main/docs/AGENT_GUIDE.md), [conversation and private briefs](https://github.com/iivko/crossroads-cli/blob/main/docs/CONVERSATION.md), [buyer/seller authorization](https://github.com/iivko/crossroads-backend/blob/main/docs/AUTHORIZATION.md), [MCP setup](https://github.com/iivko/crossroads-backend/blob/main/mcp_server/README.md).
