# ============================================================
# db_layer.py — MIIM HRM MySQL/SQLite Dual DB Layer
# ============================================================
# இந்த file-ஐ app.py-ஓட same folder-ல் வையுங்க.
# app.py-ல் old _db() block-ஐ இந்த line-ஆல் replace பண்ணுங்க:
#   from db_layer import _db
# ============================================================

import os
import sqlite3
from typing import Any, Optional

# ── Try importing pymysql (only available in production) ──
pymysql: Any = None
pymysql_cursors: Any = None
try:
    import pymysql as _pymysql
    import pymysql.cursors as _pymysql_cursors
    pymysql = _pymysql
    pymysql_cursors = _pymysql_cursors
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

MYSQL_HOST     = os.environ.get('MYSQL_HOST', '')
MYSQL_PORT     = int(os.environ.get('MYSQL_PORT', 3306))
MYSQL_USER     = os.environ.get('MYSQL_USER', '')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DB       = os.environ.get('MYSQL_DB', '')

USE_MYSQL = PYMYSQL_AVAILABLE and bool(MYSQL_HOST) and bool(MYSQL_USER) and bool(MYSQL_DB)

if USE_MYSQL:
    print(f"🗄️  Database: MySQL ({MYSQL_HOST}/{MYSQL_DB})")
else:
    _SQLITE_PATH = os.environ.get(
        'DB_PATH',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miim_hrm.db')
    )
    print(f"🗄️  Database: SQLite ({_SQLITE_PATH})")


# ── MySQL Connection Pool ──
# Reuses a small set of connections instead of opening a new one per request.
# This prevents hitting Hostinger's max_connections_per_hour limit.
import threading as _threading

_pool_lock = _threading.Lock()
_pool: list = []          # idle connections waiting to be reused
_POOL_SIZE = int(os.environ.get('DB_POOL_SIZE', 10))  # increased from 5 to 10
_active_count = 0         # track active connections
_MAX_ACTIVE   = int(os.environ.get('DB_MAX_ACTIVE', 20))  # hard ceiling


def _create_raw_mysql_conn() -> Any:
    """Open a fresh pymysql connection."""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset='utf8mb4',
        cursorclass=pymysql_cursors.DictCursor,
        autocommit=False,
        connect_timeout=10,
    )


def _get_pool_conn() -> Any:
    """Get a live connection from pool, or create one. Retries briefly if pool busy."""
    import time as _time
    global _active_count
    for attempt in range(6):          # retry up to ~3 seconds
        with _pool_lock:
            while _pool:
                conn = _pool.pop()
                try:
                    conn.ping(reconnect=True)
                    _active_count += 1
                    return conn
                except Exception:
                    pass              # stale — discard
            if _active_count < _MAX_ACTIVE:
                _active_count += 1
                break                 # will create new connection below
        # pool empty and at ceiling — wait a bit then retry
        _time.sleep(0.5)
    return _create_raw_mysql_conn()


def _return_pool_conn(conn: Any) -> None:
    """Return a connection to the pool."""
    global _active_count
    try:
        conn.rollback()
    except Exception:
        with _pool_lock:
            _active_count = max(0, _active_count - 1)
        return
    with _pool_lock:
        _active_count = max(0, _active_count - 1)
        if len(_pool) < _POOL_SIZE:
            _pool.append(conn)
        else:
            try:
                conn.close()
            except Exception:
                pass


# ── Row wrapper: makes MySQL dict behave like sqlite3.Row ──
class DictRowWrapper:
    def __init__(self, d: dict):
        self._d = d
        self._vals = list(d.values())

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._vals[key]
        return self._d[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)

    def keys(self):
        return self._d.keys()

    def __iter__(self):
        return iter(self._d)

    def __contains__(self, key: Any) -> bool:
        return key in self._d

    def _asdict(self) -> dict:
        return dict(self._d)


def _to_dict(row: Any) -> dict:
    if row is None:
        return {}
    if isinstance(row, DictRowWrapper):
        return dict(row._d)
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return {}


# ── MySQL connection wrapper ──
class MysqlConnWrapper:
    """Wraps pymysql connection to behave like sqlite3 connection.
    Auto-converts ? placeholders → %s for MySQL.
    On close(), returns the underlying connection back to the pool."""

    def __init__(self, conn: Any, cursor: Any):
        self._conn   = conn
        self._cursor = cursor
        self.lastrowid: Optional[int] = None

    def _fix(self, sql: str) -> str:
        return sql.replace('?', '%s')

    def execute(self, sql: str, params: Any = ()) -> "MysqlConnWrapper":
        self._cursor.execute(self._fix(sql), params)
        self.lastrowid = self._cursor.lastrowid
        return self

    def executemany(self, sql: str, params_list: Any) -> "MysqlConnWrapper":
        self._cursor.executemany(self._fix(sql), params_list)
        return self

    def fetchone(self) -> Optional[DictRowWrapper]:
        row = self._cursor.fetchone()
        return DictRowWrapper(row) if row else None

    def fetchall(self) -> list:
        return [DictRowWrapper(r) for r in self._cursor.fetchall()]

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        try:
            self._cursor.close()
        except Exception:
            pass
        # Return underlying connection to pool for reuse
        _return_pool_conn(self._conn)


def _db() -> Any:
    """
    Returns DB connection — MySQL (production) or SQLite (local).
    Always use conn.execute(sql, params), conn.commit(), conn.close().
    Both ? and %s placeholders work (auto-converted for MySQL).
    MySQL connections are pooled — close() returns them to pool for reuse.
    """
    if USE_MYSQL and pymysql is not None and pymysql_cursors is not None:
        conn = _get_pool_conn()
        cursor = conn.cursor()
        return MysqlConnWrapper(conn, cursor)
    else:
        conn = sqlite3.connect(_SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn