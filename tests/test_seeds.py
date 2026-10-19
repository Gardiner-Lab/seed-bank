"""The seed bank: lines, lots and plants, their lineage, and who sees them."""

import io
import sqlite3

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
STL = b'solid leaf\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid leaf\n'


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_json())
    return r.get_json()


def _line(client, name='Col-0', **extra):
    return _ok(client.post('/api/lines', json={'name': name, 'species': 'Arabidopsis thaliana', **extra}), 201)['record']


def _lot(client, line, **extra):
    return _ok(client.post('/api/lots', json={'line': line, **extra}), 201)['record']


def test_nothing_without_the_suite_saying_who_you_are(world):
    client = world['app'].test_client()
    assert client.get('/api/lines').status_code == 401
    assert client.get('/').status_code == 302
    assert client.get('/health').get_json()['status'] == 'healthy'


def test_from_stock_centre_seeds_to_a_homozygous_t3_line(as_user):
    """The whole transformation route: dip, select T1s, found lines, test T2s, find a homozygous T3."""
    ana = as_user('ana')
    col = _line(ana, 'Col-0', kind='wild type', background='Col-0')
    assert col['code'] == 'GL-L-0001', 'Gardiner Lab: GL'
    nasc = _lot(ana, col['code'], generation='', source='NASC N1092', amount='~2000 seeds',
                location='Freezer 2 / box 4 / A1', germination=98)
    assert nasc['code'] == 'GL-S-0001' and nasc['from_plant'] is None

    # Transformed with a plasmid: a population line whose T1 seeds came from dipped Col-0 plants.
    dipped = _ok(ana.post(f"/api/lots/{nasc['code']}/sow", json={'count': 6, 'sown_on': '2026-07-01',
                                                                  'location': 'Tray 3'}), 201)['record']
    assert [p['number'] for p in dipped['plants']] == [1, 2, 3, 4, 5, 6]
    population = _line(ana, '35S:GFP', kind='population', background='Col-0',
                       parents=[{'id': col['id'], 'role': 'background'}],
                       plasmids=[{'id': 'p1', 'name': 'pGreen-35S-GFP'}])
    t1_seeds = _lot(ana, population['code'], generation='T1', source='floral dip of tray 3', location='Freezer 2 / box 4 / A2')

    # Six T1 plants; #4 is resistant and green: it founds a line of its own, an independent event.
    sown = _ok(ana.post(f"/api/lots/{t1_seeds['code']}/sow", json={'count': 6}), 201)['record']
    t1 = sown['plants'][3]
    event = _ok(ana.post(f"/api/plants/{t1['code']}/found-line", json={}), 201)['record']
    assert event['name'] == '35S:GFP-4' and event['line_kind'] == 'transgenic'
    assert [p['name'] for p in event['plasmids']] == ['pGreen-35S-GFP'], 'the plasmid comes with it'
    assert event['parents'][0]['code'] == population['code'] and event['parents'][0]['role'] == 'founded from'

    # Harvest it: a T2 lot of the new line.
    t2 = _ok(ana.post(f"/api/plants/{t1['code']}/harvest", json={'amount': '300 mg', 'location': 'Box 5 / B1'}), 201)['record']
    assert t2['generation'] == 'T2' and t2['line']['code'] == event['code'] and t2['from_plant']['code'] == t1['code']
    assert _ok(ana.get(f"/api/plant/{t1['code']}"))['record']['status'] == 'harvested'

    # T2 segregates 3:1 on Basta: one insertion.
    tested = _ok(ana.post(f"/api/lots/{t2['code']}/seg-tests", json={
        'selection': 'Basta', 'resistant': 74, 'sensitive': 26, 'expected': '3:1'}), 201)['record']
    test = tested['seg_tests'][0]
    assert test['fits']['3:1']['fits'] is True and test['fits']['15:1']['fits'] is False
    assert test['verdict'].startswith('Consistent with 3:1 (one insertion)')

    # T2 plant #2 gives T3 seeds that are all resistant: homozygous.
    t2_plants = _ok(ana.post(f"/api/lots/{t2['code']}/sow", json={'count': 3}), 201)['record']['plants']
    t3 = _ok(ana.post(f"/api/plants/{t2_plants[1]['code']}/harvest", json={}), 201)['record']
    assert t3['generation'] == 'T3'
    homo = _ok(ana.post(f"/api/lots/{t3['code']}/seg-tests", json={'resistant': 112, 'sensitive': 0, 'expected': '1:0'}), 201)
    assert homo['record']['seg_tests'][0]['verdict'].startswith('Consistent with homozygous')
    _ok(ana.put(f"/api/lots/{t3['code']}", json={'zygosity': 'homozygous'}))

    # Lineage, both ways.
    ancestry = [n['code'] for n in t3['ancestry']]
    assert ancestry == [t2_plants[1]['code'], t2['code'], t1['code'], t1_seeds['code']]
    down = _ok(ana.get(f"/api/lot/{t1_seeds['code']}"))['record']['descendants']
    plant4 = next(n for n in down if n['code'] == t1['code'])
    assert plant4['children'][0]['code'] == t2['code']
    assert [c['code'] for c in plant4['children'][0]['children']] == [p['code'] for p in t2_plants]

    # The pedigree of the line, and which lines carry the plasmid.
    detail = _ok(ana.get(f"/api/line/{event['code']}"))['record']
    assert detail['pedigree']['parents'][0]['code'] == population['code']
    assert detail['pedigree']['parents'][0]['parents'][0]['code'] == col['code']
    carrying = _ok(ana.get('/api/plasmids/p1/lines'))['lines']
    assert {l['code'] for l in carrying} == {population['code'], event['code']}
    # Every change is in the record's history.
    assert any('harvested into' in c['what'] for c in _ok(ana.get(f"/api/plant/{t1['code']}"))['record']['changes'])


def test_crossing_two_plants(as_user):
    ana = as_user('ana')
    a = _line(ana, 'gfp-4', kind='transgenic', plasmids=[{'id': 'p1', 'name': 'pGreen-35S-GFP'}])
    b = _line(ana, 'myb21', kind='mutant')
    pa = _ok(ana.post(f"/api/lots/{_lot(ana, a['code'], generation='T3')['code']}/sow", json={'count': 1}), 201)['record']['plants'][0]
    pb = _ok(ana.post(f"/api/lots/{_lot(ana, b['code'], generation='M3')['code']}/sow", json={'count': 1}), 201)['record']['plants'][0]
    f1 = _ok(ana.post(f"/api/plants/{pa['code']}/cross", json={'father': pb['code'], 'harvested_on': '2026-09-01'}), 201)['record']
    assert f1['generation'] == 'F1' and f1['from_plant']['code'] == pa['code'] and f1['father_plant']['code'] == pb['code']
    line = _ok(ana.get(f"/api/line/{f1['line']['code']}"))['record']
    assert line['name'] == 'gfp-4 × myb21' and line['line_kind'] == 'cross'
    assert {(p['code'], p['role']) for p in line['parents']} == {(a['code'], 'mother'), (b['code'], 'father')}
    assert [p['name'] for p in line['plasmids']] == ['pGreen-35S-GFP']
    roles = [(n['code'], n.get('role')) for n in f1['ancestry'][:2]]
    assert roles == [(pb['code'], 'father'), (pa['code'], 'mother')]
    assert ana.post(f"/api/plants/{pa['code']}/cross", json={'father': pa['code']}).status_code == 400


def test_a_lab_shares_its_stocks_and_other_labs_do_not_see_them(as_user):
    ana, ben, zoe, boss = as_user('ana'), as_user('ben'), as_user('zoe'), as_user('boss')
    line = _line(ana, 'Ler-0')
    lot = _lot(ana, line['code'], location='Box 1')
    # Ben, in the same lab, sees and changes it.
    assert _ok(ben.get(f"/api/line/{line['code']}"))['record']['name'] == 'Ler-0'
    _ok(ben.put(f"/api/lots/{lot['code']}", json={'amount': '50 mg'}))
    assert any(c['changed_by'] == 'ben' for c in _ok(ana.get(f"/api/lot/{lot['code']}"))['record']['changes'])
    # Zoe, another lab, does not even learn it exists.
    assert zoe.get(f"/api/line/{line['code']}").status_code == 404
    assert zoe.put(f"/api/lots/{lot['code']}", json={'amount': 'x'}).status_code == 404
    assert _ok(zoe.get('/api/lines'))['lines'] == [] and _ok(zoe.get('/api/search?q=Ler'))['results'] == []
    assert zoe.post('/api/lots', json={'line': line['code']}).status_code == 404
    # Her own lab's stocks are hers; the admin sees all.
    zl = _line(zoe, 'Col-0 (Other Lab)')
    assert ana.get(f"/api/line/{zl['code']}").status_code == 404
    assert {l['code'] for l in _ok(boss.get('/api/lines'))['lines']} == {line['code'], zl['code']}
    # Someone in no lab keeps their own.
    solo = _line(as_user('loner'), 'Mine')
    assert ana.get(f"/api/line/{solo['code']}").status_code == 404


def test_phenotypes_with_photos_and_3d_scans(as_user):
    ana, zoe = as_user('ana'), as_user('zoe')
    line = _line(ana)
    plant = _ok(ana.post(f"/api/lots/{_lot(ana, line['code'])['code']}/sow", json={'count': 1}), 201)['record']['plants'][0]
    rec = _ok(ana.post(f"/api/plant/{plant['code']}/observations", json={
        'trait': 'flowering', 'value': 'day 24', 'observed_on': '2026-08-02'}), 201)['record']
    obs = rec['observations'][0]
    assert (obs['trait'], obs['value'], obs['created_by']) == ('flowering', 'day 24', 'ana')
    # A photo on the observation, a 3D scan and a document on the plant.
    up = _ok(ana.post(f"/api/observation/{obs['id']}/attachments", content_type='multipart/form-data',
                      data={'file': [(io.BytesIO(PNG), 'rosette.png')], 'caption': 'day 24'}), 201)['attachments'][0]
    assert up['image'] is True and up['caption'] == 'day 24'
    files = _ok(ana.post(f"/api/plant/{plant['code']}/attachments", content_type='multipart/form-data',
                         data={'file': [(io.BytesIO(STL), 'scan.stl'), (io.BytesIO(b'PK\x03\x04'), 'genotyping.xlsx')]}), 201)['attachments']
    scan, sheet = files
    assert (scan['kind'], scan['model'], sheet['kind']) == ('3d', True, 'excel')
    got = ana.get(f"/api/attachments/{scan['id']}")
    assert got.data == STL and got.headers['Content-Disposition'].startswith('attachment')
    assert ana.get(f"/api/attachments/{up['id']}").headers['Content-Disposition'].startswith('inline')
    # Another lab cannot open them.
    assert zoe.get(f"/api/attachments/{up['id']}").status_code == 404
    assert zoe.get(f"/api/attachments/{scan['id']}").status_code == 404
    detail = _ok(ana.get(f"/api/plant/{plant['code']}"))['record']
    assert detail['observations'][0]['attachments'][0]['filename'] == 'rosette.png'
    assert [a['filename'] for a in detail['attachments']] == ['scan.stl', 'genotyping.xlsx']


def test_segregation_maths():
    from app import stats
    single = stats.assess(75, 25, '3:1')
    assert single['fits']['3:1']['chi2'] == 0 and single['fits']['3:1']['p'] == 1.0
    two = stats.assess(150, 10, '15:1')
    assert two['fits']['15:1']['fits'] is True and two['fits']['3:1']['fits'] is False
    off = stats.assess(60, 40, '3:1')
    assert off['fits']['3:1']['fits'] is False and off['verdict'].startswith('Differs from 3:1')
    assert stats.assess(50, 1, '1:0')['verdict'].startswith('Not homozygous: 1 of 51')
    assert 'Few seedlings' in stats.assess(10, 2, '3:1')['verdict']
    # chi-square 3.841 is p = 0.05 at one degree of freedom.
    assert abs(stats.chi_square(85, 15, '3:1')['p'] - 0.0209) < 0.001
    assert stats.chi_square(300, 300, '3:1')['p_text'] == '< 0.0001'
    assert 'p < 0.0001' in stats.assess(300, 300, '3:1')['verdict']


def test_rules_that_keep_lineage_whole(as_user):
    ana = as_user('ana')
    line = _line(ana)
    lot = _lot(ana, line['code'])
    plants = _ok(ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 2}), 201)['record']['plants']
    assert ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 0}).status_code == 400
    assert ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 501}).status_code == 400
    # Numbering continues after an earlier sowing.
    more = _ok(ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 1}), 201)['record']['plants']
    assert [p['number'] for p in more] == [1, 2, 3]
    _ok(ana.post(f"/api/plants/{plants[0]['code']}/harvest", json={}), 201)
    # What others descend from cannot be removed.
    assert ana.delete(f"/api/plant/{plants[0]['code']}").status_code == 400
    assert ana.delete(f"/api/lot/{lot['code']}").status_code == 400
    assert ana.delete(f"/api/line/{line['code']}").status_code == 400
    assert ana.delete(f"/api/plant/{plants[1]['code']}").status_code == 200
    # No line its own ancestor; checked values.
    child = _line(ana, 'child', parents=[{'id': line['id'], 'role': 'background'}])
    assert ana.put(f"/api/lines/{line['code']}", json={'parents': [{'id': child['id'], 'role': 'parent'}]}).status_code == 400
    assert ana.post('/api/lines', json={'name': ''}).status_code == 400
    assert ana.post('/api/lines', json={'name': 'x', 'kind': 'alien'}).status_code == 400
    assert ana.put(f"/api/lots/{lot['code']}", json={'germination': 120}).status_code == 400
    assert ana.put(f"/api/lots/{lot['code']}", json={'harvested_on': '15/10/2026'}).status_code == 400
    assert ana.post(f"/api/lots/{lot['code']}/seg-tests", json={'resistant': 0, 'sensitive': 0}).status_code == 400


def test_plasmids_and_notebook_mentions(as_user, world):
    ana, ben, zoe = as_user('ana'), as_user('ben'), as_user('zoe')
    found = _ok(ben.get('/api/plasmids?q=pGreen'))['plasmids']
    assert [p['id'] for p in found] == ['p1']
    assert [p['id'] for p in _ok(ben.get('/api/plasmids'))['plasmids']] == ['p1'], "ana's private plasmid stays hers"
    line = _line(ana)
    lot = _lot(ana, line['code'])
    conn = sqlite3.connect(world['paths']['notebook'])
    conn.execute("INSERT INTO notes VALUES ('n1', '2026-10-15 Thursday', 'day', 'ana', '2026-10-15', NULL)")
    conn.execute("INSERT INTO links VALUES ('n1', 'seed', ?)", (lot['code'],))
    conn.commit()
    conn.close()
    assert [m['title'] for m in _ok(ana.get(f"/api/lot/{lot['code']}"))['record']['mentions']] == ['2026-10-15 Thursday']
    assert _ok(ben.get(f"/api/lot/{lot['code']}"))['record']['mentions'] == [], "a labmate's notebook stays private"
    assert [m['id'] for m in _ok(as_user('lead').get(f"/api/lot/{lot['code']}"))['record']['mentions']] == ['n1']
    assert zoe.get(f"/api/lot/{lot['code']}").status_code == 404
    # Search for the notebook's link picker: by code first.
    results = _ok(ana.get(f"/api/search?q={lot['code']}"))['results']
    assert results[0]['code'] == lot['code'] and results[0]['kind'] == 'lot'


def test_seeds_of_a_dipped_plant_go_to_the_transgenic_line(as_user):
    """Transformation, exactly: Col-0 plants dipped, their seeds the T1 of the new line, traced back."""
    ana = as_user('ana')
    col = _line(ana, 'Col-0', kind='wild type')
    nasc = _lot(ana, col['code'], source='NASC N1092')
    dipped = _ok(ana.post(f"/api/lots/{nasc['code']}/sow", json={'count': 2}), 201)['record']['plants'][0]
    gfp = _line(ana, '35S:GFP', kind='population', plasmids=[{'id': 'p1', 'name': 'pGreen-35S-GFP'}])
    t1 = _ok(ana.post(f"/api/plants/{dipped['code']}/harvest", json={'line': gfp['code']}), 201)['record']
    assert (t1['line']['code'], t1['generation'], t1['from_plant']['code']) == (gfp['code'], 'T1', dipped['code'])
    assert [n['code'] for n in t1['ancestry']] == [dipped['code'], nasc['code']]
    # Without a line, a harvest stays in the plant's own line, one generation on.
    other = _ok(ana.post(f"/api/lots/{nasc['code']}/sow", json={'count': 1}), 201)['record']['plants'][0]
    own = _ok(ana.post(f"/api/plants/{other['code']}/harvest", json={}), 201)['record']
    assert own['line']['code'] == col['code']
    # Another lab's line is not a place to put seeds.
    zl = _line(as_user('zoe'), 'Theirs')
    assert ana.post(f"/api/plants/{other['code']}/harvest", json={'line': zl['code']}).status_code == 404


def test_a_lot_in_the_wrong_line_can_be_moved_until_it_is_sown(as_user):
    ana = as_user('ana')
    right, wrong = _line(ana, 'Right'), _line(ana, 'Wrong')
    lot = _lot(ana, wrong['code'])
    moved = _ok(ana.put(f"/api/lots/{lot['code']}", json={'line': right['code']}))['record']
    assert moved['line']['code'] == right['code']
    assert any(f"line: {wrong['code']} → {right['code']}" in c['what'] for c in moved['changes'])
    ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 1})
    assert ana.put(f"/api/lots/{lot['code']}", json={'line': wrong['code']}).status_code == 400


def test_the_help_page(as_user):
    page = as_user('ana').get('/help')
    assert page.status_code == 200 and b'Golden rules' in page.data and b'Found a line' in page.data



def test_each_lab_has_its_own_code_and_numbering(as_user, world):
    import sqlite3
    ana, zoe, lead = as_user('ana'), as_user('zoe'), as_user('lead')
    # A third lab whose initials clash with Gardiner Lab's.
    conn = sqlite3.connect(world['paths']['suite'])
    conn.execute("INSERT INTO labs VALUES (3, 'Green Lab')")
    conn.execute("INSERT INTO members VALUES ('gil', 3, 'lab_lead')")
    conn.commit()
    conn.close()
    conn = sqlite3.connect(world['paths']['moclo'])
    conn.execute("INSERT INTO users VALUES ('gil', 'gil', 0)")
    conn.commit()
    conn.close()
    gil = as_user('gil')

    # Before its first record, a lab's lead chooses its code; members cannot.
    assert _ok(lead.get('/api/lab'))['code'] == 'GL' and _ok(lead.get('/api/lab'))['can_change'] is True
    assert ana.put('/api/lab', json={'code': 'GARD'}).status_code == 403
    assert lead.put('/api/lab', json={'code': '1X'}).status_code == 400
    assert _ok(lead.put('/api/lab', json={'code': 'gard'}))['code'] == 'GARD'

    a1 = _line(ana, 'Col-0')
    a2 = _line(ana, 'Ler-0')
    z1 = _line(zoe, 'Col-0')
    g1 = _line(gil, 'Col-0')
    assert (a1['code'], a2['code']) == ('GARD-L-0001', 'GARD-L-0002')
    assert z1['code'] == 'OL-L-0001', 'Other Lab numbers from 1 too'
    assert g1['code'] == 'GL-L-0001', 'Green Lab gets GL now that Gardiner Lab is GARD'
    # Once a lab has records, its code is fixed.
    lab = _ok(lead.get('/api/lab'))
    assert lab['fixed'] is True and lab['can_change'] is False
    assert lead.put('/api/lab', json={'code': 'GDL'}).status_code == 400
    # A code another lab holds cannot be taken.
    assert as_user('boss').put('/api/lab', json={'code': 'OL'}).status_code == 400

    lot = _lot(ana, a1['code'])
    plants = _ok(ana.post(f"/api/lots/{lot['code']}/sow", json={'count': 2}), 201)['record']['plants']
    assert lot['code'] == 'GARD-S-0001' and [p['code'] for p in plants] == ['GARD-P-0001', 'GARD-P-0002']
    # Codes are found however they are typed, and the kind is read from them.
    assert _ok(ana.get('/api/lot/gard-s-0001'))['record']['code'] == 'GARD-S-0001'
    from app import records
    assert [records.kind_of(c) for c in ('GARD-S-0001', 'GL-P-0002', 'L-0003', 'X')] == ['lot', 'plant', 'line', None]
    assert _ok(ana.get('/api/search?q=GARD-S-0001'))['results'][0]['code'] == 'GARD-S-0001'


def test_initials_clash_between_labs_is_resolved(as_user, world):
    import sqlite3
    conn = sqlite3.connect(world['paths']['suite'])
    conn.execute("INSERT INTO labs VALUES (3, 'Green Lab')")
    conn.execute("INSERT INTO members VALUES ('gil', 3, 'member')")
    conn.commit()
    conn.close()
    conn = sqlite3.connect(world['paths']['moclo'])
    conn.execute("INSERT INTO users VALUES ('gil', 'gil', 0)")
    conn.commit()
    conn.close()
    first = _line(as_user('ana'), 'Col-0')['code']
    second = _line(as_user('gil'), 'Col-0')['code']
    assert (first, second) == ('GL-L-0001', 'GL2-L-0001')


def test_codes_made_before_lab_codes_still_work(as_user, world):
    import sqlite3
    ana = as_user('ana')
    line = _line(ana, 'Col-0')
    conn = sqlite3.connect(world['paths']['seeds'])
    conn.execute("UPDATE lines SET code = 'L-0007' WHERE id = ?", (line['id'],))
    conn.commit()
    conn.close()
    assert _ok(ana.get('/api/line/L-0007'))['record']['name'] == 'Col-0'
    assert _lot(ana, 'L-0007')['line']['code'] == 'L-0007'


def test_someone_in_two_labs_sees_both_and_chooses_where_new_records_go(as_user, world):
    import sqlite3
    conn = sqlite3.connect(world['paths']['suite'])
    conn.executescript("""
        CREATE TABLE lab_members (username TEXT, lab_id INTEGER, role TEXT, lab_admin INTEGER DEFAULT 0,
                                  joined_at TEXT, PRIMARY KEY (username, lab_id));
        INSERT INTO lab_members (username, lab_id, role, joined_at)
            SELECT username, lab_id, role, '1' FROM members;
        INSERT INTO lab_members (username, lab_id, role, joined_at) VALUES ('zoe', 1, 'lab_lead', '9');
    """)
    conn.commit()
    ana, zoe = as_user('ana'), as_user('zoe')
    gardiner = _line(ana, 'Col-0 35S::GFP')
    me = zoe.get('/api/me').get_json()
    assert me['labs'] == ['Other Lab', 'Gardiner Lab'] and me['lab'] == 'Other Lab'
    # Zoe sees Gardiner Lab's records as well as her own lab's.
    assert zoe.get(f"/api/line/{gardiner['code']}").status_code == 200
    # A new line goes to the lab chosen, of hers; her first lab without a choice; never another's.
    chosen = _line(zoe, 'Ler pER8', lab='Gardiner Lab')
    assert chosen['lab'] == 'Gardiner Lab'
    assert _line(zoe, 'Ler wild type')['lab'] == 'Other Lab'
    assert zoe.post('/api/lines', json={'name': 'x', 'species': 'Arabidopsis thaliana', 'lab': 'Smith Lab'}).status_code == 400
    # A lot of a Gardiner Lab line is Gardiner Lab's.
    lot = zoe.post('/api/lots', json={'line': chosen['code'], 'generation': 'T1'}).get_json()['record']
    assert lot['lab'] == 'Gardiner Lab'
    # She leads Gardiner Lab, not Other Lab: its code is hers to see, not to choose.
    assert zoe.get('/api/lab?lab=Gardiner Lab').get_json()['lab'] == 'Gardiner Lab'
    assert zoe.get('/api/lab').get_json()['can_change'] is False or zoe.get('/api/lab').get_json()['fixed']
    assert zoe.put('/api/lab', json={'code': 'OTH', 'lab': 'Other Lab'}).status_code == 403
