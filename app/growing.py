"""
What is growing, and where, and what was measured on it.

    places      a lab's growth chambers, greenhouses and rooms, with their
                conditions (16 h light, 22 °C): plants are sown into one, at a
                position there (shelf 2, tray B)
    growing     every plant still growing, with its place, sowing and treatment,
                for the Growing page; many at once can be moved, or marked
                harvested, discarded or dead
    scoring     one trait on many plants at once, as a sheet
    phenotypes  what was seen on a lot's (or a line's) plants, by trait and by
                treatment: for measurements their mean and spread, for the rest
                how often each value was seen; and every observation, for a CSV
"""

import csv
import io
import statistics
from typing import Any, Dict, List

from app.db import connect
from app.people import Person
from app.records import (Forbidden, NotFound, PLANT_STATUS, _log, _new_id, _text, can_change, can_see, changeable,
                         insert_observation, lab_of, place_for, visible)

PLACE_KINDS = ('growth chamber', 'greenhouse', 'growth room', 'field', 'bench', 'other')
MAX_AT_ONCE = 1000


# --- places ------------------------------------------------------------------------

def _place_fields(data: dict, partial: bool = False) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    if not partial or 'name' in data:
        name = _text(data.get('name'), 120)
        if not name:
            raise ValueError('What is the place called? (e.g. "Chamber 3", "Greenhouse B")')
        fields['name'] = name
    if not partial or 'kind' in data:
        kind = _text(data.get('kind')) or 'growth chamber'
        if kind not in PLACE_KINDS:
            raise ValueError(f'kind must be one of {", ".join(PLACE_KINDS)}')
        fields['kind'] = kind
    for key, limit in (('conditions', 500), ('notes', 2000)):
        if not partial or key in data:
            fields[key] = _text(data.get(key), limit)
    return fields


def _place(conn, person: Person, place_id: str):
    row = conn.execute('SELECT * FROM places WHERE id = ? AND deleted_at IS NULL', (place_id,)).fetchone()
    if row is None or not can_see(person, row):         # another lab's: as if there were none
        raise NotFound('No such place')
    if not can_change(person, row):
        raise Forbidden(f"{row['name']} is {row['lab']}'s: only its own lab changes it")
    return row


def list_places(person: Person) -> List[dict]:
    """The places of this person's labs, with how many plants grow in each."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT pl.*, (SELECT COUNT(*) FROM plants WHERE place_id = pl.id AND status = 'growing' "
            'AND deleted_at IS NULL) AS growing FROM places pl WHERE pl.deleted_at IS NULL ORDER BY pl.name').fetchall()
        return [{'id': r['id'], 'lab': r['lab'], 'name': r['name'], 'kind': r['kind'], 'conditions': r['conditions'],
                 'notes': r['notes'], 'growing': r['growing'], 'mine': can_change(person, r)}
                for r in rows if can_see(person, r)]


def create_place(person: Person, data: dict) -> str:
    fields = _place_fields(data)
    lab = lab_of(person, data.get('lab'), strict=True)
    with connect() as conn:
        if conn.execute('SELECT 1 FROM places WHERE lab = ? AND name = ? COLLATE NOCASE AND deleted_at IS NULL',
                        (lab, fields['name'])).fetchone():
            raise ValueError(f'{fields["name"]} is already on the list')
        place_id = _new_id()
        conn.execute('INSERT INTO places (id, lab, name, kind, conditions, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)',
                     (place_id, lab, fields['name'], fields['kind'], fields['conditions'], fields['notes'],
                      person.username))
        return place_id


def update_place(person: Person, place_id: str, data: dict) -> None:
    fields = _place_fields(data, partial=True)
    with connect() as conn:
        row = _place(conn, person, place_id)
        if fields.get('name') and conn.execute(
                'SELECT 1 FROM places WHERE lab = ? AND name = ? COLLATE NOCASE AND id != ? AND deleted_at IS NULL',
                (row['lab'], fields['name'], row['id'])).fetchone():
            raise ValueError(f'{fields["name"]} is already on the list')
        if fields:
            conn.execute(f'UPDATE places SET {", ".join(f"{k} = ?" for k in fields)} WHERE id = ?',
                         (*fields.values(), row['id']))


def remove_place(person: Person, place_id: str) -> None:
    """Off the list once nothing grows there; plants that grew there keep it, by name."""
    with connect() as conn:
        row = _place(conn, person, place_id)
        if conn.execute("SELECT 1 FROM plants WHERE place_id = ? AND status = 'growing' AND deleted_at IS NULL",
                        (row['id'],)).fetchone():
            raise ValueError(f'Plants are still growing in {row["name"]}: move them first')
        conn.execute('UPDATE places SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?', (row['id'],))


# --- what is growing -----------------------------------------------------------------

def growing(person: Person, limit: int = 5000) -> List[dict]:
    """Every plant still growing that this person sees, oldest sowing first."""
    with connect() as conn:
        rows = conn.execute(
            'SELECT p.id, p.code, p.lab, p.number, p.sown_on, p.location, p.treatment, p.place_id, p.selected, '
            'p.zygosity, s.code AS lot, s.generation, l.code AS line_code, l.name AS line '
            'FROM plants p JOIN lots s ON s.id = p.lot_id JOIN lines l ON l.id = p.line_id '
            "WHERE p.status = 'growing' AND p.deleted_at IS NULL "
            'ORDER BY COALESCE(p.sown_on, p.created_at), s.code, p.number').fetchall()
        return [{'code': r['code'], 'lab': r['lab'], 'number': r['number'], 'sown_on': r['sown_on'],
                 'location': r['location'], 'treatment': r['treatment'], 'place': r['place_id'],
                 'selected': bool(r['selected']), 'zygosity': r['zygosity'], 'lot': r['lot'],
                 'generation': r['generation'], 'line_code': r['line_code'], 'line': r['line'],
                 'mine': can_change(person, r)}
                for r in rows if can_see(person, r)][:limit]


def _plants(conn, person: Person, codes: Any) -> list:
    if not isinstance(codes, list) or not codes:
        raise ValueError('Which plants?')
    if len(codes) > MAX_AT_ONCE:
        raise ValueError(f'At most {MAX_AT_ONCE} plants at a time')
    return [changeable(conn, person, 'plant', _text(c, 40)) for c in dict.fromkeys(codes)]


def change_plants(person: Person, data: dict) -> int:
    """Move many plants (to a place and position), treat them, or mark them harvested, discarded or dead."""
    status = _text(data.get('status'))
    if status and status not in PLANT_STATUS:
        raise ValueError(f'status must be one of {", ".join(PLANT_STATUS)}')
    with connect() as conn:
        plants = _plants(conn, person, data.get('plants'))
        for plant in plants:
            fields: Dict[str, Any] = {}
            said = []
            if 'place' in data:
                place = place_for(conn, plant['lab'], data.get('place'))
                fields['place_id'] = place['id'] if place else None
                said.append(f"moved to {place['name'] if place else 'no place'}")
            if 'location' in data:
                fields['location'] = _text(data.get('location'), 200)
                said.append(f"position: {fields['location'] or '—'}")
            if 'treatment' in data:
                fields['treatment'] = _text(data.get('treatment'), 200)
                said.append(f"treatment: {fields['treatment'] or '—'}")
            if status:
                fields['status'] = status
                said.append(f'status: {plant["status"]} → {status}')
            if not fields:
                raise ValueError('Nothing to change')
            conn.execute(f'UPDATE plants SET {", ".join(f"{k} = ?" for k in fields)}, updated_at = CURRENT_TIMESTAMP '
                         'WHERE id = ?', (*fields.values(), plant['id']))
            _log(conn, 'plant', plant['id'], person.username, '; '.join(said))
        return len(plants)


# --- scoring --------------------------------------------------------------------------

def score(person: Person, data: dict) -> int:
    """One trait on many plants, on one day: each value an observation of its plant. Empty values are skipped."""
    trait = _text(data.get('trait'), 200)
    if not trait:
        raise ValueError('Which trait? (e.g. "height", "flowering time")')
    values = data.get('values')
    if not isinstance(values, list):
        raise ValueError('No values')
    entered = [v for v in values if isinstance(v, dict) and _text(v.get('value'), 500)]
    if not entered:
        raise ValueError('Enter a value for at least one plant')
    with connect() as conn:
        plants = _plants(conn, person, [v.get('plant') for v in entered])
        by_code = {p['code'].upper(): p for p in plants}
        for v in entered:
            plant = by_code.get(_text(v.get('plant'), 40).upper()) or changeable(conn, person, 'plant', _text(v.get('plant'), 40))
            insert_observation(conn, person, 'plant', plant['id'], {
                'trait': trait, 'value': v.get('value'), 'unit': data.get('unit'),
                'observed_on': data.get('observed_on'), 'notes': v.get('notes')})
        return len(entered)


# --- phenotypes -------------------------------------------------------------------------

def _observations(conn, kind: str, row) -> List[dict]:
    """What was seen on a lot or a line, and on the plants sown from it: newest first."""
    if kind == 'lot':
        plants = 'p.lot_id = ?'
    elif kind == 'line':
        plants = 'p.line_id = ?'
    else:
        plants = 'p.id = ?'
    rows = conn.execute(
        'SELECT o.*, p.code AS plant, p.number AS plant_number, p.treatment, s.code AS lot, s.generation, l.code AS line_code, '
        'l.name AS line FROM observations o JOIN plants p ON p.id = o.record_id '
        'JOIN lots s ON s.id = p.lot_id JOIN lines l ON l.id = p.line_id '
        f"WHERE o.record_kind = 'plant' AND o.deleted_at IS NULL AND p.deleted_at IS NULL AND {plants} "
        'ORDER BY COALESCE(o.observed_on, o.created_at) DESC, s.code, p.number', (row['id'],)).fetchall()
    out = [dict(r) for r in rows]
    if kind in ('lot', 'line'):
        own = conn.execute(f"SELECT * FROM observations WHERE record_kind = ? AND record_id = ? AND deleted_at IS NULL "
                           'ORDER BY COALESCE(observed_on, created_at) DESC', (kind, row['id'])).fetchall()
        out += [dict(r, plant='', plant_number=None, treatment='', lot=row['code'] if kind == 'lot' else '', generation='',
                     line_code='', line='') for r in own]
    return out


def _summary(observations: List[dict]) -> List[dict]:
    """By trait (and unit), by treatment: a measurement's n, mean, SD and range; otherwise each value's count."""
    traits: Dict[tuple, dict] = {}
    for o in observations:
        key = (o['trait'].strip().casefold(), (o['unit'] or '').strip())
        trait = traits.setdefault(key, {'trait': o['trait'].strip(), 'unit': key[1], 'groups': {}})
        trait['groups'].setdefault(o['treatment'] or '', []).append(o)
    out = []
    for trait in traits.values():
        groups = []
        for treatment, seen in sorted(trait['groups'].items()):
            numbers = [o['number'] for o in seen if o['number'] is not None]
            group: Dict[str, Any] = {'treatment': treatment, 'n': len(seen)}
            if numbers and len(numbers) * 2 >= len(seen):
                group.update(measured=len(numbers), mean=statistics.fmean(numbers),
                             sd=statistics.stdev(numbers) if len(numbers) > 1 else None,
                             min=min(numbers), max=max(numbers))
            else:
                counts: Dict[str, int] = {}
                for o in seen:
                    counts[o['value'] or '—'] = counts.get(o['value'] or '—', 0) + 1
                group['counts'] = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            groups.append(group)
        out.append({'trait': trait['trait'], 'unit': trait['unit'], 'groups': groups})
    return sorted(out, key=lambda t: t['trait'].casefold())


def phenotypes(person: Person, kind: str, ident: str) -> dict:
    with connect() as conn:
        row = visible(conn, person, kind, ident)
        observations = _observations(conn, kind, row)
    return {'summary': _summary(observations), 'count': len(observations)}


CSV_COLUMNS = ('line', 'line_name', 'lot', 'generation', 'plant', 'plant_number', 'treatment', 'observed_on', 'trait',
               'value', 'measured', 'unit', 'notes', 'observed_by')


def phenotypes_csv(person: Person, kind: str, ident: str) -> tuple:
    """Every observation on a lot's or a line's plants, one per row: (file name, CSV text)."""
    with connect() as conn:
        row = visible(conn, person, kind, ident)
        observations = _observations(conn, kind, row)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for o in sorted(observations, key=lambda o: (o['lot'], o['plant_number'] or 0, o['observed_on'] or '', o['trait'])):
        writer.writerow([o['line_code'], o['line'], o['lot'], o['generation'], o['plant'], o['plant_number'] or '',
                         o['treatment'], o['observed_on'] or '', o['trait'], o['value'],
                         '' if o['number'] is None else o['number'], o['unit'], o['notes'], o['created_by'] or ''])
    return f'{row["code"]}-phenotypes.csv', out.getvalue()
