# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# engine/institutional.py
#
# Smart Money / Institutional Confirmation Engine
#
# Reprodução fiel da CÉLULA 12 do estudo.
#
# Sinais:
# 1. Volume anormal
# 2. Absorção
# 3. Acumulação
# 4. OBV
# 5. Divergência preço/volume
# 6. Reversão curta
#
# O Institutional Score é usado como CONFIRMAÇÃO.
# NÃO é filtro eliminatório.
# =============================================================================

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


# =============================================================================
# 1. PREPARAR INDICADORES
# =============================================================================

def add_institutional_indicators(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Reproduz os indicadores utilizados na Célula 12.
    """

    data = df.copy()

    # -------------------------------------------------------------------------
    # Preço utilizado
    #
    # data.py já utiliza preços ajustados via auto_adjust=True.
    # Portanto Close é o equivalente operacional ao PX do estudo.
    # -------------------------------------------------------------------------

    data["PX"] = data["Close"]

    # -------------------------------------------------------------------------
    # RETORNO 1D
    # -------------------------------------------------------------------------

    data["ret_1d"] = (
        data["PX"]
        .pct_change(
            fill_method=None
        )
    )

    # -------------------------------------------------------------------------
    # VOLUME MÉDIO 20
    #
    # IMPORTANTE:
    # A célula 12 original incluía o próprio dia na média.
    # Mantemos exatamente essa lógica.
    # -------------------------------------------------------------------------

    data["vol_med_20"] = (
        data["Volume"]
        .rolling(
            20,
            min_periods=20,
        )
        .mean()
    )

    data["vol_ratio"] = (
        data["Volume"]
        /
        data["vol_med_20"]
    )

    # -------------------------------------------------------------------------
    # DOLLAR VOLUME
    # Mantido por equivalência com o estudo.
    # -------------------------------------------------------------------------

    data["dollar_volume"] = (
        data["Close"]
        *
        data["Volume"]
    )

    data["dollar_vol_med20"] = (
        data["dollar_volume"]
        .rolling(
            20,
            min_periods=20,
        )
        .mean()
    )

    # -------------------------------------------------------------------------
    # CLOSE LOCATION
    # -------------------------------------------------------------------------

    amplitude = (
        data["High"]
        -
        data["Low"]
    ).replace(
        0,
        np.nan,
    )

    data["close_location_inst"] = (
        (
            data["Close"]
            -
            data["Low"]
        )
        /
        amplitude
    )

    # -------------------------------------------------------------------------
    # OBV
    # -------------------------------------------------------------------------

    direction = np.sign(
        data["PX"].diff()
    ).fillna(0)

    data["OBV"] = (
        direction
        *
        data["Volume"]
    ).cumsum()

    data["OBV_MA20"] = (
        data["OBV"]
        .rolling(
            20,
            min_periods=20,
        )
        .mean()
    )

    # -------------------------------------------------------------------------
    # SMA20 / SMA50
    # -------------------------------------------------------------------------

    data["SMA20_INST"] = (
        data["PX"]
        .rolling(
            20,
            min_periods=20,
        )
        .mean()
    )

    data["SMA50_INST"] = (
        data["PX"]
        .rolling(
            50,
            min_periods=50,
        )
        .mean()
    )

    # -------------------------------------------------------------------------
    # RETORNOS
    # -------------------------------------------------------------------------

    data["ret_5d_inst"] = (
        data["PX"]
        .pct_change(
            5,
            fill_method=None,
        )
    )

    data["ret_20d_inst"] = (
        data["PX"]
        .pct_change(
            20,
            fill_method=None,
        )
    )

    return data


# =============================================================================
# 2. CALCULAR SINAIS — CÉLULA 12
# =============================================================================

def calculate_institutional_signals(
    hist: pd.DataFrame,
) -> Dict[str, object]:
    """
    Calcula os 6 sinais usando somente
    informações existentes até o último dia de hist.
    """

    if hist is None or len(hist) < 60:

        return {
            "institutional_score": np.nan,
            "institutional_class": "SEM_DADOS",
        }

    atual = hist.iloc[-1]

    ult10 = hist.tail(10)

    volume_ratio = atual[
        "vol_ratio"
    ]

    close_location = atual[
        "close_location_inst"
    ]

    # =========================================================================
    # SINAL 1 — VOLUME ANORMAL
    # =========================================================================

    sinal_volume = (
        pd.notna(volume_ratio)
        and
        volume_ratio >= 1.30
    )

    # =========================================================================
    # SINAL 2 — ABSORÇÃO
    #
    # Volume >= 1,20x
    # +
    # fechamento na parte superior do candle.
    # =========================================================================

    sinal_absorcao = (
        pd.notna(volume_ratio)
        and
        volume_ratio >= 1.20
        and
        pd.notna(close_location)
        and
        close_location >= 0.60
    )

    # =========================================================================
    # SINAL 3 — ACUMULAÇÃO
    #
    # Nos últimos 10 pregões:
    # retorno positivo + volume relativo >1,10.
    # =========================================================================

    accumulation_days = (
        (
            (
                ult10["ret_1d"]
                >
                0
            )
            &
            (
                ult10["vol_ratio"]
                >
                1.10
            )
        )
        .sum()
    )

    sinal_acumulacao = (
        accumulation_days
        >=
        2
    )

    # =========================================================================
    # SINAL 4 — OBV
    # =========================================================================

    sinal_obv = (
        pd.notna(
            atual["OBV"]
        )
        and
        pd.notna(
            atual["OBV_MA20"]
        )
        and
        atual["OBV"]
        >
        atual["OBV_MA20"]
    )

    # =========================================================================
    # SINAL 5 — DIVERGÊNCIA PREÇO / VOLUME
    #
    # Preço caiu em aproximadamente 20 pregões
    # e OBV melhorou.
    # =========================================================================

    sinal_divergencia = False

    preco_change = np.nan
    obv_change = np.nan

    if len(hist) >= 21:

        inicio20 = hist.iloc[-21]

        preco_change = (
            atual["PX"]
            /
            inicio20["PX"]
            -
            1
        )

        obv_change = (
            atual["OBV"]
            -
            inicio20["OBV"]
        )

        sinal_divergencia = (
            preco_change < 0
            and
            obv_change > 0
        )

    # =========================================================================
    # SINAL 6 — REVERSÃO CURTA
    #
    # ret20 < 0
    # ret5 > 0
    # =========================================================================

    ret5 = atual[
        "ret_5d_inst"
    ]

    ret20 = atual[
        "ret_20d_inst"
    ]

    sinal_reversao = (
        pd.notna(ret5)
        and
        pd.notna(ret20)
        and
        ret20 < 0
        and
        ret5 > 0
    )

    # =========================================================================
    # SCORE INSTITUCIONAL
    # =========================================================================

    score = (
        int(sinal_volume)
        +
        int(sinal_absorcao)
        +
        int(sinal_acumulacao)
        +
        int(sinal_obv)
        +
        int(sinal_divergencia)
        +
        int(sinal_reversao)
    )

    # =========================================================================
    # CLASSE
    # =========================================================================

    if score >= 4:

        classe = "FORTE"

    elif score >= 2:

        classe = "MODERADO"

    else:

        classe = "FRACO"

    return {
        "institutional_score":
            int(score),

        "institutional_class":
            classe,

        "institutional_volume_ratio":
            float(volume_ratio)
            if pd.notna(volume_ratio)
            else np.nan,

        "accumulation_days_10":
            int(accumulation_days),

        "signal_volume":
            bool(sinal_volume),

        "signal_absorption":
            bool(sinal_absorcao),

        "signal_accumulation":
            bool(sinal_acumulacao),

        "signal_obv":
            bool(sinal_obv),

        "signal_divergence":
            bool(sinal_divergencia),

        "signal_reversal":
            bool(sinal_reversao),

        "price_change_20d":
            float(preco_change)
            if pd.notna(preco_change)
            else np.nan,

        "obv_change_20d":
            float(obv_change)
            if pd.notna(obv_change)
            else np.nan,
    }


# =============================================================================
# 3. ANALISAR UM TICKER
# =============================================================================

def analyze_ticker_institutional(
    df: pd.DataFrame,
) -> dict | None:
    """
    Analisa o último pregão disponível.
    """

    if df is None or df.empty:
        return None

    data = add_institutional_indicators(
        df
    )

    required = [
        "vol_ratio",
        "OBV",
        "OBV_MA20",
        "ret_5d_inst",
        "ret_20d_inst",
        "close_location_inst",
    ]

    valid = data.dropna(
        subset=required
    )

    if len(valid) < 60:
        return None

    result = (
        calculate_institutional_signals(
            valid
        )
    )

    if pd.isna(
        result.get(
            "institutional_score",
            np.nan,
        )
    ):
        return None

    result[
        "date"
    ] = valid.index[-1]

    return result


# =============================================================================
# 4. ANALISAR UNIVERSO
# =============================================================================

def analyze_institutional(
    market_data: Dict[
        str,
        pd.DataFrame,
    ],
) -> pd.DataFrame:
    """
    Analisa Smart Money de todo o universo.
    """

    rows = []

    print("=" * 90)
    print(
        "GROWTH OPPORTUNITY ENGINE"
    )
    print(
        "SMART MONEY / INSTITUCIONAL — MODELO CÉLULA 12"
    )
    print("=" * 90)

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
            f"Score {result['institutional_score']} | "
            f"{result['institutional_class']}"
        )

    result_df = pd.DataFrame(
        rows
    )

    if not result_df.empty:

        columns_order = [
            "ticker",
            "date",
            "institutional_score",
            "institutional_class",
            "signal_volume",
            "signal_absorption",
            "signal_accumulation",
            "signal_obv",
            "signal_divergence",
            "signal_reversal",
            "institutional_volume_ratio",
            "accumulation_days_10",
            "price_change_20d",
            "obv_change_20d",
        ]

        result_df = result_df[
            [
                col
                for col in columns_order
                if col in result_df.columns
            ]
        ]

    print("-" * 90)

    print(
        f"Empresas analisadas: "
        f"{len(result_df)}"
    )

    if not result_df.empty:

        confirmed = (
            result_df[
                "institutional_score"
            ]
            >=
            2
        ).sum()

        strong = (
            result_df[
                "institutional_score"
            ]
            >=
            4
        ).sum()

        print(
            f"Score institucional >=2: "
            f"{confirmed}"
        )

        print(
            f"Score institucional >=4: "
            f"{strong}"
        )

    print("=" * 90)

    return result_df


# =============================================================================
# 5. TESTE LOCAL
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
