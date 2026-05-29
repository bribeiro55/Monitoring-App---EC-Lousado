# Tire Test Dashboard

This app helps teams load tire test logs and view them in 3 simple screens:

- **Live Monitor**: current test tracking by machine and position
- **Data Analysis**: compare one or more tests
- **O-TKPH Analysis**: thermal camera focused analysis

The goal of this README is to explain the app in plain language, including where the important logic lives after the recent refactor.

---

## How the app works (plain language)

1. You add test numbers to the **Test Registry** (the document icon next to "Current Tests Running").
2. The app **automatically syncs** the corresponding test folders from the network share (`Z:\prstruh\ctend_pt`) into a local `logs/` folder at :20 and :50 each hour, and **reloads the charts automatically** within 10 seconds of each sync completing.
3. You type test numbers into the machine/position slots on the Live Monitor and click **Refresh** to view charts.
4. Each screen (Monitor / Analysis / O-TKPH) reads data from stores and builds charts/tables.
5. Filters (steps, ignore stopped, limits) only change what is shown; they do not modify the original files.

---

## Log folder structure expected

Inside your configured project root, each test should look like this:

```text
<PROJECT_ROOT>/
  08370916.00a/
    08370916.log
  08409480.00a/
    08409480.log
```

Rules:

- folder ends with `<TEST_NUMBER>.00a`
- log filename ends with `<TEST_NUMBER>.log`
- scan is one level down from root

---

## Where to configure paths

Path configuration is centralized in `config.py`.

Important lines:

- `APP_ROOT` = this project folder
- `PROJECT_ROOT` = where test folders are stored locally (`logs/` by default)
- `SYNC_SOURCE_ROOT` = network share to sync from (currently `Z:\prstruh\ctend_pt`)
- `SYNC_DEST_ROOT` = same as `PROJECT_ROOT` — the local `logs/` folder
- `SYNC_SCHEDULE_MINUTES` = `[20, 50]` — sync fires at XX:20 and XX:50 each hour
- `TEST_REGISTRY_PATH` = `data/test_registry.json` — persisted list of active/planned tests

---

## Sync and Test Registry

### How syncing works

The app replicates the test folder from the network share into the local `logs/` folder using a Python mirror (no external scripts needed). For each active test, it:

1. Scans `SYNC_SOURCE_ROOT` for a folder ending in `<test_number>.00a` that contains `<test_number>.log`.
2. Mirrors that folder locally: copies new/changed files (comparing mtime + size), deletes files that no longer exist on the share.
3. Logs the result (files copied, deleted, unchanged) in the Sync Status panel.

### Timing design

| Scheduler | Fires at | Purpose |
|---|---|---|
| Sync | `:20` and `:50` | Copies files from share into `logs/` |
| Sync-triggered refresh | Within 10 s of sync completing | Reloads charts automatically after new data arrives |

Charts update within seconds of each sync completing. There is no fixed-clock fallback — use the **Refresh** button if you need to reload manually.

### Test Registry

The **Test Registry** (opened by clicking the document icon next to "Current Tests Running") is the replacement for `active_test.txt`. It persists to `data/test_registry.json` and survives app restarts.

- **Active** tests are synced automatically on each cycle.
- **Planned** tests are kept for reference but not synced yet.
- Removing a test from the registry stops future syncs but does **not** delete any local log files already copied.

All users connected to the same server see the same registry — changes by one user are visible to others within 10 seconds (poll interval).

### Sync Status panel

Below the Diagnostics section on the Live Monitor tab you will find the Sync Status panel:

- Shows **Last sync** time (relative) and **Next** sync time.
- Per-test rows with status icons: ✓ ok / ✗ error / – not found on share.
- **Sync Now** button to trigger an immediate sync.
- **Auto-sync** toggle to pause/resume the background scheduler.
- A warning banner if the network share is unreachable.

---

## Current project structure (non-programmer view)

### What each folder does (simple)

- `assets/`  
  Visual files for the app interface (CSS styles, icons, images).

- `features/`  
  Main business logic grouped by screen/feature.
  - `features/monitor/`: logic for the **Live Monitor** tab (charts, refresh, auto-refresh, sync UI, test registry modal).
  - `features/analysis/`: logic for the **Data Analysis** tab.
  - `features/otkph/`: logic for the **O-TKPH Analysis** tab.
  - `features/navigation/`: logic for switching between tabs.

- `services/`  
  Shared helper code used by more than one feature.
  - `log_service.py`: file lookup and parse caching
  - `sync_service.py`: mirror logic + background sync scheduler (no Dash dependency)
  - `test_registry.py`: thread-safe, JSON-backed active/planned test list (no Dash dependency)
  - `chart_utils.py`: step/chart utilities (downsample, step ranges, step transitions)
  - `data_utils.py`: cross-feature data utilities — deserialise store rows, filter by steps/stopped state, serialise to store
  - `filter_utils.py`: shared date/time parsing used by analysis and O-TKPH filters

- `data/`  
  Persisted app state. Created automatically on first run. Currently holds `test_registry.json` (gitignored).

- `domain/`  
  Shared data models/types that keep stored data consistent between callbacks.

- `tests/`  
  Automated checks that confirm important app behavior still works after changes.

- `logs/` (if present locally)  
  Local test log files — either manually placed or automatically synced from the network share.

Folder summary in one line:  
`features/` = what the app does, `services/` = shared helpers, `domain/` = data shapes, `data/` = persisted state, `assets/` = visual style, `tests/` = safety checks.

---

## Logic by screen

### Live Monitor

- Loads test data by slot (machine + position)
- Shows chart cards and modal details
- Supports step filtering and ignore stopped
- Uses cached parsing for speed
- **Auto-refresh** (optional, on by default): reloads charts automatically within 10 seconds of each sync completing
- **Auto-sync** (on by default): mirrors active tests from the network share in the background
- **Test Registry**: document icon button in the top bar opens a modal to manage active/planned tests — accessible from any tab

#### Auto-refresh behavior

Auto-refresh only applies to the **Live Monitor** tab. It re-runs the same load logic as the **Refresh** button using the current test numbers in the input fields.

| Situation | What happens |
|---|---|
| Sync completes (~:20 or ~:50), **Auto-refresh** toggle is on | Charts reload silently within 10 seconds |
| Sync completes, **Auto-refresh** toggle is off | No reload |
| Manual **Refresh** button | Always reloads immediately, regardless of toggle state |

#### Auto-sync behavior

The background sync runs in a daemon thread and never blocks the UI.

| Situation | What happens |
|---|---|
| `:20` or `:50` (server time) | Sync fires for all **Active** tests in the registry |
| **Sync Now** button clicked | Sync fires immediately, then resumes the normal schedule |
| **Auto-sync** toggle is off | Scheduled syncs are skipped; Sync Now still works |
| Source share unreachable | A warning is shown in the Sync Status panel; sync is skipped |
| Test not yet on the share | Recorded as "not found"; sync retries on next cycle automatically |
| Test removed from registry | Future syncs stop; already-copied local files are kept |

Notes:

- Sync-triggered refresh fires within 10 seconds of sync completing, driven by the 10-second poll interval.
- `SYNC_SOURCE_ROOT` in `config.py` is the only place to change the share path.
- The registry is shared across all users connected to the same server instance.

### Data Analysis

- Lets users add/remove tests by test number
- Stores parsed test data in analysis stores
- Applies value/time filters and limit bands
- Renders comparison charts and violation table
- Exports analysis CSV

### O-TKPH Analysis

- Focused on thermal camera channels
- Uses test number lookup and parser output
- Includes camera thresholds, frozen-period table, and export tools
- **Excel export** includes a `CPC Temp. (°C)` column in the Data sheet and a CPC temperature line series in the Test Analysis chart (alongside the thermal camera channels and speed), for export visibility without affecting the in-app view
- Ownership is split by concern in `features/otkph/`:
  - `layout.py` for Dash layout
  - `services.py` for pure data/filter/frozen logic
  - `figures.py` for Plotly figure builders
  - callback modules for filters, selection, visuals, and table/export

---

## Why the structure is organised this way

`app.py` is the single composition root — it wires together layouts and registers callbacks using explicit keyword arguments. All feature logic lives in purpose-specific modules:

- `services/` — code shared across two or more features. Adding a screen never requires touching `features/monitor/`.
- `services/sync_service.py` and `services/test_registry.py` have **no Dash or Plotly imports** — fully unit-testable and independently runnable.
- `features/*/services.py` — pure business logic with no Dash or Plotly imports; fully unit-testable.
- `features/*/figures.py` — Plotly figure builders; depend on data, not on Dash state.
- `features/*/components.py` — Dash HTML builders; depend on data and figures, not on callbacks.
- `features/*/callbacks*.py` — the only files that touch `app.callback`; thin orchestration wiring state to the functions above.

Key invariants:
- `features/analysis/` and `features/otkph/` never import from `features/monitor/`. Cross-feature utilities live in `services/`.
- `config.py` is the single source for all column lists (`OUTPUT_COLUMNS`, `STORE_COLUMNS`), machine names, colors, variable mappings, and sync settings.
- All `register_*` functions accept keyword-only arguments — missing dependencies cause a `TypeError` at startup rather than a `KeyError` at the first callback invocation.
- Sync state is protected by a `threading.Lock`; the Dash main thread only reads a snapshot via `scheduler.get_state()`.

---

## Helpful notes

- If the app says a test is not found, first verify folder and file naming format under `PROJECT_ROOT`.
- If you move the log location, only update `PROJECT_ROOT` in `config.py`.
- If you move the network share, only update `SYNC_SOURCE_ROOT` in `config.py`.
- If you add a new measured variable, update `config.py` (`VARIABLE_CONFIG`) and the parser mapping in `log_parser.py`. Adding it to `VARIABLE_CONFIG` automatically propagates it to the variable dropdowns in Monitor, Data Analysis, and the analysis data filters.
- Available variables: Temperature, Load, Inflation Pressure, Room Temperature, Speed, Torque, Deflection.
- Auto-refresh and auto-sync timing both use server wall-clock time (same source as the topbar clock).
- The test registry (`data/test_registry.json`) is created automatically on first run — no manual setup needed.
- The external PowerShell script (`Sync-CtendLogs.ps1`) and its Task Scheduler job are no longer needed and can be removed.

---

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Default URL: `http://127.0.0.1:8050`
