import os
import sqlite3
import tempfile

import pytest

os.environ['SEEDS_NO_APP'] = '1'


def _make(path, script, rows=()):
    conn = sqlite3.connect(path)
    conn.executescript(script)
    for sql, args in rows:
        conn.execute(sql, args)
    conn.commit()
    conn.close()


@pytest.fixture()
def world(monkeypatch):
    """A seed bank beside a suite: two labs with a lead each, an admin, the editor, a notebook and Lab Stocks."""
    d = tempfile.mkdtemp()
    paths = {k: os.path.join(d, f'{k}.db') for k in ('seeds', 'moclo', 'suite', 'editor', 'notebook', 'stocks')}
    _make(paths['moclo'], 'CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT UNIQUE, is_admin INTEGER DEFAULT 0);',
          [('INSERT INTO users VALUES (?, ?, ?)', (u, u, 1 if u == 'boss' else 0))
           for u in ('ana', 'ben', 'lead', 'boss', 'zoe', 'loner')])
    _make(paths['suite'],
          'CREATE TABLE labs (id INTEGER PRIMARY KEY, name TEXT);'
          'CREATE TABLE members (username TEXT PRIMARY KEY, lab_id INTEGER, role TEXT);',
          [('INSERT INTO labs VALUES (1, ?)', ('Gardiner Lab',)), ('INSERT INTO labs VALUES (2, ?)', ('Other Lab',))]
          + [('INSERT INTO members VALUES (?, ?, ?)', m) for m in
             [('ana', 1, 'member'), ('ben', 1, 'member'), ('lead', 1, 'lab_lead'), ('zoe', 2, 'member')]])
    _make(paths['editor'],
          'CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT);'
          'CREATE TABLE sequences (id TEXT PRIMARY KEY, name TEXT, sequence TEXT, shared INTEGER, owner_id TEXT, '
          'confirmed_at TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);',
          [('INSERT INTO users VALUES (?, ?)', ('ana', 'ana'))]
          + [('INSERT INTO sequences (id, name, sequence, shared, owner_id) VALUES (?, ?, ?, ?, ?)', s)
             for s in [('p1', 'pGreen-35S-GFP', 'ACGT' * 100, 1, 'ana'), ('p2', 'pPrivate', 'ACGT', 0, 'ana')]])
    _make(paths['notebook'],
          'CREATE TABLE notes (id TEXT PRIMARY KEY, title TEXT, type TEXT, owner TEXT, updated_at TEXT, deleted_at TEXT);'
          'CREATE TABLE links (note_id TEXT, target_type TEXT, target_id TEXT);')
    _make(paths['stocks'],
          'CREATE TABLE glycerol (id TEXT PRIMARY KEY, code TEXT, lab TEXT, plasmid_id TEXT, plasmid_name TEXT, '
          'clone TEXT, host TEXT, location TEXT, status TEXT, deleted_at TEXT);')
    for key, env in (('seeds', 'SEEDS_DATABASE_PATH'), ('moclo', 'MOCLO_DATABASE_PATH'), ('suite', 'SUITE_DATABASE_PATH'),
                     ('editor', 'EDITOR_DATABASE_PATH'), ('notebook', 'NOTEBOOK_DATABASE_PATH'),
                     ('stocks', 'STOCKS_DATABASE_PATH')):
        monkeypatch.setenv(env, paths[key])
    from app.main import create_app
    app = create_app()
    app.testing = True
    return {'app': app, 'paths': paths}


@pytest.fixture()
def as_user(world):
    def make(username):
        client = world['app'].test_client()
        client.environ_base['HTTP_X_SUITE_USER'] = username
        return client
    return make
