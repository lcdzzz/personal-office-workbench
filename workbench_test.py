"""Exercise source-workbench lifecycle in an isolated checkout and data folder."""
import json
import os
import shlex
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workbench lifecycle ')
        self.root = Path(self.temp.name)
        self.checkout = self.root / 'source checkout'
        self.checkout.mkdir()
        for name in ('workbench.sh', 'start.sh', 'shutdown.sh', 'restart.sh', 'cqgzt.sh', 'shutdowngzt.sh', '工作台.sh'):
            source = ROOT / name
            if source.exists():
                shutil.copy2(source, self.checkout / name)
        source = (ROOT / 'server.py').read_text()
        source = source.replace('CONFIG_PATH = APP_DIR / "config.json"',
                                'APP_DIR = Path(__file__).parent / "test-data"\nCONFIG_PATH = Path(__file__).parent / "config.json"')
        (self.checkout / 'server.py').write_text(source)
        (self.checkout / 'personal-office-workbench.html').write_text('workbench lifecycle fixture')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.config = self.checkout / 'config.json'
        self.config.write_text(json.dumps({'host':'127.0.0.1', 'port':self.port}))
        self.env = dict(os.environ, TMPDIR=str(self.root / 'runtime'))
        self.opened = self.root / 'opened-urls.log'
        mockbin = self.root / 'mock-bin'
        mockbin.mkdir()
        opener = mockbin / 'open'
        opener.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> ' + shlex.quote(str(self.opened)) + '\n')
        opener.chmod(0o755)
        self.env['PATH'] = str(mockbin) + os.pathsep + self.env['PATH']
        self.pidfile = Path(self.env['TMPDIR']) / 'personal-office-workbench/server.pid'
        self.started = set()

    def tearDown(self):
        if self.pidfile.exists() and self.pidfile.read_text().strip().isdigit():
            self.started.add(int(self.pidfile.read_text().strip()))
        for pid in self.started:
            try:
                command = subprocess.check_output(['ps','-p',str(pid),'-o','command='], text=True).strip()
                if str(self.checkout / 'server.py') in command:
                    os.kill(pid, 15)
            except (ProcessLookupError, subprocess.CalledProcessError):
                pass
        self.temp.cleanup()

    def run_script(self, action, *args, name='workbench.sh', input=None):
        try:
            result = subprocess.run(['bash', '-x', str(self.checkout / name), action, *args],
                                    cwd=self.root, env=self.env, input=input, text=True, errors='replace',
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        except subprocess.TimeoutExpired as error:
            logfile = self.pidfile.parent / 'server.log'
            detail = logfile.read_text(errors='replace') if logfile.exists() else '(no server log)'
            raise AssertionError(f'Lifecycle command timed out.\nstdout={error.stdout!r}\nstderr={error.stderr!r}\nserver={detail}') from error
        if self.pidfile.exists() and self.pidfile.read_text().strip().isdigit():
            self.started.add(int(self.pidfile.read_text().strip()))
        return result

    def ok(self, action, *args, **kwargs):
        result = self.run_script(action, *args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def pid(self):
        return int(self.pidfile.read_text().strip())

    def test_start_status_idempotence_restart_and_stop_from_another_directory(self):
        self.ok('start', '--no-open')
        first = self.pid()
        self.assertIn(str(first), self.ok('status'))
        self.ok('start', '--no-open')
        self.assertEqual(self.pid(), first)
        self.ok('restart', '--no-open')
        self.assertNotEqual(self.pid(), first)
        self.ok('stop')
        self.assertIn('未运行', self.ok('status'))
        self.ok('stop')

    def test_missing_pid_can_recover_the_verified_listener(self):
        self.ok('start', '--no-open')
        first = self.pid()
        self.pidfile.write_text('')
        self.assertIn(str(first), self.ok('status'))
        self.ok('stop')
        self.assertIn('未运行', self.ok('status'))

    def test_unrelated_pid_is_never_stopped_and_restart_aborts(self):
        process = subprocess.Popen(['sleep','30'])
        try:
            self.pidfile.parent.mkdir(parents=True)
            self.pidfile.write_text(str(process.pid))
            for action in ('stop','restart'):
                result = self.run_script(action, '--no-open')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('拒绝', result.stdout + result.stderr)
                self.assertIsNone(process.poll())
        finally:
            process.terminate()
            process.wait()

    def test_foreign_port_is_not_accepted_as_workbench(self):
        class QuietHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'not the workbench')
        http = ThreadingHTTPServer(('127.0.0.1', self.port), QuietHandler)
        thread = threading.Thread(target=http.serve_forever)
        thread.start()
        try:
            for action in ('start','stop','restart'):
                result = self.run_script(action, '--no-open')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('其他程序', result.stdout + result.stderr)
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

    def test_invalid_config_and_failed_start_return_errors(self):
        self.config.write_text('{invalid-json')
        self.assertNotEqual(self.run_script('start', '--no-open').returncode, 0)
        self.config.write_text(json.dumps({'host':'127.0.0.1','port':self.port}))
        source = self.checkout / 'server.py'
        source.write_text(source.read_text().replace('if __name__ == "__main__":',
                                                   'if __name__ == "__main__":\n    raise SystemExit(3)'))
        result = self.run_script('start','--no-open')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('启动失败', result.stdout + result.stderr)
        self.assertFalse(self.opened.exists(), '启动失败不得打开页面')

    def test_browser_is_opened_only_when_requested_after_start(self):
        self.ok('start')
        lines = self.opened.read_text().splitlines()
        self.assertEqual(lines, [f'http://127.0.0.1:{self.port}/personal-office-workbench.html'])
        self.ok('start', '--no-open')
        self.assertEqual(self.opened.read_text().splitlines(), lines)
        self.ok('stop')

    def test_interactive_menu_can_restart_without_opening_browser(self):
        output = self.ok('', '--no-open', input='3\n')
        self.assertIn('工作台已启动', output)
        self.assertFalse(self.opened.exists())
        self.ok('stop')

    def test_old_launchers_use_their_own_directory(self):
        self.ok('--no-open', name='start.sh')
        first = self.pid()
        self.ok('--no-open', name='cqgzt.sh')
        self.assertNotEqual(self.pid(), first)
        self.ok('', name='shutdowngzt.sh')
        self.ok('--no-open', name='工作台.sh')
        self.ok('--no-open', name='restart.sh')
        self.ok('', name='shutdown.sh')


if __name__ == '__main__':
    unittest.main()
