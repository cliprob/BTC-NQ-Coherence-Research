"""Build and verify the academic PDF from committed aggregate research artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from build_figures import ROOT, build_all
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

REPORTS = ROOT / "reports" / "development"
OUTPUT = ROOT / "output" / "pdf" / "btc_nq_coherence_research.pdf"
MANIFEST = ROOT / "report" / "report_manifest.json"
FIGURES = ROOT / "report" / "figures"

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2F5D8A")
TEAL = colors.HexColor("#3B7A78")
RED = colors.HexColor("#A64B4B")
GRAY = colors.HexColor("#667085")
LIGHT = colors.HexColor("#E8EDF1")
PALE_BLUE = colors.HexColor("#EEF4F8")
PALE_TEAL = colors.HexColor("#EDF6F4")
PALE_RED = colors.HexColor("#FAF0F0")
WHITE = colors.white


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class InvariantCanvas(canvas.Canvas):
    """Deterministic ReportLab canvas with stable metadata."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["invariant"] = 1
        super().__init__(*args, **kwargs)
        self.setTitle("BTC-NQ Cross-Market Coherence Research")
        self.setAuthor("Robert Mazurczak")
        self.setSubject("Completed development study, protocol v1.0.0")

def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11.5,
            leading=16,
            textColor=GRAY,
            spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "Heading1Academic",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
            textColor=NAVY,
            spaceBefore=0,
            spaceAfter=9,
        ),
        "h2": ParagraphStyle(
            "Heading2Academic",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=BLUE,
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "BodyAcademic",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=9.2,
            leading=12.2,
            textColor=colors.HexColor("#263442"),
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "SmallAcademic",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=7.8,
            leading=10.2,
            textColor=GRAY,
            spaceAfter=3,
        ),
        "caption": ParagraphStyle(
            "CaptionAcademic",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.4,
            leading=9.4,
            textColor=GRAY,
            spaceBefore=3,
            spaceAfter=7,
        ),
        "box": ParagraphStyle(
            "BoxAcademic",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.6,
            leading=11.4,
            textColor=NAVY,
        ),
        "formula": ParagraphStyle(
            "FormulaAcademic",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.7,
            leading=10.2,
            textColor=NAVY,
            leftIndent=5,
            spaceAfter=4,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.1,
            leading=8.6,
            textColor=WHITE,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.0,
            leading=8.7,
            textColor=colors.HexColor("#263442"),
        ),
        "reference": ParagraphStyle(
            "Reference",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=7.2,
            leading=9.2,
            leftIndent=12,
            firstLineIndent=-12,
            textColor=colors.HexColor("#354454"),
            spaceAfter=4,
        ),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def _section(title: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    return [
        _p(title, styles["h1"]),
        HRFlowable(width="100%", thickness=0.8, color=LIGHT, spaceAfter=8),
    ]


def _box(
    label: str,
    text: str,
    styles: dict[str, ParagraphStyle],
    *,
    background: colors.Color = PALE_BLUE,
    accent: colors.Color = BLUE,
) -> Table:
    body = _p(f"<b>{label}</b><br/>{text}", styles["box"])
    table = Table([[body]], colWidths=[17.4 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.5, accent),
                ("LINEBEFORE", (0, 0), (0, -1), 4, accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _table(
    rows: list[list[str]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
    *,
    alignments: list[str] | None = None,
) -> Table:
    data: list[list[Paragraph]] = []
    for row_index, row in enumerate(rows):
        style = styles["table_header"] if row_index == 0 else styles["table_cell"]
        data.append([_p(value, style) for value in row])
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5DE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#F6F8FA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if alignments:
        for column, alignment in enumerate(alignments):
            commands.append(("ALIGN", (column, 1), (column, -1), alignment))
    table.setStyle(TableStyle(commands))
    return table


def _timeline(styles: dict[str, ParagraphStyle]) -> Table:
    boxes = [
        ("LOOKBACK", "Past-only<br/>features"),
        ("BAR t", "Close observed<br/>at tau"),
        ("SIGNAL", "Forecast formed<br/>after close"),
        ("ENTRY", "Next tradable<br/>open"),
        ("OUTCOME", "Open at<br/>tau + 5 min"),
    ]
    row: list[Any] = []
    widths: list[float] = []
    for index, (label, text) in enumerate(boxes):
        row.append(_p(f"<b>{label}</b><br/>{text}", styles["table_cell"]))
        widths.append(2.75 * cm)
        if index < len(boxes) - 1:
            row.append(_p("&gt;", styles["box"]))
            widths.append(0.65 * cm)
    table = Table([row], colWidths=widths, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    for column in range(0, len(row), 2):
        commands.extend(
            [
                ("BACKGROUND", (column, 0), (column, 0), PALE_BLUE),
                ("BOX", (column, 0), (column, 0), 0.5, BLUE),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def _draw_page_decorations(canvas_obj: canvas.Canvas) -> None:
    canvas_obj.saveState()
    canvas_obj.resetTransforms()
    width, height = A4
    page_number = canvas_obj.getPageNumber()
    if page_number > 1:
        canvas_obj.setStrokeColor(LIGHT)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(1.65 * cm, height - 1.12 * cm, width - 1.65 * cm, height - 1.12 * cm)
        canvas_obj.setFont("Helvetica", 7.2)
        canvas_obj.setFillColor(GRAY)
        canvas_obj.drawString(1.65 * cm, height - 0.88 * cm, "BTC-NQ Cross-Market Coherence")
        canvas_obj.drawRightString(
            width - 1.65 * cm, height - 0.88 * cm, "Completed development study | v1.0.0"
        )
    canvas_obj.setStrokeColor(LIGHT)
    canvas_obj.line(1.65 * cm, 1.02 * cm, width - 1.65 * cm, 1.02 * cm)
    canvas_obj.setFont("Helvetica", 7.2)
    canvas_obj.setFillColor(GRAY)
    canvas_obj.drawString(1.65 * cm, 0.68 * cm, "Robert Mazurczak | 17 September 2026")
    canvas_obj.drawRightString(width - 1.65 * cm, 0.68 * cm, str(page_number))
    canvas_obj.restoreState()


def _decorate_pdf(content_path: Path, output_path: Path) -> None:
    """Merge decorations from an identity-coordinate overlay onto every page."""
    content_reader = PdfReader(str(content_path))
    overlay_path = output_path.with_suffix(".overlay.pdf")
    overlay_canvas = InvariantCanvas(
        str(overlay_path), pagesize=A4, pageCompression=1
    )
    for _ in content_reader.pages:
        _draw_page_decorations(overlay_canvas)
        overlay_canvas.showPage()
    overlay_canvas.save()

    overlay_reader = PdfReader(str(overlay_path))
    writer = PdfWriter()
    for content_page, overlay_page in zip(
        content_reader.pages, overlay_reader.pages, strict=True
    ):
        overlay_page.merge_page(content_page)
        writer.add_page(overlay_page)
    writer.add_metadata(
        {
            "/Title": "BTC-NQ Cross-Market Coherence Research",
            "/Author": "Robert Mazurczak",
            "/Subject": "Completed development study, protocol v1.0.0",
        }
    )
    with output_path.open("wb") as stream:
        writer.write(stream)
    overlay_path.unlink()


def _build_story(styles: dict[str, ParagraphStyle]) -> list[Any]:
    state = _load(REPORTS / "state_model_summary.json")
    returns = _load(REPORTS / "return_model_summary.json")
    descriptive = _load(REPORTS / "descriptive_summary.json")
    overnight = _load(REPORTS / "overnight_control_summary.json")
    eligibility = _load(ROOT / "data" / "registry" / "available_data_eligibility.json")

    state_5 = state["five_minute_primary"]
    return_5 = returns["five_minute_primary"]
    overnight_state = overnight["state_model"]["five_minute_primary"]
    overnight_return = overnight["return_model"]["five_minute_primary"]
    descriptive_5 = descriptive["primary_five_minute"]

    story: list[Any] = []

    # Page 1 - title and abstract
    story.extend(
        [
            Spacer(1, 0.55 * cm),
            _p("BTC-NQ Cross-Market Coherence", styles["title"]),
            _p(
                "A development study of magnitude-conditioned state persistence and "
                "incremental Nasdaq futures return value",
                styles["subtitle"],
            ),
            HRFlowable(width="100%", thickness=2.0, color=NAVY, spaceAfter=15),
            _p(
                "<b>Robert Mazurczak</b><br/>Python | scikit-learn | purged walk-forward "
                "validation | session-block bootstrap",
                styles["body"],
            ),
            Spacer(1, 0.25 * cm),
            _box(
                "Finding",
                "Joint move intensity and magnitude balance add a small, repeatable "
                "amount of information about next-bar BTC-NQ directional agreement. "
                "They do not improve the registered five-minute NQ return forecast over "
                "an NQ-only baseline. The state effect also appears overnight, so it is "
                "not specific to US cash hours.",
                styles,
                background=PALE_TEAL,
                accent=TEAL,
            ),
            Spacer(1, 0.34 * cm),
            _p("Abstract", styles["h1"]),
            _p(
                "This study tests whether synchronized, volatility-adjusted Bitcoin and "
                "Nasdaq futures candle bodies define persistent cross-market states, and "
                "whether relative body magnitude contributes information beyond recent "
                "directional coherence. One-minute BTCUSDT perpetual and stitched NQ "
                "front-month bars are synchronized in UTC and filtered with DST-aware "
                "session calendars. Five-minute bars are primary; one-minute results are "
                "mandatory robustness evidence. A nested logistic comparison evaluates "
                "state persistence, while matched Ridge models test incremental NQ return "
                "value. All preprocessing and regularization selection occur inside "
                "purged expanding folds.",
                styles["body"],
            ),
            _p(
                "Magnitude features reduce primary Brier loss by 0.000699 (95% "
                "session-block interval: -0.001120 to -0.000297). In contrast, the "
                "cross-market return model increases MSE by 0.1924 bps^2 versus NQ-only "
                "(95% interval: 0.0728 to 0.3222), and both Ridge models underperform a "
                "fold training-mean benchmark. A prespecified overnight control repeats "
                "the state result but not an economic return result. The evidence supports "
                "a narrow state-dependence finding, not alpha or deployment readiness.",
                styles["body"],
            ),
            Spacer(1, 0.15 * cm),
            _table(
                [
                    ["Primary comparison", "Estimate", "95% session-block interval", "Decision"],
                    ["State Brier: M1 - M0", "-0.000699", "[-0.001120, -0.000297]", "Small development signal"],
                    ["Return MSE: cross - NQ-only", "+0.1924 bps^2", "[+0.0728, +0.3222]", "No incremental value"],
                    ["Overnight state Brier: M1 - M0", "-0.000259", "[-0.000440, -0.000081]", "Not cash-specific"],
                ],
                [5.0 * cm, 3.1 * cm, 4.2 * cm, 4.3 * cm],
                styles,
            ),
            Spacer(1, 0.2 * cm),
            _p(
                "<b>Keywords:</b> cross-market dependence, Bitcoin, Nasdaq futures, "
                "calibration, walk-forward validation, data leakage, negative control",
                styles["small"],
            ),
            PageBreak(),
        ]
    )

    # Page 2 - question and governance
    story.extend(_section("1. Research question and inferential governance", styles))
    story.extend(
        [
            _p(
                "The motivating observation is contemporaneous: BTC and NQ candle bodies "
                "often share a direction but differ in volatility-adjusted size. The study "
                "does not assume that BTC leads NQ or that the weaker market must catch up. "
                "Continuation, reversal and no economically relevant effect remain competing "
                "outcomes.",
                styles["body"],
            ),
            _p("Prespecified questions", styles["h2"]),
            _table(
                [
                    ["Stage", "Estimand", "Comparison", "Role"],
                    ["Descriptive", "Signed future NQ return after current agreement", "5-minute primary; 15/30/60 secondary", "Context"],
                    ["State", "Next-bar agreement probability given current agreement", "M1 magnitude model minus M0 coherence model", "Primary state"],
                    ["Economic", "Executable next-five-minute signed NQ return", "NQ+BTC Ridge minus NQ-only Ridge", "Primary return"],
                    ["Control", "Same estimands during 18:00-09:30 ET", "Identical definitions and model grids", "Negative control"],
                ],
                [2.2 * cm, 5.5 * cm, 5.4 * cm, 3.5 * cm],
                styles,
            ),
            _p("Causal timing", styles["h2"]),
            _timeline(styles),
            _p(
                "The event bar close is observed before a signal exists. Economic outcomes "
                "start at the next tradable open and end at the open five minutes later. "
                "No known close is treated as an executable fill.",
                styles["caption"],
            ),
            _p("Multiplicity and closure", styles["h2"]),
            _p(
                "The five-minute state and return comparisons are primary for distinct "
                "questions. Their 95% complete-session bootstrap intervals are unadjusted. "
                "One-minute results, secondary horizons, weekday diagnostics, coefficients "
                "and overnight results cannot replace or rescue a primary result. Trial "
                "ledgers retain every nested model-selection attempt.",
                styles["body"],
            ),
            _box(
                "Governance",
                "Protocol v1.0.0 locks a completed development record after results. It is "
                "not a preregistration, no final holdout was opened, and no family-wise "
                "confirmatory error-control claim is made. New confirmation requires a "
                "new protocol and untouched data.",
                styles,
                background=PALE_RED,
                accent=RED,
            ),
            PageBreak(),
        ]
    )

    # Page 3 - data and features
    story.extend(_section("2. Data, sessions and feature construction", styles))
    story.extend(
        [
            _table(
                [
                    ["Input", "Coverage and role", "Provenance", "Key limitation"],
                    ["BTCUSDT USDT-M perpetual, Binance, 1-minute OHLCV", "2024-03-07 to 2026-05-12; synchronized BTC leg", "Verified public archive acquisition", "Post-ETP only; previously inspected"],
                    ["NQ stitched front-month, CME/IBKR, 1-minute OHLCV", "Common range through 2026-05-12; NQ price process", "Partial stitched-source provenance", "Historical roll rule incomplete; proprietary rows"],
                ],
                [4.1 * cm, 4.5 * cm, 3.7 * cm, 4.3 * cm],
                styles,
            ),
            Spacer(1, 0.15 * cm),
            _p(
                f"The deterministic eligibility pass retains "
                f"<b>{eligibility['primary']['eligible_sessions']}</b> complete cash sessions "
                f"and <b>{eligibility['overnight_negative_control']['eligible_sessions']}</b> "
                "complete overnight sessions before the 63-session scale warm-up. Entire "
                "incomplete or contract-transition sessions are excluded; missing prices "
                "are never forward-filled.",
                styles["body"],
            ),
            _p("Feature definitions", styles["h2"]),
            _p("body(i,t) = log(close(i,t) / open(i,t))", styles["formula"]),
            _p("agreement(t) = sign(body(BTC,t)) * sign(body(NQ,t))", styles["formula"]),
            _p("coherence(L,t) = mean agreement over L in {15, 30, 60} minutes", styles["formula"]),
            _p("m(i,t) = abs(body(i,t)) / [1.4826 * same-slot MAD over 63 prior sessions]", styles["formula"]),
            _p("joint intensity J(t) = sqrt(m(BTC,t) * m(NQ,t))", styles["formula"]),
            _p("magnitude balance B(t) = [m(BTC,t) - m(NQ,t)] / [m(BTC,t) + m(NQ,t)]", styles["formula"]),
            _p(
                "The historical scale is estimated separately by asset, resolution and "
                "DST-aware New York session slot. The current session is excluded. Missing "
                "history, zero scale, known gaps and roll contamination make an observation "
                "ineligible; no epsilon or future-data fallback is allowed.",
                styles["body"],
            ),
            _p("Parameter provenance", styles["h2"]),
            _table(
                [
                    ["Parameter", "Value", "Status and rationale"],
                    ["Primary bars", "5 minutes", "Computationally tractable primary representation; 1-minute mandatory robustness"],
                    ["Coherence clocks", "15/30/60 minutes", "Used jointly; no best-window selection by outcome"],
                    ["Historical scale", "63 sessions", "Causal same-slot robust scale; current session excluded"],
                    ["Economic horizon", "5 minutes", "Next-open to horizon-open; fixed across 1m and 5m representations"],
                    ["Purge", "1 full session", "Exceeds the five-minute target horizon and prevents adjacent-session leakage"],
                    ["Entry/exit threshold", "None", "Strategy stage not opened after negative return comparison"],
                ],
                [4.0 * cm, 2.8 * cm, 9.8 * cm],
                styles,
            ),
            PageBreak(),
        ]
    )

    # Page 4 - validation design
    story.extend(_section("3. Purged walk-forward design", styles))
    story.extend(
        [
            _p(
                "All scored predictions are out of fold. The cash-session design starts "
                "with 130 feature-ready training sessions, purges one complete session, and "
                "scores 12 consecutive 22-session validation blocks. Each outer fold uses "
                "three trailing expanding inner validation blocks, again separated by a "
                "complete-session purge. The overnight walk is mechanically adapted to the "
                "available sample: 135 initial sessions, one purge and 16 blocks of 22.",
                styles["body"],
            ),
            _p("Nested comparisons", styles["h2"]),
            _table(
                [
                    ["Model", "Predictors", "Fold-local selection", "Primary score"],
                    ["M0 logistic", "Coherence 15/30/60 + common direction", "Standardization; C in 0.01/0.1/1/10", "Brier loss"],
                    ["M1 logistic", "M0 + J + B + abs(B)", "Independent nested C selection", "Brier loss"],
                    ["NQ-only Ridge", "NQ direction, magnitude, momentum, time and weekday", "Standardization; alpha in 0.01...1000", "MSE"],
                    ["Cross-market Ridge", "NQ-only + BTC momentum/magnitude + coherence/J/B", "Independent nested alpha selection", "MSE"],
                ],
                [3.3 * cm, 6.3 * cm, 4.3 * cm, 2.7 * cm],
                styles,
            ),
            _p("Leakage controls", styles["h2"]),
            _table(
                [
                    ["Risk", "Control"],
                    ["Look-ahead feature scale", "Same-slot MAD uses completed prior sessions only"],
                    ["Preprocessing leakage", "Scaler is fitted inside each outer training fold"],
                    ["Hyperparameter leakage", "Regularization is selected only through inner purged folds"],
                    ["Outcome overlap and dependence", "Complete sessions are purged and bootstrap resampling uses session blocks"],
                    ["Researcher selection", "Primary/secondary roles are fixed; all nested attempts enter trial ledgers"],
                    ["Control-result cherry-picking", "Overnight control is mandatory and cannot replace the primary"],
                ],
                [5.0 * cm, 11.6 * cm],
                styles,
            ),
            Spacer(1, 0.15 * cm),
            _box(
                "Interpretation rule",
                "A lower loss is better. State evidence requires the upper 95% bound of "
                "M1-minus-M0 Brier loss below zero, directionally consistent log loss and "
                "no material calibration deterioration. Return evidence requires the upper "
                "95% bound of cross-minus-NQ-only squared-error loss below zero and "
                "directionally consistent MAE.",
                styles,
            ),
            _p(
                "The bootstrap conditions on fitted OOF predictions. It captures clustering "
                "within analysis sessions but not uncertainty from rerunning the complete "
                "research process on an independent historical sample.",
                styles["small"],
            ),
            PageBreak(),
        ]
    )

    # Page 5 - descriptive and state results
    story.extend(_section("4. Descriptive response and state persistence", styles))
    story.extend(
        [
            Image(str(FIGURES / "response_curve.png"), width=16.8 * cm, height=6.9 * cm),
            _p(
                "Figure 1. Signed NQ open-to-open response conditional on current BTC-NQ "
                "body-direction agreement. Intervals resample complete sessions. The "
                "positive 60-minute cash estimate is secondary and cannot replace the "
                "five-minute primary.",
                styles["caption"],
            ),
            _p(
                f"The cash-session primary descriptive estimate is "
                f"<b>{descriptive_5['mean_signed_nq_return_bps']:.3f} bps</b> across "
                f"{descriptive_5['event_count']:,} events; its interval includes zero. "
                "There is therefore no unconditional five-minute continuation result to "
                "serve as a trading premise.",
                styles["body"],
            ),
            _p("State-model result", styles["h2"]),
            _table(
                [
                    ["Five-minute model", "Brier", "Log loss", "ECE"],
                    ["Training-rate benchmark", f"{state_5['metrics']['benchmark']['brier_score']:.6f}", f"{state_5['metrics']['benchmark']['log_loss']:.6f}", f"{state_5['metrics']['benchmark']['expected_calibration_error']:.6f}"],
                    ["M0: coherence", f"{state_5['metrics']['m0']['brier_score']:.6f}", f"{state_5['metrics']['m0']['log_loss']:.6f}", f"{state_5['metrics']['m0']['expected_calibration_error']:.6f}"],
                    ["M1: + magnitude", f"{state_5['metrics']['m1']['brier_score']:.6f}", f"{state_5['metrics']['m1']['log_loss']:.6f}", f"{state_5['metrics']['m1']['expected_calibration_error']:.6f}"],
                ],
                [6.4 * cm, 3.4 * cm, 3.4 * cm, 3.4 * cm],
                styles,
                alignments=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
            ),
            _p(
                f"Across {state_5['event_count']:,} OOF events, M1-minus-M0 Brier loss is "
                "<b>-0.000699</b> with interval <b>[-0.001120, -0.000297]</b>. The reduction "
                "is only about 0.32% relative to M0. It is statistically stable within this "
                "development sample, but practically small and not a result about "
                "execution or P&amp;L.",
                styles["body"],
            ),
            PageBreak(),
        ]
    )

    # Page 6 - return and control results
    story.extend(_section("5. Incremental return value and overnight control", styles))
    story.extend(
        [
            Image(str(FIGURES / "primary_results.png"), width=17.0 * cm, height=5.1 * cm),
            _p(
                "Figure 2. Primary five-minute paired loss differences. Points are OOF "
                "means; bars are complete-session bootstrap 95% intervals. Lower favors "
                "the expanded cross-market model.",
                styles["caption"],
            ),
            _p("Cash-session return comparison", styles["h2"]),
            _table(
                [
                    ["Model", "MSE (bps^2)", "RMSE (bps)", "MAE (bps)", "OOS R2"],
                    ["Fold training mean", f"{return_5['metrics']['benchmark']['mean_squared_error']:.3f}", f"{return_5['metrics']['benchmark']['root_mean_squared_error_bps']:.3f}", f"{return_5['metrics']['benchmark']['mean_absolute_error_bps']:.3f}", "0.0000"],
                    ["NQ-only Ridge", f"{return_5['metrics']['nq_only']['mean_squared_error']:.3f}", f"{return_5['metrics']['nq_only']['root_mean_squared_error_bps']:.3f}", f"{return_5['metrics']['nq_only']['mean_absolute_error_bps']:.3f}", f"{return_5['metrics']['nq_only']['out_of_sample_r_squared_vs_benchmark']:.4f}"],
                    ["Cross-market Ridge", f"{return_5['metrics']['cross_market']['mean_squared_error']:.3f}", f"{return_5['metrics']['cross_market']['root_mean_squared_error_bps']:.3f}", f"{return_5['metrics']['cross_market']['mean_absolute_error_bps']:.3f}", f"{return_5['metrics']['cross_market']['out_of_sample_r_squared_vs_benchmark']:.4f}"],
                ],
                [5.0 * cm, 3.1 * cm, 2.9 * cm, 2.8 * cm, 2.8 * cm],
                styles,
                alignments=["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
            ),
            _p(
                "Cross-market-minus-NQ-only MSE is <b>+0.1924 bps^2</b> with interval "
                "<b>[+0.0728, +0.3222]</b>; MAE is also worse. Both Ridge models trail the "
                "fold training-mean benchmark. The registered incremental-return criterion "
                "is not met.",
                styles["body"],
            ),
            _p("Overnight negative control", styles["h2"]),
            _p(
                f"Magnitude also improves overnight state prediction: M1-minus-M0 Brier "
                f"loss is {overnight_state['m1_minus_m0']['brier_score_difference']:.6f} "
                "with interval [-0.000440, -0.000081]. Cash-session specificity is therefore "
                "not supported. The overnight return MSE difference is "
                f"{overnight_return['cross_market_minus_nq_only']['mean_squared_error_difference']:+.4f} "
                "bps^2 with an interval spanning zero, MAE worsens, and both Ridge models "
                "again trail the fold mean.",
                styles["body"],
            ),
            _box(
                "Economic conclusion",
                "The data separate state predictability from return predictability. A small "
                "improvement in agreement probabilities does not imply an exploitable NQ "
                "return. Costs cannot rescue a gross return effect that is already absent.",
                styles,
                background=PALE_RED,
                accent=RED,
            ),
            PageBreak(),
        ]
    )

    # Page 7 - calibration, limitations and conclusion
    story.extend(_section("6. Calibration, limitations and conclusion", styles))
    story.extend(
        [
            Image(str(FIGURES / "state_calibration.png"), width=14.6 * cm, height=5.6 * cm),
            _p(
                "Figure 3. Reliability bins for five-minute M0 and M1 predictions. Empty "
                "bins are omitted from the plotted lines but retained in committed tables.",
                styles["caption"],
            ),
            _p("Limitations", styles["h2"]),
            _table(
                [
                    ["Limitation", "Consequence"],
                    ["No pre-ETP history", "The motivating post-ETF integration narrative is not tested causally or as a before/after design"],
                    ["No pristine holdout", "Intervals and model comparisons remain development evidence"],
                    ["Partial NQ provenance", "The complete historical roll-selection rule cannot be reconstructed"],
                    ["Systematic missing sessions", "Results may not generalize as if session loss were random; weekdays are reported separately"],
                    ["No execution-quality MNQ data", "No cost-adjusted strategy, liquidity or deployment claim is made"],
                ],
                [5.0 * cm, 11.6 * cm],
                styles,
            ),
            _p("Conclusion", styles["h2"]),
            _p(
                "The study finds a small and reproducible development-sample association "
                "between volatility-adjusted joint magnitude and persistence of the "
                "BTC-NQ same-direction state. That association repeats in overnight trading, "
                "which argues against a cash-session-specific mechanism. The registered "
                "linear return test is negative: BTC/coherence variables do not add "
                "five-minute NQ return value over an NQ-only baseline. The appropriate "
                "conclusion is conditional state dependence without demonstrated alpha.",
                styles["body"],
            ),
            _p("Reproducibility and credit", styles["h2"]),
            _p(
                "All compact results, fold diagnostics, trial ledgers, configurations and "
                "SHA-256 manifests are committed in release research-v1.0.0. Proprietary "
                "NQ rows remain local. The research question grew from earlier collaborative "
                "coursework with Alex Samuseva; this repository is a clean redesign and does "
                "not treat legacy notebook results as evidence.",
                styles["body"],
            ),
            _p("Selected references", styles["h2"]),
            _p(
                "Bailey, D. H., Borwein, J. M., Lopez de Prado, M., and Zhu, Q. J. (2014). "
                "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest "
                "Overfitting, and Non-Normality. <i>Journal of Portfolio Management</i>.",
                styles["reference"],
            ),
            _p(
                "Bailey, D. H., Borwein, J. M., Lopez de Prado, M., and Zhu, Q. J. (2017). "
                "The Probability of Backtest Overfitting. <i>Journal of Computational "
                "Finance</i>.",
                styles["reference"],
            ),
            _p(
                "Lopez de Prado, M. (2018). <i>Advances in Financial Machine Learning</i>. "
                "Wiley.",
                styles["reference"],
            ),
        ]
    )
    return story


def build_report() -> dict[str, Any]:
    """Generate figures, build the final PDF, and write an integrity manifest."""
    figure_manifest = build_all()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    content_path = OUTPUT.with_suffix(".content.pdf")
    styles = _styles()
    width, height = A4
    frame = Frame(
        1.65 * cm,
        1.20 * cm,
        width - 3.30 * cm,
        height - 2.55 * cm,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc = BaseDocTemplate(
        str(content_path),
        pagesize=A4,
        title="BTC-NQ Cross-Market Coherence Research",
        author="Robert Mazurczak",
        leftMargin=1.65 * cm,
        rightMargin=1.65 * cm,
        topMargin=1.35 * cm,
        bottomMargin=1.20 * cm,
        pageCompression=1,
    )
    doc.addPageTemplates([PageTemplate(id="academic", frames=[frame])])
    doc.build(_build_story(styles), canvasmaker=InvariantCanvas)
    _decorate_pdf(content_path, OUTPUT)
    content_path.unlink()

    reader = PdfReader(str(OUTPUT))
    manifest = {
        "schema_version": 1,
        "report_version": "1.0.0",
        "status": "completed_development_report",
        "source_policy": "committed_frozen_aggregates_only",
        "page_count": len(reader.pages),
        "pdf": {"file_name": OUTPUT.name, "sha256": _hash(OUTPUT)},
        "figure_manifest_sha256": _hash(ROOT / "report" / "figure_manifest.json"),
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


def verify_report() -> None:
    """Verify the committed PDF and every report artifact against its manifest."""
    manifest = _load(MANIFEST)
    if manifest["pdf"]["sha256"] != _hash(OUTPUT):
        raise ValueError("Committed report PDF does not match report_manifest.json.")
    if manifest["protocol_sha256"] != _hash(ROOT / "configs" / "research_protocol.yaml"):
        raise ValueError("Protocol changed after the report was generated.")
    if manifest["builder_sha256"] != _hash(Path(__file__)):
        raise ValueError("Report builder changed after the report was generated.")
    if manifest["figure_manifest_sha256"] != _hash(
        ROOT / "report" / "figure_manifest.json"
    ):
        raise ValueError("Figure manifest changed after the report was generated.")
    for name, expected in manifest["figures"].items():
        if _hash(FIGURES / name) != expected:
            raise ValueError(f"Figure hash mismatch: {name}")
    reader = PdfReader(str(OUTPUT))
    if len(reader.pages) != 7 or manifest["page_count"] != 7:
        raise ValueError("The final academic report must contain exactly seven pages.")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    required = [
        "completed development study",
        "not a preregistration",
        "No incremental value",
        "Overnight negative control",
        "conditional state dependence without demonstrated alpha",
    ]
    normalized_text = text.casefold()
    missing = [phrase for phrase in required if phrase.casefold() not in normalized_text]
    if missing:
        raise ValueError(f"Report text is missing required conclusions: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Verify committed report artifacts only."
    )
    args = parser.parse_args()
    if args.check:
        verify_report()
        print("Verified seven-page report and frozen-artifact hashes.")
    else:
        manifest = build_report()
        verify_report()
        print(
            f"Built {manifest['page_count']}-page report: {OUTPUT.relative_to(ROOT)}"
        )


if __name__ == "__main__":
    main()
