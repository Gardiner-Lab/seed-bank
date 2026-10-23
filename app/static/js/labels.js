'use strict';
/*
 * Labels for seed lots, plants and lines, each with a QR code that opens the
 * record, laid out as the LabTAG DYMO label chosen. /labels?codes=S-0001,P-0003 ; print from the browser.
 */

const SB = window.SB;
const KIND = { L: 'line', S: 'lot', P: 'plant' };
// GL-S-0001 (or S-0001): the letter before the number says what it is.
const kindOf = (code) => KIND[code.split('-').slice(-2, -1)[0]];

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
        [rec.harvested_on, rec.location].filter(Boolean).join(' · ')]
      : [`${rec.line?.name || ''} #${rec.number}`, `${rec.lot?.code || ''} ${rec.lot?.generation || ''}`, rec.sown_on ? `sown ${rec.sown_on}` : rec.location];
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
      ? ' This is this computer\'s own address, which phones cannot reach: open this page through the server\'s name (e.g. http://UU115629:8080), or set SUITE_PUBLIC_URL for the suite.' : '');
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
  const hint = document.getElementById('dymoHint');
  const recall = (key) => { try { return localStorage.getItem(key); } catch { return null; } };
  const remember = (key, value) => { try { localStorage.setItem(key, value); } catch { /* not kept: fine */ } };
  for (const [range, title] of Object.entries(Dymo.RANGES)) {
    stock.append(el('optgroup', { label: title },
      Dymo.stocks.filter((s) => s.range === range).map((s) => el('option', { value: s.id }, `${s.id} · ${s.size}`))));
  }
  stock.value = Dymo.stocks.some((s) => s.id === recall('dymoStock')) ? recall('dymoStock') : Dymo.stocks[0].id;
  region.value = recall('dymoRegion') === 'NA' ? 'NA' : 'EU';
  withQr.checked = recall('dymoQr') !== 'no';
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
    hint.textContent = `DYMO: ${labels.length} label${labels.length === 1 ? '' : 's'} on LabTAG ${s.id} (${s.size}; ${s.products})`
      + `${per > 1 ? `, ${per} to a printed label: ${printed} printed` : ''}.`
      + (s.range === 'lwcs' ? ' DYMO Connect recognises the LWCS roll in the 550; if it asks to use the loaded label, say yes.'
        : ' DY4 labels are LabTAG\'s LabelWriter 450-series range.');
  };
  for (const [node, key] of [[stock, 'dymoStock'], [region, 'dymoRegion']]) {
    node.addEventListener('change', () => { remember(key, node.value); describe(); draw(); });
  }
  withQr.addEventListener('change', () => { remember('dymoQr', withQr.checked ? 'yes' : 'no'); draw(); });
  document.getElementById('btnDymo').addEventListener('click', () => {
    if (!labels.length) return;
    const files = Dymo.files(stock.value, region.value, labels, { qr: withQr.checked });
    const day = new Date().toISOString().slice(0, 10);
    Dymo.download(`labels-${stock.value}-${day}.zip`, Dymo.zip(files));
  });
  describe();
  draw();
}

document.addEventListener('DOMContentLoaded', main);
