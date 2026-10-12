"""Corrida completa: recolecta, clasifica, ubica y guarda.

Uso:  python -m scraper.run            (normal)
      python -m scraper.run --prueba   (no guarda nada, solo muestra lo que haría)
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from . import clasificar, config, fuentes
from .geocodificar import Geo, dentro

AHORA = datetime.now(timezone.utc)
PRUEBA = "--prueba" in sys.argv


def log(*a):
    print(*a, flush=True)


def cargar(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return defecto


def guardar(ruta, datos):
    if PRUEBA:
        return
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
        f.write("\n")


def slug(s, maximo=48):
    s = clasificar.sin_acentos(s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maximo].strip("-") or "sin-lugar"


def ts_de(a):
    try:
        return datetime.fromisoformat(a.get("ts") or f"{a['d']}T12:00:00-06:00")
    except Exception:
        return AHORA


def es_excluida(nota):
    t = clasificar.sin_acentos(nota.get("fuente", "") + " " + nota.get("url", ""))
    return any(x in t for x in config.FUENTES_EXCLUIDAS)


def main():
    pub, priv = config.DATA_PUBLICA, config.DATA_PRIVADA
    acc = cargar(f"{pub}/accidentes.json", [])
    sin = cargar(f"{pub}/sinubicacion.json", [])
    vistos = cargar(f"{priv}/vistos.json", {})          # url -> fecha ISO en que se revisó
    geocache = cargar(f"{priv}/geocache.json", {})
    geo = Geo(geocache)
    modo_ia = bool(os.environ.get("ANTHROPIC_API_KEY"))
    log(f"Inicio {AHORA.isoformat()} · clasificación con {'Claude' if modo_ia else 'reglas de palabras clave'}")

    # 1. Recolectar ------------------------------------------------------------
    notas = fuentes.recolectar(log)
    limite = AHORA - timedelta(hours=config.VENTANA_HORAS)
    candidatas = []
    for n in notas:
        if n["url"] in vistos or es_excluida(n):
            continue
        if n.get("pendiente"):
            # antes de descargar el artículo, revisar si el enlace (slug) suena a accidente
            del_enlace = n["url"].rstrip("/").split("/")[-1].replace(".html", "").replace("-", " ")
            n["titulo"] = del_enlace
            if not clasificarlas_parece(n):
                vistos[n["url"]] = AHORA.isoformat()
                continue
            n["titulo"] = ""
            fuentes.completar_articulo(n)
            n["titulo"] = n.get("titulo") or del_enlace
        if n.get("fecha") and n["fecha"] < limite:
            vistos[n["url"]] = AHORA.isoformat()
            continue
        if not clasificarlas_parece(n):
            vistos[n["url"]] = AHORA.isoformat()
            continue
        candidatas.append(n)
    # primero las que vienen directo de medios (tienen mejor texto) y las más recientes
    candidatas.sort(key=lambda n: (bool(n.get("google")), -(n["fecha"].timestamp() if n.get("fecha") else 0)))
    log(f"Notas: {len(notas)} · candidatas a revisar: {len(candidatas)}")

    # 2. Clasificar y ubicar ---------------------------------------------------
    nuevos, confirmados, errores = [], 0, 0
    por_id = {a["id"]: a for a in acc + sin}
    for n in candidatas[:config.MAX_CLASIFICAR]:
        recientes = [a for a in acc + sin if ts_de(a) >= AHORA - timedelta(hours=72)]
        try:
            info, metodo = clasificar.clasificar(n, recientes)
        except Exception as e:
            errores += 1
            log(f"  ! error al clasificar {n['url']}: {e}")
            continue          # no se marca como vista: se reintenta en la próxima corrida
        vistos[n["url"]] = AHORA.isoformat()
        if not info.get("es_accidente") or info.get("estado") not in config.ESTADOS:
            continue
        fuente = {"n": n.get("fuente") or fuentes.nombre_por_dominio(n["url"], "Medio local"), "u": n["url"]}

        # ¿ya existe? (lo dice Claude, o mismo día + mismo lugar)
        dup = info.get("duplicado_de")
        existente = por_id.get(dup) if dup else None
        f_pub = n.get("fecha") or AHORA
        desfase = config.DESFASE[info["estado"]]
        local = f_pub.astimezone(timezone(timedelta(hours=int(desfase[:3]))))
        d = info.get("d") or local.strftime("%Y-%m-%d")
        if not re.match(r"^\d{4}-\d\d-\d\d$", d):
            d = local.strftime("%Y-%m-%d")
        if not existente and modo_ia and info.get("p"):
            posible = f"{d}_{slug(info['p'])}"
            if posible in por_id:
                existente = por_id[posible]
        if not existente and not modo_ia:
            # sin IA: misma ciudad, mismo día y título muy parecido
            for a in recientes:
                if a.get("d") == d and a.get("estado") == info["estado"] and parecido(a.get("t", ""), info.get("t", "")):
                    existente = a
                    break
        if existente:
            if not any(s.get("u") == fuente["u"] or s.get("n") == fuente["n"] for s in existente.get("src", [])):
                antes = any(s.get("n") in config.CONFIRMADORAS for s in existente.get("src", []))
                existente.setdefault("src", []).append(fuente)
                if not antes and fuente["n"] in config.CONFIRMADORAS:
                    confirmados += 1
                # si la nueva fuente dice que hubo muertos o heridos, se actualiza
                orden = {"sd": 0, "les": 1, "fatal": 2}
                if "sev" in existente and orden.get(info.get("sev"), 0) > orden.get(existente.get("sev"), 0):
                    existente["sev"] = info["sev"]
                log(f"  + fuente para {existente['id']}: {fuente['n']}")
            continue

        h = info.get("h") or ""
        hora = h if re.match(r"^\d\d:\d\d$", h) else "12:00"
        doc = {
            "d": d, "h": h, "ts": f"{d}T{hora}:00{desfase}",
            "t": (info.get("t") or n.get("titulo", ""))[:140],
            "p": info.get("p") or "", "estado": info["estado"],
            "tipo": info.get("tipo") if info.get("tipo") in ("vial", "laboral", "hogar", "incendio", "agua", "otro") else "otro",
            "src": [fuente], "creado": AHORA.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        base = f"{d}_{slug(doc['p'] or doc['t'])}"
        doc_id, k = base, 2
        while doc_id in por_id:
            doc_id, k = f"{base}-{k}", k + 1
        doc["id"] = doc_id

        punto = geo.ubicar(info, info["estado"]) if doc["p"] else None
        if punto and dentro(punto[0], punto[1]):
            doc.update({"lat": punto[0], "lon": punto[1], "pr": punto[2],
                        "sev": info.get("sev") if info.get("sev") in ("fatal", "les", "sd") else "sd"})
            acc.append(doc)
            destino = "mapa"
        else:
            sin.append(doc)
            destino = "sin ubicación"
        por_id[doc_id] = doc
        nuevos.append(doc)
        log(f"  NUEVO ({destino}) {doc['estado']} · {doc['tipo']} · {doc['t']} · {doc['p']}")

    # 3. Limpieza --------------------------------------------------------------
    corte = AHORA - timedelta(days=config.DIAS_CONSERVAR)
    acc = [a for a in acc if ts_de(a) >= corte]
    sin = [a for a in sin if ts_de(a) >= corte]
    corte_vistos = (AHORA - timedelta(days=7)).isoformat()
    vistos = {u: f for u, f in vistos.items() if f >= corte_vistos}

    # 4. Guardar ---------------------------------------------------------------
    abrev = {"Yucatán": "Yuc", "Campeche": "Camp", "Quintana Roo": "QRoo"}
    if nuevos:
        partes = [f"{abrev[e]} {c}" for e in config.ESTADOS if (c := sum(1 for x in nuevos if x["estado"] == e))]
        resultado = f"{len(nuevos)} nuevo{'s' if len(nuevos) != 1 else ''} ({', '.join(partes)})"
    else:
        resultado = "sin novedades"
    if confirmados:
        resultado += f", {confirmados} confirmado{'s' if confirmados != 1 else ''}"
    if errores:
        resultado += f"; {errores} notas con error"
    estado = {"ultimaRevision": AHORA.strftime("%Y-%m-%dT%H:%M:%SZ"), "intervaloMin": 60, "resultado": resultado,
              "fuentes": ["medios de la península", "Google Noticias"],
              "metodo": "Claude" if modo_ia else "palabras clave"}
    orden = lambda lst: sorted(lst, key=lambda a: a.get("ts", ""), reverse=True)
    guardar(f"{pub}/accidentes.json", orden(acc))
    guardar(f"{pub}/sinubicacion.json", orden(sin))
    guardar(f"{pub}/estado.json", estado)
    guardar(f"{priv}/vistos.json", vistos)
    guardar(f"{priv}/geocache.json", geocache)
    log(f"Fin: {resultado}")


def clasificarlas_parece(n):
    return clasificar.parece_accidente(n)


def parecido(a, b):
    pa = set(re.findall(r"[a-z0-9]{4,}", clasificar.sin_acentos(a)))
    pb = set(re.findall(r"[a-z0-9]{4,}", clasificar.sin_acentos(b)))
    return bool(pa and pb) and len(pa & pb) / min(len(pa), len(pb)) >= 0.6


if __name__ == "__main__":
    main()
