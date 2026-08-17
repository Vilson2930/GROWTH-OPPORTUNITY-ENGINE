# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# engine/institutional.py
#
# Smart Money / Institutional Confirmation Engine
#
# Objetivo:
# gerar um Institutional Score simples, auditável e baseado
# apenas em dados disponíveis até o momento atual.
#
# O score é usado como CONFIRMAÇÃO.
# NÃO é filtro eliminatório.
# =============================================================================

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


# =============================================================================
# 1. INDICADORES INSTITUCIONAIS
#
# A lógica segue a linha validada no estudo:
#
# - volume acima da média
# - acumulação
# - OBV
# - divergência
# - reversão
#
# Cada sinal verdadeiro soma +1.
# =============================================================================


def _calculate_obv(df: pd.DataFrame) -> pd.Series:
    """
    On Balance Volume.
    """

    direction = np.sign(
        df["Close"].diff()
    )

    direction = direction.fillna(0)

    obv = (
        direction
        *
        df["Volume"]
    ).cumsum()

    return obv


# =============================================================================
# 2. PREPARAR HISTÓRICO
# =============================================================================

def add_institutional_indicators(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Adiciona indicadores institucionais ao histórico.
    """

    data = df.copy()

    # -------------------------------------------------------------------------
    # VOLUME RELATIVO
    # -------------------------------------------------------------------------

    volume_mean_20 = (
        data["Volume"]
        .shift(1)
        .rolling(
            20,
            min_periods=20,
        )
        .mean()
    )

    data[
        "inst_volume_ratio"
    ] = (
        data["Volume"]
        /
        volume_mean_20
    )

    # -------------------------------------------------------------------------
    # OBV
    # -------------------------------------------------------------------------

    data[
        "obv"
    ] = _calculate_obv(
        data
    )

    data[
        "obv_ma20"
    ] = (
        data["obv"]
        .rolling(
            20,
            min_periods=20,
        )
        .mean()
    )

    # -------------------------------------------------------------------------
    # RETORNOS
    # -------------------------------------------------------------------------

    data[
        "ret_5d_inst"
    ] = (
        data["Close"]
        .pct_change(
            5,
            fill_method=None,
        )
    )

    data[
        "ret_20d_inst"
    ] = (
        data["Close"]
        .pct_change(
            20,
            fill_method=None,
        )
    )

    # -------------------------------------------------------------------------
    # CLOSE LOCATION
    # -------------------------------------------------------------------------

    candle_range = (
        data["High"]
        -
        data["Low"]
    )

    data[
        "inst_close_location"
    ] = np.where(
        candle_range > 0,
        (
            data["Close"]
            -
            data["Low"]
        )
        /
        candle_range,
        0.5,
    )

    # -------------------------------------------------------------------------
    # ACUMULAÇÃO
    #
    # Dia de acumulação:
    # fechamento positivo + volume acima da média.
    # -------------------------------------------------------------------------

    data[
        "accumulation_day"
    ] = (
        (
            data["Close"]
            >
            data["Close"].shift(1)
        )
        &
        (
            data["inst_volume_ratio"]
            >= 1.20
        )
    )

    data[
        "accumulation_days_10"
    ] = (
        data[
            "accumulation_day"
        ]
        .rolling(
            10,
            min_periods=1,
        )
        .sum()
    )

    return data


# =============================================================================
# 3. SINAIS
# =============================================================================

def calculate_institutional_signals(
    row: pd.Series,
) -> Dict[str, object]:
    """
    Calcula sinais institucionais para o último pregão.
    """

    volume_ratio = row.get(
        "inst_volume_ratio",
        np.nan,
    )

    accumulation_days = row.get(
        "accumulation_days_10",
        np.nan,
    )

    obv = row.get(
        "obv",
        np.nan,
    )

    obv_ma20 = row.get(
        "obv_ma20",
        np.nan,
    )

    ret5 = row.get(
        "ret_5d_inst",
        np.nan,
    )

    ret20 = row.get(
        "ret_20d_inst",
        np.nan,
    )

    close_location = row.get(
        "inst_close_location",
        np.nan,
    )

    # -------------------------------------------------------------------------
    # 1. VOLUME
    # -------------------------------------------------------------------------

    signal_volume = (
        pd.notna(volume_ratio)
        and
        volume_ratio >= 1.30
    )

    # -------------------------------------------------------------------------
    # 2. ACUMULAÇÃO
    # -------------------------------------------------------------------------

    signal_accumulation = (
        pd.notna(accumulation_days)
        and
        accumulation_days >= 2
    )

    # -------------------------------------------------------------------------
    # 3. OBV
    # -------------------------------------------------------------------------

    signal_obv = (
        pd.notna(obv)
        and
        pd.notna(obv_ma20)
        and
        obv > obv_ma20
    )

    # -------------------------------------------------------------------------
    # 4. DIVERGÊNCIA
    #
    # preço caiu em 20d, mas OBV está acima da média.
    # -------------------------------------------------------------------------

    signal_divergence = (
        pd.notna(ret20)
        and
        ret20 < 0
        and
        signal_obv
    )

    # -------------------------------------------------------------------------
    # 5. REVERSÃO
    #
    # curto prazo positivo após queda de 20d,
    # fechando na metade superior do candle.
    # -------------------------------------------------------------------------

    signal_reversal = (
        pd.notna(ret5)
        and
        pd.notna(ret20)
        and
        pd.notna(close_location)
        and
        ret20 < 0
        and
        ret5 > 0
        and
        close_location >= 0.60
    )

    score = sum(
        [
            int(signal_volume),
            int(signal_accumulation),
            int(signal_obv),
            int(signal_divergence),
            int(signal_reversal),
        ]
    )

    return {
        "signal_volume":
            signal_volume,

        "signal_accumulation":
            signal_accumulation,

        "signal_obv":
            signal_obv,

        "signal_divergence":
            signal_divergence,

        "signal_reversal":
            signal_reversal,

        "institutional_score":
            int(score),
    }


# =============================================================================
# 4. ANALISAR EMPRESA
# =============================================================================

def analyze_ticker_institutional(
    df: pd.DataFrame,
) -> dict | None:
    """
    Analisa somente o último pregão válido.
    """

    if df is None or df.empty:
        return None

    data = add_institutional_indicators(
        df
    )

    required = [
        "inst_volume_ratio",
        "obv",
        "obv_ma20",
        "ret_5d_inst",
        "ret_20d_inst",
        "inst_close_location",
    ]

    valid = data.dropna(
        subset=required
    )

    if valid.empty:
        return None

    row = valid.iloc[-1]

    signals = (
        calculate_institutional_signals(
            row
        )
    )

    return {
        "date":
            valid.index[-1],

        "institutional_score":
            signals[
                "institutional_score"
            ],

        "signal_volume":
            signals[
                "signal_volume"
            ],

        "signal_accumulation":
            signals[
                "signal_accumulation"
            ],

        "signal_obv":
            signals[
                "signal_obv"
            ],

        "signal_divergence":
            signals[
                "signal_divergence"
            ],

        "signal_reversal":
            signals[
                "signal_reversal"
            ],

        "institutional_volume_ratio":
            float(
                row[
                    "inst_volume_ratio"
                ]
            ),

        "accumulation_days_10":
            float(
                row[
                    "accumulation_days_10"
                ]
            ),
    }


# =============================================================================
# 5. ANALISAR UNIVERSO
# =============================================================================

def analyze_institutional(
    market_data: Dict[
        str,
        pd.DataFrame,
    ],
) -> pd.DataFrame:
    """
    Analisa Smart Money em todo o universo.
    """

    rows = []

    print("=" * 80)
    print(
        "GROWTH OPPORTUNITY ENGINE"
    )
    print(
        "SMART MONEY / INSTITUCIONAL"
    )
    print("=" * 80)

    total = len(
        market_data
    )

    for i, (
        ticker,
        df,
    ) in enumerate(
        market_data.items(),
        start=1,
    ):

        result = (
            analyze_ticker_institutional(
                df
            )
        )

        if result is None:

            print(
                f"[{i:>3}/{total}] "
                f"{ticker:<8} ❌"
            )

            continue

        result[
            "ticker"
        ] = ticker

        rows.append(
            result
        )

        print(
            f"[{i:>3}/{total}] "
            f"{ticker:<8} "
            f"Score {result['institutional_score']}"
        )

    result_df = pd.DataFrame(
        rows
    )

    if not result_df.empty:

        columns_order = [
            "ticker",
            "date",
            "institutional_score",
            "signal_volume",
            "signal_accumulation",
            "signal_obv",
            "signal_divergence",
            "signal_reversal",
            "institutional_volume_ratio",
            "accumulation_days_10",
        ]

        result_df = result_df[
            columns_order
        ]

    print("-" * 80)

    print(
        f"Empresas analisadas: "
        f"{len(result_df)}"
    )

    if not result_df.empty:

        confirmed = (
            result_df[
                "institutional_score"
            ] >= 2
        ).sum()

        print(
            f"Score institucional >=2: "
            f"{confirmed}"
        )

    print("=" * 80)

    return result_df


# =============================================================================
# 6. TESTE LOCAL
# =============================================================================

if __name__ == "__main__":

    from engine.data import (
        download_market_data,
    )

    test_tickers = [
        "NVDA",
        "AMD",
        "MSFT",
        "AMZN",
    ]

    market = (
        download_market_data(
            test_tickers
        )
    )

    institutional = (
        analyze_institutional(
            market
        )
    )

    if institutional.empty:

        print(
            "Nenhum resultado institucional."
        )

    else:

        print(
            institutional.to_string(
                index=False
            )
        )
