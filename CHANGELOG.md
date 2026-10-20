# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

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
