# Vídeos de la demo

Cuatro vídeos de un minuto y pico, sin voz, que se graban solos: un robot maneja la app, ffmpeg le pone intro, cierre y música.

| Vídeo | De qué va |
| --- | --- |
| 01 | Del informe clínico a los códigos CIE-10, con las estrategias y el resumidor |
| 02 | Registro, conversaciones, historial, papelera y privacidad |
| 03 | Cómo piensa el motor: datos, métricas y explicabilidad |
| 04 | La infraestructura: servicios y monitorización |

## Sacarlos

Con la app levantada (`make mock-up`) y, para el 04, la monitorización (`make start-monitoring-dev`):

```bash
make demo-video-1     # graba y monta el vídeo 1 (de 1 a 4)
make demo-videos      # los cuatro, uno detrás de otro
```

Los mp4 acaban en `demo/out/videos/` y las capturas de cada paso en `demo/out/screenshots/`. Si el frontend no está en el puerto 3100: `make demo-video-1 DEMO_BASE_URL=http://host.docker.internal:3000`.

## Cómo funciona

1. `demo/guiones/NN.yml` dice qué hacer: abrir una página, escribir, hacer clic, enseñar un rótulo.
2. `demo/capturas/runner.mjs` lo ejecuta con Playwright dentro de un contenedor y graba `demo/out/clips/NN.webm`.
3. `demo/montaje/montar.sh` pone intro, cierre y música con ffmpeg, también en contenedor, y deja `demo/out/videos/NN.mp4`.

Cada comando de `make` se ve en pantalla, así que se puede seguir lo que hace.

## Carpetas

| Ruta | Qué hay |
| --- | --- |
| `demo/guiones/` | Un YAML por vídeo, `tema.yml` con los colores y `textos/` con los informes |
| `demo/guiones/js/` | Pasos que no se pueden escribir en YAML |
| `demo/capturas/` | `runner.mjs` que ejecuta el guion, `lib.mjs` con el cursor, los rótulos y el zoom, y `run.sh` que lo lanza |
| `demo/capturas/paginas/` | Páginas HTML que se enseñan en los vídeos 03 y 04 |
| `demo/montaje/` | Montaje con ffmpeg y plantillas HTML de la intro y el cierre |
| `demo/out/` | Todo lo generado. No se versiona |

## Cambiar cosas

- **Un texto o un paso:** edita `demo/guiones/NN.yml`. Los pasos están explicados en `demo/guiones/ESQUEMA.md`.
- **Los colores o la letra:** `demo/guiones/tema.yml`. Un guion puede sobrescribir cualquier valor con su propia clave `tema`.
- **Ir más rápido:** `ritmo` en el guion (menor es más rápido) o `velocidad`, que acelera el clip al montarlo.
- **Un vídeo nuevo:** copia `01.yml` a `05.yml` y lanza `make demo-video-5`.
- **La intro, el cierre o la música:** `intro`, `cierre` y `musica` de `tema.yml`. El resto de opciones del montaje están al final.

Para probar un guion sin grabar: `bash demo/capturas/run.sh --validar 01`.

## Cosas a saber

- Solo se graba un vídeo a la vez. `run.sh` crea `demo/out/.grabando` y las demás grabaciones esperan.
- Los vídeos 01 y 02 se registran con una cuenta nueva cada vez, así que no se ven conversaciones de pruebas anteriores. El 02 hace el registro entero, incluido el correo de confirmación, que lee de Mailpit.
- Al crear una conversación nueva, la app empuja el informe antes de que exista la conversación en la base de datos y el texto se pierde. `js/retraso_ws.mjs` retrasa ese mensaje 300 ms solo en la grabación.
- Con el motor mock, el vídeo 01 muestra lo que devuelve el mock. Para códigos reales hay que levantar el motor de verdad.
- En el vídeo 04 hay paneles de Grafana vacíos en el entorno mock (no hay métricas del motor ni de Traefik), así que solo se enseñan los que tienen datos.

## Opciones del montaje

Se leen de `demo/out/clips/NN.env`, que escribe el runner a partir del guion y del tema. Todas son opcionales. Un valor inválido avisa y usa el valor por defecto.

| Clave | Qué cambia | Defecto |
| --- | --- | --- |
| `TITULO`, `SUBTITULO` | Texto de la intro | `Clicoder` |
| `MARCA` | Etiqueta bajo el logo | `Clicoder` |
| `URL_BARRA` | Barra de direcciones de la ventana | `MARCA` |
| `CIERRE_1`, `CIERRE_2`, `CIERRE_3` | Textos del cierre | |
| `COLOR_A`, `COLOR_B` | Colores principales, `#rrggbb` | `#4338ca`, `#2563eb` |
| `COLOR_ACENTO` | Brillos y detalles | `#22d3ee` |
| `COLOR_TEXTO`, `COLOR_FONDO` | Texto de intro y cierre, y fondo de la ventana | `#ffffff`, `#eef2ff` |
| `FONDO_BASE` | Base oscura del fondo animado | derivado de A y B |
| `MARCO`, `PROGRESO` | `0` quita la ventana o la barra de progreso | `1` |
| `INTRO_S`, `CIERRE_S` | Duración en segundos, mínimo 2,5 | `4` |
| `INTRO_TITULO_PX`, `INTRO_SUB_PX` | Tamaño del texto de la intro | `84`, `44` |
| `RECORTE_INI` | Segundos que se quitan al principio del clip | `0.5` |
| `VELOCIDAD` | Aceleración del clip | `1` |
| `MUSICA`, `MUSICA_VOL` | Activar y volumen relativo | `1`, `0.10` |
| `MUSICA_BPM`, `MUSICA_ESCALA`, `MUSICA_TONOS` | Tempo, `mayor` o `menor`, y acorde fijo en Hz | `96`, `mayor` |

El montaje avisa si el vídeo final queda fuera de 75 a 105 segundos. Para montar sin grabar: `CLIPS_DIR=/ruta VIDEOS_DIR=/ruta demo/montaje/montar.sh NN`.
