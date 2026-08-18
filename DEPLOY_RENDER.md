# Deploy on Render

## 1) Push project to GitHub
Upload this folder to a GitHub repository.

## 2) Deploy with Blueprint
- Render Dashboard -> New -> Blueprint
- Select your GitHub repository
- Render detects `render.yaml`
- It creates:
  - a Web Service (`baby-names-app`)
  - a Postgres database (`baby-names-db`)
- Click Deploy

## 3) Verify environment variables
In Render service settings, confirm:
- `DATABASE_URL` is linked from the Render Postgres connection string
- `BABY_NAMES_DB_PATH=/tmp/baby_names.db` exists as fallback only

## 4) Open your public URL
Render gives a URL like:
`https://baby-names-app.onrender.com`

## 5) Install on iPhone
In Safari on iPhone:
- open the Render URL
- Share -> Add to Home Screen

## Data persistence behavior
- Production: app uses Postgres automatically when `DATABASE_URL` is set.
- Local/dev fallback: app uses SQLite (`BABY_NAMES_DB_PATH`) when `DATABASE_URL` is missing.
