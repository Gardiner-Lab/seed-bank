"""The seed bank's JSON API, under /api."""

from functools import wraps
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from app import attachments, people, records, sources, stats

api = Blueprint('api', __name__)


def signed_in(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        person = people.current()
        if person is None:
            return jsonify({'error': 'Sign in through the lab suite first'}), 401
        try:
            return view(person, *args, **kwargs)
        except records.Forbidden as exc:
            return jsonify({'error': str(exc)}), 403
        except records.NotFound as exc:
            return jsonify({'error': str(exc)}), 404
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
    return wrapper


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _kind(kind: str) -> str:
    if kind not in records.TABLE:
        raise records.NotFound('No such kind of record')
    return kind


@api.get('/me')
@signed_in
def me(person):
    return jsonify({'person': person.to_dict(), 'lab': records.lab_of(person), 'labs': records.labs_of(person),
                    'kinds': records.LINE_KINDS, 'zygosity': records.ZYGOSITY,
                    'line_options': {'biosafety': records.BIOSAFETY, 'gmo_types': records.GMO_TYPES,
                                     'gene_expression': records.GENE_EXPRESSION, 'permits': records.PERMITS,
                                     'collections': records.COLLECTIONS},
                    'plant_status': records.PLANT_STATUS, 'parent_roles': records.PARENT_ROLES,
                    'ratios': list(stats.RATIOS)})


@api.get('/lab')
@signed_in
def get_lab(person):
    return jsonify(records.lab_info(person, request.args.get('lab')))


@api.put('/lab')
@signed_in
def put_lab(person):
    return jsonify(records.set_lab_code(person, str(_body().get('code') or ''), _body().get('lab')))


@api.get('/lines')
@signed_in
def list_lines(person):
    return jsonify({'lines': records.list_lines(person, request.args.get('q', ''))})


@api.get('/lots')
@signed_in
def list_lots(person):
    return jsonify({'lots': records.list_lots(person, request.args.get('q', ''))})


@api.get('/plants')
@signed_in
def list_plants(person):
    return jsonify({'plants': records.list_plants(person, request.args.get('q', ''))})


@api.get('/search')
@signed_in
def search(person):
    return jsonify({'results': records.search(person, request.args.get('q', ''))})


@api.get('/<kind>/<ident>')
@signed_in
def get_record(person, kind, ident):
    record = records.detail(person, _kind(kind), ident)
    record['mentions'] = sources.notebook_mentions(person, record['code'])
    return jsonify({'record': record})


@api.post('/lines')
@signed_in
def create_line(person):
    line_id = records.create_line(person, _body())
    return jsonify({'record': records.line_detail(person, line_id)}), 201


@api.put('/lines/<ident>')
@signed_in
def update_line(person, ident):
    data = _body()
    records.update_line(person, ident, data)
    if 'plasmids' in data:
        records.set_plasmids(person, ident, data['plasmids'])
    if 'parents' in data:
        records.set_parents(person, ident, data['parents'])
    return jsonify({'record': records.line_detail(person, ident)})


@api.post('/lots')
@signed_in
def create_lot(person):
    lot_id = records.create_lot(person, _body())
    return jsonify({'record': records.lot_detail(person, lot_id)}), 201


@api.put('/lots/<ident>')
@signed_in
def update_lot(person, ident):
    records.update_lot(person, ident, _body())
    return jsonify({'record': records.lot_detail(person, ident)})


@api.post('/lots/<ident>/sow')
@signed_in
def sow(person, ident):
    made = records.sow(person, ident, _body())
    return jsonify({'record': records.lot_detail(person, ident), 'plants': len(made)}), 201


@api.post('/lots/<ident>/seg-tests')
@signed_in
def add_seg_test(person, ident):
    records.add_seg_test(person, ident, _body())
    return jsonify({'record': records.lot_detail(person, ident)}), 201


@api.delete('/seg-tests/<test_id>')
@signed_in
def remove_seg_test(person, test_id):
    records.remove_seg_test(person, test_id)
    return jsonify({'ok': True})


@api.get('/segregation')
@signed_in
def segregation(person):
    """Work a test out before saving it, as counts are typed."""
    try:
        r, s = int(request.args.get('resistant', 0)), int(request.args.get('sensitive', 0))
    except ValueError:
        raise ValueError('Counts are whole numbers')
    expected = request.args.get('expected', '3:1')
    if expected not in stats.RATIOS:
        raise ValueError('Unknown ratio')
    return jsonify(stats.assess(max(0, r), max(0, s), expected))


@api.put('/plants/<ident>')
@signed_in
def update_plant(person, ident):
    records.update_plant(person, ident, _body())
    return jsonify({'record': records.plant_detail(person, ident)})


@api.post('/plants/<ident>/harvest')
@signed_in
def harvest(person, ident):
    lot_id = records.harvest(person, ident, _body())
    return jsonify({'record': records.lot_detail(person, lot_id)}), 201


@api.post('/plants/<ident>/cross')
@signed_in
def cross(person, ident):
    data = _body()
    made = records.cross(person, ident, str(data.get('father') or ''), data)
    return jsonify({'record': records.lot_detail(person, made['lot'])}), 201


@api.post('/plants/<ident>/found-line')
@signed_in
def found_line(person, ident):
    line_id = records.found_line(person, ident, _body())
    return jsonify({'record': records.line_detail(person, line_id)}), 201


@api.post('/<kind>/<ident>/observations')
@signed_in
def add_observation(person, kind, ident):
    obs_id = records.add_observation(person, _kind(kind), ident, _body())
    return jsonify({'record': records.detail(person, kind, ident), 'id': obs_id}), 201


@api.delete('/observations/<obs_id>')
@signed_in
def remove_observation(person, obs_id):
    records.remove_observation(person, obs_id)
    return jsonify({'ok': True})


@api.delete('/<kind>/<ident>')
@signed_in
def delete_record(person, kind, ident):
    records.delete(person, _kind(kind), ident)
    return jsonify({'ok': True})


@api.post('/<kind>/<ident>/attachments')
@signed_in
def add_attachments(person, kind, ident):
    files = [(f.filename or 'file', f.read(attachments.MAX_BYTES + 1)) for f in request.files.getlist('file')]
    return jsonify({'attachments': attachments.add(person, kind, ident, files, request.form.get('caption', ''))}), 201


@api.get('/attachments/<att_id>')
@signed_in
def get_attachment(person, att_id):
    found = attachments.fetch(person, att_id)
    shown = (found['inline'] or found['preview']) and request.args.get('download') is None
    response = Response(found['data'], mimetype=attachments.sent_as(found['mime']))
    response.headers['Content-Disposition'] = (f"{'inline' if shown else 'attachment'}; "
                                               f"filename*=UTF-8''{quote(found['filename'])}")
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = ("default-src 'none'" if found['preview'] and shown
                                                    else "default-src 'none'; sandbox")
    response.headers['Cache-Control'] = 'private, max-age=86400'
    response.headers['ETag'] = found['sha256']
    return response


@api.delete('/attachments/<att_id>')
@signed_in
def remove_attachment(person, att_id):
    attachments.remove(person, att_id)
    return jsonify({'ok': True})


@api.get('/plasmids')
@signed_in
def find_plasmids(person):
    return jsonify({'plasmids': sources.plasmids(person, request.args.get('q', ''))})


@api.get('/plasmids/<plasmid_id>/lines')
@signed_in
def plasmid_lines(person, plasmid_id):
    return jsonify({'lines': records.lines_with_plasmid(person, plasmid_id)})
