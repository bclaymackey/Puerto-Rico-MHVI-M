from datetime import datetime

import dash
from dash import Input, Output, State, dcc, html, ALL, MATCH, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from ai_service import consume_report, process_chat_message
from chat_history_manager import clear_session, get_history_for_display
from pdf_export import build_pdf_bytes

from data import (
    fetch_map_data,
    fetch_municipality_name,
    query_axis_data,
    query_indicator_table,
    normalize_series,
    forecast_series,
    get_db_connection,
    counties,
)


def register_callbacks(app: dash.Dash, db_metadata: dict, data_dictionary_df=None) -> None:

    @app.callback(
        Output('pr-map', 'figure'),
        Input('global-category-dropdown', 'value')
    )
    def update_map(category):
        df = fetch_map_data(category)

        if df.empty:
            fig = px.choropleth_map(
                geojson=counties, locations=[], map_style='carto-positron',
                zoom=7.5, center={'lat': 18.2208, 'lon': -66.5901}
            )
            fig.update_layout(margin={'r': 0, 't': 0, 'l': 0, 'b': 0})
            return fig

        fig = px.choropleth_map(
            df,
            geojson=counties,
            locations='fips_code',
            color='value',
            hover_name='name',
            color_continuous_scale='Viridis_r',
            map_style='carto-positron',
            zoom=7.5,
            center={'lat': 18.2208, 'lon': -66.5901},
            opacity=0.8,
            hover_data={'fips_code': False, 'value': True}
        )
        fig.update_layout(margin={'r': 0, 't': 0, 'l': 0, 'b': 0})
        return fig

    @app.callback(
        [Output('y-ind-dropdown', 'options'),
         Output('y-ind-dropdown', 'value'),
         Output('y-ind-dropdown', 'disabled')],
        Input('y-cat-dropdown', 'value')
    )
    def update_y_indicator(y_cat):
        if y_cat in ['N/A', 'Overall MHVI-M Score']:
            return [], [], True
        indicators = db_metadata.get(y_cat, [])
        options = [{'label': i.replace('_', ' '), 'value': i} for i in indicators]
        default = [indicators[0]] if indicators else []
        return options, default, False

    @app.callback(
        [Output('color-ind-dropdown', 'options'),
         Output('color-ind-dropdown', 'value'),
         Output('color-ind-dropdown', 'disabled')],
        Input('color-cat-dropdown', 'value')
    )
    def update_color_indicator(color_cat):
        if color_cat in ['N/A', 'Overall MHVI-M Score']:
            return [{'label': 'N/A', 'value': 'N/A'}], 'N/A', True
        indicators = db_metadata.get(color_cat, [])
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
        if current_style and current_style.get('display') == 'none':
            return {
                'flex': '2', 'padding': '20px', 'backgroundColor': '#f0f2f5',
                'borderRight': '1px solid #ccc', 'fontFamily': 'Arial',
                'height': '68vh', 'display': 'flex', 'flexDirection': 'column',
                'minWidth': '0'
            }
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
        if trigger_id == 'close-panel-btn':
            return {'display': 'none'}
        elif trigger_id == 'pr-map' and map_click is not None:
            return {
                'flex': '4', 'padding': '20px', 'backgroundColor': '#f8f9fa',
                'borderLeft': '1px solid #ccc', 'fontFamily': 'Arial',
                'height': '75vh', 'overflowY': 'auto',
                'display': 'flex', 'flexDirection': 'column',
                'minWidth': '0'
            }
        return {'display': 'none'}

    app.clientside_callback(
        """
        function(n_clicks) {
            if (!n_clicks) { return window.dash_clientside.no_update; }
            var el = document.getElementById('chat-popup');
            if (!el) { return window.dash_clientside.no_update; }
            var cur = window.getComputedStyle(el).display;
            el.style.display = (cur === 'none') ? 'flex' : 'none';
            return window.dash_clientside.no_update;
        }
        """,
        Output('chat-popup', 'id'),
        Input('chat-btn', 'n_clicks'),
    )

    app.clientside_callback(
        """
        function(id) {
            if (window._chatResizeInit) { return window.dash_clientside.no_update; }
            var handle = document.getElementById('chat-resize-handle');
            var popup = document.getElementById('chat-popup');
            if (!handle || !popup) { return window.dash_clientside.no_update; }
            window._chatResizeInit = true;

            var dragging = false;
            var startX, startY, startW, startH;

            handle.addEventListener('mousedown', function (e) {
                dragging = true;
                startX = e.clientX;
                startY = e.clientY;
                var rect = popup.getBoundingClientRect();
                startW = rect.width;
                startH = rect.height;
                e.preventDefault();
                e.stopPropagation();
            });

            document.addEventListener('mousemove', function (e) {
                if (!dragging) { return; }
                var dx = e.clientX - startX;
                var dy = e.clientY - startY;
                var newW = Math.min(window.innerWidth * 0.9, Math.max(280, startW + dx));
                var newH = Math.min(
                    window.innerHeight * 0.85,
                    Math.max(350, startH - dy)
                );
                popup.style.width = newW + 'px';
                popup.style.height = newH + 'px';
            });

            document.addEventListener('mouseup', function () { dragging = false; });

            return window.dash_clientside.no_update;
        }
        """,
        Output('chat-resize-handle', 'title'),
        Input('chat-resize-handle', 'id'),
    )

    def _user_bubble(text):
        return html.Div(
            html.Div(
                text,
                style={
                    'backgroundColor': '#4b0082', 'color': 'white',
                    'padding': '8px 12px',
                    'borderRadius': '16px 16px 4px 16px',
                    'maxWidth': '75%', 'wordWrap': 'break-word'
                }
            ),
            style={'display': 'flex', 'justifyContent': 'flex-end', 'marginBottom': '6px'}
        )

    def _ai_bubble(text):
        return html.Div(
            html.Div(
                text,
                style={
                    'backgroundColor': '#f0f0f0', 'color': '#333',
                    'padding': '8px 12px',
                    'borderRadius': '16px 16px 16px 4px',
                    'maxWidth': '75%', 'wordWrap': 'break-word'
                }
            ),
            style={'display': 'flex', 'justifyContent': 'flex-start', 'marginBottom': '6px'}
        )

    # v1: one outstanding report at a time. The button id is fixed; clicking
    # always downloads whichever report is currently pinned in `pending-report`.
    def _report_bubble(message, language):
        btn_label = 'Descargar informe' if language == 'es' else 'Download report'
        return html.Div(
            html.Div(
                [
                    html.Div(message, style={'marginBottom': '8px'}),
                    html.Button(
                        btn_label,
                        id='download-report-btn',
                        n_clicks=0,
                        style={
                            'fontSize': '12px',
                            'padding': '6px 12px',
                            'border': '1px solid #4b0082',
                            'borderRadius': '6px',
                            'background': '#4b0082',
                            'color': 'white',
                            'cursor': 'pointer',
                        },
                    ),
                ],
                style={
                    'backgroundColor': '#f0f0f0', 'color': '#333',
                    'padding': '10px 14px',
                    'borderRadius': '16px 16px 16px 4px',
                    'maxWidth': '75%', 'wordWrap': 'break-word',
                },
            ),
            style={'display': 'flex', 'justifyContent': 'flex-start', 'marginBottom': '6px'},
        )

    def _typing_bubble():
        dot_style = {
            'width': '8px', 'height': '8px',
            'backgroundColor': '#888',
            'borderRadius': '50%',
            'display': 'inline-block',
            'margin': '0 2px',
        }
        return html.Div(
            html.Div(
                [
                    html.Span(className='typing-dot typing-dot-1', style=dot_style),
                    html.Span(className='typing-dot typing-dot-2', style=dot_style),
                    html.Span(className='typing-dot typing-dot-3', style=dot_style),
                ],
                style={
                    'backgroundColor': '#f0f0f0',
                    'padding': '10px 14px',
                    'borderRadius': '16px 16px 16px 4px',
                    'display': 'inline-block',
                }
            ),
            id='typing-indicator',
            style={'display': 'flex', 'justifyContent': 'flex-start', 'marginBottom': '6px'}
        )

    def _is_typing_indicator(child):
        if isinstance(child, dict):
            return child.get('props', {}).get('id') == 'typing-indicator'
        return getattr(child, 'id', None) == 'typing-indicator'

    def _welcome_bubble(language):
        if language == 'es':
            header = "¡Hola! 👋 Soy tu asistente de IA."
            body = (
                "Puedes hacerme preguntas sobre los datos de vulnerabilidad de "
                "salud mental de Puerto Rico, tendencias por municipio, factores "
                "de riesgo comunitarios y determinantes sociales de la salud."
            )
            try_label = "Prueba con preguntas como:"
            examples = [
                '"¿Cuál es el puntaje general de Arecibo?"',
                '"¿Puedes darme un informe general sobre Arecibo?"',
                '"¿Cómo cambio el mapa para mostrar las puntuaciones educativas?"',
            ]
        else:
            header = "Hello! 👋 I'm your AI assistant."
            body = (
                "You can ask me questions about Puerto Rico's mental health "
                "vulnerability data, municipality trends, community risk "
                "factors, and social determinants of health."
            )
            try_label = "Try questions like:"
            examples = [
                '"What is the overall score for Arecibo?"',
                '"Can you give me an overall report for Arecibo?"',
                '"How do I change the map to education scores?"',
            ]

        return html.Div(
            html.Div(
                [
                    html.Div(header, style={'marginBottom': '6px', 'fontWeight': '600'}),
                    html.Div(body, style={'marginBottom': '6px'}),
                    html.Div(try_label, style={'marginBottom': '2px'}),
                    html.Ul(
                        [html.Li(ex) for ex in examples],
                        style={'paddingLeft': '18px', 'margin': '0 0 6px 0'}
                    ),
                ],
                style={
                    'backgroundColor': '#f0f0f0', 'color': '#333',
                    'padding': '8px 12px',
                    'borderRadius': '16px 16px 16px 4px',
                    'maxWidth': '90%', 'wordWrap': 'break-word',
                    'fontSize': '13px', 'lineHeight': '1.4'
                }
            ),
            style={
                'display': 'flex', 'justifyContent': 'flex-start',
                'marginBottom': '6px'
            }
        )

    @app.callback(
        [Output('chat-language', 'data'),
         Output('language-selection', 'style'),
         Output('chat-interface', 'style'),
         Output('chat-messages', 'children'),
         Output('chat-history-tick', 'data', allow_duplicate=True)],
        [Input('lang-en-btn', 'n_clicks'),
         Input('lang-es-btn', 'n_clicks')],
        State('chat-session-id', 'data'),
        State('chat-history-tick', 'data'),
        prevent_initial_call=True
    )
    def select_language(en_clicks, es_clicks, session_id, tick):
        trigger_id = dash.ctx.triggered_id
        if trigger_id not in ('lang-en-btn', 'lang-es-btn'):
            return (dash.no_update, dash.no_update, dash.no_update,
                    dash.no_update, dash.no_update)

        language = 'es' if trigger_id == 'lang-es-btn' else 'en'

        if session_id:
            clear_session(session_id)

        return (
            language,
            {'display': 'none'},
            {'display': 'flex', 'flex': '1', 'flexDirection': 'column', 'minHeight': '0'},
            [_welcome_bubble(language)],
            (tick or 0) + 1,
        )

    @app.callback(
        [Output('chat-messages', 'children', allow_duplicate=True),
         Output('chat-input', 'value'),
         Output('pending-user-message', 'data')],
        Input('chat-send-btn', 'n_clicks'),
        State('chat-input', 'value'),
        State('chat-messages', 'children'),
        prevent_initial_call=True
    )
    def show_user_message(n_clicks, user_input, messages):
        if not n_clicks or not user_input:
            return dash.no_update, dash.no_update, dash.no_update

        if messages is None:
            messages = []

        messages.append(_user_bubble(user_input))
        messages.append(_typing_bubble())

        return messages, '', {'text': user_input, 'n': n_clicks}

    @app.callback(
        [Output('chat-messages', 'children', allow_duplicate=True),
         Output('chat-history-tick', 'data', allow_duplicate=True),
         Output('pending-report', 'data', allow_duplicate=True)],
        Input('pending-user-message', 'data'),
        State('chat-messages', 'children'),
        State('chat-language', 'data'),
        State('chat-session-id', 'data'),
        State('chat-history-tick', 'data'),
        prevent_initial_call=True
    )
    def generate_ai_response(pending, messages, language, session_id, tick):
        if not pending or not pending.get('text'):
            return dash.no_update, dash.no_update, dash.no_update

        print(
            f"[generate_ai_response] text={pending.get('text')!r} "
            f"session_id={session_id!r} language={language!r}"
        )

        try:
            ai_response = process_chat_message(
                pending['text'], language or 'en', session_id,
            )
        except Exception as e:
            print(f"[generate_ai_response] error: {e}")
            ai_response = {
                "kind": "text",
                "text": "The AI assistant is currently unavailable.",
            }

        messages = [m for m in (messages or []) if not _is_typing_indicator(m)]

        pending_report_update = dash.no_update
        if isinstance(ai_response, dict) and ai_response.get('kind') == 'report':
            messages.append(
                _report_bubble(ai_response.get('message', ''), language or 'en')
            )
            pending_report_update = {
                'token': ai_response.get('report_token'),
                'filename': ai_response.get('filename'),
            }
        else:
            text = (
                ai_response.get('text')
                if isinstance(ai_response, dict)
                else str(ai_response)
            )
            messages.append(_ai_bubble(text or ''))

        return messages, (tick or 0) + 1, pending_report_update

    @app.callback(
        Output('download-pdf', 'data'),
        Input('download-pdf-btn', 'n_clicks'),
        State('chat-session-id', 'data'),
        State('chat-language', 'data'),
        prevent_initial_call=True
    )
    def export_chat_pdf(n_clicks, session_id, language):
        if not n_clicks or not session_id:
            return dash.no_update

        history = get_history_for_display(session_id)
        if not history:
            return dash.no_update

        pdf_bytes = build_pdf_bytes(history, language=language or 'en')

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        filename = f'chat_transcript_{timestamp}.pdf'

        return dcc.send_bytes(pdf_bytes, filename=filename)

    @app.callback(
        Output('download-report', 'data'),
        Input('download-report-btn', 'n_clicks'),
        State('pending-report', 'data'),
        prevent_initial_call=True,
    )
    def export_report_pdf(n_clicks, pending):
        if not n_clicks or not pending or not pending.get('token'):
            return dash.no_update
        result = consume_report(pending['token'])
        if result is None:
            return dash.no_update
        pdf_bytes, filename = result
        return dcc.send_bytes(pdf_bytes, filename=filename)

    @app.callback(
        Output('download-pdf-btn', 'disabled'),
        Input('chat-history-tick', 'data'),
        State('chat-session-id', 'data'),
    )
    def toggle_pdf_button(_tick, session_id):
        if not session_id:
            return True
        history = get_history_for_display(session_id)
        if not history:
            return True
        return not any(m.get('role') == 'assistant' for m in history)

    @app.callback(
        [Output('chat-header-label', 'children'),
         Output('download-pdf-btn', 'children'),
         Output('chat-btn', 'children')],
        Input('chat-language', 'data'),
    )
    def translate_chat_header(language):
        if language == 'es':
            return 'Asistente de IA', 'Descargar PDF', 'Asistente de IA'
        return 'AI Assistant', 'Download PDF', 'AI Assistant'

    def _series_for_category(fips, category, indicator):
        """Return sorted DataFrame[year, val] for one (cat, ind). Handles Overall."""
        if category == 'Overall MHVI-M Score':
            df = query_axis_data(fips, category, indicator)
        else:
            df = query_axis_data(fips, category, indicator)
        if df is None or df.empty:
            return pd.DataFrame(columns=['year', 'val'])
        df = df.dropna(subset=['val']).sort_values(by='year')
        df['year'] = pd.to_numeric(df['year'], errors='coerce')
        df = df.dropna(subset=['year'])
        return df

    def _add_trace_with_options(fig, df, label, options, color=None, group=None):
        if df.empty:
            return
        years = df['year'].astype(int).tolist()
        vals = df['val'].astype(float).tolist()
        plot_vals = (
            list(normalize_series(vals)) if 'normalize' in (options or []) else vals
        )
        legend_group = group or label
        fig.add_trace(go.Scatter(
            x=years, y=plot_vals, mode='lines+markers',
            name=label, legendgroup=legend_group,
            marker=dict(size=8), line=dict(color=color) if color else dict(),
        ))
        if 'forecast' in (options or []):
            fc = forecast_series(years, plot_vals)
            if fc is not None:
                fc_years, fc_vals = fc
                last_x = [years[-1]] + list(int(y) for y in fc_years)
                last_y = [plot_vals[-1]] + list(fc_vals)
                fig.add_trace(go.Scatter(
                    x=last_x, y=last_y, mode='lines',
                    name=f'{label} (forecast)', legendgroup=legend_group,
                    line=dict(dash='dash', color=color) if color else dict(dash='dash'),
                    showlegend=False,
                ))

    def _empty_fig(title):
        fig = px.scatter(title=title)
        fig.update_layout(
            margin={'r': 0, 't': 30, 'l': 0, 'b': 0},
            paper_bgcolor='#f8f9fa', plot_bgcolor='#f8f9fa',
        )
        return fig

    @app.callback(
        [Output('county-title', 'children'),
         Output('factor-trend-graph', 'figure'),
         Output('secondary-trend-graph', 'figure'),
         Output('secondary-trend-wrapper', 'style')],
        [Input('pr-map', 'clickData'),
         Input('y-cat-dropdown', 'value'),
         Input('y-ind-dropdown', 'value'),
         Input('color-cat-dropdown', 'value'),
         Input('color-ind-dropdown', 'value'),
         Input('graph-options-toggles', 'value')]
    )
    def update_dynamic_plot(clickData, y_cat, y_ind, color_cat, color_ind, options):
        if clickData is None:
            raise dash.exceptions.PreventUpdate

        clicked_fips = clickData['points'][0]['location']
        muni_name = fetch_municipality_name(clicked_fips)

        # ----- Primary -----
        primary_fig = _empty_fig('No Y-Axis Data Found')
        y_label_axis = ''
        if y_cat == 'Overall MHVI-M Score':
            df = _series_for_category(clicked_fips, y_cat, None)
            if not df.empty:
                primary_fig = go.Figure()
                _add_trace_with_options(primary_fig, df, 'Overall MHVI-M Score', options)
                y_label_axis = 'Overall MHVI-M Score'
        else:
            inds = y_ind if isinstance(y_ind, list) else ([y_ind] if y_ind else [])
            inds = [i for i in inds if i and i != 'N/A']
            if inds:
                primary_fig = go.Figure()
                for ind in inds:
                    df = _series_for_category(clicked_fips, y_cat, ind)
                    label = ind.replace('_', ' ')
                    _add_trace_with_options(primary_fig, df, label, options)
                y_label_axis = (
                    'Normalized (0–100)' if 'normalize' in (options or []) else 'Value'
                )

        if isinstance(primary_fig, go.Figure):
            primary_fig.update_layout(
                margin={'r': 0, 't': 10, 'l': 0, 'b': 0},
                paper_bgcolor='#f8f9fa', plot_bgcolor='#f8f9fa',
                xaxis={'title': 'Year', 'type': 'category'},
                yaxis={'title': y_label_axis},
                legend={'orientation': 'h', 'yanchor': 'bottom', 'y': 1.02},
            )

        # ----- Secondary -----
        if color_cat and color_cat != 'N/A':
            if color_cat == 'Overall MHVI-M Score':
                df_sec = _series_for_category(clicked_fips, color_cat, None)
                sec_label = 'Overall MHVI-M Score'
            elif color_ind and color_ind != 'N/A':
                df_sec = _series_for_category(clicked_fips, color_cat, color_ind)
                sec_label = color_ind.replace('_', ' ')
            else:
                df_sec = pd.DataFrame(columns=['year', 'val'])
                sec_label = ''

            secondary_fig = go.Figure()
            if df_sec.empty:
                secondary_fig = _empty_fig('No Secondary Data Found')
            else:
                _add_trace_with_options(secondary_fig, df_sec, sec_label, options,
                                         color='#e76f51')
                secondary_fig.update_layout(
                    margin={'r': 0, 't': 10, 'l': 0, 'b': 0},
                    paper_bgcolor='#f8f9fa', plot_bgcolor='#f8f9fa',
                    xaxis={'title': 'Year', 'type': 'category'},
                    yaxis={'title': 'Normalized (0–100)' if 'normalize' in (options or []) else sec_label},
                    legend={'orientation': 'h', 'yanchor': 'bottom', 'y': 1.02},
                )
            sec_style = {'display': 'block', 'marginBottom': '20px'}
        else:
            secondary_fig = _empty_fig('')
            sec_style = {'display': 'none'}

        return muni_name, primary_fig, secondary_fig, sec_style

    # ----- Indicator accordion -----
    @app.callback(
        Output('indicator-table-container', 'children'),
        [Input('pr-map', 'clickData'),
         Input('global-category-dropdown', 'value')]
    )
    def update_indicator_table(clickData, category):
        if clickData is None or not category:
            return []
        fips = clickData['points'][0]['location']
        df = query_indicator_table(fips, category)
        if df.empty:
            return html.Div('No indicators available for this selection.',
                            style={'color': '#888', 'fontStyle': 'italic'})

        groups = []
        for ind, sub in df.groupby('indicator_name'):
            if ind == 'Subcategory Index Score':
                continue
            sub = sub.sort_values('year')
            rows = [
                html.Tr([
                    html.Td(int(r['year']) if pd.notna(r['year']) else '',
                            style={'padding': '3px 8px'}),
                    html.Td(
                        '—' if pd.isna(r['value']) else f"{r['value']:.4g}",
                        style={'padding': '3px 8px'},
                    ),
                ])
                for _, r in sub.iterrows()
            ]
            disabled = category == 'Overall MHVI-M Score'
            groups.append(html.Details([
                html.Summary([
                    html.Span(ind.replace('_', ' '),
                              style={'fontWeight': 'bold'}),
                    html.Button(
                        'Plot',
                        id={'type': 'plot-ind-btn', 'index': ind},
                        n_clicks=0,
                        disabled=disabled,
                        style={
                            'marginLeft': '10px', 'padding': '2px 8px',
                            'fontSize': '11px',
                            'border': '1px solid #4b0082',
                            'borderRadius': '4px',
                            'backgroundColor': 'white' if not disabled else '#eee',
                            'color': '#4b0082' if not disabled else '#999',
                            'cursor': 'pointer' if not disabled else 'not-allowed',
                        },
                    ),
                ], style={'cursor': 'pointer', 'padding': '6px 0'}),
                html.Table(
                    [html.Thead(html.Tr([
                        html.Th('Year', style={'textAlign': 'left', 'padding': '3px 8px'}),
                        html.Th('Value', style={'textAlign': 'left', 'padding': '3px 8px'}),
                    ]))] + [html.Tbody(rows)],
                    style={'width': '100%', 'borderCollapse': 'collapse',
                           'fontSize': '12px', 'marginTop': '4px'},
                ),
            ], style={
                'backgroundColor': '#ffffff',
                'border': '1px solid #ddd', 'borderRadius': '4px',
                'padding': '6px 10px', 'marginBottom': '4px',
            }))
        return groups

    @app.callback(
        Output('y-ind-dropdown', 'value', allow_duplicate=True),
        Input({'type': 'plot-ind-btn', 'index': ALL}, 'n_clicks'),
        State('y-ind-dropdown', 'value'),
        State('y-cat-dropdown', 'value'),
        State('global-category-dropdown', 'value'),
        prevent_initial_call=True,
    )
    def handle_plot_btn_clicks(n_clicks_list, current_value, y_cat, global_cat):
        if not n_clicks_list or not any(n for n in n_clicks_list if n):
            raise dash.exceptions.PreventUpdate
        trigger = dash.ctx.triggered_id
        if not isinstance(trigger, dict) or trigger.get('type') != 'plot-ind-btn':
            raise dash.exceptions.PreventUpdate
        # Only act when the clicked indicator belongs to the current Y-axis category.
        if y_cat != global_cat or y_cat == 'Overall MHVI-M Score':
            raise dash.exceptions.PreventUpdate
        ind = trigger['index']
        current = current_value if isinstance(current_value, list) else (
            [current_value] if current_value else []
        )
        if ind in current:
            raise dash.exceptions.PreventUpdate
        return current + [ind]

    # ----- Index breakdown -----
    @app.callback(
        Output('index-breakdown-container', 'children'),
        [Input('pr-map', 'clickData'),
         Input('global-category-dropdown', 'value')]
    )
    def update_index_breakdown(clickData, category):
        if clickData is None or not category:
            return []
        fips = clickData['points'][0]['location']
        df = query_indicator_table(fips, category)
        if df.empty:
            return html.Div('No data for this municipality.',
                            style={'color': '#888'})

        included, missing = [], []
        for ind, sub in df.groupby('indicator_name'):
            if ind == 'Subcategory Index Score':
                continue
            if sub['value'].notna().any():
                included.append(ind.replace('_', ' '))
            else:
                missing.append(ind.replace('_', ' '))

        def _box(title, items, bg, fg):
            return html.Div([
                html.Div(title, style={
                    'fontWeight': 'bold', 'marginBottom': '4px', 'color': fg,
                }),
                html.Ul(
                    [html.Li(i, style={'fontSize': '12px'}) for i in items]
                    or [html.Li('—', style={'fontSize': '12px', 'color': '#888'})],
                    style={'margin': '0', 'paddingLeft': '18px'},
                ),
            ], style={
                'flex': '1', 'backgroundColor': bg, 'border': f'1px solid {fg}',
                'padding': '8px 12px', 'borderRadius': '6px',
            })

        return html.Div([
            _box(f'Included ({len(included)})', included, '#e8f5e9', '#2e7d32'),
            html.Div(style={'width': '12px'}),
            _box(f'Missing ({len(missing)})', missing, '#fdecea', '#c62828'),
        ], style={'display': 'flex', 'flexDirection': 'row'})

    # ----- Modal toggles -----
    @app.callback(
        [Output('help-modal', 'style'),
         Output('data-dictionary-table', 'data')],
        [Input('open-help-btn', 'n_clicks'),
         Input('help-modal-close', 'n_clicks')],
        prevent_initial_call=True,
    )
    def toggle_help_modal(open_clicks, close_clicks):
        trigger = dash.ctx.triggered_id
        if trigger == 'open-help-btn':
            rows = (
                data_dictionary_df.to_dict('records')
                if data_dictionary_df is not None and not data_dictionary_df.empty
                else []
            )
            return {'display': 'block'}, rows
        return {'display': 'none'}, dash.no_update

    @app.callback(
        Output('custom-reports-modal', 'style'),
        [Input('open-custom-reports-btn', 'n_clicks'),
         Input('custom-reports-close', 'n_clicks')],
        prevent_initial_call=True,
    )
    def toggle_reports_modal(open_clicks, close_clicks):
        trigger = dash.ctx.triggered_id
        if trigger == 'open-custom-reports-btn':
            return {'display': 'block'}
        return {'display': 'none'}

    # ----- Custom Report Builder -----
    def _report_element_block(index, categories):
        cat_options = [{'label': c.replace('_', ' '), 'value': c} for c in categories]
        muni_options = _all_municipality_options()
        return html.Div(
            id={'type': 'report-element', 'index': index},
            style={
                'border': '1px solid #ddd', 'borderRadius': '6px',
                'padding': '12px', 'marginBottom': '10px',
                'backgroundColor': '#fafafa',
            },
            children=[
                html.Div([
                    html.Span(f'Element #{index + 1}', style={'fontWeight': 'bold'}),
                    html.Button('Remove',
                                id={'type': 'remove-report-element-btn', 'index': index},
                                n_clicks=0,
                                style={
                                    'marginLeft': 'auto', 'border': '1px solid #c62828',
                                    'background': 'white', 'color': '#c62828',
                                    'borderRadius': '4px', 'padding': '2px 8px',
                                    'cursor': 'pointer', 'fontSize': '12px',
                                }),
                ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '8px'}),

                html.Div([
                    html.Div([
                        html.Label('Element Type', style={'fontSize': '12px'}),
                        dcc.Dropdown(
                            id={'type': 'report-element-type', 'index': index},
                            options=[
                                {'label': 'Line Graph', 'value': 'graph'},
                                {'label': 'Data Table', 'value': 'table'},
                                {'label': 'Index Breakdown Table', 'value': 'breakdown'},
                            ],
                            value='graph', clearable=False,
                        ),
                    ], style={'flex': '1', 'marginRight': '8px'}),
                    html.Div([
                        html.Label('Municipalities', style={'fontSize': '12px'}),
                        dcc.Dropdown(
                            id={'type': 'report-county', 'index': index},
                            options=muni_options, value=[], multi=True,
                            placeholder='Pick one or more',
                        ),
                    ], style={'flex': '2', 'marginRight': '8px'}),
                    html.Div([
                        html.Label('Category', style={'fontSize': '12px'}),
                        dcc.Dropdown(
                            id={'type': 'report-category', 'index': index},
                            options=cat_options,
                            value='Overall MHVI-M Score', clearable=False,
                        ),
                    ], style={'flex': '1', 'marginRight': '8px'}),
                    html.Div([
                        html.Label('Indicator', style={'fontSize': '12px'}),
                        dcc.Dropdown(
                            id={'type': 'report-indicator', 'index': index},
                            options=[], value=None,
                            placeholder='—',
                        ),
                    ], style={'flex': '2'}),
                ], style={'display': 'flex', 'marginBottom': '8px'}),

                dcc.Checklist(
                    id={'type': 'report-options', 'index': index},
                    options=[
                        {'label': ' Normalize', 'value': 'normalize'},
                        {'label': ' Forecast', 'value': 'forecast'},
                    ],
                    value=[],
                    style={'fontSize': '12px', 'marginBottom': '6px'},
                    labelStyle={'marginRight': '12px'},
                ),

                html.Div(
                    id={'type': 'report-element-preview', 'index': index},
                    style={'backgroundColor': 'white', 'padding': '8px',
                           'border': '1px solid #eee', 'borderRadius': '4px',
                           'minHeight': '60px'},
                ),
            ],
        )

    def _all_municipality_options():
        conn = get_db_connection()
        try:
            df = pd.read_sql_query(
                "SELECT fips_code, name FROM municipalities ORDER BY name", conn
            )
        except Exception:
            return []
        finally:
            conn.close()
        return [{'label': r['name'], 'value': r['fips_code']} for _, r in df.iterrows()]

    @app.callback(
        Output('report-elements-container', 'children'),
        [Input('add-report-element-btn', 'n_clicks'),
         Input({'type': 'remove-report-element-btn', 'index': ALL}, 'n_clicks')],
        State('report-elements-container', 'children'),
        State('custom-reports-categories', 'data'),
        prevent_initial_call=True,
    )
    def add_or_remove_report_element(add_clicks, remove_clicks_list, current, categories):
        trigger = dash.ctx.triggered_id
        current = current or []

        if trigger == 'add-report-element-btn':
            # Index is the count of currently rendered elements (so it stays unique
            # across renders even after removals).
            idx = len(current)
            current.append(_report_element_block(idx, categories or []))
            return current

        if isinstance(trigger, dict) and trigger.get('type') == 'remove-report-element-btn':
            target_idx = trigger['index']
            new = []
            for child in current:
                # Children may be Dash components or dict reps; both have 'props' on the
                # rendered side, but here on the server they're component instances.
                child_id = getattr(child, 'id', None)
                if isinstance(child, dict):
                    child_id = child.get('props', {}).get('id')
                if isinstance(child_id, dict) and child_id.get('index') == target_idx:
                    continue
                new.append(child)
            return new

        raise dash.exceptions.PreventUpdate

    @app.callback(
        [Output({'type': 'report-indicator', 'index': MATCH}, 'options'),
         Output({'type': 'report-indicator', 'index': MATCH}, 'value'),
         Output({'type': 'report-indicator', 'index': MATCH}, 'disabled')],
        Input({'type': 'report-category', 'index': MATCH}, 'value'),
    )
    def update_report_indicator(category):
        if category in (None, 'Overall MHVI-M Score'):
            return [], None, True
        inds = db_metadata.get(category, [])
        opts = [{'label': i.replace('_', ' '), 'value': i} for i in inds]
        return opts, (inds[0] if inds else None), False

    @app.callback(
        Output({'type': 'report-element-preview', 'index': MATCH}, 'children'),
        [Input({'type': 'report-element-type', 'index': MATCH}, 'value'),
         Input({'type': 'report-county', 'index': MATCH}, 'value'),
         Input({'type': 'report-category', 'index': MATCH}, 'value'),
         Input({'type': 'report-indicator', 'index': MATCH}, 'value'),
         Input({'type': 'report-options', 'index': MATCH}, 'value')],
    )
    def render_report_element(elem_type, fips_list, category, indicator, options):
        fips_list = fips_list or []
        if not fips_list:
            return html.Div('Pick at least one municipality.',
                            style={'color': '#888', 'fontStyle': 'italic'})
        if not category:
            return html.Div('Pick a category.',
                            style={'color': '#888', 'fontStyle': 'italic'})

        if elem_type == 'breakdown':
            blocks = []
            for fips in fips_list:
                muni = fetch_municipality_name(fips)
                df = query_indicator_table(fips, category)
                if df.empty:
                    blocks.append(html.Div(f'{muni}: no data',
                                            style={'marginBottom': '6px'}))
                    continue
                included, missing = [], []
                for ind, sub in df.groupby('indicator_name'):
                    if ind == 'Subcategory Index Score':
                        continue
                    (included if sub['value'].notna().any() else missing).append(
                        ind.replace('_', ' ')
                    )
                blocks.append(html.Div([
                    html.Div(muni, style={'fontWeight': 'bold', 'marginBottom': '4px'}),
                    html.Div([
                        html.Span(f'Included ({len(included)}): ',
                                  style={'color': '#2e7d32', 'fontWeight': 'bold'}),
                        html.Span(', '.join(included) or '—', style={'fontSize': '12px'}),
                    ], style={'marginBottom': '2px'}),
                    html.Div([
                        html.Span(f'Missing ({len(missing)}): ',
                                  style={'color': '#c62828', 'fontWeight': 'bold'}),
                        html.Span(', '.join(missing) or '—', style={'fontSize': '12px'}),
                    ]),
                ], style={'marginBottom': '10px'}))
            return blocks

        # Graph or table both need a (year × muni) frame.
        is_overall = category == 'Overall MHVI-M Score'
        if not is_overall and not indicator:
            return html.Div('Pick an indicator.',
                            style={'color': '#888', 'fontStyle': 'italic'})

        series_per_muni = {}
        for fips in fips_list:
            muni = fetch_municipality_name(fips)
            df = query_axis_data(
                fips, category, None if is_overall else indicator
            )
            if df is None or df.empty:
                continue
            df = df.dropna(subset=['val']).sort_values('year')
            df['year'] = pd.to_numeric(df['year'], errors='coerce')
            df = df.dropna(subset=['year'])
            if df.empty:
                continue
            series_per_muni[muni] = df

        if not series_per_muni:
            return html.Div('No data for the chosen selection.',
                            style={'color': '#888', 'fontStyle': 'italic'})

        if elem_type == 'graph':
            fig = go.Figure()
            for muni, df in series_per_muni.items():
                years = df['year'].astype(int).tolist()
                vals = df['val'].astype(float).tolist()
                plot_vals = (
                    list(normalize_series(vals)) if 'normalize' in (options or []) else vals
                )
                fig.add_trace(go.Scatter(
                    x=years, y=plot_vals, mode='lines+markers',
                    name=muni, legendgroup=muni,
                ))
                if 'forecast' in (options or []):
                    fc = forecast_series(years, plot_vals)
                    if fc is not None:
                        fc_years, fc_vals = fc
                        fig.add_trace(go.Scatter(
                            x=[years[-1]] + list(int(y) for y in fc_years),
                            y=[plot_vals[-1]] + list(fc_vals),
                            mode='lines',
                            name=f'{muni} (forecast)', legendgroup=muni,
                            line=dict(dash='dash'), showlegend=False,
                        ))
            fig.update_layout(
                margin={'r': 0, 't': 10, 'l': 0, 'b': 0},
                paper_bgcolor='white', plot_bgcolor='white',
                xaxis={'title': 'Year', 'type': 'category'},
                yaxis={'title': 'Normalized (0–100)' if 'normalize' in (options or []) else 'Value'},
                height=320,
            )
            return dcc.Graph(figure=fig)

        # table: pivot to years × munis
        frames = []
        for muni, df in series_per_muni.items():
            sub = df[['year', 'val']].copy()
            sub['year'] = sub['year'].astype(int)
            sub = sub.rename(columns={'val': muni}).set_index('year')
            frames.append(sub)
        wide = pd.concat(frames, axis=1).sort_index().reset_index()
        cols = [{'name': str(c), 'id': str(c)} for c in wide.columns]
        rows = wide.astype(object).where(wide.notna(), '—').to_dict('records')
        return dash_table.DataTable(
            data=rows, columns=cols, page_size=10,
            style_cell={'fontFamily': 'Arial', 'fontSize': '12px',
                        'padding': '4px', 'textAlign': 'left'},
            style_header={'backgroundColor': '#4b0082', 'color': 'white',
                          'fontWeight': 'bold'},
        )

    # Custom Reports → native browser print. Inline @media print CSS in
    # MHVIM_Dashboard_App.py (app.index_string) hides everything except the modal.
    app.clientside_callback(
        """
        function(n_clicks) {
            if(n_clicks > 0) {
                window.print();
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output('export-report-pdf-btn', 'n_clicks_timestamp'),
        Input('export-report-pdf-btn', 'n_clicks'),
    )
