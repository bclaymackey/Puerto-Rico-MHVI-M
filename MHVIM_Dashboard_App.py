# %% [markdown]
# # MHVI-M Dashboard V6
# This notebook contains the Plotly Dash infrastructure for analyzing the mental health vulnerability index.

# %%
import dash
from dash import dcc, html, Input, Output, State, MATCH, ALL, dash_table
import plotly.express as px
import pandas as pd
import numpy as np
import json
from urllib.request import urlopen
import base64
import sqlite3
import os

# %%
# Load geographical/map data
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    counties = json.load(response)

# Connect to database to fetch metadata
db_path = r'C:\Users\bthem\Documents\AI_Masters\GRA\pr_dashboard.db'

def get_db_connection():
    return sqlite3.connect(db_path)

conn = get_db_connection()
tables_query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('municipalities', 'sqlite_sequence', 'Overall_MHVI_M_Score', 'Data_Dictionary')"
tables = pd.read_sql_query(tables_query, conn)['name'].tolist()

db_metadata = {}
for tbl in tables:
    try:
        inds = pd.read_sql_query(f"SELECT DISTINCT indicator_name FROM {tbl}", conn)['indicator_name'].tolist()
        if inds:
            db_metadata[tbl] = inds
    except Exception as e:
        pass

try:
    muni_df = pd.read_sql_query("SELECT fips_code, name FROM municipalities ORDER BY name", conn)
    all_counties = muni_df.to_dict('records')
except:
    all_counties = []
    
try:
    dict_df = pd.read_sql_query("SELECT * FROM Data_Dictionary", conn)
    data_dictionary_records = dict_df.to_dict('records')
except:
    data_dictionary_records = []
    
conn.close()

available_subcats = list(db_metadata.keys())
global_categories = ['Overall MHVI-M Score'] + available_subcats

# %%
# Helper to encode local images
def encode_image(image_path):
    try:
        with open(image_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('ascii')
        return f'data:image/png;base64,{encoded}'
    except FileNotFoundError:
        return ""

logo1_path = r'C:\Users\bthem\Documents\AI_Masters\GRA\MB_Horz_3Clr.png'
logo2_path = r'C:\Users\bthem\Documents\AI_Masters\GRA\Grupo_nexos.png'
encoded_logo1 = encode_image(logo1_path)
encoded_logo2 = encode_image(logo2_path)

# %%
# Initialize Dash App
app = dash.Dash(__name__, suppress_callback_exceptions=True)

menu_btn_style = {
    'width': '100%', 'padding': '10px', 'marginBottom': '10px', 
    'backgroundColor': '#ffffff', 'border': '1px solid #ccc', 
    'borderRadius': '4px', 'cursor': 'pointer', 'textAlign': 'left',
    'fontWeight': 'bold', 'color': '#333'
}

dropdown_style = {'width': '100%', 'marginBottom': '15px'}

# Inject CSS for printing reports and floating Chatbot
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
            .fab {
                position: fixed; bottom: 20px; right: 20px; width: 60px; height: 60px; 
                background-color: #008CBA; color: white; border-radius: 50%; text-align: center; 
                box-shadow: 2px 2px 10px rgba(0,0,0,0.3); font-size: 30px; cursor: pointer; z-index: 1000;
                display: flex; align-items: center; justify-content: center;
            }
            .fab:hover { background-color: #005f7a; }
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

# Define Layout
app.layout = html.Div([
    
    # Header Container
    html.Div([
        html.Div([
            html.Button("☰", id="left-menu-btn", style={
                'fontSize': '24px', 'backgroundColor': 'transparent', 
                'border': 'none', 'cursor': 'pointer', 'padding': '10px', 'marginRight': '15px'
            }),
            html.Div([
                html.H1("Puerto Rico Mental Health Vulnerability Index for Minors", style={'margin': '0', 'fontFamily': 'Arial'}),
            ]),
            html.Button("ℹ️ Data Dictionary", id='open-help-btn', style={
                'marginLeft': '20px', 'backgroundColor': '#f0f2f5', 'border': '1px solid #ccc',
                'padding': '5px 10px', 'borderRadius': '4px', 'cursor': 'pointer', 'fontWeight': 'bold'
            })
        ], style={'display': 'flex', 'alignItems': 'center'}),
        
        html.Div([
            html.Img(src=encoded_logo1, style={'height': '50px', 'objectFit': 'contain'}),
            html.Span(" | ", style={'fontSize': '30px', 'color': '#ccc', 'margin': '0 15px'}),
            html.Img(src=encoded_logo2, style={'height': '50px', 'objectFit': 'contain'})
        ], style={'display': 'flex', 'alignItems': 'center'})
        
    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'padding': '10px 20px', 'borderBottom': '1px solid #ccc'}),
    
    # General Controls (Top Bar)
    html.Div([
        html.Div([
            html.Label("Category:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
            dcc.Dropdown(
                id='global-category-dropdown',
                options=[{'label': cat.replace('_', ' '), 'value': cat} for cat in global_categories],
                value='Overall MHVI-M Score',
                clearable=False, searchable=True,
                style={'width': '350px'}
            )
        ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '20px'}),
    ], style={'display': 'flex', 'padding': '10px 20px', 'backgroundColor': '#f0f2f5', 'borderBottom': '1px solid #ccc', 'fontFamily': 'Arial'}),

    # Main Content Container (Flexbox)
    html.Div([
        
        # Left column: Navigational Menu
        html.Div(
            id='left-menu-container',
            style={'display': 'none'}, 
            children=[
                html.H3("Navigation", style={'borderBottom': '2px solid #ccc', 'paddingBottom': '10px'}),
                html.Button("Custom Reports", id='open-reports-btn', style=menu_btn_style),
                html.Button("Publication", style=menu_btn_style),
                html.Button("Data Sources", style=menu_btn_style),
                html.Button("Source Code", style=menu_btn_style)
            ]
        ),
        
        # Center column: Interactive Map
        html.Div([
            dcc.Graph(
                id='pr-map', 
                style={'height': '75vh'}
            )
        ], style={'flex': '7', 'padding': '10px', 'minWidth': '0'}), 
        
        # Right column: Dynamic Feature Data Panel
        html.Div(
            id='side-panel-container', 
            style={'display': 'none'}, 
            children=[
                html.Button("✖ Close", id="close-panel-btn", style={
                    'float': 'right', 'backgroundColor': '#ff4d4d', 'color': 'white', 
                    'border': 'none', 'padding': '5px 10px', 'borderRadius': '4px', 'cursor': 'pointer'
                }),
                html.H2(id='county-title', style={'borderBottom': '2px solid #ccc', 'paddingBottom': '10px', 'marginTop': '0'}),
                
                # 2x2 Factor Matrix
                html.Div([
                    # Left Column: Primary Graph (Y-Axis)
                    html.Div([
                        html.Label("Y-Axis Category", style={'fontWeight': 'bold', 'fontSize': '14px'}),
                        dcc.Dropdown(
                            id='y-cat-dropdown',
                            options=[{'label': c.replace('_', ' '), 'value': c} for c in global_categories],
                            value='Overall MHVI-M Score', clearable=False, searchable=True, style=dropdown_style
                        ),
                        html.Label("Y-Axis Indicator(s)", style={'fontWeight': 'bold', 'fontSize': '14px', 'color': '#666'}),
                        dcc.Dropdown(
                            id='y-ind-dropdown',
                            options=[{'label': 'N/A', 'value': 'N/A'}],
                            value=['N/A'], multi=True, disabled=True, searchable=True, style=dropdown_style
                        ),
                        # ML & Normalization Toggles
                        dcc.Checklist(
                            id='graph-options-toggles',
                            options=[
                                {'label': ' Normalize Data (0-100)', 'value': 'normalize'},
                                {'label': ' Predict Future Years (ML)', 'value': 'forecast'}
                            ],
                            value=[],
                            style={'fontSize': '13px', 'marginBottom': '10px', 'display': 'flex', 'flexDirection': 'column', 'gap': '5px'}
                        )
                    ], style={'flex': '1', 'marginRight': '15px'}),
                    
                    # Right Column: Additional Graph
                    html.Div([
                        html.Label("Secondary Category", style={'fontWeight': 'bold', 'fontSize': '14px'}),
                        dcc.Dropdown(
                            id='color-cat-dropdown',
                            options=[{'label': c.replace('_', ' '), 'value': c} for c in ['N/A'] + global_categories],
                            value='N/A', clearable=False, searchable=True, style=dropdown_style
                        ),
                        html.Label("Secondary Indicator", style={'fontWeight': 'bold', 'fontSize': '14px', 'color': '#666'}),
                        dcc.Dropdown(
                            id='color-ind-dropdown',
                            options=[{'label': 'N/A', 'value': 'N/A'}],
                            value='N/A', disabled=True, clearable=False, searchable=True, style=dropdown_style
                        ),
                    ], style={'flex': '1'})
                ], style={'display': 'flex', 'flexDirection': 'row', 'marginBottom': '10px'}),
                
                html.Hr(),
                
                html.Div([
                    dcc.Graph(id='factor-trend-graph', style={'height': '35vh', 'marginBottom': '10px'}),
                    dcc.Graph(id='secondary-trend-graph', style={'height': '35vh', 'display': 'none'})
                ], style={'marginBottom': '20px'}),
                
                html.Hr(),
                html.H4("Index Score Breakdown (2018-2024)", id='index-breakdown-title', style={'marginTop': '0', 'display': 'none'}),
                html.Div(id='index-breakdown-container', style={'display': 'none'}),
                
                html.H4("Subcategory Indicators", id='indicator-table-title', style={'marginTop': '20px'}),
                html.Div(id='indicator-table-container')
            ]
        )
    ], style={'display': 'flex', 'flexDirection': 'row'}),

    # MODAL: Data Dictionary Help
    html.Div(
        id='help-modal',
        style={
            'display': 'none', 'position': 'fixed', 'top': '0', 'left': '0', 'width': '100%', 'height': '100%', 
            'backgroundColor': 'rgba(0,0,0,0.5)', 'zIndex': '2000', 'justifyContent': 'center', 'alignItems': 'center'
        },
        children=[
            html.Div(
                style={
                    'backgroundColor': 'white', 'padding': '30px', 'borderRadius': '8px', 
                    'width': '80%', 'height': '80%', 'overflowY': 'auto', 'position': 'relative'
                },
                children=[
                    html.Button("✖ Close", id="close-help-btn", style={
                        'position': 'absolute', 'top': '15px', 'right': '15px', 
                        'backgroundColor': '#ff4d4d', 'color': 'white', 'border': 'none', 
                        'padding': '8px 12px', 'borderRadius': '4px', 'cursor': 'pointer'
                    }),
                    html.H2("Data Dictionary & Glossary", style={'marginTop': '0', 'borderBottom': '2px solid #ccc', 'paddingBottom': '10px'}),
                    dash_table.DataTable(
                        data=data_dictionary_records,
                        columns=[
                            {'id': 'friendly_name', 'name': 'Indicator Name'},
                            {'id': 'category', 'name': 'Category'},
                            {'id': 'description', 'name': 'Description'},
                            {'id': 'source', 'name': 'Data Source'}
                        ],
                        style_cell={'textAlign': 'left', 'padding': '10px', 'fontFamily': 'Arial'},
                        style_header={'fontWeight': 'bold', 'backgroundColor': '#f0f2f5'},
                        filter_action='native', sort_action='native', page_size=20
                    )
                ]
            )
        ]
    ),

    # MODAL: Custom Report Builder
    html.Div(
        id='custom-reports-modal',
        style={
            'display': 'none', 'position': 'fixed', 'top': '0', 'left': '0', 'width': '100%', 'height': '100%', 
            'backgroundColor': 'rgba(0,0,0,0.5)', 'zIndex': '1000', 'justifyContent': 'center', 'alignItems': 'center'
        },
        children=[
            html.Div(
                style={
                    'backgroundColor': 'white', 'padding': '30px', 'borderRadius': '8px', 
                    'width': '80%', 'height': '80%', 'overflowY': 'auto', 'position': 'relative'
                },
                children=[
                    html.Button("✖ Close", id="close-modal-btn", className="no-print", style={
                        'position': 'absolute', 'top': '15px', 'right': '15px', 
                        'backgroundColor': '#ff4d4d', 'color': 'white', 'border': 'none', 
                        'padding': '8px 12px', 'borderRadius': '4px', 'cursor': 'pointer'
                    }),
                    html.H2("Custom Report Builder", style={'marginTop': '0', 'borderBottom': '2px solid #ccc', 'paddingBottom': '10px'}),
                    
                    html.Div(id='report-elements-container', children=[], style={'marginBottom': '20px'}),
                    
                    html.Div([
                        html.Button("+ Add Element", id='add-report-element-btn', className="no-print", style={
                            'padding': '10px 15px', 'backgroundColor': '#4CAF50', 'color': 'white', 
                            'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer', 'marginRight': '10px'
                        }),
                        html.Button("Export to PDF", id='export-pdf-btn', className="no-print", style={
                            'padding': '10px 15px', 'backgroundColor': '#008CBA', 'color': 'white', 
                            'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer'
                        })
                    ], className="no-print", style={'borderTop': '1px solid #eee', 'paddingTop': '20px'})
                ]
            )
        ]
    ),
    
    # CHATBOT FAB
    html.Div("💬", id='chatbot-fab', className='fab'),
    html.Div(
        id='chatbot-drawer',
        style={
            'position': 'fixed', 'bottom': '90px', 'right': '20px', 'width': '350px', 'height': '500px',
            'backgroundColor': 'white', 'boxShadow': '0 4px 15px rgba(0,0,0,0.2)', 'borderRadius': '8px',
            'display': 'none', 'zIndex': '1000', 'flexDirection': 'column'
        },
        children=[
            html.Div([
                html.H4("Chatbot Assistant", style={'margin': '0'}),
                html.Button("✖", id='close-chatbot-btn', style={'border': 'none', 'background': 'none', 'cursor': 'pointer'})
            ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'padding': '15px', 'borderBottom': '1px solid #eee', 'backgroundColor': '#f0f2f5', 'borderTopLeftRadius': '8px', 'borderTopRightRadius': '8px'}),
            html.Div(
                id='chatbot-iframe-container',
                children=[html.P("Chatbot widget will be embedded here.", style={'textAlign': 'center', 'color': '#888', 'marginTop': '50px'})],
                style={'flex': '1', 'padding': '15px', 'overflowY': 'auto'}
            )
        ]
    )

], style={'fontFamily': 'Arial'})

db_metadata_json = json.dumps(db_metadata)

# %%
# Callbacks
@app.callback(
    Output('pr-map', 'figure'),
    Input('global-category-dropdown', 'value')
)
def update_map(category):
    conn = get_db_connection()
    if category == 'Overall MHVI-M Score':
        target_table = 'Overall_MHVI_M_Score'
        ind = 'Overall MHVI-M Score'
    else:
        target_table = category
        ind = 'Subcategory Index Score'
    
    try:
        df = pd.read_sql(f"""
            SELECT m.fips_code, m.name, t.value 
            FROM {target_table} t 
            JOIN municipalities m ON t.fips_code = m.fips_code 
            WHERE t.indicator_name = '{ind}' AND t.year = (SELECT MAX(year) FROM {target_table})
        """, conn)
    except:
        df = pd.DataFrame(columns=['fips_code', 'value', 'name'])
    finally:
        conn.close()
        
    if df.empty:
        fig = px.choropleth_map(geojson=counties, locations=[], map_style="carto-positron", zoom=7.5, center={"lat": 18.2208, "lon": -66.5901})
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        return fig
        
    fig = px.choropleth_map(
        df,
        geojson=counties,
        locations='fips_code',
        color='value',
        hover_name='name',
        color_continuous_scale="Viridis_r",
        map_style="carto-positron",
        zoom=7.5,
        center={"lat": 18.2208, "lon": -66.5901},
        opacity=0.8,
        hover_data={'fips_code': False, 'value': True}
    )
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return fig

@app.callback(
    [Output('y-ind-dropdown', 'options'), Output('y-ind-dropdown', 'value'), Output('y-ind-dropdown', 'disabled')],
    Input('y-cat-dropdown', 'value')
)
def update_y_indicator(y_cat):
    metadata = json.loads(db_metadata_json)
    
    if y_cat in ['N/A', 'Overall MHVI-M Score']:
        return [{'label': 'N/A', 'value': 'N/A'}], ['N/A'], True
        
    indicators = metadata.get(y_cat, [])
    options = [{'label': i.replace('_', ' '), 'value': i} for i in indicators]
    val = [indicators[0]] if indicators else ['N/A']
    return options, val, False

@app.callback(
    Output('indicator-table-container', 'children'),
    [Input('pr-map', 'clickData'), Input('y-cat-dropdown', 'value')]
)
def update_indicator_table(clickData, y_cat):
    if not clickData or y_cat in ['N/A', 'Overall MHVI-M Score']:
        return html.P("Select a Subcategory and Municipality to view indicator data points.")
        
    clicked_fips = clickData['points'][0]['location']
    metadata = json.loads(db_metadata_json)
    indicators = metadata.get(y_cat, [])
    
    conn = get_db_connection()
    accordion_items = []
    
    for ind in indicators:
        if ind == 'Subcategory Index Score':
            continue
            
        try:
            df = pd.read_sql(f"SELECT year, value FROM {y_cat} WHERE fips_code = '{clicked_fips}' AND indicator_name = '{ind}' ORDER BY year", conn)
        except:
            df = pd.DataFrame(columns=['year', 'value'])
            
        if not df.empty:
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df['value'] = df['value'].apply(lambda x: round(float(x), 4) if pd.notnull(x) else x)
            table = dash_table.DataTable(
                data=df.to_dict('records'),
                columns=[{'id': 'year', 'name': 'Year'}, {'id': 'value', 'name': 'Value'}],
                style_cell={'textAlign': 'center', 'padding': '5px'},
                style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'}
            )
        else:
            table = html.P("No data points available.", style={'color': '#888', 'fontStyle': 'italic'})
            
        # Create a "Plot" button to quickly map this indicator
        plot_btn = html.Button("📈 Plot", id={'type': 'plot-ind-btn', 'index': ind}, style={
            'marginLeft': '15px', 'backgroundColor': '#008CBA', 'color': 'white', 'border': 'none',
            'borderRadius': '3px', 'cursor': 'pointer', 'padding': '2px 8px', 'fontSize': '12px'
        })
            
        details = html.Details([
            html.Summary(html.Div([html.Span(ind.replace('_', ' ')), plot_btn], style={'display': 'inline-flex', 'alignItems': 'center'}), style={
                'fontWeight': 'bold', 'cursor': 'pointer', 'padding': '10px', 
                'backgroundColor': '#f0f2f5', 'borderBottom': '1px solid #ccc', 'outline': 'none'
            }),
            html.Div(table, style={'padding': '10px', 'backgroundColor': 'white', 'borderLeft': '1px solid #ccc', 'borderRight': '1px solid #ccc'})
        ], style={'marginBottom': '5px'})
        
        accordion_items.append(details)
        
    conn.close()
    return html.Div(accordion_items)

# Listen to the mini plot buttons
@app.callback(
    Output('y-ind-dropdown', 'value', allow_duplicate=True),
    Input({'type': 'plot-ind-btn', 'index': ALL}, 'n_clicks'),
    State('y-ind-dropdown', 'value'),
    prevent_initial_call=True
)
def handle_plot_btn_clicks(n_clicks, current_y_inds):
    ctx = dash.ctx
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    
    btn_id = json.loads(ctx.triggered[0]['prop_id'].split('.')[0])
    ind_clicked = btn_id['index']
    
    # Check if we should append or just set it
    if current_y_inds and isinstance(current_y_inds, list):
        if ind_clicked not in current_y_inds:
            # If "N/A" is in there, remove it
            res = [i for i in current_y_inds if i != 'N/A'] + [ind_clicked]
            return res
        return current_y_inds
    return [ind_clicked]

@app.callback(
    [Output('index-breakdown-title', 'style'), Output('index-breakdown-container', 'style'), Output('index-breakdown-container', 'children')],
    [Input('pr-map', 'clickData'), Input('y-cat-dropdown', 'value')]
)
def update_index_breakdown(clickData, y_cat):
    if not clickData or y_cat in ['N/A', 'Overall MHVI-M Score']:
        return {'display': 'none'}, {'display': 'none'}, []
        
    clicked_fips = clickData['points'][0]['location']
    
    conn = get_db_connection()
    try:
        # Get count of non-null values for each indicator in this category for this county
        df = pd.read_sql(f"SELECT indicator_name, COUNT(value) as obs_count FROM {y_cat} WHERE fips_code = '{clicked_fips}' GROUP BY indicator_name", conn)
    except:
        df = pd.DataFrame(columns=['indicator_name', 'obs_count'])
    finally:
        conn.close()
        
    if df.empty:
        return {'display': 'none'}, {'display': 'none'}, []
        
    included = df[df['obs_count'] > 0]['indicator_name'].tolist()
    excluded = df[df['obs_count'] == 0]['indicator_name'].tolist()
    
    # We want to omit "Subcategory Index Score" from these lists
    included = [i for i in included if i != 'Subcategory Index Score']
    excluded = [i for i in excluded if i != 'Subcategory Index Score']
    
    # Also grab metadata to see if any indicators completely missing from DB for this county
    metadata = json.loads(db_metadata_json)
    all_inds = [i for i in metadata.get(y_cat, []) if i != 'Subcategory Index Score']
    for i in all_inds:
        if i not in included and i not in excluded:
            excluded.append(i)
            
    content = html.Div([
        html.Div([
            html.H5("Included (Data Present)", style={'color': 'green', 'marginTop': '0'}),
            html.Ul([html.Li(i.replace('_', ' ')) for i in included] if included else [html.Li("None")])
        ], style={'flex': '1', 'backgroundColor': '#e8f5e9', 'padding': '10px', 'borderRadius': '4px', 'marginRight': '10px'}),
        html.Div([
            html.H5("Excluded (Missing/Null)", style={'color': 'red', 'marginTop': '0'}),
            html.Ul([html.Li(i.replace('_', ' ')) for i in excluded] if excluded else [html.Li("None")])
        ], style={'flex': '1', 'backgroundColor': '#ffebee', 'padding': '10px', 'borderRadius': '4px'})
    ], style={'display': 'flex', 'flexDirection': 'row'})
    
    return {'marginTop': '0', 'display': 'block'}, {'display': 'block', 'marginBottom': '20px'}, content

@app.callback(
    [Output('color-ind-dropdown', 'options'), Output('color-ind-dropdown', 'value'), Output('color-ind-dropdown', 'disabled')],
    Input('color-cat-dropdown', 'value')
)
def update_color_indicator(color_cat):
    if color_cat in ['N/A', 'Overall MHVI-M Score']:
        return [{'label': 'N/A', 'value': 'N/A'}], 'N/A', True
        
    metadata = json.loads(db_metadata_json)
    indicators = metadata.get(color_cat, [])
    options = [{'label': i.replace('_', ' '), 'value': i} for i in indicators]
    val = indicators[0] if indicators else 'N/A'
    return options, val, False

@app.callback(
    Output('left-menu-container', 'style'),
    Input('left-menu-btn', 'n_clicks'),
    State('left-menu-container', 'style') 
)
def toggle_left_menu(n_clicks, current_style):
    if n_clicks is None:
        raise dash.exceptions.PreventUpdate
    open_style = {
        'flex': '2', 'padding': '20px', 'backgroundColor': '#f0f2f5', 
        'borderRight': '1px solid #ccc', 'fontFamily': 'Arial', 
        'height': '68vh', 'display': 'flex', 'flexDirection': 'column',
        'minWidth': '0'
    }
    if current_style and current_style.get('display') == 'none':
        return open_style
    else:
        return {'display': 'none'}

@app.callback(
    Output('side-panel-container', 'style'),
    [Input('pr-map', 'clickData'), 
     Input('close-panel-btn', 'n_clicks')]
)
def toggle_right_panel(map_click, close_click):
    trigger_id = dash.ctx.triggered_id
    if not trigger_id:
        return {'display': 'none'} 
    open_style = {
        'flex': '4', 'padding': '20px', 'backgroundColor': '#f8f9fa', 
        'borderLeft': '1px solid #ccc', 'fontFamily': 'Arial', 
        'height': '75vh', 'overflowY': 'auto',
        'display': 'flex', 'flexDirection': 'column',
        'minWidth': '0'
    }
    if trigger_id == 'close-panel-btn':
        return {'display': 'none'}
    elif trigger_id == 'pr-map' and map_click is not None:
        return open_style
    return {'display': 'none'}

@app.callback(
    Output('help-modal', 'style'),
    [Input('open-help-btn', 'n_clicks'), Input('close-help-btn', 'n_clicks')],
    State('help-modal', 'style')
)
def toggle_help_modal(open_clicks, close_clicks, style):
    trigger = dash.ctx.triggered_id
    if trigger == 'open-help-btn':
        style['display'] = 'flex'
    elif trigger == 'close-help-btn':
        style['display'] = 'none'
    return style

@app.callback(
    Output('chatbot-drawer', 'style'),
    [Input('chatbot-fab', 'n_clicks'), Input('close-chatbot-btn', 'n_clicks')],
    State('chatbot-drawer', 'style')
)
def toggle_chatbot(open_clicks, close_clicks, style):
    trigger = dash.ctx.triggered_id
    if trigger == 'chatbot-fab':
        if style.get('display') == 'none':
            style['display'] = 'flex'
        else:
            style['display'] = 'none'
    elif trigger == 'close-chatbot-btn':
        style['display'] = 'none'
    return style


def query_axis_data(fips, cat, ind):
    conn = get_db_connection()
    if cat == 'Year':
        try:
            years_df = pd.read_sql("SELECT DISTINCT year FROM Economic_Employment ORDER BY year", conn) 
            years_df['val'] = years_df['year']
            return years_df
        except:
            return pd.DataFrame({'year': [2018, 2019, 2020, 2021, 2022, 2023, 2024], 'val': [2018, 2019, 2020, 2021, 2022, 2023, 2024]})
        finally:
            conn.close()
    elif cat == 'Overall MHVI-M Score':
        try:
            df = pd.read_sql(f"SELECT year, value as val FROM Overall_MHVI_M_Score WHERE fips_code = '{fips}'", conn)
        except:
            df = pd.DataFrame(columns=['year', 'val'])
        finally:
            conn.close()
        return df
    else:
        try:
            df = pd.read_sql(f"SELECT year, value as val FROM {cat} WHERE fips_code = '{fips}' AND indicator_name = '{ind}'", conn)
        except:
            df = pd.DataFrame(columns=['year', 'val'])
        finally:
            conn.close()
        return df

@app.callback(
    [Output('county-title', 'children'), 
     Output('factor-trend-graph', 'figure'),
     Output('secondary-trend-graph', 'figure'),
     Output('secondary-trend-graph', 'style')],
    [Input('pr-map', 'clickData'), Input('y-cat-dropdown', 'value'), Input('y-ind-dropdown', 'value'),
     Input('color-cat-dropdown', 'value'), Input('color-ind-dropdown', 'value'),
     Input('graph-options-toggles', 'value')]
)
def update_dynamic_plot(clickData, y_cat, y_ind_list, sec_cat, sec_ind, options_toggles):
    if clickData is None:
        raise dash.exceptions.PreventUpdate
        
    clicked_fips = clickData['points'][0]['location']
    
    conn = get_db_connection()
    try:
        muni_name = pd.read_sql_query(f"SELECT name FROM municipalities WHERE fips_code = '{clicked_fips}'", conn).iloc[0]['name']
    except:
        muni_name = "Unknown Municipality"
    finally:
        conn.close()
    
    options_toggles = options_toggles or []
    do_normalize = 'normalize' in options_toggles
    do_forecast = 'forecast' in options_toggles
    
    # Process Base Y-Axis
    df_y_all = pd.DataFrame()
    
    if not isinstance(y_ind_list, list):
        y_ind_list = [y_ind_list]
        
    for ind in y_ind_list:
        if ind == 'N/A' and y_cat != 'Overall MHVI-M Score':
            continue
            
        # Overall Score uses a dummy ind
        if y_cat == 'Overall MHVI-M Score':
            ind = 'Overall MHVI-M Score'
            
        df_y = query_axis_data(clicked_fips, y_cat, ind)
        if not df_y.empty:
            df_y = df_y.sort_values(by='year')
            df_y['indicator'] = ind.replace('_', ' ')
            
            # Normalize
            if do_normalize and df_y['val'].max() != df_y['val'].min():
                vmin, vmax = df_y['val'].min(), df_y['val'].max()
                df_y['val'] = ((df_y['val'] - vmin) / (vmax - vmin)) * 100
                
            # Forecast (Numpy Polyfit)
            if do_forecast and len(df_y) >= 3:
                x = df_y['year'].astype(float).values
                y = df_y['val'].astype(float).values
                z = np.polyfit(x, y, 1)
                p = np.poly1d(z)
                future_years = [2025, 2026, 2027, 2028]
                future_vals = p(future_years)
                
                # Append projections
                forecast_df = pd.DataFrame({
                    'year': future_years,
                    'val': future_vals,
                    'indicator': [ind.replace('_', ' ') + ' (Forecast)'] * len(future_years)
                })
                df_y = pd.concat([df_y, forecast_df])
                
            df_y_all = pd.concat([df_y_all, df_y])
            
        if y_cat == 'Overall MHVI-M Score':
            break # only run once for overall score
            
    if df_y_all.empty:
        fig1 = px.scatter(title="No Y-Axis Data Found")
    else:
        y_title = "Normalized Value (0-100)" if do_normalize else "Value"
        # Standardize styling for forecasts vs actuals
        fig1 = px.line(df_y_all, x='year', y='val', color='indicator', markers=True)
        
        # Make forecasts dashed
        for trace in fig1.data:
            if 'Forecast' in trace.name:
                trace.line.dash = 'dash'
                
        fig1.update_layout(
            margin={"r":0,"t":30,"l":0,"b":0}, paper_bgcolor='#f8f9fa', plot_bgcolor='#f8f9fa', 
            xaxis=dict(title="Year", type='category'), yaxis=dict(title=y_title),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
    # Secondary Graph Logic
    fig2 = px.scatter() # Empty placeholder
    style2 = {'display': 'none'}
    
    if sec_cat != 'N/A' and sec_ind != 'N/A':
        df_sec = query_axis_data(clicked_fips, sec_cat, sec_ind)
        if not df_sec.empty:
            df_sec = df_sec.sort_values(by='year')
            label_sec = sec_ind.replace('_', ' ') if sec_cat not in ['Overall MHVI-M Score'] else sec_cat
            df_sec['indicator'] = label_sec
            
            if do_normalize and df_sec['val'].max() != df_sec['val'].min():
                vmin, vmax = df_sec['val'].min(), df_sec['val'].max()
                df_sec['val'] = ((df_sec['val'] - vmin) / (vmax - vmin)) * 100
                
            if do_forecast and len(df_sec) >= 3:
                x = df_sec['year'].astype(float).values
                y = df_sec['val'].astype(float).values
                z = np.polyfit(x, y, 1)
                p = np.poly1d(z)
                future_years = [2025, 2026, 2027, 2028]
                future_vals = p(future_years)
                forecast_df = pd.DataFrame({
                    'year': future_years,
                    'val': future_vals,
                    'indicator': [label_sec + ' (Forecast)'] * len(future_years)
                })
                df_sec = pd.concat([df_sec, forecast_df])
                
            fig2 = px.line(df_sec, x='year', y='val', color='indicator', markers=True)
            for trace in fig2.data:
                if 'Forecast' in trace.name:
                    trace.line.dash = 'dash'
                    
            y2_title = "Normalized Value (0-100)" if do_normalize else label_sec
            fig2.update_layout(
                margin={"r":0,"t":10,"l":0,"b":0}, paper_bgcolor='#f8f9fa', plot_bgcolor='#f8f9fa', 
                xaxis=dict(title="Year", type='category'), yaxis=dict(title=y2_title),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            style2 = {'height': '35vh', 'display': 'block', 'borderTop': '2px dashed #ccc', 'paddingTop': '10px'}
            
    return muni_name, fig1, fig2, style2


# =========================================================
# REPORT BUILDER CALLBACKS
# =========================================================

@app.callback(
    Output('custom-reports-modal', 'style', allow_duplicate=True),
    [Input('open-reports-btn', 'n_clicks'), Input('close-modal-btn', 'n_clicks')],
    State('custom-reports-modal', 'style'),
    prevent_initial_call=True
)
def toggle_reports_modal(open_clicks, close_clicks, style):
    trigger = dash.ctx.triggered_id
    if trigger == 'open-reports-btn':
        style['display'] = 'flex'
    elif trigger == 'close-modal-btn':
        style['display'] = 'none'
    return style

@app.callback(
    Output('report-elements-container', 'children'),
    Input('add-report-element-btn', 'n_clicks'),
    State('report-elements-container', 'children')
)
def add_report_element(n_clicks, children):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
        
    new_element = html.Div(
        id={'type': 'report-block', 'index': n_clicks},
        className='print-page-break',
        style={'border': '1px solid #ddd', 'padding': '15px', 'marginBottom': '15px', 'borderRadius': '5px'},
        children=[
            html.Div(className='no-print', children=[
                html.Label("Element Type:", style={'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id={'type': 'report-type', 'index': n_clicks},
                    options=[
                        {'label': 'Line Graph', 'value': 'Graph'}, 
                        {'label': 'Data Table', 'value': 'Table'},
                        {'label': 'Index Breakdown Table', 'value': 'Breakdown'}
                    ],
                    value='Graph', clearable=False, style={'marginBottom': '10px'}
                ),
                html.Label("Select Municipalities:", style={'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id={'type': 'report-county', 'index': n_clicks},
                    options=[{'label': c['name'], 'value': c['fips_code']} for c in all_counties],
                    multi=True, placeholder="Select counties...", style={'marginBottom': '10px'}
                ),
                html.Label("Category:", style={'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id={'type': 'report-cat', 'index': n_clicks},
                    options=[{'label': c.replace('_', ' '), 'value': c} for c in global_categories],
                    value='Overall MHVI-M Score', clearable=False, style={'marginBottom': '10px'}
                ),
                html.Label("Indicator:", style={'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id={'type': 'report-ind', 'index': n_clicks},
                    options=[{'label': 'N/A', 'value': 'N/A'}],
                    value='N/A', disabled=True, clearable=False, style={'marginBottom': '10px'}
                ),
                dcc.Checklist(
                    id={'type': 'report-options', 'index': n_clicks},
                    options=[
                        {'label': ' Normalize Data (0-100)', 'value': 'normalize'},
                        {'label': ' Predict Future Years (ML)', 'value': 'forecast'}
                    ],
                    value=[],
                    style={'fontSize': '13px', 'marginBottom': '10px'}
                ),
                html.Button("✖ Remove Element", id={'type': 'remove-element-btn', 'index': n_clicks}, style={
                    'backgroundColor': '#ff4d4d', 'color': 'white', 'border': 'none', 'padding': '5px 10px', 
                    'borderRadius': '4px', 'cursor': 'pointer', 'marginTop': '10px'
                }),
                html.Hr()
            ]),
            # Output display
            html.Div(id={'type': 'report-output', 'index': n_clicks})
        ]
    )
    children.append(new_element)
    return children

@app.callback(
    Output({'type': 'report-block', 'index': MATCH}, 'style'),
    Input({'type': 'remove-element-btn', 'index': MATCH}, 'n_clicks'),
    State({'type': 'report-block', 'index': MATCH}, 'style')
)
def remove_element(n_clicks, style):
    if n_clicks:
        style['display'] = 'none'
    return style

@app.callback(
    [Output({'type': 'report-ind', 'index': MATCH}, 'options'),
     Output({'type': 'report-ind', 'index': MATCH}, 'value'),
     Output({'type': 'report-ind', 'index': MATCH}, 'disabled')],
    Input({'type': 'report-cat', 'index': MATCH}, 'value')
)
def update_report_indicator(cat):
    if cat in ['N/A', 'Overall MHVI-M Score']:
        return [{'label': 'N/A', 'value': 'N/A'}], 'N/A', True
        
    metadata = json.loads(db_metadata_json)
    indicators = metadata.get(cat, [])
    options = [{'label': i.replace('_', ' '), 'value': i} for i in indicators]
    val = indicators[0] if indicators else 'N/A'
    return options, val, False

@app.callback(
    Output({'type': 'report-output', 'index': MATCH}, 'children'),
    [Input({'type': 'report-type', 'index': MATCH}, 'value'),
     Input({'type': 'report-county', 'index': MATCH}, 'value'),
     Input({'type': 'report-cat', 'index': MATCH}, 'value'),
     Input({'type': 'report-ind', 'index': MATCH}, 'value'),
     Input({'type': 'report-options', 'index': MATCH}, 'value')]
)
def render_report_element(rtype, counties_list, cat, ind, options):
    if not counties_list:
        return html.P("Please select at least one municipality.", style={'fontStyle': 'italic', 'color': '#666'})
        
    options = options or []
    do_normalize = 'normalize' in options
    do_forecast = 'forecast' in options
    
    # Translate FIPS to Names
    conn = get_db_connection()
    try:
        fips_str = "','".join(counties_list)
        names_df = pd.read_sql(f"SELECT fips_code, name FROM municipalities WHERE fips_code IN ('{fips_str}')", conn)
        name_map = dict(zip(names_df['fips_code'], names_df['name']))
    except:
        name_map = {c: c for c in counties_list}
        
    if rtype == 'Breakdown':
        blocks = []
        for fips in counties_list:
            county_name = name_map.get(fips, fips)
            try:
                df = pd.read_sql(f"SELECT indicator_name, COUNT(value) as obs_count FROM {cat} WHERE fips_code = '{fips}' GROUP BY indicator_name", conn)
            except:
                df = pd.DataFrame()
                
            if df.empty:
                blocks.append(html.P(f"No breakdown available for {county_name}"))
                continue
                
            included = [i for i in df[df['obs_count'] > 0]['indicator_name'].tolist() if i != 'Subcategory Index Score']
            excluded = [i for i in df[df['obs_count'] == 0]['indicator_name'].tolist() if i != 'Subcategory Index Score']
            
            # Check DB metadata for totally missing cols
            metadata = json.loads(db_metadata_json)
            all_inds = [i for i in metadata.get(cat, []) if i != 'Subcategory Index Score']
            for i in all_inds:
                if i not in included and i not in excluded:
                    excluded.append(i)
                    
            content = html.Div([
                html.H4(f"Breakdown for {county_name}"),
                html.Div([
                    html.Div([
                        html.H5("Included (Data Present)", style={'color': 'green', 'marginTop': '0'}),
                        html.Ul([html.Li(i.replace('_', ' ')) for i in included] if included else [html.Li("None")])
                    ], style={'flex': '1', 'backgroundColor': '#e8f5e9', 'padding': '10px', 'borderRadius': '4px', 'marginRight': '10px'}),
                    html.Div([
                        html.H5("Excluded (Missing/Null)", style={'color': 'red', 'marginTop': '0'}),
                        html.Ul([html.Li(i.replace('_', ' ')) for i in excluded] if excluded else [html.Li("None")])
                    ], style={'flex': '1', 'backgroundColor': '#ffebee', 'padding': '10px', 'borderRadius': '4px'})
                ], style={'display': 'flex', 'flexDirection': 'row'})
            ], style={'marginBottom': '20px'})
            blocks.append(content)
        conn.close()
        return html.Div(blocks)
    
    # Otherwise graphing/table logic
    combined_df = pd.DataFrame()
    for fips in counties_list:
        df = query_axis_data(fips, cat, ind)
        if not df.empty:
            df['County'] = name_map.get(fips, fips)
            
            if do_normalize and df['val'].max() != df['val'].min():
                vmin, vmax = df['val'].min(), df['val'].max()
                df['val'] = ((df['val'] - vmin) / (vmax - vmin)) * 100
                
            if do_forecast and len(df) >= 3:
                x = df['year'].astype(float).values
                y = df['val'].astype(float).values
                z = np.polyfit(x, y, 1)
                p = np.poly1d(z)
                future_years = [2025, 2026, 2027, 2028]
                future_vals = p(future_years)
                forecast_df = pd.DataFrame({
                    'year': future_years,
                    'val': future_vals,
                    'County': [df['County'].iloc[0] + ' (Forecast)'] * len(future_years)
                })
                df = pd.concat([df, forecast_df])
                
            combined_df = pd.concat([combined_df, df])
    conn.close()
    
    if combined_df.empty:
        return html.P("No data available for the selected parameters.")
        
    combined_df = combined_df.sort_values(by='year')
    label = ind.replace('_', ' ') if cat != 'Overall MHVI-M Score' else cat
    
    if rtype == 'Graph':
        y_title = "Normalized Value (0-100)" if do_normalize else label
        fig = px.line(combined_df, x='year', y='val', color='County', markers=True, title=f"Comparison: {label}")
        for trace in fig.data:
            if 'Forecast' in trace.name:
                trace.line.dash = 'dash'
        fig.update_layout(xaxis=dict(title="Year", type='category'), yaxis=dict(title=y_title), paper_bgcolor='white', plot_bgcolor='white')
        return dcc.Graph(figure=fig)
    else:
        # Pivot table
        pivot = combined_df.pivot(index='year', columns='County', values='val').reset_index()
        return html.Div([
            html.H3(f"Data Table: {label}"),
            dash_table.DataTable(
                data=pivot.to_dict('records'),
                columns=[{'id': str(c), 'name': str(c)} for c in pivot.columns],
                style_cell={'textAlign': 'center', 'padding': '5px'},
                style_header={'fontWeight': 'bold', 'backgroundColor': '#f0f2f5'}
            )
        ])

# Client-side callback to trigger print dialog natively
app.clientside_callback(
    """
    function(n_clicks) {
        if(n_clicks > 0) {
            window.print();
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("export-pdf-btn", "n_clicks_timestamp"), # Dummy output to satisfy dash
    Input("export-pdf-btn", "n_clicks")
)

# %%
if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, port=8056)
