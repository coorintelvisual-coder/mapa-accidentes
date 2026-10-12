# Mapa de accidentes · Península de Yucatán

Mapa en vivo de accidentes en Yucatán, Campeche y Quintana Roo: viales, laborales, en el hogar, incendios, en el agua y otros. Un programa corre solo cada hora en GitHub, lee los medios de la península y actualiza el mapa. Nadie tiene que hacerlo a mano.

## Cómo funciona

1. **GitHub Actions** ejecuta `scraper/run.py` cada hora. Es gratis si el repositorio es público.
2. El programa lee:
   - las secciones de sucesos de Por Esto! (Yucatán, Campeche y Quintana Roo), Quintana Roo Hoy, Noticias Cancún, TV Azteca Quintana Roo y Diario de Yucatán;
   - unas 35 búsquedas en Google Noticias, como "accidente Cancún" o "incendio Campeche", que traen notas de otros medios.
3. Descarta lo que no parece accidente y lo que es intencional (riñas, asaltos, homicidios).
4. **Clasifica** cada nota de una de dos formas:
   - **Con Claude** (recomendado): si configuras una clave de la API de Anthropic, Claude Haiku lee la nota. Decide si es un accidente y extrae el tipo, el estado, el lugar exacto, la gravedad y la hora. También reconoce si es el mismo hecho que otro medio ya publicó.
   - **Sin clave**: usa reglas de palabras clave. Es gratis, pero solo identifica la ciudad, no la calle. Por eso casi todo queda en "Sin ubicación precisa".
5. **Ubica** cada accidente con OpenStreetMap: Overpass para cruces de calles y Nominatim para colonias y lugares.
6. Guarda todo en `docs/data/*.json`. La página `docs/index.html` lee esos archivos y se actualiza sola cada 5 minutos.

Un accidente queda **confirmado** cuando lo publicó alguna de las fuentes de la lista `CONFIRMADORAS` en `scraper/config.py`.

**Lo que no hace:** no lee Facebook, porque Facebook no permite leer páginas sin iniciar sesión. Tampoco registra calles cerradas nuevas. Los cierres que ya existían se conservan en `docs/data/cierres.json` y se pueden editar a mano.

---

## Puesta en marcha (unos 15 minutos)

### 1. Crea el repositorio

1. Entra a [github.com](https://github.com) y crea una cuenta si no tienes.
2. Arriba a la derecha, haz clic en **+ → New repository**.
3. Nombre: `mapa-accidentes`. Elige **Public**: así GitHub Actions y GitHub Pages son gratis. Haz clic en **Create repository**.
4. En la página del repositorio vacío, haz clic en **uploading an existing file**. Arrastra **todo el contenido** de esta carpeta, sin la carpeta misma. Deben quedar en la raíz `docs/`, `scraper/`, `data/`, `.github/`, `requirements.txt` y `README.md`.
   - La carpeta `.github` empieza con punto y a veces queda oculta. Si no la ves, crea el archivo a mano: **Add file → Create new file**, nombre `.github/workflows/actualizar.yml`, y pega el contenido del archivo `actualizar.yml`.
5. Haz clic en **Commit changes**.

### 2. Publica el mapa (GitHub Pages)

1. En el repositorio, ve a **Settings → Pages**.
2. En **Source** elige **Deploy from a branch**. En **Branch** elige `main` y la carpeta `/docs`. Haz clic en **Save**.
3. En uno o dos minutos aparece la dirección del mapa, algo como `https://TU-USUARIO.github.io/mapa-accidentes/`.

### 3. Configura la clasificación con Claude (recomendado)

1. Crea una clave en [console.anthropic.com](https://console.anthropic.com), en **API Keys → Create Key**. Agrega saldo en **Billing**; con 5 a 10 USD alcanza para empezar.
2. En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**.
   - Name: `ANTHROPIC_API_KEY`
   - Secret: la clave que copiaste.
3. En la pestaña **Variables** de esa misma pantalla, crea `CONTACTO_EMAIL` con tu correo. OpenStreetMap pide un contacto a quien usa su servicio de ubicación.

Sin el paso 3 el programa funciona igual, en modo de palabras clave.

### 4. Pruébalo

1. Ve a la pestaña **Actions**. Si GitHub pregunta, activa los workflows.
2. Elige **Actualizar mapa de accidentes → Run workflow → Run workflow**.
3. En 2 a 5 minutos verás si terminó en verde. Si haces clic en la corrida y luego en **Buscar accidentes nuevos**, ves qué leyó, qué agregó y qué falló.
4. Abre la dirección del mapa. Arriba dice la hora de la última revisión y lo que encontró.

A partir de ahí corre cada hora sin que hagas nada.

---

## Costos

- **GitHub Actions y Pages:** gratis en repositorios públicos.
- **API de Claude:** solo se mandan a Claude las notas que pasan el filtro de palabras clave, hasta 40 por corrida (`MAX_CLASIFICAR`). Una nota que ya se revisó no se vuelve a mandar. Calcula del orden de **5 a 20 USD al mes**, según cuántas notas haya. En console.anthropic.com puedes ver el gasto real y poner un límite mensual.

## Pausar o reanudar

- **Pausar:** pestaña **Actions → Actualizar mapa de accidentes →** menú **⋯ → Disable workflow**.
- **Reanudar:** el mismo menú, **Enable workflow**.
- GitHub pausa por su cuenta los workflows programados de un repositorio sin actividad en 60 días. Como este programa guarda cambios casi cada hora, normalmente no pasa. Si pasa, se reactiva igual.

## Ajustes frecuentes (`scraper/config.py`)

| Qué | Dónde |
|---|---|
| Agregar o quitar un medio | `FUENTES` (sección con RSS o página HTML) |
| Cambiar las búsquedas | `BUSQUEDAS` |
| Qué medios confirman | `CONFIRMADORAS` |
| Reconocer un medio por su dominio | `DOMINIOS` |
| Días que se conservan en el mapa | `DIAS_CONSERVAR` (35) |
| Límite de notas por hora (costo) | `MAX_CLASIFICAR` (40) |
| Modelo de Claude | `MODELO_CLAUDE` |

Para probar en tu computadora sin guardar nada:

```
pip install -r requirements.txt
python -m scraper.run --prueba
```

## Corregir algo a mano

Los datos son archivos de texto en `docs/data/`. En GitHub abre `accidentes.json`, haz clic en el lápiz, corrige o borra el registro y guarda. Cada accidente tiene esta forma:

```json
{"id": "2026-10-09_kinchil", "d": "2026-10-09", "h": "", "ts": "2026-10-09T12:00:00-06:00",
 "t": "Titular", "p": "Lugar, Municipio", "estado": "Yucatán", "lat": 20.91, "lon": -89.94,
 "pr": "colonia", "sev": "sd", "tipo": "vial",
 "src": [{"n": "Por Esto!", "u": "https://..."}], "creado": "2026-10-09T16:15:42Z"}
```

## Problemas comunes

- **Un medio aparece con ERROR en el registro.** Puede que cambió su página o que bloquea a los servidores de GitHub. Las búsquedas de Google Noticias suelen cubrir ese hueco. Si se repite, quítalo de `FUENTES`.
- **El mapa dice que la revisión se retrasó.** GitHub a veces atrasa las tareas programadas de 10 a 30 minutos en horas pico. Si pasan varias horas, revisa la pestaña Actions.
- **Accidentes en el lugar equivocado.** Cuando no encuentra el cruce exacto, el programa usa el centro de la colonia (`pr: "colonia"`). Corrígelo a mano si hace falta.
