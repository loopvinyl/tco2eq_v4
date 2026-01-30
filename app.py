import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import warnings
import math
import re

warnings.filterwarnings("ignore")

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Mercado de Carbono para Propriedades Rurais - Baseado em Dados Reais FAO",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# FUNÇÕES DE FORMATAÇÃO
# =========================

def formatar_br_dec(numero, decimais=2):
    if pd.isna(numero):
        return "N/A"
    numero = round(float(numero), decimais)
    return f"{numero:,.{decimais}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_br_inteiro(numero):
    if pd.isna(numero):
        return "N/A"
    return f"{int(numero):,}".replace(",", "X").replace(".", ",").replace("X", ".")

# =========================
# FUNÇÕES AUXILIARES
# =========================

def convert_to_numeric(value):
    try:
        if pd.isna(value):
            return None
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except:
        return None

def extract_year_from_value(value):
    if pd.isna(value):
        return None
    match = re.search(r"(19|20)\d{2}", str(value))
    return int(match.group()) if match else None

def get_country_name(value):
    if not value:
        return "Não especificado"
    return str(value).strip().title()

def clean_dataframe(df):
    df = df.copy()
    df = df.dropna(axis=1, how="all")
    df = df.dropna(how="all")
    df.reset_index(drop=True, inplace=True)
    return df

# =========================================================
# 🔥 NOVA FUNÇÃO — TOTAIS OFICIAIS DO MERCADO (FAO)
# =========================================================

def extract_global_totals_from_standards(dataframes):
    """
    Fonte única:
    Aba '1. Standards' — linha 'TOTALS'
    """
    totals = {
        "projetos_registrados": 0,
        "creditos_emitidos": 0,
        "creditos_aposentados": 0
    }

    if "1. Standards" not in dataframes:
        return totals

    df = clean_dataframe(dataframes["1. Standards"])

    for _, row in df.iterrows():
        nome = str(row.get("Name of standard/registry/platform", "")).upper()
        if nome == "TOTALS":
            totals["projetos_registrados"] = convert_to_numeric(
                row.get("Total registered projects")
            ) or 0
            totals["creditos_emitidos"] = convert_to_numeric(
                row.get("Total credits issued")
            ) or 0
            totals["creditos_aposentados"] = convert_to_numeric(
                row.get("Total credits retired")
            ) or 0
            break

    return totals

# =========================================================
# ANÁLISE COMPLETA DO DATASET
# =========================================================

@st.cache_data(ttl=3600)
def analyze_complete_dataset(dataframes):

    analysis = {
        "estatisticas_gerais": {},
        "comparativo_emitidos_vs_aposentados": {
            "total_emitido": 0,
            "total_aposentado": 0
        }
    }

    # -----------------------------------------------------
    # ANÁLISE ORIGINAL (mantida)
    # -----------------------------------------------------

    for sheet, df in dataframes.items():
        df = clean_dataframe(df)
        for _, row in df.iterrows():
            emitidos = convert_to_numeric(row.get("Total credits issued")) or 0
            aposentados = convert_to_numeric(row.get("Total credits retired")) or 0

            analysis["comparativo_emitidos_vs_aposentados"]["total_emitido"] += emitidos
            analysis["comparativo_emitidos_vs_aposentados"]["total_aposentado"] += aposentados

    # -----------------------------------------------------
    # 🔥 AJUSTE FINAL — TOTAIS OFICIAIS DO MERCADO
    # -----------------------------------------------------

    official_totals = extract_global_totals_from_standards(dataframes)

    emitidos = official_totals["creditos_emitidos"]
    aposentados = official_totals["creditos_aposentados"]

    analysis["estatisticas_gerais"] = {
        "total_projetos": official_totals["projetos_registrados"],
        "creditos_emitidos": emitidos,
        "creditos_aposentados": aposentados,
        "taxa_aposentadoria": (aposentados / emitidos * 100) if emitidos > 0 else 0
    }

    return analysis

# =========================================================
# STREAMLIT — CARGA E EXECUÇÃO
# =========================================================

st.title("🌱 Mercado Voluntário de Carbono — Visão Global")

uploaded_file = st.file_uploader("Upload do Dataset FAO (.xlsx)", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    dataframes = {sheet: xls.parse(sheet) for sheet in xls.sheet_names}

    analysis = analyze_complete_dataset(dataframes)

    st.metric(
        "Projetos registrados (mercado voluntário)",
        formatar_br_inteiro(analysis["estatisticas_gerais"]["total_projetos"])
    )

    st.metric(
        "Créditos emitidos",
        formatar_br_inteiro(analysis["estatisticas_gerais"]["creditos_emitidos"])
    )

    st.metric(
        "Créditos aposentados",
        formatar_br_inteiro(analysis["estatisticas_gerais"]["creditos_aposentados"])
    )

    st.metric(
        "Taxa de aposentadoria (%)",
        formatar_br_dec(analysis["estatisticas_gerais"]["taxa_aposentadoria"], 1)
    )
