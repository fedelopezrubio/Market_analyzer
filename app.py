# ============================================================
# app.py
# ------------------------------------------------------------
# Este es el archivo principal que lanza el dashboard web.
# Usa Dash (de Plotly) para crear una interfaz interactiva
# en el navegador.
#
# Para ejecutar: python app.py
# Luego abrí en el navegador: http://127.0.0.1:8050
# ============================================================

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# Importamos nuestros propios módulos
from data_fetcher import obtener_precios, obtener_info_empresa, obtener_noticias
from technical import agregar_todos_los_indicadores, generar_señales
from sentiment import analizar_noticias, sentimiento_a_descripcion
from predictor import entrenar_y_predecir, calcular_veredicto_final
from macro import analizar_macro
from geopolitics import analizar_geopolitica
from watchlist import escanear_oportunidades, TODOS_LOS_TICKERS
from alerts import iniciar_scheduler, detener_scheduler, obtener_estado
from paper_trading import calcular_resumen, simular_compra, simular_venta, cargar_historial

# ============================================================
# INICIALIZACIÓN DE LA APP
# ============================================================

# dbc.themes.CYBORG: tema oscuro oscuro. Podés cambiarlo por DARKLY, SLATE, etc.
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    title="📈 Market Analyzer"
)

# ============================================================
# ESTILOS PERSONALIZADOS
# ============================================================

ESTILO_CARD = {
    "backgroundColor": "#1a1a2e",
    "border": "1px solid #16213e",
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "16px"
}

ESTILO_VEREDICTO = {
    "fontSize": "48px",
    "fontWeight": "bold",
    "textAlign": "center",
    "padding": "20px",
    "borderRadius": "12px",
}

# ============================================================
# LAYOUT (DISEÑO DE LA PÁGINA)
# ============================================================

app.layout = dbc.Container([

    # ── Encabezado
    dbc.Row([
        dbc.Col([
            html.H1("📈 Market Analyzer", className="text-center mt-4 mb-1",
                    style={"color": "#00d4ff", "fontWeight": "bold"}),
            html.P("Análisis técnico · Sentimiento · Machine Learning · Macroeconomía · Geopolítica",
                   className="text-center text-muted mb-4"),
        ])
    ]),

    # ── Buscador
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Símbolo de la acción (ticker):", className="text-light"),
                            dbc.Input(
                                id="input-ticker",
                                placeholder="Ej: AAPL, MSFT · Arg: GGAL.BA, YPFD.BA, BMA.BA, PAMP.BA",
                                value="AAPL",
                                type="text",
                                className="mb-2",
                                style={"backgroundColor": "#16213e", "color": "white", "border": "1px solid #00d4ff"}
                            ),
                        ], md=3),
                        dbc.Col([
                            dbc.Label("🔎 Acciones rápidas:", className="text-light"),
                            dcc.Dropdown(
                                id="dropdown-ticker-rapido",
                                options=[
                                    {"label": f"🇦🇷 {n} ({t})", "value": t}
                                    for t, n, s in __import__('watchlist').ACCIONES_ARGENTINAS
                                ] + [
                                    {"label": f"🌎 {n} ({t})", "value": t}
                                    for t, n, s in __import__('watchlist').ACCIONES_GLOBALES
                                ],
                                placeholder="Seleccioná una acción...",
                                clearable=True,
                                className="mb-2",
                                style={"backgroundColor": "#16213e", "color": "white"}
                            ),
                        ], md=3),
                        dbc.Col([
                            dbc.Label("Período de análisis:", className="text-light"),
                            dcc.Dropdown(
                                id="input-periodo",
                                options=[
                                    {"label": "1 mes", "value": "1mo"},
                                    {"label": "3 meses", "value": "3mo"},
                                    {"label": "6 meses", "value": "6mo"},
                                    {"label": "1 año", "value": "1y"},
                                    {"label": "2 años", "value": "2y"},
                                ],
                                value="6mo",
                                clearable=False,
                                style={"backgroundColor": "#16213e", "color": "white"}
                            ),
                        ], md=3),
                        dbc.Col([
                            dbc.Label("‎", className="text-light"),  # Espacio para alinear
                            dbc.Button(
                                "🔍 Analizar",
                                id="boton-analizar",
                                color="info",
                                className="w-100",
                                style={"fontWeight": "bold", "height": "38px"}
                            ),
                        ], md=3),
                    ]),
                    html.Div(id="mensaje-error", className="text-danger mt-2"),
                ])
            ], style=ESTILO_CARD)
        ])
    ]),

    # ── Tabs: Dashboard principal / Paper Trading / Monitor
    dbc.Tabs([

      # ════════════════════════════════════════
      # TAB 1: ANÁLISIS DE MERCADO
      # ════════════════════════════════════════
      dbc.Tab(label="📈 Análisis", tab_id="tab-analisis", children=[

    # ── Panel de oportunidades (se carga al abrir la app)
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    dbc.Row([
                        dbc.Col(html.H5("🚀 Oportunidades del Momento", className="text-warning mb-0"), md=8),
                        dbc.Col(
                            dbc.Button("🔄 Actualizar", id="boton-actualizar-watchlist",
                                       color="outline-warning", size="sm", className="float-end"),
                            md=4, className="text-end"
                        ),
                    ])
                ]),
                dbc.CardBody([
                    html.P("Analizando el mercado...", className="text-muted small mb-2",
                           id="watchlist-status"),
                    dbc.Spinner(
                        html.Div(id="panel-oportunidades"),
                        color="warning", size="sm"
                    ),
                ])
            ], style={**ESTILO_CARD, "border": "1px solid #ffd700"})
        ])
    ]),

    # Intervalo para disparar el escaneo al cargar (una sola vez)
    dcc.Interval(id="intervalo-inicio", interval=500, max_intervals=1),

    # ── Loading spinner mientras carga
    dbc.Spinner([

        # ── Panel de info de la empresa
        html.Div(id="panel-empresa"),

        # ── VEREDICTO PRINCIPAL
        html.Div(id="panel-veredicto"),

        # ── Gráfico de velas + indicadores
        html.Div(id="panel-grafico"),

        # ── Panel de indicadores técnicos
        html.Div(id="panel-indicadores"),

        # ── Panel de noticias
        html.Div(id="panel-noticias"),

        # ── Panel macroeconómico
        html.Div(id="panel-macro"),

        # ── Panel geopolítico
        html.Div(id="panel-geopolitica"),

    ], color="info", type="border"),

      ]),  # end Tab Análisis

      # ════════════════════════════════════════
      # TAB 2: PAPER TRADING
      # ════════════════════════════════════════
      dbc.Tab(label="💼 Paper Trading", tab_id="tab-paper", children=[
        dbc.Row([dbc.Col([
          dbc.Card([
            dbc.CardHeader(html.H5("💼 Paper Trading — Registro de Decisiones", className="text-warning mb-0")),
            dbc.CardBody([
              dcc.Interval(id="intervalo-paper", interval=10_000, n_intervals=0),
              html.Div(id="panel-paper-trading"),
            ])
          ], style={**ESTILO_CARD, "border":"1px solid #ffd700"})
        ])], className="mt-3"),
      ]),

      # ════════════════════════════════════════
      # TAB 3: MONITOR DE ALERTAS
      # ════════════════════════════════════════
      dbc.Tab(label="🔔 Monitor", tab_id="tab-monitor", children=[
        dbc.Row([dbc.Col([
          dbc.Card([
            dbc.CardHeader([
              dbc.Row([
                dbc.Col(html.H5("🔔 Monitor de Alertas Automáticas", className="text-info mb-0"), md=6),
                dbc.Col([
                  dbc.Button("▶ Iniciar monitoreo", id="btn-iniciar-scheduler",
                             color="success", size="sm", className="me-2"),
                  dbc.Button("⏸ Pausar", id="btn-detener-scheduler",
                             color="danger", size="sm"),
                ], md=6, className="text-end"),
              ])
            ]),
            dbc.CardBody([
              dcc.Interval(id="intervalo-monitor", interval=5_000, n_intervals=0),
              html.Div(id="panel-monitor"),
            ])
          ], style={**ESTILO_CARD, "border":"1px solid #00d4ff"})
        ])], className="mt-3"),

        # Config email reminder
        dbc.Row([dbc.Col([
          dbc.Alert([
            html.Strong("⚙️ Configuración de email: "),
            "Editá el archivo ",
            html.Code("email_sender.py"),
            " con tu Gmail y tu contraseña de aplicación para recibir alertas en el celular.",
          ], color="info", className="mt-2 small"),
        ])]),
      ]),

    ], id="tabs-principales", active_tab="tab-analisis"),

    # ── Footer
    dbc.Row([
        dbc.Col([
            html.Hr(style={"borderColor": "#16213e"}),
            html.P(
                "⚠️ Este análisis es solo educativo y no constituye asesoramiento financiero. "
                "Siempre investigá por tu cuenta antes de invertir.",
                className="text-center text-muted small mb-4"
            )
        ])
    ])

], fluid=True, style={"backgroundColor": "#0f0f1a", "minHeight": "100vh"})


# ============================================================
# CALLBACKS (LÓGICA INTERACTIVA)
# ============================================================
# En Dash, un "callback" es una función que se ejecuta
# automáticamente cuando el usuario hace algo (ej: presiona un botón).
# @app.callback define qué Inputs disparan la función y qué Outputs actualiza.


# ── Callback: dropdown rápido → rellena el input de ticker
@app.callback(
    Output("input-ticker", "value"),
    Input("dropdown-ticker-rapido", "value"),
    prevent_initial_call=True,
)
def rellenar_ticker_desde_dropdown(ticker_seleccionado):
    """Cuando el usuario elige del dropdown, carga el ticker en el input."""
    if ticker_seleccionado:
        return ticker_seleccionado
    return dash.no_update


# ── Callback: escaneo de oportunidades al inicio (y al hacer clic en Actualizar)
@app.callback(
    [
        Output("panel-oportunidades", "children"),
        Output("watchlist-status", "children"),
    ],
    [
        Input("intervalo-inicio", "n_intervals"),
        Input("boton-actualizar-watchlist", "n_clicks"),
    ],
    prevent_initial_call=False,
)
def cargar_oportunidades(n_intervals, n_clicks):
    """
    Se ejecuta automáticamente al abrir la app (via dcc.Interval)
    y también al hacer clic en 'Actualizar'.
    Escanea 10 acciones mixtas y muestra las 5 mejores oportunidades.
    """
    try:
        resultados = escanear_oportunidades(
            n_total=5,
            incluir_argentinas=True,
            incluir_globales=True,
        )

        if not resultados:
            return html.P("No se pudieron obtener datos de mercado.", className="text-muted"), "Sin datos"

        status = f"Última actualización: {__import__('datetime').datetime.now().strftime('%H:%M:%S')} · {len(resultados)} oportunidades encontradas"
        panel = construir_panel_oportunidades(resultados)
        return panel, status

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return html.P(f"Error al escanear: {str(e)}", className="text-danger small"), "Error"


@app.callback(
    [
        Output("panel-empresa", "children"),
        Output("panel-veredicto", "children"),
        Output("panel-grafico", "children"),
        Output("panel-indicadores", "children"),
        Output("panel-noticias", "children"),
        Output("panel-macro", "children"),
        Output("panel-geopolitica", "children"),
        Output("mensaje-error", "children"),
    ],
    Input("boton-analizar", "n_clicks"),
    [
        State("input-ticker", "value"),
        State("input-periodo", "value"),
    ],
    prevent_initial_call=False  # Ejecutar al cargar la página con valor por defecto
)
def analizar(n_clicks, ticker, periodo):  # noqa
    """
    Función principal del dashboard.
    Se ejecuta cuando el usuario presiona "Analizar".
    Descarga datos, calcula indicadores, predice y dibuja todo.
    """

    if not ticker:
        return [], [], [], [], [], "Por favor ingresá un ticker válido."

    ticker = ticker.upper().strip()

    try:
        # ── 1. DESCARGAR DATOS
        df_raw = obtener_precios(ticker, periodo=periodo)
        info = obtener_info_empresa(ticker)
        noticias_raw = obtener_noticias(ticker, empresa=info.get("nombre", ""))

        # ── 2. CALCULAR INDICADORES TÉCNICOS
        df = agregar_todos_los_indicadores(df_raw)
        señales = generar_señales(df)

        # ── 3. ANÁLISIS DE SENTIMIENTO
        sentimiento = analizar_noticias(noticias_raw)

        # ── 4. PREDICCIÓN CON ML
        prediccion_ml = entrenar_y_predecir(df)

        # ── 5. ANÁLISIS MACROECONÓMICO
        sector = info.get('sector') or 'Technology'
        try:
            macro = analizar_macro(sector)
        except Exception as e_macro:
            print(f"⚠️ Error en macro: {e_macro}")
            macro = {"señales": {}, "alertas": [], "puntaje": 0, "sentimiento_macro": "N/D", "señal": 0, "fred": {}, "mercado": {}, "sector": sector}

        # ── 6. ANÁLISIS GEOPOLÍTICO
        try:
            geopolitica = analizar_geopolitica(sector)
        except Exception as e_geo:
            print(f"⚠️ Error en geopolítica: {e_geo}")
            geopolitica = {"señales": {}, "noticias_relevantes": [], "alertas": [], "puntaje": 0, "sentimiento_geo": "N/D", "señal": 0, "sector": sector, "total_noticias_analizadas": 0}

        # ── 7. VEREDICTO FINAL
        veredicto = calcular_veredicto_final(señales, sentimiento, prediccion_ml, macro, geopolitica)

        # ── Construimos cada panel ──────────────────────────────────────────

        panel_empresa = construir_panel_empresa(info, ticker)
        panel_veredicto = construir_panel_veredicto(veredicto, prediccion_ml)
        panel_grafico = construir_panel_grafico(df, ticker)
        panel_indicadores = construir_panel_indicadores(señales)
        panel_noticias = construir_panel_noticias(sentimiento)
        panel_macro = construir_panel_macro(macro)
        panel_geo = construir_panel_geopolitica(geopolitica)

        return panel_empresa, panel_veredicto, panel_grafico, panel_indicadores, panel_noticias, panel_macro, panel_geo, ""

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("=== ERROR COMPLETO ===")
        print(tb)
        error_msg = f"❌ Error: {str(e)} | Detalle: {tb[-300:]}"
        return [], [], [], [], [], [], [], error_msg


# ============================================================
# FUNCIONES PARA CONSTRUIR CADA PANEL DEL DASHBOARD
# ============================================================


def construir_panel_oportunidades(resultados: list):
    """
    Construye las tarjetas de oportunidades de inversión.
    Cada tarjeta es clickeable y carga el análisis completo en el buscador.
    """
    if not resultados:
        return html.P("No hay oportunidades disponibles.", className="text-muted")

    tarjetas = []
    for r in resultados:
        veredicto = r["veredicto"]
        puntaje = r["puntaje"]
        cambio_7d = r["cambio_7d"]
        rsi = r["rsi"]
        moneda = r["moneda"]
        es_arg = r["es_argentina"]

        # Colores según veredicto
        if veredicto == "COMPRAR":
            borde = "#00ff88"
            badge_color = "success"
            fondo = "rgba(0,255,136,0.05)"
        elif veredicto == "VENDER":
            borde = "#ff4466"
            badge_color = "danger"
            fondo = "rgba(255,68,102,0.05)"
        else:
            borde = "#ffd700"
            badge_color = "warning"
            fondo = "rgba(255,215,0,0.05)"

        # Color del cambio 7 días
        color_cambio = "text-success" if cambio_7d >= 0 else "text-danger"
        icono_cambio = "▲" if cambio_7d >= 0 else "▼"

        # Bandera según mercado
        bandera = "🇦🇷" if es_arg else "🌎"

        tarjeta = dbc.Col([
            html.Div([
                # Header de la tarjeta
                dbc.Row([
                    dbc.Col([
                        html.Span(f"{bandera} {r['ticker']}", className="text-info fw-bold"),
                        html.Br(),
                        html.Small(r["nombre"][:22], className="text-muted"),
                    ], md=7),
                    dbc.Col([
                        dbc.Badge(f"{r['emoji']} {veredicto}", color=badge_color,
                                  className="float-end mb-1 d-block"),
                        html.Small(f"Score: {puntaje:+.2f}",
                                   className="text-muted float-end d-block"),
                    ], md=5),
                ], className="mb-2"),

                html.Hr(style={"borderColor": "#333", "margin": "6px 0"}),

                # Métricas
                dbc.Row([
                    dbc.Col([
                        html.Small("Precio", className="text-muted d-block"),
                        html.Span(f"{moneda} {r['precio_actual']:,.2f}",
                                  className="text-white small fw-bold"),
                    ], md=4),
                    dbc.Col([
                        html.Small("7 días", className="text-muted d-block"),
                        html.Span(f"{icono_cambio} {abs(cambio_7d):.1f}%",
                                  className=f"{color_cambio} small fw-bold"),
                    ], md=4),
                    dbc.Col([
                        html.Small("RSI", className="text-muted d-block"),
                        html.Span(str(rsi),
                                  className=f"small fw-bold {'text-danger' if rsi > 70 else 'text-success' if rsi < 30 else 'text-white'}"),
                    ], md=4),
                ], className="mb-2"),

                # Causa principal
                html.Small(
                    f"💡 {r['causa_principal']}",
                    className="text-muted fst-italic",
                    style={"fontSize": "10px", "lineHeight": "1.3"}
                ),

                html.Hr(style={"borderColor": "#333", "margin": "8px 0"}),

                # Botón para análisis completo
                dbc.Button(
                    "Ver análisis completo →",
                    id={"type": "btn-oportunidad", "index": r["ticker"]},
                    color="outline-info",
                    size="sm",
                    className="w-100",
                    style={"fontSize": "11px"}
                ),
            ], style={
                "backgroundColor": fondo,
                "border": f"1px solid {borde}",
                "borderRadius": "10px",
                "padding": "14px",
                "height": "100%",
            })
        ], md=12 // min(len(resultados), 5), className="mb-3")

        tarjetas.append(tarjeta)

    return dbc.Row(tarjetas)

def construir_panel_empresa(info: dict, ticker: str):
    """Panel superior con información general de la empresa."""

    precio = info.get("precio_actual", 0)
    max_a = info.get("maximo_anual", 0)
    min_a = info.get("minimo_anual", 0)
    cap = info.get("capitalizacion", 0)
    moneda = info.get("moneda", "USD")
    es_arg = info.get("es_argentina", False)

    # Formateamos la capitalización de mercado
    if cap >= 1e12:
        cap_str = f"${cap/1e12:.2f}T"
    elif cap >= 1e9:
        cap_str = f"${cap/1e9:.2f}B"
    elif cap >= 1e6:
        cap_str = f"${cap/1e6:.2f}M"
    else:
        cap_str = f"${cap:,.0f}"

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4(f"{info.get('nombre', ticker)} ({ticker})",
                            className="text-info mb-1"),
                    html.P(f"{info.get('sector', '')} · {info.get('industria', '')}",
                           className="text-muted small mb-3"),
                    dbc.Row([
                        dbc.Col([
                            html.H3(f"{moneda} {precio:,.2f}", className="text-white mb-0"),
                            html.Small("Precio actual", className="text-muted"),
                        ], md=3),
                        dbc.Col([
                            html.H5(f"{moneda} {max_a:,.2f}", className="text-success mb-0"),
                            html.Small("Máximo anual", className="text-muted"),
                        ], md=3),
                        dbc.Col([
                            html.H5(f"{moneda} {min_a:,.2f}", className="text-danger mb-0"),
                            html.Small("Mínimo anual", className="text-muted"),
                        ], md=3),
                        dbc.Col([
                            html.H5(cap_str, className="text-warning mb-0"),
                            html.Small("Cap. de mercado", className="text-muted"),
                        ], md=3),
                    ]),
                ])
            ], style=ESTILO_CARD)
        ])
    ])


def construir_panel_veredicto(veredicto: dict, prediccion_ml: dict):
    """Panel central con el veredicto de COMPRAR / VENDER / MANTENER."""

    v = veredicto["veredicto"]
    emoji = veredicto["emoji"]
    puntaje = veredicto["puntaje"]
    confianza = veredicto["confianza"]
    desglose = veredicto["desglose"]

    # Color del veredicto
    if v == "COMPRAR":
        color_v = "#00ff88"
        color_bg = "rgba(0, 255, 136, 0.1)"
    elif v == "VENDER":
        color_v = "#ff4466"
        color_bg = "rgba(255, 68, 102, 0.1)"
    else:
        color_v = "#ffd700"
        color_bg = "rgba(255, 215, 0, 0.1)"

    # Barra de progreso del puntaje (-1 a +1 → 0% a 100%)
    pct = int((puntaje + 1) / 2 * 100)

    precision_ml = prediccion_ml.get("precision_historica", 0)
    prob_subida = prediccion_ml.get("probabilidad_subida", 0.5)

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        # Veredicto principal
                        dbc.Col([
                            html.Div([
                                html.Div(f"{emoji} {v}", style={
                                    **ESTILO_VEREDICTO,
                                    "color": color_v,
                                    "backgroundColor": color_bg,
                                    "border": f"2px solid {color_v}",
                                }),
                                html.P(f"Confianza: {confianza} · Puntaje: {puntaje:+.3f}",
                                       className="text-center text-muted mt-2"),
                                dbc.Progress(value=pct, color="info" if v == "COMPRAR" else "danger" if v == "VENDER" else "warning",
                                             className="mb-2", style={"height": "8px"}),
                                html.P("VENDER ◄────────────────────► COMPRAR",
                                       className="text-center text-muted small"),
                            ])
                        ], md=6),

                        # Desglose del puntaje
                        dbc.Col([
                            html.H6("Desglose del análisis", className="text-info mb-3"),
                            html.Div([
                                fila_desglose("📊 Indicadores técnicos", desglose["tecnico"], peso="40%"),
                                fila_desglose("🤖 Modelo ML", desglose["ml"], peso="25%"),
                                fila_desglose("📰 Sentimiento noticias", desglose["sentimiento"], peso="15%"),
                                fila_desglose("🌐 Macroeconomía", desglose.get("macro", 0), peso="12%"),
                                fila_desglose("🌍 Geopolítica", desglose.get("geo", 0), peso="8%"),
                            ]),
                            html.Hr(style={"borderColor": "#333"}),
                            html.P(f"🤖 ML: {prediccion_ml.get('descripcion', '')}",
                                   className="text-muted small"),
                            html.P(f"📈 Prob. de subida: {prob_subida:.1%} · Precisión histórica del modelo: {precision_ml:.1%}",
                                   className="text-muted small"),
                        ], md=6),
                    ])
                ])
            ], style=ESTILO_CARD)
        ])
    ])


def fila_desglose(nombre: str, valor: float, peso: str = ""):
    """Fila individual del desglose del veredicto."""
    if valor > 0.1:
        color = "text-success"
        icono = "▲"
    elif valor < -0.1:
        color = "text-danger"
        icono = "▼"
    else:
        color = "text-warning"
        icono = "━"

    return html.Div([
        dbc.Row([
            dbc.Col(html.Small(nombre, className="text-muted"), md=7),
            dbc.Col(html.Small(f"{icono} {valor:+.3f}", className=f"{color} fw-bold text-end"), md=3),
            dbc.Col(html.Small(peso, className="text-muted text-end"), md=2),
        ], className="mb-1")
    ])


def construir_panel_grafico(df: pd.DataFrame, ticker: str):
    """Gráfico interactivo de velas japonesas con indicadores superpuestos."""

    close = df["Close"].squeeze()
    open_ = df["Open"].squeeze()
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    # Creamos una figura con 3 subplots:
    # 1. Velas japonesas + Medias móviles + Bollinger
    # 2. Volumen
    # 3. RSI
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(f"{ticker} - Velas Japonesas", "Volumen", "RSI (14)")
    )

    # ── Velas japonesas
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=open_, high=high, low=low, close=close,
        name="Precio",
        increasing_line_color="#00ff88",
        decreasing_line_color="#ff4466",
        increasing_fillcolor="#00ff88",
        decreasing_fillcolor="#ff4466",
    ), row=1, col=1)

    # ── Bandas de Bollinger
    fig.add_trace(go.Scatter(
        x=df.index, y=df["BB_Superior"].squeeze(),
        name="BB Superior", line=dict(color="rgba(100,149,237,0.5)", dash="dot"),
        showlegend=True
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["BB_Inferior"].squeeze(),
        name="BB Inferior", line=dict(color="rgba(100,149,237,0.5)", dash="dot"),
        fill="tonexty", fillcolor="rgba(100,149,237,0.05)",
        showlegend=True
    ), row=1, col=1)

    # ── Medias Móviles
    fig.add_trace(go.Scatter(
        x=df.index, y=df["SMA_20"].squeeze(),
        name="SMA 20", line=dict(color="#ffd700", width=1.5)
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["SMA_50"].squeeze(),
        name="SMA 50", line=dict(color="#ff9500", width=1.5)
    ), row=1, col=1)

    # ── Volumen (barras de color según vela sube o baja)
    colores_vol = ["#00ff88" if c >= o else "#ff4466"
                   for c, o in zip(close, open_)]

    fig.add_trace(go.Bar(
        x=df.index, y=volume,
        name="Volumen", marker_color=colores_vol, opacity=0.7
    ), row=2, col=1)

    # ── RSI
    rsi = df["RSI"].squeeze()
    fig.add_trace(go.Scatter(
        x=df.index, y=rsi,
        name="RSI", line=dict(color="#00d4ff", width=2)
    ), row=3, col=1)

    # Líneas de referencia del RSI (70 = sobrecompra, 30 = sobreventa)
    fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.3, row=3, col=1)

    # ── Estilo del gráfico
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#0f0f1a",
        height=700,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_rangeslider_visible=False,
        font=dict(color="#aaaaaa"),
    )
    fig.update_yaxes(showgrid=True, gridcolor="#1e1e2e")
    fig.update_xaxes(showgrid=False)

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(figure=fig, config={"displayModeBar": True, "scrollZoom": True})
                ])
            ], style=ESTILO_CARD)
        ])
    ])


def construir_panel_indicadores(señales: dict):
    """Panel con el resumen de cada indicador técnico."""

    filas = []
    for nombre, datos in señales.items():
        señal = datos["señal"]
        if señal > 0:
            badge_color = "success"
            badge_text = "COMPRA ▲"
        elif señal < 0:
            badge_color = "danger"
            badge_text = "VENTA ▼"
        else:
            badge_color = "warning"
            badge_text = "NEUTRAL ━"

        filas.append(
            dbc.ListGroupItem([
                dbc.Row([
                    dbc.Col(html.Span(nombre.replace("_", " "), className="text-light fw-bold"), md=3),
                    dbc.Col(html.Span(datos["descripcion"], className="text-muted small"), md=7),
                    dbc.Col(dbc.Badge(badge_text, color=badge_color, className="float-end"), md=2),
                ])
            ], style={"backgroundColor": "#1a1a2e", "border": "1px solid #16213e"})
        )

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("📊 Indicadores Técnicos", className="text-info mb-0")),
                dbc.CardBody([
                    dbc.ListGroup(filas, flush=True)
                ])
            ], style=ESTILO_CARD)
        ])
    ])


def construir_panel_noticias(sentimiento: dict):
    """Panel con las noticias analizadas y su sentimiento."""

    noticias = sentimiento.get("noticias_analizadas", [])
    conteo = sentimiento.get("conteo", {})
    general = sentimiento.get("sentimiento_general", "Neutral")
    promedio = sentimiento.get("puntaje_promedio", 0)

    # Badge de sentimiento general
    if general == "Positivo":
        color_general = "success"
    elif general == "Negativo":
        color_general = "danger"
    else:
        color_general = "warning"

    items_noticias = []
    for n in noticias[:8]:  # Mostramos máximo 8 noticias
        etiqueta = n.get("etiqueta", "Neutral")
        puntaje_n = n.get("puntaje", 0)

        if etiqueta == "Positivo":
            color_badge = "success"
            icono = "📈"
        elif etiqueta == "Negativo":
            color_badge = "danger"
            icono = "📉"
        else:
            color_badge = "secondary"
            icono = "➖"

        items_noticias.append(
            dbc.ListGroupItem([
                dbc.Row([
                    dbc.Col([
                        html.A(
                            n.get("titulo", "Sin título"),
                            href=n.get("link", "#"),
                            target="_blank",
                            className="text-light small",
                            style={"textDecoration": "none"}
                        ),
                        html.Br(),
                        html.Small(n.get("fecha", "")[:25], className="text-muted"),
                    ], md=10),
                    dbc.Col([
                        dbc.Badge(f"{icono} {puntaje_n:+.2f}", color=color_badge, className="float-end")
                    ], md=2),
                ])
            ], style={"backgroundColor": "#1a1a2e", "border": "1px solid #16213e"})
        )

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    dbc.Row([
                        dbc.Col(html.H5("📰 Noticias y Sentimiento", className="text-info mb-0"), md=6),
                        dbc.Col([
                            dbc.Badge(f"General: {general} ({promedio:+.3f})", color=color_general, className="me-2"),
                            dbc.Badge(f"✅ {conteo.get('Positivo', 0)} pos", color="success", className="me-1"),
                            dbc.Badge(f"❌ {conteo.get('Negativo', 0)} neg", color="danger", className="me-1"),
                            dbc.Badge(f"➖ {conteo.get('Neutral', 0)} neu", color="secondary"),
                        ], md=6, className="text-end"),
                    ])
                ]),
                dbc.CardBody([
                    dbc.ListGroup(items_noticias if items_noticias else [
                        dbc.ListGroupItem("No se encontraron noticias recientes.",
                                          style={"backgroundColor": "#1a1a2e"})
                    ], flush=True)
                ])
            ], style=ESTILO_CARD)
        ])
    ])



def construir_panel_macro(macro: dict):
    """Panel con indicadores macroeconómicos y su impacto sectorial."""

    if not macro or not macro.get("señales"):
        return dbc.Row([dbc.Col([dbc.Card([
            dbc.CardHeader(html.H5("🌐 Análisis Macroeconómico", className="text-info mb-0")),
            dbc.CardBody(html.P("No se pudieron obtener datos macroeconómicos.", className="text-muted"))
        ], style=ESTILO_CARD)])])

    señales = macro.get("señales", {})
    alertas = macro.get("alertas", [])
    sentimiento_macro = macro.get("sentimiento_macro", "Mixto")
    puntaje = macro.get("puntaje", 0)
    fred_data = macro.get("fred", {})
    mercado_data = macro.get("mercado", {})

    color_badge = "success" if sentimiento_macro == "Favorable" else "danger" if sentimiento_macro == "Desfavorable" else "warning"

    # Filas de señales macro
    filas_señales = []
    for nombre, datos in señales.items():
        impacto = datos.get("impacto", 0)
        if impacto > 0:
            badge_color, badge_text, icono = "success", "POSITIVO ▲", "🟢"
        elif impacto < 0:
            badge_color, badge_text, icono = "danger", "NEGATIVO ▼", "🔴"
        else:
            badge_color, badge_text, icono = "warning", "NEUTRAL ━", "🟡"

        filas_señales.append(
            dbc.ListGroupItem([
                dbc.Row([
                    dbc.Col(html.Span(f"{icono} {nombre}", className="text-light fw-bold small"), md=3),
                    dbc.Col(html.Span(datos.get("descripcion", ""), className="text-muted small"), md=7),
                    dbc.Col(dbc.Badge(badge_text, color=badge_color, className="float-end small"), md=2),
                ])
            ], style={"backgroundColor": "#1a1a2e", "border": "1px solid #16213e"})
        )

    # Métricas clave de FRED y mercado
    metricas = []
    for key, datos in fred_data.items():
        if not datos.get("error") and datos.get("valor_actual") is not None:
            tendencia = datos.get("tendencia", "")
            color_tend = "text-success" if "▲" in tendencia else "text-danger" if "▼" in tendencia else "text-muted"
            metricas.append(
                dbc.Col([
                    html.Div([
                        html.Small(datos.get("nombre", key), className="text-muted d-block"),
                        html.Span(f"{datos['valor_actual']}", className="text-white fw-bold"),
                        html.Span(f" {tendencia}", className=f"{color_tend} small"),
                    ], style={"backgroundColor": "#16213e", "borderRadius": "8px", "padding": "10px", "margin": "4px"})
                ], md=2)
            )

    for key, datos in mercado_data.items():
        if not datos.get("error") and datos.get("valor") is not None:
            cambio = datos.get("cambio_pct", 0) or 0
            color_cambio = "text-success" if cambio >= 0 else "text-danger"
            metricas.append(
                dbc.Col([
                    html.Div([
                        html.Small(datos.get("nombre", key), className="text-muted d-block"),
                        html.Span(f"{datos['valor']}", className="text-white fw-bold"),
                        html.Span(f" ({cambio:+.1f}%)", className=f"{color_cambio} small"),
                    ], style={"backgroundColor": "#16213e", "borderRadius": "8px", "padding": "10px", "margin": "4px"})
                ], md=2)
            )

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    dbc.Row([
                        dbc.Col(html.H5("🌐 Análisis Macroeconómico", className="text-info mb-0"), md=7),
                        dbc.Col([
                            dbc.Badge(f"Entorno: {sentimiento_macro} ({puntaje:+.3f})", color=color_badge)
                        ], md=5, className="text-end"),
                    ])
                ]),
                dbc.CardBody([
                    # Métricas de datos
                    dbc.Row(metricas, className="mb-3"),
                    # Alertas críticas
                    *([html.Div([
                        dbc.Alert(alerta, color="danger" if "🚨" in alerta else "warning", className="py-2 mb-1 small")
                        for alerta in alertas
                    ])] if alertas else []),
                    # Señales
                    dbc.ListGroup(filas_señales, flush=True),
                ])
            ], style=ESTILO_CARD)
        ])
    ])


def construir_panel_geopolitica(geopolitica: dict):
    """Panel con análisis geopolítico y su impacto sobre el sector."""

    if not geopolitica or not geopolitica.get("señales"):
        return dbc.Row([dbc.Col([dbc.Card([
            dbc.CardHeader(html.H5("🌍 Análisis Geopolítico", className="text-info mb-0")),
            dbc.CardBody(html.P("No se detectaron eventos geopolíticos relevantes.", className="text-muted"))
        ], style=ESTILO_CARD)])])

    señales = geopolitica.get("señales", {})
    noticias = geopolitica.get("noticias_relevantes", [])
    alertas = geopolitica.get("alertas", [])
    sentimiento_geo = geopolitica.get("sentimiento_geo", "Mixto")
    puntaje = geopolitica.get("puntaje", 0)
    total = geopolitica.get("total_noticias_analizadas", 0)
    sector = geopolitica.get("sector", "")

    color_badge = "success" if sentimiento_geo == "Favorable" else "danger" if sentimiento_geo == "Desfavorable" else "warning"

    # Tarjetas de categorías detectadas
    tarjetas_cat = []
    for cat_id, datos in señales.items():
        impacto = datos.get("impacto", 0)
        if impacto > 0:
            border_color, icono = "#00ff88", "📈"
        elif impacto < 0:
            border_color, icono = "#ff4466", "📉"
        else:
            border_color, icono = "#ffd700", "━"

        tarjetas_cat.append(
            dbc.Col([
                html.Div([
                    html.Div(f"{icono} {datos['descripcion']}", className="text-white small fw-bold mb-1"),
                    html.Div(f"{datos['noticias_detectadas']} noticias · Impacto: {datos['impacto_sector']}",
                             className="text-muted", style={"fontSize": "11px"}),
                    html.Div(f'"{datos["ejemplo_titulo"][:60]}..."',
                             className="text-muted fst-italic", style={"fontSize": "10px", "marginTop": "4px"}) if datos.get("ejemplo_titulo") else html.Div(),
                ], style={"backgroundColor": "#16213e", "borderLeft": f"3px solid {border_color}",
                          "borderRadius": "6px", "padding": "10px", "marginBottom": "8px"})
            ], md=6)
        )

    # Noticias geopolíticas relevantes (top 8)
    items_noticias_geo = []
    for n in noticias[:8]:
        impacto = n.get("impacto", 0)
        color_imp = "success" if impacto > 0 else "danger" if impacto < 0 else "secondary"
        items_noticias_geo.append(
            dbc.ListGroupItem([
                dbc.Row([
                    dbc.Col([
                        html.Small(dbc.Badge(n.get("categoria", ""), color="info", className="me-2")),
                        html.Small(dbc.Badge(n.get("fuente", ""), color="secondary")),
                        html.Br(),
                        html.A(n.get("titulo", "")[:100], href=n.get("link", "#"),
                               target="_blank", className="text-light small",
                               style={"textDecoration": "none"}),
                    ], md=10),
                    dbc.Col([
                        dbc.Badge(f"{impacto:+d}", color=color_imp, className="float-end")
                    ], md=2),
                ])
            ], style={"backgroundColor": "#1a1a2e", "border": "1px solid #16213e"})
        )

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    dbc.Row([
                        dbc.Col(html.H5("🌍 Análisis Geopolítico", className="text-info mb-0"), md=7),
                        dbc.Col([
                            dbc.Badge(f"Impacto en {sector}: {sentimiento_geo} ({puntaje:+.3f})", color=color_badge, className="me-2"),
                            dbc.Badge(f"{total} noticias analizadas", color="secondary"),
                        ], md=5, className="text-end"),
                    ])
                ]),
                dbc.CardBody([
                    # Alertas
                    *([html.Div([
                        dbc.Alert(alerta, color="warning", className="py-2 mb-1 small")
                        for alerta in alertas
                    ])] if alertas else []),
                    # Categorías detectadas
                    html.H6("Categorías de riesgo detectadas:", className="text-muted mb-2"),
                    dbc.Row(tarjetas_cat, className="mb-3") if tarjetas_cat else html.P("Sin categorías de riesgo detectadas.", className="text-muted small"),
                    # Noticias relevantes
                    html.H6("Noticias geopolíticas relevantes:", className="text-muted mb-2"),
                    dbc.ListGroup(items_noticias_geo if items_noticias_geo else [
                        dbc.ListGroupItem("No se encontraron noticias geopolíticas relevantes.",
                                          style={"backgroundColor": "#1a1a2e"})
                    ], flush=True),
                ])
            ], style=ESTILO_CARD)
        ])
    ])

# ── Callback: botón "Ver análisis completo" en tarjetas de oportunidades
from dash import ctx, ALL

@app.callback(
    [Output("input-ticker", "value", allow_duplicate=True),
     Output("boton-analizar", "n_clicks")],
    Input({"type": "btn-oportunidad", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def cargar_ticker_desde_oportunidad(n_clicks_list):
    """
    Cuando el usuario hace clic en 'Ver análisis completo' de una tarjeta,
    carga ese ticker en el input y dispara el análisis automáticamente.
    """
    if not any(n for n in n_clicks_list if n):
        return dash.no_update, dash.no_update

    # Identificamos cuál botón se presionó
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        ticker = triggered.get("index", "")
        if ticker:
            return ticker, 1  # Carga el ticker y simula clic en Analizar

    return dash.no_update, dash.no_update




# ── Callback: scheduler iniciar/detener
@app.callback(
    Output("panel-monitor", "children"),
    [Input("btn-iniciar-scheduler", "n_clicks"),
     Input("btn-detener-scheduler", "n_clicks"),
     Input("intervalo-monitor", "n_intervals")],
    prevent_initial_call=False,
)
def controlar_scheduler(n_ini, n_det, n_int):
    from dash import ctx
    trigger = ctx.triggered_id if ctx.triggered_id else "intervalo-monitor"

    if trigger == "btn-iniciar-scheduler" and n_ini:
        msg = iniciar_scheduler()
    elif trigger == "btn-detener-scheduler" and n_det:
        msg = detener_scheduler()
    else:
        msg = None

    estado = obtener_estado()
    activo = estado["activo"]

    badge = dbc.Badge("🟢 ACTIVO", color="success") if activo else dbc.Badge("🔴 INACTIVO", color="danger")

    log_items = [
        html.Li(linea, className="text-muted small",
                style={"fontFamily": "monospace", "fontSize": "11px"})
        for linea in reversed(estado["log"])
    ] or [html.Li("Sin actividad aún.", className="text-muted small")]

    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Span("Estado: ", className="text-muted small me-2"),
                badge,
            ], md=4),
            dbc.Col([
                html.Small(f"Última revisión: {estado['ultima_revision'] or '—'}", className="text-muted d-block"),
                html.Small(f"Próxima revisión: {estado['proxima_revision'] or '—'}", className="text-muted d-block"),
            ], md=4),
            dbc.Col([
                html.Small(f"Alertas esta sesión: {estado['alertas_sesion']}", className="text-muted d-block"),
                html.Small(f"Intervalo: cada 1 hora", className="text-muted d-block"),
            ], md=4),
        ], className="mb-3"),
        dbc.Alert(msg, color="info", className="py-2 small") if msg else html.Div(),
        html.H6("Log de actividad:", className="text-muted mt-2 mb-1"),
        html.Ul(log_items, style={"maxHeight": "300px", "overflowY": "auto",
                                   "backgroundColor": "#0f0f1a", "padding": "10px",
                                   "borderRadius": "6px", "listStyle": "none"}),
    ])


# ── Callback: panel de paper trading
@app.callback(
    Output("panel-paper-trading", "children"),
    Input("intervalo-paper", "n_intervals"),
    prevent_initial_call=False,
)
def actualizar_paper_trading(n):
    resumen = calcular_resumen()
    historial = cargar_historial()

    cap_actual  = resumen["capital_actual"]
    cap_inicial = resumen["capital_inicial"]
    rend        = resumen["rendimiento_total"]
    color_rend  = "text-success" if rend >= 0 else "text-danger"
    icono_rend  = "▲" if rend >= 0 else "▼"

    # Métricas principales
    metricas = dbc.Row([
        dbc.Col(html.Div([
            html.Small("Capital actual", className="text-muted d-block"),
            html.H4(f"USD {cap_actual:,.2f}", className="text-white mb-0"),
        ], style={"backgroundColor":"#16213e","borderRadius":"8px","padding":"14px"}), md=3),
        dbc.Col(html.Div([
            html.Small("Rendimiento total", className="text-muted d-block"),
            html.H4(f"{icono_rend} {abs(rend):.2f}%", className=f"{color_rend} mb-0"),
        ], style={"backgroundColor":"#16213e","borderRadius":"8px","padding":"14px"}), md=3),
        dbc.Col(html.Div([
            html.Small("Operaciones cerradas", className="text-muted d-block"),
            html.H4(str(resumen["operaciones_cerradas"]), className="text-white mb-0"),
            html.Small(f"Ganadas: {resumen['operaciones_ganadas']} · "
                       f"Tasa acierto: {resumen['tasa_acierto']:.0f}%", className="text-muted"),
        ], style={"backgroundColor":"#16213e","borderRadius":"8px","padding":"14px"}), md=3),
        dbc.Col(html.Div([
            html.Small("Precisión del modelo", className="text-muted d-block"),
            html.H4(
                f"{resumen['precision_modelo']:.1f}%" if resumen['precision_modelo'] else "Sin datos",
                className="text-info mb-0"
            ),
            html.Small("(señales evaluadas vs resultado real)", className="text-muted"),
        ], style={"backgroundColor":"#16213e","borderRadius":"8px","padding":"14px"}), md=3),
    ], className="mb-3")

    # Posiciones abiertas
    posiciones = historial.get("posiciones", {})
    if posiciones:
        filas_pos = []
        for tick, pos in posiciones.items():
            filas_pos.append(dbc.ListGroupItem([
                dbc.Row([
                    dbc.Col(html.Span(f"📌 {tick}", className="text-info fw-bold"), md=2),
                    dbc.Col(html.Small(f"Entrada: {pos['moneda']} {pos['precio_entrada']:,.2f}", className="text-muted"), md=3),
                    dbc.Col(html.Small(f"Cantidad: {pos['cantidad']:.4f}", className="text-muted"), md=3),
                    dbc.Col(html.Small(f"Invertido: USD {pos['monto_invertido']:,.2f}", className="text-muted"), md=2),
                    dbc.Col(
                        dbc.Button("Simular venta", id={"type":"btn-vender","index":tick},
                                   color="outline-danger", size="sm"),
                        md=2
                    ),
                ])
            ], style={"backgroundColor":"#1a1a2e","border":"1px solid #16213e"}))
        panel_posiciones = html.Div([
            html.H6("📌 Posiciones abiertas", className="text-warning mt-3 mb-2"),
            dbc.ListGroup(filas_pos, flush=True),
        ])
    else:
        panel_posiciones = html.Div()

    # Alertas recientes con botón de simular compra
    alertas_rec = resumen.get("alertas_recientes", [])
    filas_alertas = []
    for a in alertas_rec:
        v = a.get("veredicto","")
        color_v = "success" if v == "COMPRAR" else "danger" if v == "VENDER" else "warning"
        decision = a.get("decision_usuario")
        filas_alertas.append(dbc.ListGroupItem([
            dbc.Row([
                dbc.Col(dbc.Badge(f"{a.get('emoji','')} {v}", color=color_v), md=2),
                dbc.Col(html.Small(f"{a.get('ticker','')} · {a.get('timestamp','')}", className="text-muted"), md=3),
                dbc.Col(html.Small(a.get("causa_principal","")[:60], className="text-muted fst-italic"), md=5),
                dbc.Col(
                    html.Small(f"✅ {decision}", className="text-success") if decision
                    else dbc.Button("💰 Simular compra",
                                    id={"type":"btn-comprar","index":a.get("id",0)},
                                    color="outline-success", size="sm"),
                    md=2
                ),
            ])
        ], style={"backgroundColor":"#1a1a2e","border":"1px solid #16213e"}))

    panel_alertas = html.Div([
        html.H6("🔔 Alertas recientes", className="text-info mt-3 mb-2"),
        dbc.ListGroup(filas_alertas, flush=True) if filas_alertas
        else html.P("Aún no hay alertas. Iniciá el monitor en la pestaña 🔔 Monitor.", className="text-muted small"),
    ])

    return html.Div([metricas, panel_posiciones, panel_alertas])


# ── Callback: simular compra desde paper trading
@app.callback(
    Output("panel-paper-trading", "children", allow_duplicate=True),
    Input({"type": "btn-comprar", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def ejecutar_compra(n_clicks_list):
    from dash import ctx
    if not any(n for n in (n_clicks_list or []) if n):
        return dash.no_update
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        alerta_id = triggered.get("index", 0)
        resultado = simular_compra(alerta_id, monto_usd=1000.0)
        print(resultado["msg"])
    return actualizar_paper_trading(0)


# ── Callback: simular venta desde paper trading
@app.callback(
    Output("panel-paper-trading", "children", allow_duplicate=True),
    Input({"type": "btn-vender", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def ejecutar_venta(n_clicks_list):
    from dash import ctx
    if not any(n for n in (n_clicks_list or []) if n):
        return dash.no_update
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        ticker = triggered.get("index", "")
        resultado = simular_venta(ticker)
        print(resultado["msg"])
    return actualizar_paper_trading(0)


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("  📈 Market Analyzer - Dashboard de Análisis Bursátil")
    print("=" * 55)
    print("  🌐 Abrí tu navegador en: http://127.0.0.1:8050")
    print("  🛑 Para detener: presioná Ctrl+C en la terminal")
    print("=" * 55)

    # debug=True permite ver errores en el navegador durante desarrollo
    # Cambiar a False en producción
    app.run(debug=True, port=8050, use_reloader=False)
