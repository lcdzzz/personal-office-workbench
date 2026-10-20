import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import server


class LinkedFileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original_dir = server.APP_DIR
        server.APP_DIR = Path(self.directory.name)
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.http.server_port}'

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        server.APP_DIR = self.original_dir
        self.directory.cleanup()

    def request(self, path='/api/workbench', state=None, method=None, headers=None):
        body = json.dumps(state).encode() if isinstance(state, dict) else state
        req = Request(self.url + path, data=body, method=method, headers=headers or {})
        try:
            with urlopen(req) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def linked_state(self, path, kind='file'):
        state = server.initial_state()
        state['tasks'] = [{'id': 'linked', 'title': '经验任务', 'linkedFiles': [
            {'path': str(path), 'kind': kind, 'note': '现场排障经验'}]}]
        return self.request(state=state, method='PUT')[1]

    def reveal(self, path, origin=None, task_id='linked', headers=None):
        return self.request('/api/linked-files/reveal', {'taskId': task_id, 'path': str(path)}, 'POST',
                            headers if headers is not None else {'Origin': origin or self.url})

    def test_linked_files_survive_save_backup_and_import(self):
        saved = self.linked_state(Path(self.directory.name) / '不存在的经验.md')
        _, reloaded = self.request()
        self.assertEqual(reloaded['tasks'], saved['tasks'])
        raw = server.zip_bytes(saved)
        self.assertEqual(server.state_from_zip(raw)['tasks'], saved['tasks'])
        status, imported = self.request('/api/backup/import?mode=replace', raw, 'POST', {'If-Match': str(saved['generation'])})
        self.assertEqual(status, 200)
        self.assertEqual(imported['tasks'], saved['tasks'])
        self.assertEqual(server.state_from_zip(json.dumps(saved).encode())['tasks'], saved['tasks'])
        merged = server.merge_states(server.initial_state(), saved)
        self.assertEqual(merged['tasks'][0]['linkedFiles'], saved['tasks'][0]['linkedFiles'])

    def test_reveal_only_saved_local_links_and_check_missing_file(self):
        path = Path(self.directory.name) / '经验.md'
        self.linked_state(path)
        self.assertEqual(self.reveal(path)[0], 400, '失效路径应提示错误，保留关联')
        path.write_text('经验', encoding='utf-8')
        with patch('server.subprocess.run') as run:
            self.assertEqual(self.reveal(path, origin='https://evil.example')[0], 403)
            self.assertEqual(self.reveal(path, origin=self.url + '.evil.example')[0], 403)
            self.assertEqual(self.reveal(path, headers={})[0], 403)
            self.assertEqual(self.reveal(path, task_id='missing')[0], 400)
            self.assertEqual(self.reveal(path.parent)[0], 400)
            run.assert_not_called()
            self.assertEqual(self.reveal(path)[0], 200)
            run.assert_called_once()
            self.assertIsInstance(run.call_args.args[0], list)
            self.assertNotIn('shell', run.call_args.kwargs)

    def test_reveal_directory_and_type_mismatch(self):
        path = Path(self.directory.name) / '经验目录'
        path.mkdir()
        self.linked_state(path, 'file')
        with patch('server.subprocess.run') as run:
            self.assertEqual(self.reveal(path)[0], 400)
            run.assert_not_called()
        state = self.request()[1]
        state['tasks'][0]['linkedFiles'][0]['kind'] = 'directory'
        self.request(state=state, method='PUT')
        with patch('server.subprocess.run') as run:
            self.assertEqual(self.reveal(path)[0], 200)
            self.assertEqual(run.call_args.args[0][-1], str(path))

    def test_reveal_system_commands_and_os_error(self):
        path = Path(self.directory.name) / 'a $(literal) "quoted".md'
        path.write_text('经验', encoding='utf-8')
        self.linked_state(path)
        with patch('server.sys.platform', 'darwin'), patch('server.subprocess.run') as run:
            server.reveal_linked_file('linked', str(path))
            self.assertEqual(run.call_args.args[0], ['open', '-R', '--', str(path)])
        with patch('server.sys.platform', 'win32'), patch('server.subprocess.run') as run:
            server.reveal_linked_file('linked', str(path))
            self.assertEqual(run.call_args.args[0], ['explorer.exe', '/select,', str(path)])
        with patch('server.subprocess.run', side_effect=OSError('missing file manager')):
            self.assertEqual(self.reveal(path)[0], 400)

    def test_mac_directory_reveals_when_finder_cannot_open(self):
        path = Path(self.directory.name) / 'Example.app'
        path.mkdir()
        self.linked_state(path, 'directory')
        with patch('server.sys.platform', 'darwin'), patch('server.subprocess.run', side_effect=[subprocess.CalledProcessError(1, 'open'), None]) as run:
            self.assertEqual(self.reveal(path)[0], 200)
            self.assertEqual(run.call_args_list[0].args[0], ['open', '-a', '/System/Library/CoreServices/Finder.app', '--', str(path)])
            self.assertEqual(run.call_args_list[1].args[0], ['open', '-R', '--', str(path)])



if __name__ == "__main__":
    unittest.main()
