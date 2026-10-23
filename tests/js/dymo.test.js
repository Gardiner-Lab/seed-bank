/* Checks dymo.js, the files for DYMO Connect on LabTAG labels (no browser needed). */
const assert = require('assert');
const path = require('path');

const { Dymo, DYMO_STOCKS, DYMO_LWCS } = require(path.join(__dirname, '..', '..', 'app', 'static', 'js', 'dymo.js'));

const labels = Array.from({ length: 5 }, (_, i) => ({
  code: `GL-G-004${i + 1}`, lines: ['pTest & <sfGFP> "clone"', 'DH5α · Amp', '', '−80 °C'], url: `https://suite/stocks/#glycerol=GL-G-004${i + 1}`,
}));

// Every LabTAG DYMO label: the 19 on the DY4 page, and the 5 LWCS for the LabelWriter 550.
assert.strictEqual(DYMO_STOCKS.length, 19);
assert.strictEqual(DYMO_LWCS.length, 5);
assert.deepStrictEqual(DYMO_LWCS.map((s) => s.id), ['LWCS-501', 'LWCS-502', 'LWCS-504', 'LWCS-505', 'LWCS-506']);
for (const s of Dymo.stocks) {
  assert.ok(s.names.NA || s.names.EU, `${s.id}: a DYMO stock name`);
  for (const slot of s.slots) {
    for (const part of [slot.main, slot.cap].filter(Boolean)) {
      // Each sticker part inside the label's printable area.
      assert.ok(part.x >= s.rect.x - 0.1 && part.y >= s.rect.y - 0.1 && part.x + part.w <= s.rect.x + s.rect.w + 0.1
        && part.y + part.h <= s.rect.y + s.rect.h + 0.1, `${s.id}: a sticker inside the label`);
    }
  }
}

// A file: well-formed enough to count, on the stock named for the region, text escaped, QR in both data nodes.
const stock = Dymo.stock('DY4-072');
const xml = Dymo.file(stock, 'EU', labels.slice(0, 1), { qr: true });
assert.ok(xml.includes('<LabelName>Small1976411</LabelName>'), 'Europe\'s stock name');
assert.ok(Dymo.file(stock, 'NA', labels.slice(0, 1)).includes('<LabelName>Small30336</LabelName>'), 'North America\'s');
const big = Dymo.file(Dymo.stock('DY4-082'), 'EU', labels.slice(0, 1));
assert.ok(big.includes('pTest &amp; &lt;sfGFP&gt; &quot;clone&quot;') && !big.includes('<sfGFP>'), 'text escaped');
// Lines only as legible text allows: a big label keeps them all, a tube label drops what would shrink the rest.
assert.ok(big.includes('−80 °C'), 'a big label keeps every line');
assert.ok(!xml.includes('pTest &amp;') && xml.includes('<Text>GL-G-0041</Text>'), 'a tube label keeps the code, not a line too long for it');
assert.deepStrictEqual(Dymo.fitLines(['GL-G-0041', 'a line far too long to stay legible on this', 'DH5α'], 0.5, 0.58), ['GL-G-0041', 'DH5α']);
assert.ok(Dymo.pointSize(['GL-G-0041'], 0.45, 0.58) >= Dymo.MIN_PT);
assert.ok(xml.includes('<DataString>https://suite/stocks/#glycerol=GL-G-0041</DataString>')
  && xml.includes('<Value>https://suite/stocks/#glycerol=GL-G-0041</Value>'), 'QR content in both data nodes');
assert.ok(xml.includes('<Text>G-0041</Text>'), 'the cap carries the short code');
for (const tag of ['DesktopLabel', 'DYMOLabel', 'TextObject', 'QRCodeObject', 'LineTextSpan']) {
  assert.strictEqual((xml.match(new RegExp(`<${tag}[ >]`, 'g')) || []).length, (xml.match(new RegExp(`</${tag}>`, 'g')) || []).length, `${tag} balanced`);
}
assert.ok(!Dymo.file(stock, 'EU', labels.slice(0, 1), { qr: false }).includes('QRCodeObject'), 'no QR when not wanted');
// Empty lines are left out; a code is shortened for caps.
assert.strictEqual(Dymo.shortCode('GL-S-0007'), 'S-0007');

// Several stickers to a printed label: grouped, and the spreadsheet's columns are the design's fields.
const twoUp = Dymo.stock('DY4-040');
assert.deepStrictEqual(Dymo.groups(twoUp, labels).map((g) => g.length), [2, 2, 1]);
const files = Dymo.files('DY4-040', 'NA', labels, { qr: true });
assert.deepStrictEqual(files.slice(0, 3).map((f) => f.name), ['README.txt', 'labels-design.dymo', 'labels-data.csv']);
assert.strictEqual(files.filter((f) => f.name.startsWith('labels/')).length, 3);
const csv = files[2].data.replace(/^﻿/, '').split('\r\n');
assert.strictEqual(csv[0], 'Text1,QR1,Text2,QR2');
for (const field of csv[0].split(',')) assert.ok(files[1].data.includes(`<Name>${field}</Name>`), `${field} is in the design`);
assert.ok(csv[1].startsWith('"GL-G-0041\n'), 'a sticker\'s lines in one cell');
// Strips too thin for a QR code: no QR objects, and no QR columns.
const strips = Dymo.files('DY4-075', 'EU', labels, { qr: true });
assert.strictEqual(strips[2].data.replace(/^﻿/, '').split('\r\n')[0], 'Text1,Text2,Text3');
assert.ok(!strips[1].data.includes('QRCodeObject'));
// An LWCS label says how DYMO Connect takes it.
assert.ok(Dymo.files('LWCS-506', 'EU', labels)[0].data.includes('recognises'));

// The zip: its central directory lists every file, at the size given.
const zip = Dymo.zip(files);
const view = new DataView(zip.buffer);
const end = zip.length - 22;
assert.strictEqual(view.getUint32(end, true), 0x06054b50, 'end of central directory');
assert.strictEqual(view.getUint16(end + 10, true), files.length);
let at = view.getUint32(end + 16, true);
const names = [];
for (let i = 0; i < files.length; i++) {
  assert.strictEqual(view.getUint32(at, true), 0x02014b50);
  const length = view.getUint16(at + 28, true);
  names.push(new TextDecoder().decode(zip.slice(at + 46, at + 46 + length)));
  at += 46 + length;
}
assert.deepStrictEqual(names, files.map((f) => f.name));

// The same layout as a picture: the paper's size in inches, the QR codes drawn from the modules
// given, the same lines as the file, and the stickers' outlines marked for the screen only.
const tube = Dymo.stock('DY4-072');
const modules = [[true, false], [false, true]];
const picture = Dymo.svg(tube, labels.slice(0, 1), { qr: true }, () => modules);
const paper = Dymo.paper(tube);
assert.ok(picture.includes(`viewBox="0 0 ${Dymo.num(paper.w)} ${Dymo.num(paper.h)}"`) && picture.includes(`width="${Dymo.num(paper.w)}in"`));
// An LWCS label prints on a page the size of its stickers, not of the DY4 stock it borrows its layout from.
const snap = Dymo.paper(Dymo.stock('LWCS-506'));
assert.ok(snap.w < 1.7 && snap.h < 0.6 && snap.x > 0, `LWCS-506 page ${snap.w} x ${snap.h} in`);
assert.ok(Dymo.svg(Dymo.stock('LWCS-506'), labels.slice(0, 1), {}, () => modules).includes(`viewBox="${Dymo.num(snap.x)} ${Dymo.num(snap.y)} `));
assert.strictEqual((picture.match(/<path d="M/g) || []).length, 1, 'one QR code');
assert.ok(picture.includes('>GL-G-0041</text>') && picture.includes('>G-0041</text>') && picture.includes('rotate(90)'));
assert.ok(!picture.includes('pTest &amp;'), 'the same lines left out as in the file');
assert.ok(picture.includes('class="cut"') && picture.includes('<ellipse class="cut"'), 'outlines, the cap round');
assert.ok(!Dymo.svg(tube, labels.slice(0, 1), { qr: false }, () => modules).includes('<path'), 'no QR when not wanted');

console.log('dymo: all checks passed');
