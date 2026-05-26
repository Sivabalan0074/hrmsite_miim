"""
MIIM HR Dashboard — Flask Backend
All routes, DB helpers, and background services in one file.
"""
from flask import Flask, jsonify, request
import threading, datetime

app = Flask(__name__)

# ── CORS: Secure — only allow whitelisted origins ──
from security import (
    limiter, hash_password, verify_password, needs_bcrypt_upgrade,
    create_token, verify_token, get_current_user,
    require_auth, require_role,
    apply_cors_headers,
    safe_str,
    SMTP_USER as _CHAT_SMTP_USER,
    SMTP_PASS as _CHAT_SMTP_PASS,
    ADMIN_EMAIL as _ADMIN_EMAIL,
)
limiter.init_app(app)


@app.after_request
def _add_cors(response):
    origin = request.headers.get('Origin', '')
    return apply_cors_headers(response, origin)


@app.before_request
def _handle_options():
    if request.method == 'OPTIONS':
        from flask import make_response as _mr
        r = _mr('', 204)
        origin = request.headers.get('Origin', '')
        r = apply_cors_headers(r, origin)
        return r


@app.before_request
def _inject_token_from_cookie():
    """Fallback: if JS didn't send Authorization header, read from cookie."""
    if not request.headers.get('Authorization'):
        token = request.cookies.get('miim_token', '')
        if token:
            request.environ['HTTP_AUTHORIZATION'] = 'Bearer ' + token


# ── IN-MEMORY DATA STORE ──
employees = [
    {"id": 1, "emp_id": "MIIM001", "name": "Aravind Kumar", "department": "Engineering", "designation": "Senior Developer", "email": "aravind@miim.com", "phone": "9876543210", "status": "active", "join_date": "2022-01-15", "salary": 75000, "pending_leaves": 2},
    {"id": 2, "emp_id": "MIIM002", "name": "Priya Sharma", "department": "HR", "designation": "HR Manager", "email": "priya@miim.com", "phone": "9876543211", "status": "active", "join_date": "2021-06-01", "salary": 65000, "pending_leaves": 1},
    {"id": 3, "emp_id": "MIIM003", "name": "Ravi Chandran", "department": "Finance", "designation": "Accountant", "email": "ravi@miim.com", "phone": "9876543212", "status": "active", "join_date": "2023-03-10", "salary": 55000, "pending_leaves": 0},
    {"id": 4, "emp_id": "MIIM004", "name": "Meena Devi", "department": "Marketing", "designation": "Marketing Lead", "email": "meena@miim.com", "phone": "9876543213", "status": "active", "join_date": "2022-08-20", "salary": 60000, "pending_leaves": 3},
    {"id": 5, "emp_id": "MIIM005", "name": "Suresh Babu", "department": "Engineering", "designation": "Junior Developer", "email": "suresh@miim.com", "phone": "9876543214", "status": "active", "join_date": "2023-11-01", "salary": 45000, "pending_leaves": 0},
    {"id": 6, "emp_id": "MIIM006", "name": "Lakshmi Nair", "department": "Operations", "designation": "Operations Manager", "email": "lakshmi@miim.com", "phone": "9876543215", "status": "inactive", "join_date": "2020-04-15", "salary": 70000, "pending_leaves": 0},
]

attendance_records = [
    {"id": 1, "emp_id": "MIIM001", "name": "Aravind Kumar", "date": "2026-04-19", "check_in": "09:02", "check_out": "18:05", "status": "present", "hours": 9.05},
    {"id": 2, "emp_id": "MIIM002", "name": "Priya Sharma", "date": "2026-04-19", "check_in": "08:55", "check_out": "18:00", "status": "present", "hours": 9.08},
    {"id": 3, "emp_id": "MIIM003", "name": "Ravi Chandran", "date": "2026-04-19", "check_in": None, "check_out": None, "status": "absent", "hours": 0},
    {"id": 4, "emp_id": "MIIM004", "name": "Meena Devi", "date": "2026-04-19", "check_in": "09:30", "check_out": "17:45", "status": "late", "hours": 8.25},
    {"id": 5, "emp_id": "MIIM005", "name": "Suresh Babu", "date": "2026-04-19", "check_in": "09:00", "check_out": "18:00", "status": "present", "hours": 9.0},
]

leave_requests = [
    {"id": 1, "emp_id": "MIIM001", "name": "Aravind Kumar", "type": "Casual Leave", "from_date": "2026-04-22", "to_date": "2026-04-23", "days": 2, "reason": "Personal work", "status": "pending", "applied_on": "2026-04-18"},
    {"id": 2, "emp_id": "MIIM004", "name": "Meena Devi", "type": "Sick Leave", "from_date": "2026-04-21", "to_date": "2026-04-21", "days": 1, "reason": "Not feeling well", "status": "pending", "applied_on": "2026-04-19"},
    {"id": 3, "emp_id": "MIIM002", "name": "Priya Sharma", "type": "Annual Leave", "from_date": "2026-05-01", "to_date": "2026-05-05", "days": 5, "reason": "Vacation", "status": "approved", "applied_on": "2026-04-10"},
]

holidays = [
    {"id": 1, "name": "Tamil New Year", "date": "2026-04-14", "day": "Tuesday", "type": "National"},
    {"id": 2, "name": "Labour Day", "date": "2026-05-01", "day": "Friday", "type": "National"},
    {"id": 3, "name": "Eid al-Adha", "date": "2026-06-07", "day": "Sunday", "type": "National"},
    {"id": 4, "name": "Independence Day", "date": "2026-08-15", "day": "Saturday", "type": "National"},
    {"id": 5, "name": "Gandhi Jayanti", "date": "2026-10-02", "day": "Friday", "type": "National"},
    {"id": 6, "name": "Diwali", "date": "2026-10-19", "day": "Monday", "type": "National"},
    {"id": 7, "name": "Christmas", "date": "2026-12-25", "day": "Friday", "type": "National"},
    {"id": 8, "name": "Company Foundation Day", "date": "2026-03-10", "day": "Tuesday", "type": "Company"},
]

accounts = [
    {"id": 1, "type": "income", "category": "Salary Disbursement", "amount": 450000, "date": "2026-04-01", "description": "April salary processed", "status": "completed"},
    {"id": 2, "type": "expense", "category": "Office Rent", "amount": 80000, "date": "2026-04-01", "description": "Monthly rent", "status": "completed"},
    {"id": 3, "type": "expense", "category": "Utilities", "amount": 12000, "date": "2026-04-05", "description": "Electricity & internet", "status": "completed"},
    {"id": 4, "type": "income", "category": "Project Revenue", "amount": 200000, "date": "2026-04-10", "description": "Client payment Q1", "status": "completed"},
    {"id": 5, "type": "expense", "category": "Office Supplies", "amount": 8500, "date": "2026-04-12", "description": "Stationery & supplies", "status": "pending"},
]

guests = [
    {"id": 1, "name": "Rajesh Verma", "company": "TechCorp Ltd", "purpose": "Business Meeting", "host": "Aravind Kumar", "date": "2026-04-19", "check_in": "10:30", "check_out": "12:00", "status": "checked_out"},
    {"id": 2, "name": "Sunita Patel", "company": "DesignStudio", "purpose": "Interview", "host": "Priya Sharma", "date": "2026-04-19", "check_in": "14:00", "check_out": None, "status": "checked_in"},
    {"id": 3, "name": "Michael Brown", "company": "GlobalVentures", "purpose": "Partnership Discussion", "host": "Meena Devi", "date": "2026-04-20", "check_in": None, "check_out": None, "status": "expected"},
]


# ── ROUTES ──


@app.route('/')


@app.route('/3_hr_dashboard.html')
def index():
    import os
    from flask import Response, send_file
    # Try to serve the HTML file directly (stays in sync with latest edits)
    _base = os.path.dirname(os.path.abspath(__file__))
    for _f in [
        os.path.join(_base, 'template', '3_hr_dashboard.html'),
        os.path.join(_base, '3_hr_dashboard.html'),
    ]:
        if os.path.exists(_f):
            return send_file(_f, mimetype='text/html')
    return Response('<h3>Dashboard file not found.</h3>', mimetype='text/html')


# ── DB helper — MySQL (production) / SQLite (local) ──
from db_layer import _db

# Stats


@app.route('/api/stats')
@require_auth
def get_stats():
    try:
        conn = _db()
        total = conn.execute("SELECT COUNT(*) FROM employees WHERE status='active'").fetchone()[0]
        pending_lv = conn.execute("SELECT COUNT(*) FROM leave_requests WHERE status='pending'").fetchone()[0]
        conn.close()
        return jsonify({"total_employees": total, "present_today": 0, "pending_leaves": pending_lv, "total_income": 0, "total_expense": 0, "net_balance": 0, "guests_today": 0})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500

# Employees


@app.route('/api/employees', methods=['GET'])
@require_auth
def get_employees():
    try:
        conn = _db()
        rows = conn.execute("SELECT * FROM employees WHERE status='active' ORDER BY id").fetchall()
        emps = [dict(r) for r in rows]
        # Merge days_worked, pay_date, mode_of_payment from accounts table
        # (source of truth for these fields until employees table is fully synced)
        accs = conn.execute(
            "SELECT emp_id, days_worked, pay_date, mode_of_payment FROM accounts"
        ).fetchall()
        acc_map = {}
        for a in accs:
            acc_map[str(a['emp_id'])] = dict(a)
        for emp in emps:
            ac = acc_map.get(str(emp['id']))
            if ac:
                if not emp.get('days_worked') and ac.get('days_worked'):
                    emp['days_worked'] = ac['days_worked']
                if not emp.get('pay_date') and ac.get('pay_date'):
                    emp['pay_date'] = ac['pay_date']
                if not emp.get('mode_of_payment') and ac.get('mode_of_payment'):
                    emp['mode_of_payment'] = ac['mode_of_payment']
        conn.close()
        return jsonify({"success": True, "employees": emps})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/employees/all-with-pending', methods=['GET'])
@require_auth
def get_employees_with_pending():
    try:
        conn = _db()
        rows = conn.execute("SELECT * FROM employees WHERE status='active' ORDER BY id").fetchall()
        emps = [dict(r) for r in rows]
        # Merge days_worked, pay_date, mode_of_payment from accounts table
        accs = conn.execute(
            "SELECT emp_id, days_worked, pay_date, mode_of_payment FROM accounts"
        ).fetchall()
        acc_map = {}
        for a in accs:
            acc_map[str(a['emp_id'])] = dict(a)
        for emp in emps:
            ac = acc_map.get(str(emp['id']))
            if ac:
                if not emp.get('days_worked') and ac.get('days_worked'):
                    emp['days_worked'] = ac['days_worked']
                if not emp.get('pay_date') and ac.get('pay_date'):
                    emp['pay_date'] = ac['pay_date']
                if not emp.get('mode_of_payment') and ac.get('mode_of_payment'):
                    emp['mode_of_payment'] = ac['mode_of_payment']
        pending_rows = conn.execute("SELECT * FROM pending_employees").fetchall()
        pending_list = []
        for r in pending_rows:
            d = dict(r)
            d['pending_id'] = d['id']
            pending_list.append(d)
        conn.close()
        return jsonify({"success": True, "employees": emps, "pending": pending_list})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/employees/<int:emp_id>', methods=['GET'])
@require_auth
def get_employee(emp_id):
    try:
        conn = _db()
        row = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
        conn.close()
        if not row: return jsonify({"error": "Not found"}), 404
        return jsonify({"success": True, "employee": dict(row)})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/employees', methods=['POST'])
@require_auth
def add_employee():
    try:
        data = request.json or {}
        # Auto-generate user_id: name letters + DD + MM of joindate
        _uname5 = data.get('username', '').strip()
        _ujd5 = data.get('joindate', '').strip()
        # Keep username lowercase as-is, only strip whitespace — dot/underscore stays
        _letters5 = _uname5.lower().replace(' ', '')
        if _ujd5 and len(_ujd5) >= 10:
            _parts5 = _ujd5.split('-')
            _dd5 = _parts5[2][:2] if len(_parts5) > 2 else '01'
            _mm5 = _parts5[1][:2] if len(_parts5) > 1 else '01'
            _uid5 = _letters5 + _dd5 + _mm5
        else:
            _uid5 = _letters5 + '0101'
        conn = _db()
        conn.execute("""INSERT INTO employees (username,user_id,empid,dept,desig,manager,joindate,type,company_email,password_hash,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     (_uname5, _uid5, data.get('empid', ''),
                      data.get('dept', ''), data.get('desig', ''), data.get('manager', ''),
                      _ujd5, data.get('type', 'Regular'),
                      data.get('company_email', ''), hash_password(data.get('password_hash') or 'miim@123'), 'active'))
        conn.commit()
        conn.close()
        return jsonify({"success": True}), 201
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/employees/request', methods=['POST'])
@require_auth
def request_employee():
    try:
        data = request.json or {}
        conn = _db()
        # Auto-generate user_id from empid
        empid = data.get('empid', '').strip()
        username = data.get('username', '').strip()
        # Generate user_id: first 4 chars of username + empid digits
        import re as _re
        digits = _re.sub(r'[^0-9]', '', empid)[-4:]
        letters = _re.sub(r'[^a-zA-Z]', '', username)[:4].lower()
        user_id = letters + digits if digits else letters + '0001'
        # Insert into pending_employees
        conn.execute("""INSERT INTO pending_employees
            (username, user_id, empid, dept, desig, manager, joindate, type,
             company_email, password_hash, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (username, user_id, empid,
                      data.get('dept', ''), data.get('desig', ''),
                      data.get('manager', ''), data.get('joindate', ''),
                      data.get('type', 'Regular'), data.get('company_email', ''),
                      'miim@123', 'pending', str(datetime.datetime.now())))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Employee request submitted for approval'}), 201
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/request', methods=['GET'])
@require_auth
def get_employee_requests():
    try:
        conn = _db()
        rows = conn.execute("SELECT * FROM pending_employees WHERE status='pending' ORDER BY id DESC").fetchall()
        conn.close()
        return jsonify({'success': True, 'requests': [dict(r) for r in rows]})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/<int:emp_id>', methods=['PUT'])
@require_auth
def update_employee(emp_id):
    try:
        data = request.json or {}
        # Whitelist allowed columns to prevent SQL errors on unknown fields
        ALLOWED = {
            'username', 'user_id', 'empid', 'dept', 'desig', 'manager',
            'joindate', 'type', 'company_email', 'mobile', 'dob',
            'father_name', 'photo_url', 'password_hash', 'force_reset',
            'status', 'salary_status', 'probation_period', 'intern_period',
            'days_worked', 'pay_date', 'mode_of_payment'
        }
        filtered = {k: v for k, v in data.items() if k in ALLOWED}
        if not filtered:
            return jsonify({"success": True})
        # ── Auto-regenerate user_id when username or joindate changes ──
        username = filtered.get('username') or data.get('username') or ''
        joindate = filtered.get('joindate') or data.get('joindate') or ''
        if not username or not joindate:
            # Fetch existing values from DB if not in payload
            conn = _db()
            _row = conn.execute("SELECT username, joindate FROM employees WHERE id=?", (emp_id,)).fetchone()
            conn.close()
            if _row:
                username = username or _row[0] or ''
                joindate = joindate or _row[1] or ''
            conn = _db()
        else:
            conn = _db()
        # Keep username lowercase as-is, only strip whitespace — dot/underscore stays
        _letters = username.lower().replace(' ', '')
        if joindate and len(joindate) >= 10:
            _parts = joindate.split('-')
            _dd = _parts[2][:2] if len(_parts) > 2 else '01'
            _mm = _parts[1][:2] if len(_parts) > 1 else '01'
            filtered['user_id'] = _letters + _dd + _mm
        else:
            filtered['user_id'] = _letters + '0101'
        fields = ', '.join(f"{k}=?" for k in filtered.keys())
        conn.execute(f"UPDATE employees SET {fields} WHERE id=?", list(filtered.values()) + [emp_id])
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/employees/<int:emp_id>/history', methods=['GET'])
@require_auth
def get_emp_history(emp_id):
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT field, from_val as [from], to_val as [to], changed_date as date FROM emp_status_history WHERE emp_id=? ORDER BY id ASC",
            (emp_id,)
        ).fetchall()
        conn.close()
        return jsonify({"success": True, "history": [dict(r) for r in rows]})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/<int:emp_id>/history', methods=['POST'])
@require_auth
def add_emp_history(emp_id):
    try:
        data = request.json or {}
        import datetime as _dt
        conn = _db()
        conn.execute(
            "INSERT INTO emp_status_history (emp_id, field, from_val, to_val, changed_date, created_at) VALUES (?,?,?,?,?,?)",
            (emp_id, data.get('field', ''), data.get('from', '—'), data.get('to', ''), data.get('date', str(_dt.date.today())), str(_dt.datetime.now()))
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/<int:emp_id>', methods=['DELETE'])
@require_auth
def delete_employee(emp_id):
    try:
        conn = _db()
        conn.execute("UPDATE employees SET status='inactive' WHERE id=?", (emp_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


# ── PROMOTION: SM/PM request -> Admin approve ──
def _ensure_pending_promotions_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS pending_promotions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER NOT NULL,
        old_desig TEXT, new_desig TEXT,
        effective_date TEXT, remarks TEXT,
        requested_by TEXT, requested_at TEXT,
        status TEXT DEFAULT 'pending',
        approved_by TEXT, approved_at TEXT,
        rejected_reason TEXT,
        hr_approved_by TEXT, hr_approved_at TEXT,
        admin_approved_by TEXT, admin_approved_at TEXT
    )""")
    for _col, _def in [
        ('rejected_reason', 'TEXT'),
        ('hr_approved_by', 'TEXT'),
        ('hr_approved_at', 'TEXT'),
        ('admin_approved_by', 'TEXT'),
        ('admin_approved_at', 'TEXT'),
    ]:
        try:
            conn.execute("ALTER TABLE pending_promotions ADD COLUMN " + _col + " " + _def)
        except Exception:
            pass
    conn.commit()


@app.route('/api/promotions/request', methods=['POST'])
@require_auth
def promotion_request():
    try:
        data = request.json or {}
        emp_id = data.get('emp_id')
        new_desig = data.get('new_desig', '').strip()
        eff_date = data.get('effective_date', str(datetime.date.today()))
        remarks = data.get('remarks', '')
        requested_by = data.get('requested_by', 'Admin')
        if not emp_id or not new_desig:
            return jsonify({'success': False, 'error': 'emp_id and new_desig are required'}), 400
        conn = _db()
        _ensure_pending_promotions_table(conn)
        emp = conn.execute('SELECT desig FROM employees WHERE id=?', (emp_id,)).fetchone()
        if not emp:
            conn.close()
            return jsonify({'success': False, 'error': 'Employee not found'}), 404
        old_desig = emp['desig'] or ''
        conn.execute(
            "INSERT INTO pending_promotions (emp_id, old_desig, new_desig, effective_date, remarks, requested_by, requested_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
            (emp_id, old_desig, new_desig, eff_date, remarks, requested_by, str(datetime.datetime.now()))
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Promotion request submitted. Waiting for Admin approval.'})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/promotions/pending', methods=['GET'])
@require_auth
def get_pending_promotions():
    try:
        caller = request.args.get('caller', '').strip()
        role, dept = _get_role_dept(caller) if caller else ('admin', '')
        conn = _db()
        _ensure_pending_promotions_table(conn)
        # HR sees: status='pending' (waiting for HR approval)
        # Admin sees: status='hr_approved' (waiting for Admin approval)
        # Admin also sees all if no caller given
        if role == 'hr':
            rows = conn.execute(
                "SELECT pp.*, e.username, e.dept FROM pending_promotions pp JOIN employees e ON e.id = pp.emp_id WHERE pp.status = 'pending' ORDER BY pp.requested_at DESC"
            ).fetchall()
        elif role == 'admin':
            rows = conn.execute(
                "SELECT pp.*, e.username, e.dept FROM pending_promotions pp JOIN employees e ON e.id = pp.emp_id WHERE pp.status IN ('pending','hr_approved') ORDER BY pp.requested_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT pp.*, e.username, e.dept FROM pending_promotions pp JOIN employees e ON e.id = pp.emp_id WHERE pp.status IN ('pending','hr_approved') ORDER BY pp.requested_at DESC"
            ).fetchall()
        conn.close()
        return jsonify({'success': True, 'promotions': [dict(r) for r in rows]})
    except Exception:
        return jsonify({"success": True})


@app.route('/api/promotions/<int:promo_id>/approve', methods=['POST'])
@require_auth
def approve_promotion(promo_id):
    try:
        data = request.json or {}
        approved_by = data.get('approved_by', 'Admin')
        caller = data.get('caller', approved_by)
        conn = _db()
        _ensure_pending_promotions_table(conn)
        row = conn.execute('SELECT * FROM pending_promotions WHERE id=?', (promo_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Promotion request not found'}), 404
        now = str(datetime.datetime.now())
        role, _ = _get_role_dept(caller)
        status = row['status']

        # ── STAGE 1: HR approves (status: pending → hr_approved) ──
        if status == 'pending' and role in ('hr',):
            conn.execute(
                "UPDATE pending_promotions SET status='hr_approved', hr_approved_by=?, hr_approved_at=? WHERE id=?",
                (approved_by, now, promo_id)
            )
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'stage': 'hr_approved',
                            'message': 'HR approved. Waiting for Admin final approval.'})

        # ── STAGE 2: Admin final approve (status: hr_approved → approved) ──
        if status == 'hr_approved' and role == 'admin':
            conn.execute('UPDATE employees SET desig=? WHERE id=?', (row['new_desig'], row['emp_id']))
            hist_to = row['new_desig'] + (' | ' + row['remarks'] if row['remarks'] else '') + ' * by: ' + approved_by
            conn.execute(
                'INSERT INTO emp_status_history (emp_id, field, from_val, to_val, changed_date, created_at) VALUES (?,?,?,?,?,?)',
                (row['emp_id'], '\U0001f3c6 Promotion', row['old_desig'], hist_to, row['effective_date'], now)
            )
            conn.execute(
                "UPDATE pending_promotions SET status='approved', admin_approved_by=?, admin_approved_at=?, approved_by=?, approved_at=? WHERE id=?",
                (approved_by, now, approved_by, now, promo_id)
            )
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'stage': 'approved',
                            'message': 'Promotion fully approved! Designation updated.'})

        # ── Admin can also approve directly from pending (skip HR) ──
        if status == 'pending' and role == 'admin':
            conn.execute('UPDATE employees SET desig=? WHERE id=?', (row['new_desig'], row['emp_id']))
            hist_to = row['new_desig'] + (' | ' + row['remarks'] if row['remarks'] else '') + ' * by: ' + approved_by
            conn.execute(
                'INSERT INTO emp_status_history (emp_id, field, from_val, to_val, changed_date, created_at) VALUES (?,?,?,?,?,?)',
                (row['emp_id'], '\U0001f3c6 Promotion', row['old_desig'], hist_to, row['effective_date'], now)
            )
            conn.execute(
                "UPDATE pending_promotions SET status='approved', admin_approved_by=?, admin_approved_at=?, approved_by=?, approved_at=? WHERE id=?",
                (approved_by, now, approved_by, now, promo_id)
            )
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'stage': 'approved',
                            'message': 'Promotion approved by Admin.'})

        conn.close()
        return jsonify({'success': False, 'error': 'Cannot approve at this stage (status: ' + status + ', role: ' + role + ')'}), 400
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/promotions/<int:promo_id>/reject', methods=['POST'])
@require_auth
def reject_promotion(promo_id):
    try:
        data = request.json or {}
        rejected_by = data.get('rejected_by', 'Admin')
        reason = data.get('reason', '')
        conn = _db()
        _ensure_pending_promotions_table(conn)
        row = conn.execute('SELECT * FROM pending_promotions WHERE id=?', (promo_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Promotion request not found'}), 404
        if row['status'] != 'pending':
            conn.close()
            return jsonify({'success': False, 'error': 'Already ' + row['status']}), 400
        conn.execute(
            "UPDATE pending_promotions SET status='rejected', approved_by=?, approved_at=?, rejected_reason=? WHERE id=?",
            (rejected_by, str(datetime.datetime.now()), reason, promo_id)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Promotion request rejected.'})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/<int:emp_id>/relieve', methods=['POST'])
@require_auth
def relieve_employee(emp_id):
    try:
        data = request.json or {}
        relieve_date = data.get('relieve_date', str(datetime.date.today()))
        relieve_reason = data.get('relieve_reason', '')
        relieved_by = data.get('relieved_by', 'Admin')
        conn = _db()
        conn.execute(
            "UPDATE employees SET status='relieved', relieve_date=?, relieve_reason=?, relieved_by=? WHERE id=?",
            (relieve_date, relieve_reason, relieved_by, emp_id)
        )
        conn.execute(
            "INSERT INTO emp_status_history (emp_id, field, from_val, to_val, changed_date, created_at) VALUES (?,?,?,?,?,?)",
            (emp_id, 'Relieved', 'Active', relieve_reason or 'Relieved from service', relieve_date, str(datetime.datetime.now()))
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Employee relieved successfully"})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/ex-employees', methods=['GET'])
@require_auth
def get_ex_employees():
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT * FROM employees WHERE status='relieved' ORDER BY relieve_date DESC"
        ).fetchall()
        ex_emps = [dict(r) for r in rows]
        for emp in ex_emps:
            sal_rows = conn.execute(
                "SELECT period, net_pay, total_earnings, total_deductions, basic, days_worked, approval_status FROM salary_structures WHERE emp_id=? ORDER BY id ASC",
                (emp['id'],)
            ).fetchall()
            emp['salary_history'] = [dict(s) for s in sal_rows]
            hist_rows = conn.execute(
                "SELECT field, from_val, to_val, changed_date FROM emp_status_history WHERE emp_id=? ORDER BY id ASC",
                (emp['id'],)
            ).fetchall()
            emp['history'] = [dict(h) for h in hist_rows]
            approved_sal = [s for s in emp['salary_history'] if (s.get('approval_status') or '').lower() == 'approved']
            emp['total_salary_received'] = sum(s.get('net_pay', 0) or 0 for s in approved_sal)
            emp['months_worked'] = len(approved_sal)
        conn.close()
        return jsonify({"success": True, "ex_employees": ex_emps, "count": len(ex_emps)})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/ex-employees/<int:emp_id>', methods=['DELETE'])
@require_auth
def delete_ex_employee(emp_id):
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id FROM employees WHERE id=? AND status='relieved'", (emp_id,)
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "error": "Ex-employee record not found"}), 404
        conn.execute("DELETE FROM emp_status_history WHERE emp_id=?", (emp_id,))
        conn.execute("DELETE FROM salary_structures WHERE emp_id=?", (emp_id,))
        conn.execute("DELETE FROM employees WHERE id=?", (emp_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Ex-employee record deleted successfully"})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/ex-employees/<int:emp_id>/restore', methods=['POST'])
@require_auth
def restore_ex_employee(emp_id):
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id FROM employees WHERE id=? AND status='relieved'", (emp_id,)
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "error": "Ex-employee record not found"}), 404
        conn.execute(
            "UPDATE employees SET status='active', relieve_date='', relieve_reason='', relieved_by='' WHERE id=?",
            (emp_id,)
        )
        today = str(datetime.date.today())
        conn.execute(
            "INSERT INTO emp_status_history (emp_id, field, from_val, to_val, changed_date, created_at) VALUES (?,?,?,?,?,?)",
            (emp_id, 'Status', 'Relieved', 'Active', today, str(datetime.datetime.now()))
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Employee restored successfully"})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/<int:emp_id>/salary-status', methods=['PUT', 'POST'])
@require_auth
def update_employee_salary_status(emp_id):
    try:
        data = request.json or {}
        salary_status = data.get('salary_status', '')
        conn = _db()
        conn.execute("UPDATE employees SET salary_status=? WHERE id=?", (salary_status, emp_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "salary_status": salary_status})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

# Attendance


@app.route('/api/attendance', methods=['GET'])
@require_auth
def get_attendance():
    try:
        date = request.args.get('date', str(datetime.date.today()))
        conn = _db()
        rows = conn.execute("""SELECT a.*, e.username as name, e.empid as emp_id FROM attendance a
            JOIN employees e ON e.id=a.emp_id WHERE a.date=?""", (date,)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/attendance', methods=['POST'])
@require_auth
def mark_attendance():
    try:
        data = request.json or {}
        conn = _db()
        conn.execute("INSERT INTO attendance (emp_id,date,checkin,checkout,status,marked_by) VALUES (?,?,?,?,?,?)",
                     (data.get('emp_id'), data.get('date'), data.get('checkin', '--'), data.get('checkout', '--'), data.get('status', 'present'), data.get('marked_by', 'admin')))
        conn.commit()
        conn.close()
        return jsonify({"success": True}), 201
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500

# Leaves


@app.route('/api/leaves', methods=['GET'])
@require_auth
def get_leaves():
    try:
        conn = _db()
        status = request.args.get('status')
        if status:
            rows = conn.execute("SELECT * FROM leave_requests WHERE status=?", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM leave_requests ORDER BY id DESC").fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/leaves', methods=['POST'])
@require_auth
def apply_leave():
    try:
        data = request.json or {}
        conn = _db()
        conn.execute("INSERT INTO leave_requests (emp_id,leave_type,from_date,to_date,days,reason,status,applied_at) VALUES (?,?,?,?,?,?,'pending',?)",
                     (data.get('emp_id'), data.get('leave_type'), data.get('from_date'), data.get('to_date'), data.get('days', 1), data.get('reason', ''), str(datetime.datetime.now())))
        conn.commit()
        conn.close()
        return jsonify({"success": True}), 201
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/leaves/<int:leave_id>/approve', methods=['POST'])
@require_auth
def approve_leave(leave_id):
    try:
        conn = _db()
        conn.execute("UPDATE leave_requests SET status='approved' WHERE id=?", (leave_id,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/leaves/<int:leave_id>/reject', methods=['POST'])
@require_auth
def reject_leave(leave_id):
    try:
        conn = _db()
        conn.execute("UPDATE leave_requests SET status='rejected' WHERE id=?", (leave_id,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500

# Holidays


@app.route('/api/holidays', methods=['GET'])
@require_auth
def get_holidays():
    try:
        year = request.args.get('year', '')
        conn = _db()
        if year:
            rows = conn.execute("SELECT * FROM holidays WHERE date LIKE ? ORDER BY date", (f"{year}%",)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM holidays ORDER BY date").fetchall()
        conn.close()
        return jsonify({"success": True, "holidays": [dict(r) for r in rows]})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/holidays', methods=['POST'])
@require_auth
def add_holiday():
    try:
        data = request.json or {}
        conn = _db()
        conn.execute("INSERT INTO holidays (date,name,type,emoji,desc) VALUES (?,?,?,?,?)",
                     (data.get('date'), data.get('name'), data.get('type', 'National'), data.get('emoji', '🎉'), data.get('desc', '')))
        conn.commit(); conn.close()
        return jsonify({"success": True}), 201
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/holidays/<int:hid>', methods=['PUT'])
@require_auth
def update_holiday(hid):
    try:
        data = request.json or {}
        conn = _db()
        conn.execute("UPDATE holidays SET date=?,name=?,type=?,emoji=?,desc=? WHERE id=?",
                     (data.get('date'), data.get('name'), data.get('type', 'National'), data.get('emoji', ''), data.get('desc', ''), hid))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/holidays/<int:hid>', methods=['DELETE'])
@require_auth
def delete_holiday(hid):
    try:
        conn = _db()
        conn.execute("DELETE FROM holidays WHERE id=?", (hid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500

# Guests


@app.route('/api/guests', methods=['GET'])
@require_auth
def get_guests():
    try:
        conn = _db()
        rows = conn.execute("SELECT * FROM guests ORDER BY id DESC").fetchall()
        conn.close()
        result = []
        for r in rows:
            g = dict(r)
            # Strip MIIM@ prefix from guest_id if present (legacy data cleanup)
            if g.get('guest_id', '').upper().startswith('MIIM@'):
                clean_id = g['guest_id'][5:]
                try:
                    c2 = _db()
                    c2.execute("UPDATE guests SET guest_id=? WHERE id=?", (clean_id, g['id']))
                    c2.commit(); c2.close()
                except: pass
                g['guest_id'] = clean_id
            # Ensure new fields have defaults
            g.setdefault('access_from', '')
            g.setdefault('access_to', '')
            g.setdefault('perm_enabled', 1)
            result.append(g)
        return jsonify(result)
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/guests', methods=['POST'])
@require_auth
def add_guest():
    try:
        data = request.json or {}
        conn = _db()
        cur = conn.execute("INSERT INTO guests (name,email,project,access_date,guest_id,password,sent_opt) VALUES (?,?,?,?,?,?,0)",
                           (data.get('name'), data.get('email'), data.get('project'), data.get('access_date'), data.get('guest_id', ''), data.get('password', '')))
        new_id = cur.lastrowid
        conn.commit(); conn.close()
        return jsonify({"success": True, "guest": {"id": new_id}}), 201
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/guests/<int:gid>', methods=['DELETE'])
@require_auth
def delete_guest(gid):
    try:
        conn = _db()
        conn.execute("DELETE FROM guests WHERE id=?", (gid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/guests/<int:gid>/set-access', methods=['POST', 'PATCH'])
@require_auth
def set_guest_access(gid):
    """Set time window and/or on/off toggle for permanent password."""
    try:
        data = request.json or {}
        conn = _db()
        if 'perm_enabled' in data:
            conn.execute("UPDATE guests SET perm_enabled=? WHERE id=?",
                         (1 if data['perm_enabled'] else 0, gid))
        if 'access_from' in data or 'access_to' in data:
            conn.execute("UPDATE guests SET access_from=?, access_to=? WHERE id=?",
                         (data.get('access_from', ''), data.get('access_to', ''), gid))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/guests/<int:gid>/sent', methods=['POST', 'PATCH'])
@require_auth
def mark_guest_sent(gid):
    try:
        data = request.json or {}
        conn = _db()
        sent_opt = data.get('sent_opt', 1)
        if sent_opt == 1:
            # Temporary: update the main password column so login check matches
            conn.execute(
                "UPDATE guests SET sent_opt=?, password=?, new_guest_id='', new_password='', login_used=0 WHERE id=?",
                (sent_opt, data.get('new_password', ''), gid)
            )
        else:
            conn.execute(
                "UPDATE guests SET sent_opt=?, new_guest_id=?, new_password=? WHERE id=?",
                (sent_opt, data.get('new_guest_id', ''), data.get('new_password', ''), gid)
            )
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


# Tracker


@app.route('/api/tracker/<path:key>', methods=['GET'])
@require_auth
def get_tracker(key):
    try:
        conn = _db()
        row = conn.execute("SELECT * FROM tracker_data WHERE key=?", (key,)).fetchone()
        conn.close()
        if not row: return jsonify({"key": key, "value": None})
        return jsonify(dict(row))
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/tracker/<path:key>', methods=['POST'])
@require_auth
def set_tracker(key):
    try:
        data = request.json or {}
        value = data.get('value', '')
        conn = _db()
        conn.execute("INSERT INTO tracker_data (key,value,updated_at) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=?,updated_at=?",
                     (key, value, str(datetime.datetime.now()), value, str(datetime.datetime.now())))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/tracker/bulk-get', methods=['POST'])
@require_auth
def bulk_get_tracker():
    """Fetch multiple tracker_data keys. prefix='' fetches ALL rows."""
    try:
        body = request.json or {}
        prefix = body.get('prefix', None)
        keys = body.get('keys', [])
        conn = _db()
        result = {}
        if prefix is not None:
            if prefix == '':
                rows = conn.execute("SELECT key, value FROM tracker_data").fetchall()
            else:
                rows = conn.execute(
                    "SELECT key, value FROM tracker_data WHERE key=? OR key LIKE ?",
                    (prefix, prefix + '_%')
                ).fetchall()
            for r in rows:
                result[r['key']] = r['value']
        for k in keys:
            if k not in result:
                row = conn.execute("SELECT value FROM tracker_data WHERE key=?", (k,)).fetchone()
                if row:
                    result[k] = row['value']
        conn.close()
        return jsonify({"success": True, "data": result})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/tracker/bulk', methods=['POST'])
@require_auth
def bulk_set_tracker():
    """Save multiple key-value pairs. Accepts {pairs:{}} or {data:{}}."""
    try:
        body = request.json or {}
        items = body.get('pairs', body.get('data', {}))
        conn = _db()
        now = str(datetime.datetime.now())
        for k, v in items.items():
            conn.execute(
                "INSERT INTO tracker_data (key,value,updated_at) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=?,updated_at=?",
                (k, v, now, v, now)
            )
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

# Leave balance


@app.route('/api/leave-balance', methods=['GET'])
@require_auth
def get_leave_balance():
    try:
        conn = _db()
        emp_id = request.args.get('emp_id')
        year = request.args.get('year', str(datetime.date.today().year))
        row = conn.execute("SELECT * FROM leave_balances WHERE emp_id=? AND year=?", (emp_id, year)).fetchone()
        conn.close()
        if not row: return jsonify({"annual": 18, "sick": 10, "casual": 6, "earned": 0, "used_annual": 0, "used_sick": 0, "used_casual": 0})
        return jsonify(dict(row))
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500

# Notifications


@app.route('/api/notifications', methods=['GET'])
@require_auth
def get_notifications():
    try:
        conn = _db()
        emp_id = request.args.get('emp_id')
        rows = conn.execute("SELECT * FROM notifications WHERE emp_id=? OR emp_id IS NULL ORDER BY id DESC LIMIT 20", (emp_id,)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500

# Upload photo


@app.route('/api/upload-photo/<int:emp_id>', methods=['POST'])
@require_auth
def upload_photo(emp_id):
    try:
        from flask import request as req
        file = req.files.get('photo')
        if not file: return jsonify({"success": False, "error": "No file"})
        import base64
        data = base64.b64encode(file.read()).decode()
        mime = file.content_type or 'image/jpeg'
        photo_url = f"data:{mime};base64,{data}"
        conn = _db()
        conn.execute("UPDATE employees SET photo_url=? WHERE id=?", (photo_url, emp_id))
        conn.commit(); conn.close()
        return jsonify({"success": True, "photo_url": photo_url})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

# Profile update


@app.route('/api/profile/update', methods=['POST'])
@require_auth
def profile_update():
    try:
        data = request.json or {}
        emp_id = data.get('id') or data.get('emp_id')
        if not emp_id: return jsonify({"success": False, "error": "No emp_id"})
        allowed = ['mobile', 'dob', 'father_name', 'address']
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields: return jsonify({"success": True})
        conn = _db()
        set_clause = ', '.join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE employees SET {set_clause} WHERE id=?", list(fields.values()) + [emp_id])
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

# Set password


@app.route('/api/set-password', methods=['POST'])
@require_auth
def set_password():
    try:
        data = request.json or {}
        username = safe_str(data.get('username', ''))
        new_pw = data.get('new_password') or data.get('password', '')
        force_reset = data.get('force_reset', False)
        current_pw = data.get('current_password', '')

        if not username or not new_pw:
            return jsonify({"success": False, "error": "Username and new password required"}), 400
        if len(new_pw) < 6:
            return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400

        conn = _db()
        row = conn.execute(
            "SELECT id, password_hash FROM employees WHERE username=?", (username,)
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "error": "User not found"}), 404

        # Verify current password if not a forced reset
        if not force_reset and current_pw:
            if not verify_password(current_pw, row["password_hash"]):
                conn.close()
                return jsonify({"success": False, "error": "Current password is incorrect"}), 400

        # Hash new password before storing
        hashed_new_pw = hash_password(new_pw)
        conn.execute(
            "UPDATE employees SET password_hash=?, force_reset=0 WHERE username=?",
            (hashed_new_pw, username)
        )
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[set-password error] {ex}")
        return jsonify({"success": False, "error": "Failed to update password"})

# Salary


@app.route('/api/salary', methods=['GET'])
@require_auth
def get_salary():
    try:
        conn = _db()
        rows = conn.execute("SELECT * FROM salary_structures").fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


# Login


@app.route('/api/login', methods=['POST'])
@limiter.limit('10 per 15 minutes')
def login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"success": False, "message": "Username and password are required"}), 400
    try:
        conn = _db()
        # Step 1: Try login by user_id only (all users)
        emp = conn.execute(
            "SELECT * FROM employees WHERE user_id=? AND status='active'",
            (username,)
        ).fetchone()
        # Step 2: If not found, try by username — but ONLY if the matched employee is admin
        if not emp:
            emp_by_name = conn.execute(
                "SELECT * FROM employees WHERE username=? AND status='active'",
                (username,)
            ).fetchone()
            if emp_by_name:
                _chk_d = (emp_by_name["desig"] or "").lower()
                _chk_dept = (emp_by_name["dept"] or "").lower()
                _chk_type = (emp_by_name["type"] or "").lower() if "type" in emp_by_name.keys() else ""
                _chk_name = (emp_by_name["username"] or "").lower()
                _is_admin = ("admin" in _chk_d or _chk_dept == "admin" or _chk_type == "admin" or _chk_name == "admin")
                if _is_admin:
                    emp = emp_by_name  # allow admin to login with username
                # Non-admin trying to login with username → reject (emp stays None)
        if emp:
            # ── Verify password with bcrypt (or legacy plain) ──
            if not verify_password(password, emp["password_hash"] or ""):
                conn.close()
                return jsonify({"success": False, "message": "Invalid username or password"}), 401
            # ── Auto-upgrade legacy plain passwords to bcrypt ──
            if needs_bcrypt_upgrade(emp["password_hash"] or ""):
                conn.execute(
                    "UPDATE employees SET password_hash=? WHERE id=?",
                    (hash_password(password), emp["id"])
                )
                conn.commit()
                print(f"[Security] Password upgraded to bcrypt for: {emp['username']}")
            _d = (emp["desig"] or "").lower()
            _dept = (emp["dept"] or "").lower()
            _type = (emp["type"] or "").lower() if "type" in emp.keys() else ""
            _uname = (emp["username"] or "").lower()
            if "admin" in _d or _dept == "admin" or _type == "admin" or _uname == "admin": _role = "admin"
            elif "hr" in _d or _dept == "hr": _role = "hr"
            elif ("account manager" in _d or _dept in ("account", "accounts", "finance")): _role = "account_manager"
            elif ("senior" in _d and "manager" in _d) or "senior-manager" in _d: _role = "sm"
            elif ("project" in _d and "manager" in _d) or "project-manager" in _d: _role = "pm"
            else: _role = "member"
            # ── Issue JWT token ──
            token = create_token(
                user_id=emp["id"],
                username=emp["username"],
                role=_role,
                emp_id=emp["empid"] or ""
            )
            from flask import make_response as _mkr
            _resp_data = {
                "success": True,
                "token": token,
                "role": _role,
                "dept": emp["dept"],
                "user": {
                    "id": emp["id"],
                    "username": emp["username"],
                    "name": emp["username"],
                    "user_id": emp["user_id"],
                    "empid": emp["empid"],
                    "role": _role,
                    "dept": emp["dept"],
                    "desig": emp["desig"],
                    "manager": emp["manager"],
                    "joindate": emp["joindate"],
                    "type": emp["type"],
                    "company_email": emp["company_email"],
                    "mobile": emp["mobile"] or "",
                    "dob": emp["dob"] or "",
                    "father_name": emp["father_name"] or "",
                    "photo_url": emp["photo_url"] or "",
                    "force_reset": emp["force_reset"],
                    "status": emp["status"],
                }
            }
            _resp = _mkr(jsonify(_resp_data))
            _resp.set_cookie('miim_token', token, httponly=True, samesite='Lax', max_age=86400 * 7, path='/')
            return _resp
        # ── Guest login check ──
        conn2 = _db()
        # Support both plain name and legacy MIIM@ prefixed guest_id
        username_alt = 'MIIM@' + username if not username.upper().startswith('MIIM@') else username[5:]
        guest = conn2.execute(
            "SELECT * FROM guests WHERE (guest_id IN (?,?) OR new_guest_id IN (?,?)) AND (password=? OR new_password=?)",
            (username, username_alt, username, username_alt, password, password)
        ).fetchone()

        if guest:
            g = dict(guest)
            # Normalise guest_id in DB (strip MIIM@ prefix if present)
            if g.get('guest_id', '').upper().startswith('MIIM@'):
                clean_id = g['guest_id'][5:]
                conn2.execute("UPDATE guests SET guest_id=? WHERE id=?", (clean_id, g['id']))
                conn2.commit()
                g['guest_id'] = clean_id
            # Determine which credential set matched

            # One-time block: if sent_opt=1 (temporary) and already used, deny
            if g.get('sent_opt') == 1 and g.get('login_used', 0) == 1:
                conn2.close()
                return jsonify({"success": False, "message": "\u26a0 This temporary access has already been used. It is a one-time login only."}), 401

            # Permanent password checks (sent_opt=2)
            if g.get('sent_opt') == 2:
                # On/Off toggle check
                if g.get('perm_enabled', 1) == 0:
                    conn2.close()
                    return jsonify({"success": False, "message": "\u26d4 Your access has been disabled by the administrator. Please contact HR."}), 401
                # Time window check — set time = BLOCKED period (IST)
                import datetime as _dt
                from zoneinfo import ZoneInfo as _ZI; _IST = _ZI('Asia/Kolkata')
                af = (g.get('access_from') or '').strip()
                at = (g.get('access_to') or '').strip()
                if af and at:
                    try:
                        now_time = _dt.datetime.now(_IST).time()
                        from_t = _dt.datetime.strptime(af, '%H:%M').time()
                        to_t = _dt.datetime.strptime(at, '%H:%M').time()
                        if from_t <= to_t:
                            is_blocked = from_t <= now_time <= to_t
                        else:  # overnight e.g. 23:00 - 01:00
                            is_blocked = now_time >= from_t or now_time <= to_t
                        if is_blocked:
                            conn2.close()
                            return jsonify({"success": False, "message": "\u274c Server Error. Please try again later."}), 500
                    except Exception:
                        pass

            # ── Project deadline / completion check ──
            # If the guest's project is completed OR its deadline has passed, deny access.
            try:
                import json as _json_gl, datetime as _dt_gl
                guest_project = (g.get('project') or '').strip()
                if guest_project:
                    _proj_row = conn2.execute(
                        "SELECT value FROM tracker_data WHERE key='miim_projects'"
                    ).fetchone()
                    if _proj_row:
                        _projects = _json_gl.loads(_proj_row['value'] or '[]')
                        for _p in _projects:
                            # Match by project name (case-insensitive)
                            if (_p.get('name') or '').strip().lower() == guest_project.lower():
                                # Block if project is completed
                                _pstatus = (_p.get('status') or '').strip().lower()
                                if _pstatus in ('completed', 'complete', 'done', 'closed', 'finished'):
                                    conn2.close()
                                    return jsonify({
                                        "success": False,
                                        "message": "🔒 Access Denied: The project '{}' has been completed. Your guest access is no longer valid.".format(guest_project)
                                    }), 401
                                # Block if deadline has passed
                                _deadline = (_p.get('deadline') or '').strip()
                                if _deadline:
                                    try:
                                        _dl_date = _dt_gl.date.fromisoformat(_deadline)
                                        _today = _dt_gl.date.today()
                                        if _today > _dl_date:
                                            conn2.close()
                                            return jsonify({
                                                "success": False,
                                                "message": "⏰ Access Expired: The deadline for project '{}' was {}. Your guest access has expired.".format(guest_project, _deadline)
                                            }), 401
                                    except Exception:
                                        pass
                                break
            except Exception:
                pass  # If check fails, do not block login (fail-open for safety)

            # Mark as used if temporary
            if g.get('sent_opt') == 1:
                conn2.execute("UPDATE guests SET login_used=1 WHERE id=?", (g['id'],))
                conn2.commit()

            conn2.close()
            return jsonify({
                "success": True,
                "role": "guest",
                "dept": "Guest",
                "user": {
                    "id": g['id'],
                    "username": username,
                    "name": g.get('name', username),
                    "user_id": username,
                    "empid": username,
                    "role": "guest",
                    "dept": "Guest",
                    "desig": "Guest",
                    "project": g.get('project', ''),
                    "is_guest": True,
                    "one_time": (g.get('sent_opt') == 1),
                    "force_reset": 0,
                    "status": "active",
                }
            })
        conn2.close()
        return jsonify({"success": False, "message": "Invalid username or password"}), 401
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/account-check/<path:username>")
@require_auth
def accheck(username):
    try:
        conn = _db()
        # Accept login by user_id OR username
        emp = conn.execute("SELECT id, salary_status FROM employees WHERE user_id=? OR username=?", (username, username)).fetchone()
        emp_id_val = emp['id'] if emp else None
        emp_salary_status = (emp['salary_status'] or '') if emp else ''
        has_account = False
        account_approved = False
        if emp_id_val:
            r = conn.execute("SELECT COUNT(*) c FROM accounts WHERE emp_id=?", (emp_id_val,)).fetchone()
            has_account = r["c"] > 0
            # Try with approval_status column first, fall back to status only
            try:
                ra = conn.execute(
                    "SELECT COUNT(*) c FROM accounts WHERE emp_id=? AND (LOWER(COALESCE(approval_status,'')) LIKE '%approved%' OR LOWER(COALESCE(status,''))='approved' OR LOWER(COALESCE(status,''))='completed')",
                    (emp_id_val,)
                ).fetchone()
            except Exception:
                # approval_status column may not exist — use status only
                ra = conn.execute(
                    "SELECT COUNT(*) c FROM accounts WHERE emp_id=? AND LOWER(COALESCE(status,''))='approved'",
                    (emp_id_val,)
                ).fetchone()
            account_approved = ra["c"] > 0
        try:
            s = conn.execute("SELECT COUNT(*) c FROM salary_structures ss JOIN employees e ON e.id=ss.emp_id WHERE e.user_id=? OR e.username=?", (username, username)).fetchone()
            has_salary = s["c"] > 0
        except Exception:
            has_salary = False
        conn.close()
        return jsonify({"success": True, "has_account": has_account, "account_approved": account_approved, "has_salary": has_salary, "salary_status": emp_salary_status})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/accounts/employee/<int:emp_id>', methods=['GET'])
@require_auth
def api_accounts_by_employee(emp_id):
    try:
        conn = _db()
        rows = conn.execute("SELECT * FROM accounts WHERE emp_id=? ORDER BY id DESC", (emp_id,)).fetchall()
        conn.close()
        result = [dict(r) for r in rows]
        return jsonify({"success": True, "accounts": result, "data": result})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/salary-structures', methods=['GET', 'POST'])
@require_auth
def api_salary_structures():
    try:
        conn = _db()
        # Ensure table exists
        conn.execute("""CREATE TABLE IF NOT EXISTS salary_structures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id INTEGER, period TEXT, department TEXT, designation TEXT,
            employee_type TEXT, basic REAL DEFAULT 0, hra REAL DEFAULT 0,
            dearness_allowance REAL DEFAULT 0, medical_allowance REAL DEFAULT 0,
            lta REAL DEFAULT 0, special_allowance REAL DEFAULT 0,
            city_compensatory_allowance REAL DEFAULT 0,
            professional_tax REAL DEFAULT 0, tds REAL DEFAULT 0,
            existing_advance REAL DEFAULT 0, other_deductions REAL DEFAULT 0,
            total_earnings REAL DEFAULT 0, total_deductions REAL DEFAULT 0,
            net_pay REAL DEFAULT 0, days_worked INTEGER DEFAULT 0,
            mode_of_payment TEXT DEFAULT 'Account', pay_date TEXT,
            notes TEXT, approval_status TEXT, correction_note TEXT,
            salary_ctc REAL DEFAULT 0, father_name TEXT,
            acct_approved_by TEXT, acct_approved_at TEXT, acct_approval_count INTEGER DEFAULT 0,
            mgmt_approved_by TEXT, mgmt_approved_at TEXT, mgmt_approval_count INTEGER DEFAULT 0
        )""")
        # Add approval columns to existing tables (migration)
        for col, definition in [
            ('acct_approved_by', 'TEXT'),
            ('acct_approved_at', 'TEXT'),
            ('acct_approval_count', 'INTEGER DEFAULT 0'),
            ('mgmt_approved_by', 'TEXT'),
            ('mgmt_approved_at', 'TEXT'),
            ('mgmt_approval_count', 'INTEGER DEFAULT 0'),
        ]:
            try:
                conn.execute(f"ALTER TABLE salary_structures ADD COLUMN {col} {definition}")
            except Exception:
                pass
        conn.commit()
        if request.method == 'GET':
            emp_id = request.args.get('emp_id')
            if emp_id:
                rows = conn.execute("SELECT * FROM salary_structures WHERE emp_id=? ORDER BY id DESC", (emp_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM salary_structures ORDER BY id DESC").fetchall()
            conn.close()
            result = [dict(r) for r in rows]
            return jsonify({"success": True, "data": result, "salary_structures": result})
        data = request.json or {}
        emp_id = data.get('emp_id')
        # Get valid columns from DB schema
        col_rows = conn.execute("PRAGMA table_info(salary_structures)").fetchall()
        valid_cols = {r['name'] for r in col_rows}
        # Filter payload to only valid columns (exclude approval tracking — managed by /approve endpoint)
        approval_cols = {'acct_approved_by', 'acct_approved_at', 'acct_approval_count', 'mgmt_approved_by', 'mgmt_approved_at', 'mgmt_approval_count'}
        clean_data = {k: v for k, v in data.items() if k in valid_cols and k not in approval_cols}
        # Auto-set required fields if missing
        if 'period' not in clean_data or not clean_data.get('period'):
            from datetime import date
            clean_data['period'] = date.today().strftime('%Y-%m-01')
        if 'emp_id' not in clean_data and emp_id:
            clean_data['emp_id'] = emp_id
        period = clean_data.get('period')
        # Match by emp_id + period so each month gets its own independent row
        existing = conn.execute(
            "SELECT id FROM salary_structures WHERE emp_id=? AND period=?", (emp_id, period)
        ).fetchone()
        if existing:
            # Update existing row for this period (preserve approval data)
            fields = [k for k in clean_data.keys() if k not in ('emp_id', 'id')]
            if fields:
                set_clause = ', '.join(f"{k}=?" for k in fields)
                values = [clean_data[k] for k in fields] + [existing['id']]
                conn.execute(f"UPDATE salary_structures SET {set_clause} WHERE id=?", values)
            conn.commit()
            conn.close()
            return jsonify({"success": True, "id": existing['id']})
        cols = ', '.join(clean_data.keys())
        placeholders = ', '.join('?' for _ in clean_data)
        conn.execute(f"INSERT INTO salary_structures ({cols}) VALUES ({placeholders})", list(clean_data.values()))
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return jsonify({"success": True, "id": new_id}), 201
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/salary-structures/export-excel', methods=['GET'])
@require_auth
def export_salary_structures_excel():
    """Export monthly salary structures to Excel on demand.
    One sheet per department. Saves to miim_storage folder."""
    import io, os, datetime as _dt
    import openpyxl  # type: ignore[import]
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side  # type: ignore[import]
    from openpyxl.utils import get_column_letter  # type: ignore[import]

    try:
        conn = _db()

        # Get requested period from query param (default: current month)
        period_param = request.args.get('period', '')
        if period_param:
            # Accept YYYY-MM or YYYY-MM-DD
            period_filter = period_param[:7]  # YYYY-MM
        else:
            period_filter = _dt.date.today().strftime('%Y-%m')

        # Fetch salary structures joined with employees for the period
        rows = conn.execute("""
            SELECT
                e.username,
                e.empid         AS employee_id,
                e.dept,
                e.desig         AS designation,
                e.type          AS emp_type,
                e.joindate      AS date_of_joining,
                e.father_name,
                ss.id           AS ss_id,
                ss.period,
                ss.basic,
                ss.hra,
                ss.dearness_allowance,
                ss.medical_allowance,
                ss.lta,
                ss.special_allowance,
                ss.city_compensatory_allowance,
                ss.professional_tax,
                ss.tds,
                ss.existing_advance,
                ss.other_deductions,
                ss.total_earnings,
                ss.total_deductions,
                ss.net_pay,
                ss.days_worked,
                ss.mode_of_payment,
                ss.pay_date,
                ss.salary_ctc,
                ss.approval_status,
                ss.acct_approved_by,
                ss.mgmt_approved_by
            FROM employees e
            LEFT JOIN salary_structures ss
                ON ss.emp_id = e.id
                AND substr(ss.period, 1, 7) = ?
            WHERE e.status = 'active'
            ORDER BY e.dept, e.username
        """, (period_filter,)).fetchall()
        conn.close()

        from collections import OrderedDict
        dept_map = OrderedDict()
        for r in rows:
            d = dict(r)
            dn = (d.get('dept') or 'Unassigned').strip()
            dept_map.setdefault(dn, []).append(d)

        # ── Styles ──
        HDR_BG = "F97316"
        HDR_FG = "FFFFFF"
        ROW_A = "1E1E2E"
        ROW_B = "16162A"
        GRN = "22C55E"
        YLW = "EAB308"
        RED = "EF4444"
        GRY = "999999"
        TXT = "E5E5E5"
        TITLE_BG = "1A1A2A"
        EARN_CLR = "4ADE80"
        DED_CLR = "F87171"
        NET_CLR = "FB923C"

        thin = Side(style='thin', color="333333")
        brd = Border(left=thin, right=thin, top=thin, bottom=thin)

        # Columns matching the salary structure modal exactly
        COLUMNS = [
            ("S.No", 5),
            ("Name", 18),
            ("Emp ID", 13),
            ("Designation", 22),
            ("Emp Type", 13),
            ("Date of Joining", 16),
            ("Father's Name", 18),
            ("Period", 12),
            ("Days Worked", 12),
            ("Mode of Payment", 17),
            ("Pay Date", 13),
            ("Salary CTC", 14),
            # Earnings
            ("Basic", 12),
            ("HRA", 10),
            ("DA", 10),
            ("Medical Allow.", 14),
            ("LTA", 10),
            ("Special Allow.", 14),
            ("City Comp. Allow.", 16),
            ("Total Earnings", 14),
            # Deductions
            ("Prof. Tax", 11),
            ("TDS", 10),
            ("Advance", 11),
            ("Other Ded.", 11),
            ("Total Deductions", 15),
            # Net
            ("Net Pay", 13),
            # Approval
            ("Approval Status", 16),
            ("Acct Approved By", 16),
            ("Mgmt Approved By", 16),
        ]
        NC = len(COLUMNS)

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # type: ignore[union-attr]
        tab_colours = ["F97316", "22C55E", "3B82F6", "A855F7", "EAB308", "EF4444", "06B6D4", "F43F5E"]

        # Format period for display: YYYY-MM → Month YYYY
        try:
            period_display = _dt.datetime.strptime(period_filter + '-01', '%Y-%m-%d').strftime('%B %Y')
        except Exception:
            period_display = period_filter

        for di, (dn, emps) in enumerate(dept_map.items()):
            sn = dn[:31]
            for ch in ['/', chr(92), '*', '?', '[', ']', ':']:
                sn = sn.replace(ch, '-')
            ws = wb.create_sheet(title=sn or 'Sheet')

            # Row 1 — Title
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=NC)
            t = ws.cell(row=1, column=1)
            t.value = ("MIIM HR -- " + dn.upper()
                       + " DEPARTMENT -- SALARY STRUCTURE -- " + period_display.upper())
            t.font = Font(bold=True, size=13, color=HDR_BG, name="Calibri")
            t.fill = PatternFill("solid", fgColor=TITLE_BG)
            t.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[1].height = 26

            # Row 2 — Timestamp
            ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=NC)
            g = ws.cell(row=2, column=1)
            g.value = ("Generated: " + _dt.datetime.now().strftime('%d %B %Y, %I:%M %p')
                       + "   |   Period: " + period_display
                       + "   |   Employees: " + str(len(emps)))
            g.font = Font(italic=True, size=9, color=GRY, name="Calibri")
            g.fill = PatternFill("solid", fgColor=TITLE_BG)
            g.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[2].height = 15

            # Row 3 — Section labels (Earnings / Deductions / Net)
            ws.merge_cells(start_row=3, start_column=13, end_row=3, end_column=20)
            earn_lbl = ws.cell(row=3, column=13)
            earn_lbl.value = "EARNINGS"
            earn_lbl.font = Font(bold=True, size=9, color=EARN_CLR, name="Calibri")
            earn_lbl.fill = PatternFill("solid", fgColor="0A1F0A")
            earn_lbl.alignment = Alignment(horizontal="center", vertical="center")

            ws.merge_cells(start_row=3, start_column=21, end_row=3, end_column=25)
            ded_lbl = ws.cell(row=3, column=21)
            ded_lbl.value = "DEDUCTIONS"
            ded_lbl.font = Font(bold=True, size=9, color=DED_CLR, name="Calibri")
            ded_lbl.fill = PatternFill("solid", fgColor="1F0A0A")
            ded_lbl.alignment = Alignment(horizontal="center", vertical="center")

            ws.merge_cells(start_row=3, start_column=26, end_row=3, end_column=26)
            net_lbl = ws.cell(row=3, column=26)
            net_lbl.value = "NET"
            net_lbl.font = Font(bold=True, size=9, color=NET_CLR, name="Calibri")
            net_lbl.fill = PatternFill("solid", fgColor="1F0F00")
            net_lbl.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[3].height = 14

            # Row 4 — Column headers
            for ci, (cn, cw) in enumerate(COLUMNS, start=1):
                c = ws.cell(row=4, column=ci)
                c.value = cn.upper()
                c.font = Font(bold=True, size=9, color=HDR_FG, name="Calibri")
                # Colour header by section
                if 13 <= ci <= 20:
                    c.fill = PatternFill("solid", fgColor="0D3B0D")
                elif 21 <= ci <= 25:
                    c.fill = PatternFill("solid", fgColor="3B0D0D")
                elif ci == 26:
                    c.fill = PatternFill("solid", fgColor="3B1F00")
                else:
                    c.fill = PatternFill("solid", fgColor=HDR_BG)
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                c.border = brd
                ws.column_dimensions[get_column_letter(ci)].width = cw
            ws.row_dimensions[4].height = 24

            # Data rows start at row 5
            for ri, emp in enumerate(emps, start=1):
                rn = ri + 4
                has_ss = bool(emp.get('ss_id'))

                def n(key):
                    val = emp.get(key)
                    if val is None or str(val).strip() in ('', '0', '0.0'):
                        return '-' if not has_ss else '0'
                    return str(val).strip()

                def amt(key):
                    if not has_ss:
                        return '-'
                    val = emp.get(key)
                    try:
                        return round(float(val), 2) if val and float(val) != 0 else 0
                    except Exception:
                        return 0

                apv_st = emp.get('approval_status') or ('Not Set' if not has_ss else 'Pending')

                vals = [
                    ri,
                    emp.get('username') or '-',
                    emp.get('employee_id') or '-',
                    emp.get('designation') or '-',
                    emp.get('emp_type') or '-',
                    emp.get('date_of_joining') or '-',
                    emp.get('father_name') or '-',
                    emp.get('period') or period_filter,
                    emp.get('days_worked') if has_ss else '-',
                    emp.get('mode_of_payment') or '-',
                    emp.get('pay_date') or '-',
                    amt('salary_ctc'),
                    # Earnings
                    amt('basic'), amt('hra'), amt('dearness_allowance'),
                    amt('medical_allowance'), amt('lta'), amt('special_allowance'),
                    amt('city_compensatory_allowance'), amt('total_earnings'),
                    # Deductions
                    amt('professional_tax'), amt('tds'), amt('existing_advance'),
                    amt('other_deductions'), amt('total_deductions'),
                    # Net
                    amt('net_pay'),
                    # Approval
                    apv_st,
                    emp.get('acct_approved_by') or '-',
                    emp.get('mgmt_approved_by') or '-',
                ]

                rfill = PatternFill("solid", fgColor=(ROW_A if ri % 2 == 1 else ROW_B))
                for ci, val in enumerate(vals, start=1):
                    c = ws.cell(row=rn, column=ci)
                    c.value = val if val is not None else '-'
                    c.fill = rfill
                    # Section-specific font colours for amounts
                    if 13 <= ci <= 20:
                        c.font = Font(size=10, color=EARN_CLR, name="Calibri")
                    elif 21 <= ci <= 25:
                        c.font = Font(size=10, color=DED_CLR, name="Calibri")
                    elif ci == 26:
                        c.font = Font(size=10, color=NET_CLR, bold=True, name="Calibri")
                    else:
                        c.font = Font(size=10, color=TXT, name="Calibri")
                    c.alignment = Alignment(vertical="center",
                                            horizontal="right" if isinstance(val, (int, float)) else "left")
                    c.border = brd
                ws.row_dimensions[rn].height = 18

                # Colour-code Approval Status (col 27)
                ac = ws.cell(row=rn, column=27)
                if apv_st == 'Fully Approved':
                    ac.font = Font(size=10, color=GRN, bold=True, name="Calibri")
                elif apv_st == 'Acct Approved':
                    ac.font = Font(size=10, color="3B82F6", bold=True, name="Calibri")
                elif apv_st in ('Pending', 'Not Set'):
                    ac.font = Font(size=10, color=YLW, name="Calibri")
                elif apv_st == 'Rejected':
                    ac.font = Font(size=10, color=RED, bold=True, name="Calibri")

            ws.freeze_panes = "A5"
            ws.auto_filter.ref = "A4:" + get_column_letter(NC) + "4"
            ws.sheet_properties.tabColor = tab_colours[di % len(tab_colours)]

        # ── Save to miim_storage ──
        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        period_slug = period_filter.replace('-', '_')
        filename = "MIIM_Salary_" + period_slug + "_" + timestamp + ".xlsx"
        save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miim_storage', 'salary_structure')
        saved_path = "Not saved"
        try:
            os.makedirs(save_dir, exist_ok=True)
            full_path = os.path.join(save_dir, filename)
            wb.save(full_path)
            saved_path = full_path
        except Exception as save_err:
            saved_path = "Save error: " + str(save_err)

        # ── Stream as browser download ──
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        from flask import make_response
        resp = make_response(buf.read())
        resp.headers['Content-Type'] = (
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resp.headers['Content-Disposition'] = 'attachment; filename="' + filename + '"'
        resp.headers['Cache-Control'] = 'no-cache'
        resp.headers['X-Saved-Path'] = saved_path
        return resp

    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/salary-structures/<int:ss_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
def api_salary_structure_detail(ss_id):  # type: ignore
    try:
        conn = _db()
        if request.method == 'GET':
            row = conn.execute("SELECT * FROM salary_structures WHERE id=?", (ss_id,)).fetchone()
            conn.close()
            return jsonify({"success": True, "data": dict(row)}) if row else (jsonify({"success": False, "error": "Not found"}), 404)
        if request.method == 'PUT':
            data = request.json or {}
            # Get actual column names from DB to avoid unknown column errors
            col_rows = conn.execute("PRAGMA table_info(salary_structures)").fetchall()
            valid_cols = {r['name'] for r in col_rows}
            # If table doesn't exist yet, valid_cols will be empty — create table first
            if not valid_cols:
                conn.execute("""CREATE TABLE IF NOT EXISTS salary_structures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    emp_id INTEGER, period TEXT, department TEXT, designation TEXT,
                    employee_type TEXT, basic REAL DEFAULT 0, hra REAL DEFAULT 0,
                    dearness_allowance REAL DEFAULT 0, medical_allowance REAL DEFAULT 0,
                    lta REAL DEFAULT 0, special_allowance REAL DEFAULT 0,
                    city_compensatory_allowance REAL DEFAULT 0,
                    professional_tax REAL DEFAULT 0, tds REAL DEFAULT 0,
                    existing_advance REAL DEFAULT 0, other_deductions REAL DEFAULT 0,
                    total_earnings REAL DEFAULT 0, total_deductions REAL DEFAULT 0,
                    net_pay REAL DEFAULT 0, days_worked INTEGER DEFAULT 0,
                    mode_of_payment TEXT DEFAULT 'Account', pay_date TEXT,
                    notes TEXT, approval_status TEXT, correction_note TEXT,
                    salary_ctc REAL DEFAULT 0, father_name TEXT,
                    acct_approved_by TEXT, acct_approved_at TEXT, acct_approval_count INTEGER DEFAULT 0,
                    mgmt_approved_by TEXT, mgmt_approved_at TEXT, mgmt_approval_count INTEGER DEFAULT 0
                )""")
                conn.commit()
                col_rows = conn.execute("PRAGMA table_info(salary_structures)").fetchall()
                valid_cols = {r['name'] for r in col_rows}
            fields = [k for k in data.keys() if k != 'id' and k in valid_cols]
            if fields:
                set_clause = ', '.join(f"{k}=?" for k in fields)
                values = [data[k] for k in fields] + [ss_id]
                conn.execute(f"UPDATE salary_structures SET {set_clause} WHERE id=?", values)
            conn.commit()
            conn.close()
            return jsonify({"success": True})
        if request.method == 'DELETE':
            conn.execute("DELETE FROM salary_structures WHERE id=?", (ss_id,))
            conn.commit()
            conn.close()
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Method not allowed"}), 405
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/archived-slips', methods=['GET', 'POST'])
@require_auth
def api_archived_slips():  # type: ignore
    import json as _json
    try:
        conn = _db()
        if request.method == 'GET':
            emp_id = request.args.get('emp_id', '')
            if emp_id:
                rows = conn.execute(
                    "SELECT slip_data FROM archived_slips WHERE emp_id=? ORDER BY archived_at DESC",
                    (str(emp_id),)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT slip_data FROM archived_slips ORDER BY archived_at DESC"
                ).fetchall()
            conn.close()
            result = []
            for r in rows:
                try:
                    result.append(_json.loads(r['slip_data']))
                except Exception:
                    pass
            return jsonify(result)
        if request.method == 'POST':
            data = request.json or {}
            archive_uid = data.get('_archive_uid', '')
            emp_id = str(data.get('emp_id', ''))
            period = (data.get('period', '') or '')[:7]
            archived_at = data.get('_archived_at', '')
            slip_json = _json.dumps(data)
            conn.execute("""
                INSERT INTO archived_slips (emp_id, archive_uid, period, archived_at, slip_data)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(archive_uid) DO UPDATE SET
                    slip_data=excluded.slip_data,
                    archived_at=excluded.archived_at
            """, (emp_id, archive_uid, period, archived_at, slip_json))
            conn.commit()
            conn.close()
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Method not allowed"}), 405
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/salary-structures/<int:ss_id>/approve', methods=['POST'])
@require_auth
def api_salary_structure_approve(ss_id):
    """
    Body: { "role": "acct" | "mgmt", "approved_by": "<username or name>" }
    - role="acct"  → sets approval_status="Acct Approved", increments acct_approval_count
    - role="mgmt"  → sets approval_status="Fully Approved", increments mgmt_approval_count
    Both record who approved and when.
    """
    try:
        import datetime as _dt
        conn = _db()
        row = conn.execute("SELECT * FROM salary_structures WHERE id=?", (ss_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "error": "Salary slip not found"}), 404
        row = dict(row)
        data = request.json or {}
        role = (data.get('role') or '').lower().strip()   # 'acct' or 'mgmt'
        approved_by = data.get('approved_by') or 'Admin'
        now = _dt.datetime.now().isoformat(timespec='seconds')
        if role == 'acct':
            new_count = (row.get('acct_approval_count') or 0) + 1
            # Clear correction_note and reset mgmt approval fields so management
            # must re-approve after any correction cycle
            conn.execute("""UPDATE salary_structures
                SET approval_status=?, acct_approved_by=?, acct_approved_at=?, acct_approval_count=?,
                    correction_note=NULL,
                    mgmt_approved_by=NULL, mgmt_approved_at=NULL
                WHERE id=?""",
                         ('Acct Approved', approved_by, now, new_count, ss_id))
        elif role == 'mgmt':
            new_count = (row.get('mgmt_approval_count') or 0) + 1
            conn.execute("""UPDATE salary_structures
                SET approval_status=?, mgmt_approved_by=?, mgmt_approved_at=?, mgmt_approval_count=?
                WHERE id=?""",
                         ('Fully Approved', approved_by, now, new_count, ss_id))
        else:
            conn.close()
            return jsonify({"success": False, "error": "Invalid role. Use 'acct' or 'mgmt'"}), 400
        conn.commit()
        updated = dict(conn.execute("SELECT * FROM salary_structures WHERE id=?", (ss_id,)).fetchone())
        conn.close()
        return jsonify({"success": True, "data": updated})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/salary-structures/<int:ss_id>/send-back', methods=['POST'])
@require_auth
def api_salary_structure_send_back(ss_id):
    """
    Management sends back a salary slip to Account Dept for correction.
    Body: { "correction_note": "...", "sent_by": "username" }
    Sets approval_status='Needs Correction' and saves the correction note.
    """
    try:
        conn = _db()
        row = conn.execute("SELECT * FROM salary_structures WHERE id=?", (ss_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "error": "Salary slip not found"}), 404
        data = request.json or {}
        note = (data.get('correction_note') or '').strip()
        conn.execute(
            "UPDATE salary_structures SET approval_status=?, correction_note=?, mgmt_approved_by=NULL, mgmt_approved_at=NULL WHERE id=?",
            ('Needs Correction', note, ss_id)
        )
        conn.commit()
        updated = dict(conn.execute("SELECT * FROM salary_structures WHERE id=?", (ss_id,)).fetchone())
        conn.close()
        return jsonify({"success": True, "data": updated})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/<int:emp_id>/generate-password', methods=['POST'])
@require_role('admin', 'hr')
def generate_password(emp_id):
    try:
        import string, secrets as _sec
        alphabet = string.ascii_letters + string.digits + '!@#$'
        new_pw = ''.join(_sec.choice(alphabet) for _ in range(12))
        hashed_pw = hash_password(new_pw)
        conn = _db()
        conn.execute("UPDATE employees SET password_hash=?, force_reset=1 WHERE id=?", (hashed_pw, emp_id))
        conn.commit()
        row = conn.execute("SELECT username, company_email FROM employees WHERE id=?", (emp_id,)).fetchone()
        conn.close()
        return jsonify({"success": True, "temp_password": new_pw, "username": row['username'] if row else '', "email": row['company_email'] if row else ''})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/<int:emp_id>/send-password', methods=['POST'])
@require_auth
def send_password_email(emp_id):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    try:
        data = request.json or {}
        sender_role = data.get('sender_role', 'Admin')

        conn = _db()
        # Get employee + their current temp password
        row = conn.execute(
            "SELECT username, company_email, password_hash FROM employees WHERE id=?",
            (emp_id,)
        ).fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False, "error": "Employee not found"}), 404

        username = row['username']
        email = row['company_email']
        password = row['password_hash']   # the temp password set by generate-password

        if not email or '@' not in email:
            return jsonify({"success": False, "error": "Employee has no valid email address"}), 400

        # ── HOSTINGER SMTP CONFIG (from environment via security.py) ──
        SMTP_HOST = 'smtp.hostinger.com'
        SMTP_PORT = 465
        SMTP_USER = _CHAT_SMTP_USER
        SMTP_PASS = _CHAT_SMTP_PASS

        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'MIIM — Your Login Password Has Been Reset'
        msg['From'] = f'MIIM HR System <{SMTP_USER}>'
        msg['To'] = email

        html_body = f"""
        <html>
        <body style="margin:0;padding:0;background:#0f0f0f;font-family:Arial,sans-serif;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f0f;padding:40px 0;">
            <tr><td align="center">
              <table width="520" cellpadding="0" cellspacing="0"
                     style="background:#1a1a1a;border-radius:14px;border:1px solid #2a2a2a;overflow:hidden;">

                <!-- Header -->
                <tr>
                  <td style="background:linear-gradient(135deg,#1a0a00,#2a1200);
                              padding:28px 32px;border-bottom:2px solid #f97316;">
                    <div style="font-family:'Arial Black',Arial,sans-serif;
                                font-size:22px;font-weight:900;
                                letter-spacing:3px;color:#f97316;
                                text-transform:uppercase;">MIIM</div>
                    <div style="font-size:12px;color:#888;letter-spacing:2px;margin-top:4px;">
                      Mission Impossible Industrial Management
                    </div>
                  </td>
                </tr>

                <!-- Body -->
                <tr>
                  <td style="padding:32px;">
                    <h2 style="color:#f97316;font-size:20px;margin:0 0 16px;">
                      🔑 Password Reset Notification
                    </h2>

                    <p style="color:#ccc;font-size:14px;line-height:1.7;margin:0 0 12px;">
                      Hi <strong style="color:#fff;">{username}</strong>,
                    </p>
                    <p style="color:#ccc;font-size:14px;line-height:1.7;margin:0 0 24px;">
                      Your login password has been reset by
                      <strong style="color:#f97316;">{sender_role}</strong>.
                      Use the temporary password below to login to the MIIM HR System.
                    </p>

                    <!-- Password Box -->
                    <div style="background:#111;border:2px solid #f97316;border-radius:10px;
                                padding:20px;text-align:center;margin:0 0 24px;">
                      <div style="font-size:11px;color:#888;letter-spacing:2px;
                                  text-transform:uppercase;margin-bottom:10px;">
                        Your Temporary Password
                      </div>
                      <div style="font-size:28px;font-weight:900;letter-spacing:4px;
                                  color:#4ade80;font-family:monospace;">
                        {password}
                      </div>
                    </div>

                    <!-- Credentials -->
                    <table width="100%" cellpadding="0" cellspacing="0"
                           style="background:#111;border-radius:8px;border:1px solid #2a2a2a;
                                  margin:0 0 24px;overflow:hidden;">
                      <tr>
                        <td style="padding:12px 16px;border-bottom:1px solid #1e1e1e;">
                          <span style="font-size:11px;color:#888;letter-spacing:1px;
                                       text-transform:uppercase;">Username</span><br/>
                          <span style="font-size:15px;font-weight:700;
                                       color:#a5b4fc;font-family:monospace;
                                       letter-spacing:1px;">{username}</span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:12px 16px;">
                          <span style="font-size:11px;color:#888;letter-spacing:1px;
                                       text-transform:uppercase;">Password</span><br/>
                          <span style="font-size:15px;font-weight:700;
                                       color:#4ade80;font-family:monospace;
                                       letter-spacing:2px;">{password}</span>
                        </td>
                      </tr>
                    </table>

                    <!-- Warning -->
                    <div style="background:#1a1000;border:1px solid #f97316;
                                border-radius:8px;padding:14px 16px;margin:0 0 24px;">
                      <p style="margin:0;font-size:13px;color:#fbbf24;line-height:1.6;">
                        ⚠️ <strong>Important:</strong> This is a temporary password.
                        Please login immediately and change your password from
                        <em>Settings → Security</em>.
                      </p>
                    </div>

                    <p style="color:#555;font-size:12px;line-height:1.6;margin:0;">
                      If you did not request this change, please contact your HR department immediately.
                    </p>
                  </td>
                </tr>

                <!-- Footer -->
                <tr>
                  <td style="background:#111;padding:16px 32px;border-top:1px solid #1e1e1e;
                              text-align:center;">
                    <p style="margin:0;font-size:11px;color:#555;letter-spacing:1px;">
                      © 2026 MIIM · Mission Impossible Industrial Management<br/>
                      NO.31, CHINNAN CHETTIYAR STREET, VELANDIPALAYAM, COIMBATORE – 641025
                    </p>
                  </td>
                </tr>

              </table>
            </td></tr>
          </table>
        </body>
        </html>
        """

        plain = f'Hi {username},\n\nPassword reset by {sender_role}.\nUsername: {username}\nTemporary Password: {password}\n\nLogin and change your password immediately.\n\nMIIM HR'
        msg.attach(MIMEText(plain, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        import ssl as _ssl
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=_ssl.create_default_context(), timeout=30) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [email], msg.as_string())

        return jsonify({
            "success": True,
            "message": f"Password email sent to {email}",
            "email": email
        })

    except smtplib.SMTPAuthenticationError:
        return jsonify({
            "success": False,
            "error": "SMTP Authentication failed. Check your Hostinger email and password."
        }), 500
    except smtplib.SMTPException as smtp_err:
        return jsonify({
            "success": False,
            "error": f"SMTP error: {str(smtp_err)}"
        }), 500
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/approve/<int:emp_id>', methods=['POST'])
@require_auth
def approve_employee(emp_id):
    try:
        conn = _db()
        # pending_employees-ல இருந்தா அதை employees-க்கு move பண்ணு
        pending = conn.execute("SELECT * FROM pending_employees WHERE id=?", (emp_id,)).fetchone()
        if pending:
            p = dict(pending)
            # Auto-generate user_id: name letters + DD + MM of joindate
            _uname = p.get('username', '')
            _ujd = p.get('joindate', '')
            # Keep username lowercase as-is, only strip whitespace — dot/underscore stays
            _letters = _uname.lower().replace(' ', '')
            if _ujd and len(_ujd) >= 10:
                _parts = _ujd.split('-')
                _dd = _parts[2][:2] if len(_parts) > 2 else '01'
                _mm = _parts[1][:2] if len(_parts) > 1 else '01'
                _gen_uid = _letters + _dd + _mm
            else:
                _gen_uid = _letters + '0101'
            conn.execute("""INSERT INTO employees
                (username, user_id, empid, dept, desig, manager, joindate, type,
                 company_email, mobile, dob, father_name, photo_url,
                 password_hash, force_reset, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (_uname, _gen_uid, p.get('empid', ''),
                          p.get('dept', ''), p.get('desig', ''), p.get('manager', ''),
                             _ujd, p.get('type', 'Regular'),
                             p.get('company_email', ''), p.get('mobile', ''), p.get('dob', ''),
                             p.get('father_name', ''), p.get('photo_url', ''),
                             hash_password(p.get('password_hash') or 'miim@123'), 0, 'active'))
            conn.execute("DELETE FROM pending_employees WHERE id=?", (emp_id,))
        else:
            # Already in employees table — just activate
            conn.execute("UPDATE employees SET status='active' WHERE id=?", (emp_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Employee approved successfully"})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/employees/reject/<int:emp_id>', methods=['POST'])
@require_auth
def reject_employee(emp_id):
    try:
        conn = _db()
        conn.execute("DELETE FROM pending_employees WHERE id=?", (emp_id,))
        conn.execute("UPDATE employees SET status='inactive' WHERE id=?", (emp_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/accounts', methods=['GET', 'POST'])
@require_auth
def api_accounts():
    try:
        conn = _db()
        if request.method == 'GET':
            emp_id = request.args.get('emp_id')
            if emp_id:
                rows = conn.execute("SELECT * FROM accounts WHERE emp_id=? ORDER BY id DESC", (emp_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM accounts ORDER BY id DESC").fetchall()
            conn.close()
            result = [dict(r) for r in rows]
            return jsonify({"success": True, "accounts": result, "data": result})
        data = request.json or {}
        emp_id = data.get('emp_id')
        existing = conn.execute("SELECT id FROM accounts WHERE emp_id=?", (emp_id,)).fetchone()
        if existing:
            conn.close()
            return jsonify({"success": False, "error": "Employee already has an account", "existing_id": existing["id"]}), 400
        conn.execute(
            "INSERT INTO accounts (emp_id,account_type,bank_name,account_number,ifsc_code,branch,upi_id,status,notes,mode_of_payment,pay_date,days_worked) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (emp_id, data.get('account_type', 'Salary'), data.get('bank_name', 'Bank'),
             data.get('account_number', ''), data.get('ifsc_code', ''),
             data.get('branch', ''), data.get('upi_id', ''),
             data.get('status', 'Approved'), data.get('notes', ''),
             data.get('mode_of_payment', ''), data.get('pay_date', ''),
             data.get('days_worked', 0))
        )
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return jsonify({"success": True, "account": {"id": new_id}}), 201
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/accounts/export-excel', methods=['GET'])
@require_auth
def export_accounts_excel():
    """Export account section to Excel. One sheet per department.
    Columns match exactly what is shown in the account modal."""
    import io, os, datetime as _dt
    import openpyxl  # type: ignore[import]
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side  # type: ignore[import]
    from openpyxl.utils import get_column_letter  # type: ignore[import]
    if not openpyxl:
        return jsonify({"success": False, "error": "openpyxl not installed. Run: pip install openpyxl"}), 500

    try:
        conn = _db()
        # Join employees + accounts to get all modal fields
        rows = conn.execute("""
            SELECT
                e.id            AS emp_id,
                e.empid         AS employee_id,
                e.dept          AS department,
                e.desig         AS designation,
                e.joindate      AS date_of_joining,
                e.dob           AS date_of_birth,
                e.father_name,
                e.username,
                e.user_id,
                e.type          AS emp_type,
                e.dept,
                a.account_number,
                a.ifsc_code,
                a.status        AS account_status,
                a.mode_of_payment,
                a.pay_date,
                a.days_worked
            FROM employees e
            LEFT JOIN accounts a ON a.emp_id = e.id
            WHERE e.status = 'active'
            ORDER BY e.dept, e.username
        """).fetchall()
        conn.close()

        # Group by department
        from collections import OrderedDict
        dept_map = OrderedDict()
        for r in rows:
            d = dict(r)
            dn = (d.get('dept') or 'Unassigned').strip()
            dept_map.setdefault(dn, []).append(d)

        # ── Styles ──
        HDR_BG = "F97316"   # orange
        HDR_FG = "FFFFFF"
        ROW_A = "1E1E2E"
        ROW_B = "16162A"
        GRN = "22C55E"
        YLW = "EAB308"
        RED = "EF4444"
        GRY = "999999"
        TXT = "E5E5E5"
        TITLE_BG = "1A1A2A"

        thin = Side(style='thin', color="333333")
        brd = Border(left=thin, right=thin, top=thin, bottom=thin)

        # Exact columns matching the modal fields
        COLUMNS = [
            ("S.No", 5),
            ("Name", 18),
            ("User ID", 14),
            ("Employee ID", 14),
            ("Department", 16),
            ("Designation", 22),
            ("Emp Type", 13),
            ("Date of Joining", 16),
            ("Date of Birth", 14),
            ("Father's Name", 20),
            ("Mode of Payment", 18),
            ("Pay Date", 14),
            ("Days Worked", 13),
            ("Account Number", 22),
            ("IFSC Code", 14),
            ("Account Status", 16),
        ]
        NC = len(COLUMNS)

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # type: ignore[union-attr]
        tab_colours = ["F97316", "22C55E", "3B82F6", "A855F7", "EAB308", "EF4444", "06B6D4", "F43F5E"]

        for di, (dn, emps) in enumerate(dept_map.items()):
            # Clean sheet name (Excel max 31 chars, no special chars)
            sn = dn[:31]
            for ch in ['/', chr(92), '*', '?', '[', ']', ':']:
                sn = sn.replace(ch, '-')
            ws = wb.create_sheet(title=sn or 'Sheet')

            # Row 1 — Department title
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=NC)
            t = ws.cell(row=1, column=1)
            t.value = "MIIM HR -- " + dn.upper() + " DEPARTMENT -- ACCOUNT DETAILS"
            t.font = Font(bold=True, size=13, color=HDR_BG, name="Calibri")
            t.fill = PatternFill("solid", fgColor=TITLE_BG)
            t.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[1].height = 26

            # Row 2 — Timestamp
            ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=NC)
            g = ws.cell(row=2, column=1)
            g.value = ("Generated: " + _dt.datetime.now().strftime('%d %B %Y, %I:%M %p')
                       + "   |   Employees: " + str(len(emps)))
            g.font = Font(italic=True, size=9, color=GRY, name="Calibri")
            g.fill = PatternFill("solid", fgColor=TITLE_BG)
            g.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[2].height = 15

            # Row 3 — Column headers
            for ci, (cn, cw) in enumerate(COLUMNS, start=1):
                c = ws.cell(row=3, column=ci)
                c.value = cn.upper()
                c.font = Font(bold=True, size=10, color=HDR_FG, name="Calibri")
                c.fill = PatternFill("solid", fgColor=HDR_BG)
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                c.border = brd
                ws.column_dimensions[get_column_letter(ci)].width = cw
            ws.row_dimensions[3].height = 22

            # Data rows starting at row 4
            for ri, emp in enumerate(emps, start=1):
                rn = ri + 3
                ha = bool(emp.get('account_number'))
                accst = emp.get('account_status') or ('No Account' if not ha else '-')

                def v(key, fallback='-'):
                    val = emp.get(key)
                    if val is None or str(val).strip() == '':
                        return fallback
                    return str(val).strip()

                vals = [
                    ri,
                    v('username'),
                    v('user_id'),
                    v('employee_id'),
                    v('department'),
                    v('designation'),
                    v('emp_type'),
                    v('date_of_joining'),
                    v('date_of_birth'),
                    v('father_name'),
                    v('mode_of_payment'),
                    v('pay_date'),
                    v('days_worked'),
                    v('account_number'),
                    v('ifsc_code'),
                    accst,
                ]

                rfill = PatternFill("solid", fgColor=(ROW_A if ri % 2 == 1 else ROW_B))
                for ci, val in enumerate(vals, start=1):
                    c = ws.cell(row=rn, column=ci)
                    c.value = val if val is not None else '-'
                    c.fill = rfill
                    c.font = Font(size=10, color=TXT, name="Calibri")
                    c.alignment = Alignment(vertical="center")
                    c.border = brd
                ws.row_dimensions[rn].height = 18

                # Colour-code Account Status (last col)
                ac = ws.cell(row=rn, column=NC)
                if accst == 'Approved':
                    ac.font = Font(size=10, color=GRN, bold=True, name="Calibri")
                elif accst.lower() == 'pending':
                    ac.font = Font(size=10, color=YLW, bold=True, name="Calibri")
                elif accst.lower() == 'rejected':
                    ac.font = Font(size=10, color=RED, bold=True, name="Calibri")
                else:
                    ac.font = Font(size=10, color=GRY, italic=True, name="Calibri")

            ws.freeze_panes = "A4"
            ws.auto_filter.ref = "A3:" + get_column_letter(NC) + "3"
            ws.sheet_properties.tabColor = tab_colours[di % len(tab_colours)]

        # ── Save to disk ──
        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "MIIM_Accounts_" + timestamp + ".xlsx"
        save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miim_storage', 'accounts')
        try:
            os.makedirs(save_dir, exist_ok=True)
            wb.save(os.path.join(save_dir, filename))
        except Exception:
            pass  # disk save failure is non-fatal

        # ── Stream as browser download ──
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        from flask import make_response
        resp = make_response(buf.read())
        resp.headers['Content-Type'] = (
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resp.headers['Content-Disposition'] = 'attachment; filename="' + filename + '"'
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/accounts/export-excel/status', methods=['GET'])
@require_auth
def export_accounts_excel_status():
    """Quick check: returns how many accounts + employees exist, ready to export."""
    try:
        conn = _db()
        emp_count = conn.execute("SELECT COUNT(*) FROM employees WHERE status='active'").fetchone()[0]
        acc_count = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        depts = [r[0] for r in conn.execute("SELECT DISTINCT dept FROM employees WHERE status='active' ORDER BY dept").fetchall()]
        conn.close()
        return jsonify({"success": True, "employees": emp_count, "accounts": acc_count, "departments": depts})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/accounts/<int:acc_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
def api_account_detail(acc_id):  # type: ignore
    try:
        conn = _db()
        if request.method == 'GET':
            row = conn.execute("SELECT * FROM accounts WHERE id=?", (acc_id,)).fetchone()
            conn.close()
            return jsonify({"success": True, "account": dict(row)}) if row else jsonify({"success": False, "error": "Not found"}), 404
        if request.method == 'PUT':
            data = request.json or {}
            conn.execute(
                "UPDATE accounts SET account_type=?,bank_name=?,account_number=?,ifsc_code=?,branch=?,upi_id=?,status=?,notes=?,mode_of_payment=?,pay_date=?,days_worked=? WHERE id=?",
                (data.get('account_type', 'Salary'), data.get('bank_name', 'Bank'),
                 data.get('account_number', ''), data.get('ifsc_code', ''),
                 data.get('branch', ''), data.get('upi_id', ''),
                 data.get('status', 'Approved'), data.get('notes', ''),
                 data.get('mode_of_payment', ''), data.get('pay_date', ''),
                 data.get('days_worked', 0), acc_id)
            )
            conn.commit()
            conn.close()
            return jsonify({"success": True})
        if request.method == 'DELETE':
            conn.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
            conn.commit()
            conn.close()
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Method not allowed"}), 405
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/checkin', methods=['POST'])
@require_auth
def checkin():
    try:
        data = request.json or {}
        emp_id = data.get('emp_id')
        import datetime as _dt
        conn = _db()
        today = str(_dt.date.today())
        now_time = _dt.datetime.now().strftime('%H:%M')
        now_str = str(_dt.datetime.now())
        existing = conn.execute("SELECT id FROM attendance WHERE emp_id=? AND date=?", (emp_id, today)).fetchone()
        if existing:
            conn.execute("UPDATE attendance SET checkin=?,status='present',updated_at=? WHERE emp_id=? AND date=?", (now_time, now_str, emp_id, today))
        else:
            conn.execute("INSERT INTO attendance (emp_id,date,checkin,checkout,status,marked_by,updated_at) VALUES (?,?,?,'--','present','self',?)", (emp_id, today, now_time, now_str))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/checkout', methods=['POST'])
@require_auth
def checkout():
    try:
        data = request.json or {}
        emp_id = data.get('emp_id')
        import datetime as _dt
        conn = _db()
        today = str(_dt.date.today())
        conn.execute("UPDATE attendance SET checkout=?,updated_at=? WHERE emp_id=? AND date=?",
                     (_dt.datetime.now().strftime('%H:%M'), str(_dt.datetime.now()), emp_id, today))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/break/start', methods=['POST'])
@require_auth
def break_start():
    return jsonify({"success": True})


@app.route('/api/break/end', methods=['POST'])
@require_auth
def break_end():
    return jsonify({"success": True, "duration_min": 0})


@app.route('/api/attendance/employee/<int:emp_id>', methods=['GET'])
@require_auth
def get_emp_attendance(emp_id):
    try:
        from_date = request.args.get('from', '')
        to_date = request.args.get('to', '')
        conn = _db()
        rows = conn.execute("SELECT * FROM attendance WHERE emp_id=? AND date BETWEEN ? AND ? ORDER BY date", (emp_id, from_date, to_date)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/photo/<int:emp_id>', methods=['GET'])
@require_auth
def get_photo(emp_id):
    try:
        conn = _db()
        row = conn.execute("SELECT photo_url FROM employees WHERE id=?", (emp_id,)).fetchone()
        conn.close()
        if row and row['photo_url']:
            return jsonify({"success": True, "photo_url": row['photo_url']})
        return jsonify({"success": False})
    except Exception:
        return jsonify({"success": False}), 500


@app.route('/api/me/role', methods=['GET'])
@require_auth
def me_role():
    try:
        from flask import request as req
        username = req.headers.get('X-User-Id', '') or req.args.get('username', '')
        conn = _db()
        emp = conn.execute("SELECT dept, desig FROM employees WHERE username=? OR user_id=?", (username, username)).fetchone()
        conn.close()
        if emp:
            d = (emp["desig"] or "").lower()
            dept = (emp["dept"] or "").lower()
            if "admin" in d or dept == "admin": role = "admin"
            elif "hr" in d or dept == "hr": role = "hr"
            elif "senior manager" in d: role = "sm"
            elif "project manager" in d: role = "pm"
            else: role = "member"
            return jsonify({"success": True, "role": role, "dept": emp["dept"]})
        return jsonify({"success": True, "role": "member", "dept": ""})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/attendance/range', methods=['GET'])
@require_auth
def get_attendance_range():
    try:
        from_date = request.args.get('from', '')
        to_date = request.args.get('to', '')
        conn = _db()
        rows = conn.execute("SELECT a.*, e.username as emp_name, e.empid FROM attendance a JOIN employees e ON e.id=a.emp_id WHERE a.date BETWEEN ? AND ? ORDER BY a.date", (from_date, to_date)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/attendance/save', methods=['POST'])
@require_auth
def save_attendance():
    try:
        data = request.json or {}
        records = data.get('records', [data])
        conn = _db()
        for rec in records:
            emp_id = rec.get('emp_id')
            date = rec.get('date')
            existing = conn.execute("SELECT id FROM attendance WHERE emp_id=? AND date=?", (emp_id, date)).fetchone()
            if existing:
                conn.execute("UPDATE attendance SET checkin=?,checkout=?,status=?,note=?,marked_by=?,updated_at=? WHERE emp_id=? AND date=?",
                             (rec.get('checkin', '--'), rec.get('checkout', '--'), rec.get('status', 'present'), rec.get('note', ''), rec.get('marked_by', 'admin'), str(datetime.datetime.now()), emp_id, date))
            else:
                conn.execute("INSERT INTO attendance (emp_id,date,checkin,checkout,status,note,marked_by,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                             (emp_id, date, rec.get('checkin', '--'), rec.get('checkout', '--'), rec.get('status', 'present'), rec.get('note', ''), rec.get('marked_by', 'admin'), str(datetime.datetime.now())))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/attendance/correction-request', methods=['POST'])
@require_auth
def correction_request():
    try:
        data = request.json or {}
        conn = _db()
        conn.execute("INSERT INTO attendance_corrections (emp_id,emp_name,dept,date,req_checkin,req_checkout,req_status,reason,status,created_at) VALUES (?,?,?,?,?,?,?,?,'pending',?)",
                     (data.get('emp_id'), data.get('emp_name', ''), data.get('dept', ''), data.get('date'), data.get('req_checkin', '--'), data.get('req_checkout', '--'), data.get('req_status', 'present'), data.get('reason', ''), str(datetime.datetime.now())))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/attendance/corrections', methods=['GET'])
@require_auth
def get_corrections():
    try:
        status = request.args.get('status', 'pending')
        emp_id = request.args.get('emp_id')
        conn = _db()
        if emp_id and status == 'all':
            rows = conn.execute("SELECT * FROM attendance_corrections WHERE emp_id=? ORDER BY created_at DESC", (emp_id,)).fetchall()
        elif status == 'all':
            rows = conn.execute("SELECT * FROM attendance_corrections ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM attendance_corrections WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/attendance/corrections/<int:corr_id>/<action>', methods=['POST'])
@require_auth
def review_correction(corr_id, action):
    try:
        data = request.json or {}
        status = 'approved' if action == 'approve' else 'rejected'
        conn = _db()
        conn.execute("UPDATE attendance_corrections SET status=?,reviewed_by=?,reviewed_by_name=?,review_note=?,reviewed_at=? WHERE id=?",
                     (status, data.get('reviewed_by', ''), data.get('reviewed_by_name', ''), data.get('review_note', ''), str(datetime.datetime.now()), corr_id))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/approval-history', methods=['GET', 'POST'])
@require_auth
def approval_history():
    try:
        conn = _db()
        if request.method == 'POST':
            data = request.json or {}
            conn.execute("INSERT INTO approval_history (emp_id,emp_name,dept,leave_type,leave_date,action,actioned_by,actioned_by_name,reason,actioned_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (data.get('emp_id'), data.get('emp_name', ''), data.get('dept', ''), data.get('leave_type', ''), data.get('leave_date', ''), data.get('action', ''), data.get('actioned_by', ''), data.get('actioned_by_name', ''), data.get('reason', ''), str(datetime.datetime.now())))
            conn.commit(); conn.close()
            return jsonify({"success": True})
        rows = conn.execute("SELECT * FROM approval_history ORDER BY actioned_at DESC LIMIT 50").fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/leave/apply', methods=['POST'])
@require_auth
def apply_leave_new():
    try:
        data = request.json or {}
        conn = _db()
        conn.execute("INSERT INTO leave_requests (emp_id,leave_type,from_date,to_date,days,reason,status,applied_at) VALUES (?,?,?,?,?,?,'pending',?)",
                     (data.get('emp_id'), data.get('leave_type'), data.get('from_date'), data.get('to_date'), data.get('days', 1), data.get('reason', ''), str(datetime.datetime.now())))
        conn.commit(); conn.close()
        return jsonify({"success": True}), 201
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/leave/balance/<int:emp_id>', methods=['GET'])
@require_auth
def get_leave_balance_by_id(emp_id):
    try:
        year = request.args.get('year', str(datetime.date.today().year))
        conn = _db()
        row = conn.execute("SELECT * FROM leave_balances WHERE emp_id=? AND year=?", (emp_id, year)).fetchone()
        conn.close()
        if row: return jsonify(dict(row))
        return jsonify({"annual": 18, "sick": 10, "casual": 6, "earned": 0, "used_annual": 0, "used_sick": 0, "used_casual": 0})
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/leave', methods=['GET'])
@require_auth
def get_leave_new():
    try:
        status = request.args.get('status')
        emp_id = request.args.get('emp_id')
        conn = _db()
        if emp_id and status:
            rows = conn.execute("SELECT * FROM leave_requests WHERE emp_id=? AND status=? ORDER BY id DESC", (emp_id, status)).fetchall()
        elif status:
            rows = conn.execute("SELECT * FROM leave_requests WHERE status=? ORDER BY id DESC", (status,)).fetchall()
        elif emp_id:
            rows = conn.execute("SELECT * FROM leave_requests WHERE emp_id=? ORDER BY id DESC", (emp_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM leave_requests ORDER BY id DESC").fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as ex:
        print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500


@app.route('/api/leave/<int:leave_id>/<action>', methods=['POST'])
@require_auth
def action_leave(leave_id, action):
    try:
        status = 'approved' if action == 'approve' else 'rejected'
        conn = _db()
        conn.execute("UPDATE leave_requests SET status=?,reviewed_at=? WHERE id=?", (status, str(datetime.datetime.now()), leave_id))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/attendance.html')


@app.route('/account_section.html')


@app.route('/expance.html')


@app.route('/holiday-dashboard.html')


@app.route('/performance_report.html')


@app.route('/project_tracker.html')


@app.route('/salary_slip_miim_.html')


@app.route('/salary_structure.html')
@require_auth
@require_auth
@require_auth
@require_auth
@require_auth
def serve_template():
    import os
    from flask import request as req
    # Get the filename from the URL path — sanitize to prevent path traversal
    raw = req.path.lstrip('/')
    filename = os.path.basename(raw)  # strips any ../ components
    # Only allow .html files
    if not filename.endswith('.html'):
        return 'Not found', 404
    base_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'template'))
    f = os.path.realpath(os.path.join(base_dir, filename))
    # Ensure resolved path is still inside template/ (double-check)
    if not f.startswith(base_dir + os.sep):
        return 'Not found', 403
    if os.path.exists(f):
        return open(f, 'r', encoding='utf-8', errors='replace').read()
    # Escape filename to prevent reflected XSS in 404
    import html as _html
    return '<h1>Page not found: ' + _html.escape(filename) + '</h1>', 404


@app.route('/landing')
def landing():
    import os
    _base = os.path.dirname(os.path.abspath(__file__))
    for _f in [
        os.path.join(_base, 'template', '1_miim (1).html'),
        os.path.join(_base, 'template', '1_miim.html'),
    ]:
        if os.path.exists(_f):
            return open(_f, 'r', encoding='utf-8', errors='replace').read()
    return '<h1>Landing page not found</h1>', 404


@app.route('/guest-login')
@require_auth
def guest_login_page():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MIIM — Guest Login</title>
<rect width='100' height='100' rx='16' fill='%23f97316'/><text y='.9em' font-size='80' x='10' font-weight='bold' fill='white'>M</text></svg>">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600&family=Rajdhani:wght@600;700&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0f0f0f;
    color: #e5e5e5;
    font-family: 'Exo 2', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .card {
    background: #141420;
    border: 1px solid rgba(99,102,241,0.35);
    border-top: 3px solid #6366f1;
    border-radius: 16px;
    width: 100%;
    max-width: 420px;
    padding: 36px 32px;
    box-shadow: 0 30px 80px rgba(0,0,0,0.7), 0 0 40px rgba(99,102,241,0.1);
  }
  .logo {
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.5rem;
    font-weight: 700;
    color: #f97316;
    letter-spacing: 3px;
    text-align: center;
    margin-bottom: 6px;
  }
  .subtitle {
    text-align: center;
    font-size: .78rem;
    color: #6366f1;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 32px;
    font-weight: 600;
  }
  label {
    display: block;
    font-size: .7rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #888;
    margin-bottom: 6px;
  }
  input {
    width: 100%;
    background: #111;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    color: #e5e5e5;
    font-family: 'Exo 2', sans-serif;
    font-size: .9rem;
    padding: 11px 14px;
    outline: none;
    transition: border-color .2s;
    margin-bottom: 18px;
  }
  input:focus { border-color: #6366f1; }
  .btn {
    width: 100%;
    background: #6366f1;
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 13px;
    font-family: 'Rajdhani', sans-serif;
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    cursor: pointer;
    transition: background .2s, opacity .2s;
    margin-top: 4px;
  }
  .btn:hover { background: #4f46e5; }
  .btn:disabled { opacity: .6; cursor: not-allowed; }
  .msg { text-align: center; font-size: .82rem; min-height: 22px; margin-top: 14px; }
  .back-link {
    text-align: center;
    margin-top: 22px;
    font-size: .78rem;
    color: #555;
  }
  .back-link a { color: #f97316; text-decoration: none; }
  .back-link a:hover { text-decoration: underline; }
  .guest-icon {
    text-align: center;
    font-size: 2.5rem;
    margin-bottom: 12px;
  }
</style>
</head>
<body>
<div class="card">
  <div class="guest-icon">👤</div>
  <div class="logo">MIIM</div>
  <div class="subtitle">Guest Access Portal</div>

  <label>Guest ID</label>
  <input type="text" id="gid" placeholder="Enter your Guest ID" autocomplete="off">

  <label>Password</label>
  <input type="password" id="gpw" placeholder="Enter your password" onkeydown="if(event.key==='Enter')doGuestLogin()">

  <button class="btn" id="login-btn" onclick="doGuestLogin()">LOGIN AS GUEST</button>
  <div class="msg" id="msg"></div>
  <div class="back-link"><a href="/landing">← Back to Staff Login</a></div>
</div>

<script>
async function doGuestLogin() {
  var gid  = document.getElementById('gid').value.trim();
  var gpw  = document.getElementById('gpw').value.trim();
  var msg  = document.getElementById('msg');
  var btn  = document.getElementById('login-btn');

  if (!gid || !gpw) {
    msg.style.color = '#f87171';
    msg.textContent = '⚠ Please enter both Guest ID and Password.';
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Verifying…';
  msg.textContent = '';

  try {
    var resp = await fetch(_apiUrl('/api/login'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: gid, password: gpw })
    });
    var data = await resp.json();

    if (data.success && data.role === 'guest') {
      // Save session
      if (data.user && data.role) data.user.role = data.role;
      sessionStorage.setItem('miim_user',  JSON.stringify(data.user));
      sessionStorage.setItem('userRole',   'guest');
      sessionStorage.setItem('userDept',   'Guest');
      localStorage.setItem('userRole',     'guest');
      localStorage.setItem('userDept',     'Guest');
      try { localStorage.setItem('miim_session', JSON.stringify(data.user)); } catch(e) {}

      msg.style.color = '#4ade80';
      msg.textContent = '✅ Access granted! Redirecting…';
      sessionStorage.setItem('miim_just_logged_in', '1');
      setTimeout(function(){ window.location.href = '/'; }, 800);
    } else if (data.success && data.role !== 'guest') {
      msg.style.color = '#f87171';
      msg.textContent = '⚠ This portal is for guests only. Use Staff Login.';
      btn.disabled = false;
      btn.textContent = 'LOGIN AS GUEST';
    } else {
      msg.style.color = '#f87171';
      msg.textContent = '❌ ' + (data.message || 'Invalid Guest ID or Password.');
      btn.disabled = false;
      btn.textContent = 'LOGIN AS GUEST';
    }
  } catch(e) {
    msg.style.color = '#f87171';
    msg.textContent = '❌ Server error. Please try again.';
    btn.disabled = false;
    btn.textContent = 'LOGIN AS GUEST';
  }
}
</script>
</body>
</html>'''



def init_db():
    """Create all required tables if they don't exist."""
    conn = _db()
    conn.execute("""CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT, user_id TEXT, empid TEXT,
        dept TEXT, desig TEXT, manager TEXT,
        joindate TEXT, type TEXT DEFAULT 'Regular',
        company_email TEXT, mobile TEXT, dob TEXT,
        father_name TEXT, photo_url TEXT,
        password_hash TEXT DEFAULT '',
        force_reset INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',
        salary_status TEXT DEFAULT '',
        probation_period TEXT DEFAULT '',
        intern_period TEXT DEFAULT ''
    )""")
    # Migration: add salary_status to existing employees table
    try:
        conn.execute("ALTER TABLE employees ADD COLUMN salary_status TEXT DEFAULT ''")
    except Exception:
        pass
    # Migration: add probation_period and intern_period
    try:
        conn.execute("ALTER TABLE employees ADD COLUMN probation_period TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE employees ADD COLUMN intern_period TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE employees ADD COLUMN address TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE employees ADD COLUMN days_worked INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE employees ADD COLUMN pay_date TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE employees ADD COLUMN mode_of_payment TEXT DEFAULT 'Account'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE employees ADD COLUMN relieve_date TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE employees ADD COLUMN relieve_reason TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE employees ADD COLUMN relieved_by TEXT DEFAULT ''")
    except Exception:
        pass
    # ── MIGRATION: Regenerate all user_ids → name+DD+MM format ──
    try:
        rows = conn.execute("SELECT id, username, joindate FROM employees").fetchall()
        for row in rows:
            _uid_id, _uname, _ujd = row[0], row[1] or '', row[2] or ''
            # Keep username lowercase as-is, only strip whitespace — dot/underscore stays
            _letters = _uname.lower().replace(' ', '')
            if _ujd and len(_ujd) >= 10:
                _parts = _ujd.split('-')
                _dd = _parts[2][:2] if len(_parts) > 2 else '01'
                _mm = _parts[1][:2] if len(_parts) > 1 else '01'
                _new_uid = _letters + _dd + _mm
            else:
                _new_uid = _letters + '0101'
            conn.execute("UPDATE employees SET user_id=? WHERE id=?", (_new_uid, _uid_id))
        conn.commit()
    except Exception:
        pass
    # ── Pending Promotions table ──
    conn.execute("""CREATE TABLE IF NOT EXISTS pending_promotions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER NOT NULL,
        old_desig TEXT,
        new_desig TEXT,
        effective_date TEXT,
        remarks TEXT,
        requested_by TEXT,
        requested_at TEXT,
        status TEXT DEFAULT 'pending',
        approved_by TEXT,
        approved_at TEXT,
        rejected_reason TEXT,
        hr_approved_by TEXT,
        hr_approved_at TEXT,
        admin_approved_by TEXT,
        admin_approved_at TEXT
    )""")
    for _col, _def in [
        ('rejected_reason', 'TEXT'),
        ('hr_approved_by', 'TEXT'),
        ('hr_approved_at', 'TEXT'),
        ('admin_approved_by', 'TEXT'),
        ('admin_approved_at', 'TEXT'),
    ]:
        try:
            conn.execute("ALTER TABLE pending_promotions ADD COLUMN " + _col + " " + _def)
        except Exception:
            pass
    conn.execute("""CREATE TABLE IF NOT EXISTS pending_employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT, user_id TEXT, empid TEXT,
        dept TEXT, desig TEXT, manager TEXT,
        joindate TEXT, type TEXT DEFAULT 'Regular',
        company_email TEXT, mobile TEXT, dob TEXT,
        father_name TEXT, photo_url TEXT,
        password_hash TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS salary_structures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER, period TEXT, department TEXT, designation TEXT,
        employee_type TEXT, basic REAL DEFAULT 0, hra REAL DEFAULT 0,
        dearness_allowance REAL DEFAULT 0, medical_allowance REAL DEFAULT 0,
        lta REAL DEFAULT 0, special_allowance REAL DEFAULT 0,
        city_compensatory_allowance REAL DEFAULT 0,
        professional_tax REAL DEFAULT 0, tds REAL DEFAULT 0,
        existing_advance REAL DEFAULT 0, other_deductions REAL DEFAULT 0,
        total_earnings REAL DEFAULT 0, total_deductions REAL DEFAULT 0,
        net_pay REAL DEFAULT 0, days_worked INTEGER DEFAULT 0,
        mode_of_payment TEXT DEFAULT 'Account', pay_date TEXT,
        notes TEXT, approval_status TEXT, correction_note TEXT,
        salary_ctc REAL DEFAULT 0, father_name TEXT,
        acct_approved_by TEXT, acct_approved_at TEXT, acct_approval_count INTEGER DEFAULT 0,
        mgmt_approved_by TEXT, mgmt_approved_at TEXT, mgmt_approval_count INTEGER DEFAULT 0
    )""")
    # Migration: add approval columns to existing salary_structures tables
    for _col, _def in [
        ('acct_approved_by', 'TEXT'),
        ('acct_approved_at', 'TEXT'),
        ('acct_approval_count', 'INTEGER DEFAULT 0'),
        ('mgmt_approved_by', 'TEXT'),
        ('mgmt_approved_at', 'TEXT'),
        ('mgmt_approval_count', 'INTEGER DEFAULT 0'),
    ]:
        try:
            conn.execute(f"ALTER TABLE salary_structures ADD COLUMN {_col} {_def}")
        except Exception:
            pass
    conn.execute("""CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER,
        account_type TEXT DEFAULT 'Salary',
        bank_name TEXT DEFAULT '',
        account_number TEXT DEFAULT '',
        ifsc_code TEXT DEFAULT '',
        branch TEXT DEFAULT '',
        upi_id TEXT DEFAULT '',
        status TEXT DEFAULT 'Approved',
        notes TEXT DEFAULT '',
        mode_of_payment TEXT DEFAULT 'Account',
        pay_date TEXT DEFAULT '',
        days_worked INTEGER DEFAULT 0,
        type TEXT DEFAULT '',
        category TEXT DEFAULT '',
        amount REAL DEFAULT 0,
        date TEXT DEFAULT '',
        description TEXT DEFAULT ''
    )""")
    # ── Migrate existing accounts table — add missing columns safely ──
    for _acol, _adef in [
        ('account_type', "TEXT DEFAULT 'Salary'"),
        ('bank_name', "TEXT DEFAULT ''"),
        ('account_number', "TEXT DEFAULT ''"),
        ('ifsc_code', "TEXT DEFAULT ''"),
        ('branch', "TEXT DEFAULT ''"),
        ('upi_id', "TEXT DEFAULT ''"),
        ('notes', "TEXT DEFAULT ''"),
        ('mode_of_payment', "TEXT DEFAULT 'Account'"),
        ('pay_date', "TEXT DEFAULT ''"),
        ('days_worked', "INTEGER DEFAULT 0"),
        ('approval_status', "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE accounts ADD COLUMN {_acol} {_adef}")
        except Exception:
            pass  # column already exists
    conn.execute("""CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT, leave_type TEXT, from_date TEXT,
        to_date TEXT, days INTEGER DEFAULT 1,
        reason TEXT, status TEXT DEFAULT 'pending',
        applied_at TEXT, reviewed_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS leave_balances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER, year TEXT,
        annual INTEGER DEFAULT 18, sick INTEGER DEFAULT 10,
        casual INTEGER DEFAULT 6, earned INTEGER DEFAULT 0,
        used_annual INTEGER DEFAULT 0, used_sick INTEGER DEFAULT 0,
        used_casual INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS attendance_corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT, emp_name TEXT, dept TEXT, date TEXT,
        req_checkin TEXT, req_checkout TEXT, req_status TEXT,
        reason TEXT, status TEXT DEFAULT 'pending',
        reviewed_by TEXT, reviewed_by_name TEXT,
        review_note TEXT, reviewed_at TEXT, created_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS approval_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT, emp_name TEXT, dept TEXT,
        leave_type TEXT, leave_date TEXT, action TEXT,
        actioned_by TEXT, actioned_by_name TEXT,
        reason TEXT, actioned_at TEXT
    )""")
    conn.commit()
    # Employee status change history
    conn.execute("""CREATE TABLE IF NOT EXISTS emp_status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER NOT NULL,
        field TEXT, from_val TEXT, to_val TEXT,
        changed_date TEXT, created_at TEXT
    )""")
    conn.commit()
    # Migration: set intern_period = '3m' for existing Interns with empty period
    conn.execute("UPDATE employees SET intern_period='3m' WHERE type='Intern' AND (intern_period IS NULL OR intern_period='')")
    conn.commit()

    # Migration: add emp_status_history if missing
    try:
        conn.execute("SELECT 1 FROM emp_status_history LIMIT 1")
    except Exception:
        conn.execute("""CREATE TABLE emp_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id INTEGER NOT NULL,
            field TEXT, from_val TEXT, to_val TEXT,
            changed_date TEXT, created_at TEXT
        )""")
        conn.commit()

    # ── Additional tables ──
    conn.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER, date TEXT, checkin TEXT, checkout TEXT,
        status TEXT DEFAULT 'present', marked_by TEXT,
        hours REAL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS holidays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, name TEXT, type TEXT DEFAULT 'National',
        emoji TEXT DEFAULT '🎉', desc TEXT DEFAULT ''
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS guests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT, project TEXT, access_date TEXT,
        guest_id TEXT, password TEXT, sent_opt INTEGER DEFAULT 0,
        new_guest_id TEXT, new_password TEXT,
        login_used INTEGER DEFAULT 0,
        access_from TEXT DEFAULT '',
        access_to TEXT DEFAULT '',
        perm_enabled INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS archived_slips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT,
        archive_uid TEXT UNIQUE,
        period TEXT,
        archived_at TEXT,
        slip_data TEXT
    )""")
    # Add login_used column if it doesn't exist (for existing DBs)
    try:
        conn.execute("ALTER TABLE guests ADD COLUMN login_used INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass  # column already exists
    try:
        conn.execute("ALTER TABLE guests ADD COLUMN access_from TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE guests ADD COLUMN access_to TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE guests ADD COLUMN perm_enabled INTEGER DEFAULT 1")
        conn.commit()
    except Exception:
        pass
    conn.execute("""CREATE TABLE IF NOT EXISTS tracker_data (
        key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT, message TEXT, type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0, created_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, description TEXT, status TEXT DEFAULT 'active',
        created_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT, emp_name TEXT, dept TEXT,
        category TEXT, amount REAL DEFAULT 0,
        description TEXT, receipt_url TEXT, receipt_files TEXT,
        status TEXT DEFAULT 'pending',
        approval_stage TEXT DEFAULT 'pending',
        sm_pm_approved_by TEXT, sm_pm_approved_at TEXT,
        hr_approved_by TEXT, hr_approved_at TEXT,
        accounts_approved_by TEXT, accounts_approved_at TEXT,
        final_approved_by TEXT, final_approved_at TEXT,
        reapprove_reason TEXT, reapproved_by TEXT, reapproved_at TEXT,
        review_note TEXT, reviewed_by TEXT,
        submitted_at TEXT, updated_at TEXT
    )""")
    # Migration: add approval_stage columns to existing expenses table
    for _col, _def in [
        ('approval_stage', 'TEXT DEFAULT \'pending\''),
        ('sm_pm_approved_by', 'TEXT'), ('sm_pm_approved_at', 'TEXT'),
        ('hr_approved_by', 'TEXT'), ('hr_approved_at', 'TEXT'),
        ('accounts_approved_by', 'TEXT'), ('accounts_approved_at', 'TEXT'),
        ('final_approved_by', 'TEXT'), ('final_approved_at', 'TEXT'),
        ('reapprove_reason', 'TEXT'), ('reapproved_by', 'TEXT'), ('reapproved_at', 'TEXT'),
    ]:
        try:
            conn.execute(f"ALTER TABLE expenses ADD COLUMN {_col} {_def}")
        except Exception:
            pass
    conn.commit()

    # Seed default admin if no employees exist
    count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    if count == 0:
        import datetime as _dt
        conn.execute("""INSERT INTO employees
            (username, user_id, empid, dept, desig, manager, joindate, type,
             company_email, mobile, dob, father_name, photo_url,
             password_hash, force_reset, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     ('admin', 'adm0001', 'MIIM000', 'Admin', 'Administrator',
                      '', _dt.date.today().isoformat(), 'Regular',
                      'admin@miim.com', '', '', '', '',
                      hash_password('miim@123'), 0, 'active'))
        conn.commit()
        print("[DB] Default admin created: username=admin  password=miim@123")

    # Seed default miim_projects in tracker_data if not present
    existing = conn.execute("SELECT key FROM tracker_data WHERE key='miim_projects'").fetchone()
    if not existing:
        import json as _json, datetime as _dt2
        default_projects = [
            {"id": "PRJ001", "name": "MIIM Website Redesign", "status": "Active", "manager": "Aravind Kumar", "deadline": "2026-06-30"},
            {"id": "PRJ002", "name": "HR Automation System", "status": "Active", "manager": "Priya Sharma", "deadline": "2026-07-15"},
            {"id": "PRJ003", "name": "Manufacturing Process Audit", "status": "Yet to Start", "manager": "Ravi Chandran", "deadline": "2026-08-01"},
            {"id": "PRJ004", "name": "Client Portal v2", "status": "Planning", "manager": "Meena Devi", "deadline": "2026-09-10"},
            {"id": "PRJ005", "name": "Internal Training Program", "status": "Active", "manager": "Suresh Babu", "deadline": "2026-05-31"},
        ]
        conn.execute(
            "INSERT INTO tracker_data (key, value, updated_at) VALUES (?, ?, ?)",
            ('miim_projects', _json.dumps(default_projects), _dt2.datetime.now().isoformat())
        )
        conn.commit()
        print("[DB] Default miim_projects seeded in tracker_data")

    # Seed default holidays if none exist
    hol_count = conn.execute("SELECT COUNT(*) FROM holidays").fetchone()[0]
    if hol_count == 0:
        default_holidays = [
            ("2026-01-01", "New Year's Day", "National", "🎉"),
            ("2026-01-14", "Pongal", "National", "🌾"),
            ("2026-01-15", "Thiruvalluvar Day", "National", "📜"),
            ("2026-01-16", "Uzhavar Thirunal", "National", "🌻"),
            ("2026-01-26", "Republic Day", "Government", "🇮🇳"),
            ("2026-03-10", "Company Foundation Day", "National", "🏢"),
            ("2026-04-14", "Tamil New Year", "National", "🎊"),
            ("2026-04-14", "Dr. Ambedkar Jayanti", "Government", "🙏"),
            ("2026-05-01", "Labour Day", "Government", "⚒️"),
            ("2026-06-07", "Eid al-Adha", "Religious", "🌙"),
            ("2026-08-15", "Independence Day", "Government", "🇮🇳"),
            ("2026-08-19", "Krishna Jayanthi", "Religious", "🪈"),
            ("2026-10-02", "Gandhi Jayanti", "Government", "🕊️"),
            ("2026-10-02", "Vijaya Dasami", "Religious", "⚔️"),
            ("2026-10-19", "Diwali", "Religious", "🪔"),
            ("2026-10-20", "Diwali Holiday", "National", "🪔"),
            ("2026-11-01", "Kannada Rajyotsava", "National", "🌟"),
            ("2026-11-14", "Children's Day", "National", "🧒"),
            ("2026-12-25", "Christmas", "Religious", "🎄"),
        ]
        for h in default_holidays:
            conn.execute(
                "INSERT INTO holidays (date, name, type, emoji, desc) VALUES (?,?,?,?,?)",
                (h[0], h[1], h[2], h[3], '')
            )
        conn.commit()
        print(f"[DB] {len(default_holidays)} default holidays seeded.")

    conn.close()
    print("[DB] Initialized successfully")


# ── AUTO-INIT DB on every startup (module level) ──
try:
    init_db()
except Exception as _e:
    print(f"[DB INIT WARNING] {_e}")

# ── EXPENSES API ──────────────────────────────────────────────────────────────



def _exp_conn():
    return _db()



def _exp_row(r):
    import json as _j
    d = dict(r)
    # parse receipt_files JSON
    try:
        d['receipt_files'] = _j.loads(d.get('receipt_files') or '[]')
    except Exception:
        d['receipt_files'] = []
    return d



def _get_role_dept(username):
    """Return (role, dept) for a username/user_id."""
    try:
        c = _exp_conn()
        emp = c.execute(
            "SELECT dept, desig FROM employees WHERE username=? OR user_id=?",
            (username, username)).fetchone()
        c.close()
        if emp:
            d = (emp['desig'] or '').lower()
            dept = (emp['dept'] or '')
            dl = dept.lower()
            if 'admin' in d or dl == 'admin': role = 'admin'
            elif 'hr' in d or dl == 'hr': role = 'hr'
            elif 'account manager' in d or dl in ('account', 'accounts', 'finance'): role = 'account_manager'
            elif 'senior manager' in d: role = 'sm'
            elif 'project manager' in d: role = 'pm'
            else: role = 'member'
            return role, dept
    except Exception:
        pass
    return 'member', ''


@app.route('/api/expance', methods=['GET'])
@require_auth
def exp_get():
    try:
        emp_id = request.args.get('emp_id', '').strip()
        status = request.args.get('status', '').strip()
        caller = request.args.get('caller', '').strip()   # username of requester
        c = _exp_conn()
        q = "SELECT * FROM expenses WHERE 1=1"
        params = []
        if emp_id:
            q += " AND emp_id=?"
            params.append(emp_id)
        if status and status != 'all':
            q += " AND status=?"
            params.append(status)
        # Role-based filter:
        # admin / hr / account_manager → see ALL expenses
        # sm / pm → see only their dept
        # member → see only own (emp_id from frontend)
        if caller:
            role, dept = _get_role_dept(caller)
            if role in ('admin', 'hr', 'account_manager'):
                pass  # no restriction
            elif role in ('sm', 'pm') and dept:
                q += " AND dept=?"
                params.append(dept)
            else:
                if emp_id:
                    q += " AND emp_id=?"
                    params.append(emp_id)
        elif emp_id:
            q += " AND emp_id=?"
            params.append(emp_id)
        q += " ORDER BY submitted_at DESC"
        rows = c.execute(q, params).fetchall()
        c.close()
        return jsonify({'success': True, 'expenses': [_exp_row(r) for r in rows]})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/expance', methods=['POST'])
@require_auth
def exp_post():
    import datetime as _dt, json as _j
    try:
        data = request.json or {}
        now = _dt.datetime.now().isoformat()
        c = _exp_conn()
        c.execute("""INSERT INTO expenses
            (emp_id, emp_name, dept, category, amount, description,
             receipt_url, receipt_files, status, approval_stage, submitted_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (data.get('emp_id', ''), data.get('emp_name', ''), data.get('dept', ''),
                   data.get('category', ''), data.get('amount', 0), data.get('description', ''),
                   data.get('receipt_b64', ''), _j.dumps(data.get('receipt_files', [])),
                   'pending', 'pending', now, now))
        c.commit()
        new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = c.execute("SELECT * FROM expenses WHERE id=?", (new_id,)).fetchone()
        c.close()
        return jsonify({'success': True, 'expense': _exp_row(row)})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/expance/<int:exp_id>', methods=['PUT'])
@require_auth
def exp_put(exp_id):
    import datetime as _dt, json as _j
    try:
        data = request.json or {}
        now = _dt.datetime.now().isoformat()
        c = _exp_conn()
        row = c.execute("SELECT * FROM expenses WHERE id=?", (exp_id,)).fetchone()
        if not row:
            c.close()
            return jsonify({'success': False, 'error': 'Not found'}), 404

        # Determine what kind of action this is
        action = data.get('action', '')          # 'sm_pm_approve','hr_approve','accounts_approve','final_approve','reject','reapprove_reset'
        status = data.get('status', '')           # 'approved' / 'rejected' / ''
        review_note = data.get('review_note', '')
        reviewed_by = data.get('reviewed_by', '')
        caller = data.get('caller', '')

        role, dept = _get_role_dept(caller) if caller else ('admin', '')

        cur_stage = row['approval_stage'] or 'pending'

        updates = {'updated_at': now}

        if action == 'reject' or status == 'rejected':
            updates['status'] = 'rejected'
            updates['approval_stage'] = 'rejected'
            updates['review_note'] = review_note
            updates['reviewed_by'] = reviewed_by or caller

        elif action == 'sm_pm_approve' and cur_stage == 'pending':
            updates['approval_stage'] = 'sm_pm_approved'
            updates['sm_pm_approved_by'] = reviewed_by or caller
            updates['sm_pm_approved_at'] = now
            updates['review_note'] = review_note

        elif action == 'hr_approve' and cur_stage == 'sm_pm_approved':
            updates['approval_stage'] = 'hr_approved'
            updates['hr_approved_by'] = reviewed_by or caller
            updates['hr_approved_at'] = now
            updates['review_note'] = review_note

        elif action == 'accounts_approve' and cur_stage == 'hr_approved':
            updates['approval_stage'] = 'accounts_approved'
            updates['accounts_approved_by'] = reviewed_by or caller
            updates['accounts_approved_at'] = now
            updates['review_note'] = review_note

        elif action == 'final_approve' and cur_stage == 'accounts_approved':
            updates['approval_stage'] = 'approved'
            updates['status'] = 'approved'
            updates['final_approved_by'] = reviewed_by or caller
            updates['final_approved_at'] = now
            updates['review_note'] = review_note

        elif action == 'reapprove_reset' and role in ('admin', 'hr'):
            # Admin/HR triggered re-approve: reset all stages, go back to pending
            # Update content fields too
            updates['status'] = 'pending'
            updates['approval_stage'] = 'pending'
            updates['sm_pm_approved_by'] = None  # type: ignore[assignment]
            updates['sm_pm_approved_at'] = None  # type: ignore[assignment]
            updates['hr_approved_by'] = None  # type: ignore[assignment]
            updates['hr_approved_at'] = None  # type: ignore[assignment]
            updates['accounts_approved_by'] = None  # type: ignore[assignment]
            updates['accounts_approved_at'] = None  # type: ignore[assignment]
            updates['final_approved_by'] = None  # type: ignore[assignment]
            updates['final_approved_at'] = None  # type: ignore[assignment]
            updates['reapprove_reason'] = data.get('reapprove_reason', '')
            updates['reapproved_by'] = data.get('reapproved_by', '') or reviewed_by or caller
            updates['reapproved_at'] = now
            # Update editable fields
            for fld in ('category', 'amount', 'description'):
                if fld in data: updates[fld] = data[fld]
            if 'receipt_b64' in data and data['receipt_b64']:
                updates['receipt_url'] = data['receipt_b64']
            if 'receipt_files' in data:
                updates['receipt_files'] = _j.dumps(data['receipt_files'])

        elif status == 'approved' and role == 'admin':
            # Legacy: admin direct approve
            updates['approval_stage'] = 'approved'
            updates['status'] = 'approved'
            updates['final_approved_by'] = reviewed_by or caller
            updates['final_approved_at'] = now
            updates['review_note'] = review_note

        else:
            # Edit mode (no action) — update basic fields
            for fld in ('category', 'amount', 'description', 'receipt_b64', 'receipt_files'):
                if fld in data:
                    col = 'receipt_url' if fld == 'receipt_b64' else fld
                    if fld == 'receipt_files':
                        updates[col] = _j.dumps(data[fld])
                    else:
                        updates[col] = data[fld]

        set_clause = ', '.join(f"{k}=?" for k in updates)
        c.execute(f"UPDATE expenses SET {set_clause} WHERE id=?", list(updates.values()) + [exp_id])
        c.commit()
        updated = c.execute("SELECT * FROM expenses WHERE id=?", (exp_id,)).fetchone()
        c.close()
        return jsonify({'success': True, 'expense': _exp_row(updated)})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/expance/<int:exp_id>', methods=['DELETE'])
@require_auth
def exp_delete(exp_id):
    try:
        c = _exp_conn()
        c.execute("DELETE FROM expenses WHERE id=?", (exp_id,))
        c.commit(); c.close()
        return jsonify({'success': True})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/expance/summary', methods=['GET'])
@require_auth
def exp_summary():
    try:
        caller = request.args.get('caller', '').strip()
        c = _exp_conn()
        q = "SELECT emp_id, emp_name, dept, status, amount FROM expenses WHERE 1=1"
        params = []
        if caller:
            role, dept = _get_role_dept(caller)
            if role in ('sm', 'pm') and dept:
                q += " AND dept=?"
                params.append(dept)
        rows = c.execute(q, params).fetchall()
        c.close()
        mp = {}
        for r in rows:
            k = str(r['emp_id']) + '|' + (r['emp_name'] or '')
            if k not in mp:
                mp[k] = {'emp_id': r['emp_id'], 'emp_name': r['emp_name'] or '',
                         'dept': r['dept'] or '', 'total': 0, 'approved': 0,
                         'pending_amt': 0, 'rejected': 0, 'count': 0}
            mp[k]['total'] += float(r['amount'] or 0)
            mp[k]['count'] += 1
            if r['status'] == 'approved': mp[k]['approved'] += float(r['amount'] or 0)
            if r['status'] == 'pending': mp[k]['pending_amt'] += float(r['amount'] or 0)
            if r['status'] == 'rejected': mp[k]['rejected'] += float(r['amount'] or 0)
        return jsonify({'success': True, 'summary': list(mp.values())})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

# ── GUEST SEND CREDENTIALS ──


@app.route('/api/guests/send-credentials', methods=['POST'])
@require_auth
def guest_send_credentials():
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    try:

        data = request.json or {}
        email = data.get('email', '').strip()
        guest_name = data.get('guest_name', 'Guest')
        project = data.get('project', '')
        access_date = data.get('access_date', '')
        guest_id = data.get('guest_id', '')
        password = data.get('password', '')

        if not email:
            return jsonify({"success": False, "error": "Email address is required."}), 400

        # ── GUEST SMTP — claude.ai@miim.co.in ──
        import os as _guest_os
        SMTP_HOST = 'smtp.hostinger.com'
        SMTP_PORT = 465
        SMTP_USER = _guest_os.environ.get('MIIM_GUEST_SMTP_USER', _CHAT_SMTP_USER)
        SMTP_PASS = _guest_os.environ.get('MIIM_GUEST_SMTP_PASS', _CHAT_SMTP_PASS)

        send_opt = data.get('send_opt', 1)
        is_temp = (send_opt == 1)
        access_type_label = "Temporary (One-Time Login)" if is_temp else "Permanent Access"
        access_note = (
            "<p style='margin:16px 0 0;padding:12px 16px;background:rgba(249,115,22,0.1);border:1px solid rgba(249,115,22,0.3);border-radius:8px;font-size:.82rem;color:#f97316;'>"
            "⚠️ <strong>One-Time Access:</strong> These credentials are valid for a single login only. After you log in once, they will expire automatically."
            "</p>"
        ) if is_temp else (
            "<p style='margin:16px 0 0;padding:12px 16px;background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);border-radius:8px;font-size:.82rem;color:#4ade80;'>"
            "✅ <strong>Permanent Access:</strong> You can use these credentials to log in anytime — no expiry."
            "</p>"
        )

        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;background:#0f0f0f;color:#e5e5e5;border-radius:12px;overflow:hidden;border:1px solid #2a2a2a;">
          <div style="background:#f97316;padding:20px 28px;">
            <h2 style="margin:0;color:#fff;font-size:1.3rem;letter-spacing:1px;">MIIM — Guest Access Credentials</h2>
            <div style="margin-top:6px;font-size:.8rem;color:rgba(255,255,255,0.75);">{access_type_label}</div>
          </div>
          <div style="padding:28px;">
            <p style="margin:0 0 16px;">Hi <strong>{guest_name}</strong>,</p>
            <p style="margin:0 0 20px;color:#aaa;">Here are your login credentials for <strong style="color:#f97316;">{project}</strong> on <strong>{access_date}</strong>:</p>
            <table style="width:100%;border-collapse:collapse;background:#1a1a1a;border-radius:8px;overflow:hidden;">
              <tr><td style="padding:12px 16px;color:#888;width:40%;">Guest ID</td><td style="padding:12px 16px;font-weight:700;color:#f97316;letter-spacing:1px;">{guest_id}</td></tr>
              <tr style="border-top:1px solid #2a2a2a;"><td style="padding:12px 16px;color:#888;">Password</td><td style="padding:12px 16px;font-weight:700;color:#4ade80;letter-spacing:1px;">{password}</td></tr>
            </table>
            {access_note}
            <p style="margin:20px 0 0;font-size:.82rem;color:#666;">Please keep these credentials confidential. Contact HR if you face any issues.</p>
          </div>
          <div style="padding:14px 28px;border-top:1px solid #2a2a2a;text-align:center;font-size:.75rem;color:#555;">MIIM HR System &nbsp;·&nbsp; Automated Notification</div>
        </div>
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'MIIM — Guest Access Credentials ({project})'
        msg['From'] = f'MIIM HR System <{SMTP_USER}>'
        msg['To'] = email
        msg.attach(MIMEText(html_body, 'html'))

        import ssl as _ssl
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=_ssl.create_default_context(), timeout=30) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [email], msg.as_string())

        return jsonify({"success": True, "message": f"Credentials sent to {email}"})

    except smtplib.SMTPAuthenticationError:
        return jsonify({"success": False, "error": "SMTP Authentication failed. Check your Hostinger email and password."}), 500
    except smtplib.SMTPException as smtp_err:
        return jsonify({"success": False, "error": f"SMTP error: {str(smtp_err)}"}), 500
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ══════════════════════════════════════════════════
# ── MIIM ROBOT CHATBOT API ──
# Employee messages → only Admin can read them
# Admin can reply to any employee
# ══════════════════════════════════════════════════
import os as _ch_os
import datetime as _ch_dt



def _chat_db():
    c = _db()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id        INTEGER PRIMARY KEY AUTO_INCREMENT,
        emp_id    TEXT NOT NULL,
        emp_name  TEXT NOT NULL,
        dept      TEXT NOT NULL DEFAULT '',
        role      TEXT NOT NULL DEFAULT 'member',
        sender    TEXT NOT NULL,
        message   TEXT NOT NULL,
        ts        TEXT NOT NULL
    )''')
        c.commit()
    except Exception:
        pass
    return c


@app.route('/api/chat/messages', methods=['GET'])
@require_auth
def chat_get():
    try:
        caller_id = request.args.get('emp_id', '').strip()
        caller_role = request.args.get('role', 'member').strip().lower()
        conn = _chat_db()
        if caller_role == 'admin':
            # Admin sees ALL messages
            rows = conn.execute('SELECT * FROM chat_messages ORDER BY id ASC').fetchall()
        else:
            # Employee sees ONLY their own messages
            rows = conn.execute(
                'SELECT * FROM chat_messages WHERE emp_id=? ORDER BY id ASC',
                (caller_id,)
            ).fetchall()
        conn.close()
        return jsonify({'success': True, 'messages': [dict(r) for r in rows]})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ── SMTP constants for chat alerts ──
_CHAT_SMTP_HOST = 'smtp.hostinger.com'
_CHAT_SMTP_PORT = 465
# ── Credentials loaded from environment variables (see security.py) ──
# _CHAT_SMTP_USER, _CHAT_SMTP_PASS, _ADMIN_EMAIL are imported from security.py above



def _send_chat_alert(emp_id, emp_name, dept, message, ts):
    """Deliver chat alert to inbox using IMAP APPEND — avoids self-send SMTP bounce. Name/identity hidden."""
    try:
        import ssl as _ssl, time as _time
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;background:#0f0f0f;color:#e5e5e5;border-radius:12px;overflow:hidden;border:1px solid #2a2a2a;">
          <div style="background:#f97316;padding:16px 24px;">
            <h2 style="margin:0;color:#fff;font-size:1.1rem;letter-spacing:1px;">MIIM — New Chat Message</h2>
          </div>
          <div style="padding:24px;">
            <table style="width:100%;border-collapse:collapse;background:#1a1a1a;border-radius:8px;overflow:hidden;margin-bottom:16px;">
              <tr><td style="padding:10px 14px;color:#888;width:35%;">Time</td><td style="padding:10px 14px;">{ts}</td></tr>
            </table>
            <div style="background:#1a1a1a;border-left:3px solid #f97316;padding:14px 16px;border-radius:6px;font-size:.95rem;">
              {message}
            </div>
            <p style="margin:20px 0 0;font-size:.8rem;color:#555;">
              <strong style="color:#f97316;">Reply to this email</strong> — your reply will appear in the employee chat automatically.
            </p>
          </div>
          <div style="padding:12px 24px;border-top:1px solid #2a2a2a;text-align:center;font-size:.72rem;color:#555;">
            MIIM HR System · Ref: {emp_id}
          </div>
        </div>
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'[MIIM Chat] New message — Ref: {emp_id}'
        msg['From'] = f'MIIM HR System <{_CHAT_SMTP_USER}>'
        msg['To'] = _ADMIN_EMAIL or ''
        msg['Reply-To'] = f'MIIM Chat <{_CHAT_SMTP_USER}>'
        msg['X-MIIM-EmpId'] = emp_id
        msg['X-MIIM-Alert'] = 'outgoing'
        msg.attach(MIMEText(html_body, 'html'))

        # IMAP APPEND — places mail directly in inbox, no SMTP self-send bounce
        ctx = _ssl.create_default_context()
        imap = _imap.IMAP4_SSL('imap.hostinger.com', 993, ssl_context=ctx)
        imap.login(_CHAT_SMTP_USER, _CHAT_SMTP_PASS)
        imap.append('INBOX', '', _imap.Time2Internaldate(_time.time()), msg.as_bytes())
        imap.logout()
        print(f'[ChatAlert] ✅ Alert delivered to inbox — Ref: {emp_id}')
    except Exception as _e:
        print(f'[ChatAlert] ❌ Failed: {_e}')


@app.route('/api/chat/send', methods=['POST'])
@require_auth
def chat_send():
    try:
        data = request.json or {}
        emp_id = data.get('emp_id', '').strip()
        emp_name = data.get('emp_name', 'Employee').strip()
        dept = data.get('dept', '').strip()
        role = data.get('role', 'member').strip().lower()
        sender = data.get('sender', 'user')
        message = data.get('message', '').strip()
        if not emp_id or not message:
            return jsonify({'success': False, 'error': 'emp_id and message required'}), 400
        ts = _ch_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = _chat_db()
        conn.execute(
            'INSERT INTO chat_messages (emp_id,emp_name,dept,role,sender,message,ts) VALUES (?,?,?,?,?,?,?)',
            (emp_id, emp_name, dept, role, sender, message, ts)
        )
        conn.commit(); conn.close()
        # ── Send email alert to admin for employee messages only (not bot auto-replies) ──
        if sender == 'user' and emp_name != 'MIIM Bot':
            import threading as _th
            _th.Thread(target=_send_chat_alert, args=(emp_id, emp_name, dept, message, ts), daemon=True).start()
        return jsonify({'success': True, 'ts': ts})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ══════════════════════════════════════════════════
# ── EMAIL INBOUND WEBHOOK — Admin email reply → Chat ──
# Admin replies to the alert email → POST to /api/chat/email-reply
# This endpoint is called by Hostinger email webhook or a polling script
# ══════════════════════════════════════════════════


@app.route('/api/chat/email-reply', methods=['POST'])
def chat_email_reply():
    """
    Receive admin's email reply and post it as a bot (admin) message in chat.
    Expected JSON: { emp_id, reply_text, admin_name (optional), secret }
    Call this from your email polling script or Hostinger webhook.
    """
    try:
        import os as _os_sec
        SECRET = _os_sec.environ.get('EMAIL_REPLY_SECRET', '')
        if not SECRET:
            return jsonify({'success': False, 'error': 'Server misconfiguration'}), 500
        data = request.json or {}
        if data.get('secret', '') != SECRET:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        emp_id = data.get('emp_id', '').strip()
        reply_text = data.get('reply_text', '').strip()
        if not emp_id or not reply_text:
            return jsonify({'success': False, 'error': 'emp_id and reply_text required'}), 400
        # Look up emp_name from DB
        conn = _chat_db()
        row = conn.execute('SELECT emp_name FROM chat_messages WHERE emp_id=? AND sender="user" ORDER BY id DESC LIMIT 1', (emp_id,)).fetchone()
        emp_name = row['emp_name'] if row else emp_id
        ts = _ch_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            'INSERT INTO chat_messages (emp_id,emp_name,dept,role,sender,message,ts) VALUES (?,?,?,?,?,?,?)',
            (emp_id, emp_name, '', 'admin', 'bot', reply_text, ts)
        )
        conn.commit(); conn.close()
        return jsonify({'success': True, 'ts': ts, 'emp_id': emp_id})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/api/chat/clear', methods=['DELETE'])
@require_auth
def chat_clear():
    try:
        # Role from verified JWT token — NOT from URL query param
        current_user = get_current_user()
        caller_role = current_user.get('role', 'member')  # type: ignore[union-attr]
        caller_id = str(current_user.get('emp_id', ''))  # type: ignore[union-attr]
        conn = _chat_db()
        if caller_role == 'admin':
            conn.execute('DELETE FROM chat_messages')
        else:
            conn.execute('DELETE FROM chat_messages WHERE emp_id=?', (caller_id,))
        conn.commit(); conn.close()
        return jsonify({'success': True})
    except Exception as ex:
        print(f"[chat_clear error] {ex}")
        return jsonify({'success': False, 'error': 'Operation failed'}), 500

# ── FAVICON — prevents 404 in browser console ──


@app.route('/api/chat/test-email', methods=['GET'])
def chat_test_email():
    """Test IMAP APPEND - call from browser: http://localhost:5000/api/chat/test-email"""
    try:
        import ssl as _ssl, time as _time
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart('alternative')
        msg['Subject'] = '[MIIM Chat] Test — IMAP Deliver Working'
        msg['From'] = f'MIIM HR System <{_CHAT_SMTP_USER}>'
        msg['To'] = _ADMIN_EMAIL or ''
        msg['X-MIIM-Alert'] = 'outgoing'
        msg.attach(MIMEText('<h2 style="color:#f97316;">✅ IMAP deliver working!</h2><p>Chat alerts will appear in inbox.</p>', 'html'))
        ctx = _ssl.create_default_context()
        imap = _imap.IMAP4_SSL('imap.hostinger.com', 993, ssl_context=ctx)
        imap.login(_CHAT_SMTP_USER, _CHAT_SMTP_PASS)
        imap.append('INBOX', '', _imap.Time2Internaldate(_time.time()), msg.as_bytes())
        imap.logout()
        return jsonify({'success': True, 'message': f'Test mail delivered to inbox at {_ADMIN_EMAIL}'})
    except Exception as ex:
        print(f"[ERROR] {ex}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route('/favicon.ico')
def favicon():
    import base64
    from flask import Response
    # Minimal 1x1 transparent ICO
    ico_b64 = "AAABAAEAAQEAAAEAIAAwAAAAFgAAACgAAAABAAAAAgAAAAEAIAAAAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
    return Response(base64.b64decode(ico_b64), mimetype='image/x-icon')


# ══════════════════════════════════════════════════
# ── EMBEDDED EMAIL REPLY POLLER ──
# Runs in background thread — checks inbox every 30s
# ══════════════════════════════════════════════════
import imaplib as _imap_lib
import imaplib as _imap  # for _send_chat_alert IMAP APPEND
import email as _email_lib
from email.header import decode_header as _decode_header
import re as _re_mail

_IMAP_HOST = 'imap.hostinger.com'
_IMAP_PORT = 993
_POLL_EVERY = 30



def _mail_decode_str(s):
    if s is None: return ''
    parts = _decode_header(s)
    result = ''
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or 'utf-8', errors='replace')
        else:
            result += str(part)
    return result



def _mail_get_plain(msg):
    text = ''
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get('Content-Disposition', ''))
            if ct == 'text/plain' and 'attachment' not in cd:
                charset = part.get_content_charset() or 'utf-8'
                try: text = part.get_payload(decode=True).decode(charset, errors='replace')
                except: pass
                break
    else:
        charset = msg.get_content_charset() or 'utf-8'
        try: text = msg.get_payload(decode=True).decode(charset, errors='replace')
        except: pass
    return text



def _mail_strip_quoted(text):
    lines = text.splitlines()
    clean = []
    for line in lines:
        s = line.strip()
        if s.startswith('>'): break
        if _re_mail.match(r'^On .+ wrote:$', s): break
        if '--- Original Message ---' in s: break
        if s.startswith('From:') and len(clean) > 2: break
        clean.append(line)
    return '\n'.join(clean).strip()



def _mail_extract_emp_id(subject, body):
    m = _re_mail.search(r'Ref[:\s]+([A-Za-z0-9_-]+)', subject or '')
    if m: return m.group(1).strip()
    m = _re_mail.search(r'Ref[:\s]+([A-Za-z0-9_-]+)', body or '')
    if m: return m.group(1).strip()
    return None



def _email_poll_loop():
    import time as _time
    print('[EmailPoller] Started — watching', _CHAT_SMTP_USER)
    while True:
        try:
            mail = _imap_lib.IMAP4_SSL(_IMAP_HOST, _IMAP_PORT)
            mail.login(_CHAT_SMTP_USER, _CHAT_SMTP_PASS)
            mail.select('INBOX')
            status, messages = mail.search(None, '(UNSEEN SUBJECT "[MIIM Chat]")')
            if status == 'OK':
                msg_ids = messages[0].split()
                for msg_id in msg_ids:
                    try:
                        _, msg_data = mail.fetch(msg_id, '(RFC822)')
                        if not msg_data or not isinstance(msg_data[0], tuple):
                            continue
                        raw: bytes = msg_data[0][1]  # type: ignore[index]
                        msg = _email_lib.message_from_bytes(raw)
                        subject = _mail_decode_str(msg.get('Subject', ''))
                        body = _mail_get_plain(msg)
                        # Skip our own outgoing alerts (tagged with X-MIIM-Alert: outgoing)
                        if msg.get('X-MIIM-Alert') == 'outgoing':
                            mail.store(msg_id, '+FLAGS', '\\Seen')
                            continue
                        emp_id = _mail_extract_emp_id(subject, body)
                        reply_text = _mail_strip_quoted(body)
                        if emp_id and reply_text:
                            conn2 = _chat_db()
                            row = conn2.execute(
                                'SELECT emp_name FROM chat_messages WHERE emp_id=? AND sender="user" ORDER BY id DESC LIMIT 1',
                                (emp_id,)
                            ).fetchone()
                            emp_name2 = row['emp_name'] if row else emp_id
                            ts2 = _ch_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            conn2.execute(
                                'INSERT INTO chat_messages (emp_id,emp_name,dept,role,sender,message,ts) VALUES (?,?,?,?,?,?,?)',
                                (emp_id, emp_name2, '', 'admin', 'bot', reply_text, ts2)
                            )
                            conn2.commit(); conn2.close()
                            print(f'[EmailPoller] ✅ Reply saved for {emp_id}')
                        mail.store(msg_id, '+FLAGS', '\\Seen')
                    except Exception as _ep:
                        print(f'[EmailPoller] msg error: {_ep}')
            mail.logout()
        except Exception as _e:
            print(f'[EmailPoller] IMAP error: {_e}')
        _time.sleep(_POLL_EVERY)


# ══════════════════════════════════════════════════════════════════
# ── DB ADMIN PANEL — /dbadmin  (Admin only) ──
# hrm.miim.co.in/dbadmin → admin login மட்டும் access
# ══════════════════════════════════════════════════════════════════

import sqlite3 as _dba_sqlite
import os as _dba_os

_DBA_BASE = _dba_os.path.dirname(_dba_os.path.abspath(__file__))

def _dba_find_databases():
    return sorted([f for f in _dba_os.listdir(_DBA_BASE) if f.endswith('.db')])

def _dba_get_path(db_name):
    safe = _dba_os.path.basename(db_name)
    path = _dba_os.path.join(_DBA_BASE, safe)
    return path if _dba_os.path.exists(path) else None

def _dba_is_admin():
    """Check admin via JWT token directly — bypasses get_current_user issues."""
    try:
        # Read token from Authorization header first
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        # Fallback: cookie (miim_token set by /api/login)
        if not token:
            token = request.cookies.get("miim_token", "")
        # Fallback: query param (for export download URLs)
        if not token:
            token = request.args.get("token", "")
        if not token:
            return False
        # Decode JWT directly with verify_token
        payload = verify_token(token)
        if not payload:
            return False
        role = (payload.get("role", "") or "").lower()
        name = (payload.get("username", "") or "").lower()
        return role == "admin" or name == "admin"
    except Exception as _e:
        print(f"[DBA] auth error: {_e}")
        return False

_DBA_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MIIM DB Admin</title>
<rect width='100' height='100' rx='16' fill='%23f97316'/><text y='.9em' font-size='80' x='10' font-weight='bold' fill='white'>M</text></svg>">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Exo+2:wght@300;400;500;600&display=swap');
  :root{--bg:#0f0f0f;--sur:#141414;--sur2:#1a1a1a;--brd:#2a2a2a;--acc:#f97316;--acc2:#fb923c;--acc-dim:#c2570f;--dan:#f74f6a;--ok:#22c55e;--txt:#e5e5e5;--mut:#888;--r:8px;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--bg);color:var(--txt);font-family:'Exo 2','Segoe UI',system-ui,sans-serif;font-size:14px;min-height:100vh;}
  /* Login */
  .login-wrap{display:flex;align-items:center;justify-content:center;min-height:100vh;background:var(--bg);}
  .login-box{background:var(--sur);border:1px solid var(--brd);border-radius:14px;padding:40px 36px;width:340px;text-align:center;box-shadow:0 0 40px rgba(249,115,22,.08);}
  .login-box h1{font-family:'Rajdhani',sans-serif;font-size:24px;font-weight:700;letter-spacing:2px;color:var(--acc);margin-bottom:6px;text-shadow:0 0 20px rgba(249,115,22,.4);}
  .login-box p{color:var(--mut);font-size:13px;margin-bottom:28px;}
  .login-box input{width:100%;background:#111;border:1px solid var(--brd);color:var(--txt);padding:11px 14px;border-radius:var(--r);font-size:14px;margin-bottom:12px;outline:none;transition:border-color .2s;}
  .login-box input:focus{border-color:var(--acc);box-shadow:0 0 0 2px rgba(249,115,22,.15);}
  .login-box button{width:100%;background:var(--acc);color:#fff;border:none;padding:11px;border-radius:var(--r);font-size:14px;font-weight:700;cursor:pointer;margin-top:4px;font-family:'Rajdhani',sans-serif;letter-spacing:1px;transition:background .2s,box-shadow .2s;}
  .login-box button:hover{background:var(--acc-dim);box-shadow:0 0 16px rgba(249,115,22,.4);}
  .err-msg{color:var(--dan);font-size:13px;margin-top:10px;display:none;}
  /* Header */
  .header{background:var(--sur);border-bottom:1px solid var(--brd);padding:0 24px;height:58px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;}
  .header h1{font-family:'Rajdhani',sans-serif;font-size:20px;font-weight:700;letter-spacing:2px;color:var(--acc);}
  .db-sel{background:#111;border:1px solid var(--brd);color:var(--txt);padding:7px 12px;border-radius:var(--r);font-size:13px;cursor:pointer;outline:none;transition:border-color .2s;}
  .db-sel:focus{border-color:var(--acc);}
  .badge{background:var(--acc);color:#fff;font-size:11px;padding:2px 8px;border-radius:999px;font-weight:700;}
  .logout-btn{margin-left:auto;background:var(--sur2);border:1px solid var(--brd);color:var(--mut);padding:6px 14px;border-radius:var(--r);cursor:pointer;font-size:13px;transition:all .2s;}
  .logout-btn:hover{border-color:var(--dan);color:var(--dan);}
  /* Layout */
  .layout{display:flex;height:calc(100vh - 58px);}
  .sidebar{width:200px;min-width:160px;background:var(--sur);border-right:1px solid var(--brd);overflow-y:auto;padding:12px 0;}
  .sidebar-title{font-size:11px;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:.08em;padding:0 16px 8px;}
  .tbl-item{padding:9px 16px;cursor:pointer;transition:background .15s;display:flex;align-items:center;gap:8px;color:var(--txt);font-size:13px;}
  .tbl-item:hover{background:var(--sur2);}
  .tbl-item.active{background:rgba(249,115,22,.12);border-left:3px solid var(--acc);color:var(--acc);font-weight:600;}
  /* Main */
  .main{flex:1;display:flex;flex-direction:column;overflow:hidden;}
  .toolbar{background:var(--sur);border-bottom:1px solid var(--brd);padding:10px 18px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
  .toolbar input,.toolbar select{background:#111;border:1px solid var(--brd);color:var(--txt);padding:7px 12px;border-radius:var(--r);font-size:13px;outline:none;transition:border-color .2s;}
  .toolbar input{width:220px;}
  .toolbar input:focus,.toolbar select:focus{border-color:var(--acc);}
  .btn{padding:7px 14px;border-radius:var(--r);border:none;cursor:pointer;font-size:13px;font-weight:600;transition:opacity .15s,transform .1s,box-shadow .15s;}
  .btn:hover{opacity:.85;transform:translateY(-1px);}
  .btn-ok{background:var(--acc);color:#fff;}
  .btn-ok:hover{box-shadow:0 0 12px rgba(249,115,22,.4);}
  .btn-ghost{background:var(--sur2);color:var(--txt);border:1px solid var(--brd);}
  .btn-ghost:hover{border-color:var(--acc);color:var(--acc);}
  .row-count{margin-left:auto;font-size:12px;color:var(--mut);}
  /* Table */
  .table-wrap{flex:1;overflow:auto;}
  table{width:100%;border-collapse:collapse;}
  thead{position:sticky;top:0;z-index:10;}
  th{background:#111;color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.08em;padding:10px 14px;text-align:left;border-bottom:1px solid var(--brd);white-space:nowrap;}
  td{padding:9px 14px;border-bottom:1px solid rgba(42,42,42,.6);vertical-align:middle;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  tr:hover td{background:rgba(249,115,22,.04);}
  .act{display:flex;gap:6px;white-space:nowrap;}
  .ic{background:none;border:1px solid var(--brd);border-radius:6px;color:var(--mut);cursor:pointer;padding:4px 8px;font-size:14px;transition:all .15s;}
  .ic:hover.ed{border-color:var(--acc);color:var(--acc);background:rgba(249,115,22,.1);}
  .ic:hover.sv{border-color:var(--ok);color:var(--ok);background:rgba(34,197,94,.1);}
  .ic:hover.dl{border-color:var(--dan);color:var(--dan);background:rgba(247,79,106,.1);}
  td input.ci{background:#111;border:1px solid var(--acc);color:var(--txt);border-radius:5px;padding:4px 8px;font-size:13px;width:100%;min-width:80px;}
  /* Pagination */
  .pg{background:var(--sur);border-top:1px solid var(--brd);padding:10px 18px;display:flex;align-items:center;gap:8px;}
  .pb{background:var(--sur2);border:1px solid var(--brd);color:var(--txt);padding:5px 12px;border-radius:var(--r);cursor:pointer;font-size:13px;transition:all .15s;}
  .pb:hover{border-color:var(--acc);color:var(--acc);}
  .pb.act{background:var(--acc);color:#fff;border-color:var(--acc);}
  .pi{color:var(--mut);font-size:12px;margin-left:8px;}
  /* Modal */
  .modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:100;align-items:center;justify-content:center;}
  .modal-bg.show{display:flex;}
  .modal{background:var(--sur);border:1px solid var(--brd);border-radius:12px;padding:24px;min-width:380px;max-width:90vw;max-height:85vh;overflow-y:auto;box-shadow:0 0 40px rgba(0,0,0,.6);}
  .modal h2{font-family:'Rajdhani',sans-serif;font-size:18px;font-weight:700;letter-spacing:1px;margin-bottom:16px;color:var(--acc);}
  .field{margin-bottom:14px;}
  .field label{display:block;font-size:11px;color:var(--mut);margin-bottom:5px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;}
  .field input{width:100%;background:#111;border:1px solid var(--brd);color:var(--txt);padding:9px 12px;border-radius:var(--r);font-size:13px;outline:none;transition:border-color .2s;}
  .field input:focus{border-color:var(--acc);box-shadow:0 0 0 2px rgba(249,115,22,.12);}
  .modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:20px;}
  /* Toast */
  #toast{position:fixed;bottom:24px;right:24px;background:var(--acc);color:#fff;padding:10px 18px;border-radius:var(--r);font-weight:600;font-size:13px;display:none;z-index:999;box-shadow:0 4px 20px rgba(249,115,22,.4);}
  #toast.err{background:var(--dan);color:#fff;box-shadow:0 4px 20px rgba(247,79,106,.4);}
  .empty{text-align:center;color:var(--mut);padding:60px 20px;font-size:15px;}
  .nv{color:var(--mut);font-style:italic;font-size:12px;}
  /* Nav Tabs */
  .nav-tabs{display:flex;gap:6px;align-items:center;margin-left:16px;}
  .nav-tab{padding:6px 16px;border-radius:var(--r);border:1px solid var(--brd);background:var(--sur2);color:var(--mut);cursor:pointer;font-size:13px;font-weight:600;transition:all .15s;}
  .nav-tab:hover{border-color:var(--acc);color:var(--acc);}
  .nav-tab.active{background:var(--acc);color:#fff;border-color:var(--acc);box-shadow:0 0 10px rgba(249,115,22,.3);}
  /* Backup Panel */
  #backupPanel{display:none;flex:1;overflow-y:auto;padding:24px;background:var(--bg);}
  .bk-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px;}
  .bk-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;}
  .bk-card{background:var(--sur);border:1px solid var(--brd);border-radius:10px;padding:18px;transition:border-color .2s;}
  .bk-card:hover{border-color:rgba(249,115,22,.3);}
  .bk-card-header{display:flex;align-items:center;gap:10px;margin-bottom:12px;}
  .bk-date{font-size:15px;font-weight:700;color:var(--acc);font-family:'Rajdhani',sans-serif;letter-spacing:1px;}
  .bk-files{display:flex;flex-direction:column;gap:8px;}
  .bk-file{display:flex;align-items:center;gap:10px;background:#111;border-radius:6px;padding:8px 12px;border:1.5px solid transparent;transition:all .15s;}
  .bk-file.selected{border-color:var(--acc);background:rgba(249,115,22,.08);}
  .bk-cb{width:16px;height:16px;accent-color:var(--acc);cursor:pointer;flex-shrink:0;}
  .bk-info{flex:1;}
  .bk-fname{font-size:13px;color:var(--txt);font-weight:600;}
  .bk-size{font-size:11px;color:var(--mut);margin-left:6px;}
  .bk-dl{background:var(--acc);color:#fff;border:none;border-radius:6px;padding:5px 12px;cursor:pointer;font-size:12px;font-weight:600;transition:all .15s;flex-shrink:0;}
  .bk-dl:hover{background:var(--acc-dim);box-shadow:0 0 8px rgba(249,115,22,.4);}
  .bk-empty{text-align:center;color:var(--mut);padding:60px 20px;font-size:15px;}
  .bk-refresh{background:var(--sur2);border:1px solid var(--brd);color:var(--txt);padding:7px 14px;border-radius:var(--r);cursor:pointer;font-size:13px;font-weight:600;transition:all .15s;}
  .bk-refresh:hover{border-color:var(--acc);color:var(--acc);}
  .bk-count{font-size:12px;color:var(--mut);}
  .bk-export-btn{background:var(--acc);color:#fff;border:none;border-radius:var(--r);padding:7px 16px;cursor:pointer;font-size:13px;font-weight:700;display:none;transition:all .15s;}
  .bk-export-btn:hover{background:var(--acc-dim);box-shadow:0 0 12px rgba(249,115,22,.4);}
  .bk-sel-count{font-size:12px;color:var(--acc);font-weight:600;display:none;}
</style>
</head>
<body>

<!-- LOGIN PAGE -->
<div class="login-wrap" id="loginPage">
  <div class="login-box">
    <h1>⚡ MIIM DB Admin</h1>
    <p>Admin credentials only have access</p>
    <input type="text" id="loginUser" placeholder="User ID / Username" autocomplete="username">
    <input type="password" id="loginPass" placeholder="Password" autocomplete="current-password"
           onkeydown="if(event.key==='Enter')doLogin()">
    <button onclick="doLogin()">Login →</button>
    <div class="err-msg" id="loginErr">Invalid credentials or not admin</div>
  </div>
</div>

<!-- MAIN PANEL (hidden until login) -->
<div id="mainPanel" style="display:none;flex-direction:column;height:100vh;">
  <div class="header">
    <h1>⚡ MIIM DB Admin</h1>
    <select class="db-sel" id="dbSelect" onchange="switchDB()"></select>
    <span class="badge" id="dbBadge">—</span>
    <div class="nav-tabs">
      <button class="nav-tab active" id="tabDB" onclick="showTab('db')">🗄 Database</button>
      <button class="nav-tab" id="tabBK" onclick="showTab('backup')">💾 Backups</button>
    </div>
    <button class="logout-btn" onclick="doLogout()">Logout</button>
  </div>
  <!-- DB View -->
  <div class="layout" id="dbView" style="flex:1;">
    <div class="sidebar">
      <div class="sidebar-title">Tables</div>
      <div id="tableList"></div>
    </div>
    <div class="main">
      <div class="toolbar">
        <select id="filterCol" class="db-sel" style="width:130px"></select>
        <input id="filterVal" placeholder="Search…" oninput="applyFilter()">
        <button class="btn btn-ghost" onclick="clearFilter()">✕ Clear</button>
        <button class="btn btn-ok" onclick="openAddModal()">+ Add Row</button>
        <span class="row-count" id="rowCount"></span>
        <button class="btn btn-ghost" style="margin-left:auto" onclick="exportTable('csv')" title="Export CSV">⬇ CSV</button>
        <button class="btn btn-ghost" onclick="exportTable('excel')" title="Export Excel">⬇ Excel</button>
      </div>
      <div class="table-wrap" id="tableWrap">
        <div class="empty">← Select a table from the left</div>
      </div>
      <div class="pg" id="pagination" style="display:none"></div>
    </div>
  </div>
  <!-- Backup View -->
  <div id="backupPanel">
    <div class="bk-toolbar">
      <h2 style="font-size:18px;color:var(--acc);">💾 Backup History</h2>
      <button class="bk-refresh" onclick="loadBackups()">🔄 Refresh</button>
      <button class="bk-refresh" onclick="bkSelectAll()">☑ Select All</button>
      <button class="bk-refresh" onclick="bkClearAll()">✕ Clear</button>
      <span class="bk-sel-count" id="bkSelCount"></span>
      <button class="bk-export-btn" id="bkExportBtn" onclick="bkExportExcel()">📊 Export Selected to Excel</button>
      <span class="bk-count" id="bkCount"></span>
    </div>
    <div class="bk-grid" id="bkGrid">
      <div class="bk-empty">Loading backups…</div>
    </div>
  </div>
</div>

<div class="modal-bg" id="addModal">
  <div class="modal">
    <h2>➕ Add New Row</h2>
    <div id="addFields"></div>
    <div class="modal-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-ok" onclick="submitAdd()">Insert</button>
    </div>
  </div>
</div>
<div id="toast"></div>

<script>
let _token = sessionStorage.getItem('dba_token') || '';
let currentDB = '', currentTable = '', allRows = [], columns = [], page = 1;
const PER_PAGE = 50;
let editingRow = null;

// ── Auth ──────────────────────────────────────────────────────────────────────
async function doLogin() {
  const u = document.getElementById('loginUser').value.trim();
  const p = document.getElementById('loginPass').value.trim();
  if (!u || !p) return;
  const btn = document.querySelector('.login-box button');
  if (btn) { btn.textContent = 'Logging in…'; btn.disabled = true; }
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      credentials: 'include',
      body: JSON.stringify({username: u, password: p})
    });
    if (!res.ok && res.status !== 401) { showErr('Server error ' + res.status); return; }
    const d = await res.json();
    const role = (d.role || '').toLowerCase();
    const userRole = (d.user && d.user.role || '').toLowerCase();
    const isAdmin = role === 'admin' || userRole === 'admin';
    if (d.success && isAdmin) {
      _token = d.token;
      sessionStorage.setItem('dba_token', _token);
      showPanel();
    } else if (d.success && !isAdmin) {
      showErr('Access denied — Admin only');
    } else {
      showErr(d.message || 'Invalid credentials');
    }
  } catch(err) {
    showErr('Network error: ' + err.message);
  } finally {
    if (btn) { btn.textContent = 'Login →'; btn.disabled = false; }
  }
}

function showErr(msg) {
  const e = document.getElementById('loginErr');
  e.textContent = msg; e.style.display = 'block';
  setTimeout(() => e.style.display = 'none', 3000);
}

function doLogout() {
  _token = ''; sessionStorage.removeItem('dba_token');
  document.getElementById('mainPanel').style.display = 'none';
  document.getElementById('loginPage').style.display = 'flex';
}

function authHeaders() {
  return {'Content-Type':'application/json','Authorization':'Bearer '+_token};
}

async function showPanel() {
  document.getElementById('loginPage').style.display = 'none';
  document.getElementById('mainPanel').style.display = 'flex';
  await init();
}

// Auto-login if token exists
if (_token) {
  showPanel();
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  const res = await fetch('/dbadmin/api/databases', {headers: authHeaders(), credentials: 'include'});
  if (res.status === 401 || res.status === 403) {
    const errData = await res.json().catch(() => ({}));
    console.error('[DBA] Auth failed:', res.status, errData);
    showErr('Session expired — please login again');
    doLogout(); return;
  }
  const dbs = await res.json();
  const sel = document.getElementById('dbSelect');
  sel.innerHTML = dbs.map(d => `<option value="${d}">${d}</option>`).join('');
  if (dbs.length) { currentDB = dbs[0]; await loadTables(); }
}

// ── Tab switching ─────────────────────────────────────────────────────────────
function showTab(tab) {
  if (tab === 'db') {
    document.getElementById('dbView').style.display = 'flex';
    document.getElementById('backupPanel').style.display = 'none';
    document.getElementById('tabDB').classList.add('active');
    document.getElementById('tabBK').classList.remove('active');
    document.getElementById('dbSelect').style.display = '';
    document.getElementById('dbBadge').style.display = '';
  } else {
    document.getElementById('dbView').style.display = 'none';
    document.getElementById('backupPanel').style.display = 'block';
    document.getElementById('tabDB').classList.remove('active');
    document.getElementById('tabBK').classList.add('active');
    document.getElementById('dbSelect').style.display = 'none';
    document.getElementById('dbBadge').style.display = 'none';
    loadBackups();
  }
}

// ── Backup ────────────────────────────────────────────────────────────────────
let _bkData = []; // store loaded backup data

async function loadBackups() {
  document.getElementById('bkGrid').innerHTML = '<div class="bk-empty">Loading…</div>';
  const res = await fetch('/dbadmin/api/backups', {headers: authHeaders()});
  if (!res.ok) { document.getElementById('bkGrid').innerHTML = '<div class="bk-empty">Failed to load backups.</div>'; return; }
  const data = await res.json();
  _bkData = (data.backups || []).slice().reverse(); // newest first
  document.getElementById('bkCount').textContent = `${_bkData.length} backup(s) found`;
  if (!_bkData.length) {
    document.getElementById('bkGrid').innerHTML = '<div class="bk-empty">No backups found yet. Backups are created automatically every 24 hours.</div>';
    return;
  }
  document.getElementById('bkGrid').innerHTML = _bkData.map((bk, bi) => `
    <div class="bk-card">
      <div class="bk-card-header">
        <span class="bk-date">📅 ${bk.folder}</span>
      </div>
      <div class="bk-files">
        ${bk.files.map((f, fi) => `
          <div class="bk-file" id="bkf_${bi}_${fi}">
            <input type="checkbox" class="bk-cb" id="bkcb_${bi}_${fi}"
              onchange="bkToggle(${bi},${fi})"
              data-folder="${bk.folder}" data-file="${f.name}" data-date="${bk.folder}">
            <div class="bk-info">
              <span class="bk-fname">🗄 ${f.name}</span>
              <span class="bk-size">${f.size_kb} KB</span>
            </div>
            <button class="bk-dl" onclick="downloadBackup('${bk.folder}','${f.name}')">⬇ Download</button>
          </div>
        `).join('')}
        ${!bk.files.length ? '<span style="color:var(--mut);font-size:12px">No files</span>' : ''}
      </div>
    </div>
  `).join('');
  updateBkSelUI();
}

function bkToggle(bi, fi) {
  const cb = document.getElementById(`bkcb_${bi}_${fi}`);
  const row = document.getElementById(`bkf_${bi}_${fi}`);
  row.classList.toggle('selected', cb.checked);
  updateBkSelUI();
}

function bkSelectAll() {
  document.querySelectorAll('.bk-cb').forEach(cb => {
    cb.checked = true;
    const id = cb.id.replace('bkcb_','bkf_');
    document.getElementById(id)?.classList.add('selected');
  });
  updateBkSelUI();
}

function bkClearAll() {
  document.querySelectorAll('.bk-cb').forEach(cb => {
    cb.checked = false;
    const id = cb.id.replace('bkcb_','bkf_');
    document.getElementById(id)?.classList.remove('selected');
  });
  updateBkSelUI();
}

function updateBkSelUI() {
  const selected = document.querySelectorAll('.bk-cb:checked');
  const countEl  = document.getElementById('bkSelCount');
  const btnEl    = document.getElementById('bkExportBtn');
  if (selected.length > 0) {
    countEl.textContent = `${selected.length} file(s) selected`;
    countEl.style.display = 'inline';
    btnEl.style.display = 'inline-block';
  } else {
    countEl.style.display = 'none';
    btnEl.style.display = 'none';
  }
}

async function bkExportExcel() {
  const selected = document.querySelectorAll('.bk-cb:checked');
  if (!selected.length) { showToast('Select at least one file', true); return; }
  const files = Array.from(selected).map(cb => ({
    folder: cb.dataset.folder,
    file: cb.dataset.file,
    date: cb.dataset.date
  }));
  showToast('Preparing Excel export…');
  const res = await fetch('/dbadmin/api/backup-export-excel', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({files})
  });
  if (!res.ok) { const e = await res.json(); showToast(e.error || 'Export failed', true); return; }
  const blob = await res.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'backup_export.xlsx'; a.click();
  URL.revokeObjectURL(url);
  showToast('Excel downloaded! ✓');
}

async function downloadBackup(folder, filename) {
  const url = `/dbadmin/api/backup-download?folder=${encodeURIComponent(folder)}&file=${encodeURIComponent(filename)}&token=${encodeURIComponent(_token)}`;
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
}

// ── Export — filtered rows மட்டும் download ஆகும் ──────────────────────────
function getFilteredRows() {
  const col = document.getElementById('filterCol').value;
  const val = document.getElementById('filterVal').value.toLowerCase();
  if (!val) return allRows;
  const ci = col ? columns.indexOf(col) : -1;
  return allRows.filter(row =>
    ci >= 0 ? String(row[ci]??'').toLowerCase().includes(val)
            : row.some(cell => String(cell??'').toLowerCase().includes(val))
  );
}

function exportTable(fmt) {
  if (!currentTable) { showToast('Select a table first', true); return; }
  const rows = getFilteredRows();
  if (!rows.length) { showToast('No rows to export', true); return; }
  const filterCol = document.getElementById('filterCol').value;
  const filterVal = document.getElementById('filterVal').value;
  const isFiltered = !!filterVal;

  if (fmt === 'csv') {
    // Client-side CSV — filtered rows மட்டும்
    const escape = v => {
      const s = v === null || v === undefined ? '' : String(v);
      return s.includes(',') || s.includes('"') || s.includes('\\n')
        ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const lines = [columns.map(escape).join(',')];
    rows.forEach(r => lines.push(r.map(escape).join(',')));
    const blob = new Blob([lines.join('\\r\\n')], {type: 'text/csv;charset=utf-8;'});
    const fname = isFiltered
      ? `${currentDB.replace('.db','')}_${currentTable}_filtered.csv`
      : `${currentDB.replace('.db','')}_${currentTable}.csv`;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = fname; a.click();
    URL.revokeObjectURL(a.href);
    showToast(`CSV downloaded (${rows.length} rows) ✓`);

  } else if (fmt === 'excel') {
    // Server-side Excel — filtered row data POST பண்றோம்
    const fname = isFiltered
      ? `${currentDB.replace('.db','')}_${currentTable}_filtered.xlsx`
      : `${currentDB.replace('.db','')}_${currentTable}.xlsx`;
    fetch('/dbadmin/api/export-filtered', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ db: currentDB, table: currentTable, columns, rows, filename: fname })
    }).then(res => {
      if (!res.ok) return res.json().then(e => { throw new Error(e.error || 'Export failed'); });
      return res.blob();
    }).then(blob => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = fname; a.click();
      URL.revokeObjectURL(a.href);
      showToast(`Excel downloaded (${rows.length} rows) ✓`);
    }).catch(e => showToast(e.message, true));
  }
}

async function switchDB() {
  currentDB = document.getElementById('dbSelect').value;
  currentTable = '';
  document.getElementById('tableWrap').innerHTML = '<div class="empty">← Select a table from the left</div>';
  document.getElementById('pagination').style.display = 'none';
  document.getElementById('rowCount').textContent = '';
  await loadTables();
}

async function loadTables() {
  const res = await fetch(`/dbadmin/api/tables?db=${encodeURIComponent(currentDB)}`, {headers: authHeaders()});
  const data = await res.json();
  document.getElementById('dbBadge').textContent = `${data.tables.length} tables`;
  const list = document.getElementById('tableList');
  list.innerHTML = data.tables.map(t =>
    `<div class="tbl-item" id="ti_${t}" onclick="selectTable('${t}')">📋 ${t}</div>`
  ).join('');
  if (data.tables.length) selectTable(data.tables[0]);
}

async function selectTable(name) {
  currentTable = name; page = 1;
  document.querySelectorAll('.tbl-item').forEach(el => el.classList.remove('active'));
  const el = document.getElementById('ti_' + name);
  if (el) el.classList.add('active');
  clearFilter(false);
  await fetchRows();
}

// ── Data ──────────────────────────────────────────────────────────────────────
async function fetchRows() {
  if (!currentTable) return;
  const res = await fetch(`/dbadmin/api/rows?db=${encodeURIComponent(currentDB)}&table=${encodeURIComponent(currentTable)}`, {headers: authHeaders()});
  const data = await res.json();
  if (data.error) { showToast(data.error, true); return; }
  columns = data.columns; allRows = data.rows;
  const sel = document.getElementById('filterCol');
  sel.innerHTML = '<option value="">All columns</option>' + columns.map(c => `<option value="${c}">${c}</option>`).join('');
  renderTable(allRows);
}

function applyFilter() {
  const col = document.getElementById('filterCol').value;
  const val = document.getElementById('filterVal').value.toLowerCase();
  if (!val) { renderTable(allRows); return; }
  const ci = col ? columns.indexOf(col) : -1;
  const filtered = allRows.filter(row =>
    ci >= 0 ? String(row[ci]??'').toLowerCase().includes(val)
            : row.some(cell => String(cell??'').toLowerCase().includes(val))
  );
  page = 1; renderTable(filtered);
}

function clearFilter(doRender = true) {
  document.getElementById('filterVal').value = '';
  document.getElementById('filterCol').value = '';
  if (doRender) renderTable(allRows);
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderTable(rows) {
  document.getElementById('rowCount').textContent = `${rows.length} rows`;
  const totalPages = Math.max(1, Math.ceil(rows.length / PER_PAGE));
  if (page > totalPages) page = totalPages;
  const slice = rows.slice((page-1)*PER_PAGE, page*PER_PAGE);
  if (!columns.length) {
    document.getElementById('tableWrap').innerHTML = '<div class="empty">No data</div>';
    document.getElementById('pagination').style.display = 'none'; return;
  }
  const thead = `<thead><tr><th style="width:90px">Actions</th>${columns.map(c=>`<th>${c}</th>`).join('')}</tr></thead>`;
  const tbody = slice.map((row, i) => {
    const idx = (page-1)*PER_PAGE + i;
    const cells = columns.map((c,ci) => {
      const raw = row[ci];
      if (raw === null) return '<td id="cell_' + idx + '_' + ci + '" title="NULL"><span class="nv">NULL</span></td>';
      const rawStr = String(raw);
      const isHtml = /<[a-z][\\s\\S]*>/i.test(rawStr);
      const display = isHtml ? rawStr.replace(/<[^>]*>/g, ' ').replace(/\\s+/g, ' ').trim() : rawStr;
      const titleTxt = esc(display.substring(0, 300));
      const style = isHtml ? 'color:var(--mut);font-style:italic;' : '';
      return '<td id="cell_' + idx + '_' + ci + '" title="' + titleTxt + '" style="' + style + '">' + esc(display) + '</td>';
    }).join('');
    return `<tr id="row_${idx}">
      <td><div class="act">
        <button class="ic ed" id="eb_${idx}" onclick="startEdit(${idx})" title="Edit">✏</button>
        <button class="ic sv" id="sb_${idx}" onclick="saveEdit(${idx})" style="display:none" title="Save">✓</button>
        <button class="ic" id="cb_${idx}" onclick="cancelEdit(${idx})" style="display:none" title="Cancel">✕</button>
        <button class="ic dl" onclick="deleteRow(${idx})" title="Delete">🗑</button>
      </div></td>${cells}</tr>`;
  }).join('');
  document.getElementById('tableWrap').innerHTML = `<table>${thead}<tbody>${tbody}</tbody></table>`;
  const pg = document.getElementById('pagination');
  if (totalPages <= 1) { pg.style.display='none'; return; }
  pg.style.display = 'flex';
  let html = `<button class="pb" onclick="goPage(${page-1})" ${page===1?'disabled':''}>‹</button>`;
  for (let p2=1;p2<=totalPages;p2++) {
    if (totalPages>10 && Math.abs(p2-page)>2 && p2!==1 && p2!==totalPages) {
      if (p2===2||p2===totalPages-1) html+='<span style="color:var(--mut);padding:0 4px">…</span>'; continue;
    }
    html+=`<button class="pb ${p2===page?'act':''}" onclick="goPage(${p2})">${p2}</button>`;
  }
  html+=`<button class="pb" onclick="goPage(${page+1})" ${page===totalPages?'disabled':''}>›</button><span class="pi">Page ${page} of ${totalPages}</span>`;
  pg.innerHTML = html;
}

function goPage(p) { page=p; applyFilter(); }

// ── Edit ──────────────────────────────────────────────────────────────────────
function startEdit(idx) {
  if (editingRow!==null) cancelEdit(editingRow);
  editingRow=idx;
  document.getElementById('eb_'+idx).style.display='none';
  document.getElementById('sb_'+idx).style.display='';
  document.getElementById('cb_'+idx).style.display='';
  const row=allRows[idx];
  columns.forEach((c,ci)=>{
    const cell=document.getElementById(`cell_${idx}_${ci}`);
    if(cell) cell.innerHTML=`<input class="ci" id="inp_${idx}_${ci}" value="${ea(String(row[ci]??''))}">`;
  });
}

function cancelEdit(idx) {
  editingRow=null;
  document.getElementById('eb_'+idx).style.display='';
  document.getElementById('sb_'+idx).style.display='none';
  document.getElementById('cb_'+idx).style.display='none';
  const row=allRows[idx];
  columns.forEach((c,ci)=>{
    const cell=document.getElementById(`cell_${idx}_${ci}`);
    if(cell) cell.innerHTML=row[ci]===null?'<span class="nv">NULL</span>':esc(String(row[ci]));
  });
}

async function saveEdit(idx) {
  const oldRow=allRows[idx];
  const newRow=columns.map((c,ci)=>{const i=document.getElementById(`inp_${idx}_${ci}`);return i?i.value:oldRow[ci];});
  const payload={db:currentDB,table:currentTable,old_row:oldRow,new_values:{}};
  columns.forEach((c,ci)=>{payload.new_values[c]=newRow[ci];});
  const res=await fetch('/dbadmin/api/update',{method:'POST',headers:authHeaders(),body:JSON.stringify(payload)});
  const data=await res.json();
  if(data.error){showToast(data.error,true);return;}
  showToast('Saved! ✓');
  allRows[idx]=newRow; editingRow=null; renderTable(allRows);
}

// ── Delete ────────────────────────────────────────────────────────────────────
async function deleteRow(idx) {
  if(!confirm('Delete this row?')) return;
  const row=allRows[idx];
  const res=await fetch('/dbadmin/api/delete',{method:'POST',headers:authHeaders(),body:JSON.stringify({db:currentDB,table:currentTable,row})});
  const data=await res.json();
  if(data.error){showToast(data.error,true);return;}
  showToast('Deleted!');
  allRows.splice(idx,1); renderTable(allRows);
}

// ── Add ───────────────────────────────────────────────────────────────────────
function openAddModal() {
  if(!currentTable){showToast('Table select பண்ணுங்க',true);return;}
  document.getElementById('addFields').innerHTML=columns.map(c=>`<div class="field"><label>${c}</label><input id="add_${c}" placeholder="${c}"></div>`).join('');
  document.getElementById('addModal').classList.add('show');
}
function closeModal(){document.getElementById('addModal').classList.remove('show');}
async function submitAdd() {
  const values={};
  columns.forEach(c=>{values[c]=document.getElementById('add_'+c)?.value??'';});
  const res=await fetch('/dbadmin/api/insert',{method:'POST',headers:authHeaders(),body:JSON.stringify({db:currentDB,table:currentTable,values})});
  const data=await res.json();
  if(data.error){showToast(data.error,true);return;}
  showToast('Row added! ✓'); closeModal(); await fetchRows();
}

// ── Utils ─────────────────────────────────────────────────────────────────────
function showToast(msg,err=false){
  const t=document.getElementById('toast');
  t.textContent=msg; t.className=err?'err':'';
  t.style.display='block'; setTimeout(()=>t.style.display='none',2500);
}
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function ea(s){return s.replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
document.getElementById('addModal').addEventListener('click',e=>{if(e.target.id==='addModal')closeModal();});
</script>
</body>
</html>"""


def _dba_check():
    """Decorator helper — returns 403 if not admin."""
    from flask import jsonify as _j
    if not _dba_is_admin():
        return _j({'error': 'Admin access only'}), 403
    return None


@app.route('/dbadmin')
@app.route('/dbadmin/')
def dbadmin_panel():
    from flask import Response
    return Response(_DBA_HTML, mimetype='text/html; charset=utf-8')


@app.route('/dbadmin/api/databases')
def dbadmin_databases():
    err = _dba_check()
    if err: return err
    return jsonify(_dba_find_databases())


def _dba_validate_table(con, table):
    """Return True only if table exists in sqlite_master — prevents SQL injection via table name."""
    valid = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    return table in valid


@app.route('/dbadmin/api/tables')
def dbadmin_tables():
    err = _dba_check()
    if err: return err
    db_name = request.args.get('db', '')
    path = _dba_get_path(db_name)
    if not path:
        return jsonify({'tables': [], 'error': 'DB not found'})
    try:
        con = _dba_sqlite.connect(path)
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        con.close()
        return jsonify({'tables': tables})
    except Exception as e:
        return jsonify({'tables': [], 'error': str(e)})


@app.route('/dbadmin/api/rows')
def dbadmin_rows():
    err = _dba_check()
    if err: return err
    db_name = request.args.get('db', '')
    table   = request.args.get('table', '')
    path = _dba_get_path(db_name)
    if not path:
        return jsonify({'error': 'DB not found'})
    try:
        con = _dba_sqlite.connect(path)
        if not _dba_validate_table(con, table):
            con.close()
            return jsonify({'error': 'Invalid table name'}), 400
        cur = con.execute(f'SELECT * FROM "{table}"')
        cols = [d[0] for d in cur.description]
        rows = [list(r) for r in cur.fetchall()]
        con.close()
        return jsonify({'columns': cols, 'rows': rows})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/dbadmin/api/update', methods=['POST'])
def dbadmin_update():
    err = _dba_check()
    if err: return err
    data     = request.json
    path     = _dba_get_path(data.get('db', ''))
    table    = data.get('table', '')
    old_row  = data.get('old_row', [])
    new_vals = data.get('new_values', {})
    if not path: return jsonify({'error': 'DB not found'})
    try:
        con  = _dba_sqlite.connect(path)
        if not _dba_validate_table(con, table):
            con.close()
            return jsonify({'error': 'Invalid table name'}), 400
        cols = [d[0] for d in con.execute(f'SELECT * FROM "{table}" LIMIT 0').description]
        set_c   = ', '.join([f'"{c}" = ?' for c in cols])
        where_c = ' AND '.join([f'"{c}" IS ?' for c in cols])
        con.execute(f'UPDATE "{table}" SET {set_c} WHERE {where_c}', [new_vals.get(c) for c in cols] + old_row)
        con.commit(); con.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/dbadmin/api/delete', methods=['POST'])
def dbadmin_delete():
    err = _dba_check()
    if err: return err
    data  = request.json
    path  = _dba_get_path(data.get('db', ''))
    table = data.get('table', '')
    row   = data.get('row', [])
    if not path: return jsonify({'error': 'DB not found'})
    try:
        con  = _dba_sqlite.connect(path)
        if not _dba_validate_table(con, table):
            con.close()
            return jsonify({'error': 'Invalid table name'}), 400
        cols = [d[0] for d in con.execute(f'SELECT * FROM "{table}" LIMIT 0').description]
        where_c = ' AND '.join([f'"{c}" IS ?' for c in cols])
        con.execute(f'DELETE FROM "{table}" WHERE {where_c}', row)
        con.commit(); con.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/dbadmin/api/insert', methods=['POST'])
def dbadmin_insert():
    err = _dba_check()
    if err: return err
    data   = request.json
    path   = _dba_get_path(data.get('db', ''))
    table  = data.get('table', '')
    values = data.get('values', {})
    if not path: return jsonify({'error': 'DB not found'})
    try:
        con  = _dba_sqlite.connect(path)
        if not _dba_validate_table(con, table):
            con.close()
            return jsonify({'error': 'Invalid table name'}), 400
        cols = list(values.keys())
        con.execute(
            f'INSERT INTO "{table}" ({", ".join([f"{chr(34)}{c}{chr(34)}" for c in cols])}) VALUES ({", ".join(["?" for _ in cols])})',
            [values[c] for c in cols]
        )
        con.commit(); con.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)})
# ══════════════════════════════════════════════════════════════════
# EXPORT API — Table → CSV / Excel / Full DB download
# ══════════════════════════════════════════════════════════════════
# Usage (Admin login வேணும்):
#   CSV  : /dbadmin/api/export?db=miim_hr.db&table=employees&format=csv
#   Excel: /dbadmin/api/export?db=miim_hr.db&table=employees&format=excel
#   DB   : /dbadmin/api/export-db?db=miim_hr.db
# ══════════════════════════════════════════════════════════════════

import csv as _csv_mod
import io as _io_mod

@app.route('/dbadmin/api/export')
def dbadmin_export():
    """Export any table as CSV or Excel. Admin only."""
    err = _dba_check()
    if err: return err

    db_name = request.args.get('db', '')
    table   = request.args.get('table', '')
    fmt     = request.args.get('format', 'csv').lower()

    path = _dba_get_path(db_name)
    if not path:
        return jsonify({'error': 'DB not found'}), 404

    try:
        con  = _dba_sqlite.connect(path)
        cur  = con.execute(f'SELECT * FROM "{table}"')
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        con.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    filename_base = f"{db_name.replace('.db', '')}_{table}"

    # ── CSV ──────────────────────────────────────────────────────
    if fmt == 'csv':
        from flask import Response as _FResp
        output = _io_mod.StringIO()
        writer = _csv_mod.writer(output)
        writer.writerow(cols)
        writer.writerows(rows)
        output.seek(0)
        return _FResp(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename_base}.csv"'}
        )

    # ── Excel ─────────────────────────────────────────────────────
    elif fmt == 'excel':
        import openpyxl as _xl  # type: ignore[import]
        from openpyxl.styles import Font, PatternFill, Alignment  # type: ignore[import]
        from openpyxl.utils import get_column_letter as _gcl  # type: ignore[import]
        from flask import send_file as _sf_xl  # type: ignore[import]
        wb = _xl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = table[:31]

        header_fill = PatternFill("solid", fgColor="F97316")
        header_font = Font(bold=True, color="FFFFFF")
        ws.append(cols)
        for cell in ws[1]:
            cell.fill      = header_fill
            cell.font      = header_font
            cell.alignment = Alignment(horizontal='center')

        for row in rows:
            ws.append([str(v) if v is not None else '' for v in row])

        for idx, col in enumerate(ws.columns, start=1):
            max_len = max((len(str(cell.value or '')) for cell in col), default=10)
            ws.column_dimensions[_gcl(idx)].width = min(max_len + 4, 50)

        buf = _io_mod.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return _sf_xl(  # type: ignore[return-value]
            buf,
            as_attachment=True,
            download_name=f"{filename_base}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    else:
        return jsonify({'error': 'format must be csv or excel'}), 400


@app.route('/dbadmin/api/export-db')
def dbadmin_export_db():
    """Download full .db file. Admin only."""
    err = _dba_check()
    if err: return err

    db_name = request.args.get('db', '')
    path    = _dba_get_path(db_name)
    if not path:
        return jsonify({'error': 'DB not found'}), 404

    from flask import send_file as _sf_db  # type: ignore[import]
    return _sf_db(  # type: ignore[return-value]
        path,
        as_attachment=True,
        download_name=db_name,
        mimetype='application/octet-stream'
    )


# ══════════════════════════════════════════════════════════════════


@app.route('/dbadmin/api/export-filtered', methods=['POST'])
def dbadmin_export_filtered():
    """Export filtered rows as Excel. Admin only. Rows sent from frontend (already filtered)."""
    err = _dba_check()
    if err: return err
    data     = request.json or {}
    columns  = data.get('columns', [])
    rows     = data.get('rows', [])
    table    = data.get('table', 'export')
    filename = data.get('filename', f'{table}_filtered.xlsx')
    import openpyxl as _xl  # type: ignore[import]
    from openpyxl.styles import Font, PatternFill, Alignment  # type: ignore[import]
    from openpyxl.utils import get_column_letter as _gcl  # type: ignore[import]
    wb = _xl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = table[:31]
    header_fill = PatternFill("solid", fgColor="F97316")
    header_font = Font(bold=True, color="FFFFFF")
    ws.append(columns)
    for cell in ws[1]:
        cell.fill      = header_fill
        cell.font      = header_font
        cell.alignment = Alignment(horizontal='center')
    for row in rows:
        ws.append([str(v) if v is not None else '' for v in row])
    for idx, col in enumerate(ws.columns, start=1):
        max_len = max((len(str(cell.value or '')) for cell in col), default=10)
        ws.column_dimensions[_gcl(idx)].width = min(max_len + 4, 50)
    buf = _io_mod.BytesIO()
    wb.save(buf)
    buf.seek(0)
    from flask import send_file as _sf_filt  # type: ignore[import]
    return _sf_filt(  # type: ignore[return-value]
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# AUTO BACKUP — Daily SQLite DB backup with auto-cleanup
# ══════════════════════════════════════════════════════════════════
# Manual run : python app.py → background-ல auto start ஆகும்
# Backup location: <project>/backups/YYYY-MM-DD_HH-MM/
# 30 days-க்கு மேல பழைய backups auto delete ஆகும்
# ══════════════════════════════════════════════════════════════════

import shutil  as _shutil
import glob    as _glob

_BACKUP_BASE_DIR  = _dba_os.path.dirname(_dba_os.path.abspath(__file__))
_BACKUP_DIR       = _dba_os.path.join(_BACKUP_BASE_DIR, 'backups')
_BACKUP_DBS       = ['miim_hr.db', 'miim_chat.db']
_BACKUP_KEEP_DAYS = 30

def _run_backup():
    """Backup all DB files into backups/YYYY-MM-DD/ folder. Runs once per day."""
    import logging as _log
    _log.basicConfig(
        filename=_dba_os.path.join(_BACKUP_BASE_DIR, 'backup.log'),
        level=_log.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    try:
        today   = datetime.datetime.now().strftime('%Y-%m-%d')
        day_dir = _dba_os.path.join(_BACKUP_DIR, today)

        # Already backed up today — skip
        if _dba_os.path.exists(day_dir):
            return

        _dba_os.makedirs(day_dir, exist_ok=True)

        for db_file in _BACKUP_DBS:
            src = _dba_os.path.join(_BACKUP_BASE_DIR, db_file)
            if not _dba_os.path.exists(src):
                _log.warning(f"Backup skip (not found): {db_file}")
                continue
            dst = _dba_os.path.join(day_dir, db_file)
            _shutil.copy2(src, dst)
            size_kb = _dba_os.path.getsize(dst) // 1024
            _log.info(f"Backed up: {db_file} ({size_kb} KB) → {dst}")

        # Cleanup old backups
        cutoff   = datetime.datetime.now() - datetime.timedelta(days=_BACKUP_KEEP_DAYS)
        old_dirs = _glob.glob(_dba_os.path.join(_BACKUP_DIR, '????-??-??'))
        for d in old_dirs:
            try:
                folder_dt = datetime.datetime.strptime(_dba_os.path.basename(d), '%Y-%m-%d')
                if folder_dt < cutoff:
                    _shutil.rmtree(d)
                    _log.info(f"Deleted old backup: {d}")
            except Exception:
                pass

    except Exception as e:
        import logging as _log2
        _log2.error(f"Backup error: {e}")

def _backup_loop():
    """Check every hour — run backup once per day."""
    import time
    while True:
        _run_backup()
        time.sleep(3600)  # Check every 1 hour (but backup runs only once/day)


@app.route('/dbadmin/api/backup-export-excel', methods=['POST'])
def dbadmin_backup_export_excel():
    """Export selected backup DB tables to a single Excel file. Admin only."""
    err = _dba_check()
    if err: return err

    import openpyxl as _xl  # type: ignore[import]
    from openpyxl.styles import Font, PatternFill, Alignment  # type: ignore[import]
    from openpyxl.utils import get_column_letter  # type: ignore[import]
    data  = request.json or {}
    files = data.get('files', [])  # [{folder, file, date}, ...]
    if not files:
        return jsonify({'error': 'No files selected'}), 400

    wb = _xl.Workbook()
    wb.remove(wb.active)  # remove default sheet  # type: ignore[union-attr]

    header_fill = PatternFill("solid", fgColor="F97316")
    header_font = Font(bold=True, color="FFFFFF")

    for item in files:
        folder   = _dba_os.path.basename(item.get('folder',''))
        filename = _dba_os.path.basename(item.get('file',''))
        filepath = _dba_os.path.join(_DBA_BASE, 'backups', folder, filename)

        if not _dba_os.path.exists(filepath):
            continue

        try:
            con    = _dba_sqlite.connect(filepath)
            tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]

            for table in tables:
                cur  = con.execute(f'SELECT * FROM "{table}"')
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()

                # Sheet name: date_dbname_table (max 31 chars)
                db_short  = filename.replace('.db','').replace('miim_','')
                sheet_name = f"{folder}_{db_short}_{table}"[:31]

                # Avoid duplicate sheet names
                existing = [ws.title for ws in wb.worksheets]
                if sheet_name in existing:
                    sheet_name = sheet_name[:28] + '_2'

                ws = wb.create_sheet(title=sheet_name)

                # Header row
                ws.append(cols)
                for cell in ws[1]:
                    cell.fill      = header_fill
                    cell.font      = header_font
                    cell.alignment = Alignment(horizontal='center')

                # Data rows
                for row in rows:
                    ws.append([str(v) if v is not None else '' for v in row])

                # Auto column width
                for idx, col in enumerate(ws.columns, start=1):
                    max_len = max((len(str(cell.value or '')) for cell in col), default=10)
                    ws.column_dimensions[get_column_letter(idx)].width = min(max_len + 4, 50)

            con.close()
        except Exception:
            continue  # skip broken DB, continue with others

    if not wb.worksheets:
        return jsonify({'error': 'No data found in selected backups'}), 400

    buf = _io_mod.BytesIO()
    wb.save(buf)
    buf.seek(0)

    from flask import send_file as _sf_bkxl  # type: ignore[import]
    return _sf_bkxl(  # type: ignore[return-value]
        buf,
        as_attachment=True,
        download_name='backup_export.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/dbadmin/api/backups')
def dbadmin_backups():
    """List all backup folders and files. Admin only."""
    err = _dba_check()
    if err: return err
    backup_dir = _dba_os.path.join(_DBA_BASE, 'backups')
    if not _dba_os.path.exists(backup_dir):
        return jsonify({'backups': []})
    import glob as _bk_glob
    folders = sorted(_bk_glob.glob(_dba_os.path.join(backup_dir, '????-??-??')))
    result = []
    for folder in folders:
        folder_name = _dba_os.path.basename(folder)
        files = []
        try:
            for f in sorted(_dba_os.listdir(folder)):
                fpath = _dba_os.path.join(folder, f)
                if _dba_os.path.isfile(fpath):
                    files.append({
                        'name': f,
                        'size_kb': _dba_os.path.getsize(fpath) // 1024
                    })
        except Exception:
            pass
        result.append({'folder': folder_name, 'files': files})
    return jsonify({'backups': result})


@app.route('/dbadmin/api/backup-download')
def dbadmin_backup_download():
    """Download a specific backup file. Admin only."""
    # Token can come from query param (for direct link download)
    token_param = request.args.get('token', '')
    if token_param and not request.headers.get('Authorization'):
        request.environ['HTTP_AUTHORIZATION'] = 'Bearer ' + token_param

    err = _dba_check()
    if err: return err

    folder   = request.args.get('folder', '')
    filename = request.args.get('file', '')

    # Safety: no path traversal
    folder   = _dba_os.path.basename(folder)
    filename = _dba_os.path.basename(filename)

    filepath = _dba_os.path.join(_DBA_BASE, 'backups', folder, filename)
    if not _dba_os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    from flask import send_file as _sf_bk  # type: ignore[import]
    return _sf_bk(  # type: ignore[return-value]
        filepath,
        as_attachment=True,
        download_name=f"{folder}_{filename}",
        mimetype='application/octet-stream'
    )


if __name__ == '__main__':
    # Start email reply poller in background
    _poller_thread = threading.Thread(target=_email_poll_loop, daemon=True)
    _poller_thread.start()

    # Start daily backup in background
    _backup_thread = threading.Thread(target=_backup_loop, daemon=True)
    _backup_thread.start()

    import os as _run_os
    port = int(_run_os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)