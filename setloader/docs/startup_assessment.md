# Startup Process Assessment

## Current Entry Points
- `server.py` – FastAPI application intended to run under Uvicorn/Gunicorn.
- `run.sh` – Packaging orchestrator invoked by the `/run` webhook and local operators.
- `setloader.sh` – Legacy one-off helper for manual conversions.

## Findings
1. **Ambiguous working directory** – prior code invoked `run.sh` from the API folder, causing relative paths (`etc/`, `pack/`) to resolve incorrectly. The updated service now executes in the repository root and reuses consistent directories. 【F:server.py†L102-L153】
2. **Hard-coded secrets in shell script** – the previous `run.sh` exported live credentials, making every deployment insecure and blocking rotation. The rewritten script respects environment overrides and ships without embedded secrets. 【F:run.sh†L1-L26】
3. **Missing directory bootstrapping** – uploads, work, and pack directories were not created when custom locations were injected. The FastAPI bootstrapper now provisions them based on environment variables, preventing `FileNotFoundError`s on cold starts. 【F:server.py†L46-L66】
4. **Lack of health instrumentation** – `/health` previously exposed path discovery data but no readiness check on `run.sh`. The handler still returns the resolved script path; operators should extend it with subprocess dry-runs if deeper coverage is required.

## Recommendations
- **Service launch**: run the API with `uvicorn server:app --host 0.0.0.0 --port 8000` after exporting required secrets (SECRET/SMTP/OPENAI keys). Provide a systemd unit or container entry point that loads an `.env` file rather than hard-coding secrets.
- **Background workers**: if packaging jobs become long-running, offload `/run` invocations to a task queue (RQ/Celery) to avoid blocking HTTP threads.
- **Observability**: capture stdout/stderr of `run.sh` to a structured log (e.g., `work/run-<timestamp>.log`) and expose aggregated metrics for success/failure counts.
- **Configuration management**: centralize environment defaults in a `.env.example` file and document optional directories (`UPLOAD_DIR`, `WORK_DIR`, `PACK_DIR`) to support multi-tenant deployments.
- **Graceful startup checks**: add a CI smoke test that executes `run.sh` against `tests/data/sample.pdf` to validate dependencies when building release artifacts.

## Next Steps
1. Implement the `.env` template and systemd/container instructions in the README.
2. Add structured logging around `subprocess.run` for easier triage.
3. Automate the `run.sh` smoke test inside CI using the provided sample PDF.
