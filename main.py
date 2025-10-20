from flask import Flask, render_template, request, jsonify, session
import os
from werkzeug.utils import secure_filename
import PyPDF2
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuración de subida
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {'pdf'}

# Crear carpeta de subida si no existe
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extrae texto de un PDF. PyPDF2 puede retornar None en extract_text(), así que normalizamos.
    """
    text_parts = []
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        raise Exception(f"Error al extraer texto del PDF: {str(e)}")


def get_book_text() -> str:
    """
    Lee el texto del libro desde el archivo guardado en disco.
    Evita almacenar contenido pesado en la cookie de sesión.
    """
    book_path = session.get('book_path')
    if not book_path:
        raise FileNotFoundError("No hay libro cargado.")
    if not os.path.exists(book_path):
        raise FileNotFoundError("El archivo del libro no existe en el servidor.")
    return extract_text_from_pdf(book_path)


def ensure_openai_client() -> OpenAI:
    """
    Crea el cliente de OpenAI usando la API key desde la variable de entorno OPENAI_API_KEY.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError(
            "API key de OpenAI no configurada. "
            "Establece la variable de entorno OPENAI_API_KEY."
        )
    return OpenAI()  # toma la API key desde OPENAI_API_KEY


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No se encontró el campo "file" en la solicitud.'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'No se seleccionó archivo.'}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Guardamos SOLO la ruta y el título en la sesión (no el contenido)
            session['book_path'] = filepath
            session['book_title'] = filename

            # Validamos que realmente podamos extraer algo (opcional pero útil)
            _ = extract_text_from_pdf(filepath)

            return jsonify({
                'success': True,
                'message': 'Libro cargado exitosamente',
                'title': filename
            }), 200

        return jsonify({'error': 'Archivo no permitido. Solo PDFs.'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json or {}
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'error': 'Mensaje vacío.'}), 400

        # Cargamos texto del libro desde disco
        book_content = get_book_text()

        # Cliente OpenAI
        client = ensure_openai_client()

        # Recorta contexto para no enviar demasiado texto
        context = book_content[:3000]

        system_prompt = (
            "Eres un tutor educativo para niños. Tienes acceso al siguiente libro:\n\n"
            f"{context}...\n\n"
            "Tu trabajo es ayudar al niño a comprender el libro respondiendo sus preguntas de manera simple y clara, "
            "usando lenguaje apropiado para niños. Sé paciente, motivador y didáctico."
        )

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=500,
            temperature=0.7
        )

        assistant_message = response.choices[0].message.content
        return jsonify({'response': assistant_message}), 200

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 400
    except EnvironmentError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        # Captura genérica
        return jsonify({'error': f'Error en /chat: {str(e)}'}), 500


@app.route('/generate-questions', methods=['POST'])
def generate_questions():
    try:
        # Cargamos texto del libro desde disco
        book_content = get_book_text()

        # Cliente OpenAI
        client = ensure_openai_client()

        # Recorta contexto para no enviar demasiado texto
        context = book_content[:2000]

        prompt = (
            "Basándote en este fragmento del libro:\n\n"
            f"{context}\n\n"
            "Genera 5 preguntas de comprensión lectora apropiadas para niños. "
            "Las preguntas deben ser simples, claras y ayudar a verificar que el niño entendió la lectura."
        )

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un profesor que crea preguntas de comprensión para niños."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )

        questions = response.choices[0].message.content
        return jsonify({'questions': questions}), 200

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 400
    except EnvironmentError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        # Captura genérica
        return jsonify({'error': f'Error en /generate-questions: {str(e)}'}), 500


if __name__ == '__main__':
    # Debug solo para desarrollo: no usar en producción
    app.run(debug=True, host='0.0.0.0', port=5000)
