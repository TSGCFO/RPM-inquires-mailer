# Detailed TODO – RPM Inquiries Mailer

This document expands each issue into concrete sub‑tasks so anyone on the team can pick up a card and know exactly what to do.

---

## 1  Protect the Microsoft Graph token cache  

**Problem recap**  
The global `_token` dictionary is shared across the thread pool. Two threads could refresh simultaneously, resulting in an incomplete overwrite and an invalid `Bearer` token.

### Sub‑tasks

1. Create a module‑level `threading.Lock()` called `token_lock`.
2. Wrap **both** reads and writes to `_token` in `with token_lock: …`.
3. Add a regression test: spin two threads; mock the token endpoint to delay one; assert both send valid tokens.

---

## 2  Add robust thread supervision  

**Problem recap**  
If a listener thread crashes (database disconnect, JSON error) the process remains alive but silently stops monitoring that database.

### Sub‑tasks

1. Replace manual `threading.Thread` start‑up with `concurrent.futures.ThreadPoolExecutor(max_workers=n)`.
2. Submit each `listen_to_database()` call; store the returned `Future`.
3. Add a watchdog loop that checks `future.done()` every 30 s.  
   * If `future.exception()` is not None, log it and re‑submit a new thread for that DB.
4. Unit‑test by forcing an exception in the listener and asserting the watchdog restarts it.

---

## 3  Respect Postgres 8 kB NOTIFY payload limit  

**Problem recap**  
`pg_notify` drops bytes beyond ≈8,000 characters. Large inquiry messages get truncated.

### Sub‑tasks

1. **Server‑side (SQL)**: Modify `notify_new_row()` to emit only  

   ```sql
   pg_notify('new_record_channel', json_build_object('id', NEW.id)::text);
   ```

2. **Listener**: on receipt, run  

   ```python
   cur.execute("SELECT * FROM public.inquiries WHERE id = %s", (record["id"],))
   full_row = cur.fetchone()
   ```

3. Ensure a connection pool or reuse the existing connection to avoid excessive new connections.
4. Update docs & tests to reflect the new payload format.

---

## 4  Fix Render health‑check false positives  

**Problem recap**  
Blueprint uses `healthCheckPath: /` but the worker has no HTTP server, causing Render to mark it unhealthy.

### Sub‑tasks

1. **Quick fix**: remove the `healthCheckPath` stanza in `render.yaml`.
2. **Better**: add a minimal FastAPI app inside listener:

   ```python
   from fastapi import FastAPI
   app = FastAPI()
   @app.get("/health")
   def health(): return {"status": "ok"}
   ```

   and run it in a separate thread (uvicorn) so Render can hit `/health`.
3. Validate Render dashboard shows “Healthy”.

---

## 5  Remove unused persistent disk

**Problem recap**  
`render.yaml` allocates a 1 GB disk mounted at `/data` but the code never writes to it.

### Sub‑tasks

1. Delete the `disk:` block from `render.yaml`.
2. Re‑deploy and confirm service plan cost drops.

---

## 6  Documentation and CI updates

| Task | Detail |
|------|--------|
| Update **MULTI_DATABASE_SETUP.md** | Describe new minimal NOTIFY payload and full‑row fetch. |
| Update **README** run‑book | Add section “How we supervise threads & restart on failure”. |
| Extend **pytest** suite | New tests for token locking, NOTIFY handler regression, watchdog restart. |

---

## 7  Secret hygiene and rotation

1. Remove any client secrets or DB passwords accidentally committed (e.g. in *CLAUDE.md* history).  
2. Generate new secrets in Azure AD and Postgres; update Render env‑vars.  
3. Add a quarterly rotation reminder (Google Calendar / GitHub Actions secret‑scan).

---

## Tracking Table

| Status | Epic | Issue reference |
|--------|------|-----------------|
| [ ] | Token locking | #protect-token |
| [ ] | Thread supervision | #thread-watchdog |
| [ ] | NOTIFY payload refactor | #notify-size |
| [ ] | Render health‑check | #render-health |
| [ ] | Disk removal | #disk-cleanup |
| [ ] | Docs & CI | #docs-ci |
| [ ] | Secret rotation | #secrets |

Mark “Status” as `[x]` when complete.

---

*Generated : 2025‑06‑02*
