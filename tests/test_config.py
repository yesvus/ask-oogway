"""Tests for ask_oogway.config.get_provider."""

import os
import stat
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from ask_oogway import config
from ask_oogway.config import DEFAULT_PROVIDER, get_provider
from ask_oogway.errors import AskOogwayError


class TestGetProvider(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config_path = Path(self._tmp.name) / "config.toml"
        patcher = mock.patch.object(config, "CONFIG_PATH", self.config_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.bindir = Path(self._tmp.name) / "bin"
        self.bindir.mkdir()
        env_patcher = mock.patch.dict(os.environ, {"PATH": str(self.bindir)})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

    def _write_bin(self, name):
        path = self.bindir / name
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(
            stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
        )

    def test_missing_file_returns_default(self):
        self.assertFalse(self.config_path.exists())
        self.assertEqual(get_provider(), "claude")
        self.assertEqual(get_provider(), DEFAULT_PROVIDER)

    def test_chatgpt_provider(self):
        self.config_path.write_text('provider = "chatgpt"\n')
        self.assertEqual(get_provider(), "chatgpt")

    def test_valid_toml_without_provider_returns_default(self):
        self.config_path.write_text('foo = "bar"\n')
        self.assertEqual(get_provider(), "claude")

    def test_empty_file_returns_default(self):
        self.config_path.write_bytes(b"")
        self.assertEqual(get_provider(), "claude")

    def test_malformed_toml_raises(self):
        self.config_path.write_text("provider = \n")
        with self.assertRaises(AskOogwayError) as ctx:
            get_provider()
        msg = str(ctx.exception)
        self.assertIn("invalid config.toml", msg)
        self.assertIn(str(self.config_path), msg)
        self.assertIsInstance(ctx.exception.__cause__, tomllib.TOMLDecodeError)

    def test_detects_lone_binary(self):
        self._write_bin("chatgpt")
        self.assertEqual(get_provider(), "chatgpt")

    def test_detection_prefers_claude(self):
        self._write_bin("chatgpt")
        self._write_bin("claude")
        self.assertEqual(get_provider(), "claude")

    def test_explicit_config_wins_over_detection(self):
        self._write_bin("claude")
        self.config_path.write_text('provider = "chatgpt"\n')
        self.assertEqual(get_provider(), "chatgpt")

    def test_keyless_config_detects(self):
        self._write_bin("chatgpt")
        self.config_path.write_text('foo = "bar"\n')
        self.assertEqual(get_provider(), "chatgpt")

    def test_nothing_detected_falls_back_to_default(self):
        self.assertEqual(get_provider(), "claude")
        self.assertEqual(get_provider(), DEFAULT_PROVIDER)


if __name__ == "__main__":
    unittest.main()
