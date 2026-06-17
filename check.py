import pymysql

conn = pymysql.connect(
    host='srv1870.hstgr.io',
    user='u597435008_miim_hrm',
    password='Miim@2026#',
    database='u597435008_miim_hrm',
    charset='utf8mb4'
)
cur = conn.cursor()
cur.execute("SELECT username, status, force_reset FROM employees WHERE username='gokulraj.b'")
row = cur.fetchone()
print(row if row else 'NOT FOUND')
cur.close()
conn.close()