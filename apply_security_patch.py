#!/usr/bin/env python3
"""
apply_security_patch.py
========================
இந்த script run பண்ணா app.py-ல் உள்ள
security vulnerabilities automatically fix ஆகும்.

Usage:
  python apply_security_patch.py

Note: Original app.py → app.py.backup என save ஆகும்
"""

import os
import shutil
import re

APP_PY = 'app.py'
BACKUP = 'app.py.backup'

def backup_original():
    shutil.copy2(APP_PY, BACKUP)
    print(f"✅ Original backed up → {BACKUP}")

def read_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def apply_patch(content):
    patches_applied = []

    # ─────────────────────────────────────────────────────────
    # PATCH 1: Replace CORS wildcard with secure origin check
    # ─────────────────────────────────────────────────────────
    old_cors = '''# ── CORS: allow requests from file:// and localhost ──
@app.after_request
def _add_cors(response):
    origin = request.headers.get('Origin', '')
    # Allow file:// origins (empty origin) and any localhost port
    if not origin or 'localhost' in origin or '127.0.0.1' in origin:
        response.headers['Access-Control-Allow-Origin'] = origin or '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-User-Id, X-User-Role, X-User-Dept, X-Role, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

@app.before_request
def _handle_options():
    if request.method == 'OPTIONS':
        from flask import make_response as _mr
        r = _mr('', 204)
        origin = request.headers.get('Origin', '')
        r.headers['Access-Control-Allow-Origin'] = origin or '*'
        r.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-User-Id, X-User-Role, X-User-Dept, X-Role, Authorization'
        r.headers['Access-Control-Allow-Credentials'] = 'true'
        return r'''

    new_cors = '''# ── CORS: Secure — only allow whitelisted origins ──
from security import (
    limiter, hash_password, verify_password, needs_bcrypt_upgrade,
    create_token, verify_token, get_current_user,
    require_auth, require_role,
    apply_cors_headers, is_origin_allowed,
    error_response, safe_str, safe_int,
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
        return r'''

    if old_cors in content:
        content = content.replace(old_cors, new_cors)
        patches_applied.append("PATCH 1: CORS wildcard → secure origin check ✅")
    else:
        patches_applied.append("PATCH 1: CORS — pattern not found, manual review needed ⚠️")

    # ─────────────────────────────────────────────────────────
    # PATCH 2: Hardcoded SMTP credentials → environment vars
    # ─────────────────────────────────────────────────────────
    old_smtp = """_CHAT_SMTP_HOST = 'smtp.hostinger.com'
_CHAT_SMTP_PORT = 465
_CHAT_SMTP_USER = 'claude.ai@miim.co.in'
_CHAT_SMTP_PASS = 'Sivan*007'
_ADMIN_EMAIL    = 'claude.ai@miim.co.in'   # admin receives alerts here"""

    new_smtp = """_CHAT_SMTP_HOST = 'smtp.hostinger.com'
_CHAT_SMTP_PORT = 465
# ── Credentials loaded from environment variables (see security.py) ──
# _CHAT_SMTP_USER, _CHAT_SMTP_PASS, _ADMIN_EMAIL are imported from security.py above"""

    if old_smtp in content:
        content = content.replace(old_smtp, new_smtp)
        patches_applied.append("PATCH 2: Hardcoded SMTP password removed ✅")
    else:
        patches_applied.append("PATCH 2: SMTP credentials — pattern not found, manual review needed ⚠️")

    # Also remove duplicate SMTP in send_password_email
    old_smtp2 = """        # ── HOSTINGER SMTP CONFIG ──
        SMTP_HOST = 'smtp.hostinger.com'
        SMTP_PORT = 465
        SMTP_USER = 'claude.ai@miim.co.in'
        SMTP_PASS = 'Sivan*007'"""
    new_smtp2 = """        # ── HOSTINGER SMTP CONFIG (from environment via security.py) ──
        SMTP_HOST = 'smtp.hostinger.com'
        SMTP_PORT = 465
        SMTP_USER = _CHAT_SMTP_USER
        SMTP_PASS = _CHAT_SMTP_PASS"""
    if old_smtp2 in content:
        content = content.replace(old_smtp2, new_smtp2)
        patches_applied.append("PATCH 2b: Duplicate SMTP password in send_password_email removed ✅")

    # ─────────────────────────────────────────────────────────
    # PATCH 3: Login — plain text comparison → bcrypt verify
    #          + return JWT token
    # ─────────────────────────────────────────────────────────
    old_login_query = '''            "SELECT * FROM employees WHERE user_id=? AND password_hash=? AND status='active'",
            (username, password)'''
    new_login_query = '''            "SELECT * FROM employees WHERE user_id=? AND status='active'",
            (username,)'''

    if old_login_query in content:
        content = content.replace(old_login_query, new_login_query)
        patches_applied.append("PATCH 3a: Login query — removed plain password from SQL ✅")

    # Patch login step 2 query
    old_login_query2 = '''                "SELECT * FROM employees WHERE username=? AND password_hash=? AND status='active'",
                (username, password)'''
    new_login_query2 = '''                "SELECT * FROM employees WHERE username=? AND status='active'",
                (username,)'''
    if old_login_query2 in content:
        content = content.replace(old_login_query2, new_login_query2)
        patches_applied.append("PATCH 3b: Login step2 query — removed plain password ✅")

    # Add bcrypt verify + token creation after employee found
    old_login_if_emp = '''        if emp:
            _d    = (emp["desig"] or "").lower()
            _dept = (emp["dept"]  or "").lower()'''
    new_login_if_emp = '''        if emp:
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
            _d    = (emp["desig"] or "").lower()
            _dept = (emp["dept"]  or "").lower()'''
    if old_login_if_emp in content:
        content = content.replace(old_login_if_emp, new_login_if_emp)
        patches_applied.append("PATCH 3c: Login — added bcrypt verify ✅")

    # Add JWT token to login response
    old_login_return = '''            return jsonify({
                "success": True,
                "role": _role,
                "dept": emp["dept"],
                "user": {'''
    new_login_return = '''            # ── Issue JWT token ──
            token = create_token(
                user_id=emp["id"],
                username=emp["username"],
                role=_role,
                emp_id=emp["empid"] or ""
            )
            return jsonify({
                "success": True,
                "token":   token,
                "role": _role,
                "dept": emp["dept"],
                "user": {'''
    if old_login_return in content:
        content = content.replace(old_login_return, new_login_return)
        patches_applied.append("PATCH 3d: Login — JWT token added to response ✅")

    # Add rate limiting to login route
    old_login_route = "@app.route('/api/login', methods=['POST'])\ndef login():"
    new_login_route = "@app.route('/api/login', methods=['POST'])\n@limiter.limit('10 per 15 minutes')\ndef login():"
    if old_login_route in content:
        content = content.replace(old_login_route, new_login_route, 1)
        patches_applied.append("PATCH 3e: Login rate limiting added ✅")

    # ─────────────────────────────────────────────────────────
    # PATCH 4: set-password — hash new password with bcrypt
    # ─────────────────────────────────────────────────────────
    old_set_pw = '''@app.route('/api/set-password', methods=['POST'])
def set_password():
    try:
        data = request.json or {}
        username = data.get('username')
        new_pw = data.get('new_password') or data.get('password')
        conn = _db()
        conn.execute("UPDATE employees SET password_hash=?, force_reset=0 WHERE username=?", (new_pw, username))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as ex:
        return jsonify({"success": False, "error": str(ex)})'''

    new_set_pw = '''@app.route('/api/set-password', methods=['POST'])
def set_password():
    try:
        data = request.json or {}
        username   = safe_str(data.get('username', ''))
        new_pw     = data.get('new_password') or data.get('password', '')
        force_reset = data.get('force_reset', False)
        current_pw  = data.get('current_password', '')

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
        return jsonify({"success": False, "error": "Failed to update password"})'''

    if old_set_pw in content:
        content = content.replace(old_set_pw, new_set_pw)
        patches_applied.append("PATCH 4: set-password — bcrypt hashing added ✅")
    else:
        patches_applied.append("PATCH 4: set-password — pattern not found ⚠️")

    # ─────────────────────────────────────────────────────────
    # PATCH 5: generate-password — use secrets module + hash
    # ─────────────────────────────────────────────────────────
    old_gen_pw = '''@app.route('/api/employees/<int:emp_id>/generate-password', methods=['POST'])
def generate_password(emp_id):
    try:
        import random, string
        new_pw = ''.join(random.choices(string.ascii_letters + string.digits + '!@#$', k=10))
        conn = _db()
        conn.execute("UPDATE employees SET password_hash=?, force_reset=1 WHERE id=?", (new_pw, emp_id))'''

    new_gen_pw = '''@app.route('/api/employees/<int:emp_id>/generate-password', methods=['POST'])
@require_role('admin', 'hr')
def generate_password(emp_id):
    try:
        import string, secrets as _sec
        alphabet = string.ascii_letters + string.digits + '!@#$'
        new_pw = ''.join(_sec.choice(alphabet) for _ in range(12))
        hashed_pw = hash_password(new_pw)
        conn = _db()
        conn.execute("UPDATE employees SET password_hash=?, force_reset=1 WHERE id=?", (hashed_pw, emp_id))'''

    if old_gen_pw in content:
        content = content.replace(old_gen_pw, new_gen_pw)
        patches_applied.append("PATCH 5: generate-password — secrets module + bcrypt + role check ✅")
    else:
        patches_applied.append("PATCH 5: generate-password — pattern not found ⚠️")

    # ─────────────────────────────────────────────────────────
    # PATCH 6: Chat clear — role from JWT not URL param
    # ─────────────────────────────────────────────────────────
    old_chat_clear = '''@app.route('/api/chat/clear', methods=['DELETE'])
def chat_clear():
    try:
        caller_id   = request.args.get('emp_id','').strip()
        caller_role = request.args.get('role','member').strip().lower()
        conn = _chat_db()
        if caller_role == 'admin':
            conn.execute('DELETE FROM chat_messages')
        else:
            conn.execute('DELETE FROM chat_messages WHERE emp_id=?', (caller_id,))
        conn.commit(); conn.close()
        return jsonify({'success': True})
    except Exception as ex:
        return jsonify({'success': False, 'error': str(ex)}), 500'''

    new_chat_clear = '''@app.route('/api/chat/clear', methods=['DELETE'])
@require_auth
def chat_clear():
    try:
        # Role from verified JWT token — NOT from URL query param
        current_user = get_current_user()
        caller_role  = current_user.get('role', 'member')
        caller_id    = str(current_user.get('emp_id', ''))
        conn = _chat_db()
        if caller_role == 'admin':
            conn.execute('DELETE FROM chat_messages')
        else:
            conn.execute('DELETE FROM chat_messages WHERE emp_id=?', (caller_id,))
        conn.commit(); conn.close()
        return jsonify({'success': True})
    except Exception as ex:
        print(f"[chat_clear error] {ex}")
        return jsonify({'success': False, 'error': 'Operation failed'}), 500'''

    if old_chat_clear in content:
        content = content.replace(old_chat_clear, new_chat_clear)
        patches_applied.append("PATCH 6: chat/clear — role from JWT not URL param ✅")
    else:
        patches_applied.append("PATCH 6: chat/clear — pattern not found ⚠️")

    # ─────────────────────────────────────────────────────────
    # PATCH 7: Default password in DB schema → empty string
    # ─────────────────────────────────────────────────────────
    old_default_pw_schema = "        password_hash TEXT DEFAULT 'miim@123',"
    new_default_pw_schema = "        password_hash TEXT DEFAULT '',"  # hash on creation
    count = content.count(old_default_pw_schema)
    if count > 0:
        content = content.replace(old_default_pw_schema, new_default_pw_schema)
        patches_applied.append(f"PATCH 7: DB schema default password removed ({count} places) ✅")

    # ─────────────────────────────────────────────────────────
    # PATCH 8: Seed admin — hash default password
    # ─────────────────────────────────────────────────────────
    old_seed_admin = "             'miim@123',0,'active'))\n        conn.commit()\n        print(\"[DB] Default admin created: username=admin  password=miim@123\")"
    new_seed_admin = "             hash_password('miim@123'),0,'active'))\n        conn.commit()\n        print(\"[DB] Default admin created: username=admin  password=miim@123\")"
    if old_seed_admin in content:
        content = content.replace(old_seed_admin, new_seed_admin)
        patches_applied.append("PATCH 8: Seed admin — bcrypt hash for default password ✅")

    # ─────────────────────────────────────────────────────────
    # PATCH 9: approve_employee default password → bcrypt
    # ─────────────────────────────────────────────────────────
    old_approve_pw = "                 p.get('password_hash','miim@123'), 0, 'active'))"
    new_approve_pw = "                 hash_password(p.get('password_hash') or 'miim@123'), 0, 'active'))"
    if old_approve_pw in content:
        content = content.replace(old_approve_pw, new_approve_pw)
        patches_applied.append("PATCH 9: approve_employee — bcrypt for default password ✅")

    # ─────────────────────────────────────────────────────────
    # PATCH 10: add_employee — hash password on creation
    # ─────────────────────────────────────────────────────────
    old_add_emp = "             data.get('company_email',''), data.get('password_hash','miim@123'), 'active'))"
    new_add_emp = "             data.get('company_email',''), hash_password(data.get('password_hash') or 'miim@123'), 'active'))"
    if old_add_emp in content:
        content = content.replace(old_add_emp, new_add_emp)
        patches_applied.append("PATCH 10: add_employee — bcrypt on creation ✅")

    # ─────────────────────────────────────────────────────────
    # PATCH 11: Error responses — don't leak str(ex)
    # ─────────────────────────────────────────────────────────
    # Replace common pattern: return jsonify({"error": str(ex)}), 500
    old_err = 'return jsonify({"error": str(ex)}), 500'
    new_err = 'print(f"[API Error] {ex}"); return jsonify({"error": "Internal server error"}), 500'
    count = content.count(old_err)
    if count > 0:
        content = content.replace(old_err, new_err)
        patches_applied.append(f"PATCH 11: Error leak fixed ({count} places) ✅")

    return content, patches_applied


def main():
    if not os.path.exists(APP_PY):
        print(f"❌ {APP_PY} not found. Run this script in the same directory as app.py")
        return

    print("🔒 MIIM HRM Security Patch Tool")
    print("=" * 50)

    # Backup
    backup_original()

    # Read
    content = read_file(APP_PY)
    original_len = len(content)

    # Apply patches
    patched_content, applied = apply_patch(content)

    # Write
    write_file(APP_PY, patched_content)

    print("\n📋 Patches Applied:")
    for p in applied:
        print(f"   {p}")

    print(f"\n📊 File size: {original_len:,} → {len(patched_content):,} bytes")
    print("\n✅ Done! Next steps:")
    print("   1. Copy security.py to the same folder as app.py")
    print("   2. Install deps: pip install bcrypt flask-limiter PyJWT")
    print("   3. Set environment variables (see security.py top section)")
    print("   4. Run: python app.py")
    print("   5. Test login — passwords will auto-upgrade to bcrypt")
    print("\n⚠️  IMPORTANT: Update frontend JS to send Authorization header:")
    print("   headers: { 'Authorization': 'Bearer ' + token }")
    print("   (Remove X-User-Role, X-User-Id from all fetch() calls)")

if __name__ == '__main__':
    main()
