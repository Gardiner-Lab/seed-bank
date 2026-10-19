"""
What the seed bank reads from the other tools, never changing it.

    Plasmids        from the Plasmid Editor's library, to say which construct a
                    line carries; a plasmid opens in the editor.
    Notebook pages  that link to a line, seed lot or plant (data-seed="S-0001"),
                    shown on that record to whoever may open the page.
"""

import os
import sqlite3
from typing import List

from app.people import Person


def _read(path: str, sql: str, args=()) -> List[sqlite3.Row]:
    if not path or not os.path.exists(path):
        return []
    try:
        conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def _public_column(path: str) -> str:
    """The editor's "Public" flag, or none (0) in an editor database from before it."""
    names = {r['name'] for r in _read(path, 'PRAGMA table_info(sequences)')}
    return 's.public' if 'public' in names else '0 AS public'


def plasmids(person: Person, query: str = '', limit: int = 25) -> List[dict]:
    """Plasmids in the editor's library this person may open, best matches first."""
    q = (query or '').strip()
    path = os.environ.get('EDITOR_DATABASE_PATH', '/editor/plasmid_editor.db')
    rows = _read(path,
                 f'SELECT s.id, s.name, length(s.sequence) AS length, {_public_column(path)}, s.confirmed_at, u.username AS owner '
                 'FROM sequences s LEFT JOIN users u ON u.id = s.owner_id '
                 "WHERE (? = '' OR s.name LIKE ?) ORDER BY CASE WHEN s.name LIKE ? THEN 0 ELSE 1 END, "
                 's.updated_at DESC LIMIT 400', (q, f'%{q}%', f'{q}%'))
    found = []
    for r in rows:
        if person.oversees(r['owner']) or person.shares_lab(r['owner']) or r['public']:
            found.append({'id': r['id'], 'name': r['name'], 'length': r['length'], 'owner': r['owner'],
                          'confirmed': bool(r['confirmed_at'])})
        if len(found) >= limit:
            break
    return found


def notebook_mentions(person: Person, code: str) -> List[dict]:
    """Notebook pages that link to this record, which this person may open."""
    rows = _read(os.environ.get('NOTEBOOK_DATABASE_PATH', '/notebook/notebook.db'),
                 "SELECT n.id, n.title, n.type, n.owner, n.updated_at FROM links l JOIN notes n ON n.id = l.note_id "
                 "WHERE l.target_type = 'seed' AND l.target_id = ? AND n.deleted_at IS NULL "
                 'ORDER BY n.updated_at DESC LIMIT 100', (code,))
    return [dict(r) for r in rows if r['owner'] is None or person.oversees(r['owner'])]
