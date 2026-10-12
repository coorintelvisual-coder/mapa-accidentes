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


def parece_accidente(nota):
    txt = sin_acentos(nota.get("titulo", "") + " " + nota.get("resumen", "")[:400])
    if not any(sin_acentos(k) in txt for k in config.CLAVE_ACCIDENTE):
        return False
    titulo = sin_acentos(nota.get("titulo", ""))
    if any(sin_acentos(k) in titulo for k in config.CLAVE_EXCLUIR):
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
def con_reglas(nota):
    txt = sin_acentos(nota.get("titulo", "") + " " + nota.get("resumen", ""))
    tipo = "vial"
    for t, palabras in config.TIPOS_PALABRAS:
        if any(sin_acentos(p) in txt for p in palabras):
            tipo = t
            break
    ciudad, estado = "", ""
    # la ciudad mencionada primero (en título y luego en texto)
    for parte in (sin_acentos(nota.get("titulo", "")), txt):
        hallazgos = [(parte.find(sin_acentos(c)), c) for c in config.CIUDADES if sin_acentos(c) in parte]
        if hallazgos:
            ciudad = min(hallazgos)[1]
            estado = config.CIUDADES[ciudad][0]
            break
    if not estado:
        for e in config.ESTADOS:
            if sin_acentos(e) in txt:
                estado = e
                break
    if not estado and "poresto.com/" in nota["url"]:
        for slug, e in (("/yucatan/", "Yucatán"), ("/campeche/", "Campeche"), ("/quintana-roo/", "Quintana Roo")):
            if slug in nota["url"]:
                estado = e
    if not estado:
        return {"es_accidente": False}
    # Notas de medios desconocidos (p.ej. por Google Noticias) solo si nombran el estado:
    # evita confundir Mérida (España/Venezuela) o Campeche con otros lugares.
    conocidos = set(config.DOMINIOS.values()) | config.CONFIRMADORAS
    if nota.get("fuente") not in conocidos and not any(sin_acentos(e) in txt for e in config.ESTADOS + ["Q. Roo", "Quintana"]):
        return {"es_accidente": False}
    sev = "sd"
    if re.search(r"muer|fallec|sin vida|pierde la vida|perdio la vida|cadaver|deceso", txt):
        sev = "fatal"
    elif re.search(r"lesionad|herid|hospital|policontundid|trasladad|paramedic", txt):
        sev = "les"
    f = nota.get("fecha")
    return {
        "es_accidente": True, "tipo": tipo, "estado": estado,
        "d": "", "h": "", "t": nota.get("titulo", "")[:110],
        "p": ciudad, "sev": sev,
        "geo": {"modo": "ninguno", "municipio": ciudad},
        "duplicado_de": None,
    }


def clasificar(nota, registrados):
    if os.environ.get("ANTHROPIC_API_KEY"):
        return con_claude(nota, registrados), "claude"
    return con_reglas(nota), "reglas"
