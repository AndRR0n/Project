import sqlite3
from datetime import datetime

DB_FILE = "points.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            status TEXT DEFAULT 'в проработке',
            comment TEXT,
            updated TEXT,
            updated_by TEXT
        )
    ''')
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


def upsert_point(point: dict):
    """Создаёт новую запись или обновляет существующую по id"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if "id" in point and point["id"]:
        cur.execute('''
            UPDATE points
            SET name = ?, address = ?, phone = ?, status = ?, comment = ?, updated = ?, updated_by = ?
            WHERE id = ?
        ''', (
            point["name"],
            point.get("address"),
            point.get("phone"),
            point.get("status", "в проработке"),
            point.get("comment"),
            datetime.now().isoformat(),
            point.get("updated_by", "system"),
            point["id"]
        ))
    else:
        cur.execute('''
            INSERT INTO points (name, address, phone, status, comment, updated, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            point["name"],
            point.get("address"),
            point.get("phone"),
            point.get("status", "в проработке"),
            point.get("comment"),
            datetime.now().isoformat(),
            point.get("updated_by", "system")
        ))

    conn.commit()
    conn.close()


def delete_point(point_id: int):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM points WHERE id = ?", (point_id,))
    conn.commit()
    conn.close()