"""The official QR protocol is exercised only against fake HTTP responses."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import workflow_login as login


TOKEN = "FAKE-ONLY-BOT-TOKEN"
BOT_ID = "FAKE-ONLY-BOT-ID"
QR_URL = "https://liteapp.weixin.qq.com/qrcode?ticket=fake-only"


class Clock:
    def __init__(self):
        self.value = 2000000000.0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class HTTP:
    def __init__(self, states=None):
        self.calls = []
        self.states = list(states or [{"status": "wait"}])
        self.begin_error = False
        self.qr_response = {"qrcode": "fake-opaque-challenge", "qrcode_img_content": QR_URL}

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body, "timeout": timeout})
        if "get_bot_qrcode" in url:
            if self.begin_error:
                raise RuntimeError("DO-NOT-PRINT-RAW-EXCEPTION")
            response = self.qr_response
        else:
            response = self.states.pop(0) if len(self.states) > 1 else self.states[0]
            if isinstance(response, Exception):
                raise response
        return 200, {}, json.dumps(response).encode()


class LoginTests(unittest.TestCase):
    def setUp(self):
        # Credential storage intentionally disallows the shared temp tree.
        # The test creates and later removes only its own private home subfolder.
        self.temp = tempfile.TemporaryDirectory(prefix=".hc-login-test-", dir=Path.home())
        self.root = Path(self.temp.name)
        self.credentials = self.root / "new-private-parent" / "wechat.json"
        self.challenge = self.credentials.with_name(self.credentials.name + ".challenge.json")
        self.clock = Clock()
        self.http = HTTP()
        self.wizard = login.WeChatLogin(request_fn=self.http, clock=self.clock, sleep=self.clock.sleep)

    def tearDown(self):
        self.temp.cleanup()

    def begin(self):
        return self.wizard.begin(self.credentials)

    def confirm(self):
        self.http.states = [{"status": "confirmed", "bot_token": TOKEN, "ilink_bot_id": BOT_ID,
                             "baseurl": login.API_BASE, "ilink_user_id": "fake-peer"}]
        return self.wizard.wait(self.credentials, timeout=2)

    def test_default_and_doctor_never_read_files_or_contact_network(self):
        for arguments in ([], ["--doctor"], ["wechat", "--doctor", "--credentials-file", "/tmp/not-to-be-read"],
                          ["dreamina", "--doctor"], ["minimax-design", "--doctor"]):
            with redirect_stdout(io.StringIO()) as stream, mock.patch.object(login, "read_private_json", side_effect=AssertionError("must not read")):
                code = login.main(arguments, request_fn=lambda *a: self.fail("doctor must not use HTTP"))
            result = json.loads(stream.getvalue())
            self.assertEqual(code, 0)
            self.assertFalse(result["network_used"])
            self.assertFalse(result["credentials_read"])
            self.assertFalse(result["login_performed"])

    def test_begin_contract_has_no_existing_tokens_or_auth_header(self):
        result = self.begin()
        self.assertEqual(result["status"], "awaiting_scan")
        self.assertEqual(result["qrcode_url"], QR_URL)
        self.assertFalse(result["qr_image_generated"])
        request = self.http.calls[0]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["url"], login.API_BASE + "/ilink/bot/get_bot_qrcode?bot_type=3")
        self.assertEqual(json.loads(request["body"]), {"local_token_list": []})
        self.assertIn("AuthorizationType", request["headers"])
        self.assertIn("X-WECHAT-UIN", request["headers"])
        self.assertNotIn("Authorization", request["headers"])
        self.assertFalse(self.credentials.exists())
        self.assertEqual(stat.S_IMODE(self.challenge.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.challenge.parent.stat().st_mode), 0o700)

    def test_begin_reuses_same_active_challenge_without_request(self):
        self.begin()
        result = self.begin()
        self.assertTrue(result["reused_challenge"])
        self.assertEqual(len(self.http.calls), 1)

    def test_lost_begin_is_recorded_unknown_and_not_automatically_repeated(self):
        self.http.begin_error = True
        result = self.begin()
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("DO-NOT-PRINT", json.dumps(result))
        self.assertEqual(self.begin()["status"], "unknown")
        self.assertEqual(len(self.http.calls), 1)
        self.http.begin_error = False
        self.assertEqual(self.wizard.begin(self.credentials, restart=True)["status"], "awaiting_scan")
        self.assertEqual(len(self.http.calls), 2)

    def test_confirmed_credentials_private_and_result_contains_no_values(self):
        self.begin()
        result = self.confirm()
        self.assertEqual(result["status"], "connected")
        rendered = json.dumps(result)
        self.assertNotIn(TOKEN, rendered)
        self.assertNotIn(BOT_ID, rendered)
        self.assertEqual(stat.S_IMODE(self.credentials.stat().st_mode), 0o600)
        saved = login.load_wechat_credentials(self.credentials)
        self.assertEqual(saved["bot_token"], TOKEN)
        self.assertEqual(saved["ilink_bot_id"], BOT_ID)
        self.assertNotIn("qrcode", login.read_private_json(self.challenge))
        request = self.http.calls[-1]
        self.assertEqual(request["method"], "GET")
        for name in ("Authorization", "AuthorizationType", "X-WECHAT-UIN"):
            self.assertNotIn(name, request["headers"])
        self.assertEqual(parse_qs(urlsplit(request["url"]).query)["qrcode"], ["fake-opaque-challenge"])

    def test_wait_is_bounded_and_never_creates_second_qrcode(self):
        self.begin()
        self.http.states = [{"status": "scaned"}, {"status": "wait"}]
        before = self.clock.value
        result = self.wizard.wait(self.credentials, timeout=3, interval=1)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(self.clock.value - before, 3)
        self.assertEqual(sum("get_bot_qrcode" in call["url"] for call in self.http.calls), 1)
        self.assertTrue(all("qrcode=fake-opaque-challenge" in call["url"] for call in self.http.calls[1:]))
        self.assertFalse(self.credentials.exists())

    def test_readonly_poll_errors_retain_same_challenge(self):
        self.begin()
        self.http.states = [RuntimeError("RAW SECRET URL")]
        result = self.wizard.wait(self.credentials, timeout=10)
        self.assertEqual(result["status"], "pending_network")
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual(sum("get_bot_qrcode" in call["url"] for call in self.http.calls), 1)

    def test_expired_does_not_refresh_and_expiry_does_not_extend_on_resume(self):
        self.begin()
        self.clock.value += login.CHALLENGE_TTL
        result = self.wizard.wait(self.credentials, timeout=1)
        self.assertEqual(result["status"], "expired")
        self.assertFalse(result["network_used"])
        self.assertEqual(len(self.http.calls), 1)

    def test_server_expired_is_terminal_for_that_challenge(self):
        self.begin()
        self.http.states = [{"status": "expired"}]
        self.assertEqual(self.wizard.wait(self.credentials, timeout=1)["status"], "expired")
        count = len(self.http.calls)
        self.assertEqual(self.wizard.wait(self.credentials, timeout=1)["status"], "expired")
        self.assertEqual(len(self.http.calls), count)
        # An explicit new begin, unlike wait, can replace a known expired challenge.
        self.assertEqual(self.begin()["status"], "awaiting_scan")
        self.assertEqual(sum("get_bot_qrcode" in call["url"] for call in self.http.calls), 2)

    def test_pairing_digits_use_same_challenge_and_are_not_saved(self):
        self.begin()
        self.http.states = [{"status": "need_verifycode"}]
        self.assertEqual(self.wizard.wait(self.credentials, timeout=1)["status"], "needs_verification")
        result = self.wizard.wait(self.credentials, timeout=1, verify_code="123456")
        self.assertEqual(result["status"], "needs_verification")
        self.assertEqual(parse_qs(urlsplit(self.http.calls[-1]["url"]).query)["verify_code"], ["123456"])
        self.assertNotIn("123456", self.challenge.read_text())
        self.assertNotIn("123456", json.dumps(result))

    def test_untrusted_redirect_and_api_region_are_not_followed(self):
        self.begin()
        self.http.states = [{"status": "scaned_but_redirect", "redirect_host": "evil.example"}]
        result = self.wizard.wait(self.credentials, timeout=1)
        self.assertEqual(result["status"], "unsupported_region")
        self.assertTrue(all(urlsplit(call["url"]).netloc == "ilinkai.weixin.qq.com" for call in self.http.calls))
        self.http.states = [{"status": "confirmed", "bot_token": TOKEN, "ilink_bot_id": BOT_ID, "baseurl": "https://evil.example"}]
        with self.assertRaises(login.LoginError):
            self.wizard.wait(self.credentials, timeout=1)
        self.assertFalse(self.credentials.exists())

    def test_unknown_qr_image_content_is_not_fabricated(self):
        self.http.qr_response["qrcode_img_content"] = "not-a-documented-URL-or-image"
        result = self.begin()
        self.assertIsNone(result["qrcode_url"])
        self.assertFalse(result["qr_image_generated"])
        self.assertEqual(len(list(self.credentials.parent.glob("*.png"))), 0)

    def test_existing_credentials_are_not_replaced_without_explicit_flag(self):
        self.begin()
        self.confirm()
        initial = self.credentials.read_bytes()
        count = len(self.http.calls)
        with self.assertRaises(login.LoginError):
            self.begin()
        self.assertEqual(self.credentials.read_bytes(), initial)
        self.assertEqual(len(self.http.calls), count)

    def test_destination_and_challenge_must_remain_bound(self):
        self.begin()
        with self.assertRaises(login.LoginError):
            self.wizard.wait(self.credentials.with_name("another.json"), challenge_file=self.challenge, timeout=1)
        self.assertEqual(len(self.http.calls), 1)

    def test_shared_tmp_repository_symlink_and_insecure_files_refused(self):
        with self.assertRaises(login.LoginError):
            self.wizard.begin(Path(tempfile.gettempdir()) / "forbidden-wechat-test.json")
        repo = self.root / "repository"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: fake-test-marker")
        with self.assertRaises(login.LoginError):
            self.wizard.begin(repo / "credentials.json")
        link = self.root / "linked"
        link.symlink_to(repo, target_is_directory=True)
        with self.assertRaises(login.LoginError):
            self.wizard.begin(link / "credentials.json")
        self.begin()
        os.chmod(self.challenge, 0o644)
        with self.assertRaises(login.LoginError):
            self.wizard.wait(self.credentials, timeout=1)

    def test_failed_or_incomplete_confirmation_is_not_saved(self):
        self.begin()
        self.http.states = [{"status": "confirmed", "bot_token": TOKEN}]
        with self.assertRaises(login.LoginError):
            self.wizard.wait(self.credentials, timeout=1)
        self.assertFalse(self.credentials.exists())

    def test_cli_never_prints_tokens_or_bot_ids(self):
        with redirect_stdout(io.StringIO()) as begin_output:
            code = login.main(["wechat", "--begin", "--credentials-file", str(self.credentials)],
                              request_fn=self.http, clock=self.clock, sleep=self.clock.sleep)
        self.assertEqual(code, 0)
        self.http.states = [{"status": "confirmed", "bot_token": TOKEN, "ilink_bot_id": BOT_ID}]
        with redirect_stdout(io.StringIO()) as wait_output:
            code = login.main(["wechat", "--wait", "--credentials-file", str(self.credentials)],
                              request_fn=self.http, clock=self.clock, sleep=self.clock.sleep)
        self.assertEqual(code, 0)
        output = begin_output.getvalue() + wait_output.getvalue()
        self.assertNotIn(TOKEN, output)
        self.assertNotIn(BOT_ID, output)
        self.assertIn("HC_WECHAT_BOT_TOKEN", output)
        self.assertIn("--wechat-credentials", output)


if __name__ == "__main__":
    unittest.main()
