"""Compatibility entry point for existing macOS build commands."""
from desktop_app import main, server_is_ready, show_error

if __name__ == '__main__':
    raise SystemExit(main())
