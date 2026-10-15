'use strict';
/*
 * Labels for seed lots, plants and lines, each with a QR code that opens the
 * record. /labels?codes=S-0001,P-0003 ; print from the browser.
 */

const SB = window.SB;
const KIND = { L: 'line', S: 'lot', P: 'plant' };

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

function qr(text) {
  const code = qrcode(0, 'M');
  code.addData(text);
  code.make();
  const holder = el('div', { class: 'qr' });
  holder.innerHTML = code.createSvgTag({ cellSize: 2, margin: 0, scalable: true });   // made here, from our own URL
  return holder;
}

function label(rec) {
  const target = `${publicBase()}/#${rec.kind}=${rec.code}`;
  const lines = rec.kind === 'line'
    ? [rec.name, [rec.line_kind, rec.species].filter(Boolean).join(' · '), rec.plasmids?.map((p) => p.name).join(', ')]
    : rec.kind === 'lot'
      ? [`${rec.line?.name || ''} ${rec.generation || ''}`, rec.from_plant ? `from ${rec.from_plant.code}` : rec.source,
        [rec.harvested_on, rec.location].filter(Boolean).join(' · ')]
      : [`${rec.line?.name || ''} #${rec.number}`, `${rec.lot?.code || ''} ${rec.lot?.generation || ''}`, rec.sown_on ? `sown ${rec.sown_on}` : rec.location];
  return el('div', { class: `label label-${rec.kind}` }, qr(target),
    el('div', { class: 'label-text' }, el('div', { class: 'label-code' }, rec.code),
      lines.filter(Boolean).map((t) => el('div', { class: 'label-line' }, t))));
}

async function main() {
  const codes = (new URLSearchParams(location.search).get('codes') || '').split(',').map((c) => c.trim().toUpperCase()).filter(Boolean);
  const sheet = document.getElementById('sheet');
  const help = document.getElementById('labelsHelp');
  const host = new URL(publicBase()).hostname;
  help.textContent = `${codes.length} label${codes.length === 1 ? '' : 's'}. The codes open ${publicBase()}/ on a phone.`
    + (['localhost', '127.0.0.1', '::1'].includes(host)
      ? ' This is this computer\'s own address, which phones cannot reach: open this page through the server\'s name (e.g. http://UU115629:8080), or set SUITE_PUBLIC_URL for the suite.' : '');
  for (const code of codes) {
    const kind = KIND[code[0]];
    if (!kind) continue;
    try {
      const res = await fetch(`${SB.base}/api/${kind}/${encodeURIComponent(code)}`, { credentials: 'same-origin' });
      const data = await res.json();
      sheet.append(res.ok ? label(data.record) : el('div', { class: 'label label-missing' }, `${code}: ${data.error || 'not found'}`));
    } catch (err) {
      sheet.append(el('div', { class: 'label label-missing' }, `${code}: ${err.message}`));
    }
  }
  const size = document.getElementById('labelSize');
  const apply = () => { sheet.className = `label-sheet size-${size.value}`; };
  size.addEventListener('change', apply);
  apply();
}

document.addEventListener('DOMContentLoaded', main);
