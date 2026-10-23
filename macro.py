# ============================================================
# macro.py
# ------------------------------------------------------------
# Este módulo obtiene y analiza indicadores macroeconómicos
# usando fuentes 100% gratuitas:
#
#   - FRED (Federal Reserve Economic Data): inflación, tasas,
#     PBI, desempleo, spread de crédito, índice de confianza.
#   - Yahoo Finance: VIX (índice de miedo), bonos del tesoro,
#     índices bursátiles globales, precio del oro y petróleo.
#
# Cada indicador genera una SEÑAL de impacto sobre el mercado
# y en particular sobre el SECTOR de la empresa analizada.
# ============================================================

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import feedparser
from datetime import datetime, timedelta


# ============================================================
# MAPA DE IMPACTO SECTORIAL
# ------------------------------------------------------------
# Define cómo cada condición macro afecta a cada sector.
# Valores: +1 (positivo), -1 (negativo), 0 (neutral)
# ============================================================

IMPACTO_SECTORIAL = {
    # ── Tasas de interés ALTAS son malas para...
    "tasas_altas": {
        "Technology":           -1,   # Encarece financiación de crecimiento
        "Real Estate":          -1,   # Hipotecas más caras, demanda cae
        "Consumer Discretionary": -1, # Crédito al consumo más caro
        "Utilities":            -1,   # Endeudadas, costo sube
        "Financials":           +1,   # Bancos ganan más margen de interés
        "Energy":                0,
        "Health Care":           0,
        "Consumer Staples":     -1,
        "Industrials":          -1,
        "Materials":             0,
        "Communication Services": -1,
        "default":              -1,
    },
    # ── Inflación ALTA
    "inflacion_alta": {
        "Technology":           -1,   # Costos operativos suben
        "Real Estate":          +1,   # Activo real, cobertura inflacionaria
        "Consumer Discretionary": -1, # Consumidor aprieta el cinturón
        "Consumer Staples":     +1,   # Pueden trasladar precios
        "Energy":               +1,   # Commodities suben
        "Materials":            +1,   # Idem
        "Financials":           -1,   # Erosiona márgenes reales
        "Utilities":            +1,   # Reguladas con ajuste inflacionario
        "Health Care":           0,
        "Industrials":          -1,
        "Communication Services": -1,
        "default":              -1,
    },
    # ── Recesión / PBI cayendo
    "recesion": {
        "Technology":           -1,
        "Consumer Discretionary": -2,  # Los más golpeados
        "Financials":           -1,
        "Industrials":          -1,
        "Energy":               -1,
        "Materials":            -1,
        "Consumer Staples":     +1,   # Defensivo: la gente igual come
        "Health Care":          +1,   # Defensivo
        "Utilities":            +1,   # Defensivo
        "Real Estate":          -1,
        "Communication Services": -1,
        "default":              -1,
    },
    # ── VIX alto (miedo en el mercado)
    "vix_alto": {
        "default": -1,   # Malo para todo el mercado en general
        "Consumer Staples": 0,
        "Health Care":      0,
        "Utilities":        0,
    },
    # ── Desempleo alto
    "desempleo_alto": {
        "Consumer Discretionary": -1,
        "Consumer Staples":       -1,
        "Real Estate":            -1,
        "Financials":             -1,
        "Technology":             -1,
        "Health Care":             0,
        "Utilities":               0,
        "default":                -1,
    },
}

# Sectores reconocidos por Yahoo Finance (para mapear el sector de la empresa)
SECTORES_CONOCIDOS = list(set(
    k for d in IMPACTO_SECTORIAL.values() for k in d.keys() if k != "default"
))


def impacto_para_sector(condicion: str, sector: str) -> int:
    """Retorna el impacto (+1, 0, -1) de una condición macro sobre un sector."""
    mapa = IMPACTO_SECTORIAL.get(condicion, {})
    return mapa.get(sector, mapa.get("default", 0))


# ============================================================
# OBTENCIÓN DE DATOS DEL FRED (Federal Reserve)
# ============================================================

def obtener_serie_fred(serie_id: str, nombre: str) -> dict:
    """
    Descarga una serie macroeconómica del FRED usando su API pública.
    El FRED es la base de datos económicos de la Reserva Federal de EE.UU.
    No requiere API key para lecturas simples.

    Series más usadas:
    - CPIAUCSL: Inflación (CPI mensual)
    - FEDFUNDS: Tasa de fondos federales
    - GDP: PBI de EE.UU.
    - UNRATE: Tasa de desempleo
    - T10Y2Y: Spread de la curva de rendimiento (10y - 2y)
    - UMCSENT: Índice de confianza del consumidor Michigan
    """
    try:
        url = (
            f"https://fred.stlouisfed.org/graph/fredgraph.csv"
            f"?id={serie_id}"
        )
        # Descargamos el CSV directamente
        df = pd.read_csv(url, parse_dates=["DATE"], index_col="DATE")
        df = df.replace(".", np.nan).dropna()
        df[serie_id] = pd.to_numeric(df[serie_id], errors="coerce")

        if df.empty:
            return {"nombre": nombre, "valor_actual": None, "valor_anterior": None, "tendencia": "N/D", "error": True}

        valor_actual = float(df[serie_id].iloc[-1])
        valor_anterior = float(df[serie_id].iloc[-2]) if len(df) > 1 else valor_actual
        valor_hace_1y = float(df[serie_id].iloc[-13]) if len(df) > 12 else valor_anterior

        # Tendencia: subiendo, bajando o estable
        cambio = valor_actual - valor_anterior
        if abs(cambio) < 0.01:
            tendencia = "Estable"
        elif cambio > 0:
            tendencia = "Subiendo ▲"
        else:
            tendencia = "Bajando ▼"

        return {
            "nombre": nombre,
            "serie_id": serie_id,
            "valor_actual": round(valor_actual, 3),
            "valor_anterior": round(valor_anterior, 3),
            "valor_hace_1y": round(valor_hace_1y, 3),
            "cambio": round(cambio, 3),
            "tendencia": tendencia,
            "fecha": str(df.index[-1].date()),
            "error": False
        }

    except Exception as e:
        return {"nombre": nombre, "serie_id": serie_id, "valor_actual": None, "tendencia": "N/D", "error": True, "msg": str(e)}


def obtener_indicadores_fred() -> dict:
    """
    Descarga todos los indicadores macroeconómicos del FRED.
    Retorna un diccionario con cada indicador y sus valores.
    """
    print("📊 Descargando indicadores macroeconómicos del FRED...")

    indicadores = {
        "inflacion":     obtener_serie_fred("CPIAUCSL", "Inflación (CPI)"),
        "tasa_fed":      obtener_serie_fred("FEDFUNDS", "Tasa Fed Funds"),
        "desempleo":     obtener_serie_fred("UNRATE", "Desempleo (%)"),
        "curva_rdto":    obtener_serie_fred("T10Y2Y", "Curva Rendimiento (10y-2y)"),
        "confianza":     obtener_serie_fred("UMCSENT", "Confianza Consumidor (Michigan)"),
        "pbi":           obtener_serie_fred("GDPC1", "PBI Real (miles de millones USD)"),
    }

    print("✅ Indicadores FRED descargados")
    return indicadores


# ============================================================
# OBTENCIÓN DE DATOS DE MERCADO (Yahoo Finance)
# ============================================================

def obtener_indicadores_mercado() -> dict:
    """
    Obtiene indicadores de mercado en tiempo real de Yahoo Finance:
    - VIX: Índice de volatilidad (miedo del mercado)
    - Bonos del tesoro a 10 años
    - S&P 500, NASDAQ, Dow Jones
    - Oro y Petróleo (como activos refugio y macro)
    - DXY (Índice del dólar)
    """
    print("📈 Descargando indicadores de mercado...")

    tickers_mercado = {
        "VIX":     ("^VIX",   "Índice de Volatilidad (VIX)"),
        "SP500":   ("^GSPC",  "S&P 500"),
        "NASDAQ":  ("^IXIC",  "NASDAQ"),
        "BONO10Y": ("^TNX",   "Bono Tesoro 10 años (%)"),
        "ORO":     ("GC=F",   "Oro (USD/oz)"),
        "PETROLEO":("CL=F",   "Petróleo WTI (USD/barril)"),
        "DOLAR":   ("DX-Y.NYB","Índice Dólar (DXY)"),
    }

    resultados = {}
    for clave, (ticker_sym, nombre) in tickers_mercado.items():
        try:
            datos = yf.download(ticker_sym, period="5d", interval="1d", progress=False)
            if datos.empty:
                resultados[clave] = {"nombre": nombre, "valor": None, "cambio_pct": None, "error": True}
                continue

            close = datos["Close"].squeeze()
            valor_actual = float(close.iloc[-1])
            valor_anterior = float(close.iloc[-2]) if len(close) > 1 else valor_actual
            cambio_pct = ((valor_actual - valor_anterior) / valor_anterior) * 100

            resultados[clave] = {
                "nombre": nombre,
                "valor": round(valor_actual, 2),
                "cambio_pct": round(cambio_pct, 2),
                "tendencia": "Subiendo ▲" if cambio_pct > 0 else "Bajando ▼",
                "error": False
            }
        except Exception as e:
            resultados[clave] = {"nombre": nombre, "valor": None, "cambio_pct": None, "error": True}

    print("✅ Indicadores de mercado descargados")
    return resultados


# ============================================================
# ANÁLISIS MACRO INTEGRADO
# ============================================================

def analizar_macro(sector: str = "Technology") -> dict:
    """
    Función principal de análisis macroeconómico.
    Integra FRED + Yahoo Finance y calcula señales por sector.

    Parámetro:
    ----------
    sector: Sector de la empresa (ej: "Technology", "Financials")

    Retorna:
    --------
    Diccionario con indicadores, señales y puntaje macro total.
    """

    sector = sector or "Technology"
    fred = obtener_indicadores_fred()
    mercado = obtener_indicadores_mercado()

    señales = {}
    alertas = []

    # ── Análisis de inflación
    inflacion = fred.get("inflacion", {})
    if not inflacion.get("error"):
        cpi = inflacion["valor_actual"]
        cpi_anterior = inflacion.get("valor_hace_1y") or inflacion.get("valor_anterior") or cpi
        inflacion_anual = ((cpi - cpi_anterior) / cpi_anterior * 100) if (cpi_anterior and cpi_anterior != 0) else 0

        if inflacion_anual > 4.0:
            impacto = impacto_para_sector("inflacion_alta", sector)
            señales["Inflación"] = {
                "valor": f"{inflacion_anual:.1f}% interanual",
                "condicion": "Alta",
                "impacto": impacto,
                "descripcion": f"Inflación {inflacion_anual:.1f}% → {'Negativo' if impacto < 0 else 'Positivo' if impacto > 0 else 'Neutral'} para {sector}"
            }
            if inflacion_anual > 6:
                alertas.append(f"🚨 Inflación muy alta ({inflacion_anual:.1f}%) — riesgo de recesión")
        elif inflacion_anual < 1.0:
            señales["Inflación"] = {
                "valor": f"{inflacion_anual:.1f}% interanual",
                "condicion": "Muy baja (deflación)",
                "impacto": -1,
                "descripcion": "Inflación muy baja → posible deflación, señal contractiva"
            }
        else:
            señales["Inflación"] = {
                "valor": f"{inflacion_anual:.1f}% interanual",
                "condicion": "Moderada",
                "impacto": 0,
                "descripcion": f"Inflación {inflacion_anual:.1f}% → dentro del rango saludable (2-4%)"
            }

    # ── Análisis de tasa de la Fed
    tasa = fred.get("tasa_fed", {})
    if not tasa.get("error"):
        tasa_val = tasa["valor_actual"]
        if tasa_val > 4.5:
            impacto = impacto_para_sector("tasas_altas", sector)
            señales["Tasa Fed"] = {
                "valor": f"{tasa_val:.2f}%",
                "condicion": "Restrictiva",
                "impacto": impacto,
                "descripcion": f"Tasa Fed {tasa_val:.2f}% (restrictiva) → {'Negativo' if impacto < 0 else 'Positivo'} para {sector}"
            }
            alertas.append(f"⚠️ Tasa Fed en {tasa_val:.2f}% — entorno de crédito caro")
        elif tasa_val < 1.0:
            señales["Tasa Fed"] = {
                "valor": f"{tasa_val:.2f}%",
                "condicion": "Expansiva",
                "impacto": +1,
                "descripcion": f"Tasa Fed baja ({tasa_val:.2f}%) → estímulo monetario, positivo para activos de riesgo"
            }
        else:
            señales["Tasa Fed"] = {
                "valor": f"{tasa_val:.2f}%",
                "condicion": "Neutral",
                "impacto": 0,
                "descripcion": f"Tasa Fed {tasa_val:.2f}% → rango neutral"
            }

    # ── Análisis de curva de rendimiento (inversión = señal recesiva)
    curva = fred.get("curva_rdto", {})
    if not curva.get("error") and curva.get("valor_actual") is not None:
        spread = curva["valor_actual"]
        if spread < 0:
            impacto = impacto_para_sector("recesion", sector)
            señales["Curva de Rendimiento"] = {
                "valor": f"{spread:.2f}%",
                "condicion": "Invertida ⚠️",
                "impacto": impacto,
                "descripcion": f"Curva invertida ({spread:.2f}%) → señal histórica de recesión próxima"
            }
            alertas.append("🚨 Curva de rendimiento invertida — recesión posible en 12-18 meses")
        else:
            señales["Curva de Rendimiento"] = {
                "valor": f"{spread:.2f}%",
                "condicion": "Normal",
                "impacto": +1,
                "descripcion": f"Curva normal ({spread:.2f}%) → expansión económica"
            }

    # ── Análisis de desempleo
    desempleo = fred.get("desempleo", {})
    if not desempleo.get("error"):
        des_val = desempleo["valor_actual"]
        if des_val > 6.0:
            impacto = impacto_para_sector("desempleo_alto", sector)
            señales["Desempleo"] = {
                "valor": f"{des_val:.1f}%",
                "condicion": "Alto",
                "impacto": impacto,
                "descripcion": f"Desempleo alto ({des_val:.1f}%) → debilidad en consumo"
            }
        elif des_val < 4.0:
            señales["Desempleo"] = {
                "valor": f"{des_val:.1f}%",
                "condicion": "Bajo (pleno empleo)",
                "impacto": +1,
                "descripcion": f"Desempleo bajo ({des_val:.1f}%) → mercado laboral fuerte, positivo para consumo"
            }
        else:
            señales["Desempleo"] = {
                "valor": f"{des_val:.1f}%",
                "condicion": "Moderado",
                "impacto": 0,
                "descripcion": f"Desempleo moderado ({des_val:.1f}%) → mercado laboral estable"
            }

    # ── Análisis del VIX
    vix_data = mercado.get("VIX", {})
    if not vix_data.get("error") and vix_data.get("valor"):
        vix_val = vix_data["valor"]
        if vix_val > 30:
            impacto = impacto_para_sector("vix_alto", sector)
            señales["VIX (Miedo)"] = {
                "valor": f"{vix_val:.1f}",
                "condicion": "Muy alto — pánico",
                "impacto": impacto,
                "descripcion": f"VIX {vix_val:.1f} → alta volatilidad y miedo en el mercado"
            }
            alertas.append(f"🚨 VIX en {vix_val:.1f} — mercado en modo pánico")
        elif vix_val > 20:
            señales["VIX (Miedo)"] = {
                "valor": f"{vix_val:.1f}",
                "condicion": "Elevado — cautela",
                "impacto": -1,
                "descripcion": f"VIX {vix_val:.1f} → incertidumbre moderada"
            }
        else:
            señales["VIX (Miedo)"] = {
                "valor": f"{vix_val:.1f}",
                "condicion": "Bajo — calma",
                "impacto": +1,
                "descripcion": f"VIX {vix_val:.1f} → mercado tranquilo, baja volatilidad"
            }

    # ── Análisis del Oro (activo refugio)
    oro = mercado.get("ORO", {})
    if not oro.get("error") and oro.get("cambio_pct") is not None:
        cambio_oro = oro["cambio_pct"]
        if cambio_oro > 1.0:
            señales["Oro"] = {
                "valor": f"${oro['valor']:.0f} ({cambio_oro:+.1f}%)",
                "condicion": "Subiendo fuerte",
                "impacto": -1,
                "descripcion": "Oro subiendo → inversores buscan refugio (señal de riesgo)"
            }
        elif cambio_oro < -1.0:
            señales["Oro"] = {
                "valor": f"${oro['valor']:.0f} ({cambio_oro:+.1f}%)",
                "condicion": "Bajando",
                "impacto": +1,
                "descripcion": "Oro bajando → menor demanda de refugio (señal de calma)"
            }

    # ── Análisis del Petróleo
    petroleo = mercado.get("PETROLEO", {})
    if not petroleo.get("error") and petroleo.get("cambio_pct") is not None:
        cambio_pet = petroleo["cambio_pct"]
        if sector == "Energy":
            impacto_pet = +1 if cambio_pet > 0 else -1
        elif sector in ["Consumer Discretionary", "Industrials", "Transportation"]:
            impacto_pet = -1 if cambio_pet > 2 else 0
        else:
            impacto_pet = -1 if cambio_pet > 3 else 0

        if abs(cambio_pet) > 2:
            señales["Petróleo"] = {
                "valor": f"${petroleo['valor']:.1f} ({cambio_pet:+.1f}%)",
                "condicion": "Movimiento significativo",
                "impacto": impacto_pet,
                "descripcion": f"Petróleo {cambio_pet:+.1f}% → {'Positivo' if impacto_pet > 0 else 'Negativo'} para {sector}"
            }

    # ── Cálculo del puntaje macro total
    votos = [s["impacto"] for s in señales.values()]
    puntaje_macro = sum(votos) / len(votos) if votos else 0

    if puntaje_macro > 0.2:
        sentimiento_macro = "Favorable"
        señal_macro = 1
    elif puntaje_macro < -0.2:
        sentimiento_macro = "Desfavorable"
        señal_macro = -1
    else:
        sentimiento_macro = "Mixto"
        señal_macro = 0

    return {
        "señales": señales,
        "alertas": alertas,
        "puntaje": round(puntaje_macro, 3),
        "sentimiento_macro": sentimiento_macro,
        "señal": señal_macro,
        "fred": fred,
        "mercado": mercado,
        "sector": sector,
    }
