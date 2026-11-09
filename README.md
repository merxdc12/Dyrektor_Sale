# ITHutir Pinterest OS

Cross-platform, offline-first desktop workspace for organic Pinterest content production. **No Pinterest or Google API integration.** Publishing happens manually in the system browser.

## Phase 1: working foundation

- PyQt6 desktop window with the approved menu order: FILE, PIN, BOARD, CALENDAR, PUBLISHING, ANALYTICS, REPORTS, TIME, SETTINGS, HELP.
- Local SQLite storage for products, boards, pins, work sessions, and time entries.
- A session timer that starts on launch, supports pause/resume, and saves time to SQLite.
- Local pin drafts and board records. Publishing is not automated.

## Run (Linux Mint / Windows / macOS)

Install Python 3.11+ and create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pinterest_os
```

On Windows use `.venv\\Scripts\\activate` and `python` instead of `python3`. PyQt6 requires a desktop environment. SQLite data is stored in the platform-specific application data directory via Qt QStandardPaths.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Scope and limitations

This is the first foundation, **not** a complete Pinterest publisher. The Calendar, Analytics, Reports, and Settings menu entries are placeholders. The app does not access accounts, scrape websites, or post pins. The developer has not yet verified runtime behavior on Linux Mint, Windows, or macOS; run the smoke test on each target OS before claiming support.

## Safety

Never commit local SQLite files, credentials, exported user content, or virtual environments. Do not use browser automation for account actions.
