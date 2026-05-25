# Tire Test Dashboard

This app helps teams load tire test logs and view them in 3 simple screens:

- **Live Monitor**: current test tracking by machine and position
- **Data Analysis**: compare one or more tests
- **O-TKPH Analysis**: thermal camera focused analysis

The goal of this README is to explain the app in plain language, including where the important logic lives after the recent refactor.

---

## How the app works (plain language)

1. You type a **test number**.
2. The app finds the corresponding `.log` file in the configured root folder.
3. The parser turns that file into structured data.
4. Each screen (Monitor / Analysis / O-TKPH) reads that data from stores and builds charts/tables.
5. Filters (steps, ignore stopped, limits) only change what is shown; they do not modify the original file.

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

Path configuration is now centralized in `config.py`.

Important lines:

- `APP_ROOT` = this project folder
- `PROJECT_ROOT` = where test folders are searched

Included comments already show common options:

- network path (example)
- local logs folder example: `os.path.join(APP_ROOT, "logs")`

---

## Current project structure (non-programmer view)

### What each folder does (simple)

- `assets/`  
  Visual files for the app interface (CSS styles, icons, images).  
  Think of this as the app's look-and-feel folder.

- `features/`  
  Main business logic grouped by screen/feature.
  - `features/monitor/`: logic for the **Live Monitor** tab (charts, manual refresh, auto-refresh).
  - `features/analysis/`: logic for the **Data Analysis** tab.
  - `features/otkph/`: logic for the **O-TKPH Analysis** tab.
  - `features/navigation/`: logic for switching between tabs.

- `services/`  
  Shared helper code used by more than one feature (for example file lookup, cache, time formatting, step/chart utilities).

- `domain/`  
  Shared data models/types that keep stored data consistent between callbacks.

- `tests/`  
  Automated checks that confirm important app behavior still works after changes.

- `logs/` (if present locally)  
  Local test log files used during development when `PROJECT_ROOT` points here.

Folder summary in one line:  
`features/` = what the app does, `services/` = shared helpers, `domain/` = data shapes, `assets/` = visual style, `tests/` = safety checks.

- `app.py`  
  Main startup file. Creates the app, loads layout, and connects feature modules.

- `config.py`  
  Central place for settings and constants (paths, machine names, colors, variable labels).

- `log_parser.py`  
  Reads raw `.log` files and converts them into clean table-like data.

- `services/`  
  Shared logic used by multiple screens.
  - `services/log_service.py`: file lookup + parse caching
  - `services/runtime.py`: elapsed runtime calculations and formatting
  - `services/chart_utils.py`: shared step/chart utilities used by monitor, analysis, and O-TKPH (downsample, step ranges, step transitions)

- `features/monitor/`  
  Live Monitor-specific callbacks and UI helpers.
  - `icons.py`: SVG icon constants (no project dependencies)
  - `data.py`: pure data transforms — row parsing, filtering, serialization (no Dash, no Plotly)
  - `figures.py`: Plotly figure builders — temperature chart, summary stats
  - `components.py`: Dash panel builders — chart panel, placement history note
  - `layout.py`: layout helpers — `build_monitor_layout()`, `_input_id()`, chart/modal UI helpers
  - `callbacks.py`: chart rendering, modal, manual refresh
  - `log_loading.py`: shared log-loading logic for manual and auto refresh
  - `auto_refresh/`: wall-clock auto-refresh scheduler, banner, and toggle
    - `schedule.py`: pure state machine (testable, no Dash dependency)
    - `callbacks.py`: scheduler and UI callbacks
    - `layout.py`: banner and toggle components

- `features/analysis/`  
  Data Analysis-specific logic.
  - `layout.py`: Dash layout for the Data Analysis tab
  - `figures.py`: Plotly figure builders — comparison chart, distribution, step-average heatmap
  - `services.py`: pure analysis logic — filters, band limits, violations, test frame building
  - `callbacks.py` (facade/entrypoint)
  - `callbacks_filters.py`
  - `callbacks_data_loading.py`
  - `callbacks_rendering.py`
  - `callbacks_export.py`

- `features/navigation/`  
  Top tab switching behavior.

- `features/otkph/`  
  O-TKPH feature entrypoints and module map.
  - `layout.py` (layout entrypoint)
  - `callbacks.py` (facade/entrypoint)
  - `callbacks_filters.py`
  - `callbacks_selection.py`
  - `callbacks_visuals.py`
  - `callbacks_table.py`
  - `services.py`
  - `figures.py`

- `analysis_tab.py`  
  Legacy compatibility shim that re-exports analysis symbols from `features/analysis/*` and `services/chart_utils.py`.
  It is no longer the source of truth for analysis behavior.

- `otkph_tab.py`  
  Legacy compatibility shim that re-exports O-TKPH symbols from `features/otkph/*`.
  It is no longer the source of truth for O-TKPH behavior.

- `domain/models.py`  
  Shared data shapes used in stores (to keep payloads consistent and safer).

- `tests/test_analysis_services.py`  
  Unit tests for key analysis helper behavior.

- `tests/test_otkph_services.py`  
  Unit tests for O-TKPH filter/frozen-period helper behavior.

---

## Programmer view (simple tree)

```text
Monitoring_V1/
  app.py
  config.py
  log_parser.py
  analysis_tab.py
  otkph_tab.py
  assets/
    style.css
  domain/
    models.py
  services/
    log_service.py
    runtime.py
    chart_utils.py
  features/
    monitor/
      icons.py
      data.py
      figures.py
      components.py
      layout.py
      callbacks.py
      log_loading.py
      auto_refresh/
        schedule.py
        callbacks.py
        layout.py
    navigation/
      callbacks.py
    analysis/
      layout.py
      figures.py
      services.py
      callbacks.py
      callbacks_filters.py
      callbacks_data_loading.py
      callbacks_rendering.py
      callbacks_export.py
    otkph/
      layout.py
      callbacks.py
      callbacks_filters.py
      callbacks_selection.py
      callbacks_visuals.py
      callbacks_table.py
      services.py
      figures.py
  tests/
    test_analysis_services.py
    test_otkph_services.py
```

---

## Logic by screen

### Live Monitor

- Loads test data by slot (machine + position)
- Shows chart cards and modal details
- Supports step filtering and ignore stopped
- Uses cached parsing for speed
- **Auto-refresh** (optional, on by default): reloads test data on a wall-clock schedule

#### Auto-refresh behavior

Auto-refresh only applies to the **Live Monitor** tab. It re-runs the same load logic as the **Refresh** button using the current test numbers in the input fields.

| Situation | What happens |
|---|---|
| `:00` or `:30` (server time), you are on Monitor | A warning banner appears with a live 30-second countdown, then data reloads |
| Same time, you are on another tab | Reload runs silently in the background; no banner |
| You click **Dismiss** during the countdown | That half-hour cycle is skipped; the next attempt is at the next `:00` or `:30` |
| **Auto-refresh** toggle is off | The cycle is skipped silently (no banner, no reload) |
| No test numbers typed | The cycle is skipped silently |
| You switch tabs during the countdown | The countdown continues; reload still happens unless you dismissed first |
| Manual **Refresh** | Works independently; still closes the expanded chart modal |

Notes:

- Schedule is aligned to server wall-clock (`:00` and `:30`), not "30 minutes since last refresh".
- The toggle resets to **on** each time the app is loaded.
- If the app starts mid-way through a half-hour window (for example at `:00:15`), it waits for the next boundary rather than refreshing immediately.
- When a chart modal is open, auto-refresh keeps it open and updates the modal content; manual Refresh still closes it.

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
- Ownership is split by concern in `features/otkph/`:
  - `layout.py` for Dash layout
  - `services.py` for pure data/filter/frozen logic
  - `figures.py` for Plotly figure builders
  - callback modules for filters, selection, visuals, and table/export

---

## Why the new structure matters

`app.py` is now ~200 lines and `analysis_tab.py` is now a ~33-line shim — both are pure composition roots. All logic has been extracted into purpose-specific modules:

- `features/monitor/icons.py` — constants only
- `features/monitor/data.py` — pure transforms (no Dash, no Plotly; unit-testable)
- `features/monitor/figures.py` — Plotly figure builders for the monitor tab
- `features/monitor/components.py` — Dash panel builders
- `features/monitor/layout.py` — layout assembly
- `features/analysis/figures.py` — Plotly figure builders for the analysis tab
- `features/analysis/layout.py` — Dash layout for the analysis tab
- `features/analysis/services.py` — pure analysis logic (unit-testable)
- `services/chart_utils.py` — shared step/chart helpers used across all three tabs

This makes the app easier to maintain, safer to change, and easier for new team members to understand.

---

## Helpful notes

- If the app says a test is not found, first verify folder and file naming format under `PROJECT_ROOT`.
- If you move log location, only update `PROJECT_ROOT` in `config.py`.
- If you add a new measured variable, update `config.py` (`VARIABLE_CONFIG`) and parser mapping in `log_parser.py`.
- Auto-refresh timing uses server time (same source as the topbar clock). Browser tab throttling in the background may affect timing if the tab is minimized for long periods.

---

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Default URL: `http://127.0.0.1:8050`
