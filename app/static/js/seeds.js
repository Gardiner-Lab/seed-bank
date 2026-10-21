'use strict';
/*
 * The Seed Bank page: lists of lines, seed lots and plants, and a page for
 * each, with what can be done to it (sow, harvest, cross, test, photograph).
 * Addresses: #lines, #lots, #plants, #line=L-0001, #lot=S-0001, #plant=P-0001.
 */

const SB = window.SB;
const url = (path) => `${SB.base}${path}`;

/* --- helpers ------------------------------------------------------------------ */

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'style') node.setAttribute('style', value);
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else if (key in node && typeof value !== 'string') node[key] = value;
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function put(node, ...children) {
  node.replaceChildren(...children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false)
    .map((c) => (c instanceof Node ? c : document.createTextNode(String(c)))));
  return node;
}

async function api(method, path, body, form) {
  const res = await fetch(url(`/api${path}`), {
    method, credentials: 'same-origin',
    headers: form || body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: form || (body === undefined ? undefined : JSON.stringify(body)),
  });
  let data = {};
  try { data = await res.json(); } catch (e) { /* not JSON */ }
  if (!res.ok) {
    const err = new Error(data.error || (res.status === 413 ? 'Too large to send at once' : `${res.status} ${res.statusText}`));
    err.status = res.status;
    throw err;
  }
  return data;
}

function toast(message, kind = 'info', ms = 3500) {
  const box = el('div', { class: `toast toast-${kind}` }, message);
  document.getElementById('toasts').append(box);
  setTimeout(() => box.remove(), ms);
}

function modal({ title, build, buttons = [{ label: 'Close', kind: 'secondary' }], wide = false, onClose }) {
  const body = el('div', { class: 'modal-body' });
  const backdrop = el('div', { class: 'modal-backdrop' });
  let closed = false;
  const close = () => { if (closed) return; closed = true; backdrop.remove(); onClose?.(); };
  const foot = el('div', { class: 'modal-foot' }, buttons.map((b) => el('button', {
    class: `btn ${b.kind === 'secondary' ? 'btn-secondary' : b.kind === 'danger' ? 'btn-danger' : 'btn-primary'}`,
    type: 'button',
    onclick: async (ev) => {
      const btn = ev.currentTarget;
      btn.disabled = true;
      try {
        const keep = await b.onClick?.({ close, body });
        if (keep !== false) close();
      } catch (err) {
        toast(err.message, 'error', 6000);
      } finally {
        btn.disabled = false;
      }
    },
  }, b.label)));
  backdrop.append(el('div', { class: `modal ${wide ? 'modal-wide' : ''}`, role: 'dialog' },
    el('div', { class: 'modal-head' }, el('span', { class: 'modal-title', text: title }),
      el('button', { class: 'icon-btn', title: 'Close', onclick: close }, '✕')),
    body, foot));
  backdrop.addEventListener('mousedown', (e) => { if (e.target === backdrop) close(); });
  document.body.append(backdrop);
  build?.(body, close);
  return { close, body };
}

/**
 * A dialog with a form. fields: [{name, label, type, value, options, placeholder, hint}].
 * submit(values) runs on the main button; returning false keeps the dialog open.
 */
function formModal({ title, intro, fields, submit, label = 'Save', wide = false }) {
  const inputs = {};
  modal({
    title, wide,
    build: (body) => {
      if (intro) body.append(el('p', { class: 'hint' }, intro));
      for (const f of fields) {
        let input;
        if (f.type === 'select') {
          input = el('select', {}, f.options.map((o) => {
            const [value, text] = Array.isArray(o) ? o : [o, o || '—'];
            return el('option', { value, selected: String(f.value ?? '') === String(value) }, text);
          }));
        } else if (f.type === 'textarea') {
          input = el('textarea', { rows: 3, placeholder: f.placeholder || '' });
          input.value = f.value ?? '';
        } else if (f.type === 'checkbox') {
          input = el('input', { type: 'checkbox', checked: !!f.value });
        } else {
          input = el('input', { type: f.type || 'text', placeholder: f.placeholder || '', list: f.list || null });
          input.value = f.value ?? '';
          if (f.min !== undefined) input.min = f.min;
          if (f.max !== undefined) input.max = f.max;
          if (f.step !== undefined) input.step = f.step;
        }
        inputs[f.name] = input;
        body.append(el('label', { class: `field ${f.type === 'checkbox' ? 'field-check' : ''}` },
          el('span', { class: 'field-label' }, f.label), input, f.hint ? el('span', { class: 'hint' }, f.hint) : null));
      }
      setTimeout(() => body.querySelector('input, select, textarea')?.focus(), 0);
    },
    buttons: [{ label: 'Cancel', kind: 'secondary' }, {
      label,
      onClick: async () => {
        const values = {};
        for (const [k, input] of Object.entries(inputs)) values[k] = input.type === 'checkbox' ? input.checked : input.value.trim();
        return submit(values);
      },
    }],
  });
}

/** Search-as-you-type list in a dialog; resolves with the item chosen, or null. */
function picker({ title, placeholder, search, describe }) {
  return new Promise((resolve) => {
    let chosen = null;
    modal({
      title,
      onClose: () => resolve(chosen),
      build: (body, close) => {
        const input = el('input', { type: 'search', class: 'picker-input', placeholder });
        const list = el('ul', { class: 'picker-list' });
        let ticket = 0;
        const run = async () => {
          const mine = ++ticket;
          let items = [];
          try { items = await search(input.value.trim()); } catch (err) { toast(err.message, 'error'); }
          if (mine !== ticket) return;
          put(list, items.length ? items.map((item) => el('li', {
            class: 'picker-item', tabindex: '0',
            onclick: () => { chosen = item; close(); },
            onkeydown: (e) => { if (e.key === 'Enter') { chosen = item; close(); } },
          }, describe(item))) : el('li', { class: 'hint' }, 'Nothing found'));
        };
        input.addEventListener('input', run);
        body.append(input, list);
        setTimeout(() => input.focus(), 0);
        run();
      },
      buttons: [{ label: 'Cancel', kind: 'secondary' }],
    });
  });
}

function localTime(stamp) {
  if (!stamp) return '';
  const d = new Date(String(stamp).replace(' ', 'T') + (/[zZ]|[+-]\d\d:?\d\d$/.test(stamp) ? '' : 'Z'));
  if (Number.isNaN(d.getTime())) return String(stamp).slice(0, 16);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const today = () => new Date().toISOString().slice(0, 10);
const ICON = { line: '🧬', lot: '🫘', plant: '🌱' };
const KIND_NAME = { line: 'line', lot: 'seed lot', plant: 'plant' };
const FILE_ICONS = { pdf: '📕', word: '📝', powerpoint: '📽️', excel: '📊', archive: '🗜️', sequence: '🧬', text: '📄', '3d': '🧊', image: '🖼️', file: '📎' };
const fileUrl = (id, download = false) => url(`/api/attachments/${encodeURIComponent(id)}${download ? '?download' : ''}`);
const sizeLabel = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} kB`);
const link = (item) => (item ? el('a', { href: `#${item.kind}=${item.code}`, class: `rec-link rec-${item.kind}` },
  `${ICON[item.kind]} ${item.code}`, item.kind === 'line' ? ` ${item.name}` : item.kind === 'plant' ? ` #${item.number}` : '') : '—');
const TRAITS = ['germination', 'rosette size', 'leaf colour', 'leaf shape', 'flowering time', 'height', 'branching',
  'seed set', 'fluorescence (GFP)', 'resistance (Basta)', 'resistance (kanamycin)', 'genotype (PCR)', 'phenotype', 'note'];

/* --- the app ----------------------------------------------------------------- */

const App = {
  meta: null,
  selected: new Set(),

  async init() {
    try {
      this.meta = await api('GET', '/me');
      this.labPicker(this.meta.labs);
      await this.loadLab();
    } catch (err) {
      put(document.getElementById('main'), el('p', { class: 'empty' }, err.message));
      return;
    }
    document.body.append(el('datalist', { id: 'traits' }, TRAITS.map((t) => el('option', { value: t }))));
    const lo = this.meta.line_options;
    for (const [id, list] of [['permits', lo.permits], ['collections', lo.collections]]) {
      document.body.append(el('datalist', { id }, list.map((v) => el('option', { value: v }))));
    }
    window.addEventListener('hashchange', () => this.route());
    this.route();
  },

  route() {
    const hash = location.hash.slice(1) || 'lines';
    const record = hash.match(/^(line|lot|plant)=(.+)$/);
    for (const tab of document.querySelectorAll('.view-tab')) {
      tab.classList.toggle('active', tab.dataset.view === (record ? `${record[1]}s` : hash));
    }
    if (record) this.showRecord(record[1], decodeURIComponent(record[2]));
    else this.showList(['lines', 'lots', 'plants'].includes(hash) ? hash : 'lines');
  },

  /* lists ------------------------------------------------------------------------ */

  async showList(view) {
    const main = document.getElementById('main');
    const query = el('input', { type: 'search', class: 'list-search', value: this[`q_${view}`] || '',
      placeholder: { lines: 'Search lines by code, name, species, background or plasmid',
        lots: 'Search seed lots by code, line, generation, location or source',
        plants: 'Search plants by code, line, lot, location or status' }[view] });
    const table = el('div', { class: 'list' });
    const labelBtn = el('button', { class: 'btn btn-secondary', onclick: () => this.openLabels([...this.selected]) }, '🏷 Labels for selected');
    const draw = async () => {
      this[`q_${view}`] = query.value;
      const data = await api('GET', `/${view}?q=${encodeURIComponent(query.value)}`);
      put(table, this.listTable(view, data[view]));
      labelBtn.disabled = !this.selected.size;
    };
    let timer;
    query.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(draw, 250); });
    this.onSelection = () => { labelBtn.disabled = !this.selected.size; labelBtn.textContent = `🏷 Labels for selected${this.selected.size ? ` (${this.selected.size})` : ''}`; };
    put(main,
      el('div', { class: 'page-head' },
        el('h1', {}, { lines: '🧬 Lines', lots: '🫘 Seed lots', plants: '🌱 Plants' }[view]),
        el('span', { class: 'actions' },
          view === 'lines' ? el('button', { class: 'btn btn-primary', onclick: () => this.editLine() }, '＋ New line') : null,
          view === 'lots' ? el('button', { class: 'btn btn-primary', onclick: () => this.newLot() }, '＋ Seed lot') : null,
          labelBtn)),
      this.labCodeLine(),
      this.elabLine(),
      el('p', { class: 'hint' }, {
        lines: 'Wild types, mutants, transgenic events and crosses, with the plasmids they carry. Open one for its seed lots and pedigree.',
        lots: 'Seeds as they are kept. Sow plants from a lot; plants are harvested into the next generation.',
        plants: 'Each plant sown, numbered within its lot. Record phenotypes with photos; harvest, cross, or found a line.',
      }[view], ' ', el('a', { href: url('/help') }, 'How to enter things so they can be traced →')),
      query, table);
    await draw();
    this.onSelection();
    query.focus();
  },

  /** Which code this lab's records start with, and a way to choose it before the first one. */
  /**
   * Someone in several labs chooses which one new records go to (their first,
   * until they choose; remembered on this computer). They see all their labs' records.
   */
  chosenLab: null,
  labPicker(labs) {
    if (!labs || labs.length < 2) return;
    let kept = null;
    try { kept = localStorage.getItem('labChoice'); } catch (e) { /* private window */ }
    this.chosenLab = labs.includes(kept) ? kept : labs[0];
    const picker = el('select', { class: 'lab-picker', title: 'New records go to this lab; you see the records of all your labs',
      'aria-label': 'Lab for new records', onchange: async (e) => {
        this.chosenLab = e.target.value;
        try { localStorage.setItem('labChoice', this.chosenLab); } catch (e) { /* private window */ }
        await this.loadLab();
        this.route();
      } }, labs.map((l) => el('option', { value: l, selected: l === this.chosenLab }, l)));
    document.querySelector('.topbar-user')?.before(el('label', { class: 'lab-pick' }, 'New in ', picker));
  },

  /** The chosen lab's code, for the line above the lists. */
  async loadLab() {
    this.lab = await api('GET', this.chosenLab ? `/lab?lab=${encodeURIComponent(this.chosenLab)}` : '/lab');
  },

  labCodeLine() {
    const lab = this.lab;
    if (!lab) return null;
    return el('p', { class: 'lab-code-line' },
      'Codes in ', el('b', {}, lab.lab.startsWith('user:') ? 'your own stocks' : lab.lab), ' start with ',
      el('span', { class: 'code-badge' }, `${lab.code}-`), ` (${lab.code}-L lines, ${lab.code}-S seed lots, ${lab.code}-P plants)`,
      lab.can_change ? el('button', { class: 'btn btn-secondary btn-sm', style: 'margin-left:.6rem', onclick: () => formModal({
        title: 'Choose the lab code',
        intro: 'Every code your lab makes starts with it, so no two labs\' codes are ever the same. It can be chosen until the lab\'s first record; after that it is fixed, as codes on labels never change.',
        fields: [{ name: 'code', label: 'Lab code', value: lab.code, placeholder: 'e.g. GL, GARD', hint: '1 to 6 letters and digits, starting with a letter.' }],
        submit: async (v) => { this.lab = await api('PUT', '/lab', { ...v, lab: lab.lab }); this.route(); },
      }) }, 'Change…') : null);
  },

  /**
   * How far the lab's seed lots are copied to eLabJournal (Lab Stocks copies them there), and sending
   * them now. Empty when the lab does not copy its seed lots, or Lab Stocks is away.
   */
  elabLine() {
    const line = el('p', { class: 'lab-code-line elab-line' });
    const lab = this.lab?.lab;
    if (!lab) return null;
    const stocks = async (method, path, body) => {
      const res = await fetch(`${SB.stocks}/api/elab/seed-lots${path}`, { method, credentials: 'same-origin',
        headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `Lab Stocks: ${res.status}`);
      return data;
    };
    const draw = async () => {
      let s;
      try { s = await stocks('GET', `?lab=${encodeURIComponent(lab)}`); } catch (err) { return; }
      if (!s.copies) { put(line); return; }
      const failed = s.failed.length;
      put(line,
        'Seed lots copied to ', el('a', { href: s.url, target: '_blank', rel: 'noopener' }, 'eLabJournal'), ': ',
        `${s.synced} sent`, s.waiting ? `, ${s.waiting} waiting` : '',
        s.held ? el('span', { title: 'Archived in eLab (by someone there): no longer sent, and not made again' }, `, ${s.held} archived in eLab`) : '',
        failed ? el('a', { href: '#', class: 'elab-failed', onclick: (e) => {
          e.preventDefault();
          modal({ title: 'Not copied to eLabJournal', build: (body, close) => body.append(el('ul', { onclick: (ev) => { if (ev.target.closest('a')) close(); } },
            ...s.failed.map((f) => el('li', {}, link({ kind: 'lot', code: f.code }), ` ${f.error}`)))) });
        } }, `, ${failed} failed`) : '',
        s.last_error ? el('span', { class: 'elab-failed' }, ` — ${s.last_error}`) : '',
        el('button', { class: 'btn btn-secondary btn-sm', style: 'margin-left:.6rem',
          title: 'Send what changed to eLab now, not at the next round (every few minutes)', onclick: async (ev) => {
            ev.target.disabled = true;
            try { await stocks('POST', '/sync', { lab }); } catch (err) { toast(err.message, 'error', 6000); ev.target.disabled = false; return; }
            toast('Sending to eLabJournal', 'success');
            setTimeout(draw, 8000);
          } }, '⟳ Send now'),
        el('a', { href: SB.stocks, class: 'hint', style: 'margin-left:.6rem', title: 'eLab settings and bringing over from eLab are in Lab Stocks' }, 'eLab settings in Lab Stocks →'));
    };
    draw();
    return line;
  },

  pick(code) {
    return el('input', { type: 'checkbox', checked: this.selected.has(code), title: 'Choose for labels',
      onclick: (e) => e.stopPropagation(),
      onchange: (e) => { if (e.target.checked) this.selected.add(code); else this.selected.delete(code); this.onSelection?.(); } });
  },

  listTable(view, rows) {
    if (!rows.length) {
      return el('div', { class: 'empty' }, el('p', {}, 'Nothing here yet.'),
        el('p', {}, 'New to the seed bank? ', el('a', { href: url('/help') }, 'Read how to enter seeds, plants and lines'),
          ' first: it takes five minutes, and it is what makes the lineage work.'));
    }
    const head = {
      lines: ['', 'Code', 'Name', 'Kind', 'Species', 'Plasmids', 'Seed lots', 'Plants'],
      lots: ['', 'Code', 'Line', 'Gen.', 'From', 'Location', 'Amount', 'Zygosity', 'Germ.', 'Sown'],
      plants: ['', 'Code', 'Line', 'Lot', '#', 'Status', 'Zygosity', 'Location', 'Sown'],
    }[view];
    const kind = view.slice(0, -1);
    const cells = {
      lines: (r) => [r.name, r.line_kind, el('i', {}, r.species), r.plasmids, r.lots, r.plants],
      lots: (r) => [`${r.line}`, r.generation, r.from_plant || r.source || '—', r.location, r.amount,
        r.zygosity, r.germination !== null && r.germination !== undefined ? `${r.germination}%` : '', r.sown || ''],
      plants: (r) => [r.line, r.lot, `#${r.number}${r.selected ? ' ★' : ''}`, r.status, r.zygosity, r.location, r.sown_on || ''],
    }[view];
    return el('table', { class: 'data' },
      el('thead', {}, el('tr', {}, head.map((h) => el('th', {}, h)))),
      el('tbody', {}, rows.map((r) => el('tr', {
        class: `${r.used_up ? 'faded' : ''} clickable`, onclick: () => { location.hash = `${kind}=${r.code}`; },
      }, el('td', { class: 'pick' }, this.pick(r.code)), el('td', { class: 'code' }, r.code),
      cells(r).map((c) => el('td', {}, c))))));
  },

  openLabels(codes) {
    if (!codes.length) { toast('Tick the records to print labels for', 'error'); return; }
    window.open(url(`/labels?codes=${encodeURIComponent(codes.join(','))}`), '_blank', 'noopener');
  },

  /* one record -------------------------------------------------------------------- */

  async showRecord(kind, code) {
    const main = document.getElementById('main');
    let rec;
    try {
      rec = (await api('GET', `/${kind}/${encodeURIComponent(code)}`)).record;
    } catch (err) {
      put(main, el('p', { class: 'empty' }, err.message), el('a', { href: `#${kind}s` }, `All ${KIND_NAME[kind]}s`));
      return;
    }
    this.rec = rec;
    const view = { line: () => this.lineView(rec), lot: () => this.lotView(rec), plant: () => this.plantView(rec) }[kind]();
    put(main, view, this.observations(rec), this.files(rec.kind, rec.code, rec.attachments, 'Photos, 3D scans and files'),
      this.mentions(rec), this.history(rec));
  },

  reload() { this.showRecord(this.rec.kind, this.rec.code); },

  head(rec, title, subtitle, actions) {
    return el('div', { class: 'record-head' },
      el('div', {}, el('div', { class: 'crumbs' }, el('a', { href: `#${rec.kind}s` }, `${ICON[rec.kind]} All ${KIND_NAME[rec.kind]}s`)),
        el('h1', {}, el('span', { class: 'code-badge' }, rec.code), ' ', title),
        subtitle ? el('div', { class: 'hint' }, subtitle) : null),
      el('span', { class: 'actions' }, actions,
        el('button', { class: 'btn btn-secondary', title: 'A label with a QR code that opens this page',
          onclick: () => this.openLabels([rec.code]) }, '🏷 Label'),
        el('button', { class: 'btn btn-secondary', title: `Delete this ${KIND_NAME[rec.kind]}`, onclick: () => modal({
          title: `Delete ${rec.code}?`,
          build: (b) => b.append(el('p', {}, 'It is removed from the lists. Records that came from it keep it as their parent, ',
            'so a line, lot or plant that others descend from cannot be deleted.')),
          buttons: [{ label: 'Cancel', kind: 'secondary' }, { label: 'Delete', kind: 'danger', onClick: async () => {
            await api('DELETE', `/${rec.kind}/${rec.code}`);
            toast(`Deleted ${rec.code}`, 'success');
            location.hash = `${rec.kind}s`;
          } }],
        }) }, '🗑')));
  },

  facts(pairs) {
    return el('dl', { class: 'facts' }, pairs.filter(([, v]) => v !== null && v !== undefined && v !== '' && v !== false)
      .map(([k, v]) => [el('dt', {}, k), el('dd', {}, v)]));
  },

  section(title, ...content) {
    return el('section', { class: 'section' }, el('h2', {}, title), content);
  },

  /* lines */

  lineView(rec) {
    const tree = (node, role) => el('li', {}, role ? el('span', { class: 'role' }, role) : null, link(node),
      node.species ? el('span', { class: 'hint' }, ` ${node.line_kind || ''}`) : null,
      node.parents?.length ? el('ul', {}, node.parents.map((p) => tree(p, p.role))) : null);
    return el('div', {},
      this.head(rec, rec.name, [rec.line_kind, rec.species, rec.background && `background ${rec.background}`].filter(Boolean).join(' · '), [
        el('button', { class: 'btn btn-secondary', onclick: () => this.editLine(rec) }, '✎ Edit'),
        el('button', { class: 'btn btn-primary', onclick: () => this.newLot(rec) }, '＋ Seed lot')]),
      this.facts([['Kind', rec.line_kind], ['Species', rec.species && el('i', {}, rec.species)], ['Background', rec.background],
        ['Made by', `${rec.created_by || '—'} · ${localTime(rec.created_at)}`]]),
      rec.description ? el('p', { class: 'description' }, rec.description) : null,
      this.section('Biosafety and stock center', this.facts([
        ['Permit', rec.permit || el('span', { class: 'hint' }, 'the lab\'s')],
        ['Biosafety level', rec.biosafety || el('span', { class: 'hint' }, 'the lab\'s')],
        ['GMO type', rec.gmo_type], ['Gene expression', rec.gene_expression], ['Selection marker', rec.selection_marker],
        ['Mutation information', rec.mutation_info], ['Construction method', rec.construction],
        ['Stock center', [rec.collection, rec.stock_center_number].filter(Boolean).join(' ')],
        ['Accession', rec.accession],
        ['Stock center link', rec.stock_center_url ? el('a', { href: rec.stock_center_url, target: '_blank', rel: 'noopener' }, rec.stock_center_url) : null]])),
      this.section('Plasmids',
        rec.plasmids.length ? el('div', { class: 'chips' }, rec.plasmids.map((p) => el('a', {
          class: 'chip chip-plasmid', href: `${SB.editor}/editor?open=${encodeURIComponent(p.id)}`, target: '_blank', rel: 'noopener',
          title: 'Open in the Plasmid Editor' }, `🧬 ${p.name}`))) : el('p', { class: 'hint' }, 'No plasmid recorded.'),
        el('button', { class: 'btn btn-secondary btn-sm', onclick: () => this.editPlasmids(rec) }, 'Change plasmids…')),
      this.section('Pedigree',
        rec.pedigree?.parents?.length ? el('ul', { class: 'tree' }, tree(rec.pedigree)) : el('p', { class: 'hint' }, 'No parent lines recorded.'),
        rec.children.length ? el('p', {}, el('b', {}, 'Lines from it: '), rec.children.map((c, i) => [i ? ', ' : '', link(c), el('span', { class: 'hint' }, ` (${c.role})`)])) : null,
        el('button', { class: 'btn btn-secondary btn-sm', onclick: () => this.editParents(rec) }, 'Change parents…')),
      this.section(`Seed lots (${rec.lots.length})`,
        rec.lots.length ? el('table', { class: 'data' }, el('thead', {}, el('tr', {}, ['Code', 'Generation', 'Location'].map((h) => el('th', {}, h)))),
          el('tbody', {}, rec.lots.map((l) => el('tr', { class: 'clickable', onclick: () => { location.hash = `lot=${l.code}`; } },
            el('td', { class: 'code' }, l.code), el('td', {}, l.generation), el('td', {}, l.location)))))
          : el('p', { class: 'hint' }, 'No seed lots yet: add one, or harvest plants of this line.')));
  },

  editLine(rec) {
    const m = this.meta;
    formModal({
      title: rec ? `Edit ${rec.code}` : 'New line',
      intro: rec ? null : 'A genetic identity: a wild type or ecotype, a mutant, a transgenic event or population, a cross. Seed lots and plants belong to a line.',
      fields: [
        { name: 'name', label: 'Name', value: rec?.name, placeholder: 'e.g. Col-0, myb21-1, 35S:GFP-4' },
        { name: 'kind', label: 'Kind', type: 'select', options: m.kinds, value: rec?.line_kind || 'wild type' },
        { name: 'species', label: 'Species', value: rec?.species ?? 'Arabidopsis thaliana', list: null },
        { name: 'background', label: 'Background', value: rec?.background, placeholder: 'e.g. Col-0' },
        { name: 'description', label: 'Description', type: 'textarea', value: rec?.description },
        // Biosafety, stock center and genetics: for the GMO register (and eLab's Plant Seed).
        { name: 'permit', label: 'Permit', value: rec?.permit, list: 'permits', placeholder: 'empty: the lab\'s' },
        { name: 'biosafety', label: 'Biosafety level', type: 'select', value: rec?.biosafety,
          options: m.line_options.biosafety.map((v) => [v, v || '— the lab\'s —']) },
        { name: 'gmo_type', label: 'GMO type', type: 'select', value: rec?.gmo_type, options: m.line_options.gmo_types },
        { name: 'gene_expression', label: 'Gene expression', type: 'select', value: rec?.gene_expression,
          options: m.line_options.gene_expression },
        { name: 'selection_marker', label: 'Selection marker', value: rec?.selection_marker, placeholder: 'e.g. BASTA, Kanamycin' },
        { name: 'mutation_info', label: 'Mutation information', type: 'textarea', value: rec?.mutation_info },
        { name: 'construction', label: 'Construction method', type: 'textarea', value: rec?.construction },
        { name: 'collection', label: 'Stock center collection', value: rec?.collection, list: 'collections', placeholder: 'e.g. SALK, GABI' },
        { name: 'stock_center_number', label: 'Stock center number', value: rec?.stock_center_number, placeholder: 'e.g. SALK_012345C' },
        { name: 'accession', label: 'Accession', value: rec?.accession, placeholder: 'e.g. N12345, CGN13357' },
        { name: 'stock_center_url', label: 'Stock center link', value: rec?.stock_center_url, placeholder: 'https://…' },
      ],
      wide: true,
      submit: async (v) => {
        const res = rec ? await api('PUT', `/lines/${rec.code}`, v) : await api('POST', '/lines', { ...v, lab: this.chosenLab });
        if (rec) this.reload(); else location.hash = `line=${res.record.code}`;
        toast(rec ? 'Saved' : `Made ${res.record.code}`, 'success');
      },
    });
  },

  async editPlasmids(rec) {
    let chosen = rec.plasmids.map((p) => ({ ...p }));
    modal({
      title: `Plasmids in ${rec.code} ${rec.name}`, wide: true,
      build: (body) => {
        const list = el('div', { class: 'chips' });
        const draw = () => put(list, chosen.length ? chosen.map((p, i) => el('span', { class: 'chip chip-plasmid' }, `🧬 ${p.name} `,
          el('button', { class: 'chip-x', title: 'Remove', onclick: () => { chosen.splice(i, 1); draw(); } }, '×')))
          : el('span', { class: 'hint' }, 'None'));
        draw();
        body.append(el('p', { class: 'hint' }, 'From the Plasmid Editor\'s library. Crosses and lines founded from a plant take their parents\' plasmids.'),
          list, el('button', { class: 'btn btn-secondary btn-sm', onclick: async () => {
            const p = await picker({ title: 'Add a plasmid', placeholder: 'Search the plasmid library',
              search: async (q) => (await api('GET', `/plasmids?q=${encodeURIComponent(q)}`)).plasmids,
              describe: (x) => [el('b', { text: x.name }), el('span', { class: 'hint' }, ` · ${x.length.toLocaleString()} bp${x.owner ? ` · ${x.owner}` : ''}${x.confirmed ? ' · ✓ sequenced' : ''}`)] });
            if (p && !chosen.some((c) => c.id === p.id)) { chosen.push({ id: p.id, name: p.name }); draw(); }
          } }, '＋ Add a plasmid'));
      },
      buttons: [{ label: 'Cancel', kind: 'secondary' }, { label: 'Save', onClick: async () => {
        await api('PUT', `/lines/${rec.code}`, { plasmids: chosen });
        this.reload();
      } }],
    });
  },

  async editParents(rec) {
    const chosen = rec.parents.map((p) => ({ id: p.id, code: p.code, name: p.name, role: p.role }));
    modal({
      title: `Parents of ${rec.code} ${rec.name}`, wide: true,
      build: (body) => {
        const list = el('div');
        const draw = () => put(list, chosen.length ? chosen.map((p, i) => el('div', { class: 'parent-row' },
          el('select', { onchange: (e) => { p.role = e.target.value; } }, this.meta.parent_roles.map((r) => el('option', { value: r, selected: r === p.role }, r))),
          el('span', {}, `🧬 ${p.code} ${p.name}`),
          el('button', { class: 'icon-btn', title: 'Remove', onclick: () => { chosen.splice(i, 1); draw(); } }, '✕')))
          : el('p', { class: 'hint' }, 'None'));
        draw();
        body.append(el('p', { class: 'hint' }, 'The lines this one came from: a cross\'s mother and father, a transgenic line\'s background.'),
          list, el('button', { class: 'btn btn-secondary btn-sm', onclick: async () => {
            const l = await picker({ title: 'Add a parent line', placeholder: 'Search lines',
              search: async (q) => (await api('GET', `/lines?q=${encodeURIComponent(q)}`)).lines.filter((x) => x.id !== rec.id),
              describe: (x) => [el('b', {}, `${x.code} ${x.name}`), el('span', { class: 'hint' }, ` · ${x.line_kind} · ${x.species}`)] });
            if (l && !chosen.some((c) => c.id === l.id)) { chosen.push({ id: l.id, code: l.code, name: l.name, role: 'parent' }); draw(); }
          } }, '＋ Add a parent'));
      },
      buttons: [{ label: 'Cancel', kind: 'secondary' }, { label: 'Save', onClick: async () => {
        await api('PUT', `/lines/${rec.code}`, { parents: chosen.map((p) => ({ id: p.id, role: p.role })) });
        this.reload();
      } }],
    });
  },

  /* seed lots */

  lotFields(lot) {
    return [
      { name: 'generation', label: 'Generation', value: lot?.generation, placeholder: 'e.g. T2, F3, M3; empty for wild-type stocks' },
      { name: 'source', label: 'Source', value: lot?.source, placeholder: 'e.g. NASC N1092, from a colleague' },
      { name: 'harvested_on', label: 'Harvested on', type: 'date', value: lot?.harvested_on },
      { name: 'amount', label: 'Amount', value: lot?.amount, placeholder: 'e.g. 300 mg, ~2000 seeds' },
      { name: 'location', label: 'Kept in', value: lot?.location, placeholder: 'e.g. Freezer 2 / box 4 / A1' },
      { name: 'germination', label: 'Germination (%)', type: 'number', min: 0, max: 100, step: 'any', value: lot?.germination ?? '' },
      { name: 'zygosity', label: 'Zygosity', type: 'select', options: this.meta.zygosity, value: lot?.zygosity || '' },
      { name: 'notes', label: 'Notes', type: 'textarea', value: lot?.notes },
    ];
  },

  async newLot(line) {
    if (!line) {
      line = await picker({ title: 'A seed lot of which line?', placeholder: 'Search lines',
        search: async (q) => (await api('GET', `/lines?q=${encodeURIComponent(q)}`)).lines,
        describe: (x) => [el('b', {}, `${x.code} ${x.name}`), el('span', { class: 'hint' }, ` · ${x.line_kind} · ${x.species}`)] });
      if (!line) return;
    }
    formModal({
      title: `New seed lot of ${line.code} ${line.name}`,
      intro: 'Seeds from outside (a stock centre, a colleague) or found in a drawer. Seeds harvested from a plant here are added from that plant: Harvest.',
      fields: this.lotFields(null),
      submit: async (v) => {
        const { record } = await api('POST', '/lots', { ...v, line: line.code });
        location.hash = `lot=${record.code}`;
        toast(`Made ${record.code}`, 'success');
      },
    });
  },

  ancestry(rec) {
    const chain = [...(rec.ancestry || [])].reverse();
    if (!chain.length) return null;
    return el('div', { class: 'ancestry' }, el('span', { class: 'hint' }, 'From: '),
      chain.map((n, i) => [i ? el('span', { class: 'arrow' }, '→') : null, n.role && n.role !== 'parent' ? el('span', { class: 'role' }, n.role) : null, link(n)]),
      el('span', { class: 'arrow' }, '→'), el('b', {}, rec.code));
  },

  descendants(nodes) {
    if (!nodes?.length) return null;
    const item = (n) => el('li', {}, link(n), n.kind === 'lot' ? el('span', { class: 'hint' }, ` ${n.generation || ''}`) :
      el('span', { class: 'hint' }, ` ${n.status || ''}`), n.children?.length ? el('ul', {}, n.children.map(item)) : null);
    return el('ul', { class: 'tree' }, nodes.map(item));
  },

  lotView(rec) {
    return el('div', {},
      this.head(rec, `${rec.line?.name || ''} ${rec.generation || ''}`,
        [rec.used_up ? 'used up' : null, rec.location && `kept in ${rec.location}`, rec.amount].filter(Boolean).join(' · '), [
          el('button', { class: 'btn btn-primary', onclick: () => this.sow(rec) }, '🌱 Sow…'),
          el('button', { class: 'btn btn-secondary', onclick: () => this.segTest(rec) }, '🧮 Segregation test…'),
          el('button', { class: 'btn btn-secondary', onclick: () => formModal({
            title: `Edit ${rec.code}`,
            fields: [...(rec.plants.length ? [] : [{ name: 'line', label: 'Line (code)', value: rec.line?.code,
              hint: 'Correct it if the seeds were put in the wrong line. Possible until plants are sown from this lot.' }]),
            ...this.lotFields(rec), { name: 'used_up', label: 'Used up', type: 'checkbox', value: rec.used_up }],
            submit: async (v) => { await api('PUT', `/lots/${rec.code}`, v); this.reload(); },
          }) }, '✎ Edit')]),
      this.ancestry(rec),
      this.facts([['Line', link(rec.line)], ['Generation', rec.generation], ['Harvested from', rec.from_plant ? link(rec.from_plant) : null],
        ['Father', rec.father_plant ? link(rec.father_plant) : null], ['Source', rec.source], ['Harvested on', rec.harvested_on],
        ['Amount', rec.amount], ['Kept in', rec.location], ['Germination', rec.germination !== null ? `${rec.germination}%` : null],
        ['Zygosity', rec.zygosity], ['Made by', `${rec.created_by || '—'} · ${localTime(rec.created_at)}`]]),
      this.elabFact(rec),
      rec.notes ? el('p', { class: 'description' }, rec.notes) : null,
      this.section(`Segregation tests (${rec.seg_tests.length})`,
        rec.seg_tests.length ? el('table', { class: 'data' },
          el('thead', {}, el('tr', {}, ['Date', 'Selection', 'Resistant', 'Sensitive', '% R', 'Expected', 'χ²', 'p', 'Result', ''].map((h) => el('th', {}, h)))),
          el('tbody', {}, rec.seg_tests.map((t) => el('tr', { class: t.fits[t.expected].fits ? 'fit' : 'misfit' },
            el('td', {}, t.tested_on || localTime(t.created_at).slice(0, 10)), el('td', {}, t.selection), el('td', {}, t.resistant),
            el('td', {}, t.sensitive), el('td', {}, t.share.split(' ')[0]), el('td', {}, t.expected),
            el('td', {}, t.fits[t.expected].chi2 ?? '—'), el('td', {}, t.fits[t.expected].p_text ?? '—'), el('td', { class: 'verdict' }, t.verdict),
            el('td', {}, el('button', { class: 'icon-btn', title: 'Remove this test', onclick: async () => {
              await api('DELETE', `/seg-tests/${t.id}`); this.reload();
            } }, '✕'))))))
          : el('p', { class: 'hint' }, 'Count resistant and sensitive seedlings on a selection plate to see whether a T2 lot carries one insertion (3:1) or a T3 lot is homozygous.')),
      this.section(`Plants sown (${rec.plants.length})`,
        rec.plants.length ? el('table', { class: 'data' },
          el('thead', {}, el('tr', {}, ['', 'Code', '#', 'Line', 'Status', 'Zygosity', 'Kept at', 'Harvested into'].map((h) => el('th', {}, h)))),
          el('tbody', {}, rec.plants.map((p) => el('tr', { class: 'clickable', onclick: () => { location.hash = `plant=${p.code}`; } },
            el('td', { class: 'pick' }, this.pick(p.code)), el('td', { class: 'code' }, p.code), el('td', {}, `#${p.number}${p.selected ? ' ★' : ''}`),
            el('td', {}, p.line), el('td', {}, p.status), el('td', {}, p.zygosity), el('td', {}, p.location),
            el('td', {}, p.harvested.map((h, i) => [i ? ', ' : '', link(h)])))))) : el('p', { class: 'hint' }, 'None sown yet.')),
      rec.descendants?.length ? this.section('Descendants', this.descendants(rec.descendants)) : null);
  },

  /**
   * Where the lot is in eLabJournal (Lab Stocks copies the lab's seed lots there): a link to its sample,
   * how it stands, and sending it now. Empty when the lab does not copy its seed lots, or Lab Stocks is away.
   */
  elabFact(rec) {
    const line = el('p', { class: 'elab-fact' });
    const stocks = async (method, path) => {
      const res = await fetch(`${SB.stocks}/api/elab/seed-lots/${encodeURIComponent(rec.code)}${path}`, { method, credentials: 'same-origin' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `Lab Stocks: ${res.status}`);
      return data;
    };
    const draw = async () => {
      let e;
      try { e = (await stocks('GET', '')).elab; } catch (err) { return; }
      if (!e) { put(line); return; }
      const said = {
        sent: ['✓ sent', ''], waiting: ['waiting to be sent', ''], 'not sent': ['not in eLab yet', ''],
        failed: ['not sent', ` (${e.error || 'eLab refused it'})`], archived: ['archived there', ' (used up or deleted here)'],
        'archived in eLab': ['archived in eLab', ' (by someone there): no longer sent. Restore it there (open it, then Restore), or send it again'],
      }[e.state] || [e.state, ''];
      const again = e.state === 'archived in eLab';
      const send = e.state === 'archived' ? null : el('button', { class: 'btn btn-secondary btn-sm', style: 'margin-left:.5rem',
        title: again ? 'If it was restored in eLab, it goes on following changes here; if not, a new sample is made'
          : 'Send it to eLab now, not at the next round (every few minutes)',
        onclick: async (ev) => {
          ev.target.disabled = true;
          let res;
          try { res = await stocks('POST', '/send'); } catch (err) { toast(err.message, 'error', 6000); ev.target.disabled = false; return; }
          toast(again ? (res.restored ? 'Restored in eLab: changes go to it again' : 'A new sample is being made in eLab')
            : 'Sending to eLabJournal', 'success', 5000);
          setTimeout(draw, 8000);
        } }, again ? 'Send to eLab again' : '⟳ Send to eLab now');
      const link = e.url ? el('a', { href: e.url, target: '_blank', rel: 'noopener', title: 'Open its sample in eLab' }, `sample ${e.sample_id} ↗`) : null;
      line.classList.toggle('elab-failed', e.state === 'failed');
      put(line, '🔗 In eLabJournal: ', link, link ? ' · ' : '', el('b', {}, said[0]), said[1], send);
    };
    draw();
    return line;
  },

  sow(rec) {
    formModal({
      title: `Sow from ${rec.code}`,
      intro: 'Plants are numbered on from any sown before, and each gets a code for its label.',
      fields: [{ name: 'count', label: 'How many plants', type: 'number', min: 1, max: 500, value: 12 },
        { name: 'sown_on', label: 'Sown on', type: 'date', value: today() },
        { name: 'location', label: 'Where', placeholder: 'e.g. Tray 3, growth chamber B' }],
      label: 'Sow',
      submit: async (v) => {
        const res = await api('POST', `/lots/${rec.code}/sow`, v);
        toast(`Sowed ${res.plants} plant${res.plants > 1 ? 's' : ''}`, 'success');
        this.reload();
      },
    });
  },

  segTest(rec) {
    let result;
    modal({
      title: `Segregation test on ${rec.code}`,
      build: (body) => {
        const f = {
          tested_on: el('input', { type: 'date', value: today() }),
          selection: el('input', { type: 'text', placeholder: 'e.g. Basta, kanamycin, hygromycin, GFP' }),
          resistant: el('input', { type: 'number', min: 0, placeholder: '0' }),
          sensitive: el('input', { type: 'number', min: 0, placeholder: '0' }),
          expected: el('select', {}, [['3:1', '3:1 — one insertion (T2)'], ['15:1', '15:1 — two unlinked insertions'], ['1:0', 'All resistant — homozygous (T3)']]
            .map(([v, t]) => el('option', { value: v, selected: v === (rec.generation === 'T3' ? '1:0' : '3:1') }, t))),
          notes: el('textarea', { rows: 2 }),
        };
        result = el('div', { class: 'seg-result' });
        let ticket = 0;
        const calc = async () => {
          const mine = ++ticket;
          const r = +f.resistant.value || 0; const s = +f.sensitive.value || 0;
          if (!r && !s) { put(result, el('span', { class: 'hint' }, 'Enter the counts to see the test.')); return; }
          const a = await api('GET', `/segregation?resistant=${r}&sensitive=${s}&expected=${f.expected.value}`);
          if (mine !== ticket) return;
          put(result, el('div', { class: a.fits[f.expected.value].fits ? 'fit' : 'misfit' }, a.verdict),
            el('div', { class: 'hint' }, `${a.n} seedlings, ${a.share}. `,
              Object.values(a.fits).filter((x) => x.p !== null).map((x) => `${x.ratio}: p ${x.p_text.startsWith('<') ? '' : '= '}${x.p_text}`).join(' · ')));
        };
        for (const key of ['resistant', 'sensitive', 'expected']) f[key].addEventListener('input', calc);
        body.append(el('p', { class: 'hint' }, 'Seedlings on the selection plate. The χ² test (1 degree of freedom) says whether the counts fit the ratio expected; p below 0.05 means they do not.'),
          ...[['Tested on', 'tested_on'], ['Selection', 'selection'], ['Resistant', 'resistant'], ['Sensitive', 'sensitive'], ['Expected', 'expected'], ['Notes', 'notes']]
            .map(([label, key]) => el('label', { class: 'field' }, el('span', { class: 'field-label' }, label), f[key])), result);
        this._seg = f;
        calc();
        setTimeout(() => f.resistant.focus(), 0);
      },
      buttons: [{ label: 'Cancel', kind: 'secondary' }, { label: 'Save', onClick: async () => {
        const f = this._seg;
        await api('POST', `/lots/${rec.code}/seg-tests`, Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v.value])));
        this.reload();
      } }],
    });
  },

  /* plants */

  plantView(rec) {
    return el('div', {},
      this.head(rec, `${rec.line?.name || ''} #${rec.number}`,
        [rec.lot?.generation, rec.status, rec.zygosity, rec.location && `at ${rec.location}`, rec.selected ? '★ selected' : null].filter(Boolean).join(' · '), [
          el('button', { class: 'btn btn-primary', onclick: () => this.harvest(rec) }, '🫘 Harvest…'),
          el('button', { class: 'btn btn-secondary', onclick: () => this.cross(rec) }, '✕ Cross with…'),
          el('button', { class: 'btn btn-secondary', title: 'Make this plant the founder of a line of its own, e.g. an independent T1 transformant',
            onclick: () => this.foundLine(rec) }, '🧬 Found a line…'),
          el('button', { class: 'btn btn-secondary', onclick: () => formModal({
            title: `Edit ${rec.code}`,
            fields: [{ name: 'status', label: 'Status', type: 'select', options: this.meta.plant_status, value: rec.status },
              { name: 'zygosity', label: 'Zygosity', type: 'select', options: this.meta.zygosity, value: rec.zygosity },
              { name: 'selected', label: 'Selected (★, a keeper)', type: 'checkbox', value: rec.selected },
              { name: 'sown_on', label: 'Sown on', type: 'date', value: rec.sown_on },
              { name: 'location', label: 'Where', value: rec.location }, { name: 'notes', label: 'Notes', type: 'textarea', value: rec.notes }],
            submit: async (v) => { await api('PUT', `/plants/${rec.code}`, v); this.reload(); },
          }) }, '✎ Edit')]),
      this.ancestry(rec),
      this.facts([['Line', link(rec.line)], ['Sown from', link(rec.lot)], ['Number', `#${rec.number}`], ['Sown on', rec.sown_on],
        ['Where', rec.location], ['Status', rec.status], ['Zygosity', rec.zygosity], ['Selected', rec.selected ? '★ a keeper' : null],
        ['Made by', `${rec.created_by || '—'} · ${localTime(rec.created_at)}`]]),
      rec.notes ? el('p', { class: 'description' }, rec.notes) : null,
      rec.harvested.length ? this.section('Seeds from this plant', el('p', {}, rec.harvested.map((h, i) => [i ? ', ' : '', link(h), el('span', { class: 'hint' }, ` ${h.generation} `)]))) : null,
      rec.siblings.length ? this.section(`Others sown from ${rec.lot.code}`, el('div', { class: 'chips' }, rec.siblings.map((s) => el('a', {
        class: `chip ${s.status === 'harvested' ? 'chip-done' : ''}`, href: `#plant=${s.code}` }, `#${s.number} ${s.status}`)))) : null);
  },

  harvest(rec) {
    formModal({
      title: `Harvest ${rec.code} (${rec.line?.name} #${rec.number})`,
      intro: 'A new seed lot from this one plant. The plant is marked harvested. See Help for transformations and bulk harvests.',
      fields: [{ name: 'into', label: 'Seeds belong to', type: 'select', value: '', options: [
        ['', `${rec.line?.code} ${rec.line?.name}: this plant's own line`],
        ['other', 'Another line: this plant was transformed (dipped), its seeds are T1 of a transgenic line…']] },
        { name: 'generation', label: 'Generation', value: rec.next_generation, placeholder: 'e.g. T3', hint: 'Suggested: one on from the lot it was sown from. T1 for seeds of a dipped plant.' },
        { name: 'harvested_on', label: 'Harvested on', type: 'date', value: today() },
        { name: 'amount', label: 'Amount', placeholder: 'e.g. 200 mg' },
        { name: 'location', label: 'Kept in', placeholder: 'e.g. Freezer 2 / box 5 / C3' },
        { name: 'notes', label: 'Notes', type: 'textarea' }],
      label: 'Harvest',
      submit: async (v) => {
        const { into, ...data } = v;
        if (into === 'other') {
          const line = await picker({ title: 'Which transgenic line are these seeds?', placeholder: 'Search lines, e.g. 35S:GFP',
            search: async (q) => (await api('GET', `/lines?q=${encodeURIComponent(q)}`)).lines.filter((x) => x.code !== rec.line?.code),
            describe: (x) => [el('b', {}, `${x.code} ${x.name}`), el('span', { class: 'hint' }, ` · ${x.line_kind}${x.plasmids ? ` · ${x.plasmids}` : ''}`)] });
          if (!line) return false;
          data.line = line.code;
          // The generation suggested was this plant's own; a dipped plant's seeds are T1.
          if (data.generation === rec.next_generation) data.generation = 'T1';
        }
        const { record } = await api('POST', `/plants/${rec.code}/harvest`, data);
        toast(`Harvested into ${record.code}`, 'success');
        location.hash = `lot=${record.code}`;
      },
    });
  },

  async cross(rec) {
    const father = await picker({ title: `Cross ${rec.code} (mother) with…`, placeholder: 'Search plants for the father (pollen donor)',
      search: async (q) => (await api('GET', `/plants?q=${encodeURIComponent(q)}`)).plants.filter((p) => p.code !== rec.code && p.status === 'growing'),
      describe: (p) => [el('b', {}, `${p.code} ${p.line} #${p.number}`), el('span', { class: 'hint' }, ` · ${p.lot} ${p.generation} · ${p.location || ''}`)] });
    if (!father) return;
    formModal({
      title: `${rec.line?.name} #${rec.number} ♀ × ${father.line} #${father.number} ♂`,
      intro: 'A new line (a cross of the two lines, carrying both lines\' plasmids) and its F1 seed lot, from the mother.',
      fields: [{ name: 'name', label: 'Name of the cross', value: `${rec.line?.name} × ${father.line}` },
        { name: 'harvested_on', label: 'Harvested on', type: 'date', value: today() },
        { name: 'amount', label: 'Amount', placeholder: 'e.g. 1 silique, 30 seeds' },
        { name: 'location', label: 'Kept in' }],
      label: 'Cross',
      submit: async (v) => {
        const { record } = await api('POST', `/plants/${rec.code}/cross`, { ...v, father: father.code });
        toast(`Made ${record.line.code} and its F1 lot ${record.code}`, 'success', 5000);
        location.hash = `lot=${record.code}`;
      },
    });
  },

  foundLine(rec) {
    formModal({
      title: `Found a line from ${rec.code}`,
      intro: 'Each T1 transformant is an independent insertion: it becomes a line of its own, with the plasmids of the line it came from. Seeds harvested from this plant afterwards belong to the new line.',
      fields: [{ name: 'name', label: 'Name', value: `${rec.line?.name}-${rec.number}` },
        { name: 'kind', label: 'Kind', type: 'select', options: this.meta.kinds, value: 'transgenic' }],
      label: 'Found the line',
      submit: async (v) => {
        const { record } = await api('POST', `/plants/${rec.code}/found-line`, v);
        toast(`Made line ${record.code} ${record.name}`, 'success');
        this.reload();
      },
    });
  },

  /* phenotypes, files, mentions, history ------------------------------------------ */

  observations(rec) {
    const add = () => {
      let files = [];
      formModal({
        title: `Observation on ${rec.code}`,
        fields: [{ name: 'observed_on', label: 'Date', type: 'date', value: today() },
          { name: 'trait', label: 'Trait', list: 'traits', placeholder: 'e.g. flowering time, leaf colour, GFP' },
          { name: 'value', label: 'Value', placeholder: 'e.g. day 24, pale, strong' },
          { name: 'notes', label: 'Notes', type: 'textarea' }],
        submit: async (v) => {
          const { id } = await api('POST', `/${rec.kind}/${rec.code}/observations`, v);
          files = [...(document.getElementById('obsFiles')?.files || [])];
          if (files.length) await this.upload('observation', id, files);
          this.reload();
        },
      });
      // Photos with it, sent once it is saved.
      setTimeout(() => document.querySelector('.modal-body')?.append(el('label', { class: 'field' },
        el('span', { class: 'field-label' }, 'Photos or files'), el('input', { type: 'file', id: 'obsFiles', multiple: true }))), 0);
    };
    return this.section(`Phenotypes (${rec.observations.length})`,
      el('button', { class: 'btn btn-secondary btn-sm', onclick: add }, '＋ Observation'),
      rec.observations.length ? el('div', { class: 'observations' }, rec.observations.map((o) => el('div', { class: 'observation' },
        el('div', { class: 'obs-head' }, el('b', {}, o.trait), o.value ? `: ${o.value}` : '',
          el('span', { class: 'hint' }, ` · ${o.observed_on || localTime(o.created_at).slice(0, 10)} · ${o.created_by || ''}`),
          el('button', { class: 'icon-btn', title: 'Remove', onclick: async () => { await api('DELETE', `/observations/${o.id}`); this.reload(); } }, '✕')),
        o.notes ? el('div', {}, o.notes) : null,
        this.files('observation', o.id, o.attachments, null)))) : el('p', { class: 'hint' }, 'Nothing recorded yet.'));
  },

  async upload(kind, ident, files) {
    const form = new FormData();
    for (const f of files) form.append('file', f, f.name || 'photo.png');
    try {
      return (await api('POST', `/${kind}/${encodeURIComponent(ident)}/attachments`, undefined, form)).attachments;
    } catch (err) {
      toast(`Not attached: ${err.message}`, 'error', 7000);
      return [];
    }
  },

  files(kind, ident, list, title) {
    const photos = list.filter((a) => a.image);
    const models = list.filter((a) => a.model);
    const others = list.filter((a) => !a.image && !a.model);
    const input = el('input', { type: 'file', multiple: true, hidden: true, onchange: async (e) => {
      const files = [...e.target.files];
      if (files.length && (await this.upload(kind, ident, files)).length) this.reload();
    } });
    const remove = (a) => modal({
      title: `Remove ${a.filename}?`, build: (b) => b.append(el('p', {}, 'It leaves this record\'s files (and is kept in the database).')),
      buttons: [{ label: 'Cancel', kind: 'secondary' }, { label: 'Remove', kind: 'danger', onClick: async () => { await api('DELETE', `/attachments/${a.id}`); this.reload(); } }],
    });
    const zone = el('div', { class: `files ${title ? '' : 'files-inline'}` },
      photos.length ? el('div', { class: 'gallery' }, photos.map((a) => el('figure', {},
        el('img', { src: fileUrl(a.id), loading: 'lazy', alt: a.filename, onclick: () => window.open(fileUrl(a.id), '_blank', 'noopener') }),
        el('figcaption', {}, a.caption || a.filename, el('button', { class: 'icon-btn', title: 'Remove', onclick: () => remove(a) }, '✕'))))) : null,
      [...models, ...others].length ? el('ul', { class: 'file-list' }, [...models, ...others].map((a) => el('li', {},
        el('span', { class: 'file-icon' }, FILE_ICONS[a.kind] || '📎'),
        el('a', { href: fileUrl(a.id), target: '_blank', rel: 'noopener' }, a.filename),
        el('span', { class: 'hint' }, ` ${sizeLabel(a.size)} · ${a.created_by || ''} · ${localTime(a.created_at)}`),
        a.model ? el('button', { class: 'btn btn-secondary btn-sm', onclick: () => this.view3d(a) }, '🧊 View in 3D') : null,
        el('a', { class: 'btn btn-secondary btn-sm', href: fileUrl(a.id, true), title: 'Download' }, '⤓'),
        el('button', { class: 'icon-btn', title: 'Remove', onclick: () => remove(a) }, '✕')))) : null,
      el('label', { class: 'btn btn-secondary btn-sm', title: 'Photos, 3D scans (STL, PLY, OBJ, glTF) and any other file. You can also drop files here.' },
        title ? '📎 Add photos or files…' : '📎 Add', input));
    zone.addEventListener('dragover', (e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); zone.classList.add('drop'); } });
    zone.addEventListener('dragleave', () => zone.classList.remove('drop'));
    zone.addEventListener('drop', async (e) => {
      e.preventDefault();
      zone.classList.remove('drop');
      if ((await this.upload(kind, ident, [...e.dataTransfer.files])).length) this.reload();
    });
    return title ? this.section(`${title} (${list.length})`, zone) : zone;
  },

  async view3d(a) {
    const holder = el('div', { class: 'viewer3d' }, el('p', { class: 'hint' }, 'Loading…'));
    modal({ title: `🧊 ${a.filename}`, wide: true, build: (b) => b.append(holder,
      el('p', { class: 'hint' }, 'Drag to turn, scroll to zoom, right-drag to move.')) });
    try {
      const viewer = await import(url('/static/js/viewer3d.js'));
      await viewer.show(holder, fileUrl(a.id, true), a.filename);
    } catch (err) {
      put(holder, el('p', { class: 'empty' }, `This model could not be shown: ${err.message}`));
    }
  },

  mentions(rec) {
    if (!rec.mentions?.length) return null;
    return this.section('In the lab notebook', el('ul', { class: 'plain' }, rec.mentions.map((m) => el('li', {},
      el('a', { href: `${SB.notebook}/#note=${m.id}`, target: '_blank', rel: 'noopener' }, `📓 ${m.title}`),
      el('span', { class: 'hint' }, m.owner ? ` · ${m.owner}` : ' · protocol library')))));
  },

  history(rec) {
    return el('details', { class: 'history' }, el('summary', {}, `History (${rec.changes.length})`),
      el('ul', { class: 'plain' }, rec.changes.map((c) => el('li', {}, el('span', { class: 'hint' }, `${localTime(c.changed_at)} · ${c.changed_by || '—'}: `), c.what))));
  },
};

document.addEventListener('DOMContentLoaded', () => App.init());
