# MK Cinema

Repozitář doplňku **MK Cinema** (Midar Kilahim Cinema) pro Kodi.

- `repo/` – Kodi repozitář. Doplněk *MK Cinema repozitář* odsud stahuje nové verze.
- `vybery.json` – obsah sekce **Výběry** (Halloween, Vánoce, In memoriam…). Změny se v Kodi projeví do půl hodiny, bez nové verze doplňku.
- `epizody/` – seznamy dílů seriálů pro Výběry (např. halloweenské díly).

## Typy položek ve `vybery.json`

| type | co dělá | povinné údaje |
|---|---|---|
| (složka) | podsložka s dalšími položkami | `items` |
| `discover` | seznam z TMDB | `media` (`movie`/`tv`), `query` (parametry TMDB discover) |
| `person` | filmografie herce nebo tvůrce | `id` (TMDB id osoby) |
| `titles` | ručně vybrané filmy a seriály | `titles`: `[{"media": "movie", "id": 123}]` |
| `episodes` | vybrané díly seriálů | `file` (cesta k souboru v `epizody/`) |

Volitelně: `color` (barva názvu, např. `FFFF9800`), `home: true` (ukázat i v hlavním menu), `icon`.

## Žebříčky IMDb

`zebricky.json` počítá jednou měsíčně GitHub Actions (`.github/workflows/zebricky.yml`) skriptem `tools/make_charts.py` z oficiálních dat IMDb: 150 nejlepších a 150 nejhorších titulů v každé kategorii (vážené hodnocení jako u IMDb Top 250, min. 25 000 hlasů u filmů a 10 000 u seriálů) a herce a herečky podle průměru hodnocení filmů, kde hráli hlavní roli (aspoň 10 filmů). Doplněk vyřadí tituly, u kterých se hodnocení IMDb a TMDB liší o víc než 3 body, a ukáže prvních 100.
