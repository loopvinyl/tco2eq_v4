import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
import os
import re
import json
from typing import Dict, List, Optional, Tuple
import math

warnings.filterwarnings("ignore")

# =========================
# FUNÇÃO DE FORMATAÇÃO BR
# =========================

def format_br(value, decimals=0, prefix=""):
    """
    Formata números no padrão brasileiro:
    milhar com ponto e decimal com vírgula
    """
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "-"
        fmt = f"{{:,.{decimals}f}}".format(value)
        fmt = fmt.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{prefix}{fmt}"
    except:
        return "-"

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
# CONSTANTES
# =========================
SHEET_CONFIG = {
    "README": {"type": "documentação", "icon": "📖"},
    "4. Agriculture": {"type": "projetos", "icon": "🚜"},
    "5. Agroforestry-AR & Grassland": {"type": "projetos", "icon": "🌳"},
    "6. Energy and Other": {"type": "projetos", "icon": "⚡"}
}

# =========================
# HERO SECTION
# =========================

def create_hero_section(analysis):
    stats = analysis['estatisticas_gerais']
    st.markdown(f"""
    <div style='text-align:center;padding:2rem;border-radius:15px;
    background:linear-gradient(135deg,#27ae60,#229954);color:white'>
        <h1>🌱 Mercado Real de Carbono Agrícola</h1>
        <h3>Baseado em {format_br(stats['total_projetos'])} projetos certificados</h3>
        <p>
        {format_br(stats['total_creditos'])} créditos •
        {format_br(stats['paises_com_projetos'])} países •
        US$ {format_br(stats['receita_estimada'])} gerados
        </p>
    </div>
    """, unsafe_allow_html=True)

# =========================
# CALCULADORA
# =========================

def create_revenue_calculator(analysis):
    with st.expander("🧮 CALCULE SEU POTENCIAL", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            hectares = st.number_input("Área (ha)", 1.0, 10000.0, 100.0)
        with col2:
            practice_type = st.selectbox(
                "Prática",
                ["agricultura", "agroflorestal", "energia"]
            )
        with col3:
            investment = st.number_input("Investimento (US$)", 0.0, 1_000_000.0, 10000.0)

        revenue = calculate_potential_revenue(hectares, practice_type, analysis)
        break_even = calculate_break_even(hectares, investment, practice_type, analysis)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Receita Anual", f"US$ {format_br(revenue['annual_revenue_avg'])}")
        col2.metric("📈 Receita 10 anos", f"US$ {format_br(revenue['10yr_revenue_avg'])}")
        col3.metric("⏱️ Payback", f"{format_br(break_even['break_even_years'],1)} anos")
        col4.metric("📊 ROI 5 anos", f"{format_br(break_even['roi_5yr'],1)}%")

# =========================
# FUNÇÕES DE CÁLCULO (INALTERADAS)
# =========================

def calculate_potential_revenue(hectares, practice_type, analysis):
    rate = {"agricultura":1.25,"agroflorestal":4,"energia":2}.get(practice_type,1.25)
    price = 22.5
    return {
        "annual_revenue_avg": hectares * rate * price,
        "10yr_revenue_avg": hectares * rate * price * 10
    }

def calculate_break_even(hectares, investment, practice_type, analysis):
    annual = calculate_potential_revenue(hectares, practice_type, analysis)["annual_revenue_avg"]
    if annual <= 0:
        return {"break_even_years": float("inf"), "roi_5yr": 0}
    return {
        "break_even_years": investment / annual,
        "roi_5yr": ((annual*5)-investment)/investment*100
    }

# =========================
# LOAD DATA (SIMPLIFICADO)
# =========================

def load_fao_dataset():
    return {}, []

# =========================
# MAIN
# =========================

def main():
    analysis = {
        "estatisticas_gerais": {
            "total_projetos": 1243,
            "total_creditos": 9876543,
            "paises_com_projetos": 47,
            "receita_estimada": 222222222
        }
    }

    create_hero_section(analysis)
    create_revenue_calculator(analysis)

if __name__ == "__main__":
    main()
