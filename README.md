# 📈 Market Analyzer

Simulador de análisis bursátil que combina análisis técnico, machine learning y fuentes de información externa para generar sugerencias de inversión sobre acciones argentinas y globales.

> ⚠️ **Aviso:** Este proyecto es un simulador educativo. No constituye asesoramiento financiero ni ejecuta órdenes reales de compra/venta.

---

## ¿Qué hace?

El sistema analiza acciones del MERVAL, CEDEARs y mercados globales (NYSE/NASDAQ) evaluando múltiples fuentes de información de forma simultánea:

- **Análisis técnico:** velas japonesas, RSI, MACD, Bandas de Bollinger y medias móviles (SMA/EMA)
- **Machine Learning:** modelo Random Forest entrenado con datos históricos del propio activo para predecir movimientos a 5 días
- **Sentimiento de noticias:** análisis NLP de noticias recientes sobre cada empresa usando TextBlob
- **Macroeconomía:** indicadores del FRED (Fed de EE.UU.) — inflación, tasas de interés, desempleo, curva de rendimiento — más VIX, oro y petróleo vía Yahoo Finance
- **Geopolítica:** monitoreo de noticias internacionales (Reuters, BBC, Al Jazeera) clasificadas por categoría (conflictos, sanciones, crisis energéticas) y su impacto sectorial

Cuando la confianza del análisis supera un umbral definido, el sistema envía una **alerta automática por email** con el veredicto, precio actual, causa principal de la señal y desglose de indicadores. El usuario decide si actuar o no.

---

## Funcionalidades principales

- **Dashboard web** interactivo con gráfico de velas japonesas, indicadores técnicos y panel de noticias
- **Panel de oportunidades** al inicio: escanea automáticamente el mercado y muestra los activos más prometedores
- **Monitor de alertas** con scheduler configurable (cada 30 minutos por defecto)
- **Paper trading:** registro persistente de decisiones simuladas con capital ficticio, historial de operaciones y métricas de rendimiento
- **Soporte para acciones argentinas** con tickers verificados del MERVAL y CEDEARs

---

## Stack tecnológico

| Capa | Tecnologías |
|---|---|
| Dashboard | Dash, Plotly, Dash Bootstrap Components |
| Datos de mercado | yfinance (Yahoo Finance) |
| Indicadores técnicos | Cálculo propio sobre pandas/numpy |
| Machine Learning | scikit-learn (Random Forest) |
| NLP / Sentimiento | TextBlob, feedparser |
| Macroeconomía | FRED API pública, Yahoo Finance |
| Emails | smtplib (Gmail SMTP) |
| Persistencia | JSON local |

---

## Estructura del proyecto

```
market_analyzer/
├── app.py              # Dashboard web (punto de entrada)
├── data_fetcher.py     # Descarga de precios y noticias
├── technical.py        # Indicadores técnicos y señales
├── predictor.py        # Modelo ML y veredicto final
├── sentiment.py        # Análisis de sentimiento de noticias
├── macro.py            # Indicadores macroeconómicos
├── geopolitics.py      # Análisis geopolítico por categoría
├── watchlist.py        # Lista de acciones y escaneo de oportunidades
├── alerts.py           # Scheduler de alertas automáticas
├── paper_trading.py    # Registro de decisiones simuladas
├── email_sender.py     # Envío de alertas por Gmail
└── requirements.txt    # Dependencias
```

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/fedelopezrubio/Market_analyzer.git
cd Market_analyzer

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar email (opcional, para recibir alertas)
# Editá email_sender.py con tu cuenta Gmail y tu contraseña de aplicación
# Instrucciones: https://myaccount.google.com/apppasswords

# 4. Ejecutar
python app.py
```

Abrí el navegador en `http://127.0.0.1:8050`

---

## Cómo funciona el veredicto

Cada señal se pondera para calcular un puntaje final entre -1 y +1:

| Fuente | Peso |
|---|---|
| Indicadores técnicos | 40% |
| Modelo ML | 25% |
| Sentimiento de noticias | 15% |
| Macroeconomía | 12% |
| Geopolítica | 8% |

El sistema emite **COMPRAR** si el puntaje supera +0.2, **VENDER** si cae por debajo de -0.2, y **MANTENER** en el rango intermedio. Las alertas por email se envían solo cuando el puntaje supera ±0.45 (umbral de alta confianza).

---

## Mercados cubiertos

- **MERVAL (Argentina):** GGAL, YPFD, BMA, PAMP, TXAR, ALUA, CEPU, TECO2, CRES, LOMA, EDN, TGSU2, IRSA, METR, COME
- **CEDEARs:** AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, BABA, GOLD, KO
- **Globales (NYSE/NASDAQ):** AAPL, MSFT, GOOGL, NVDA, META, AMZN, TSLA, JPM, BAC, XOM, CVX, JNJ, PFE, WMT, NFLX, DIS, BRK-B, entre otros

---

## Autor

Fede López Rubio — Buenos Aires, Argentina
Estudiante de Licenciatura en Ciencia de Datos e Inteligencia Artificial (UADE)
