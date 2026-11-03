# MK Cinema

Repozitář doplňku **MK Cinema** (Midar Kilahim Cinema) pro Kodi.

- `repo/` – Kodi repozitář. Doplněk *MK Cinema repozitář* odsud stahuje nové verze.
- `vybery.json` – obsah sekce **Výběry**: sezóny Valentýn, Velikonoce, Léto a prázdniny, Halloween, Vánoce (později In memoriam…). Změny se v Kodi projeví do půl hodiny, bez nové verze doplňku.
- `oceneni.json` – Oscary a festivaly (Berlinale, Cannes, Karlovy Vary, Ji.hlava). Generuje se sám každý den, ručně ho neupravuj (viz níže).
- `oceneni-rucne.json` – ručně doplňované ročníky festivalů bez strojově čitelného zdroje (Ji.hlava).
- `epizody/` – seznamy dílů seriálů pro Výběry (halloweenské, vánoční, valentýnské a velikonoční díly, vytváří je `tools/make_episodes.py` v projektu).

## Typy položek ve `vybery.json`

| type | co dělá | povinné údaje |
|---|---|---|
| (složka) | podsložka s dalšími položkami | `items` |
| `discover` | seznam z TMDB | `media` (`movie`/`tv`), `query` (parametry TMDB discover) |
| `person` | filmografie herce nebo tvůrce | `id` (TMDB id osoby) |
| `titles` | ručně vybrané filmy a seriály | `titles`: `[{"media": "movie", "id": 123}]`; místo `id` i `imdb` (`tt…`) nebo `search` + `year`, volitelně `label` (text před názvem), `note` (za názvem) a `title` (když se film v databázi nenajde) |
| `episodes` | vybrané díly seriálů | `file` (cesta k souboru v `epizody/`) |

Volitelně: `color` (barva názvu, např. `FFFF9800`), `home: true` (ukázat i v hlavním menu), `icon`, `from` a `to` (kdy se položka ukazuje, včetně obou dnů).

`from`/`to` ve tvaru `MM-DD` platí každý rok a můžou jít i přes Nový rok (Vánoce `11-02` až `01-06`). Ve tvaru `RRRR-MM-DD` platí jen jednou (např. In memoriam na týden). `velikonoce-30` a `velikonoce+1` počítají dny od Velikonoční neděle daného roku (od verze 1.9.0). Položka bez nich se ukazuje pořád. Funguje to i u položek uvnitř složky. Když se zrovna neukazuje žádný výběr, sekce Výběry v hlavním menu chybí (doplněk od verze 1.8.1).

## Žebříčky IMDb

`zebricky.json` počítá jednou měsíčně GitHub Actions (`.github/workflows/zebricky.yml`) skriptem `tools/make_charts.py` z oficiálních dat IMDb: 150 nejlepších a 150 nejhorších titulů v každé kategorii (vážené hodnocení jako u IMDb Top 250, min. 25 000 hlasů u filmů a 10 000 u seriálů) a herce a herečky podle průměru hodnocení filmů, kde hráli hlavní roli (aspoň 10 filmů). Doplněk vyřadí tituly, u kterých se hodnocení IMDb a TMDB liší o víc než 3 body, a ukáže prvních 100.

## Oscary a festivaly

`oceneni.json` sestavuje každý den GitHub Actions (`.github/workflows/oceneni.yml`) skriptem `tools/make_awards.py`:

- 30 dní před vyhlášením až do dne vyhlášení se ukazují nominace (u festivalu hlavní soutěž), 7 dní po vyhlášení jen vítězové v každé kategorii. U festivalů se za den vyhlášení bere poslední den festivalu.
- Oscary se berou z Wikidat, Berlinale, Cannes a Karlovy Vary z anglické Wikipedie (stránka ročníku: data, hlavní soutěž, ceny).
- Ji.hlava nemá strojově čitelný zdroj. Její ročník se doplňuje ručně do `oceneni-rucne.json` a skript na to od 20. září založí issue.
- Když zdroj zrovna nefunguje, zůstanou výběry z předchozího dne. Ruční spuštění: Actions → Ocenění → Run workflow, místně `python3 tools/make_awards.py --today 2027-03-01 --out /tmp/test.json`.
