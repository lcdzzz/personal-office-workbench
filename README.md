# Personal Office Workbench

A lightweight, local-first personal workbench for tracking tasks, notes, and projects. It runs entirely on your computer: the interface is a single HTML page and the bundled Python server stores data in local JSON files.

## Features

- Focus view for the work that needs attention now
- Task, note, project, and work-log management
- Link tasks to local files and folders, with notes capturing lessons learned; browse all linked resources from the sidebar
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

## Start, stop, restart, and status (macOS source version)

Use the unified controller from the repository directory:

```bash
./workbench.sh start                 # Start and open the browser
./workbench.sh stop                  # Stop the source-workbench server
./workbench.sh restart               # Stop, wait for exit, then start the current code
./workbench.sh status                # Show the running PID and URL
./workbench.sh                       # Interactive menu
./workbench.sh restart --no-open     # Restart without opening a browser tab
```

Save pending edits in the page before restarting. Restart stops the old Python process so backend code changes take effect; refreshing the page alone does not reload backend code. The controller reads the configured loopback host and port and reports configuration errors, startup failures, or occupied ports.

`start.sh`, `shutdown.sh`, and `restart.sh` are shortcuts to the same controller. The Raycast entries `工作台.sh` (start), `shutdowngzt.sh` (stop), and `cqgzt.sh` (restart) resolve their own directory, so they also work when launched from another folder.

Before stopping a process, the controller checks its Python command line against this checkout's exact `server.py` path. If the PID file is missing, it finds the port listener and applies the same check. Unrelated processes and ambiguous matches are rejected; a failed stop prevents the restart from starting another server. These scripts manage the source server; a separately installed macOS app keeps its own lifecycle.

## Data and backups

Use **Add link** when creating or editing a task to paste an absolute local file or folder path and add a note about the result or lesson learned. Multiple links are supported. **Linked files** in the sidebar groups matching paths and shows every associated task, including completed and abandoned tasks. Search by path, task title, or note, filter files/folders, copy paths, or show resources in the system file manager. Click a task title to edit its links. Missing or moved resources keep their references; update their paths in the task editor when needed.

Links reference the original location. Unlinking or deleting a task does not delete the resource. ZIP/JSON backups contain paths and notes, not the linked files or folder contents; paths may need updating after moving to another computer.

Your runtime data is kept outside the checkout in:

macOS: `~/Library/Application Support/PersonalOfficeWorkbench/`

Windows: `%APPDATA%\PersonalOfficeWorkbench\` (usually `C:\Users\<you>\AppData\Roaming\PersonalOfficeWorkbench\`)

It contains `tasks.json`, `notes.json`, `projects.json`, `logs.json`, and `meta.json`. These files are intentionally not part of this repository. Use the **Backup** view in the application to export a ZIP before moving computers or making major changes.

## Development checks

```bash
python3 -m py_compile server.py
python3 -m unittest -v linked_files_server_test.py workbench_test.py
bash -n workbench.sh
bash -n restart.sh
bash -n start.sh
bash -n shutdown.sh
bash shutdown_test.sh
node smoke_test.cjs
node linked_files_test.cjs
```

`smoke_test.cjs` needs the `jsdom` package available in your Node environment; it is only used for the UI smoke test, not for running the app.

## License

[MIT](LICENSE)
