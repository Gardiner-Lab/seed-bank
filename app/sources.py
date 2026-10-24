"""
What the seed bank reads from the other tools, never changing it.

    Plasmids        from the Plasmid Editor's library, to say which construct a
                    line carries; a plasmid opens in the editor.
    Notebook pages  that link to a line, seed lot or plant (data-seed="S-0001"),
                    shown on that record to whoever may open the page; and, for
                    a family tree, those linking to its plasmids and stocks
    Glycerol stocks from Lab Stocks: the frozen cultures holding a plasmid, for
                    a family tree (of this person's labs and chair groups)
"""

import os
import sqlite3
from typing import Dict, Iterable, List, Tuple

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


def plasmid_info(person: Person, ids: Iterable[str]) -> Dict[str, dict]:
    """The editor's plasmids by id, as far as this person may open them: {id: {name, length, confirmed, opens}}."""
    ids = list(dict.fromkeys(i for i in ids if i))[:400]
    if not ids:
        return {}
    path = os.environ.get('EDITOR_DATABASE_PATH', '/editor/plasmid_editor.db')
    rows = _read(path, f'SELECT s.id, s.name, length(s.sequence) AS length, {_public_column(path)}, s.confirmed_at, '
                       f'u.username AS owner FROM sequences s LEFT JOIN users u ON u.id = s.owner_id '
                       f'WHERE s.id IN ({",".join("?" * len(ids))})', ids)
    return {r['id']: {'name': r['name'], 'length': r['length'], 'confirmed': bool(r['confirmed_at']),
                      'opens': bool(person.oversees(r['owner']) or person.shares_lab(r['owner']) or r['public'])}
            for r in rows}


def glycerol_stocks(person: Person, plasmid_ids: Iterable[str]) -> Dict[str, List[dict]]:
    """Lab Stocks' glycerol stocks of these plasmids that this person sees there: their labs' and their chair groups'."""
    ids = list(dict.fromkeys(i for i in plasmid_ids if i))[:400]
    if not ids:
        return {}
    rows = _read(os.environ.get('STOCKS_DATABASE_PATH', '/stocks/stocks.db'),
                 'SELECT code, lab, plasmid_id, plasmid_name, clone, host, location, status FROM glycerol '
                 f'WHERE deleted_at IS NULL AND plasmid_id IN ({",".join("?" * len(ids))}) ORDER BY code', ids)
    from app.records import sees
    labs = sees(person)
    out: Dict[str, List[dict]] = {}
    for r in rows:
        if person.is_admin or (r['lab'] or '').casefold() in labs:
            out.setdefault(r['plasmid_id'], []).append({k: r[k] for k in ('code', 'clone', 'host', 'location', 'status')})
    return out


def mentions_of(person: Person, targets: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], List[dict]]:
    """Notebook pages linking to each of many records ((kind, id): 'seed' and a code, 'plasmid' and an id, ...)."""
    targets = list(dict.fromkeys(t for t in targets if t[1]))
    path = os.environ.get('NOTEBOOK_DATABASE_PATH', '/notebook/notebook.db')
    out: Dict[Tuple[str, str], List[dict]] = {}
    for start in range(0, len(targets), 400):
        chunk = targets[start:start + 400]
        rows = _read(path, 'SELECT l.target_type, l.target_id, n.id, n.title, n.owner, n.updated_at FROM links l '
                           'JOIN notes n ON n.id = l.note_id WHERE n.deleted_at IS NULL AND ('
                           + ' OR '.join(['(l.target_type = ? AND l.target_id = ?)'] * len(chunk))
                           + ') ORDER BY n.updated_at DESC', [x for t in chunk for x in t])
        for r in rows:
            if r['owner'] is None or person.oversees(r['owner']):
                out.setdefault((r['target_type'], r['target_id']), []).append(
                    {'id': r['id'], 'title': r['title'], 'updated_at': r['updated_at']})
    return out
