# Playwright E2E suite

The Phase 18 suite starts an isolated SQLite application through Uvicorn and a
real Nginx reverse proxy. Nginx serves static files and protected downloads, so
the critical browser flow verifies the same `X-Accel-Redirect` boundary used in
production.

The tests are skipped during the normal unit/integration run. Run Chromium
locally after installing Playwright and Nginx:

```bash
SOFTWARE_HUB_RUN_E2E=1 \
SOFTWARE_HUB_E2E_BROWSERS=chromium \
uv run --with playwright==1.61.0 \
pytest -o addopts="" -m e2e tests/e2e -q
```

The GitHub Actions browser job installs Chromium, Firefox and WebKit and runs:

- the full administrator → upload → publish → public download → disable flow;
- mobile and desktop overflow checks;
- deterministic accessible-name, label, heading and landmark checks;
- keyboard focus smoke checks;
- real theme persistence through `localStorage`.

Screenshots and optional videos are uploaded when the job fails.

## Accessibility engine

Install the pinned axe-core package and expose its script path:

```bash
npm install --no-save --package-lock=false --ignore-scripts axe-core@4.11.4
export AXE_CORE_PATH="$PWD/node_modules/axe-core/axe.min.js"
```

The custom DOM audit and axe-core WCAG A/AA serious/critical audit must both pass.
