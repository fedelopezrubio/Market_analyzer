# ============================================================
# alerts.py
# ------------------------------------------------------------
# Motor de alertas con estado persistido en scheduler_estado.json
# para que el dashboard siempre lea el estado real del scheduler,
# incluso cuando corre en un hilo separado.
# ============================================================

import threading
import time
import json
import os
from datetime import datetime, timedelta

from data_fetcher import obtener_precios, obtener_info_empresa, obtener_noticias
from technical import agregar_todos_los_indicadores, generar_señales
from predictor import entrenar_y_predecir, calcular_veredicto_final
from sentiment import analizar_noticias
from email_sender import enviar_alerta, configuracion_valida
from paper_trading import registrar_alerta
from watchlist import ACCIONES_ARGENTINAS, ACCIONES_GLOBALES

INTERVALO_HORAS     = 0.5    # 30 minutos
UMBRAL_ALERTA       = 0.45
COOLDOWN_POR_TICKER = 4

ARCHIVO_ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduler_estado.json")

# Hilo activo (solo en memoria, no se persiste)
_hilo_activo = None


# ── Funciones de estado persistido ──────────────────────────

def _leer_estado() -> dict:
    if os.path.exists(ARCHIVO_ESTADO):
        try:
            with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "activo": False,
        "ultima_revision": None,
        "proxima_revision": None,
        "alertas_sesion": 0,
        "log": [],
        "ultima_alerta_por_ticker": {},
    }


def _guardar_estado(estado: dict) -> None:
    try:
        with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ No se pudo guardar estado scheduler: {e}")


def _log(mensaje: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    linea = f"[{ts}] {mensaje}"
    print(linea)
    estado = _leer_estado()
    estado["log"].append(linea)
    if len(estado["log"]) > 50:
        estado["log"] = estado["log"][-50:]
    _guardar_estado(estado)


def _en_cooldown(ticker: str) -> bool:
    estado = _leer_estado()
    ultima_str = estado["ultima_alerta_por_ticker"].get(ticker)
    if not ultima_str:
        return False
    try:
        ultima = datetime.strptime(ultima_str, "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - ultima) < timedelta(hours=COOLDOWN_POR_TICKER)
    except Exception:
        return False


def _marcar_cooldown(ticker: str) -> None:
    estado = _leer_estado()
    estado["ultima_alerta_por_ticker"][ticker] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _guardar_estado(estado)


# ── Análisis de un ticker ────────────────────────────────────

def analizar_ticker_para_alerta(ticker: str, nombre: str, sector: str):
    try:
        df_raw = obtener_precios(ticker, periodo="6mo")
        if df_raw is None or len(df_raw) < 20:
            return None

        df      = agregar_todos_los_indicadores(df_raw)
        señales = generar_señales(df)
        ml      = entrenar_y_predecir(df, dias_futuro=5)

        noticias_raw = obtener_noticias(ticker, empresa=nombre, max_noticias=5)
        sentimiento  = analizar_noticias(noticias_raw)
        veredicto    = calcular_veredicto_final(señales, sentimiento, ml)

        if abs(veredicto["puntaje"]) < UMBRAL_ALERTA:
            return None

        close         = df_raw["Close"].squeeze()
        precio_actual = float(close.iloc[-1])
        precio_semana = float(close.iloc[-6]) if len(close) > 5 else precio_actual
        cambio_7d     = ((precio_actual - precio_semana) / precio_semana * 100) if precio_semana else 0
        info          = obtener_info_empresa(ticker)

        return {
            "ticker":           ticker,
            "nombre":           nombre,
            "sector":           sector,
            "veredicto":        veredicto["veredicto"],
            "emoji":            veredicto["emoji"],
            "puntaje":          veredicto["puntaje"],
            "confianza":        veredicto["confianza"],
            "precio_actual":    round(precio_actual, 2),
            "cambio_7d":        round(cambio_7d, 2),
            "moneda":           info.get("moneda", "USD"),
            "es_argentina":     ticker.endswith(".BA"),
            "prob_subida":      ml.get("probabilidad_subida", 0.5),
            "causa_principal":  max(señales.values(), key=lambda x: abs(x["señal"]))["descripcion"],
            "señales_tecnicas": señales,
            "timestamp":        datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
    except Exception as e:
        _log(f"⚠️ Error analizando {ticker}: {e}")
        return None


# ── Ciclo de revisión ────────────────────────────────────────

def ciclo_revision() -> None:
    _log("🔍 Iniciando revisión del mercado...")

    estado = _leer_estado()
    estado["ultima_revision"]  = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    estado["proxima_revision"] = (
        datetime.now() + timedelta(hours=INTERVALO_HORAS)
    ).strftime("%d/%m/%Y %H:%M:%S")
    _guardar_estado(estado)

    todas = ACCIONES_ARGENTINAS[:15] + ACCIONES_GLOBALES[:15]
    alertas_generadas = 0

    for ticker, nombre, sector in todas:
        # Leer estado fresco en cada iteración
        if not _leer_estado().get("activo", False):
            _log("⏸ Scheduler detenido durante revisión.")
            break

        if _en_cooldown(ticker):
            _log(f"  ⏭ {ticker}: en cooldown, omitiendo")
            continue

        _log(f"  📊 Analizando {ticker}...")
        alerta = analizar_ticker_para_alerta(ticker, nombre, sector)

        if alerta:
            _log(f"  🚨 SEÑAL: {alerta['veredicto']} {ticker} (puntaje: {alerta['puntaje']:+.3f})")

            email_ok = False
            if configuracion_valida():
                ok, msg_email = enviar_alerta(alerta)
                email_ok = ok
                if ok:
                    _log(f"  ✅ Email enviado a {alerta['ticker']}")
                else:
                    _log(f"  ⚠️ Email fallido: {msg_email}")
            else:
                _log("  ⚠️ Email no configurado")

            registrar_alerta(alerta, email_enviado=email_ok)
            _marcar_cooldown(ticker)

            # Incrementar contador en estado persistido
            estado = _leer_estado()
            estado["alertas_sesion"] = estado.get("alertas_sesion", 0) + 1
            _guardar_estado(estado)

            alertas_generadas += 1

        time.sleep(3)

    _log(f"✅ Revisión completa: {alertas_generadas} alertas de {len(todas)} acciones (próxima en 30 min).")


# ── Loop del scheduler ───────────────────────────────────────

def _loop_scheduler() -> None:
    _log("🟢 Scheduler iniciado.")
    while True:
        # Verificar si sigue activo antes de cada ciclo
        if not _leer_estado().get("activo", False):
            break

        try:
            ciclo_revision()
        except Exception as e:
            _log(f"❌ Error en ciclo: {e}")

        # Esperar INTERVALO_HORAS antes del próximo ciclo
        # Chequeamos cada 15 segundos si fue detenido
        _log(f"⏳ Esperando {INTERVALO_HORAS}h para la próxima revisión...")
        segundos_espera = INTERVALO_HORAS * 3600
        transcurridos   = 0
        detenido        = False

        while transcurridos < segundos_espera:
            time.sleep(15)
            transcurridos += 15
            if not _leer_estado().get("activo", False):
                _log("⏸ Scheduler detenido durante espera.")
                detenido = True
                break

        if detenido:
            break

    _log("🔴 Scheduler detenido.")


# ── API pública ──────────────────────────────────────────────

def iniciar_scheduler() -> str:
    global _hilo_activo
    estado = _leer_estado()
    if estado.get("activo", False):
        return "El scheduler ya está activo."

    estado["activo"]         = True
    estado["alertas_sesion"] = 0
    estado["log"]            = []
    _guardar_estado(estado)

    _hilo_activo = threading.Thread(target=_loop_scheduler, daemon=True)
    _hilo_activo.start()
    return "✅ Scheduler iniciado. Revisará el mercado cada 1 hora."


def detener_scheduler() -> str:
    estado = _leer_estado()
    if not estado.get("activo", False):
        return "El scheduler no está activo."
    estado["activo"] = False
    _guardar_estado(estado)
    return "⏸ Scheduler detenido."


def obtener_estado() -> dict:
    estado = _leer_estado()
    return {
        "activo":           estado.get("activo", False),
        "ultima_revision":  estado.get("ultima_revision"),
        "proxima_revision": estado.get("proxima_revision"),
        "alertas_sesion":   estado.get("alertas_sesion", 0),
        "log":              estado.get("log", [])[-15:],
    }
