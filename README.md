# Sex Health News

Independent reporting on sexual health, rights, and wellness for all.

Live at **[sexhealthnew.com](https://sexhealthnew.com)**

An automated news archive that continuously collects articles from global sources, curates and categorizes them, and publishes them through a clean editorial web interface.

---

## What it does

- **Collects** news from 16+ RSS feeds and NewsAPI every hour
- **Curates** each article using Claude AI — scoring relevance, assigning a category, severity level, and a one-line summary
- **Stores** qualifying articles in a PostgreSQL database
- **Publishes** them on a live web interface with categories, search, pagination, related articles, and dark mode
- **Authenticates** users via email/password or OAuth (Google, LinkedIn, X)

## Categories tracked

| Category | Examples |
|---|---|
| Sexual Health & Wellness | Sexual function, sexual satisfaction, menstrual health, fertility, PCOS, endometriosis |
| Reproductive Health & Policy | Abortion access, contraception regulation, family planning laws |
| Maternal & Child Health | Pregnancy care, childbirth, postpartum care, maternal mortality, child sexual health |
| Infectious Diseases & STIs | HIV/AIDS, STI testing and treatment, viral infections, prevention strategies |
| Mental Health & Sexuality | Body image, anxiety, depression, sexual dysfunction, relationships |
| LGBTQ+ Rights & Issues | Legal rights, discrimination, same-sex marriage, trans healthcare, gender identity |
| Sex Education & Literacy | School curriculum, public awareness campaigns, misinformation |
| Sexual Violence & Consent | Assault, harassment, survivor support, consent education |
| Sex Workers & Adult Industry | Sex work legalization, labor protections, content creators, industry safety |

## Quick start

### Prerequisites
- Python 3.10 or later
- Docker (for PostgreSQL)
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### Setup (first time)

```bash
# 1. Clone and enter the project
cd sexhealthnews

# 2. Copy environment template
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY (required)

# 3. Start PostgreSQL (in one terminal)
./start-postgres.sh      # Linux / macOS
start-postgres.bat       # Windows

# 4. Start the app (in another terminal)
./run.sh                 # Linux / macOS
run.bat                  # Windows
make run                 # any platform with make
```

Open **http://localhost:8000** to see the live feed.

### Admin Dashboard

In another terminal:
```bash
./run_admin.sh           # Linux / macOS
run_admin.bat            # Windows
```

Open **http://127.0.0.1:8001** to access the admin panel.

### pgAdmin Database Browser

Open **http://localhost:5050** to browse and manage the database.
- Email: `admin@localhost`
- Password: `admin`

## Modern Design

Built for 18-35 year olds with:
- 🎨 Vibrant cyan & coral color palette with gradients
- ⚡ Contemporary typography and spacing
- 📱 Mobile-first responsive design
- 🌙 Dark mode support
- ♿ WCAG AA accessibility compliance

View the complete **[Design System](docs/DESIGN_SYSTEM.html)** for colors, typography, components, and guidelines.

## Features

- 🔍 **Full-text search** across all articles
- 📰 **Categories** organized by sexual health topics
- 🔐 **User accounts** with bookmarks and personalized newsletters
- 🔗 **OAuth social login** (Google, LinkedIn, Microsoft)
- 📧 **Email verification** and password reset
- 🤖 **AI curation** using Claude Haiku
- 📊 **Admin dashboard** for content management
- 🌐 **Responsive web design** optimized for all devices

## API keys

| Key | Where to get it | Required? |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Yes — powers curation |
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org) (free tier) | No — adds keyword search on top of RSS |
| `RESEND_API_KEY` | [resend.com](https://resend.com) | No — enables email verification and password reset |
| `JWT_SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` | Yes in production |

## Project structure

```
sexhealthnews/
├── main.py                          # App entry point, scheduler startup
├── admin/                           # Local admin dashboard (port 8001)
├── run.bat / run_admin.bat          # Windows launchers
├── run.sh / Makefile                # Linux / macOS launchers
├── fly_secrets.ps1                  # Push .env secrets to Fly.io
├── requirements.txt
├── .env                             # Your keys (git-ignored)
├── .env.example                     # Key template
├── backend/
│   ├── collectors/
│   │   ├── rss_collector.py         # RSS feeds
│   │   └── newsapi_collector.py     # NewsAPI keyword queries
│   ├── processors/
│   │   └── curator.py               # Claude Haiku scoring + categorization
│   ├── database/
│   │   ├── models.py                # SQLAlchemy models (Article, CollectionLog, User)
│   │   └── db.py                    # Async PostgreSQL engine
│   ├── auth/                        # JWT + OAuth (Google, LinkedIn, X)
│   ├── scheduler.py                 # Hourly pipeline (collect → curate → store → prune)
│   └── routes.py                    # FastAPI routes + REST API
├── frontend/
│   ├── templates/                   # Jinja2 HTML templates
│   └── static/
│       ├── css/main.css             # Stylesheet
│       └── js/main.js               # Minimal frontend JS
└── data/
    └── (PostgreSQL database)
```

## REST API

| Endpoint | Description |
|---|---|
| `GET /api/articles?limit=20&category=...` | List articles as JSON |
| `GET /api/stats` | Archive statistics |
| `POST /api/trigger-collection` | Manually trigger the pipeline |
| `GET /sitemap.xml` | Sitemap for SEO |

## Configuration

All settings live in `.env`:

```env
ANTHROPIC_API_KEY=...
NEWSAPI_KEY=...

APP_HOST=0.0.0.0
APP_PORT=8000
APP_URL=http://localhost:8000

# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=change-me-in-production

COLLECTION_INTERVAL_MINUTES=60
MIN_RELEVANCE_SCORE=0.65

# Set to 0 to keep articles forever
ARTICLE_RETENTION_DAYS=0

# Email (Resend — leave empty to disable)
RESEND_API_KEY=
FROM_EMAIL=Sex Health News <noreply@sexhealthnew.com>

# OAuth (leave empty to disable a provider)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
TWITTER_CLIENT_ID=
TWITTER_CLIENT_SECRET=
```

See `docs/OAUTH_SETUP.md` for step-by-step OAuth provider setup.

## Deployment (Fly.io)

```bash
# Install Fly CLI (Windows)
pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"

# Login
fly auth login

# Push .env secrets to Fly.io
.\fly_secrets.ps1

# Deploy
fly deploy
```

For subsequent deploys after pushing changes to GitHub:

```bash
fly deploy
```

### Custom domain

```bash
# Add certs
fly certs add sexhealthnew.com -a sexhealthnews
fly certs add www.sexhealthnew.com -a sexhealthnews

# Update APP_URL secret
fly secrets set APP_URL=https://sexhealthnew.com -a sexhealthnews
```

In your DNS provider add:
- `A` record: `@` → your Fly.io v4 IP (`fly ips list -a sexhealthnews`)
- `AAAA` record: `@` → your Fly.io v6 IP
- `CNAME` record: `www` → `sexhealthnews.fly.dev.`

See `docs/OAUTH_SETUP.md` → Production checklist for updating OAuth redirect URIs after deploying.

---

## Documentation

| Document | Purpose |
|---|---|
| **[Design System](docs/DESIGN_SYSTEM.html)** | Colors, typography, components, and brand guidelines |
| **[GUIDE.md](GUIDE.md)** | Complete operator guide for setup, configuration, and deployment |
| **[CLAUDE.md](CLAUDE.md)** | Developer guide for working with the codebase |
| **[docs/OVERVIEW.md](docs/OVERVIEW.md)** | Project architecture and tech stack |
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | System design and module organization |
| **[docs/DATA_MODEL.md](docs/DATA_MODEL.md)** | Database schema and relationships |

## Development

```bash
# Watch for changes and auto-reload
make run         # main app
make admin       # admin dashboard

# Manually trigger the collection pipeline
make trigger

# Reset database (careful!)
make reset
```

## Support & Contributing

- **Issues**: Report bugs on [GitHub Issues](https://github.com/azenkwed/sexhealthnews/issues)
- **Questions**: See [GUIDE.md](GUIDE.md) for detailed documentation
- **Development**: See [CLAUDE.md](CLAUDE.md) for setup and coding guidelines
