# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# engine/data.py
#
# Motor de dados de mercado.
#
# Responsabilidades:
# - Baixar preços históricos
# - Padronizar OHLCV
# - Calcular SMA20 e SMA50
# - Calcular volume relativo
# - Calcular retornos de 5, 10 e 20 dias
# - Calcular distância da SMA50
# - Calcular posição do fechamento dentro do candle
#
# NÃO toma decisão de investimento.
# =============================================================================

from __future__ import annotations

import time
from typing import Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from config import (
    UNIVERSE,
    BENCHMARK,
    PRICE_PERIOD,
    PRICE_INTERVAL,
    MIN_HISTORY_DAYS,
    SMA_SHORT,
    SMA_CONFIRMATION,
    VOLUME_LOOKBACK,
    RETURN_WINDOWS,
    VERBOSE,
)


# =============================================================================
# 1. PADRONIZAÇÃO
# =============================================================================

REQUIRED_COLUMNS = [
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza as colunas retornadas pelo yfinance.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # yfinance pode retornar MultiIndex.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Remove colunas duplicadas.
    df = df.loc[:, ~df.columns.duplicated()]

    return df


# =============================================================================
# 2. VALIDAÇÃO
# =============================================================================

def _validate_ohlcv(
    df: pd.DataFrame,
    ticker: str,
) -> bool:

    if df.empty:
        return False

    missing = [
        col
        for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing:

        if VERBOSE:
            print(
                f"⚠️ {ticker}: colunas ausentes: "
                f"{missing}"
            )

        return False

    valid_close = df["Close"].dropna()

    if len(valid_close) < MIN_HISTORY_DAYS:

        if VERBOSE:
            print(
                f"⚠️ {ticker}: histórico insuficiente "
                f"({len(valid_close)} pregões)"
            )

        return False

    return True


# =============================================================================
# 3. DOWNLOAD INDIVIDUAL
# =============================================================================

def download_ticker(
    ticker: str,
    retries: int = 3,
) -> Optional[pd.DataFrame]:
    """
    Baixa histórico diário de um ticker.
    """

    for attempt in range(1, retries + 1):

        try:

            df = yf.download(
                ticker,
                period=PRICE_PERIOD,
                interval=PRICE_INTERVAL,
                auto_adjust=True,
                progress=False,
                threads=False,
            )

            df = _normalize_columns(df)

            if not _validate_ohlcv(
                df,
                ticker,
            ):
                return None

            df = df[
                REQUIRED_COLUMNS
            ].copy()

            df = df.sort_index()

            df = df[
                ~df.index.duplicated(
                    keep="last"
                )
            ]

            return df

        except Exception as exc:

            if VERBOSE:
                print(
                    f"⚠️ {ticker}: tentativa "
                    f"{attempt}/{retries} falhou: "
                    f"{exc}"
                )

            if attempt < retries:
                time.sleep(2)

    return None


# =============================================================================
# 4. INDICADORES DE MERCADO
# =============================================================================

def add_market_indicators(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Adiciona somente indicadores necessários
    para as próximas etapas da estratégia.
    """

    df = df.copy()

    # -------------------------------------------------------------------------
    # MÉDIAS MÓVEIS
    # -------------------------------------------------------------------------

    df["sma20"] = (
        df["Close"]
        .rolling(
            SMA_SHORT,
            min_periods=SMA_SHORT,
        )
        .mean()
    )

    df["sma50"] = (
        df["Close"]
        .rolling(
            SMA_CONFIRMATION,
            min_periods=SMA_CONFIRMATION,
        )
        .mean()
    )

    # -------------------------------------------------------------------------
    # DISTÂNCIA DA SMA50
    #
    # Exemplo:
    # -0.12 = preço 12% abaixo da SMA50.
    # -------------------------------------------------------------------------

    df["dist_sma50"] = (
        df["Close"]
        / df["sma50"]
        - 1
    )

    # -------------------------------------------------------------------------
    # RETORNOS
    # -------------------------------------------------------------------------

    for name, window in RETURN_WINDOWS.items():

        column = (
            f"ret_{name.lower()}"
        )

        df[column] = (
            df["Close"]
            .pct_change(
                periods=window,
                fill_method=None,
            )
        )

    # -------------------------------------------------------------------------
    # VOLUME RELATIVO
    #
    # Volume atual / média dos 20 pregões anteriores.
    #
    # shift(1) evita que o volume atual entre
    # na própria referência.
    # -------------------------------------------------------------------------

    previous_volume_mean = (
        df["Volume"]
        .shift(1)
        .rolling(
            VOLUME_LOOKBACK,
            min_periods=VOLUME_LOOKBACK,
        )
        .mean()
    )

    df["volume_ratio"] = (
        df["Volume"]
        / previous_volume_mean
    )

    # -------------------------------------------------------------------------
    # CLOSE LOCATION
    #
    # 0 = fechamento na mínima
    # 1 = fechamento na máxima
    # -------------------------------------------------------------------------

    candle_range = (
        df["High"]
        - df["Low"]
    )

    df["close_location"] = np.where(
        candle_range > 0,
        (
            df["Close"]
            - df["Low"]
        )
        / candle_range,
        0.5,
    )

    # -------------------------------------------------------------------------
    # CROSSOVER REAL DA SMA50
    #
    # Ontem:
    # preço <= SMA50
    #
    # Hoje:
    # preço > SMA50
    # -------------------------------------------------------------------------

    df["cross_sma50"] = (
        (
            df["Close"].shift(1)
            <=
            df["sma50"].shift(1)
        )
        &
        (
            df["Close"]
            >
            df["sma50"]
        )
    )

    return df


# =============================================================================
# 5. DOWNLOAD DO UNIVERSO
# =============================================================================

def download_market_data(
    tickers=None,
) -> Dict[str, pd.DataFrame]:
    """
    Baixa e processa o universo completo.
    """

    if tickers is None:
        tickers = UNIVERSE

    # Remove duplicatas.
    tickers = list(
        dict.fromkeys(tickers)
    )

    market_data = {}

    total = len(tickers)

    print("=" * 80)
    print(
        "GROWTH OPPORTUNITY ENGINE"
    )
    print(
        "COLETA DE DADOS DE MERCADO"
    )
    print("=" * 80)

    for position, ticker in enumerate(
        tickers,
        start=1,
    ):

        if VERBOSE:
            print(
                f"[{position:>3}/{total}] "
                f"{ticker:<8}",
                end=" ",
            )

        df = download_ticker(
            ticker
        )

        if df is None:

            if VERBOSE:
                print("❌")

            continue

        df = add_market_indicators(
            df
        )

        market_data[ticker] = df

        if VERBOSE:
            print(
                f"✅ {len(df)} pregões"
            )

    print("-" * 80)

    print(
        f"Empresas solicitadas: "
        f"{total}"
    )

    print(
        f"Empresas válidas: "
        f"{len(market_data)}"
    )

    print(
        f"Falhas: "
        f"{total - len(market_data)}"
    )

    print("=" * 80)

    return market_data


# =============================================================================
# 6. BENCHMARK
# =============================================================================

def download_benchmark():
    """
    Baixa o SPY separadamente.
    """

    df = download_ticker(
        BENCHMARK
    )

    if df is None:

        raise RuntimeError(
            f"Não foi possível baixar "
            f"o benchmark {BENCHMARK}."
        )

    return add_market_indicators(
        df
    )


# =============================================================================
# 7. SNAPSHOT ATUAL
# =============================================================================

def build_market_snapshot(
    market_data: Dict[
        str,
        pd.DataFrame,
    ],
) -> pd.DataFrame:
    """
    Produz uma linha por empresa usando
    somente o último pregão disponível.
    """

    rows = []

    for ticker, df in market_data.items():

        valid = df.dropna(
            subset=[
                "Close",
                "sma20",
                "sma50",
                "dist_sma50",
                "volume_ratio",
                "ret_5d",
                "ret_10d",
                "ret_20d",
                "close_location",
            ]
        )

        if valid.empty:
            continue

        row = valid.iloc[-1]

        rows.append(
            {
                "ticker": ticker,
                "date": valid.index[-1],
                "close": float(
                    row["Close"]
                ),
                "sma20": float(
                    row["sma20"]
                ),
                "sma50": float(
                    row["sma50"]
                ),
                "dist_sma50": float(
                    row["dist_sma50"]
                ),
                "ret_5d": float(
                    row["ret_5d"]
                ),
                "ret_10d": float(
                    row["ret_10d"]
                ),
                "ret_20d": float(
                    row["ret_20d"]
                ),
                "volume_ratio": float(
                    row["volume_ratio"]
                ),
                "close_location": float(
                    row["close_location"]
                ),
                "cross_sma50": bool(
                    row["cross_sma50"]
                ),
            }
        )

    if not rows:
        return pd.DataFrame()

    snapshot = pd.DataFrame(
        rows
    )

    snapshot = snapshot.sort_values(
        "ticker"
    ).reset_index(
        drop=True
    )

    return snapshot


# =============================================================================
# 8. TESTE LOCAL
# =============================================================================

if __name__ == "__main__":

    # Teste pequeno para evitar baixar
    # todo o universo durante desenvolvimento.

    test_tickers = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
    ]

    data = download_market_data(
        test_tickers
    )

    snapshot = build_market_snapshot(
        data
    )

    if snapshot.empty:

        print(
            "❌ Nenhum snapshot produzido."
        )

    else:

        columns = [
            "ticker",
            "date",
            "close",
            "dist_sma50",
            "ret_5d",
            "ret_10d",
            "ret_20d",
            "volume_ratio",
            "close_location",
            "cross_sma50",
        ]

        print(
            snapshot[
                columns
            ].to_string(
                index=False
            )
        )
