"""Establish the Phase 3 migration baseline.

Revision ID: 0001_phase3_baseline
Revises:
Create Date: 2026-07-23
"""

from collections.abc import Sequence

revision: str = "0001_phase3_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Record the baseline; domain tables are introduced in Phase 4."""


def downgrade() -> None:
    """Remove the baseline revision marker."""
