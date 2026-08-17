# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# main.py
#
# Pipeline principal:
#
# 1. Configuração
# 2. Dados de mercado
# 3. Fundamentos
# 4. Smart Money / Institucional
# 5. Sinais
# 6. Estratégia
# 7. Relatórios
# =============================================================================

from __future__ import annotations

import sys
import traceback
from datetime import datetime

import pandas as pd

from config import (
    PROJECT_NAME,
    PROJECT_VERSION,
    UNIVERSE,
    VERBOSE,
    print_config,
)

from engine.data import (
    download_market_data,
)

from engine.fundamentals import (
    analyze_fundamentals,
)

from engine.institutional import (
    analyze_institutional,
)

from engine.signals import (
    build_full_signal_table,
)

from engine.strategy import (
    apply_strategy,
    rank_opportunities,
    strategy_summary,
)

from engine.report import (
    generate_reports,
    build_text_summary,
)


# =============================================================================
# 1. CABEÇALHO
# =============================================================================

def print_header():

    print("=" * 90)
    print(PROJECT_NAME)
    print(f"Versão {PROJECT_VERSION}")
    print(
        "Execução: "
        + datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    )
    print("=" * 90)


# =============================================================================
# 2. VALIDAÇÃO DO UNIVERSO
# =============================================================================

def validate_universe():

    tickers = [
        str(ticker).strip().upper()
        for ticker in UNIVERSE
        if str(ticker).strip()
    ]

    tickers = list(
        dict.fromkeys(
            tickers
        )
    )

    if not tickers:

        raise RuntimeError(
            "UNIVERSE está vazio."
        )

    return tickers


# =============================================================================
# 3. RESUMO DOS SINAIS
# =============================================================================

def print_signal_summary(
    strategy_table: pd.DataFrame,
):

    print("\n" + "=" * 90)
    print("RESULTADO OPERACIONAL")
    print("=" * 90)

    if (
        strategy_table is None
        or strategy_table.empty
    ):

        print(
            "Nenhuma empresa disponível "
            "para classificação."
        )

        return

    summary = strategy_summary(
        strategy_table
    )

    if not summary.empty:

        output = summary.copy()

        if (
            "pullback_mediano"
            in output.columns
        ):

            output[
                "pullback_mediano"
            ] *= 100

        if (
            "peso_inicial_mediano"
            in output.columns
        ):

            output[
                "peso_inicial_mediano"
            ] *= 100

        print(
            output.to_string(
                index=False
            )
        )

    strong = strategy_table[
        strategy_table[
            "signal"
        ] == "ENTRADA_FORTE"
    ]

    partial = strategy_table[
        strategy_table[
            "signal"
        ] == "ENTRADA_PARCIAL"
    ]

    wait = strategy_table[
        strategy_table[
            "signal"
        ] == "AGUARDAR"
    ]

    print("\n" + "-" * 90)

    print(
        f"ENTRADA FORTE   : "
        f"{len(strong)}"
    )

    print(
        f"ENTRADA PARCIAL : "
        f"{len(partial)}"
    )

    print(
        f"AGUARDAR        : "
        f"{len(wait)}"
    )

    print("-" * 90)


# =============================================================================
# 4. MOSTRAR OPORTUNIDADES
# =============================================================================

def print_top_opportunities(
    strategy_table: pd.DataFrame,
    limit: int = 20,
):

    if (
        strategy_table is None
        or strategy_table.empty
    ):
        return

    candidates = strategy_table[
        strategy_table[
            "signal"
        ].isin(
            [
                "ENTRADA_FORTE",
                "ENTRADA_PARCIAL",
            ]
        )
    ].head(
        limit
    )

    print("\n" + "=" * 90)
    print("OPORTUNIDADES")
    print("=" * 90)

    if candidates.empty:

        print(
            "Nenhuma ENTRADA FORTE ou "
            "ENTRADA PARCIAL hoje."
        )

        return

    columns = [
        "ticker",
        "date",
        "signal",
        "pullback",
        "revenue_yoy",
        "eps_growth_yoy",
        "falling_score",
        "institutional_score",
        "confirmations_total",
        "dist_sma50",
        "volume_ratio",
        "initial_weight",
        "current_cash_weight",
    ]

    columns = [
        col
        for col in columns
        if col in candidates.columns
    ]

    output = candidates[
        columns
    ].copy()

    for col in [
        "pullback",
        "revenue_yoy",
        "eps_growth_yoy",
        "dist_sma50",
        "initial_weight",
        "current_cash_weight",
    ]:

        if col in output.columns:

            output[col] = (
                output[col]
                * 100
            )

    formatters = {}

    for col in [
        "pullback",
        "revenue_yoy",
        "eps_growth_yoy",
        "dist_sma50",
    ]:

        if col in output.columns:

            formatters[col] = (
                "{:.2f}%".format
            )

    for col in [
        "initial_weight",
        "current_cash_weight",
    ]:

        if col in output.columns:

            formatters[col] = (
                "{:.0f}%".format
            )

    if (
        "volume_ratio"
        in output.columns
    ):

        formatters[
            "volume_ratio"
        ] = "{:.2f}x".format

    print(
        output.to_string(
            index=False,
            formatters=formatters,
        )
    )


# =============================================================================
# 5. PIPELINE
# =============================================================================

def run_engine():

    print_header()

    # -------------------------------------------------------------------------
    # CONFIG
    # -------------------------------------------------------------------------

    print_config()

    tickers = validate_universe()

    print(
        f"\nUniverso operacional: "
        f"{len(tickers)} empresas"
    )

    # =========================================================================
    # ETAPA 1 — MERCADO
    # =========================================================================

    print("\n" + "=" * 90)
    print("ETAPA 1/6 — DADOS DE MERCADO")
    print("=" * 90)

    market_data = (
        download_market_data(
            tickers
        )
    )

    if not market_data:

        raise RuntimeError(
            "Nenhum dado de mercado "
            "foi obtido."
        )

    # =========================================================================
    # ETAPA 2 — FUNDAMENTOS
    # =========================================================================

    print("\n" + "=" * 90)
    print("ETAPA 2/6 — FUNDAMENTOS")
    print("=" * 90)

    fundamentals = (
        analyze_fundamentals(
            tickers
        )
    )

    if fundamentals.empty:

        raise RuntimeError(
            "Nenhum fundamento "
            "foi obtido."
        )

    # =========================================================================
    # ETAPA 3 — SMART MONEY / INSTITUCIONAL
    # =========================================================================

    print("\n" + "=" * 90)
    print("ETAPA 3/6 — SMART MONEY / INSTITUCIONAL")
    print("=" * 90)

    institutional_scores = (
        analyze_institutional(
            market_data
        )
    )

    if institutional_scores.empty:

        print(
            "⚠️ Nenhum score institucional foi obtido."
        )

    else:

        print(
            f"Scores institucionais calculados: "
            f"{len(institutional_scores)}"
        )

        confirmed = (
            institutional_scores[
                "institutional_score"
            ] >= 2
        ).sum()

        print(
            f"Com score institucional >=2: "
            f"{confirmed}"
        )

    # =========================================================================
    # ETAPA 4 — SINAIS
    # =========================================================================

    print("\n" + "=" * 90)
    print("ETAPA 4/6 — SINAIS")
    print("=" * 90)

    signal_table = (
        build_full_signal_table(
            market_data=market_data,
            institutional_scores=institutional_scores,
        )
    )

    if signal_table.empty:

        raise RuntimeError(
            "Tabela de sinais vazia."
        )

    print(
        f"Sinais calculados: "
        f"{len(signal_table)}"
    )

    print(
        f"Na zona 20%-30%: "
        f"{signal_table['pullback_zone'].sum()}"
    )

    # =========================================================================
    # ETAPA 5 — ESTRATÉGIA
    # =========================================================================

    print("\n" + "=" * 90)
    print("ETAPA 5/6 — ESTRATÉGIA")
    print("=" * 90)

    strategy_table = apply_strategy(
        signal_table=signal_table,
        fundamentals=fundamentals,
    )

    strategy_table = (
        rank_opportunities(
            strategy_table
        )
    )

    if strategy_table.empty:

        raise RuntimeError(
            "Estratégia não produziu "
            "nenhuma classificação."
        )

    print_signal_summary(
        strategy_table
    )

    print_top_opportunities(
        strategy_table
    )

    # =========================================================================
    # ETAPA 6 — RELATÓRIOS
    # =========================================================================

    print("\n" + "=" * 90)
    print("ETAPA 6/6 — RELATÓRIOS")
    print("=" * 90)

    outputs = generate_reports(
        strategy_table
    )

    # =========================================================================
    # FINAL
    # =========================================================================

    print("\n" + "=" * 90)
    print("EXECUÇÃO CONCLUÍDA")
    print("=" * 90)

    print(
        build_text_summary(
            strategy_table
        )
    )

    if outputs:

        print("\nArquivos gerados:")

        for name, path in outputs.items():

            print(
                f"  {name}: {path}"
            )

    print("=" * 90)

    return {
        "market_data":
            market_data,

        "fundamentals":
            fundamentals,

        "institutional":
            institutional_scores,

        "signals":
            signal_table,

        "strategy":
            strategy_table,

        "outputs":
            outputs,
    }


# =============================================================================
# 6. EXECUÇÃO
# =============================================================================

def main():

    try:

        run_engine()

        return 0

    except KeyboardInterrupt:

        print(
            "\n⚠️ Execução interrompida "
            "pelo usuário."
        )

        return 130

    except Exception as exc:

        print("\n" + "=" * 90)

        print(
            "❌ ERRO NO "
            "GROWTH OPPORTUNITY ENGINE"
        )

        print("=" * 90)

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        if VERBOSE:

            print("\nTraceback:")

            traceback.print_exc()

        print("=" * 90)

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )
