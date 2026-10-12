"""Ubicación con OpenStreetMap: Nominatim (lugares) y Overpass (cruces de calles)."""
import os
import re
import time

import requests

from . import config

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]


def _ua():
    contacto = os.environ.get("CONTACTO_EMAIL", "sin-correo")
    return {"User-Agent": f"mapa-accidentes-peninsula/1.0 ({contacto})"}


def dentro(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return config.LAT_MIN <= lat <= config.LAT_MAX and config.LON_MIN <= lon <= config.LON_MAX


class Geo:
    def __init__(self, cache):
        self.cache = cache          # dict persistente: consulta -> [lat, lon] o None
        self._ultimo = 0.0

    def _espera(self, seg):
        falta = self._ultimo + seg - time.time()
        if falta > 0:
            time.sleep(falta)
        self._ultimo = time.time()

    def buscar(self, texto, estado):
        clave = f"N|{texto}|{estado}".lower()
        if clave in self.cache:
            return self.cache[clave]
        self._espera(1.1)   # política de Nominatim: máx. 1 consulta por segundo
        res = None
        try:
            r = requests.get(NOMINATIM, params={"format": "json", "limit": 1, "countrycodes": "mx",
                                                "q": f"{texto}, {estado}, México"},
                             headers=_ua(), timeout=25)
            r.raise_for_status()
            j = r.json()
            if j and dentro(j[0]["lat"], j[0]["lon"]):
                res = [round(float(j[0]["lat"]), 6), round(float(j[0]["lon"]), 6)]
        except Exception:
            return None   # no se guarda en caché para reintentar después
        self.cache[clave] = res
        return res

    def cruce(self, calle_a, calle_b, centro, radio=2500):
        clave = f"O|{calle_a}|{calle_b}|{centro[0]:.3f},{centro[1]:.3f}".lower()
        if clave in self.cache:
            return self.cache[clave]

        def rx(nombre):
            # "Av. Tulum" -> "Tulum"; luego acepta "Calle", "Avenida", etc. delante
            n = re.sub(r"^(calle|avenida|av\.?|circuito|boulevard|blvd\.?|bulevar)\s+", "", nombre.strip(), flags=re.I)
            n = re.sub(r'[\\^$.|?*+()\[\]{}"]', ".", n)   # sin caracteres especiales de regex
            return f"^((Calle|Avenida|Av.?|Circuito|Boulevard|Blvd.?|Bulevar) )?{n}$"

        lat, lon = centro
        q = (f'[out:json][timeout:25];'
             f'way(around:{radio},{lat},{lon})[highway][name~"{rx(calle_a)}",i]->.a;'
             f'way(around:{radio},{lat},{lon})[highway][name~"{rx(calle_b)}",i]->.b;'
             f'node(w.a)->.na;node(w.b)->.nb;node.na.nb;out;')
        for url in OVERPASS:
            self._espera(3)
            try:
                r = requests.post(url, data={"data": q}, headers=_ua(), timeout=40)
                if r.status_code != 200:
                    continue
                nodos = r.json().get("elements", [])
                res = None
                if nodos:
                    la = sum(n["lat"] for n in nodos) / len(nodos)
                    lo = sum(n["lon"] for n in nodos) / len(nodos)
                    if dentro(la, lo):
                        res = [round(la, 6), round(lo, 6)]
                self.cache[clave] = res
                return res
            except Exception:
                continue
        return None

    def ubicar(self, info, estado):
        """Devuelve (lat, lon, pr) o None."""
        g = info.get("geo") or {}
        modo = g.get("modo", "ninguno")
        muni = g.get("municipio") or ""
        centro_muni = config.CIUDADES.get(muni)
        if modo == "cruce" and g.get("calle_a") and g.get("calle_b"):
            centro = None
            if g.get("colonia"):
                centro = self.buscar(f"{g['colonia']}, {muni}", estado)
            if not centro and centro_muni:
                centro = centro_muni[1:]
            if not centro and muni:
                centro = self.buscar(muni, estado)
            if centro:
                p = self.cruce(g["calle_a"], g["calle_b"], centro)
                if p:
                    return p[0], p[1], "cruce"
            if g.get("colonia"):
                p = self.buscar(f"{g['colonia']}, {muni}", estado)
                if p:
                    return p[0], p[1], "colonia"
            return None
        if modo == "lugar" and (g.get("lugar") or g.get("colonia")):
            nombre = g.get("lugar") or g.get("colonia")
            p = self.buscar(f"{nombre}, {muni}" if muni else nombre, estado)
            if p:
                es_colonia = bool(re.match(r"(col(onia)?\.?|fracc(ionamiento)?\.?|barrio|sm|supermanzana|región)\b",
                                           nombre, re.I))
                return p[0], p[1], "colonia" if es_colonia else "lugar"
            return None
        if modo == "tramo":
            if dentro(g.get("lat"), g.get("lon")):
                return round(float(g["lat"]), 5), round(float(g["lon"]), 5), "tramo"
            if g.get("lugar"):
                p = self.buscar(f"{g['lugar']}, {muni}" if muni else g["lugar"], estado)
                if p:
                    return p[0], p[1], "tramo"
        return None
