# KML to FBX

Conversor de `KML -> OBJ/FBX` que:

- Extrae `Placemark` con `Point`, `LineString`, `Polygon` y `MultiGeometry`.
- Conserva nombres jerárquicos: `padre_hijo_nieto_...`.
- Si existe `GEOID` en el KML, el nivel de objeto usa `GEOID_NOMBRE` para evitar colisiones.
- Asigna material individual por shape.
- Soporta particionado por nivel de jerarquía.
- Exporta FBX con Autodesk FBX SDK (`fbx-sdk`).

## Requisitos

- Python 3.10+
- Autodesk FBX SDK 2020.3.9

Resolución de SDK:
- Puedes pasar `--fbxsdk-root PATH`
- o definir `FBXSDK_ROOT`
- en macOS, por defecto usa `tools/fbxsdk/pkg_expanded/.../FBX SDK/2020.3.9` si existe.

Notas Windows:
- El exportador FBX SDK usa `tools/fbxsdk/bin/fbxsdk_exporter.exe`.
- En Windows no se autocompila por ahora desde Python: compílalo con:
  - `tools\fbxsdk\build_fbxsdk_exporter_windows.bat`
  - opcionalmente define `FBXSDK_ROOT`.
- Luego puedes usar `--fbxsdk-exporter-bin` si quieres una ruta concreta.

## Instalación del proyecto

```bash
python -m pip install -e .
```

## Uso

Generar `.obj`:

```bash
kml2fbx samples/example.kml out/example.obj --output-format obj
```

Generar `.fbx` con FBX SDK:

```bash
kml2fbx samples/example.kml out/example_sdk.fbx --output-format fbx-sdk
```

Opciones útiles:

```bash
kml2fbx input.kml output.fbx --output-format fbx-sdk --polygon-height 30
kml2fbx input.kml output.fbx --output-format fbx-sdk --partition-level 2
kml2fbx input.kml output.obj --output-format obj --material-mode shared
```

Particionado por nivel (`all`, `1`, `2`, `3`, ...):

```bash
# Todo en un solo fichero
kml2fbx input.kml out/scene.fbx --output-format fbx-sdk --partition-level all

# Un fichero por segundo nivel
kml2fbx input.kml out/scene.fbx --output-format fbx-sdk --partition-level 2
```

Cuando se particiona, los archivos salen como:
`scene__nivel1_nivel2....ext`

## Opciones CLI (completas)

```
kml2fbx INPUT_KML OUTPUT_PATH [opciones]
```

Para inspeccionar el KML sin exportar:

```
kml2fbx INPUT_KML --inspect-kml
```

- `INPUT_KML`:
  ruta del KML de entrada.
- `OUTPUT_PATH`:
  ruta base de salida (`.obj` o `.fbx` según `--output-format`). No se usa con `--inspect-kml`.
- `--output-format {obj,fbx-sdk}`:
  formato de salida. Por defecto: `fbx-sdk`.
- `--material-mode {per-shape,source,shared}`:
  `per-shape` crea material por shape; `source` preserva agrupación de material según estilo original del KML (modo por defecto); `shared` usa un único material en todo el archivo.
- `--partition-level all|N`:
  `all` genera un único fichero; `N` (1,2,3,...) genera un fichero por rama de jerarquía hasta ese nivel.
- `--point-radius FLOAT`:
  radio (m) de representación para `Point`. Por defecto: `1.0`.
- `--line-width FLOAT`:
  grosor (m) de representación para `LineString`. Por defecto: `0.2`.
- `--polygon-height FLOAT`:
  extrusión (m) para `Polygon`. `0` = sin extrusión. Por defecto: `0.0`.
- `--polygon-front {up,down,keep}`:
  orientación de caras frontales para polígonos no extruidos. Por defecto: `up`.
- `--decimate-tolerance FLOAT`:
  simplificación geométrica en metros para `LineString` y `Polygon` (en plano XZ local). `0` desactiva. Por defecto: `0.0`.
- `--flip-winding`:
  invierte winding de todos los triángulos.
- `--fbxsdk-exporter-bin PATH`:
  ruta explícita al binario `fbxsdk_exporter` (solo `fbx-sdk`).
- `--fbxsdk-root PATH`:
  ruta raíz del Autodesk FBX SDK extraído (solo `fbx-sdk`).
- `--inspect-kml`:
  imprime un informe del KML origen (objetos, shapes, tipos, jerarquía, estilos/materiales) y termina sin exportar.

## Notas

- Coordenadas `lon/lat/alt` -> sistema local en metros.
- `Point` -> octaedro.
- `LineString` -> ribbon.
- `Polygon` -> triangulación ear clipping con soporte de huecos.
- `--polygon-height` extruye polígonos para mejorar visibilidad.

## Tests

```bash
PYTHONPATH=src python3 -m unittest -v tests/test_kml_parser.py tests/test_cli_output_modes_unittest.py tests/test_edge_cases_unittest.py tests/test_fbx_writer.py
```
