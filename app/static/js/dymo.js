'use strict';
/*
 * Labels for DYMO Connect (the LabelWriter 550's software), on LabTAG's DYMO
 * labels: https://www.labtag.com/resources/templates/dymo-compatible/
 *
 * Each label stock is placed as LabTAG's own templates place it: the DYMO
 * stock it is cut on (LabelName, by region: North America or Europe), and
 * where each sticker on it is - one, or several (2 up, 4 dots, 6 tags), some
 * with a cap circle or strip beside the main part. Each sticker gets a QR code
 * (where there is room) and its code and lines of text, shrunk to fit.
 *
 * An export is a zip: a ready .dymo file for each printed label, to open and
 * print; and, for printing many at once, a design (labels-design.dymo) and the
 * labels as a spreadsheet (labels-data.csv) for DYMO Connect's "Import data".
 *
 * The same file is in Lab Stocks and the Seed Bank.
 */

// Sizes in inches, as DYMO Connect lays out a label. A slot is one sticker:
// `main` its printed part (r: 90 when the text runs along its length, as on a
// tube), `cap` a small part beside it (a cap circle or a strip), if any.
const DYMO_DY4 = (code, products, size, names, orientation, rect, slots) => ({
  id: `DY4-${code}`, range: 'dy4', products, size, names, orientation, rect, slots });
const R = (x, y, w, h, r = 0) => ({ x, y, w, h, r });

const DYMO_STOCKS = [
  DYMO_DY4('010', 'EDY-010, EF1F-010, EDWA-010WH', '25.4 × 54 mm', { NA: 'Small30336', EU: 'Small1976411' }, 'Portrait',
    R(0.04, 0.09, 0.9, 1.98), [{ main: R(0.12, 0.12, 0.74, 1.92, 90) }]),
  DYMO_DY4('020', 'EDY-020 and others', '28.6 × 88.9 mm', { NA: 'Address', EU: 'Address1982991' }, 'Portrait',
    R(0.03, 0.23, 1.0, 3.21), [{ main: R(0.1, 0.23, 0.86, 3.1, 90) }]),
  DYMO_DY4('030', 'EDY-030 and others', '9.5 mm dots, 4 to a label', { NA: 'Small30336', EU: 'Small1976411' }, 'Portrait',
    R(0.04, 0.09, 0.9, 1.98), [R(0.11, 0.12, 0.3, 0.3), R(0.57, 0.12, 0.3, 0.3), R(0.11, 0.82, 0.3, 0.3), R(0.57, 0.82, 0.3, 0.3)]
      .map((dot) => ({ cap: dot }))),
  DYMO_DY4('040', 'EDY-040 and others', '12.7 × 25.4 mm, 2 to a label', { NA: 'Small30333', EU: 'SmallS0722530' }, 'Portrait',
    R(0.04, 0.1, 0.9, 0.84), [{ main: R(0.08, 0.1, 0.32, 0.78, 90) }, { main: R(0.6, 0.1, 0.32, 0.78, 90) }]),
  DYMO_DY4('050', 'EDY-050 and others', '12.7 mm dots, 4 to a label', { NA: 'Small30336', EU: 'Small1976411' }, 'Portrait',
    R(0.04, 0.09, 0.9, 1.98), [R(0.15, 0.13, 0.26, 0.27), R(0.6, 0.13, 0.26, 0.27), R(0.15, 0.74, 0.26, 0.27), R(0.6, 0.73, 0.26, 0.27)]
      .map((dot) => ({ cap: dot }))),
  DYMO_DY4('060', 'EDY-060', '14.2 × 87.4 mm', { NA: 'FileFolder' }, 'Landscape',
    R(0.22, 0.04, 3.16, 0.48), [{ main: R(0.3, 0.06, 3.0, 0.44) }]),
  DYMO_DY4('070', 'EDY-070 and others', '25.4 × 25.4 mm', { NA: 'Small30332', EU: 'SmallS0929120' }, 'Portrait',
    R(0.04, 0.1, 0.9, 0.84), [{ main: R(0.08, 0.12, 0.82, 0.8) }]),
  DYMO_DY4('071', 'EDY-071 and others', '20.1 × 45 mm, with a side strip', { NA: 'Small30336', EU: 'Small1976411' }, 'Portrait',
    R(0.04, 0.09, 0.9, 1.98), [{ main: R(0.08, 0.2, 0.44, 1.59, 90), cap: R(0.77, 0.11, 0.17, 1.91, 90) }]),
  DYMO_DY4('072', 'EDCS-072WH, EDY-072, EG1F-072', '12.7 × 26.4 mm + 9.5 mm cap', { NA: 'Small30336', EU: 'Small1976411' }, 'Portrait',
    R(0.04, 0.09, 0.9, 1.98), [{ main: R(0.29, 0.61, 0.58, 0.9, 90), cap: R(0.39, 1.68, 0.37, 0.39) }]),
  DYMO_DY4('073', 'EDY-073', '17.8 × 37.9 mm', { NA: 'Small30347' }, 'Portrait',
    R(0.04, 0.23, 0.9, 1.21), [{ main: R(0.2, 0.23, 0.6, 1.1, 90) }]),
  DYMO_DY4('074', 'EDY-074', '35.6 × 88.9 mm', { NA: 'FileFolder' }, 'Portrait',
    R(0.04, 0.22, 0.48, 3.16), [{ main: R(0.08, 0.26, 0.4, 3.0, 90) }]),
  DYMO_DY4('075', 'EDY-075', '50.8 × 6.4 mm strips, 3 to a label', { NA: 'ReturnAddress30330', EU: 'ReturnAddressS0722550' }, 'Landscape',
    R(0.23, 0.06, 1.71, 0.65), [0.06, 0.28, 0.52].map((y) => ({ main: R(0.26, y, 1.5, 0.19) }))),
  DYMO_DY4('076', 'EDY-076', '23.9 × 12.7 mm + 11.1 mm cap', { NA: 'LargeShipping', EU: 'LargeShippingS0719190' }, 'Portrait',
    R(0.04, 0.23, 2.22, 3.71), [{ main: R(0.24, 0.25, 0.91, 0.48), cap: R(1.38, 0.3, 0.4, 0.42) }]),
  DYMO_DY4('079', 'EDY-079', '20.1 × 5.1 mm + 6.4 mm cap, 6 to a label', { NA: 'LargeShipping', EU: 'LargeShippingS0719190' }, 'Portrait',
    R(0.04, 0.23, 2.22, 3.71), [[0.28, 0.32], [0.54, 0.57], [0.83, 0.87], [1.8, 1.85], [2.05, 2.09], [2.28, 2.32]]
      // The tags are 5.1 mm (0.2 in) tall, by LabTAG's die-cut shapes: their sample text boxes are
      // taller, and would overlap the next tag. Each is the tag itself, centred as LabTAG centres it;
      // too thin for a QR code.
      .map(([y, capY]) => ({ main: R(0.04, y + 0.095, 0.8, 0.2), cap: R(0.85, capY, 0.3, 0.31), noQr: true }))),
  DYMO_DY4('080', 'EDY-080', '19.1 × 38.1 mm', { NA: 'Small30336', EU: 'Small1976411' }, 'Portrait',
    R(0.04, 0.09, 0.9, 1.98), [{ main: R(0.16, 0.09, 0.68, 1.17, 90) }]),
  DYMO_DY4('081', 'EDY-081 and others', '26.4 × 12.7 mm + 9.5 mm cap', { NA: 'LargeShipping', EU: 'LargeShippingS0719190' }, 'Portrait',
    R(0.04, 0.23, 2.22, 3.71), [{ main: R(0.24, 0.25, 0.91, 0.48), cap: R(1.35, 0.27, 0.31, 0.38) }]),
  DYMO_DY4('082', 'EDY-082 and others', '57.2 × 31.8 mm', { NA: 'Small30334', EU: 'S0722540 multipurpose' }, 'Portrait',
    R(0.04, 0.06, 2.17, 1.13), [{ main: R(0.1, 0.1, 2.05, 1.05) }]),
  DYMO_DY4('083', 'EDY-083', '54 × 101 mm', { NA: 'Shipping', EU: 'LargeShippingS0719190' }, 'Portrait',
    R(0.04, 0.21, 2.03, 3.7), [{ main: R(0.4, 0.4, 1.3, 3.1, 90) }]),
  DYMO_DY4('084', 'EDY-084 and others', '31.8 × 12.7 mm + 11.1 mm cap', { NA: 'LargeShipping', EU: 'LargeShippingS0719190' }, 'Portrait',
    R(0.04, 0.23, 2.22, 3.71), [{ main: R(0.35, 0.24, 0.81, 0.3), cap: R(1.71, 0.23, 0.37, 0.31) }]),
];

// LabTAG's LabelWriter 550 labels (LWCS). LabTAG publishes no template files for them: DYMO Connect
// has its own, and recognises the roll in the printer. Each is laid out as the DY4 label of the same
// size; with an LWCS roll in the 550, DYMO Connect may ask to use the loaded label - say yes.
const DYMO_LWCS = [
  ['LWCS-501', '50.8 × 25.4 mm (2 × 1 in)', 'DY4-010'],
  ['LWCS-502', '50.8 × 6.4 mm (2 × 0.25 in)', 'DY4-075'],
  ['LWCS-504', '25.4 × 25.4 mm (1 × 1 in)', 'DY4-070'],
  ['LWCS-505', '25.4 × 12.7 mm (1 × 0.5 in)', 'DY4-040'],
  ['LWCS-506', '23.9 × 12.7 mm + 9.5 mm cap, SnapPeel', 'DY4-076'],
].map(([id, size, like]) => ({ ...DYMO_STOCKS.find((s) => s.id === like), id, range: 'lwcs', size, products: id, like }));

const Dymo = {
  stocks: [...DYMO_LWCS, ...DYMO_STOCKS],
  RANGES: { lwcs: 'LabTAG LWCS · LabelWriter 550', dy4: 'LabTAG DY4 · LabelWriter 450 series' },
  MIN_QR: 0.3,               // inches: a QR code smaller than this does not scan reliably
  GAP: 0.04,
  MIN_PT: 5.5,               // points: smaller printed text is hard to read

  /**
   * The lines that fit a box of text legibly: the code always, then each further line only if
   * the text (shrunk to fit as one block) can stay at MIN_PT or larger. A long line that would
   * shrink everything is left out; the QR code leads to the rest.
   */
  fitLines(lines, along, across) {
    const chosen = [lines[0]];
    for (const line of lines.slice(1)) {
      if (this.pointSize([...chosen, line], along, across) >= this.MIN_PT) chosen.push(line);
    }
    return chosen;
  },

  /** About the size, in points, lines of text take when shrunk together to fit a box (inches). */
  pointSize(lines, along, across) {
    return Math.min(across * 72 / (lines.length * 1.25),
      ...lines.map((line) => along * 72 / (Math.max(String(line).length, 4) * 0.56)));
  },

  stock(id) { return this.stocks.find((s) => s.id === id) || this.stocks[0]; },

  esc: (s) => String(s ?? '').replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch])),
  num: (n) => String(Math.round(n * 10000) / 10000),

  /** A code as short as it can be and still be read: "GL-G-0042" -> "G-0042". */
  shortCode: (code) => String(code).split('-').slice(-2).join('-'),

  brushes(background, fill) {
    const brush = (tag, [a, r, g, b]) => `<${tag}><SolidColorBrush><Color A="${a}" R="${r}" G="${g}" B="${b}"></Color></SolidColorBrush></${tag}>`;
    return `<Brushes>${brush('BackgroundBrush', background)}${brush('BorderBrush', [1, 0, 0, 0])}`
      + `${brush('StrokeBrush', [1, 0, 0, 0])}${brush('FillBrush', fill)}</Brushes>`;
  },

  layout(box) {
    return `<ObjectLayout><DYMOPoint><X>${this.num(box.x)}</X><Y>${this.num(box.y)}</Y></DYMOPoint>`
      + `<Size><Width>${this.num(box.w)}</Width><Height>${this.num(box.h)}</Height></Size></ObjectLayout>`;
  },

  /** A text object: lines (the first bold), shrunk to fit its box, turned 90° when r is 90. */
  text(name, box, lines, { size = 8, bold = true } = {}) {
    const spans = lines.map((line, i) => `<LineTextSpan><TextSpan><Text>${this.esc(line)}</Text><FontInfo>`
      + `<FontName>Segoe UI</FontName><FontSize>${i === 0 ? size + 1 : size}</FontSize><IsBold>${i === 0 && bold ? 'True' : 'False'}</IsBold>`
      + '<IsItalic>False</IsItalic><IsUnderline>False</IsUnderline><FontBrush><SolidColorBrush><Color A="1" R="0" G="0" B="0"></Color>'
      + '</SolidColorBrush></FontBrush></FontInfo></TextSpan></LineTextSpan>').join('');
    return `<TextObject><Name>${this.esc(name)}</Name>${this.brushes([0, 0, 0, 0], [0, 0, 0, 0])}`
      + `<Rotation>Rotation${box.r || 0}</Rotation><OutlineThickness>1</OutlineThickness><IsOutlined>False</IsOutlined>`
      + '<BorderStyle>SolidLine</BorderStyle><Margin><DYMOThickness Left="0" Top="0" Right="0" Bottom="0" /></Margin>'
      + '<HorizontalAlignment>Center</HorizontalAlignment><VerticalAlignment>Middle</VerticalAlignment><FitMode>AlwaysFit</FitMode>'
      + '<IsVertical>False</IsVertical><FormattedText><FitMode>AlwaysFit</FitMode><HorizontalAlignment>Center</HorizontalAlignment>'
      + `<VerticalAlignment>Middle</VerticalAlignment><IsVertical>False</IsVertical>${spans}</FormattedText>${this.layout(box)}</TextObject>`;
  },

  /** A QR code object, as DYMO Connect writes one: what it holds in both of its data nodes. */
  qr(name, box, value) {
    return `<QRCodeObject><Name>${this.esc(name)}</Name>${this.brushes([1, 1, 1, 1], [1, 0, 0, 0])}`
      + `<Rotation>Rotation${box.r || 0}</Rotation><OutlineThickness>1</OutlineThickness><IsOutlined>False</IsOutlined>`
      + '<BorderStyle>SolidLine</BorderStyle><Margin><DYMOThickness Left="0" Top="0" Right="0" Bottom="0" /></Margin>'
      + `<BarcodeFormat>QRCode</BarcodeFormat><Data><DataString>${this.esc(value)}</DataString></Data>`
      + '<HorizontalAlignment>Center</HorizontalAlignment><VerticalAlignment>Middle</VerticalAlignment><Size>Medium</Size>'
      + `<EQRCodeType>QRCodeText</EQRCodeType><TextDataHolder><Value>${this.esc(value)}</Value></TextDataHolder>`
      + `${this.layout({ ...box, r: 0 })}</QRCodeObject>`;
  },

  /** The side of the QR code a sticker's main part holds: 0 when it has none (no room, or not wanted). */
  qrSide(slot, { qr = true } = {}) {
    const m = slot.main;
    if (!qr || !m || slot.noQr) return 0;
    const side = Math.min(m.r === 90 ? m.w : m.h, (m.r === 90 ? m.h : m.w) * 0.45);
    return side >= this.MIN_QR ? side : 0;
  },

  /**
   * One sticker's layout: in its main part a QR code at one end, where it fits, and the code and
   * lines along the rest; in its cap (or strip) the short code. As [{kind: 'qr'|'text', name, box,
   * value | lines, size}], drawn as DYMO objects (sticker) or as a picture (svg). `n` numbers the
   * objects, so a design names its fields Text1, QR1, Cap1, Text2...
   */
  objects(slot, label, n, options = {}) {
    const out = [];
    const lines = [label.code, ...label.lines.filter(Boolean).slice(0, 3)];
    if (slot.main) {
      const m = slot.main;
      const across = m.r === 90 ? m.w : m.h;          // across the way the text runs
      const side = label.url ? this.qrSide(slot, options) : 0;
      if (side) {
        const q = m.r === 90
          ? { x: m.x + (m.w - side) / 2, y: m.y, w: side, h: side }
          : { x: m.x, y: m.y + (m.h - side) / 2, w: side, h: side };
        const rest = m.r === 90
          ? { x: m.x, y: m.y + side + this.GAP, w: m.w, h: m.h - side - this.GAP, r: 90 }
          : { x: m.x + side + this.GAP, y: m.y, w: m.w - side - this.GAP, h: m.h, r: 0 };
        const along = m.r === 90 ? rest.h : rest.w;
        out.push({ kind: 'qr', name: `QR${n}`, box: q, value: label.url },
          { kind: 'text', name: `Text${n}`, box: rest, lines: this.fitLines(lines, along, across) });
      } else {
        const along = m.r === 90 ? m.h : m.w;
        // A strip too thin for two lines: one, the code with its first line beside it while that stays legible.
        const beside = `${label.code}  ${lines[1] || ''}`.trim();
        const shown = across < 0.25
          ? [this.pointSize([beside], along, across) >= this.MIN_PT ? beside : label.code]
          : this.fitLines(lines, along, across);
        out.push({ kind: 'text', name: `Text${n}`, box: m, lines: shown });
      }
    }
    if (slot.cap) out.push({ kind: 'text', name: `Cap${n}`, box: slot.cap, lines: [this.shortCode(label.code)], size: 6 });
    return out;
  },

  /** One sticker as DYMO objects. */
  sticker(slot, label, n, options = {}) {
    return this.objects(slot, label, n, options).map((o) => (o.kind === 'qr'
      ? this.qr(o.name, o.box, o.value) : this.text(o.name, o.box, o.lines, o.size ? { size: o.size } : {}))).join('');
  },

  /**
   * The page a printed label takes, in inches ({x, y} its corner in the layout): for a DY4 label the
   * DYMO stock LabTAG's template prints on, its printable area with the margins around it; for an
   * LWCS label, whose liner LabTAG does not publish, the stickers themselves with a small margin,
   * so a page printed to the 550 is the size of the label in it.
   */
  paper(stock) {
    if (stock.range !== 'lwcs') return { x: 0, y: 0, w: stock.rect.x * 2 + stock.rect.w, h: stock.rect.y * 2 + stock.rect.h };
    const parts = stock.slots.flatMap((slot) => [slot.main, slot.cap].filter(Boolean));
    const m = 0.04;
    const x = Math.min(...parts.map((p) => p.x)) - m;
    const y = Math.min(...parts.map((p) => p.y)) - m;
    return { x, y, w: Math.max(...parts.map((p) => p.x + p.w)) + m - x, h: Math.max(...parts.map((p) => p.y + p.h)) + m - y };
  },

  /**
   * One printed label as a picture (SVG markup, in inches): the stickers' outlines (class "cut",
   * for the screen only), and on them what the .dymo file prints - QR codes and text, the text
   * shrunk to fit its box as DYMO Connect does. qrModules(value) gives a QR code's modules as rows
   * of booleans (the page's qrcode-generator).
   */
  svg(stock, labels, options = {}, qrModules = null) {
    const { x, y, w, h } = this.paper(stock);
    const n = (v) => this.num(v);
    const parts = [];
    stock.slots.forEach((slot, i) => {
      for (const part of [slot.main, slot.cap].filter(Boolean)) {
        const round = Math.abs(part.w - part.h) < 0.12 && part === slot.cap;
        parts.push(round
          ? `<ellipse class="cut" cx="${n(part.x + part.w / 2)}" cy="${n(part.y + part.h / 2)}" rx="${n(part.w / 2)}" ry="${n(part.h / 2)}"/>`
          : `<rect class="cut" x="${n(part.x)}" y="${n(part.y)}" width="${n(part.w)}" height="${n(part.h)}" rx="0.03"/>`);
      }
      if (!labels[i]) return;
      for (const o of this.objects(slot, labels[i], i + 1, options)) {
        const b = o.box;
        if (o.kind === 'qr') {
          const modules = qrModules ? qrModules(o.value) : null;
          if (!modules) {
            parts.push(`<rect x="${n(b.x)}" y="${n(b.y)}" width="${n(b.w)}" height="${n(b.h)}" fill="#000" opacity=".15"/>`);
            continue;
          }
          const cell = b.w / modules.length;
          let d = '';
          modules.forEach((row, r) => row.forEach((on, c) => {
            if (on) d += `M${n(b.x + c * cell)} ${n(b.y + r * cell)}h${n(cell)}v${n(cell)}h-${n(cell)}z`;
          }));
          parts.push(`<path d="${d}" fill="#000"/>`);
          continue;
        }
        // Text across the box, or along it when turned 90°, centred, all lines one size; in a round cap,
        // within the circle (about 0.7 of its width). Bold digits run wider than the average glyph.
        const round = o.name.startsWith('Cap') && Math.abs(b.w - b.h) < 0.12;
        const along = (b.r === 90 ? b.h : b.w) * (round ? 0.7 : 1);
        const across = (b.r === 90 ? b.w : b.h) * (round ? 0.7 : 1);
        const longest = Math.max(...o.lines.map((l) => String(l).length), 3);
        const size = Math.min(across / (o.lines.length * 1.2), along / (longest * 0.64), 0.3);
        const cx = b.x + b.w / 2;
        const cy = b.y + b.h / 2;
        const top = -((o.lines.length - 1) * size * 1.2) / 2;
        const spans = o.lines.map((line, k) => `<text x="0" y="${n(top + k * size * 1.2)}" font-size="${n(size)}"`
          + `${k === 0 ? ' font-weight="700"' : ''} text-anchor="middle" dominant-baseline="central">${this.esc(line)}</text>`).join('');
        parts.push(`<g transform="translate(${n(cx)} ${n(cy)})${b.r === 90 ? ' rotate(90)' : ''}">${spans}</g>`);
      }
    });
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${n(x)} ${n(y)} ${n(w)} ${n(h)}" width="${n(w)}in" height="${n(h)}in"`
      + ` font-family="Segoe UI, Arial, sans-serif" fill="#000">${parts.join('')}</svg>`;
  },

  /** A .dymo file (DYMO Connect's own format): one printed label holding these stickers. */
  file(stock, region, labels, options) {
    const name = stock.names[region] || stock.names.NA || Object.values(stock.names)[0];
    const objects = stock.slots.map((slot, i) => (labels[i] ? this.sticker(slot, labels[i], i + 1, options) : '')).join('');
    const r = stock.rect;
    return '﻿<?xml version="1.0" encoding="utf-8"?>\n<DesktopLabel Version="1"><DYMOLabel Version="3">'
      + `<Description>${this.esc(`${stock.id}: ${labels.map((l) => l.code).join(', ')}`)}</Description>`
      + `<Orientation>${stock.orientation}</Orientation><LabelName>${this.esc(name)}</LabelName><InitialLength>0</InitialLength>`
      + `<BorderStyle>SolidLine</BorderStyle><DYMORect><DYMOPoint><X>${this.num(r.x)}</X><Y>${this.num(r.y)}</Y></DYMOPoint>`
      + `<Size><Width>${this.num(r.w)}</Width><Height>${this.num(r.h)}</Height></Size></DYMORect>`
      + '<BorderColor><SolidColorBrush><Color A="1" R="0" G="0" B="0"></Color></SolidColorBrush></BorderColor>'
      + '<BorderThickness>1</BorderThickness><Show_Border>False</Show_Border><DynamicLayoutManager>'
      + `<RotationBehavior>ClearObjects</RotationBehavior><LabelObjects>${objects}</LabelObjects></DynamicLayoutManager>`
      + '</DYMOLabel><LabelApplication>Blank</LabelApplication><DataTable><Columns></Columns><Rows></Rows></DataTable></DesktopLabel>\n';
  },

  /** The labels, a printed label's worth of stickers at a time. */
  groups(stock, labels) {
    const per = stock.slots.length;
    const out = [];
    for (let i = 0; i < labels.length; i += per) out.push(labels.slice(i, i + per));
    return out;
  },

  /** The labels as a spreadsheet for DYMO Connect's Import data: a row per printed label, columns as the design names its fields. */
  csv(stock, labels, options = {}) {
    // The columns are the design's fields, so each has an object to go into.
    const columns = [];
    stock.slots.forEach((slot, i) => {
      if (slot.main) columns.push(`Text${i + 1}`, ...(this.qrSide(slot, options) ? [`QR${i + 1}`] : []));
      if (slot.cap) columns.push(`Cap${i + 1}`);
    });
    const cell = (v) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
    const rows = this.groups(stock, labels).map((group) => columns.map((col) => {
      const n = Number(col.match(/\d+$/)[0]);
      const label = group[n - 1];
      if (!label) return '';
      if (col.startsWith('QR')) return label.url || '';
      if (col.startsWith('Cap')) return this.shortCode(label.code);
      return [label.code, ...label.lines.filter(Boolean).slice(0, 3)].join('\n');
    }).map(cell).join(','));
    return `﻿${[columns.join(','), ...rows].join('\r\n')}\r\n`;
  },

  readme(stock, region, count, groups) {
    const lwcs = stock.range === 'lwcs'
      ? `\r\nThis is a LabelWriter 550 (LWCS) label. LabTAG publishes no template for it, so these files use the\r\n`
        + `layout of ${stock.like}, the DY4 label of the same size. With the LWCS roll in the printer, DYMO Connect\r\n`
        + 'recognises it; if it asks whether to use the label in the printer, say yes.\r\n'
      : '';
    return [`${count} label${count === 1 ? '' : 's'} on LabTAG ${stock.id} (${stock.size}; ${stock.products}),`,
      `${groups} printed label${groups === 1 ? '' : 's'}, for DYMO Connect (${region === 'EU' ? 'Europe' : 'North America'}).`, lwcs,
      'TO PRINT A FEW: open a file in the "labels" folder in DYMO Connect (Open > Browse) and print it.',
      'Each file is one printed label, with its stickers filled in.', '',
      'TO PRINT MANY AT ONCE: open labels-design.dymo in DYMO Connect, choose Import data, pick',
      'labels-data.csv, and connect each column to the object of the same name (Text1, QR1, Cap1 ...).',
      'Then print: one printed label for each row.', '',
      'If DYMO Connect will not open a file, the computer may be set to the other region: export again',
      'with the other region chosen.', ''].join('\r\n');
  },

  /** Everything for DYMO Connect, as files: [{name, data}]. */
  files(stockId, region, labels, options = {}) {
    const stock = this.stock(stockId);
    const groups = this.groups(stock, labels);
    const safe = (s) => String(s).replace(/[^A-Za-z0-9._-]+/g, '_');
    return [
      { name: 'README.txt', data: this.readme(stock, region, labels.length, groups.length) },
      { name: 'labels-design.dymo', data: this.file(stock, region, groups[0] || [], options) },
      { name: 'labels-data.csv', data: this.csv(stock, labels, options) },
      ...groups.map((group, i) => ({
        name: `labels/${String(i + 1).padStart(3, '0')}_${safe(group.map((l) => l.code).join('_')).slice(0, 80)}.dymo`,
        data: this.file(stock, region, group, options),
      })),
    ];
  },

  /** Files as a zip (stored, not compressed: label files are small), as a Uint8Array. */
  zip(files) {
    const enc = new TextEncoder();
    const table = new Uint32Array(256).map((_, n) => {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      return c >>> 0;
    });
    const crc32 = (bytes) => {
      let c = 0xffffffff;
      for (const b of bytes) c = table[(c ^ b) & 0xff] ^ (c >>> 8);
      return (c ^ 0xffffffff) >>> 0;
    };
    const now = new Date();
    const time = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
    const date = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
    const chunks = [];
    const central = [];
    let offset = 0;
    for (const file of files) {
      const name = enc.encode(file.name);
      const data = typeof file.data === 'string' ? enc.encode(file.data) : file.data;
      const crc = crc32(data);
      const local = new DataView(new ArrayBuffer(30));
      local.setUint32(0, 0x04034b50, true); local.setUint16(4, 20, true); local.setUint16(6, 0x0800, true);
      local.setUint16(8, 0, true); local.setUint16(10, time, true); local.setUint16(12, date, true);
      local.setUint32(14, crc, true); local.setUint32(18, data.length, true); local.setUint32(22, data.length, true);
      local.setUint16(26, name.length, true); local.setUint16(28, 0, true);
      chunks.push(new Uint8Array(local.buffer), name, data);
      const head = new DataView(new ArrayBuffer(46));
      head.setUint32(0, 0x02014b50, true); head.setUint16(4, 20, true); head.setUint16(6, 20, true);
      head.setUint16(8, 0x0800, true); head.setUint16(10, 0, true); head.setUint16(12, time, true);
      head.setUint16(14, date, true); head.setUint32(16, crc, true); head.setUint32(20, data.length, true);
      head.setUint32(24, data.length, true); head.setUint16(28, name.length, true);
      head.setUint32(42, offset, true);
      central.push(new Uint8Array(head.buffer), name);
      offset += 30 + name.length + data.length;
    }
    const size = central.reduce((n, c) => n + c.length, 0);
    const end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true);
    end.setUint32(12, size, true); end.setUint32(16, offset, true);
    const parts = [...chunks, ...central, new Uint8Array(end.buffer)];
    const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
    let at = 0;
    for (const p of parts) { out.set(p, at); at += p.length; }
    return out;
  },

  /** Save the zip in the browser. */
  download(filename, bytes) {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }));
    link.download = filename;
    document.body.append(link);
    link.click();
    setTimeout(() => { URL.revokeObjectURL(link.href); link.remove(); }, 1000);
  },
};

if (typeof module !== 'undefined') module.exports = { Dymo, DYMO_STOCKS, DYMO_LWCS };
