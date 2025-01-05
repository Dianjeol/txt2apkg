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

# Konfiguration für temporäre Dateien
TEMP_DIR = '/tmp'  # Für Python Anywhere
FILES_DIR = os.path.join(TEMP_DIR, 'anki_files')
os.makedirs(FILES_DIR, exist_ok=True)

# Dictionary zum Speichern der Datei-Informationen
temp_files = {}

def detect_separator(file):
    first_line = file.readline().decode('utf-8').strip()
    file.seek(0)
    
    separators = ['\t', ';', ',']
    for sep in separators:
        if sep in first_line:
            return sep
    return '\t'

def create_deck_from_file(file, deck_name):
    model = genanki.Model(
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
            .cloze, .cloze b, .cloze u, .cloze i { 
                font-weight: bold; 
                color: MediumSeaGreen !important;
            }
            #extra, #extra i { 
                font-size: 15px; 
                color:#D7DEE9; 
                font-style: italic; 
            }
            .tags { 
                color: #A6ABB9;
                opacity: 1;
                font-size: 10px; 
                width: 100%;
                text-align: center;
                text-transform: uppercase; 
                position: fixed; 
                padding: 0; 
                top:0;  
                right: 0;
            }
            .tags:hover { 
                opacity: 1; 
                position: fixed;
            }
            img { 
                display: block; 
                max-width: 100%; 
                max-height: none; 
                margin-left: auto; 
                margin: 10px auto 10px auto;
            }
            tr {
                font-size: 12px; 
            }
            b { color: #C695C6 !important; }
            u { text-decoration: none; color: #5EB3B3;}
            i  { color: IndianRed; }
            a { 
                color: LightGray !important; 
                text-decoration: none; 
                font-size: 10px; 
                font-style: normal; 
            }
            .mobile .card { 
                color: #D7DEE9; 
                background-color: #333B45; 
            } 
            .mobile .tags { 
                opacity: 1; 
                position: relative;
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
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    deck_name = request.form.get('deck_name', 'Anki-Karten')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith(('.txt', '.csv')):
        return jsonify({'error': 'Invalid file format'}), 400
    
    try:
        # Generiere eine eindeutige ID für die Datei
        file_id = str(uuid.uuid4())
        
        # Erstelle die Anki-Datei
        output_path = create_deck_from_file(file, deck_name)
        
        # Verschiebe die Datei in den permanenten Speicherort
        permanent_path = os.path.join(FILES_DIR, f"{file_id}.apkg")
        shutil.move(output_path, permanent_path)
        
        # Speichere die Datei-Informationen
        expiry_time = datetime.now() + timedelta(hours=24)  # Link läuft nach 24 Stunden ab
        temp_files[file_id] = {
            'path': permanent_path,
            'expires': expiry_time,
            'deck_name': deck_name
        }
        
        # Cleanup alte Dateien
        cleanup_old_files()
        
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

@app.route('/download/<file_id>')
def download_file(file_id):
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
    cleanup_old_files()

if __name__ == '__main__':
    app.run(debug=True)
