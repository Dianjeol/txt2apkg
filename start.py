from flask import Flask, render_template, request, send_file
import pandas as pd
import genanki
import io
import os
import tempfile
import csv

app = Flask(__name__)

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

if __name__ == '__main__':
    app.run(debug=True)
