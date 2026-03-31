"""
organiza_dataframes.py
======================
Módulo de ingestão e transformação dos dados de EAR (Energia Armazenada
Reservatório) por subsistema – ONS Dados Abertos.

Otimizações em relação à versão original:
  - Leitura via Parquet (mais rápido e menor consumo de memória que CSV).
  - Cache com @st.cache_data para evitar re-downloads desnecessários.
  - Uso de vectorized ops no lugar de apply() onde possível.
  - Tipagem explícita e docstrings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime
from calendar import monthrange


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BASE_URL = (
    "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/"
    "ear_subsistema_di/EAR_DIARIO_SUBSISTEMA_{year}.parquet"
)
ANO_INICIO = 2000
ANO_FIM    = int(datetime.today().year)
SUBSISTEMAS = ["N", "NE", "SE", "S"]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _url(year: int) -> str:
    return BASE_URL.format(year=year)


def _normaliza_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante que as colunas essenciais existem e têm o tipo correto.

    Alguns arquivos Parquet da ONS armazenam colunas numéricas como object/string
    (vírgula decimal ou metadados de schema inconsistentes entre anos).
    pd.to_numeric com errors='coerce' converte qualquer valor inválido para NaN
    em vez de lançar exceção.
    """
    df = df.copy()
    df["ear_data"] = pd.to_datetime(df["ear_data"], errors="coerce")

    cols_numericas = [
        "ear_max_subsistema",
        "ear_verif_subsistema_mwmes",
        "ear_verif_subsistema_percentual",
    ]
    for col in cols_numericas:
        if col in df.columns:
            # Substitui vírgula decimal (padrão BR) por ponto antes de converter
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce")

    cols_keep = ["id_subsistema", "ear_data"] + cols_numericas
    return df[[c for c in cols_keep if c in df.columns]]


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Carregando dados históricos de EAR…", ttl=3600)
def retorna_historico_EAR_subsistema() -> pd.DataFrame:
    """
    Baixa e consolida os dados diários de EAR por subsistema de
    ANO_INICIO até ANO_FIM (inclusive), acrescentando a climatologia
    (média histórica representada como ano 1904).

    Returns
    -------
    pd.DataFrame
        Colunas: id_subsistema, ear_data, ear_max_subsistema,
                 ear_verif_subsistema_mwmes, ear_verif_subsistema_percentual
    """
    frames: list[pd.DataFrame] = []
    for year in range(ANO_INICIO, ANO_FIM + 1):
        try:
            df = pd.read_parquet(_url(year))
            frames.append(_normaliza_colunas(df))
        except Exception:
            # Ano ainda sem dados ou URL indisponível – ignora silenciosamente
            continue

    if not frames:
        return pd.DataFrame()

    historico = pd.concat(frames, ignore_index=True)
    climatologia = _calcula_climatologia(historico)
    tabela = pd.concat([climatologia, historico], ignore_index=True)
    tabela["ear_data"] = pd.to_datetime(tabela["ear_data"])
    return tabela.reset_index(drop=True)


def _calcula_climatologia(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula a média histórica por (subsistema, dia, mês) e representa
    os registros no ano fictício 1904 (ano base da climatologia).
    """
    df = df[df["ear_data"].dt.year != 1904].copy()  # exclui eventual climatologia já presente
    df["_dia"]  = df["ear_data"].dt.day
    df["_mes"]  = df["ear_data"].dt.month

    cols_num = ["ear_max_subsistema", "ear_verif_subsistema_mwmes", "ear_verif_subsistema_percentual"]
    # numeric_only=True evita o TypeError em pandas >= 2.0 quando colunas object estão presentes
    grp = (
        df.groupby(["id_subsistema", "_dia", "_mes"])[cols_num]
        .mean(numeric_only=True)
        .reset_index()
    )

    # Reconstrói a coluna de data com ano fictício 1904
    grp["ear_data"] = pd.to_datetime(
        grp.apply(lambda r: f"1904-{int(r['_mes']):02d}-{int(r['_dia']):02d}", axis=1),
        errors="coerce",
    )
    grp = grp.dropna(subset=["ear_data"])
    return grp[
        ["id_subsistema", "ear_data", "ear_max_subsistema",
         "ear_verif_subsistema_mwmes", "ear_verif_subsistema_percentual"]
    ].sort_values("ear_data")


@st.cache_data(show_spinner=False, ttl=3600)
def retorna_historico_EAR_subsistema_com_SIN(
    tabela: pd.DataFrame,
) -> pd.DataFrame:
    """
    Acrescenta o agregado SIN (Sistema Interligado Nacional) ao DataFrame
    de subsistemas e retorna apenas as colunas de percentual de EAR.

    Parameters
    ----------
    tabela : pd.DataFrame
        Saída de `retorna_historico_EAR_subsistema`.

    Returns
    -------
    pd.DataFrame
        Colunas: id_subsistema, ear_data, ear_verif_subsistema_percentual
    """
    pivot = tabela.pivot_table(
        index="ear_data", columns="id_subsistema", aggfunc="first"
    )

    mwmes  = pivot["ear_verif_subsistema_mwmes"]
    maxima = pivot["ear_max_subsistema"]

    # SIN = soma dos 4 subsistemas
    sin_verif = mwmes[SUBSISTEMAS].sum(axis=1)
    sin_max   = maxima[SUBSISTEMAS].sum(axis=1)
    sin_pct   = (sin_verif / sin_max * 100).round(2).rename("ear_verif_subsistema_percentual")

    sin_df = sin_pct.reset_index()
    sin_df["id_subsistema"] = "SIN"

    base = tabela[["id_subsistema", "ear_data", "ear_verif_subsistema_percentual"]].copy()
    resultado = pd.concat([base, sin_df], ignore_index=True)
    resultado["ear_data"] = pd.to_datetime(resultado["ear_data"])
    return resultado


def retorna_fechamento_dos_meses(ear_percent: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra apenas os registros do último dia de cada mês/ano.

    Returns
    -------
    pd.DataFrame com ear_data formatada como 'MM/YYYY' (ex.: '01/2024').
    """
    # Datas do último dia de cada (ano, mês) presentes nos dados
    anos  = ear_percent["ear_data"].dt.year.unique()
    meses = ear_percent["ear_data"].dt.month.unique()

    ultimos_dias = pd.to_datetime([
        datetime(ano, mes, monthrange(ano, mes)[1])
        for ano in anos
        for mes in meses
    ])

    fechamento = ear_percent[ear_percent["ear_data"].isin(ultimos_dias)].copy()
    fechamento["ear_data"] = fechamento["ear_data"].dt.strftime("%m/%Y")
    return fechamento
