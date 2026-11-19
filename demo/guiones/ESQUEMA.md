# Guiones (YAML)

`demo/guiones/NN.yml` describe un vídeo. `demo/capturas/runner.mjs` lo ejecuta, graba `demo/out/clips/NN.webm` y escribe `NN.env` para el montaje.

```bash
make demo-video-1                         # graba y monta
bash demo/capturas/run.sh 01              # solo graba
bash demo/capturas/run.sh --validar all   # comprueba los YAML sin abrir el navegador
```

`run.sh` toma el bloqueo `demo/out/.grabando`: solo hay una grabación a la vez.

## Estructura

```yaml
id: "01"
titulo: Del informe al código
subtitulo: Sugerencias CIE-10
ritmo: 1
velocidad: 1
cuenta: demo
textos:
  informe: ./textos/informe.txt
tema: {}
pasos: []
```

| Clave | Notas |
| --- | --- |
| `ritmo` | Escala pausas, rótulos, resaltados, tecleo y velocidad del cursor. Menor es más rápido. No escala `esperar`. |
| `velocidad` | Acelera el clip en el montaje. |
| `cuenta` | `demo` usa `DEMO_EMAIL`/`DEMO_PASSWORD` (o `SEED_ADMIN_*` del `.env`). `registro` da de alta una cuenta nueva antes de grabar. `nueva` genera los datos sin registrarlos, para que el guion haga el registro en pantalla. Define `@email` y `@password`, y con `nueva` también `@nombre`, `@apellidos` y `@usuario`. |
| `textos` | `@nombre` en un paso se sustituye por el texto. Una ruta relativa al guion se lee de fichero. |
| `tema` | Sobrescribe claves de `tema.yml` (fusión profunda). |

## Tema

Valores por defecto en `tema.yml`. Se inyectan como variables CSS (`--d-*`).

```yaml
colores: { primario, secundario, acento, texto, texto_suave, fondo, rotulo_a, rotulo_b, borde, cursor, onda }
tipografia: { familia, titulo_px, sub_px, fuente_embebida }
rotulo: { pos, radio_px, opacidad, blur_px, sombra, margen_px, ancho_max_px, contador, progreso, entrada_ms, salida_ms, escalonado_ms }
cursor: { tamano, color, onda_color, halo, halo_px }
spotlight: { oscurecido, radio_px, margen_px, ms }
camara: { easing, pan, ms }
transicion: { fundido_ms, color }
intro: { segundos, marca, titulo_px, sub_px }
cierre: { segundos, linea1, linea2 }
musica: { activada, volumen, tonos }
viewport: { ancho, alto }
```

`rotulo.pos`: `bottom`, `top`, `center`, `bottom-left`, `bottom-right`, `top-left`, `top-right`.

## Pasos

Cada paso tiene una acción y, opcionalmente, `seguro`, `timeout` y `nota`.

| Acción | Forma | Qué hace |
| --- | --- | --- |
| `rotulo` | `{ titulo, sub, pos, ms }` | Muestra un rótulo. Con `ms: 0` se queda hasta el siguiente rótulo o `quitar_rotulo`. |
| `quitar_rotulo` | `true` | Retira el rótulo. |
| `clic` | `selector` o `{ en, ms, despues }` | Mueve el cursor y hace clic. |
| `teclear` | `{ en, texto, retardo, despues }` | Teclea en un campo. `retardo` en ms por tecla. |
| `mover` | `selector` o `{ en, ms }` | Mueve el cursor. |
| `zoom` | `{ en, escala, ms }` o `{ reset: true }` | Zoom de cámara. Un zoom activo bloquea los clics: quítalo antes. |
| `resaltar` | `{ en, ms, margen }` | Atenúa todo menos el elemento. |
| `pausa` | `ms` | Espera. |
| `esperar` | `texto` o `{ texto \| selector, max }` | Espera a que aparezca algo. `max` en segundos (60). |
| `ir` | `url` | `/ruta` se resuelve contra la app. Expande `${VAR}` y `${VAR:-defecto}`. |
| `tecla` | `Enter`, `Control+Enter`... | Pulsa una tecla. |
| `scroll` | `{ en }`, `{ y }` o `{ en, y }` | `en`: lo lleva a la vista. `y`: posición absoluta. Ambos: scroll de ese elemento. |
| `captura` | `nombre` | Guarda `demo/out/screenshots/NN/NN-nombre.png`. |
| `login` | `true` o `{ lento: false }` | Inicia sesión con la cuenta del guion. |
| `confirmar` | `correo` | Abre el enlace de confirmación que llega a Mailpit y entra con la cuenta `nueva`. |
| `js` | `{ modulo, args }` | Ejecuta `export default async (v, lib, args, ctx)`. `modulo` es relativo a `demo/guiones/`. |

- `seguro: true`: si el paso falla, guarda `fallo-<acción>-<n>` y continúa. Falla en 8 s en lugar de 30.
- `timeout: N`: segundos de espera para ese paso.
- Sin `seguro`, un fallo detiene el vídeo y no se escribe el `.env`.

## Selectores

Cualquier selector de Playwright, más `rol=button[name=/nuevo análisis/i]` y `texto=Validar`. Se encadenan con ` >> `: `.opblock-get >> nth=0 >> .opblock-summary`. Si hay varios elementos se usa el primero.

Dentro de `{ ... }` una coma corta el valor: entrecomilla los textos que la lleven. `--validar` lo detecta como una clave desconocida.

## `NN.env`

`TITULO SUBTITULO COLOR_A COLOR_B COLOR_ACENTO COLOR_TEXTO COLOR_FONDO INTRO_S CIERRE_S MARCA CIERRE_1 CIERRE_2 MUSICA MUSICA_VOL MUSICA_TONOS VELOCIDAD INTRO_TITULO_PX INTRO_SUB_PX RITMO`. Las claves de montaje están en `demo/README.md`.

## Ejemplo

```yaml
id: "05"
titulo: Ejemplo
subtitulo: Un guion mínimo
ritmo: 0.8
cuenta: demo
textos:
  informe: ./textos/informe.txt
tema:
  colores: { primario: "#059669", secundario: "#0d9488" }
  rotulo: { pos: top, sombra: false }
pasos:
  - ir: /
  - login: true
  - rotulo: { titulo: "Empieza", sub: "Un informe, una conversación", ms: 2500 }
  - clic: "rol=button[name=/nuevo análisis/i]"
  - teclear: { en: '[placeholder*="informe" i]', texto: "@informe", retardo: 15 }
  - clic: "rol=button[name=/analizar/i]"
  - esperar: { selector: "rol=button[name=/^validar/i]", max: 120 }
  - captura: resultado
  - zoom: { reset: true }
