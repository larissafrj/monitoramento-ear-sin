# 💧 monitoramento-ear-sin

Dashboard interativo para acompanhamento diário da **Energia Armazenada nos Reservatórios (EAR)** do Sistema Interligado Nacional (SIN), com dados abertos do [ONS](https://dados.ons.org.br).

---

## ✨ Funcionalidades

- Visualização da EAR (%) por subsistema — N, NE, SE, S e SIN
- Comparação entre anos e climatologia histórica (média 2000–2025)
- Cards com a situação mais recente de cada subsistema
- Tabela de fechamento mensal

## 🛠 Tecnologias

| | |
|---|---|
| Interface | [Streamlit](https://streamlit.io) |
| Visualização | [Plotly](https://plotly.com/python) |
| Dados | [ONS – Dados Abertos](https://dados.ons.org.br) |
| Linguagem | Python 3.10+ |

## 🚀 Como executar

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/monitoramento-ear-sin.git
cd monitoramento-ear-sin

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Rode o app
streamlit run app_ear.py
```

## 📂 Estrutura

```
├── app_ear.py               # Dashboard Streamlit
├── organiza_dataframes.py   # Ingestão e transformação dos dados
└── requirements.txt
```

---

> Dados atualizados automaticamente via API pública do ONS.
