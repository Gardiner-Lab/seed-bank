"""
Photos, 3D scans and files on lines, seed lots, plants and phenotype records.

Kept in the seed bank's database, so the suite's backup takes them along.
Whoever can see a record sees its files, and whoever can change it adds them.
Photos in common formats are shown in the page; 3D models (STL, PLY, OBJ, glTF)
open in the page's 3D viewer, which reads them as data; PDFs open in the
browser's viewer. Everything else downloads, and types a browser could run as
a page are sent as plain bytes. Removing a file hides it but keeps it.
"""

import hashlib
import mimetypes
import re
import secrets
from typing import Dict, List

from app import records
from app.db import connect
from app.people import Person

MAX_BYTES = 100 * 1024 * 1024          # 3D scans are large
INLINE_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp'}
PREVIEW_TYPES = {'application/pdf'}
RISKY = ('text/html', 'application/xhtml', 'image/svg', 'text/xml', 'application/xml',
         'text/javascript', 'application/javascript', 'application/x-javascript')
MODEL_EXTENSIONS = {'.stl': 'model/stl', '.ply': 'model/ply', '.obj': 'model/obj',
                    '.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json'}
KINDS = [('pdf', ('application/pdf',)), ('3d', ('model/',)),
         ('word', ('msword', 'wordprocessingml', 'opendocument.text', 'rtf')),
         ('powerpoint', ('powerpoint', 'presentationml', 'opendocument.presentation')),
         ('excel', ('excel', 'spreadsheetml', 'opendocument.spreadsheet', 'text/csv', 'tab-separated')),
         ('archive', ('zip', 'x-7z', 'x-tar', 'gzip', 'x-rar')),
         ('sequence', ('genbank', 'x-snapgene', 'fasta')), ('text', ('text/',))]
RECORD_KINDS = ('line', 'lot', 'plant', 'observation')
_SIGNATURES = [(b'\x89PNG\r\n\x1a\n', 'image/png'), (b'\xff\xd8\xff', 'image/jpeg'), (b'GIF8', 'image/gif'),
               (b'BM', 'image/bmp')]
for _ext, _type in (('.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                    ('.pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'),
                    ('.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('.gb', 'chemical/x-genbank'), ('.dna', 'application/x-snapgene')):
    mimetypes.add_type(_type, _ext)


def _sniff(data: bytes, filename: str) -> str:
    for magic, kind in _SIGNATURES:
        if data.startswith(magic):
            return kind
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    if data.startswith(b'%PDF-'):
        return 'application/pdf'
    ext = ('.' + filename.rsplit('.', 1)[-1].lower()) if '.' in filename else ''
    if ext in MODEL_EXTENSIONS:
        return MODEL_EXTENSIONS[ext]
    guessed = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    return 'application/octet-stream' if guessed in INLINE_TYPES | PREVIEW_TYPES else guessed


def kind(mime: str) -> str:
    if mime in INLINE_TYPES:
        return 'image'
    for name, marks in KINDS:
        if any(m in mime for m in marks):
            return name
    return 'file'


def sent_as(mime: str) -> str:
    return 'application/octet-stream' if mime.startswith(RISKY) else mime


def _summary(row) -> dict:
    return {'id': row['id'], 'filename': row['filename'], 'mime': row['mime'], 'size': row['size'],
            'kind': kind(row['mime']), 'image': row['mime'] in INLINE_TYPES,
            'preview': row['mime'] in PREVIEW_TYPES, 'model': row['mime'].startswith('model/'),
            'caption': row['caption'], 'created_by': row['created_by'], 'created_at': row['created_at']}


def listed(conn, record_kind: str, record_id: str) -> List[dict]:
    return [_summary(r) for r in conn.execute(
        'SELECT id, filename, mime, size, caption, created_by, created_at FROM attachments '
        'WHERE record_kind = ? AND record_id = ? AND deleted_at IS NULL ORDER BY created_at, rowid',
        (record_kind, record_id))]


def _owner(conn, person: Person, record_kind: str, record_id: str):
    """The record a file hangs on, checked visible; an observation through its record."""
    if record_kind not in RECORD_KINDS:
        raise ValueError('Files go on a line, seed lot, plant or observation')
    if record_kind == 'observation':
        obs = conn.execute('SELECT * FROM observations WHERE id = ? AND deleted_at IS NULL', (record_id,)).fetchone()
        if obs is None:
            raise records.NotFound('No such observation')
        records.visible(conn, person, obs['record_kind'], obs['record_id'])
        return obs['id'], obs['record_kind'], obs['record_id']
    row = records.visible(conn, person, record_kind, record_id)
    return row['id'], record_kind, row['id']


def add(person: Person, record_kind: str, record_ident: str, files: List[tuple], caption: str = '') -> List[dict]:
    if not files:
        raise ValueError('Choose a file to attach')
    added = []
    with connect() as conn:
        owner_id, log_kind, log_id = _owner(conn, person, record_kind, record_ident)
        for filename, data in files:
            name = re.sub(r'[\x00-\x1f/\\]', '_', (filename or '').strip())[:200] or 'file'
            if not data:
                raise ValueError(f'{name} is empty')
            if len(data) > MAX_BYTES:
                raise ValueError(f'{name} is larger than {MAX_BYTES // (1024 * 1024)} MB')
            att_id = secrets.token_hex(12)
            conn.execute('INSERT INTO attachments (id, record_kind, record_id, filename, mime, size, sha256, data, '
                         'caption, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         (att_id, record_kind, owner_id, name, _sniff(data, name), len(data),
                          hashlib.sha256(data).hexdigest(), data, (caption or '').strip()[:300], person.username))
            added.append(att_id)
        records._log(conn, log_kind, log_id, person.username,
                     f'attached {", ".join(n for n, _ in files)[:200]}')
        return [a for a in listed(conn, record_kind, owner_id) if a['id'] in added]


def fetch(person: Person, att_id: str) -> Dict:
    with connect() as conn:
        row = conn.execute('SELECT * FROM attachments WHERE id = ?', (att_id,)).fetchone()
        if row is None:
            raise records.NotFound('No such file')
        _owner_any(conn, person, row)
    return {'data': bytes(row['data']), 'mime': row['mime'], 'filename': row['filename'],
            'inline': row['mime'] in INLINE_TYPES, 'preview': row['mime'] in PREVIEW_TYPES, 'sha256': row['sha256']}


def _owner_any(conn, person: Person, row) -> None:
    """Visible to whoever sees the record, even one since removed (its files stay readable)."""
    kind_, rid = row['record_kind'], row['record_id']
    if kind_ == 'observation':
        obs = conn.execute('SELECT record_kind, record_id FROM observations WHERE id = ?', (rid,)).fetchone()
        if obs is None:
            raise records.NotFound('No such file')
        kind_, rid = obs['record_kind'], obs['record_id']
    rec = conn.execute(f'SELECT lab FROM {records.TABLE[kind_]} WHERE id = ?', (rid,)).fetchone()
    if rec is None or not records.can_see(person, rec):
        raise records.NotFound('No such file')


def remove(person: Person, att_id: str) -> None:
    with connect() as conn:
        row = conn.execute('SELECT * FROM attachments WHERE id = ? AND deleted_at IS NULL', (att_id,)).fetchone()
        if row is None:
            raise records.NotFound('No such file')
        _, log_kind, log_id = _owner(conn, person, row['record_kind'], row['record_id'])
        conn.execute('UPDATE attachments SET deleted_at = CURRENT_TIMESTAMP, deleted_by = ? WHERE id = ?',
                     (person.username, att_id))
        records._log(conn, log_kind, log_id, person.username, f'removed {row["filename"]}')
