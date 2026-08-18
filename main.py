from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))
DB_PATH = Path(os.getenv("BABY_NAMES_DB_PATH", str(BASE_DIR / "baby_names.db")))
ALLOWED_USERS = {"user1", "user2"}

if IS_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row

# Load names
with open(BASE_DIR / "names.json", "r", encoding="utf-8") as f:
    NAMES = json.load(f)

BASE_NAME_LOOKUP = {
    str(item.get("name")): item for item in NAMES if item.get("name")
}


def parse_csv_values(raw: str | None):
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def item_matches_filters(item: dict, selected_genders: set[str], selected_origins: set[str]):
    item_gender = str(item.get("gender", "")).strip().lower()
    item_origin = str(item.get("origin", "")).strip().lower()
    gender_ok = not selected_genders or item_gender in selected_genders
    origin_ok = not selected_origins or item_origin in selected_origins
    return gender_ok and origin_ok


def names_to_items(names: list[str], selected_genders: set[str], selected_origins: set[str]):
    lookup = get_name_lookup()
    items = []
    for name in names:
        item = lookup.get(name)
        if not item:
            continue
        if item_matches_filters(item, selected_genders, selected_origins):
            items.append(item)
    return items


def _sql(query: str):
    if IS_POSTGRES:
        return query.replace("?", "%s")
    return query


def get_name_lookup():
    lookup = dict(BASE_NAME_LOOKUP)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT name, gender, origin
            FROM suggestions
            ORDER BY created_at DESC
            """
        ).fetchall()
    for row in rows:
        name = str(row["name"]).strip()
        if not name:
            continue
        lookup[name] = {
            "name": name,
            "gender": str(row["gender"]).strip(),
            "origin": str(row["origin"]).strip(),
        }
    return lookup


def get_candidates_for_user(user: str):
    candidates = []
    seen_names = set()
    with get_conn() as conn:
        suggestion_rows = conn.execute(
            """
            SELECT name, gender, origin
            FROM suggestions
            WHERE to_user = ?
            ORDER BY created_at DESC
            """,
            (user,),
        ).fetchall()

    for row in suggestion_rows:
        name = str(row["name"]).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        candidates.append(
            {
                "name": name,
                "gender": str(row["gender"]).strip(),
                "origin": str(row["origin"]).strip(),
            }
        )

    for item in NAMES:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        candidates.append(item)

    return candidates


class DBConnection:
    def __init__(self, raw_conn):
        self.raw_conn = raw_conn

    def execute(self, query: str, params=()):
        return self.raw_conn.execute(_sql(query), params)

    def commit(self):
        self.raw_conn.commit()

    def rollback(self):
        self.raw_conn.rollback()

    def close(self):
        self.raw_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            try:
                self.rollback()
            except Exception:
                pass
        self.close()


def get_conn():
    if IS_POSTGRES:
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return DBConnection(raw)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(DB_PATH)
    raw.row_factory = sqlite3.Row
    return DBConnection(raw)


def init_db():
    with get_conn() as conn:
        if IS_POSTGRES:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS likes (
                    "user" TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY ("user", name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dislikes (
                    "user" TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY ("user", name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    "user" TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS suggestions (
                    id BIGSERIAL PRIMARY KEY,
                    from_user TEXT NOT NULL,
                    to_user TEXT NOT NULL,
                    name TEXT NOT NULL,
                    gender TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "INSERT INTO users (\"user\", display_name) VALUES ('user1', 'user1') ON CONFLICT (\"user\") DO NOTHING"
            )
            conn.execute(
                "INSERT INTO users (\"user\", display_name) VALUES ('user2', 'user2') ON CONFLICT (\"user\") DO NOTHING"
            )
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS likes (
                    "user" TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY ("user", name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dislikes (
                    "user" TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY ("user", name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    "user" TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user TEXT NOT NULL,
                    to_user TEXT NOT NULL,
                    name TEXT NOT NULL,
                    gender TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO users (\"user\", display_name) VALUES ('user1', 'user1')"
            )
            conn.execute(
                "INSERT OR IGNORE INTO users (\"user\", display_name) VALUES ('user2', 'user2')"
            )
        conn.commit()


def ensure_user(user: str):
    if user not in ALLOWED_USERS:
        raise ValueError("Invalid user. Use 'user1' or 'user2'.")


def get_user_display_names():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT \"user\", display_name FROM users WHERE \"user\" IN ('user1', 'user2')"
        ).fetchall()
    labels = {"user1": "user1", "user2": "user2"}
    for row in rows:
        labels[row["user"]] = row["display_name"]
    return labels


def get_other_user(user: str):
    return "user2" if user == "user1" else "user1"


def get_available_filters():
    lookup = get_name_lookup()
    genders = sorted(
        {
            str(item.get("gender", "")).strip()
            for item in lookup.values()
            if str(item.get("gender", "")).strip()
        },
        key=str.lower,
    )
    origins = sorted(
        {
            str(item.get("origin", "")).strip()
            for item in lookup.values()
            if str(item.get("origin", "")).strip()
        },
        key=str.lower,
    )
    return {"genders": genders, "origins": origins}


@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/manifest.json")
def manifest():
    return FileResponse(BASE_DIR / "static" / "pwa" / "manifest.json", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(BASE_DIR / "static" / "pwa" / "sw.js", media_type="application/javascript")


@app.get("/filters")
def get_filters():
    return get_available_filters()


@app.get("/users")
def get_users():
    return get_user_display_names()


@app.post("/suggestions")
def create_suggestion(payload: dict):
    from_user = payload.get("from_user")
    name = str(payload.get("name", "")).strip()
    gender = str(payload.get("gender", "")).strip().upper()
    origin = str(payload.get("origin", "")).strip()

    try:
        ensure_user(from_user)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    if not name or not origin:
        return JSONResponse(status_code=400, content={"error": "Name and origin are required."})

    if gender not in {"M", "F"}:
        return JSONResponse(status_code=400, content={"error": "Gender must be M or F."})

    if len(name) > 80 or len(origin) > 60:
        return JSONResponse(status_code=400, content={"error": "Name/origin too long."})

    to_user = get_other_user(from_user)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO suggestions (from_user, to_user, name, gender, origin)
            VALUES (?, ?, ?, ?, ?)
            """,
            (from_user, to_user, name, gender, origin),
        )
        if IS_POSTGRES:
            conn.execute(
                "INSERT INTO likes (\"user\", name) VALUES (?, ?) ON CONFLICT (\"user\", name) DO NOTHING",
                (from_user, name),
            )
        else:
            conn.execute("INSERT OR IGNORE INTO likes (\"user\", name) VALUES (?, ?)", (from_user, name))
        conn.execute("DELETE FROM dislikes WHERE \"user\" = ? AND name = ?", (from_user, name))
        other_like = conn.execute(
            "SELECT 1 FROM likes WHERE \"user\" = ? AND name = ?",
            (to_user, name),
        ).fetchone()
        conn.commit()

    return {"status": "ok", "to_user": to_user, "match": bool(other_like)}


@app.get("/suggestions")
def get_suggestions(user: str, genders: str | None = None, origins: str | None = None):
    try:
        ensure_user(user)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    selected_genders = parse_csv_values(genders)
    selected_origins = parse_csv_values(origins)
    labels = get_user_display_names()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT name, gender, origin, from_user, created_at
            FROM suggestions
            WHERE to_user = ?
            ORDER BY created_at DESC
            """,
            (user,),
        ).fetchall()

    suggestions = []
    for row in rows:
        item = {
            "name": row["name"],
            "gender": row["gender"],
            "origin": row["origin"],
        }
        if not item_matches_filters(item, selected_genders, selected_origins):
            continue
        suggestions.append(
            {
                "name": row["name"],
                "gender": row["gender"],
                "origin": row["origin"],
                "from_user": row["from_user"],
                "from_display_name": labels.get(row["from_user"], row["from_user"]),
            }
        )

    return suggestions


@app.post("/users")
def update_users(payload: dict):
    user1_name = str(payload.get("user1_name", "")).strip()
    user2_name = str(payload.get("user2_name", "")).strip()

    if not user1_name or not user2_name:
        return JSONResponse(status_code=400, content={"error": "Both names are required."})

    if len(user1_name) > 60 or len(user2_name) > 60:
        return JSONResponse(status_code=400, content={"error": "Names must be 60 chars or fewer."})

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (\"user\", display_name) VALUES ('user1', ?) ON CONFLICT(\"user\") DO UPDATE SET display_name = excluded.display_name",
            (user1_name,),
        )
        conn.execute(
            "INSERT INTO users (\"user\", display_name) VALUES ('user2', ?) ON CONFLICT(\"user\") DO UPDATE SET display_name = excluded.display_name",
            (user2_name,),
        )
        conn.commit()

    return {"status": "ok", "users": get_user_display_names()}


@app.post("/reset")
def reset_data(payload: dict):
    confirm = bool(payload.get("confirm", False))
    if not confirm:
        return JSONResponse(status_code=400, content={"error": "Confirmation is required."})

    with get_conn() as conn:
        conn.execute("DELETE FROM likes")
        conn.execute("DELETE FROM dislikes")
        conn.execute("DELETE FROM suggestions")
        conn.commit()

    return {"status": "ok"}


@app.get("/next")
def next_name(user: str, cursor: int = 0, genders: str | None = None, origins: str | None = None):
    try:
        ensure_user(user)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    selected_genders = parse_csv_values(genders)
    selected_origins = parse_csv_values(origins)
    candidates = get_candidates_for_user(user)

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT name FROM likes WHERE "user" = ?
            UNION
            SELECT name FROM dislikes WHERE "user" = ?
            """,
            (user, user),
        ).fetchall()
    seen = {row["name"] for row in rows}

    index = max(cursor, 0)
    while index < len(candidates):
        item = candidates[index]
        name = item.get("name")
        item_gender = str(item.get("gender", "")).strip().lower()
        item_origin = str(item.get("origin", "")).strip().lower()

        gender_ok = not selected_genders or item_gender in selected_genders
        origin_ok = not selected_origins or item_origin in selected_origins

        if name not in seen and gender_ok and origin_ok:
            result = dict(item)
            result["index"] = index
            return result
        index += 1

    if index >= len(candidates):
        return {"done": True}
    return {"done": True}


@app.post("/like")
def like(payload: dict):
    user = payload.get("user")
    name = payload.get("name")

    if not user or not name:
        return JSONResponse(status_code=400, content={"error": "Missing user or name."})

    try:
        ensure_user(user)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    other = get_other_user(user)

    with get_conn() as conn:
        if IS_POSTGRES:
            conn.execute(
                "INSERT INTO likes (\"user\", name) VALUES (?, ?) ON CONFLICT (\"user\", name) DO NOTHING",
                (user, name),
            )
        else:
            conn.execute("INSERT OR IGNORE INTO likes (\"user\", name) VALUES (?, ?)", (user, name))
        conn.execute("DELETE FROM dislikes WHERE \"user\" = ? AND name = ?", (user, name))
        other_like = conn.execute(
            "SELECT 1 FROM likes WHERE \"user\" = ? AND name = ?",
            (other, name),
        ).fetchone()
        conn.commit()

    return {"status": "ok", "match": bool(other_like)}


@app.post("/dislike")
def dislike(payload: dict):
    user = payload.get("user")
    name = payload.get("name")

    if not user or not name:
        return JSONResponse(status_code=400, content={"error": "Missing user or name."})

    try:
        ensure_user(user)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    with get_conn() as conn:
        if IS_POSTGRES:
            conn.execute(
                "INSERT INTO dislikes (\"user\", name) VALUES (?, ?) ON CONFLICT (\"user\", name) DO NOTHING",
                (user, name),
            )
        else:
            conn.execute("INSERT OR IGNORE INTO dislikes (\"user\", name) VALUES (?, ?)", (user, name))
        conn.execute("DELETE FROM likes WHERE \"user\" = ? AND name = ?", (user, name))
        conn.commit()

    return {"status": "ok"}


@app.get("/likes")
def get_likes(user: str, genders: str | None = None, origins: str | None = None):
    try:
        ensure_user(user)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    selected_genders = parse_csv_values(genders)
    selected_origins = parse_csv_values(origins)

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM likes WHERE \"user\" = ? ORDER BY created_at DESC",
            (user,),
        ).fetchall()
    names = [row["name"] for row in rows]
    items = names_to_items(names, selected_genders, selected_origins)
    return items


@app.get("/dislikes")
def get_dislikes(user: str, genders: str | None = None, origins: str | None = None):
    try:
        ensure_user(user)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    selected_genders = parse_csv_values(genders)
    selected_origins = parse_csv_values(origins)

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM dislikes WHERE \"user\" = ? ORDER BY created_at DESC",
            (user,),
        ).fetchall()
    names = [row["name"] for row in rows]
    items = names_to_items(names, selected_genders, selected_origins)
    return items


@app.get("/matches")
def get_matches(user: str | None = None, genders: str | None = None, origins: str | None = None):
    selected_genders = parse_csv_values(genders)
    selected_origins = parse_csv_values(origins)

    if user:
        try:
            ensure_user(user)
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT l1.name
            FROM likes l1
            JOIN likes l2 ON l1.name = l2.name
            WHERE l1."user" = 'user1' AND l2."user" = 'user2'
            ORDER BY lower(l1.name)
            """
        ).fetchall()
    names = [row["name"] for row in rows]
    items = names_to_items(names, selected_genders, selected_origins)
    return items


@app.get("/history")
def get_history(user: str, genders: str | None = None, origins: str | None = None):
    try:
        ensure_user(user)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    selected_genders = parse_csv_values(genders)
    selected_origins = parse_csv_values(origins)

    with get_conn() as conn:
        likes_rows = conn.execute(
            "SELECT name FROM likes WHERE \"user\" = ? ORDER BY created_at DESC",
            (user,),
        ).fetchall()
        dislikes_rows = conn.execute(
            "SELECT name FROM dislikes WHERE \"user\" = ? ORDER BY created_at DESC",
            (user,),
        ).fetchall()
        match_rows = conn.execute(
            """
            SELECT l1.name
            FROM likes l1
            JOIN likes l2 ON l1.name = l2.name
            WHERE l1."user" = 'user1' AND l2."user" = 'user2'
            ORDER BY lower(l1.name)
            """
        ).fetchall()

    likes_names = [row["name"] for row in likes_rows]
    dislikes_names = [row["name"] for row in dislikes_rows]
    match_names = [row["name"] for row in match_rows]

    return {
        "likes": names_to_items(likes_names, selected_genders, selected_origins),
        "dislikes": names_to_items(dislikes_names, selected_genders, selected_origins),
        "matches": names_to_items(match_names, selected_genders, selected_origins),
    }
