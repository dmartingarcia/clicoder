# Reglas del repositorio

## Tests e2e

- Todo test e2e saca capturas de pantalla y las conserva como artefacto, no solo cuando falla.
- `e2e/conftest.py` captura al final de cada test (`e2e/screenshots/<test>-ok.png` o `-fallo.png`) y la CI las sube (job `e2e`, artefacto `e2e-screenshots`).
- Los guiones de `demo/guiones/` hacen lo mismo: una captura por paso clave en `demo/out/screenshots/<video>/`.
