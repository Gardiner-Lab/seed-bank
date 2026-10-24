"""
Lines, seed lots and plants, and how they descend from each other.

    a line        is a genetic identity: wild type, a mutant, a transgenic event, a cross
    a seed lot    holds seeds of a line and generation; it came from a plant
                  (harvested), from two plants (a cross), or from outside (a
                  stock centre, a colleague)
    a plant       is sown from a lot and numbered within it; it can be harvested
                  into a new lot (T1 -> T2), crossed, or found a line of its own
                  (a T1 transformant becomes an independent event). It grows in
                  a place (a growth chamber, a greenhouse; app/growing.py), at a
                  position there, under a treatment.

Records belong to the lab of whoever made them. Everyone in that lab sees and
changes them; the other labs of its chair group (app/chairs.py) see them, but do
not change them; other labs do not see them at all; administrators see and
change all. Every change is logged with who made it.
"""

import re
import secrets
from typing import Any, Dict, List, Optional

from app import stats
from app.db import connect
from app.people import Person

LINE_KINDS = ('wild type', 'mutant', 'transgenic', 'population', 'cross', 'other')
ZYGOSITY = ('', 'homozygous', 'heterozygous', 'hemizygous', 'segregating', 'wild type', 'unknown')
PLANT_STATUS = ('growing', 'harvested', 'discarded', 'dead')
PARENT_ROLES = ('mother', 'father', 'background', 'founded from', 'parent')
# A line's biosafety, stock center and genetics, as the GMO register (and eLab's
# Plant Seed) has them. An empty permit or biosafety level: the lab's own.
BIOSAFETY = ('', 'I', 'II', 'III', 'IV', 'Unknown')
GMO_TYPES = ('', 'T-DNA insertion', 'Plasmid introduction', 'Chromosomal mutation', 'Unknown')
GENE_EXPRESSION = ('', 'knock-out', 'knock-down', 'knock-in', 'overexpressor line', 'marker line', 'unknown', '~ other ~')
PERMITS = ('IG 99-249', 'New GMO (not yet in permit)')
COLLECTIONS = ('SALK', 'GABI', 'SAIL', 'WiscDsLox', 'FLAG (INRA)', 'SM', 'CSHL', 'AGRIKOLA', 'TRANSPLANTA',
               'IMA (Ds insertion)', 'Feldmann T-DNA Tagged lines', 'wildtype', 'non-GMO mutant')
LINE_TEXT = (('permit', 120), ('accession', 120), ('collection', 120), ('stock_center_number', 120),
             ('stock_center_url', 500), ('selection_marker', 200), ('mutation_info', 5000), ('construction', 5000))
PREFIX = {'line': 'L', 'lot': 'S', 'plant': 'P'}
TABLE = {'line': 'lines', 'lot': 'lots', 'plant': 'plants'}
KIND_OF_PREFIX = {v: k for k, v in PREFIX.items()}
MAX_PLANTS_PER_SOWING = 500


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


def labs_of(person: Person) -> List[str]:
    """Every lab whose records this person sees: theirs, or their own without a lab."""
    names = [m['lab'] for m in person.labs if m.get('lab')] or ([person.lab] if person.lab else [])
    return names or [f'user:{person.username}']


def lab_of(person: Person, chosen: Optional[str] = None, strict: bool = False) -> str:
    """
    The lab a new record joins: the one chosen, of theirs, else their first;
    their own without a lab. strict: a lab chosen that is not theirs is refused.
    """
    names = labs_of(person)
    if chosen:
        found = next((n for n in names if n.casefold() == str(chosen).strip().casefold()), None)
        if found:
            return found
        if strict:
            raise ValueError('Choose one of your labs')
    return names[0]


def leads(person: Person, lab: str) -> bool:
    """Chooses this lab's code: its lead, an admin, or anyone for their own records without a lab."""
    return person.is_admin or person.leads(lab) or lab.startswith('user:')


def sees(person: Person) -> set:
    """The labs (casefolded) whose records this person sees: theirs, and the other labs of their chair groups."""
    cached = getattr(person, '_sees', None)
    if cached is None:
        from app import chairs
        own = {n.casefold() for n in labs_of(person)}
        cached = own | chairs.mates(own)
        person._sees = cached
    return cached


def can_see(person: Person, row) -> bool:
    return person.is_admin or (row['lab'] or '').casefold() in sees(person)


def can_change(person: Person, row) -> bool:
    """Their own lab's: a chair group's other labs see a record, but do not change it."""
    return person.is_admin or (row['lab'] or '').casefold() in {n.casefold() for n in labs_of(person)}


def _new_id() -> str:
    return secrets.token_hex(12)


LAB_CODE = re.compile(r'[A-Z][A-Z0-9]{0,5}')


def _suggest_lab_code(lab: str) -> str:
    """A lab's initials (Gardiner Lab -> GL); a person without a lab, their name's first letters."""
    if lab.startswith('user:'):
        letters = re.sub(r'[^A-Za-z]', '', lab[5:])[:3]
    else:
        words = re.findall(r'[A-Za-z0-9]+', lab)
        letters = ''.join(w[0] for w in words if w[0].isalpha())[:4]
        if len(letters) < 2:
            letters = re.sub(r'[^A-Za-z]', '', lab)[:3]
    return (letters or 'LAB').upper()


def lab_code(conn, lab: str) -> str:
    """The lab's code, given it the first time it is needed, and never the same as another lab's."""
    row = conn.execute('SELECT code FROM lab_codes WHERE lab = ?', (lab,)).fetchone()
    if row:
        return row['code']
    base = _suggest_lab_code(lab)
    code, n = base, 2
    while conn.execute('SELECT 1 FROM lab_codes WHERE code = ?', (code,)).fetchone():
        code, n = f'{base[:5]}{n}', n + 1
    conn.execute('INSERT INTO lab_codes (lab, code) VALUES (?, ?)', (lab, code))
    return code


def _code(conn, kind: str, lab: str) -> str:
    """The next code in this lab for this kind of record: GL-S-0042."""
    prefix = f'{lab_code(conn, lab)}-{PREFIX[kind]}'
    conn.execute('INSERT INTO counters (prefix, value) VALUES (?, 1) '
                 'ON CONFLICT(prefix) DO UPDATE SET value = value + 1', (prefix,))
    n = conn.execute('SELECT value FROM counters WHERE prefix = ?', (prefix,)).fetchone()[0]
    return f'{prefix}-{n:04d}'


def _lab_has_records(conn, lab: str) -> bool:
    return any(conn.execute(f'SELECT 1 FROM {t} WHERE lab = ? LIMIT 1', (lab,)).fetchone()
               for t in ('lines', 'lots', 'plants'))


def lab_info(person: Person, chosen: Optional[str] = None) -> dict:
    lab = lab_of(person, chosen)
    with connect() as conn:
        code = lab_code(conn, lab)
        fixed = _lab_has_records(conn, lab)
    return {'lab': lab, 'code': code, 'fixed': fixed, 'labs': labs_of(person),
            'can_change': not fixed and leads(person, lab)}


def set_lab_code(person: Person, code: str, chosen: Optional[str] = None) -> dict:
    """Choose the lab's code, before it has any records: a lab lead, an admin, or someone without a lab."""
    lab = lab_of(person, chosen, strict=True)
    code = (code or '').strip().upper()
    if not LAB_CODE.fullmatch(code):
        raise ValueError('A lab code is 1 to 6 letters and digits, starting with a letter, e.g. GL or GARD')
    if not leads(person, lab):
        raise Forbidden("Only the lab's lead or an administrator chooses the lab's code")
    with connect() as conn:
        if _lab_has_records(conn, lab):
            raise ValueError('The lab already has records: its code is fixed, as codes on labels never change')
        taken = conn.execute('SELECT lab FROM lab_codes WHERE code = ? AND lab != ?', (code, lab)).fetchone()
        if taken:
            raise ValueError(f'{code} is already another lab\'s code')
        conn.execute('INSERT INTO lab_codes (lab, code, set_by) VALUES (?, ?, ?) '
                     'ON CONFLICT(lab) DO UPDATE SET code = excluded.code, set_by = excluded.set_by, '
                     'set_at = CURRENT_TIMESTAMP', (lab, code, person.username))
    return lab_info(person, lab)


def _log(conn, kind: str, record_id: str, by: str, what: str) -> None:
    conn.execute('INSERT INTO changes (record_kind, record_id, changed_by, what) VALUES (?, ?, ?, ?)',
                 (kind, record_id, by, what[:1000]))


def _text(value: Any, limit: int = 500) -> str:
    return str(value if value is not None else '').strip()[:limit]


def _date(value: Any) -> Optional[str]:
    v = _text(value, 10)
    if not v:
        return None
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
        raise ValueError('Dates are written YYYY-MM-DD')
    return v


def next_generation(generation: str) -> str:
    """T1 -> T2, F2 -> F3; anything else is left for the person to say."""
    m = re.fullmatch(r'([A-Za-z]+)(\d+)', (generation or '').strip())
    return f'{m.group(1)}{int(m.group(2)) + 1}' if m else ''


def kind_of(ident: str) -> Optional[str]:
    """What a code names: GL-L-0001 a line, GL-S-0001 a seed lot, GL-P-0001 a plant (S-0001 too)."""
    m = re.fullmatch(r'(?:[A-Z][A-Z0-9]{0,5}-)?([LSP])-\d+', (ident or '').strip().upper())
    return KIND_OF_PREFIX[m.group(1)] if m else None


def _row(conn, kind: str, ident: str):
    table = TABLE[kind]
    row = conn.execute(f'SELECT * FROM {table} WHERE (id = ? OR code = ?) AND deleted_at IS NULL',
                       (ident, (ident or '').upper())).fetchone()
    if row is None:
        raise NotFound(f'No such {"seed lot" if kind == "lot" else kind}')
    return row


def visible(conn, person: Person, kind: str, ident: str):
    row = _row(conn, kind, ident)
    if not can_see(person, row):
        # As if it were not there: another lab's stocks are not even named.
        raise NotFound(f'No such {"seed lot" if kind == "lot" else kind}')
    return row


def changeable(conn, person: Person, kind: str, ident: str):
    """A record this person may change: their own lab's."""
    row = visible(conn, person, kind, ident)
    if not can_change(person, row):
        raise Forbidden(f"This {'seed lot' if kind == 'lot' else kind} is {row['lab']}'s: only its own lab changes it")
    return row


def _brief(conn, kind: str, record_id: Optional[str]) -> Optional[dict]:
    if not record_id:
        return None
    row = conn.execute(f'SELECT * FROM {TABLE[kind]} WHERE id = ?', (record_id,)).fetchone()
    if row is None:
        return None
    out = {'kind': kind, 'id': row['id'], 'code': row['code'], 'deleted': bool(row['deleted_at'])}
    if kind == 'line':
        out.update(name=row['name'], species=row['species'], line_kind=row['kind'])
    elif kind == 'lot':
        line = conn.execute('SELECT name FROM lines WHERE id = ?', (row['line_id'],)).fetchone()
        out.update(generation=row['generation'], line=line['name'] if line else '', location=row['location'])
    else:
        line = conn.execute('SELECT name FROM lines WHERE id = ?', (row['line_id'],)).fetchone()
        lot = conn.execute('SELECT code, generation FROM lots WHERE id = ?', (row['lot_id'],)).fetchone()
        out.update(number=row['number'], line=line['name'] if line else '', status=row['status'],
                   generation=lot['generation'] if lot else '', lot=lot['code'] if lot else '')
    return out


def _changed(row, fields: Dict[str, Any]) -> List[str]:
    return [f'{k}: {row[k]!r} → {v!r}' for k, v in fields.items() if row[k] != v]


# --- lines -----------------------------------------------------------------------

def _line_fields(data: dict, partial: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if 'name' in data or not partial:
        name = _text(data.get('name'), 200)
        if not name:
            raise ValueError('A line needs a name')
        out['name'] = name
    for key, limit in (('species', 120), ('background', 200), ('description', 5000)):
        if key in data or not partial:
            out[key] = _text(data.get(key), limit)
    if 'kind' in data or not partial:
        kind = _text(data.get('kind')) or 'other'
        if kind not in LINE_KINDS:
            raise ValueError(f'kind must be one of {", ".join(LINE_KINDS)}')
        out['kind'] = kind
    for key, limit in LINE_TEXT:
        if key in data or not partial:
            out[key] = _text(data.get(key), limit)
    if out.get('stock_center_url') and not re.match(r'https?://', out['stock_center_url']):
        raise ValueError('The stock center link is a web address, starting with https://')
    for key, allowed, what in (('biosafety', BIOSAFETY, 'biosafety level'), ('gmo_type', GMO_TYPES, 'GMO type'),
                               ('gene_expression', GENE_EXPRESSION, 'gene expression')):
        if key in data or not partial:
            v = _text(data.get(key))
            if v not in allowed:
                raise ValueError(f'{what} must be one of {", ".join(a for a in allowed if a)}, or empty')
            out[key] = v
    return out


def create_line(person: Person, data: dict) -> str:
    fields = _line_fields(data)
    with connect() as conn:
        line_id = _new_id()
        lab = lab_of(person, data.get('lab'), strict=True)
        code = _code(conn, 'line', lab)
        cols = ['id', 'code', 'lab', 'created_by', *fields]
        conn.execute(f'INSERT INTO lines ({", ".join(cols)}) VALUES ({", ".join("?" * len(cols))})',
                     (line_id, code, lab, person.username, *fields.values()))
        for parent in data.get('parents') or []:
            _add_parent(conn, person, line_id, parent.get('id'), parent.get('role') or 'parent')
        for plasmid in data.get('plasmids') or []:
            _add_plasmid(conn, line_id, plasmid)
        _log(conn, 'line', line_id, person.username, f'created {code}')
        return line_id


def _add_parent(conn, person: Person, line_id: str, parent_ident: str, role: str) -> None:
    if role not in PARENT_ROLES:
        raise ValueError(f'role must be one of {", ".join(PARENT_ROLES)}')
    parent = visible(conn, person, 'line', parent_ident or '')
    if parent['id'] == line_id:
        raise ValueError('A line cannot be its own parent')
    conn.execute('INSERT OR IGNORE INTO line_parents (line_id, parent_id, role) VALUES (?, ?, ?)',
                 (line_id, parent['id'], role))


def _add_plasmid(conn, line_id: str, plasmid: dict) -> None:
    pid, name = _text(plasmid.get('id'), 80), _text(plasmid.get('name'), 200)
    if not pid:
        raise ValueError('Choose a plasmid')
    conn.execute('INSERT OR REPLACE INTO line_plasmids (line_id, plasmid_id, name) VALUES (?, ?, ?)',
                 (line_id, pid, name or pid))


def update_line(person: Person, ident: str, data: dict) -> None:
    fields = _line_fields(data, partial=True)
    with connect() as conn:
        row = changeable(conn, person, 'line', ident)
        changes = _changed(row, fields)
        if fields:
            conn.execute(f'UPDATE lines SET {", ".join(f"{k} = ?" for k in fields)}, updated_at = CURRENT_TIMESTAMP '
                         'WHERE id = ?', (*fields.values(), row['id']))
        if changes:
            _log(conn, 'line', row['id'], person.username, '; '.join(changes))


def set_plasmids(person: Person, ident: str, plasmids: List[dict]) -> None:
    with connect() as conn:
        row = changeable(conn, person, 'line', ident)
        before = sorted(r['name'] for r in conn.execute('SELECT name FROM line_plasmids WHERE line_id = ?', (row['id'],)))
        conn.execute('DELETE FROM line_plasmids WHERE line_id = ?', (row['id'],))
        for p in plasmids or []:
            _add_plasmid(conn, row['id'], p)
        after = sorted(r['name'] for r in conn.execute('SELECT name FROM line_plasmids WHERE line_id = ?', (row['id'],)))
        if before != after:
            _log(conn, 'line', row['id'], person.username, f'plasmids: {", ".join(before) or "none"} → {", ".join(after) or "none"}')


def set_parents(person: Person, ident: str, parents: List[dict]) -> None:
    with connect() as conn:
        row = changeable(conn, person, 'line', ident)
        conn.execute('DELETE FROM line_parents WHERE line_id = ?', (row['id'],))
        for p in parents or []:
            _add_parent(conn, person, row['id'], p.get('id'), p.get('role') or 'parent')
        # No line may end up among its own ancestors.
        if row['id'] in _ancestor_lines(conn, row['id']):
            raise ValueError('That would make the line its own ancestor')
        _log(conn, 'line', row['id'], person.username, 'parents changed')


def _ancestor_lines(conn, line_id: str, limit: int = 200) -> List[str]:
    found, todo = [], [line_id]
    while todo and len(found) < limit:
        current = todo.pop()
        for r in conn.execute('SELECT parent_id FROM line_parents WHERE line_id = ?', (current,)):
            if r['parent_id'] not in found:
                found.append(r['parent_id'])
                todo.append(r['parent_id'])
    return found


# --- seed lots ---------------------------------------------------------------------

def _lot_fields(data: dict, partial: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, limit in (('generation', 20), ('source', 300), ('amount', 100), ('location', 200), ('notes', 5000)):
        if key in data or not partial:
            out[key] = _text(data.get(key), limit)
    if 'harvested_on' in data or not partial:
        out['harvested_on'] = _date(data.get('harvested_on'))
    if 'germination' in data or not partial:
        g = data.get('germination')
        if g in (None, ''):
            out['germination'] = None
        else:
            try:
                g = float(g)
            except (TypeError, ValueError):
                raise ValueError('Germination is a percentage')
            if not 0 <= g <= 100:
                raise ValueError('Germination is a percentage, 0 to 100')
            out['germination'] = g
    if 'zygosity' in data or not partial:
        z = _text(data.get('zygosity'))
        if z not in ZYGOSITY:
            raise ValueError(f'zygosity must be one of {", ".join(z for z in ZYGOSITY if z)}')
        out['zygosity'] = z
    if 'used_up' in data:
        out['used_up'] = 1 if data.get('used_up') else 0
    return out


def create_lot(person: Person, data: dict, *, from_plant: Optional[str] = None,
               father_plant: Optional[str] = None, line_id: Optional[str] = None) -> str:
    fields = _lot_fields(data)
    with connect() as conn:
        if line_id is None:
            line_id = changeable(conn, person, 'line', _text(data.get('line')))['id']
        # A lot belongs to its line's lab, whoever harvests it.
        lab = conn.execute('SELECT lab FROM lines WHERE id = ?', (line_id,)).fetchone()['lab']
        lot_id = _new_id()
        code = _code(conn, 'lot', lab)
        conn.execute('INSERT INTO lots (id, code, lab, line_id, generation, from_plant_id, father_plant_id, source, '
                     'harvested_on, amount, location, germination, zygosity, notes, created_by) '
                     'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     (lot_id, code, lab, line_id, fields['generation'], from_plant, father_plant,
                      fields['source'], fields['harvested_on'], fields['amount'], fields['location'],
                      fields['germination'], fields['zygosity'], fields['notes'], person.username))
        _log(conn, 'lot', lot_id, person.username, f'created {code}')
        return lot_id


def update_lot(person: Person, ident: str, data: dict) -> None:
    fields = _lot_fields(data, partial=True)
    with connect() as conn:
        row = changeable(conn, person, 'lot', ident)
        changes = _changed(row, fields)
        # Seeds put in the wrong line can be moved, until plants grow from them
        # (those plants would then be of the wrong line too).
        into = _text(data.get('line'))
        if into:
            target = changeable(conn, person, 'line', into)
            if target['id'] != row['line_id']:
                if conn.execute('SELECT 1 FROM plants WHERE lot_id = ? AND deleted_at IS NULL', (row['id'],)).fetchone():
                    raise ValueError('Plants were sown from this lot: its line can no longer be changed')
                old = conn.execute('SELECT code FROM lines WHERE id = ?', (row['line_id'],)).fetchone()
                fields['line_id'] = target['id']
                changes.append(f"line: {old['code'] if old else '?'} → {target['code']}")
        if fields:
            conn.execute(f'UPDATE lots SET {", ".join(f"{k} = ?" for k in fields)}, updated_at = CURRENT_TIMESTAMP '
                         'WHERE id = ?', (*fields.values(), row['id']))
        if changes:
            _log(conn, 'lot', row['id'], person.username, '; '.join(changes))


def sow(person: Person, lot_ident: str, data: dict) -> List[str]:
    """Plants from a seed lot, numbered on from those sown before."""
    try:
        count = int(data.get('count'))
    except (TypeError, ValueError):
        raise ValueError('How many plants?')
    if not 1 <= count <= MAX_PLANTS_PER_SOWING:
        raise ValueError(f'Sow 1 to {MAX_PLANTS_PER_SOWING} plants at a time')
    sown_on, location = _date(data.get('sown_on')), _text(data.get('location'), 200)
    treatment = _text(data.get('treatment'), 200)
    with connect() as conn:
        lot = changeable(conn, person, 'lot', lot_ident)
        place = place_for(conn, lot['lab'], data.get('place'))
        start = conn.execute('SELECT COALESCE(MAX(number), 0) FROM plants WHERE lot_id = ?', (lot['id'],)).fetchone()[0]
        made = []
        for i in range(1, count + 1):
            plant_id = _new_id()
            conn.execute('INSERT INTO plants (id, code, lab, lot_id, line_id, number, sown_on, location, place_id, '
                         'treatment, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         (plant_id, _code(conn, 'plant', lot['lab']), lot['lab'], lot['id'], lot['line_id'], start + i,
                          sown_on, location, place['id'] if place else None, treatment, person.username))
            made.append(plant_id)
        _log(conn, 'lot', lot['id'], person.username, f'sowed {count} plant{"s" if count > 1 else ""}'
             f' (#{start + 1}–#{start + count})' + (f' in {place["name"]}' if place else '')
             + (f', {treatment}' if treatment else ''))
        return made


def place_for(conn, lab: str, ident: Any) -> Optional[Any]:
    """The place a plant of this lab is to grow in (none for an empty choice): one of its own lab's."""
    ident = _text(ident, 40)
    if not ident:
        return None
    row = conn.execute('SELECT * FROM places WHERE id = ? AND deleted_at IS NULL', (ident,)).fetchone()
    if row is None or (row['lab'] or '').casefold() != (lab or '').casefold():
        raise ValueError("No such place in this lab's list")
    return row


# --- plants -------------------------------------------------------------------------

def update_plant(person: Person, ident: str, data: dict) -> None:
    fields: Dict[str, Any] = {}
    for key, limit in (('location', 200), ('treatment', 200), ('notes', 5000)):
        if key in data:
            fields[key] = _text(data.get(key), limit)
    if 'sown_on' in data:
        fields['sown_on'] = _date(data.get('sown_on'))
    if 'zygosity' in data:
        z = _text(data.get('zygosity'))
        if z not in ZYGOSITY:
            raise ValueError('Unknown zygosity')
        fields['zygosity'] = z
    if 'status' in data:
        s = _text(data.get('status'))
        if s not in PLANT_STATUS:
            raise ValueError(f'status must be one of {", ".join(PLANT_STATUS)}')
        fields['status'] = s
    if 'selected' in data:
        fields['selected'] = 1 if data.get('selected') else 0
    with connect() as conn:
        row = changeable(conn, person, 'plant', ident)
        changes = _changed(row, fields)
        if 'place' in data:
            place = place_for(conn, row['lab'], data.get('place'))
            if (place['id'] if place else None) != row['place_id']:
                fields['place_id'] = place['id'] if place else None
                changes.append(f"place: {place['name'] if place else 'none'}")
        if fields:
            conn.execute(f'UPDATE plants SET {", ".join(f"{k} = ?" for k in fields)}, updated_at = CURRENT_TIMESTAMP '
                         'WHERE id = ?', (*fields.values(), row['id']))
        if changes:
            _log(conn, 'plant', row['id'], person.username, '; '.join(changes))


def harvest(person: Person, plant_ident: str, data: dict) -> str:
    """
    A new seed lot from one plant: of its line, the next generation. Seeds from
    a plant that was transformed (dipped) belong to the transgenic line instead:
    `line` names it, and the lot is its T1 unless a generation is given.
    """
    with connect() as conn:
        plant = changeable(conn, person, 'plant', plant_ident)
        lot = conn.execute('SELECT generation FROM lots WHERE id = ?', (plant['lot_id'],)).fetchone()
        line_id = plant['line_id']
        into = _text(data.get('line'))
        if into:
            target = changeable(conn, person, 'line', into)
            line_id = target['id']
    data = dict(data)
    if line_id != plant['line_id']:
        data['generation'] = data.get('generation') or 'T1'
    else:
        data['generation'] = data.get('generation') or next_generation(lot['generation'] if lot else '')
    lot_id = create_lot(person, data, from_plant=plant['id'], line_id=line_id)
    with connect() as conn:
        conn.execute("UPDATE plants SET status = 'harvested', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                     (plant['id'],))
        code = conn.execute('SELECT code FROM lots WHERE id = ?', (lot_id,)).fetchone()['code']
        _log(conn, 'plant', plant['id'], person.username, f'harvested into {code}')
    return lot_id


def cross(person: Person, mother_ident: str, father_ident: str, data: dict) -> Dict[str, str]:
    """
    Seeds from crossing two plants: a new line (a cross, its parents the two
    plants' lines, carrying both lines' plasmids) and its F1 seed lot.
    """
    with connect() as conn:
        mother = changeable(conn, person, 'plant', mother_ident)
        father = visible(conn, person, 'plant', father_ident)
        if mother['id'] == father['id']:
            raise ValueError('Choose two different plants (harvest a plant to self it)')
        m_line = conn.execute('SELECT * FROM lines WHERE id = ?', (mother['line_id'],)).fetchone()
        f_line = conn.execute('SELECT * FROM lines WHERE id = ?', (father['line_id'],)).fetchone()
        plasmids = {r['plasmid_id']: r['name'] for r in conn.execute(
            'SELECT plasmid_id, name FROM line_plasmids WHERE line_id IN (?, ?)', (m_line['id'], f_line['id']))}
    name = _text(data.get('name'), 200) or f"{m_line['name']} × {f_line['name']}"
    line_id = create_line(person, {
        'name': name, 'species': m_line['species'], 'kind': 'cross',
        'background': f"{m_line['background'] or m_line['name']} × {f_line['background'] or f_line['name']}",
        'description': _text(data.get('description'), 5000),
        'parents': [{'id': m_line['id'], 'role': 'mother'}, {'id': f_line['id'], 'role': 'father'}],
        'plasmids': [{'id': k, 'name': v} for k, v in plasmids.items()],
    })
    lot_data = dict(data)
    lot_data.setdefault('generation', 'F1')
    lot_id = create_lot(person, lot_data, from_plant=mother['id'], father_plant=father['id'], line_id=line_id)
    with connect() as conn:
        code = conn.execute('SELECT code FROM lots WHERE id = ?', (lot_id,)).fetchone()['code']
        for plant, role in ((mother, 'mother'), (father, 'father')):
            _log(conn, 'plant', plant['id'], person.username, f'crossed as {role} into {code}')
    return {'line': line_id, 'lot': lot_id}


def found_line(person: Person, plant_ident: str, data: dict) -> str:
    """
    Make a plant the founder of a line of its own, as a T1 transformant is an
    independent insertion event. Its seeds, harvested later, belong to the new line.
    """
    with connect() as conn:
        plant = changeable(conn, person, 'plant', plant_ident)
        old = conn.execute('SELECT * FROM lines WHERE id = ?', (plant['line_id'],)).fetchone()
        plasmids = [{'id': r['plasmid_id'], 'name': r['name']} for r in conn.execute(
            'SELECT plasmid_id, name FROM line_plasmids WHERE line_id = ?', (old['id'],))]
    name = _text(data.get('name'), 200) or f"{old['name']}-{plant['number']}"
    line_id = create_line(person, {
        'name': name, 'species': old['species'], 'background': old['background'],
        'kind': _text(data.get('kind')) or ('transgenic' if old['kind'] in ('transgenic', 'population') else old['kind']),
        'description': _text(data.get('description'), 5000) or f"Founded from plant {plant['code']} of {old['name']}.",
        'parents': [{'id': old['id'], 'role': 'founded from'}], 'plasmids': plasmids,
    })
    with connect() as conn:
        conn.execute('UPDATE plants SET line_id = ?, selected = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                     (line_id, plant['id']))
        code = conn.execute('SELECT code FROM lines WHERE id = ?', (line_id,)).fetchone()['code']
        _log(conn, 'plant', plant['id'], person.username, f'founded line {code}')
    return line_id


# --- observations and segregation tests --------------------------------------------

_MEASURED = re.compile(r'^([-+]?\d+(?:[.,]\d+)?)\s*([^\d\s][^\s]{0,11})?$')


def measured(value: str, unit: str = '') -> tuple:
    """
    A value's number and unit when it is a measurement: "12.5" -> (12.5, unit),
    "12,5 cm" -> (12.5, 'cm'); anything else (a colour, "early") -> (None, unit).
    """
    m = _MEASURED.match(value.strip())
    if not m:
        return None, unit
    return float(m.group(1).replace(',', '.')), unit or (m.group(2) or '')


def insert_observation(conn, person: Person, kind: str, record_id: str, data: dict) -> str:
    trait = _text(data.get('trait'), 200)
    if not trait:
        raise ValueError('What was observed? (the trait, e.g. "flowering", "leaf colour")')
    value = _text(data.get('value'), 500)
    number, unit = measured(value, _text(data.get('unit'), 20))
    obs_id = _new_id()
    conn.execute('INSERT INTO observations (id, record_kind, record_id, observed_on, trait, value, number, unit, notes, '
                 'created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (obs_id, kind, record_id, _date(data.get('observed_on')), trait, value, number, unit,
                  _text(data.get('notes'), 5000), person.username))
    shown = f'{value[:80]} {unit}' if unit and number is not None and not value.endswith(unit) else value[:80]
    _log(conn, kind, record_id, person.username, f'observed {trait}: {shown}')
    return obs_id


def add_observation(person: Person, kind: str, ident: str, data: dict) -> str:
    with connect() as conn:
        row = changeable(conn, person, kind, ident)
        return insert_observation(conn, person, kind, row['id'], data)


def _observation_record(conn, person: Person, obs_id: str):
    obs = conn.execute('SELECT * FROM observations WHERE id = ? AND deleted_at IS NULL', (obs_id,)).fetchone()
    if obs is None:
        raise NotFound('No such observation')
    changeable(conn, person, obs['record_kind'], obs['record_id'])
    return obs


def remove_observation(person: Person, obs_id: str) -> None:
    with connect() as conn:
        obs = _observation_record(conn, person, obs_id)
        conn.execute('UPDATE observations SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?', (obs_id,))
        _log(conn, obs['record_kind'], obs['record_id'], person.username, f'removed observation {obs["trait"]}')


def add_seg_test(person: Person, lot_ident: str, data: dict) -> str:
    try:
        resistant, sensitive = int(data.get('resistant')), int(data.get('sensitive'))
    except (TypeError, ValueError):
        raise ValueError('Count the resistant and sensitive seedlings')
    if resistant < 0 or sensitive < 0 or resistant + sensitive == 0:
        raise ValueError('Count at least one seedling')
    expected = _text(data.get('expected')) or '3:1'
    if expected not in stats.RATIOS:
        raise ValueError(f'expected must be one of {", ".join(stats.RATIOS)}')
    with connect() as conn:
        lot = changeable(conn, person, 'lot', lot_ident)
        test_id = _new_id()
        conn.execute('INSERT INTO seg_tests (id, lot_id, tested_on, selection, resistant, sensitive, expected, notes, '
                     'created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     (test_id, lot['id'], _date(data.get('tested_on')), _text(data.get('selection'), 120),
                      resistant, sensitive, expected, _text(data.get('notes'), 5000), person.username))
        verdict = stats.assess(resistant, sensitive, expected)['verdict']
        _log(conn, 'lot', lot['id'], person.username, f'segregation test {resistant}:{sensitive} – {verdict}')
        return test_id


def remove_seg_test(person: Person, test_id: str) -> None:
    with connect() as conn:
        t = conn.execute('SELECT * FROM seg_tests WHERE id = ? AND deleted_at IS NULL', (test_id,)).fetchone()
        if t is None:
            raise NotFound('No such test')
        changeable(conn, person, 'lot', t['lot_id'])
        conn.execute('UPDATE seg_tests SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?', (test_id,))
        _log(conn, 'lot', t['lot_id'], person.username, 'removed a segregation test')


# --- deleting ------------------------------------------------------------------------

def delete(person: Person, kind: str, ident: str) -> None:
    """Remove a record that nothing else depends on (kept, out of sight)."""
    with connect() as conn:
        row = changeable(conn, person, kind, ident)
        if kind == 'line':
            used = conn.execute('SELECT COUNT(*) FROM lots WHERE line_id = ? AND deleted_at IS NULL', (row['id'],)).fetchone()[0] \
                + conn.execute('SELECT COUNT(*) FROM plants WHERE line_id = ? AND deleted_at IS NULL', (row['id'],)).fetchone()[0]
            if used:
                raise ValueError('This line still has seed lots or plants: remove those first')
        elif kind == 'lot':
            if conn.execute('SELECT 1 FROM plants WHERE lot_id = ? AND deleted_at IS NULL', (row['id'],)).fetchone():
                raise ValueError('Plants were sown from this lot: remove them first, or mark the lot used up')
        else:
            if conn.execute('SELECT 1 FROM lots WHERE (from_plant_id = ? OR father_plant_id = ?) AND deleted_at IS NULL',
                            (row['id'], row['id'])).fetchone():
                raise ValueError('Seeds were harvested from this plant: it stays as their parent')
        conn.execute(f'UPDATE {TABLE[kind]} SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?', (row['id'],))
        _log(conn, kind, row['id'], person.username, f'deleted {row["code"]}')


# --- reading --------------------------------------------------------------------------

def _list(conn, person: Person, sql: str, args: list, kind: str, limit: int) -> List[dict]:
    out = []
    for r in conn.execute(sql, args):
        if can_see(person, r):
            out.append(_brief(conn, kind, r['id']))
            if len(out) >= limit:
                break
    return out


def list_lines(person: Person, q: str = '', limit: int = 300) -> List[dict]:
    like = f'%{q.strip()}%'
    with connect() as conn:
        rows = conn.execute(
            'SELECT l.*, (SELECT COUNT(*) FROM lots WHERE line_id = l.id AND deleted_at IS NULL) AS lot_count, '
            '(SELECT COUNT(*) FROM plants WHERE line_id = l.id AND deleted_at IS NULL) AS plant_count, '
            "(SELECT GROUP_CONCAT(name, ', ') FROM line_plasmids WHERE line_id = l.id) AS plasmids "
            'FROM lines l WHERE l.deleted_at IS NULL AND (l.code LIKE ? OR l.name LIKE ? OR l.species LIKE ? '
            'OR l.background LIKE ? OR l.description LIKE ? OR l.id IN (SELECT line_id FROM line_plasmids WHERE name LIKE ?)) '
            'ORDER BY l.created_at DESC', (like, like, like, like, like, like)).fetchall()
        return [{'id': r['id'], 'code': r['code'], 'name': r['name'], 'species': r['species'],
                 'background': r['background'], 'line_kind': r['kind'], 'lots': r['lot_count'],
                 'plants': r['plant_count'], 'plasmids': r['plasmids'] or '', 'lab': r['lab'],
                 'created_by': r['created_by'], 'created_at': r['created_at']}
                for r in rows if can_see(person, r)][:limit]


def list_lots(person: Person, q: str = '', limit: int = 500) -> List[dict]:
    like = f'%{q.strip()}%'
    with connect() as conn:
        rows = conn.execute(
            'SELECT s.*, l.name AS line_name, l.code AS line_code, p.code AS plant_code, '
            '(SELECT COUNT(*) FROM plants WHERE lot_id = s.id AND deleted_at IS NULL) AS sown '
            'FROM lots s JOIN lines l ON l.id = s.line_id LEFT JOIN plants p ON p.id = s.from_plant_id '
            'WHERE s.deleted_at IS NULL AND (s.code LIKE ? OR l.name LIKE ? OR l.code LIKE ? OR s.location LIKE ? '
            'OR s.generation LIKE ? OR s.source LIKE ? OR s.notes LIKE ?) ORDER BY s.created_at DESC',
            (like,) * 7).fetchall()
        return [{'id': r['id'], 'code': r['code'], 'line': r['line_name'], 'line_code': r['line_code'],
                 'generation': r['generation'], 'location': r['location'], 'amount': r['amount'],
                 'zygosity': r['zygosity'], 'germination': r['germination'], 'used_up': bool(r['used_up']),
                 'from_plant': r['plant_code'], 'source': r['source'], 'harvested_on': r['harvested_on'],
                 'sown': r['sown'], 'lab': r['lab']}
                for r in rows if can_see(person, r)][:limit]


def list_plants(person: Person, q: str = '', limit: int = 500) -> List[dict]:
    like = f'%{q.strip()}%'
    with connect() as conn:
        rows = conn.execute(
            'SELECT p.*, l.name AS line_name, l.code AS line_code, s.code AS lot_code, s.generation, pl.name AS place '
            'FROM plants p JOIN lines l ON l.id = p.line_id JOIN lots s ON s.id = p.lot_id '
            'LEFT JOIN places pl ON pl.id = p.place_id '
            'WHERE p.deleted_at IS NULL AND (p.code LIKE ? OR l.name LIKE ? OR s.code LIKE ? OR p.location LIKE ? '
            'OR p.status LIKE ? OR p.notes LIKE ? OR p.treatment LIKE ? OR pl.name LIKE ?) '
            'ORDER BY p.created_at DESC, p.number', (like,) * 8).fetchall()
        return [{'id': r['id'], 'code': r['code'], 'number': r['number'], 'line': r['line_name'],
                 'line_code': r['line_code'], 'lot': r['lot_code'], 'generation': r['generation'],
                 'status': r['status'], 'zygosity': r['zygosity'], 'selected': bool(r['selected']),
                 'location': r['location'], 'place': r['place'] or '', 'treatment': r['treatment'],
                 'sown_on': r['sown_on'], 'lab': r['lab']}
                for r in rows if can_see(person, r)][:limit]


def search(person: Person, q: str, limit: int = 20) -> List[dict]:
    """Lines, lots and plants by code or name, for linking from elsewhere (the notebook)."""
    q = (q or '').strip()
    found = [dict(x, kind='line', label=f"{x['code']} {x['name']}") for x in list_lines(person, q, limit)]
    found += [dict(x, kind='lot', label=f"{x['code']} {x['line']} {x['generation']}".strip()) for x in list_lots(person, q, limit)]
    found += [dict(x, kind='plant', label=f"{x['code']} {x['line']} #{x['number']}") for x in list_plants(person, q, limit)]
    exact = [f for f in found if f['code'].upper() == q.upper()]
    return (exact + [f for f in found if f not in exact])[:limit]


def _extras(conn, kind: str, record_id: str) -> Dict[str, Any]:
    from app import attachments
    obs = [dict(r) for r in conn.execute(
        'SELECT id, observed_on, trait, value, number, unit, notes, created_by, created_at FROM observations '
        'WHERE record_kind = ? AND record_id = ? AND deleted_at IS NULL ORDER BY COALESCE(observed_on, created_at) DESC',
        (kind, record_id))]
    for o in obs:
        o['attachments'] = attachments.listed(conn, 'observation', o['id'])
    return {
        'observations': obs,
        'attachments': attachments.listed(conn, kind, record_id),
        'changes': [dict(r) for r in conn.execute(
            'SELECT changed_by, changed_at, what FROM changes WHERE record_kind = ? AND record_id = ? '
            'ORDER BY rowid DESC LIMIT 200', (kind, record_id))],
    }


def line_detail(person: Person, ident: str) -> dict:
    with connect() as conn:
        row = visible(conn, person, 'line', ident)
        parents = [dict(_brief(conn, 'line', r['parent_id']), role=r['role']) for r in conn.execute(
            'SELECT parent_id, role FROM line_parents WHERE line_id = ?', (row['id'],))]
        children = [dict(_brief(conn, 'line', r['line_id']), role=r['role']) for r in conn.execute(
            'SELECT lp.line_id, lp.role FROM line_parents lp JOIN lines l ON l.id = lp.line_id '
            'WHERE lp.parent_id = ? AND l.deleted_at IS NULL', (row['id'],))]
        lots = [_brief(conn, 'lot', r['id']) for r in conn.execute(
            'SELECT id FROM lots WHERE line_id = ? AND deleted_at IS NULL ORDER BY created_at', (row['id'],))]
        out = {**dict(row), 'line_kind': row['kind'], 'kind': 'line',
               'parents': [p for p in parents if p], 'children': [c for c in children if c],
               'plasmids': [dict(r) for r in conn.execute(
                   'SELECT plasmid_id AS id, name FROM line_plasmids WHERE line_id = ? ORDER BY name', (row['id'],))],
               'lots': lots, 'pedigree': _pedigree(conn, row['id']), **_extras(conn, 'line', row['id'])}
        out.pop('data', None)
        return out


def _pedigree(conn, line_id: str, depth: int = 0) -> dict:
    """A line and its parent lines, and theirs, as a tree."""
    line = _brief(conn, 'line', line_id)
    if depth >= 8 or line is None:
        return line or {}
    line['parents'] = [dict(_pedigree(conn, r['parent_id'], depth + 1), role=r['role']) for r in conn.execute(
        'SELECT parent_id, role FROM line_parents WHERE line_id = ?', (line_id,))]
    return line


def lot_detail(person: Person, ident: str) -> dict:
    with connect() as conn:
        row = visible(conn, person, 'lot', ident)
        tests = []
        for t in conn.execute('SELECT * FROM seg_tests WHERE lot_id = ? AND deleted_at IS NULL '
                              'ORDER BY COALESCE(tested_on, created_at) DESC', (row['id'],)):
            tests.append({**dict(t), **stats.assess(t['resistant'], t['sensitive'], t['expected'])})
        plants = [dict(_brief(conn, 'plant', r['id']), zygosity=r['zygosity'], selected=bool(r['selected']),
                       location=r['location'], treatment=r['treatment'], sown_on=r['sown_on'], place=r['place'] or '',
                       harvested=[_brief(conn, 'lot', h['id']) for h in conn.execute(
                           'SELECT id FROM lots WHERE from_plant_id = ? AND deleted_at IS NULL', (r['id'],))])
                  for r in conn.execute('SELECT p.*, pl.name AS place FROM plants p LEFT JOIN places pl ON pl.id = p.place_id '
                                        'WHERE p.lot_id = ? AND p.deleted_at IS NULL ORDER BY p.number', (row['id'],))]
        return {**dict(row), 'kind': 'lot', 'line': _brief(conn, 'line', row['line_id']),
                'from_plant': _brief(conn, 'plant', row['from_plant_id']),
                'father_plant': _brief(conn, 'plant', row['father_plant_id']),
                'used_up': bool(row['used_up']), 'plants': plants, 'seg_tests': tests,
                'next_generation': next_generation(row['generation']),
                'ancestry': _ancestry(conn, 'lot', row['id']), 'descendants': _descendants(conn, 'lot', row['id']),
                **_extras(conn, 'lot', row['id'])}


def plant_detail(person: Person, ident: str) -> dict:
    with connect() as conn:
        row = visible(conn, person, 'plant', ident)
        lot = _brief(conn, 'lot', row['lot_id'])
        harvested = [_brief(conn, 'lot', r['id']) for r in conn.execute(
            'SELECT id FROM lots WHERE (from_plant_id = ? OR father_plant_id = ?) AND deleted_at IS NULL',
            (row['id'], row['id']))]
        siblings = [_brief(conn, 'plant', r['id']) for r in conn.execute(
            'SELECT id FROM plants WHERE lot_id = ? AND id != ? AND deleted_at IS NULL ORDER BY number',
            (row['lot_id'], row['id']))]
        place = conn.execute('SELECT id, name, kind, conditions FROM places WHERE id = ?', (row['place_id'],)).fetchone() \
            if row['place_id'] else None
        return {**dict(row), 'kind': 'plant', 'selected': bool(row['selected']), 'place': dict(place) if place else None,
                'line': _brief(conn, 'line', row['line_id']), 'lot': lot, 'harvested': harvested,
                'siblings': siblings, 'next_generation': next_generation(lot['generation'] if lot else ''),
                'ancestry': _ancestry(conn, 'plant', row['id']), 'descendants': _descendants(conn, 'plant', row['id']),
                **_extras(conn, 'plant', row['id'])}


def _ancestry(conn, kind: str, record_id: str, limit: int = 40) -> List[dict]:
    """
    From a lot or plant back through the plants and lots it came from, nearest
    first: plant -> the lot it was sown from -> the plant that lot was harvested
    from -> ... A cross's lot lists its father, then follows its mother.
    """
    chain, seen = [], set()
    while record_id and len(chain) < limit and (kind, record_id) not in seen:
        seen.add((kind, record_id))
        if kind == 'plant':
            row = conn.execute('SELECT lot_id FROM plants WHERE id = ?', (record_id,)).fetchone()
            if not row:
                break
            kind, record_id = 'lot', row['lot_id']
            chain.append(_brief(conn, 'lot', record_id))
        else:
            row = conn.execute('SELECT from_plant_id, father_plant_id FROM lots WHERE id = ?', (record_id,)).fetchone()
            if not row or not row['from_plant_id']:
                break                      # from outside: a stock centre, a colleague
            if row['father_plant_id']:
                chain.append(dict(_brief(conn, 'plant', row['father_plant_id']), role='father'))
            kind, record_id = 'plant', row['from_plant_id']
            chain.append(dict(_brief(conn, 'plant', record_id), role='mother' if row['father_plant_id'] else 'parent'))
    return [c for c in chain if c]


def _descendants(conn, kind: str, record_id: str, depth: int = 0, budget: Optional[list] = None) -> List[dict]:
    """What came from a lot or plant: plants sown, lots harvested, and so on (a tree)."""
    budget = budget if budget is not None else [300]
    if depth > 12 or budget[0] <= 0:
        return []
    if kind == 'lot':
        rows = conn.execute('SELECT id FROM plants WHERE lot_id = ? AND deleted_at IS NULL ORDER BY number', (record_id,))
        child_kind = 'plant'
    else:
        rows = conn.execute('SELECT id FROM lots WHERE (from_plant_id = ? OR father_plant_id = ?) AND deleted_at IS NULL '
                            'ORDER BY created_at', (record_id, record_id))
        child_kind = 'lot'
    out = []
    for r in rows.fetchall():
        budget[0] -= 1
        if budget[0] < 0:
            break
        node = _brief(conn, child_kind, r['id'])
        node['children'] = _descendants(conn, child_kind, r['id'], depth + 1, budget)
        out.append(node)
    return out


def detail(person: Person, kind: str, ident: str) -> dict:
    return {'line': line_detail, 'lot': lot_detail, 'plant': plant_detail}[kind](person, ident)


def lines_with_plasmid(person: Person, plasmid_id: str) -> List[dict]:
    with connect() as conn:
        rows = conn.execute('SELECT l.* FROM line_plasmids lp JOIN lines l ON l.id = lp.line_id '
                            'WHERE lp.plasmid_id = ? AND l.deleted_at IS NULL', (plasmid_id,)).fetchall()
        return [_brief(conn, 'line', r['id']) for r in rows if can_see(person, r)]

