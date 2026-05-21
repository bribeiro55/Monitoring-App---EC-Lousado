# Analysis Baseline (Pre-Refactor)

This baseline captures expected Analysis tab behavior and store payload shape before the scalability refactor.

## Manual Smoke Flows

- Add/remove tests from sidebar and confirm selection list updates.
- Update upper/lower band limits and confirm chart/legend/table updates.
- Toggle value/time filter modes and verify filter UI state changes correctly.
- Toggle violations "View more/Show less" and confirm list expansion behavior.
- Export CSV from Analysis and verify download is triggered.

## Key Stores and Expected Shapes

- `analysis-tests-store`: list of `{ test_number, color_index }`
- `analysis-data-store`: map keyed by test number with `{ test_number, status, rows, message?, load_debug? }`
- `analysis-limits-store`: `{ upper, lower }`
- `analysis-data-filters-store`: `{ value_mode, time_mode, value_a, value_b, time_date_a, time_date_b, time_time_a, time_time_b }`
- `analysis-violations-expanded-store`: boolean

## Safety Criteria

- Callback IDs and outputs remain unchanged.
- Store keys remain backward-compatible.
- No new lint or compile errors in touched modules.
