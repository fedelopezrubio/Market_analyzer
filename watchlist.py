# ============================================================
# watchlist.py
# ------------------------------------------------------------
# Este módulo escanea una lista de acciones predefinidas
# (argentinas + globales) y las rankea por oportunidad
# de inversión al momento de abrir la app.
#
# Para cada acción calcula un puntaje rápido basado en:
#   - Indicadores técnicos (RSI, MACD, Bollinger, SMAs)
#   - Predicción del modelo ML
#   - Datos macroeconómicos cacheados (se calculan una sola vez)
#
# El análisis de noticias y geopolítica se omite en el
# escaneo rápido para no tardar demasiado. Se muestra
# el detalle completo solo cuando el usuario hace clic.
# ============================================================

import yfinance as yf
import pandas as pd
import concurrent.futures
from data_fetcher import obtener_precios, obtener_info_empresa
from technical import agregar_todos_los_indicadores, generar_señales
from predictor import entrenar_y_predecir


# ============================================================
# LISTAS DE ACCIONES PREDEFINIDAS
# ============================================================

# Acciones argentinas (Bolsa de Buenos Aires - BYMA)
# Yahoo Finance las reconoce con el sufijo .BA
# ──────────────────────────────────────────────────────────
# TICKERS VERIFICADOS EN YAHOO FINANCE
# Incluye acciones del MERVAL y CEDEARs (sufijo .BA)
# Nota: YPF cotiza como YPFD.BA (no YPF.BA) en Yahoo Finance
# CEDEARs: certificados de acciones extranjeras que cotizan
# en pesos en la bolsa argentina (BYMA)
# ──────────────────────────────────────────────────────────
ACCIONES_ARGENTINAS = [
    # ── Acciones MERVAL ──
    ("GGAL.BA",  "Grupo Financiero Galicia",   "Financials"),
    ("YPFD.BA",  "YPF S.A.",                   "Energy"),
    ("BMA.BA",   "Banco Macro",                "Financials"),
    ("PAMP.BA",  "Pampa Energía",              "Utilities"),
    ("TXAR.BA",  "Ternium Argentina",          "Materials"),
    ("ALUA.BA",  "Aluar Aluminio",             "Materials"),
    ("CEPU.BA",  "Central Puerto",             "Utilities"),
    ("TECO2.BA", "Telecom Argentina",          "Communication Services"),
    ("CRES.BA",  "Cresud",                     "Real Estate"),
    ("LOMA.BA",  "Loma Negra",                "Materials"),
    ("EDN.BA",   "Edenor",                     "Utilities"),
    ("TGSU2.BA", "Transportadora Gas Sur",     "Energy"),
    ("IRSA.BA",  "IRSA Inversiones",           "Real Estate"),
    ("METR.BA",  "Metrogas",                   "Utilities"),
    ("COME.BA",  "Soc. Comercial del Plata",   "Consumer Discretionary"),
    # ── CEDEARs (acciones globales que cotizan en BYMA en ARS) ──
    ("AAPL.BA",  "CEDEAR Apple",               "Technology"),
    ("MSFT.BA",  "CEDEAR Microsoft",           "Technology"),
    ("GOOGL.BA", "CEDEAR Alphabet",            "Technology"),
    ("AMZN.BA",  "CEDEAR Amazon",              "Consumer Discretionary"),
    ("TSLA.BA",  "CEDEAR Tesla",               "Consumer Discretionary"),
    ("NVDA.BA",  "CEDEAR NVIDIA",              "Technology"),
    ("META.BA",  "CEDEAR Meta",                "Communication Services"),
    ("BABA.BA",  "CEDEAR Alibaba",             "Consumer Discretionary"),
    ("GOLD.BA",  "CEDEAR Barrick Gold",        "Materials"),
    ("KO.BA",    "CEDEAR Coca-Cola",           "Consumer Staples"),
]

# Acciones globales (NYSE / NASDAQ)
ACCIONES_GLOBALES = [
    # ── Tecnología ──
    ("AAPL",  "Apple",              "Technology"),
    ("MSFT",  "Microsoft",          "Technology"),
    ("GOOGL", "Alphabet",           "Technology"),
    ("NVDA",  "NVIDIA",             "Technology"),
    ("META",  "Meta",               "Communication Services"),
    ("ORCL",  "Oracle",             "Technology"),
    ("CRM",   "Salesforce",         "Technology"),
    # ── Consumo / Retail ──
    ("AMZN",  "Amazon",             "Consumer Discretionary"),
    ("TSLA",  "Tesla",              "Consumer Discretionary"),
    ("WMT",   "Walmart",            "Consumer Staples"),
    ("PG",    "Procter & Gamble",   "Consumer Staples"),
    ("KO",    "Coca-Cola",          "Consumer Staples"),
    # ── Finanzas ──
    ("JPM",   "JPMorgan Chase",     "Financials"),
    ("BAC",   "Bank of America",    "Financials"),
    ("MA",    "Mastercard",         "Financials"),
    ("GS",    "Goldman Sachs",      "Financials"),
    ("V",     "Visa",               "Financials"),
    # ── Energía / Materiales ──
    ("XOM",   "ExxonMobil",         "Energy"),
    ("CVX",   "Chevron",            "Energy"),
    ("GOLD",  "Barrick Gold",       "Materials"),
    # ── Salud ──
    ("JNJ",   "Johnson & Johnson",  "Health Care"),
    ("PFE",   "Pfizer",             "Health Care"),
    # ── Otros ──
    ("DIS",   "Disney",             "Communication Services"),
    ("NFLX",  "Netflix",            "Communication Services"),
    ("BRK-B", "Berkshire Hathaway", "Financials"),
    ("BA",    "Boeing",             "Industrials"),
    ("CAT",   "Caterpillar",        "Industrials"),
    ("LLY",   "Eli Lilly",          "Health Care"),
]

# Lista combinada completa para referencia en el buscador
TODOS_LOS_TICKERS = ACCIONES_ARGENTINAS + ACCIONES_GLOBALES


def analisis_rapido(ticker: str, nombre: str, sector: str) -> dict:
    """
    Hace un análisis rápido de una acción para el panel de oportunidades.
    Solo usa indicadores técnicos + ML (sin noticias ni geopolítica,
    para que sea rápido).

    Retorna un diccionario con el veredicto y los datos clave,
    o None si hubo un error (acción sin datos, etc.).
    """
    try:
        # Descargamos 6 meses de datos
        df_raw = obtener_precios(ticker, periodo="6mo")
        if df_raw is None or df_raw.empty or len(df_raw) < 30:
            return None

        # Calculamos indicadores técnicos
        df = agregar_todos_los_indicadores(df_raw)
        señales = generar_señales(df)

        # Puntaje técnico (promedio de votos)
        votos = [v["señal"] for v in señales.values()]
        puntaje_tecnico = sum(votos) / len(votos) if votos else 0

        # Predicción ML rápida
        ml = entrenar_y_predecir(df, dias_futuro=5)
        puntaje_ml = ml.get("señal", 0)

        # Puntaje combinado (70% técnico, 30% ML — sin macro/geo para velocidad)
        puntaje_total = puntaje_tecnico * 0.70 + puntaje_ml * 0.30

        # Precio actual y cambio reciente
        close = df_raw["Close"].squeeze()
        precio_actual = float(close.iloc[-1])
        precio_semana = float(close.iloc[-6]) if len(close) > 5 else precio_actual
        cambio_7d = ((precio_actual - precio_semana) / precio_semana * 100) if precio_semana else 0

        # RSI actual para mostrar en la tarjeta
        rsi_actual = float(df["RSI"].squeeze().iloc[-1]) if "RSI" in df.columns else 50

        # Determinar veredicto
        if puntaje_total > 0.2:
            veredicto = "COMPRAR"
            emoji = "🟢"
        elif puntaje_total < -0.2:
            veredicto = "VENDER"
            emoji = "🔴"
        else:
            veredicto = "MANTENER"
            emoji = "🟡"

        # Causa principal: el indicador con señal más extrema
        causa = max(señales.values(), key=lambda x: abs(x["señal"]))["descripcion"]
        # Truncamos para que quepa en la tarjeta
        causa = causa[:80] + "..." if len(causa) > 80 else causa

        # Detectar si es argentina (sufijo .BA)
        es_argentina = ticker.endswith(".BA")
        moneda = "ARS" if es_argentina else "USD"

        return {
            "ticker": ticker,
            "nombre": nombre,
            "sector": sector,
            "veredicto": veredicto,
            "emoji": emoji,
            "puntaje": round(puntaje_total, 3),
            "precio_actual": round(precio_actual, 2),
            "cambio_7d": round(cambio_7d, 2),
            "rsi": round(rsi_actual, 1),
            "prob_subida": ml.get("probabilidad_subida", 0.5),
            "causa_principal": causa,
            "es_argentina": es_argentina,
            "moneda": moneda,
        }

    except Exception as e:
        print(f"  ⚠️ Error analizando {ticker}: {e}")
        return None


def escanear_oportunidades(
    n_total: int = 5,
    incluir_argentinas: bool = True,
    incluir_globales: bool = True,
) -> list:
    """
    Escanea el universo de acciones y retorna las N mejores oportunidades.

    Para ser rápido, analiza en paralelo usando ThreadPoolExecutor.
    Prioriza mostrar resultados mixtos (argentinas + globales).

    Parámetros:
    -----------
    n_total         : Cuántas acciones mostrar en el panel final
    incluir_argentinas: Si incluir acciones del MERVAL
    incluir_globales  : Si incluir acciones de NYSE/NASDAQ

    Retorna:
    --------
    Lista de dicts ordenada de mayor a menor puntaje (oportunidad)
    """

    # Construimos la lista a analizar
    # Tomamos una muestra representativa para no tardar demasiado:
    # 5 argentinas + 5 globales → analizamos 10 y mostramos las 5 mejores
    lista_a_analizar = []

    if incluir_argentinas:
        # Las primeras 8 argentinas/CEDEARs más líquidas
        lista_a_analizar += [(t, n, s) for t, n, s in ACCIONES_ARGENTINAS[:8]]

    if incluir_globales:
        # Las primeras 7 globales
        lista_a_analizar += [(t, n, s) for t, n, s in ACCIONES_GLOBALES[:7]]

    print(f"\n🔍 Escaneando {len(lista_a_analizar)} acciones en busca de oportunidades...")

    resultados = []

    # Análisis en paralelo: analiza varias acciones simultáneamente
    # max_workers=4: hasta 4 descargas en paralelo (no sobrecargar Yahoo Finance)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futuros = {
            executor.submit(analisis_rapido, ticker, nombre, sector): ticker
            for ticker, nombre, sector in lista_a_analizar
        }

        for futuro in concurrent.futures.as_completed(futuros):
            ticker = futuros[futuro]
            try:
                resultado = futuro.result(timeout=30)
                if resultado is not None:
                    resultados.append(resultado)
                    print(f"  ✅ {ticker}: {resultado['veredicto']} (puntaje: {resultado['puntaje']:+.3f})")
            except Exception as e:
                print(f"  ❌ {ticker} falló: {e}")

    # Ordenamos por puntaje absoluto (más extremo = más decisivo)
    # Primero las COMPRAS (puntaje > 0) ordenadas de mayor a menor
    # Luego las VENTAS (puntaje < 0) de menor a mayor (más negativo = más urgente)
    compras = sorted([r for r in resultados if r["puntaje"] > 0.1],
                     key=lambda x: x["puntaje"], reverse=True)
    mantener = sorted([r for r in resultados if -0.1 <= r["puntaje"] <= 0.1],
                      key=lambda x: abs(x["puntaje"]), reverse=True)
    ventas = sorted([r for r in resultados if r["puntaje"] < -0.1],
                    key=lambda x: x["puntaje"])

    # Combinamos: primero las mejores oportunidades de compra,
    # después neutras y finalmente alertas de venta
    ranking = (compras + mantener + ventas)[:n_total]

    print(f"\n✅ Escaneo completo: {len(compras)} compras, {len(mantener)} neutral, {len(ventas)} ventas")
    return ranking
