from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_markdown_uses_github_math_delimiters() -> None:
    markdown_files = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    forbidden = {
        r"\(": "use $...$ for inline mathematics",
        r"\[": "use $$...$$ for display mathematics",
        r"\operatorname": r"use a GitHub-supported macro such as \mathrm",
    }

    violations: list[str] = []
    for path in markdown_files:
        content = path.read_text(encoding="utf-8")
        for token, guidance in forbidden.items():
            if token in content:
                violations.append(f"{path.relative_to(ROOT)}: {token!r}; {guidance}")

    assert not violations, "\n".join(violations)
