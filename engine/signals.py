# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# engine/signals.py
#
# Motor de sinais da estratégia.
#
# Responsabilidades:
# - detectar pullback de 20%-30%
# - calcular máxima anterior
# - calcular Falling Knife Score
# - calcular confirmações
# - preparar dados para strategy.py
#
# NÃO decide ENTRADA_FORTE / PARCIAL / AGUARDAR.
# =============================================================================

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from config import (
    MIN_PULLBACK,
    MAX_PULLBACK,
    FALLING_RULES,
    CONFIRMATION_SMA50_DISTANCE,
    CONFIRMATION_INSTITUTIONAL_SCORE,
    CONFIRMATION_VOLUME_RATIO,
)


# =============================================================================
# 1. DETECÇÃO DE PULLBACK
# =============================================================================

def calculate_pullback(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcula a queda atual em relação à máxima histórica anterior.

    pullback:
    0.20 = queda de 20%
    0.30 = queda de 30%
    """

    data = df.copy()

    # máxima anterior, sem usar o próprio dia
    data["previous_high"] = (
        data["Close"]
        .shift(1)
        .cummax()
    )

    data["pullback"] = (
        1
        -
        (
            data["Close"]
            /
            data["previous_high"]
        )
    )

    return data


# =============================================================================
# 2. ZONA DE OPORTUNIDADE
# =============================================================================

def detect_pullback_zone(
    pullback: float,
) -> bool:
    """
    Retorna True quando a queda está entre 20% e 30%.
    """

    if pd.isna(pullback):
        return False

    return (
        MIN_PULLBACK
        <= pullback
        <= MAX_PULLBACK
    )


# =============================================================================
# 3. FALLING KNIFE SCORE
# =============================================================================

def calculate_falling_score(
    dist_sma50: float,
    ret_5d: float,
    ret_10d: float,
    ret_20d: float,
    close_location: float,
    volume_ratio: float,
) -> int:
    """
    Reproduz as regras da Célula 18D.

    Cada condição verdadeira soma 1 ponto.
    """

    score = 0

    # -------------------------------------------------------------------------
    # SMA50
    # -------------------------------------------------------------------------

    if (
        pd.notna(dist_sma50)
        and
        dist_sma50
        <= FALLING_RULES[
            "DIST_SMA50_10"
        ]
    ):
        score += 1

    if (
        pd.notna(dist_sma50)
        and
        dist_sma50
        <= FALLING_RULES[
            "DIST_SMA50_15"
        ]
    ):
        score += 1

    # -------------------------------------------------------------------------
    # Momentum
    # -------------------------------------------------------------------------

    if (
        pd.notna(ret_5d)
        and
        ret_5d
        <= FALLING_RULES[
            "RETURN_5D"
        ]
    ):
        score += 1

    if (
        pd.notna(ret_10d)
        and
        ret_10d
        <= FALLING_RULES[
            "RETURN_10D"
        ]
    ):
        score += 1

    if (
        pd.notna(ret_20d)
        and
        ret_20d
        <= FALLING_RULES[
            "RETURN_20D"
        ]
    ):
        score += 1

    # -------------------------------------------------------------------------
    # Fechamento perto da mínima
    # -------------------------------------------------------------------------

    if (
        pd.notna(close_location)
        and
        close_location
        <= FALLING_RULES[
            "CLOSE_LOCATION"
        ]
    ):
        score += 1

    # -------------------------------------------------------------------------
    # Volume relativo fraco
    # -------------------------------------------------------------------------

    if (
        pd.notna(volume_ratio)
        and
        volume_ratio
        <
        FALLING_RULES[
            "VOLUME_RELATIVE_LOW"
        ]
    ):
        score += 1

    return score


# =============================================================================
# 4. CLASSIFICAÇÃO DO RISCO
# =============================================================================

def classify_falling_risk(
    score: int,
) -> str:
    """
    Classificação simples do Falling Score.
    """

    if score <= 1:
        return "BAIXO"

    elif score == 2:
        return "MODERADO"

    return "ALTO"


# =============================================================================
# 5. CONFIRMAÇÕES
# =============================================================================

def calculate_confirmations(
    dist_sma50: float,
    institutional_score: float,
    volume_ratio: float,
) -> Dict[str, object]:
    """
    Calcula as três confirmações da estratégia.
    """

    conf_sma50 = (
        pd.notna(dist_sma50)
        and
        dist_sma50
        >= CONFIRMATION_SMA50_DISTANCE
    )

    conf_institutional = (
        pd.notna(institutional_score)
        and
        institutional_score
        >= CONFIRMATION_INSTITUTIONAL_SCORE
    )

    conf_volume = (
        pd.notna(volume_ratio)
        and
        volume_ratio
        >= CONFIRMATION_VOLUME_RATIO
    )

    total = int(
        conf_sma50
    ) + int(
        conf_institutional
    ) + int(
        conf_volume
    )

    return {
        "confirmation_sma50":
            conf_sma50,

        "confirmation_institutional":
            conf_institutional,

        "confirmation_volume":
            conf_volume,

        "confirmations_total":
            total,
    }


# =============================================================================
# 6. SNAPSHOT DE SINAL
# =============================================================================

def build_signal_snapshot(
    market_snapshot: pd.DataFrame,
    institutional_scores: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Recebe snapshot de mercado produzido por data.py
    e adiciona sinais da estratégia.

    institutional_scores deve conter:
    ticker
    institutional_score
    """

    if market_snapshot.empty:
        return pd.DataFrame()

    df = market_snapshot.copy()

    # -------------------------------------------------------------------------
    # Smart Money
    # -------------------------------------------------------------------------

    if (
        institutional_scores is not None
        and
        not institutional_scores.empty
    ):

        scores = (
            institutional_scores[
                [
                    "ticker",
                    "institutional_score",
                ]
            ]
            .drop_duplicates(
                subset="ticker",
                keep="last",
            )
        )

        df = df.merge(
            scores,
            on="ticker",
            how="left",
        )

    else:

        df[
            "institutional_score"
        ] = np.nan

    # -------------------------------------------------------------------------
    # FALLING SCORE
    # -------------------------------------------------------------------------

    df[
        "falling_score"
    ] = df.apply(
        lambda row:
            calculate_falling_score(
                dist_sma50=row[
                    "dist_sma50"
                ],
                ret_5d=row[
                    "ret_5d"
                ],
                ret_10d=row[
                    "ret_10d"
                ],
                ret_20d=row[
                    "ret_20d"
                ],
                close_location=row[
                    "close_location"
                ],
                volume_ratio=row[
                    "volume_ratio"
                ],
            ),
        axis=1,
    )

    df[
        "falling_risk"
    ] = df[
        "falling_score"
    ].apply(
        classify_falling_risk
    )

    # -------------------------------------------------------------------------
    # CONFIRMAÇÕES
    # -------------------------------------------------------------------------

    confirmations = df.apply(
        lambda row:
            calculate_confirmations(
                dist_sma50=row[
                    "dist_sma50"
                ],
                institutional_score=row[
                    "institutional_score"
                ],
                volume_ratio=row[
                    "volume_ratio"
                ],
            ),
        axis=1,
        result_type="expand",
    )

    df = pd.concat(
        [
            df.reset_index(
                drop=True
            ),
            confirmations.reset_index(
                drop=True
            ),
        ],
        axis=1,
    )

    return df


# =============================================================================
# 7. SNAPSHOT COMPLETO COM PULLBACK
# =============================================================================

def build_full_signal_table(
    market_data: Dict[
        str,
        pd.DataFrame,
    ],
    institutional_scores: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Usa o histórico de mercado completo
    para calcular o pullback atual de cada ticker.

    Retorna uma linha por ticker.
    """

    rows = []

    for ticker, raw_df in market_data.items():

        if raw_df is None or raw_df.empty:
            continue

        df = calculate_pullback(
            raw_df
        )

        # linhas completas necessárias
        required = [
            "Close",
            "sma50",
            "dist_sma50",
            "ret_5d",
            "ret_10d",
            "ret_20d",
            "volume_ratio",
            "close_location",
            "pullback",
        ]

        valid = df.dropna(
            subset=required
        )

        if valid.empty:
            continue

        row = valid.iloc[-1]

        rows.append(
            {
                "ticker":
                    ticker,

                "date":
                    valid.index[-1],

                "close":
                    float(
                        row["Close"]
                    ),

                "previous_high":
                    float(
                        row[
                            "previous_high"
                        ]
                    ),

                "pullback":
                    float(
                        row["pullback"]
                    ),

                "pullback_zone":
                    detect_pullback_zone(
                        row["pullback"]
                    ),

                "sma50":
                    float(
                        row["sma50"]
                    ),

                "dist_sma50":
                    float(
                        row["dist_sma50"]
                    ),

                "ret_5d":
                    float(
                        row["ret_5d"]
                    ),

                "ret_10d":
                    float(
                        row["ret_10d"]
                    ),

                "ret_20d":
                    float(
                        row["ret_20d"]
                    ),

                "volume_ratio":
                    float(
                        row["volume_ratio"]
                    ),

                "close_location":
                    float(
                        row[
                            "close_location"
                        ]
                    ),

                "cross_sma50":
                    bool(
                        row.get(
                            "cross_sma50",
                            False,
                        )
                    ),
            }
        )

    if not rows:
        return pd.DataFrame()

    market_snapshot = pd.DataFrame(
        rows
    )

    return build_signal_snapshot(
        market_snapshot,
        institutional_scores,
    )


# =============================================================================
# 8. FILTRO DE OPORTUNIDADES
# =============================================================================

def filter_pullback_candidates(
    signal_table: pd.DataFrame,
) -> pd.DataFrame:
    """
    Mantém somente empresas na zona de queda
    validada pelo estudo: 20%-30%.
    """

    if signal_table.empty:
        return signal_table

    candidates = signal_table[
        signal_table[
            "pullback_zone"
        ] == True
    ].copy()

    return (
        candidates
        .sort_values(
            [
                "falling_score",
                "pullback",
            ],
            ascending=[
                True,
                False,
            ],
        )
        .reset_index(
            drop=True
        )
    )


# =============================================================================
# 9. TESTE LOCAL
# =============================================================================

if __name__ == "__main__":

    from engine.data import (
        download_market_data,
    )

    test_tickers = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMD",
        "AMZN",
    ]

    market_data = (
        download_market_data(
            test_tickers
        )
    )

    signals = (
        build_full_signal_table(
            market_data
        )
    )

    print("\n" + "=" * 100)
    print("SINAIS")
    print("=" * 100)

    if signals.empty:

        print(
            "Nenhum sinal disponível."
        )

    else:

        show_columns = [
            "ticker",
            "date",
            "close",
            "pullback",
            "pullback_zone",
            "falling_score",
            "falling_risk",
            "dist_sma50",
            "volume_ratio",
            "confirmations_total",
            "cross_sma50",
        ]

        output = signals[
            show_columns
        ].copy()

        output[
            "pullback"
        ] *= 100

        output[
            "dist_sma50"
        ] *= 100

        print(
            output.to_string(
                index=False
            )
        )
