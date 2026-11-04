"""Feishu setup safety contracts; fake SDK/processes only, never real accounts."""

from contextlib import redirect_stderr, redirect_stdout
import asyncio
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import feishu_setup as setup
import workflow_bridge as bridge


APP_ID = "cli_fake_only"
APP_SECRET = "FAKE-ONLY-DO-NOT-PRINT-APP-SECRET"
RAW_ERROR = "RAW-HTTP-TENANT-TOKEN-MUST-NOT-PRINT"
OWNER = "ou_fake_owner"
CHAT = "oc_fake_private_chat"


def event(phrase, *, app=APP_ID, sender="user", chat_type="p2p", text=None):
    return {"header": {"app_id": app, "event_type": "im.message.receive_v1"},
            "event": {"sender": {"sender_type": sender, "sender_id": {"open_id": OWNER}},
                      "message": {"chat_type": chat_type, "message_type": "text", "chat_id": CHAT,
                                  "content": json.dumps({"text": phrase if text is None else text})}}}


class Pipe:
    def __init__(self, inbound=None):
        self.inbound = list(inbound or [])
        self.sent = []
        self.closed = False

    def recv(self):
        return self.inbound.pop(0)

    def send(self, value):
        self.sent.append(value)

    def poll(self, timeout):
        return bool(self.inbound)

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self):
        self.pid = None
        self.alive = True
        self.terminated = False
        self.joined = []

    def start(self):
        self.pid = 123

    def is_alive(self):
        return self.alive

    def terminate(self):
        self.terminated = True
        self.alive = False

    def join(self, timeout):
        self.joined.append(timeout)

    def kill(self):
        self.alive = False


def sdk_for_client(client):
    class Handler:
        def register_p2_im_message_receive_v1(self, callback):
            self.callback = callback
            return self
        def build(self):
            return self
    return SimpleNamespace(EventDispatcherHandler=SimpleNamespace(builder=lambda *args: Handler()),
                           ws=SimpleNamespace(Client=client), JSON=SimpleNamespace(marshal=json.dumps),
                           LogLevel=SimpleNamespace(ERROR="ERROR"))


class FakeConnectedClient:
    def __init__(self, app, secret, **kwargs):
        self.handler = kwargs["event_handler"]
        self._conn = None

    async def _connect(self):
        self._conn = object()

    async def _disconnect(self):
        self._conn = None

    async def _receive_message_loop(self):
        return None


def spawned_fake_sdk():
    """Importable spawn fixture; no HTTP stack or real SDK is used."""
    class Client(FakeConnectedClient):
        def start(self):
            asyncio.run(self._connect())
            self.handler.callback(event("spawned-one-use-phrase"))
            threading.Event().wait()  # Parent must terminate the blocked official-style start().
    return sdk_for_client(Client)


def spawned_disconnected_sdk():
    """The worker remains alive after losing its connection, as 1.7.5 can do."""
    class Client(FakeConnectedClient):
        def start(self):
            asyncio.run(self._connect())
            asyncio.run(self._disconnect())
            threading.Event().wait()
    return sdk_for_client(Client)


def spawned_receive_stopped_sdk():
    class Client(FakeConnectedClient):
        def start(self):
            asyncio.run(self._connect())
            asyncio.run(self._receive_message_loop())
            threading.Event().wait()
    return sdk_for_client(Client)


def spawned_blocked_cleanup_sdk():
    class Client(FakeConnectedClient):
        async def _disconnect(self):
            await asyncio.Event().wait()
        def start(self):
            asyncio.run(self._connect())
            asyncio.run(self._disconnect())  # The SDK close never completes.
    return sdk_for_client(Client)


class SetupTests(unittest.TestCase):
    def setUp(self):
        # Only this test's own home subdirectory; shared tmp is deliberately forbidden.
        self.temp = tempfile.TemporaryDirectory(prefix=".hc-feishu-test-", dir=Path.home())
        self.root = Path(self.temp.name)
        self.path = self.root / "private" / "feishu.json"
        self.progress = []

    def tearDown(self):
        self.temp.cleanup()

    def configured(self):
        values = iter([APP_ID, APP_SECRET])
        return setup.configure(self.path, secret_reader=lambda prompt: next(values))

    def pair(self, *, listener=None, confirmation=setup.CONFIRMATION, rebind=False):
        def matched(data, phrase, timeout, progress):
            return setup.pairing_candidate(event(phrase), data["app_id"], phrase)
        return setup.pair(self.path, listener=listener or matched, rebind=rebind,
                          confirm_reader=lambda prompt: confirmation, progress=self.progress.append)

    def test_default_and_doctor_are_offline_and_do_not_read_selected_path(self):
        for arguments in ([], ["--doctor"], ["--credentials-file", "/tmp/not-to-be-read"]):
            with redirect_stdout(io.StringIO()) as output, \
                 mock.patch.object(setup, "read_private_json", side_effect=AssertionError("must not read")), \
                 mock.patch.object(setup, "_parent", side_effect=AssertionError("must not open")), \
                 mock.patch.object(setup.importlib.metadata, "version", side_effect=AssertionError("do not import SDK")):
                code = setup.main(arguments, listener=lambda *args: self.fail("must not connect"))
            result = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertFalse(result["network_used"])
            self.assertFalse(result["credentials_read"])
            self.assertFalse(result["installed_anything"])

    def test_configure_is_private_atomic_unpaired_and_never_prints_secret(self):
        result = self.configured()
        data = setup.read_private_json(self.path)
        self.assertEqual(result["status"], "configured_not_paired")
        self.assertNotIn(APP_SECRET, json.dumps(result))
        self.assertEqual(data["app_secret"], APP_SECRET)
        self.assertEqual(data["state"], "configured")
        self.assertNotIn("approvers", data)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        with self.assertRaises(setup.SetupError):
            setup.load_feishu_environment(self.path)

    def test_configure_interruption_saves_no_file_or_partial_secret(self):
        values = iter([APP_ID])
        def reader(prompt):
            try:
                return next(values)
            except StopIteration:
                raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            setup.configure(self.path, secret_reader=reader)
        self.assertFalse(self.path.exists())
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_configure_does_not_overwrite_existing_application(self):
        self.configured()
        original = self.path.read_bytes()
        with self.assertRaises(setup.SetupError):
            setup.configure(self.path, secret_reader=lambda prompt: self.fail("do not read another credential"))
        self.assertEqual(self.path.read_bytes(), original)

    def test_pair_requires_correct_app_user_private_chat_and_exact_phrase(self):
        phrase = "one-use-phrase"
        invalid = [event(phrase, app="cli_other"), event(phrase, sender="bot"), event(phrase, chat_type="group"),
                   event(phrase, text=" " + phrase), event(phrase, text=phrase + "\n"), event(phrase, text="hello"), {}]
        for payload in invalid:
            self.assertIsNone(setup.pairing_candidate(payload, APP_ID, phrase))
        wrong_kind = event(phrase)
        wrong_kind["header"]["event_type"] = "another.event"
        self.assertIsNone(setup.pairing_candidate(wrong_kind, APP_ID, phrase))
        self.assertEqual(setup.pairing_candidate(event(phrase), APP_ID, phrase), {"open_id": OWNER, "chat_id": CHAT})

    def test_pair_saves_both_ids_and_exact_single_owner_allowlists_after_confirmation(self):
        self.configured()
        original = self.path.read_bytes()
        def listener(data, phrase, timeout, progress):
            self.assertEqual(self.path.read_bytes(), original)
            return setup.pairing_candidate(event(phrase), APP_ID, phrase)
        result = self.pair(listener=listener)
        self.assertEqual(result["status"], "paired")
        self.assertEqual(result["confirmation_reason"], "exact_confirmed")
        data = setup.read_private_json(self.path)
        self.assertEqual(data["allowed_chats"], [CHAT])
        self.assertEqual(data["approvers"], [OWNER])
        self.assertEqual(data["recipient"], CHAT)
        environment = setup.load_feishu_environment(self.path)
        self.assertEqual(environment["HC_FEISHU_APP_SECRET"], APP_SECRET)
        self.assertEqual(environment["HC_FEISHU_ALLOWED_CHATS"], CHAT)
        self.assertEqual(environment["HC_FEISHU_APPROVERS"], OWNER)
        self.assertNotIn(APP_SECRET, "\n".join(self.progress) + json.dumps(result))
        self.assertNotIn(OWNER, "\n".join(self.progress) + json.dumps(result))
        self.assertNotIn(CHAT, "\n".join(self.progress) + json.dumps(result))
        self.assertNotIn("硬核导演配对-", self.path.read_text())
        self.assertNotIn("confirmation_reason", data)

    def test_cancel_timeout_and_interrupt_preserve_original_without_half_binding(self):
        self.configured()
        original = self.path.read_bytes()
        self.assertEqual(self.pair(confirmation="no")["status"], "pairing_cancelled")
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.pair(listener=lambda *args: None)["status"], "pairing_timed_out")
        self.assertEqual(self.path.read_bytes(), original)
        def interrupted(*args):
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.pair(listener=interrupted)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_confirmation_reasons_preserve_credentials_without_recording_input(self):
        self.configured()
        original = self.path.read_bytes()
        def raises(error):
            def reader(prompt):
                raise error(APP_SECRET + RAW_ERROR)
            return reader
        cases = [(lambda prompt: "", "empty_line"),
                 (lambda prompt: " " + setup.CONFIRMATION, "nonmatching_input"),
                 (lambda prompt: setup.CONFIRMATION + "\n", "nonmatching_input"),
                 (lambda prompt: RAW_ERROR, "nonmatching_input"),
                 (raises(EOFError), "eof"), (raises(TimeoutError), "wait_timeout"),
                 (raises(RuntimeError), "read_failed"), (lambda prompt: None, "read_failed"),
                 (lambda prompt: True, "read_failed")]
        for reader, reason in cases:
            with self.subTest(reason=reason), redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors:
                result = setup.pair(self.path, listener=lambda *args: {"open_id": OWNER, "chat_id": CHAT},
                                    confirm_reader=reader, progress=self.progress.append)
            self.assertEqual(result["status"], "pairing_cancelled")
            self.assertEqual(result["confirmation_reason"], reason)
            self.assertFalse(result["binding_saved"])
            self.assertEqual(self.path.read_bytes(), original)
            self.assertEqual(list(self.path.parent.iterdir()), [self.path])
            visible = json.dumps(result) + "\n".join(self.progress) + output.getvalue() + errors.getvalue()
            for sensitive in (APP_SECRET, RAW_ERROR, OWNER, CHAT):
                self.assertNotIn(sensitive, visible)

    def test_confirmation_interrupt_is_not_misclassified_as_empty_input(self):
        self.configured()
        original = self.path.read_bytes()
        def interrupted(prompt):
            raise KeyboardInterrupt(APP_SECRET + RAW_ERROR)
        with self.assertRaises(KeyboardInterrupt):
            setup.pair(self.path, listener=lambda *args: {"open_id": OWNER, "chat_id": CHAT},
                       confirm_reader=interrupted, progress=self.progress.append)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_duplicate_pair_is_blocked_before_network_and_rebind_is_explicit(self):
        self.configured()
        self.pair()
        original = self.path.read_bytes()
        with self.assertRaises(setup.SetupError):
            self.pair(listener=lambda *args: self.fail("must not connect"))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.pair(rebind=True, confirmation="no")["status"], "pairing_cancelled")
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.pair(rebind=True)["status"], "paired")

    def test_inconsistent_or_partial_allowlists_are_not_loaded(self):
        self.configured()
        configured = setup.read_private_json(self.path)
        with self.assertRaises(setup.SetupError):
            setup._validate(dict(configured, owner_open_id=OWNER))
        self.pair()
        paired = setup.read_private_json(self.path)
        for key, value in (("approvers", [OWNER, "ou_other"]), ("allowed_chats", ["oc_other"]), ("recipient", "oc_other")):
            with self.assertRaises(setup.SetupError):
                setup._validate(dict(paired, **{key: value}), require_paired=True)

    def test_insecure_storage_symlinks_hardlinks_and_repositories_are_rejected(self):
        for path in (Path("relative.json"), Path("/tmp/feishu-test.json"), setup.PACKAGE_ROOT / "secret.json",
                     Path("/" + str(setup.PACKAGE_ROOT / "secret.json"))):
            with self.assertRaises(setup.SetupError):
                setup.configure(path, secret_reader=lambda prompt: self.fail("must reject path first"))
        self.configured()
        self.path.parent.chmod(0o755)
        with self.assertRaises(setup.SetupError):
            setup.read_private_json(self.path)
        self.path.parent.chmod(0o700)
        self.path.chmod(0o644)
        with self.assertRaises(setup.SetupError):
            setup.read_private_json(self.path)
        self.path.chmod(0o600)
        link = self.root / "symlink"
        link.symlink_to(self.path.parent, target_is_directory=True)
        with self.assertRaises(setup.SetupError):
            setup.read_private_json(link / self.path.name)
        leaf = self.path.with_name("link.json")
        leaf.symlink_to(self.path)
        with self.assertRaises(setup.SetupError):
            setup.read_private_json(leaf)
        hardlink = self.path.with_name("hard.json")
        os.link(self.path, hardlink)
        with self.assertRaises(setup.SetupError):
            setup.read_private_json(self.path)
        hardlink.unlink()
        (self.root / ".git").touch()
        with self.assertRaises(setup.SetupError):
            setup.read_private_json(self.path)

    def test_wrong_file_owner_is_rejected(self):
        self.configured()
        actual = os.fstat
        def foreign(fd):
            info = actual(fd)
            values = list(info)
            values[4] = os.getuid() + 1
            return os.stat_result(values)
        with mock.patch.object(setup.os, "fstat", side_effect=foreign), self.assertRaises(setup.SetupError):
            setup.read_private_json(self.path)

    def test_other_skill_ancestors_and_symlinked_skill_markers_are_rejected_before_secret_input(self):
        other_skill = self.root / "another-skill"
        other_skill.mkdir(mode=0o700)
        marker = other_skill / "SKILL.md"
        for symlink in (False, True):
            if symlink:
                marker.symlink_to(other_skill / "missing-target")
            else:
                marker.write_text("# Fake Skill for this test only\n")
            path = other_skill / "private" / "credentials.json"
            with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors, \
                 self.assertRaises(setup.SetupError):
                setup.configure(path, secret_reader=lambda prompt: self.fail("must reject Skill ancestor before reading secrets"))
            self.assertFalse(path.exists())
            self.assertFalse(path.parent.exists())
            self.assertEqual(output.getvalue() + errors.getvalue(), "")
            marker.unlink()

    def test_cli_requires_interactive_terminal_and_suppresses_raw_failures(self):
        with redirect_stdout(io.StringIO()) as output, mock.patch.object(sys.stdin, "isatty", return_value=False):
            code = setup.main(["--configure", "--credentials-file", str(self.path)],
                              secret_reader=lambda prompt: self.fail("must not read"))
        self.assertEqual(code, 1)
        self.assertFalse(self.path.exists())
        self.configured()
        def failed(*args):
            raise RuntimeError(APP_SECRET + RAW_ERROR)
        with redirect_stdout(io.StringIO()) as output, mock.patch.object(sys.stdin, "isatty", return_value=True):
            self.assertEqual(setup.main(["--pair", "--credentials-file", str(self.path)], listener=failed), 1)
        self.assertNotIn(APP_SECRET, output.getvalue())
        self.assertNotIn(RAW_ERROR, output.getvalue())
        self.assertEqual(setup.read_private_json(self.path)["state"], "configured")

    def test_worker_fake_sdk_filters_events_consumes_phrase_once_and_never_sends(self):
        phrase = "fake-one-use-phrase"
        connection = Pipe([({"app_id": APP_ID, "app_secret": APP_SECRET}, phrase)])
        calls = []
        class Client(FakeConnectedClient):
            def __init__(self, app_id, secret, **kwargs):
                calls.append((app_id, secret, kwargs))
                super().__init__(app_id, secret, **kwargs)
            def start(self):
                self.assert_connecting_only()
                asyncio.run(self._connect())
                for payload in (event(phrase, chat_type="group"), event(phrase, text="hello"), event(phrase), event(phrase)):
                    self.handler.callback(payload)
            def assert_connecting_only(self):
                if connection.sent != [{"status": "connecting"}]:
                    raise AssertionError("connected was reported before a handshake")
        sdk = sdk_for_client(Client)
        setup._sdk_worker(connection, sdk_loader=lambda: sdk)
        self.assertEqual(connection.sent, [{"status": "connecting"}, {"status": "connected"},
                                          {"status": "message_not_matched"},
                                          {"status": "candidate", "open_id": OWNER, "chat_id": CHAT},
                                          {"status": "listener_stopped"}])
        self.assertFalse(calls[0][2]["auto_reconnect"])
        self.assertTrue(connection.closed)

    def test_worker_does_not_claim_connected_when_handshake_fails_or_has_no_socket(self):
        for mode in ("raises", "no_socket"):
            connection = Pipe([({"app_id": APP_ID, "app_secret": APP_SECRET}, "phrase")])
            class Client(FakeConnectedClient):
                async def _connect(self):
                    if mode == "raises":
                        raise RuntimeError(APP_SECRET + RAW_ERROR)
                    return None
                def start(self):
                    asyncio.run(self._connect())
            with self.subTest(mode=mode), redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors:
                setup._sdk_worker(connection, sdk_loader=lambda: sdk_for_client(Client))
            statuses = [message["status"] for message in connection.sent]
            self.assertEqual(statuses[0], "connecting")
            self.assertNotIn("connected", statuses)
            self.assertIn("failed" if mode == "raises" else "connection_failed", statuses)
            self.assertEqual(output.getvalue() + errors.getvalue(), "")
            self.assertTrue(connection.closed)

    def test_unmatched_message_limit_never_hides_connection_control_outcomes(self):
        connection = Pipe([({"app_id": APP_ID, "app_secret": APP_SECRET}, "phrase")])
        class Client(FakeConnectedClient):
            def start(self):
                asyncio.run(self._connect())
                for _ in range(150):
                    self.handler.callback(event("phrase", text=RAW_ERROR))
                asyncio.run(self._disconnect())
                asyncio.run(self._receive_message_loop())
        setup._sdk_worker(connection, sdk_loader=lambda: sdk_for_client(Client))
        statuses = [message["status"] for message in connection.sent]
        self.assertEqual(statuses.count("message_not_matched"), 1)
        self.assertEqual(statuses, ["connecting", "connected", "message_not_matched", "disconnecting", "disconnected",
                                    "receive_stopped", "listener_stopped"])
        self.assertNotIn(RAW_ERROR, json.dumps(connection.sent))
        self.assertTrue(connection.closed)

    def test_worker_fake_http_failure_does_not_print_exception_or_secret(self):
        connection = Pipe([({"app_id": APP_ID, "app_secret": APP_SECRET}, "phrase")])
        def fake_http_sdk_loader():
            print(APP_SECRET)
            print(RAW_ERROR, file=sys.stderr)
            raise RuntimeError(APP_SECRET + RAW_ERROR)
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors:
            setup._sdk_worker(connection, sdk_loader=fake_http_sdk_loader)
        self.assertEqual(connection.sent, [{"status": "failed"}])
        self.assertEqual(output.getvalue() + errors.getvalue(), "")

    def test_worker_special_interrupt_never_reaches_process_default_exception_printer(self):
        # A separate interpreter catches failures that multiprocessing would print
        # only after leaving the worker's redirect_stdout/redirect_stderr context.
        script = '''
import json
import sys
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
import feishu_setup as setup
class Pipe:
    def recv(self):
        return ({"app_id": "cli_fake", "app_secret": "FAKE-APP-SECRET-SENTINEL"}, "phrase")
    def send(self, value):
        print(json.dumps(value))
    def close(self):
        pass
class Handler:
    def register_p2_im_message_receive_v1(self, callback):
        return self
    def build(self):
        return self
class Client:
    def __init__(self, *args, **kwargs):
        pass
    def start(self):
        raise KeyboardInterrupt("FAKE-SENSITIVE-INTERRUPT-SENTINEL")
sdk = SimpleNamespace(EventDispatcherHandler=SimpleNamespace(builder=lambda *args: Handler()),
    ws=SimpleNamespace(Client=Client), LogLevel=SimpleNamespace(ERROR="ERROR"))
setup._sdk_worker(Pipe(), sdk_loader=lambda: sdk)
'''
        result = subprocess.run([sys.executable, "-B", "-c", script, str(setup.PACKAGE_ROOT / "scripts")],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), {"status": "failed"})
        self.assertNotIn("SENTINEL", result.stdout + result.stderr)

    def test_bounded_collection_terminates_and_joins_child_on_match_timeout_or_interrupt(self):
        for mode in ("matched", "timeout", "interrupt"):
            parent = Pipe([{"status": "connected"}, {"status": "candidate", "open_id": OWNER, "chat_id": CHAT}]
                          if mode == "matched" else [])
            child, process = Pipe(), FakeProcess()
            context = SimpleNamespace(Pipe=lambda: (parent, child), Process=lambda **kwargs: process)
            clock = mock.Mock(side_effect=[0, 2]) if mode == "timeout" else lambda: 0
            with mock.patch.object(setup.importlib.metadata, "version", return_value=setup.SDK_VERSION), \
                 mock.patch.object(setup.multiprocessing, "get_context", return_value=context), \
                 mock.patch.object(setup.time, "monotonic", clock):
                if mode == "interrupt":
                    with mock.patch.object(parent, "poll", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
                        setup.collect_pair({"app_id": APP_ID, "app_secret": APP_SECRET}, "phrase", 1, lambda text: None)
                else:
                    result = setup.collect_pair({"app_id": APP_ID, "app_secret": APP_SECRET}, "phrase", 1, lambda text: None)
                    self.assertEqual(result, {"open_id": OWNER, "chat_id": CHAT} if mode == "matched" else None)
            self.assertTrue(process.terminated)
            self.assertTrue(process.joined)
            self.assertTrue(parent.closed)
            self.assertTrue(child.closed)

    def test_collection_rejects_connection_loss_even_while_worker_stays_alive(self):
        for status in ("disconnecting", "disconnected", "receive_stopped", "connection_failed", "listener_stopped", "failed"):
            parent = Pipe([{"status": "connecting"}, {"status": "connected"}, {"status": status}])
            child, process = Pipe(), FakeProcess()
            context = SimpleNamespace(Pipe=lambda: (parent, child), Process=lambda **kwargs: process)
            with self.subTest(status=status), \
                 mock.patch.object(setup.importlib.metadata, "version", return_value=setup.SDK_VERSION), \
                 mock.patch.object(setup.multiprocessing, "get_context", return_value=context), \
                 mock.patch.object(setup.time, "monotonic", side_effect=range(30)), \
                 self.assertRaises(setup.SetupError):
                setup.collect_pair({"app_id": APP_ID, "app_secret": APP_SECRET}, "phrase", 10, self.progress.append)
            self.assertTrue(process.terminated)
            self.assertTrue(process.joined)
            self.assertTrue(parent.closed)
            self.assertTrue(child.closed)
            self.assertNotIn(APP_SECRET, "\n".join(self.progress))

    def test_candidate_requires_handshake_and_later_listener_cleanup_does_not_undo_match(self):
        candidate = {"status": "candidate", "open_id": OWNER, "chat_id": CHAT}
        for confirmed in (False, True):
            parent = Pipe(([{"status": "connected"}] if confirmed else []) +
                          [candidate, {"status": "disconnecting"}, {"status": "disconnected"}, {"status": "receive_stopped"}])
            child, process = Pipe(), FakeProcess()
            context = SimpleNamespace(Pipe=lambda: (parent, child), Process=lambda **kwargs: process)
            with self.subTest(confirmed=confirmed), \
                 mock.patch.object(setup.importlib.metadata, "version", return_value=setup.SDK_VERSION), \
                 mock.patch.object(setup.multiprocessing, "get_context", return_value=context):
                if confirmed:
                    result = setup.collect_pair({"app_id": APP_ID, "app_secret": APP_SECRET}, "phrase", 5, self.progress.append)
                    self.assertEqual(result, {"open_id": OWNER, "chat_id": CHAT})
                else:
                    with self.assertRaises(setup.SetupError):
                        setup.collect_pair({"app_id": APP_ID, "app_secret": APP_SECRET}, "phrase", 5, self.progress.append)
            self.assertTrue(process.terminated)
            self.assertTrue(process.joined)
            self.assertTrue(parent.closed)

    def test_unreviewed_sdk_version_is_blocked_without_starting_process(self):
        with mock.patch.object(setup.importlib.metadata, "version", return_value="9.9.9"), \
             mock.patch.object(setup.multiprocessing, "get_context", side_effect=AssertionError("must not start")), \
             self.assertRaises(setup.SetupError):
            setup.collect_pair({"app_id": APP_ID, "app_secret": APP_SECRET}, "phrase", 1, lambda text: None)

    def test_real_spawn_with_fake_sdk_stops_the_blocking_listener(self):
        real_context = setup.multiprocessing.get_context("spawn")
        processes = []
        def process_factory(**kwargs):
            process = real_context.Process(**kwargs, kwargs={"sdk_loader": spawned_fake_sdk})
            processes.append(process)
            return process
        context = SimpleNamespace(Pipe=real_context.Pipe, Process=process_factory)
        with mock.patch.object(setup.importlib.metadata, "version", return_value=setup.SDK_VERSION), \
             mock.patch.object(setup.multiprocessing, "get_context", return_value=context):
            result = setup.collect_pair({"app_id": APP_ID, "app_secret": APP_SECRET},
                                        "spawned-one-use-phrase", 5, lambda text: None)
        self.assertEqual(result, {"open_id": OWNER, "chat_id": CHAT})
        self.assertFalse(processes[0].is_alive())
        self.assertIsNotNone(processes[0].exitcode)

    def test_real_spawn_reports_connection_loss_without_waiting_for_live_worker_to_exit(self):
        real_context = setup.multiprocessing.get_context("spawn")
        for loader in (spawned_disconnected_sdk, spawned_receive_stopped_sdk, spawned_blocked_cleanup_sdk):
            processes = []
            def process_factory(**kwargs):
                process = real_context.Process(**kwargs, kwargs={"sdk_loader": loader})
                processes.append(process)
                return process
            context = SimpleNamespace(Pipe=real_context.Pipe, Process=process_factory)
            with self.subTest(loader=loader.__name__), \
                 mock.patch.object(setup.importlib.metadata, "version", return_value=setup.SDK_VERSION), \
                 mock.patch.object(setup.multiprocessing, "get_context", return_value=context), \
                 self.assertRaises(setup.SetupError):
                setup.collect_pair({"app_id": APP_ID, "app_secret": APP_SECRET}, "phrase", 5, self.progress.append)
            self.assertFalse(processes[0].is_alive())
            self.assertIsNotNone(processes[0].exitcode)

    def test_bridge_doctor_never_reads_feishu_file_and_rejects_mismatched_or_double_files(self):
        with redirect_stdout(io.StringIO()) as output, \
             mock.patch.object(setup, "load_feishu_environment", side_effect=AssertionError("doctor must not read")):
            self.assertEqual(bridge.main(["--channel", "feishu", "--doctor", "--feishu-credentials", "/tmp/unread"]), 0)
        for arguments in (["--channel", "wechat", "--feishu-credentials", "/tmp/unread"],
                          ["--channel", "feishu", "--wechat-credentials", "/tmp/unread"],
                          ["--channel", "feishu", "--feishu-credentials", "/tmp/a", "--wechat-credentials", "/tmp/b"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                bridge.main(arguments)

    def test_bridge_loads_paired_file_only_for_run_and_restores_environment(self):
        self.configured()
        self.pair()
        engine_db = self.root / "engine.sqlite"
        engine_db.touch(mode=0o600)
        fake_channel = SimpleNamespace(broker=SimpleNamespace(close=lambda: None))
        fake_engine = mock.Mock()
        observed = []
        fake_bridge = SimpleNamespace(run=lambda **kwargs: observed.append(os.environ.get("HC_FEISHU_APP_SECRET")))
        with mock.patch.dict(os.environ, {"HC_FEISHU_APP_SECRET": "ORIGINAL"}), \
             mock.patch.object(bridge, "create_channel", return_value=fake_channel), \
             mock.patch.object(bridge, "WorkflowBridge", return_value=fake_bridge), \
             mock.patch("hc_workflow.engine.Engine", return_value=fake_engine), \
             mock.patch("hc_workflow.providers.get_provider", return_value=mock.Mock()):
            code = bridge.main(["--channel", "feishu", "--run", "--feishu-credentials", str(self.path),
                                "--engine-db", str(engine_db), "--approval-db", str(self.root / "approval.sqlite"),
                                "--artifact-root", str(self.root), "--project-id", "fake-project"])
            self.assertEqual(os.environ["HC_FEISHU_APP_SECRET"], "ORIGINAL")
        self.assertEqual(code, 0)
        self.assertEqual(observed, [APP_SECRET])
        fake_engine.status.assert_called_once_with("fake-project")


if __name__ == "__main__":
    unittest.main()
