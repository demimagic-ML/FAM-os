"""Five concrete everyday workflows backed by real local tools."""

from __future__ import annotations

import csv
import io
import math
import urllib.request
from pathlib import Path

from fam_os.product.useful_tasks.artifacts import UsefulArtifactWriter, selected_paths
from fam_os.product.useful_tasks.text import VisibleTextParser, extractive_summary, pdf_text


def summarize_pdfs(root: Path, document: dict, writer: UsefulArtifactWriter):
    paths = selected_paths(root, document.get("input_paths"), (".pdf",))
    sections = []
    for path in paths:
        text = pdf_text(path)
        sections.append(f"## {path.name}\n\n{extractive_summary(text)}")
    content = "# PDF summary\n\n" + "\n\n".join(sections) + "\n"
    artifact = writer.write_text("summary.md", content, kind="report", media_type="text/markdown")
    return f"Summarized {len(paths)} PDF file(s).", (artifact,), None


def analyze_csv(root: Path, document: dict, writer: UsefulArtifactWriter):
    path = selected_paths(root, document.get("input_paths"), (".csv",))[0]
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(io.StringIO(stream.read(4_194_304))))
    if not rows:
        raise ValueError("CSV contains no data rows")
    fields = tuple(rows[0])
    numeric: dict[str, list[float]] = {}
    for field in fields:
        values = []
        for row in rows:
            try:
                value = float(row.get(field, ""))
                if math.isfinite(value):
                    values.append(value)
            except (TypeError, ValueError):
                continue
        if values:
            numeric[field] = values
    report = [f"# CSV analysis: {path.name}", "", f"Rows: **{len(rows)}**", f"Columns: **{len(fields)}**", "", "## Numeric columns", ""]
    for field, values in numeric.items():
        report.append(
            f"- **{field}**: count {len(values)}, min {min(values):.3g}, "
            f"mean {sum(values) / len(values):.3g}, max {max(values):.3g}"
        )
    if not numeric:
        report.append("No numeric columns were detected.")
    report_artifact = writer.write_text(
        "analysis.md", "\n".join(report) + "\n", kind="report", media_type="text/markdown",
    )
    chart_artifact = writer.write_text(
        "chart.svg", _chart(numeric), kind="chart", media_type="image/svg+xml",
    )
    return f"Analyzed {len(rows)} rows and {len(fields)} columns.", (report_artifact, chart_artifact), None


def transcribe_audio(root: Path, document: dict, writer: UsefulArtifactWriter, recognizer):
    path = selected_paths(root, document.get("input_paths"), (".wav", ".mp3", ".m4a", ".ogg", ".flac"))[0]
    if recognizer is None:
        raise RuntimeError("speech recognition is unavailable; install the FAM_OS media extra")
    result = recognizer.transcribe(path)
    content = f"# Transcript: {path.name}\n\n{result.text}\n"
    artifact = writer.write_text("transcript.md", content, kind="transcript", media_type="text/markdown")
    return f"Transcribed {path.name} using {result.model_ref}.", (artifact,), None


def research_urls(root: Path, document: dict, writer: UsefulArtifactWriter):
    urls = document.get("urls")
    if not isinstance(urls, list) or not 1 <= len(urls) <= 10 or not all(isinstance(item, str) for item in urls):
        raise ValueError("research requires between one and ten URLs")
    sections = []
    for index, url in enumerate(urls, 1):
        if not url.startswith(("https://", "http://")):
            raise ValueError("research URLs must use HTTP or HTTPS")
        request = urllib.request.Request(url, headers={"User-Agent": "FAM_OS/0.1"})
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read(2_097_153)
            if len(payload) > 2_097_152:
                raise ValueError("research source exceeds the per-source limit")
        parser = VisibleTextParser()
        parser.feed(payload.decode("utf-8", errors="replace"))
        sections.append(f"## Source {index}\n\n{extractive_summary(parser.text, sentences=5)}\n\n[{url}]({url})")
    report = "# Research brief\n\n" + "\n\n".join(sections) + "\n"
    artifact = writer.write_text("research.md", report, kind="research", media_type="text/markdown")
    return f"Created a cited brief from {len(urls)} source(s).", (artifact,), None


def engineering_task(root: Path, document: dict, writer: UsefulArtifactWriter, delegate):
    if delegate is None:
        raise RuntimeError("natural engineering is unavailable")
    proposal = delegate(document["prompt"], str(root))
    note = (
        "# Engineering task\n\nThe task entered FAM_OS's governed engineering lifecycle.\n\n"
        f"Proposal: `{proposal.get('proposal_id', 'created')}`\n"
    )
    artifact = writer.write_text("engineering-task.md", note, kind="handoff", media_type="text/markdown")
    return "Prepared an engineering task for owner review.", (artifact,), proposal


def _chart(numeric: dict[str, list[float]]) -> str:
    items = list(numeric.items())[:8]
    bars = []
    maximum = max((sum(values) / len(values) for _, values in items), default=1.0) or 1.0
    for index, (name, values) in enumerate(items):
        mean = sum(values) / len(values)
        width = max(2, int(560 * max(mean, 0) / maximum))
        y = 42 + index * 42
        bars.append(f'<text x="10" y="{y + 16}" font-size="13">{name[:22]}</text><rect x="180" y="{y}" width="{width}" height="24" fill="#537a6a"/><text x="{190 + width}" y="{y + 17}" font-size="12">{mean:.3g}</text>')
    height = max(100, 70 + len(items) * 42)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{height}" viewBox="0 0 800 {height}"><rect width="100%" height="100%" fill="#f5f1e8"/><text x="10" y="24" font-size="17" font-weight="bold">Numeric column means</text>{"".join(bars)}</svg>\n'
