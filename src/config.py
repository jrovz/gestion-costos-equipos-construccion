"""Constantes compartidas entre los notebooks, las Azure Functions y el agente.

Un solo lugar para nombres de columnas, umbrales y parametros que antes vivian
repetidos (a veces con copy-paste) en cada notebook.
"""

COLS = ["price_x", "price_y", "price_z", "price_equipo1", "price_equipo2"]
MATERIAS = ["price_x", "price_y", "price_z"]
EQUIPOS = ["price_equipo1", "price_equipo2"]

NOMBRES = {
    "price_x": "X",
    "price_y": "Y",
    "price_z": "Z",
    "price_equipo1": "Equipo1",
    "price_equipo2": "Equipo2",
}

# Fase 1: umbral de variacion diaria para marcar un salto de precio como inusual.
# Fase 4 (agente): mismo umbral para decidir si un precio reportado por Telegram
# necesita confirmacion antes de guardarse.
UMBRAL_VARIACION = 0.15

# Fase 2
MAX_LAG_CCF = 20
N_LAGS_FEATURES = 5
VAR_MAXLAGS = 10
JOHANSEN_K_AR_DIFF = 1
GRANGER_MAXLAG = 5

# Fase 3
HORIZONTES = {"1 mes": 21, "3 meses": 63, "6 meses": 126}
TEST_DIAS = 504  # ~2 anios habiles
ORIGIN_STEP = 21
VECM_K_AR_DIFF = 1
VECM_COINT_RANK = 1
