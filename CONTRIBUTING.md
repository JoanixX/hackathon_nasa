# Cómo trabajar en NiñoRadar

## Leer antes de cambiar

Revisar `README.md`, `docs/CONTEXTO_FUENTE.md`, `docs/ALCANCE_Y_VALIDACION.md` y `docs/FUENTES_Y_DECISIONES.md`. El texto adjunto define el alcance; el Google Docs es complementario. Registrar qué es requisito, propuesta, hipótesis o resultado verificado.

## Un commit por archivo

Por instrucción del propietario, **cada commit nuevo debe cambiar exactamente un archivo versionado**, incluso cuando varios archivos correspondan a la misma tarea. No agruparlos en un commit ni hacer squash de varios archivos. Usar mensajes que expliquen el cambio.

Ejemplo para cambios futuros, ejecutando y revisando cada paso:

```powershell
git add -- README.md
git diff --cached --name-only
git diff --cached
git commit -m "docs: actualizar contexto de NiñoRadar"
```

Antes de confirmar, `git diff --cached --name-only` debe mostrar solo el archivo previsto. Repetir el proceso para cada archivo. Evitar `git add .` y `git commit -a`. Las renombradas deben revisarse expresamente por cómo Git representa el cambio. No alterar commits publicados para reorganizar el historial.

La excepción son los archivos ignorados: no llevan commit. `prompts/` permanece exclusivamente en local; nunca usar `git add -f` para publicarlo. Comprobarlo con `git check-ignore -v prompts/01_logica_y_refactor_visual.md`.

## Investigación y documentación

- Preferir documentación oficial y papers para hechos técnicos. Incluir URL, fecha de consulta, producto/versión y evidencia concreta.
- Marcar como pendiente todo acceso, descarga, prueba o benchmark que no se haya ejecutado.
- Registrar decisiones con alternativas, motivos, coste, límites y condición de revisión.
- No ampliar territorio ni capacidades del MVP porque aparezcan como ideas futuras en otra fuente.
- Mantener coherentes documentación, nombres de campos, unidades y etiquetas visibles.

## Datos y secretos

No versionar credenciales, archivos `.env`, tokens Earthdata, datos personales de brigadas ni escenas/rasters grandes. Los directorios `data/`, `outputs/`, `artifacts/` y `.local/` están ignorados. Guardar en documentación metadatos, enlaces de descarga, checksum y licencia, cuando estén disponibles. Redistribuir muestras solo con derechos comprobados.

## Validación proporcional

Para documentación: comprobar enlaces internos, términos, coherencia y ausencia de afirmaciones de implementación no verificadas. Para código futuro: ejecutar los checks existentes y pruebas relevantes de ciencia, geometría, contratos, accesibilidad o errores según el cambio. No presentar un build exitoso como validación científica.

Antes de publicar: revisar `git status`, el archivo de cada commit y que no se incluya `prompts/`. Hacer push sin `--force` y comprobar que la rama remota coincide con el resultado esperado.
