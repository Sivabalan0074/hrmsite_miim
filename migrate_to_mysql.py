"""
migrate_to_mysql.py — MIIM HRM
SQLite → Hostinger MySQL Migration Script
=========================================
Run this ONCE from your local machine (where miim_hrm.db is present).

Usage:
  pip install PyMySQL
  python migrate_to_mysql.py
"""

import sqlite3
import pymysql
import sys

# ─── CONFIG — உங்க Hostinger details இங்கே fill பண்ணுங்க ───
SQLITE_PATH = "miim_hrm.db"   # Local SQLite DB path

MYSQL_HOST     = "srv1870.hstgr.io"
MYSQL_PORT     = 3306
MYSQL_USER     = "u597435008_sivabalan"
MYSQL_PASSWORD = "Miim@2026#"   # ← இங்கே உங்க password போடுங்க
MYSQL_DB       = "u597435008_miim_hrm"
# ─────────────────────────────────────────────────────────────

def get_sqlite_tables(sq):
    rows = sq.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    return [r[0] for r in rows]

def sqlite_type_to_mysql(col_type: str) -> str:
    t = col_type.upper().strip()
    if not t or t == "TEXT":         return "TEXT"
    if t == "INTEGER":               return "BIGINT"
    if t == "REAL" or t == "NUMERIC": return "DOUBLE"
    if t == "BLOB":                  return "LONGBLOB"
    if "INT" in t:                   return "BIGINT"
    if "CHAR" in t or "CLOB" in t:   return "TEXT"
    if "REAL" in t or "FLOA" in t or "DOUB" in t: return "DOUBLE"
    return "TEXT"

def migrate():
    print("=" * 55)
    print("  MIIM HRM — SQLite → MySQL Migration")
    print("=" * 55)

    # Connect SQLite
    try:
        sq = sqlite3.connect(SQLITE_PATH)
        sq.row_factory = sqlite3.Row
        print(f"✅ SQLite connected: {SQLITE_PATH}")
    except Exception as e:
        print(f"❌ SQLite error: {e}")
        sys.exit(1)

    # Connect MySQL
    try:
        my = pymysql.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=MYSQL_DB, charset="utf8mb4",
            autocommit=False
        )
        cur = my.cursor()
        print(f"✅ MySQL connected: {MYSQL_HOST}/{MYSQL_DB}")
    except Exception as e:
        print(f"❌ MySQL connection error: {e}")
        print("   → Password correct-ஆ இருக்கா? Hostinger Remote MySQL allow பண்ணினீங்களா?")
        sys.exit(1)

    tables = get_sqlite_tables(sq)
    print(f"\n📋 Tables found: {tables}\n")

    for table in tables:
        print(f"─── Migrating: {table} ───")

        # Get SQLite schema
        cols_info = sq.execute(f"PRAGMA table_info({table})").fetchall()
        if not cols_info:
            print(f"   ⚠️  No columns found, skipping.")
            continue

        # Build CREATE TABLE for MySQL
        col_defs = []
        pk_col = None
        for col in cols_info:
            cname = col[1]
            ctype = sqlite_type_to_mysql(col[2])
            notnull = "NOT NULL" if col[3] else ""
            is_pk = col[5]
            if is_pk == 1:
                pk_col = cname
                col_defs.append(f"`{cname}` BIGINT NOT NULL AUTO_INCREMENT")
            else:
                col_defs.append(f"`{cname}` {ctype} {notnull}".strip())

        if pk_col:
            col_defs.append(f"PRIMARY KEY (`{pk_col}`)")

        create_sql = f"CREATE TABLE IF NOT EXISTS `{table}` (\n  " + ",\n  ".join(col_defs) + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"

        try:
            cur.execute(f"DROP TABLE IF EXISTS `{table}`")
            cur.execute(create_sql)
            my.commit()
            print(f"   ✅ Table created")
        except Exception as e:
            print(f"   ❌ Table create error: {e}")
            print(f"   SQL: {create_sql}")
            continue

        # Migrate data
        rows = sq.execute(f"SELECT * FROM `{table}`").fetchall()
        if not rows:
            print(f"   ℹ️  No data to migrate")
            continue

        col_names = [col[1] for col in cols_info]
        placeholders = ", ".join(["%s"] * len(col_names))
        col_list = ", ".join([f"`{c}`" for c in col_names])
        insert_sql = f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders})"

        batch = []
        for row in rows:
            batch.append(tuple(row[c] for c in col_names))

        try:
            cur.executemany(insert_sql, batch)
            my.commit()
            print(f"   ✅ {len(batch)} rows migrated")
        except Exception as e:
            print(f"   ❌ Insert error: {e}")
            my.rollback()

    sq.close()
    my.close()
    print("\n" + "=" * 55)
    print("  Migration Complete! ✅")
    print("  இப்போ Render-ல் MySQL env vars set பண்ணுங்க.")
    print("=" * 55)

if __name__ == "__main__":
    if "YOUR_PASSWORD_HERE" in MYSQL_PASSWORD:
        print("❌ MYSQL_PASSWORD fill பண்ணலை! Script-ல் உங்க password போடுங்க.")
        sys.exit(1)
    migrate()