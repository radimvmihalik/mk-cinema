# MK Cinema

Repozitář doplňku **MK Cinema** (Midar Kilahim Cinema) pro Kodi.

- `repo/` – Kodi repozitář. Doplněk *MK Cinema repozitář* odsud stahuje nové verze.
- `vybery.json` – obsah sekce **Výběry** (Halloween, Vánoce, In memoriam…). Změny se v Kodi projeví do půl hodiny, bez nové verze doplňku.
- `epizody/` – seznamy dílů seriálů pro Výběry (halloweenské a vánoční díly, vytváří je `tools/make_episodes.py` v projektu).

## Typy položek ve `vybery.json`

| type | co dělá | povinné údaje |
|---|---|---|
| (složka) | podsložka s dalšími položkami | `items` |
| `discover` | seznam z TMDB | `media` (`movie`/`tv`), `query` (parametry TMDB discover) |
| `person` | filmografie herce nebo tvůrce | `id` (TMDB id osoby) |
| `titles` | ručně vybrané filmy a seriály | `titles`: `[{"media": "movie", "id": 123}]` |
| `episodes` | vybrané díly seriálů | `file` (cesta k souboru v `epizody/`) |

Volitelně: `color` (barva názvu, např. `FFFF9800`), `home: true` (ukázat i v hlavním menu), `icon`, `from` a `to` (kdy se položka ukazuje, včetně obou dnů).

`from`/`to` ve tvaru `MM-DD` platí každý rok a můžou jít i přes Nový rok (Vánoce `11-03` až `01-06`). Ve tvaru `RRRR-MM-DD` platí jen jednou (např. In memoriam na týden). Položka bez nich se ukazuje pořád. Funguje to i u položek uvnitř složky. Když se zrovna neukazuje žádný výběr, sekce Výběry v hlavním menu chybí (doplněk od verze 1.8.1).

## Žebříčky IMDb

`zebricky.json` počítá jednou měsíčně GitHub Actions (`.github/workflows/zebricky.yml`) skriptem `tools/make_charts.py` z oficiálních dat IMDb: 150 nejlepších a 150 nejhorších titulů v každé kategorii (vážené hodnocení jako u IMDb Top 250, min. 25 000 hlasů u filmů a 10 000 u seriálů) a herce a herečky podle průměru hodnocení filmů, kde hráli hlavní roli (aspoň 10 filmů). Doplněk vyřadí tituly, u kterých se hodnocení IMDb a TMDB liší o víc než 3 body, a ukáže prvních 100.
