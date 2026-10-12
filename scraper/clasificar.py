"""Decide si una nota es un accidente y extrae sus datos.

Con ANTHROPIC_API_KEY usa Claude (mucho más preciso). Sin clave usa reglas
de palabras clave: detecta el tipo y la ciudad, pero no la calle exacta.
"""
import json
import os
import re
import unicodedata

import requests

from . import config


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def contiene(texto, palabra):
    """Busca la palabra como palabra completa (no dentro de otra: 'Ticul' no está en 'artículo')."""
    return re.search(r"(?<![a-z0-9])" + re.escape(sin_acentos(palabra)), texto) is not None


def parece_accidente(nota):
    titulo = sin_acentos(nota.get("titulo", ""))
    txt = sin_acentos(nota.get("titulo", "") + " " + nota.get("resumen", "")[:400])
    if not any(sin_acentos(k) in txt for k in config.CLAVE_ACCIDENTE):
        return False
    if any(sin_acentos(k) in txt for k in config.CLAVE_EXCLUIR):
        return False
    if any(sin_acentos(k) in titulo for k in config.CLAVE_NO_HECHO):
        return False
    if any(contiene(titulo, e) for e in config.OTROS_ESTADOS):
        return False
    return True


# ---------------------------------------------------------------------------
INSTRUCCIONES = """Eres el editor de un mapa de accidentes de la Península de Yucatán (estados de Yucatán, Campeche y Quintana Roo, México).
Recibes una nota periodística y respondes SOLO con un objeto JSON, sin texto adicional.

Reglas:
- es_accidente: true solo si narra un accidente concreto y NO intencional ocurrido en Yucatán, Campeche o Quintana Roo. false para riñas, asaltos, homicidios, suicidios, operativos, estadísticas, opinión, prevención o hechos de otros estados o países (ojo: hay una Mérida en España y en Venezuela).
- tipo: "vial" (choques, volcaduras, atropellos, motos, salidas de camino, tren, transporte), "laboral" (obras, fábricas, talleres, caídas de trabajadores, maquinaria, electrocución trabajando), "hogar" (caídas, quemaduras, intoxicaciones o electrocuciones en casa), "incendio" (incendios, explosiones, fugas de gas), "agua" (ahogamientos o rescates en cenotes, albercas, playas, mar, pozos), "otro" (caída de árboles, postes, bardas o estructuras, ataques de animales, otros).
- estado: "Yucatán" | "Campeche" | "Quintana Roo".
- d: fecha local del accidente "AAAA-MM-DD" (si dice "anoche" o "esta madrugada", calcula a partir de la fecha de publicación).
- h: "HH:MM" en 24 h si la nota da la hora; "madrugada" o "noche" si solo dice eso; "" si no se sabe.
- t: titular breve en español, sin mayúsculas sostenidas, máximo 110 caracteres.
- p: lugar legible con la ciudad o municipio, p.ej. "Calle 60 x 45, Centro, Mérida" o "Carretera 307 km 280, Tulum". "" si la nota no dice dónde.
- sev: "fatal" si murió alguien, "les" si hubo lesionados, "sd" si no se menciona.
- geo: cómo ubicarlo en el mapa:
    modo "cruce": se conocen dos calles que se cruzan -> calle_a, calle_b (nombres como aparecen en OpenStreetMap: "Calle 60", "Avenida Tulum", "Avenida Itzáes"), colonia, municipio.
    modo "lugar": un sitio con nombre (plaza, hospital, cenote, playa, fábrica, colonia o fraccionamiento) -> lugar, municipio.
    modo "tramo": carretera con km o referencia -> lat y lon aproximados sobre la vía (solo si estás razonablemente seguro), lugar, municipio.
    modo "ninguno": no hay lugar identificable más allá de la ciudad.
- duplicado_de: si el accidente es EL MISMO hecho que alguno de la lista "ya registrados" (mismo día y mismo lugar o mismo suceso), pon su id; si no, null.

Formato:
{"es_accidente":true,"tipo":"vial","estado":"Yucatán","d":"2026-10-09","h":"","t":"...","p":"...","sev":"sd","geo":{"modo":"cruce","calle_a":"","calle_b":"","colonia":"","lugar":"","municipio":"","lat":null,"lon":null},"duplicado_de":null}"""


def con_claude(nota, registrados):
    clave = os.environ.get("ANTHROPIC_API_KEY")
    lista = "\n".join(f"- {r['id']}: {r.get('t','')} | {r.get('p','')}" for r in registrados[:60]) or "(ninguno)"
    publicado = nota["fecha"].isoformat() if nota.get("fecha") else "desconocida"
    contenido = (f"Fuente: {nota.get('fuente','')}\nPublicada: {publicado}\nURL: {nota['url']}\n"
                 f"Título: {nota.get('titulo','')}\nTexto: {nota.get('resumen','')[:1800]}\n\n"
                 f"Ya registrados en las últimas 48 h:\n{lista}")
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": os.environ.get("MODELO_CLAUDE", config.MODELO_CLAUDE), "max_tokens": 600,
              "system": INSTRUCCIONES, "messages": [{"role": "user", "content": contenido}]},
        timeout=60,
    )
    r.raise_for_status()
    texto = "".join(b.get("text", "") for b in r.json().get("content", []))
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError("respuesta sin JSON")
    return json.loads(m.group(0))


# ---------------------------------------------------------------------------
LUGAR_RX = re.compile(
    r"\b(?:en|sobre|de)\s+(?:la|el|los)?\s*"
    r"((?:avenida|av\.|calle|carretera|colonia|col\.|fraccionamiento|fracc\.|regi[oó]n|supermanzana|sm|"
    r"bulevar|boulevard|perif[eé]rico|puente|glorieta|libramiento|tramo)\s+[^,;:!?()]{2,60})",
    re.I)


def lugar_de(texto):
    """Extrae una referencia de lugar del texto: 'avenida Andrés Quintana Roo', 'carretera Mérida-Motul'."""
    m = LUGAR_RX.search(texto or "")
    if not m:
        return ""
    lugar = re.sub(r"\bQ\.\s*Roo\b", "Quintana Roo", m.group(1), flags=re.I)
    lugar = re.split(r"\.(?:\s|$)", lugar, maxsplit=1)[0]          # fin de oración
    # cortar antes de verbos o conectores que ya no son parte del nombre
    lugar = re.split(r"\s+(?:deja|dejó|provoca|provocó|genera|tras|luego|donde|cuando|que|y|con|a la altura|en|de la ciudad|del municipio|esta|este|hoy)\b",
                     lugar, maxsplit=1, flags=re.I)[0]
    lugar = lugar.strip(" -")
    for c in sorted(config.CIUDADES, key=len, reverse=True):     # "... de Cancún" -> "..."
        lugar = re.sub(rf"\s+(?:de|del|en)\s+{re.escape(c)}$", "", lugar, flags=re.I)
    return lugar.strip(" -")


CRUCE_RX = re.compile(r"\bcalle\s+(\d{1,3}[a-z]?)\s+(?:x|por|y|esquina con)\s+(?:calle\s+)?(\d{1,3}[a-z]?)\b", re.I)
COLONIA_RX = re.compile(r"\b(?:colonia|col\.|fraccionamiento|fracc\.|del)\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ0-9][\wáéíóúñ]*){0,3})")


def con_reglas(nota):
    titulo = nota.get("titulo", "")
    txt = sin_acentos(titulo + " " + nota.get("resumen", ""))
    tipo = "vial"
    for t, palabras in config.TIPOS_PALABRAS:
        if any(sin_acentos(p) in txt for p in palabras):
            tipo = t
            break
    ciudad, estado = "", ""
    # la ciudad mencionada primero, como palabra completa (primero en el título, luego en el texto)
    for parte in (sin_acentos(titulo), txt):
        hallazgos = []
        for c in config.CIUDADES:
            m = re.search(r"(?<![a-z0-9])" + re.escape(sin_acentos(c)) + r"(?![a-z0-9])", parte)
            if m:
                hallazgos.append((m.start(), -len(c), c))
        if hallazgos:
            ciudad = min(hallazgos)[2]
            estado = config.CIUDADES[ciudad][0]
            break
    # el estado nombrado explícitamente manda sobre la ciudad
    for e in config.ESTADOS:
        if contiene(sin_acentos(titulo), e) and not (e == "Campeche" and ciudad == "Campeche"):
            if estado and estado != e:
                ciudad = ""
            estado = e
            break
    if not estado:
        for e in config.ESTADOS:
            if contiene(txt, e):
                estado = e
                break
    if not estado and "poresto.com/" in nota["url"]:
        for slug, e in (("/yucatan/", "Yucatán"), ("/campeche/", "Campeche"), ("/quintana-roo/", "Quintana Roo")):
            if slug in nota["url"]:
                estado = e
    if not estado:
        return {"es_accidente": False}
    # Notas de medios desconocidos (p.ej. por Google Noticias) solo si nombran el estado o una ciudad
    conocidos = set(config.DOMINIOS.values()) | config.CONFIRMADORAS
    if nota.get("fuente") not in conocidos and not ciudad and not any(contiene(txt, e) for e in config.ESTADOS):
        return {"es_accidente": False}
    sev = "sd"
    if re.search(r"muer|fallec|sin vida|pierde la vida|perdio la vida|cadaver|deceso", txt):
        sev = "fatal"
    elif re.search(r"lesionad|herid|hospital|policontundid|trasladad|paramedic", txt):
        sev = "les"
    lugar = lugar_de(titulo) or lugar_de(nota.get("resumen", "")[:600])
    if lugar and ciudad and sin_acentos(ciudad) not in sin_acentos(lugar):
        p = f"{lugar[0].upper()}{lugar[1:]}, {ciudad}"
    else:
        p = (lugar[0].upper() + lugar[1:]) if lugar else ciudad
    es_carretera = bool(re.match(r"(carretera|tramo|libramiento|perif)", sin_acentos(lugar)))
    geo = {"modo": "ninguno", "municipio": ciudad}
    cruce = CRUCE_RX.search(lugar or "")
    if cruce and ciudad:
        col = COLONIA_RX.search(lugar)
        geo = {"modo": "cruce", "calle_a": f"Calle {cruce.group(1)}", "calle_b": f"Calle {cruce.group(2)}",
               "colonia": col.group(1) if col else "", "municipio": ciudad}
    elif lugar and ciudad and not es_carretera:
        geo = {"modo": "lugar", "lugar": lugar, "municipio": ciudad}
    t = re.sub(r"\s+", " ", re.sub(r"[^\w\s,.;:¡!¿?()\"'%-]", "", titulo)).strip()
    if t.isupper() or sum(1 for w in t.split() if len(w) > 3 and w.isupper()) >= 2:
        t = t.capitalize()
    return {
        "es_accidente": True, "tipo": tipo, "estado": estado,
        "d": "", "h": "", "t": t[:110],
        "p": p, "sev": sev, "geo": geo,
        "duplicado_de": None, "clave_lugar": clave_lugar(lugar) if lugar else "",
    }


def clave_lugar(lugar):
    """Forma normalizada del lugar para detectar el mismo accidente contado por varios medios."""
    s = sin_acentos(lugar)
    s = re.sub(r"\b(la|el|de|del|los|las|avenida|av|calle|carretera|colonia|col|fraccionamiento|fracc|tramo)\b", " ", s)
    return " ".join(re.findall(r"[a-z0-9]+", s))


def clasificar(nota, registrados):
    if os.environ.get("ANTHROPIC_API_KEY"):
        return con_claude(nota, registrados), "claude"
    return con_reglas(nota), "reglas"
