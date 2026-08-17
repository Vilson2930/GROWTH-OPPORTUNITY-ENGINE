# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# config.py
#
# Configuração central da estratégia.
#
# IMPORTANTE:
# Estes parâmetros reproduzem as regras finais do estudo.
# Não alterar sem novo estudo estatístico.
# =============================================================================

from pathlib import Path


# =============================================================================
# 1. IDENTIDADE DO PROJETO
# =============================================================================

PROJECT_NAME = "GROWTH OPPORTUNITY ENGINE"

PROJECT_VERSION = "1.0.0"

PROJECT_DESCRIPTION = (
    "Institutional Growth & Entry Opportunity System"
)


# =============================================================================
# 2. DIRETÓRIOS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

OUTPUT_DIR = BASE_DIR / "output"

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =============================================================================
# 3. ARQUIVOS DE SAÍDA
# =============================================================================

HISTORY_FILE = DATA_DIR / "history.csv"

OPPORTUNITIES_FILE = (
    OUTPUT_DIR / "opportunities.csv"
)

REPORT_FILE = (
    OUTPUT_DIR / "report.pdf"
)


# =============================================================================
# 4. BENCHMARK
# =============================================================================

BENCHMARK = "SPY"


# =============================================================================
# 5. UNIVERSO INICIAL
#
# Começamos com o mesmo universo usado no estudo.
# Depois poderemos expandir sem alterar a estratégia.
# =============================================================================

UNIVERSE = [

    # ---------------------------------------------------------
    # MEGA CAP / SOFTWARE / INTERNET
    # ---------------------------------------------------------

    "MSFT",
    "GOOGL",
    "META",
    "AMZN",
    "AAPL",
    "CRM",
    "ADBE",
    "NOW",
    "ORCL",

    # ---------------------------------------------------------
    # SEMICONDUTORES
    # ---------------------------------------------------------

    "NVDA",
    "AMD",
    "AVGO",
    "QCOM",
    "MU",
    "INTC",

    # ---------------------------------------------------------
    # FINTECH / PAGAMENTOS / FINANCE
    # ---------------------------------------------------------

    "SOFI",
    "PYPL",
    "HOOD",
    "V",
    "MA",
    "JPM",

    # ---------------------------------------------------------
    # E-COMMERCE / DIGITAL
    # ---------------------------------------------------------

    "MELI",
    "SHOP",
    "NFLX",
    "UBER",

    # ---------------------------------------------------------
    # CONSUMO
    # ---------------------------------------------------------

    "COST",
    "WMT",
    "NKE",
    "SBUX",
    "MCD",

    # ---------------------------------------------------------
    # SAÚDE
    # ---------------------------------------------------------

    "LLY",
    "UNH",
    "JNJ",
    "PFE",

    # ---------------------------------------------------------
    # INDUSTRIAL
    # ---------------------------------------------------------

    "CAT",
    "GE",
    "BA",

    # ---------------------------------------------------------
    # ENERGIA
    # ---------------------------------------------------------

    "XOM",
    "CVX",

    # ---------------------------------------------------------
    # OUTROS
    # ---------------------------------------------------------

    "DIS",
    "F",
    "GM",
]


# =============================================================================
# 6. DADOS DE MERCADO
# =============================================================================

PRICE_PERIOD = "max"

PRICE_INTERVAL = "1d"

MIN_HISTORY_DAYS = 252

SMA_SHORT = 20

SMA_CONFIRMATION = 50


# =============================================================================
# 7. EVENTO DE QUEDA
#
# Zona validada no estudo.
# =============================================================================

MIN_PULLBACK = 0.20

MAX_PULLBACK = 0.30


# =============================================================================
# 8. CRESCIMENTO FUNDAMENTAL
#
# O estudo final usa crescimento de receita + EPS/LPA
# como núcleo fundamental.
#
# Estes valores são critérios mínimos operacionais.
# =============================================================================

MIN_REVENUE_GROWTH = 0.10

MIN_EPS_GROWTH = 0.10


# =============================================================================
# 9. FALLING KNIFE SCORE
#
# Regras congeladas da Célula 18D.
#
# Cada condição verdadeira soma +1.
# =============================================================================

FALLING_RULES = {

    # preço 10% ou mais abaixo da SMA50
    "DIST_SMA50_10": -0.10,

    # preço 15% ou mais abaixo da SMA50
    "DIST_SMA50_15": -0.15,

    # retorno 5 dias
    "RETURN_5D": -0.05,

    # retorno 10 dias
    "RETURN_10D": -0.08,

    # retorno 20 dias
    "RETURN_20D": -0.12,

    # fechamento perto da mínima do candle
    "CLOSE_LOCATION": 0.25,

    # volume relativo fraco
    "VOLUME_RELATIVE_LOW": 1.00,
}


# =============================================================================
# 10. CLASSIFICAÇÃO FALLING KNIFE
# =============================================================================

FALLING_LOW_MAX = 1

FALLING_MODERATE = 2

FALLING_HIGH_MIN = 3


# =============================================================================
# 11. CONFIRMAÇÕES
#
# Usadas principalmente quando Falling Score >= 3.
# =============================================================================

CONFIRMATION_SMA50_DISTANCE = -0.10

CONFIRMATION_INSTITUTIONAL_SCORE = 2

CONFIRMATION_VOLUME_RATIO = 1.30

MIN_CONFIRMATIONS_HIGH_RISK = 2


# =============================================================================
# 12. SMART MONEY / INSTITUCIONAL
#
# Mantido como confirmação.
# Não é filtro eliminatório.
# =============================================================================

INSTITUTIONAL_SCORE_MIN_CONFIRMATION = 2


# =============================================================================
# 13. REGRA DE ENTRADA
#
# ENTRADA FORTE:
# Falling Score <= 1
#
# ENTRADA PARCIAL:
# Falling Score == 2
#
# OU:
# Falling Score >= 3 + 2 confirmações
#
# AGUARDAR:
# Falling Score >= 3 sem confirmações suficientes
# =============================================================================

SIGNAL_STRONG = "ENTRADA_FORTE"

SIGNAL_PARTIAL = "ENTRADA_PARCIAL"

SIGNAL_WAIT = "AGUARDAR"


# =============================================================================
# 14. TAMANHO DA POSIÇÃO
# =============================================================================

STRONG_INITIAL_WEIGHT = 1.00

PARTIAL_INITIAL_WEIGHT = 0.60

PARTIAL_CONFIRMATION_WEIGHT = 0.40

WAIT_INITIAL_WEIGHT = 0.00


# =============================================================================
# 15. REGRA DA SEGUNDA ENTRADA
#
# Para ENTRADA PARCIAL:
# os 40% restantes somente entram após crossover real da SMA50.
#
# Caso não aconteça:
# permanece em caixa.
# =============================================================================

SECOND_ENTRY_TRIGGER = "CROSS_SMA50"

KEEP_UNCONFIRMED_CAPITAL_IN_CASH = True


# =============================================================================
# 16. VOLUME
# =============================================================================

VOLUME_LOOKBACK = 20

VOLUME_CONFIRMATION_RATIO = 1.30


# =============================================================================
# 17. MOMENTUM
# =============================================================================

RETURN_WINDOWS = {

    "5D": 5,

    "10D": 10,

    "20D": 20,
}


# =============================================================================
# 18. RELATÓRIO
# =============================================================================

REPORT_TOP_OPPORTUNITIES = 20

REPORT_INCLUDE_WAIT = True

REPORT_INCLUDE_REASON = True

REPORT_INCLUDE_RAW_METRICS = True


# =============================================================================
# 19. HISTÓRICO
# =============================================================================

SAVE_HISTORY = True

HISTORY_DEDUPLICATE_KEYS = [
    "ticker",
    "date",
    "signal",
]


# =============================================================================
# 20. VALIDAÇÕES DE SEGURANÇA
# =============================================================================

REQUIRE_PRICE_DATA = True

REQUIRE_FUNDAMENTAL_DATA = True

REQUIRE_VOLUME_DATA = True

ALLOW_PARTIAL_DATA = False


# =============================================================================
# 21. PROTEÇÃO CONTRA LOOK-AHEAD
# =============================================================================

STRICT_POINT_IN_TIME = True

ALLOW_FUTURE_DATA = False


# =============================================================================
# 22. MODO OPERACIONAL
# =============================================================================

DRY_RUN = False

GENERATE_CSV = True

GENERATE_PDF = True

VERBOSE = True


# =============================================================================
# 23. RESUMO DA CONFIGURAÇÃO
# =============================================================================

def print_config():

    print("=" * 80)

    print(PROJECT_NAME)

    print("=" * 80)

    print(
        f"Versão: {PROJECT_VERSION}"
    )

    print(
        f"Benchmark: {BENCHMARK}"
    )

    print(
        f"Empresas no universo: "
        f"{len(UNIVERSE)}"
    )

    print(
        f"Zona de queda: "
        f"{MIN_PULLBACK*100:.0f}% "
        f"a "
        f"{MAX_PULLBACK*100:.0f}%"
    )

    print(
        f"Crescimento mínimo receita: "
        f"{MIN_REVENUE_GROWTH*100:.0f}%"
    )

    print(
        f"Crescimento mínimo EPS: "
        f"{MIN_EPS_GROWTH*100:.0f}%"
    )

    print(
        f"Entrada forte: "
        f"{STRONG_INITIAL_WEIGHT*100:.0f}%"
    )

    print(
        f"Entrada parcial: "
        f"{PARTIAL_INITIAL_WEIGHT*100:.0f}% "
        f"+ "
        f"{PARTIAL_CONFIRMATION_WEIGHT*100:.0f}% "
        f"após SMA50"
    )

    print(
        f"Confirmações exigidas em falling alto: "
        f"{MIN_CONFIRMATIONS_HIGH_RISK}"
    )

    print(
        f"Point-in-time estrito: "
        f"{STRICT_POINT_IN_TIME}"
    )

    print("=" * 80)


# =============================================================================
# TESTE LOCAL
# =============================================================================

if __name__ == "__main__":

    print_config()
