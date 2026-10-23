# 📈 Market Analyzer

Analizador de acciones con indicadores técnicos, sentimiento de noticias y Machine Learning.

---

## 🚀 Instalación paso a paso

### 1. Instalá Python (si no lo tenés)
Descargá Python 3.10 o superior desde: https://www.python.org/downloads/

### 2. Creá una carpeta y copiá todos los archivos
Asegurate de tener en la misma carpeta:
```
market_analyzer/
├── app.py
├── data_fetcher.py
├── technical.py
├── sentiment.py
├── predictor.py
└── requirements.txt
```

### 3. Instalá las dependencias
Abrí una terminal (cmd en Windows, Terminal en Mac/Linux) dentro de la carpeta y ejecutá:

```bash
pip install -r requirements.txt
```

Si usás Python 3 y el comando anterior no funciona, probá:
```bash
pip3 install -r requirements.txt
```

### 4. Descargá los datos de idioma de TextBlob (solo la primera vez)
```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('averaged_perceptron_tagger')"
```

### 5. Ejecutá la aplicación
```bash
python app.py
```

### 6. Abrí el dashboard
En tu navegador, ingresá a: **http://127.0.0.1:8050**

---

## 🎯 Cómo usarlo

1. Escribí el **ticker** de la acción que querés analizar:
   - `AAPL` → Apple
   - `MSFT` → Microsoft
   - `GOOGL` → Google / Alphabet
   - `TSLA` → Tesla
   - `AMZN` → Amazon
   - `NVDA` → NVIDIA
   - `META` → Meta (Facebook)
   - `BRK-B` → Berkshire Hathaway

2. Seleccioná el **período** de análisis (más datos = modelo más preciso)

3. Presioná **"🔍 Analizar"** y esperá unos segundos

---

## 📊 ¿Qué analiza el programa?

### Indicadores Técnicos (50% del peso)
| Indicador | Qué mide |
|-----------|----------|
| RSI | Sobrecompra / sobreventa |
| MACD | Dirección de la tendencia |
| Bollinger | Volatilidad y extremos de precio |
| SMA 50 | Tendencia de mediano plazo |
| Cruce MA | Cruce Dorado / Cruce de la Muerte |

### Modelo de Machine Learning (30% del peso)
- Algoritmo: **Random Forest** (100 árboles de decisión)
- Entrenado con los propios datos históricos del activo
- Predice si el precio subirá en los próximos 5 días

### Sentimiento de Noticias (20% del peso)
- Fuente: Google News RSS (gratis, sin API key)
- Análisis con **TextBlob** (NLP)
- Puntaje de -1 (muy negativo) a +1 (muy positivo)

---

## ⚠️ Disclaimer
Este programa es **solo educativo**. No constituye asesoramiento financiero.
Los mercados son impredecibles y ningún modelo garantiza resultados.
Siempre consultá con un profesional antes de invertir.
