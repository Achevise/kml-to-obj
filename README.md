# KMLto OBJ

Conversor de `KML -> OBJ` que:

- Extrae `Placemark` con `Point`, `LineString`, `Polygon` y `MultiGeometry`.
- Conserva nombres jerárquicos: `padre_hijo_nieto_...`.
- Si existe `GEOID` en el KML, usa `GEOID_NOMBRE` para evitar colisiones.
- Soporta materiales por shape, por estilo de origen o material compartido.
- Soporta particionado por nivel de jerarquía.

## Requisitos

- Python 3.10+

## Instalación en macOS

```bash
git clone https://github.com/Achevise/kml-to-obj.git
cd kml-to-obj
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Instalación en Windows

```powershell
git clone https://github.com/Achevise/kml-to-obj.git
cd kml-to-obj
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

## Uso

Generar OBJ:

```bash
kml2obj samples/example.kml out/example.obj
```

Inspeccionar estructura del KML sin exportar:

```bash
kml2obj samples/example.kml --inspect-kml
```

Además, en cada exportación se genera un fichero `.py` con el mismo nombre base que el OBJ (por ejemplo `scene.obj -> scene.py`) con:

```python
GEOID_TO_OBJECT = {
    "08001": "US_08001_Adams",
    ...
}
```

## Opciones CLI

```text
kml2obj INPUT_KML OUTPUT_PATH [opciones]
kml2obj INPUT_KML --inspect-kml
```

- `INPUT_KML`: ruta del KML de entrada.
- `OUTPUT_PATH`: ruta base de salida `.obj`.
- `--material-mode {per-shape,source,shared}`:
  - Default: `source`.
  - `per-shape`: material por shape.
  - `source`: agrupa material según estilo original del KML.
  - `shared`: un único material para todo el archivo.
- `--partition-level all|N`: `all` un solo fichero, `N` un fichero por rama de jerarquía a ese nivel. Default: `all`.
- `--point-radius FLOAT`: radio (m) para `Point`. Default: `1.0`.
- `--line-width FLOAT`: grosor (m) para `LineString`. Default: `0.2`.
- `--polygon-height FLOAT`: extrusión (m) para `Polygon`. Default: `0.0`.
- `--polygon-render-mode {polygon,outline,polygon+outline}`: modo de render para shapes `Polygon`. Default: `polygon`.
- `--polygon-outline-width auto|FLOAT|PERCENT%`: modo de tamaño del contorno de anillos de `Polygon`.
  - Default: `auto`.
  - `auto`: calcula el grosor como el `5%` del tamaño del bounding box del shape.
  - `FLOAT` (ej. `1`): grosor fijo en metros.
  - `PERCENT%` (ej. `5%`): porcentaje del tamaño del bounding box del shape.
  - Solo se usa si `--polygon-render-mode` es `outline` o `polygon+outline`.
  - Debe ser `> 0`, `>0%` o `auto` si `--polygon-render-mode` es `outline` o `polygon+outline`.
  - El outline se exporta como objeto independiente con sufijo `_Outline`.
- `--up-axis {x,y,z}`: eje vertical global. Por defecto: `z`.
- `--scale FLOAT`: escala global. Default: `1.0`.
- `--scale-x FLOAT`: escala adicional del eje X. Default: `1.0`.
- `--scale-y FLOAT`: escala adicional del eje Y. Default: `1.0`.
- `--scale-z FLOAT`: escala adicional del eje Z. Default: `1.0`.
- `--polygon-front {up,down,keep}`: dirección de frente para polígonos no extruidos. Default: `up`.
- `--decimate-tolerance FLOAT`: simplificación geométrica en metros (`0` desactiva). Default: `0.0`.
- `--flip-winding`: invierte winding de triángulos. Default: desactivado.
- `--inspect-kml`: imprime informe del KML y termina. Default: desactivado.

## Tests

```bash
PYTHONPATH=src python3 -m unittest -v tests/test_kml_parser.py tests/test_cli_output_modes_unittest.py tests/test_edge_cases_unittest.py
```
