import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from unittest.mock import patch

from egobits.desktop import service
from egobits.adapters.xml_adapter import Library


class DesktopAuthTests(unittest.TestCase):
    def test_packaged_backend_requires_session_token(self):
        # Authentication must not depend on tasklist completing within 2s.
        monitor = patch.object(service._MONITOR, 'check_state', return_value='unknown')
        monitor.start()
        self.addCleanup(monitor.stop)
        # Test authentication against the bundled fixture, not the DJ's XML.
        # Parsing a real 23k-track collection can exceed this security test's timeout.
        library = patch.object(service, '_GLOBAL_LIB', Library(service.EXAMPLES_DIR / 'library.xml'))
        library.start()
        self.addCleanup(library.stop)
        old_token = service._SESSION_TOKEN
        service._SESSION_TOKEN = 'test-session-token'
        server = HTTPServer(('127.0.0.1', 0), service.EgoBitsRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/api/status'
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(url, timeout=2)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()

            request = urllib.request.Request(url, headers={'X-EgoBits-Token': 'test-session-token',
                                                           'Origin': 'http://tauri.localhost'})
            with urllib.request.urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'http://tauri.localhost')

            for filename in ('rekord-ia.png', 'favicon.png'):
                image_request = urllib.request.Request(url.replace('/api/status', '/' + filename),
                    headers={'X-EgoBits-Token': 'test-session-token'})
                with urllib.request.urlopen(image_request, timeout=2) as response:
                    self.assertEqual(response.headers['Content-Type'], 'image/png')
                    self.assertTrue(response.read().startswith(b'\x89PNG\r\n\x1a\n'))

            blocked = urllib.request.Request(url, headers={'X-EgoBits-Token': 'test-session-token',
                                                           'Origin': 'https://attacker.invalid'})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(blocked, timeout=2)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            service._SESSION_TOKEN = old_token
