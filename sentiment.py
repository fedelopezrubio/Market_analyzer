# ============================================================
# sentiment.py
# ------------------------------------------------------------
# Este módulo analiza el sentimiento de las noticias.
# "Sentimiento" en este contexto significa: ¿las noticias
# sobre la empresa son positivas, negativas o neutras?
#
# Usamos TextBlob, una librería de Procesamiento de Lenguaje
# Natural (NLP) que asigna un puntaje de -1 a +1 a cualquier
# texto en inglés:
#   +1 = muy positivo
#    0 = neutral
#   -1 = muy negativo
# ============================================================

from textblob import TextBlob   # Librería de análisis de texto


def analizar_sentimiento_texto(texto: str) -> dict:
    """
    Analiza el sentimiento de un texto y retorna un diccionario
    con el puntaje y la etiqueta correspondiente.

    TextBlob usa un diccionario de palabras con puntajes pre-asignados.
    Por ejemplo: "great" = +0.8, "terrible" = -0.9, etc.

    Retorna:
    --------
    {
        "puntaje": float entre -1.0 y 1.0,
        "etiqueta": "Positivo" | "Negativo" | "Neutral",
        "subjetividad": float entre 0 (objetivo) y 1 (subjetivo)
    }
    """

    if not texto or str(texto).strip() == "":
        return {"puntaje": 0.0, "etiqueta": "Neutral", "subjetividad": 0.0}

    # TextBlob analiza el texto y devuelve polarity y subjectivity
    analisis = TextBlob(str(texto))

    puntaje = analisis.sentiment.polarity        # -1 a +1
    subjetividad = analisis.sentiment.subjectivity  # 0 a 1

    # Clasificamos el puntaje en categorías
    if puntaje > 0.1:
        etiqueta = "Positivo"
    elif puntaje < -0.1:
        etiqueta = "Negativo"
    else:
        etiqueta = "Neutral"

    return {
        "puntaje": round(puntaje, 3),
        "etiqueta": etiqueta,
        "subjetividad": round(subjetividad, 3)
    }


def analizar_noticias(noticias: list) -> dict:
    """
    Analiza el sentimiento de una lista de noticias y calcula
    un puntaje general de sentimiento del mercado.

    Parámetro:
    ----------
    noticias: Lista de diccionarios con claves 'titulo' y 'resumen'
              (tal como retorna data_fetcher.obtener_noticias)

    Retorna:
    --------
    {
        "puntaje_promedio": promedio de todos los puntajes,
        "sentimiento_general": "Positivo" | "Negativo" | "Neutral",
        "noticias_analizadas": lista con cada noticia y su sentimiento,
        "señal": 1 (positivo), -1 (negativo), 0 (neutral),
        "conteo": {"Positivo": N, "Negativo": N, "Neutral": N}
    }
    """

    if not noticias:
        return {
            "puntaje_promedio": 0.0,
            "sentimiento_general": "Neutral",
            "noticias_analizadas": [],
            "señal": 0,
            "conteo": {"Positivo": 0, "Negativo": 0, "Neutral": 0}
        }

    noticias_analizadas = []
    puntajes = []
    conteo = {"Positivo": 0, "Negativo": 0, "Neutral": 0}

    for noticia in noticias:
        # Combinamos título y resumen para un análisis más completo
        texto_completo = f"{noticia.get('titulo', '')} {noticia.get('resumen', '')}"

        resultado = analizar_sentimiento_texto(texto_completo)

        # Agregamos el resultado a la noticia original
        noticia_con_sentimiento = {**noticia, **resultado}
        noticias_analizadas.append(noticia_con_sentimiento)

        puntajes.append(resultado["puntaje"])
        conteo[resultado["etiqueta"]] += 1

    # Calculamos el promedio de todos los puntajes
    puntaje_promedio = sum(puntajes) / len(puntajes) if puntajes else 0.0

    # Determinamos el sentimiento general
    if puntaje_promedio > 0.05:
        sentimiento_general = "Positivo"
        señal = 1
    elif puntaje_promedio < -0.05:
        sentimiento_general = "Negativo"
        señal = -1
    else:
        sentimiento_general = "Neutral"
        señal = 0

    return {
        "puntaje_promedio": round(puntaje_promedio, 3),
        "sentimiento_general": sentimiento_general,
        "noticias_analizadas": noticias_analizadas,
        "señal": señal,
        "conteo": conteo
    }


def sentimiento_a_descripcion(resultado: dict) -> str:
    """
    Convierte el resultado del análisis de sentimiento en un
    texto legible para mostrar en el dashboard.
    """
    promedio = resultado["puntaje_promedio"]
    general = resultado["sentimiento_general"]
    conteo = resultado["conteo"]

    return (
        f"Sentimiento de noticias: {general} (puntaje: {promedio:+.3f}) | "
        f"📈 {conteo['Positivo']} positivas · "
        f"📉 {conteo['Negativo']} negativas · "
        f"➖ {conteo['Neutral']} neutras"
    )
