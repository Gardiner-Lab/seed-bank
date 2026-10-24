"""Where plants grow, what was measured on them, and a record's family tree across the suite."""

import csv
import io
import sqlite3


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_json())
    return r.get_json()


def _line(client, name='Col-0', **extra):
    return _ok(client.post('/api/lines', json={'name': name, 'species': 'Arabidopsis thaliana', **extra}), 201)['record']


def _lot(client, line, **extra):
    return _ok(client.post('/api/lots', json={'line': line, **extra}), 201)['record']


def _place(client, name='Chamber 3', **extra):
    made = _ok(client.post('/api/places', json={'name': name, 'conditions': '16 h light, 22 °C', **extra}), 201)
    return next(p for p in made['places'] if p['id'] == made['id'])


def test_places_belong_to_a_lab_and_plants_are_sown_into_them(as_user):
    ana, ben, zoe = as_user('ana'), as_user('ben'), as_user('zoe')
    chamber = _place(ana)
    assert chamber['kind'] == 'growth chamber' and chamber['growing'] == 0
    assert ana.post('/api/places', json={'name': 'chamber 3'}).status_code == 400            # already on the list
    assert ana.post('/api/places', json={'name': 'Bench', 'kind': 'moon'}).status_code == 400
    assert [p['name'] for p in _ok(ben.get('/api/places'))['places']] == ['Chamber 3']          # the same lab
    assert _ok(zoe.get('/api/places'))['places'] == []                                          # not another lab
    zoes = _place(zoe, 'Greenhouse Z', kind='greenhouse')

    lot = _lot(ana, _line(ana)['code'])
    sown = _ok(ana.post(f"/api/lots/{lot['code']}/sow", json={
        'count': 3, 'sown_on': '2026-10-01', 'place': chamber['id'], 'location': 'shelf 2, tray B',
        'treatment': 'drought'}), 201)['record']
    assert {p['place'] for p in sown['plants']} == {'Chamber 3'} and {p['treatment'] for p in sown['plants']} == {'drought'}
    assert 'in Chamber 3, drought' in sown['changes'][0]['what']
    assert ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 1, 'place': zoes['id']}).status_code == 400

    plant = _ok(ana.get(f"/api/plant/{sown['plants'][0]['code']}"))['record']
    assert plant['place']['name'] == 'Chamber 3' and plant['location'] == 'shelf 2, tray B'
    assert _ok(ana.get('/api/plants?q=drought'))['plants'][0]['place'] == 'Chamber 3'

    grown = _ok(ana.get('/api/growing'))
    assert len(grown['plants']) == 3 and grown['places'][0]['growing'] == 3
    assert grown['plants'][0]['place'] == chamber['id'] and grown['plants'][0]['sown_on'] == '2026-10-01'
    assert _ok(zoe.get('/api/growing'))['plants'] == []

    # A place stays on the list while plants grow there.
    assert ana.delete(f"/api/places/{chamber['id']}").status_code == 400
    assert zoe.delete(f"/api/places/{chamber['id']}").status_code == 404           # as if there were none


def test_many_plants_are_moved_and_marked_at_once(as_user):
    ana, zoe = as_user('ana'), as_user('zoe')
    chamber, greenhouse = _place(ana), _place(ana, 'Greenhouse B', kind='greenhouse')
    lot = _lot(ana, _line(ana)['code'])
    plants = [p['code'] for p in _ok(ana.post(f"/api/lots/{lot['code']}/sow",
                                              json={'count': 4, 'place': chamber['id']}), 201)['record']['plants']]
    assert _ok(ana.post('/api/plants/change', json={'plants': plants[:3], 'place': greenhouse['id'],
                                                    'location': 'bench 4', 'treatment': 'heat'}))['changed'] == 3
    moved = _ok(ana.get(f'/api/plant/{plants[0]}'))['record']
    assert moved['place']['name'] == 'Greenhouse B' and moved['location'] == 'bench 4' and moved['treatment'] == 'heat'
    assert 'moved to Greenhouse B' in moved['changes'][0]['what']
    _ok(ana.post('/api/plants/change', json={'plants': plants[1:], 'status': 'discarded'}))
    grown = _ok(ana.get('/api/growing'))['plants']
    assert [p['code'] for p in grown] == [plants[0]]
    assert ana.post('/api/plants/change', json={'plants': plants, 'status': 'eaten'}).status_code == 400
    assert ana.post('/api/plants/change', json={'plants': plants}).status_code == 400            # nothing to change
    assert zoe.post('/api/plants/change', json={'plants': plants, 'status': 'dead'}).status_code == 404
    # Nothing grows in the chamber any more: it can go.
    _ok(ana.delete(f"/api/places/{chamber['id']}"))
    assert [p['name'] for p in _ok(ana.get('/api/places'))['places']] == ['Greenhouse B']


def test_a_measurement_keeps_its_number_and_unit(as_user):
    ana = as_user('ana')
    lot = _lot(ana, _line(ana)['code'])
    plant = _ok(ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 1}), 201)['record']['plants'][0]['code']
    for value, unit in (('12,5 cm', ''), ('30', 'days'), ('pale green', '')):
        _ok(ana.post(f'/api/plant/{plant}/observations', json={'trait': 'x', 'value': value, 'unit': unit}), 201)
    seen = {o['value']: (o['number'], o['unit']) for o in _ok(ana.get(f'/api/plant/{plant}'))['record']['observations']}
    assert seen == {'12,5 cm': (12.5, 'cm'), '30': (30.0, 'days'), 'pale green': (None, '')}


def test_scoring_many_plants_and_their_phenotypes_by_treatment(as_user):
    ana, zoe = as_user('ana'), as_user('zoe')
    line = _line(ana)
    lot = _lot(ana, line['code'])
    control = _ok(ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 3, 'treatment': 'control'}), 201)
    drought = _ok(ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 3, 'treatment': 'drought'}), 201)
    plants = [p['code'] for p in drought['record']['plants']]
    heights = {plants[0]: '10', plants[1]: '12', plants[2]: '14', plants[3]: '6', plants[4]: '8', plants[5]: ''}
    recorded = _ok(ana.post('/api/score', json={
        'trait': 'height', 'unit': 'cm', 'observed_on': '2026-10-20',
        'values': [{'plant': c, 'value': v} for c, v in heights.items()]}), 201)['recorded']
    assert recorded == 5                                                         # the empty one is skipped
    _ok(ana.post('/api/score', json={'trait': 'leaf colour', 'values': [
        {'plant': plants[0], 'value': 'green'}, {'plant': plants[1], 'value': 'green'},
        {'plant': plants[3], 'value': 'yellow', 'notes': 'wilting'}]}), 201)
    assert ana.post('/api/score', json={'trait': 'height', 'values': [{'plant': plants[0], 'value': ''}]}).status_code == 400
    assert zoe.post('/api/score', json={'trait': 'height', 'values': [{'plant': plants[0], 'value': '1'}]}).status_code == 404

    found = _ok(ana.get(f"/api/lot/{lot['code']}/phenotypes"))
    assert found['count'] == 8
    height = next(t for t in found['summary'] if t['trait'] == 'height')
    assert height['unit'] == 'cm'
    by = {g['treatment']: g for g in height['groups']}
    assert by['control']['n'] == 3 and by['control']['mean'] == 12 and by['control']['sd'] == 2
    assert by['drought']['n'] == 2 and by['drought']['mean'] == 7 and (by['drought']['min'], by['drought']['max']) == (6, 8)
    colour = next(t for t in found['summary'] if t['trait'] == 'leaf colour')
    assert {g['treatment']: g['counts'] for g in colour['groups']} == {'control': [['green', 2]], 'drought': [['yellow', 1]]}
    # The line's summary takes in all its lots' plants.
    assert _ok(ana.get(f"/api/line/{line['code']}/phenotypes"))['count'] == 8
    assert zoe.get(f"/api/lot/{lot['code']}/phenotypes").status_code == 404

    sheet = ana.get(f"/api/lot/{lot['code']}/phenotypes.csv")
    assert sheet.status_code == 200 and 'attachment' in sheet.headers['Content-Disposition']
    rows = list(csv.DictReader(io.StringIO(sheet.get_data(as_text=True).lstrip('﻿'))))
    assert len(rows) == 8 and rows[0]['lot'] == lot['code'] and rows[0]['plant_number'] == '1'
    first = next(r for r in rows if r['trait'] == 'height' and r['plant'] == plants[0])
    assert (first['measured'], first['unit'], first['treatment'], first['observed_on']) == ('10.0', 'cm', 'control', '2026-10-20')
    assert next(r for r in rows if r['value'] == 'yellow')['notes'] == 'wilting'


def _link(world, note_id, title, target_type, target_id, owner='ana'):
    conn = sqlite3.connect(world['paths']['notebook'])
    conn.execute('INSERT OR IGNORE INTO notes (id, title, type, owner, updated_at) VALUES (?, ?, ?, ?, ?)',
                 (note_id, title, 'page', owner, '2026-10-20'))
    conn.execute('INSERT INTO links VALUES (?, ?, ?)', (note_id, target_type, target_id))
    conn.commit()
    conn.close()


def _stock(world, code, lab, plasmid='p1'):
    conn = sqlite3.connect(world['paths']['stocks'])
    conn.execute('INSERT INTO glycerol (id, code, lab, plasmid_id, plasmid_name, clone, host, location, status) '
                 "VALUES (?, ?, ?, ?, 'pGreen-35S-GFP', '2', 'DH5a', '-80 box 3', 'in stock')", (code, code, lab, plasmid))
    conn.commit()
    conn.close()


def _transgenic(ana):
    """pGreen-35S-GFP into Col-0: a T1 lot, a plant harvested into T2, and its siblings."""
    col = _line(ana, 'Col-0', kind='wild type')
    gfp = _line(ana, '35S:GFP #1', kind='transgenic', parents=[{'id': col['code'], 'role': 'background'}])
    _ok(ana.put(f"/api/lines/{gfp['code']}", json={'plasmids': [{'id': 'p1', 'name': 'pGreen-35S-GFP'}]}))
    t1 = _lot(ana, gfp['code'], generation='T1')
    plants = [p['code'] for p in _ok(ana.post(f"/api/lots/{t1['code']}/sow", json={'count': 5}), 201)['record']['plants']]
    t2 = _ok(ana.post(f'/api/plants/{plants[0]}/harvest', json={}), 201)['record']
    _ok(ana.put(f'/api/plants/{plants[1]}', json={'status': 'discarded'}))
    return col, gfp, t1, plants, t2


def test_a_plasmids_family_tree_runs_through_stocks_lines_lots_and_plants(as_user, world):
    ana, zoe = as_user('ana'), as_user('zoe')
    col, gfp, t1, plants, t2 = _transgenic(ana)
    _stock(world, 'GL-G-0001', 'Gardiner Lab')
    _stock(world, 'OL-G-0001', 'Other Lab')
    _link(world, 'n1', 'Cloning pGreen', 'plasmid', 'p1')
    _link(world, 'n2', 'Glycerol stocks', 'stock', 'GL-G-0001')
    _link(world, 'n3', 'Dipping', 'seed', t1['code'])
    _link(world, 'n4', 'Ben private', 'seed', t1['code'], owner='ben')         # ana does not see ben's notebook
    _link(world, 'n5', 'Plant 3 looked odd', 'seed', plants[2])

    tree = _ok(ana.get('/api/tree/plasmid/p1'))
    plasmid = tree['constructs'][0]
    assert plasmid['name'] == 'pGreen-35S-GFP' and plasmid['opens']
    assert [s['code'] for s in plasmid['stocks']] == ['GL-G-0001']                 # not another lab's stock
    assert plasmid['stocks'][0]['mentions'][0]['title'] == 'Glycerol stocks'
    assert [m['title'] for m in plasmid['mentions']] == ['Cloning pGreen']
    [line] = tree['descendants']
    assert line['code'] == gfp['code'] and line['lots'][0]['code'] == t1['code']
    lot = line['lots'][0]
    assert [m['title'] for m in lot['mentions']] == ['Dipping']
    # Plant by plant: the one harvested, and the one written about; the rest counted.
    assert [p['code'] for p in lot['plants']] == [plants[0], plants[2]]
    assert lot['others'] == {'growing': 2, 'discarded': 1}
    assert lot['plants'][0]['lots'][0]['code'] == t2['code']
    # Col-0 is the background, not a carrier: it is not in a tree that starts from the plasmid.
    assert col['code'] not in str(tree['descendants'])

    assert ana.get('/api/tree/plasmid/p-none').status_code == 404
    # Another lab sees the plasmid through its own stock of it, and nothing of Gardiner Lab's.
    theirs = _ok(zoe.get('/api/tree/plasmid/p1'))
    assert [s['code'] for s in theirs['constructs'][0]['stocks']] == ['OL-G-0001'] and theirs['descendants'] == []
    assert theirs['constructs'][0]['mentions'] == []                            # ana's page


def test_a_seed_lots_family_tree_goes_back_to_its_construct(as_user, world):
    ana, zoe = as_user('ana'), as_user('zoe')
    col, gfp, t1, plants, t2 = _transgenic(ana)
    _stock(world, 'GL-G-0001', 'Gardiner Lab')
    t3_plant = _ok(ana.post(f"/api/lots/{t2['code']}/sow", json={'count': 1}), 201)['record']['plants'][0]['code']
    t3 = _ok(ana.post(f'/api/plants/{t3_plant}/harvest', json={}), 201)['record']

    tree = _ok(ana.get(f"/api/tree/lot/{t2['code']}"))
    assert tree['focus'] == {'kind': 'lot', 'code': t2['code']}
    assert tree['constructs'][0]['carried_by'] == [{'code': gfp['code'], 'name': '35S:GFP #1'}]
    assert tree['constructs'][0]['stocks'][0]['code'] == 'GL-G-0001'
    assert [c['code'] for c in tree['chain']] == [t1['code'], plants[0]]        # oldest first
    assert tree['pedigree']['code'] == gfp['code'] and tree['pedigree']['parents'][0]['code'] == col['code']
    [focus] = tree['descendants']
    assert focus['focus'] and focus['plants'][0]['code'] == t3_plant and focus['plants'][0]['lots'][0]['code'] == t3['code']

    # From the wild type: the transgenic line made from it, with all its seeds.
    from_col = _ok(ana.get(f"/api/tree/line/{col['code']}"))
    assert from_col['constructs'] == [] and from_col['descendants'][0]['lines'][0]['code'] == gfp['code']
    assert from_col['descendants'][0]['lines'][0]['role'] == 'background'
    assert zoe.get(f"/api/tree/lot/{t2['code']}").status_code == 404


def test_an_older_database_gets_places_treatments_and_units(world):
    from app import db
    conn = sqlite3.connect(db.path())
    conn.executescript("""
        ALTER TABLE plants RENAME TO plants_new;
        CREATE TABLE plants (id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, lab TEXT, lot_id TEXT NOT NULL,
            line_id TEXT NOT NULL, number INTEGER NOT NULL, sown_on TEXT, location TEXT NOT NULL DEFAULT '',
            zygosity TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'growing', selected INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '', created_by TEXT, created_at TIMESTAMP, updated_at TIMESTAMP, deleted_at TIMESTAMP);
        INSERT INTO plants (id, code, lot_id, line_id, number) VALUES ('old', 'GARD-P-0001', 's', 'l', 1);
        ALTER TABLE observations DROP COLUMN unit;
        ALTER TABLE observations DROP COLUMN number;
    """)
    conn.commit()
    conn.close()
    db.initialize()
    conn = sqlite3.connect(db.path())
    assert conn.execute("SELECT place_id, treatment FROM plants WHERE id = 'old'").fetchone() == (None, '')
    assert {'number', 'unit'} <= {r[1] for r in conn.execute('PRAGMA table_info(observations)')}
    conn.close()
