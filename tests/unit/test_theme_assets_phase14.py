"""Static theme, contrast and CSP-compatibility checks for Phase 14."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _rgb(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.removeprefix("#")
    return (
        int(value[0:2], 16) / 255,
        int(value[2:4], 16) / 255,
        int(value[4:6], 16) / 255,
    )


def _luminance(hex_color: str) -> float:
    channels = [
        (channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
        for channel in _rgb(hex_color)
    ]
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(foreground: str, background: str) -> float:
    light = max(_luminance(foreground), _luminance(background))
    dark = min(_luminance(foreground), _luminance(background))
    return (light + 0.05) / (dark + 0.05)


def test_approved_theme_colors_meet_normal_text_contrast() -> None:
    pairs = (
        ("#172033", "#f5f7fb"),
        ("#647084", "#ffffff"),
        ("#1d4ed8", "#ffffff"),
        ("#edf2ff", "#0c1220"),
        ("#a9b4c8", "#121a2a"),
        ("#bfdbfe", "#121a2a"),
    )

    assert all(_contrast(foreground, background) >= 4.5 for foreground, background in pairs)


def test_templates_do_not_require_inline_scripts_or_styles() -> None:
    templates = (_ROOT / "app" / "templates").rglob("*.html")
    for template in templates:
        content = template.read_text(encoding="utf-8")
        assert "<style" not in content.lower(), template
        for script in re.findall(r"<script[^>]*>", content, flags=re.IGNORECASE):
            assert " src=" in script.lower(), template


def test_theme_javascript_avoids_untrusted_html_sinks() -> None:
    javascript = (_ROOT / "app" / "static" / "js" / "theme.js").read_text(encoding="utf-8")
    bootstrap = (_ROOT / "app" / "static" / "js" / "theme-bootstrap.js").read_text(encoding="utf-8")

    assert "innerHTML" not in javascript
    assert "outerHTML" not in javascript
    assert "document.write" not in javascript
    assert "eval(" not in javascript
    assert "software-hub-theme" in bootstrap
