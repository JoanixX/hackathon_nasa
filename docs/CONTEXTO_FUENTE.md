# NiñoRadar
### Inteligencia satelital para comprender el impacto de las inundaciones

**Challenge:** Dancing with the SARs — NASA Space Apps Challenge 2026

**Área de aplicación:** Gestión del riesgo de desastres, observación de la Tierra e inteligencia geoespacial.

**Zona piloto:** Catacaos y Cura Mori, Piura, Perú.

**Tecnología principal:** Radar de Apertura Sintética (SAR) de la misión NISAR (NASA–ISRO).

---

## 1. Problemática

El Perú es altamente vulnerable a los efectos de las lluvias extremas asociadas al fenómeno de El Niño Costero, especialmente en regiones como Piura, donde el desbordamiento de los ríos y las inundaciones pueden afectar viviendas, carreteras, terrenos agrícolas y servicios esenciales.

Durante estos eventos, uno de los principales desafíos es conocer con precisión **cómo se extiende una inundación, qué sectores del territorio están siendo afectados y cuáles requieren una evaluación prioritaria**.

Si bien el Perú dispone de sistemas de monitoreo hidrológico, mapas de riesgo y mecanismos de reporte de emergencias, la información se encuentra distribuida entre diferentes plataformas y no siempre permite visualizar conjuntamente los cambios observados en el terreno y la infraestructura potencialmente expuesta.

Además, la nubosidad intensa durante las lluvias dificulta el uso de imágenes satelitales ópticas para evaluar las condiciones de la superficie.

Esto plantea una necesidad concreta: **transformar observaciones satelitales de la superficie terrestre en información geoespacial accesible y útil para apoyar la evaluación de inundaciones**.

## 2. Nuestra solución

**NiñoRadar** es una plataforma web interactiva que utiliza imágenes de radar de apertura sintética de la misión NISAR para detectar cambios en la extensión del agua superficial, monitorear la evolución de las inundaciones y analizar su posible impacto sobre infraestructura y comunidades.

A diferencia de los satélites ópticos convencionales, NISAR puede observar la superficie terrestre de día o de noche y a través de la nubosidad, lo que resulta especialmente valioso durante episodios de lluvias intensas.

Mediante el análisis de imágenes obtenidas en diferentes fechas, NiñoRadar identifica superficies donde aparecen nuevas acumulaciones de agua y las integra con información geográfica sobre carreteras, centros poblados y terrenos agrícolas.

La plataforma transforma estos resultados en mapas interactivos e indicadores territoriales que permiten responder tres preguntas fundamentales:

1. **¿Dónde se ha extendido el agua?** Identificar áreas con cambios compatibles con inundación respecto de condiciones anteriores.
2. **¿Qué podría estar siendo afectado?** Estimar qué carreteras, edificaciones y terrenos agrícolas se encuentran dentro de las áreas detectadas.
3. **¿Dónde conviene priorizar la evaluación?** Identificar sectores con mayor concentración de infraestructura potencialmente expuesta para apoyar las verificaciones en campo.

De esta manera, NiñoRadar busca convertir datos científicos complejos en información comprensible y útil para quienes participan en la gestión del riesgo de desastres.

## 3. ¿Cómo funciona NiñoRadar?

La plataforma se organiza en cuatro etapas:

**Etapa 1. Observación satelital**

Se obtienen imágenes SAR de la misión NISAR correspondientes a distintas fechas sobre una misma región de estudio.

**Etapa 2. Detección de cambios**

Mediante procesamiento de imágenes radar, se identifican variaciones en la señal de retrodispersión que pueden indicar la aparición o expansión de cuerpos de agua.

Se aplican filtros y métodos de clasificación para producir mapas preliminares de inundación.

**Etapa 3. Análisis territorial**

Las superficies inundadas detectadas se cruzan con capas geográficas de infraestructura, carreteras y uso del suelo para estimar posibles afectaciones.

También se analizan las conexiones viales que podrían encontrarse interrumpidas, con el fin de identificar localidades que requieren una revisión de accesibilidad.

**Etapa 4. Visualización y apoyo a decisiones**

Los resultados se muestran en una aplicación web interactiva que permite comparar fechas, visualizar áreas afectadas y generar reportes geoespaciales para apoyar la evaluación territorial.

## 4. Propuesta de innovación

El principal valor de NiñoRadar no reside únicamente en detectar superficies inundadas, una aplicación que ya existe en el campo de la teledetección SAR.

**Nuestra propuesta consiste en conectar la observación satelital con el análisis de exposición territorial y la priorización de evaluaciones en campo.**

Mientras los sistemas hidrometeorológicos permiten conocer la evolución de las lluvias y de los ríos, NiñoRadar busca complementar esa información mostrando dónde ha cambiado la superficie terrestre y qué infraestructura coincide espacialmente con esos cambios.

Su diferenciación se concentra en tres capacidades:

- **Observación a través de las nubes:** utilizar SAR para analizar superficies durante condiciones meteorológicas que limitan las imágenes ópticas.
- **Análisis de impacto territorial:** transformar mapas de agua en estimaciones cuantificables de infraestructura y terrenos agrícolas potencialmente expuestos.
- **Priorización geoespacial:** identificar sectores donde la exposición detectada justifica una verificación más urgente, incorporando indicadores de calidad e incertidumbre.

La solución no pretende reemplazar los sistemas oficiales de alertas o evaluación de daños, sino complementarlos mediante información derivada de observaciones satelitales.

## 5. Caso de estudio: Piura, Perú

El proyecto se desarrollará inicialmente en los distritos de Catacaos y Cura Mori, ubicados en la región Piura, territorios afectados históricamente por inundaciones asociadas a lluvias extraordinarias.

La región constituye un caso de estudio relevante debido a la presencia de zonas urbanas, agrícolas y redes de transporte expuestas a las crecidas del río Piura.

El prototipo permitirá analizar cómo cambia la extensión del agua entre observaciones satelitales y cómo estos cambios se superponen con elementos del territorio.

Posteriormente, la metodología podría adaptarse a otras regiones vulnerables del Perú, como sectores de la cuenca del río Rímac en Lima, siempre que existan observaciones SAR adecuadas.

## 6. Beneficiarios

Los principales usuarios potenciales son:

- **Municipalidades y gobiernos regionales:** para apoyar la identificación de sectores que requieren evaluación.
- **Instituciones de gestión del riesgo:** como INDECI y CENEPRED, como fuente complementaria de información geoespacial.
- **Equipos de respuesta humanitaria:** para conocer posibles afectaciones en vías de acceso y asentamientos.
- **Investigadores y comunidades:** para comprender cómo evolucionan las inundaciones y sus efectos sobre el territorio.

## 7. Prototipo para NASA Space Apps

Durante el hackathon se desarrollará una versión funcional de NiñoRadar con tres capacidades principales:

**1. Mapa de detección de inundaciones:** visualización de los cambios entre dos observaciones SAR comparables.

**2. Mapa de infraestructura expuesta:** identificación de segmentos viales y áreas agrícolas que intersectan las superficies detectadas como inundadas.

**3. Panel de evaluación territorial:** indicadores de superficie inundada, infraestructura potencialmente expuesta y sectores propuestos para verificación.

El prototipo utilizará productos georreferenciados NISAR, cuando existan adquisiciones comparables sobre el área de estudio, e información cartográfica abierta. Podrán utilizarse imágenes históricas Sentinel-1 para validar la metodología, identificándolas claramente como datos de otra misión.

Se documentará la incertidumbre de la clasificación y la fecha de cada observación. La plataforma no presentará sus resultados como detecciones en tiempo real ni como confirmaciones de daños.

## 8. Impacto esperado

NiñoRadar busca demostrar cómo las observaciones de la misión NISAR pueden contribuir a mejorar la comprensión espacial de las inundaciones.

El impacto del proyecto se plantea en tres dimensiones:

**Científica:** demostrar una metodología reproducible de detección de cambios en superficies inundadas mediante radar satelital.

**Tecnológica:** convertir datos SAR en mapas interactivos e indicadores de exposición comprensibles para usuarios no especializados.

**Social:** facilitar la identificación preliminar de áreas potencialmente afectadas y apoyar una mejor priorización de verificaciones territoriales.

---

## 9. Nuestra visión

Aspiramos a que NiñoRadar evolucione hacia una herramienta abierta y escalable, capaz de integrar observaciones satelitales con datos territoriales para apoyar la gestión de inundaciones en distintas regiones vulnerables.

Nuestro objetivo es que las imágenes satelitales no se queden únicamente en laboratorios o plataformas científicas, sino que puedan convertirse en información útil para las comunidades que enfrentan los efectos del cambio ambiental.

**NiñoRadar: del espacio al territorio, transformando datos satelitales en información para actuar.**