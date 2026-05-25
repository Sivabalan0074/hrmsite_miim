# 🔒 MIIM HRM — Security Fix Guide

## இந்த files என்னன்னா?

| File | Purpose |
|------|---------|
| `security.py` | Security module — bcrypt, JWT, rate limiting, CORS |
| `apply_security_patch.py` | Automatic patch script for app.py |
| `frontend_security_fix.js` | Frontend JS changes needed |
| `.env.example` | Environment variables template |

---

## Step-by-Step: எப்படி Apply பண்றது?

### Step 1 — Dependencies Install பண்ணுங்க
```bash
pip install bcrypt flask-limiter PyJWT python-dotenv
```

### Step 2 — Files copy பண்ணுங்க
```bash
# security.py to same folder as app.py
cp security.py /path/to/your/miim_hrm/security.py
cp apply_security_patch.py /path/to/your/miim_hrm/
```

### Step 3 — Environment Variables Set பண்ணுங்க
```bash
# .env.example → .env என copy பண்ணுங்க
cp .env.example .env

# .env file திறந்து உங்கள் credentials fill பண்ணுங்க:
nano .env
```

#### Secret Key generate பண்றது:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
# Output example: a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0
# இதை MIIM_SECRET_KEY= value-ஆ paste பண்ணுங்க
```

### Step 4 — Patch Script Run பண்ணுங்க
```bash
cd /path/to/your/miim_hrm/
python apply_security_patch.py
```
Output:
```
✅ Original backed up → app.py.backup
📋 Patches Applied:
   PATCH 1: CORS wildcard → secure origin check ✅
   PATCH 2: Hardcoded SMTP password removed ✅
   PATCH 3a-e: Login — bcrypt + JWT + rate limiting ✅
   PATCH 4: set-password — bcrypt hashing ✅
   ...
```

### Step 5 — Frontend JS Update பண்ணுங்க
app.py-ல் embedded JavaScript-ல் (line ~9520):

**Remove இந்த pattern எங்கேயும் இருந்தாலும்:**
```javascript
'X-User-Role': sessionStorage.getItem('userRole') || 'member'
'X-User-Id': String(empId)
```

**Add இதை:**
```javascript
// Already in apiFetch() now — just use apiFetch() everywhere
```

**Login handler update:**
```javascript
// After successful /api/login:
if (data.success) {
    sessionStorage.setItem('authToken', data.token);  // ← JWT token save
    sessionStorage.setItem('userRole', data.role);    // UI only
    ...
}
```

### Step 6 — Server Start பண்ணுங்க
```bash
python app.py
```

---

## What changed — Users-க்கு என்ன தெரியும்?

### Existing Users:
- **First login**: Auto-migrates plain password to bcrypt (transparent)
- **No password change needed** — existing passwords work as-is
- JWT token 8 hours valid — browser tab close ஆனா re-login வேணும்

### New Users:
- Default password `miim@123` bcrypt-ஆ store ஆகுது
- force_reset=1 → first login-ல் change பண்ண சொல்லும்

---

## Security Fixes Summary

| # | Issue | Fix |
|---|-------|-----|
| 1 | CORS wildcard `*` | Whitelist-based origin check |
| 2 | Hardcoded SMTP password | Environment variable |
| 3 | Plain text passwords | bcrypt hashing |
| 4 | No auth on APIs | JWT token verification |
| 5 | Role spoofing via headers | JWT role (server-verified) |
| 6 | Brute force login | Rate limiting: 10/15min |
| 7 | Error details leaked | Generic error messages |
| 8 | `random` for passwords | `secrets` module |
| 9 | Chat role via URL param | JWT role check |
| 10 | Default `miim@123` plain | bcrypt hashed |

---

## Rollback — பழைய version திரும்ப வேணுமா?

```bash
cp app.py.backup app.py
python app.py
```

---

## .gitignore Update பண்ணுங்க

```gitignore
# Never commit these
.env
*.backup
miim_hr.db
__pycache__/
```

---

## Production Checklist

- [ ] `MIIM_SECRET_KEY` strong random value set பண்ணினீங்களா?
- [ ] `MIIM_SMTP_PASS` environment variable-ல் set ஆச்சா?
- [ ] `.env` file git-ல் commit ஆகலன்னு confirm பண்ணினீங்களா?
- [ ] HTTPS enabled பண்ணினீங்களா? (Let's Encrypt free)
- [ ] `FLASK_DEBUG=0` production-ல் set ஆச்சா?
- [ ] Firewall — port 5000 direct access block ஆச்சா? (nginx proxy use பண்ணுங்க)
