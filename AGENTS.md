# Instrucciones para agentes en este repositorio

- El proyecto es NiñoRadar y este setup es documental. No iniciar implementación por inferencia: atender el encargo concreto de cada sesión.
- Leer `README.md` y los tres documentos en `docs/` antes de decidir alcance.
- `docs/CONTEXTO_FUENTE.md` conserva el texto principal del usuario. No sustituirlo por propuestas del Google Docs. Documentar cambios de alcance expresamente pedidos por el propietario.
- Piloto: Catacaos y Cura Mori, Piura. Tumbes, Rímac, coordinación de brigadas, pronósticos, AR y gemelos digitales son extensiones sujetas a investigación, salvo instrucción posterior.
- Preservar la distinción entre agua detectada, exposición potencial, verificación en campo y daños confirmados. No prometer tiempo real, rutas seguras, profundidad o precisión no medida.
- Verificar cobertura NISAR, productos, versiones y comparabilidad; no atribuir a NISAR escenas históricas de otra misión.
- **Cada commit nuevo debe cambiar exactamente un archivo versionado**, por instrucción del usuario. Preparar y revisar cada archivo por separado. No hacer squash de commits que agrupe varios archivos.
- `prompts/` es local y está ignorado: no subirlo, no copiar sus contenidos a archivos versionados y no usar `git add -f` para incluirlo. Los cambios en archivos ignorados no llevan commit.
- No versionar secretos, credenciales ni datos satelitales grandes. Mantener fuentes, fechas, licencias, calidad y procedencia en los metadatos de los futuros resultados.
- No elegir una licencia abierta, instalar infraestructuras de pago ni desplegar servicios salvo que la tarea lo autorice.
- Documentar verificaciones ejecutadas y limitaciones reales. Una investigación debe distinguir evidencia, recomendación, supuesto y pendiente.
