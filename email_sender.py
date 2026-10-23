# ============================================================
# email_sender.py
# ------------------------------------------------------------
# Envía alertas de inversión por email usando Gmail SMTP.
#
# CONFIGURACIÓN (una sola vez):
#   1. Abrí tu cuenta Gmail
#   2. Activá la verificación en dos pasos si no la tenés
#   3. Andá a: Cuenta Google → Seguridad → Contraseñas de aplicación
#   4. Creá una contraseña para "Correo" → copiá los 16 caracteres
#   5. Pegala en EMAIL_PASSWORD abajo (no es tu contraseña real)
# ============================================================

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ============================================================
# ⚙️  CONFIGURACIÓN — EDITÁ ESTOS VALORES
# ============================================================
EMAIL_REMITENTE    = ""
EMAIL_CONTRASENA   = ""   # Contraseña de aplicación (16 chars)
EMAIL_DESTINATARIO = ""
# ============================================================


def configuracion_valida() -> bool:
    return (
        EMAIL_REMITENTE != ""
        and EMAIL_CONTRASENA != ""
        and len(EMAIL_CONTRASENA.replace(" ", "")) == 16
    )


def construir_html_alerta(alerta: dict) -> str:
    ticker    = alerta.get("ticker", "N/A")
    nombre    = alerta.get("nombre", ticker)
    veredicto = alerta.get("veredicto", "N/A")
    puntaje   = alerta.get("puntaje", 0)
    precio    = alerta.get("precio_actual", 0)
    moneda    = alerta.get("moneda", "USD")
    cambio_7d = alerta.get("cambio_7d", 0)
    causa     = alerta.get("causa_principal", "")
    confianza = alerta.get("confianza", "Media")
    sector    = alerta.get("sector", "")
    hora      = alerta.get("timestamp", datetime.now().strftime("%d/%m/%Y %H:%M"))
    es_arg    = alerta.get("es_argentina", False)

    if veredicto == "COMPRAR":
        color_v, fondo_v, emoji_v = "#00c853", "#e8f5e9", "🟢"
    elif veredicto == "VENDER":
        color_v, fondo_v, emoji_v = "#d50000", "#ffebee", "🔴"
    else:
        color_v, fondo_v, emoji_v = "#f57f17", "#fff8e1", "🟡"

    color_cambio = "#00c853" if cambio_7d >= 0 else "#d50000"
    icono_cambio = "▲" if cambio_7d >= 0 else "▼"
    bandera      = "🇦🇷" if es_arg else "🌎"

    señales_html = ""
    for nombre_s, datos_s in alerta.get("señales_tecnicas", {}).items():
        s    = datos_s.get("señal", 0)
        desc = datos_s.get("descripcion", "")
        color_s = "#00c853" if s > 0 else "#d50000" if s < 0 else "#888"
        icono_s = "▲" if s > 0 else "▼" if s < 0 else "━"
        señales_html += (
            f"<tr>"
            f"<td style='padding:4px 8px;color:#555;font-size:13px;'>{nombre_s.replace('_',' ')}</td>"
            f"<td style='padding:4px 8px;color:{color_s};font-size:13px;'>{icono_s} {desc}</td>"
            f"</tr>"
        )

    señales_bloque = ""
    if señales_html:
        señales_bloque = (
            "<div style='margin-bottom:20px;'>"
            "<div style='font-size:12px;color:#888;margin-bottom:8px;'>INDICADORES TÉCNICOS</div>"
            f"<table style='width:100%;border-collapse:collapse;'>{señales_html}</table>"
            "</div>"
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1);overflow:hidden;">
  <div style="background:#1a1a2e;padding:20px 24px;">
    <h2 style="color:#00d4ff;margin:0;font-size:20px;">📈 Market Analyzer — Alerta de Inversión</h2>
    <p style="color:#888;margin:4px 0 0;font-size:13px;">{hora}</p>
  </div>
  <div style="padding:24px;">
    <h3 style="margin:0 0 4px;font-size:22px;color:#1a1a2e;">{bandera} {ticker} — {nombre}</h3>
    <p style="margin:0 0 16px;color:#888;font-size:13px;">{sector}</p>

    <div style="background:{fondo_v};border-left:4px solid {color_v};border-radius:8px;padding:16px;margin-bottom:20px;text-align:center;">
      <div style="font-size:36px;font-weight:bold;color:{color_v};">{emoji_v} {veredicto}</div>
      <div style="color:#555;margin-top:4px;font-size:14px;">Puntaje: <b>{puntaje:+.3f}</b> · Confianza: <b>{confianza}</b></div>
    </div>

    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
      <tr>
        <td style="padding:10px;background:#f9f9f9;border-radius:8px;text-align:center;width:33%;">
          <div style="font-size:11px;color:#888;">PRECIO ACTUAL</div>
          <div style="font-size:18px;font-weight:bold;color:#1a1a2e;">{moneda} {precio:,.2f}</div>
        </td>
        <td style="width:2%;"></td>
        <td style="padding:10px;background:#f9f9f9;border-radius:8px;text-align:center;width:33%;">
          <div style="font-size:11px;color:#888;">ÚLTIMOS 7 DÍAS</div>
          <div style="font-size:18px;font-weight:bold;color:{color_cambio};">{icono_cambio} {abs(cambio_7d):.1f}%</div>
        </td>
        <td style="width:2%;"></td>
        <td style="padding:10px;background:#f9f9f9;border-radius:8px;text-align:center;width:33%;">
          <div style="font-size:11px;color:#888;">ML: PROB. SUBIDA</div>
          <div style="font-size:18px;font-weight:bold;color:#1a1a2e;">{alerta.get('prob_subida', 0.5):.1%}</div>
        </td>
      </tr>
    </table>

    <div style="background:#f0f4ff;border-radius:8px;padding:14px;margin-bottom:20px;">
      <div style="font-size:12px;color:#888;margin-bottom:4px;">SEÑAL PRINCIPAL</div>
      <div style="font-size:14px;color:#1a1a2e;">💡 {causa}</div>
    </div>

    {señales_bloque}

    <div style="border-top:1px solid #eee;padding-top:16px;">
      <p style="font-size:11px;color:#aaa;margin:0;">
        ⚠️ Alerta generada automáticamente por Market Analyzer. Solo educativo.
        No constituye asesoramiento financiero.
      </p>
    </div>
  </div>
</div>
</body></html>"""


def enviar_alerta(alerta: dict) -> tuple:
    """
    Envía el email de alerta. Retorna (True, "OK") o (False, "error").
    """
    if not configuracion_valida():
        return False, "Configuración de email incompleta. Editá email_sender.py con tus datos de Gmail."

    ticker    = alerta.get("ticker", "N/A")
    veredicto = alerta.get("veredicto", "N/A")
    emoji_v   = "🟢" if veredicto == "COMPRAR" else "🔴" if veredicto == "VENDER" else "🟡"

    try:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = f"{emoji_v} Market Analyzer: {veredicto} {ticker}"
        msg["From"]    = EMAIL_REMITENTE
        msg["To"]      = EMAIL_DESTINATARIO

        texto_plano = (
            f"ALERTA MARKET ANALYZER\n{'='*40}\n"
            f"Acción: {ticker} — {alerta.get('nombre','')}\n"
            f"Veredicto: {veredicto}\n"
            f"Puntaje: {alerta.get('puntaje',0):+.3f}\n"
            f"Precio: {alerta.get('moneda','USD')} {alerta.get('precio_actual',0):,.2f}\n"
            f"Causa: {alerta.get('causa_principal','')}\n\n"
            f"⚠️ Solo educativo. No es asesoramiento financiero."
        )

        msg.attach(MIMEText(texto_plano, "plain", "utf-8"))
        msg.attach(MIMEText(construir_html_alerta(alerta), "html", "utf-8"))

        with smtplib.SMTP("smtp.gmail.com", 587) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(EMAIL_REMITENTE, EMAIL_CONTRASENA)
            srv.sendmail(EMAIL_REMITENTE, EMAIL_DESTINATARIO, msg.as_string())

        print(f"✅ Email enviado: {veredicto} {ticker}")
        return True, "OK"

    except smtplib.SMTPAuthenticationError:
        err = "Error de autenticación Gmail. Usá una 'Contraseña de aplicación', no tu clave normal."
        print(f"❌ {err}")
        return False, err

    except Exception as e:
        err = f"Error al enviar email: {str(e)}"
        print(f"❌ {err}")
        return False, err
