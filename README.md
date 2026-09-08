# easymakebot

## Local setup

```bash
# 1. Run a PostgreSQL database (if you don't already have one, the easiest way is Docker)
docker run --name easymakebot-db -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=easymakebot -p 5432:5432 -d postgres:16

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create the .env file
cp .env.example .env
# Set the following inside .env:
#   BOT_TOKEN            → bot token from @BotFather
#   PLATFORM_ADMIN_ID    → your numeric Telegram ID (get it from @userinfobot)
#   ENCRYPTION_KEY        → generate one with the command below:
#     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   DATABASE_URL          → the default value is fine if you used the command above
#   WEBAPP_URL             → public HTTPS URL for the visual flow builder Mini App (see below)
#   WEBAPP_PORT            → local port the Mini App server listens on (default 8080)

# 5. Build the visual flow builder Mini App frontend
cd webapp && npm install && npm run build && cd ..

# 6. Run the bot
python -m bot.main
```

Database tables are created automatically (via `init_db`), no manual migration needed.

If everything is set up correctly, you'll see "Bot is running..." in the terminal.
Now go to Telegram and send `/start` to your bot — you should get the welcome message.

### Visual flow builder (Mini App)

Selecting a bot also offers a "🎨 Visual Builder" button that opens a Telegram Mini
App — a drag-and-drop canvas for building the bot's `/start` flow. Telegram requires
the Mini App URL to be HTTPS, so for local development, tunnel the bot's built-in
web server (`WEBAPP_PORT`, default 8080) and put the tunnel's HTTPS URL in
`WEBAPP_URL`:

```bash
cloudflared tunnel --url http://localhost:8080
```

If `WEBAPP_URL` is empty, the "Visual Builder" button just doesn't appear — every
other feature works as before.

## Project structure

```
easymakebot/
├── bot/
│   ├── config.py               # Reads settings from .env
│   ├── main.py                 # Bot entry point (polling + Mini App server)
│   ├── session.py               # Shared Bot session factory
│   ├── runtime.py               # Live polling loop for each built bot
│   ├── flow_engine.py           # Interpreter for visual-builder flows
│   ├── force_join_gate.py       # Shared force-join gate (legacy + flow engine)
│   ├── webapp_auth.py           # Telegram Mini App initData validation
│   ├── webapp_server.py         # aiohttp server: serves webapp/dist/ + /api/flow
│   ├── states.py                # FSM states
│   ├── keyboards.py             # Keyboards + editable tools list (TOOLS)
│   ├── db/
│   │   ├── base.py               # Database connection
│   │   ├── models.py             # User, BuiltBot, Command, JoinChannel
│   │   └── encrypted_types.py    # Automatic encryption for sensitive fields
│   ├── filters/
│   │   └── admin.py              # Platform admin detection filter
│   └── handlers/
│       ├── start.py              # /start + user registration
│       ├── my_bots.py            # List and select built bots
│       ├── create_bot.py         # Receive token and register new bot
│       ├── tools_menu.py         # Show the tools menu
│       └── tools/
│           ├── define_command.py # Define-command tool
│           └── force_join.py     # Force-join channel tool
├── webapp/                     # Visual flow builder Mini App (React + React Flow)
├── requirements.txt
└── .env.example
```

## Current implemented scenario
1. `/start` → welcome message with user ID + two buttons (View My Bots / Create New Bot)
2. "My Bots" → list of bots + "Create New Bot" button at the end
3. Selecting a bot → enters that bot's edit environment + bottom-screen "Build & Edit Tools" menu
4. "Create New Bot" → receive token from BotFather, validate it, register a new record in the database
5. "Define Command" tool → receive command names (with a special message for the first command/start), "Show Commands" button
6. "Force Join" tool → manage required channels and toggle the join gate on `/start`
7. "🎨 Visual Builder" → opens a Mini App with a drag-and-drop canvas for the bot's `/start` flow, as an alternative to the chat-based tools above

Planned for upcoming steps:
- Conditional branching in the visual flow builder (v1 only supports linear chains)
- Automatic deployment of built bots to the main server

## Deploying to a server

See [`deploy/README.md`](deploy/README.md) — a Docker Compose stack (the bot +
its own Postgres) that shares the WordPress site's Caddy for TLS and serves the
Mini App at `https://app.<domain>`. Deploy the site (`web/`) first.
