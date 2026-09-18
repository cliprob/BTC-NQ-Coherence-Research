"""Compile and verify the LaTeX quantitative-research manuscript."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from build_figures import ROOT, build_all
from pypdf import PdfReader

REPORT_DIR = ROOT / "report"
SOURCE = REPORT_DIR / "manuscript.tex"
BUILD_DIR = REPORT_DIR / "build"
OUTPUT = ROOT / "output" / "pdf" / "btc_nq_coherence_research.pdf"
MANIFEST = REPORT_DIR / "report_manifest.json"
FIGURES = REPORT_DIR / "figures"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_pdflatex() -> str:
    configured = os.environ.get("PDFLATEX")
    if configured:
        return configured
    discovered = shutil.which("pdflatex")
    if discovered:
        return discovered
    miktex = (
        Path.home()
        / "AppData"
        / "Local"
        / "Programs"
        / "MiKTeX"
        / "miktex"
        / "bin"
        / "x64"
        / "pdflatex.exe"
    )
    if miktex.is_file():
        return str(miktex)
    raise FileNotFoundError(
        "pdflatex was not found. Install MiKTeX/TeX Live or set PDFLATEX."
    )


def _compile_latex() -> None:
    pdflatex = _find_pdflatex()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = "1789596000"
    environment["FORCE_SOURCE_DATE"] = "1"
    command = [
        pdflatex,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        f"-output-directory={BUILD_DIR}",
        str(SOURCE),
    ]
    for _ in range(2):
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        if completed.returncode != 0:
            tail = "\n".join(completed.stdout.splitlines()[-60:])
            raise RuntimeError(f"LaTeX compilation failed:\n{tail}")
    compiled = BUILD_DIR / "manuscript.pdf"
    if not compiled.is_file():
        raise FileNotFoundError("LaTeX completed without producing manuscript.pdf.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(compiled, OUTPUT)


def _write_manifest(figure_manifest: dict[str, Any]) -> dict[str, Any]:
    reader = PdfReader(str(OUTPUT))
    manifest = {
        "schema_version": 2,
        "report_version": "1.2.0",
        "status": "completed_development_manuscript",
        "source_policy": "committed_frozen_aggregates_only",
        "typesetting": "LaTeX research report",
        "page_count": len(reader.pages),
        "pdf": {"file_name": OUTPUT.name, "sha256": _hash(OUTPUT)},
        "latex_source": {"file_name": SOURCE.name, "sha256": _hash(SOURCE)},
        "figure_manifest_sha256": _hash(REPORT_DIR / "figure_manifest.json"),
        "figures": figure_manifest["figures"],
        "protocol_sha256": _hash(ROOT / "configs" / "research_protocol.yaml"),
        "builder_sha256": _hash(Path(__file__)),
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def build_report() -> dict[str, Any]:
    """Regenerate figures, compile the manuscript, and bind artifact hashes."""
    figure_manifest = build_all()
    _compile_latex()
    manifest = _write_manifest(figure_manifest)
    verify_report()
    return manifest


def verify_report() -> None:
    """Verify the committed manuscript, PDF, figures, and conclusions."""
    manifest = _load(MANIFEST)
    if manifest["schema_version"] != 2:
        raise ValueError("Expected the LaTeX report manifest schema v2.")
    if manifest["pdf"]["sha256"] != _hash(OUTPUT):
        raise ValueError("Committed report PDF does not match report_manifest.json.")
    if manifest["latex_source"]["sha256"] != _hash(SOURCE):
        raise ValueError("LaTeX source changed after the report was generated.")
    if manifest["protocol_sha256"] != _hash(ROOT / "configs" / "research_protocol.yaml"):
        raise ValueError("Protocol changed after the report was generated.")
    if manifest["builder_sha256"] != _hash(Path(__file__)):
        raise ValueError("Report builder changed after the report was generated.")
    if manifest["figure_manifest_sha256"] != _hash(
        REPORT_DIR / "figure_manifest.json"
    ):
        raise ValueError("Figure manifest changed after the report was generated.")
    for name, expected in manifest["figures"].items():
        if _hash(FIGURES / name) != expected:
            raise ValueError(f"Figure hash mismatch: {name}")

    reader = PdfReader(str(OUTPUT))
    if len(reader.pages) != manifest["page_count"]:
        raise ValueError("PDF page count does not match the report manifest.")
    if not 8 <= len(reader.pages) <= 14:
        raise ValueError("Journal manuscript should contain between 8 and 14 pages.")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    required = [
        "Magnitude-conditioned state persistence",
        "not a preregistration",
        "Incremental return value",
        "Robustness and negative control",
        "conditional state dependence without demonstrated alpha",
    ]
    normalized = text.casefold()
    missing = [phrase for phrase in required if phrase.casefold() not in normalized]
    if missing:
        raise ValueError(f"Report text is missing required conclusions: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Verify committed artifacts without TeX."
    )
    args = parser.parse_args()
    if args.check:
        verify_report()
        print("Verified LaTeX manuscript, PDF, and frozen-artifact hashes.")
    else:
        manifest = build_report()
        print(
            f"Built {manifest['page_count']}-page LaTeX manuscript: "
            f"{OUTPUT.relative_to(ROOT)}"
        )


if __name__ == "__main__":
    main()
