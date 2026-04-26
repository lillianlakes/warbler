# Warbler

### A Twitter-like social networking platform that allows users to post, view, like, or unlike messages and view a feed of, follow, or unfollow other users

This project is a part of <a href="https://www.rithmschool.com/">Rithm School's</a> curriculum, and was done in collaboration with my partner <a href="https://github.com/jragni">Jhensen Agni</a> using:

- Flask
- Python
- PostgreSQL
- SQLAlchemy
- Jinja
- WTForms

## Live Demo

- Here is a live demo of the <a href="https://lillian-warbler.herokuapp.com/">Warbler</a> app.

## Environment Variables (recommended)

- `DATABASE_URL` (Postgres connection string)
- `SECRET_KEY` (required in production)
- `FLASK_ENV` (`development` or `production`)
- `RENDER=true` (automatically set on Render)

### Getting started:

1. Clone or fork this repository
2. Setup a virtual environment (inside the repo directory)

- `python3 -m venv venv`
- `source venv/bin/activate`
- `pip3 install -r requirements.txt`

3. Create the database

- `createdb warbler`
- `python3 seed.py`

4. (Optional) initialize migrations

- `flask db init`
- `flask db migrate -m "initial schema"`
- `flask db upgrade`

5. Start the Server

- `flask run`

### Functionality:

- Users can do the following:
  - Login, signup, edit, or delete profile
  - Post, view, like, or unlike messages
  - View a feed of, follow, or unfollow other users
  - Use bookmarks, reposts, quote posts, and notifications
  - Browse hashtags and trending topics
  - Use the built-in AI assistant for compose, summary, and rewrite

## Production Hardening Included

- Secure session cookies in production (`Secure`, `HttpOnly`, `SameSite=Lax`)
- Secret key required in production environments
- Unread notification badge in navbar
- Notification read-state transitions on per-item view and mark-all-read
- Feed supports pagination (`/?page=2`) and intentionally does not use infinite scroll
- Request ID response header (`X-Request-ID`) and request timing logs

### SECRET_KEY Rotation (Production Runbook)

1. Generate a new key: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Set the new `SECRET_KEY` in your production environment variables.
3. Deploy/restart the app so all instances pick up the new key.
4. Verify app health (`/healthz`) and login flow.

Note: rotating `SECRET_KEY` invalidates existing signed sessions, so users will need to log in again.

## Seed/Admin Operations

- Deterministic demo seed from CSVs:
  - `python3 seed.py`
- Safe operator bootstrap/update:
  - `python3 scripts/bootstrap_user.py --username admin --email admin@example.com --password strongpassword`

## Tests:

1. Create the test database

- `createdb warbler-test`

2. Run tests:

- Run all tests: `python3 -m unittest`
- Run specific file: `python3 -m unittest test_file_to_run.py`
