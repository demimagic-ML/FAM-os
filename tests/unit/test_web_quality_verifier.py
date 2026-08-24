"""Positive and deliberately failing deterministic HTML/CSS fixtures."""

import unittest

from tools.verifiers.web_quality import verify_css, verify_html


class WebQualityVerifierTests(unittest.TestCase):
    def test_html_positive_and_accessibility_failure(self):
        self.assertEqual((), verify_html(
            "<!doctype html><html><body><img alt='Logo' src='logo.png'></body></html>",
        ))
        self.assertIn("img requires nonempty alt text", verify_html(
            "<!doctype html><html><body><img src='logo.png'></body></html>",
        ))

    def test_css_positive_and_syntax_failure(self):
        self.assertEqual((), verify_css("body { color: black; margin: 0; }"))
        self.assertIn("CSS braces are unbalanced", verify_css("body { color: black;"))


if __name__ == "__main__":
    unittest.main()
