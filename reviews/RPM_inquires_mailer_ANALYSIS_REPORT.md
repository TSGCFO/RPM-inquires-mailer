# RPM Inquiries Mailer — Full Technical Analysis (Code Branch)

**Repository**: <https://github.com/TSGCFO/RPM-inquires-mailer>  
**Branch analysed**: `code`  
**Date**: 2025‑06‑02

---

## 1  Repository Structure

| Path / File | Purpose |
|-------------|---------|
| `listener.py` | Main background worker: LISTEN on Postgres, send email via Microsoft Graph |
| `requirements.txt` | Runtime deps (`psycopg[binary]`, `requests`) + `pytest` for dev |
| `render.yaml` | Render Blueprint — defines worker, env‑vars, disk, health‑check |
| `README.md` | Quick‑start guide |
| `MULTI_DATABASE_SETUP.md` | Docs for multi‑DB configuration |
| `CLAUDE.md` | Historical notes (contains an obsolete secret) |
| `tests/` | `test_listener.py` (unit tests) |
| `.github/workflows/` | CI pipeline: lint + pytest |

---

## 2  Runtime Flow

1. **Environment bootstrap**  
   * Script validates presence of 8+ env‑vars: DB creds, Graph creds, email addresses.  
2. **Database connectivity**  
   * Uses `psycopg.connect()` with `autocommit=True`.  
3. **Notification subscription**  
   * Executes `LISTEN new_record_channel;`.  
   * For multi‑DB, a new thread plus connection is created per database.  
4. **Event loop**  
   * Blocks on `conn.notifies()` (psycopg 3 generator).  
   * On each NOTIFY payload → `json.loads()` → `send_email(record)`.  
5. **Graph mailer**  
   * App‑only OAuth2 (`client_credentials`).  
   * Caches token in `_token` dict with expiry check.  
   * POSTs to `https://graph.microsoft.com/v1.0/users/{FROM_EMAIL}/sendMail`.  
6. **Logging**  
   * `print(...)` to stdout; no external logger/metrics.

---

## 3  Deployment via `render.yaml`

```yaml
type: worker
buildCommand: pip install -r requirements.txt
startCommand: python listener.py
healthCheckPath: /
disk: { sizeGB: 1, mountPath: /data }
envVars: PGHOST, PGDATABASE, ...
```

* ✅ One‑click deploy & auto‑redeploy on commit.  
* ⚠️ Health‑check path invalid (worker is not HTTP).  
* ⚠️ 1 GB disk allocated but unused.  
* Env‑vars hard‑coded for up to **two** databases (`PGHOST_2`, …).

---

## 4  Critical Issues

| 🚩 Issue                               | Impact                                                                                                       | Recommended Fix                                                                                         |
|---------------------------------------|--------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| **Shared `_token` dict not protected** | Two DB threads may refresh the Graph token simultaneously → one thread could read a half‑updated value → invalid `Bearer …`. | Wrap updates in `threading.Lock()` **or** give each thread its own `GraphClient`. |
| **Thread failure silent**              | If a listener thread crashes (network reset, JSON error) that DB stops sending alerts but the main process stays alive. | Run listeners in `ThreadPoolExecutor`; watchdog & restart any thread whose `Future` ends with an exception. |
| **8 kB NOTIFY limit**                  | Inquiry `message` field > 8 kB gets truncated silently, resulting in incomplete e‑mails.                    | Notify only `{ "id": … }`; listener fetches full row via `SELECT`. |
| **Render health‑check false‑alarm**    | `healthCheckPath: /` returns 404 → Render repeatedly restarts the worker.                                   | Remove health‑check or expose a `/health` endpoint; ensure service type is “background worker”. |
| **Disk unused**                        | Paying for 1 GB persistent disk never written to.                                                           | Remove `disk:` block or start writing logs/metrics to `/data`. |
| **Secrets committed** (`CLAUDE.md`)    | Repository history contains a real `CLIENT_SECRET` (security risk).                                         | Purge secret from git history; rotate credentials. |
| **Token cache race** (multi‑thread)    | Same as first issue; if unaddressed may produce sporadic HTTP 401 from Graph.                               | Same lock/per‑thread fix. |

---

## 5  Architectural Observations

| Area | ✅ Strength | ⚠️ Weakness |
|------|------------|-------------|
| **Simplicity** | Single file, minimal deps, easy to grok. | Hard‑coded two‑DB scaling, global state. |
| **Configuration** | Everything via env‑vars, good for 12‑factor apps. | Verbose: need 20+ vars for two DBs; JSON matrix would scale cleaner. |
| **Email formatting** | Updated human‑friendly plain‑text layout. | Plain‑text only; no HTML alt; no reply‑to header. |
| **Tests/CI** | Lint + pytest on push. | No integration test for NOTIFY path. |
| **Observability** | Logs to stdout captured by host. | No metrics, no trace correlation IDs. |

---

## 6  Recommended Roadmap

1. **Lock or isolate token cache** (race‑condition fix).  
2. **Supervisor / watchdog** for listener threads.  
3. **NOTIFY payload refactor** to ID‑only + DB fetch.  
4. **Render blueprint cleanup** (health‑check, disk).  
5. **Secret hygiene**: remove leaked secret, rotate live creds.  
6. **Optional**: move to JSON‑based DB matrix env‑var, add retries/back‑off, add Prometheus metrics.

---

*Prepared by ChatGPT on 2025‑06‑02 – using latest psycopg 3 docs & Render platform reference.*
