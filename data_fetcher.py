# ============================================================
# data_fetcher.py
# ------------------------------------------------------------
# Este módulo se encarga de conseguir toda la información
# que el programa necesita:
#   1. Precios históricos (velas japonesas) de Yahoo Finance
#   2. Noticias recientes sobre la empresa
#
# ACCIONES ARGENTINAS:
#   Yahoo Finance las identifica con el sufijo ".BA"
#   Ej: YPF.BA, GGAL.BA, BMA.BA
#   Diferencias vs acciones globales:
#   - Cotizan en pesos argentinos (ARS)
#   - Menor liquidez → algunos días sin volumen
#   - El campo "sector" a veces viene vacío
#   - "currentPrice" suele venir en None → usamos el último Close
# ============================================================

import yfinance as yf
import feedparser
import pandas as pd
import numpy as np


# ============================================================
# TICKERS ARGENTINOS VERIFICADOS EN YAHOO FINANCE
# ------------------------------------------------------------
# Importante: varios tickers del MERVAL usan nombres distintos
# en Yahoo Finance respecto a los que se ven en los brokers.
# Esta tabla tiene los tickers EXACTOS que funcionan.
# ============================================================

SECTORES_ARGENTINA = {
    "GGAL.BA":  "Financials",
    "YPFD.BA":  "Energy",           # YPF cotiza como YPFD.BA en Yahoo
    "BMA.BA":   "Financials",
    "PAMP.BA":  "Utilities",
    "TXAR.BA":  "Materials",
    "ALUA.BA":  "Materials",
    "SUPV.BA":  "Financials",
    "CEPU.BA":  "Utilities",
    "TECO2.BA": "Communication Services",
    "CRES.BA":  "Real Estate",
    "LOMA.BA":  "Materials",
    "BYMA.BA":  "Financials",
    "EDN.BA":   "Utilities",
    "TGSU2.BA": "Energy",
    "VALO.BA":  "Financials",
    "MIRG.BA":  "Financials",
    "IRSA.BA":  "Real Estate",
    "HARG.BA":  "Utilities",
    "METR.BA":   "Utilities",
    "COME.BA":   "Consumer Discretionary",
    # CEDEARs
    "AAPL.BA":   "Technology",
    "MSFT.BA":   "Technology",
    "GOOGL.BA":  "Technology",
    "AMZN.BA":   "Consumer Discretionary",
    "TSLA.BA":   "Consumer Discretionary",
    "NVDA.BA":   "Technology",
    "META.BA":   "Communication Services",
    "BABA.BA":   "Consumer Discretionary",
    "GOLD.BA":   "Materials",
    "KO.BA":     "Consumer Staples",
}

NOMBRES_ARGENTINA = {
    "GGAL.BA":  "Grupo Financiero Galicia",
    "YPFD.BA":  "YPF S.A.",
    "BMA.BA":   "Banco Macro",
    "PAMP.BA":  "Pampa Energía",
    "TXAR.BA":  "Ternium Argentina",
    "ALUA.BA":  "Aluar Aluminio",
    "SUPV.BA":  "Supervielle",
    "CEPU.BA":  "Central Puerto",
    "TECO2.BA": "Telecom Argentina",
    "CRES.BA":  "Cresud",
    "LOMA.BA":  "Loma Negra",
    "BYMA.BA":  "Bolsas y Mercados Arg.",
    "EDN.BA":   "Edenor",
    "TGSU2.BA": "Transportadora Gas Sur",
    "VALO.BA":  "Grupo Supervielle",
    "MIRG.BA":  "Mirgor",
    "IRSA.BA":  "IRSA Inversiones",
    "HARG.BA":  "Holcim Argentina",
    "METR.BA":   "Metrogas",
    "COME.BA":   "Soc. Comercial del Plata",
    # CEDEARs
    "AAPL.BA":   "CEDEAR Apple",
    "MSFT.BA":   "CEDEAR Microsoft",
    "GOOGL.BA":  "CEDEAR Alphabet",
    "AMZN.BA":   "CEDEAR Amazon",
    "TSLA.BA":   "CEDEAR Tesla",
    "NVDA.BA":   "CEDEAR NVIDIA",
    "META.BA":   "CEDEAR Meta",
    "BABA.BA":   "CEDEAR Alibaba",
    "GOLD.BA":   "CEDEAR Barrick Gold",
    "KO.BA":     "CEDEAR Coca-Cola",
}

# Alias: si el usuario escribe un ticker incorrecto, lo redirigimos
# Ej: el usuario escribe YPF.BA pero Yahoo lo tiene como YPFD.BA
ALIAS_ARGENTINA = {
    # Acciones MERVAL con nombres alternativos
    "YPF.BA":     "YPFD.BA",
    "GALICIA.BA": "GGAL.BA",
    "MACRO.BA":   "BMA.BA",
    "PAMPA.BA":   "PAMP.BA",
    "TELECOM.BA": "TECO2.BA",
    # CEDEARs: se identifican igual que el ticker global + .BA
    # Yahoo Finance los reconoce directamente con ese formato
}


def es_ticker_argentino(ticker: str) -> bool:
    """Retorna True si el ticker es de la bolsa argentina (termina en .BA)."""
    return str(ticker).upper().endswith(".BA")


def normalizar_dataframe(datos: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Normaliza el DataFrame de precios para que siempre tenga
    columnas simples: Open, High, Low, Close, Volume.

    yfinance a veces devuelve MultiIndex cuando se piden varios
    tickers a la vez. También limpia filas con NaN en Close.
    """
    # Aplanar MultiIndex si existe
    if isinstance(datos.columns, pd.MultiIndex):
        # El MultiIndex es (campo, ticker) → nos quedamos con el campo
        datos.columns = datos.columns.get_level_values(0)

    # Eliminar columnas duplicadas (puede pasar con algunos tickers)
    datos = datos.loc[:, ~datos.columns.duplicated()]

    # Asegurarnos de que existen las columnas básicas
    columnas_necesarias = ["Open", "High", "Low", "Close", "Volume"]
    for col in columnas_necesarias:
        if col not in datos.columns:
            # Buscar variante en minúsculas
            col_lower = [c for c in datos.columns if c.lower() == col.lower()]
            if col_lower:
                datos.rename(columns={col_lower[0]: col}, inplace=True)

    # Convertir todo a numérico
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in datos.columns:
            datos[col] = pd.to_numeric(datos[col], errors="coerce")

    # Eliminar filas donde Close es NaN o 0
    if "Close" in datos.columns:
        datos = datos[datos["Close"].notna() & (datos["Close"] > 0)]

    datos.index.name = "Date"
    return datos


def _descargar(ticker: str, periodo: str, intervalo: str) -> pd.DataFrame:
    """Intenta descargar datos de yfinance, retorna DataFrame vacío si falla."""
    try:
        df = yf.download(
            ticker,
            period=periodo,
            interval=intervalo,
            progress=False,
            auto_adjust=True,
        )
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def obtener_precios(ticker: str, periodo: str = "6mo", intervalo: str = "1d") -> pd.DataFrame:
    """
    Descarga el historial de precios de una acción.
    Compatible con acciones argentinas (.BA) y globales.

    Manejo especial para .BA:
    - Resuelve aliases (ej: YPF.BA → YPFD.BA)
    - Si falla, prueba variantes del ticker automáticamente
    - Si hay pocos datos, amplía el período a 1 año
    """
    ticker = ticker.upper().strip()

    # Resolver alias conocidos (ej: YPF.BA → YPFD.BA)
    if ticker in ALIAS_ARGENTINA:
        ticker_original = ticker
        ticker = ALIAS_ARGENTINA[ticker]
        print(f"ℹ️  Redirigiendo {ticker_original} → {ticker}")

    print(f"📥 Descargando precios de {ticker}...")

    datos = _descargar(ticker, periodo, intervalo)

    # Si falló y es argentino, probar variantes automáticamente
    if datos.empty and es_ticker_argentino(ticker):
        base = ticker.replace(".BA", "")
        variantes = [
            f"{base}D.BA",   # Ej: YPF → YPFD.BA
            f"{base}3.BA",   # Ej: COME3.BA
            f"{base}2.BA",
            f"{base}4.BA",
            base,            # Sin sufijo (ADR en NYSE)
        ]
        for variante in variantes:
            if variante == ticker:
                continue
            print(f"  🔄 Probando variante: {variante}")
            datos = _descargar(variante, periodo, intervalo)
            if not datos.empty:
                print(f"  ✅ Encontrado como {variante}")
                ticker = variante
                break

    if datos.empty:
        if es_ticker_argentino(ticker):
            raise ValueError(
                f"No se encontraron datos para '{ticker}'. "
                f"Probá con el ticker exacto de Yahoo Finance. "
                f"Tickers argentinos verificados: GGAL.BA, YPFD.BA, BMA.BA, PAMP.BA, ALUA.BA, CEPU.BA"
            )
        else:
            raise ValueError(
                f"No se encontraron datos para '{ticker}'. "
                f"Verificá que el ticker esté bien escrito (ej: AAPL, MSFT, GOOGL)."
            )

    datos = normalizar_dataframe(datos, ticker)

    # Para acciones argentinas con pocos datos, ampliar el período
    if es_ticker_argentino(ticker) and len(datos) < 30 and periodo != "1y":
        print(f"  ℹ️  Pocos datos ({len(datos)} velas), ampliando a 1 año...")
        try:
            datos2 = yf.download(ticker, period="1y", interval=intervalo,
                                  progress=False, auto_adjust=True)
            if not datos2.empty and len(datos2) > len(datos):
                datos = normalizar_dataframe(datos2, ticker)
        except Exception:
            pass  # Si falla, usamos lo que tenemos

    if len(datos) < 10:
        raise ValueError(
            f"Datos insuficientes para '{ticker}' ({len(datos)} velas). "
            f"El activo puede tener poca liquidez o estar inactivo."
        )

    print(f"✅ {len(datos)} velas descargadas para {ticker}")
    return datos


def obtener_info_empresa(ticker: str) -> dict:
    """
    Obtiene información general de la empresa.
    Para acciones argentinas usa el mapa manual como fallback
    cuando Yahoo Finance no devuelve los campos correctamente.
    """
    ticker = ticker.upper().strip()
    print(f"🏢 Obteniendo información de {ticker}...")

    es_arg = es_ticker_argentino(ticker)

    try:
        accion = yf.Ticker(ticker)
        info = accion.info or {}
    except Exception:
        info = {}

    # --- Nombre ---
    nombre = (
        info.get("longName")
        or info.get("shortName")
        or NOMBRES_ARGENTINA.get(ticker)
        or ticker
    )

    # --- Sector ---
    # Para .BA Yahoo Finance suele devolver sector vacío → usamos mapa manual
    sector = (
        info.get("sector")
        or SECTORES_ARGENTINA.get(ticker)
        or "Desconocido"
    )

    # --- Precio actual ---
    # Para .BA, currentPrice suele venir None → lo sacamos del historial
    precio = info.get("currentPrice") or info.get("regularMarketPrice")
    if not precio or precio == 0:
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if not hist.empty:
                precio = float(hist["Close"].iloc[-1])
        except Exception:
            precio = 0

    # --- Máximo/mínimo anual ---
    max_anual = info.get("fiftyTwoWeekHigh") or 0
    min_anual = info.get("fiftyTwoWeekLow") or 0

    # --- Capitalización ---
    cap = info.get("marketCap") or 0

    # --- Moneda ---
    moneda = info.get("currency") or ("ARS" if es_arg else "USD")

    # --- Descripción ---
    descripcion = (
        info.get("longBusinessSummary", "")
        or ("Empresa argentina que cotiza en el MERVAL (BYMA)." if es_arg else "Sin descripción disponible.")
    )

    return {
        "nombre": nombre,
        "sector": sector,
        "industria": info.get("industry", "N/A"),
        "precio_actual": round(float(precio), 2) if precio else 0,
        "maximo_anual": round(float(max_anual), 2) if max_anual else 0,
        "minimo_anual": round(float(min_anual), 2) if min_anual else 0,
        "capitalizacion": int(cap) if cap else 0,
        "moneda": moneda,
        "descripcion": str(descripcion)[:300],
        "es_argentina": es_arg,
    }


def obtener_noticias(ticker: str, empresa: str = "", max_noticias: int = 10) -> list:
    """
    Obtiene noticias recientes sobre la empresa desde Google News RSS.
    Para acciones argentinas busca también en español.
    """
    print(f"📰 Buscando noticias sobre {ticker}...")

    # Para argentinas buscamos por nombre (sin .BA que confunde)
    ticker_limpio = ticker.replace(".BA", "")
    termino = f"{ticker_limpio} {empresa} accion bolsa".replace(" ", "+") if ticker.endswith(".BA") \
              else f"{ticker} {empresa} stock".replace(" ", "+")

    # Para argentinas usamos Google News en español
    if ticker.endswith(".BA"):
        url_rss = f"https://news.google.com/rss/search?q={termino}&hl=es-419&gl=AR&ceid=AR:es-419"
    else:
        url_rss = f"https://news.google.com/rss/search?q={termino}&hl=en-US&gl=US&ceid=US:en"

    try:
        feed = feedparser.parse(url_rss)
        noticias = []
        for entrada in feed.entries[:max_noticias]:
            noticias.append({
                "titulo":  entrada.get("title", "Sin título") or "Sin título",
                "resumen": entrada.get("summary", "") or entrada.get("title", "") or "",
                "link":    entrada.get("link", ""),
                "fecha":   entrada.get("published", ""),
            })
        print(f"✅ {len(noticias)} noticias encontradas")
        return noticias
    except Exception as e:
        print(f"⚠️ No se pudieron obtener noticias: {e}")
        return []
