# Command results — Software Hub release audit

> CR-001…037 нижче — незмінний historical evidence початкового read-only audit.
> CR-038…046 — focused P1 remediation evidence від 2026-07-26.
> CR-047…051 — focused P2/P3 remediation evidence від 2026-07-26.

## CR-038 — Clean locked Python 3.14 environment

Command: `uv lock --check && uv sync --all-groups --locked` у новому temporary venv  
Status: PASS  
Key output: resolved 56 packages; FastAPI 0.140.0, Pydantic 2.13.4,
pydantic-core 2.46.4, Starlette 1.3.1, HTTPX2 2.9.1 imports PASS на CPython 3.14.6.  
Evidence: `pyproject.toml`, `uv.lock`.

## CR-039 — Ruff

Command: `ruff format --check . && ruff check .`  
Status: PASS  
Key output: `192 files already formatted`; `All checks passed!`.

## CR-040 — Strict mypy

Command: `mypy --no-incremental`  
Status: PASS  
Key output: `Success: no issues found in 188 source files`.

## CR-041 — Full standard pytest with coverage

Command: `pytest --junitxml=test-results/quality/pytest-p1-remediation.xml`  
Status: PASS  
Key output: `497 passed, 17 skipped`; combined coverage `92.16%` (threshold 90%).  
Interpretation: skips are opt-in Nginx/Playwright, unavailable `sh`, and Windows-only
symlink/POSIX-permission capability checks; Ubuntu jobs execute the POSIX checks.

## CR-042 — Infrastructure and form-parser regression

Command: `pytest -o addopts='' tests/infrastructure tests/integration/test_auth_routes.py -q`  
Status: PASS  
Key output: `35 passed, 1 skipped`; urlencoded field flood rejected before authentication.

## CR-043 — Frozen runtime dependency audit

Command: `uv export --frozen --no-dev ... && pip-audit==2.10.1 --requirement ...`  
Status: PASS  
Key output: 27 runtime dependencies; `No known vulnerabilities found`.  
Artifact: `test-results/quality/pip-audit-p1-remediation.json`.

## CR-044 — Bandit

Command: `bandit[toml]==1.9.4 -c pyproject.toml -r app -f json`  
Status: PASS  
Key output: 0 findings.  
Artifact: `test-results/quality/bandit-p1-remediation.json`.

## CR-045 — Workflow/static container remediation

Command: focused infrastructure tests + static workflow inspection  
Status: PASS  
Key output: CI and release verifier audit frozen runtime requirements; E2E uses locked
Playwright; app healthcheck path is `/usr/local/bin/software-hub-healthcheck.py`.

## CR-046 — Full Ubuntu/container/browser/recovery acceptance

Status: BLOCKED BY ENVIRONMENT  
Reason: Docker, Nginx, Trivy and a Linux Playwright browser matrix are unavailable on this
Windows host. This does not reopen SH-AUDIT-001…007, but prevents changing the original
full-audit verdict to GO.

## CR-047 — Immutable GitHub Action references

Command: official `git ls-remote` tag/peeled-tag verification + static workflow scan  
Status: PASS  
Key output: 15 third-party `uses:` entries; 15 full 40-hex commit SHAs; 15 version
comments; 0 mutable refs. Signed Trivy `v0.36.0` pinned to peeled commit
`ed142fd0673e97e23eac54620cfb913e5ce36c25`, not its annotated tag object.  
Evidence: four `.github/workflows/*.yml`, `.github/dependabot.yml`.

## CR-048 — RC provenance and immutable evidence regression

Command: `pytest -o addopts="" tests/infrastructure/test_quality_gates_phase18.py
tests/infrastructure/test_release_candidate_phase19.py -q`  
Status: PASS  
Key output: `15 passed`. Exact RC tag/commit validation, deterministic
`git archive | gzip -n`, archive/manifest SHA-256, run identity manifest, GitHub
attestation permissions/action and unique commit/attempt artifact naming are asserted.  
Evidence: `.github/workflows/release-candidate.yml`, updated release/acceptance docs.

## CR-049 — Ruff and strict mypy after P2/P3 remediation

Command: `ruff format --check . && ruff check .`; `mypy`  
Status: PASS  
Key output: `192 files already formatted`; `All checks passed!`;
`Success: no issues found in 188 source files`.

## CR-050 — Full Windows portability regression

Command: `pytest --basetemp=.runtime/p2p3-pytest-03
--junitxml=test-results/quality/pytest-p2p3-remediation.xml` in the frozen Python 3.14 graph  
Status: PASS  
Key output: `500 passed, 17 skipped`; combined coverage `92.16%` (threshold 90%).  
Interpretation: explicit workspace `--basetemp` avoids the host sandbox's unreadable global
pytest temp ACL; remaining skips are intentional platform/E2E capability boundaries. P3
remains resolved.

## CR-051 — Audit finding state validation

Command: JSON parse/count validation and audit artifact inventory  
Status: PASS  
Key output: `open_severity_counts` is P0=0, P1=0, P2=0, P3=0; exactly seven files remain
in `audit-output/`. Original NO-GO score/verdict are retained pending the full external
Ubuntu/container/browser/recovery/protected-tag run.

Дата: 2026-07-26.  
Source directory: `D:\work\software_hub`.  
Temporary execution copy: `%TEMP%\software-hub-release-audit-019f9ecc` (усі 61 audit children очищено після валідації; лишився лише ACL-заблокований `.pytest_cache` directory).

Секретні значення й довгі compiler traces скорочено; exit codes і ключові повідомлення збережено.

## CR-001 — Repository identity

Command: `git status --short --branch`  
Directory: `D:\work\software_hub`  
Exit code: 128  
Status: BLOCKED BY ENVIRONMENT  
Key output: `fatal: not a git repository (or any of the parent directories): .git`  
Artifact/log: цей запис; `.git` відсутня у snapshot.  
Interpretation: Worktree cleanliness, commit identity та branch не можна встановити.

## CR-002 — Git history/tags

Command: `git log --oneline --decorate -n 20` і `git tag --list`  
Directory: `D:\work\software_hub`  
Exit code: 128  
Status: BLOCKED BY ENVIRONMENT  
Key output: `not a git repository`.  
Artifact/log: цей запис.  
Interpretation: History secret scan, release tag і provenance не надані.

## CR-003 — Inventory

Command: `rg --files` + PowerShell grouping/counts  
Directory: `D:\work\software_hub`  
Exit code: 0  
Status: PASS  
Key output: 354 files; 70 directories; 190 Python files; 36 templates; 84 test modules; 19 PHASE manifests; 4 workflows; 2 migrations.  
Artifact/log: `ARTIFACT_INVENTORY.md`.  
Interpretation: Source/evidence scope зафіксовано.

## CR-004 — Repository hygiene

Command: inventory for `.env`, DB, backup, key/cert, cache, large files, symlinks  
Directory: `D:\work\software_hub`  
Exit code: 0  
Status: PASS  
Key output: лише `.env.example` і `.env.production.example`; немає SQLite DB, backup, private key/cert, cache, `node_modules`, symlink або file >10 MB.  
Artifact/log: `ARTIFACT_INVENTORY.md`.  
Interpretation: Current source snapshot не містить runtime debris.

## CR-005 — Lock validation

Command: `uv lock --check`  
Directory: temporary audit copy  
Exit code: 0  
Status: PASS  
Key output: `Resolved 50 packages`; CPython 3.14.3.  
Artifact/log: цей запис.  
Interpretation: `uv.lock` синтаксично/семантично узгоджений із metadata.

## CR-006 — Frozen runtime export

Command: `uv export --frozen --no-dev`  
Directory: temporary audit copy  
Exit code: 0  
Status: PASS  
Key output: 214 lines; SHA-256 `A9F9379B6DF48E281B2F9B657525372510FF9716BF2C980E1338D479E494611A`.  
Artifact/log: hash у цьому записі.  
Interpretation: Runtime resolution експортується, але installability перевіряється окремо.

## CR-007 — Target clean sync

Command: `uv sync --all-groups --locked`  
Directory: temporary audit copy, clean environment, CPython 3.14.3  
Exit code: 1  
Status: FAIL  
Key output: `pydantic-core==2.33.1`; `configured Python interpreter version (3.14) is newer than PyO3's maximum supported version (3.13)`; PyO3 0.24.0.  
Artifact/log: SH-AUDIT-001.  
Interpretation: Release candidate не встановлюється на власному target Python.

## CR-008 — Target sync ABI-forward retry

Command: `$env:PYO3_USE_ABI3_FORWARD_COMPATIBILITY='1'; uv sync --all-groups --locked`  
Directory: temporary audit copy, CPython 3.14.3  
Exit code: 1  
Status: FAIL  
Key output: `jiter==0.9.0` compilation fails against removed Python 3.14 Unicode APIs.  
Artifact/log: SH-AUDIT-001.  
Interpretation: Suggested PyO3 bypass не усуває incompatibility.

## CR-009 — Target application import/version

Command: `uv run python -c "import app; print(app.__version__)"`  
Directory: temporary audit copy  
Exit code: 1  
Status: FAIL  
Key output: Environment build stops on pydantic-core before application import.  
Artifact/log: SH-AUDIT-001.  
Interpretation: Runtime smoke на target недоступний через product dependency blocker.

## CR-010 — Fallback exact dependency install

Command: install all-groups frozen export with hashes in isolated CPython 3.13.12 venv  
Directory: temporary audit copy  
Exit code: 0  
Status: PARTIAL  
Key output: exact exported dependency set installed.  
Artifact/log: temporary environment; deleted after audit.  
Interpretation: Дозволяє часткові tests, але не підтверджує target Python 3.14.

## CR-011 — Standard pytest before ad-hoc Playwright

Command: `python -m pytest`  
Directory: temporary audit copy, exact fallback graph  
Exit code: 2  
Status: FAIL  
Key output: collection error `ModuleNotFoundError: No module named 'playwright'` from `tests/e2e/conftest.py`.  
Artifact/log: SH-AUDIT-003.  
Interpretation: Declared dev graph недостатній для documented standard pytest.

## CR-012 — Full fallback tests after temporary Playwright

Command: `python -m pytest -o addopts="" -q`  
Directory: temporary audit copy, CPython 3.13.12 + temporary Playwright 1.61.0 package  
Exit code: 1  
Status: PARTIAL  
Key output: `460 passed, 43 failed, 10 skipped in 30.73s`.  
Artifact/log: SH-AUDIT-010.  
Interpretation: Значний functional signal, але Windows POSIX/encoding failures і non-target Python не дозволяють PASS.

## CR-013 — Coverage fallback

Command: `$env:COVERAGE_CORE='pytrace'; python -m pytest`  
Directory: temporary audit copy  
Exit code: 1  
Status: PARTIAL  
Key output: 460 passed, 43 failed, 10 skipped; total branch coverage 86.29%, threshold 90%.  
Artifact/log: цей запис.  
Interpretation: Попередній claim 92.82% не відтворено; host failures зменшили executed coverage.

## CR-014 — Critical auth/session/CSRF/download/public tests

Command: `python -m pytest -o addopts="" <selected security/auth/download/public modules> -q`  
Directory: temporary audit copy  
Exit code: 0  
Status: PASS  
Key output: `56 passed in 7.80s`.  
Artifact/log: coverage of auth failure/lockout/expiry/rotation/revocation, CSRF inventory/cross-session, private/quarantine/disabled download, public catalog/SEO.  
Interpretation: Strong app-level critical path evidence на fallback.

## CR-015 — Upload/storage security tests

Command: `python -m pytest -o addopts="" <selected upload/storage/security modules> -q`  
Directory: temporary audit copy  
Exit code: 1  
Status: PARTIAL  
Key output: `57 passed, 1 failed`; failure — expected POSIX mode `0o640` on Windows.  
Artifact/log: SH-AUDIT-010.  
Interpretation: Traversal/filename/signature/stream/scanner/compensation controls пройшли; target filesystem evidence неповне.

## CR-016 — Infrastructure tests

Command: `python -m pytest -o addopts="" tests/infrastructure -q`  
Directory: temporary audit copy  
Exit code: 1  
Status: FAIL  
Key output: `21 passed, 3 failed`; missing `sh` in Python PATH, Windows executable bit, і platform-independent missing phrase `Створити категорію`.  
Artifact/log: SH-AUDIT-004, SH-AUDIT-010.  
Interpretation: Один deterministic product test blocker; два host limitations.

## CR-017 — Compileall

Command: `python -m compileall -q app tests`  
Directory: temporary audit copy  
Exit code: 0  
Status: PASS  
Key output: no syntax errors.  
Artifact/log: цей запис.  
Interpretation: Python source синтаксично валідний на fallback.

## CR-018 — Locked Ruff

Command: `uv tool run --from ruff==0.11.7 ruff check .`  
Directory: `D:\work\software_hub`  
Exit code: 2  
Status: FAIL  
Key output: `pyproject.toml:36 unknown variant py314; expected ... py313`.  
Artifact/log: SH-AUDIT-002.  
Interpretation: Frozen CI lint tool не може прочитати project config.

## CR-019 — Supported Ruff format

Command: `uv tool run --from ruff==0.15.22 ruff format --check .`  
Directory: `D:\work\software_hub`  
Exit code: 1  
Status: FAIL  
Key output: 46 files would be reformatted; 144 files already formatted.  
Artifact/log: SH-AUDIT-002.  
Interpretation: Навіть після tool upgrade formatter gate не green.

## CR-020 — Supported Ruff lint

Command: `uv tool run --from ruff==0.15.22 ruff check --statistics .`  
Directory: `D:\work\software_hub`  
Exit code: 1  
Status: FAIL  
Key output: 687 errors; найбільше TRY003 272, RUF001 66, I001 65, S106 63, E501 57; 100 auto-fixable.  
Artifact/log: SH-AUDIT-002.  
Interpretation: Значний lint debt under configured rules.

## CR-021 — Locked mypy

Command: `python -m mypy` з locked mypy 1.15.0  
Directory: temporary audit copy  
Exit code: 2  
Status: FAIL  
Key output: missing `playwright.sync_api` у 2 files; `tests/e2e/accessibility.py` found twice як `e2e.accessibility` і `tests.e2e.accessibility`.  
Artifact/log: SH-AUDIT-003.  
Interpretation: CI type gate не green навіть у fallback install.

## CR-022 — Pre-commit

Command: `pre-commit run --all-files` із writable `PRE_COMMIT_HOME`  
Directory: source snapshot  
Exit code: 1  
Status: BLOCKED BY ENVIRONMENT  
Key output: not a Git repository.  
Artifact/log: цей запис.  
Interpretation: Snapshot без `.git` не дозволяє коректний pre-commit inventory.

## CR-023 — Bandit

Command: `uvx --from "bandit[toml]==1.9.4" bandit -c pyproject.toml -r app`  
Directory: source snapshot  
Exit code: 1  
Status: PARTIAL  
Key output: 0 High, 0 Medium, 6 Low; reviewed B105/B406/B404/B603.  
Artifact/log: цей запис.  
Interpretation: Немає blocking Bandit findings; Low items reviewed як constants/escaping/fixed no-shell scanner invocation.

## CR-024 — CI-exact dependency audit

Command: `uvx --from "pip-audit==2.10.1" pip-audit`  
Directory: temporary audit copy  
Exit code: 0  
Status: FAIL  
Key output: `No known vulnerabilities found`.  
Artifact/log: SH-AUDIT-006.  
Interpretation: Exit 0 не є PASS: команда аудитить isolated uvx tool environment, не frozen application runtime.

## CR-025 — Frozen runtime dependency audit

Command: `uvx --from "pip-audit==2.10.1" pip-audit -r audit-requirements.txt`  
Directory: temporary audit copy  
Exit code: 1  
Status: FAIL  
Key output: 7 advisory records у click 8.1.8, idna 3.10, python-dotenv 1.1.0, Starlette 1.1.0; GHSA-82w8-qh3p-5jfq High, fix Starlette 1.3.1.  
Artifact/log: SH-AUDIT-005/006.  
Interpretation: Runtime dependency set має release-blocking vulnerability.

## CR-026 — Fresh migration upgrade/current/check

Command: `alembic upgrade head`; `alembic current`; `alembic check`  
Directory: temporary audit copy, fresh temp SQLite  
Exit code: 0 / 0 / 0  
Status: PASS  
Key output: `0002_phase4_domain_schema (head)`; `No new upgrade operations detected`.  
Artifact/log: temp DB SHA-256 `4A8506737DA5AA9B397C977556BEB48A66EBC95ABCCD120C0A6346FAE094F3BB`.  
Interpretation: Fresh schema and metadata parity підтверджені на fallback.

## CR-027 — Migration downgrade/upgrade repeat

Command: `alembic downgrade base`; `alembic upgrade head`; `alembic check`  
Directory: temporary audit copy  
Exit code: 0 / 0 / 0  
Status: PASS  
Key output: downgrade і повторний upgrade успішні; no new operations.  
Artifact/log: цей запис.  
Interpretation: Reversible migration rehearsal пройшов на fresh fallback DB.

## CR-028 — CLI surface

Command: `python -m app.cli --help` і `<command> --help` для 14 required commands  
Directory: temporary audit copy  
Exit code: 0 для всіх  
Status: PASS  
Key output: create/change/revoke/cleanup, backup/list/verify/restore, storage/checksum/orphans/status commands доступні; destructive flags `--yes`/`--apply`.  
Artifact/log: цей запис.  
Interpretation: CLI parser/guards присутні; full behavior залишається PARTIAL.

## CR-029 — Shell syntax

Command: `bash -n` для `docker/*.sh` і `scripts/*.sh`  
Directory: source snapshot  
Exit code: 0  
Status: PASS  
Key output: syntax errors absent.  
Artifact/log: цей запис.  
Interpretation: Shell syntax валідний; execution semantics окремі.

## CR-030 — RC rehearsal

Command: `bash -lc "./scripts/rehearse-release-candidate.sh"` із temporary non-production env  
Directory: temporary audit copy  
Exit code: 1  
Status: BLOCKED BY ENVIRONMENT  
Key output: Windows/Git Bash path перетворення призвело до SQLite `unable to open database file`.  
Artifact/log: temporary rehearsal state cleaned.  
Interpretation: Не product proof і не PASS; необхідний Ubuntu rehearsal.

## CR-031 — Local health

Command: Start fallback Uvicorn on `127.0.0.1:8765`; PowerShell `Invoke-WebRequest /health`  
Directory: temporary audit copy  
Exit code: 0; HTTP 200  
Status: PASS  
Key output: `status=ok`, version `1.0.0-rc.1`, application/database/storage/disk `ok`.  
Artifact/log: bounded JSON summarized here; server terminated.  
Interpretation: App health працює у fallback host process, не підтверджує target/container.

## CR-032 — In-app browser

Command: open `http://127.0.0.1:8765/` та host bridge alternative  
Directory: in-app browser sandbox  
Exit code: N/A  
Status: BLOCKED BY ENVIRONMENT  
Key output: `ERR_CONNECTION_REFUSED`; host bridge name unresolved, хоча host PowerShell health був 200.  
Artifact/log: browser session closed.  
Interpretation: UI/browser runtime не можна чесно класифікувати PASS.

## CR-033 — Docker/Compose

Command: `Get-Command docker` / planned `docker compose config/build/up`  
Directory: `D:\work\software_hub`  
Exit code: command unavailable  
Status: BLOCKED BY ENVIRONMENT  
Key output: Docker CLI/daemon відсутні.  
Artifact/log: static Docker/Compose review у report/matrix.  
Interpretation: Config/build/runtime не виконані; static defects не приховуються blocked status.

## CR-034 — Nginx/TLS

Command: planned `nginx -t` and runtime HTTPS checks  
Directory: source snapshot  
Exit code: NOT RUN  
Status: BLOCKED BY ENVIRONMENT  
Key output: Nginx executable/container і certificates відсутні.  
Artifact/log: static template review.  
Interpretation: TLS/internal delivery не мають runtime evidence.

## CR-035 — Trivy

Command: planned filesystem and image Trivy scans  
Directory: source snapshot  
Exit code: NOT RUN  
Status: BLOCKED BY ENVIRONMENT  
Key output: Trivy і Docker images відсутні; зовнішній SARIF не надано.  
Artifact/log: workflow static review only.  
Interpretation: Critical container scan не отримує PASS.

## CR-036 — Static source/security scans

Command: `rg` scans for TODO/FIXME/HACK/pass/broad exceptions/eval/exec/shell=True, commits/raw SQL, template safe/Markup, secrets, CI pins, path/security symbols  
Directory: `D:\work\software_hub`  
Exit code: 0  
Status: PASS  
Key output: no app `eval`/`exec`/`shell=True`; broad catches limited to documented boundaries; repositories do not commit; no Jinja `|safe`; current-tree secrets limited to tests/rehearsal.  
Artifact/log: relevant file/line evidence in `AUDIT_REPORT.md`.  
Interpretation: Статичний security/architecture review не виявив P0 path/execution/secret defect.

## CR-037 — Temporary audit cleanup

Command: validated `Remove-Item -LiteralPath <exact-audit-temp-path> -Recurse -Force` для двох audit-created directories  
Directory: `%TEMP%`  
Exit code: partial cleanup  
Status: PARTIAL  
Key output: `%TEMP%\software-hub-audit-tools` видалено повністю; з work copy видалено 61 children, включно з venv/runtime DB/storage/temporary secrets. Windows ACL відмовив у доступі до єдиного залишку `.pytest_cache`, тому parent directory не видалено.  
Artifact/log: цей запис.  
Interpretation: Матеріальні runtime/test дані очищено; залишився лише pytest cache directory, який поточний процес не має права читати або видалити.
