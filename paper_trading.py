# ============================================================
# paper_trading.py
# ------------------------------------------------------------
# Registra alertas y decisiones de inversión simuladas.
#
# "Paper trading" = trading con dinero imaginario.
# La idea es registrar cada señal del programa y cada
# decisión que VOS tomás, para después ver:
#   - ¿Cuánto habrías ganado/perdido si hubieras comprado?
#   - ¿El modelo acertó o no?
#   - ¿Cuál es tu tasa de acierto vs la del modelo?
#
# Todos los datos se guardan en historial_alertas.json
# para que persistan entre sesiones.
# ============================================================

import json
import os
from datetime import datetime


ARCHIVO_HISTORIAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial_alertas.json")
CAPITAL_INICIAL   = 10_000.0   # Capital simulado en USD para calcular rendimientos


def cargar_historial() -> dict:
    """
    Carga el historial desde el archivo JSON.
    Si no existe lo crea con los valores iniciales.
    Si existe pero le faltan claves (versión vieja), las agrega sin tocar el resto.
    NUNCA resetea el capital ni las posiciones si el archivo ya existe.
    """
    base = {
        "alertas":         [],
        "decisiones":      [],
        "capital":         CAPITAL_INICIAL,
        "posiciones":      {},
        "total_alertas":   0,
        "alertas_enviadas": 0,
    }

    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                guardado = json.load(f)
            # Agregar claves que puedan faltar en versiones viejas del archivo
            # pero NUNCA pisar lo que ya está guardado
            for clave, valor_default in base.items():
                if clave not in guardado:
                    guardado[clave] = valor_default
            return guardado
        except Exception as e:
            print(f"⚠️ Error leyendo historial, se crea uno nuevo: {e}")

    # Primera vez: crear archivo con valores iniciales
    guardar_historial(base)
    return base


def guardar_historial(historial: dict) -> None:
    """Guarda el historial actualizado en el archivo JSON."""
    try:
        with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ No se pudo guardar historial: {e}")


def registrar_alerta(alerta: dict, email_enviado: bool = False) -> dict:
    """
    Registra una nueva alerta en el historial.
    Se llama cada vez que el scheduler detecta una señal fuerte.

    Retorna el historial actualizado.
    """
    historial = cargar_historial()

    entrada = {
        **alerta,
        "id":             len(historial["alertas"]) + 1,
        "timestamp":      datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "email_enviado":  email_enviado,
        "decision_usuario": None,   # Se completa cuando el usuario decide
        "precio_cierre":  None,     # Se completa al cerrar la posición
        "resultado_usd":  None,
        "resultado_pct":  None,
    }

    historial["alertas"].append(entrada)
    historial["total_alertas"] += 1
    if email_enviado:
        historial["alertas_enviadas"] += 1

    guardar_historial(historial)
    print(f"📝 Alerta registrada: #{entrada['id']} {alerta.get('veredicto')} {alerta.get('ticker')}")
    return historial


def simular_compra(alerta_id: int, monto_usd: float = 1000.0) -> dict:
    """
    Registra una decisión de compra simulada sobre una alerta.

    Parámetros:
    -----------
    alerta_id : ID de la alerta en el historial
    monto_usd : Cuánto dinero simulado invertir (default $1000)

    Retorna: resultado de la operación
    """
    historial = cargar_historial()

    # Buscamos la alerta
    alerta = next((a for a in historial["alertas"] if a["id"] == alerta_id), None)
    if not alerta:
        return {"ok": False, "msg": f"No se encontró la alerta #{alerta_id}"}

    ticker        = alerta["ticker"]
    precio_actual = alerta.get("precio_actual", 0)

    if precio_actual <= 0:
        return {"ok": False, "msg": "Precio inválido, no se puede simular la compra"}

    if historial["capital"] < monto_usd:
        return {"ok": False, "msg": f"Capital insuficiente (disponible: ${historial['capital']:,.2f})"}

    # Calculamos cuántas unidades compramos
    cantidad = monto_usd / precio_actual

    # Actualizamos capital y posiciones
    historial["capital"] -= monto_usd

    if ticker in historial["posiciones"]:
        # Promediamos con posición existente
        pos = historial["posiciones"][ticker]
        total_cant  = pos["cantidad"] + cantidad
        total_invest = pos["precio_entrada"] * pos["cantidad"] + monto_usd
        historial["posiciones"][ticker] = {
            "cantidad":       total_cant,
            "precio_entrada": total_invest / total_cant,
            "monto_invertido": total_invest,
            "fecha_entrada":  datetime.now().strftime("%d/%m/%Y %H:%M"),
            "moneda":         alerta.get("moneda", "USD"),
        }
    else:
        historial["posiciones"][ticker] = {
            "cantidad":       cantidad,
            "precio_entrada": precio_actual,
            "monto_invertido": monto_usd,
            "fecha_entrada":  datetime.now().strftime("%d/%m/%Y %H:%M"),
            "moneda":         alerta.get("moneda", "USD"),
        }

    # Marcamos la decisión en la alerta
    alerta["decision_usuario"] = "COMPRA"
    alerta["monto_simulado"]   = monto_usd

    # Registramos en decisiones
    historial["decisiones"].append({
        "tipo":           "COMPRA",
        "alerta_id":      alerta_id,
        "ticker":         ticker,
        "precio":         precio_actual,
        "cantidad":       cantidad,
        "monto":          monto_usd,
        "timestamp":      datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    })

    guardar_historial(historial)
    return {
        "ok":       True,
        "msg":      f"✅ Compra simulada: {cantidad:.4f} {ticker} a ${precio_actual:,.2f}",
        "capital":  historial["capital"],
        "posicion": historial["posiciones"][ticker],
    }


def simular_venta(ticker: str, precio_venta: float = None) -> dict:
    """
    Registra una venta simulada de una posición abierta.
    Si no se especifica precio_venta, usa el precio de la última alerta.
    """
    historial = cargar_historial()

    if ticker not in historial["posiciones"]:
        return {"ok": False, "msg": f"No tenés posición abierta en {ticker}"}

    pos           = historial["posiciones"][ticker]
    precio_entrada = pos["precio_entrada"]
    cantidad       = pos["cantidad"]
    monto_original = pos["monto_invertido"]

    # Precio de venta: el especificado o el de la última alerta del ticker
    if not precio_venta:
        alertas_ticker = [a for a in historial["alertas"] if a["ticker"] == ticker]
        precio_venta   = alertas_ticker[-1]["precio_actual"] if alertas_ticker else precio_entrada

    monto_final    = precio_venta * cantidad
    resultado_usd  = monto_final - monto_original
    resultado_pct  = (resultado_usd / monto_original) * 100

    # Actualizamos capital
    historial["capital"] += monto_final

    # Cerramos la posición
    del historial["posiciones"][ticker]

    # Registramos en decisiones
    historial["decisiones"].append({
        "tipo":           "VENTA",
        "ticker":         ticker,
        "precio_entrada": precio_entrada,
        "precio_venta":   precio_venta,
        "cantidad":       cantidad,
        "monto_original": monto_original,
        "monto_final":    monto_final,
        "resultado_usd":  resultado_usd,
        "resultado_pct":  resultado_pct,
        "timestamp":      datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    })

    guardar_historial(historial)

    emoji = "✅" if resultado_usd >= 0 else "❌"
    return {
        "ok":          True,
        "msg":         f"{emoji} Venta simulada {ticker}: {resultado_pct:+.2f}% (${resultado_usd:+,.2f})",
        "resultado_usd": resultado_usd,
        "resultado_pct": resultado_pct,
        "capital":     historial["capital"],
    }


def calcular_resumen() -> dict:
    """
    Calcula un resumen del rendimiento del paper trading.
    Incluye métricas del modelo y del usuario.
    """
    historial = cargar_historial()
    decisiones = historial.get("decisiones", [])
    alertas    = historial.get("alertas", [])

    # Operaciones cerradas (VENTA)
    ventas = [d for d in decisiones if d["tipo"] == "VENTA"]
    ganadas  = [v for v in ventas if v.get("resultado_usd", 0) > 0]
    perdidas = [v for v in ventas if v.get("resultado_usd", 0) <= 0]

    total_resultado = sum(v.get("resultado_usd", 0) for v in ventas)
    rendimiento_total = ((historial["capital"] - CAPITAL_INICIAL) / CAPITAL_INICIAL) * 100

    # Precisión del modelo: de las alertas con veredicto COMPRAR,
    # ¿cuántas efectivamente subieron? (comparando precio de la alerta vs cierre)
    aciertos_modelo = 0
    total_evaluables = 0
    for a in alertas:
        if a.get("precio_cierre") and a.get("precio_actual"):
            total_evaluables += 1
            subio = a["precio_cierre"] > a["precio_actual"]
            if (a["veredicto"] == "COMPRAR" and subio) or (a["veredicto"] == "VENDER" and not subio):
                aciertos_modelo += 1

    precision_modelo = (aciertos_modelo / total_evaluables * 100) if total_evaluables else None

    return {
        "capital_actual":      round(historial["capital"], 2),
        "capital_inicial":     CAPITAL_INICIAL,
        "rendimiento_total":   round(rendimiento_total, 2),
        "total_resultado_usd": round(total_resultado, 2),
        "operaciones_cerradas": len(ventas),
        "operaciones_ganadas": len(ganadas),
        "operaciones_perdidas": len(perdidas),
        "tasa_acierto":        round(len(ganadas) / len(ventas) * 100, 1) if ventas else 0,
        "precision_modelo":    round(precision_modelo, 1) if precision_modelo else None,
        "total_alertas":       historial["total_alertas"],
        "posiciones_abiertas": historial["posiciones"],
        "alertas_recientes":   alertas[-10:][::-1],   # Últimas 10, más reciente primero
        "decisiones_recientes": decisiones[-10:][::-1],
    }
