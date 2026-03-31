"""
app_ear.py
==========
Dashboard Streamlit – Energia Armazenada dos Reservatórios (EAR)
Dados: ONS – Operador Nacional do Sistema Elétrico

Execute com:
    streamlit run app_ear.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import organiza_dataframes as od

# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="EAR · Reservatórios Brasil",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS customizado – paleta industrial/técnica, tipografia limpa
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap');

    /* ---- base ---- */
    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        background-color: #0d1117;
        color: #c9d1d9;
    }

    /* ---- sidebar ---- */
    [data-testid="stSidebar"] {
        background-color: #91a8c7;
        border-right: 1px solid #6a89aa;
    }
    [data-testid="stSidebar"] * { color: #0d1f30 !important; }
    [data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] {
        background-color: #1f6feb !important;
        border-radius: 4px;
    }

    /* ---- títulos ---- */
    h1, h2, h3 { font-family: 'Space Mono', monospace; letter-spacing: -0.5px; }
    h1 { font-size: 1.7rem !important; color: #58a6ff; }
    h2 { font-size: 1.1rem !important; color: #79c0ff; }

    /* ---- metric cards ---- */
    [data-testid="metric-container"] {
        background: #d6dadf;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 16px 20px;
    }
    [data-testid="metric-container"] label {
        font-size: 0.72rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #8b949e !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'Space Mono', monospace;
        font-size: 1.9rem !important;
        color: #f0f6fc !important;
    }

    /* ---- divider ---- */
    hr { border-color: #21262d; }

    /* ---- slider label ---- */
    .stSlider label { color: #8b949e !important; font-size: 0.8rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SUBSISTEMAS     = ["N", "NE", "SE", "S", "SIN"]
COR_POR_SERIE   = [
    "#58a6ff", "#3fb950", "#f78166", "#d2a8ff",
    "#ffa657", "#79c0ff", "#56d364", "#ff7b72","#e3b341", # Amarelo/Dourado
    "#39c5cf", # Ciano/Turquesa
    "#f692ce", # Rosa/Magenta
    "#a371f7", # Roxo Profundo
    "#238636", # Verde Escuro
    "#1f6feb", # Azul Royal
    "#bd561d", # Laranja Queimado
    "#6e7681",
]
ANO_CLIMATOLOGIA = 1904
LABEL_CLIMATOLOGIA = "Climatologia (Média)"

# ---------------------------------------------------------------------------
# Funções auxiliares de visualização
# ---------------------------------------------------------------------------


def _label_ano(ano: int) -> str:
    return LABEL_CLIMATOLOGIA if ano == ANO_CLIMATOLOGIA else str(ano)


def _filtra_subsistema_ano(
    ear_percent: pd.DataFrame, subsistema: str, ano: int
) -> pd.DataFrame:
    """Filtra e formata uma fatia do DataFrame para um (subsistema, ano)."""
    mask = (ear_percent["id_subsistema"] == subsistema) & (
        ear_percent["ear_data"].dt.year == ano
    )
    df = ear_percent.loc[mask].copy()
    df["data_str"] = df["ear_data"].dt.strftime("%d %b")
    df = df[df["data_str"] != "29 Feb"]          # remove 29/Fev de anos bissextos
    df = df.sort_values("ear_data")
    return df


def _ultimo_valor(ear_percent: pd.DataFrame, subsistema: str) -> tuple[float | None, str]:
    """Retorna o valor mais recente de EAR% para um subsistema (excluindo climatologia)."""
    df = ear_percent[
        (ear_percent["id_subsistema"] == subsistema)
        & (ear_percent["ear_data"].dt.year != ANO_CLIMATOLOGIA)
    ]
    if df.empty:
        return None, "–"
    row = df.sort_values("ear_data").iloc[-1]
    return row["ear_verif_subsistema_percentual"], row["ear_data"].strftime("%d/%m/%Y")


def _cor_percentual(valor: float | None) -> str:
    if valor is None:
        return "#8b949e"
    if valor >= 60:
        return "#3fb950"
    if valor >= 30:
        return "#ffa657"
    return "#f78166"


# ---------------------------------------------------------------------------
# Carregamento de dados
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _carrega_dados() -> pd.DataFrame:
    tabela      = od.retorna_historico_EAR_subsistema()
    ear_percent = od.retorna_historico_EAR_subsistema_com_SIN(tabela)
    return ear_percent


# ---------------------------------------------------------------------------
# Sidebar – controles
# ---------------------------------------------------------------------------


def _sidebar(anos_disponiveis: list[int]) -> tuple[str, list[int]]:
    with st.sidebar:
        st.markdown("## 💧 EAR · Filtros")
        st.markdown("---")

        subsistema = st.selectbox(
            "Subsistema",
            SUBSISTEMAS,
            index=SUBSISTEMAS.index("SE"),
        )

        st.markdown("**Anos para comparação**")

        # Opção rápida de mostrar climatologia
        mostrar_climatologia = st.checkbox("Incluir Climatologia (média hist.)", value=True)

        # Range de anos via slider duplo
        ano_min_dados = min(a for a in anos_disponiveis if a != ANO_CLIMATOLOGIA)
        ano_max_dados = max(a for a in anos_disponiveis if a != ANO_CLIMATOLOGIA)

        intervalo = st.slider(
            "Intervalo de anos",
            min_value=ano_min_dados,
            max_value=ano_max_dados,
            value=(ano_max_dados - 4, ano_max_dados),
            step=1,
        )
        anos_selecionados = list(range(intervalo[0], intervalo[1] + 1))

        if mostrar_climatologia:
            anos_selecionados = [ANO_CLIMATOLOGIA] + anos_selecionados

        st.markdown("---")
        st.caption("Fonte: ONS – Dados Abertos  \nhttps://dados.ons.org.br")

    return subsistema, anos_selecionados


# ---------------------------------------------------------------------------
# Construção do gráfico principal
# ---------------------------------------------------------------------------


def _build_figure(
    ear_percent: pd.DataFrame,
    subsistema: str,
    anos: list[int],
) -> go.Figure:
    fig = go.Figure()

    for idx, ano in enumerate(anos):
        df = _filtra_subsistema_ano(ear_percent, subsistema, ano)
        if df.empty:
            continue

        label = _label_ano(ano)
        cor   = COR_POR_SERIE[idx % len(COR_POR_SERIE)]

        # Climatologia: linha tracejada mais grossa em cinza claro
        if ano == ANO_CLIMATOLOGIA:
            fig.add_trace(
                go.Scatter(
                    x=df["data_str"],
                    y=df["ear_verif_subsistema_percentual"].round(1),
                    name=label,
                    mode="lines",
                    line=dict(color="#8b949e", width=2.5, dash="dot"),
                    hovertemplate="%{x}<br><b>%{y:.1f}%</b> (média)<extra></extra>",
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=df["data_str"],
                    y=df["ear_verif_subsistema_percentual"].round(1),
                    name=label,
                    mode="lines",
                    line=dict(color=cor, width=2),
                    hovertemplate=f"%{{x}}<br><b>%{{y:.1f}}%</b> ({ano})<extra></extra>",
                )
            )

    # Layout
    anos_reais = [a for a in anos if a != ANO_CLIMATOLOGIA]
    titulo = (
        f"Evolução da EAR — Subsistema {subsistema}"
        + (f"  ·  {anos_reais[0]}–{anos_reais[-1]}" if anos_reais else "")
    )

    fig.update_layout(
        title=dict(text=titulo, x=0.01, font=dict(family="Space Mono", size=16, color="#01060c")),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#d6dadf",
        font=dict(family="DM Sans", color="#01060c"),
        legend=dict(
            bgcolor="#d6dadf",
            bordercolor="#21262d",
            borderwidth=1,
            font=dict(size=12),
            orientation="v",
            x=1.015, y=1,
        ),
        hovermode="x unified",
        margin=dict(l=10, r=10, t=50, b=50),
        yaxis=dict(
            title="EAR (%)",
            gridcolor="#7c7e81",
            zerolinecolor="#7c7e81",
            tickfont=dict(size=12),
        ),
        xaxis=dict(
            gridcolor="#7c7e81",
            tickfont=dict(size=11),
            tickmode="array",
            tickvals=_ticks_mensais(ear_percent, subsistema, anos),
        ),
    )
    return fig


def _ticks_mensais(ear_percent: pd.DataFrame, subsistema: str, anos: list[int]) -> list[str]:
    """Retorna labels mensais (1º de cada mês) para o eixo X."""
    ano_ref = next((a for a in anos if a != ANO_CLIMATOLOGIA), ANO_CLIMATOLOGIA)
    df = _filtra_subsistema_ano(ear_percent, subsistema, ano_ref)
    if df.empty and ANO_CLIMATOLOGIA in anos:
        df = _filtra_subsistema_ano(ear_percent, subsistema, ANO_CLIMATOLOGIA)
    primeiros = df[df["ear_data"].dt.day == 1]["data_str"].tolist()
    return primeiros if primeiros else df["data_str"].values[::30].tolist()


# ---------------------------------------------------------------------------
# Cards de métricas
# ---------------------------------------------------------------------------


def _render_metrics(ear_percent: pd.DataFrame) -> None:
    cols = st.columns(len(SUBSISTEMAS))
    for col, sub in zip(cols, SUBSISTEMAS):
        valor, data = _ultimo_valor(ear_percent, sub)
        cor = _cor_percentual(valor)
        with col:
            st.markdown(
                f"""
                <div style="
                    background:#d6dadf; border:1px solid #21262d; border-radius:8px;
                    padding:14px 16px; text-align:center;
                ">
                    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:#8b949e;">{sub}</div>
                    <div style="font-family:'Space Mono',monospace;font-size:2rem;color:{cor};line-height:1.2;">
                        {"–" if valor is None else f"{valor:.1f}%"}
                    </div>
                    <div style="font-size:.7rem;color:#484f58;">{data}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# App principal
# ---------------------------------------------------------------------------


def main() -> None:
    # ---- Cabeçalho ----
    st.markdown("# 💧 Energia Armazenada dos Reservatórios")
    st.markdown(
        "<span style='color:#8b949e;font-size:.9rem;'>"
        "Monitoramento diário do nível dos reservatórios do Sistema Interligado Nacional (SIN) · ONS"
        "</span>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ---- Dados ----
    with st.spinner("Carregando dados históricos de EAR…"):
        ear_percent = _carrega_dados()

    if ear_percent.empty:
        st.error("Não foi possível carregar os dados. Verifique sua conexão com a internet.")
        return

    anos_disponiveis = sorted(ear_percent["ear_data"].dt.year.unique().tolist())

    # ---- Sidebar ----
    subsistema, anos_selecionados = _sidebar(anos_disponiveis)

    # ---- Métricas do dia mais recente ----
    st.markdown("### Situação Atual dos Reservatórios")
    _render_metrics(ear_percent)

    st.markdown("---")

    # ---- Gráfico principal ----
    st.markdown("### Série Histórica Comparativa")

    if not anos_selecionados:
        st.warning("Selecione ao menos um ano no painel lateral.")
        return

    fig = _build_figure(ear_percent, subsistema, anos_selecionados)
    st.plotly_chart(fig, use_container_width=True)

    # ---- Tabela de fechamento mensal (expansível) ----
    with st.expander("📋 Fechamento mensal (último dia do mês)"):
        anos_reais = [a for a in anos_selecionados if a != ANO_CLIMATOLOGIA]
        if anos_reais:
            df_sub = ear_percent[
                (ear_percent["id_subsistema"] == subsistema)
                & (ear_percent["ear_data"].dt.year.isin(anos_reais))
            ]
            fechamento = od.retorna_fechamento_dos_meses(df_sub)
            fechamento = fechamento.rename(
                columns={
                    "ear_data": "Mês",
                    "id_subsistema": "Subsistema",
                    "ear_verif_subsistema_percentual": "EAR (%)",
                }
            )
            st.dataframe(
                fechamento[["Mês", "EAR (%)"]].sort_values("Mês"),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Selecione ao menos um ano real para ver o fechamento mensal.")

    # ---- Rodapé ----
    st.markdown("---")
    st.caption(
        "Dados: [ONS – Dados Abertos](https://dados.ons.org.br) · "
        "Atualização automática a cada hora · "
        "Desenvolvido com Streamlit + Plotly"
    )


if __name__ == "__main__":
    main()