"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest

FIXTURE_PDB = Path(__file__).parent / "data" / "minimal_pmhc.pdb"


@pytest.fixture
def fixture_pdb() -> str:
    return str(FIXTURE_PDB)
