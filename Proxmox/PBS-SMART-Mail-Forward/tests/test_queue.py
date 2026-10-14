"""Isolated tests: no Docker, network, PBS or real mail is involved."""
import importlib.machinery
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "pbs-smart-queue"


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        loader = importlib.machinery.SourceFileLoader("pbs_smart_queue_test", str(SRC))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.mod = importlib.util.module_from_spec(spec)
        loader.exec_module(self.mod)
        self.mod.SPOOL = root / "spool"
        self.mod.SPOOL.mkdir(mode=0o700)
        self.mail = root / "sample.eml"
        self.mail.write_bytes(b"From: a@b\nTo: root\nSubject: TEST\n\nTest body\n")
        self.mock = root / "fake-forwarder"
        self.mock.write_text("#!/bin/sh\nexit 0\n")
        self.mock.chmod(0o700)
        self.mod.FORWARDER = str(self.mock)
        self.mod._checked_helper_available = lambda: True

    def queued(self):
        with sqlite3.connect(self.mod.SPOOL / "queue.sqlite3") as con:
            return con.execute("SELECT attempts, next_attempt_at, body FROM mail_queue").fetchall()

    def test_success_removes_only_after_ack(self):
        self.mod.enqueue(self.mail)
        self.assertEqual(len(self.queued()), 1)
        self.mod.drain()
        self.assertEqual(len(self.queued()), 0)

    def test_failure_is_durable_and_retried(self):
        self.mock.write_text("#!/bin/sh\nexit 24\n")
        self.mod.enqueue(self.mail)
        self.mod.drain()
        self.assertEqual(self.queued()[0][0], 1)
        self.assertEqual(self.queued()[0][2], self.mail.read_bytes())
        # Pending across connections (simulated restart); retry after due time.
        with sqlite3.connect(self.mod.SPOOL / "queue.sqlite3") as con:
            con.execute("UPDATE mail_queue SET next_attempt_at=0")
        self.mock.write_text("#!/bin/sh\nexit 0\n")
        self.mod.drain()
        self.assertEqual(len(self.queued()), 0)

    def test_unverified_helper_does_not_remove(self):
        self.mod._checked_helper_available = lambda: False
        self.mod.enqueue(self.mail)
        self.mod.drain()
        self.assertEqual(self.queued()[0][0], 1)

    def test_queue_limit_never_evicts_older_mail(self):
        self.mod.MAX_PENDING_COUNT = 1
        self.mod.enqueue(self.mail)
        with self.assertRaisesRegex(RuntimeError, "queue full"):
            self.mod.enqueue(self.mail)
        self.assertEqual(len(self.queued()), 1)

    def test_message_size_limit(self):
        self.mail.write_bytes(b"x" * (256 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.mod.enqueue(self.mail)


if __name__ == "__main__":
    unittest.main()
