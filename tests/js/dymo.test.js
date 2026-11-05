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
  // A sheet label names the DYMO stock it is cut on. A roll is its own label, and names one only
  // where somebody has recorded what DYMO Connect calls it, so that it is never named wrongly.
  if (s.roll) assert.deepStrictEqual(s.names, {}, `${s.id}: a roll names no DYMO stock of its own`);
  else assert.ok(s.names.NA || s.names.EU, `${s.id}: a DYMO stock name`);
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
assert.strictEqual(csv[0], 'QR1,Text1,Text1b,QR2,Text2,Text2b');
for (const field of csv[0].split(',')) assert.ok(files[1].data.includes(`<Name>${field}</Name>`), `${field} is in the design`);
// DYMO Connect's import reads a line break as the end of the row, quoted or not, which left every
// column after it unread. So no cell holds one: a sticker's lines are a column each (Text1, Text1b,
// Text1c), and a row is one line of the file.
assert.ok(!csv.some((line) => line.includes('\n')), 'no line break inside a row');
assert.strictEqual(csv.filter(Boolean).length, 1 + Dymo.groups(twoUp, labels).length, 'a header and a row per printed label');
const split = (line) => line.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/);
for (const line of csv.filter(Boolean)) assert.strictEqual(split(line).length, split(csv[0]).length, 'every row has every column');
// The design and the spreadsheet are read from the same objects, so neither can name a field the other lacks.
const named = [...new Set([...files[1].data.matchAll(/<Name>([^<]+)<\/Name>/g)].map((m) => m[1]))];
assert.deepStrictEqual(csv[0].split(',').slice().sort(), named.slice().sort(), 'the columns are exactly the design\'s fields');
// A sticker with room for several lines: a column for each, the code in its own cell.
const long = Dymo.files('DY4-010', 'EU', labels.slice(0, 1), { qr: true })[2].data.replace(/^﻿/, '').split('\r\n');
assert.ok(long[0].includes('Text1,Text1b,Text1c'), 'each line of text is a column of its own');
assert.ok(long[1].includes('GL-G-0041,'), 'the code is a cell of its own');
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

// --- Labels the lab has measured itself (the suite's label_stocks) --------------------------
// Sigma Z743355: a 38.1 x 12.7 mm tag with a 9.5 mm spot 5 mm to its right, and no DYMO stock
// recorded for the roll. Millimetres in, inches out, and the file names no label stock.
const measured = [{ id: 'abc-123', name: 'Cryo-Tag 38 mm', tag_w: 38.1, tag_h: 12.7, spot: 9.5, gap: 5,
  dymo_label: '', orientation: 'Landscape' }];
const [own] = Dymo.own(measured);
assert.strictEqual(own.range, 'own');
assert.ok(own.roll, 'a label of the lab\'s own is a roll');
assert.strictEqual(Dymo.num(own.slots[0].main.w), '1.5', '38.1 mm is 1.5 in');
assert.strictEqual(Dymo.num(own.slots[0].main.h), '0.5');
assert.strictEqual(Dymo.num(own.slots[0].cap.w), '0.374', '9.5 mm spot');
// The spot sits past the tag and the gap, and is centred on the tag's height.
assert.strictEqual(Dymo.num(own.slots[0].cap.x - (own.slots[0].main.x + own.slots[0].main.w)), '0.1969', '5 mm gap');
assert.ok(Math.abs((own.slots[0].cap.y + own.slots[0].cap.h / 2) - (own.slots[0].main.y + own.slots[0].main.h / 2)) < 0.001);
assert.strictEqual(own.size, '38.1 × 12.7 mm + 9.5 mm spot');
assert.strictEqual(Dymo.called(own), 'Cryo-Tag 38 mm', 'named, not a uuid');
assert.strictEqual(Dymo.stock('abc-123').id, 'abc-123', 'offered beside LabTAG\'s');
// Its page is the label itself: tag + gap + spot across, the tag's height down, and a small margin.
const ownPaper = Dymo.paper(own);
assert.ok(Math.abs(ownPaper.w - (1.5 + 0.1969 + 0.374 + 0.08)) < 0.01, `page ${ownPaper.w} in across`);
assert.ok(Math.abs(ownPaper.h - (0.5 + 0.08)) < 0.01, `page ${ownPaper.h} in down`);
// Nobody has said what DYMO Connect calls the roll, so the file names no stock at all - naming the
// wrong one is what sent LWCS-506 to a 56 x 94 mm shipping template.
const ownFiles = Dymo.files('abc-123', 'EU', labels.slice(0, 1), { qr: true });
const ownDesign = ownFiles.find((f) => f.name === 'labels-design.dymo').data;
assert.ok(!ownDesign.includes('<LabelName>'), 'no label stock named when none is known');
assert.ok(ownFiles[0].data.includes('prints on the label already loaded'), 'the README says so');
assert.ok(ownFiles[0].data.includes('Cryo-Tag 38 mm'), 'the README names the label');
// With a name recorded, that stock is asked for.
const [withName] = Dymo.own([{ ...measured[0], dymo_label: 'Small30336' }]);
assert.ok(Dymo.file(withName, 'EU', labels.slice(0, 1), {}).includes('<LabelName>Small30336</LabelName>'));
// An LWCS label no longer borrows the DY4 sheet's stock: LWCS-506's was a 56 x 94 mm shipping label.
const snapFile = Dymo.file(Dymo.stock('LWCS-506'), 'EU', labels.slice(0, 1), {});
assert.ok(!snapFile.includes('LargeShipping'), 'LWCS-506 does not ask for a shipping label');
assert.ok(!snapFile.includes('<LabelName>'), 'and names no stock of its own');
// A DY4 sheet label is unchanged: it still names its stock and keeps its printable area.
const sheet = Dymo.file(Dymo.stock('DY4-072'), 'EU', labels.slice(0, 1), {});
assert.ok(sheet.includes('<LabelName>Small1976411</LabelName>'), 'a sheet label still names its stock');
assert.ok(sheet.includes(`<X>${Dymo.num(Dymo.stock('DY4-072').rect.x)}</X>`), 'and keeps its printable area');
Dymo.own([]);                                   // back to LabTAG's alone, for anything after this
assert.ok(!Dymo.stocks.some((s) => s.range === 'own'));

// --- The separator DYMO Connect splits a row on -----------------------------------------------
// On a Dutch or German computer the list separator is a semicolon, and a file of commas arrives as
// one column - which is why the spreadsheet had to be opened in Excel and saved again.
const semi = Dymo.files('DY4-040', 'NA', labels, { qr: true, separator: ';' })[2].data.replace(/^﻿/, '');
const rowsOf = (text) => text.split('\r\n').filter(Boolean);
assert.strictEqual(rowsOf(semi)[0], 'QR1;Text1;Text1b;QR2;Text2;Text2b', 'semicolons between the columns');
for (const line of rowsOf(semi)) {
  assert.strictEqual(line.split(/;(?=(?:[^"]*"[^"]*")*[^"]*$)/).length, 6, 'every row has every column');
}
// A comma in a cell needs no quotes when the separator is a semicolon, and the other way about.
const commaInside = [{ code: 'GL-G-0041', lines: ['one, two', 'three'], url: 'u' }];
assert.ok(Dymo.files('DY4-010', 'EU', commaInside, { separator: ';' })[2].data.includes('one, two;'),
  'a comma in a cell is left alone when semicolons separate');
assert.ok(Dymo.files('DY4-010', 'EU', commaInside, { separator: ',' })[2].data.includes('"one, two",'),
  'and is quoted when commas do');
assert.ok(Dymo.files('DY4-010', 'EU', commaInside, { separator: ';' })[0].data.includes('separated by a semicolon'),
  'the README says which separator was used');
assert.ok([';', ','].includes(Dymo.separator()), 'a separator is chosen for this computer');

console.log('dymo: all checks passed');
