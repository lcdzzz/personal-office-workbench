# Personal Office Workbench

A lightweight, local-first personal workbench for tracking tasks, notes, and projects. It runs entirely on your computer: the interface is a single HTML page and the bundled Python server stores data in local JSON files.

## Features

- Focus view for the work that needs attention now
- Task, note, and project management
- JSON data stored locally, not in a cloud service
- ZIP export, preview, merge, and restore
- Atomic writes with backup files and generation checks to avoid silently losing inconsistent data
- Chinese and English interface

## Requirements

- macOS (the included launcher opens the default browser with `open`)
- Python 3

No database, Node.js runtime, or third-party Python package is required to run the application.

## Start

```bash
chmod +x start.sh
./start.sh
```

The launcher starts a server on `http://127.0.0.1:8799` and opens the workbench in your browser. If that port is occupied, create this file and choose a free local port:

`~/Library/Application Support/PersonalOfficeWorkbench/config.json`

```json
{
  "host": "127.0.0.1",
  "port": 8799
}
```

Only loopback addresses are accepted, so the server is not exposed to your network.

## Data and backups

Your runtime data is kept outside the checkout in:

`~/Library/Application Support/PersonalOfficeWorkbench/`

It contains `tasks.json`, `notes.json`, `projects.json`, and `meta.json`. These files are intentionally not part of this repository. Use the **Backup** view in the application to export a ZIP before moving computers or making major changes.

## Development checks

```bash
python3 -m py_compile server.py
bash -n start.sh
node smoke_test.cjs
```

`smoke_test.cjs` needs the `jsdom` package available in your Node environment; it is only used for the UI smoke test, not for running the app.

## License

[MIT](LICENSE)
