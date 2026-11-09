import io
import json
import os
import tempfile
import unittest
import urllib.error

from kohaku_tabletd import updates


def opener_returning(payload=None, error=None):
    def opener(request, timeout):
        assert request.full_url == updates.API_URL
        assert request.get_header("User-agent").startswith("kohaku-tabletd/")
        if error:
            raise error
        return io.BytesIO(json.dumps(payload).encode())
    return opener


class UpdatesTest(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(updates.parse_version("v0.10.2-rc1"), (0, 10, 2))
        self.assertTrue(updates.is_newer("v0.10.0", "0.9.9"))
        self.assertFalse(updates.is_newer("0.2.0", "0.2.0"))

    def test_available(self):
        result = updates.check(opener_returning({"tag_name": "v99.0.0", "html_url": "https://x/r"}))
        self.assertEqual((result["state"], result["latest"], result["url"]), ("available", "99.0.0", "https://x/r"))

    def test_up_to_date(self):
        result = updates.check(opener_returning({"tag_name": "v0.0.1"}))
        self.assertEqual((result["state"], result["url"]), ("up-to-date", updates.RELEASES_URL))

    def test_no_release_and_errors(self):
        not_found = urllib.error.HTTPError(updates.API_URL, 404, "Not Found", {}, None)
        self.assertEqual(updates.check(opener_returning(error=not_found))["state"], "no-release")
        offline = urllib.error.URLError("no network")
        result = updates.check(opener_returning(error=offline))
        self.assertEqual((result["state"], result["error"]), ("error", "no network"))
        self.assertEqual(updates.check(opener_returning({"name": "untagged"}))["state"], "error")

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a", "update.json")
            self.assertEqual(updates.load_state(path), {})
            updates.save_state({"notified": "0.3.0"}, path)
            self.assertEqual(updates.load_state(path), {"notified": "0.3.0"})
