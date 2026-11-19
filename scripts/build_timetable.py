"""Construit data/horaires-<ligne>.json : horaires théoriques (GTFS IDFM) des lignes 52 et 22
aux arrêts utiles (maison, bureaux, arrêts proches de la maison), pour les 8 prochains jours.
Lancé chaque nuit par .github/workflows/horaires.yml."""
import csv, io, json, math, os, sys, unicodedata, urllib.request, zipfile, datetime as dt
from zoneinfo import ZoneInfo

GTFS_URLS = [
    "https://eu.ftp.opendatasoft.com/stif/GTFS/IDFM-gtfs.zip",
    "https://data.iledefrance-mobilites.fr/explore/dataset/offre-horaires-tc-gtfs-idfm/files/a925e164271e4bca93433756d6a340d1/download/",
]
LINES = {
    "52": {"home": ["fontaine", "radio"], "offices": {"vhpv": ["victor", "hugo", "valery"], "cdg": ["gaulle", "etoile", "victor"]}},
    "22": {"home": ["george", "sand", "fontaine"], "offices": {"kleber": ["kleber", "etoile", "gaulle"]}},
}
NEAR_HOME_M = 650
DAYS = 8
TZ = ZoneInfo("Europe/Paris")

def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return " " + "".join(c if c.isalnum() else " " for c in s) + " "

def score(name, toks):
    n = norm(name)
    return sum(1 for t in toks if " " + t in n) / len(toks)

def dist(a, b):
    r = math.pi / 180
    x = (b[1] - a[1]) * r * math.cos((a[0] + b[0]) / 2 * r); y = (b[0] - a[0]) * r
    return 6371000 * math.hypot(x, y)

def download():
    for u in GTFS_URLS:
        try:
            print("Téléchargement", u, flush=True)
            req = urllib.request.Request(u, headers={"User-Agent": "bus52-timetable"})
            with urllib.request.urlopen(req, timeout=600) as r:
                data = r.read()
            zipfile.ZipFile(io.BytesIO(data))  # vérifie que c'est un zip
            print(f"OK {len(data)/1e6:.0f} Mo", flush=True)
            return data
        except Exception as e:
            print("échec :", e, flush=True)
    sys.exit("GTFS introuvable")

def rows(z, name):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))

def main():
    z = zipfile.ZipFile(io.BytesIO(download()))
    agencies = {a["agency_id"]: a.get("agency_name", "") for a in rows(z, "agency.txt")}
    all_routes = list(rows(z, "routes.txt"))
    route_of = {}
    for line in LINES:
        rs = [r for r in all_routes if r["route_short_name"] == line and r.get("route_type") in ("3", "700", "702", "704")]
        rs.sort(key=lambda r: 0 if "RATP" in agencies.get(r.get("agency_id"), "").upper() else 1)
        if rs: route_of[line] = rs[0]["route_id"]
        print("ligne", line, "->", route_of.get(line), flush=True)
    rid_line = {v: k for k, v in route_of.items()}
    trips = {t["trip_id"]: t for t in rows(z, "trips.txt") if t["route_id"] in rid_line}
    print(len(trips), "courses", flush=True)
    times, route_stops = {}, {l: set() for l in route_of}
    for st in rows(z, "stop_times.txt"):
        t = trips.get(st["trip_id"])
        if t:
            times.setdefault(st["trip_id"], []).append((int(st["stop_sequence"]), st["stop_id"], st["departure_time"] or st["arrival_time"]))
            route_stops[rid_line[t["route_id"]]].add(st["stop_id"])
    all_ids = set().union(*route_stops.values()) if route_stops else set()
    stops_all = {s["stop_id"]: s for s in rows(z, "stops.txt") if s["stop_id"] in all_ids}

    cal = {c["service_id"]: c for c in rows(z, "calendar.txt")} if "calendar.txt" in z.namelist() else {}
    exc = {}
    if "calendar_dates.txt" in z.namelist():
        for c in rows(z, "calendar_dates.txt"):
            exc.setdefault(c["date"], {})[c["service_id"]] = c["exception_type"]
    wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    today = dt.datetime.now(TZ).date()
    active_of = {}
    for i in range(-1, DAYS):
        d = today + dt.timedelta(days=i); ds = d.strftime("%Y%m%d")
        active = {sid for sid, c in cal.items() if c["start_date"] <= ds <= c["end_date"] and c[wd[d.weekday()]] == "1"}
        for sid, e in exc.get(ds, {}).items():
            (active.add if e == "1" else active.discard)(sid)
        active_of[d.isoformat()] = active
    num = lambda sid: sid.split(":")[-1]
    os.makedirs("data", exist_ok=True)

    for line, cfg in LINES.items():
        if line not in route_of: print("ligne absente", line); continue
        stops = {k: stops_all[k] for k in route_stops[line] if k in stops_all}
        def pick(toks):
            best = max((score(s["stop_name"], toks) for s in stops.values()), default=0)
            return [sid for sid, s in stops.items() if best >= .6 and score(s["stop_name"], toks) == best]
        home = pick(cfg["home"])
        if not home: print("arrêt maison introuvable pour", line); continue
        hpos = (sum(float(stops[s]["stop_lat"]) for s in home) / len(home), sum(float(stops[s]["stop_lon"]) for s in home) / len(home))
        offices = {k: pick(v) for k, v in cfg["offices"].items()}
        near = [sid for sid, s in stops.items() if sid not in home and dist(hpos, (float(s["stop_lat"]), float(s["stop_lon"]))) < NEAR_HOME_M]
        keep = set(home) | set(near) | {q for v in offices.values() for q in v}
        days = {}
        for day, active in active_of.items():
            out = []
            for tid, t in trips.items():
                if t["route_id"] != route_of[line] or t["service_id"] not in active: continue
                seq = [(num(s), tm[:5]) for _, s, tm in sorted(times.get(tid, [])) if s in keep]
                if seq: out.append({"d": t.get("direction_id", ""), "h": t.get("trip_headsign", ""), "c": seq})
            out.sort(key=lambda x: x["c"][0][1])
            days[day] = out
        res = {"generated": dt.datetime.now(TZ).isoformat(timespec="minutes"), "line": line, "route": route_of[line],
               "home": [num(s) for s in home], "near": [num(s) for s in near],
               "offices": {k: [num(s) for s in v] for k, v in offices.items()},
               "stops": {num(s): stops[s]["stop_name"] for s in keep}, "days": days}
        path = f"data/horaires-{line}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, separators=(",", ":"))
        print("écrit", path, os.path.getsize(path), "octets; maison", [stops[s]["stop_name"] for s in home],
              "bureaux", {k: [stops[s]["stop_name"] for s in v] for k, v in offices.items()},
              "courses/jour", {k: len(v) for k, v in days.items()}, flush=True)

if __name__ == "__main__":
    main()
