'use strict';
/*
 * Labels for seed lots, plants and lines, each with a QR code that opens the
 * record, laid out as the LabTAG DYMO label chosen. /labels?codes=S-0001,P-0003 ; print from the browser.
 */

const SB = window.SB;
const KIND = { L: 'line', S: 'lot', P: 'plant' };
// GL-S-0001 (or S-0001): the letter before the number says what it is.
const kindOf = (code) => KIND[code.split('-').slice(-2, -1)[0]];
// A stored date (2026-10-30) as the lab writes it: 30-10-2026.
const euDate = (iso) => (/^\d{4}-\d\d-\d\d$/.test(String(iso || '')) ? String(iso).split('-').reverse().join('-') : (iso || ''));

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v; else node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false && c !== '') node.append(c);
  return node;
}

/** Where a phone reaches the suite: the address set for it, or the one this page is open at. */
function publicBase() {
  return `${SB.public || location.origin}${SB.base}`;
}

/** A QR code's modules, row by row (qrcode-generator, kept in this repository), for dymo.js to draw. */
function qrModules(text) {
  const code = qrcode(0, 'M');
  code.addData(text);
  code.make();
  const n = code.getModuleCount();
  return Array.from({ length: n }, (_, r) => Array.from({ length: n }, (__, c) => code.isDark(r, c)));
}

/** What a label says: its code, its lines, and where its QR code leads. */
function content(rec) {
  const target = `${publicBase()}/#${rec.kind}=${rec.code}`;
  const lines = rec.kind === 'line'
    ? [rec.name, [rec.line_kind, rec.species].filter(Boolean).join(' · '), rec.plasmids?.map((p) => p.name).join(', ')]
    : rec.kind === 'lot'
      ? [`${rec.line?.name || ''} ${rec.generation || ''}`, rec.from_plant ? `from ${rec.from_plant.code}` : rec.source,
        [euDate(rec.harvested_on), rec.location].filter(Boolean).join(' · ')]
      : [`${rec.line?.name || ''} #${rec.number}`, `${rec.lot?.code || ''} ${rec.lot?.generation || ''}`, rec.sown_on ? `sown ${euDate(rec.sown_on)}` : rec.location];
  return { code: rec.code, lines: lines.filter(Boolean), url: target, kind: rec.kind };
}

async function main() {
  const codes = (new URLSearchParams(location.search).get('codes') || '').split(',').map((c) => c.trim().toUpperCase()).filter(Boolean);
  const sheet = document.getElementById('sheet');
  const missing = document.getElementById('missing');
  const loaded = [];        // what each label says
  const help = document.getElementById('labelsHelp');
  const host = new URL(publicBase()).hostname;
  help.textContent = `${codes.length} label${codes.length === 1 ? '' : 's'}. The codes open ${publicBase()}/ on a phone.`
    + (['localhost', '127.0.0.1', '::1'].includes(host)
      ? ' This is this computer\'s own address, which phones cannot reach: open this page through the server\'s name (e.g. http://UU115629:8080), or ask an administrator to set the suite’s public address (dashboard, Hosting).' : '');
  for (const code of codes) {
    const kind = kindOf(code);
    if (!kind) continue;
    try {
      const res = await fetch(`${SB.base}/api/${kind}/${encodeURIComponent(code)}`, { credentials: 'same-origin' });
      const data = await res.json();
      if (res.ok) loaded.push(content(data.record));
      else missing.append(el('div', { class: 'label-missing' }, `${code}: ${data.error || 'not found'}`));
    } catch (err) {
      missing.append(el('div', { class: 'label-missing' }, `${code}: ${err.message}`));
    }
  }
  setupDymo(loaded, sheet);
}

/**
 * The labels as the LabTAG DYMO label chosen (dymo.js) lays them out: shown on the sheet as the
 * printed labels, printed one to a page of that label's size, and as files for DYMO Connect
 * (the LabelWriter 550's software) - a zip of ready .dymo files, and a design and spreadsheet to
 * print many at once. The choices are remembered.
 */
function setupDymo(labels, sheet) {
  const stock = document.getElementById('dymoStock');
  const region = document.getElementById('dymoRegion');
  const withQr = document.getElementById('dymoQr');
  const sep = document.getElementById('dymoSep');
  const hint = document.getElementById('dymoHint');
  const recall = (key) => { try { return localStorage.getItem(key); } catch { return null; } };
  const remember = (key, value) => { try { localStorage.setItem(key, value); } catch { /* not kept: fine */ } };
  const fillStocks = () => {
    const chosen = stock.value || recall('dymoStock');
    stock.replaceChildren();
    for (const [range, title] of Object.entries(Dymo.RANGES)) {
      const of = Dymo.stocks.filter((s) => s.range === range);
      if (!of.length) continue;              // no labels of the lab's own yet: no group for them
      stock.append(el('optgroup', { label: title },
        of.map((s) => el('option', { value: s.id }, s.shown || `${s.id} · ${s.size}`))));
    }
    stock.value = Dymo.stocks.some((s) => s.id === chosen) ? chosen : Dymo.stocks[0].id;
  };
  fillStocks();
  region.value = recall('dymoRegion') === 'NA' ? 'NA' : 'EU';
  withQr.checked = recall('dymoQr') !== 'no';
  // What this computer's programs use, unless someone has chosen otherwise here before.
  sep.value = [';', ','].includes(recall('dymoSep')) ? recall('dymoSep') : Dymo.separator();
  const pageStyle = el('style');
  document.head.append(pageStyle);
  const draw = () => {
    const s = Dymo.stock(stock.value);
    const { w, h } = Dymo.paper(s);
    // Printed, each label is a page of the label's own size: the DYMO driver takes it as it is.
    pageStyle.textContent = `@page { size: ${w}in ${h}in; margin: 0; }`
      + `@media print { .dymo-label { width: ${w}in; height: ${h}in; } }`;
    sheet.replaceChildren(...Dymo.groups(s, labels).map((group) => {
      const box = el('div', { class: 'dymo-label', title: group.map((l) => l.code).join(', ') });
      box.innerHTML = Dymo.svg(s, group, { qr: withQr.checked }, qrModules);   // made here, from our own records
      return box;
    }));
  };
  const describe = () => {
    const s = Dymo.stock(stock.value);
    const per = s.slots.length;
    const printed = Math.ceil(labels.length / per);
    const about = {
      lwcs: ' DYMO Connect recognises the LWCS roll in the 550; if it asks to use the loaded label, say yes.',
      dy4: ' DY4 labels are LabTAG\'s LabelWriter 450-series range.',
      own: s.names.NA ? ` DYMO Connect is asked for "${s.names.NA}".`
        : ' No DYMO label stock is named for this one, so DYMO Connect prints on the roll in the printer.',
    }[s.range] || '';
    hint.textContent = `DYMO: ${labels.length} label${labels.length === 1 ? '' : 's'} on ${Dymo.called(s)} (${s.size}; ${s.products})`
      + `${per > 1 ? `, ${per} to a printed label: ${printed} printed` : ''}.` + about;
  };
  for (const [node, key] of [[stock, 'dymoStock'], [region, 'dymoRegion']]) {
    node.addEventListener('change', () => { remember(key, node.value); describe(); draw(); });
  }
  withQr.addEventListener('change', () => { remember('dymoQr', withQr.checked ? 'yes' : 'no'); draw(); });
  sep.addEventListener('change', () => remember('dymoSep', sep.value));
  document.getElementById('btnDymo').addEventListener('click', () => {
    if (!labels.length) return;
    const s = Dymo.stock(stock.value);
    const files = Dymo.files(stock.value, region.value, labels, { qr: withQr.checked, separator: sep.value });
    const day = new Date().toISOString().slice(0, 10);
    const named = String(s.range === 'own' ? s.name : s.id).replace(/[^A-Za-z0-9._-]+/g, '-');
    Dymo.download(`labels-${named}-${day}.zip`, Dymo.zip(files));
  });
  setupOwnLabels(stock, fillStocks, describe, draw);
  describe();
  draw();
}

/**
 * The labels the lab has measured itself, kept by the suite (the portal) so everyone's labels page
 * offers them. Anyone signed in may add one: whoever has the new roll in hand is who knows its size.
 */
function setupOwnLabels(stock, fillStocks, describe, draw) {
    const box = document.getElementById('ownLabel');
    if (!box) return;
  const api = async (method, path, body) => {
    const res = await fetch(`/account/api/label-stocks${path}`, {
      method,
      credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `The suite answered ${res.status}`);
    return data;
  };
  const reload = async (keep) => {
    const { label_stocks: rows } = await api('GET', '');
    Dymo.own(rows);
    if (keep) stock.value = keep;
    fillStocks();
    describe();
    draw();
  };
  const field = (name, label, attrs = {}) => el('label', { class: 'field' }, label,
    el('input', { name, autocomplete: 'off', ...attrs }));
  box.addEventListener('click', (e) => {
    if (!e.target.closest('#btnOwnLabel')) return;
    const chosen = Dymo.stock(stock.value);
    const editing = chosen.range === 'own' ? chosen : null;     // the one shown, when it is the lab's own
    const form = el('form', { class: 'own-label-form' },
      el('p', { class: 'hint' }, 'Measure the label: the printed tag, the spot or cap beside it (0 if it has '
        + 'none), and the gap between them. Everyone in the suite can then print on it.'),
      field('name', 'Name', { required: 'required', value: editing ? editing.name : '', placeholder: 'Cryo-Tag 38 mm' }),
      field('tag_w', 'Tag width (mm)', { type: 'number', step: '0.1', min: '1', required: 'required' }),
      field('tag_h', 'Tag height (mm)', { type: 'number', step: '0.1', min: '1', required: 'required' }),
      field('spot', 'Spot or cap (mm)', { type: 'number', step: '0.1', min: '0', value: '0' }),
      field('gap', 'Gap to the spot (mm)', { type: 'number', step: '0.1', min: '0', value: '0' }),
      field('dymo_label', 'What DYMO Connect calls the roll (if known)', { placeholder: 'leave empty if unsure' }),
      el('div', { class: 'own-label-buttons' },
        el('button', { class: 'btn btn-primary', type: 'submit' }, editing ? 'Save' : 'Add'),
        editing ? el('button', { class: 'btn', type: 'button', 'data-remove': '1' }, 'Remove') : null,
        el('button', { class: 'btn', type: 'button', 'data-close': '1' }, 'Cancel')),
      el('div', { class: 'own-label-error hint' }));
    if (editing) {
      const mm = (v) => String(Math.round(v * 25.4 * 100) / 100);
      form.tag_w.value = mm(editing.slots[0].main.w);
      form.tag_h.value = mm(editing.slots[0].main.h);
      form.spot.value = editing.slots[0].cap ? mm(editing.slots[0].cap.w) : '0';
      form.gap.value = editing.slots[0].cap
        ? mm(editing.slots[0].cap.x - (editing.slots[0].main.x + editing.slots[0].main.w)) : '0';
      form.dymo_label.value = editing.names.NA || '';
    }
    const dialog = el('dialog', { class: 'own-label-dialog' }, el('h2', {}, editing ? 'This label' : 'A label of your own'), form);
    const say = (err) => { form.querySelector('.own-label-error').textContent = err; };
    const close = () => { dialog.close(); dialog.remove(); };
    form.addEventListener('click', async (ev) => {
      if (ev.target.dataset.close) close();
      if (!ev.target.dataset.remove) return;
      try { await api('DELETE', `/${encodeURIComponent(editing.id)}`); close(); await reload(null); } catch (err) { say(err.message); }
    });
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const body = Object.fromEntries(new FormData(form).entries());
      try {
        const { label_stock: saved } = editing
          ? await api('PATCH', `/${encodeURIComponent(editing.id)}`, body)
          : await api('POST', '', body);
        close();
        await reload(saved.id);
      } catch (err) { say(err.message); }
    });
    document.body.append(dialog);
    dialog.showModal();
  });
  reload(null).catch(() => { /* the suite is not answering: LabTAG's labels still work */ });
}

document.addEventListener('DOMContentLoaded', main);
