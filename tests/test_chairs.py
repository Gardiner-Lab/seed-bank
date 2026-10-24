"""A chair group's labs see each other's lines, seed lots, plants and places; only a record's own lab changes it."""

import io
import sqlite3

import pytest

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_json())
    return r.get_json()


@pytest.fixture()
def chair(world):
    """Gardiner Lab and Other Lab in one chair group; a third lab, Far Lab, outside it."""
    conn = sqlite3.connect(world['paths']['suite'])
    conn.executescript("""
        CREATE TABLE chair_groups (id INTEGER PRIMARY KEY, name TEXT);
        INSERT INTO chair_groups VALUES (1, 'Plant Sciences');
        ALTER TABLE labs ADD COLUMN chair_group_id INTEGER;
        UPDATE labs SET chair_group_id = 1;
        INSERT INTO labs (id, name) VALUES (3, 'Far Lab');
        INSERT INTO members VALUES ('far', 3, 'member');
    """)
    conn.commit()
    conn.close()
    conn = sqlite3.connect(world['paths']['moclo'])
    conn.execute("INSERT INTO users VALUES ('far', 'far', 0)")
    conn.commit()
    conn.close()


def _gardiner(ana):
    """Ana's (Gardiner Lab's) line with a plasmid, a lot sown into a place, and a plant."""
    line = _ok(ana.post('/api/lines', json={'name': '35S:GFP #1', 'species': 'Arabidopsis thaliana', 'kind': 'transgenic',
                                           'plasmids': [{'id': 'p1', 'name': 'pGreen-35S-GFP'}]}), 201)['record']
    lot = _ok(ana.post('/api/lots', json={'line': line['code'], 'generation': 'T2'}), 201)['record']
    made = _ok(ana.post('/api/places', json={'name': 'Chamber 3'}), 201)
    plants = _ok(ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 2, 'place': made['id']}), 201)['record']['plants']
    return line, lot, made['id'], [p['code'] for p in plants]


def test_a_chair_group_sees_each_others_records_but_does_not_change_them(as_user, chair):
    ana, zoe, far = as_user('ana'), as_user('zoe'), as_user('far')
    line, lot, place, plants = _gardiner(ana)

    # Seen, in the lists and opened, and said to be another lab's.
    assert line['code'] in [x['code'] for x in _ok(zoe.get('/api/lines'))['lines']]
    assert plants[0] in [x['code'] for x in _ok(zoe.get('/api/plants'))['plants']]
    seen = _ok(zoe.get(f"/api/lot/{lot['code']}"))['record']
    assert seen['mine'] is False and seen['lab'] == 'Gardiner Lab' and seen['chair_group'] == 'Plant Sciences'
    assert _ok(ana.get(f"/api/lot/{lot['code']}"))['record']['mine'] is True
    assert _ok(zoe.get(f"/api/lot/{lot['code']}/phenotypes"))['count'] == 0
    grown = _ok(zoe.get('/api/growing'))
    assert {p['code'] for p in grown['plants']} == set(plants) and not any(p['mine'] for p in grown['plants'])
    assert grown['places'][0]['name'] == 'Chamber 3' and grown['places'][0]['mine'] is False

    # Not changed: each refused, and the reason given.
    refused = [
        zoe.put(f"/api/lines/{line['code']}", json={'name': 'mine now'}),
        zoe.put(f"/api/lines/{line['code']}", json={'plasmids': []}),
        zoe.post('/api/lots', json={'line': line['code']}),
        zoe.put(f"/api/lots/{lot['code']}", json={'amount': 'none'}),
        zoe.post(f"/api/lots/{lot['code']}/sow", json={'count': 1}),
        zoe.post(f"/api/lots/{lot['code']}/seg-tests", json={'resistant': 30, 'sensitive': 10, 'expected': '3:1'}),
        zoe.put(f'/api/plants/{plants[0]}', json={'status': 'dead'}),
        zoe.post(f'/api/plants/{plants[0]}/harvest', json={}),
        zoe.post(f'/api/plants/{plants[0]}/found-line', json={}),
        zoe.post(f'/api/plant/{plants[0]}/observations', json={'trait': 'height', 'value': '3'}),
        zoe.post('/api/score', json={'trait': 'height', 'values': [{'plant': plants[0], 'value': '3'}]}),
        zoe.post('/api/plants/change', json={'plants': plants, 'status': 'discarded'}),
        zoe.post(f'/api/plant/{plants[0]}/attachments', data={'file': (io.BytesIO(PNG), 'leaf.png')},
                 content_type='multipart/form-data'),
        zoe.delete(f'/api/plant/{plants[1]}'),
        zoe.put(f'/api/places/{place}', json={'name': 'Ours'}),
        zoe.delete(f'/api/places/{place}'),
    ]
    assert [r.status_code for r in refused] == [403] * len(refused), [r.get_json() for r in refused if r.status_code != 403]
    assert "only its own lab changes it" in refused[0].get_json()['error']
    assert _ok(ana.get(f"/api/line/{line['code']}"))['record']['name'] == '35S:GFP #1'

    # Ana's observation and file stay hers.
    obs = _ok(ana.post(f'/api/plant/{plants[0]}/observations', json={'trait': 'height', 'value': '3'}), 201)['id']
    assert zoe.delete(f'/api/observations/{obs}').status_code == 403
    att = _ok(ana.post(f'/api/plant/{plants[0]}/attachments', data={'file': (io.BytesIO(PNG), 'leaf.png')},
                       content_type='multipart/form-data'), 201)['attachments'][0]['id']
    assert zoe.get(f'/api/attachments/{att}').status_code == 200                          # seen
    assert zoe.delete(f'/api/attachments/{att}').status_code == 403                       # not removed

    # A lab outside the chair group sees nothing of it.
    assert far.get(f"/api/lot/{lot['code']}").status_code == 404
    assert _ok(far.get('/api/lines'))['lines'] == [] and _ok(far.get('/api/growing'))['plants'] == []


def test_a_chair_groups_records_can_be_parents_and_pollen_donors(as_user, chair):
    ana, zoe = as_user('ana'), as_user('zoe')
    line, lot, place, plants = _gardiner(ana)
    # Zoe's own line, from Gardiner Lab's as its background.
    own = _ok(zoe.post('/api/lines', json={'name': 'gfp in Ler', 'parents': [{'id': line['code'], 'role': 'background'}]}), 201)['record']
    assert own['parents'][0]['code'] == line['code'] and own['lab'] == 'Other Lab'
    own_lot = _ok(zoe.post('/api/lots', json={'line': own['code']}), 201)['record']
    mother = _ok(zoe.post(f"/api/lots/{own_lot['code']}/sow", json={'count': 1}), 201)['record']['plants'][0]['code']
    # Her plant crossed with Ana's: the cross and its F1 seeds are Zoe's.
    crossed = _ok(zoe.post(f'/api/plants/{mother}/cross', json={'father': plants[0]}), 201)['record']
    assert crossed['lab'] == 'Other Lab' and crossed['father_plant']['code'] == plants[0]
    # But not the other way round: the mother's lab makes the seeds.
    assert zoe.post(f'/api/plants/{plants[0]}/cross', json={'father': mother}).status_code == 403
    # Her plants do not go into Gardiner Lab's chamber.
    assert zoe.post(f"/api/lots/{own_lot['code']}/sow", json={'count': 1, 'place': place}).status_code == 400


def test_a_family_tree_takes_in_the_chair_group(as_user, world, chair):
    ana, zoe, far = as_user('ana'), as_user('zoe'), as_user('far')
    line, lot, place, plants = _gardiner(ana)
    conn = sqlite3.connect(world['paths']['stocks'])
    conn.executemany("INSERT INTO glycerol (id, code, lab, plasmid_id, status) VALUES (?, ?, ?, 'p1', 'in stock')",
                     [('a', 'GL-G-0001', 'Gardiner Lab'), ('b', 'FL-G-0001', 'Far Lab')])
    conn.commit()
    conn.close()
    tree = _ok(zoe.get('/api/tree/plasmid/p1'))
    assert [s['code'] for s in tree['constructs'][0]['stocks']] == ['GL-G-0001']            # not Far Lab's
    assert tree['descendants'][0]['code'] == line['code']
    assert _ok(zoe.get(f"/api/tree/lot/{lot['code']}"))['descendants'][0]['code'] == lot['code']
    assert far.get(f"/api/tree/lot/{lot['code']}").status_code == 404


def test_without_chair_groups_labs_stay_apart(as_user):
    ana, zoe = as_user('ana'), as_user('zoe')
    line = _ok(ana.post('/api/lines', json={'name': 'Col-0'}), 201)['record']
    assert zoe.get(f"/api/line/{line['code']}").status_code == 404
    assert _ok(zoe.get('/api/lines'))['lines'] == []
