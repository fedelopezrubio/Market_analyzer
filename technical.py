# ============================================================
# technical.py
# ------------------------------------------------------------
# Este módulo calcula todos los indicadores técnicos sobre
# las velas japonesas. Los indicadores técnicos son fórmulas
# matemáticas que ayudan a interpretar el comportamiento del
# precio de una acción.
#
# Indicadores incluidos:
#   - SMA (Simple Moving Average) / Media Móvil Simple
#   - EMA (Exponential Moving Average) / Media Móvil Exponencial
#   - RSI (Relative Strength Index) / Índice de Fuerza Relativa
#   - MACD (Moving Average Convergence/Divergence)
#   - Bandas de Bollinger
#   - Volumen promedio
# ============================================================

import pandas as pd
import numpy as np


def calcular_sma(serie: pd.Series, ventana: int) -> pd.Series:
    """
    SMA - Media Móvil Simple.

    Promedia los últimos N precios de cierre.
    Si la SMA corta sube y el precio la cruza hacia arriba → señal alcista.

    Parámetro 'ventana': cantidad de días a promediar. Ej: 20, 50, 200.
    """
    return serie.rolling(window=ventana).mean()


def calcular_ema(serie: pd.Series, ventana: int) -> pd.Series:
    """
    EMA - Media Móvil Exponencial.

    Similar a la SMA pero da más peso a los precios recientes.
    Reacciona más rápido a cambios de tendencia que la SMA.
    """
    return serie.ewm(span=ventana, adjust=False).mean()


def calcular_rsi(serie: pd.Series, ventana: int = 14) -> pd.Series:
    """
    RSI - Índice de Fuerza Relativa (0 a 100).

    Mide la velocidad y magnitud de los movimientos de precio.

    Interpretación:
    - RSI > 70 → Sobrecomprado (posible señal de VENTA)
    - RSI < 30 → Sobrevendido (posible señal de COMPRA)
    - RSI entre 30-70 → Zona neutral
    """

    # Calculamos la diferencia de precio entre días consecutivos
    delta = serie.diff()

    # Separamos los días que subió y los que bajó
    ganancias = delta.clip(lower=0)    # Solo subidas (negativos → 0)
    perdidas = (-delta).clip(lower=0)  # Solo bajadas (positivos → 0)

    # Promedio de ganancias y pérdidas en la ventana de días
    avg_ganancia = ganancias.rolling(window=ventana).mean()
    avg_perdida = perdidas.rolling(window=ventana).mean()

    # Fórmula del RSI
    rs = avg_ganancia / avg_perdida.replace(0, np.nan)  # Evitamos división por cero
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calcular_macd(serie: pd.Series, rapida: int = 12, lenta: int = 26, señal: int = 9) -> tuple:
    """
    MACD - Convergencia/Divergencia de Medias Móviles.

    Mide la diferencia entre dos EMAs para detectar cambios de tendencia.

    Retorna tres series:
    - macd_line: La línea principal del MACD
    - señal_line: La línea de señal (EMA del MACD)
    - histograma: Diferencia entre MACD y señal (mide la fuerza del movimiento)

    Interpretación:
    - Cuando MACD cruza señal hacia ARRIBA → señal de COMPRA
    - Cuando MACD cruza señal hacia ABAJO → señal de VENTA
    """

    ema_rapida = calcular_ema(serie, rapida)
    ema_lenta = calcular_ema(serie, lenta)

    macd_line = ema_rapida - ema_lenta
    señal_line = calcular_ema(macd_line, señal)
    histograma = macd_line - señal_line

    return macd_line, señal_line, histograma


def calcular_bollinger(serie: pd.Series, ventana: int = 20, desviaciones: float = 2.0) -> tuple:
    """
    Bandas de Bollinger.

    Crean un "canal" alrededor del precio usando la desviación estándar.

    Retorna:
    - banda_superior: Precio "caro" (posible resistencia)
    - banda_media: SMA de la ventana (la media)
    - banda_inferior: Precio "barato" (posible soporte)

    Interpretación:
    - Precio toca banda SUPERIOR → posible VENTA (sobrecomprado)
    - Precio toca banda INFERIOR → posible COMPRA (sobrevendido)
    - Bandas muy estrechas → baja volatilidad, posible movimiento grande próximo
    """

    banda_media = calcular_sma(serie, ventana)
    desviacion = serie.rolling(window=ventana).std()

    banda_superior = banda_media + (desviaciones * desviacion)
    banda_inferior = banda_media - (desviaciones * desviacion)

    return banda_superior, banda_media, banda_inferior


def agregar_todos_los_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Función principal: toma el DataFrame de precios y agrega
    todos los indicadores técnicos como columnas nuevas.

    Entrada: DataFrame con columnas Open, High, Low, Close, Volume
    Salida: El mismo DataFrame con columnas adicionales de indicadores
    """

    # Trabajamos sobre una copia para no modificar el original
    df = df.copy()

    # Aseguramos que Close sea una Serie 1D (a veces yfinance retorna DataFrame)
    close = df["Close"].squeeze()
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = pd.to_numeric(close, errors="coerce")

    volume = df["Volume"].squeeze()
    if isinstance(volume, pd.DataFrame):
        volume = volume.iloc[:, 0]
    volume = pd.to_numeric(volume, errors="coerce").fillna(0)

    n = len(df)  # Cantidad de filas disponibles

    # --- Medias Móviles ---
    # Para acciones con pocos datos ajustamos la ventana mínima
    df["SMA_20"]  = calcular_sma(close, min(20, n))
    df["SMA_50"]  = calcular_sma(close, min(50, n))
    df["SMA_200"] = calcular_sma(close, min(200, n))
    df["EMA_12"]  = calcular_ema(close, 12)    # EMA rápida (para MACD)
    df["EMA_26"]  = calcular_ema(close, 26)    # EMA lenta (para MACD)

    # --- RSI ---
    df["RSI"] = calcular_rsi(close, ventana=14)

    # --- MACD ---
    df["MACD"], df["MACD_Señal"], df["MACD_Hist"] = calcular_macd(close)

    # --- Bollinger ---
    df["BB_Superior"], df["BB_Media"], df["BB_Inferior"] = calcular_bollinger(close)

    # --- Volumen promedio (para contexto) ---
    df["Volumen_SMA_20"] = calcular_sma(volume, 20)

    # --- Posición del precio dentro de Bollinger (0 a 1) ---
    # 0 = en la banda inferior, 1 = en la banda superior
    rango_bb = df["BB_Superior"] - df["BB_Inferior"]
    df["BB_Posicion"] = (close - df["BB_Inferior"]) / rango_bb.replace(0, np.nan)

    return df


def generar_señales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera señales de compra/venta basadas en los indicadores técnicos.

    Cada indicador vota: +1 (alcista/compra), -1 (bajista/venta), 0 (neutral).
    Al final sumamos los votos para obtener un consenso.
    """

    df = df.copy()

    # Tomamos la última fila (el día más reciente)
    ultima = df.iloc[-1]
    _close_series = df["Close"].squeeze()
    if isinstance(_close_series, pd.DataFrame):
        _close_series = _close_series.iloc[:, 0]
    close_actual = float(pd.to_numeric(_close_series, errors="coerce").dropna().iloc[-1])

    señales = {}

    # --- Señal RSI ---
    rsi = float(ultima["RSI"]) if not pd.isna(ultima["RSI"]) else 50
    if rsi < 30:
        señales["RSI"] = {"valor": round(rsi, 2), "señal": 1, "descripcion": f"RSI={rsi:.1f} → Sobrevendido (COMPRA)"}
    elif rsi > 70:
        señales["RSI"] = {"valor": round(rsi, 2), "señal": -1, "descripcion": f"RSI={rsi:.1f} → Sobrecomprado (VENTA)"}
    else:
        señales["RSI"] = {"valor": round(rsi, 2), "señal": 0, "descripcion": f"RSI={rsi:.1f} → Zona neutral"}

    # --- Señal MACD ---
    macd_val = float(ultima["MACD"]) if not pd.isna(ultima["MACD"]) else 0
    señal_val = float(ultima["MACD_Señal"]) if not pd.isna(ultima["MACD_Señal"]) else 0
    if macd_val > señal_val:
        señales["MACD"] = {"valor": round(macd_val, 4), "señal": 1, "descripcion": "MACD > Señal → Tendencia alcista (COMPRA)"}
    else:
        señales["MACD"] = {"valor": round(macd_val, 4), "señal": -1, "descripcion": "MACD < Señal → Tendencia bajista (VENTA)"}

    # --- Señal Bollinger ---
    bb_pos = float(ultima["BB_Posicion"]) if not pd.isna(ultima["BB_Posicion"]) else 0.5
    if bb_pos < 0.2:
        señales["Bollinger"] = {"valor": round(bb_pos, 3), "señal": 1, "descripcion": "Precio cerca de banda inferior (COMPRA)"}
    elif bb_pos > 0.8:
        señales["Bollinger"] = {"valor": round(bb_pos, 3), "señal": -1, "descripcion": "Precio cerca de banda superior (VENTA)"}
    else:
        señales["Bollinger"] = {"valor": round(bb_pos, 3), "señal": 0, "descripcion": "Precio dentro de las bandas (NEUTRAL)"}

    # --- Señal SMA (precio vs media de 50 días) ---
    # Para acciones con pocos datos, SMA50 puede ser NaN → usamos la SMA disponible
    _sma50_col = df["SMA_50"].dropna()
    sma50 = float(_sma50_col.iloc[-1]) if not _sma50_col.empty else close_actual
    if close_actual > sma50:
        señales["SMA_50"] = {"valor": round(sma50, 2), "señal": 1, "descripcion": f"Precio > SMA50 (${sma50:.2f}) → Tendencia alcista"}
    else:
        señales["SMA_50"] = {"valor": round(sma50, 2), "señal": -1, "descripcion": f"Precio < SMA50 (${sma50:.2f}) → Tendencia bajista"}

    # --- Cruce Dorado / Cruce de la Muerte (SMA20 vs SMA50) ---
    _sma20_col = df["SMA_20"].dropna()
    sma20 = float(_sma20_col.iloc[-1]) if not _sma20_col.empty else close_actual
    if sma20 > sma50:
        señales["Cruce_MA"] = {"valor": round(sma20 - sma50, 2), "señal": 1, "descripcion": "SMA20 > SMA50 → Cruce Dorado (COMPRA)"}
    else:
        señales["Cruce_MA"] = {"valor": round(sma20 - sma50, 2), "señal": -1, "descripcion": "SMA20 < SMA50 → Cruce de la Muerte (VENTA)"}

    return señales
