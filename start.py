from flask import Flask, render_template, request, send_file, jsonify, url_for
import pandas as pd
import genanki
import io
import os
import tempfile
import csv
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from pathlib import Path
import shutil

app = Flask(__name__)

# Konfiguration
TEMP_DIR = '/tmp'  # Für Python Anywhere
FILES_DIR = os.path.join(TEMP_DIR, 'anki_files')
os.makedirs(FILES_DIR, exist_ok=True)

# Dictionary zum Speichern der temporären Dateien
temp_files = {}

def detect_separator(file):
    """Erkennt den Separator in der CSV/TXT Datei"""
    first_line = file.readline().decode('utf-8').strip()
    file.seek(0)
    
    separators = ['\t', ';', ',']
    for sep in separators:
        if sep in first_line:
            return sep
    return '\t'

def create_anki_model():
    """Erstellt das Anki Kartenmodell"""
    return genanki.Model(
        1607392319,
        'Simple Model',
        fields=[
            {'name': 'Front'},
            {'name': 'Back'},
        ],
        templates=[{
            'name': 'Card 1',
            'qfmt': '''
                <div id="kard">
                    <div class="front">{{Front}}</div>
                </div>
            ''',
            'afmt': '''
                <div id="kard">
                    <div class="front">{{Front}}</div>
                    <hr id="answer">
                    <div class="back">{{Back}}</div>
                </div>
            ''',
        }],
        css='''
            html { overflow: scroll; overflow-x: hidden; }
            #kard {
                padding: 0px 0px;
                max-width: 700px;
                margin: 0 auto;
                word-wrap: break-word;
            }
            .card {
                font-family: Menlo, baskerville, sans;
                font-size: 18px;
                text-align: center;
                color: #D7DEE9;
                line-height: 1.6em;
                background-color: #333B45;
            }
            hr {
                border: none;
                border-top: 1px solid #D7DEE9;
                margin: 20px 0;
            }
            .front, .back {
                padding: 20px;
            }
        '''
    )

def create_deck_from_file(file, deck_name):
    """Erstellt ein Anki-Deck aus einer Datei"""
    model = create_anki_model()
    deck = genanki.Deck(2059400110, deck_name)

    separator = detect_separator(file)
    file.seek(0)

    df = pd.read_csv(file, sep=separator, header=None, names=['front', 'back'])

    for _, row in df.iterrows():
        note = genanki.Note(
            model=model,
            fields=[str(row['front']), str(row['back'])]
        )
        deck.add_note(note)

    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, f"{deck_name}.apkg")
    
    package = genanki.Package(deck)
    package.write_to_file(output_path)
    
    return output_path

def create_deck_from_vocabulary(vocabulary, deck_name):
    """Erstellt ein Anki-Deck aus einem Vokabel-Dictionary oder einer Liste"""
    model = create_anki_model()
    deck = genanki.Deck(2059400110, deck_name)

    # Verarbeite verschiedene Eingabeformate
    if isinstance(vocabulary, dict):
        # Format: {"Hallo": "Hello", "Welt": "World"}
        items = vocabulary.items()
    elif isinstance(vocabulary, list):
        # Format: [["Hallo", "Hello"], ["Welt", "World"]]
        items = vocabulary
    else:
        raise ValueError("Ungültiges Vokabelformat")

    for front, back in items:
        note = genanki.Note(
            model=model,
            fields=[str(front), str(back)]
        )
        deck.add_note(note)

    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, f"{deck_name}.apkg")
    
    package = genanki.Package(deck)
    package.write_to_file(output_path)
    
    return output_path

def cleanup_old_files():
    """Entfernt abgelaufene temporäre Dateien"""
    current_time = datetime.now()
    expired_files = [file_id for file_id, info in temp_files.items() 
                    if info['expires'] < current_time]
    
    for file_id in expired_files:
        file_info = temp_files.pop(file_id)
        try:
            os.remove(file_info['path'])
        except OSError:
            pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    """Endpunkt für Datei-Upload über Web-Interface"""
    if 'file' not in request.files:
        return 'Keine Datei hochgeladen', 400
    
    file = request.files['file']
    deck_name = request.form.get('deck_name', 'Anki-Karten')
    
    if file.filename == '':
        return 'Keine Datei ausgewählt', 400
    
    if not file.filename.endswith(('.txt', '.csv')):
        return 'Ungültiges Dateiformat', 400
    
    try:
        output_path = create_deck_from_file(file, deck_name)
        return send_file(output_path, 
                        as_attachment=True,
                        download_name=f"{deck_name}.apkg")
    except Exception as e:
        return str(e), 400

@app.route('/api/convert', methods=['POST'])
def api_convert():
    """API-Endpunkt für Datei-Upload"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    deck_name = request.form.get('deck_name', 'Anki-Karten')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith(('.txt', '.csv')):
        return jsonify({'error': 'Invalid file format'}), 400
    
    try:
        output_path = create_deck_from_file(file, deck_name)
        
        # Generiere eindeutige ID und speichere die Datei
        file_id = str(uuid.uuid4())
        permanent_path = os.path.join(FILES_DIR, f"{file_id}.apkg")
        shutil.move(output_path, permanent_path)
        
        # Speichere Datei-Informationen
        expiry_time = datetime.now() + timedelta(hours=24)
        temp_files[file_id] = {
            'path': permanent_path,
            'expires': expiry_time,
            'deck_name': deck_name
        }
        
        # Generiere Download-URL
        download_url = url_for('download_file', file_id=file_id, _external=True)
        
        return jsonify({
            'success': True,
            'message': 'File converted successfully',
            'download_url': download_url,
            'expires': expiry_time.isoformat(),
            'deck_name': deck_name
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/convert-direct', methods=['POST'])
def api_convert_direct():
    """API-Endpunkt für direkte Vokabeleingabe"""
    try:
        data = request.get_json()
        
        if not data or 'vocabulary' not in data:
            return jsonify({'error': 'No vocabulary data provided'}), 400
            
        deck_name = data.get('deck_name', 'Anki-Karten')
        vocabulary = data['vocabulary']
        
        # Erstelle Anki-Deck direkt aus den Vokabeln
        output_path = create_deck_from_vocabulary(vocabulary, deck_name)
        
        # Generiere eindeutige ID und speichere die Datei
        file_id = str(uuid.uuid4())
        permanent_path = os.path.join(FILES_DIR, f"{file_id}.apkg")
        shutil.move(output_path, permanent_path)
        
        # Speichere Datei-Informationen
        expiry_time = datetime.now() + timedelta(hours=24)
        temp_files[file_id] = {
            'path': permanent_path,
            'expires': expiry_time,
            'deck_name': deck_name
        }
        
        # Generiere Download-URL
        download_url = url_for('download_file', file_id=file_id, _external=True)
        
        return jsonify({
            'success': True,
            'message': 'Deck created successfully',
            'download_url': download_url,
            'expires': expiry_time.isoformat(),
            'deck_name': deck_name
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download/<file_id>')
def download_file(file_id):
    """Endpunkt für das Herunterladen der generierten Dateien"""
    if file_id not in temp_files:
        return jsonify({'error': 'File not found or expired'}), 404
    
    file_info = temp_files[file_id]
    
    if datetime.now() > file_info['expires']:
        # Entferne abgelaufene Datei
        temp_files.pop(file_id)
        try:
            os.remove(file_info['path'])
        except OSError:
            pass
        return jsonify({'error': 'Download link has expired'}), 410
    
    return send_file(
        file_info['path'],
        as_attachment=True,
        download_name=f"{file_info['deck_name']}.apkg",
        mimetype='application/octet-stream'
    )

@app.before_request
def before_request():
    """Führt Cleanup vor jeder Anfrage durch"""
    cleanup_old_files()

if __name__ == '__main__':
    app.run(debug=True)
