# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# engine/report.py
#
# Relatórios operacionais.
#
# Responsabilidades:
# - salvar opportunities.csv
# - atualizar history.csv
# - gerar resumo textual
# - gerar relatório PDF simples e profissional
#
# NÃO toma decisão de investimento.
# =============================================================================

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from config import (
    PROJECT_NAME,
    PROJECT_VERSION,
    OPPORTUNITIES_FILE,
    HISTORY_FILE,
    REPORT_FILE,
    SAVE_HISTORY,
    REPORT_TOP_OPPORTUNITIES,
    REPORT_INCLUDE_WAIT,
    GENERATE_CSV,
    GENERATE_PDF,
)


# =============================================================================
# 1. COLUNAS PRINCIPAIS
# =============================================================================

REPORT_COLUMNS = [
    "ticker",
    "date",
    "signal",
    "report_status",
    "pullback",
    "revenue_yoy",
    "eps_growth_yoy",
    "falling_score",
    "falling_risk",
    "confirmations_total",
    "dist_sma50",
    "volume_ratio",
    "initial_weight",
    "confirmation_weight",
    "current_cash_weight",
    "reason",
]


# =============================================================================
# 2. PREPARAR TABELA
# =============================================================================

def prepare_report_table(
    strategy_table: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prepara a tabela de saída sem alterar o sinal operacional.

    report_status é SOMENTE uma classificação visual para o relatório:
    - ENTRADA_FORTE
    - ENTRADA_PARCIAL
    - PROXIMO_DO_GATILHO
    - AGUARDAR

    PROXIMO_DO_GATILHO:
    empresa ainda em AGUARDAR, com fundamentos aprovados,
    Falling Score <= 2 e pullback entre 18% e menos de 20%.

    Isso NÃO cria novo sinal de compra e NÃO altera strategy.py.
    """

    if strategy_table is None or strategy_table.empty:
        return pd.DataFrame()

    df = strategy_table.copy()

    if not REPORT_INCLUDE_WAIT:
        df = df[
            df["signal"] != "AGUARDAR"
        ]

    def classify_report_status(row):
        signal = row.get("signal", "AGUARDAR")

        if signal == "ENTRADA_FORTE":
            return "ENTRADA_FORTE"

        if signal == "ENTRADA_PARCIAL":
            return "ENTRADA_PARCIAL"

        fundamentals_ok = bool(
            row.get("fundamentals_ok", False)
        )

        falling_score = row.get(
            "falling_score",
            float("nan"),
        )

        pullback = row.get(
            "pullback",
            float("nan"),
        )

        if (
            signal == "AGUARDAR"
            and fundamentals_ok
            and pd.notna(falling_score)
            and falling_score <= 2
            and pd.notna(pullback)
            and 0.18 <= pullback < 0.20
        ):
            return "PROXIMO_DO_GATILHO"

        return "AGUARDAR"

    df["report_status"] = df.apply(
        classify_report_status,
        axis=1,
    )

    priority = {
        "ENTRADA_FORTE": 0,
        "ENTRADA_PARCIAL": 1,
        "PROXIMO_DO_GATILHO": 2,
        "AGUARDAR": 3,
    }

    df["_report_priority"] = (
        df["report_status"]
        .map(priority)
        .fillna(99)
    )

    # Dentro de PROXIMO_DO_GATILHO, maior pullback vem primeiro,
    # pois está mais perto do limite mínimo de 20%.
    # Nos demais grupos, preservamos a ordenação operacional original.
    df["_original_order"] = range(len(df))

    near_mask = (
        df["report_status"]
        == "PROXIMO_DO_GATILHO"
    )

    near = (
        df[near_mask]
        .sort_values(
            ["pullback", "_original_order"],
            ascending=[False, True],
        )
    )

    others = df[~near_mask].copy()

    ordered_parts = []

    for status in [
        "ENTRADA_FORTE",
        "ENTRADA_PARCIAL",
    ]:
        ordered_parts.append(
            others[
                others["report_status"] == status
            ].sort_values("_original_order")
        )

    ordered_parts.append(near)

    ordered_parts.append(
        others[
            others["report_status"] == "AGUARDAR"
        ].sort_values("_original_order")
    )

    df = pd.concat(
        ordered_parts,
        ignore_index=True,
    )

    available = [
        c
        for c in REPORT_COLUMNS
        if c in df.columns
    ]

    df = df[
        available
    ].copy()

    return df.reset_index(drop=True)


# =============================================================================
# 3. SALVAR CSV
# =============================================================================

def save_opportunities_csv(
    strategy_table: pd.DataFrame,
) -> Path:

    table = prepare_report_table(
        strategy_table
    )

    OPPORTUNITIES_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    table.to_csv(
        OPPORTUNITIES_FILE,
        index=False,
    )

    return OPPORTUNITIES_FILE


# =============================================================================
# 4. HISTÓRICO
# =============================================================================

def update_history(
    strategy_table: pd.DataFrame,
) -> Path | None:

    if not SAVE_HISTORY:
        return None

    if strategy_table is None or strategy_table.empty:
        return None

    table = strategy_table.copy()

    run_timestamp = pd.Timestamp.utcnow()

    table[
        "run_timestamp"
    ] = run_timestamp

    HISTORY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if HISTORY_FILE.exists():

        try:

            old = pd.read_csv(
                HISTORY_FILE
            )

            history = pd.concat(
                [
                    old,
                    table,
                ],
                ignore_index=True,
            )

        except Exception:

            history = table

    else:

        history = table

    # -------------------------------------------------------------------------
    # PRESERVAR O FORWARD TEST
    #
    # Cada execução deve permanecer auditável no histórico.
    # Não deduplicamos mais por ticker + date + signal, pois isso apagava
    # execuções repetidas do mesmo pregão e do mesmo sinal.
    #
    # Mantemos apenas uma proteção contra duplicação exata da mesma execução,
    # usando run_timestamp quando disponível.
    # -------------------------------------------------------------------------

    dedupe_cols = [
        col
        for col in [
            "ticker",
            "date",
            "signal",
            "run_timestamp",
        ]
        if col in history.columns
    ]

    if len(dedupe_cols) == 4:

        history = history.drop_duplicates(
            subset=dedupe_cols,
            keep="last",
        )

    history.to_csv(
        HISTORY_FILE,
        index=False,
    )

    return HISTORY_FILE


# =============================================================================
# 5. RESUMO OPERACIONAL
# =============================================================================

def build_text_summary(
    strategy_table: pd.DataFrame,
) -> str:

    if strategy_table is None or strategy_table.empty:

        return (
            f"{PROJECT_NAME}\n"
            "Nenhuma oportunidade disponível."
        )

    total = len(
        strategy_table
    )

    strong = (
        strategy_table[
            "signal"
        ]
        ==
        "ENTRADA_FORTE"
    ).sum()

    partial = (
        strategy_table[
            "signal"
        ]
        ==
        "ENTRADA_PARCIAL"
    ).sum()

    wait = (
        strategy_table[
            "signal"
        ]
        ==
        "AGUARDAR"
    ).sum()

    lines = [
        PROJECT_NAME,
        f"Versão {PROJECT_VERSION}",
        "",
        f"Empresas analisadas: {total}",
        f"Entradas fortes: {strong}",
        f"Entradas parciais: {partial}",
        f"Aguardar: {wait}",
    ]

    return "\n".join(
        lines
    )


# =============================================================================
# 6. FORMATADORES
# =============================================================================

def _pct(
    value,
    decimals=1,
):

    if pd.isna(value):
        return "N/A"

    return (
        f"{value * 100:.{decimals}f}%"
    )


def _weight(
    value,
):

    if pd.isna(value):
        return "N/A"

    return (
        f"{value * 100:.0f}%"
    )


# =============================================================================
# 7. TABELA PARA PDF
# =============================================================================

def _build_pdf_rows(
    strategy_table: pd.DataFrame,
) -> list[list[str]]:

    rows = []

    if strategy_table.empty:
        return rows

    top = strategy_table.head(
        REPORT_TOP_OPPORTUNITIES
    )

    for _, row in top.iterrows():

        rows.append(
            [
                str(
                    row.get(
                        "ticker",
                        ""
                    )
                ),

                str(
                    row.get(
                        "report_status",
                        row.get(
                            "signal",
                            ""
                        )
                    )
                ),

                _pct(
                    row.get(
                        "pullback",
                        float("nan"),
                    )
                ),

                str(
                    int(
                        row.get(
                            "falling_score",
                            0,
                        )
                    )
                ),

                str(
                    int(
                        row.get(
                            "confirmations_total",
                            0,
                        )
                    )
                ),

                _pct(
                    row.get(
                        "revenue_yoy",
                        float("nan"),
                    )
                ),

                _pct(
                    row.get(
                        "eps_growth_yoy",
                        float("nan"),
                    )
                ),

                _weight(
                    row.get(
                        "initial_weight",
                        float("nan"),
                    )
                ),
            ]
        )

    return rows


# =============================================================================
# 8. PDF
# =============================================================================

def generate_pdf_report(
    strategy_table: pd.DataFrame,
) -> Path:

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with PdfPages(
        REPORT_FILE
    ) as pdf:

        # ---------------------------------------------------------------------
        # PÁGINA 1 — RESUMO
        # ---------------------------------------------------------------------

        fig = plt.figure(
            figsize=(11.69, 8.27)
        )

        fig.text(
            0.06,
            0.93,
            PROJECT_NAME,
            fontsize=22,
            weight="bold",
        )

        fig.text(
            0.06,
            0.89,
            f"Operational Opportunity Report | v{PROJECT_VERSION}",
            fontsize=11,
        )

        fig.text(
            0.06,
            0.85,
            datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            ),
            fontsize=10,
        )

        if (
            strategy_table is None
            or strategy_table.empty
        ):

            fig.text(
                0.06,
                0.75,
                "Nenhuma oportunidade disponível.",
                fontsize=14,
            )

            plt.axis("off")

            pdf.savefig(
                fig,
                bbox_inches="tight",
            )

            plt.close(fig)

            return REPORT_FILE

        total = len(
            strategy_table
        )

        strong = (
            strategy_table[
                "signal"
            ]
            ==
            "ENTRADA_FORTE"
        ).sum()

        partial = (
            strategy_table[
                "signal"
            ]
            ==
            "ENTRADA_PARCIAL"
        ).sum()

        wait = (
            strategy_table[
                "signal"
            ]
            ==
            "AGUARDAR"
        ).sum()

        summary_text = (
            f"Empresas avaliadas: {total}\n\n"
            f"ENTRADA FORTE: {strong}\n"
            f"ENTRADA PARCIAL: {partial}\n"
            f"AGUARDAR: {wait}"
        )

        fig.text(
            0.06,
            0.72,
            summary_text,
            fontsize=15,
        )

        fig.text(
            0.06,
            0.43,
            "Regra operacional",
            fontsize=14,
            weight="bold",
        )

        rules = (
            "ENTRADA FORTE\n"
            "Falling Score <= 1\n"
            "100% da posição planejada.\n\n"

            "ENTRADA PARCIAL\n"
            "Falling Score = 2, ou Falling >= 3 "
            "com pelo menos 2 confirmações.\n"
            "60% inicialmente + 40% após crossover SMA50.\n\n"

            "AGUARDAR\n"
            "Não há entrada operacional.\n\n"

            "PROXIMO DO GATILHO (apenas monitoramento)\n"
            "Fundamentos aprovados + Falling <= 2 + queda entre 18% e menos de 20%.\n"
            "Não é sinal de compra; apenas destaca empresas próximas da zona de 20%-30%."
        )

        fig.text(
            0.06,
            0.37,
            rules,
            fontsize=11,
            va="top",
        )

        plt.axis(
            "off"
        )

        pdf.savefig(
            fig,
            bbox_inches="tight",
        )

        plt.close(
            fig
        )

        # ---------------------------------------------------------------------
        # PÁGINA 2 — OPORTUNIDADES
        # ---------------------------------------------------------------------

        report_table = prepare_report_table(
            strategy_table
        )

        rows = _build_pdf_rows(
            report_table
        )

        fig = plt.figure(
            figsize=(11.69, 8.27)
        )

        ax = fig.add_axes(
            [
                0.03,
                0.05,
                0.94,
                0.88,
            ]
        )

        ax.axis(
            "off"
        )

        ax.set_title(
            "Oportunidades e monitoramento",
            fontsize=17,
            pad=20,
            weight="bold",
        )

        if rows:

            headers = [
                "Ticker",
                "Status",
                "Queda",
                "Falling",
                "Conf.",
                "Receita",
                "EPS",
                "Entrada",
            ]

            table = ax.table(
                cellText=rows,
                colLabels=headers,
                loc="upper center",
                cellLoc="center",
            )

            table.auto_set_font_size(
                False
            )

            table.set_fontsize(
                8
            )

            table.scale(
                1,
                1.4,
            )

        else:

            ax.text(
                0.5,
                0.7,
                "Nenhuma oportunidade elegível.",
                ha="center",
                fontsize=14,
            )

        pdf.savefig(
            fig,
            bbox_inches="tight",
        )

        plt.close(
            fig
        )

        # ---------------------------------------------------------------------
        # PÁGINAS INDIVIDUAIS
        # ---------------------------------------------------------------------

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
            REPORT_TOP_OPPORTUNITIES
        )

        for _, row in candidates.iterrows():

            fig = plt.figure(
                figsize=(11.69, 8.27)
            )

            ticker = row.get(
                "ticker",
                ""
            )

            signal = row.get(
                "signal",
                ""
            )

            fig.text(
                0.06,
                0.92,
                f"{ticker} — {signal}",
                fontsize=20,
                weight="bold",
            )

            details = [
                (
                    "Status no relatório",
                    str(
                        row.get(
                            "report_status",
                            row.get(
                                "signal",
                                ""
                            )
                        )
                    ),
                ),
                (
                    "Queda",
                    _pct(
                        row.get(
                            "pullback",
                            float("nan"),
                        )
                    ),
                ),
                (
                    "Receita YoY",
                    _pct(
                        row.get(
                            "revenue_yoy",
                            float("nan"),
                        )
                    ),
                ),
                (
                    "EPS YoY",
                    _pct(
                        row.get(
                            "eps_growth_yoy",
                            float("nan"),
                        )
                    ),
                ),
                (
                    "Falling Score",
                    str(
                        row.get(
                            "falling_score",
                            ""
                        )
                    ),
                ),
                (
                    "Risco Falling",
                    str(
                        row.get(
                            "falling_risk",
                            ""
                        )
                    ),
                ),
                (
                    "Confirmações",
                    str(
                        row.get(
                            "confirmations_total",
                            ""
                        )
                    ),
                ),
                (
                    "Distância SMA50",
                    _pct(
                        row.get(
                            "dist_sma50",
                            float("nan"),
                        )
                    ),
                ),
                (
                    "Volume Relativo",
                    (
                        f"{row.get('volume_ratio', float('nan')):.2f}x"
                        if pd.notna(
                            row.get(
                                "volume_ratio",
                                float("nan"),
                            )
                        )
                        else "N/A"
                    ),
                ),
                (
                    "Entrada inicial",
                    _weight(
                        row.get(
                            "initial_weight",
                            float("nan"),
                        )
                    ),
                ),
            ]

            y = 0.82

            for label, value in details:

                fig.text(
                    0.08,
                    y,
                    f"{label}:",
                    fontsize=12,
                    weight="bold",
                )

                fig.text(
                    0.30,
                    y,
                    value,
                    fontsize=12,
                )

                y -= 0.055

            reason = row.get(
                "reason",
                ""
            )

            fig.text(
                0.08,
                y - 0.03,
                "Justificativa:",
                fontsize=12,
                weight="bold",
            )

            fig.text(
                0.08,
                y - 0.08,
                str(reason),
                fontsize=11,
                wrap=True,
            )

            plt.axis(
                "off"
            )

            pdf.savefig(
                fig,
                bbox_inches="tight",
            )

            plt.close(
                fig
            )

    return REPORT_FILE


# =============================================================================
# 9. EXECUTAR TODAS AS SAÍDAS
# =============================================================================

def generate_reports(
    strategy_table: pd.DataFrame,
) -> dict:

    outputs = {}

    print("=" * 80)
    print(
        "GROWTH OPPORTUNITY ENGINE"
    )
    print(
        "GERAÇÃO DE RELATÓRIOS"
    )
    print("=" * 80)

    if GENERATE_CSV:

        csv_path = save_opportunities_csv(
            strategy_table
        )

        outputs[
            "opportunities_csv"
        ] = csv_path

        print(
            f"✅ CSV: {csv_path}"
        )

    history_path = update_history(
        strategy_table
    )

    if history_path is not None:

        outputs[
            "history_csv"
        ] = history_path

        print(
            f"✅ Histórico: {history_path}"
        )

    if GENERATE_PDF:

        pdf_path = generate_pdf_report(
            strategy_table
        )

        outputs[
            "report_pdf"
        ] = pdf_path

        print(
            f"✅ PDF: {pdf_path}"
        )

    print("=" * 80)

    return outputs


# =============================================================================
# 10. TESTE LOCAL
# =============================================================================

if __name__ == "__main__":

    test = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "date": "2026-08-14",
                "signal": "ENTRADA_FORTE",
                "pullback": 0.22,
                "revenue_yoy": 0.35,
                "eps_growth_yoy": 0.52,
                "falling_score": 1,
                "falling_risk": "BAIXO",
                "confirmations_total": 2,
                "dist_sma50": -0.04,
                "volume_ratio": 1.45,
                "initial_weight": 1.0,
                "confirmation_weight": 0.0,
                "current_cash_weight": 0.0,
                "reason":
                    "fundamentos aprovados | queda 22.0% | "
                    "Falling Score 1 | 2 confirmações",
            },

            {
                "ticker": "AMD",
                "date": "2026-08-14",
                "signal": "ENTRADA_PARCIAL",
                "pullback": 0.25,
                "revenue_yoy": 0.24,
                "eps_growth_yoy": 0.40,
                "falling_score": 3,
                "falling_risk": "ALTO",
                "confirmations_total": 2,
                "dist_sma50": -0.09,
                "volume_ratio": 1.50,
                "initial_weight": 0.60,
                "confirmation_weight": 0.40,
                "current_cash_weight": 0.40,
                "reason":
                    "fundamentos aprovados | queda 25.0% | "
                    "Falling Score 3 | 2 confirmações",
            },
        ]
    )

    print(
        build_text_summary(
            test
        )
    )

    generate_reports(
        test
    )
