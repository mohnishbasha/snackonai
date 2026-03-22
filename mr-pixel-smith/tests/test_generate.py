"""Tests for _generate_via_cli, _generate_via_api, and make_output_filename."""

import base64
import json
import re
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mr_pixel_smith.cli import (
    _generate_via_cli,
    _generate_via_api,
    make_output_filename,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
)

# Minimal 1x1 PNG
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
PNG_B64 = base64.b64encode(PNG_BYTES).decode()

DIMENSION_CASES = [
    (DEFAULT_WIDTH, DEFAULT_HEIGHT),
    (1584, 396),
    (100, 100),
]


def run_parallel(fn, cases):
    """Run fn(case) for each case in parallel; return list of results in order."""
    results = [None] * len(cases)
    with ThreadPoolExecutor(max_workers=len(cases)) as executor:
        futures = {executor.submit(fn, *case): i for i, case in enumerate(cases)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results


# ── CLI tests ─────────────────────────────────────────────────────────────────

class TestGenerateViaCli(unittest.TestCase):

    def _mock_run(self, stdout="", stderr="", returncode=0):
        result = MagicMock()
        result.stdout = stdout
        result.stderr = stderr
        result.returncode = returncode
        return result

    @patch("mr_pixel_smith.cli.subprocess.run")
    def test_returns_bytes_when_image_saved_to_in_stdout_default_dims(self, mock_run):
        tmp = Path("/tmp/test_cli_stdout_default.png")
        tmp.write_bytes(PNG_BYTES)
        mock_run.return_value = self._mock_run(stdout=f"Image saved to: {tmp}\n")
        result = _generate_via_cli("test", DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.assertEqual(result, PNG_BYTES)
        self.assertFalse(tmp.exists())

    @patch("mr_pixel_smith.cli.subprocess.run")
    def test_returns_bytes_when_image_saved_to_in_stdout_custom_dims(self, mock_run):
        tmp = Path("/tmp/test_cli_stdout_custom.png")
        tmp.write_bytes(PNG_BYTES)
        mock_run.return_value = self._mock_run(stdout=f"Image saved to: {tmp}\n")
        result = _generate_via_cli("test", 1584, 396)
        self.assertEqual(result, PNG_BYTES)
        self.assertFalse(tmp.exists())
        call_args = mock_run.call_args[0][0]
        self.assertIn("1584", call_args)
        self.assertIn("396", call_args)

    @patch("mr_pixel_smith.cli.subprocess.run")
    def test_returns_bytes_when_image_saved_to_in_stderr_default_dims(self, mock_run):
        tmp = Path("/tmp/test_cli_stderr_default.png")
        tmp.write_bytes(PNG_BYTES)
        mock_run.return_value = self._mock_run(stderr=f"Image saved to: {tmp}\n")
        result = _generate_via_cli("test", DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.assertEqual(result, PNG_BYTES)

    @patch("mr_pixel_smith.cli.subprocess.run")
    def test_returns_bytes_when_image_saved_to_in_stderr_custom_dims(self, mock_run):
        tmp = Path("/tmp/test_cli_stderr_custom.png")
        tmp.write_bytes(PNG_BYTES)
        mock_run.return_value = self._mock_run(stderr=f"Image saved to: {tmp}\n")
        result = _generate_via_cli("test", 1584, 396)
        self.assertEqual(result, PNG_BYTES)

    @patch("mr_pixel_smith.cli.subprocess.run")
    def test_returns_none_when_no_image_saved_to_line_parallel(self, mock_run):
        mock_run.return_value = self._mock_run(stdout="some other output")
        results = run_parallel(lambda w, h: _generate_via_cli("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertIsNone(result)

    @patch("mr_pixel_smith.cli.subprocess.run")
    def test_returns_none_on_nonzero_returncode_parallel(self, mock_run):
        mock_run.return_value = self._mock_run(returncode=1, stderr="error")
        results = run_parallel(lambda w, h: _generate_via_cli("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertIsNone(result)

    @patch("mr_pixel_smith.cli.subprocess.run")
    def test_returns_none_on_empty_output_parallel(self, mock_run):
        mock_run.return_value = self._mock_run()
        results = run_parallel(lambda w, h: _generate_via_cli("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertIsNone(result)

    @patch("mr_pixel_smith.cli.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ollama", timeout=300))
    def test_returns_none_on_timeout_parallel(self, mock_run):
        results = run_parallel(lambda w, h: _generate_via_cli("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertIsNone(result)

    @patch("mr_pixel_smith.cli.subprocess.run", side_effect=OSError("not found"))
    def test_returns_none_on_os_error_parallel(self, mock_run):
        results = run_parallel(lambda w, h: _generate_via_cli("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertIsNone(result)


# ── API tests ─────────────────────────────────────────────────────────────────

class TestGenerateViaApi(unittest.TestCase):

    def _mock_response(self, body: dict):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(body).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("mr_pixel_smith.cli.urllib.request.urlopen")
    def test_returns_bytes_from_image_key_parallel(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response({"image": PNG_B64})
        results = run_parallel(lambda w, h: _generate_via_api("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertEqual(result, PNG_BYTES)

    @patch("mr_pixel_smith.cli.urllib.request.urlopen")
    def test_returns_bytes_from_response_key_parallel(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response({"response": PNG_B64})
        results = run_parallel(lambda w, h: _generate_via_api("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertEqual(result, PNG_BYTES)

    @patch("mr_pixel_smith.cli.urllib.request.urlopen")
    def test_returns_bytes_from_images_list_parallel(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response({"images": [PNG_B64]})
        results = run_parallel(lambda w, h: _generate_via_api("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertEqual(result, PNG_BYTES)

    @patch("mr_pixel_smith.cli.urllib.request.urlopen")
    def test_dimensions_passed_in_payload_parallel(self, mock_urlopen):
        captured = {}

        def side_effect(req, timeout=None):
            payload = json.loads(req.data.decode())
            key = (payload["options"]["width"], payload["options"]["height"])
            captured[key] = payload
            return self._mock_response({"image": PNG_B64})

        mock_urlopen.side_effect = side_effect
        run_parallel(lambda w, h: _generate_via_api("test", w, h), DIMENSION_CASES)
        for w, h in DIMENSION_CASES:
            with self.subTest(width=w, height=h):
                self.assertIn((w, h), captured)
                self.assertEqual(captured[(w, h)]["options"]["width"], w)
                self.assertEqual(captured[(w, h)]["options"]["height"], h)

    @patch("mr_pixel_smith.cli.urllib.request.urlopen")
    def test_returns_none_when_no_image_keys_parallel(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response({"model": "x/z-image-turbo", "done": True})
        results = run_parallel(lambda w, h: _generate_via_api("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertIsNone(result)

    @patch("mr_pixel_smith.cli.urllib.request.urlopen")
    def test_returns_none_on_invalid_json_parallel(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        results = run_parallel(lambda w, h: _generate_via_api("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertIsNone(result)

    @patch("mr_pixel_smith.cli.urllib.request.urlopen")
    def test_returns_none_on_url_error_parallel(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        results = run_parallel(lambda w, h: _generate_via_api("test", w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertIsNone(result)


# ── Filename tests ─────────────────────────────────────────────────────────────

class TestMakeOutputFilename(unittest.TestCase):

    def test_contains_slug_width_height(self):
        name = make_output_filename("A beautiful sunset", 1584, 396)
        self.assertIn("a-beautiful-sunset", name)
        self.assertIn("1584x396", name)
        self.assertTrue(name.endswith(".png"))

    def test_filename_for_all_dims_parallel(self):
        results = run_parallel(
            lambda w, h: make_output_filename("test", w, h),
            DIMENSION_CASES,
        )
        for (w, h), name in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertIn(f"{w}x{h}", name)
                self.assertIn("test", name)
                self.assertTrue(name.endswith(".png"))

    def test_special_chars_stripped(self):
        name = make_output_filename("hello! @world#", 100, 100)
        self.assertFalse(re.search(r"[^a-z0-9\-.]", name.replace(".png", "")))

    def test_slug_max_length(self):
        long_prompt = "word " * 20
        name = make_output_filename(long_prompt, 100, 100)
        slug = name.split("-100x100-")[0]
        self.assertLessEqual(len(slug), 40)


if __name__ == "__main__":
    unittest.main()
