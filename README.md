# GROWTH OPPORTUNITY ENGINE

Sistema quantitativo para identificação de oportunidades em empresas de crescimento após correções relevantes de preço.

O objetivo do projeto é localizar empresas com **crescimento fundamentalista forte**, avaliar o contexto da queda, buscar sinais de participação institucional e classificar a oportunidade de entrada por meio de regras quantitativas validadas historicamente.

---

## 1. Filosofia do sistema

O GROWTH OPPORTUNITY ENGINE não procura simplesmente ações que caíram.

A lógica central é:

> **Crescimento forte + correção relevante + qualidade da queda + confirmação institucional + gestão do timing.**

O sistema procura diferenciar uma oportunidade de crescimento temporariamente descontada de uma possível deterioração estrutural.

---

## 2. Origem da estratégia

As regras operacionais foram desenvolvidas a partir de estudo histórico com eventos de empresas de crescimento.

A amostra final utilizada no backtest consolidado apresentou:

- 77 eventos;
- 18 empresas;
- período com retornos completos entre 2015 e 2024;
- análise fundamentalista;
- comportamento do preço;
- volume;
- Smart Money;
- distância das médias;
- velocidade da queda;
- timing de entrada;
- drawdown;
- retorno futuro;
- comparação com o SPY;
- testes temporais;
- bootstrap estatístico.

As regras finais foram congeladas antes do backtest final.

---

## 3. Resultado do backtest final

A estratégia final executou 54 das 77 oportunidades avaliadas.

### Operações executadas

| Métrica | Resultado |
|---|---:|
| Operações | 54 |
| Empresas | 18 |
| Retorno mediano 3 meses | 7,16% |
| Retorno mediano 6 meses | 16,07% |
| Retorno mediano 12 meses | 34,26% |
| Retorno médio 12 meses | 41,37% |
| Alpha mediano 12 meses | 10,71% |
| Win rate 12 meses | 81,5% |
| Bateu SPY | 66,7% |
| Drawdown mediano 6 meses | -17,33% |
| Perdas superiores a 20% | 5,6% |

### Benchmark: comprar todos os eventos

| Métrica | Regra Final | Todos os Eventos |
|---|---:|---:|
| Retorno mediano 12M | 34,26% | 29,67% |
| Alpha mediano 12M | 10,71% | 7,80% |
| Win rate | 81,5% | 76,6% |
| Perdas >20% | 5,6% | 11,7% |
| MDD mediano | -17,33% | -20,59% |

A regra de seleção apresentou melhora simultânea de retorno mediano, alpha, taxa de acerto e controle das perdas graves dentro da amostra estudada.

---

## 4. Arquitetura

O projeto foi mantido propositalmente enxuto.

```text
GROWTH_OPPORTUNITY_ENGINE/
│
├── main.py
├── config.py
├── requirements.txt
├── README.md
│
├── engine/
│   ├── __init__.py
│   ├── data.py
│   ├── fundamentals.py
│   ├── institutional.py
│   ├── signals.py
│   ├── strategy.py
│   └── report.py
│
├── data/
│   └── history.csv
│
├── output/
│   ├── opportunities.csv
│   └── report.pdf
│
└── .github/
    └── workflows/
        └── scanner.yml
```

---

## 5. Pipeline

O processamento segue uma sequência definida.

```text
UNIVERSO
   ↓
DADOS DE MERCADO
   ↓
FUNDAMENTOS
   ↓
CORREÇÃO DE PREÇO
   ↓
SMART MONEY
   ↓
FALLING KNIFE / RISCO
   ↓
SCORE
   ↓
DECISÃO OPERACIONAL
   ↓
RELATÓRIO
```

A ordem é importante.

O sistema não deve transformar um sinal técnico isolado em oportunidade caso a tese fundamentalista não esteja presente.

---

## 6. Fundamentos

A análise fundamentalista tem prioridade na estratégia.

Entre as variáveis avaliadas estão:

- crescimento de receita;
- crescimento de lucro/EPS;
- persistência do crescimento;
- qualidade fundamentalista;
- disponibilidade dos dados.

A finalidade é procurar empresas cujo crescimento empresarial continue justificando investigação mesmo depois de uma queda relevante das ações.

---

## 7. Correção de preço

O engine procura eventos de queda relevantes.

Uma queda isoladamente não representa sinal de compra.

Ela funciona como o evento que inicia a análise.

Depois da correção, o sistema verifica se existem características que indiquem oportunidade ou risco de continuação da deterioração.

---

## 8. Smart Money

O módulo institucional utiliza sinais de mercado como confirmação.

Entre eles:

- volume relativo;
- dias de acumulação;
- OBV;
- divergência;
- reversão.

O Smart Money é utilizado como **reforço da análise**, e não como filtro eliminatório independente.

---

## 9. Falling Knife

Um dos principais resultados do estudo foi a importância da velocidade da queda.

O sistema utiliza um **Falling Knife Score** para diferenciar quedas mais controladas de movimentos ainda potencialmente desorganizados.

No estudo histórico:

| Classe | Retorno mediano 12M | Win rate | Armadilhas |
|---|---:|---:|---:|
| Baixo | 40,60% | 90,5% | 0,0% |
| Moderado | 28,80% | 73,3% | 10,0% |
| Alto | 19,60% | 69,2% | 23,1% |

Portanto, velocidade e estrutura da queda são tratadas como componentes de risco.

---

## 10. SMA50

A média móvel de 50 períodos não é utilizada como previsão de preço.

Ela funciona principalmente como referência para:

- contexto da tendência;
- distância do preço;
- confirmação;
- dimensionamento da entrada.

O estudo mostrou que esperar integralmente pela confirmação pode reduzir retorno.

Por isso, a estratégia utiliza entrada parcial em determinadas situações.

---

## 11. Decisões

O sistema produz três decisões principais:

### ENTRADA FORTE

Oportunidade que atende aos critérios mais fortes da estratégia.

Regra operacional:

```text
100% da posição planejada
```

### ENTRADA PARCIAL

A empresa mantém características suficientes para entrada, mas existe risco adicional.

Regra operacional:

```text
60% no evento
40% após confirmação SMA50
```

Caso a confirmação não aconteça, a parcela restante permanece em caixa.

### AGUARDAR

A relação entre oportunidade e risco ainda não é suficiente.

Regra:

```text
0% investido
100% em caixa
```

AGUARDAR não significa necessariamente empresa ruim.

Significa que a oportunidade ainda não atende às condições exigidas pela estratégia.

---

## 12. Execução

Para executar localmente:

```bash
pip install -r requirements.txt
python main.py
```

---

## 13. GitHub Actions

O projeto possui execução automatizada através do GitHub Actions.

Também é possível executar manualmente:

```text
GitHub
→ Actions
→ Growth Opportunity Engine
→ Run workflow
```

O workflow executa o pipeline e disponibiliza os resultados gerados.

---

## 14. Arquivos de saída

### opportunities.csv

Contém as oportunidades analisadas e suas respectivas classificações.

### report.pdf

Relatório consolidado da execução.

### history.csv

Mantém o histórico das análises para permitir auditoria posterior das decisões produzidas pelo engine.

---

## 15. Princípios de segurança quantitativa

O projeto segue alguns princípios fundamentais:

1. dados futuros não devem participar da geração do sinal;
2. retorno futuro serve apenas para backtest;
3. fundamentos possuem prioridade;
4. Smart Money é confirmação;
5. indicadores técnicos não devem substituir fundamentos;
6. Falling Knife é tratado como risco;
7. capital não confirmado permanece em caixa;
8. regras operacionais devem permanecer separadas da validação histórica;
9. alterações relevantes na estratégia exigem novo backtest;
10. desempenho histórico não garante desempenho futuro.

---

## 16. Objetivo operacional

O GROWTH OPPORTUNITY ENGINE foi desenvolvido para responder uma pergunta:

> **Entre empresas de crescimento que sofreram correções relevantes, quais apresentam características suficientes para justificar uma entrada agora, uma entrada parcial ou simplesmente aguardar?**

A resposta final deve ser simples:

```text
ENTRADA FORTE
ENTRADA PARCIAL
AGUARDAR
```

Toda a complexidade quantitativa existe para melhorar a qualidade dessa decisão.

---

## Disclaimer

Este projeto possui finalidade quantitativa, educacional e de pesquisa.

Os resultados gerados pelo sistema não constituem recomendação individual de investimento.

Resultados históricos, backtests, scores e classificações não garantem desempenho futuro.

Decisões de investimento envolvem risco e devem considerar objetivos, patrimônio, horizonte e tolerância a perdas do investidor.
