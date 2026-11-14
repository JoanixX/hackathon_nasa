# Alcance, contratos y validación de NiñoRadar

Este documento traduce el contexto del equipo en criterios de trabajo. No acredita implementación ni adopta todavía una arquitectura. Fecha de preparación: 14 de noviembre de 2026.

## Usuarios y tarea principal

Usuarios potenciales: municipalidades, gobiernos regionales, instituciones de gestión del riesgo, equipos humanitarios, investigadores y comunidades. Para el diseño inicial se propone validar la tarea de un analista territorial municipal: comparar fechas, comprender exposición y seleccionar sectores para verificación. El rol y sus necesidades requieren entrevistas; no se afirma que el equipo ya las haya realizado.

## Prioridades

| Prioridad | Trabajo | Evidencia necesaria |
| --- | --- | --- |
| P0: MVP | Catacaos/Cura Mori, comparación SAR, exposición vial/agrícola, panel e incertidumbre | Datos comparables, metodología y procedencia visibles |
| P1: después del núcleo | Exportaciones, accesibilidad reforzada, muestras de validación, mejores estados de baja conectividad | Uso probado y límites documentados |
| P2: investigación | Tumbes/Rímac, pronósticos, reportes de campo, sincronización, AR y gemelos digitales | Caso de uso, datos, coste y validación propios |

La prioridad de una idea no prueba su viabilidad. No se implementará ahora ninguno de estos componentes como parte del setup.

## Recorrido mínimo a demostrar después

1. Elegir área de estudio y dos observaciones, con misión, fecha y cobertura visibles.
2. Comprobar comparabilidad; si falla, explicar el motivo y no generar una comparación engañosa.
3. Mostrar agua de referencia, cambios detectados y zonas sin datos o excluidas, sin confundirlas.
4. Activar infraestructura y consultar qué elementos intersectan la detección.
5. Seleccionar un sector y ver indicadores, evidencia, limitaciones y razón de prioridad.

## Contrato mínimo propuesto para los datos

El esquema final se resolverá en investigación de arquitectura. Debe preservar al menos:

- Identificación: ID de observación/producto, proveedor, misión, colección, nivel y versión.
- Tiempo: adquisición, publicación si existe, ingesta y procesamiento en UTC; presentación en hora de Perú con zona horaria explícita. Una fecha desconocida se representa como desconocida.
- Geometría: área de estudio, CRS, resolución, extensión, unidad, nodata, máscaras de calidad y cobertura válida.
- Método: versión del algoritmo, parámetros, entradas, comparabilidad y advertencias.
- Resultado: máscara/clases y estados de calidad; confianza numérica solo cuando se pueda justificar su significado y calibración.
- Procedencia: URL, licencia/condiciones, atribución y checksum cuando corresponda.
- Exposición: ID de cada elemento, capa y fecha, tipo de intersección, área/longitud calculada y vínculo con el análisis que la produjo.

No agregar coordenadas de límites distritales inventadas. Obtener límites de una fuente cartográfica y comprobar CRS/UBIGEO. No calcular hectáreas o longitudes directamente en grados.

## Criterios de aceptación del futuro MVP

| ID | Criterio | Verificación esperada |
| --- | --- | --- |
| MVP-01 | Piloto delimitado a Catacaos y Cura Mori | Fuente y geometría del área documentadas |
| MVP-02 | Comparación de observaciones válidas | Registro de misión, producto, fechas, geometría y versión |
| MVP-03 | Separación entre agua, cambio y falta de observación | Leyenda y casos de nodata, exclusión y agua permanente |
| MVP-04 | Exposición reproducible | Revisar intersecciones y evitar doble conteo de geometrías |
| MVP-05 | Unidades correctas | Área y longitud con CRS métrico adecuado o cálculo geodésico validado |
| MVP-06 | Comunicación responsable | Fechas, fuente, incertidumbre y lenguaje de afectación potencial visibles |
| MVP-07 | Fallos comprensibles | Casos sin pareja, sin cobertura, proveedor caído y datos parciales |
| MVP-08 | Demo honesta | Cada recurso indica real, histórico o simulado; misión correctamente rotulada |
| MVP-09 | Reproducibilidad | Entradas, parámetros y versiones permiten regenerar un resultado |
| MVP-10 | Interacción accesible | Navegación por teclado, contraste y alternativa textual al mapa |

## Validación científica pendiente

Comparar un método base con referencias independientes y contemporáneas cuando existan. Reportar precision, recall, F1 e IoU con definición de clases, tamaño de muestra, fechas y limitaciones. Separar datos de ajuste y evaluación por fecha/espacio para evitar fuga de información. No fijar un porcentaje de precisión como hecho ni reutilizar la propia máscara como referencia independiente.

Investigar falsos positivos/negativos en arrozales, suelos húmedos, agua permanente, zonas urbanas, vegetación, sombra radar y geometría de adquisición. Una inundación histórica anterior a NISAR no puede atribuirse a observaciones de esa misión. Sentinel-1 puede apoyar metodología histórica, con identificación explícita de la misión.

Cruzar una máscara con una vía no verifica accesibilidad; cruzarla con viviendas no confirma ocupación o daño. La priorización debe exponer reglas e incertidumbre; no equivaldrá a un índice clínico, probabilidad de muerte o instrucción de rescate.

## Rendimiento y operación pendientes

La investigación deberá proponer objetivos medibles para consulta, carga del mapa y procesamiento por separado, siempre acompañados de volumen de datos, concurrencia, hardware/red, caché fría/caliente y percentiles. Todavía no existen SLA, pruebas de carga ni infraestructura desplegada.

El procesamiento SAR pesado deberá evaluarse como trabajo asíncrono; una respuesta rápida de la interfaz no hace reciente la observación. Separar frecuencia orbital, latencia de publicación, tiempo de procesamiento y tiempo de respuesta de la aplicación.

## Riesgos y decisiones abiertas

| Riesgo/decisión | Acción de investigación | Resultado si no se resuelve |
| --- | --- | --- |
| Sin pareja NISAR comparable | Consultar catálogo y verificar escena/producto | Declarar limitación; demo histórica de otra misión o simulación rotulada |
| Cartografía incompleta/desactualizada | Revisar cobertura, licencia y muestreo local | Limitar métricas a cobertura conocida |
| Sin referencia independiente | Buscar producto contemporáneo o interpretación experta | Presentar estudio exploratorio, sin precisión operacional |
| Dependencia de APIs sin acceso | Ensayar acceso autorizado y formatos reales | Importación manual trazable; integración automática pendiente |
| UI/3D más precisa que los datos | Comparar escala visual y resolución de origen | Restringir visualización y explicar incertidumbre |
| Coste y equipo sin definir | Medir recorte pequeño y estimar escenarios | Priorizar arquitectura simple y artefactos precalculados |

AR, gemelos digitales, predicción, despacho de brigadas y alertas externas requieren investigación adicional. No son requisitos para dar por terminado el núcleo del prototipo.
