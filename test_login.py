import os
os.environ['MYSQL_HOST'] = 'srv1870.hstgr.io'
os.environ['MYSQL_USER'] = 'u597435008_sivabalan'
os.environ['MYSQL_PASSWORD'] = 'Miim@2026#'
os.environ['MYSQL_DB'] = 'u597435008_miim_hrm'
os.environ['MYSQL_PORT'] = '3306'

from db_layer import _db
from security import hash_password

conn = _db()
new_hash = hash_password('Miim@2026#')
conn.execute(
    "UPDATE employees SET password_hash=%s WHERE user_id=%s",
    (new_hash, 'mithun.r0101')
)
conn.commit()
conn.close()
print("Password reset done!")