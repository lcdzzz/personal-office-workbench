# Personal Office Workbench

A lightweight, local-first personal workbench for tracking tasks, notes, and projects. It runs entirely on your computer: the interface is a single HTML page and the bundled Python server stores data in local JSON files.

## Features

- Focus view for the work that needs attention now
- Task, note, project, and work-log management
- JSON data stored locally, not in a cloud service
- ZIP export, preview, merge, and restore
- Atomic writes with backup files and generation checks to avoid silently losing inconsistent data
- Chinese and English interface

## Requirements

- macOS or Windows
- Python 3

The browser launcher needs no database, Node.js runtime, or third-party Python package. The macOS app bundles its runtime and does not require a separate Python installation.

## Start

```bash
# macOS
./start.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\start-windows.ps1
```

The launcher starts a server on `http://127.0.0.1:8799` and opens the workbench in your browser. If that port is occupied, create this file and choose a free local port:

macOS: `~/Library/Application Support/PersonalOfficeWorkbench/config.json`

Windows: `%APPDATA%\PersonalOfficeWorkbench\config.json`

```json
{
  "host": "127.0.0.1",
  "port": 8799
}
```

## macOS app and DMG

On a Mac, build a drag-to-Applications disk image with:

```bash
./build-macos-dmg.sh
```

The script creates `dist/Personal-Office-Workbench-macOS-<architecture>.dmg`. Open the DMG and drag **Personal Office Workbench.app** to **Applications**. The app includes its Python runtime and opens the workbench in its own macOS window. Closing the window stops the local service started by the app. Your data remains in `~/Library/Application Support/PersonalOfficeWorkbench/`, independently of the installed app.

The first build downloads PyInstaller and pywebview into a project-local `.build-venv`. Builds target the architecture of the Mac running the script. This build is not signed with a Developer ID certificate or notarized, so macOS may show a security prompt. Removing that prompt for external distribution requires Developer ID signing and Apple notarization.

Only loopback addresses are accepted, so the server is not exposed to your network.

## Stop

The local server can be stopped when you no longer need it:

```bash
# macOS
./shutdown.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\shutdown-windows.ps1
```

Both stop scripts verify that the recorded process belongs to this workbench before stopping it.

## Data and backups

Your runtime data is kept outside the checkout in:

macOS: `~/Library/Application Support/PersonalOfficeWorkbench/`

Windows: `%APPDATA%\PersonalOfficeWorkbench\` (usually `C:\Users\<you>\AppData\Roaming\PersonalOfficeWorkbench\`)

It contains `tasks.json`, `notes.json`, `projects.json`, `logs.json`, and `meta.json`. These files are intentionally not part of this repository. Use the **Backup** view in the application to export a ZIP before moving computers or making major changes.

## Development checks

```bash
python3 -m py_compile server.py
bash -n start.sh
bash -n shutdown.sh
bash shutdown_test.sh
node smoke_test.cjs
```

`smoke_test.cjs` needs the `jsdom` package available in your Node environment; it is only used for the UI smoke test, not for running the app.

## License

[MIT](LICENSE)
