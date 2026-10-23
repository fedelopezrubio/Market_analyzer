# ============================================================
# geopolitics.py
# ------------------------------------------------------------
# Este módulo analiza conflictos y eventos geopolíticos
# relevantes y calcula su impacto sobre el sector de la empresa.
#
# Fuentes gratuitas utilizadas:
#   - Google News RSS (búsquedas temáticas)
#   - Reuters RSS feed
#   - BBC News RSS feed
#
# Categorías de eventos monitoreados:
#   - Conflictos armados y guerras
#   - Sanciones económicas y guerras comerciales
#   - Crisis energéticas
#   - Tensiones en cadenas de suministro
#   - Elecciones y cambios de gobierno clave
#   - Crisis financieras regionales
# ============================================================

import feedparser
import re
from datetime import datetime
from sentiment import analizar_sentimiento_texto


# ============================================================
# CONFIGURACIÓN DE EVENTOS GEOPOLÍTICOS
# ============================================================

# Cada categoría tiene:
# - keywords: palabras clave para buscar en noticias
# - impacto_sectorial: cómo afecta a cada sector
# - descripcion: texto explicativo para el usuario

CATEGORIAS_GEO = {
    "conflicto_armado": {
        "keywords": ["war", "conflict", "military", "invasion", "attack", "missile", "troops", "ceasefire", "combat"],
        "descripcion": "Conflicto armado / guerra",
        "impacto_sectorial": {
            "Energy":               +1,   # Petróleo sube en conflictos
            "Materials":            +1,   # Commodities escasos
            "Industrials":          +1,   # Defensa y manufactura bélica
            "Technology":           -1,   # Cadenas de suministro afectadas
            "Consumer Discretionary": -1,
            "Consumer Staples":      0,
            "Financials":           -1,   # Incertidumbre sistémica
            "Real Estate":          -1,
            "Health Care":          +1,   # Demanda médica
            "Utilities":            -1,
            "Communication Services": -1,
            "default":              -1,
        }
    },
    "guerra_comercial": {
        "keywords": ["tariff", "trade war", "sanctions", "embargo", "trade deal", "customs", "import duty", "export ban"],
        "descripcion": "Tensión comercial / aranceles / sanciones",
        "impacto_sectorial": {
            "Technology":           -1,   # Chips, componentes afectados
            "Consumer Discretionary": -1, # Precios al consumidor suben
            "Industrials":          -1,
            "Materials":            -1,
            "Energy":               +1,   # Reconfiguración de rutas
            "Consumer Staples":     -1,
            "Financials":            0,
            "Health Care":          -1,   # Insumos importados
            "Real Estate":           0,
            "Utilities":             0,
            "Communication Services": -1,
            "default":              -1,
        }
    },
    "crisis_energia": {
        "keywords": ["energy crisis", "oil shock", "gas shortage", "OPEC", "pipeline", "LNG", "natural gas", "blackout", "power grid"],
        "descripcion": "Crisis energética / shock petrolero",
        "impacto_sectorial": {
            "Energy":               +2,   # Muy positivo para el sector
            "Utilities":            -1,   # Costos operativos suben
            "Industrials":          -1,
            "Consumer Discretionary": -1,
            "Technology":           -1,   # Data centers energo-intensivos
            "Consumer Staples":     -1,   # Costos de producción suben
            "Financials":           -1,
            "Materials":            -1,
            "Real Estate":           0,
            "Health Care":          -1,
            "Communication Services": -1,
            "default":              -1,
        }
    },
    "crisis_suministro": {
        "keywords": ["supply chain", "shortage", "chip shortage", "semiconductor", "logistics", "shipping", "port", "freight"],
        "descripcion": "Crisis en cadenas de suministro",
        "impacto_sectorial": {
            "Technology":           -2,   # Altamente dependiente de chips
            "Consumer Discretionary": -1,
            "Industrials":          -1,
            "Materials":            +1,   # Escasez sube precios
            "Energy":                0,
            "Consumer Staples":     -1,
            "Financials":            0,
            "Real Estate":           0,
            "Health Care":          -1,
            "Utilities":             0,
            "Communication Services": -1,
            "default":              -1,
        }
    },
    "tension_geopolitica": {
        "keywords": ["geopolitical", "tension", "diplomatic", "crisis", "NATO", "UN security", "nuclear threat", "espionage", "cyber attack"],
        "descripcion": "Tensión geopolítica / diplomática",
        "impacto_sectorial": {
            "Industrials":          +1,   # Defensa
            "Energy":               +1,   # Incertidumbre de suministro
            "Technology":           -1,   # Restricciones tecnológicas
            "Financials":           -1,   # Riesgo sistémico
            "default":              -1,
        }
    },
    "elecciones_cambio_pol": {
        "keywords": ["election", "government", "policy change", "regulation", "legislation", "president", "congress", "parliament"],
        "descripcion": "Cambios políticos / regulatorios",
        "impacto_sectorial": {
            "Financials":           -1,   # Riesgo regulatorio
            "Technology":           -1,   # Riesgo antimonopolio
            "Energy":               -1,   # Regulaciones ambientales
            "Health Care":          -1,   # Reforma sanitaria
            "default":               0,
        }
    },
    "crisis_financiera": {
        "keywords": ["financial crisis", "bank failure", "recession", "default", "debt crisis", "bankruptcy", "credit crunch", "liquidity"],
        "descripcion": "Crisis financiera / bancaria",
        "impacto_sectorial": {
            "Financials":           -2,
            "Real Estate":          -2,
            "Consumer Discretionary": -2,
            "Technology":           -1,
            "Industrials":          -1,
            "Consumer Staples":     +1,   # Defensivo
            "Health Care":          +1,   # Defensivo
            "Utilities":            +1,   # Defensivo
            "default":              -1,
        }
    },
}

# Fuentes RSS de noticias internacionales (gratuitas, sin API key)
FUENTES_RSS = [
    ("Reuters", "https://feeds.reuters.com/reuters/topNews"),
    ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Google News Geopolitics", "https://news.google.com/rss/search?q=geopolitics+conflict+war+sanctions&hl=en-US&gl=US&ceid=US:en"),
    ("Google News Economy", "https://news.google.com/rss/search?q=economy+recession+inflation+tariff&hl=en-US&gl=US&ceid=US:en"),
]


def contiene_keywords(texto: str, keywords: list) -> bool:
    """Verifica si un texto contiene alguna de las palabras clave dadas."""
    if not texto:
        return False
    texto_lower = str(texto).lower()
    return any(kw.lower() in texto_lower for kw in keywords)


def obtener_noticias_geopoliticas(max_por_fuente: int = 15) -> list:
    """
    Descarga noticias de múltiples fuentes RSS internacionales.
    Retorna una lista de artículos con título, resumen y fecha.
    """
    print("🌍 Descargando noticias geopolíticas y macroeconómicas...")

    todas_noticias = []
    titulos_vistos = set()  # Para evitar duplicados

    for nombre_fuente, url in FUENTES_RSS:
        try:
            feed = feedparser.parse(url)
            for entrada in feed.entries[:max_por_fuente]:
                titulo = entrada.get("title", "")
                if titulo in titulos_vistos:
                    continue
                titulos_vistos.add(titulo)

                todas_noticias.append({
                    "fuente": nombre_fuente,
                    "titulo": titulo,
                    "resumen": entrada.get("summary", titulo),
                    "link": entrada.get("link", ""),
                    "fecha": entrada.get("published", ""),
                })
        except Exception as e:
            print(f"  ⚠️ Error en fuente {nombre_fuente}: {e}")

    print(f"  ✅ {len(todas_noticias)} noticias geopolíticas obtenidas")
    return todas_noticias


def categorizar_noticia(noticia: dict) -> list:
    """
    Determina a qué categorías geopolíticas pertenece una noticia.
    Una noticia puede pertenecer a múltiples categorías.
    Retorna lista de categorías identificadas.
    """
    texto = f"{noticia.get('titulo') or ''} {noticia.get('resumen') or ''}"
    categorias_encontradas = []

    for cat_id, cat_info in CATEGORIAS_GEO.items():
        if contiene_keywords(texto, cat_info["keywords"]):
            categorias_encontradas.append(cat_id)

    return categorias_encontradas


def analizar_geopolitica(sector: str) -> dict:
    """
    Función principal del módulo.
    Descarga noticias, las categoriza y calcula el impacto
    geopolítico sobre el sector de la empresa analizada.

    Retorna:
    --------
    {
        "señales": dict con señales por categoría detectada,
        "noticias_relevantes": lista de noticias con categoría e impacto,
        "alertas": lista de alertas críticas,
        "puntaje": float entre -2 y +2,
        "sentimiento_geo": "Favorable" | "Desfavorable" | "Mixto",
        "señal": 1 | 0 | -1
    }
    """

    noticias = obtener_noticias_geopoliticas()
    señales = {}
    noticias_relevantes = []
    alertas = []
    conteo_categorias = {}

    # ── Procesamos cada noticia
    for noticia in noticias:
        categorias = categorizar_noticia(noticia)
        if not categorias:
            continue  # Noticia sin relevancia geopolítica

        # Analizamos sentimiento del texto
        sentimiento = analizar_sentimiento_texto(f"{noticia['titulo']} {noticia['resumen']}")

        for cat_id in categorias:
            cat_info = CATEGORIAS_GEO[cat_id]
            impacto = cat_info["impacto_sectorial"].get(sector, cat_info["impacto_sectorial"].get("default", 0))

            # Acumulamos para esta categoría
            if cat_id not in conteo_categorias:
                conteo_categorias[cat_id] = {"count": 0, "impacto_total": 0, "noticias": []}
            conteo_categorias[cat_id]["count"] += 1
            conteo_categorias[cat_id]["impacto_total"] += impacto
            conteo_categorias[cat_id]["noticias"].append(noticia["titulo"])

            noticia_procesada = {
                **noticia,
                "categoria": cat_info["descripcion"],
                "impacto": impacto,
                "sentimiento": sentimiento["etiqueta"],
                "puntaje_sentimiento": sentimiento["puntaje"],
            }
            noticias_relevantes.append(noticia_procesada)

    # ── Construimos señales por categoría
    impactos_totales = []
    for cat_id, datos in conteo_categorias.items():
        cat_info = CATEGORIAS_GEO[cat_id]
        impacto_promedio = datos["impacto_total"] / datos["count"] if datos["count"] else 0
        impactos_totales.append(impacto_promedio)

        señales[cat_id] = {
            "descripcion": cat_info["descripcion"],
            "noticias_detectadas": datos["count"],
            "impacto": round(impacto_promedio, 2),
            "impacto_sector": "Positivo ▲" if impacto_promedio > 0 else "Negativo ▼" if impacto_promedio < 0 else "Neutral ━",
            "ejemplo_titulo": datos["noticias"][0][:80] if datos["noticias"] else "",
        }

        # Alertas para eventos críticos con muchas noticias
        if datos["count"] >= 5 and abs(impacto_promedio) >= 1:
            alertas.append(
                f"⚠️ {cat_info['descripcion']}: {datos['count']} noticias detectadas → "
                f"impacto {'negativo' if impacto_promedio < 0 else 'positivo'} para {sector}"
            )

    # ── Puntaje geopolítico global (promedio de todas las categorías)
    puntaje_geo = sum(impactos_totales) / len(impactos_totales) if impactos_totales else 0

    # Normalizamos a rango -1 / +1
    puntaje_normalizado = max(-1, min(1, puntaje_geo / 2))

    if puntaje_normalizado > 0.1:
        sentimiento_geo = "Favorable"
        señal = 1
    elif puntaje_normalizado < -0.1:
        sentimiento_geo = "Desfavorable"
        señal = -1
    else:
        sentimiento_geo = "Mixto"
        señal = 0

    # Eliminamos duplicados en noticias_relevantes
    titulos_vistos = set()
    noticias_unicas = []
    for n in noticias_relevantes:
        if n["titulo"] not in titulos_vistos:
            titulos_vistos.add(n["titulo"])
            noticias_unicas.append(n)

    print(f"✅ Análisis geopolítico completo: {len(señales)} categorías, {len(noticias_unicas)} noticias relevantes")

    return {
        "señales": señales,
        "noticias_relevantes": noticias_unicas[:20],  # Máximo 20 para el dashboard
        "alertas": alertas,
        "puntaje": round(puntaje_normalizado, 3),
        "sentimiento_geo": sentimiento_geo,
        "señal": señal,
        "sector": sector,
        "total_noticias_analizadas": len(noticias),
    }
