"""Deterministic and axe-core accessibility audits for Playwright E2E."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

_AUDIT_SCRIPT = r"""
() => {
  const violations = [];
  const describe = (element) => {
    const id = element.id ? `#${element.id}` : '';
    const name = element.getAttribute('name');
    return `${element.tagName.toLowerCase()}${id}${name ? `[name="${name}"]` : ''}`;
  };
  const accessibleName = (element) => {
    const labelledBy = element.getAttribute('aria-labelledby');
    if (labelledBy) {
      return labelledBy
        .split(/\s+/)
        .map((id) => document.getElementById(id)?.textContent || '')
        .join(' ')
        .trim();
    }
    return (
      element.getAttribute('aria-label') ||
      element.getAttribute('title') ||
      element.textContent ||
      ''
    ).trim();
  };

  if (document.documentElement.lang !== 'uk') {
    violations.push('html[lang] must be uk');
  }
  if (document.querySelectorAll('main').length !== 1) {
    violations.push('page must contain exactly one main landmark');
  }
  if (document.querySelectorAll('h1').length !== 1) {
    violations.push('page must contain exactly one h1');
  }
  if (!document.querySelector('a.skip-link[href^="#"]')) {
    violations.push('page must contain a skip link');
  }

  const ids = new Set();
  document.querySelectorAll('[id]').forEach((element) => {
    if (ids.has(element.id)) {
      violations.push(`duplicate id: ${element.id}`);
    }
    ids.add(element.id);
  });

  document.querySelectorAll('img').forEach((image) => {
    if (!image.hasAttribute('alt')) {
      violations.push(`${describe(image)} is missing alt`);
    }
  });

  document.querySelectorAll('input, select, textarea').forEach((control) => {
    if (control.type === 'hidden') return;
    const labelled =
      control.labels?.length > 0 ||
      Boolean(control.getAttribute('aria-label')) ||
      Boolean(control.getAttribute('aria-labelledby'));
    if (!labelled) {
      violations.push(`${describe(control)} has no accessible label`);
    }
  });

  document.querySelectorAll('button, a[href]').forEach((control) => {
    if (!accessibleName(control)) {
      violations.push(`${describe(control)} has no accessible name`);
    }
  });

  let previousLevel = 0;
  document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach((heading) => {
    const level = Number(heading.tagName.slice(1));
    if (previousLevel && level > previousLevel + 1) {
      violations.push(`heading level skips from h${previousLevel} to h${level}`);
    }
    previousLevel = level;
  });

  const overflow =
    document.documentElement.scrollWidth - document.documentElement.clientWidth;
  if (overflow > 1) {
    violations.push(`horizontal overflow: ${overflow}px`);
  }

  return violations;
}
"""

_AXE_SCRIPT = r"""
async () => {
  const result = await axe.run(document, {
    runOnly: {
      type: 'tag',
      values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'],
    },
    resultTypes: ['violations'],
  });
  return result.violations
    .filter((violation) => ['serious', 'critical'].includes(violation.impact))
    .map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      help: violation.help,
      targets: violation.nodes.flatMap((node) => node.target),
    }));
}
"""


def audit_page(page: Page) -> tuple[str, ...]:
    """Return deterministic accessibility violations for the current page."""

    result: Any = page.evaluate(_AUDIT_SCRIPT)
    if not isinstance(result, list) or not all(isinstance(item, str) for item in result):
        raise TypeError("Accessibility audit returned an unexpected payload.")
    return tuple(result)


def audit_page_with_axe(page: Page) -> tuple[str, ...]:
    """Run the pinned axe-core engine and return serious/critical violations."""

    raw_path = os.getenv("AXE_CORE_PATH")
    if not raw_path:
        raise RuntimeError("AXE_CORE_PATH is required for browser accessibility tests.")
    axe_path = Path(raw_path)
    if not axe_path.is_file():
        raise RuntimeError(f"axe-core script does not exist: {axe_path}")

    page.add_script_tag(path=str(axe_path))
    result: Any = page.evaluate(_AXE_SCRIPT)
    if not isinstance(result, list):
        raise TypeError("axe-core returned an unexpected payload.")

    violations: list[str] = []
    for item in result:
        if not isinstance(item, dict):
            raise TypeError("axe-core violation entry has an unexpected type.")
        rule_id = str(item.get("id", "unknown"))
        impact = str(item.get("impact", "unknown"))
        help_text = str(item.get("help", "Accessibility violation"))
        targets = item.get("targets", [])
        target_text = ", ".join(str(target) for target in targets)
        violations.append(f"{impact}:{rule_id}: {help_text} [{target_text}]")
    return tuple(violations)
