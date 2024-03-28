Toma el rol de un senior data scientist, senior Python engineer y arquitecto de producto B2B SaaS.

Quiero que construyas un notebook completo en Python para un MVP llamado:

Cyber Prospect Radar — X Signal Listener for Endpoint Security Sales

Objetivo del notebook:
Crear un sistema experimental que busque posts públicos en X/Twitter relacionados con señales comerciales para ventas de endpoint security, EDR, MDR, XDR y seguridad operacional. El notebook debe recolectar posts, limpiarlos, clasificarlos, asignar un opportunity score, generar un “Why Now?”, sugerir un ángulo comercial seguro y exportar los resultados a CSV.

IMPORTANTE:
Este MVP es para social listening ético usando información pública.
No debe hacer scraping agresivo.
No debe explotar vulnerabilidades.
No debe generar mensajes agresivos tipo “vi que estás vulnerable”.
No debe automatizar respuestas en X.
Solo debe generar señales internas para análisis comercial humano.

====================================================
CONTEXTO DEL PRODUCTO
====================================================

La app busca ayudar a un equipo de ventas que vende soluciones de endpoint security. Queremos detectar señales públicas como:

1. BUYING_INTENT
   Ejemplos:
   - looking for EDR
   - recommend EDR
   - best EDR
   - need MDR
   - endpoint security recommendation
   - any EDR recommendations

2. COMPETITOR_PAIN
   Ejemplos:
   - Defender is noisy
   - Defender false positives
   - CrowdStrike too expensive
   - alternatives to CrowdStrike
   - alternatives to SentinelOne
   - switching from Defender

3. OPERATIONAL_PAIN
   Ejemplos:
   - too many security alerts
   - alert fatigue
   - small security team
   - no SOC team
   - endpoint visibility
   - overwhelmed with alerts

4. COMPLIANCE_TRIGGER
   Ejemplos:
   - cyber insurance requirements
   - security questionnaire
   - SOC 2 audit
   - ISO 27001
   - endpoint compliance

5. HIRING_SIGNAL
   Ejemplos:
   - hiring security engineer
   - hiring SOC analyst
   - hiring IT manager
   - new CISO
   - new CIO

6. INDUSTRY_RISK
   Ejemplos:
   - healthcare ransomware
   - hospital ransomware
   - manufacturing ransomware
   - school district ransomware
   - municipality ransomware

====================================================
LO QUE QUIERO QUE GENERES
====================================================

Genera un notebook completo, bien estructurado y documentado, con secciones Markdown y celdas de código.

El notebook debe funcionar en Google Colab o local Jupyter.

Debe incluir:

1. Instalación de librerías
2. Imports
3. Configuración de API keys
4. Definición de queries por tipo de señal
5. Conexión con X API Recent Search
6. Recolección de posts públicos
7. Manejo de errores y rate limits
8. Limpieza de datos
9. Eliminación de duplicados
10. Clasificación rule-based
11. Scoring de oportunidad
12. Priorización High / Medium / Low / Ignore
13. Generación de:
    - why_now
    - sales_angle
    - safe_outreach_suggestion
14. Opción de clasificación con LLM usando OpenAI
15. Comparación entre clasificación rule-based y LLM
16. Visualizaciones básicas
17. Exportación a CSV
18. Diseño sugerido para pasar de notebook a app
19. Buenas prácticas éticas y legales
20. Próximos pasos

====================================================
REQUISITOS TÉCNICOS
====================================================

Usa Python 3.10+.

Librerías:
- requests
- pandas
- numpy
- python-dotenv
- matplotlib
- openai opcional

No uses seaborn.

El notebook debe poder funcionar aunque no exista X_BEARER_TOKEN, usando un modo MOCK_DATA para probar el pipeline.

Debe existir una variable:

USE_MOCK_DATA = True

Si USE_MOCK_DATA = True:
- El notebook debe cargar una lista de posts simulados.
- Los posts simulados deben incluir ejemplos de BUYING_INTENT, COMPETITOR_PAIN, OPERATIONAL_PAIN, COMPLIANCE_TRIGGER, HIRING_SIGNAL, INDUSTRY_RISK y ruido.

Si USE_MOCK_DATA = False:
- Debe usar X API Recent Search.
- Debe leer X_BEARER_TOKEN desde getpass o desde .env.
- Debe usar el endpoint:
  https://api.x.com/2/tweets/search/recent

La función de búsqueda debe llamarse:

search_recent_x_posts(query, bearer_token, max_results=10)

Debe recibir:
- query
- bearer_token
- max_results

Debe devolver una lista de posts normalizados.

Los campos normalizados deben ser:

platform
post_id
created_at
author_id
post_text
matched_query
initial_signal_type
like_count
reply_count
retweet_count
quote_count
source_url

Para source_url usa:
https://x.com/i/web/status/{post_id}

====================================================
ESTRUCTURA DEL NOTEBOOK
====================================================

Genera el notebook con esta estructura:

# Cyber Prospect Radar — X Signal Listener for Endpoint Security Sales

## 1. Problem Statement
Explica que el objetivo es identificar señales públicas de intención, dolor o contexto comercial para ventas de endpoint security.

## 2. Ethical Guardrails
Incluye reglas:
- usar solo contenido público
- no hacer scraping agresivo
- no automatizar respuestas
- no afirmar vulnerabilidad o compromiso sin evidencia explícita
- guardar solo datos mínimos necesarios
- mantener humano en el loop

## 3. Install Dependencies

Debe incluir:
!pip install requests pandas numpy python-dotenv openai matplotlib

## 4. Imports and Configuration

Incluye:
USE_MOCK_DATA = True
MAX_RESULTS_PER_QUERY = 10
SLEEP_BETWEEN_REQUESTS = 1.0
OUTPUT_CSV = "x_endpoint_sales_signals.csv"

## 5. Search Taxonomy

Define SEARCH_QUERIES como diccionario:

SEARCH_QUERIES = {
    "BUYING_INTENT": [...],
    "COMPETITOR_PAIN": [...],
    "OPERATIONAL_PAIN": [...],
    "COMPLIANCE_TRIGGER": [...],
    "HIRING_SIGNAL": [...],
    "INDUSTRY_RISK": [...]
}

Incluye queries listas para X, por ejemplo:
("looking for" OR recommend OR "any recommendations") ("EDR" OR "endpoint security" OR "MDR" OR "XDR")

Pero también incluye keywords simples entre comillas para pruebas.

## 6. Mock Data

Crea una función:

load_mock_posts()

Debe regresar una lista de diccionarios con posts simulados realistas.

Incluye al menos 18 posts:
- 3 de BUYING_INTENT
- 3 de COMPETITOR_PAIN
- 3 de OPERATIONAL_PAIN
- 3 de COMPLIANCE_TRIGGER
- 3 de HIRING_SIGNAL
- 2 de INDUSTRY_RISK
- 1 o 2 de ruido irrelevante

## 7. X API Connection

Crea funciones:

get_x_bearer_token()
search_recent_x_posts(query, bearer_token, max_results=10)
collect_x_posts(search_queries, bearer_token, max_results_per_query=10)

Requisitos:
- usar requests
- manejar response.status_code != 200
- imprimir error sin romper todo el notebook
- usar time.sleep entre requests
- normalizar datos
- agregar matched_query e initial_signal_type

## 8. Data Collection

Si USE_MOCK_DATA:
- carga mock posts
Si no:
- pide token
- colecta posts desde X API

Convierte todo a DataFrame llamado:

raw_df

Muestra:
raw_df.shape
raw_df.head()

## 9. Data Cleaning

Crea función:

clean_posts_df(df)

Debe:
- eliminar posts sin texto
- eliminar duplicados por post_id
- normalizar fechas
- crear columna post_text_clean
- remover saltos de línea extra
- preservar texto original
- reset index

## 10. Rule-Based Classification

Crea función:

classify_signal_rule_based(text)

Debe devolver:
{
  "signal_type": "...",
  "confidence": 0-100,
  "matched_terms": [...]
}

Debe detectar:
- BUYING_INTENT
- COMPETITOR_PAIN
- OPERATIONAL_PAIN
- COMPLIANCE_TRIGGER
- HIRING_SIGNAL
- INDUSTRY_RISK
- NONE

Usa listas de términos para cada categoría.

La lógica debe permitir que un post tenga múltiples señales internamente, pero debe seleccionar la principal con este orden de prioridad:

BUYING_INTENT > COMPETITOR_PAIN > OPERATIONAL_PAIN > COMPLIANCE_TRIGGER > HIRING_SIGNAL > INDUSTRY_RISK > NONE

## 11. Opportunity Scoring

Crea funciones:

score_signal(signal_type, confidence)
priority_from_score(score)

Base scores:
BUYING_INTENT = 40
COMPETITOR_PAIN = 35
OPERATIONAL_PAIN = 30
COMPLIANCE_TRIGGER = 25
HIRING_SIGNAL = 20
INDUSTRY_RISK = 15
NONE = 0

Fórmula:
score = min(100, int(base * confidence / 100))

Prioridad:
score >= 30: High
score >= 18: Medium
score > 0: Low
score == 0: Ignore

## 12. Sales Intelligence Fields

Crea funciones:

generate_why_now(signal_type)
generate_sales_angle(signal_type)
generate_safe_outreach(signal_type)

Requisitos:
- El outreach debe ser seguro, profesional, no invasivo.
- No debe usar frases como “vi que estás vulnerable”.
- Debe hablar de evaluación, checklist, visibilidad, reducción de ruido, MDR, compliance, etc.
- Debe dejar claro que es una sugerencia interna.

## 13. Apply Pipeline

Aplica:
- classification
- score
- priority
- why_now
- sales_angle
- safe_outreach_suggestion

Crea DataFrame final:

signals_df

Columnas finales:
platform
post_id
created_at
author_id
post_text
source_url
matched_query
initial_signal_type
signal_type
confidence
matched_terms
opportunity_score
priority
why_now
sales_angle
safe_outreach_suggestion
like_count
reply_count
retweet_count
quote_count

Ordena por:
priority_rank asc
opportunity_score desc
created_at desc

## 14. Review Top Signals

Muestra:
- top 20 señales
- solo High
- conteo por signal_type
- conteo por priority

## 15. Visualizations

Usa matplotlib.

Genera gráficos:
1. Bar chart de signal_type counts
2. Bar chart de priority counts
3. Histograma de opportunity_score

No uses colores específicos.
No uses seaborn.
Cada gráfico debe estar en una figura separada.

## 16. Optional LLM Classification

Agrega una sección opcional:

USE_LLM_CLASSIFIER = False

Si USE_LLM_CLASSIFIER = True:
- pedir OPENAI_API_KEY por getpass o .env
- usar OpenAI client
- clasificar solo los primeros N posts para controlar costo
- N debe estar en:
LLM_SAMPLE_SIZE = 20

Crea función:

classify_with_llm(post_text)

Prompt del LLM:

You are a cybersecurity sales intelligence analyst.

Analyze the following public X post and classify whether it contains a potential buying signal for endpoint security, EDR, MDR, XDR, ransomware protection, or security operations.

Rules:
- Use only the post text.
- Do not infer private facts.
- Do not claim the company is compromised unless the post explicitly says so.
- If the signal is weak, say weak.
- Return JSON only.

Post:
{post_text}

Return:
{
  "is_relevant": true,
  "signal_type": "BUYING_INTENT | COMPETITOR_PAIN | OPERATIONAL_PAIN | COMPLIANCE_TRIGGER | HIRING_SIGNAL | INDUSTRY_RISK | NONE",
  "confidence": 0,
  "why_it_matters": "",
  "recommended_sales_angle": "",
  "safe_outreach_suggestion": ""
}

Requisitos:
- temperature = 0
- manejar errores de JSON
- si falla, devolver NONE con confidence 0
- usar time.sleep para evitar rate limits

## 17. Compare Rule-Based vs LLM

Si USE_LLM_CLASSIFIER:
- crear comparación entre signal_type rule-based y llm_signal_type
- mostrar casos donde difieren
- explicar que el LLM ayuda a reducir falsos positivos pero puede tener costo y latencia

## 18. Export Results

Exporta:
signals_df.to_csv(OUTPUT_CSV, index=False)

Imprime ruta del archivo.

## 19. Productization Notes

Agrega Markdown explicando cómo pasar esto a app:

Fase 1:
Notebook + CSV

Fase 2:
Streamlit dashboard

Fase 3:
FastAPI + PostgreSQL

Fase 4:
Scheduler / cron

Fase 5:
Integración con Salesforce o CRM

Modelo de tabla sugerido:

CREATE TABLE x_signals (
    id SERIAL PRIMARY KEY,
    platform TEXT DEFAULT 'x',
    post_id TEXT UNIQUE,
    author_id TEXT,
    post_text TEXT,
    source_url TEXT,
    matched_query TEXT,
    signal_type TEXT,
    confidence_score INTEGER,
    opportunity_score INTEGER,
    priority TEXT,
    why_it_matters TEXT,
    recommended_sales_angle TEXT,
    safe_outreach_suggestion TEXT,
    detected_at TIMESTAMP DEFAULT NOW()
);

## 20. Final Recommendations

Agrega conclusiones:
- Primero validar calidad de señales
- Ajustar keywords
- Medir falsos positivos
- Mantener humano en el loop
- No hacer outreach automático
- Agregar company enrichment después
- Agregar fuentes adicionales como job posts, news, company pages y technographics

====================================================
CALIDAD DEL CÓDIGO
====================================================

El código debe estar limpio y comentado.

Cada función debe tener docstring.

Usa type hints cuando sea útil.

Maneja errores de forma segura.

No hardcodees secrets.

No imprimas API keys.

Haz que el notebook sea ejecutable de arriba abajo.

Debe poder correr en modo MOCK_DATA sin ninguna API key.

====================================================
ENTREGABLE
====================================================

Genera el notebook completo en formato Jupyter .ipynb.

También genera una versión Markdown o Python script si es útil.

El notebook debe llamarse:

cyber_prospect_radar_signal_listener.ipynb

Además, crea un archivo README.md breve con:
- descripción del proyecto
- cómo correrlo en modo mock
- cómo correrlo con X API
- variables de entorno necesarias
- limitaciones
- próximos pasos

No generes una app todavía. Solo el notebook completo, ejecutable y bien documentado.