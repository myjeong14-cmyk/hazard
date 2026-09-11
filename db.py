import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "hazards.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hazards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            category TEXT NOT NULL,
            risk TEXT NOT NULL,
            photo_path TEXT,
            description TEXT,
            contact_name TEXT,
            contact_phone TEXT,
            action_date TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def create_hazard(data: dict) -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO hazards
        (location, category, risk, photo_path, description, contact_name, contact_phone, action_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["location"],
            data["category"],
            data["risk"],
            data.get("photo_path"),
            data.get("description"),
            data.get("contact_name"),
            data.get("contact_phone"),
            data.get("action_date"),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_hazard(hazard_id: int, data: dict):
    conn = get_conn()
    conn.execute(
        """
        UPDATE hazards SET
            location=?, category=?, risk=?, photo_path=?, description=?,
            contact_name=?, contact_phone=?, action_date=?
        WHERE id=?
        """,
        (
            data["location"],
            data["category"],
            data["risk"],
            data.get("photo_path"),
            data.get("description"),
            data.get("contact_name"),
            data.get("contact_phone"),
            data.get("action_date"),
            hazard_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_hazard(hazard_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM hazards WHERE id=?", (hazard_id,))
    conn.commit()
    conn.close()


def get_hazard(hazard_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM hazards WHERE id=?", (hazard_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_hazards():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM hazards ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
