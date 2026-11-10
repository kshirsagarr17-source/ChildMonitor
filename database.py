import sqlite3
import os
import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "child_monitor.db")

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 20000;")
    except Exception:
        pass
    return conn

def init_db():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            battery INTEGER DEFAULT 100,
            is_charging INTEGER DEFAULT 0,
            last_seen TIMESTAMP,
            created_at TIMESTAMP
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            latitude REAL,
            longitude REAL,
            accuracy REAL DEFAULT 0.0,
            timestamp TIMESTAMP
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            device_id TEXT PRIMARY KEY,
            camera_mode TEXT DEFAULT 'OFF',
            ring_alarm INTEGER DEFAULT 0,
            torch INTEGER DEFAULT 0
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            filename TEXT,
            timestamp TIMESTAMP
        );
        """)
        conn.commit()

def update_device_heartbeat(device_id, name="Child_Phone", battery=None, is_charging=None):
    ts = now_str()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM devices WHERE id = ?", (device_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO devices (id, name, battery, is_charging, last_seen, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (device_id, name, battery or 100, 1 if is_charging else 0, ts, ts))
            cursor.execute("INSERT OR IGNORE INTO commands (device_id) VALUES (?)", (device_id,))
        else:
            cursor.execute("""
                UPDATE devices 
                SET name = ?, battery = ?, is_charging = ?, last_seen = ?
                WHERE id = ?
            """, (name, battery or 100, 1 if is_charging else 0, ts, device_id))
        conn.commit()

def get_devices():
    ts_now = datetime.datetime.now()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.id, d.name, d.battery, d.is_charging, d.last_seen,
                   c.camera_mode, c.ring_alarm, c.torch
            FROM devices d
            LEFT JOIN commands c ON d.id = c.device_id
            ORDER BY d.last_seen DESC
        """)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            item = dict(r)
            # 90 sec online status
            status = "🔴 OFFLINE"
            last_seen = item.get("last_seen")
            if last_seen:
                try:
                    dt = datetime.datetime.strptime(str(last_seen), "%Y-%m-%d %H:%M:%S")
                    if (ts_now - dt).total_seconds() < 90:
                        status = "🟢 ONLINE"
                    elif (ts_now - dt).total_seconds() < 300:
                        status = "🟡 IDLE"
                except Exception:
                    pass
            item["status"] = status
            item["latest_loc"] = get_latest_location(item["id"])
            result.append(item)
        return result

def save_location(device_id, lat, lon, accuracy=0.0):
    ts = now_str()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO locations (device_id, latitude, longitude, accuracy, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (device_id, float(lat), float(lon), float(accuracy), ts))
        conn.commit()

def get_latest_location(device_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT latitude, longitude, accuracy, timestamp
            FROM locations
            WHERE device_id = ?
            ORDER BY id DESC LIMIT 1
        """, (device_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_location_history(device_id, limit=50):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, latitude, longitude, accuracy, timestamp
            FROM locations
            WHERE device_id = ?
            ORDER BY id DESC LIMIT ?
        """, (device_id, limit))
        return [dict(r) for r in cursor.fetchall()]

def set_command(device_id, field, value):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO commands (device_id) VALUES (?)", (device_id,))
        cursor.execute(f"UPDATE commands SET {field} = ? WHERE device_id = ?", (value, device_id))
        conn.commit()

def get_commands(device_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM commands WHERE device_id = ?", (device_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {"camera_mode": "OFF", "ring_alarm": 0, "torch": 0}

def clear_camera_command(device_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE commands SET camera_mode = 'OFF' WHERE device_id = ?", (device_id,))
        conn.commit()

def save_photo(device_id, filename):
    ts = now_str()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO photos (device_id, filename, timestamp)
            VALUES (?, ?, ?)
        """, (device_id, filename, ts))
        conn.commit()

def get_photos(device_id=None, limit=30):
    with get_conn() as conn:
        cursor = conn.cursor()
        if device_id:
            cursor.execute("""
                SELECT p.id, p.device_id, p.filename, p.timestamp, d.name
                FROM photos p
                LEFT JOIN devices d ON p.device_id = d.id
                WHERE p.device_id = ?
                ORDER BY p.id DESC LIMIT ?
            """, (device_id, limit))
        else:
            cursor.execute("""
                SELECT p.id, p.device_id, p.filename, p.timestamp, d.name
                FROM photos p
                LEFT JOIN devices d ON p.device_id = d.id
                ORDER BY p.id DESC LIMIT ?
            """, (limit,))
        return [dict(r) for r in cursor.fetchall()]

def delete_device(device_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        cursor.execute("DELETE FROM locations WHERE device_id = ?", (device_id,))
        cursor.execute("DELETE FROM commands WHERE device_id = ?", (device_id,))
        cursor.execute("DELETE FROM photos WHERE device_id = ?", (device_id,))
        conn.commit()
