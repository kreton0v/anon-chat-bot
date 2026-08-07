import sqlite3
import json
import os
import time
from typing import Optional, List, Dict, Set, Tuple
from threading import Lock

from config import CONFIG
from models import (
    UserProfile, ChatSession, WaitingUser, BanRecord, Report,
    Gender, AgeGroup
)


class Repository:
    """Thread-safe SQLite repository with WAL mode."""

    _lock = Lock()

    def __init__(self):
        os.makedirs(CONFIG.DATA_DIR, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(CONFIG.db_path, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER PRIMARY KEY,
                    gender TEXT,
                    age TEXT,
                    coins INTEGER DEFAULT 0,
                    username TEXT DEFAULT '',
                    name TEXT DEFAULT '',
                    referrals TEXT DEFAULT '[]',
                    referral_batches INTEGER DEFAULT 0,
                    referred_by INTEGER
                );
                CREATE TABLE IF NOT EXISTS active_chats (
                    user_a INTEGER PRIMARY KEY,
                    user_b INTEGER NOT NULL,
                    started_at REAL NOT NULL,
                    history TEXT DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS waiting_users (
                    user_id INTEGER PRIMARY KEY,
                    gender TEXT NOT NULL,
                    age TEXT NOT NULL,
                    find_gender TEXT,
                    find_age TEXT,
                    joined_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bans (
                    user_id INTEGER PRIMARY KEY,
                    permanent INTEGER DEFAULT 0,
                    until REAL,
                    reason TEXT DEFAULT '',
                    banned_by INTEGER,
                    banned_at REAL DEFAULT (strftime('%s','now'))
                );
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reporter_id INTEGER NOT NULL,
                    offender_id INTEGER NOT NULL,
                    reported_at REAL DEFAULT (strftime('%s','now')),
                    resolved INTEGER DEFAULT 0,
                    verdict TEXT
                );
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY
                );
                CREATE INDEX IF NOT EXISTS idx_reports_offender ON reports(offender_id);
                CREATE INDEX IF NOT EXISTS idx_reports_resolved ON reports(resolved);
            """)
            conn.commit()
            cur = conn.execute("SELECT value FROM config WHERE key='reveal_price'")
            if cur.fetchone() is None:
                conn.execute("INSERT INTO config (key, value) VALUES (?, ?)",
                             ("reveal_price", str(CONFIG.REVEAL_PRICE)))
                conn.commit()

    # ---------- Profiles ----------

    def get_profile(self, user_id: int) -> UserProfile:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles WHERE user_id=?", (user_id,)
            ).fetchone()
            if row is None:
                p = UserProfile(user_id=user_id)
                self._save_profile(conn, p)
                return p
            return self._row_to_profile(row)

    def _save_profile(self, conn, p: UserProfile):
        conn.execute("""
            INSERT INTO profiles (user_id, gender, age, coins, username, name,
                                  referrals, referral_batches, referred_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                gender=excluded.gender, age=excluded.age, coins=excluded.coins,
                username=excluded.username, name=excluded.name,
                referrals=excluded.referrals, referral_batches=excluded.referral_batches,
                referred_by=excluded.referred_by
        """, (p.user_id, p.gender.value if p.gender else None,
              p.age.value if p.age else None, p.coins, p.username, p.name,
              json.dumps(p.referrals), p.referral_batches, p.referred_by))

    def save_profile(self, p: UserProfile):
        with self._connect() as conn:
            self._save_profile(conn, p)
            conn.commit()

    def _row_to_profile(self, row) -> UserProfile:
        return UserProfile(
            user_id=row["user_id"],
            gender=Gender(row["gender"]) if row["gender"] else None,
            age=AgeGroup(row["age"]) if row["age"] else None,
            coins=row["coins"],
            username=row["username"] or "",
            name=row["name"] or "",
            referrals=json.loads(row["referrals"] or "[]"),
            referral_batches=row["referral_batches"],
            referred_by=row["referred_by"]
        )

    def get_all_profiles(self) -> Dict[int, UserProfile]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM profiles").fetchall()
            return {r["user_id"]: self._row_to_profile(r) for r in rows}

    # ---------- Active Chats ----------

    def get_active_chat(self, user_id: int) -> Optional[ChatSession]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM active_chats WHERE user_a=? OR user_b=?",
                (user_id, user_id)
            ).fetchone()
            if row is None:
                return None
            return ChatSession(
                user_a=row["user_a"], user_b=row["user_b"],
                started_at=row["started_at"],
                history=json.loads(row["history"] or "[]")
            )

    def create_chat(self, session: ChatSession):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO active_chats (user_a, user_b, started_at, history)
                VALUES (?, ?, ?, ?)
            """, (session.user_a, session.user_b, session.started_at,
                  json.dumps(session.history)))
            conn.commit()

    def delete_chat(self, user_a: int, user_b: int):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM active_chats WHERE (user_a=? AND user_b=?) OR (user_a=? AND user_b=?)",
                (user_a, user_b, user_b, user_a)
            )
            conn.commit()

    def update_chat_history(self, user_a: int, user_b: int, history: List[Dict]):
        with self._connect() as conn:
            conn.execute(
                "UPDATE active_chats SET history=? WHERE (user_a=? AND user_b=?) OR (user_a=? AND user_b=?)",
                (json.dumps(history), user_a, user_b, user_b, user_a)
            )
            conn.commit()

    def get_all_active_chats(self) -> List[ChatSession]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM active_chats").fetchall()
            return [ChatSession(r["user_a"], r["user_b"], r["started_at"],
                                json.loads(r["history"] or "[]")) for r in rows]

    # ---------- Waiting ----------

    def add_waiting(self, w: WaitingUser):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO waiting_users (user_id, gender, age, find_gender, find_age, joined_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    gender=excluded.gender, age=excluded.age,
                    find_gender=excluded.find_gender, find_age=excluded.find_age,
                    joined_at=excluded.joined_at
            """, (w.user_id, w.gender.value, w.age.value,
                  w.find_gender.value if w.find_gender else None,
                  w.find_age.value if w.find_age else None, w.joined_at))
            conn.commit()

    def remove_waiting(self, user_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM waiting_users WHERE user_id=?", (user_id,))
            conn.commit()

    def get_waiting(self, user_id: int) -> Optional[WaitingUser]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM waiting_users WHERE user_id=?", (user_id,)
            ).fetchone()
            if row is None:
                return None
            return WaitingUser(
                user_id=row["user_id"],
                gender=Gender(row["gender"]),
                age=AgeGroup(row["age"]),
                find_gender=Gender(row["find_gender"]) if row["find_gender"] else None,
                find_age=AgeGroup(row["find_age"]) if row["find_age"] else None,
                joined_at=row["joined_at"]
            )

    def get_all_waiting(self) -> List[WaitingUser]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM waiting_users ORDER BY joined_at").fetchall()
            return [WaitingUser(
                r["user_id"], Gender(r["gender"]), AgeGroup(r["age"]),
                Gender(r["find_gender"]) if r["find_gender"] else None,
                AgeGroup(r["find_age"]) if r["find_age"] else None,
                r["joined_at"]
            ) for r in rows]

    # ---------- Bans ----------

    def ban(self, record: BanRecord):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO bans (user_id, permanent, until, reason, banned_by, banned_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    permanent=excluded.permanent, until=excluded.until,
                    reason=excluded.reason, banned_by=excluded.banned_by,
                    banned_at=excluded.banned_at
            """, (record.user_id, int(record.permanent), record.until,
                  record.reason, record.banned_by, record.banned_at))
            conn.commit()

    def unban(self, user_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM bans WHERE user_id=?", (user_id,))
            conn.commit()

    def is_banned(self, user_id: int) -> Tuple[bool, Optional[str]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM bans WHERE user_id=?", (user_id,)
            ).fetchone()
            if row is None:
                return False, None
            if row["permanent"]:
                return True, row["reason"]
            if row["until"] and time.time() > row["until"]:
                conn.execute("DELETE FROM bans WHERE user_id=?", (user_id,))
                conn.commit()
                return False, None
            return True, row["reason"]

    def get_ban_list(self) -> List[BanRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM bans").fetchall()
            return [BanRecord(
                r["user_id"], bool(r["permanent"]), r["until"],
                r["reason"] or "", r["banned_by"], r["banned_at"]
            ) for r in rows]

    # ---------- Reports ----------

    def add_report(self, report: Report):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO reports (reporter_id, offender_id, reported_at, resolved, verdict)
                VALUES (?, ?, ?, ?, ?)
            """, (report.reporter_id, report.offender_id, report.reported_at,
                  int(report.resolved), report.verdict))
            conn.commit()

    def get_reports_for(self, offender_id: int) -> List[Report]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reports WHERE offender_id=? ORDER BY reported_at DESC",
                (offender_id,)
            ).fetchall()
            return [Report(r["reporter_id"], r["offender_id"], r["reported_at"],
                           bool(r["resolved"]), r["verdict"]) for r in rows]

    def get_all_unresolved_reports(self) -> List[Tuple[int, List[Report]]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reports WHERE resolved=0 ORDER BY offender_id, reported_at DESC"
            ).fetchall()
            grouped: Dict[int, List[Report]] = {}
            for r in rows:
                rep = Report(r["reporter_id"], r["offender_id"], r["reported_at"],
                             bool(r["resolved"]), r["verdict"])
                grouped.setdefault(r["offender_id"], []).append(rep)
            return list(grouped.items())

    def resolve_reports(self, offender_id: int, verdict: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE reports SET resolved=1, verdict=? WHERE offender_id=? AND resolved=0",
                (verdict, offender_id)
            )
            conn.commit()

    # ---------- Config ----------

    def get_reveal_price(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM config WHERE key='reveal_price'").fetchone()
            return int(row["value"]) if row else CONFIG.REVEAL_PRICE

    def set_reveal_price(self, price: int):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO config (key, value) VALUES ('reveal_price', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(price),)
            )
            conn.commit()

    # ---------- Admins ----------

    def add_admin(self, user_id: int):
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
            conn.commit()

    def remove_admin(self, user_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
            conn.commit()

    def get_admins(self) -> Set[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT user_id FROM admins").fetchall()
            return {r["user_id"] for r in rows}

    def is_admin(self, user_id: int) -> bool:
        return user_id == CONFIG.OWNER_ID or user_id in self.get_admins()

    def is_staff(self, user_id: int) -> bool:
        return self.is_admin(user_id) or self.is_owner(user_id)

    def is_owner(self, user_id: int) -> bool:
        return user_id == CONFIG.OWNER_ID


# Singleton
repo = Repository()
