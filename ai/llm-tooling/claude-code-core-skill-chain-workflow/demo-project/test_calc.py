"""Tests for calc.py. Run with: pytest -q"""

import calc


def test_add():
    assert calc.add(2, 3) == 5
    assert calc.add(-1, 1) == 0


def test_subtract():
    assert calc.subtract(5, 2) == 3
    assert calc.subtract(0, 4) == -4
