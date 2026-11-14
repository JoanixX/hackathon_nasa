# Fuentes, precedencia y decisiones de preparación

## Registro de fuentes

| ID | Fuente | Uso | Estado |
| --- | --- | --- | --- |
| F1 | Adjunto del usuario: `Texto pegado.txt`, título NiñoRadar | Fuente principal del producto, piloto y límites | Copiado íntegramente en `CONTEXTO_FUENTE.md`; recibido el 14/11/2026 |
| F2 | [Hackathon NASA 404 Gravity, pestaña joaquin](https://docs.google.com/document/d/10_RmLBz5asZoEUewSKRS8kkQ9_lA0bDfm1piiPGLaHs/edit?tab=t.flskznlxd0bg) | Investigación complementaria | Leído mediante conector Google Docs el 14/11/2026; el texto declara actualización al 12/11/2026 |
| F3 | Documentación oficial de misiones, proveedores y herramientas | Verificación técnica posterior | Enlaces de partida; no se probaron descargas, APIs ni cobertura en este setup |

F1 tiene prioridad para los objetivos del proyecto. F2 contiene hipótesis, propuestas y afirmaciones técnicas que deben verificarse en fuentes primarias antes de adoptarlas. Ante una contradicción científica, documentar la evidencia y proponer un ajuste al equipo; la precedencia del producto no autoriza a presentar una falsedad técnica.

Se inspeccionaron las cuatro pestañas del Google Docs: notas iniciales, `joaquin` (pestaña enlazada), una pestaña con el texto de NiñoRadar y una pestaña vacía. No se copió el documento completo: se conserva un resumen de lo pertinente y su enlace.

## Conciliación entre F1 y F2

| Tema | Texto principal F1 | Complemento F2 | Decisión de preparación |
| --- | --- | --- | --- |
| Territorio | Catacaos y Cura Mori, Piura | Costa de Piura y Tumbes, un caso por departamento | Mantener el piloto de F1; Tumbes como investigación futura |
| Usuario | Municipios, gestión del riesgo, humanitarios, investigadores/comunidades | Operadores COER/COEL y brigadistas | Considerarlos para entrevistas; no declarar validación de esos roles |
| Núcleo | Cambios de agua, exposición, priorización | Pronóstico + SAR + verificación de campo | Priorizar tres capacidades de F1 |
| Coordinación | Apoyo a verificaciones | Asignar, registrar acuse y conciliar reportes | Futuro opcional, no requisito del MVP |
| Datos | NISAR si hay pareja comparable; Sentinel-1 histórico identificado | GCOV, Earthdata/ASF, SENAMHI, GPM, MTC, INEI, otros | Usar como rutas de investigación, sin afirmar acceso probado |
| Alertas | Complementa sistemas oficiales | Canales de aviso oficial, análisis y reporte de campo | Sin alertas externas ni despacho en el setup o núcleo inicial |
| Visualización | Mapas y panel | Reproducción temporal y ficha con evidencia | Evaluar UX sin cambiar el alcance científico |
| AR y gemelo digital | No definidos | No son requisito central | Investigación solicitada por el usuario; extensión experimental |
| Validación | Incertidumbre y fecha | Métricas independientes, control espacial/temporal | Incorporar como criterios futuros, sin inventar resultados |

## Aportes complementarios útiles

- Separar observación, pronóstico y reporte de campo; conservar tiempos y procedencia de cada uno.
- Distinguir adquisición, publicación, ingesta y procesamiento. Consultar más rápido no produce nuevas adquisiciones.
- NISAR debe aportar una capa analítica, no únicamente un fondo visual.
- Comprobar geometría, polarización, versión, resolución y calidad antes de comparar escenas.
- Conservar originales, normalizaciones y productos derivados, con trazabilidad.
- Comparar con soluciones existentes sin afirmar que NiñoRadar es el primer mapa de inundaciones o el primer cruce de exposición.
- Validar conectividad y tareas con usuarios antes de diseñar sincronización de brigadas o notificaciones.
- Separar utilidad de la interfaz, validez científica y rendimiento técnico.

Las cifras concretas de latencia, disponibilidad de productos, frecuencia y madurez mencionadas por F2 no se adoptan como garantías. Deben reconsultarse y asociarse a un producto/versión y fecha. Tampoco se trasladan cifras de antecedentes históricos sin revisar su fuente y período.

## Enlaces de partida extraídos del documento complementario

Estos enlaces fueron recuperados de F2. Su presencia no prueba que el servicio esté accesible, permita automatización, cubra el piloto o tenga licencia apta. No constituyen un catálogo de datos ya descargados.

| Fuente primaria o portal | Para qué revisarlo |
| --- | --- |
| [NASA: misión NISAR](https://science.nasa.gov/mission/nisar/mission-overview/) | Misión, observación y restricciones físicas |
| [ASF: disponibilidad NISAR](https://nisar-docs.asf.alaska.edu/availability-overview/) | Colecciones, madurez y acceso actuales |
| [ASF: productos NISAR](https://nisar-docs.asf.alaska.edu/products-overview/) | Nivel, formato, variables y calidad |
| [ASF: respuesta urgente](https://nisar-docs.asf.alaska.edu/urgent-response/) | Restricciones de acceso y diferencias de producto |
| [NASA Earthdata Search](https://search.earthdata.nasa.gov/) | Búsqueda de escenas y registro de metadatos |
| [SENAMHI: monitoreo](https://www.senamhi.gob.pe/servicios/main.php?p=monitoreo-informacion-diaria) | Contexto hidrológico y antigüedad de datos |
| [SENAMHI: geoservicios IDESEP](https://idesep.senamhi.gob.pe/portalidesep/idesep_componente_catalogo_geoservicios.jsp) | Servicios y formatos disponibles |
| [SENAMHI: observación de inundaciones](https://web2.senamhi.gob.pe/?p=observacion-de-inundaciones) | Productos e iniciativas existentes |
| [CENEPRED: SIGRID Collect](https://sigrid.cenepred.gob.pe/sigridv3/sigrid-collect) | Referente de información territorial y campo |
| [INEI: infraestructura de datos espaciales](https://ide.inei.gob.pe/) | Cartografía, límites y escala de información |
| [MTC: datos abiertos de emergencias viales](https://www.datosabiertos.gob.pe/dataset/emergencias-en-la-red-vial-nacional-ministerio-de-transportes-y-comunicaciones-%E2%80%93-mtc-0) | Estados reportados, diccionario y fecha de corte |
| [Copernicus EMSR199](https://mapping.emergency.copernicus.eu/activations/EMSR199/) | Referente histórico Perú 2017; otra misión y período |
| [Copernicus GloFAS](https://global-flood.emergency.copernicus.eu/general-information/about-glofas) | Distinguir pronóstico de observación |

El nombre `SERVIR-NKH` de las notas iniciales aparece discutido en F2 como posible referencia a SERVIR-HKH. No asumir equivalencia ni cobertura peruana sin verificar.

## Decisiones vigentes del setup

1. Repositorio privado `JoanixX/hackathon_nasa`; descripción relacionada con NASA Space Apps y NiñoRadar.
2. Solo contexto y preparación: no se eligió stack, no se construyó la aplicación y no se descargaron escenas.
3. Tres prompts autocontenidos en `prompts/`, excluidos de Git. No se publica su contenido ni se fuerza su inclusión.
4. Un archivo versionado por commit, a partir de este setup.
5. No se asignó licencia de código ni se asumieron permisos de redistribución de datos.

## Preguntas que resolverán las investigaciones

- ¿Existe una pareja NISAR comparable y útil sobre el piloto? ¿Qué producto y versión convienen?
- ¿Qué referencia independiente permite evaluar cambios de agua y con qué limitaciones?
- ¿Qué cartografía permite medir exposición vial y agrícola sin sobredimensionar cobertura?
- ¿Qué arquitectura mínima puede demostrar el flujo con tiempos medidos y fallos controlados?
- ¿Qué decisiones necesitan los usuarios y cómo interpretan fechas, incertidumbre y exposición?
- ¿Aportan valor demostrable AR o un gemelo digital frente a una visualización 2D accesible?
