"""IMDb charts for MK Cinema: the best and worst titles per category, and actors/actresses.

Run monthly by GitHub Actions (.github/workflows/zebricky.yml), or by hand:
    python3 tools/make_charts.py zebricky.json [data-folder]

Uses IMDb's official datasets (https://datasets.imdbws.com/, personal and non-commercial use).
Titles are ranked by a weighted rating like IMDb's Top 250, so a film with a handful of votes
can't top a chart. Each list keeps a few spare candidates: the add-on drops titles whose IMDb
rating is far from TMDB's (vote campaigns) and shows the first 100.
Only the standard library is used, so the workflow needs no packages.
"""
import datetime
import gzip
import json
import os
import sys
import urllib.request

DATASETS = "https://datasets.imdbws.com/"
FILES = ("title.ratings.tsv.gz", "title.basics.tsv.gz", "title.principals.tsv.gz", "name.basics.tsv.gz")
MIN_VOTES = {"movie": 25000, "tv": 10000}  # also the weight m in the weighted rating
KEEP = 150  # candidates per list; the add-on shows 100
ACTOR_MIN_FILMS = 10
ACTOR_TOP_BILLING = 4  # only leading roles count

# (chart id, Czech title, IMDb genre or None, media)
CHARTS = [
    ("movies", "Filmy", None, "movie"),
    ("series", "Seriály", None, "tv"),
    ("documentaries", "Dokumenty", "Documentary", "any"),
    ("action", "Akční", "Action", "movie"),
    ("animation", "Animované", "Animation", "movie"),
    ("adventure", "Dobrodružné", "Adventure", "movie"),
    ("drama", "Drama", "Drama", "movie"),
    ("fantasy", "Fantasy", "Fantasy", "movie"),
    ("horror", "Horory", "Horror", "movie"),
    ("comedy", "Komedie", "Comedy", "movie"),
    ("crime", "Krimi", "Crime", "movie"),
    ("romance", "Romantické", "Romance", "movie"),
    ("family", "Rodinné", "Family", "movie"),
    ("scifi", "Sci-fi", "Sci-Fi", "movie"),
    ("thriller", "Thrillery", "Thriller", "movie"),
    ("war", "Válečné", "War", "movie"),
    ("western", "Westerny", "Western", "movie"),
]
MEDIA = {"movie": "movie", "tvSeries": "tv", "tvMiniSeries": "tv"}


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            yield line.rstrip("\n").split("\t")


def download(folder):
    os.makedirs(folder, exist_ok=True)
    for name in FILES:
        target = os.path.join(folder, name)
        if not os.path.isfile(target):
            print("downloading", name, flush=True)
            urllib.request.urlretrieve(DATASETS + name, target)


def main(out, folder):
    download(folder)
    ratings = {t: (float(r), int(v)) for t, r, v in rows(os.path.join(folder, "title.ratings.tsv.gz"))
               if int(v) >= min(MIN_VOTES.values())}
    titles = {}
    for t, kind, title, _, _, year, _, _, genres in rows(os.path.join(folder, "title.basics.tsv.gz")):
        media = MEDIA.get(kind)
        if media and t in ratings and ratings[t][1] >= MIN_VOTES[media]:
            titles[t] = {"media": media, "title": title, "year": year if year != "\\N" else "",
                         "genres": set(genres.split(","))}
    mean = {m: sum(ratings[t][0] for t, x in titles.items() if x["media"] == m) /
            max(1, sum(1 for x in titles.values() if x["media"] == m)) for m in MIN_VOTES}

    def weighted(t):
        r, v = ratings[t]
        m = MIN_VOTES[titles[t]["media"]]
        return (v * r + m * mean[titles[t]["media"]]) / (v + m)

    def entry(t):
        r, v = ratings[t]
        return [t, r, v, titles[t]["media"], titles[t]["title"], titles[t]["year"]]

    charts = []
    for chart_id, name, genre, media in CHARTS:
        pool = [t for t, x in titles.items()
                if (media == "any" or x["media"] == media)
                and (genre in x["genres"] if genre else "Documentary" not in x["genres"])]
        ranked = sorted(pool, key=weighted)
        charts.append({"id": chart_id, "title": name, "best": [entry(t) for t in ranked[::-1][:KEEP]],
                       "worst": [entry(t) for t in ranked[:KEEP]]})
        print("%-14s %5d titles, best %s, worst %s" % (chart_id, len(pool), ranked[-1:] and titles[ranked[-1]]["title"],
                                                       ranked[:1] and titles[ranked[0]]["title"]), flush=True)

    # Actors and actresses: average IMDb rating of the films where they had a leading role
    # voice roles in animated films and appearances in documentaries aren't acting in the usual sense
    films = {t for t, x in titles.items() if x["media"] == "movie" and not x["genres"] & {"Documentary", "Animation"}}
    roles = {"actor": {}, "actress": {}}
    for t, ordering, person, category, _, _ in rows(os.path.join(folder, "title.principals.tsv.gz")):
        if t in films and category in roles and int(ordering) <= ACTOR_TOP_BILLING:
            roles[category].setdefault(person, []).append(ratings[t][0])
    wanted = {p for people in roles.values() for p, rs in people.items() if len(rs) >= ACTOR_MIN_FILMS}
    names = {p: n for p, n, *_ in rows(os.path.join(folder, "name.basics.tsv.gz")) if p in wanted}
    for chart_id, name, category in (("actors", "Herci", "actor"), ("actresses", "Herečky", "actress")):
        people = [(p, round(sum(rs) / len(rs), 2), len(rs)) for p, rs in roles[category].items()
                  if len(rs) >= ACTOR_MIN_FILMS and p in names]
        people.sort(key=lambda x: (x[1], x[2]))
        charts.append({"id": chart_id, "title": name, "person": True,
                       "best": [[p, avg, n, names[p]] for p, avg, n in people[::-1][:KEEP]],
                       "worst": [[p, avg, n, names[p]] for p, avg, n in people[:KEEP]]})
        print("%-14s %5d people, best %s" % (chart_id, len(people), people and names[people[-1][0]]), flush=True)

    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"updated": datetime.date.today().isoformat(), "charts": charts}, fh, ensure_ascii=False, separators=(",", ":"))
    print("written", out, os.path.getsize(out) // 1024, "kB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "zebricky.json", sys.argv[2] if len(sys.argv) > 2 else "imdb-data")
