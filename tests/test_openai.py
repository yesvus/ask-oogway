"""Tests for the OpenAI-compatible endpoint provider."""

import json
import os
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from ask_oogway.errors import AskOogwayError
from ask_oogway.providers import openai


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.server.seen.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "user_agent": self.headers.get("User-Agent"),
                "json": json.loads(body or b"{}"),
            }
        )
        status, payload = self.server.queue.pop(0)
        if isinstance(payload, (bytes, bytearray)):
            data = bytes(payload)
        else:
            data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class OpenAITestCase(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.server.seen = []
        self.server.queue = []
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.addCleanup(self._stop_server)

        self._env = mock.patch.dict(
            os.environ,
            {
                "ASK_OOGWAY_BASE_URL": (
                    f"http://127.0.0.1:{self.server.server_port}/v1"
                ),
                "ASK_OOGWAY_MODEL": "test-model",
                "ASK_OOGWAY_API_KEY": "test-key",
            },
        )
        self._env.start()
        self.addCleanup(self._env.stop)

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _enqueue(self, status, payload):
        self.server.queue.append((status, payload))

    def test_success_posts_openai_shape(self):
        self._enqueue(
            200, {"choices": [{"message": {"content": "  hello world  "}}]}
        )
        self.assertEqual(openai.ask("hi"), "hello world")
        request = self.server.seen[0]
        self.assertEqual(request["path"], "/v1/chat/completions")
        self.assertEqual(request["authorization"], "Bearer test-key")
        self.assertEqual(request["user_agent"], "ask-oogway")
        self.assertEqual(request["json"]["model"], "test-model")
        roles = [m["role"] for m in request["json"]["messages"]]
        self.assertEqual(roles, ["system", "user"])
        self.assertEqual(request["json"]["messages"][1]["content"], "hi")
        self.assertTrue(request["json"]["messages"][0]["content"])

    def test_content_parts_list(self):
        self._enqueue(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "par"},
                                {"type": "text", "text": "ts"},
                            ]
                        }
                    }
                ]
            },
        )
        self.assertEqual(openai.ask("hi"), "parts")

    def test_missing_key(self):
        with mock.patch.dict(
            os.environ, {"ASK_OOGWAY_API_KEY": "", "OPENAI_API_KEY": ""}
        ):
            with self.assertRaises(AskOogwayError) as cm:
                openai.ask("hi")
        self.assertIn("no API key", str(cm.exception))

    def test_negative_timeout(self):
        with self.assertRaises(AskOogwayError) as cm:
            openai.ask("hi", timeout=-1)
        self.assertIn("--timeout must be >= 0", str(cm.exception))

    def _classified(self, status, payload, mode=None):
        self._enqueue(status, payload)
        with self.assertRaises(AskOogwayError) as cm:
            openai.ask("hi", timeout=mode)
        return str(cm.exception)

    def test_auth_failure_hint(self):
        msg = self._classified(401, {"error": {"message": "Unauthorized"}})
        self.assertIn("auth failed", msg)
        self.assertIn("401", msg)

    def test_rate_limit_hint(self):
        msg = self._classified(
            429, {"error": {"message": "rate limit exceeded"}}
        )
        self.assertIn("rate-limited", msg)

    def test_out_of_funds_hint(self):
        msg = self._classified(
            402, {"error": {"message": "Insufficient account funds"}}
        )
        self.assertIn("out of funds", msg)

    def test_rejected_hint(self):
        msg = self._classified(
            403,
            {
                "error": {
                    "type": "permission_error",
                    "message": "not allowed for this organization",
                }
            },
        )
        self.assertIn("rejected", msg)

    def test_model_unavailable_hint(self):
        msg = self._classified(
            400, {"error": {"message": "model 'x' not found"}}
        )
        self.assertIn("model unavailable", msg)

    def test_unmatched_http_error_stays_generic(self):
        msg = self._classified(500, {"error": {"message": "boom"}})
        self.assertIn("HTTP 500", msg)
        self.assertIn("boom", msg)

    def test_error_payload_with_200(self):
        msg = self._classified(200, {"error": {"message": "bad request"}})
        self.assertIn("openai error: bad request", msg)

    def test_invalid_json(self):
        self._enqueue(200, b"not json")
        with self.assertRaises(AskOogwayError) as cm:
            openai.ask("hi")
        self.assertIn("invalid JSON", str(cm.exception))

    def test_no_choices(self):
        self._enqueue(200, {"choices": []})
        with self.assertRaises(AskOogwayError) as cm:
            openai.ask("hi")
        self.assertIn("no choices", str(cm.exception))

    def test_non_dict_json_array(self):
        self._enqueue(200, [])
        with self.assertRaises(AskOogwayError) as cm:
            openai.ask("hi")
        self.assertIn("unexpected JSON", str(cm.exception))

    def test_non_dict_json_string(self):
        self._enqueue(200, "x")
        with self.assertRaises(AskOogwayError) as cm:
            openai.ask("hi")
        self.assertIn("unexpected JSON", str(cm.exception))

    def test_choice_not_object(self):
        self._enqueue(200, {"choices": [None]})
        with self.assertRaises(AskOogwayError) as cm:
            openai.ask("hi")
        self.assertIn("no choices", str(cm.exception))

    def test_message_not_object(self):
        self._enqueue(200, {"choices": [{"message": "x"}]})
        with self.assertRaises(AskOogwayError) as cm:
            openai.ask("hi")
        self.assertIn("empty output", str(cm.exception))

    def test_empty_output(self):
        self._enqueue(200, {"choices": [{"message": {"content": "  "}}]})
        with self.assertRaises(AskOogwayError) as cm:
            openai.ask("hi")
        self.assertIn("empty output", str(cm.exception))

    def test_network_error(self):
        with mock.patch.object(
            openai.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError("boom"),
        ):
            with self.assertRaises(AskOogwayError) as cm:
                openai.ask("hi")
        self.assertIn("network error", str(cm.exception))

    def test_timeout_override(self):
        with mock.patch.object(
            openai.urllib.request, "urlopen", side_effect=TimeoutError()
        ):
            with self.assertRaises(AskOogwayError) as cm:
                openai.ask("hi", timeout=5)
        self.assertIn("timed out after 5s", str(cm.exception))

    def test_defaults(self):
        with mock.patch.dict(
            os.environ,
            {"ASK_OOGWAY_BASE_URL": "", "ASK_OOGWAY_MODEL": ""},
        ):
            self.assertEqual(
                openai._base_url(), "https://api.openai.com/v1"
            )
            self.assertEqual(
                openai._model(), "claude-opus-4-6-thinking"
            )

    def test_base_url_trailing_slash_stripped(self):
        with mock.patch.dict(
            os.environ, {"ASK_OOGWAY_BASE_URL": "http://x/v1/"}
        ):
            self.assertEqual(openai._base_url(), "http://x/v1")


if __name__ == "__main__":
    unittest.main()
