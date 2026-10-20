import hashlib
import json
import threading
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.request import urlopen

import desktop_app
import server


class DesktopPackageTests(unittest.TestCase):
    def test_runtime_metadata_uses_packaged_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'ROOT',Path(directory)), patch.object(server.sys,'frozen',True,create=True):
            info={'version':'v1.0.0','sourceCommit':'a'*40,'coreSha256':'b'*64,'architecture':'arm64','platform':'darwin'}
            (Path(directory)/'build-info.json').write_text(json.dumps(info))
            server.runtime_info.cache_clear()
            try:
                self.assertEqual(server.runtime_info(),info)
            finally:
                server.runtime_info.cache_clear()

    def test_source_fingerprint_covers_html_and_server(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'ROOT',Path(directory)):
            root=Path(directory)
            (root/'personal-office-workbench.html').write_bytes(b'ui')
            (root/'server.py').write_bytes(b'backend')
            expected=hashlib.sha256(b'personal-office-workbench.html\0ui' + b'server.py\0backend').hexdigest()
            self.assertEqual(server.source_fingerprint(),expected)
            (root/'server.py').write_bytes(b'new backend')
            self.assertNotEqual(server.source_fingerprint(),expected)

    def test_old_backend_is_not_reused_by_native_app(self):
        response=Mock(status=404)
        response.read.return_value=b'{"error":"not found"}'
        connection=Mock()
        connection.getresponse.return_value=response
        with patch('desktop_app.http.client.HTTPConnection',return_value=connection):
            self.assertFalse(desktop_app.server_is_ready('127.0.0.1',8799))

    def test_fingerprints_ignore_windows_checkout_line_endings(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'ROOT',Path(directory)):
            root=Path(directory)
            for name in ('personal-office-workbench.html','server.py'):
                (root/name).write_bytes(b'first\nsecond\n')
            first=server.source_fingerprint()
            for name in ('personal-office-workbench.html','server.py'):
                (root/name).write_bytes(b'first\r\nsecond\r\n')
            self.assertEqual(server.source_fingerprint(),first)

    def test_runtime_api_identifies_the_loaded_core(self):
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever)
        thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{http.server_port}/api/runtime',timeout=3) as response:
                info=json.load(response)
            self.assertEqual(info['coreSha256'],server.runtime_info()['coreSha256'])
            self.assertEqual(len(info['coreSha256']),64)
        finally:
            http.shutdown();http.server_close();thread.join()

    def test_only_a_matching_backend_fingerprint_is_reused(self):
        connection=Mock()
        response=Mock(status=200)
        connection.getresponse.return_value=response
        with patch('desktop_app.http.client.HTTPConnection',return_value=connection), patch.object(server,'runtime_info',return_value={'coreSha256':'expected'}):
            for actual, expected in [('expected',True),('old',False)]:
                response.read.return_value=json.dumps({'coreSha256':actual}).encode()
                self.assertEqual(desktop_app.server_is_ready('127.0.0.1',8799),expected)
            response.read.return_value=b'"not an object"'
            self.assertFalse(desktop_app.server_is_ready('127.0.0.1',8799))

    def test_verification_never_resets_an_existing_unmarked_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'keep.txt').write_text('existing data')
            with self.assertRaises(ValueError):
                desktop_app.prepare_verification(root)
            self.assertEqual((root/'keep.txt').read_text(),'existing data')


if __name__ == '__main__':
    unittest.main()
