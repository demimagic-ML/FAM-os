"""Bounded deterministic text extraction and summarization helpers."""

from __future__ import annotations

import html
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path


def pdf_text(path: Path, *, maximum_bytes: int = 4_194_304) -> str:
    result = subprocess.run(
        ("/usr/bin/pdftotext", "-f", "1", "-l", "50", "-layout", str(path), "-"),
        check=False, capture_output=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed for {path.name}")
    if len(result.stdout) > maximum_bytes:
        raise ValueError(f"extracted PDF text exceeds limit: {path.name}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def extractive_summary(text: str, *, sentences: int = 8) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return "No extractable text was found."
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", normalized.casefold())
    stop = {"the", "and", "that", "this", "with", "from", "for", "are", "was", "were", "have", "has", "not", "but", "you", "your"}
    frequencies: dict[str, int] = {}
    for word in words:
        if word not in stop:
            frequencies[word] = frequencies.get(word, 0) + 1
    ranked = []
    for index, sentence in enumerate(parts):
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", sentence.casefold())
        score = sum(frequencies.get(token, 0) for token in set(tokens)) / max(len(tokens), 1)
        if 30 <= len(sentence) <= 600:
            ranked.append((score, index, sentence.strip()))
    chosen = sorted(sorted(ranked, reverse=True)[:sentences], key=lambda item: item[1])
    return " ".join(item[2] for item in chosen) or normalized[:2000]


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._hidden:
            self._hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden and data.strip():
            self.parts.append(html.unescape(data.strip()))

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()
