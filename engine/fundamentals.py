# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# engine/fundamentals.py
#
# MOTOR FUNDAMENTAL — SEC / EDGAR
#
# Objetivo:
# - mapear ticker -> CIK
# - baixar Company Facts oficiais da SEC
# - reconstruir trimestres DISCRETOS
# - comparar o mesmo trimestre contra o ano anterior
# - evitar mistura entre trimestre, YTD e exercício anual
# - priorizar EPS diluído
# - manter lógica point-in-time
#
# NÃO toma decisão final de entrada.
# =============================================================================

from __future__ import annotations

import os
import time
from typing import Dict, Optional

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
# 1. CONFIGURAÇÃO SEC
# =============================================================================

SEC_TICKERS_URL = (
    "https://www.sec.gov/files/company_tickers.json"
)

SEC_COMPANYFACTS_URL = (
    "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
)

REQUEST_TIMEOUT = 30

SEC_DELAY = 0.12


# -----------------------------------------------------------------------------
# A SEC recomenda User-Agent identificável.
#
# No GitHub Actions podemos futuramente definir:
#
# SEC_USER_AGENT="GrowthOpportunityEngine/1.0 seu-email@dominio.com"
#
# -----------------------------------------------------------------------------

SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "GrowthOpportunityEngine/1.0 research@example.com",
)

SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}

SESSION = requests.Session()

# Máxima idade aceita para o trimestre fundamental atual.
# Evita usar silenciosamente fundamentos antigos como se fossem atuais.
MAX_FUNDAMENTAL_AGE_DAYS = 400


# =============================================================================
# 2. TAGS XBRL
# =============================================================================

REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues",
]

EPS_TAGS = [
    "EarningsPerShareDiluted",
    "EarningsPerShareBasicAndDiluted",
    "EarningsPerShareBasic",
]


# =============================================================================
# 3. MAPA TICKER -> CIK
# =============================================================================

def load_sec_ticker_map() -> Dict[str, str]:
    """
    Baixa o mapa oficial ticker -> CIK.
    """

    response = SESSION.get(
        SEC_TICKERS_URL,
        headers=SEC_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    raw = response.json()

    mapping = {}

    for item in raw.values():

        ticker = str(
            item.get(
                "ticker",
                "",
            )
        ).upper()

        cik = str(
            item.get(
                "cik_str",
                "",
            )
        ).zfill(10)

        if ticker and cik:
            mapping[ticker] = cik

    return mapping


# =============================================================================
# 4. COMPANY FACTS
# =============================================================================

def download_company_facts(
    cik: str,
    ticker: str = "",
    retries: int = 3,
) -> Optional[dict]:
    """
    Baixa Company Facts da SEC.
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

            result = response.json()

            time.sleep(
                SEC_DELAY
            )

            return result

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
# 5. LOCALIZAR TAG XBRL
# =============================================================================

def _find_fact(
    companyfacts: dict,
    tags: list[str],
) -> tuple[Optional[dict], Optional[str]]:
    """
    Retorna a primeira tag existente.
    """

    facts = (
        companyfacts
        .get("facts", {})
        .get("us-gaap", {})
    )

    for tag in tags:

        if tag in facts:

            return (
                facts[tag],
                tag,
            )

    return None, None


# =============================================================================
# 6. CONVERTER FACT PARA DATAFRAME
# =============================================================================

def _fact_to_dataframe(
    fact: Optional[dict],
    preferred_units: list[str],
) -> pd.DataFrame:
    """
    Converte uma tag Company Facts para DataFrame.
    """

    if fact is None:
        return pd.DataFrame()

    units = fact.get(
        "units",
        {},
    )

    values = None
    selected_unit = None

    for unit in preferred_units:

        if unit in units:

            values = units[unit]
            selected_unit = unit

            break

    if values is None:
        return pd.DataFrame()

    df = pd.DataFrame(
        values
    )

    if df.empty:
        return df

    required = [
        "start",
        "end",
        "val",
        "filed",
        "form",
    ]

    for column in required:

        if column not in df.columns:
            return pd.DataFrame()

    df["start"] = pd.to_datetime(
        df["start"],
        errors="coerce",
    )

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
            "start",
            "end",
            "filed",
            "val",
        ]
    ).copy()

    df["unit"] = selected_unit

    df["duration_days"] = (
        df["end"]
        -
        df["start"]
    ).dt.days + 1

    return df


# =============================================================================
# 7. FILTRO POINT-IN-TIME
# =============================================================================

def _point_in_time(
    df: pd.DataFrame,
    as_of_date=None,
) -> pd.DataFrame:
    """
    Mantém somente informações protocoladas
    até a data permitida.
    """

    if df.empty:
        return df

    if as_of_date is None:

        as_of_date = pd.Timestamp.utcnow()

        if as_of_date.tzinfo is not None:
            as_of_date = as_of_date.tz_localize(None)

        as_of_date = as_of_date.normalize()

    else:

        as_of_date = pd.Timestamp(
            as_of_date
        )

        if as_of_date.tzinfo is not None:
            as_of_date = as_of_date.tz_localize(None)

    return df[
        df["filed"]
        <= as_of_date
    ].copy()


# =============================================================================
# 8. FORMULÁRIOS VÁLIDOS
# =============================================================================

def _filter_financial_forms(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Mantém filings financeiros úteis.
    """

    if df.empty:
        return df

    valid_forms = [
        "10-Q",
        "10-Q/A",
        "10-K",
        "10-K/A",
    ]

    return df[
        df["form"].isin(
            valid_forms
        )
    ].copy()


# =============================================================================
# 9. TRIMESTRES DISCRETOS DIRETOS
# =============================================================================

def _direct_discrete_quarters(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Seleciona somente fatos com duração típica
    de um trimestre.

    Evita misturar:
    - trimestre
    - 6 meses acumulados
    - 9 meses acumulados
    - ano completo
    """

    if df.empty:
        return pd.DataFrame()

    temp = df[
        df["duration_days"].between(
            70,
            110,
        )
    ].copy()

    if temp.empty:
        return temp

    # -------------------------------------------------------------------------
    # Identificar trimestre fiscal.
    #
    # 10-Q:
    # Q1 / Q2 / Q3.
    #
    # Um fato trimestral discreto encontrado dentro de 10-K
    # é tratado como Q4.
    # -------------------------------------------------------------------------

    temp["quarter"] = None

    if "fp" in temp.columns:

        for q in [
            "Q1",
            "Q2",
            "Q3",
        ]:

            mask = (
                temp["fp"]
                ==
                q
            )

            temp.loc[
                mask,
                "quarter",
            ] = q

    mask_10k = (
        temp["form"]
        .isin(
            [
                "10-K",
                "10-K/A",
            ]
        )
    )

    temp.loc[
        mask_10k
        &
        temp["quarter"].isna(),
        "quarter",
    ] = "Q4"

    # -------------------------------------------------------------------------
    # Se frame SEC explicitamente indicar quarter,
    # pode ajudar na classificação.
    # -------------------------------------------------------------------------

    if "frame" in temp.columns:

        frame = (
            temp["frame"]
            .astype(str)
        )

        for q in [
            "Q1",
            "Q2",
            "Q3",
            "Q4",
        ]:

            mask = (
                frame.str.contains(
                    q,
                    regex=False,
                    na=False,
                )
            )

            temp.loc[
                mask
                &
                temp["quarter"].isna(),
                "quarter",
            ] = q

    temp = temp[
        temp["quarter"].notna()
    ].copy()

    # -------------------------------------------------------------------------
    # Fiscal year
    # -------------------------------------------------------------------------

    if "fy" in temp.columns:

        temp["fiscal_year"] = pd.to_numeric(
            temp["fy"],
            errors="coerce",
        )

    else:

        temp["fiscal_year"] = np.nan

    # fallback
    temp["fiscal_year"] = (
        temp["fiscal_year"]
        .fillna(
            temp["end"].dt.year
        )
    )

    # -------------------------------------------------------------------------
    # O mesmo trimestre pode aparecer novamente
    # em filings posteriores como comparativo.
    #
    # Mantemos a observação protocolada mais recentemente.
    # -------------------------------------------------------------------------

    temp = (
        temp
        .sort_values(
            [
                "fiscal_year",
                "quarter",
                "filed",
            ]
        )
        .drop_duplicates(
            subset=[
                "fiscal_year",
                "quarter",
            ],
            keep="last",
        )
    )

    temp["derived"] = False

    return temp


# =============================================================================
# 10. RECONSTRUIR Q4 DE RECEITA
# =============================================================================

def _derive_q4_revenue(
    full_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Para RECEITA somente:

    Q4 = Receita anual - Receita acumulada 9M.

    Receita é aditiva, portanto essa reconstrução
    é aceitável quando annual e 9M pertencem
    ao mesmo exercício fiscal.

    NÃO usamos esta técnica para EPS.
    """

    if full_df.empty:
        return pd.DataFrame()

    df = full_df.copy()

    if "fy" not in df.columns:
        return pd.DataFrame()

    df["fiscal_year"] = pd.to_numeric(
        df["fy"],
        errors="coerce",
    )

    rows = []

    fiscal_years = (
        df["fiscal_year"]
        .dropna()
        .unique()
    )

    for fiscal_year in fiscal_years:

        subset = df[
            df["fiscal_year"]
            ==
            fiscal_year
        ].copy()

        # ---------------------------------------------------------------------
        # ANUAL
        # ---------------------------------------------------------------------

        annual = subset[
            subset[
                "duration_days"
            ].between(
                300,
                400,
            )
            &
            subset[
                "form"
            ].isin(
                [
                    "10-K",
                    "10-K/A",
                ]
            )
        ].copy()

        if annual.empty:
            continue

        annual = (
            annual
            .sort_values(
                "filed"
            )
            .iloc[-1]
        )

        # ---------------------------------------------------------------------
        # 9 MESES / Q3 YTD
        # ---------------------------------------------------------------------

        ytd9 = subset[
            subset[
                "duration_days"
            ].between(
                240,
                300,
            )
            &
            subset[
                "form"
            ].isin(
                [
                    "10-Q",
                    "10-Q/A",
                ]
            )
        ].copy()

        if "fp" in ytd9.columns:

            preferred = ytd9[
                ytd9["fp"] == "Q3"
            ]

            if not preferred.empty:
                ytd9 = preferred

        if ytd9.empty:
            continue

        # somente 9M que termina antes do anual
        ytd9 = ytd9[
            ytd9["end"]
            <
            annual["end"]
        ]

        if ytd9.empty:
            continue

        ytd9 = (
            ytd9
            .sort_values(
                [
                    "end",
                    "filed",
                ]
            )
            .iloc[-1]
        )

        q4_value = (
            annual["val"]
            -
            ytd9["val"]
        )

        if not np.isfinite(
            q4_value
        ):
            continue

        q4_start = (
            ytd9["end"]
            +
            pd.Timedelta(
                days=1
            )
        )

        q4_duration = (
            annual["end"]
            -
            q4_start
        ).days + 1

        if not (
            60
            <= q4_duration
            <= 120
        ):
            continue

        rows.append(
            {
                "start":
                    q4_start,

                "end":
                    annual["end"],

                "val":
                    float(
                        q4_value
                    ),

                "filed":
                    annual["filed"],

                "form":
                    annual["form"],

                "fy":
                    fiscal_year,

                "fp":
                    "Q4",

                "quarter":
                    "Q4",

                "fiscal_year":
                    fiscal_year,

                "duration_days":
                    q4_duration,

                "unit":
                    annual.get(
                        "unit",
                        "USD",
                    ),

                "derived":
                    True,
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# 11. CONSTRUIR SÉRIE TRIMESTRAL
# =============================================================================

def _build_quarterly_series(
    fact: Optional[dict],
    preferred_units: list[str],
    as_of_date=None,
    allow_q4_derivation: bool = False,
) -> pd.DataFrame:
    """
    Constrói série de trimestres comparáveis.
    """

    df = _fact_to_dataframe(
        fact,
        preferred_units,
    )

    df = _filter_financial_forms(
        df
    )

    df = _point_in_time(
        df,
        as_of_date,
    )

    if df.empty:
        return pd.DataFrame()

    direct = (
        _direct_discrete_quarters(
            df
        )
    )

    pieces = []

    if not direct.empty:
        pieces.append(
            direct
        )

    if allow_q4_derivation:

        derived_q4 = (
            _derive_q4_revenue(
                df
            )
        )

        if not derived_q4.empty:
            pieces.append(
                derived_q4
            )

    if not pieces:
        return pd.DataFrame()

    result = pd.concat(
        pieces,
        ignore_index=True,
        sort=False,
    )

    # -------------------------------------------------------------------------
    # Se existe observação direta e reconstruída do mesmo trimestre,
    # preferimos DIRETA.
    # -------------------------------------------------------------------------

    result[
        "_derived_sort"
    ] = result[
        "derived"
    ].astype(int)

    result = (
        result
        .sort_values(
            [
                "fiscal_year",
                "quarter",
                "_derived_sort",
                "filed",
            ],
            ascending=[
                True,
                True,
                True,
                True,
            ],
        )
        .drop_duplicates(
            subset=[
                "fiscal_year",
                "quarter",
            ],
            keep="first",
        )
        .drop(
            columns=[
                "_derived_sort"
            ]
        )
    )

    return (
        result
        .sort_values(
            [
                "end",
                "fiscal_year",
                "quarter",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =============================================================================
# 12. CRESCIMENTO DO MESMO TRIMESTRE
# =============================================================================

def _quarter_yoy(
    quarters: pd.DataFrame,
    fiscal_year: int,
    quarter: str,
) -> tuple[
    float,
    Optional[pd.Timestamp],
    Optional[pd.Timestamp],
]:
    """
    Compara:

    Qx do ano fiscal atual
    contra
    Qx do ano fiscal anterior.
    """

    if quarters.empty:
        return np.nan, None, None

    current = quarters[
        (
            quarters["fiscal_year"]
            ==
            fiscal_year
        )
        &
        (
            quarters["quarter"]
            ==
            quarter
        )
    ]

    previous = quarters[
        (
            quarters["fiscal_year"]
            ==
            fiscal_year - 1
        )
        &
        (
            quarters["quarter"]
            ==
            quarter
        )
    ]

    if (
        current.empty
        or previous.empty
    ):

        return np.nan, None, None

    current = current.iloc[-1]
    previous = previous.iloc[-1]

    current_value = float(
        current["val"]
    )

    previous_value = float(
        previous["val"]
    )

    if (
        not np.isfinite(current_value)
        or
        not np.isfinite(previous_value)
        or
        previous_value == 0
    ):

        return (
            np.nan,
            current["end"],
            current["filed"],
        )

    growth = (
        current_value
        /
        previous_value
        - 1
    )

    return (
        float(growth),
        current["end"],
        current["filed"],
    )


# =============================================================================
# 13. EPS YOY
# =============================================================================

def _eps_quarter_yoy(
    quarters: pd.DataFrame,
    fiscal_year: int,
    quarter: str,
) -> tuple[
    float,
    str,
    Optional[pd.Timestamp],
    Optional[pd.Timestamp],
]:
    """
    Crescimento de EPS apenas quando percentual
    é economicamente interpretável.

    Não converte prejuízo -> lucro artificialmente
    em +100%.
    """

    if quarters.empty:

        return (
            np.nan,
            "SEM_DADOS",
            None,
            None,
        )

    current = quarters[
        (
            quarters["fiscal_year"]
            ==
            fiscal_year
        )
        &
        (
            quarters["quarter"]
            ==
            quarter
        )
    ]

    previous = quarters[
        (
            quarters["fiscal_year"]
            ==
            fiscal_year - 1
        )
        &
        (
            quarters["quarter"]
            ==
            quarter
        )
    ]

    if (
        current.empty
        or previous.empty
    ):

        return (
            np.nan,
            "SEM_COMPARATIVO",
            None,
            None,
        )

    current = current.iloc[-1]
    previous = previous.iloc[-1]

    current_eps = float(
        current["val"]
    )

    previous_eps = float(
        previous["val"]
    )

    # -------------------------------------------------------------------------
    # ambos positivos
    # -------------------------------------------------------------------------

    if (
        previous_eps > 0
        and
        current_eps > 0
    ):

        growth = (
            current_eps
            /
            previous_eps
            - 1
        )

        return (
            float(growth),
            "POSITIVO_CRESCIMENTO",
            current["end"],
            current["filed"],
        )

    # -------------------------------------------------------------------------
    # prejuízo -> lucro
    #
    # É recuperação, mas crescimento percentual
    # não é matematicamente comparável.
    # -------------------------------------------------------------------------

    if (
        previous_eps <= 0
        and
        current_eps > 0
    ):

        return (
            np.nan,
            "RECUPERANDO",
            current["end"],
            current["filed"],
        )

    # -------------------------------------------------------------------------
    # lucro -> prejuízo
    # -------------------------------------------------------------------------

    if (
        previous_eps > 0
        and
        current_eps <= 0
    ):

        return (
            np.nan,
            "DETERIORANDO",
            current["end"],
            current["filed"],
        )

    # -------------------------------------------------------------------------
    # ambos negativos
    # -------------------------------------------------------------------------

    return (
        np.nan,
        "EPS_NEGATIVO",
        current["end"],
        current["filed"],
    )


# =============================================================================
# 14. LOCALIZAR ÚLTIMO TRIMESTRE COMUM
# =============================================================================

def _latest_common_quarter(
    revenue_q: pd.DataFrame,
    eps_q: pd.DataFrame,
    as_of_date=None,
    max_age_days: int = MAX_FUNDAMENTAL_AGE_DAYS,
) -> Optional[tuple[int, str]]:
    """
    Localiza o trimestre fiscal mais recente que seja realmente utilizável.

    Requisitos:
    - receita e EPS pertencem ao MESMO trimestre fiscal;
    - o mesmo trimestre do ano anterior existe para receita;
    - o mesmo trimestre do ano anterior existe para EPS;
    - o período atual não pode estar excessivamente antigo.

    Se não houver trimestre recente e comparável, retorna None.
    """

    if revenue_q.empty or eps_q.empty:
        return None

    if as_of_date is None:
        ref_date = pd.Timestamp.utcnow()
        if ref_date.tzinfo is not None:
            ref_date = ref_date.tz_localize(None)
        ref_date = ref_date.normalize()
    else:
        ref_date = pd.Timestamp(as_of_date)
        if ref_date.tzinfo is not None:
            ref_date = ref_date.tz_localize(None)
        ref_date = ref_date.normalize()

    rev = revenue_q.copy()
    eps = eps_q.copy()

    rev["fiscal_year"] = pd.to_numeric(
        rev["fiscal_year"],
        errors="coerce",
    )
    eps["fiscal_year"] = pd.to_numeric(
        eps["fiscal_year"],
        errors="coerce",
    )

    rev = rev.dropna(subset=["fiscal_year", "quarter", "end"])
    eps = eps.dropna(subset=["fiscal_year", "quarter", "end"])

    if rev.empty or eps.empty:
        return None

    rev["fiscal_year"] = rev["fiscal_year"].astype(int)
    eps["fiscal_year"] = eps["fiscal_year"].astype(int)

    rev_keys = set(zip(rev["fiscal_year"], rev["quarter"]))
    eps_keys = set(zip(eps["fiscal_year"], eps["quarter"]))

    current_common = rev_keys & eps_keys

    candidates = []

    for fiscal_year, quarter in current_common:
        # Exige comparativo do mesmo trimestre no ano fiscal anterior
        prev_key = (int(fiscal_year) - 1, quarter)

        if prev_key not in rev_keys or prev_key not in eps_keys:
            continue

        rev_current = rev[
            (rev["fiscal_year"] == fiscal_year)
            & (rev["quarter"] == quarter)
        ]

        eps_current = eps[
            (eps["fiscal_year"] == fiscal_year)
            & (eps["quarter"] == quarter)
        ]

        if rev_current.empty or eps_current.empty:
            continue

        # Usa o menor end entre receita e EPS para ser conservador
        period_end = min(
            pd.Timestamp(rev_current.iloc[-1]["end"]),
            pd.Timestamp(eps_current.iloc[-1]["end"]),
        )

        age_days = (ref_date - period_end.normalize()).days

        # Não aceita período no futuro nem fundamentos velhos demais
        if age_days < 0 or age_days > max_age_days:
            continue

        # Data de filing mais recente entre os dois componentes
        filed_dates = []
        for frame in (rev_current, eps_current):
            if "filed" in frame.columns and pd.notna(frame.iloc[-1]["filed"]):
                filed_dates.append(pd.Timestamp(frame.iloc[-1]["filed"]))

        latest_filed = max(filed_dates) if filed_dates else pd.Timestamp.min

        candidates.append(
            (
                period_end,
                latest_filed,
                int(fiscal_year),
                str(quarter),
            )
        )

    if not candidates:
        return None

    # Prioridade absoluta para o período econômico mais recente.
    # Filing serve apenas como desempate.
    candidates.sort(key=lambda x: (x[0], x[1]))

    _, _, fiscal_year, quarter = candidates[-1]

    return fiscal_year, quarter


# =============================================================================
# 15. CLASSIFICAÇÃO FUNDAMENTAL
# =============================================================================

def classify_growth(
    revenue_growth: float,
    eps_growth: float,
    eps_state: str,
) -> str:
    """
    CRESCIMENTO_FORTE exige:

    Receita YoY >= mínimo
    +
    EPS YoY positivo e >= mínimo.

    Recuperação de prejuízo para lucro
    NÃO é automaticamente transformada
    em crescimento percentual.
    """

    if pd.isna(
        revenue_growth
    ):

        return "SEM_DADOS"

    if eps_state in {
        "RECUPERANDO",
        "DETERIORANDO",
        "EPS_NEGATIVO",
    }:

        return "NAO_APROVADO"

    if pd.isna(
        eps_growth
    ):

        return "SEM_DADOS"

    if (
        revenue_growth
        >=
        MIN_REVENUE_GROWTH
        and
        eps_growth
        >=
        MIN_EPS_GROWTH
    ):

        return "CRESCIMENTO_FORTE"

    return "NAO_APROVADO"


# =============================================================================
# 16. ANALISAR EMPRESA
# =============================================================================

def analyze_company_fundamentals(
    ticker: str,
    cik: str,
    as_of_date=None,
) -> Optional[dict]:
    """
    Analisa uma empresa usando trimestres
    fiscalmente comparáveis.
    """

    companyfacts = (
        download_company_facts(
            cik=cik,
            ticker=ticker,
        )
    )

    if companyfacts is None:
        return None

    # -------------------------------------------------------------------------
    # RECEITA
    # -------------------------------------------------------------------------

    revenue_fact, revenue_tag = (
        _find_fact(
            companyfacts,
            REVENUE_TAGS,
        )
    )

    revenue_q = (
        _build_quarterly_series(
            revenue_fact,
            preferred_units=[
                "USD",
            ],
            as_of_date=as_of_date,
            allow_q4_derivation=True,
        )
    )

    # -------------------------------------------------------------------------
    # EPS
    # -------------------------------------------------------------------------

    eps_fact, eps_tag = (
        _find_fact(
            companyfacts,
            EPS_TAGS,
        )
    )

    eps_q = (
        _build_quarterly_series(
            eps_fact,
            preferred_units=[
                "USD/shares",
                "USD / shares",
            ],
            as_of_date=as_of_date,
            allow_q4_derivation=False,
        )
    )

    # -------------------------------------------------------------------------
    # MESMO TRIMESTRE PARA RECEITA + EPS
    # -------------------------------------------------------------------------

    common = (
        _latest_common_quarter(
            revenue_q,
            eps_q,
            as_of_date=as_of_date,
        )
    )

    if common is None:

        return {
            "ticker":
                ticker,

            "cik":
                cik,

            "revenue_yoy":
                np.nan,

            "eps_growth_yoy":
                np.nan,

            "eps_state":
                "SEM_DADOS",

            "fiscal_year":
                np.nan,

            "fiscal_quarter":
                None,

            "period_end":
                None,

            "revenue_filed":
                None,

            "eps_filed":
                None,

            "revenue_tag":
                revenue_tag,

            "eps_tag":
                eps_tag,

            "fundamental_age_days":
                np.nan,

            "fundamental_recent":
                False,

            "growth_class":
                "SEM_DADOS",

            "fundamentals_ok":
                False,
        }

    fiscal_year, quarter = common

    # -------------------------------------------------------------------------
    # RECEITA YOY
    # -------------------------------------------------------------------------

    (
        revenue_growth,
        revenue_period,
        revenue_filed,
    ) = _quarter_yoy(
        revenue_q,
        fiscal_year,
        quarter,
    )

    # -------------------------------------------------------------------------
    # EPS YOY
    # -------------------------------------------------------------------------

    (
        eps_growth,
        eps_state,
        eps_period,
        eps_filed,
    ) = _eps_quarter_yoy(
        eps_q,
        fiscal_year,
        quarter,
    )

    # -------------------------------------------------------------------------
    # CLASSIFICAÇÃO
    # -------------------------------------------------------------------------

    classification = (
        classify_growth(
            revenue_growth,
            eps_growth,
            eps_state,
        )
    )

    period_end = None

    periods = [
        x
        for x in [
            revenue_period,
            eps_period,
        ]
        if x is not None
    ]

    if periods:

        period_end = min(
            periods
        )

    if period_end is not None:

        if as_of_date is None:
            ref_date = pd.Timestamp.utcnow()
            if ref_date.tzinfo is not None:
                ref_date = ref_date.tz_localize(None)
            ref_date = ref_date.normalize()
        else:
            ref_date = pd.Timestamp(as_of_date)
            if ref_date.tzinfo is not None:
                ref_date = ref_date.tz_localize(None)
            ref_date = ref_date.normalize()

        fundamental_age_days = (
            ref_date - pd.Timestamp(period_end).normalize()
        ).days

    else:
        fundamental_age_days = np.nan

    fundamental_recent = (
        pd.notna(fundamental_age_days)
        and 0 <= fundamental_age_days <= MAX_FUNDAMENTAL_AGE_DAYS
    )

    # Fail-safe adicional: fundamentos velhos nunca podem ser aprovados.
    if not fundamental_recent:
        classification = "SEM_DADOS"

    return {
        "ticker":
            ticker,

        "cik":
            cik,

        "revenue_yoy":
            revenue_growth,

        "eps_growth_yoy":
            eps_growth,

        "eps_state":
            eps_state,

        "fiscal_year":
            fiscal_year,

        "fiscal_quarter":
            quarter,

        "period_end":
            period_end,

        "revenue_filed":
            revenue_filed,

        "eps_filed":
            eps_filed,

        "revenue_tag":
            revenue_tag,

        "eps_tag":
            eps_tag,

        "fundamental_age_days":
            fundamental_age_days,

        "fundamental_recent":
            bool(fundamental_recent),

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
# 17. ANALISAR UNIVERSO
# =============================================================================

def analyze_fundamentals(
    tickers=None,
    as_of_date=None,
) -> pd.DataFrame:
    """
    Analisa todo o universo.
    """

    if tickers is None:
        tickers = UNIVERSE

    ticker_map = (
        load_sec_ticker_map()
    )

    rows = []

    total = len(
        tickers
    )

    print("=" * 90)
    print(
        "GROWTH OPPORTUNITY ENGINE"
    )
    print(
        "ANÁLISE FUNDAMENTAL — SEC | TRIMESTRES DISCRETOS + RECÊNCIA"
    )
    print("=" * 90)

    for i, ticker in enumerate(
        tickers,
        start=1,
    ):

        ticker = (
            str(ticker)
            .upper()
            .strip()
        )

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
                ticker=ticker,
                cik=cik,
                as_of_date=as_of_date,
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

            period_text = (
                f"{result['fiscal_year']}"
                f"-{result['fiscal_quarter']}"
                if pd.notna(
                    result[
                        "fiscal_year"
                    ]
                )
                else "N/A"
            )

            age = result.get("fundamental_age_days", np.nan)
            age_text = (
                f"{int(age)}d"
                if pd.notna(age)
                else "N/A"
            )

            print(
                f"✅ {period_text} | "
                f"idade {age_text} | "
                f"Receita {rev_text} | "
                f"EPS {eps_text} | "
                f"{result['eps_state']} | "
                f"{result['growth_class']}"
            )

    result_df = pd.DataFrame(
        rows
    )

    print("-" * 90)

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
            ]
            .fillna(False)
            .sum()
        )

        no_data = (
            result_df[
                "growth_class"
            ]
            ==
            "SEM_DADOS"
        ).sum()

        print(
            f"Crescimento forte: "
            f"{approved}"
        )

        print(
            f"Sem dados comparáveis: "
            f"{no_data}"
        )

    print("=" * 90)

    return result_df


# =============================================================================
# 18. TESTE LOCAL
# =============================================================================

if __name__ == "__main__":

    TEST_TICKERS = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "MU",
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

        print(
            "\nRESULTADO FUNDAMENTAL:"
        )

        columns = [
            "ticker",
            "fiscal_year",
            "fiscal_quarter",
            "period_end",
            "revenue_yoy",
            "eps_growth_yoy",
            "eps_state",
            "growth_class",
            "fundamentals_ok",
        ]

        columns = [
            c
            for c in columns
            if c in fundamentals.columns
        ]

        show = fundamentals[
            columns
        ].copy()

        for col in [
            "revenue_yoy",
            "eps_growth_yoy",
        ]:

            if col in show.columns:

                show[col] = (
                    show[col]
                    * 100
                )

        print(
            show.to_string(
                index=False
            )
        )
