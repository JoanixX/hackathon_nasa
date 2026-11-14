# NiñoRadar

### Inteligencia satelital para comprender el impacto de las inundaciones

Proyecto para la hackathon **NASA Space Apps Challenge 2026**, asociado al reto **Dancing with the SARs**, según el contexto del equipo. Repositorio: `hackathon_nasa`. Equipo mencionado en el documento complementario: **404 Gravity**.

**Estado: preparación documental.** Este repositorio contiene contexto, alcance y reglas de trabajo. Todavía no contiene una aplicación, un pipeline SAR, datos descargados, integraciones probadas ni resultados científicos validados. El stack y el despliegue se decidirán después de investigar su viabilidad.

## Qué buscamos resolver

Las lluvias extremas y las inundaciones en Piura pueden afectar viviendas, carreteras, agricultura y servicios esenciales. La información territorial está distribuida entre distintas fuentes y la nubosidad limita la observación óptica.

NiñoRadar propone transformar observaciones SAR de la misión NISAR (NASA–ISRO) en mapas comprensibles de cambios en el agua superficial, cruzarlos con infraestructura y apoyar la priorización de evaluaciones en campo.

El piloto se concentra en **Catacaos y Cura Mori, Piura, Perú**. La expansión a otras zonas requiere datos adecuados y validación independiente.

## Tres preguntas que guían el producto

1. **¿Dónde se ha extendido el agua?** Mostrar cambios compatibles con inundación entre observaciones comparables.
2. **¿Qué podría estar siendo afectado?** Estimar intersecciones con vías, edificaciones y áreas agrícolas, según las capas disponibles.
3. **¿Dónde conviene priorizar la evaluación?** Mostrar sectores propuestos para verificación con reglas explicables e incertidumbre visible.

## MVP previsto

| Capacidad | Resultado esperado | Condición previa |
| --- | --- | --- |
| Mapa de detección | Comparación antes/después y extensión de agua detectada | Pareja SAR comparable y método documentado |
| Mapa de exposición | Segmentos viales y áreas agrícolas potencialmente expuestos; edificaciones si existe una capa adecuada | Cartografía con cobertura, fecha y licencia conocidas |
| Panel territorial | Superficie en ha/km², longitud vial en km y sectores para verificar | Cálculos reproducibles y metadatos de calidad |

Flujo conceptual: **observación satelital → detección de cambios → cruce territorial → visualización y apoyo a la evaluación**. Estas capacidades son objetivos, no funcionalidades ya implementadas.

## Cómo interpretar los resultados futuros

- Una máscara de agua es una **estimación preliminar**, no una confirmación de daños.
- Una vía que intersecta la máscara está **potencialmente expuesta**; la intersección no acredita corte, transitabilidad ni ruta segura.
- Las adquisiciones tienen fecha, cobertura y limitaciones. La aplicación no debe presentar la detección como tiempo real.
- NISAR es la misión principal. Sentinel-1 puede apoyar una validación histórica, siempre rotulado como otra misión.
- No inferir profundidad, velocidad del agua, víctimas ni causalidad climática únicamente a partir de retrodispersión SAR.
- El producto complementa a las instituciones; las decisiones oficiales corresponden a sus responsables.

## Fuentes y prioridad del contexto

1. [Texto principal íntegro](docs/CONTEXTO_FUENTE.md): copia del adjunto proporcionado por el usuario; define producto, piloto y límites.
2. [Google Docs del equipo](https://docs.google.com/document/d/10_RmLBz5asZoEUewSKRS8kkQ9_lA0bDfm1piiPGLaHs/edit?tab=t.flskznlxd0bg): investigación complementaria, consultada el 14 de noviembre de 2026.
3. Documentación primaria y evidencia reproducible: necesarias para verificar datos, herramientas, cobertura y rendimiento antes de implementar.

El Google Docs propone también Piura/Tumbes, pronósticos, asignación de verificaciones y reportes de brigadas. Esas ideas **no amplían automáticamente el MVP**: véase la [conciliación de fuentes](docs/FUENTES_Y_DECISIONES.md).

## Contenido del repositorio

```text
hackathon_nasa/
├── .gitattributes
├── .gitignore
├── AGENTS.md
├── CONTRIBUTING.md
├── README.md
├── docs/
│   ├── CONTEXTO_FUENTE.md
│   ├── ALCANCE_Y_VALIDACION.md
│   └── FUENTES_Y_DECISIONES.md
└── prompts/                         # Solo local; excluido de Git
    ├── 01_logica_y_refactor_visual.md
    ├── 02_investigacion_arquitectura.md
    └── 03_investigacion_ux_ui_ar_gemelos.md
```

## Cómo usar los prompts locales

Los tres archivos son autocontenidos: incluyen el texto principal íntegro, el complemento delimitado, instrucciones de trabajo y entregables verificables. Se pueden copiar completos a otra IA sin acceso al Google Docs ni a los otros prompts.

| Archivo local | Encargo | Modo de trabajo |
| --- | --- | --- |
| `prompts/01_logica_y_refactor_visual.md` | Nueva lógica, flujos, contratos de presentación y refactor visual | Auditar y planificar primero; ejecutar cuando se solicite implementar |
| `prompts/02_investigacion_arquitectura.md` | Datos SAR, implementación, escalabilidad, concurrencia, latencia y errores | Investigar y producir un plan técnico reproducible |
| `prompts/03_investigacion_ux_ui_ar_gemelos.md` | UX/UI geoespacial, animaciones, AR y gemelos digitales | Investigar, comparar y especificar una experiencia viable |

Orden sugerido para reducir retrabajo: investigar arquitectura y UX/UI; luego integrar decisiones en el encargo de lógica/refactor. También pueden usarse por separado: las decisiones ajenas que falten se registran como pendientes.

`prompts/` no se publica, no tiene commits y no aparecerá al clonar. Para mover los prompts a otro equipo hay que copiarlos por un canal privado autorizado. Las investigaciones futuras pueden guardarse en `docs/investigacion/`; esta carpeta todavía no existe.

## Próximos pasos

1. Verificar las reglas vigentes del reto y localizar una pareja NISAR comparable sobre el piloto; registrar IDs y metadatos.
2. Revisar cartografía de vías, agricultura y límites distritales, con licencias y fechas.
3. Evaluar un método base SAR y una referencia independiente, sin prometer precisión no medida.
4. Elegir arquitectura y experiencia 2D antes de comprometer AR, simulaciones o coordinación operativa.
5. Implementar el MVP por incrementos verificables, conservando la procedencia de cada resultado.

Consultar [alcance y validación](docs/ALCANCE_Y_VALIDACION.md) y [reglas de contribución](CONTRIBUTING.md). Desde este setup, **cada commit debe modificar un solo archivo versionado**. Los prompts permanecen ignorados; no usar `git add -f` para incluirlos.

## Licencias y atribuciones

La licencia del código del proyecto queda pendiente de decisión del equipo. El repositorio es privado y no se concede aquí una licencia abierta. Cada dataset, mapa base, biblioteca y recurso visual conservará su propia licencia y atribución. Participar en NASA Space Apps no implica respaldo institucional de NASA, ISRO u organismos peruanos.
