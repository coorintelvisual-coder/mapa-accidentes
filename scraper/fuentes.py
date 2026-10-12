"""Lectura de fuentes: feeds RSS, páginas de sección y Google Noticias."""
import html
import re
import time
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from . import config

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SES = requests.Session()
SES.headers.update({"User-Agent": UA, "Accept-Language": "es-MX,es;q=0.9"})


def bajar(url, timeout=25):
    r = SES.get(url, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
    return r.text


def limpiar(s):
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)
    s = re.sub(r"<[^>]+>", " ", html.unescape(s))
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def fecha(s):
    """Convierte fechas RSS o ISO a datetime con zona horaria (o None)."""
    if not s:
        return None
    s = s.strip()
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _tag(bloque, nombre):
    m = re.search(rf"<{nombre}\b[^>]*>(.*?)</{nombre}>", bloque, re.S | re.I)
    return m.group(1) if m else ""


def nombre_por_dominio(url, defecto=""):
    u = url.lower()
    host = urllib.parse.urlparse(u).netloc.replace("www.", "")
    ruta = host + urllib.parse.urlparse(u).path
    # primero las claves más largas (p.ej. sipse.com/novedades-yucatan antes que sipse.com/novedades)
    for clave in sorted(config.DOMINIOS, key=len, reverse=True):
        if ruta.startswith(clave) or host == clave or host.endswith("." + clave):
            return config.DOMINIOS[clave]
    return defecto


# ---------------------------------------------------------------------------
def leer_rss(url, nombre=None):
    xml = bajar(url)
    notas = []
    for b in re.split(r"<item\b|<entry\b", xml)[1:]:
        link = limpiar(_tag(b, "link"))
        if not link:
            m = re.search(r'<link[^>]+href="([^"]+)"', b)
            link = m.group(1) if m else ""
        fuente = nombre
        m = re.search(r'<source[^>]*url="([^"]+)"[^>]*>(.*?)</source>', b, re.S)
        if not fuente and m:
            fuente = nombre_por_dominio(m.group(1), limpiar(m.group(2)))
        notas.append({
            "titulo": limpiar(_tag(b, "title")),
            "resumen": limpiar(_tag(b, "description") or _tag(b, "summary") or _tag(b, "content:encoded"))[:1200],
            "url": link.strip(),
            "fecha": fecha(limpiar(_tag(b, "pubDate") or _tag(b, "published") or _tag(b, "updated") or _tag(b, "dc:date"))),
            "fuente": fuente or "",
        })
    return notas


def leer_html(url, nombre, patron=None):
    pagina = bajar(url)
    base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
    enlaces = []
    for href in re.findall(r'href="([^"#?]+)"', pagina):
        absoluto = urllib.parse.urljoin(base, href)
        if urllib.parse.urlparse(absoluto).netloc != urllib.parse.urlparse(base).netloc:
            continue
        ruta = urllib.parse.urlparse(absoluto).path
        if patron:
            if not re.search(patron, ruta):
                continue
        else:
            # artículo típico: slug largo con guiones
            ultimo = ruta.rstrip("/").split("/")[-1]
            if ultimo.count("-") < 4:
                continue
        if absoluto not in enlaces:
            enlaces.append(absoluto)
    return [{"titulo": "", "resumen": "", "url": u, "fecha": None, "fuente": nombre, "pendiente": True}
            for u in enlaces[:25]]


def completar_articulo(nota):
    """Descarga el artículo y toma título, resumen, fecha y primeros párrafos."""
    try:
        pag = bajar(nota["url"])
    except Exception:
        return nota

    def meta(prop):
        m = re.search(rf'<meta[^>]+(?:property|name|itemprop)="{prop}"[^>]+content="([^"]*)"', pag, re.I) \
            or re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name|itemprop)="{prop}"', pag, re.I)
        return html.unescape(m.group(1)).strip() if m else ""

    nota["titulo"] = nota.get("titulo") or meta("og:title") or limpiar(_tag(pag, "title"))
    desc = meta("og:description") or meta("description")
    parrafos = [limpiar(p) for p in re.findall(r"<p\b[^>]*>(.*?)</p>", pag, re.S | re.I)]
    cuerpo = " ".join(p for p in parrafos if len(p) > 60)[:1500]
    nota["resumen"] = (desc + " " + cuerpo).strip()[:1800]
    if not nota.get("fecha"):
        f = meta("article:published_time") or meta("datePublished")
        if not f:
            m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', pag)
            f = m.group(1) if m else ""
        nota["fecha"] = fecha(f)
    if not nota.get("fecha"):
        m = re.search(r"/(\d{4})/(\d\d)/(\d\d)/", nota["url"])
        if m:
            nota["fecha"] = datetime(int(m[1]), int(m[2]), int(m[3]), 12, tzinfo=timezone.utc)
    nota.pop("pendiente", None)
    return nota


def google_noticias(consulta):
    q = urllib.parse.quote(consulta + " when:1d")
    url = f"https://news.google.com/rss/search?q={q}&hl=es-419&gl=MX&ceid=MX:es-419"
    notas = leer_rss(url)
    for n in notas:
        # Google pone " - Nombre del medio" al final del título
        n["titulo"] = re.sub(r"\s+-\s+[^-]{2,60}$", "", n["titulo"])
        n["google"] = True
    return notas


def recolectar(log):
    """Devuelve todas las notas candidatas de todas las fuentes."""
    notas = []
    for f in config.FUENTES:
        try:
            if f["tipo"] == "rss":
                r = leer_rss(f["url"], f["n"])
            else:
                r = leer_html(f["url"], f["n"], f.get("patron"))
            log(f"  {f['n']}: {len(r)} enlaces ({f['url']})")
            notas += r
        except Exception as e:
            log(f"  ERROR {f['n']} ({f['url']}): {e}")
    for q in config.BUSQUEDAS:
        try:
            r = google_noticias(q)
            notas += r
            time.sleep(1)
        except Exception as e:
            log(f"  ERROR Google Noticias '{q}': {e}")
    log(f"  Google Noticias: {sum(1 for n in notas if n.get('google'))} resultados")
    # quitar repetidos por URL
    vistos, unicas = set(), []
    for n in notas:
        if n["url"] and n["url"] not in vistos:
            vistos.add(n["url"])
            unicas.append(n)
    return unicas
