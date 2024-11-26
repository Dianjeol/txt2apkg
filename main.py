from flask import Flask, render_template, request, send_file, after_this_request
import genanki
import pandas as pd
import io
import csv
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

def detect_delimiter(text):
    """Detect the delimiter in the text (tab, semicolon, or comma)"""
    delimiters = ['\t', ';', ',']
    counts = [text.count(d) for d in delimiters]
    return delimiters[counts.index(max(counts))] if max(counts) > 0 else '\t'

def create_anki_deck(data, deck_name="My Flashcards"):
    """Create an Anki deck from the provided data"""
    model = genanki.Model(
        1607392319,
        'Simple Model',
        fields=[
            {'name': 'Front'},
            {'name': 'Back'},
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': '{{Front}}',
                'afmt': '{{FrontSide}}<hr id="answer">{{Back}}',
            },
        ])

    deck = genanki.Deck(2059400110, deck_name)

    for front, back in data:
        note = genanki.Note(
            model=model,
            fields=[str(front).strip(), str(back).strip()]
        )
        deck.add_note(note)

    return deck

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        deck_name = request.form.get('deck_name', 'My Flashcards')
        
        try:
            # Get content either from file upload or text input
            content = ""
            if 'file' in request.files and request.files['file'].filename:
                file = request.files['file']
                content = file.read().decode('utf-8')
            else:
                content = request.form.get('text', '')

            if not content.strip():
                return render_template('index.html', error="Please provide input text or upload a file")

            # Detect delimiter and parse content
            delimiter = detect_delimiter(content)
            df = pd.read_csv(io.StringIO(content), 
                           sep=delimiter, 
                           header=None, 
                           encoding='utf-8',
                           quoting=csv.QUOTE_MINIMAL,
                           on_bad_lines='skip')

            if len(df.columns) < 2:
                return render_template('index.html', 
                                     error="Input must have at least 2 columns (front and back of cards)")

            # Create deck from data
            data = df.iloc[:, 0:2].values.tolist()
            deck = create_anki_deck(data, deck_name)
            
            # Create temporary file
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, f"{secure_filename(deck_name)}.apkg")
            
            # Write deck to temporary file
            package = genanki.Package(deck)
            package.write_to_file(temp_path)
            
            # Send file
            try:
                return send_file(
                    temp_path,
                    as_attachment=True,
                    download_name=f"{secure_filename(deck_name)}.apkg",
                    mimetype='application/octet-stream'
                )
            finally:
                # Clean up temporary file
                try:
                    os.remove(temp_path)
                    os.rmdir(temp_dir)
                except:
                    pass

        except Exception as e:
            return render_template('index.html', error=f"Error: {str(e)}")

    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

