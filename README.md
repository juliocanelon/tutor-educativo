# 📘 Tutor Educativo con IA

Una aplicación web desarrollada con **Flask** que utiliza la **API de OpenAI** para ayudar a los niños a comprender libros y fortalecer sus habilidades de lectura y comprensión.

## ✨ Características

- 📄 **Carga de PDFs:** Permite subir archivos PDF y extraer su texto automáticamente.  
- 💬 **Chat educativo:** Usa GPT-3.5-Turbo para responder preguntas sobre el contenido del libro en un lenguaje simple y didáctico.  
- ❓ **Generación de preguntas:** Crea 5 preguntas de comprensión lectora adaptadas para niños.  

---

## ⚙️ Instalación

### 1. Clonar o descargar el proyecto
```bash
git clone https://github.com/tu_usuario/tutor-educativo-ia.git
cd tutor-educativo-ia
```

### 2. Crear entorno virtual
**Windows (PowerShell):**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias
El proyecto usa versiones compatibles para evitar errores con `httpx` y `openai`:

```bash
pip install -r requirements.txt
```

Tu `requirements.txt` debe incluir:
```txt
Flask>=2.3
Werkzeug>=2.3
PyPDF2>=3.0
openai>=1.51.0,<2
httpx<0.28
```

### 4. Configurar la API key de OpenAI
Obtén tu API key en: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

**Windows (PowerShell):**
```bash
$env:OPENAI_API_KEY = "tu_api_key_aqui"
```

**Linux / macOS:**
```bash
export OPENAI_API_KEY="tu_api_key_aqui"
```

> 💡 No es necesario un archivo `.env`. La aplicación toma la clave directamente de la variable de entorno.

---

## 🚀 Ejecución del proyecto

1. **Iniciar la aplicación:**
   ```bash
   python main.py
   ```

2. **Abrir en el navegador:**
   ```
   http://127.0.0.1:5000
   ```

3. **Uso:**
   - Sube un libro en formato **PDF** desde la interfaz web.  
   - La aplicación extrae el texto y guarda **solo la ruta del archivo** (no el contenido) por seguridad y eficiencia.  
   - Puedes:
     - Chatear con el tutor virtual sobre el contenido del libro.  
     - Generar preguntas de comprensión lectora.

---

## 🧩 Estructura del Proyecto

```
tutor-educativo-ia/
├── main.py                  # Aplicación principal Flask
├── templates/
│   └── index.html           # Interfaz web
├── uploads/                 # Carpeta donde se guardan los PDFs subidos
├── requirements.txt         # Dependencias del proyecto
└── tarea.md                 # Documento de evaluación universitaria
```

---

## 🧠 Tecnologías Utilizadas

- **Flask** – Framework web en Python  
- **OpenAI API (GPT-3.5-Turbo)** – Motor de lenguaje natural  
- **PyPDF2** – Extracción de texto de archivos PDF  
- **HTML / CSS / JavaScript** – Interfaz de usuario  
- **Werkzeug** – Seguridad y manejo de archivos en Flask  

---

## 🛠️ Notas Técnicas

- El pdf del libro se guarda su ruta en `uploads/`.
- La app maneja errores comunes (falta de archivo, API key no configurada, libro no encontrado) con respuestas JSON claras.
- `debug=True` está activo solo para desarrollo; desactívalo en entornos de producción.

---

## 📚 Ejemplo de flujo de uso

1. Cargar `cuentos_infantiles.pdf`  
2. Preguntar:  
   > ¿Por qué el lobo sopló la casa de los cerditos?

3. Generar preguntas de comprensión:  
   > - ¿Quiénes eran los personajes principales del cuento?  
   > - ¿Qué materiales usaron los cerditos para construir sus casas?

---

## 🧾 Licencia
Este proyecto se distribuye bajo la licencia **MIT**. Puedes usarlo, modificarlo y compartirlo libremente.
