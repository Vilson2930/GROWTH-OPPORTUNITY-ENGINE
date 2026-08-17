# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# engine/strategy.py
#
# Motor decisório final.
#
# Responsabilidades:
# - juntar fundamentos + sinais
# - exigir crescimento fundamental
# - exigir pullback de 20%-30%
# - aplicar Falling Score
# - aplicar confirmações
# - classificar:
#
#   ENTRADA_FORTE
#   ENTRADA_PARCIAL
#   AGUARDAR
#
# - definir tamanho da posição
#
# NÃO coleta dados.
# NÃO recalcula indicadores.
# =============================================================================

from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    SIGNAL_STRONG,
    SIGNAL_PARTIAL,
    SIGNAL_WAIT,
    STRONG_INITIAL_WEIGHT,
    PARTIAL_INITIAL_WEIGHT,
    PARTIAL_CONFIRMATION_WEIGHT,
    WAIT_INITIAL_WEIGHT,
    FALLING_LOW_MAX,
    FALLING_MODERATE,
    FALLING_HIGH_MIN,
    MIN_CONFIRMATIONS_HIGH_RISK,
    SECOND_ENTRY_TRIGGER,
    KEEP_UNCONFIRMED_CAPITAL_IN_CASH,
)


# =============================================================================
# 1. DECISÃO OPERACIONAL
# =============================================================================

def classify_signal(
    fundamentals_ok: bool,
    pullback_zone: bool,
    falling_score: int,
    confirmations_total: int,
) -> str:
    """
    Aplica a regra final congelada do estudo.

    Regras:

    1. Sem fundamentos aprovados:
       AGUARDAR

    2. Fora da zona de queda 20%-30%:
       AGUARDAR

    3. Falling <= 1:
       ENTRADA_FORTE

    4. Falling == 2:
       ENTRADA_PARCIAL

    5. Falling >= 3 + pelo menos 2 confirmações:
       ENTRADA_PARCIAL

    6. Falling >= 3 sem confirmações suficientes:
       AGUARDAR
    """

    if not bool(fundamentals_ok):
        return SIGNAL_WAIT

    if not bool(pullback_zone):
        return SIGNAL_WAIT

    if pd.isna(falling_score):
        return SIGNAL_WAIT

    if falling_score <= FALLING_LOW_MAX:
        return SIGNAL_STRONG

    if falling_score == FALLING_MODERATE:
        return SIGNAL_PARTIAL

    if (
        falling_score >= FALLING_HIGH_MIN
        and
        confirmations_total
        >= MIN_CONFIRMATIONS_HIGH_RISK
    ):
        return SIGNAL_PARTIAL

    return SIGNAL_WAIT


# =============================================================================
# 2. TAMANHO DA POSIÇÃO
# =============================================================================

def position_plan(
    signal: str,
) -> dict:
    """
    Define o tamanho da posição conforme
    a classificação operacional.
    """

    if signal == SIGNAL_STRONG:

        return {
            "initial_weight":
                STRONG_INITIAL_WEIGHT,

            "confirmation_weight":
                0.0,

            "cash_weight":
                0.0,

            "needs_confirmation":
                False,

            "confirmation_trigger":
                None,
        }

    if signal == SIGNAL_PARTIAL:

        return {
            "initial_weight":
                PARTIAL_INITIAL_WEIGHT,

            "confirmation_weight":
                PARTIAL_CONFIRMATION_WEIGHT,

            "cash_weight":
                PARTIAL_CONFIRMATION_WEIGHT,

            "needs_confirmation":
                True,

            "confirmation_trigger":
                SECOND_ENTRY_TRIGGER,
        }

    return {
        "initial_weight":
            WAIT_INITIAL_WEIGHT,

        "confirmation_weight":
            0.0,

        "cash_weight":
            1.0,

        "needs_confirmation":
            False,

        "confirmation_trigger":
            None,
    }


# =============================================================================
# 3. JUSTIFICATIVA DA DECISÃO
# =============================================================================

def build_reason(
    row: pd.Series,
) -> str:
    """
    Gera justificativa simples e auditável.
    """

    signal = row["signal"]

    falling = row.get(
        "falling_score",
        np.nan,
    )

    confirmations = row.get(
        "confirmations_total",
        0,
    )

    pullback = row.get(
        "pullback",
        np.nan,
    )

    growth = row.get(
        "fundamentals_ok",
        False,
    )

    reasons = []

    # -------------------------------------------------------------------------
    # Fundamentos
    # -------------------------------------------------------------------------

    if growth:
        reasons.append(
            "fundamentos aprovados"
        )

    else:
        reasons.append(
            "fundamentos não aprovados"
        )

    # -------------------------------------------------------------------------
    # Pullback
    # -------------------------------------------------------------------------

    if pd.notna(pullback):

        reasons.append(
            f"queda {pullback*100:.1f}%"
        )

    # -------------------------------------------------------------------------
    # Falling
    # -------------------------------------------------------------------------

    if pd.notna(falling):

        reasons.append(
            f"Falling Score {int(falling)}"
        )

    # -------------------------------------------------------------------------
    # Confirmações
    # -------------------------------------------------------------------------

    reasons.append(
        f"{int(confirmations)} confirmações"
    )

    # -------------------------------------------------------------------------
    # Decisão
    # -------------------------------------------------------------------------

    if signal == SIGNAL_STRONG:

        reasons.append(
            "queda estabilizada"
        )

    elif signal == SIGNAL_PARTIAL:

        reasons.append(
            "entrada escalonada por risco"
        )

    else:

        reasons.append(
            "condições insuficientes para entrada"
        )

    return " | ".join(
        reasons
    )


# =============================================================================
# 4. JUNTAR FUNDAMENTOS E SINAIS
# =============================================================================

def merge_strategy_inputs(
    signal_table: pd.DataFrame,
    fundamentals: pd.DataFrame,
) -> pd.DataFrame:
    """
    Junta sinais de mercado e fundamentos.
    """

    if signal_table is None or signal_table.empty:
        return pd.DataFrame()

    df = signal_table.copy()

    if fundamentals is None or fundamentals.empty:

        df["revenue_yoy"] = np.nan
        df["eps_growth_yoy"] = np.nan
        df["growth_class"] = "SEM_DADOS"
        df["fundamentals_ok"] = False

        return df

    fundamental_columns = [
        "ticker",
        "revenue_yoy",
        "eps_growth_yoy",
        "growth_class",
        "fundamentals_ok",
    ]

    available_columns = [
        col
        for col in fundamental_columns
        if col in fundamentals.columns
    ]

    fund = (
        fundamentals[
            available_columns
        ]
        .drop_duplicates(
            subset="ticker",
            keep="last",
        )
    )

    df = df.merge(
        fund,
        on="ticker",
        how="left",
    )

    df["fundamentals_ok"] = (
        df["fundamentals_ok"]
        .fillna(False)
        .astype(bool)
    )

    return df


# =============================================================================
# 5. APLICAR ESTRATÉGIA
# =============================================================================

def apply_strategy(
    signal_table: pd.DataFrame,
    fundamentals: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aplica toda a regra operacional final.
    """

    df = merge_strategy_inputs(
        signal_table,
        fundamentals,
    )

    if df.empty:
        return df

    # -------------------------------------------------------------------------
    # GARANTIR COLUNAS
    # -------------------------------------------------------------------------

    required_defaults = {
        "pullback_zone": False,
        "falling_score": np.nan,
        "confirmations_total": 0,
        "confirmation_sma50": False,
        "confirmation_institutional": False,
        "confirmation_volume": False,
        "cross_sma50": False,
    }

    for column, default in required_defaults.items():

        if column not in df.columns:
            df[column] = default

    # -------------------------------------------------------------------------
    # DECISÃO
    # -------------------------------------------------------------------------

    df["signal"] = df.apply(
        lambda row:
            classify_signal(
                fundamentals_ok=row[
                    "fundamentals_ok"
                ],
                pullback_zone=row[
                    "pullback_zone"
                ],
                falling_score=row[
                    "falling_score"
                ],
                confirmations_total=row[
                    "confirmations_total"
                ],
            ),
        axis=1,
    )

    # -------------------------------------------------------------------------
    # PLANO DE POSIÇÃO
    # -------------------------------------------------------------------------

    position_rows = df[
        "signal"
    ].apply(
        position_plan
    )

    position_df = pd.DataFrame(
        position_rows.tolist()
    )

    df = pd.concat(
        [
            df.reset_index(
                drop=True
            ),
            position_df.reset_index(
                drop=True
            ),
        ],
        axis=1,
    )

    # -------------------------------------------------------------------------
    # SEGUNDA PERNA
    # -------------------------------------------------------------------------

    df[
        "confirmation_executed"
    ] = (
        (
            df["signal"]
            ==
            SIGNAL_PARTIAL
        )
        &
        (
            df["cross_sma50"]
            ==
            True
        )
    )

    # -------------------------------------------------------------------------
    # CAPITAL EFETIVAMENTE LIBERADO
    # -------------------------------------------------------------------------

    df[
        "effective_weight"
    ] = df[
        "initial_weight"
    ]

    df.loc[
        df[
            "confirmation_executed"
        ],
        "effective_weight",
    ] += df.loc[
        df[
            "confirmation_executed"
        ],
        "confirmation_weight",
    ]

    # -------------------------------------------------------------------------
    # CAPITAL EM CAIXA
    # -------------------------------------------------------------------------

    if KEEP_UNCONFIRMED_CAPITAL_IN_CASH:

        df[
            "current_cash_weight"
        ] = (
            1.0
            -
            df[
                "effective_weight"
            ]
        )

    else:

        df[
            "current_cash_weight"
        ] = 0.0

    # -------------------------------------------------------------------------
    # JUSTIFICATIVA
    # -------------------------------------------------------------------------

    df[
        "reason"
    ] = df.apply(
        build_reason,
        axis=1,
    )

    return df


# =============================================================================
# 6. PRIORIDADE DAS OPORTUNIDADES
#
# Não cria score novo.
#
# Apenas ordena:
# 1. ENTRADA_FORTE
# 2. ENTRADA_PARCIAL
# 3. AGUARDAR
#
# Dentro da classe:
# menor Falling Score primeiro.
# =============================================================================

def rank_opportunities(
    strategy_table: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ordenação operacional, sem novo score composto.
    """

    if strategy_table.empty:
        return strategy_table

    df = strategy_table.copy()

    priority = {
        SIGNAL_STRONG: 1,
        SIGNAL_PARTIAL: 2,
        SIGNAL_WAIT: 3,
    }

    df[
        "_priority"
    ] = df[
        "signal"
    ].map(
        priority
    )

    df = df.sort_values(
        [
            "_priority",
            "falling_score",
            "confirmations_total",
            "pullback",
        ],
        ascending=[
            True,
            True,
            False,
            False,
        ],
    )

    return (
        df.drop(
            columns="_priority"
        )
        .reset_index(
            drop=True
        )
    )


# =============================================================================
# 7. RESUMO
# =============================================================================

def strategy_summary(
    strategy_table: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resumo das classificações atuais.
    """

    if strategy_table.empty:
        return pd.DataFrame()

    summary = (
        strategy_table
        .groupby(
            "signal"
        )
        .agg(
            empresas=(
                "ticker",
                "nunique",
            ),

            falling_mediano=(
                "falling_score",
                "median",
            ),

            confirmacoes_mediana=(
                "confirmations_total",
                "median",
            ),

            pullback_mediano=(
                "pullback",
                "median",
            ),

            peso_inicial_mediano=(
                "initial_weight",
                "median",
            ),
        )
        .reset_index()
    )

    return summary


# =============================================================================
# 8. TESTE LOCAL
# =============================================================================

if __name__ == "__main__":

    # -------------------------------------------------------------------------
    # Dados simulados apenas para testar lógica.
    # -------------------------------------------------------------------------

    signals_test = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "pullback": 0.22,
                "pullback_zone": True,
                "falling_score": 1,
                "confirmations_total": 1,
                "cross_sma50": False,
            },

            {
                "ticker": "BBB",
                "pullback": 0.25,
                "pullback_zone": True,
                "falling_score": 2,
                "confirmations_total": 1,
                "cross_sma50": False,
            },

            {
                "ticker": "CCC",
                "pullback": 0.27,
                "pullback_zone": True,
                "falling_score": 5,
                "confirmations_total": 2,
                "cross_sma50": False,
            },

            {
                "ticker": "DDD",
                "pullback": 0.24,
                "pullback_zone": True,
                "falling_score": 5,
                "confirmations_total": 1,
                "cross_sma50": False,
            },
        ]
    )

    fundamentals_test = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "revenue_yoy": 0.20,
                "eps_growth_yoy": 0.30,
                "growth_class":
                    "CRESCIMENTO_FORTE",
                "fundamentals_ok": True,
            },

            {
                "ticker": "BBB",
                "revenue_yoy": 0.18,
                "eps_growth_yoy": 0.25,
                "growth_class":
                    "CRESCIMENTO_FORTE",
                "fundamentals_ok": True,
            },

            {
                "ticker": "CCC",
                "revenue_yoy": 0.30,
                "eps_growth_yoy": 0.50,
                "growth_class":
                    "CRESCIMENTO_FORTE",
                "fundamentals_ok": True,
            },

            {
                "ticker": "DDD",
                "revenue_yoy": 0.25,
                "eps_growth_yoy": 0.40,
                "growth_class":
                    "CRESCIMENTO_FORTE",
                "fundamentals_ok": True,
            },
        ]
    )

    result = apply_strategy(
        signals_test,
        fundamentals_test,
    )

    result = rank_opportunities(
        result
    )

    print("=" * 100)
    print("TESTE STRATEGY ENGINE")
    print("=" * 100)

    print(
        result[
            [
                "ticker",
                "pullback",
                "falling_score",
                "confirmations_total",
                "signal",
                "initial_weight",
                "confirmation_weight",
                "reason",
            ]
        ].to_string(
            index=False
        )
    )
