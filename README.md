# Tire Test Dashboard

A Dash app for loading and visualising tire test logs across three screens:

- **Live Monitor** — current test tracking by machine and position
- **Data Analysis** — compare one or more tests side by side
- **O-TKPH Analysis** — thermal camera focused analysis

---

## How the app works

1. Type test numbers into the machine/position slots on the Live Monitor and click **Refresh**.
2. The app finds the corresponding log file on the network share and parses it.
3. Charts update immediately. At **:00 and :30 every hour**, charts reload automatically if auto-refresh is enabled.
4. Filters (steps, ignore stopped, limits) only change what is shown — they never modify source files.

---

## Data source

The app reads log files **directly from the network share** — no local copy is made.

| Platform | Source |
|---|---|
| Windows (local dev) | `Z:\prstruh\ctend_pt` — mapped network drive via domain SSO |
| Linux / Pergola | `//hjimssvip.tiretech.contiwan.com/hnv1-hs-ge-groups/prstruh/ctend_pt` — SMB direct read via `smbprotocol` |

`PROJECT_ROOT` in `config.py` is set automatically based on `platform.system()`.

### Log folder structure expected

```text
<PROJECT_ROOT>/
  08370916.00a/
    08370916.log
  08409480.00a/
    08409480.log
```

Rules:
- Folder ends with `<TEST_NUMBER>.00a`
- Log filename ends with `<TEST_NUMBER>.log`
- Scan is one level deep from the root

---

## Configuration (`config.py`)

| Constant | Purpose |
|---|---|
| `APP_ROOT` | This project folder |
| `PROJECT_ROOT` | Auto-set per platform — Windows: `Z:\prstruh\ctend_pt`, Linux: SMB UNC path |
| `SMB_SERVER` | Hostname of the SMB server (Linux only) |
| `SMB_SHARE` | Share name on that server |
| `SMB_PATH` | Subfolder path within the share |
| `TEST_REGISTRY_PATH` | `data/test_registry.json` — persisted list of active/planned tests |

To change the share location update `SMB_SERVER`, `SMB_SHARE`, and `SMB_PATH` — and the Windows `PROJECT_ROOT` path — all in one place in `config.py`.

---

## Credentials (Linux / Pergola only)

On Linux the app authenticates to the SMB server using two environment variables injected by **Pergola Config Management**:

- `GTT_SERVER_USER` — Conti domain username
- `GTT_SERVER_PASS` — Conti domain password

These are never stored in code or committed to Git. On Windows, OS-level SSO handles authentication automatically — no credentials needed.

The SMB session is registered once at app startup. If credentials are missing or the connection fails, the app starts with a warning log and chart loads will show an error until the issue is resolved.

---

## Auto-refresh

Charts refresh automatically at **:00 and :30** each hour (server wall-clock time).

| Situation | What happens |
|---|---|
| `:00` or `:30` arrives, **Auto-refresh** toggle is on | Charts reload silently after a 30-second countdown |
| `:00` or `:30` arrives, **Auto-refresh** toggle is off | No reload |
| Manual **Refresh** button | Always reloads immediately, regardless of toggle |

Auto-refresh only applies to the **Live Monitor** tab.

---

## Test Registry

The **Test Registry** (document icon next to "Current Tests Running") is a lightweight bookmarking tool. It persists to `data/test_registry.json` and survives app restarts.

- **Active** — tests currently being monitored
- **Planned** — kept for reference

The registry has no effect on which files are read or cached — it is purely informational. All users connected to the same server instance share the same registry. Changes are reflected immediately.

---

## Caching

Parsed log data is cached at two levels:

| Layer | Where | Invalidated when |
|---|---|---|
| Flask-Caching (server) | In-process, 600 s TTL | File mtime or size changes |
| `loaded-logs-store` (browser) | Dash dcc.Store in the tab | Next Refresh or auto-refresh |

Variable changes, step filters, and other controls read from the browser store — **no file I/O, no server round-trip**.

On Linux, directory scans are also cached (`lru_cache`) keyed on the SMB root directory's mtime — a full directory listing only happens when new test folders appear.

---

## Deployment (Pergola)

The app runs in a Linux container built from the `Dockerfile`. It is permanently running (no scheduled wake-up). Credentials are injected as environment variables via Pergola Config Management.

```yaml
# pergola.yaml — key settings
service: monitoring-app
port: 8050
resources: 500m CPU / 1Gi memory
```

To deploy: push to the repo and trigger a new build in Pergola. No volume mounts required — the app reads directly from the SMB share.

---

## Run locally (Windows)

```bash
pip install -r requirements.txt
python app.py
```

Default URL: `http://127.0.0.1:8050`

The app detects Windows automatically and reads from `Z:\prstruh\ctend_pt`. No environment variables needed.

---

## Project structure

```text
Monitoring_V1/
  app.py                          ← composition root: wires layouts + callbacks
  config.py                       ← all paths, constants, variable config
  log_parser.py                   ← raw .log file parser → DataFrame
  requirements.txt
  Dockerfile
  pergola.yaml
  assets/
    style.css
  data/
    test_registry.json            ← gitignored, created at runtime
  domain/
    models.py                     ← shared data models / store shapes
  services/
    log_service.py                ← file lookup, parse caching, SMB variants
    test_registry.py              ← thread-safe, JSON-backed test list
    chart_utils.py
    data_utils.py
    filter_utils.py
  features/
    monitor/
      layout.py
      callbacks.py
      callbacks_registry.py       ← registry modal callbacks
      components.py
      icons.py
      data.py
      figures.py
      log_loading.py
      auto_refresh/
        schedule.py               ← :00/:30 boundary logic
        callbacks.py
        layout.py
    navigation/
      callbacks.py
    analysis/
      layout.py
      figures.py
      services.py
      callbacks.py
      callbacks_data_loading.py
      callbacks_filters.py
      callbacks_rendering.py
      callbacks_export.py
    otkph/
      layout.py
      services.py
      figures.py
      callbacks.py
      callbacks_filters.py
      callbacks_selection.py
      callbacks_visuals.py
      callbacks_table.py
  tests/
    test_monitor_data.py
    test_test_registry.py
    test_sync_service.py
```

---

## Architecture notes

- `app.py` is the single composition root. All wiring happens there via explicit keyword arguments — missing dependencies raise `TypeError` at startup, not at the first callback invocation.
- `services/` holds code used by more than one feature. `log_service.py` and `test_registry.py` have **no Dash or Plotly imports** — fully unit-testable.
- `features/*/services.py` and `features/*/figures.py` are pure functions — no Dash state, no callbacks.
- `features/*/callbacks*.py` are the only files that call `app.callback` — thin orchestration only.
- `features/analysis/` and `features/otkph/` never import from `features/monitor/`. Cross-feature utilities live in `services/`.
- If you add a new measured variable, update `VARIABLE_CONFIG` in `config.py` and the parser mapping in `log_parser.py`. The change propagates automatically to all variable dropdowns.

---

## Helpful notes

- If a test is not found, verify the folder and file naming (`<TEST_NUMBER>.00a` / `<TEST_NUMBER>.log`).
- If you change the share location, update `SMB_SERVER`, `SMB_SHARE`, `SMB_PATH`, and the Windows `PROJECT_ROOT` in `config.py`.
- The test registry (`data/test_registry.json`) is created automatically on first run.
- Available variables: Temperature, Load, Inflation Pressure, Room Temperature, Speed, Torque, Deflection.
