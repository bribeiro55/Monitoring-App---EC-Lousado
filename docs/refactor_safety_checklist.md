# Refactor Safety Checklist

Use this checklist after each refactor phase.

## Done Criteria

- UI behavior is unchanged for core user flows.
- No new lints/errors in changed files.
- No callback exceptions in terminal during manual checks.

## Core Flows

- Open app and confirm top navigation and pages render.
- In Monitor tab, enter test numbers and click Refresh.
- Verify chart cards load for valid tests and empty state for invalid tests.
- Toggle step pills and confirm charts update.
- Toggle Ignore Stopped and confirm charts update.
- Open chart modal from each position and close it.
- Export CSV from modal and verify file download triggers.
- Switch to Analysis tab and confirm layout loads.
- Add/remove tests in Analysis and confirm outputs update.
- Export CSV from Analysis and verify file download triggers.
- Switch to O-TKPH tab and confirm layout loads and callbacks run.

## Regression Notes Template

- Phase:
- Date:
- Result: pass/fail
- Failures:
  - none
- Follow-up actions:
  - none
