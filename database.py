import sqlite3
from datetime import datetime

DB_FILE = "points.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS points (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            address    TEXT,
            phone      TEXT,
            status     TEXT DEFAULT 'в проработке',
            comment    TEXT,
            updated    TEXT,
            updated_by TEXT,
            owner_id   INTEGER
        )
    ''')
    # Миграция: добавляем owner_id если таблица уже существует без него
    existing_cols = {row[1] for row in cur.execute("PRAGMA table_info(points)")}
    if "owner_id" not in existing_cols:
        cur.execute("ALTER TABLE points ADD COLUMN owner_id INTEGER")
    conn.commit()
    conn.close()


def get_all_points():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM points ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_points_by_user(username: str):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM points WHERE updated_by = ? ORDER BY id",
        (username,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def upsert_point(point: dict):
    """Создаёт новую запись или обновляет существующую по id."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    now = datetime.now().isoformat()

    if "id" in point and point["id"]:
        cur.execute('''
            UPDATE points
            SET name       = ?,
                address    = ?,
                phone      = ?,
                status     = ?,
                comment    = ?,
                updated    = ?,
                updated_by = ?,
                owner_id   = COALESCE(owner_id, ?)
            WHERE id = ?
        ''', (
            point.get("name"),
            point.get("address"),
            point.get("phone"),
            point.get("status", "в проработке"),
            point.get("comment"),
            now,
            point.get("updated_by", "system"),
            point.get("owner_id"),
            point["id"]
        ))
    else:
        cur.execute('''
            INSERT INTO points (name, address, phone, status, comment, updated, updated_by, owner_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            point.get("name"),
            point.get("address"),
            point.get("phone"),
            point.get("status", "в проработке"),
            point.get("comment"),
            now,
            point.get("updated_by", "system"),
            point.get("owner_id"),
        ))

    conn.commit()
    conn.close()


def delete_point(point_id: int):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM points WHERE id = ?", (point_id,))
    conn.commit()
    conn.close()




