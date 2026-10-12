"""Configuración del mapa de accidentes de la Península de Yucatán.

Aquí se editan las fuentes, las búsquedas, las palabras clave y los nombres
de fuente que cuentan como "confirmadoras". No hace falta tocar el resto
del código para agregar o quitar una fuente.
"""

# ---------------------------------------------------------------------------
# Rutas de los archivos de datos
# ---------------------------------------------------------------------------
DATA_PUBLICA = "docs/data"          # lo que lee la página del mapa
DATA_PRIVADA = "data"               # memoria interna del script (no se publica)

# Cuántas horas hacia atrás se aceptan notas nuevas
VENTANA_HORAS = 48
# Días que se conservan los accidentes en el mapa
DIAS_CONSERVAR = 35
# Máximo de notas que se mandan a clasificar por corrida (controla el costo)
MAX_CLASIFICAR = 40
# Modelo de Claude para clasificar (barato y rápido)
MODELO_CLAUDE = "claude-haiku-4-5"

# ---------------------------------------------------------------------------
# Estados y zona horaria
# ---------------------------------------------------------------------------
DESFASE = {"Yucatán": "-06:00", "Campeche": "-06:00", "Quintana Roo": "-05:00"}
ESTADOS = list(DESFASE)

# Límites de la península (lo que cae fuera va a "sin ubicación")
LAT_MIN, LAT_MAX = 17.80, 21.70
LON_MIN, LON_MAX = -92.50, -86.70

# ---------------------------------------------------------------------------
# Fuentes que se leen directamente
#   tipo "rss":  feed RSS/Atom (WordPress suele tenerlo en /feed/)
#   tipo "html": página de sección; se toman los enlaces que cumplan "patron"
#   n: nombre EXACTO de la fuente tal como lo muestra el mapa
# ---------------------------------------------------------------------------
FUENTES = [
    {"n": "Por Esto!", "tipo": "html", "url": "https://www.poresto.com/yucatan/sucesos/",
     "patron": r"/(?:yucatan|campeche|quintana-roo)/sucesos/\d{4}/\d\d/\d\d/[a-z0-9-]+\.html"},
    {"n": "Por Esto!", "tipo": "html", "url": "https://www.poresto.com/campeche/sucesos/",
     "patron": r"/(?:yucatan|campeche|quintana-roo)/sucesos/\d{4}/\d\d/\d\d/[a-z0-9-]+\.html"},
    {"n": "Por Esto!", "tipo": "html", "url": "https://www.poresto.com/quintana-roo/sucesos/",
     "patron": r"/(?:yucatan|campeche|quintana-roo)/sucesos/\d{4}/\d\d/\d\d/[a-z0-9-]+\.html"},
    {"n": "Quintana Roo Hoy", "tipo": "rss", "url": "https://quintanaroohoy.com/tag/accidente/feed/"},
    {"n": "Noticias Cancún", "tipo": "rss", "url": "https://noticiascancun.mx/feed/"},
    {"n": "TV Azteca Quintana Roo", "tipo": "html", "url": "https://www.aztecaquintanaroo.com/trafico"},
    # Diario de Yucatán bloquea a los servidores de GitHub (error 403); sus notas llegan por Google Noticias.
]

# ---------------------------------------------------------------------------
# Búsquedas en Google Noticias (RSS). "when:1d" = últimas 24 horas.
# ---------------------------------------------------------------------------
BUSQUEDAS = [
    "accidente Mérida Yucatán", "choque Mérida", "accidente carretera Yucatán",
    "accidente Valladolid Yucatán", "accidente Progreso Yucatán", "accidente Tizimín",
    "accidente Campeche", "accidente Ciudad del Carmen", "accidente Champotón", "accidente Escárcega",
    "accidente Cancún", "accidente Playa del Carmen", "accidente Chetumal", "accidente Tulum",
    "accidente Cozumel", "accidente Felipe Carrillo Puerto", "accidente Bacalar",
    "incendio Mérida", "incendio Cancún", "incendio Campeche", "incendio Chetumal",
    "ahogado playa Quintana Roo", "ahogado cenote Yucatán", "accidente laboral Campeche",
    "accidente laboral Yucatán", "accidente laboral Cancún",
    "Guardia Nacional carretera accidente Yucatán", "Guardia Nacional carretera Quintana Roo accidente",
    "Cruz Roja Cancún accidente", "bomberos Campeche incendio", "volcadura Yucatán",
    "volcadura Quintana Roo", "volcadura Campeche", "atropellado Mérida", "atropellado Cancún",
]

# ---------------------------------------------------------------------------
# Dominio -> nombre de fuente (para notas que llegan por Google Noticias)
# ---------------------------------------------------------------------------
DOMINIOS = {
    "poresto.com": "Por Esto!",
    "lajornadamaya.mx": "La Jornada Maya",
    "yucatan.com.mx": "Diario de Yucatán",
    "aztecayucatan.com": "TV Azteca Yucatán",
    "aztecaquintanaroo.com": "TV Azteca Quintana Roo",
    "yucatan.quadratin.com.mx": "Quadratín Yucatán",
    "campeche.quadratin.com.mx": "Quadratín Campeche",
    "quintanaroo.quadratin.com.mx": "Quadratín Quintana Roo",
    "noticiascancun.mx": "Noticias Cancún",
    "quintanaroohoy.com": "Quintana Roo Hoy",
    "noticaribe.com.mx": "Noticaribe",
    "dqr.com.mx": "Diario de Quintana Roo",
    "tribunacampeche.com": "Tribuna Campeche",
    "trecevision.com": "Trecevisión",
    "sipse.com/novedades-yucatan": "Novedades Yucatán",
    "sipse.com/novedades-campeche": "Novedades Campeche",
    "sipse.com/novedades": "Novedades Quintana Roo",
}

# Nombres que la página marca como "confirmado"
CONFIRMADORAS = {
    "ECO Yucatán", "SSP Yucatán", "Policía Municipal de Mérida", "Fiscalía de Yucatán",
    "Protección Civil Yucatán", "Diario de Yucatán", "Novedades Yucatán", "Trecevisión",
    "TV Azteca Yucatán", "Quadratín Yucatán",
    "Tribuna Campeche", "Novedades Campeche", "Quadratín Campeche", "SSP Campeche",
    "Fiscalía de Campeche", "Protección Civil Campeche",
    "Novedades Quintana Roo", "Quadratín Quintana Roo", "Diario de Quintana Roo", "Noticaribe",
    "TV Azteca Quintana Roo", "Noticias Cancún", "Quintana Roo Hoy", "SSC Quintana Roo",
    "Fiscalía de Quintana Roo", "Protección Civil Quintana Roo",
    "Por Esto!", "La Jornada Maya", "Guardia Nacional", "Cruz Roja", "Bomberos",
}

# Fuentes que nunca se usan (la página "PorEso" no es Por Esto!)
FUENTES_EXCLUIDAS = {"poreso", "por eso"}

# ---------------------------------------------------------------------------
# Palabras clave
# ---------------------------------------------------------------------------
# Una nota solo se considera si su título o resumen tiene alguna de estas:
CLAVE_ACCIDENTE = [
    "accidente", "choque", "chocan", "choca", "volcadura", "vuelca", "volcó", "atropell",
    "arrollad", "derrap", "carambola", "impacta", "se impacta", "colisión", "embiste",
    "sale del camino", "salió del camino", "pierde el control", "prensad",
    "incendio", "se incendia", "explosión", "explota", "fuga de gas", "flamazo", "conato",
    "ahog", "se ahoga", "rescatan", "arrastrado por la corriente", "corriente de resaca",
    "electrocut", "descarga eléctrica", "cae de", "cayó de", "caída", "se desploma",
    "derrumbe", "colapsa", "cae árbol", "cae un árbol", "cae poste", "barda", "abejas",
    "picadura", "mordid", "quemad", "intoxica", "lesionad", "herido",
    "motociclista", "ciclista", "peaton", "peatón", "muere", "pierde la vida", "trailer", "tráiler",
]
# Si aparece alguna de estas, casi seguro NO es un accidente (hecho intencional)
CLAVE_EXCLUIR = [
    "asesin", "homicid", "balead", "balacera", "disparo", "apuñal", "riña", "pelea",
    "asalto", "asaltan", "robo", "roban", "feminicid", "suicid", "se quita la vida",
    "ahorcad", "ejecutad", "secuestr", "agresión", "golpean", "detienen a presunto",
]

TIPOS_PALABRAS = [  # en orden: la primera que coincide gana (solo modo sin Claude)
    ("incendio", ["incendi", "explosi", "explota", "fuga de gas", "flamazo", "conato", "llamas"]),
    ("vial", ["choque", "choca", "volcad", "vuelca", "atropell", "derrap", "carambola", "motociclista"]),
    ("agua", ["ahog", "cenote", "alberca", "bañista", "en la playa", "oleaje", "resaca", "pozo", "náufrag"]),
    ("laboral", ["trabajador", "obrero", "albañil", "andamio", "maquinaria", "laboral", "fábrica", "taller"]),
    ("hogar", ["en su casa", "en su domicilio", "vivienda", "hogar", "intoxica", "se quema"]),
    ("otro", ["árbol", "poste", "barda", "abejas", "perro", "cocodrilo", "picadura", "derrumbe", "techo"]),
    ("vial", ["moto", "auto", "camioneta", "tráiler", "carretera", "taxi", "autobús", "vehículo", "conductor"]),
]

# Municipios y ciudades conocidos (para adivinar el estado y la ciudad en modo sin Claude)
CIUDADES = {
    "Mérida": ("Yucatán", 20.975, -89.640), "Kanasín": ("Yucatán", 20.934, -89.558),
    "Umán": ("Yucatán", 20.880, -89.745), "Progreso": ("Yucatán", 21.283, -89.663),
    "Valladolid": ("Yucatán", 20.690, -88.202), "Tizimín": ("Yucatán", 21.143, -88.152),
    "Ticul": ("Yucatán", 20.400, -89.534), "Motul": ("Yucatán", 21.095, -89.284),
    "Tekax": ("Yucatán", 20.205, -89.288), "Izamal": ("Yucatán", 20.931, -89.018),
    "Oxkutzcab": ("Yucatán", 20.303, -89.418), "Conkal": ("Yucatán", 21.075, -89.519),
    "Hunucmá": ("Yucatán", 21.016, -89.877), "Peto": ("Yucatán", 20.126, -88.922),
    "Campeche": ("Campeche", 19.845, -90.524), "Ciudad del Carmen": ("Campeche", 18.649, -91.822),
"Champotón": ("Campeche", 19.350, -90.722),
    "Escárcega": ("Campeche", 18.609, -90.743), "Calkiní": ("Campeche", 20.371, -90.051),
    "Hecelchakán": ("Campeche", 20.178, -90.133), "Candelaria": ("Campeche", 18.185, -91.044),
    "Hopelchén": ("Campeche", 19.746, -89.845), "Palizada": ("Campeche", 18.255, -92.091),
    "Cancún": ("Quintana Roo", 21.161, -86.851), "Playa del Carmen": ("Quintana Roo", 20.629, -87.073),
    "Tulum": ("Quintana Roo", 20.211, -87.465), "Cozumel": ("Quintana Roo", 20.509, -86.950),
    "Chetumal": ("Quintana Roo", 18.500, -88.296), "Bacalar": ("Quintana Roo", 18.677, -88.393),
    "Felipe Carrillo Puerto": ("Quintana Roo", 19.580, -88.045),
    "Puerto Morelos": ("Quintana Roo", 20.847, -86.875), "Isla Mujeres": ("Quintana Roo", 21.232, -86.731),
    "José María Morelos": ("Quintana Roo", 19.748, -88.708), "Kantunilkín": ("Quintana Roo", 21.100, -87.487),
    "Puerto Aventuras": ("Quintana Roo", 20.497, -87.229),
}
