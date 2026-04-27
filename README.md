# Warbler

### AI-powered social platform built with Flask, PostgreSQL, and SQLAlchemy

Warbler began as part of <a href="https://www.rithmschool.com/">Rithm School's</a> curriculum and was originally built in collaboration with <a href="https://github.com/jragni">Jhensen Agni</a>. Since then, I independently expanded it beyond the original requirements into a richer, production-oriented application.

## What I Added Beyond the Original Curriculum

### AI-powered product features

- Built a first-party AI assistant experience (`/ai-assistant`) with three workflows:
  - Compose help for draft generation
  - Thread/text summarization with keyword extraction
  - Tone-aware rewrites (professional, witty, concise, friendly)
- Added AI entry points directly in the product flow (message detail + feed actions).
- Improved output safety and consistency with normalization, trimming, and structured response formatting.

### Social feature expansion

- Added reposts, quote posts, bookmarks, and reply threading improvements.
- Added hashtag extraction, hashtag detail pages, and trending hashtag discovery.
- Added notification system upgrades with better unread/read UX and event dedupe.

### Feed and UX quality upgrades

- Implemented engagement-based feed ranking (likes, reposts, replies).
- Added low-signal filtering and pagination for cleaner home feeds.
- Performed a UI consistency sweep across feed, message detail, notifications, and AI assistant:
  - spacing
  - typography rhythm
  - action button state consistency

### Production and reliability improvements

- Hardened auth/session behavior for production:
  - secure cookie settings (`Secure`, `HttpOnly`, `SameSite=Lax`)
  - required `SECRET_KEY` in production
  - session lifecycle tightening
- Added request tracing and diagnostics:
  - request IDs via `X-Request-ID`
  - structured request timing logs
  - `/healthz` endpoint
  - custom `404`/`500` error handling with logging

### Data model and performance work

- Added migration flow with Flask-Migrate/Alembic baseline.
- Added targeted indexes/constraints for high-traffic queries (notifications, hashtags, repost/quote lookups).
- Reduced N+1 query patterns with eager loading on key routes.

### Test and data quality investments

- Added focused test modules for:
  - notifications unread/read transitions
  - feed ranking/filtering behavior
  - repost/quote/hashtags/assistant routes
- Modernized seed data generation with more realistic users/messages and recent timestamps.
- Added safer seed/admin operations:
  - deterministic CSV seed process
  - environment guard for destructive seeding
  - admin bootstrap/update script

## Tech Stack

- Flask
- Python
- PostgreSQL
- SQLAlchemy
- Jinja
- WTForms

## Live Demo

- Original demo: <a href="https://warbler.lillianlakes.com/">Warbler</a>

## Environment Variables

- `DATABASE_URL` (Postgres connection string)
- `SECRET_KEY` (required in production)
- `FLASK_ENV` (`development` or `production`)
- `RENDER=true` (automatically set on Render)

## Local Setup

1. Clone or fork this repository.
2. Create and activate a virtual environment.
3. Install dependencies.

- `python3 -m venv venv`
- `source venv/bin/activate`
- `pip3 install -r requirements.txt`

4. Create database and seed data.

- `createdb warbler`
- `python3 seed.py`

5. (Optional) initialize migrations.

- `flask db init`
- `flask db migrate -m "initial schema"`
- `flask db upgrade`

6. Run the app.

- `flask run`

## Core Functionality

- Authentication: signup, login, profile edit/delete
- Social graph: follow/unfollow
- Messaging: create/read/delete, likes, replies, reposts, quote posts
- Discovery: hashtags + trending
- Notifications: unread tracking + read-state transitions
- AI assistant: compose, summarize, rewrite

## Production Hardening Notes

- Secure session cookie settings in production
- Required secret management in production
- Pagination-first feed behavior (no infinite scroll)
- Request tracing and health checks

### SECRET_KEY Rotation (Production Runbook)

1. Generate a new key: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Set the new `SECRET_KEY` in your production environment.
3. Deploy/restart app instances.
4. Verify `/healthz` and login flow.

Note: rotating `SECRET_KEY` invalidates existing signed sessions, requiring re-login.

## Seed/Admin Operations

- Deterministic demo seed from CSVs:
  - `python3 seed.py`
- Safe operator bootstrap/update:
  - `python3 scripts/bootstrap_user.py --username admin --email admin@example.com --password strongpassword`

## Tests

1. Create test database.

- `createdb warbler-test`

2. Run tests.

- Run all tests: `python3 -m unittest`
- Run one file: `python3 -m unittest test_file_to_run.py`
