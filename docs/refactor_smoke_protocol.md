# Refactor Smoke Protocol

Run this protocol after each refactor phase.

## Startup

1. Start app: `python app.py`
2. Wait for Dash server startup.
3. Open browser page.

## Quick Smoke

1. Monitor page renders without exceptions.
2. Refresh with at least one valid test number.
3. Toggle one step and `All` step.
4. Toggle Ignore Stopped on/off.
5. Open and close one modal.
6. Trigger modal CSV export.
7. Open Analysis tab and render outputs.
8. Trigger analysis CSV export.
9. Open O-TKPH tab.

## Expected Result

- No traceback in server logs.
- No broken callbacks.
- No missing components/errors in browser.

## Optional Command Checks

- Lints on changed files.
- `python -m py_compile app.py analysis_tab.py otkph_tab.py runtime_utils.py`
