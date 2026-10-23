# ============================================================
# predictor.py
# ------------------------------------------------------------
# Este módulo usa Machine Learning (Aprendizaje Automático)
# para predecir si el precio de la acción subirá o bajará.
#
# Algoritmo: Random Forest (Bosque Aleatorio)
# ¿Qué es? Un conjunto de muchos "árboles de decisión" que
# votan juntos para dar una predicción más robusta.
#
# ¿Cómo funciona?
# 1. Tomamos datos históricos con sus indicadores técnicos
# 2. Creamos una "etiqueta": ¿el precio subió al día siguiente? Sí/No
# 3. Entrenamos el modelo para que aprenda patrones
# 4. Le pedimos que prediga el próximo movimiento
# ============================================================

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier    # El modelo de ML
from sklearn.preprocessing import StandardScaler       # Para normalizar datos
from sklearn.model_selection import train_test_split   # Para dividir datos
from sklearn.metrics import accuracy_score             # Para medir precisión


# Columnas que usamos como "features" (variables de entrada) para el modelo
# Estas son las características que el modelo usará para aprender
FEATURES = [
    "RSI",          # Índice de fuerza relativa
    "MACD",         # MACD principal
    "MACD_Señal",   # Línea de señal del MACD
    "MACD_Hist",    # Histograma MACD
    "BB_Posicion",  # Posición dentro de Bollinger
    "SMA_20",       # Media móvil 20 días
    "SMA_50",       # Media móvil 50 días
    "EMA_12",       # EMA rápida
    "EMA_26",       # EMA lenta
]


def preparar_datos(df: pd.DataFrame, dias_futuro: int = 5) -> tuple:
    """
    Prepara los datos para entrenar el modelo de ML.

    ¿Qué hace?
    - Crea la variable objetivo (target): ¿Subió el precio en N días?
    - Limpia los datos (elimina filas con valores faltantes)
    - Separa los features (X) de la etiqueta (y)

    Parámetro 'dias_futuro': cuántos días adelante predecimos.
    Si es 5, el modelo predice si el precio será más alto en 5 días.

    Retorna: (X, y, df_limpio)
    - X: tabla de features
    - y: vector de etiquetas (1=sube, 0=baja)
    - df_limpio: DataFrame sin filas con datos faltantes
    """

    df = df.copy()

    close = df["Close"].squeeze()

    # Creamos la variable objetivo:
    # Si el precio de cierre en N días es mayor al actual → 1 (sube)
    # Si es menor o igual → 0 (baja)
    df["Target"] = (close.shift(-dias_futuro) > close).astype(int)

    # Verificamos que tengamos las columnas de features
    features_disponibles = [f for f in FEATURES if f in df.columns]

    # Eliminamos filas con valores faltantes (NaN)
    # Esto ocurre al principio donde no hay suficiente historial para calcular indicadores
    df_limpio = df[features_disponibles + ["Target"]].dropna()

    # La última fila no tiene "Target" válido (es el futuro que queremos predecir)
    # la guardamos por separado y la quitamos del entrenamiento
    X = df_limpio[features_disponibles].iloc[:-dias_futuro]
    y = df_limpio["Target"].iloc[:-dias_futuro]

    return X, y, df_limpio, features_disponibles


def entrenar_y_predecir(df: pd.DataFrame, dias_futuro: int = 5) -> dict:
    """
    Función principal: entrena el modelo Random Forest y hace una predicción.

    Retorna un diccionario con:
    - prediccion: "COMPRA" o "VENTA"
    - probabilidad: confianza del modelo (0 a 1)
    - precision_historica: qué tan bien funcionó en datos pasados
    - señal: 1 (compra) o -1 (venta)
    - descripcion: texto explicativo
    """

    print("🤖 Entrenando modelo de Machine Learning...")

    try:
        X, y, df_limpio, features_usadas = preparar_datos(df, dias_futuro)

        # Necesitamos suficientes datos para entrenar
        if len(X) < 60:
            return {
                "prediccion": "INSUFICIENTE",
                "probabilidad": 0.5,
                "precision_historica": 0.5,
                "señal": 0,
                "descripcion": "No hay suficientes datos históricos para entrenar el modelo.",
                "error": True
            }

        # Dividimos en conjunto de entrenamiento (80%) y prueba (20%)
        # random_state=42 garantiza que siempre obtengamos el mismo resultado
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, shuffle=False
        )

        # Normalizamos los datos (todos en la misma escala)
        # Esto mejora el rendimiento del modelo
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Creamos y entrenamos el Random Forest
        # n_estimators=100: usamos 100 árboles de decisión
        modelo = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,           # Limitamos la profundidad para evitar sobreajuste
            random_state=42,
            class_weight="balanced"  # Compensamos si hay más días que suben que bajan
        )
        modelo.fit(X_train_scaled, y_train)

        # Evaluamos la precisión en datos que el modelo nunca vio
        y_pred_test = modelo.predict(X_test_scaled)
        precision = accuracy_score(y_test, y_pred_test)

        # Ahora predecimos el PRÓXIMO movimiento (con los datos más recientes)
        features_disponibles = [f for f in FEATURES if f in df.columns]
        ultima_fila = df[features_disponibles].dropna().iloc[[-1]]
        ultima_scaled = scaler.transform(ultima_fila)

        # predict_proba retorna la probabilidad de cada clase [baja, sube]
        probabilidades = modelo.predict_proba(ultima_scaled)[0]
        prob_sube = probabilidades[1]   # Probabilidad de que suba
        prob_baja = probabilidades[0]   # Probabilidad de que baje

        # Determinamos la predicción final
        if prob_sube > 0.55:
            prediccion = "COMPRA"
            señal = 1
            descripcion = f"El modelo predice subida con {prob_sube:.1%} de confianza en los próximos {dias_futuro} días."
        elif prob_baja > 0.55:
            prediccion = "VENTA"
            señal = -1
            descripcion = f"El modelo predice bajada con {prob_baja:.1%} de confianza en los próximos {dias_futuro} días."
        else:
            prediccion = "NEUTRAL"
            señal = 0
            descripcion = f"El modelo no tiene suficiente confianza para predecir dirección ({prob_sube:.1%} prob. de subida)."

        print(f"✅ Modelo entrenado. Precisión histórica: {precision:.1%} | Predicción: {prediccion}")

        return {
            "prediccion": prediccion,
            "probabilidad_subida": round(float(prob_sube), 3),
            "probabilidad_bajada": round(float(prob_baja), 3),
            "precision_historica": round(float(precision), 3),
            "señal": señal,
            "descripcion": descripcion,
            "dias_futuro": dias_futuro,
            "error": False
        }

    except Exception as e:
        print(f"❌ Error en el modelo: {e}")
        return {
            "prediccion": "ERROR",
            "probabilidad": 0.5,
            "precision_historica": 0.5,
            "señal": 0,
            "descripcion": f"Error al ejecutar el modelo: {str(e)}",
            "error": True
        }


def calcular_veredicto_final(
    señales_tecnicas: dict,
    sentimiento: dict,
    prediccion_ml: dict,
    macro: dict = None,
    geopolitica: dict = None,
) -> dict:
    """
    Combina TODAS las fuentes de información para dar un veredicto final.

    Sistema de puntaje ponderado (v2 con macro y geopolítica):
    - Indicadores técnicos:    40% del peso
    - Predicción ML:           25% del peso
    - Sentimiento noticias:    15% del peso
    - Análisis macroeconómico: 12% del peso
    - Análisis geopolítico:     8% del peso

    Retorna:
    --------
    {
        "veredicto": "COMPRAR" | "VENDER" | "MANTENER",
        "puntaje": float entre -1 y 1,
        "confianza": "Alta" | "Media" | "Baja",
        "desglose": dict con el aporte de cada fuente
    }
    """

    # ── Puntaje de indicadores técnicos (promedio de votos)
    votos_tecnicos = [v["señal"] for v in señales_tecnicas.values()]
    puntaje_tecnico = sum(votos_tecnicos) / len(votos_tecnicos) if votos_tecnicos else 0

    # ── Puntaje de sentimiento de noticias de empresa
    puntaje_sentimiento = sentimiento.get("señal", 0)

    # ── Puntaje del modelo ML
    puntaje_ml = prediccion_ml.get("señal", 0)

    # ── Puntaje macroeconómico (nuevo)
    puntaje_macro = macro.get("señal", 0) if macro else 0

    # ── Puntaje geopolítico (nuevo)
    puntaje_geo = geopolitica.get("señal", 0) if geopolitica else 0

    # ── Ponderamos cada fuente (suman 100%)
    peso_tecnico     = 0.40
    peso_ml          = 0.25
    peso_sentimiento = 0.15
    peso_macro       = 0.12
    peso_geo         = 0.08

    puntaje_final = (
        puntaje_tecnico     * peso_tecnico +
        puntaje_ml          * peso_ml +
        puntaje_sentimiento * peso_sentimiento +
        puntaje_macro       * peso_macro +
        puntaje_geo         * peso_geo
    )

    # ── Determinamos el veredicto
    if puntaje_final > 0.2:
        veredicto = "COMPRAR"
        emoji = "🟢"
    elif puntaje_final < -0.2:
        veredicto = "VENDER"
        emoji = "🔴"
    else:
        veredicto = "MANTENER"
        emoji = "🟡"

    # ── Nivel de confianza basado en qué tan extremo es el puntaje
    abs_puntaje = abs(puntaje_final)
    if abs_puntaje > 0.5:
        confianza = "Alta"
    elif abs_puntaje > 0.25:
        confianza = "Media"
    else:
        confianza = "Baja"

    # ── Alertas críticas combinadas (macro + geo)
    alertas_criticas = []
    if macro:
        alertas_criticas += macro.get("alertas", [])
    if geopolitica:
        alertas_criticas += geopolitica.get("alertas", [])

    return {
        "veredicto": veredicto,
        "emoji": emoji,
        "puntaje": round(puntaje_final, 3),
        "confianza": confianza,
        "alertas_criticas": alertas_criticas,
        "desglose": {
            "tecnico": round(puntaje_tecnico, 3),
            "sentimiento": puntaje_sentimiento,
            "ml": puntaje_ml,
            "macro": round(puntaje_macro, 3),
            "geo": round(puntaje_geo, 3),
        }
    }
