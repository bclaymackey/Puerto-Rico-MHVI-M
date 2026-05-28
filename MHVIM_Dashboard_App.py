import dash
import base64
from pathlib import Path
from data import load_db_metadata, load_data_dictionary
from layout import build_layout
from callbacks import register_callbacks


def encode_image(path):
    try:
        return f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}"
    except FileNotFoundError:
        return ""


app = dash.Dash(__name__, suppress_callback_exceptions=True)

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            @media print {
                body * { visibility: hidden; }
                #custom-reports-modal, #custom-reports-modal * { visibility: visible; }
                #custom-reports-modal { position: absolute; left: 0; top: 0; width: 100%; padding: 0; margin: 0; background: white; z-index: 9999; }
                .no-print { display: none !important; }
                .print-page-break { page-break-after: always; }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

db_metadata = load_db_metadata()
data_dictionary_df = load_data_dictionary()
global_categories = ['Overall MHVI-M Score'] + list(db_metadata.keys())

_root = Path(__file__).parent
app.layout = lambda: build_layout(
    global_categories,
    encode_image(_root / 'assets' / 'logos' / 'MB_Horz_3Clr.png'),
    encode_image(_root / 'assets' / 'logos' / 'Grupo_nexos.png')
)

register_callbacks(app, db_metadata, data_dictionary_df=data_dictionary_df)

if __name__ == '__main__':
    app.run(debug=True)
