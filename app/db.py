"""
The seed bank's database.

    lines         a genetic identity: wild type, mutant, a transgenic event, a cross
    lots          seeds of a line and generation, with where they are kept
    plants        one plant sown from a lot, numbered within its sowing: where it grows
                  (a place, and a position in it) and under which treatment
    places        where plants grow: a lab's growth chambers, greenhouses and rooms, with
                  their conditions
    observations  what was seen on a plant, lot or line (a phenotype), with when and who;
                  a measurement keeps its number and unit, for summaries
    seg_tests     selection-plate counts on a lot, for segregation (3:1, 15:1, homozygous)
    line_parents  the lines a line came from: a cross's mother and father, a
                  transformant's background
    line_plasmids the plasmids a line carries, from the Plasmid Editor's library
    attachments   photos, 3D scans and files on any record
    changes       who changed what, and when, on every record

Records belong to a lab: everyone in it sees and adds to them, other labs do
not see them. Codes start with the lab's own code and say what they are:
GL-L-0001 a line, GL-S-0001 a seed lot, GL-P-0001 a plant; short enough for a
label, and never the same in two labs. (Codes made before lab codes, S-0001,
keep working.)
"""

import os
import sqlite3
from typing import Optional

_path: Optional[str] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS lines (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    lab TEXT,
    name TEXT NOT NULL,
    species TEXT NOT NULL DEFAULT '',
    background TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'other',
    description TEXT NOT NULL DEFAULT '',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lots (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    lab TEXT,
    line_id TEXT NOT NULL,
    generation TEXT NOT NULL DEFAULT '',
    from_plant_id TEXT,
    father_plant_id TEXT,
    source TEXT NOT NULL DEFAULT '',
    harvested_on TEXT,
    amount TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    germination REAL,
    zygosity TEXT NOT NULL DEFAULT '',
    used_up INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_lots_line ON lots(line_id);
CREATE INDEX IF NOT EXISTS idx_lots_plant ON lots(from_plant_id);

CREATE TABLE IF NOT EXISTS plants (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    lab TEXT,
    lot_id TEXT NOT NULL,
    line_id TEXT NOT NULL,
    number INTEGER NOT NULL,
    sown_on TEXT,
    location TEXT NOT NULL DEFAULT '',
    zygosity TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'growing',
    selected INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_plants_lot ON plants(lot_id);
CREATE INDEX IF NOT EXISTS idx_plants_line ON plants(line_id);

CREATE TABLE IF NOT EXISTS places (
    id TEXT PRIMARY KEY,
    lab TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'growth chamber',
    conditions TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_places_lab ON places(lab);

CREATE TABLE IF NOT EXISTS line_parents (
    line_id TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (line_id, parent_id, role)
);

CREATE TABLE IF NOT EXISTS line_plasmids (
    line_id TEXT NOT NULL,
    plasmid_id TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (line_id, plasmid_id)
);
CREATE INDEX IF NOT EXISTS idx_line_plasmids ON line_plasmids(plasmid_id);

CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    record_kind TEXT NOT NULL,
    record_id TEXT NOT NULL,
    observed_on TEXT,
    trait TEXT NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_observations_record ON observations(record_kind, record_id);

CREATE TABLE IF NOT EXISTS seg_tests (
    id TEXT PRIMARY KEY,
    lot_id TEXT NOT NULL,
    tested_on TEXT,
    selection TEXT NOT NULL DEFAULT '',
    resistant INTEGER NOT NULL,
    sensitive INTEGER NOT NULL,
    expected TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_seg_tests_lot ON seg_tests(lot_id);

CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    record_kind TEXT NOT NULL,
    record_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    mime TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    data BLOB NOT NULL,
    caption TEXT NOT NULL DEFAULT '',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    deleted_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_attachments_record ON attachments(record_kind, record_id);

CREATE TABLE IF NOT EXISTS changes (
    record_kind TEXT NOT NULL,
    record_id TEXT NOT NULL,
    changed_by TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    what TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_changes_record ON changes(record_kind, record_id);

-- The next number for each kind of code, per lab ("GL-S" for Gardiner Lab's seed lots).
CREATE TABLE IF NOT EXISTS counters (
    prefix TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);

-- Each lab's code, which starts every code it makes: GL-S-0001. Unique, so no
-- two labs' codes can be the same; fixed once the lab has records, as codes
-- on printed labels never change.
CREATE TABLE IF NOT EXISTS lab_codes (
    lab TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    set_by TEXT,
    set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def set_path(path: str) -> None:
    global _path
    _path = path


def path() -> str:
    return _path or os.environ.get('SEEDS_DATABASE_PATH', '/seeds/seeds.db')


class _Connection:
    def __enter__(self) -> sqlite3.Connection:
        conn = sqlite3.connect(path(), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA busy_timeout = 10000')
        self.conn = conn
        return conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()
        return False


def connect() -> _Connection:
    return _Connection()


# A line's biosafety, stock center and genetics, as the GMO register (and
# eLabJournal's Plant Seed type) asks: added to databases from before them.
LINE_ADDED = ['permit', 'biosafety', 'gmo_type', 'accession', 'collection', 'stock_center_number', 'stock_center_url',
              'selection_marker', 'gene_expression', 'mutation_info', 'construction']
# Where a plant grows and how it is treated, and a measurement's number and
# unit: added to databases from before them. (table, column, declaration)
ADDED = [('plants', 'place_id', 'TEXT'), ('plants', 'treatment', "TEXT NOT NULL DEFAULT ''"),
         ('observations', 'number', 'REAL'), ('observations', 'unit', "TEXT NOT NULL DEFAULT ''")]


def initialize(db_path: Optional[str] = None) -> None:
    if db_path:
        set_path(db_path)
    directory = os.path.dirname(path())
    if directory:
        os.makedirs(directory, exist_ok=True)
    with connect() as conn:
        # The ordinary rollback journal, not WAL: the suite's backup reads the
        # database from a read-only mount, where SQLite cannot open WAL.
        conn.execute('PRAGMA journal_mode = DELETE')
        conn.executescript(SCHEMA)
        have = {r[1] for r in conn.execute('PRAGMA table_info(lines)')}
        for column in LINE_ADDED:
            if column not in have:
                conn.execute(f"ALTER TABLE lines ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        for table, column, declaration in ADDED:
            if column not in {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {declaration}')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_plants_place ON plants(place_id)')
