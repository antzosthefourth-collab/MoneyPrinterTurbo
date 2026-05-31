"""Unit tests for the fitness_shorts engine's pure helpers.

These cover transcript note-stripping, SRT end-time parsing, and cut snapping —
the logic that does not depend on moviepy/edge-tts, so it runs in CI without a render.
"""

import os
import sys
import tempfile
import unittest

ENGINE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "projects", "fitness_shorts",
)
sys.path.insert(0, ENGINE_DIR)
import engine  # noqa: E402


class TestReadTranscript(unittest.TestCase):
    def _cfg(self, text):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "transcript.md"), "w", encoding="utf-8") as f:
            f.write(text)
        return engine.ProjectConfig(project_dir=d, task_id="t", subject="s")

    def test_strips_headers_and_comments(self):
        cfg = self._cfg(
            "# Title\n"
            "<!--\nnote line\nmore notes\n-->\n"
            "Spoken one.\n\nSpoken two.\n"
            "<!-- inline note -->\n"
        )
        text = engine.read_transcript(cfg)
        self.assertIn("Spoken one.", text)
        self.assertIn("Spoken two.", text)
        self.assertNotIn("note", text)
        self.assertNotIn("Title", text)

    def test_empty_after_strip_raises(self):
        cfg = self._cfg("# only a header\n<!-- only notes -->\n")
        with self.assertRaises(SystemExit):
            engine.read_transcript(cfg)


class TestCaptionTimes(unittest.TestCase):
    def _srt(self, body):
        fd, path = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        return path

    def test_parse_end_times_sorted(self):
        path = self._srt(
            "1\n00:00:00,000 --> 00:00:04,000\nA\n\n"
            "2\n00:00:04,000 --> 00:00:13,500\nB\n\n"
        )
        ends = engine.caption_end_times(path)
        self.assertEqual(ends, [4.0, 13.5])

    def test_missing_file_returns_empty(self):
        self.assertEqual(engine.caption_end_times("/no/such.srt"), [])


class TestSnap(unittest.TestCase):
    def test_snaps_to_largest_below_target(self):
        ends = [4.0, 13.0, 28.0, 45.0, 58.0]
        self.assertEqual(engine.snap_to_caption(45.0, ends), 45.0)
        self.assertEqual(engine.snap_to_caption(15.0, ends), 13.0)

    def test_nearest_when_none_below(self):
        self.assertEqual(engine.snap_to_caption(2.0, [10.0, 20.0]), 10.0)

    def test_empty_returns_target(self):
        self.assertEqual(engine.snap_to_caption(45.0, []), 45.0)


if __name__ == "__main__":
    unittest.main()
