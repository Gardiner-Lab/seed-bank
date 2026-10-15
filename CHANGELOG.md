# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

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
