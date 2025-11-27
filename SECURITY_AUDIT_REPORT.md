# SECURITY AUDIT REPORT: cian-analyzer (housler.ru)

**Date:** 2025-11-27
**Auditor:** Claude Code Security Review
**Scope:** Full codebase security analysis

---

## EXECUTIVE SUMMARY

The codebase contains **3 CRITICAL vulnerabilities** related to hardcoded secrets that have been committed to Git history. Additionally, there are **2 HIGH** and **2 MEDIUM** risk issues. The project also demonstrates many good security practices.

---

## CRITICAL VULNERABILITIES (Immediate Action Required)

### 1. Hardcoded Telegram Bot Token

**Location:** `app_new.py:2194`
```python
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8107613087:AAH6CZ7b1mHVfCoa8vZOwrpLRSoCbILHqV0')
```

**Risk Level:** CRITICAL
**Impact:** Attacker can take full control of the Telegram bot, read messages, and impersonate the service.

**Remediation:**
1. Revoke the compromised token via @BotFather
2. Remove the fallback value from code
3. Store token only in environment variables

---

### 2. Hardcoded DNS Provider Credentials

**Locations:**
- `add_dns_simple.py:11-14`
- `add_dns_automated.py:12-15`

```python
REG_LOGIN = "nikitatitov070@yandex.ru"
REG_PASSWORD = "#1$tBILLionaire070!070"
DOMAIN = "housler.ru"
SERVER_IP = "91.229.8.221"
```

**Risk Level:** CRITICAL
**Impact:** Complete domain takeover possible. Attacker can:
- Redirect all traffic to malicious servers
- Intercept emails
- Issue fraudulent SSL certificates
- Perform phishing attacks

**Remediation:**
1. IMMEDIATELY change Reg.ru password
2. Enable 2FA on Reg.ru account
3. Delete these files from repository AND git history
4. Check DNS records for unauthorized changes

---

### 3. Hardcoded Grafana Password

**Location:** `docker-compose.yml:89`
```yaml
GF_SECURITY_ADMIN_PASSWORD: admin
```

**Risk Level:** CRITICAL (if monitoring stack is exposed)
**Impact:** Unauthorized access to monitoring dashboards, potential data exfiltration.

**Remediation:**
1. Change password to a strong, randomly generated value
2. Use Docker secrets or environment variables

---

## HIGH RISK VULNERABILITIES

### 4. Potential SQL Injection

**Location:** `blog_database.py:122-123`
```python
if limit:
    query += f' LIMIT {limit} OFFSET {offset}'
```

**Risk Level:** HIGH
**Impact:** Although parameters have type hints, there's no runtime validation. String coercion attacks possible.

**Remediation:**
```python
query += ' LIMIT ? OFFSET ?'
c.execute(query, (limit, offset))
```

---

### 5. XSS via |safe Filter

**Location:** `templates/blog_post.html:149`
```html
{{ post.content_html | safe }}
```

**Risk Level:** HIGH
**Impact:** If markdown content contains JavaScript, it will execute in user's browser.

**Remediation:**
```python
import bleach
post['content_html'] = bleach.clean(
    markdown2.markdown(post['content']),
    tags=['p', 'h1', 'h2', 'h3', 'a', 'ul', 'ol', 'li', 'code', 'pre'],
    attributes={'a': ['href']}
)
```

---

## MEDIUM RISK VULNERABILITIES

### 6. Redis Without Authentication

**Location:** `docker-compose.yml:13`

**Risk Level:** MEDIUM
**Impact:** If Docker network is compromised, full access to cache data.

**Remediation:**
```yaml
command: redis-server --appendonly yes --maxmemory 512mb --requirepass ${REDIS_PASSWORD}
```

---

### 7. CSRF Exemption for Public Forms

**Location:** `app_new.py:2247`
```python
@csrf.exempt  # Public form
def client_request():
```

**Risk Level:** MEDIUM
**Impact:** Request forgery attacks possible on form submissions.

**Remediation:** Implement CSRF tokens for all state-changing operations.

---

## SECRETS IN GIT HISTORY

All compromised secrets exist in Git history. Even after deletion, they can be retrieved.

**Required Action:**
```bash
# Use git-filter-repo (recommended over filter-branch)
pip install git-filter-repo
git filter-repo --invert-paths --path add_dns_simple.py --path add_dns_automated.py

# Force push to all remotes
git push --force --all
```

**Note:** All collaborators must re-clone after history rewrite.

---

## POSITIVE SECURITY FINDINGS

The project implements many security best practices:

| Feature | Location | Status |
|---------|----------|--------|
| CSRF Protection | `app_new.py:106` | Enabled globally |
| Rate Limiting | `app_new.py:270-277` | Moving-window strategy |
| SSRF Protection | `app_new.py:314-371` | Domain whitelist |
| Security Headers | `app_new.py:506-547` | CSP, X-Frame-Options, etc. |
| Input Validation | `app_new.py:402-448` | Pydantic models |
| Non-root Docker | `Dockerfile:67` | USER housler |
| SECRET_KEY from env | `app_new.py:97` | Required in production |
| Security Tests | `tests/test_security.py` | Comprehensive coverage |

---

## RECOMMENDED ACTIONS

### Immediate (24 hours)
- [ ] Revoke Telegram Bot Token
- [ ] Change Reg.ru password + enable 2FA
- [ ] Change Grafana password
- [ ] Delete DNS automation scripts

### Short-term (1 week)
- [ ] Rewrite Git history to remove secrets
- [ ] Fix SQL injection in blog_database.py
- [ ] Add HTML sanitization for blog content
- [ ] Enable Redis authentication

### Medium-term (1 month)
- [ ] Add pre-commit hooks for secret detection
- [ ] Enable GitHub Secret Scanning
- [ ] Implement security scanning in CI/CD
- [ ] Regular dependency vulnerability scanning

---

## COMPLIANCE NOTES

For GDPR/152-FZ compliance, consider:
- Adding data encryption at rest for user-submitted data
- Implementing audit logging for sensitive operations
- Adding data retention policies

---

*This report was generated as part of an automated security review. Manual verification is recommended for all findings.*
