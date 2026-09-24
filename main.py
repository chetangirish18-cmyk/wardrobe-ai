from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import sqlite3

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None
import random
import os
import shutil
import io
import json
import zipfile
import html
import re
import hashlib
import hmac
import secrets
from datetime import date, datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="WARDROBE")

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

SESSION_SECRET = os.getenv("SESSION_SECRET", "change-this-session-secret")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="wardrobe_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB = "wardrobe.db"
STATIC_DIR = "static"
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(STATIC_DIR, "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Render uses a shared Postgres database in production. SQLite remains the
# local-development fallback so the project is still easy to run offline.
USE_POSTGRES = bool(DATABASE_URL)

# ---------------------------------------------------------
# Password authentication
# ---------------------------------------------------------
def normalize_phone(phone: str) -> str:
    phone = (phone or "").strip()
    phone = re.sub(r"[\s().-]", "", phone)
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if phone.startswith("+91") and len(phone) == 13:
        return phone
    if phone.isdigit() and len(phone) == 10:
        return "+91" + phone
    if phone.startswith("+") and 8 <= len(phone[1:]) <= 15:
        return phone
    raise HTTPException(status_code=400, detail="Enter a valid mobile number, e.g. 9876543210 or +919876543210")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def validate_password(password: str):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if len(password) > 128:
        raise HTTPException(status_code=400, detail="Password must be 128 characters or less.")


# ---------------------------------------------------------
# Database / authentication
# ---------------------------------------------------------
def get_db():
    if USE_POSTGRES:
        if psycopg is None:
            raise RuntimeError("psycopg is required when DATABASE_URL is set.")
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
        return conn

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def db_execute(conn, sql, params=()):
    # The application historically used SQLite's ? placeholders. Translate
    # them centrally so the rest of the code stays database-agnostic.
    if USE_POSTGRES:
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def ensure_column(conn, table, column, definition):
    if USE_POSTGRES:
        return
    columns = [r[1] for r in db_execute(conn, f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        db_execute(conn, f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = get_db()
    if USE_POSTGRES:
        statements = [
            """CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                phone TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS clothes (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT,
                category TEXT NOT NULL,
                subtype TEXT NOT NULL,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                price DOUBLE PRECISION DEFAULT 0.0,
                image_url TEXT DEFAULT '',
                is_dirty INTEGER DEFAULT 0,
                is_favorite INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS worn_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT,
                clothes_id BIGINT,
                worn_date TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS outfit_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT,
                top_id BIGINT NOT NULL,
                bottom_id BIGINT NOT NULL,
                shoes_id BIGINT NOT NULL,
                worn_date TEXT NOT NULL,
                weather TEXT DEFAULT '',
                occasion TEXT DEFAULT '',
                feedback INTEGER DEFAULT 0
            )"""
        ]
        for statement in statements:
            db_execute(conn, statement)
    else:
        db_execute(conn, """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT NOT NULL
            )
        """)
        db_execute(conn, """
            CREATE TABLE IF NOT EXISTS clothes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT NOT NULL,
                subtype TEXT NOT NULL,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                price REAL DEFAULT 0.0,
                image_url TEXT DEFAULT '',
                is_dirty INTEGER DEFAULT 0,
                is_favorite INTEGER DEFAULT 0
            )
        """)
        db_execute(conn, """
            CREATE TABLE IF NOT EXISTS worn_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                clothes_id INTEGER,
                worn_date TEXT
            )
        """)
        db_execute(conn, """
            CREATE TABLE IF NOT EXISTS outfit_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                top_id INTEGER NOT NULL,
                bottom_id INTEGER NOT NULL,
                shoes_id INTEGER NOT NULL,
                worn_date TEXT NOT NULL,
                weather TEXT DEFAULT '',
                occasion TEXT DEFAULT '',
                feedback INTEGER DEFAULT 0
            )
        """)
        ensure_column(conn, "users", "password_hash", "TEXT")
        ensure_column(conn, "clothes", "user_id", "INTEGER")
        ensure_column(conn, "clothes", "price", "REAL DEFAULT 0.0")
        ensure_column(conn, "clothes", "image_url", "TEXT DEFAULT ''")
        ensure_column(conn, "clothes", "is_dirty", "INTEGER DEFAULT 0")
        ensure_column(conn, "clothes", "is_favorite", "INTEGER DEFAULT 0")
        ensure_column(conn, "worn_history", "user_id", "INTEGER")
        ensure_column(conn, "outfit_history", "user_id", "INTEGER")
    conn.commit()
    conn.close()


init_db()


def current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Please log in first.")
    conn = get_db()
    user = db_execute(conn, "SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    return dict(user)


def user_id(request: Request) -> int:
    return int(current_user(request)["id"])


class AuthPayload(BaseModel):
    phone: str
    password: str


class SignupPayload(BaseModel):
    phone: str
    password: str
    confirm_password: str


class Clothing(BaseModel):
    category: str
    subtype: str
    name: str
    color: str
    price: Optional[float] = 0.0
    image_url: Optional[str] = ""


class WearPayload(BaseModel):
    top_id: int
    bottom_id: int
    shoes_id: int


class FeedbackPayload(BaseModel):
    outfit_id: int
    feedback: int


class OutfitPayload(BaseModel):
    top_id: int
    bottom_id: int
    shoes_id: int
    weather: Optional[str] = "mild"
    occasion: Optional[str] = "casual"


# ---------------------------------------------------------
# Auth routes
# ---------------------------------------------------------
@app.get("/login")
def login_page():
    return FileResponse("static/login.html")


@app.post("/auth/signup")
def auth_signup(payload: SignupPayload, request: Request):
    phone = normalize_phone(payload.phone)
    validate_password(payload.password)
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    existing = db_execute(conn, "SELECT id, password_hash FROM users WHERE phone = ?", (phone,)).fetchone()
    if existing and existing["password_hash"]:
        conn.close()
        raise HTTPException(status_code=409, detail="An account already exists for this mobile number. Please log in.")

    if existing:
        uid = int(existing["id"])
        db_execute(conn, "UPDATE users SET password_hash=?, last_login=? WHERE id=?", (hash_password(payload.password), now, uid))
    else:
        cur = db_execute(conn, 
            "INSERT INTO users(phone, password_hash, created_at, last_login) VALUES (?, ?, ?, ?) RETURNING id",
            (phone, hash_password(payload.password), now, now),
        )
        uid = cur.fetchone()["id"]
    conn.commit()
    conn.close()

    request.session.clear()
    request.session["user_id"] = uid
    request.session["phone"] = phone
    return {"success": True, "user": {"id": uid, "phone": phone}}


@app.post("/auth/login")
def auth_login(payload: AuthPayload, request: Request):
    phone = normalize_phone(payload.phone)
    conn = get_db()
    row = db_execute(conn, "SELECT id, phone, password_hash FROM users WHERE phone = ?", (phone,)).fetchone()
    if not row or not row["password_hash"] or not verify_password(payload.password, row["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid mobile number or password.")

    now = datetime.now(timezone.utc).isoformat()
    db_execute(conn, "UPDATE users SET last_login=? WHERE id=?", (now, row["id"]))
    conn.commit()
    conn.close()

    request.session.clear()
    request.session["user_id"] = int(row["id"])
    request.session["phone"] = row["phone"]
    return {"success": True, "user": {"id": int(row["id"]), "phone": row["phone"]}}


@app.get("/auth/me")
def auth_me(request: Request):
    try:
        user = current_user(request)
        return {"authenticated": True, "user": {"id": user["id"], "phone": user["phone"]}}
    except HTTPException:
        return {"authenticated": False}


@app.post("/auth/logout")
def auth_logout(request: Request):
    request.session.clear()
    return {"success": True}


# ---------------------------------------------------------
# Pages
# ---------------------------------------------------------
@app.get("/health")
def health():
    conn = None
    try:
        conn = get_db()
        db_execute(conn, "SELECT 1").fetchone()
        return {"ok": True, "database": "postgres" if USE_POSTGRES else "sqlite"}
    finally:
        if conn:
            conn.close()


@app.get("/")
def home(request: Request):
    if request.session.get("user_id"):
        return FileResponse("static/index.html")
    return RedirectResponse("/login", status_code=303)


@app.get("/add")
def add_page(request: Request):
    current_user(request)
    return FileResponse("static/add.html")


@app.get("/wardrobe")
def wardrobe_page(request: Request):
    current_user(request)
    return FileResponse("static/wardrobe.html")


# ---------------------------------------------------------
# Private media: image URLs are tied to the logged-in user
# ---------------------------------------------------------
@app.get("/media/{owner_id}/{filename:path}")
def media(owner_id: int, filename: str, request: Request):
    uid = user_id(request)
    if owner_id != uid:
        raise HTTPException(status_code=403, detail="Not allowed")
    safe_name = os.path.basename(filename)
    path = os.path.join(UPLOAD_DIR, str(uid), safe_name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


@app.post("/upload")
async def upload_image(file: UploadFile = File(...), request: Request = None):
    uid = user_id(request)
    user_dir = os.path.join(UPLOAD_DIR, str(uid))
    os.makedirs(user_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"
    filename = f"{random.randint(100000, 999999)}{ext}"
    path = os.path.join(user_dir, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"url": f"/media/{uid}/{filename}"}


# ---------------------------------------------------------
# Clothes — every query is scoped to the logged-in user
# ---------------------------------------------------------
@app.post("/add-clothes")
def add_clothes(item: Clothing, request: Request):
    uid = user_id(request)
    conn = get_db()
    cur = db_execute(conn, """
        INSERT INTO clothes(user_id, category, subtype, name, color, price, image_url, is_dirty, is_favorite)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0) RETURNING id
    """, (uid, item.category, item.subtype, item.name, item.color, item.price or 0.0, item.image_url or ""))
    new_id = cur.fetchone()["id"]; conn.commit(); conn.close()
    return {"success": True, "id": new_id, "message": "Clothing added successfully"}


@app.put("/clothes/{item_id}")
def update_clothes(item_id: int, item: Clothing, request: Request):
    uid = user_id(request)
    conn = get_db()
    cur = db_execute(conn, """
        UPDATE clothes SET category=?, subtype=?, name=?, color=?, price=?, image_url=?
        WHERE id=? AND user_id=?
    """, (item.category, item.subtype, item.name, item.color, item.price or 0.0, item.image_url or "", item_id, uid))
    conn.commit(); conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Clothing item not found")
    return {"success": True, "message": "Clothing updated successfully"}


@app.put("/clothes/{item_id}/toggle-laundry")
def toggle_laundry(item_id: int, request: Request):
    uid = user_id(request)
    conn = get_db()
    row = db_execute(conn, "SELECT is_dirty FROM clothes WHERE id=? AND user_id=?", (item_id, uid)).fetchone()
    if not row:
        conn.close(); raise HTTPException(status_code=404, detail="Item not found")
    new_state = 0 if row["is_dirty"] else 1
    db_execute(conn, "UPDATE clothes SET is_dirty=? WHERE id=? AND user_id=?", (new_state, item_id, uid))
    conn.commit(); conn.close()
    return {"success": True, "is_dirty": new_state}


@app.delete("/clothes/{item_id}")
def delete_clothes(item_id: int, request: Request):
    uid = user_id(request)
    conn = get_db()
    cursor = db_execute(conn, "DELETE FROM clothes WHERE id=? AND user_id=?", (item_id, uid))
    db_execute(conn, "DELETE FROM worn_history WHERE clothes_id=? AND user_id=?", (item_id, uid))
    db_execute(conn, "DELETE FROM outfit_history WHERE user_id=? AND (top_id=? OR bottom_id=? OR shoes_id=?)", (uid, item_id, item_id, item_id))
    conn.commit(); conn.close()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Clothing item not found")
    return {"success": True, "message": "Clothing deleted successfully"}


@app.get("/clothes")
def get_clothes(request: Request):
    uid = user_id(request)
    conn = get_db()
    clothes = [dict(x) for x in db_execute(conn, "SELECT * FROM clothes WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()]
    for item in clothes:
        history = db_execute(conn, "SELECT worn_date FROM worn_history WHERE clothes_id=? AND user_id=? ORDER BY id DESC", (item["id"], uid)).fetchall()
        item["worn_count"] = len(history)
        item["last_worn"] = history[0]["worn_date"] if history else None
        price = item.get("price") or 0.0
        item["cost_per_wear"] = round(price / len(history), 2) if history else round(price, 2)
    conn.close(); return clothes


@app.post("/wear-outfit")
def wear_outfit(payload: WearPayload, request: Request):
    uid = user_id(request); today_str = date.today().isoformat(); conn = get_db()
    ids = [payload.top_id, payload.bottom_id, payload.shoes_id]
    for cid in ids:
        ok = db_execute(conn, "SELECT id FROM clothes WHERE id=? AND user_id=?", (cid, uid)).fetchone()
        if not ok:
            conn.close(); raise HTTPException(status_code=400, detail="One or more outfit items do not belong to this account.")
        db_execute(conn, "INSERT INTO worn_history(user_id, clothes_id, worn_date) VALUES (?, ?, ?)", (uid, cid, today_str))
    cur = db_execute(conn, "INSERT INTO outfit_history(user_id, top_id, bottom_id, shoes_id, worn_date, weather, occasion) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id", (uid, *ids, today_str, "", ""))
    oid = cur.fetchone()["id"]; conn.commit(); conn.close()
    return {"success": True, "message": "Logged as worn today!", "outfit_id": oid}


@app.post("/outfit-history")
def save_outfit_history(payload: OutfitPayload, request: Request):
    uid = user_id(request); today_str = date.today().isoformat(); conn = get_db()
    ids = [payload.top_id, payload.bottom_id, payload.shoes_id]
    for cid in ids:
        if not db_execute(conn, "SELECT id FROM clothes WHERE id=? AND user_id=?", (cid, uid)).fetchone():
            conn.close(); raise HTTPException(status_code=400, detail="Invalid wardrobe item")
    cur = db_execute(conn, "INSERT INTO outfit_history(user_id, top_id, bottom_id, shoes_id, worn_date, weather, occasion) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id", (uid, *ids, today_str, payload.weather or "mild", payload.occasion or "casual"))
    oid = cur.fetchone()["id"]; conn.commit(); conn.close(); return {"success": True, "outfit_id": oid}


@app.get("/outfit-history")
def get_outfit_history(request: Request, limit: int = 30):
    uid = user_id(request); limit = max(1, min(limit, 100)); conn = get_db()
    rows = db_execute(conn, """
        SELECT oh.*, t.name AS top_name, b.name AS bottom_name, s.name AS shoes_name,
               t.image_url AS top_image, b.image_url AS bottom_image, s.image_url AS shoes_image
        FROM outfit_history oh
        LEFT JOIN clothes t ON t.id=oh.top_id AND t.user_id=?
        LEFT JOIN clothes b ON b.id=oh.bottom_id AND b.user_id=?
        LEFT JOIN clothes s ON s.id=oh.shoes_id AND s.user_id=?
        WHERE oh.user_id=? ORDER BY oh.id DESC LIMIT ?
    """, (uid, uid, uid, uid, limit)).fetchall()
    conn.close(); return [dict(r) for r in rows]


@app.post("/outfit-feedback")
def outfit_feedback(payload: FeedbackPayload, request: Request):
    uid = user_id(request); feedback = 1 if payload.feedback > 0 else -1 if payload.feedback < 0 else 0; conn = get_db()
    cur = db_execute(conn, "UPDATE outfit_history SET feedback=? WHERE id=? AND user_id=?", (feedback, payload.outfit_id, uid))
    conn.commit(); conn.close()
    if cur.rowcount == 0: raise HTTPException(status_code=404, detail="Outfit history entry not found")
    return {"success": True, "feedback": feedback}


@app.put("/clothes/{item_id}/favorite")
def toggle_favorite(item_id: int, request: Request):
    uid = user_id(request); conn = get_db(); row = db_execute(conn, "SELECT is_favorite FROM clothes WHERE id=? AND user_id=?", (item_id, uid)).fetchone()
    if not row: conn.close(); raise HTTPException(status_code=404, detail="Item not found")
    new_state = 0 if row["is_favorite"] else 1
    db_execute(conn, "UPDATE clothes SET is_favorite=? WHERE id=? AND user_id=?", (new_state, item_id, uid)); conn.commit(); conn.close()
    return {"success": True, "is_favorite": new_state}


@app.get("/style-dna")
def style_dna(request: Request):
    uid = user_id(request); conn = get_db(); clothes = [dict(r) for r in db_execute(conn, "SELECT * FROM clothes WHERE user_id=?", (uid,)).fetchall()]
    if not clothes:
        conn.close(); return {"dominant_style":"Getting to know you","text":"Add your first pieces to reveal your style profile.","top_color":"—","rotation":"0%","colors":[]}
    color_counts = {}
    for item in clothes:
        c = normalize_color(item["color"]); color_counts[c] = color_counts.get(c, 0) + 1
    top_color = max(color_counts, key=color_counts.get)
    style_counts = {"Minimal / Clean":0,"Street / Relaxed":0,"Smart Casual":0,"Athletic":0}
    for item in clothes:
        cat=item["category"]; sub=item["subtype"].lower()
        if cat=="Tracks" or "sports" in sub: style_counts["Athletic"] += 2
        if "oversized" in sub or cat in ["Cargo Pants","Zip Hoodie","Zipper Sweatshirt"]: style_counts["Street / Relaxed"] += 2
        if cat in ["Formal Pants","Shirt","Linen Shirt"]: style_counts["Smart Casual"] += 2
        if "plain" in sub or cat in ["Normal Pants","Jeans"]: style_counts["Minimal / Clean"] += 1
    dominant=max(style_counts,key=style_counts.get)
    active=db_execute(conn, "SELECT COUNT(DISTINCT clothes_id) FROM worn_history WHERE user_id=? AND worn_date>=date('now','-30 day')", (uid,)).fetchone()[0]
    conn.close(); rotation=round(active/len(clothes)*100) if clothes else 0
    colors=sorted([{"name":k,"count":v} for k,v in color_counts.items()], key=lambda x:x["count"], reverse=True)[:6]
    return {"dominant_style":dominant,"text":f"Your closet leans {dominant.lower()}, with {top_color} as the strongest color family.","top_color":top_color,"rotation":f"{rotation}%","colors":colors}


@app.get("/style-around/{item_id}")
def style_around(item_id: int, request: Request, weather: str="mild", occasion: str="casual"):
    uid=user_id(request); conn=get_db(); anchor=db_execute(conn, "SELECT * FROM clothes WHERE id=? AND user_id=?",(item_id,uid)).fetchone(); conn.close()
    if not anchor: raise HTTPException(status_code=404,detail="Item not found")
    return generate_outfits(weather, occasion, anchor_id=item_id, user_id=uid)


# ---------------------------------------------------------
# Backup / restore — only this account's data
# ---------------------------------------------------------
@app.get("/backup")
def export_backup(request: Request):
    uid=user_id(request); conn=get_db()
    clothes=[dict(x) for x in db_execute(conn, "SELECT * FROM clothes WHERE user_id=?",(uid,)).fetchall()]
    history=[dict(x) for x in db_execute(conn, "SELECT * FROM worn_history WHERE user_id=?",(uid,)).fetchall()]
    outfit_history=[dict(x) for x in db_execute(conn, "SELECT * FROM outfit_history WHERE user_id=?",(uid,)).fetchall()]
    conn.close(); backup_data={"version":2,"clothes":clothes,"history":history,"outfit_history":outfit_history}
    zip_buffer=io.BytesIO()
    with zipfile.ZipFile(zip_buffer,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("wardrobe_data.json",json.dumps(backup_data,indent=2))
        user_upload=os.path.join(UPLOAD_DIR,str(uid))
        if os.path.exists(user_upload):
            for root,_,files in os.walk(user_upload):
                for file in files:
                    filepath=os.path.join(root,file); z.write(filepath,os.path.join("uploads",file))
    zip_buffer.seek(0)
    return Response(content=zip_buffer.getvalue(),media_type="application/zip",headers={"Content-Disposition":"attachment; filename=wardrobe_backup.zip"})


@app.post("/restore")
async def import_backup(file: UploadFile=File(...), request: Request=None):
    uid=user_id(request)
    if not file.filename.endswith(".zip"): raise HTTPException(status_code=400,detail="File must be a .zip backup archive.")
    content=await file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(content),"r") as z:
            if "wardrobe_data.json" not in z.namelist(): raise HTTPException(status_code=400,detail="Invalid backup file")
            data=json.loads(z.read("wardrobe_data.json").decode("utf-8")); clothes=data.get("clothes",[]); history=data.get("history",[]); oh=data.get("outfit_history",[])
            conn=get_db()
            db_execute(conn, "DELETE FROM outfit_history WHERE user_id=?",(uid,)); db_execute(conn, "DELETE FROM worn_history WHERE user_id=?",(uid,)); db_execute(conn, "DELETE FROM clothes WHERE user_id=?",(uid,))
            id_map={}
            for item in clothes:
                cur=db_execute(conn, "INSERT INTO clothes(user_id,category,subtype,name,color,price,image_url,is_dirty,is_favorite) VALUES(?,?,?,?,?,?,?,?,?) RETURNING id",(uid,item.get("category"),item.get("subtype"),item.get("name"),item.get("color"),item.get("price",0),item.get("image_url",""),item.get("is_dirty",0),item.get("is_favorite",0)))
                id_map[item.get("id")]=cur.fetchone()["id"]
            for h in history:
                if h.get("clothes_id") in id_map:
                    db_execute(conn, "INSERT INTO worn_history(user_id,clothes_id,worn_date) VALUES(?,?,?)",(uid,id_map[h.get("clothes_id")],h.get("worn_date")))
            for row in oh:
                if all(x in id_map for x in [row.get("top_id"),row.get("bottom_id"),row.get("shoes_id")]):
                    db_execute(conn, "INSERT INTO outfit_history(user_id,top_id,bottom_id,shoes_id,worn_date,weather,occasion,feedback) VALUES(?,?,?,?,?,?,?,?)",(uid,id_map[row["top_id"]],id_map[row["bottom_id"]],id_map[row["shoes_id"]],row.get("worn_date"),row.get("weather",""),row.get("occasion",""),row.get("feedback",0)))
            conn.commit(); conn.close()
            user_upload=os.path.join(UPLOAD_DIR,str(uid)); os.makedirs(user_upload,exist_ok=True)
            for name in z.namelist():
                if name.startswith("uploads/") and not name.endswith("/"):
                    target=os.path.join(user_upload,os.path.basename(name))
                    with z.open(name) as src, open(target,"wb") as dst: shutil.copyfileobj(src,dst)
        return {"success":True,"message":"Your wardrobe was restored successfully."}
    except HTTPException: raise
    except Exception as exc: raise HTTPException(status_code=500,detail=f"Failed to restore backup: {exc}")
def normalize_color(color):
    color = color.lower().strip()
    groups = {
        "black":["black","jet black"], "white":["white","off white","off-white","cream","ivory"],
        "grey":["grey","gray","charcoal","silver"], "blue":["blue","navy","dark blue","light blue","sky blue"],
        "brown":["brown","tan","beige","camel","khaki"], "green":["green","olive","dark green","sage"],
        "red":["red","maroon","burgundy","wine"], "yellow":["yellow","mustard"],
        "orange":["orange","rust"], "pink":["pink","rose"], "purple":["purple","lavender"]
    }
    for group, colors in groups.items():
        if any(value in color for value in colors):
            return group
    return color

def color_score(a, b):
    a, b = normalize_color(a), normalize_color(b)
    neutrals = ["black","white","grey","brown"]
    if a == b:
        return 4 if a in ["black","white","grey"] else 2
    if a in neutrals or b in neutrals:
        return 5
    pairs = {
        "green":["black","white","brown","blue"], "brown":["blue","green","white","black"],
        "red":["black","white","grey","blue"], "yellow":["black","white","blue","grey"],
        "pink":["black","white","grey","blue"]
    }
    if b in pairs.get(a, []) or a in pairs.get(b, []):
        return 4
    return 1

def style_score(top, bottom, shoes):
    score = 0
    tc, ts = top["category"], top["subtype"].lower()
    bc, bs = bottom["category"], bottom["subtype"].lower()
    sc, ss = shoes["category"], shoes["subtype"].lower()

    if "oversized" in ts:
        if "loose" in bs: score += 4
        elif "baggy" in bs: score += 3
        elif "regular" in bs: score += 2
        if bc in ["Cargo Pants","Tracks"]: score += 2

    if "slim" in ts:
        if "loose" in bs: score += 4
        elif "regular" in bs: score += 3
        elif "baggy" in bs: score += 3

    if "plain" in ts: score += 2
    if "printed" in ts: score += 4 if "plain" in bs else -1
    if "checks" in ts and bc in ["Jeans","Normal Pants","Cargo Pants"]: score += 3
    if "striped" in ts and bc in ["Jeans","Normal Pants"]: score += 3

    if tc == "Shirt":
        if bc in ["Jeans","Normal Pants"]: score += 3
        if bc == "Formal Pants": score += 6
        if bc == "Cargo Pants": score += 2

    if tc == "Linen Shirt":
        if bc in ["Normal Pants","Jeans"]: score += 3
        if bc == "Cargo Pants": score += 2
        if bc == "Formal Pants": score += 3

    if tc == "T-Shirt":
        if bc in ["Jeans","Cargo Pants","Normal Pants","Tracks"]: score += 3
        if bc == "Formal Pants": score -= 3

    if tc in ["Zipper Sweatshirt","Zip Hoodie"]:
        if bc in ["Jeans","Cargo Pants","Tracks"]: score += 4
        if bc == "Formal Pants": score -= 5

    if bc == "Tracks":
        if sc == "Sneakers": score += 5
        if sc == "Boots": score -= 7
        if tc in ["T-Shirt","Zipper Sweatshirt","Zip Hoodie"]: score += 3

    if bc == "Formal Pants":
        if tc == "Shirt": score += 6
        if tc == "Linen Shirt": score += 3
        if tc == "T-Shirt": score -= 3
        if tc in ["Zipper Sweatshirt","Zip Hoodie"]: score -= 6
        if sc == "Boots": score += 4
        if sc == "Sneakers": score -= 2
        if sc == "Casual Slippers": score -= 7

    if bc == "Jeans" and sc in ["Sneakers","Boots"]: score += 3
    if bc == "Cargo Pants":
        if sc == "Sneakers": score += 4
        if sc == "Boots": score += 2
        if sc == "Casual Slippers": score += 1
    if bc == "Normal Pants" and sc in ["Sneakers","Boots"]: score += 3

    if sc == "Sneakers":
        score += 2
        if "casual" in ss: score += 2
        if "low-top" in ss: score += 1
        if "high-top" in ss and bc in ["Jeans","Cargo Pants"]: score += 2

    if "sports" in ss:
        if bc == "Tracks": score += 5
        elif bc == "Cargo Pants": score += 2
        elif bc == "Formal Pants": score -= 4

    if sc == "Boots":
        if "chelsea" in ss:
            if bc in ["Jeans","Normal Pants","Formal Pants"]: score += 5
            if bc == "Tracks": score -= 8
        if "lace-up" in ss:
            if bc in ["Jeans","Cargo Pants"]: score += 3
            if bc == "Formal Pants": score += 2
            if bc == "Tracks": score -= 7

    if sc == "Casual Slippers":
        if bc in ["Tracks","Cargo Pants","Jeans"]: score += 2
        if bc == "Formal Pants": score -= 8

    return score

def weather_score(top, bottom, shoes, weather):
    score = 0
    weather = (weather or "mild").lower()
    tc, bc, sc = top["category"], bottom["category"], shoes["category"]

    if weather == "hot":
        if tc == "T-Shirt": score += 7
        if tc == "Linen Shirt": score += 8
        if tc == "Shirt": score += 4
        if tc in ["Zipper Sweatshirt","Zip Hoodie"]: score -= 10
        if bc == "Tracks": score -= 5
        if sc == "Casual Slippers": score += 4
        if sc == "Sneakers": score += 1
        if sc == "Boots": score -= 4
    elif weather == "warm":
        if tc == "T-Shirt": score += 6
        if tc == "Linen Shirt": score += 6
        if tc == "Shirt": score += 4
        if tc in ["Zipper Sweatshirt","Zip Hoodie"]: score -= 6
        if sc in ["Sneakers","Casual Slippers"]: score += 2
        if sc == "Boots": score -= 2
    elif weather == "mild":
        if tc == "T-Shirt": score += 3
        if tc == "Shirt": score += 4
        if tc == "Linen Shirt": score += 3
        if tc in ["Zipper Sweatshirt","Zip Hoodie"]: score += 3
        if sc == "Sneakers": score += 3
    elif weather == "cool":
        if tc in ["Zipper Sweatshirt","Zip Hoodie"]: score += 8
        if tc == "Shirt": score += 2
        if tc == "T-Shirt": score -= 4
        if tc == "Linen Shirt": score -= 5
        if sc == "Boots": score += 4
        if bc == "Tracks": score += 2
    elif weather == "rainy":
        if tc == "Linen Shirt": score -= 5
        if sc == "Casual Slippers": score -= 8
        if sc == "Boots": score += 7
        if sc == "Sneakers": score += 2
        if bc == "Tracks": score += 1
    return score

def occasion_score(top, bottom, shoes, occasion):
    score = 0
    occ = (occasion or "casual").lower()
    tc, ts = top["category"], top["subtype"].lower()
    bc, bs = bottom["category"], bottom["subtype"].lower()
    sc, ss = shoes["category"], shoes["subtype"].lower()

    if occ == "gym":
        if bc == "Tracks": score += 10
        else: score -= 8
        if tc == "T-Shirt": score += 8
        elif tc in ["Zipper Sweatshirt", "Zip Hoodie"]: score += 4
        else: score -= 10
        if sc == "Sneakers" and "sports" in ss: score += 10
        elif sc == "Sneakers": score += 5
        else: score -= 12

    elif occ == "formal":
        if bc == "Formal Pants": score += 10
        elif bc == "Normal Pants": score += 4
        else: score -= 8
        if tc == "Shirt": score += 10
        elif tc == "Linen Shirt": score += 5
        else: score -= 10
        if sc == "Boots": score += 6
        elif sc == "Sneakers" and "casual" in ss: score += 2
        else: score -= 10

    elif occ == "party":
        if tc in ["Shirt", "Linen Shirt"] or "printed" in ts or "oversized" in ts: score += 6
        if bc in ["Jeans", "Cargo Pants", "Normal Pants"]: score += 5
        if sc in ["Sneakers", "Boots"]: score += 5
        if sc == "Casual Slippers": score -= 10

    elif occ == "date":
        if tc in ["Shirt", "Linen Shirt"]: score += 8
        elif tc == "T-Shirt" and "plain" in ts: score += 4
        if bc in ["Formal Pants", "Normal Pants", "Jeans"]: score += 6
        if sc in ["Boots", "Sneakers"]: score += 6
        if sc == "Casual Slippers": score -= 12

    elif occ == "college":
        if tc in ["T-Shirt", "Shirt", "Zipper Sweatshirt", "Zip Hoodie"]: score += 5
        if bc in ["Jeans", "Cargo Pants", "Normal Pants", "Tracks"]: score += 5
        if sc in ["Sneakers", "Boots"]: score += 5

    elif occ == "casual":
        score += 2

    return score

def get_weather_name(weather):
    return {"hot":"Hot / Sunny","warm":"Warm","mild":"Mild / Cloudy","cool":"Cool","rainy":"Rainy"}.get(weather,"Mild / Cloudy")

def get_outfit_message(weather, occasion):
    occ_str = occasion.capitalize() if occasion else "Casual"
    messages = {
        "hot":[f"Light & fresh combination for a {occ_str} day.", f"Keeping it cool for your {occ_str} outing.", f"Perfect breathable choice for {occ_str}."],
        "warm":[f"Comfortable look tailored for {occ_str}.", f"Easygoing combination for a warm {occ_str} day.", f"Great fit for {occ_str} in warm weather."],
        "mild":[f"Balanced style suited for {occ_str}.", f"Versatile outfit picked for your {occ_str} plans.", f"A clean look for today's {occ_str} vibe."],
        "cool":[f"Cozy & stylish pick for {occ_str}.", f"Warmer setup perfect for a cool {occ_str} day.", f"Smart layering for {occ_str}."],
        "rainy":[f"Practical wet-weather choice for {occ_str}.", f"Rain-friendly outfit curated for {occ_str}.", f"Keeps you sharp and dry for {occ_str}."]
    }
    return random.choice(messages.get(weather, messages["mild"]))

def outfit_reason(item, weather, occasion):
    bits=[]
    if item.get('occasion'): bits.append(item['occasion'])
    bits.append(occasion.capitalize())
    if weather == 'hot': bits.append('breathable for the heat')
    elif weather == 'rainy': bits.append('practical for wet weather')
    elif weather == 'cool': bits.append('comfortable for cooler weather')
    return " · ".join(dict.fromkeys(bits))




def build_outfit_candidates(weather="mild", occasion="casual", anchor_id=None, exclude_keys=None, user_id=None):
    exclude_keys = set(k for raw in (exclude_keys or []) for k in str(raw).split(",") if k)
    conn = get_db()
    clothes = [dict(x) for x in db_execute(conn, "SELECT * FROM clothes WHERE user_id=? AND is_dirty=0", (user_id,)).fetchall()]
    # Recent rotation: combinations worn in the last 10 days get a strong penalty.
    recent_pairs = set()
    recent_sql = (
        "SELECT top_id,bottom_id,shoes_id FROM outfit_history WHERE user_id=? AND worn_date::date >= CURRENT_DATE - INTERVAL '10 days'"
        if USE_POSTGRES else
        "SELECT top_id,bottom_id,shoes_id FROM outfit_history WHERE user_id=? AND worn_date>=date('now','-10 day')"
    )
    for row in db_execute(conn, recent_sql, (user_id,)).fetchall():
        recent_pairs.add(f"{row['top_id']}-{row['bottom_id']}-{row['shoes_id']}")
    conn.close()
    tops=[x for x in clothes if x["category"] in ["T-Shirt","Shirt","Linen Shirt","Zipper Sweatshirt","Zip Hoodie"]]
    bottoms=[x for x in clothes if x["category"] in ["Jeans","Normal Pants","Formal Pants","Cargo Pants","Tracks"]]
    shoes=[x for x in clothes if x["category"] in ["Sneakers","Boots","Casual Slippers"]]
    candidates=[]
    for top in tops:
        for bottom in bottoms:
            for shoe in shoes:
                key=f"{top['id']}-{bottom['id']}-{shoe['id']}"
                if key in exclude_keys: continue
                score=color_score(top["color"],bottom["color"])+color_score(bottom["color"],shoe["color"])+style_score(top,bottom,shoe)+weather_score(top,bottom,shoe,weather)+occasion_score(top,bottom,shoe,occasion)
                if key in recent_pairs: score -= 12
                if anchor_id in [top["id"],bottom["id"],shoe["id"]]: score += 8
                candidates.append({"top":top,"bottom":bottom,"shoes":shoe,"score":round(score,2),"key":key})
    candidates.sort(key=lambda x:x["score"], reverse=True)
    return candidates


def generate_outfits(weather="mild", occasion="casual", anchor_id=None, exclude_keys=None, count=3, user_id=None):
    candidates=build_outfit_candidates(weather,occasion,anchor_id,exclude_keys,user_id)
    if not candidates:
        return {"success":False,"message":"Add at least one clean top, one bottom and one pair of shoes to generate looks."}
    selected=[]; used_parts=set()
    for c in candidates:
        overlap=sum(item in used_parts for item in [c["top"]["id"],c["bottom"]["id"],c["shoes"]["id"]])
        if selected and overlap>=3: continue
        selected.append(c); used_parts.update([c["top"]["id"],c["bottom"]["id"],c["shoes"]["id"]])
        if len(selected)>=count: break
    for c in candidates:
        if len(selected)>=count: break
        if c not in selected: selected.append(c)
    labels=["THE CLEAN PICK","THE EASY SWITCH","THE STATEMENT"]
    looks=[]
    for i,c in enumerate(selected):
        looks.append({"top":c["top"],"bottom":c["bottom"],"shoes":c["shoes"],"score":c["score"],"outfitKey":c["key"],"label":labels[i],"why":f"A balanced {occasion} combination tuned for {get_weather_name(weather).lower()}, while avoiding recently worn combinations."})
    return {"success":True,"looks":looks,"weather":weather,"occasion":occasion,"weatherName":get_weather_name(weather),"message":f"Three {occasion} looks curated from your clean wardrobe."}


def generate_outfit(weather="mild", occasion="casual", exclude_key=None, user_id=None):
    result=generate_outfits(weather,occasion,exclude_keys=[exclude_key] if exclude_key else [],count=1,user_id=user_id)
    if not result.get("success"): return result
    look=result["looks"][0]
    return {"success":True,**look,"weather":weather,"occasion":occasion,"weatherName":result["weatherName"],"message":result["message"]}


@app.get("/recommend-outfit")
def recommend_outfit(request: Request, weather: str="mild", occasion: str="casual", exclude: str=None):
    uid=user_id(request)
    if weather not in ["hot","warm","mild","cool","rainy"]: weather="mild"
    if occasion not in ["college","casual","party","date","formal","gym"]: occasion="casual"
    return generate_outfits(weather,occasion,exclude_keys=[exclude] if exclude else [],count=3,user_id=uid)


@app.get("/ai/stylist")
def ai_stylist(request: Request, weather: str="mild", occasion: str="casual"):
    uid=user_id(request)
    return generate_outfits(weather if weather in ["hot","warm","mild","cool","rainy"] else "mild", occasion if occasion in ["college","casual","party","date","formal","gym"] else "casual", count=3,user_id=uid)
