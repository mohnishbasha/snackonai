"""
Integration tests for mr-pixel-smith — require a live Ollama instance with
the x/z-image-turbo model pulled.

Run with:
    venv/bin/python -m unittest tests/test_integration.py -v
"""

import subprocess
import sys
import unittest
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mr_pixel_smith.cli import (
    _generate_via_api,
    _generate_via_cli,
    add_watermark,
    generate_image,
    make_output_filename,
    MODEL,
    OLLAMA_API,
    WATERMARK_TEXT,
)

try:
    from PIL import Image
except ImportError:
    Image = None

DIMENSION_CASES = [
    (1200, 628),
    (1584, 396),
    (100, 100),
]

PROMPT = "a simple red circle on white background"


# ── Skip guards ───────────────────────────────────────────────────────────────

def _ollama_running() -> bool:
    try:
        urllib.request.urlopen(f"{OLLAMA_API}/api/tags", timeout=3)
        return True
    except Exception:
        return False


def _model_available() -> bool:
    try:
        resp = urllib.request.urlopen(f"{OLLAMA_API}/api/tags", timeout=3)
        import json
        data = json.loads(resp.read())
        return any(MODEL in m.get("name", "") for m in data.get("models", []))
    except Exception:
        return False


SKIP_REASON = None
if not _ollama_running():
    SKIP_REASON = "Ollama is not running (start with: ollama serve)"
elif not _model_available():
    SKIP_REASON = f"Model '{MODEL}' not pulled (run: ollama pull {MODEL})"

requires_ollama = unittest.skipIf(SKIP_REASON, SKIP_REASON or "")


def _is_valid_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def run_parallel(fn, cases):
    results = [None] * len(cases)
    with ThreadPoolExecutor(max_workers=len(cases)) as executor:
        futures = {executor.submit(fn, *case): i for i, case in enumerate(cases)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results


# ── API integration tests ─────────────────────────────────────────────────────

@requires_ollama
class TestGenerateViaApiIntegration(unittest.TestCase):

    def test_returns_valid_png_default_dims(self):
        result = _generate_via_api(PROMPT, 1200, 628)
        self.assertIsNotNone(result, "API returned None")
        self.assertTrue(_is_valid_png(result), "Response is not a valid PNG")

    def test_returns_valid_png_custom_dims(self):
        result = _generate_via_api(PROMPT, 1584, 396)
        self.assertIsNotNone(result, "API returned None")
        self.assertTrue(_is_valid_png(result), "Response is not a valid PNG")

    def test_returns_valid_png_small_dims(self):
        result = _generate_via_api(PROMPT, 100, 100)
        self.assertIsNotNone(result, "API returned None")
        self.assertTrue(_is_valid_png(result), "Response is not a valid PNG")

    def test_all_dims_in_parallel(self):
        results = run_parallel(lambda w, h: _generate_via_api(PROMPT, w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertIsNotNone(result, f"API returned None for {w}x{h}")
                self.assertTrue(_is_valid_png(result), f"Not a valid PNG for {w}x{h}")

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_image_is_openable_by_pillow(self):
        result = _generate_via_api(PROMPT, 100, 100)
        self.assertIsNotNone(result)
        img = Image.open(BytesIO(result))
        self.assertIn(img.format, ("PNG", None))


# ── CLI integration tests ─────────────────────────────────────────────────────

@requires_ollama
class TestGenerateViaCliIntegration(unittest.TestCase):

    def test_returns_bytes_or_none(self):
        """CLI may return None on newer ollama versions — just ensure no crash."""
        result = _generate_via_cli(PROMPT, 100, 100)
        if result is not None:
            self.assertTrue(_is_valid_png(result), "CLI result is not a valid PNG")

    def test_all_dims_in_parallel(self):
        results = run_parallel(lambda w, h: _generate_via_cli(PROMPT, w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                if result is not None:
                    self.assertTrue(_is_valid_png(result), f"CLI result not a valid PNG for {w}x{h}")


# ── generate_image (full flow) integration tests ──────────────────────────────

@requires_ollama
class TestGenerateImageIntegration(unittest.TestCase):

    def test_returns_valid_png_default_dims(self):
        result = generate_image(PROMPT, DEFAULT_WIDTH := 1200, DEFAULT_HEIGHT := 628)
        self.assertTrue(_is_valid_png(result))

    def test_returns_valid_png_custom_dims(self):
        result = generate_image(PROMPT, 1584, 396)
        self.assertTrue(_is_valid_png(result))

    def test_returns_valid_png_small_dims(self):
        result = generate_image(PROMPT, 100, 100)
        self.assertTrue(_is_valid_png(result))

    def test_all_dims_in_parallel(self):
        results = run_parallel(lambda w, h: generate_image(PROMPT, w, h), DIMENSION_CASES)
        for (w, h), result in zip(DIMENSION_CASES, results):
            with self.subTest(width=w, height=h):
                self.assertTrue(_is_valid_png(result), f"Not a valid PNG for {w}x{h}")


# ── Watermark integration tests ───────────────────────────────────────────────

@requires_ollama
class TestWatermarkIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.image_bytes = _generate_via_api(PROMPT, 100, 100)

    def test_watermark_returns_valid_png(self):
        self.assertIsNotNone(self.image_bytes)
        result = add_watermark(self.image_bytes, WATERMARK_TEXT)
        self.assertTrue(_is_valid_png(result))

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_watermarked_image_is_openable(self):
        self.assertIsNotNone(self.image_bytes)
        result = add_watermark(self.image_bytes, WATERMARK_TEXT)
        img = Image.open(BytesIO(result))
        self.assertEqual(img.mode, "RGB")

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_watermark_applied_to_all_dims_in_parallel(self):
        raw_images = run_parallel(lambda w, h: _generate_via_api(PROMPT, w, h), DIMENSION_CASES)

        def watermark(w_h_img):
            w, h, img = w_h_img
            return w, h, add_watermark(img, WATERMARK_TEXT)

        with ThreadPoolExecutor(max_workers=len(DIMENSION_CASES)) as executor:
            futures = [
                executor.submit(watermark, (w, h, img))
                for (w, h), img in zip(DIMENSION_CASES, raw_images)
                if img is not None
            ]
            for future in as_completed(futures):
                w, h, result = future.result()
                with self.subTest(width=w, height=h):
                    self.assertTrue(_is_valid_png(result))
                    img = Image.open(BytesIO(result))
                    self.assertEqual(img.mode, "RGB")


# ── End-to-end: generate + watermark + save ───────────────────────────────────

@requires_ollama
class TestEndToEndIntegration(unittest.TestCase):

    def _run(self, width, height):
        image_bytes = generate_image(PROMPT, width, height)
        watermarked = add_watermark(image_bytes, WATERMARK_TEXT)
        output_path = Path("/tmp") / make_output_filename(PROMPT, width, height)
        output_path.write_bytes(watermarked)
        return output_path

    def test_full_pipeline_default_dims(self):
        path = self._run(1200, 628)
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 0)
        path.unlink()

    def test_full_pipeline_custom_dims(self):
        path = self._run(1584, 396)
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 0)
        path.unlink()

    def test_full_pipeline_all_dims_in_parallel(self):
        paths = run_parallel(self._run, DIMENSION_CASES)
        for (w, h), path in zip(DIMENSION_CASES, paths):
            with self.subTest(width=w, height=h):
                self.assertTrue(path.exists(), f"Output file missing for {w}x{h}")
                self.assertGreater(path.stat().st_size, 0)
                path.unlink()


if __name__ == "__main__":
    unittest.main()
