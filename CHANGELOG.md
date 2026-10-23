# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

## [0.5.0] - 2026-10-23

### Changed
- A tick in the header of each list - lines, seed lots, plants, and a lot's plants sown - chooses
  every row it shows (what a search has left) for labels, or none; it is half-ticked when only some
  are chosen.
- The labels page shows and prints the labels as the LabTAG DYMO label chosen, in place of its three
  generic sizes.

### Added
- **Labels for the DYMO LabelWriter, on LabTAG labels.** On the labels page, choose a LabTAG DYMO
  label - the LWCS labels made for the LabelWriter 550, or the DY4 range on LabTAG's DYMO-compatible
  templates page. The page shows the labels as they will print on it, 🖨 Print prints them one to a
  page of the label's size, and ⬇ DYMO files (for the region DYMO Connect is set to) downloads a zip
  for DYMO Connect. The zip holds a ready
  .dymo file for each printed label, to open and print in DYMO Connect, and a design with the labels
  as a spreadsheet, to print many at once with Import data. Each sticker gets its code and lines
  (shrunk to fit) and a QR code where it has room; a cap circle or strip gets the short code; labels
  with several stickers (2 up, dots, tags) are filled in order. The LWCS labels have no published
  template: they are laid out as the DY4 label of the same size, and DYMO Connect takes the roll in
  the printer.

## [0.4.1] - 2026-10-21

### Added
- Seed lots in eLabJournal, as Lab Stocks copies them there: above the lists, how many of the lab's
  are sent, waiting, archived in eLab or failed (each failed lot with the reason), with Send now; on
  a lot's page, its sample in eLab and how it stands, with sending it now or again. Both stay hidden
  when the lab does not copy its seed lots. Needs Lab Stocks 0.4.3 (STOCKS_URL, default /stocks).

## [0.4.0] - 2026-10-20

### Added
- A line's biosafety, stock center and genetics, as the GMO register (and eLabJournal's Plant Seed
  type) asks: permit and biosafety level (empty: the lab's own), GMO type, gene expression, selection
  marker, mutation information, construction method, stock center collection and number, accession
  and a link to the stock center. Lab Stocks sends them to eLab with the line's seed lots.

## [0.3.0] - 2026-10-19

### Changed
- People can be in several labs: they see the records of all of them, and choose which lab a new line
  goes to (a picker at the top, for someone in more than one; their first lab until they choose). A
  seed lot belongs to its line's lab. A lab's code is chosen by that lab's lead.
- Plasmids follow the Plasmid Editor: always the owner's labs', every lab's once public.

## [0.2.0] - 2026-10-15

### Changed
- **Every code starts with its lab's code**, so no two labs' codes are ever the same and you can
  tell from a code whose it is: GL-L-0001 a line, GL-S-0042 a seed lot, GL-P-0012 a plant.
  - Each lab numbers from 1.
  - A lab's code comes from its initials (Gardiner Lab → GL). A clash gets a number (Green Lab → GL2).
  - The lab lead or an admin can choose the code before the lab's first record. After that it is
    fixed, as codes on labels never change.
  - Codes made before this (S-0001) keep working everywhere.

## [0.1.0] - 2026-10-15

The first release.

### Added
- **Help**: how to enter seeds, plants and lines so they can be traced.
  - The three records, and golden rules.
  - Step-by-step routes: seeds from outside, a transformation from dipping to a homozygous T3, a cross.
  - Phenotypes, storage, special cases such as bulk harvests, and fixing mistakes.
  - Linked from the top bar and from empty lists.
- Lines, seed lots and plants, with lineage traced plant by plant, and line pedigrees.
- Harvest a dipped plant **into the transgenic line**: its seeds become that line's T1, traced back to
  the plant.
- A seed lot put in the wrong line can be moved to the right one, until plants are sown from it.
- Sow, harvest (the next generation), cross (a new line and its F1 lot), and found a line from a
  plant (an independent T1 transformant).
- Plasmids carried by each line, from the Plasmid Editor's library.
- Segregation tests with χ² for 3:1 and 15:1, and a homozygosity check.
- Storage locations, amounts, germination and zygosity of seed lots.
- Phenotype records with photos; 3D scans (STL, PLY, OBJ, glTF) in a viewer you can turn; any
  other file.
- Labels with QR codes in three sizes, for seed bags, pots and boxes.
- Links from the Lab Notebook, and the pages that mention each record.
- A lab's stocks are shared within the lab and hidden from other labs; administrators see all.
  Every change is logged.
