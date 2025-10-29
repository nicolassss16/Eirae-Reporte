import sqlite3
import datetime
import os
import uuid
import json  # Para el mapa
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename

# --- 1. CONFIGURACIÓN DE RUTAS ABSOLUTAS ---
basedir = os.path.abspath(os.path.dirname(__file__))

# --- 2. Configuración de Carpetas ---
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Carpeta {UPLOAD_FOLDER} creada.")

# --- 3. Configuración del Servidor Web ---
static_folder = os.path.join(basedir, 'static')
app = Flask(__name__, static_folder=static_folder)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
DB_FILE = os.path.join(basedir, 'reportes.db')

# --- 4. Función de Inicialización de Base de Datos ---
def inicializar_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Crear la tabla principal
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reportes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        direccion TEXT,
        latitud REAL,
        longitud REAL,
        descripcion TEXT
    )
    ''')
    
    # Columnas a chequear (incluye la gestión de estados)
    columnas = {
        'foto_filename': 'TEXT',
        'codigo_postal': 'TEXT',
        'barrio': 'TEXT',
        'localidad': 'TEXT',
        'status': "TEXT DEFAULT 'Nuevo'"  # Para gestionar estados
    }
    
    for col, tipo in columnas.items():
        try:
            cursor.execute(f"ALTER TABLE reportes ADD COLUMN {col} {tipo}")
            print(f"Columna '{col}' añadida a la base de datos.")
        except sqlite3.OperationalError:
            print(f"La columna '{col}' ya existía.")
            
    conn.commit()
    conn.close()
    print(f"Base de datos {DB_FILE} inicializada y lista.")

# --- 5. Rutas para servir archivos estáticos (Frontend y Fotos) ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

# --- 6. RUTA API: Recibir nuevos reportes ---
@app.route('/report', methods=['POST'])
def recibir_reporte():
    try:
        # 6.1. Obtenemos los datos del formulario
        direccion = request.form.get('direccion', 'N/A')
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        descripcion = request.form.get('descripcion', '')
        fecha_hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        codigo_postal = request.form.get('codigo_postal', '')
        barrio = request.form.get('barrio', '')
        localidad = request.form.get('localidad', '')
        
        foto_nombre_final = None
        
        # 6.2. Procesar y Guardar la Foto (Localmente)
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '':
                filename_seguro = secure_filename(file.filename)
                extension = filename_seguro.rsplit('.', 1)[1].lower()
                foto_nombre_final = f"{uuid.uuid4()}.{extension}"
                ruta_guardado = os.path.join(app.config['UPLOAD_FOLDER'], foto_nombre_final)
                file.save(ruta_guardado)
                print(f"Foto guardada en: {ruta_guardado}")

        # 6.3. Guardar en la Base de Datos
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Nótese que 'status' no se inserta, usa su valor 'DEFAULT'
        sql_query = '''
        INSERT INTO reportes (
            fecha, direccion, latitud, longitud, descripcion, foto_filename, 
            codigo_postal, barrio, localidad
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        cursor.execute(sql_query, (
            fecha_hora, direccion, lat, lng, descripcion, foto_nombre_final,
            codigo_postal, barrio, localidad
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({ "status": "success", "message": "Reporte y foto guardados." }), 200

    except Exception as e:
        print(f"Error procesando el reporte: {e}")
        return jsonify({ "status": "error", "message": f"Error interno del servidor: {e}" }), 500

# --- 7. RUTA DEL PANEL DE ADMIN (¡CON MAPA!) ---
@app.route('/admin')
def admin_panel():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row # Para acceder a datos por nombre
        cursor = conn.cursor()
        
        # Obtenemos todos los reportes (incluyendo 'status')
        cursor.execute("SELECT * FROM reportes ORDER BY fecha DESC")
        reportes_data = cursor.fetchall()
        
        conn.close()
        
        # Convertir datos a JSON para el script del mapa
        reportes_list = [dict(row) for row in reportes_data]
        reportes_json = json.dumps(reportes_list)
        
        # Pasamos los datos a la plantilla admin.html
        return render_template('admin.html', reportes=reportes_data, reportes_json=reportes_json)
        
    except Exception as e:
        print(f"Error al cargar el panel de admin: {e}")
        return "<h1>Error al cargar el panel</h1><p>Revisa la consola del servidor.</p>"

# --- 8. RUTA API: Actualizar estado del reporte ---
@app.route('/update_status/<int:report_id>', methods=['POST'])
def update_status(report_id):
    try:
        data = request.json
        new_status = data.get('status')

        if not new_status:
            return jsonify({"status": "error", "message": "No se proveyó un estado"}), 400
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE reportes SET status = ? WHERE id = ?", (new_status, report_id))
        conn.commit()
        conn.close()
        
        print(f"Reporte {report_id} actualizado a estado: {new_status}")
        return jsonify({"status": "success", "message": "Estado actualizado"})
        
    except Exception as e:
        print(f"Error al actualizar estado: {e}")
        return jsonify({"status": "error", "message": "Error interno"}), 500


# --- 9. Punto de entrada (Ejecutar el servidor) ---
if __name__ == '__main__':
    inicializar_db() # Prepara la base de datos
    app.run(host='0.0.0.0', port=5000, debug=True)

