"""
MIIM HRM — SQLite → PostgreSQL Migration Script
Local miim_hrm.db → Render PostgreSQL
"""

import sqlite3
import psycopg2
import psycopg2.extras
import json
import sys

SQLITE_PATH = "miim_hrm.db"
PG_URL = "postgresql://miim_hrm_db_user:zHe5eUN2RjjeC9fkYZ7wjh1jc9Gt2g8P@dpg-d89ulqu7r5hc73dt7u6g-a.singapore-postgres.render.com/miim_hrm_db"

# ── Connect ──────────────────────────────────────────────
print("Connecting to SQLite...")
sqlite = sqlite3.connect(SQLITE_PATH)
sqlite.row_factory = sqlite3.Row

print("Connecting to PostgreSQL...")
pg = psycopg2.connect(PG_URL)
pg.autocommit = False
cur = pg.cursor()

# ── Get all SQLite tables ─────────────────────────────────
tables = [r[0] for r in sqlite.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
).fetchall()]
print(f"\nSQLite tables found: {tables}\n")

# ── Helper: SQLite type → PostgreSQL type ────────────────
def to_pg_type(sqlite_type: str) -> str:
    t = sqlite_type.upper().strip()
    if not t or t == "TEXT" or "CHAR" in t or "CLOB" in t:
        return "TEXT"
    if t in ("INTEGER", "INT") or "INT" in t:
        return "BIGINT"
    if t in ("REAL", "FLOAT", "DOUBLE"):
        return "DOUBLE PRECISION"
    if t in ("BLOB",):
        return "BYTEA"
    if t in ("BOOLEAN", "BOOL"):
        return "BOOLEAN"
    if "NUMERIC" in t or "DECIMAL" in t:
        return "NUMERIC"
    return "TEXT"

# ── Migrate each table ───────────────────────────────────
for table in tables:
    print(f"Migrating: {table}")

    # Get column info from SQLite
    cols_info = sqlite.execute(f"PRAGMA table_info({table})").fetchall()
    if not cols_info:
        print(f"  Skipping {table} (no columns)")
        continue

    # Drop & recreate table in PostgreSQL
    cur.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')

    col_defs = []
    for col in cols_info:
        col_name = col[1]
        col_type = to_pg_type(col[2])
        pk = col[5]  # 1 if primary key

        if pk and col_type == "BIGINT":
            col_defs.append(f'"{col_name}" BIGSERIAL PRIMARY KEY')
        elif pk:
            col_defs.append(f'"{col_name}" {col_type} PRIMARY KEY')
        else:
            col_defs.append(f'"{col_name}" {col_type}')

    create_sql = f'CREATE TABLE "{table}" ({", ".join(col_defs)})'
    cur.execute(create_sql)

    # Copy data
    rows = sqlite.execute(f"SELECT * FROM {table}").fetchall()
    if rows:
        col_names = [f'"{c[1]}"' for c in cols_info]
        placeholders = ", ".join(["%s"] * len(cols_info))
        insert_sql = f'INSERT INTO "{table}" ({", ".join(col_names)}) VALUES ({placeholders})'

        data = []
        for row in rows:
            row_data = []
            for val in row:
                if isinstance(val, bytes):
                    val = val.decode("utf-8", errors="replace")
                row_data.append(val)
            data.append(tuple(row_data))

        psycopg2.extras.execute_batch(cur, insert_sql, data)
        print(f"  ✅ {len(rows)} rows inserted")
    else:
        print(f"  ✅ 0 rows (empty table)")

# ── Also ensure users table exists ───────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    name TEXT,
    role TEXT,
    department TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    photo TEXT,
    access TEXT DEFAULT 'Employee',
    status TEXT DEFAULT 'Active',
    approval_status TEXT DEFAULT 'approved',
    manager TEXT DEFAULT '',
    empid TEXT DEFAULT '',
    joindate TEXT DEFAULT '',
    emp_type TEXT DEFAULT 'Regular',
    password_change_required BIGINT DEFAULT 0,
    reset_token TEXT,
    reset_token_expiry TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Insert admin if not exists
import hashlib
pw = hashlib.sha256('admin'.encode()).hexdigest()
cur.execute("""
INSERT INTO users (username,password,name,role,department,access,status,approval_status,password_change_required)
VALUES ('admin',%s,'Admin','Administrator','HR Department','Full Access','Active','approved',1)
ON CONFLICT (username) DO NOTHING
""", (pw,))

pg.commit()
print("\n✅ Migration complete!")

# ── Final check ──────────────────────────────────────────
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
pg_tables = [r[0] for r in cur.fetchall()]
print(f"PostgreSQL tables: {pg_tables}")

cur.close()
pg.close()
sqlite.close()