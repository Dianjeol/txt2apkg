from flask import Flask, render_template, request, send_file
import genanki
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

def parse_content(content, delimiter):
    """Parse the content into a list of card pairs"""
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    cards = []
    for row in reader:
        if len(row) >= 2:
            cards.append([row[0], row[1]])
    return cards

def create_anki_deck(data, deck_name="My Flashcards"):
    """Create an Anki deck from the provided data"""
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
            content = ""
            if 'file' in request.files and request.files['file'].filename:
                file = request.files['file']
                content = file.read().decode('utf-8')
            else:
                content = request.form.get('text', '')

            if not content.strip():
                return render_template('index.html', error="Please provide input text or upload a file")

            delimiter = detect_delimiter(content)
            data = parse_content(content, delimiter)

            if not data:
                return render_template('index.html', 
                                     error="Input must have at least 2 columns (front and back of cards)")

            deck = create_anki_deck(data, deck_name)
            
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, f"{secure_filename(deck_name)}.apkg")
            
            package = genanki.Package(deck)
            package.write_to_file(temp_path)
            
            try:
                return send_file(
                    temp_path,
                    as_attachment=True,
                    download_name=f"{secure_filename(deck_name)}.apkg",
                    mimetype='application/octet-stream'
                )
            finally:
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

