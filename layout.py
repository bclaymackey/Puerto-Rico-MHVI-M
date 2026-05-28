import uuid

from dash import dcc, html, dash_table


def build_layout(global_categories: list, encoded_logo1: str, encoded_logo2: str) -> html.Div:
    return html.Div([
        _header(encoded_logo1, encoded_logo2),
        _top_bar(global_categories),
        _main_content(global_categories),
        _help_modal(),
        _custom_reports_modal(global_categories),
    ], style={'fontFamily': 'Arial'})


def _header(logo1_src: str, logo2_src: str) -> html.Div:
    return html.Div([
        html.Div([
            html.Button('☰', id='left-menu-btn', style={
                'fontSize': '24px', 'backgroundColor': 'transparent',
                'border': 'none', 'cursor': 'pointer', 'padding': '10px', 'marginRight': '15px'
            }),
            html.Div([
                html.H1('Puerto Rico Mental Health Vulnerability Index for Minors',
                        style={'margin': '0', 'fontFamily': 'Arial'}),
            ])
        ], style={'display': 'flex', 'alignItems': 'center'}),

        html.Div([
            html.Button(
                'ℹ️ Data Dictionary',
                id='open-help-btn',
                n_clicks=0,
                style={'display': 'none'},
            ),
            html.Img(src=logo1_src, style={'height': '50px', 'objectFit': 'contain'}),
            html.Span(' | ', style={'fontSize': '30px', 'color': '#ccc', 'margin': '0 15px'}),
            html.Img(src=logo2_src, style={'height': '50px', 'objectFit': 'contain'})
        ], style={'display': 'flex', 'alignItems': 'center'})

    ], style={
        'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between',
        'padding': '10px 20px', 'borderBottom': '1px solid #ccc'
    })


def _top_bar(global_categories: list) -> html.Div:
    return html.Div([
        html.Div([
            html.Label('Category:', style={'fontWeight': 'bold', 'marginRight': '10px'}),
            dcc.Dropdown(
                id='global-category-dropdown',
                options=[{'label': cat.replace('_', ' '), 'value': cat} for cat in global_categories],
                value='Overall MHVI-M Score',
                clearable=False,
                style={'width': '350px'}
            )
        ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '20px'}),
    ], style={
        'display': 'flex', 'padding': '10px 20px', 'backgroundColor': '#f0f2f5',
        'borderBottom': '1px solid #ccc', 'fontFamily': 'Arial'
    })


def _left_menu() -> html.Div:
    return html.Div(
        id='left-menu-container',
        style={'display': 'none'},
        children=[
            html.H3('Navigation', style={'borderBottom': '2px solid #ccc', 'paddingBottom': '10px'}),
            html.Button('Custom Reports', id='open-custom-reports-btn', n_clicks=0, style={
                'width': '100%', 'padding': '10px', 'marginBottom': '10px',
                'backgroundColor': '#ffffff', 'border': '1px solid #ccc',
                'borderRadius': '4px', 'cursor': 'pointer', 'textAlign': 'left',
                'fontWeight': 'bold', 'color': '#333'
            }),
            html.Button('Publication', style={
                'width': '100%', 'padding': '10px', 'marginBottom': '10px',
                'backgroundColor': '#ffffff', 'border': '1px solid #ccc',
                'borderRadius': '4px', 'cursor': 'pointer', 'textAlign': 'left',
                'fontWeight': 'bold', 'color': '#333'
            }),
            html.Button('Data Sources', style={
                'width': '100%', 'padding': '10px', 'marginBottom': '10px',
                'backgroundColor': '#ffffff', 'border': '1px solid #ccc',
                'borderRadius': '4px', 'cursor': 'pointer', 'textAlign': 'left',
                'fontWeight': 'bold', 'color': '#333'
            }),
            html.Button('Source Code', style={
                'width': '100%', 'padding': '10px', 'marginBottom': '10px',
                'backgroundColor': '#ffffff', 'border': '1px solid #ccc',
                'borderRadius': '4px', 'cursor': 'pointer', 'textAlign': 'left',
                'fontWeight': 'bold', 'color': '#333'
            })
        ]
    )


def _right_panel(global_categories: list) -> html.Div:
    return html.Div(
        id='side-panel-container',
        style={'display': 'none'},
        children=[
            html.Button('✖ Close', id='close-panel-btn', style={
                'float': 'right', 'backgroundColor': '#ff4d4d', 'color': 'white',
                'border': 'none', 'padding': '5px 10px', 'borderRadius': '4px', 'cursor': 'pointer'
            }),
            html.H2(id='county-title', style={
                'borderBottom': '2px solid #ccc', 'paddingBottom': '10px', 'marginTop': '0'
            }),

            html.Div([
                html.Div([
                    html.Label('Y-Axis Category', style={'fontWeight': 'bold', 'fontSize': '14px'}),
                    dcc.Dropdown(
                        id='y-cat-dropdown',
                        options=[{'label': c.replace('_', ' '), 'value': c} for c in global_categories],
                        value='Overall MHVI-M Score', clearable=False,
                        style={'width': '100%', 'marginBottom': '15px'}
                    ),
                    html.Label('Y-Axis Indicator(s)', style={'fontWeight': 'bold', 'fontSize': '14px', 'color': '#666'}),
                    dcc.Dropdown(
                        id='y-ind-dropdown',
                        options=[],
                        value=[], disabled=True, multi=True, clearable=True,
                        placeholder='Select one or more indicators',
                        style={'width': '100%', 'marginBottom': '15px'}
                    ),
                    dcc.Checklist(
                        id='graph-options-toggles',
                        options=[
                            {'label': ' Normalize Data (0–100)', 'value': 'normalize'},
                            {'label': ' Predict Future Years (ML)', 'value': 'forecast'},
                        ],
                        value=[],
                        style={'marginBottom': '10px', 'fontSize': '13px'},
                        labelStyle={'display': 'block', 'marginBottom': '4px'},
                    ),
                ], style={'flex': '1', 'marginRight': '15px'}),

                html.Div([
                    html.Label('Secondary Category', style={'fontWeight': 'bold', 'fontSize': '14px'}),
                    dcc.Dropdown(
                        id='color-cat-dropdown',
                        options=[{'label': c.replace('_', ' '), 'value': c} for c in ['N/A'] + global_categories],
                        value='N/A', clearable=False,
                        style={'width': '100%', 'marginBottom': '15px'}
                    ),
                    html.Label('Secondary Indicator', style={'fontWeight': 'bold', 'fontSize': '14px', 'color': '#666'}),
                    dcc.Dropdown(
                        id='color-ind-dropdown',
                        options=[{'label': 'N/A', 'value': 'N/A'}],
                        value='N/A', disabled=True, clearable=False,
                        style={'width': '100%', 'marginBottom': '15px'}
                    ),
                ], style={'flex': '1'})
            ], style={'display': 'flex', 'flexDirection': 'row', 'marginBottom': '20px'}),

            html.Hr(),

            html.Div([
                dcc.Graph(id='factor-trend-graph', style={'height': '40vh'})
            ], style={'marginBottom': '20px'}),

            html.Div([
                dcc.Graph(id='secondary-trend-graph', style={'height': '35vh'})
            ], id='secondary-trend-wrapper', style={'display': 'none', 'marginBottom': '20px'}),

            html.H4('Index Breakdown', id='index-breakdown-title',
                    style={'marginTop': '10px', 'marginBottom': '6px'}),
            html.Div(id='index-breakdown-container', style={'marginBottom': '20px'}),

            html.H4('Indicators', style={'marginBottom': '6px'}),
            html.Div(id='indicator-table-container', style={'marginBottom': '20px'}),
        ]
    )


def _help_modal() -> html.Div:
    return html.Div(
        id='help-modal',
        style={'display': 'none'},
        children=[
            html.Div(
                style={
                    'position': 'fixed', 'top': '0', 'left': '0',
                    'width': '100vw', 'height': '100vh',
                    'backgroundColor': 'rgba(0,0,0,0.4)', 'zIndex': '2000',
                },
                children=[
                    html.Div(
                        style={
                            'position': 'absolute', 'top': '50%', 'left': '50%',
                            'transform': 'translate(-50%, -50%)',
                            'width': 'min(90vw, 1100px)', 'maxHeight': '85vh',
                            'backgroundColor': 'white', 'borderRadius': '10px',
                            'padding': '20px', 'overflow': 'hidden',
                            'boxShadow': '0 8px 30px rgba(0,0,0,0.2)',
                            'display': 'flex', 'flexDirection': 'column',
                        },
                        children=[
                            html.Div([
                                html.H2('Data Dictionary',
                                        style={'margin': '0', 'color': '#4b0082'}),
                                html.Button('✖', id='help-modal-close', n_clicks=0, style={
                                    'border': 'none', 'background': 'transparent',
                                    'fontSize': '20px', 'cursor': 'pointer',
                                }),
                            ], style={
                                'display': 'flex', 'justifyContent': 'space-between',
                                'alignItems': 'center', 'marginBottom': '12px',
                            }),
                            html.Div(
                                id='data-dictionary-table-wrapper',
                                style={'overflow': 'auto', 'flex': '1'},
                                children=dash_table.DataTable(
                                    id='data-dictionary-table',
                                    columns=[
                                        {'name': 'Indicator', 'id': 'friendly_name'},
                                        {'name': 'Category', 'id': 'category'},
                                        {'name': 'Description', 'id': 'description'},
                                        {'name': 'Source', 'id': 'source'},
                                    ],
                                    data=[],
                                    filter_action='native',
                                    sort_action='native',
                                    page_size=15,
                                    style_cell={
                                        'fontFamily': 'Arial', 'fontSize': '13px',
                                        'textAlign': 'left', 'padding': '6px',
                                        'whiteSpace': 'normal', 'height': 'auto',
                                    },
                                    style_header={
                                        'backgroundColor': '#4b0082',
                                        'color': 'white', 'fontWeight': 'bold',
                                    },
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _custom_reports_modal(global_categories: list) -> html.Div:
    return html.Div(
        id='custom-reports-modal',
        style={'display': 'none'},
        children=[
            html.Div(
                style={
                    'position': 'fixed', 'top': '0', 'left': '0',
                    'width': '100vw', 'height': '100vh',
                    'backgroundColor': 'rgba(0,0,0,0.4)', 'zIndex': '2000',
                },
                children=[
                    html.Div(
                        style={
                            'position': 'absolute', 'top': '50%', 'left': '50%',
                            'transform': 'translate(-50%, -50%)',
                            'width': 'min(95vw, 1200px)', 'maxHeight': '90vh',
                            'backgroundColor': 'white', 'borderRadius': '10px',
                            'padding': '20px', 'overflow': 'hidden',
                            'boxShadow': '0 8px 30px rgba(0,0,0,0.2)',
                            'display': 'flex', 'flexDirection': 'column',
                        },
                        children=[
                            html.Div([
                                html.H2('Custom Report Builder',
                                        style={'margin': '0', 'color': '#4b0082'}),
                                html.Button('✖', id='custom-reports-close', n_clicks=0, style={
                                    'border': 'none', 'background': 'transparent',
                                    'fontSize': '20px', 'cursor': 'pointer',
                                }),
                            ], style={
                                'display': 'flex', 'justifyContent': 'space-between',
                                'alignItems': 'center', 'marginBottom': '12px',
                            }),
                            html.Div([
                                html.Button('+ Add Element', id='add-report-element-btn',
                                            n_clicks=0, style={
                                                'padding': '8px 14px', 'marginRight': '10px',
                                                'border': '1px solid #4b0082',
                                                'backgroundColor': '#4b0082',
                                                'color': 'white', 'borderRadius': '6px',
                                                'cursor': 'pointer', 'fontWeight': '600',
                                            }),
                                html.Button('Export to PDF', id='export-report-pdf-btn',
                                            n_clicks=0, style={
                                                'padding': '8px 14px',
                                                'border': '1px solid #4b0082',
                                                'backgroundColor': 'white',
                                                'color': '#4b0082', 'borderRadius': '6px',
                                                'cursor': 'pointer', 'fontWeight': '600',
                                            }),
                            ], style={'marginBottom': '12px'}),
                            dcc.Store(id='custom-reports-categories', data=list(global_categories)),
                            html.Div(
                                id='report-elements-container',
                                children=[],
                                style={'overflow': 'auto', 'flex': '1', 'paddingRight': '6px'},
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _chat_widget() -> list:
    """Returns [chat_button, chat_popup] — both are children of the main-content flex row."""
    chat_btn = html.Button(
        'AI Assistant',
        id='chat-btn',
        style={
            'position': 'fixed', 'bottom': '20px', 'left': '20px', 'zIndex': '1000',
            'padding': '12px 16px', 'borderRadius': '8px', 'border': 'none',
            'background': 'linear-gradient(135deg, #03123e 0%, #4b0082 100%)',
            'color': 'white', 'cursor': 'pointer'
        }
    )

    chat_popup = html.Div(
        id='chat-popup',
        style={
            'display': 'none',
            'position': 'fixed',
            'bottom': '80px', 'left': '20px',
            'width': '300px', 'height': '400px',
            'minWidth': '280px', 'minHeight': '350px',
            'maxWidth': '90vw', 'maxHeight': '85vh',
            'backgroundColor': 'white', 'border': '1px solid #ccc',
            'borderRadius': '10px', 'boxShadow': '0 4px 10px rgba(0,0,0,0.2)',
            'zIndex': '1000', 'padding': '10px',
            'flexDirection': 'column',
            'boxSizing': 'border-box'
        },
        children=[
            html.Div(
                id='chat-resize-handle',
                style={
                    'position': 'absolute',
                    'top': '4px',
                    'right': '6px',
                    'width': '28px',
                    'height': '28px',
                    'cursor': 'nesw-resize',
                    'zIndex': '1001',
                    'userSelect': 'none'
                }
            ),
            dcc.Store(id='pending-user-message'),
            dcc.Store(id='chat-language', data=None),
            dcc.Store(id='chat-session-id', data=str(uuid.uuid4()), storage_type='memory'),
            dcc.Store(id='chat-history-tick', data=0),
            dcc.Download(id='download-pdf'),
            dcc.Download(id='download-report'),
            dcc.Store(id='pending-report'),
            html.Div(
                id='language-selection',
                style={
                    'display': 'flex', 'flexDirection': 'column',
                    'alignItems': 'center', 'justifyContent': 'center',
                    'flex': '1', 'padding': '10px'
                },
                children=[
                    html.Div(
                        'Choose a language / Elige un idioma',
                        style={
                            'fontSize': '14px', 'fontWeight': '600',
                            'marginBottom': '16px', 'textAlign': 'center',
                            'color': '#333'
                        }
                    ),
                    html.Button(
                        'English', id='lang-en-btn',
                        style={
                            'width': '80%', 'padding': '10px 14px',
                            'marginBottom': '10px', 'border': 'none',
                            'borderRadius': '8px', 'cursor': 'pointer',
                            'background': 'linear-gradient(135deg, #03123e 0%, #4b0082 100%)',
                            'color': 'white', 'fontSize': '14px', 'fontWeight': '600'
                        }
                    ),
                    html.Button(
                        'Español', id='lang-es-btn',
                        style={
                            'width': '80%', 'padding': '10px 14px',
                            'border': 'none', 'borderRadius': '8px',
                            'cursor': 'pointer',
                            'background': 'linear-gradient(135deg, #03123e 0%, #4b0082 100%)',
                            'color': 'white', 'fontSize': '14px', 'fontWeight': '600'
                        }
                    ),
                ]
            ),
            html.Div(
                id='chat-interface',
                style={
                    'display': 'none', 'flex': '1',
                    'flexDirection': 'column', 'minHeight': '0'
                },
                children=[
                    html.Div(
                        [
                            html.Span(
                                'AI Assistant',
                                id='chat-header-label',
                                style={
                                    'fontWeight': 'bold', 'color': '#4b0082',
                                    'fontSize': '14px'
                                }
                            ),
                            html.Button(
                                'Download PDF',
                                id='download-pdf-btn',
                                disabled=True,
                                n_clicks=0,
                                style={
                                    'fontSize': '12px',
                                    'padding': '4px 10px',
                                    'border': '1px solid #4b0082',
                                    'borderRadius': '6px',
                                    'background': 'white',
                                    'color': '#4b0082',
                                    'cursor': 'pointer',
                                },
                            ),
                        ],
                        style={
                            'display': 'flex',
                            'justifyContent': 'space-between',
                            'alignItems': 'center',
                            'padding': '6px 4px',
                            'borderBottom': '1px solid #eee',
                            'marginBottom': '6px',
                        },
                    ),
                    html.Div(
                        id='chat-messages',
                        children=[],
                        style={
                            'flex': '1', 'overflowY': 'auto',
                            'border': '1px solid #eee', 'padding': '5px', 'marginBottom': '10px'
                        }
                    ),
                    html.Div(
                        style={
                            'display': 'flex', 'alignItems': 'center',
                            'border': '1px solid #ddd', 'borderRadius': '20px',
                            'padding': '5px 10px', 'backgroundColor': '#f9f9f9'
                        },
                        children=[
                            dcc.Input(
                                id='chat-input', type='text', placeholder='Ask something...',
                                style={
                                    'flex': '1', 'border': 'none', 'outline': 'none',
                                    'backgroundColor': 'transparent', 'padding': '8px'
                                }
                            ),
                            html.Button(
                                '➤', id='chat-send-btn',
                                style={
                                    'border': 'none', 'backgroundColor': '#4b0082',
                                    'color': 'white', 'borderRadius': '50%',
                                    'width': '32px', 'height': '32px',
                                    'cursor': 'pointer', 'marginLeft': '5px'
                                }
                            )
                        ]
                    )
                ]
            )
        ]
    )

    return [chat_btn, chat_popup]


def _main_content(global_categories: list) -> html.Div:
    return html.Div([
        _left_menu(),
        html.Div([
            dcc.Graph(id='pr-map', style={'height': '75vh'})
        ], style={'flex': '7', 'padding': '10px', 'minWidth': '0'}),
        _right_panel(global_categories),
        *_chat_widget(),
    ], style={'display': 'flex', 'flexDirection': 'row'})
