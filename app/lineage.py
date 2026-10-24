"""
A record's family tree, across the suite: where it came from and what it led to.

    constructs   the plasmids its line carries (or a line it came from does), from
                 the Plasmid Editor, each with its glycerol stocks in Lab Stocks
    ancestry     the lines it descends from (its pedigree), and for a seed lot or
                 a plant the lots and plants it came from, oldest first
    descendants  what came from it: a line's seed lots, the plants sown from them,
                 the lots harvested from those, and so on; and the lines made from
                 it (crosses, transformants, founded lines)

Every step lists the notebook pages that link to it. Started from a plasmid, the
tree is the plasmid, its stocks, and the lines carrying it with all that came of
them. Only what was harvested, starred or written about is shown plant by plant;
the other plants of a sowing are counted. A large tree stops at TREE_BUDGET steps.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from app import sources
from app.db import connect
from app.people import Person
from app.records import NotFound, _ancestor_lines, _ancestry, _brief, _pedigree, can_see, visible

TREE_BUDGET = 400


class _Tree:
    def __init__(self, conn, person: Person, focus: Tuple[str, str]):
        self.conn, self.person, self.focus = conn, person, focus
        self.budget = TREE_BUDGET
        self.truncated = False
        self.shown: Set[Tuple[str, str]] = set()
        self.nodes: List[dict] = []          # every node, for its notebook pages

    def brief(self, kind: str, record_id: str, extra: Optional[dict] = None) -> Optional[dict]:
        row = self.conn.execute(f"SELECT * FROM {dict(line='lines', lot='lots', plant='plants')[kind]} WHERE id = ?",
                                (record_id,)).fetchone()
        if row is None:
            return None
        if not can_see(self.person, row):
            return {'kind': kind, 'code': row['code'], 'hidden': True}
        node = _brief(self.conn, kind, record_id)
        node.pop('id', None)
        node.update(extra or {})
        if kind == 'lot':
            node['used_up'] = bool(row['used_up'])
        elif kind == 'plant':
            node.update(selected=bool(row['selected']), treatment=row['treatment'])
        if (kind, record_id) == self.focus:
            node['focus'] = True
        self.nodes.append(node)
        return node

    def spend(self) -> bool:
        self.budget -= 1
        if self.budget < 0:
            self.truncated = True
        return self.budget >= 0

    def line(self, line_id: str, role: str = '', depth: int = 0) -> Optional[dict]:
        node = self.brief('line', line_id, {'role': role} if role else None)
        if node is None or node.get('hidden') or not self.spend():
            return node
        self.shown.add(('line', line_id))
        node['lots'] = []
        # Its own seeds: lots not harvested from one of its own plants (from outside, a
        # transformation, a cross); the rest follow from the plants they came from.
        for r in self.conn.execute(
                'SELECT s.id FROM lots s LEFT JOIN plants p ON p.id = s.from_plant_id '
                'WHERE s.line_id = ? AND s.deleted_at IS NULL AND (p.id IS NULL OR p.line_id != s.line_id) '
                'ORDER BY s.created_at', (line_id,)).fetchall():
            lot = self.lot(r['id'], depth)
            if lot:
                node['lots'].append(lot)
        node['lines'] = []
        if depth < 8:
            for r in self.conn.execute(
                    'SELECT lp.line_id, lp.role FROM line_parents lp JOIN lines l ON l.id = lp.line_id '
                    'WHERE lp.parent_id = ? AND l.deleted_at IS NULL ORDER BY l.created_at', (line_id,)).fetchall():
                if ('line', r['line_id']) in self.shown:
                    continue
                child = self.line(r['line_id'], r['role'], depth + 1)
                if child:
                    node['lines'].append(child)
        return node

    def lot(self, lot_id: str, depth: int = 0) -> Optional[dict]:
        if ('lot', lot_id) in self.shown:
            node = self.brief('lot', lot_id, {'ref': True})
            return node
        node = self.brief('lot', lot_id)
        if node is None or node.get('hidden') or not self.spend():
            return node
        self.shown.add(('lot', lot_id))
        node['plants'], counts = [], {}
        for p in self.conn.execute('SELECT * FROM plants WHERE lot_id = ? AND deleted_at IS NULL ORDER BY number',
                                   (lot_id,)).fetchall():
            harvested = self.conn.execute(
                'SELECT id FROM lots WHERE (from_plant_id = ? OR father_plant_id = ?) AND deleted_at IS NULL '
                'ORDER BY created_at', (p['id'], p['id'])).fetchall()
            if harvested or p['selected'] or ('plant', p['id']) == self.focus or (depth < 12 and self._written(p['code'])):
                plant = self.plant(p['id'], harvested, depth)
                if plant:
                    node['plants'].append(plant)
            else:
                counts[p['status']] = counts.get(p['status'], 0) + 1
        node['others'] = counts
        return node

    def plant(self, plant_id: str, harvested=None, depth: int = 0) -> Optional[dict]:
        node = self.brief('plant', plant_id)
        if node is None or node.get('hidden') or not self.spend():
            return node
        self.shown.add(('plant', plant_id))
        node['lots'] = []
        if depth < 12:
            for r in harvested if harvested is not None else self.conn.execute(
                    'SELECT id FROM lots WHERE (from_plant_id = ? OR father_plant_id = ?) AND deleted_at IS NULL '
                    'ORDER BY created_at', (plant_id, plant_id)).fetchall():
                lot = self.lot(r['id'], depth + 1)
                if lot:
                    node['lots'].append(lot)
        return node

    _written_codes: Optional[Set[str]] = None

    def _written(self, code: str) -> bool:
        """Whether any notebook page links to this plant (one read of the notebook, then remembered)."""
        if self._written_codes is None:
            self._written_codes = written_about()
        return code in self._written_codes


def written_about() -> Set[str]:
    """Codes of seed bank records that any notebook page links to."""
    import os
    rows = sources._read(os.environ.get('NOTEBOOK_DATABASE_PATH', '/notebook/notebook.db'),
                         "SELECT DISTINCT l.target_id FROM links l JOIN notes n ON n.id = l.note_id "
                         "WHERE l.target_type = 'seed' AND n.deleted_at IS NULL")
    return {r['target_id'] for r in rows}


def _constructs(conn, person: Person, line_ids: List[str], only: Optional[str] = None) -> List[dict]:
    """The plasmids these lines carry (or just `only`), with their stocks and which of the lines carry each."""
    carried: Dict[str, dict] = {}
    for line_id in line_ids:
        for r in conn.execute('SELECT plasmid_id, name FROM line_plasmids WHERE line_id = ? ORDER BY name', (line_id,)):
            entry = carried.setdefault(r['plasmid_id'], {'kind': 'plasmid', 'id': r['plasmid_id'], 'name': r['name'],
                                                         'carried_by': []})
            line = _brief(conn, 'line', line_id)
            if line and can_see(person, conn.execute('SELECT lab FROM lines WHERE id = ?', (line_id,)).fetchone()):
                entry['carried_by'].append({'code': line['code'], 'name': line['name']})
    if only and only not in carried:
        carried[only] = {'kind': 'plasmid', 'id': only, 'name': '', 'carried_by': []}
    info = sources.plasmid_info(person, carried)
    stocks = sources.glycerol_stocks(person, carried)
    out = []
    for plasmid_id, entry in carried.items():
        about = info.get(plasmid_id)
        entry.update(name=(about or {}).get('name') or entry['name'] or 'A plasmid no longer in the editor',
                     length=(about or {}).get('length'), confirmed=(about or {}).get('confirmed', False),
                     opens=(about or {}).get('opens', False), missing=about is None,
                     stocks=[dict(s, kind='stock') for s in stocks.get(plasmid_id, [])])
        if not entry['opens'] and not entry['carried_by'] and not entry['stocks']:
            continue                      # someone else's private plasmid, not part of anything this person sees
        out.append(entry)
    return out


def _attach_mentions(person: Person, nodes: List[dict], constructs: List[dict]) -> None:
    targets = [('seed', n['code']) for n in nodes if not n.get('hidden')]
    for c in constructs:
        targets.append(('plasmid', c['id']))
        targets += [('stock', s['code']) for s in c['stocks']]
    found = sources.mentions_of(person, targets)
    for n in nodes:
        n['mentions'] = found.get(('seed', n.get('code')), [])
    for c in constructs:
        c['mentions'] = found.get(('plasmid', c['id']), [])
        for s in c['stocks']:
            s['mentions'] = found.get(('stock', s['code']), [])


def _pedigree_nodes(tree: dict, into: List[dict]) -> None:
    if tree:
        into.append(tree)
        for parent in tree.get('parents') or []:
            _pedigree_nodes(parent, into)


def family_tree(person: Person, kind: str, ident: str) -> dict:
    with connect() as conn:
        if kind == 'plasmid':
            tree = _Tree(conn, person, ('plasmid', ident))
            carriers = [r['id'] for r in conn.execute(
                'SELECT l.id, l.lab FROM line_plasmids lp JOIN lines l ON l.id = lp.line_id '
                'WHERE lp.plasmid_id = ? AND l.deleted_at IS NULL ORDER BY l.created_at', (ident,)) if can_see(person, r)]
            constructs = _constructs(conn, person, carriers, only=ident)
            constructs = [c for c in constructs if c['id'] == ident]
            if not constructs:
                raise NotFound('No such plasmid, or not one you can open')
            # The lines that took it up: not those that inherited it from another of them.
            top = [c for c in carriers if not set(_ancestor_lines(conn, c)) & set(carriers)]
            descendants = [n for n in (tree.line(c) for c in top) if n]
            _attach_mentions(person, tree.nodes, constructs)
            return {'focus': {'kind': 'plasmid', 'id': ident, 'name': constructs[0]['name']}, 'constructs': constructs,
                    'pedigree': None, 'chain': [], 'descendants': descendants, 'truncated': tree.truncated}
        row = visible(conn, person, kind, ident)
        tree = _Tree(conn, person, (kind, row['id']))
        line_id = row['id'] if kind == 'line' else row['line_id']
        constructs = _constructs(conn, person, [line_id] + _ancestor_lines(conn, line_id))
        pedigree = _pedigree(conn, line_id)
        pedigree_nodes: List[dict] = []
        _pedigree_nodes(pedigree, pedigree_nodes)
        chain = list(reversed(_ancestry(conn, kind, row['id']))) if kind != 'line' else []
        if kind == 'line':
            descendants = [tree.line(row['id'])]
        elif kind == 'lot':
            descendants = [tree.lot(row['id'])]
        else:
            descendants = [tree.plant(row['id'])]
        all_nodes = tree.nodes + pedigree_nodes + chain
        _attach_mentions(person, all_nodes, constructs)
        return {'focus': {'kind': kind, 'code': row['code']}, 'constructs': constructs, 'pedigree': pedigree,
                'chain': chain, 'descendants': [d for d in descendants if d], 'truncated': tree.truncated}
