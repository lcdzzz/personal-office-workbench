# Local File Storage Implementation Plan

**Goal:** Replace browser `localStorage` persistence with a local Python API backed by four JSON files in the macOS application data directory.

**Architecture:** `start.sh` launches `server.py` on loopback port 8799. The HTML page reads and writes one logical workbench snapshot through `/api/workbench`; the server atomically persists `tasks.json`, `notes.json`, `projects.json`, and `meta.json`, retaining `.bak` files. Backups are ZIP archives handled by the server.

**Tech Stack:** Python 3 standard library, browser Fetch API, existing single-file HTML, Node.js/jsdom smoke test.

## Global Constraints

- No migration from the old browser cache.
- Local files are the only data source.
- Data lives outside the repository under the OS application-data directory.
- Only one local instance is supported.
- Default bind address is `127.0.0.1`; configured hosts must remain loopback-only.
- Default port is `8799`, configurable through `config.json`; repository ships only `config.example.json`.
- Writes are immediate and serialized; each JSON file is written atomically with a `.bak` fallback.
- Corrupt primary and backup files stop writes and preserve the damaged files.
- Agent access is not implemented now; JSON remains stable, readable, and generation-stamped for future read-only analysis.

## Task 1: Add local persistence server

**Files:**
- Create: `server.py`
- Create: `config.example.json`
- Modify: `start.sh`

- [ ] Implement the loopback-only HTTP server, config loading, application-data directory creation, four-file initialization, atomic writes, generation checks, snapshot GET/PUT, ZIP backup export, ZIP preview/import, and single-instance lock.
- [ ] Keep runtime PID/log files outside the repository.
- [ ] Add focused Python self-checks for path resolution, host validation, atomic persistence, and backup round-trip.

## Task 2: Switch the page to the API

**Files:**
- Modify: `personal-office-workbench.html`

- [ ] Replace synchronous `localStorage` load/save with async API load and serialized immediate API saves.
- [ ] Boot only after the initial API snapshot succeeds.
- [ ] Show a clear service/data error state instead of falling back to browser storage.
- [ ] Preserve task, note, project, review, rollover, and language behavior.
- [ ] Change export/import to the server ZIP endpoints.

## Task 3: Update runtime tests

**Files:**
- Modify: `smoke_test.cjs`

- [ ] Mock the workbench API instead of `localStorage`.
- [ ] Verify initial load, all six views, immediate save requests, backup export, and backup import controls.
- [ ] Run the existing smoke test and a server self-check.

## Acceptance

- Repository contains the HTML, Python server, launcher, smoke test, config example, and documentation only; runtime data/PID/log files stay outside it.
- A fresh start creates empty data files after the user chooses empty data, or sample data after choosing samples.
- Adding a task persists it to local JSON without browser storage.
- Restarting the server reloads the same data.
- ZIP export/import round-trips all four files.
- Corrupt data never silently resets to empty data.
- `node smoke_test.cjs` passes with zero JavaScript errors.
