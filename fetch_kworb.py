#!/usr/bin/env python3
"""Descarga el chart diario de Spotify desde kworb.net y lo añade a history.csv.
Formato de salida (lo lee directamente la app Pulso de charts):
date,region,rank,artist_names,track_name,streams
Uso: python fetch_kworb.py   (requiere: pip install requests beautifulsoup4)"""
import csv, re, pathlib, requests
from bs4 import BeautifulSoup

# Añade mercados: etiqueta -> código de kworb (p. ej. "MX": "mx", "Global": "global")
COUNTRIES = {"ES": "es", "Global": "global"}
OUT = pathlib.Path("history.csv")
HDR = ["date", "region", "rank", "artist_names", "track_name", "streams"]

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
        streams = re.sub(r"\D", "", td[6].get_text())
        if artists and track and streams:
            rows.append((date, int(td[0].get_text(strip=True)), ", ".join(artists), track, int(streams)))
    return rows

def main():
    seen = set()
    if OUT.exists():
        with OUT.open(newline="", encoding="utf-8") as f:
            seen = {(r["date"], r["region"]) for r in csv.DictReader(f)}
    new = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(HDR)
        for region, code in COUNTRIES.items():
            r = requests.get(f"https://kworb.net/spotify/country/{code}_daily.html",
                             headers={"User-Agent": "chart-pulse/1.0 (uso interno)"}, timeout=30)
            r.raise_for_status()
            rows = parse(r.text)
            if not rows or (rows[0][0], region) in seen:
                print(f"{region}: sin novedades"); continue
            for d, rk, a, t, s in rows:
                w.writerow([d, region, rk, a, t, s])
            print(f"{region}: {len(rows)} filas del {rows[0][0]}")

if __name__ == "__main__":
    main()
