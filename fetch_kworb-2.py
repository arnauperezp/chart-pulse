#!/usr/bin/env python3
"""Descarga el chart diario de Spotify desde kworb.net y lo añade a history.csv.

Columnas de salida (las lee directamente el panel Pulso de charts):
date,region,rank,artist_names,track_name,streams,days_on_chart,peak_rank,total_streams

- Fuerza UTF-8 al leer la web (así Ñ, á, é, ó... salen bien).
- Si history.csv ya existe con el formato antiguo, lo migra y repara los
  acentos rotos de las ejecuciones anteriores.

Uso: python fetch_kworb.py   (requiere: pip install requests beautifulsoup4)
"""
import csv
import pathlib
import re

import requests
from bs4 import BeautifulSoup

# Mercados: etiqueta que verás en el panel -> código de kworb ("mx", "ar", "co", "global"...)
COUNTRIES = {"ES": "es", "Global": "global"}
OUT = pathlib.Path("history.csv")
HDR = ["date", "region", "rank", "artist_names", "track_name",
       "streams", "days_on_chart", "peak_rank", "total_streams"]


def fix_text(s):
    """Repara texto UTF-8 que se leyó como latin-1/cp1252 (Ã‘engo -> Ñengo)."""
    if not s or not re.search(r"[ÃÂ]", s):
        return s
    for enc in ("latin-1", "cp1252"):
        try:
            fixed = s.encode(enc).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if fixed != s:
            return fixed
    return s


def num(cell):
    d = re.sub(r"\D", "", cell.get_text())
    return int(d) if d else ""


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    m = re.search(r"(\d{4})/(\d{2})/(\d{2})", soup.get_text(" "))
    if not m:
        raise ValueError("No se encontró la fecha del chart")
    date = "-".join(m.groups())
    rows = []
    for tr in soup.find("table").find_all("tr"):
        td = tr.find_all("td")
        if len(td) < 7 or not td[0].get_text(strip=True).isdigit():
            continue
        links = td[2].find_all("a")
        artists = [a.get_text(strip=True) for a in links if "/artist/" in a.get("href", "")]
        track = next((a.get_text(strip=True) for a in links if "/track/" in a.get("href", "")), None)
        streams = num(td[6])
        if not (artists and track and streams != ""):
            continue
        rows.append({
            "date": date,
            "rank": int(td[0].get_text(strip=True)),
            "artist_names": ", ".join(artists),
            "track_name": track,
            "streams": streams,
            "days_on_chart": num(td[3]),
            "peak_rank": num(td[4]),
            "total_streams": num(td[10]) if len(td) > 10 else "",
        })
    return rows


def load_existing():
    """Lee history.csv (formato antiguo o nuevo) y devuelve filas normalizadas."""
    if not OUT.exists():
        return []
    with OUT.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["artist_names"] = fix_text(r.get("artist_names", ""))
        r["track_name"] = fix_text(r.get("track_name", ""))
        for k in HDR:
            r.setdefault(k, "")
    return rows


def save(rows):
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HDR, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    rows = load_existing()
    seen = {(r["date"], r["region"]) for r in rows}
    added = 0
    for region, code in COUNTRIES.items():
        r = requests.get(
            f"https://kworb.net/spotify/country/{code}_daily.html",
            headers={"User-Agent": "chart-pulse/1.0 (uso interno)"},
            timeout=30,
        )
        r.raise_for_status()
        html = r.content.decode("utf-8", errors="replace")  # UTF-8 forzado
        new = parse(html)
        if not new or (new[0]["date"], region) in seen:
            print(f"{region}: sin novedades")
            continue
        for n in new:
            n["region"] = region
            rows.append(n)
        added += len(new)
        print(f"{region}: {len(new)} filas del {new[0]['date']}")
    rows.sort(key=lambda r: (r["date"], r["region"], int(r["rank"])))
    save(rows)  # siempre reescribe: migra el formato y repara acentos antiguos
    print(f"history.csv: {len(rows)} filas ({added} nuevas)")


if __name__ == "__main__":
    main()
