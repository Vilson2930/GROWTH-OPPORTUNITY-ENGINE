# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# engine/fundamentals.py
#
# Motor fundamental.
#
# Fonte principal:
# SEC / EDGAR Company Facts
#
# Responsabilidades:
# - mapear ticker -> CIK
# - baixar fundamentos oficiais
# - calcular crescimento YoY de receita
# - calcular crescimento YoY de EPS/LPA
# - classificar crescimento fundamental
#
# NÃO toma decisão final de entrada.
# =============================================================================

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import requests

from config import (
    UNIVERSE,
    MIN_REVENUE_GROWTH,
    MIN_EPS_GROWTH,
    VERBOSE,
)


# =============================================================================
# 1. SEC
# =============================================================================

SEC_TICKERS_URL = (
    "https://www.sec.gov/files/company_tickers.json"
)

SEC_COMPANYFACTS_URL = (
    "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
)

# IMPORTANTE:
# SEC exige identificação do cliente.
#
# Pode manter assim inicialmente.
# Depois podemos colocar email/configuração própria.
SEC_HEADERS = {
    "User-Agent": (
        "GrowthOpportunityEngine/1.0 "
        "research@example.com"
    ),
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}

SEC_TICKER_HEADERS = {
    "User-Agent": (
        "GrowthOpportunityEngine/1.0 "
        "research@example.com"
    )
}

REQUEST_TIMEOUT = 30

SEC_DELAY = 0.12


# =============================================================================
# 2. TAGS XBRL
# =============================================================================

# Receita pode aparecer com tags diferentes dependendo da empresa.
REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues",
]

# EPS diluído tem prioridade.
EPS_TAGS = [
    "EarningsPerShareDiluted",
    "EarningsPerShareBasicAndDiluted",
    "EarningsPerShareBasic",
]


# =============================================================================
# 3. SESSÃO HTTP
# =============================================================================

SESSION = requests.Session()


# =============================================================================
# 4. MAPA TICKER -> CIK
# =============================================================================

def load_sec_ticker_map() -> Dict[str, str]:
    """
    Baixa mapa oficial ticker -> CIK da SEC.
    """

    response = SESSION.get(
        SEC_TICKERS_URL,
        headers=SEC_TICKER_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    raw = response.json()

    mapping = {}

    for item in raw.values():

        ticker = str(
            item.get("ticker", "")
        ).upper()

        cik = str(
            item.get("cik_str", "")
        ).zfill(10)

        if ticker and cik:
            mapping[ticker] = cik

    return mapping


# =============================================================================
# 5. DOWNLOAD COMPANY FACTS
# =============================================================================

def download_company_facts(
    cik: str,
    ticker: str = "",
    retries: int = 3,
) -> Optional[dict]:
    """
    Baixa Company Facts de uma empresa.
    """

    url = SEC_COMPANYFACTS_URL.format(
        cik=cik
    )

    for attempt in range(
        1,
        retries + 1,
    ):

        try:

            response = SESSION.get(
                url,
                headers=SEC_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            time.sleep(
                SEC_DELAY
            )

            return response.json()

        except Exception as exc:

            if VERBOSE:

                print(
                    f"⚠️ {ticker}: SEC tentativa "
                    f"{attempt}/{retries}: {exc}"
                )

            if attempt < retries:
                time.sleep(2)

    return None


# =============================================================================
# 6. LOCALIZAR TAG
# =============================================================================

def _find_fact(
    companyfacts: dict,
    tags: list,
) -> Optional[dict]:
    """
    Procura a primeira tag válida em us-gaap.
    """

    facts = (
        companyfacts
        .get("facts", {})
        .get("us-gaap", {})
    )

    for tag in tags:

        if tag in facts:
            return facts[tag]

    return None


# =============================================================================
# 7. CONVERTER FACT EM DATAFRAME
# =============================================================================

def _fact_to_dataframe(
    fact: dict,
    preferred_units: list,
) -> pd.DataFrame:
    """
    Converte unidades da SEC em dataframe.
    """

    if fact is None:
        return pd.DataFrame()

    units = fact.get(
        "units",
        {}
    )

    selected = None

    for unit in preferred_units:

        if unit in units:
            selected = units[unit]
            break

    if selected is None:
        return pd.DataFrame()

    df = pd.DataFrame(
        selected
    )

    if df.empty:
        return df

    required = [
        "end",
        "val",
        "filed",
        "form",
    ]

    for col in required:

        if col not in df.columns:
            return pd.DataFrame()

    df["end"] = pd.to_datetime(
        df["end"],
        errors="coerce",
    )

    df["filed"] = pd.to_datetime(
        df["filed"],
        errors="coerce",
    )

    df["val"] = pd.to_numeric(
        df["val"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "end",
            "filed",
            "val",
        ]
    )

    return df


# =============================================================================
# 8. FILTRAR TRIMESTRES
# =============================================================================

def _quarterly_values(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Seleciona observações trimestrais utilizáveis.

    Mantém 10-Q e 10-K,
    reduz duplicidades e prioriza
    o registro mais recentemente protocolado.
    """

    if df.empty:
        return df

    temp = df[
        df["form"].isin(
            [
                "10-Q",
                "10-K",
                "10-Q/A",
                "10-K/A",
            ]
        )
    ].copy()

    if temp.empty:
        return temp

    # Se existir fp, priorizar Q1/Q2/Q3/FY.
    if "fp" in temp.columns:

        temp = temp[
            temp["fp"].isin(
                [
                    "Q1",
                    "Q2",
                    "Q3",
                    "FY",
                ]
            )
        ]

    # Elimina observações duplicadas
    # para o mesmo período.
    temp = (
        temp
        .sort_values(
            [
                "end",
                "filed",
            ]
        )
        .drop_duplicates(
            subset=[
                "end",
            ],
            keep="last",
        )
    )

    return temp.sort_values(
        "end"
    ).reset_index(
        drop=True
    )


# =============================================================================
# 9. CRESCIMENTO YOY
# =============================================================================

def _calculate_yoy(
    df: pd.DataFrame,
) -> Tuple[
    float,
    Optional[pd.Timestamp],
]:
    """
    Calcula crescimento YoY usando último período
    e período aproximadamente equivalente 1 ano antes.

    Procura período com diferença entre
    330 e 400 dias.
    """

    if df is None or len(df) < 2:
        return np.nan, None

    df = df.sort_values(
        "end"
    ).copy()

    latest = df.iloc[-1]

    latest_date = latest["end"]
    latest_value = latest["val"]

    previous_candidates = df[
        df["end"] < latest_date
    ].copy()

    previous_candidates[
        "days_difference"
    ] = (
        latest_date
        -
        previous_candidates["end"]
    ).dt.days

    previous_candidates = (
        previous_candidates[
            previous_candidates[
                "days_difference"
            ].between(
                330,
                400,
            )
        ]
    )

    if previous_candidates.empty:
        return np.nan, latest_date

    previous_candidates[
        "distance_365"
    ] = (
        previous_candidates[
            "days_difference"
        ]
        -
        365
    ).abs()

    previous = (
        previous_candidates
        .sort_values(
            "distance_365"
        )
        .iloc[0]
    )

    old_value = previous["val"]

    if (
        pd.isna(old_value)
        or old_value == 0
    ):
        return np.nan, latest_date

    # Receita: interpretação normal.
    #
    # EPS negativo pode gerar crescimento
    # matematicamente estranho.
    # O tratamento específico será feito depois.
    growth = (
        latest_value
        /
        abs(old_value)
        - 1
    )

    return float(growth), latest_date


# =============================================================================
# 10. RECEITA
# =============================================================================

def extract_revenue_growth(
    companyfacts: dict,
) -> Tuple[
    float,
    Optional[pd.Timestamp],
]:
    """
    Extrai crescimento YoY de receita.
    """

    fact = _find_fact(
        companyfacts,
        REVENUE_TAGS,
    )

    df = _fact_to_dataframe(
        fact,
        preferred_units=[
            "USD",
        ],
    )

    df = _quarterly_values(
        df
    )

    return _calculate_yoy(
        df
    )


# =============================================================================
# 11. EPS
# =============================================================================

def extract_eps_growth(
    companyfacts: dict,
) -> Tuple[
    float,
    Optional[pd.Timestamp],
]:
    """
    Extrai crescimento YoY de EPS/LPA.

    Prioridade:
    EPS diluído.
    """

    fact = _find_fact(
        companyfacts,
        EPS_TAGS,
    )

    df = _fact_to_dataframe(
        fact,
        preferred_units=[
            "USD/shares",
            "USD / shares",
        ],
    )

    df = _quarterly_values(
        df
    )

    if len(df) < 2:
        return np.nan, None

    latest = df.iloc[-1]

    latest_date = latest["end"]
    latest_eps = latest["val"]

    candidates = df[
        df["end"] < latest_date
    ].copy()

    candidates[
        "days_difference"
    ] = (
        latest_date
        -
        candidates["end"]
    ).dt.days

    candidates = candidates[
        candidates[
            "days_difference"
        ].between(
            330,
            400,
        )
    ]

    if candidates.empty:
        return np.nan, latest_date

    candidates[
        "distance_365"
    ] = (
        candidates[
            "days_difference"
        ]
        -
        365
    ).abs()

    old = (
        candidates
        .sort_values(
            "distance_365"
        )
        .iloc[0]
    )

    previous_eps = old["val"]

    # -------------------------------------------------------------------------
    # Casos
    # -------------------------------------------------------------------------

    # lucro positivo nos dois períodos
    if (
        previous_eps > 0
        and latest_eps > 0
    ):

        growth = (
            latest_eps
            /
            previous_eps
            - 1
        )

        return float(growth), latest_date

    # saiu de prejuízo para lucro:
    # recuperação fundamental forte.
    if (
        previous_eps <= 0
        and latest_eps > 0
    ):

        return 1.0, latest_date

    # continua negativo
    if latest_eps <= 0:

        return np.nan, latest_date

    return np.nan, latest_date


# =============================================================================
# 12. CLASSIFICAÇÃO FUNDAMENTAL
# =============================================================================

def classify_growth(
    revenue_growth: float,
    eps_growth: float,
) -> str:
    """
    Classificação simples e interpretável.

    CRESCIMENTO_FORTE:
    receita >= mínimo
    E
    EPS >= mínimo.
    """

    if (
        pd.isna(revenue_growth)
        or pd.isna(eps_growth)
    ):
        return "SEM_DADOS"

    if (
        revenue_growth
        >= MIN_REVENUE_GROWTH
        and
        eps_growth
        >= MIN_EPS_GROWTH
    ):
        return "CRESCIMENTO_FORTE"

    return "NAO_APROVADO"


# =============================================================================
# 13. ANALISAR EMPRESA
# =============================================================================

def analyze_company_fundamentals(
    ticker: str,
    cik: str,
) -> Optional[dict]:
    """
    Analisa uma empresa.
    """

    companyfacts = download_company_facts(
        cik=cik,
        ticker=ticker,
    )

    if companyfacts is None:
        return None

    revenue_growth, revenue_period = (
        extract_revenue_growth(
            companyfacts
        )
    )

    eps_growth, eps_period = (
        extract_eps_growth(
            companyfacts
        )
    )

    classification = classify_growth(
        revenue_growth,
        eps_growth,
    )

    return {
        "ticker":
            ticker,

        "cik":
            cik,

        "revenue_yoy":
            revenue_growth,

        "eps_growth_yoy":
            eps_growth,

        "revenue_period":
            revenue_period,

        "eps_period":
            eps_period,

        "growth_class":
            classification,

        "fundamentals_ok":
            (
                classification
                ==
                "CRESCIMENTO_FORTE"
            ),
    }


# =============================================================================
# 14. ANALISAR UNIVERSO
# =============================================================================

def analyze_fundamentals(
    tickers=None,
) -> pd.DataFrame:
    """
    Analisa o universo completo.
    """

    if tickers is None:
        tickers = UNIVERSE

    ticker_map = load_sec_ticker_map()

    rows = []

    total = len(tickers)

    print("=" * 80)
    print(
        "GROWTH OPPORTUNITY ENGINE"
    )
    print(
        "ANÁLISE FUNDAMENTAL — SEC"
    )
    print("=" * 80)

    for i, ticker in enumerate(
        tickers,
        start=1,
    ):

        ticker = ticker.upper()

        cik = ticker_map.get(
            ticker
        )

        if VERBOSE:

            print(
                f"[{i:>3}/{total}] "
                f"{ticker:<8}",
                end=" ",
            )

        if cik is None:

            if VERBOSE:
                print(
                    "❌ CIK não encontrado"
                )

            continue

        result = (
            analyze_company_fundamentals(
                ticker,
                cik,
            )
        )

        if result is None:

            if VERBOSE:
                print(
                    "❌ falha SEC"
                )

            continue

        rows.append(
            result
        )

        if VERBOSE:

            rev = result[
                "revenue_yoy"
            ]

            eps = result[
                "eps_growth_yoy"
            ]

            rev_text = (
                f"{rev*100:.1f}%"
                if pd.notna(rev)
                else "N/A"
            )

            eps_text = (
                f"{eps*100:.1f}%"
                if pd.notna(eps)
                else "N/A"
            )

            print(
                f"✅ Receita {rev_text} | "
                f"EPS {eps_text} | "
                f"{result['growth_class']}"
            )

    result_df = pd.DataFrame(
        rows
    )

    print("-" * 80)

    print(
        f"Empresas solicitadas: "
        f"{total}"
    )

    print(
        f"Fundamentos obtidos: "
        f"{len(result_df)}"
    )

    if not result_df.empty:

        approved = (
            result_df[
                "fundamentals_ok"
            ].sum()
        )

        print(
            f"Crescimento forte: "
            f"{approved}"
        )

    print("=" * 80)

    return result_df


# =============================================================================
# 15. TESTE LOCAL
# =============================================================================

if __name__ == "__main__":

    TEST_TICKERS = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
    ]

    fundamentals = (
        analyze_fundamentals(
            TEST_TICKERS
        )
    )

    if fundamentals.empty:

        print(
            "❌ Nenhum fundamento disponível."
        )

    else:

        print("\nRESULTADO:")

        show = fundamentals[
            [
                "ticker",
                "revenue_yoy",
                "eps_growth_yoy",
                "growth_class",
                "fundamentals_ok",
            ]
        ].copy()

        show[
            "revenue_yoy"
        ] *= 100

        show[
            "eps_growth_yoy"
        ] *= 100

        print(
            show.to_string(
                index=False
            )
        )
