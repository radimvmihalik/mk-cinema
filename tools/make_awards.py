"""Builds oceneni.json: Výběry for the Oscars and film festivals (Berlinale, Cannes, Karlovy Vary, Ji.hlava).

For 30 days up to the day the awards are given (for a festival: its last day, however many
ceremonies it has) a pick shows the nominations or the main competition; for 7 days after it
only the winners. Every pick carries its own from/to dates, so MK Cinema shows it on time even
if this script did not run that day. Run daily by .github/workflows/oceneni.yml.

Sources: Wikidata (Oscars), English Wikipedia (festival line-ups, awards, dates) and
oceneni-rucne.json, filled by hand for festivals without any machine-readable source (Ji.hlava).

    python3 tools/make_awards.py [--today 2027-03-01] [--out oceneni.json] [--reminders reminders.txt]
"""
import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UA = "MKCinema/1.0 (https://github.com/radimvmihalik/mk-cinema)"
BEFORE, AFTER = 30, 7        # days shown before / after the awards
LOOKAHEAD = BEFORE + 14      # generate early enough; the picks' own dates decide when they show
GOLD = "FFFFD54F"

FESTIVALS = [  # Wikipedia page of a year's edition
    {"key": "berlinale", "name": "Berlinale", "color": "FF64B5F6",
     "page": lambda y: "%s Berlin International Film Festival" % ordinal(y - 1950)},
    {"key": "cannes", "name": "Cannes", "color": "FFFFB300",
     "page": lambda y: "%d Cannes Film Festival" % y},
    {"key": "kviff", "name": "Karlovy Vary", "color": "FF4DD0E1",
     "page": lambda y: "%s Karlovy Vary International Film Festival" % ordinal(y - 1966)},
]
MANUAL_FESTIVALS = {"jihlava": {"name": "Ji.hlava", "remind": ((9, 20), (11, 5))}}  # no machine-readable source

OSCAR_CATEGORIES = [  # English label of the Wikidata award item -> Czech name, in display order
    ("best picture", "Nejlepší film"), ("best director", "Režie"), ("best actor", "Herec v hlavní roli"),
    ("best actress", "Herečka v hlavní roli"), ("best supporting actor", "Herec ve vedlejší roli"),
    ("best supporting actress", "Herečka ve vedlejší roli"), ("best original screenplay", "Původní scénář"),
    ("best writing, original screenplay", "Původní scénář"), ("best adapted screenplay", "Adaptovaný scénář"),
    ("best writing, adapted screenplay", "Adaptovaný scénář"), ("best animated feature", "Animovaný film"),
    ("best international feature film", "Mezinárodní film"), ("best documentary feature film", "Dokumentární film"),
    ("best documentary feature", "Dokumentární film"), ("best cinematography", "Kamera"), ("best film editing", "Střih"),
    ("best original score", "Hudba"), ("best original song", "Píseň"), ("best sound", "Zvuk"),
    ("best production design", "Výprava"), ("best costume design", "Kostýmy"),
    ("best makeup and hairstyling", "Masky a účesy"), ("best visual effects", "Vizuální efekty"),
    ("best casting", "Casting"), ("achievement in casting", "Casting"), ("best documentary short film", "Krátký dokument"),
    ("best documentary (short subject)", "Krátký dokument"), ("best live action short film", "Krátký hraný film"),
    ("best animated short film", "Krátký animovaný film"),
]
FESTIVAL_AWARDS = {  # English award name on Wikipedia -> Czech
    "palme d'or": "Zlatá palma", "grand prix": "Velká cena", "jury prize": "Cena poroty", "prix du jury": "Cena poroty",
    "best director": "Režie", "best actor": "Herec", "best actress": "Herečka", "best screenplay": "Scénář",
    "special prize": "Zvláštní cena", "special award": "Zvláštní cena", "special jury prize": "Zvláštní cena poroty",
    "special mention": "Zvláštní uznání", "golden bear": "Zlatý medvěd",
    "silver bear grand jury prize": "Stříbrný medvěd – velká cena poroty", "silver bear jury prize": "Stříbrný medvěd – cena poroty",
    "silver bear for best director": "Stříbrný medvěd za režii",
    "silver bear for best leading performance": "Stříbrný medvěd za hlavní roli",
    "silver bear for best supporting performance": "Stříbrný medvěd za vedlejší roli",
    "silver bear for best screenplay": "Stříbrný medvěd za scénář",
    "silver bear for outstanding artistic contribution": "Stříbrný medvěd za umělecký přínos",
    "grand prix – crystal globe": "Křišťálový glóbus", "crystal globe": "Křišťálový glóbus",
    "best director award": "Cena za režii", "best actress award": "Cena za ženský herecký výkon",
    "best actor award": "Cena za mužský herecký výkon",
}
MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"), 1)}


def ordinal(n):
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def plural(n, one, few, many):
    return one if n == 1 else few if 2 <= n <= 4 else many


# ---------------------------------------------------------------- HTTP: Wikidata, Wikipedia
def fetch(url, data=None, accept="application/json"):
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, socket.timeout, TimeoutError):
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("request failed: " + url[:120])


def sparql(query):
    data = fetch("https://query.wikidata.org/sparql", urllib.parse.urlencode({"query": query}).encode(),
                 accept="application/sparql-results+json")
    return [{k: v["value"].rsplit("/", 1)[-1] if v["type"] == "uri" else v["value"] for k, v in row.items()}
            for row in data["results"]["bindings"]]


def entities(ids):
    """Wikidata items by id: labels (cs, en) and claims."""
    out, ids = {}, sorted(set(i for i in ids if i))
    for start in range(0, len(ids), 50):
        data = fetch("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(ids[start:start + 50]), "props": "labels|claims",
            "languages": "cs|en", "format": "json"}))
        out.update(data.get("entities", {}))
        time.sleep(1)
    return out


def wiki(**params):
    params.update(format="json", formatversion=2)
    time.sleep(2)  # Wikipedia answers 429 to bursts
    return fetch("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params))


def label(entity, langs=("cs", "en")):
    labels = (entity or {}).get("labels", {})
    values = [re.sub(r"^Dílo:\s*", "", labels[l]["value"]) for l in langs if l in labels]  # some Czech labels are "Dílo:Title"
    return next((v for v in values if v), "")


def claims(entity, prop):
    values = []
    for c in (entity or {}).get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        values.append(v["id"] if isinstance(v, dict) and "id" in v else v["time"] if isinstance(v, dict) and "time" in v else v)
    return values


def film_entry(entity, fallback_title="", year=None):
    """A titles entry for MK Cinema: TMDB id, else IMDb id, else a title to search for."""
    tmdb, imdb = claims(entity, "P4947"), [i for i in claims(entity, "P345") if str(i).startswith("tt")]
    title = label(entity) or fallback_title
    if tmdb and str(tmdb[0]).isdigit():
        entry = {"media": "movie", "id": int(tmdb[0])}
    elif imdb:
        entry = {"imdb": imdb[0]}
    else:
        published = [str(t)[1:5] for t in claims(entity, "P577") if t]
        entry = {"search": label(entity, ("en", "cs")) or fallback_title}
        if published or year:
            entry["year"] = int(min(published) if published else year)
    entry["title"] = title
    return entry


# ---------------------------------------------------------------- picks
def window_picks(key, title, color, day, nominations, winners, nominations_title, winners_title):
    """The month-before pick (nominations or competition) and the week-after pick (winners)."""
    out = []
    if nominations:
        pick = {"key": key + "-pred", "title": "%s – %s" % (title, nominations_title), "color": color, "home": True,
                "from": (day - timedelta(days=BEFORE)).isoformat(), "to": day.isoformat()}
        pick.update(nominations)
        out.append(pick)
    if winners:
        out.append({"key": key + "-po", "title": "%s – %s" % (title, winners_title), "color": color, "home": True,
                    "from": (day + timedelta(days=1)).isoformat(), "to": (day + timedelta(days=AFTER)).isoformat(),
                    "type": "titles", "titles": winners})
    return out


def in_window(day, today):
    return day - timedelta(days=LOOKAHEAD) <= today <= day + timedelta(days=AFTER)


# ---------------------------------------------------------------- Oscars (Wikidata)
def oscar_category(entity):
    name = label(entity, ("en",)).lower().replace("academy award for ", "")
    for key, czech in OSCAR_CATEGORIES:
        if name == key:
            return czech
    return label(entity, ("cs",)).replace("Oscar za ", "") or name


def oscars(today):
    ceremonies = sparql("""SELECT ?c ?when WHERE { ?c wdt:P31 wd:Q16913666 ; wdt:P585 ?when .
        FILTER(?when >= "%s"^^xsd:dateTime && ?when <= "%s"^^xsd:dateTime) }""" % (
        (today - timedelta(days=AFTER + 1)).isoformat(), (today + timedelta(days=LOOKAHEAD + 1)).isoformat()))
    picks = []
    for ceremony in ceremonies:
        day = date.fromisoformat(ceremony["when"][:10])
        if not in_window(day, today):
            continue
        rows = sparql("""SELECT ?s ?p ?award ?work WHERE {
            hint:Query hint:optimizer "None" .
            ?st pq:P805 wd:%s . ?s ?p ?st .
            ?st ?ps ?award . FILTER(?ps IN (ps:P1411, ps:P166))
            OPTIONAL { ?st pq:P1686 ?work } }""" % ceremony["c"])
        items = entities([r["s"] for r in rows] + [r.get("work") for r in rows] + [r["award"] for r in rows])
        found = {}  # (category, film) -> {"who": nominees, "winners": those who won, "won": bool}
        for r in rows:
            film = r.get("work") or r["s"]
            who = label(items.get(r["s"]), ("en", "cs")) if r.get("work") and r["s"] != r.get("work") else ""
            entry = found.setdefault((r["award"], film), {"who": [], "winners": [], "won": False, "subjects": []})
            won = r["p"] == "P166"
            for key in ("who", "winners") if won else ("who",):
                if who and who not in entry[key]:
                    entry[key].append(who)
            entry["won"] = entry["won"] or won
            if r["s"] != film:
                entry["subjects"].append(r["s"])
        for (award, work), entry in list(found.items()):  # a song: play the film it is from, name the song
            if "search" in film_entry(items.get(work)):
                movie = next((q for q in entry["subjects"] if "search" not in film_entry(items.get(q))), None)
                if movie:
                    song = label(items.get(work), ("en", "cs"))
                    del found[award, work]
                    merged = found.setdefault((award, movie), {"who": [], "winners": [], "won": False, "subjects": []})
                    merged["who"] = [song]
                    merged["winners"] = [song] if entry["won"] else merged["winners"]
                    merged["won"] = merged["won"] or entry["won"]
        year = day.year
        order = [czech for _, czech in OSCAR_CATEGORIES]
        categories = sorted({a for a, _ in found}, key=lambda a: (order.index(oscar_category(items.get(a))) if oscar_category(items.get(a)) in order else 99))

        def entry(award, film, with_who=True, **extra):
            e = film_entry(items.get(film), year=year - 1)
            who = found[award, film]["who"]
            if with_who and who and oscar_category(items.get(award)) not in ("Nejlepší film",):
                e["label"] = ", ".join(who[:2]) + (" a další" if len(who) > 2 else "")
            e.update(extra)
            return e

        by_category, counts = [], {}
        for award in categories:
            films = [f for a, f in found if a == award]
            by_category.append({"title": oscar_category(items.get(award)), "type": "titles", "titles": [entry(award, f) for f in films]})
            for f in films:
                counts[f] = counts.get(f, 0) + 1
        best = next((c["titles"] for c in by_category if c["title"] == "Nejlepší film"), [])
        everything = [dict(film_entry(items.get(f), year=year - 1), note="%d %s" % (n, plural(n, "nominace", "nominace", "nominací")))
                      for f, n in sorted(counts.items(), key=lambda fn: (-fn[1], label(items.get(fn[0]))))]
        nominations = {"items": ([{"title": "Nejlepší film", "type": "titles", "titles": best}] if best else []) + [
            {"title": "Všechny nominované filmy", "type": "titles", "titles": everything},
            {"title": "Podle kategorií", "items": by_category}]} if found else None
        winners = []
        for award in categories:
            for f in [f for a, f in found if a == award and found[a, f]["won"]]:
                e = entry(award, f, with_who=False)
                who = found[award, f]["winners"]
                category = oscar_category(items.get(award))
                e["label"] = category + (" – " + ", ".join(who[:2]) if who and category != "Nejlepší film" else "")
                winners.append(e)
        picks += window_picks("oscary-%d" % year, "Oscary %d" % year, GOLD, day, nominations, winners, "nominace", "vítězové")
    return picks


# ---------------------------------------------------------------- festivals (Wikipedia)
def strip_markup(text):
    text = re.sub(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>|<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<small>.*?</small>|\{\{(?:efn|refn|sfn|citation needed)[^{}]*\}\}", "", text, flags=re.S | re.I)
    text = re.sub(r"\{\{(?:lang|nowrap|sort)\|(?:[^|{}]*\|)?([^|{}]*)\}\}", r"\1", text, flags=re.I)
    return text


def plain(text):
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", strip_markup(text))
    text = re.sub(r"\{\{[^{}]*\}\}|'''?|<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip(" *:,;")


ITALIC = re.compile(r"(?<!')''(?!')(.+?)(?<!')''(?!')")
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
BOLD_END = re.compile(r"^\s*'''(?!')")  # "'''[[Award]]:''' ''Film''": the bold that closes the award's name


def italic_films(text):
    """[(title, link target or None)] of the italic titles in a piece of wikitext."""
    films = []
    for m in ITALIC.finditer(strip_markup(text)):
        link = LINK.search(m.group(1))
        title = plain(link.group(2) or link.group(1)) if link else plain(m.group(1))
        if title:
            films.append((title, link.group(1).strip() if link else None))
    return films


def sections(wikitext):
    """[(level, title, text)] of a page; the lead is level 1."""
    parts, level, title, start = [], 1, "", 0
    for m in re.finditer(r"^(={2,6})\s*(.*?)\s*\1\s*$", wikitext, flags=re.M):
        parts.append((level, title, wikitext[start:m.start()]))
        level, title, start = len(m.group(1)), plain(m.group(2)), m.end()
    parts.append((level, title, wikitext[start:]))
    return parts


def subsection(parts, parent, child):
    """Text of the first subsection whose title matches child under a level-2 section matching parent."""
    inside = False
    for level, title, text in parts:
        if level == 2:
            inside = bool(re.search(parent, title, re.I))
        elif inside and re.search(child, title, re.I) and not re.search(r"short|out of|jury|special", title, re.I):
            return text
    return ""


def festival_end(lead):
    m = re.search(r"\{\{\s*date range\s*\|([^{}]*)\}\}", lead, re.I)
    if m:
        numbers = [int(n) for n in re.findall(r"\b\d+\b", m.group(1))]
        if len(numbers) >= 6:
            return date(*numbers[3:6])
        if len(numbers) >= 3:
            return date(*numbers[:3])
    m = re.search(r"\{\{\s*end date\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", lead, re.I)
    if m:
        return date(*map(int, m.groups()))
    m = re.search(r"\b(\d{1,2})\s*(?:to|–|-|and)\s*(\d{1,2})\s+(%s)\s+(\d{4})" % "|".join(MONTHS), plain(lead), re.I)
    if m:
        return date(int(m.group(4)), MONTHS[m.group(3).lower()], int(m.group(2)))
    return None


def competition_films(parts):
    text = subsection(parts, r"official (selection|sections?)|line-?up", r"competition|crystal globe")
    table = text[text.find("{|"):] if "{|" in text else ""
    films = []
    for row in re.split(r"\n\|-", table)[1:]:
        found = italic_films(row)
        if found:
            films.append(found[0])
    return films


def award_winners(parts):
    """[(award, who, title, link)] from the bulleted awards of the main competition."""
    text = subsection(parts, r"award", r"in competition|main competition|crystal globe|official competition")
    blocks = []
    for line in strip_markup(text).splitlines():
        if re.match(r"^\*[^*]", line):
            blocks.append([line[1:], []])
        elif line.startswith("**") and blocks:
            blocks[-1][1].append(line.lstrip("*"))
    winners = []
    for line, subs in blocks:
        depth, cut = 0, None
        for i, ch in enumerate(line):  # the first colon outside a [[link]] ends the award's name
            depth += {"[": 1, "]": -1}.get(ch, 0)
            if ch == ":" and depth == 0:
                cut = i
                break
        if cut is None:
            continue
        award = plain(line[:cut])
        czech = FESTIVAL_AWARDS.get(award.lower(), award)
        for segment in [BOLD_END.sub("", line[cut + 1:])] + subs:
            films = italic_films(segment)
            if not films:
                continue
            who = "" if segment.strip().startswith("''") else re.split(r"\s+(?:for|–|-)\s+|\(", plain(segment))[0].strip()
            who = re.sub(r"\s+and\s+", " a ", who)
            for title, link in films:
                winners.append((czech, who, title, link))
    return winners


def wikipedia_entries(films, year):
    """titles entries for (title, link) pairs, using the linked articles' Wikidata items."""
    links = sorted({link for _, link in films if link})
    qid = {}
    for start in range(0, len(links), 50):
        data = wiki(action="query", titles="|".join(links[start:start + 50]), prop="pageprops", ppprop="wikibase_item", redirects=1)
        query = data.get("query", {})
        rename = {n["from"]: n["to"] for n in query.get("normalized", []) + query.get("redirects", [])}
        pages = {p["title"]: p.get("pageprops", {}).get("wikibase_item") for p in query.get("pages", [])}
        for link in links[start:start + 50]:
            name = link
            for _ in range(3):
                name = rename.get(name, name)
            qid[link] = pages.get(name)
    items = entities(qid.values())
    out = []
    for title, link in films:
        entity = items.get(qid.get(link)) if link else None
        out.append(film_entry(entity, title, year) if entity else {"search": title, "year": year, "title": title})
    return out


def festivals(today):
    picks = []
    for fest in FESTIVALS:
        year = today.year
        try:
            page = wiki(action="parse", page=fest["page"](year), prop="wikitext")
        except urllib.error.HTTPError:
            continue
        if "parse" not in page:  # no page for this edition yet
            continue
        parts = sections(page["parse"]["wikitext"])
        day = festival_end(parts[0][2])
        if not day or not in_window(day, today):
            continue
        lineup = competition_films(parts)
        nominations = {"type": "titles", "titles": wikipedia_entries(lineup, year)} if lineup else None
        winners = []
        if today > day:
            found = award_winners(parts)
            entries = wikipedia_entries([(t, link) for _, _, t, link in found], year)
            for (award, who, _, _), entry in zip(found, entries):
                winners.append(dict(entry, label=award + (" – " + who if who else "")))
        picks += window_picks("%s-%d" % (fest["key"], year), "%s %d" % (fest["name"], year), fest["color"], day,
                              nominations, winners, "hlavní soutěž", "vítězové")
    return picks


def manual(today, data, reminders):
    """Editions filled by hand in oceneni-rucne.json; asks for them when one is due."""
    picks = []
    for e in data.get("editions", []):
        day = date.fromisoformat(e["date"])
        if in_window(day, today):
            nominations = {"type": "titles", "titles": e["competition"]} if e.get("competition") else None
            picks += window_picks("%s-%d" % (e["festival"], day.year), e["title"], e.get("color", "FFBA68C8"), day,
                                  nominations, e.get("winners", []), e.get("competition_title", "soutěž"), "vítězové")
    for key, fest in MANUAL_FESTIVALS.items():
        start, end = (date(today.year, *md) for md in fest["remind"])
        done = any(e["festival"] == key and e["date"][:4] == str(today.year) for e in data.get("editions", []))
        if start <= today <= end and not done:
            reminders.append("%s %d: doplnit soutěž a vítěze do oceneni-rucne.json" % (fest["name"], today.year))
    return picks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", default=date.today().isoformat())
    parser.add_argument("--out", default=os.path.join(ROOT, "oceneni.json"))
    parser.add_argument("--reminders")
    args = parser.parse_args()
    today = date.fromisoformat(args.today)
    old = {}
    if os.path.isfile(args.out):
        with open(args.out, encoding="utf-8") as fh:
            old = json.load(fh)
    with open(os.path.join(ROOT, "oceneni-rucne.json"), encoding="utf-8") as fh:
        hand = json.load(fh)
    reminders, picks = [], []
    for name, build in (("oscary", oscars), ("festivaly", festivals)):
        try:
            picks += build(today)
        except Exception as exc:  # a source is down: keep what we had, so a pick doesn't vanish for a day
            print("%s failed (%s), keeping the previous picks" % (name, exc), file=sys.stderr)
            keys = ("oscary",) if name == "oscary" else tuple(f["key"] for f in FESTIVALS)
            picks += [p for p in old.get("picks", []) if p.get("key", "").startswith(keys)
                      and p.get("to", "") >= today.isoformat()]
    picks += manual(today, hand, reminders)
    picks.sort(key=lambda p: p["from"])
    data = {"_napoveda": "Generuje tools/make_awards.py (GitHub Actions každý den), ručně neupravovat. "
                         "Ji.hlava a jiné festivaly bez strojově čitelného zdroje se doplňují do oceneni-rucne.json.",
            "picks": picks}
    if data != old:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    for p in picks:
        print("%s .. %s  %s" % (p["from"], p["to"], p["title"]))
    if args.reminders:
        with open(args.reminders, "w", encoding="utf-8") as fh:
            fh.write("".join(r + "\n" for r in reminders))
    for r in reminders:
        print("REMINDER:", r)


if __name__ == "__main__":
    main()
