# ============================================================
# GROWTH OPPORTUNITY ENGINE
# agent_export.py
# ============================================================
#
# Exportador oficial para integração com:
# INVESTMENT CIO AGENT
#
# PRINCÍPIO:
# Este módulo NÃO recalcula:
#
# - preços;
# - indicadores técnicos;
# - fundamentos;
# - institutional score;
# - pullback;
# - Falling Knife Score;
# - confirmações;
# - sinais;
# - ranking;
# - pesos;
# - plano de capital.
#
# Ele apenas serializa os resultados já produzidos
# pelo GROWTH OPPORTUNITY ENGINE.
#
# ============================================================

from __future__ import annotations

import json
import math
from datetime import (
    date,
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ============================================================
# IDENTIDADE DO SISTEMA
# ============================================================

SOURCE_SYSTEM = (
    "GROWTH_OPPORTUNITY_ENGINE"
)

EXPORT_VERSION = "1.0"

OUTPUT_FILE = (
    Path("outputs")
    / "agent_output_raw.json"
)


# ============================================================
# CONVERSÃO SEGURA PARA JSON
# ============================================================

def _json_safe(
    value: Any,
) -> Any:

    # --------------------------------------------------------
    # None
    # --------------------------------------------------------

    if value is None:
        return None

    # --------------------------------------------------------
    # Pandas NA / NaN
    # --------------------------------------------------------

    try:

        if pd.isna(value):

            if not isinstance(
                value,
                (
                    list,
                    tuple,
                    dict,
                    np.ndarray,
                    pd.Series,
                    pd.DataFrame,
                ),
            ):
                return None

    except (
        TypeError,
        ValueError,
    ):
        pass

    # --------------------------------------------------------
    # DataFrame
    # --------------------------------------------------------

    if isinstance(
        value,
        pd.DataFrame,
    ):

        return [
            {
                str(key):
                    _json_safe(item)
                for key, item
                in record.items()
            }
            for record
            in value.to_dict(
                orient="records"
            )
        ]

    # --------------------------------------------------------
    # Series
    # --------------------------------------------------------

    if isinstance(
        value,
        pd.Series,
    ):

        return {
            str(key):
                _json_safe(item)
            for key, item
            in value.to_dict().items()
        }

    # --------------------------------------------------------
    # Numpy array
    # --------------------------------------------------------

    if isinstance(
        value,
        np.ndarray,
    ):

        return [
            _json_safe(item)
            for item in value.tolist()
        ]

    # --------------------------------------------------------
    # Dict
    # --------------------------------------------------------

    if isinstance(
        value,
        dict,
    ):

        return {
            str(key):
                _json_safe(item)
            for key, item
            in value.items()
        }

    # --------------------------------------------------------
    # List / tuple / set
    # --------------------------------------------------------

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):

        return [
            _json_safe(item)
            for item in value
        ]

    # --------------------------------------------------------
    # Timestamp / datetime / date
    # --------------------------------------------------------

    if isinstance(
        value,
        (
            pd.Timestamp,
            datetime,
            date,
        ),
    ):

        return value.isoformat()

    # --------------------------------------------------------
    # Path
    # --------------------------------------------------------

    if isinstance(
        value,
        Path,
    ):

        return str(value)

    # --------------------------------------------------------
    # Boolean numpy
    # --------------------------------------------------------

    if isinstance(
        value,
        np.bool_,
    ):

        return bool(value)

    # --------------------------------------------------------
    # Inteiros numpy
    # --------------------------------------------------------

    if isinstance(
        value,
        np.integer,
    ):

        return int(value)

    # --------------------------------------------------------
    # Float numpy
    # --------------------------------------------------------

    if isinstance(
        value,
        np.floating,
    ):

        value = float(value)

    # --------------------------------------------------------
    # Float normal
    # --------------------------------------------------------

    if isinstance(
        value,
        float,
    ):

        if not math.isfinite(
            value
        ):
            return None

        return value

    # --------------------------------------------------------
    # Tipos JSON nativos
    # --------------------------------------------------------

    if isinstance(
        value,
        (
            str,
            int,
            bool,
        ),
    ):

        return value

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    return str(value)


# ============================================================
# DATAFRAME → RECORDS
# ============================================================

def _dataframe_to_records(
    dataframe: pd.DataFrame | None,
) -> list[dict]:

    if dataframe is None:
        return []

    if not isinstance(
        dataframe,
        pd.DataFrame,
    ):

        raise TypeError(
            "Objeto esperado como "
            "pandas.DataFrame."
        )

    if dataframe.empty:
        return []

    records = dataframe.to_dict(
        orient="records"
    )

    return [
        {
            str(key):
                _json_safe(value)
            for key, value
            in record.items()
        }
        for record in records
    ]


# ============================================================
# CONTAGEM SEGURA
# ============================================================

def _count_values(
    dataframe: pd.DataFrame | None,
    column: str,
) -> dict:

    if (
        dataframe is None
        or not isinstance(
            dataframe,
            pd.DataFrame,
        )
        or dataframe.empty
        or column
        not in dataframe.columns
    ):

        return {}

    counts = (
        dataframe[column]
        .dropna()
        .astype(str)
        .value_counts(
            dropna=False
        )
        .to_dict()
    )

    return {
        str(key):
            int(value)
        for key, value
        in counts.items()
    }


# ============================================================
# SOMA SEGURA DE COLUNA
# ============================================================

def _sum_column(
    dataframe: pd.DataFrame | None,
    column: str,
) -> float | None:

    if (
        dataframe is None
        or not isinstance(
            dataframe,
            pd.DataFrame,
        )
        or dataframe.empty
        or column
        not in dataframe.columns
    ):

        return None

    values = pd.to_numeric(
        dataframe[column],
        errors="coerce",
    )

    if values.notna().sum() == 0:
        return None

    result = float(
        values.fillna(0.0).sum()
    )

    if not math.isfinite(
        result
    ):
        return None

    return result


# ============================================================
# VALIDAÇÃO ESTRUTURAL
# ============================================================

def _validate_inputs(
    market_data,
    fundamentals,
    institutional,
    signals,
    strategy,
    outputs,
):

    if not isinstance(
        market_data,
        dict,
    ):

        raise TypeError(
            "market_data deve ser dict."
        )

    for name, dataframe in [

        (
            "fundamentals",
            fundamentals,
        ),

        (
            "institutional",
            institutional,
        ),

        (
            "signals",
            signals,
        ),

        (
            "strategy",
            strategy,
        ),

    ]:

        if not isinstance(
            dataframe,
            pd.DataFrame,
        ):

            raise TypeError(
                f"{name} deve ser "
                "pandas.DataFrame."
            )

    if not isinstance(
        outputs,
        dict,
    ):

        raise TypeError(
            "outputs deve ser dict."
        )

    # --------------------------------------------------------
    # O strategy é a saída decisória principal.
    # --------------------------------------------------------

    if strategy.empty:

        raise ValueError(
            "strategy está vazio. "
            "Não é possível exportar "
            "a decisão do motor."
        )

    # --------------------------------------------------------
    # Campos essenciais da estratégia.
    # --------------------------------------------------------

    required_strategy = [

        "ticker",
        "signal",
        "falling_score",
        "confirmations_total",

    ]

    missing_strategy = [

        column
        for column
        in required_strategy
        if column
        not in strategy.columns

    ]

    if missing_strategy:

        raise ValueError(
            "Campos obrigatórios ausentes "
            "em strategy: "
            + ", ".join(
                missing_strategy
            )
        )

    # --------------------------------------------------------
    # Campos essenciais da signal table.
    # --------------------------------------------------------

    if not signals.empty:

        required_signals = [

            "ticker",
            "pullback",
            "pullback_zone",
            "falling_score",
            "falling_risk",
            "confirmations_total",

        ]

        missing_signals = [

            column
            for column
            in required_signals
            if column
            not in signals.columns

        ]

        if missing_signals:

            raise ValueError(
                "Campos obrigatórios ausentes "
                "em signals: "
                + ", ".join(
                    missing_signals
                )
            )


# ============================================================
# RESUMO DO MOTOR
# ============================================================

def _build_summary(
    market_data,
    fundamentals,
    institutional,
    signals,
    strategy,
):

    signal_counts = (
        _count_values(
            strategy,
            "signal",
        )
    )

    falling_risk_counts = (
        _count_values(
            strategy,
            "falling_risk",
        )
    )

    growth_class_counts = (
        _count_values(
            strategy,
            "growth_class",
        )
    )

    pullback_zone_count = 0

    if (
        "pullback_zone"
        in strategy.columns
    ):

        pullback_zone_count = int(
            strategy[
                "pullback_zone"
            ]
            .fillna(False)
            .astype(bool)
            .sum()
        )

    confirmation_executed_count = 0

    if (
        "confirmation_executed"
        in strategy.columns
    ):

        confirmation_executed_count = int(
            strategy[
                "confirmation_executed"
            ]
            .fillna(False)
            .astype(bool)
            .sum()
        )

    return {

        "market_ticker_count":
            len(market_data),

        "fundamentals_count":
            len(fundamentals),

        "institutional_count":
            len(institutional),

        "signals_count":
            len(signals),

        "strategy_count":
            len(strategy),

        "signal_counts":
            signal_counts,

        "falling_risk_counts":
            falling_risk_counts,

        "growth_class_counts":
            growth_class_counts,

        "pullback_zone_count":
            pullback_zone_count,

        "confirmation_executed_count":
            confirmation_executed_count,

        # ----------------------------------------------------
        # Estes valores são SOMENTE agregações dos pesos
        # já calculados pelo próprio motor.
        # Não são novos pesos nem decisões.
        # ----------------------------------------------------

        "initial_weight_sum":
            _sum_column(
                strategy,
                "initial_weight",
            ),

        "confirmation_weight_sum":
            _sum_column(
                strategy,
                "confirmation_weight",
            ),

        "effective_weight_sum":
            _sum_column(
                strategy,
                "effective_weight",
            ),

        "current_cash_weight_sum":
            _sum_column(
                strategy,
                "current_cash_weight",
            ),
    }


# ============================================================
# METADADOS DO MARKET DATA
# ============================================================

def _build_market_summary(
    market_data: dict,
) -> list[dict]:

    result = []

    # --------------------------------------------------------
    # Não exportamos todo o histórico de preço.
    #
    # O histórico pode ser muito grande e não é necessário
    # para o CIO interpretar a decisão já calculada.
    #
    # Exportamos apenas metadados estruturais.
    # --------------------------------------------------------

    for ticker, dataframe in (
        market_data.items()
    ):

        item = {

            "ticker":
                str(ticker),

            "rows":
                0,

            "start_date":
                None,

            "end_date":
                None,
        }

        if isinstance(
            dataframe,
            pd.DataFrame,
        ):

            item[
                "rows"
            ] = len(
                dataframe
            )

            if not dataframe.empty:

                try:

                    item[
                        "start_date"
                    ] = _json_safe(
                        dataframe.index[0]
                    )

                    item[
                        "end_date"
                    ] = _json_safe(
                        dataframe.index[-1]
                    )

                except Exception:

                    pass

        result.append(
            item
        )

    return result


# ============================================================
# CONSTRUÇÃO DO PAYLOAD
# ============================================================

def build_agent_payload(
    market_data,
    fundamentals,
    institutional,
    signals,
    strategy,
    outputs,
):

    # --------------------------------------------------------
    # Validação estrutural.
    # --------------------------------------------------------

    _validate_inputs(

        market_data=
            market_data,

        fundamentals=
            fundamentals,

        institutional=
            institutional,

        signals=
            signals,

        strategy=
            strategy,

        outputs=
            outputs,
    )

    # --------------------------------------------------------
    # IMPORTANTE:
    #
    # Nenhum sort_values() é executado aqui.
    #
    # A ordem de strategy e signals é exatamente
    # a ordem recebida do motor.
    # --------------------------------------------------------

    payload = {

        "source_system":
            SOURCE_SYSTEM,

        "export_version":
            EXPORT_VERSION,

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        # ----------------------------------------------------
        # RESUMO
        # ----------------------------------------------------

        "summary":
            _build_summary(

                market_data=
                    market_data,

                fundamentals=
                    fundamentals,

                institutional=
                    institutional,

                signals=
                    signals,

                strategy=
                    strategy,
            ),

        # ----------------------------------------------------
        # METADADOS DO MERCADO
        #
        # Não duplicamos todo o histórico.
        # ----------------------------------------------------

        "market_data":
            _build_market_summary(
                market_data
            ),

        # ----------------------------------------------------
        # FUNDAMENTOS
        # ----------------------------------------------------

        "fundamentals":
            _dataframe_to_records(
                fundamentals
            ),

        # ----------------------------------------------------
        # SMART MONEY / INSTITUCIONAL
        # ----------------------------------------------------

        "institutional":
            _dataframe_to_records(
                institutional
            ),

        # ----------------------------------------------------
        # SIGNAL TABLE
        #
        # Preserva:
        # pullback
        # falling score
        # falling risk
        # confirmações
        # indicadores técnicos
        # ----------------------------------------------------

        "signals":
            _dataframe_to_records(
                signals
            ),

        # ----------------------------------------------------
        # STRATEGY TABLE
        #
        # Esta é a principal saída operacional.
        #
        # Preserva:
        # signal
        # ranking/order
        # fundamentos
        # pullback
        # falling score
        # confirmações
        # institutional score
        # plano de capital
        # reason
        # ----------------------------------------------------

        "strategy":
            _dataframe_to_records(
                strategy
            ),

        # ----------------------------------------------------
        # OUTPUTS DO REPORT ENGINE
        # ----------------------------------------------------

        "outputs":
            _json_safe(
                outputs
            ),

        # ----------------------------------------------------
        # METADADOS DE AUDITORIA
        # ----------------------------------------------------

        "metadata": {

            "architecture": {

                "pipeline": [

                    "configuration",

                    "market_data",

                    "fundamentals",

                    "institutional",

                    "signals",

                    "strategy",

                    "reports",
                ],

                "decision_layer":
                    "strategy",

                "signal_layer":
                    "signals",

                "institutional_layer":
                    "institutional",

                "fundamental_layer":
                    "fundamentals",
            },

            # ------------------------------------------------
            # CONTRATO DO EXPORTADOR
            # ------------------------------------------------

            "export_policy": {

                "recalculates_market_indicators":
                    False,

                "recalculates_fundamentals":
                    False,

                "recalculates_institutional_score":
                    False,

                "recalculates_pullback":
                    False,

                "recalculates_falling_score":
                    False,

                "recalculates_confirmations":
                    False,

                "recalculates_signals":
                    False,

                "reclassifies_signals":
                    False,

                "recalculates_ranking":
                    False,

                "reorders_ranking":
                    False,

                "recalculates_weights":
                    False,

                "changes_capital_plan":
                    False,

                "changes_confirmation_state":
                    False,

                "removes_waiting_opportunities":
                    False,

                "creates_new_investment_signal":
                    False,

                "executes_broker_orders":
                    False,
            },

            "source_of_truth": {

                "decision":
                    "strategy.signal",

                "ranking":
                    "strategy original order",

                "falling_score":
                    "signals/strategy",

                "confirmations":
                    "signals/strategy",

                "capital_plan":
                    "strategy",

                "institutional_score":
                    "institutional/strategy",
            },
        },
    }

    return _json_safe(
        payload
    )


# ============================================================
# EXPORTAÇÃO
# ============================================================

def export_agent_output(
    market_data,
    fundamentals,
    institutional,
    signals,
    strategy,
    outputs,
    output_file=OUTPUT_FILE,
):

    payload = build_agent_payload(

        market_data=
            market_data,

        fundamentals=
            fundamentals,

        institutional=
            institutional,

        signals=
            signals,

        strategy=
            strategy,

        outputs=
            outputs,
    )

    output_path = Path(
        output_file
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(

            payload,

            file,

            ensure_ascii=False,

            indent=2,

            allow_nan=False,
        )

    # --------------------------------------------------------
    # LOG DE AUDITORIA
    # --------------------------------------------------------

    summary = payload[
        "summary"
    ]

    print()
    print("=" * 80)

    print(
        "INVESTMENT CIO AGENT — "
        "EXPORT GROWTH OPPORTUNITY ENGINE"
    )

    print("=" * 80)

    print(
        f"Source system          : "
        f"{payload['source_system']}"
    )

    print(
        f"Export version         : "
        f"{payload['export_version']}"
    )

    print(
        f"Market tickers         : "
        f"{summary['market_ticker_count']}"
    )

    print(
        f"Fundamentals           : "
        f"{summary['fundamentals_count']}"
    )

    print(
        f"Institutional          : "
        f"{summary['institutional_count']}"
    )

    print(
        f"Signals                : "
        f"{summary['signals_count']}"
    )

    print(
        f"Strategy rows          : "
        f"{summary['strategy_count']}"
    )

    print(
        f"Signal distribution    : "
        f"{summary['signal_counts']}"
    )

    print(
        f"Pullback zone          : "
        f"{summary['pullback_zone_count']}"
    )

    print(
        f"Confirmations executed : "
        f"{summary['confirmation_executed_count']}"
    )

    print(
        f"Initial weight sum     : "
        f"{summary['initial_weight_sum']}"
    )

    print(
        f"Effective weight sum   : "
        f"{summary['effective_weight_sum']}"
    )

    print(
        f"Current cash sum       : "
        f"{summary['current_cash_weight_sum']}"
    )

    print(
        f"Output file            : "
        f"{output_path}"
    )

    print("=" * 80)

    return payload
