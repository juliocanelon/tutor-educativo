# 📘 Tutor Educativo con IA

Aplicación web construida con **Flask** y la **API de OpenAI** que guía a niñas y niños durante la lectura de un libro en PDF. A partir del texto cargado, el sistema genera respuestas ancladas al material, aclara vocabulario complejo y crea evaluaciones con control de calidad pedagógica.

## ✨ Novedades principales

- 🧭 **Orchestrator–Workers**: un orquestador pedagógico enruta cada petición hacia workers especializados (tutor, vocabulario y evaluaciones).
- ✅ **Evaluator–Optimizer**: cada salida pasa por un checklist pedagógico automático; si falla, se reescribe hasta dos veces antes de responder.
- 🔖 **Respuestas con anclaje**: el tutor cita fragmentos del libro y propone mini-preguntas de seguimiento.
- 🗂️ **Trazabilidad**: el frontend muestra el worker utilizado, resultados del checklist y número de reintentos.
- 🎯 **Preguntas por niveles**: los cuestionarios se agrupan en bloques literal, inferencial y crítico con retroalimentación para el docente.

---

## ⚙️ Instalación

1. **Clonar el proyecto**
   ```bash
   git clone https://github.com/tu_usuario/tutor-educativo-ia.git
   cd tutor-educativo-ia
   ```

2. **Crear entorno virtual**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux / macOS
   source .venv/bin/activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar la API key de OpenAI**
   ```bash
   # Windows PowerShell
   $env:OPENAI_API_KEY = "tu_api_key_aqui"

   # Linux / macOS
   export OPENAI_API_KEY="tu_api_key_aqui"
   ```

---

## 🚀 Ejecución

```bash
python main.py
```

Visita [http://127.0.0.1:5000](http://127.0.0.1:5000) para usar la interfaz web.

1. Carga un PDF (se guarda solo la ruta en sesión).
2. Elige modo **Explicación** o **Vocabulario** y chatea con el tutor.
3. Genera preguntas de comprensión; el resultado incluye la traza del evaluador.

---

## 🧠 Arquitectura de agentes

```
app/
├── data/
│   └── storage.py         # Gestión de PDFs y extracción de texto
├── nlp/
│   └── rag.py             # Búsqueda ligera de fragmentos relevantes
├── orchestrator/
│   └── core.py            # Orquestador pedagógico
├── quality/
│   ├── evaluator.py       # Evaluación de checklist pedagógico
│   └── optimizer.py       # Reescritura guiada por feedback
└── workers/
    ├── tutor.py           # Tutor con anclaje y mini-pregunta
    ├── vocab.py           # Explicación de vocabulario complejo
    └── evaluator_gen.py   # Generación de bloques de preguntas
```

- **Orchestrator** selecciona worker según el modo (`explicar`, `vocabulario`, `evaluar`) y coordina el ciclo Evaluator–Optimizer.
- **Evaluator** valida criterios como `anchored`, `clarity`, `variety` o `feedback` usando prompts dedicados.
- **Optimizer** vuelve a consultar a OpenAI cuando la salida no supera el checklist, con un máximo de dos reintentos.

---

## 🖥️ Interfaz

- Modo de ayuda y edad configurables antes de cada mensaje.
- El chat muestra la respuesta del agente, la cita del libro utilizada y la traza (`worker`, checklist y reintentos).
- El generador de preguntas también expone la traza para facilitar auditorías educativas.

---

## 🛠️ Notas técnicas

- Mantiene el flujo de archivos en `uploads/` y evita guardar el texto completo en sesión.
- Llama a `gpt-3.5-turbo` con límites conservadores de `max_tokens` y temperatura por worker.
- Manejo de errores centrado en respuestas JSON claras para faltas de archivo, credenciales y fallos inesperados.
- `debug=True` solo para desarrollo local; ajusta según tus necesidades en producción.

---

## 📚 Licencia

Proyecto distribuido bajo licencia **MIT**. ¡Siéntete libre de adaptarlo y mejorarlo! 
