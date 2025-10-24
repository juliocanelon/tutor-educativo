# Declaración del Problema y Arquitectura de la Solución

## 1. Declaración del Problema

### 1.1 Contexto educativo y necesidad de IAG
La aplicación aborda un escenario frecuente en escuelas primarias: niñas y niños deben leer textos extensos sin acompañamiento personalizado, lo que deriva en dudas no resueltas, vocabulario complejo y falta de evaluación formativa. El objetivo pedagógico exige respuestas contextualizadas al libro activo, ajustes al nivel de madurez del estudiante y retroalimentación inmediata para docentes. Estos requisitos implican entender lenguaje natural, razonar sobre fragmentos del libro y generar contenido nuevo de calidad, tareas que demandan capacidades generativas y de razonamiento que un sistema determinista difícilmente cubriría con reglas predefinidas. Por ello se recurre a agentes de IA generativa (IAG) basados en LLMs que pueden interpretar preguntas abiertas, sintetizar información y adaptar el tono infantil con trazabilidad de decisiones.

### 1.2 Descripción de la solución y justificación del uso de agentes inteligentes
La solución implementa un tutor virtual que ingiere el PDF elegido, construye contexto relevante y produce tres tipos de ayuda: explicación guiada, glosario de vocabulario y evaluaciones con retroalimentación pedagógica. En la etapa 2 se consolidó una arquitectura multiagente en la que un orquestador decide qué *worker* especializado debe responder, mientras un evaluador y un optimizador garantizan calidad antes de devolver la salida.【F:app/orchestrator/core.py†L17-L114】 Esta coordinación es difícil de replicar con programación tradicional porque requiere interpretar el desempeño de cada respuesta, identificar fallas pedagógicas y reescribirlas de forma creativa; capacidades que justifican el uso de agentes LLM que combinan comprensión semántica con generación adaptable.【F:README.md†L9-L47】

### 1.3 Etapas del proyecto y aportes de la IA
- **Etapa 1 (commit `c9ebd7a`):** se construyó el MVP con un solo flujo de chat y generación de preguntas donde un único *prompt* atendía todas las peticiones. La IA ya aportaba valor al interpretar preguntas libres y producir cuestionarios, pero sin control de calidad ni segmentación de tareas, lo que generaba respuestas ocasionalmente extensas o poco alineadas.
- **Etapa 2 (commits posteriores):** se incorporó la orquestación pedagógica, *workers* especializados (tutor, vocabulario, evaluaciones e imágenes) y un ciclo Evaluator–Optimizer que reintenta hasta corregir fallos detectados.【F:app/orchestrator/core.py†L27-L113】 Además se añadió RAG ligero para anclar respuestas al libro y métricas de consumo para supervisión docente.【F:README.md†L49-L105】 La IA potencia cada etapa al seleccionar fragmentos relevantes, adaptar el discurso al rango de edad y validar automáticamente criterios pedagógicos. Sin IAG resultaría inviable mantener estas mejoras dinámicas sin intervención manual; con IAG, las iteraciones se automatizan y escalan a múltiples libros y contextos.

## 2. Arquitectura Web y Patrón LLM

### 2.1 Arquitectura web identificada y trade-offs
La solución utiliza un **monolito Flask** donde las rutas HTTP, la gestión de archivos y la lógica de orquestación conviven en un único despliegue (`main.py` concentra endpoints y dependencias).【F:main.py†L1-L146】 Este enfoque simplifica el desarrollo y la entrega rápida al evitar configuraciones distribuidas, facilita compartir sesión y estado de libro, y reduce costos de infraestructura. Como trade-off, el monolito exige pruebas rigurosas para prevenir regresiones y puede dificultar el escalado independiente de módulos (por ejemplo, separación de la generación de imágenes), por lo que a futuro podría evolucionar hacia un monolito modular si la carga aumenta.

### 2.2 Patrones de arquitectura LLM aplicados
- **Router / Orchestrator Pattern:** el `Orchestrator` resuelve qué *worker* (tutor, vocabulario, evaluador o imagen) responde cada petición según el modo solicitado, encapsulando prompts y roles especializados.【F:app/orchestrator/core.py†L30-L78】 Este enrutamiento mantiene prompts diferenciados por tarea y permite añadir nuevos agentes sin reescribir el resto del sistema.
- **Self-Refine / Evaluator-Optimizer Loop:** tras recibir la respuesta del *worker*, la solución ejecuta evaluaciones automáticas y, si fallan, activa un optimizador que reescribe la salida hasta dos veces usando retroalimentación estructurada.【F:app/orchestrator/core.py†L79-L113】 Este patrón asegura calidad pedagógica consistente sin supervisión humana directa, maximizando el impacto del LLM.

En conjunto, ambos patrones explican por qué la arquitectura multiagente incrementa la confiabilidad frente al MVP original: la IA no solo genera contenido, sino que se autorregula mediante roles complementarios.
