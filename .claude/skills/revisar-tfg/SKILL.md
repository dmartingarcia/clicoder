---
name: revisar-tfg
description: Revisa la memoria del TFG (tfg/*.tex) como lo haría un tribunal, buscando incoherencias numéricas, contradicciones, afirmaciones no verificables, rastros de escritura con IA y errores de compilación latentes. Úsala cuando se pida revisar, repasar o corregir el TFG, la memoria o los anexos.
metadata:
  type: project
---

# Revisión del TFG

Revisión crítica de `tfg/` con criterio de tribunal. El objetivo no es que el texto "quede bonito",
sino que **no haya nada que un revisor pueda rebatir con el código o los datos delante**.

## Reglas del autor (no negociables)

1. **Cero em-dashes.** Ni `—` (U+2014) ni `---` de LaTeX, en ninguna parte del PDF.
   Si un em-dash llega al PDF desde el código (p. ej. un campo que la API construye), se quita **en
   el código**, no parcheando el anexo. Usar paréntesis, dos puntos o coma según el caso.
2. **Nada inventado.** Toda cifra se verifica contra su fuente real (`training_runs.csv`,
   `eval_test.json`, `code_descriptions.json`, el router, `.env.example`, `seeds.exs`…). Si un dato
   no se puede verificar, se reformula o se quita; no se rellena de memoria.
3. **Terminología**: la persona es **codificador clínico**; el modelo es **`encoder`** (en cursiva).
   Nunca "codificador" para el modelo.
4. **En la comparativa con el benchmark aparecen las dos configuraciones ejecutables** del
   sistema, cada una en su puesto por MAP: el clasificador solo (0,437, último de diez) y el modo
   fusionado (0,545, segundo). Ambas están implementadas y se pueden ejecutar. Lo que NO se puede
   es presentar la buena sin decir que no es la que se sirve por defecto, ni mezclar cifras de
   pasadas distintas sin declararlo: en la pasada de la fusión el clasificador solo da 0,434.
5. **No inventar sistemas a posteriori.** Si tres ejecuciones probaban cosas distintas, promediarlas
   porque el número sale mejor NO es un sistema propuesto. Va al anexo como observación, nunca a la
   comparativa ni al titular.
6. **Honestidad por encima del número.** No ocultar qué sistemas nos superan ni maquillar un
   requisito incumplido: se declara y se lleva a trabajo futuro.
7. **Apuntar TODO en `ROADMAP.md`**, incluidos los hallazgos que no se arreglan.
8. **Commits**: una línea, sin co-author. `make ai-lint` / `make backend-lint` / `make frontend-lint`
   antes de commitear si se tocó código.

## Premisas del proyecto (hechos, no criterio)

Esto es lo que el sistema **es**. No se deduce del texto ni se reinventa en cada revisión: si la
memoria dice otra cosa, la memoria está mal. Cada una ha costado una corrección que tocaba varios
capítulos a la vez.

- **No hay VPS ni proveedor cloud.** El sistema se sirve desde la estación de trabajo de desarrollo
  (AMD Ryzen 9 7900X, NVIDIA RTX 4080), publicada en Internet con un túnel de Cloudflare, sin abrir
  puertos entrantes. Migrar a un servidor alojado o a cloud es trabajo futuro: hoy el coste no se
  justifica porque el prototipo no tiene usuarios. Cualquier mención a un VPS, a un proveedor
  concreto o a un coste mensual de hosting es residuo de una versión anterior.
- **La máquina que sirve es la que mide.** Los tiempos del capítulo de desarrollo no son una
  extrapolación a otro entorno. Y tiene GPU, de modo que **no vale argumentar que la atribución se
  desacopla porque el despliegue no tiene acelerador**: se desacopla para que el sistema siga
  respondiendo en modo CPU, que es un escenario soportado.
- **Latencia, separada por fuerza.** Proponer códigos y justificarlos son dos costes de orden
  distinto y el sistema los sirve en peticiones distintas. No se pueden resumir en una sola cifra:
  0,331 s y 16,2 s en CPU; 0,017 s y 0,51 s en GPU (`make ai-bench-predict`,
  `make ai-bench-explain`).
- **Las copias de seguridad cubren dos bases de datos**, la de la aplicación y la del registro de
  eventos (`make db-backup`). Residen en el mismo equipo que los datos, que es una limitación
  declarada, no un descuido que haya que ocultar.
- **La trazabilidad se cumple emitiendo un evento por predicción** con el identificador del informe,
  el motor y la versión del modelo (nombre del \emph{encoder} más hash del fichero de pesos). El
  canal escribe la tabla de lectura por su cuenta para poder emitir los códigos en el acto, así que
  el proyector de ese evento no materializa nada: es solo el registro auditable.
- **Un dato medido no se cita de memoria ni se adorna.** Si un párrafo dice «con calentamiento
  previo», «en hardware moderno» o «suficiente para el caso de uso», o se sustituye por la cifra y
  su guion, o se quita. Los adjetivos no son mediciones.

## Cómo revisar

### 1. Lectura crítica en paralelo
Lanza lectores concurrentes (Agent, `general-purpose`) sobre bloques distintos: `caps/Desarrollo.tex`;
`Resumen + Introduccion + Objetivo + Planificacion + Conclusiones`; `anexos/`. Pide a cada uno:
hallazgo → cita textual → por qué es problema → corrección propuesta → severidad.

**Siempre** incluye en el prompt los cambios masivos recientes (sed, reemplazos globales,
conversiones de listas), porque es donde se concentra el daño.

### 2. Verificación mecánica
Antes de fiarte de cualquier informe, comprueba tú los números.

```bash
# nº real de ejecuciones y mejor modelo
tail -n +2 ai_engine/model/training_runs.csv | grep -c .
tail -n +2 ai_engine/model/training_runs.csv | awk -F',' \
  '{split($0,a,","); for(i=1;i<=NF;i++)gsub(/^ +| +$/,"",$i); if($30=="1767") printf "%.4f run %d %s\n",$33,NR,a[1]}' \
  | sort -rn | head -3
# OJO: val_f1_micro es la columna 33, NO la 32 (la 32 es val_r_micro)
# OJO 2: nada de $1 suelto en los snippets de esta skill. Al invocarla con argumentos se
# sustituye por el primero y el comando cambia de significado sin dar error. Usar split().

# em-dashes en el PDF renderizado (la prueba definitiva)
# grep -o, no grep -c: -c cuenta lineas y dos em-dashes en la misma linea contarian como uno
pdftotext tfg/build/uclmTFGesi.pdf - | grep -o "—" | wc -l

# celdas de tabla rotas por reemplazos globales
grep -rn "&, \|&,$" tfg/caps/ tfg/anexos/

# caracteres Unicode que LaTeX no compone (menos, comillas raras…)
grep -rn "−" tfg/caps/ tfg/anexos/ tfg/preambulo/

# figuras y tablas nunca citadas en el texto
# Los labels se buscan tambien en figs/ y preambulo/: hay figuras generadas por guion que
# viven ahi, y si solo se barren caps/ y anexos/ quedan fuera del control sin avisar.
for l in $(grep -rhoE '\\label\{(fig|tab):[^}]+\}' tfg/caps/ tfg/anexos/ tfg/figs/ tfg/preambulo/ \
           | sed -E 's/\\label\{(.*)\}/\1/' | sort -u); do
  n=$(grep -rho "ref{$l}" tfg/caps/ tfg/anexos/ tfg/preambulo/ | wc -l)
  [ "$n" -eq 0 ] && echo "SIN CITAR: $l"
done
```

### 3. Compilación
```bash
make tfg-pdf; echo "exit: $?"
```
**Usa el código de salida de `make`, no `grep "^!"` sobre el log**: hay errores de LaTeX que generan
PDF igualmente y que ese grep no caza (le pasó a esta revisión con un U+2212).

## Trampas concretas ya encontradas

| Trampa | Cómo se detecta |
|---|---|
| Un `sed` global de `—` rompe celdas `& — \\` (quedan comas impresas) y corrompe bloques `verbatim` | `grep -rn "&, "` y revisar los `verbatim` que documenten contratos de API |
| Aposiciones `—X—` convertidas en comas dejan enumeraciones falsas y relativos colgando | Lectura humana; buscar frases con 4+ comas |
| Conteos que no cuadran: "tres desafíos" seguido de cuatro viñetas | Contar los `\item` / párrafos en negrita tras cada "N líneas/fases/retos" |
| Cifras que caducan: si se entrena más, el nº de ejecuciones y las horas de GPU quedan obsoletos | Recontar el CSV en cada revisión |
| Umbral ajustado sobre el propio conjunto de test (`best_f1` barriendo en test) | Revisar que el umbral salga de **validación** y se aplique a test |
| Métricas que no aplican: el MAP no depende del umbral; el F1 sí | No mezclar conclusiones entre ambas |
| Descripciones de códigos CIE-10 inventadas | Contrastar con `ai_engine/model/code_descriptions.json` |
| URLs/endpoints que dan 404 | Contrastar con `backend/lib/app_web/router.ex` y `ai_engine/main.py` |
| Tablas duplicadas y divergentes entre anexos | Dejar una sola y que la otra remita |
| Contenido que aparece en disco entre sesiones (anexos que crecen) | Releer antes de dar por buena una revisión previa |

## Señales de escritura con IA

Buscar y reescribir:
- Listas con dos puntos por todas partes, sobre todo tríadas vagas de sustantivos abstractos.
- Patrón "N + sustantivo + dos puntos + lista" repetido a lo largo del capítulo.
- Aperturas pomposas ("proceso crítico en la gestión sanitaria moderna").
- Calcos del inglés: "compromiso fundamental" (*trade-off*), "casi infalible", "advanced NLP".
- Superlativos sin respaldo: "el paso más directo", "extremadamente bajo", "viabilidad real de mercado".
- Repetición casi verbatim de un mismo párrafo en secciones distintas.
- Muletillas repetidas ("de un vistazo", "sin necesidad de", "queda identificado como candidato").

**Conservar** las listas que de verdad ayudan a leer (requisitos, entregables, enumeraciones con
etiqueta en negrita y contenido concreto). El objetivo es quitar andamiaje vacío, no empobrecer la
estructura.

## Análisis de datos: ¿está completo o queda algo en el tintero?

No basta con que las cifras publicadas sean correctas. Hay que comprobar que **el análisis que los
datos ya permiten hacer está hecho**, y que lo que se afirma sobre ellos es lo que se ha medido.

### 1. El modelo que se reporta ES el que está cargado
Las cifras titulares tienen que salir del artefacto que `config.json` carga de verdad, no de la
mejor ejecución del CSV. Esta deriva ya ha ocurrido tres veces.

```bash
# quién está realmente en producción vs. qué dice el TFG
cat ai_engine/model/config.json
grep -rn "20260530T030233Z\|paso~36\|modelo desplegado" tfg/anexos/AnexoH.tex
# el mejor run registrado, ¿tiene evaluación en test?
tail -n +2 ai_engine/model/training_runs.csv | awk -F',' '{split($0,a,","); if($30=="1767") printf "%.4f %s\n",$33,a[1]}' | sort -rn | head -3
ls ai_engine/model/eval_*.json
```
Si `config.json` apunta a un artefacto distinto del que reportan AnexoH/Desarrollo/Resumen, o si su
`threshold` no coincide, **es un hallazgo bloqueante**: o se reevalúa ese modelo en test y se
actualizan todas las cifras titulares, o se revierte `config.json` al modelo que documenta la memoria.
Un modelo desplegado sin evaluación en test no puede ser "el sistema que este trabajo presenta".

### 2. Toda comparación se hace a la misma granularidad
El diccionario se evalúa a bloque de 3 caracteres y el neuronal a código completo. **Poner ambas
cifras en el mismo documento sin una comparación homogénea invita al tribunal a leer que el baseline
gana.** Si el texto afirma que un componente aporta valor sobre otro, esa afirmación exige una
medición cara a cara en el mismo conjunto, la misma granularidad y la misma métrica. Afirmarlo por
argumento cualitativo ("no alcanza la comprensión semántica") no vale.

### 3. Lo que dice el pie de figura es lo que la figura muestra
Trampa recurrente: la figura enseña una cosa y el caption afirma una correlación que no está
representada. Antes de dar por buena una figura:
- ¿La variable que menciona el caption está en algún eje? (p. ej. "capítulos con más ejemplos de
  entrenamiento" exige frecuencia **de entrenamiento** en la figura; el `support` de `eval_test.json`
  es de **test**, no es lo mismo).
- ¿La correlación afirmada se ha calculado? Calcúlala. Con r≈0,4 no se escribe "se concentra en".
- ¿Hay categorías con soporte ridículo (n≤10) pintadas como barras a 0,00? Se anota el soporte en
  cada barra y se excluyen o se marcan en gris; si no, dos muestras sueltas parecen un fallo total.
- ¿Faltan categorías sin explicación? (capítulos III, VIII y XXII no aparecen: hay que decirlo).

### 4. Los outliers se explican o se caen
Cualquier categoría que rompa la narrativa del documento hay que nombrarla en el texto. Si el
capítulo VI tiene F1 0,03 con el mismo soporte que otro que saca 0,40, el tribunal lo va a preguntar.
Una frase de diagnóstico basta; el silencio no.

### 5. Los techos estructurales se convierten en cifra
Si los datos permiten calcular una cota, se calcula y se usa para contextualizar el resultado:

```bash
python3 -c "
import json; d=json.load(open('ai_engine/model/eval_test.json'))
ceil=d['gold_pairs_reachable']/d['gold_pairs_total']
r=d['test_at_best']['r_micro']
print('techo de recall por vocabulario: %.3f'%ceil)
print('recall obtenido: %.3f = %.1f%% del alcanzable'%(r,100*r/ceil))"
```
Decir "el 38 % de los códigos de test no se vio en entrenamiento" es correcto pero inerte. Decir
"el recall obtenido es el 55 % del máximo alcanzable con este vocabulario" sitúa el resultado.

### 6. Gráficas que el dato ya permite y suelen faltar
Revisar si existen; si no, proponerlas (no darlas por hechas):
- **F1 por frecuencia del código en entrenamiento** (buckets 1 / 2-5 / 6-20 / >20). Es la gráfica que
  demuestra el argumento de cola larga sobre el que descansa todo el documento. El histograma de
  frecuencias del corpus NO lo demuestra: enseña el desequilibrio, no su efecto en el rendimiento.
- **Curva precisión-recall**, no solo F1 frente a umbral: es lo estándar y justifica el punto de
  operación elegido.
- **Soporte junto al rendimiento** en cualquier desglose por categoría.
- **Cara a cara de los motores** a la misma granularidad (ver punto 2).

### 6b. Las cifras de la fase 1 NO están en `training_runs.csv`
Los experimentos de selección de modelo (clasificación de capítulos, 21 clases) viven en
`training/bert-classifier/*.ipynb`. El CSV solo tiene runs de **809 y 1767 clases** y arranca en
2026-03-18. Verificar ahí antes de dar por buena cualquier cifra de la comparativa de modelos:

```bash
for f in training/bert-classifier/*.ipynb; do
  echo "$(basename $f) -> $(grep -o 'F1 Micro: 0\.[0-9]*' "$f" | sed 's/.*: //' | sort -rn | head -1)"
done
```
Ojo: hay celdas copiadas entre notebooks (un mismo valor que aparece en tres ficheros distintos no es
el resultado de los tres modelos). Y **no mezclar tareas en una misma tabla**: si una fila se midió
sobre 809 bloques y otra sobre 21 capítulos, o se separan en columnas o la nota al pie va en **todas**
las tablas donde aparezcan, no solo en el anexo.

### 7. Análisis de error
Un TFG que reclama la competencia CO4 y no enseña **en qué se equivoca el modelo** tiene un hueco
visible. Mínimo: qué sobrepredice, qué subpredice, y si los fallos son códigos hermanos del correcto
(error de especificidad) o códigos de otro capítulo (error de comprensión). Son dos consultas sobre
predicciones que ya están calculadas.

### 7b. Las cifras de cobertura de pruebas se miden, no se afirman

Es el mismo error que con las métricas del modelo, pero pasa más desapercibido porque suena a
detalle de ingeniería y no a resultado. Cualquier frase del tipo «la suite cubre íntegramente la
lógica de negocio» o «cobertura completa o muy alta» hay que contrastarla:

```bash
# backend (excoveralls): imprime [TOTAL] al final
docker compose -f docker-compose.yml -f docker-compose.cpu.yml run --rm --no-deps \
  -e MIX_ENV=test backend mix coveralls | tail -3

# motor de IA (pytest-cov): ojo, el total del directorio mezcla el servicio con los
# guiones de un solo uso (bench_*, plot_*, eval_*, soup, merge_runs, augment*), que
# nunca se prueban. La cifra defendible es la de los módulos del servicio.
docker compose -f docker-compose.yml -f docker-compose.cpu.yml run --rm --no-deps ai_engine \
  sh -c "pip install -q -r requirements-dev.txt pytest-cov && cd /app && \
         python -m pytest tests/ -q --cov=. --cov-report=term --cov-config=/dev/null" | tail -25

# frontend (vitest + v8)
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps \
  frontend npx vitest run --coverage
```

Qué comprobar además del número:

- **El número de pruebas de la memoria coincide con el que sale al ejecutarlas.** Caduca cada
  vez que se añade un test, igual que el recuento de ejecuciones de entrenamiento.
- **Un `make test` que no arranca es peor que no tenerlo**, porque da sensación de cobertura sin
  darla. Si un target falla por entorno (falta `pytest`, falta `vitest`, un directorio de root
  bloquea la escritura), eso es un hallazgo, no un obstáculo para la revisión: los tests que
  nadie ejecuta llevan rotos desde hace commits.
- **Los módulos sin cobertura se nombran y se justifican.** «Los únicos módulos sin cobertura son
  aquellos para los que no tiene sentido» no vale sin la lista.
- **No mezclar cobertura de línea con cobertura de rama** al citar, ni el total del directorio con
  el de los módulos que de verdad se despliegan.

### 8. Una sola fuente por cifra
Cuando hay varios scripts de evaluación (`eval_test.py`, `ensemble_eval.py`, `rerank_map.py`), las
cifras divergen en la 3ª decimal y acaban mezcladas entre capítulos.

```bash
grep -rn "f1_micro\|map_strict" ai_engine/model/eval_*.json | head
```
Fijar de qué fichero sale cada cifra titular y que Resumen, Desarrollo, AnexoF y AnexoH usen la misma.
Si se mezclan a propósito, la salvedad va en los tres sitios, no solo en uno.

### 9. Nada declarado "pendiente" llega a la defensa
```bash
grep -rn "pendiente\|TODO\|por determinar\|n/d" tfg/caps/ tfg/anexos/
```
Contrastar con `training_runs.csv`: si el experimento ya se ejecutó, se rellena; si no se va a
ejecutar, se reescribe el párrafo sin la promesa.

## Reglas de redacción que hay que comprobar siempre

### 1. Nada se repite
Cada cosa se explica UNA vez, en el sitio que le corresponde, y el resto de apariciones remiten
con `\ref`. La redundancia es lo primero que un tribunal lee como relleno. Casos ya encontrados:
la definición completa de CQRS dos veces, el argumento de cola larga en cuatro sitios, la brecha
léxica del 38,3 % en tres.

Detección automática de frases casi idénticas entre ficheros:

```bash
python3 - <<'EOF'
import re, glob
from difflib import SequenceMatcher
frases=[]
for f in glob.glob('tfg/caps/*.tex')+glob.glob('tfg/anexos/*.tex')+glob.glob('tfg/preambulo/*.tex'):
    t=re.sub(r'%.*','',open(f,encoding='utf-8').read())
    t=re.sub(r'\\begin\{(verbatim|lstlisting|tabular)\}.*?\\end\{\1\}',' ',t,flags=re.S)
    t=re.sub(r'\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?',' ',t)
    t=re.sub(r'[{}$&\\~^_]',' ',t)
    for fr in re.split(r'(?<=[.:;])\s+',t):
        fr=' '.join(fr.split())
        if len(fr)>=110: frases.append((f.split('/')[-1],fr))
for i,(fa,a) in enumerate(frases):
    for fb,b in frases[i+1:]:
        if abs(len(a)-len(b))>len(a)*0.35: continue
        if SequenceMatcher(None,a[:400],b[:400]).ratio()>=0.80:
            print(f'{fa} <-> {fb}\n   {a[:150]}\n')
EOF
```

Ojo: tarda varios minutos sobre el documento completo. Lánzalo en segundo plano.

Y para conceptos concretos, contar apariciones:

```bash
for c in "cola larga" "CQRS" "brecha léxica" "38,3" "Event Sourcing" "pos_weight"; do
  echo "$c: $(grep -rio "$c" tfg/caps/ tfg/anexos/ | wc -l)"
done
```

### 2. Toda figura y toda tabla se citan en el texto
Una figura que nadie referencia es una figura que el tribunal no sabe por qué está. El comando
de figuras y tablas sin citar ya está más arriba, en «Verificación mecánica»: hay que ejecutarlo
en cada revisión, no solo cuando se añade algo.

Preferir la referencia entre paréntesis al final de una frase que ya existe
(`...los campos de la proyección (Tabla~\ref{tab:conversations})`) antes que escribir una frase
nueva. Si hay que escribirla, variar el arranque: repetir «La Tabla~X recoge...» veinte veces
canta tanto como no citarlas.

### 3. Todo dato lleva su fuente, y toda tabla dice con qué se genera
Ninguna cifra, afirmación técnica o dato de contexto aparece sin decir de dónde sale. Es la regla
que más veces se ha incumplido en este trabajo y la que más caro sale: el 0,601 atribuido a
ModernBERT era de otro modelo, el 0,121 de mmBERT era de otra tarea, el 0,799 de RigoBERTa estaba
escrito a mano en una celda de notas, y el 0,74 de RigoBERTa-2.0 era de un modelo que nunca se
entrenó. Ninguno se habría colado si cada cifra hubiera tenido que declarar su origen.

- **Cada tabla de datos dice en su `\caption` o en su pie con qué se genera**: el comando
  (`make ai-eval-test`, `make ai-bench-explain`, `make ai-error-analysis`), el guion
  (`ai_engine/eval_test.py`, `rerank_map.py`, `bench_explain.py`) y, si procede, el fichero de
  salida (`model/eval_test.json`, `model/error_analysis.json`, `model/fusion_sweep.json`).
  Quien lea la memoria tiene que poder regenerar el número sin preguntar.
- **Las cifras de los cuadernos** van con el cuaderno concreto y cómo se ejecuta
  (`papermill --log-output cuaderno.ipynb salida.ipynb`), no con un "se midió".
- **Datos ajenos**: cita bibliográfica. Si se menciona una herramienta o un método que se ha
  usado de verdad (Optuna, FlashAttention, SmoothGrad), lleva su `\cite`.
- **Nada de memoria ni de notas sueltas**: una cifra escrita a mano en una celda de markdown no
  es una medición. Si no se puede rastrear hasta la salida de un programa, se reformula, se
  vuelve a medir o se quita.

```bash
# Tablas cuyo entorno no menciona ningún guion ni comando: candidatas a revisar
for l in $(grep -rhoE '\\label\{tab:[^}]+\}' tfg/caps/ tfg/anexos/ | sed -E 's/.*\{(.*)\}/\1/'); do
  f=$(grep -rl "label{$l}" tfg/caps/ tfg/anexos/ | head -1)
  n=$(grep -n "label{$l}" "$f" | cut -d: -f1)
  c=$(sed -n "$((n-14)),$((n+14))p" "$f" | grep -coE "make [a-z-]+|\.py|\.ipynb|\.json|\.csv")
  [ "$c" -eq 0 ] && echo "SIN FUENTE: $l ($f)"
done
```

```bash
# Cifras sueltas en el texto sin \ref ni \cite cerca: candidatas a revisar a mano
grep -rnoE "[^0-9]0[,.][0-9]{3}[^0-9]" tfg/caps/*.tex | head -40
```

**Barrido completo de valores numéricos.** Lo anterior mira capítulos y solo decimales del tipo
`0,xxx`. Cuando se promociona un modelo, se reevalúa algo o se rehace una medición, hay que barrer
**todas** las cifras del documento y comprobar una por una contra su fuente: lo que se cuela no es
la cifra que se cambia, sino la copia de esa cifra que vivía en otro capítulo y nadie recordaba.

```bash
# Toda cifra decimal del documento, agrupada por valor, con dónde aparece.
# Dos apariciones del mismo número en ficheros distintos son la señal a mirar: o es la misma
# medición (y entonces solo una debe ser la fuente) o son dos cosas distintas que coinciden.
grep -rnoE "[0-9]+\{?,\}?[.,][0-9]+" tfg/caps/ tfg/anexos/ tfg/preambulo/ \
  | sed 's/{,}/,/' | awk -F: '{print $3"\t"$1":"$2}' | sort | uniq -c | sort -rn | head -60
```

Después, para cada cifra titular, comprobar que **todas** sus apariciones dicen lo mismo:

```bash
for n in 0,437 0,545 0,489 0,109; do
  echo "## $n"; grep -rn -- "$n" tfg/caps/ tfg/anexos/ tfg/preambulo/ | sed 's/{,}/,/' | cut -c1-120
done
```

Ojo con dos trampas propias de este documento: las cifras del diario de experimentos
(`anexos/AnexoF.tex`) son **históricas** y no se actualizan al promocionar un modelo, porque
registran lo que midió cada paso; y el mismo modelo aparece con dos valores según la pasada de
evaluación (precisión completa frente a comparable), de modo que una discrepancia en la tercera
decimal puede ser correcta y hay que declararla, no corregirla.

### 4. Tono académico
El TFG no es un blog ni un pitch. Fuera:

- Lenguaje comercial: «modelo de suscripción», «ajustar el precio al valor generado»,
  «AI-as-a-Service», «umbral de rentabilidad extremadamente bajo».
- Entusiasmo sin respaldo: «casi infalible», «extremadamente», «el paso más directo»,
  «viabilidad real de mercado».
- Comparaciones tramposas: contraponer la latencia de inferencia (0,331 s) al acto completo
  de codificar un alta (14 minutos) no es una comparación, es un titular: el sistema propone
  candidatos, no cierra el alta.

Lo que sí va: qué se midió, cómo, con qué resultado y qué limitación tiene.

### 5. El trabajo lo firma una persona
No hay equipo. Nada de «nuestro equipo de desarrollo», «el grupo de trabajo» ni plurales que
sugieran varias personas. Cuidado con «equipo de desarrollo»: en este proyecto significa **la
máquina** (RTX 4080 / Ryzen 9 7900X), no un grupo. Si aparece, o se escribe «la máquina de
desarrollo» o se acompaña del hardware entre paréntesis, que ya desambigua.

```bash
grep -rnoE "\b(nuestro equipo|nuestros? (desarrolladores|ingenieros)|el grupo de trabajo|el equipo de desarrollo)\b" tfg/caps/ tfg/anexos/ tfg/preambulo/
```

### 6. Anglicismos: lista cerrada, y se comprueba
El texto va en español de España formal. La distinción no es "traducir todo" ni "dejarlo todo":
hay términos consolidados en el campo que se quedan, y anglicismos innecesarios que tienen
equivalente natural y se traducen.

**Se quedan en inglés** (con `\emph{}` cuando procede): `batch`, `batch size`, `mini-batch`,
`pretrain`, `mock`, `benchmark`, `snippet`, `endpoint`, `pipeline`, `encoder`, `ranking`,
`em-dash` (el signo, para no confundirlo con el guion ni con la raya), `feature toggle`
(nombre del patrón en la bibliografía), `wheel` (el paquete precompilado de
Python, nunca "rueda"), `Workflow de GitHub Actions` (nombre oficial del producto).

**Se traducen siempre:**

| Inglés | Español |
|---|---|
| run / runs | ejecución / ejecuciones |
| feedback | retroalimentación |
| dataset | corpus |
| polling | sondeo periódico |
| trade-off | compromiso |
| log de eventos | registro de eventos |
| chars | caracteres |
| free tier | nivel gratuito |
| flag (sustantivo) | opción, parámetro |
| toggle (suelto) | selector |
| Payload (cabecera de tabla) | Datos |
| Best época | Mejor época |
| progressive unfreezing | descongelado progresivo |
| static analysis | análisis estático |

```bash
grep -rnoiE "\b(runs?|feedback|dataset|polling|trade-?off|chars|free tier|toggle|payload|progressive unfreezing|static analysis)\b" tfg/caps/ tfg/anexos/ tfg/preambulo/ | grep -v "feature toggle"
```

Ojo con los falsos positivos: `run` aparece dentro de nombres de fichero y de rutas
(`training_runs.csv`, `runs/zlpr_map/`), y ahí no se toca. Lo que se corrige es la prosa.

Y ojo con las mezclas, que son lo peor de los dos mundos: «Best época», «corridas» por
ejecuciones, «el toggle» por el selector.

### 7. Los títulos de sección no se tocan
Los fija la plantilla de la UCLM. Se puede **añadir** una subsección nueva; no se renombra ni se
reorganiza ninguna de las que ya están, a ningún nivel. Si el contenido de una sección no encaja
con su título, se arregla el contenido.

## Coherencia de fondo (lo que más pesa en una defensa)

Revisar siempre que:
- Lo que promete el capítulo de **Objetivo** coincide con lo que declaran las **Conclusiones**
  (títulos de subobjetivos literalmente iguales, mismo orden).
- Todo **requisito** (RF/RNF) tiene verificación explícita, incluidos los incumplidos.
- Las **limitaciones estructurales** están declaradas (cobertura del vocabulario, fugas de datos
  entre particiones, ausencia de evaluación de algún módulo).
- Las **cifras titulares** son idénticas en Resumen ES, Abstract EN, Desarrollo, Conclusiones y anexos.
- Ninguna afirmación absoluta ("ningún algoritmo puede…") que el propio documento contradiga.

## La skill se revisa a sí misma

Antes de dar una revisión por terminada, repasa **este mismo fichero** con el mismo criterio que
aplicas al TFG: erratas, faltas de ortografía y errores semánticos. Una skill con un comando roto
o una regla que se contradice hace más daño que no tenerla, porque la revisión pasa igual y el
fallo se da por comprobado.

Qué mirar, con los casos que ya han aparecido:

- **Ortografía y tildes**, incluidas las que están dentro de las reglas y no solo en la prosa
  («ultimo», «estan», «fusion», «ningun» llegaron a convivir con reglas que exigen rigor).
- **Los comandos hacen lo que dice el comentario que hacen.** Ejecútalos. `grep -c` cuenta
  *líneas*, no ocurrencias, de modo que dos em-dashes en el mismo renglón contaban como uno.
- **Los barridos cubren todo el árbol que dicen cubrir.** El de figuras sin citar solo miraba
  `caps/` y `anexos/`, y se dejaba fuera las figuras generadas por guion que viven en `figs/`.
- **Nada de `$1` suelto en los snippets.** Al invocar la skill con argumentos se sustituye por el
  primero y el comando cambia de significado sin dar error. Usar `split()` en `awk`.
- **Las referencias cruzadas entre secciones siguen siendo ciertas.** Si una sección dice «regla 4
  aplicada al pie de la letra» y la regla 4 se ha reescrito, la referencia miente.
- **Las cifras de ejemplo de la propia skill caducan** igual que las del TFG. Si un ejemplo cita
  una latencia o un MAP, tiene que ser el vigente.
- **La lista cerrada de anglicismos incluye los que la propia skill usa.** Si el texto dice
  «em-dash» treinta veces, «em-dash» va en la lista.

## Al terminar

1. Recompilar y confirmar `make tfg-pdf` → exit 0, 0 errores, 0 referencias sin definir,
   0 overfull, 0 em-dashes.
2. Revisar visualmente las páginas con figuras y tablas nuevas (`pdftoppm -f N -l N -r 100 -png`).
3. Volcar en `ROADMAP.md` lo aplicado y lo que queda pendiente, separando lo objetivo de lo que
   requiere decisión del autor.
4. Presentar los hallazgos separando: errores reales / cuestiones de criterio / cosmético, y
   **preguntar antes de tocar** lo que cambie el discurso del trabajo (titulares, alcance, tono).
5. Repasar esta skill buscando erratas, faltas y errores semánticos, y ejecutar sus comandos para
   confirmar que siguen haciendo lo que dicen.
