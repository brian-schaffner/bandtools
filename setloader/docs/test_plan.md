# Test Plan – Setloader Automation

## Objectives
- Validate that the `/run` API endpoint securely accepts uploads, enforces authentication, and surfaces packaging failures.
- Ensure auxiliary endpoints (`/download`, `/update_catalog`) remain import-safe after refactors.
- Confirm that the packaging pipeline writes deterministic artifacts for both AI-assisted and legacy extraction flows.

## Scope
- **In scope:** FastAPI service endpoints, shell automation invoked through `run.sh`, catalog update workflow, and email notifications.
- **Out of scope:** Optical character recognition accuracy of `pdf_to_titles.py`/`ai_reader.py`, upstream AI model quality, and end-user mobile applications consuming `.sbp` packages.

## Test Strategy
1. **Automated unit/integration tests (pytest):**
   - Exercise authentication branches, content-type parsing, artifact resolution, and error handling using FastAPI's `TestClient`.
   - Mock shell execution (`subprocess.run`) and email delivery to isolate server logic.
2. **Command-line workflow checks:**
   - Invoke `run.sh` with representative flags (`--ai` vs. default) using sample PDFs and verify artifact/hash outputs.
   - Validate that environment variables override defaults without leaking credentials.
3. **Manual exploratory testing:**
   - Upload malformed payloads via HTTP clients (e.g., curl/Postman) to observe validation responses.
   - Use the `/download/{slug}` endpoint to confirm fallback search order for generated assets.
4. **Regression gates:**
   - Execute `pytest` and linting (when available) in CI on every change touching automation or API layers.
   - Capture stdout/stderr from `run.sh` to triage packaging regressions quickly.

## Test Cases
| ID | Title | Type | Preconditions | Steps | Expected Result |
|----|-------|------|---------------|-------|-----------------|
| API-001 | Reject missing secret | Automated | Server running | POST `/run` without secret header/body | HTTP 401 with `unauthorized` error |
| API-002 | Reject missing file | Automated | Valid secret | POST `/run` JSON body without `file_b64` | HTTP 422 with validation message |
| API-003 | Happy path (multipart) | Automated | Valid secret, subprocess mocked success | POST `/run` with PDF upload | HTTP 200 containing artifact path |
| API-004 | Artifact missing | Automated | Valid secret, subprocess mocked success | POST `/run` when artifact absent | HTTP 500 with diagnostic tails |
| API-005 | Base64 JSON upload | Automated | Valid secret, subprocess mocked success | POST `/run` JSON body | HTTP 200 with artifact metadata |
| SH-001 | AI extractor pipeline | Manual | OCR dependencies installed | `RUN_EXTRA_FLAGS=--ai ./run.sh sample.pdf Test` | `.sbp` artifact produced, `ARTIFACT=` echoed |
| SH-002 | Legacy pipeline | Manual | Dependencies installed | `./run.sh sample.pdf Test` | `.sbp` artifact produced without AI reader |
| CAT-001 | Catalog update | Manual | Valid `.bkp` file | POST `/update_catalog` with secret | JSON response lists output path |
| DL-001 | Download fallback | Manual | Artifact in uploads directory | GET `/download/<slug>?kind=verified` | Returns file with 200 status |

## Test Data
- `tests/data/sample.pdf` – minimal, deterministic PDF fixture used across automated tests. 【F:tests/data/sample.pdf†L1-L17】
- Synthetic `.sbp` placeholders generated within tests to emulate packaged sets.
- Example catalog backups (`*.bkp`) sourced from staging (not stored in repo) for manual CAT-001 execution.

## Environments & Tooling
- Python 3.12 with FastAPI and pytest (see `requirements.txt`).
- Local or CI Linux runner with `zip`, `md5sum`, and OCR dependencies installed for end-to-end runs.
- Secrets supplied through environment variables (`SECRET`, `SMTP_USER`, `OPENAI_API_KEY`, etc.) rather than committed files.

## Exit Criteria
- All automated pytest suites passing (`tests/test_server.py`).
- Manual checks for SH-001/SH-002/CAT-001 executed on at least one staging environment per release.
- No open high/critical defects remaining in the defect tracker.
