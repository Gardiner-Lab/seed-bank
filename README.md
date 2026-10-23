# Seed Bank

The Gardiner Lab suite's record of plant lines, the seed lots they are kept as, and the plants
grown from them, with how each descends from the others.

- **Lines** are wild types, mutants, transgenic events, populations and crosses.
  - Each has a species, a background and its parent lines.
  - It also records the **plasmids it carries**, from the Plasmid Editor's library, which open in
    the editor.
- **Seed lots** are seeds of a line and generation (T2, F3…).
  - They come from a plant here, from a cross, or from outside (a stock centre).
  - Each records where it is kept, how much is left, its germination and its zygosity.
- **Plants** are sown from a lot and numbered within it. A plant can be:
  - **harvested** into a new lot, one generation on (T1 → T2);
  - **crossed** with another plant, which makes a new line and its F1 lot;
  - made the **founder of a line** of its own, as an independent T1 transformant is.
- **Lineage** is traced exactly, plant by plant: where a lot or plant came from, everything that
  came from it, and a line's pedigree.
- **Segregation tests** take resistant and sensitive counts from selection plates. A χ² test then
  says whether the counts fit 3:1 (one insertion) or 15:1 (two), or whether a T3 lot is homozygous.
- **Phenotypes** can be recorded on any line, lot or plant, with photos. **3D scans** (STL, PLY
  meshes and point clouds, OBJ, glTF) open in a viewer you can turn, and any other file can be
  attached as well.
- **Labels** with QR codes are printed for seed bags, pots and boxes; a phone opens the record. They
  print from the browser, or go out as files for DYMO Connect on a LabTAG DYMO label (the LWCS labels
  for the LabelWriter 550, or the DY4 range).
- **Lab notebook links**: type `@` in a notebook page to link a lot, plant or line. Each record
  lists the notebook pages that mention it.
- **Who sees what**: a lab's stocks are shared within the lab, and other labs don't see them.
  Administrators see all. Every change is logged with who made it.

## Running it

It runs inside the [Gardiner Lab suite](https://github.com/Gardiner-Lab/gardiner-lab-suite), behind
its proxy at `/seeds/`, signed in through the suite. It has no accounts of its own; don't expose it
outside the proxy.

| Setting | Default | |
| --- | --- | --- |
| `SEEDS_DATABASE_PATH` | `/seeds/seeds.db` | its own data, photos and scans included |
| `MOCLO_DATABASE_PATH` | `/moclo/moclo.db` | the account directory (read only) |
| `SUITE_DATABASE_PATH` | `/suite/suite.db` | labs and their leads (read only) |
| `EDITOR_DATABASE_PATH` | `/editor/plasmid_editor.db` | plasmids (read only) |
| `NOTEBOOK_DATABASE_PATH` | `/notebook/notebook.db` | notebook links (read only) |
| `SUITE_PUBLIC_URL` | (the page's own address) | where phones reach the suite, for label QR codes; the suite dashboard's Hosting tab sets it instead |

## Development

    pip install -r requirements.txt
    pytest -q

## Licence

GNU General Public License v3.0; see [LICENSE](LICENSE). It includes three.js and
qrcode-generator, both MIT; see [NOTICE](NOTICE).
