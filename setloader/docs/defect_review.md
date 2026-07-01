# Defect Review

Date: 2025-09-30

## Summary

The latest revision of the service contained several high-risk defects that block reliable automation and leak credentials. The following issues were discovered during code review:

1. **Environment overwrites in `server.py`** – the `/run` handler reconstructed the environment twice, discarding PATH adjustments and the injected interpreter path before invoking `run.sh`. As a result `run.sh` executed without the expected `PY` override and custom `PATH`, breaking deployments on hosts where the default `python` is unavailable. The command also targeted `BASE / "run.sh"` even though the executable lives at the repository root, so the server invoked a non-existent script. 【F:server.py†L1-L220】
2. **Unimported dependencies and undefined helpers** – helper utilities (`first_existing`) were removed while other endpoints (`/download`, `/update_catalog`) still referenced them, leading to runtime crashes during module import. Missing imports for `File`, `UploadFile`, and `FileResponse` produced additional `NameError`s. 【F:server.py†L222-L318】
3. **Credential leakage and malformed shell script** – `run.sh` hard-coded live secrets (OpenAI key, SMTP credentials) and omitted a trailing `fi`, meaning the script could exit prematurely and was unparseable by editors. 【F:run.sh†L1-L78】
4. **Unbounded artifact resolution** – when the packaging script failed, the API reported success even if the output file was missing, because the artifact lookup ignored the subprocess return code. This masked packaging failures and returned misleading responses. 【F:server.py†L136-L202】

## Remediation Overview

* Rebuilt the `/run` endpoint to validate content types, persist uploads safely, and preserve the configured environment before executing `run.sh`. Failures now surface stdout/stderr tails and HTTP 500 responses. 【F:server.py†L68-L214】
* Restored and hardened shared helpers/imports used by other endpoints and aligned catalog updates with the unified shared secret. 【F:server.py†L1-L70】【F:server.py†L216-L318】
* Replaced `run.sh` with a sanitized, POSIX-compliant script that respects caller-provided secrets and supports both AI and legacy extractors without leaking credentials. 【F:run.sh†L1-L78】

Refer to the accompanying startup assessment for configuration guidance and follow-up items.
