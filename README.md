# EC Lousado Tire Test Dashboard

A Plotly Dash app for loading and visualising tire test logs from the three test machines at EC Lousado (M7900, M7950, M7960) across three screens:

- **Live Monitor** — current test tracking by machine and position, with occupation fill
- **Data Analysis** — compare one or more tests side by side
- **O-TKPH Analysis** — thermal camera focused analysis

---

## How the app works

1. Type test numbers into the machine/position slots on the Live Monitor and click **Refresh**.
2. The app finds the corresponding log file on the network share and parses it.
3. Charts update immediately. At **:00 and :30 every hour**, charts reload automatically if auto-refresh is enabled.
4. Filters (steps, ignore stopped, variable) only change what is shown — they never modify source files.
5. Click the **clock icon** on any position card to open the Occupation Fill dialog for that slot.

---

## Data sources

### Log files (read-only)

The app reads log files **directly from the network share** — no local copy is made.

| Platform | Source |
|---|---|
| Windows (local dev) | `Z:\prstruh\ctend_pt` — mapped network drive via domain SSO |
| Linux / Pergola | `//hjimssvip.tiretech.contiwan.com/hnv1-hs-ge-groups/prstruh/ctend_pt` — SMB direct read via `smbprotocol` |

`PROJECT_ROOT` in `config.py` is set automatically based on `platform.system()`.

### Excel occupation sheets (read + write)

The Occupation Fill feature reads and writes `.xlsm` files on a second SMB server.

| Platform | Source |
|---|---|
| Windows (local dev) | `O:\` — mapped drive (`\\lofs010.tiretech2.contiwan.com\cmip_groups`) |
| Linux / Pergola | `//lofs010.tiretech2.contiwan.com/cmip_groups` — SMB via `smbprotocol` |

Both SMB servers use the same credentials (`GTT_SERVER_USER` / `GTT_SERVER_PASS`). Sessions are registered once at app startup.

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
| `SMB_SERVER` | Hostname of the log-file SMB server |
| `SMB_SHARE` | Share name on that server |
| `SMB_PATH` | Subfolder path within the share |
| `OCCUPATION_SMB_SERVER` | Hostname of the Excel SMB server (`lofs010`) |
| `OCCUPATION_SMB_SHARE` | Share name on the Excel server (`cmip_groups`) |
| `OCCUPATION_ROOT` | Auto-set per platform — Windows: `O:\`, Linux: SMB UNC path |
| `OCCUPATION_EXCEL_PATHS` | Dict of machine ID → relative path to the `.xlsm` file within the share |
| `TEST_REGISTRY_PATH` | `data/test_registry.json` — persisted list of active/planned tests |

To change the log-file share, update `SMB_SERVER`, `SMB_SHARE`, `SMB_PATH`, and the Windows `PROJECT_ROOT` in `config.py`.  
To change the Excel file locations, use the **Settings** panel inside the Occupation Fill dialog (see below) — no code change needed.

---

## Credentials (Linux / Pergola only)

On Linux the app authenticates to both SMB servers using two environment variables injected by **Pergola Config Management**:

- `GTT_SERVER_USER` — Conti domain username
- `GTT_SERVER_PASS` — Conti domain password

These are never stored in code or committed to Git. On Windows, the drives are already mapped via domain SSO — no environment variables needed.

SMB sessions are registered once at app startup. If credentials are missing or the connection fails, the app starts with a warning log and the affected operations will show an error until the issue is resolved.

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

## Occupation Fill

The clock icon button on each position card opens the **Occupation Fill** dialog for that machine/position slot.

### What it writes

For each selected date the dialog writes two cells into the shared `.xlsm` occupation sheet:

| Column | Position 1 | Position 2 | Content |
|---|---|---|---|
| E / J | E | J | Stop reason (selected from dropdown) |
| G / L | G | L | Break intervals detected from log data |

Break intervals are detected automatically from the parsed log: any continuous period where **speed == 0** becomes one `Break:HH:MM-HH:MM` entry. Multiple breaks in a day are separated by a newline within the cell (equivalent to Shift+Enter in Excel).

### Stop reasons

The dropdown offers the following options:

- Mandatory inspection (3rd shift/Weekend)
- Mandatory inspection (Week)
- Mechanical downtime
- Electrical downtime
- Software downtime
- Infrastructure downtime
- Hydraulic downtime
- Pneumatic downtime
- Tire speed compatibility
- Preventive Maintenance
- Test planned activity
- Calibration
- No tires available
- EC Shutdown

### Usage

1. Click the **clock icon** on a position card (visible when a test is loaded).
2. Select a date range with the date picker.
3. For each date, a preview row shows the detected break intervals and a dropdown to select the stop reason.
4. Click **Fill Excel**. The app reads the `.xlsm` file, writes both values, and saves it back — without opening Excel.

### Excel file locations

Default paths (from `config.py`):

| Machine | File |
|---|---|
| M7900 | `LOG-EVALUATION_CENTER/9-TTT/2. Occupation Test Machine/M7900/2026/Occupation AGRO Test Machine.xlsm` |
| M7950 | `LOG-EVALUATION_CENTER/9-TTT/2. Occupation Test Machine/M7950/2026/Occupation OTR Test Machine.xlsm` |
| M7960 | `LOG-EVALUATION_CENTER/9-TTT/2. Occupation Test Machine/M7960/2026/Occupation M7960 Test Machine.xlsm` |

To change a path without redeploying: expand **Excel path settings** inside the dialog, edit the path, and click **Save paths**. The new paths are saved to `occupation_paths.json` in the project root and take effect immediately. This file is gitignored — site-specific paths are never committed.

---

## Caching

Parsed log data is cached at two levels:

| Layer | Where | Invalidated when |
|---|---|---|
| Flask-Caching (server) | In-process, 600 s TTL | File mtime or size changes |
| `loaded-logs-store` (browser) | Dash `dcc.Store` in the tab | Next Refresh or auto-refresh |

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

To deploy: push to the repo and trigger a new build in Pergola. No volume mounts required — the app reads log files directly from the SMB share. The Excel files on `lofs010` are also accessed via SMB.

---

## Run locally (Windows)

```bash
pip install -r requirements.txt
python app.py
```

Default URL: `http://127.0.0.1:8050`

The app detects Windows automatically and reads logs from `Z:\prstruh\ctend_pt` and Excel files from `O:\`. No environment variables needed — both drives must be mapped.

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
  occupation_paths.json           ← gitignored; created at runtime by Occupation Fill settings
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
      components.py               ← position cards (includes clock icon button)
      icons.py                    ← SVG icon constants
      data.py
      figures.py
      log_loading.py
      auto_refresh/
        schedule.py               ← :00/:30 boundary logic
        callbacks.py
        layout.py
      occupation/                 ← Occupation Fill feature
        __init__.py
        smb_excel.py              ← SMB read/write for lofs010 Excel server
        excel_writer.py           ← pure logic: break detection, fill_occupation, path config
        layout.py                 ← clock button + occupation modal HTML
        callbacks.py              ← toggle modal, preview, fill Excel, save paths
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
    test_occupation_excel.py      ← break detection unit tests (no SMB, no file I/O)
```

---

## Architecture notes

- `app.py` is the single composition root. All wiring happens there via explicit keyword arguments — missing dependencies raise `TypeError` at startup, not at the first callback invocation.
- `services/` holds code used by more than one feature. `log_service.py` and `test_registry.py` have **no Dash or Plotly imports** — fully unit-testable.
- `features/*/services.py`, `features/*/figures.py`, and `features/monitor/occupation/excel_writer.py` are pure functions — no Dash state, no callbacks.
- `features/*/callbacks*.py` are the only files that call `app.callback` — thin orchestration only.
- `features/analysis/` and `features/otkph/` never import from `features/monitor/`. Cross-feature utilities live in `services/`.
- The occupation feature is fully self-contained under `features/monitor/occupation/`. It imports from `config` and `services/` but not from any other feature.
- If you add a new measured variable, update `VARIABLE_CONFIG` in `config.py` and the parser mapping in `log_parser.py`. The change propagates automatically to all variable dropdowns.
- If you add a new position to a machine, extend `_POS_BREAK_COL` and `_POS_REASON_COL` in `features/monitor/occupation/excel_writer.py` with the appropriate column letters (pattern: G, L, Q, … for breaks; E, J, O, … for reasons).

---

## Helpful notes

- If a test is not found, verify the folder and file naming (`<TEST_NUMBER>.00a` / `<TEST_NUMBER>.log`).
- If you change the log share location, update `SMB_SERVER`, `SMB_SHARE`, `SMB_PATH`, and the Windows `PROJECT_ROOT` in `config.py`.
- To change Excel file paths without a code change, use the Settings panel in the Occupation Fill dialog. Changes persist to `occupation_paths.json` and survive restarts.
- The test registry (`data/test_registry.json`) is created automatically on first run.
- Available chart variables: Temperature, Load, Inflation Pressure, Room Temperature, Speed, Torque, Deflection.
- The occupation `.xlsm` files contain VBA macros. `openpyxl` opens them with `keep_vba=True` — macros are preserved but not executed during the write.
