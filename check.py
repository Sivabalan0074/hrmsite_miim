import sqlite3

conn = sqlite3.connect('miim_hr.db')
rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [r[0] for r in rows])

# Check expenses table has data or not
try:
    count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    print("Expenses count:", count)
except Exception as e:
    print("Expenses table error:", e)

conn.close()