"""
Chair groups: labs that work together (a university chair, a department), and
share what they have.

They are the suite's: an administrator puts labs in chair groups on the
dashboard's Labs tab, kept in the suite's database (suite.db: chair_groups, and
labs.chair_group_id), which is read here, never written. A lab is in one at
most. Labs of a chair group see each other's lines, seed lots, plants and
places (without changing them), as they see each other's stocks in Lab Stocks.
"""

import os
from typing import Optional, Set

from app.sources import _read


def _path() -> str:
    return os.environ.get('SUITE_DATABASE_PATH', '/suite/suite.db')


def _known() -> bool:
    """A suite with chair groups (2.9.0 on)."""
    return 'chair_group_id' in {r['name'] for r in _read(_path(), 'PRAGMA table_info(labs)')}


def name_of(lab: str) -> Optional[str]:
    """The name of the lab's chair group, or None."""
    if not _known():
        return None
    rows = _read(_path(), 'SELECT g.name FROM labs l JOIN chair_groups g ON g.id = l.chair_group_id '
                          'WHERE l.name = ? COLLATE NOCASE', (lab,))
    return rows[0]['name'] if rows else None


def mates(labs: Set[str]) -> Set[str]:
    """Every lab (casefolded) in a chair group with one of these labs (casefolded)."""
    if not labs or not _known():
        return set()
    rows = _read(_path(), 'SELECT m.name FROM labs l JOIN labs m ON m.chair_group_id = l.chair_group_id '
                          f'WHERE l.chair_group_id IS NOT NULL AND lower(l.name) IN ({", ".join("?" * len(labs))})',
                 sorted(labs))
    return {r['name'].casefold() for r in rows}


def demo_labs() -> Set[str]:
    """
    The teaching demo's labs (casefolded): those in the chair group the suite records as the
    demo's (suite.db settings 'demo.chair_group', set by the suite's demo/accounts.py).
    """
    rows = _read(_path(), "SELECT value FROM settings WHERE key = 'demo.chair_group'")
    if not rows or not rows[0]['value'] or not _known():
        return set()
    return {r['name'].casefold() for r in _read(_path(), 'SELECT name FROM labs WHERE chair_group_id = ?',
                                                 (rows[0]['value'],))}


def in_demo(person) -> bool:
    """
    In the teaching demo: every lab of theirs is one of the demo's. They see the demo's records
    only: no plasmid of a real lab's, however public, and no page of the notebook's library.
    """
    if person is None or person.is_admin:
        return False
    mine = person.lab_names()
    return bool(mine) and mine <= demo_labs()
