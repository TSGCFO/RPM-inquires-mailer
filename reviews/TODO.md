# TODO – RPM Inquiries Mailer

A concise task checklist derived from the current issue audit.

| Status | Task |
|--------|------|
| [ ] | **Protect token cache** — wrap `_token` updates with `threading.Lock()` *or* create per‑thread `GraphClient`. |
| [ ] | **Introduce thread supervision** — migrate to `ThreadPoolExecutor`, log exceptions, and auto‑restart failed listeners. |
| [ ] | **Shrink NOTIFY payload** — emit only inquiry `id`; listener fetches full row via `SELECT`. |
| [ ] | **Update listener to fetch full row** after NOTIFY. |
| [ ] | **Remove/replace Render health‑check** — either delete `healthCheckPath` or add a `/health` endpoint. |
| [ ] | **Evaluate persistent disk** — remove the 1 GB disk mount if not used. |
| [ ] | **Update documentation** — revise `MULTI_DATABASE_SETUP.md` with new NOTIFY strategy. |
| [ ] | **Extend tests** — cover token locking and multi‑DB thread handling. |
| [ ] | **Rotate secrets** — remove plaintext secrets in docs and rotate credentials. |

*Mark each item complete (`[x]`) as you implement fixes.*