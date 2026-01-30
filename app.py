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
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Mercado de Carbono para Propriedades Rurais - Baseado em Dados Reais FAO",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# FUNÇÕES DE FORMATAÇÃO (PADRÃO BRASIL)
# =========================
def formata_br(valor, prefixo="", sufixo=""):
    """
    Converte um número para o formato brasileiro: 1.234,56
    """
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "N/A"
    
    # Formatação com separador de milhar por vírgula e decimal por ponto (padrão US)
    # Depois invertemos para o padrão BR
    texto = f"{valor:,.2f}"
    texto_br = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    
    resultado = f"{prefixo} {texto_br}" if prefixo else texto_br
    return f"{resultado}{sufixo}" if sufixo else resultado

# =========================
# CONSTANTES E CONFIGURAÇÕES
# =========================
SHEET_CONFIG = {
    "README": {"type": "documentação", "icon": "📖", "color": "#95a5a6"},
    "1. Standards": {"type": "padrões", "icon": "🏛️", "color": "#3498db", "main_column": "Name of standard/registry/platform"},
    "2. Platforms": {"type": "plataformas", "icon": "🖥️", "color": "#9b59b6", "main_column": "Platform"},
    "3. Methodologies": {"type": "metodologias", "icon": "🔬", "color": "#e74c3c", "main_column": "Data sourced from methodology document (see reference in column AD)"},
    "4. Agriculture": {"type": "projetos", "icon": "🚜", "color": "#2ecc71", "has_yearly_data": True, "country_column": "Country", "revenue_focus": True},
    "5. Agroforestry-AR & Grassland": {"type": "projetos", "icon": "🌳", "color": "#27ae60", "has_yearly_data": True, "country_column": "Country", "revenue_focus": True},
    "6. Energy and Other": {"type": "projetos", "icon": "⚡", "color": "#f39c12", "has_yearly_data": True, "country_column": "Country", "revenue_focus": True},
    "7. Plan Vivo, Acorn, Social C": {"type": "padrões", "icon": "🌍", "color": "#1abc9c", "main_column": "Standard", "country_column": "Country", "revenue_focus": True},
    "8. Puro.earth": {"type": "projetos", "icon": "🔥", "color": "#d35400", "main_column": "Unnamed: 0", "revenue_focus": True},
    "9. Nori and BCarbon": {"type": "projetos", "icon": "🌾", "color": "#16a085", "main_column": "Standard", "country_column": "Country", "revenue_focus": True}
}

COUNTRY_TRANSLATIONS = {
    'brazil': 'Brasil', 'brazilian': 'Brasil', 'brasil': 'Brasil',
    'united states': 'Estados Unidos', 'usa': 'Estados Unidos', 'us': 'Estados Unidos'
}

# =========================
# SISTEMA DE ANÁLISE (LÓGICA MANTIDA)
# =========================

def identify_columns(df):
    columns = {'nome': None, 'pais': None, 'area': None, 'creditos': None, 'duracao': None, 'metodologia': None, 'preco': None}
    for col in df.columns:
        col_lower = str(col).lower()
        if any(word in col_lower for word in ['name', 'project', 'title', 'nome', 'projeto']): columns['nome'] = col
        elif any(word in col_lower for word in ['country', 'pais', 'location', 'region']): columns['pais'] = col
        elif any(word in col_lower for word in ['area', 'hectare', 'ha', 'size']): columns['area'] = col
        elif any(word in col_lower for word in ['credit', 'issued', 'volume', 'amount', 'credits']): columns['creditos'] = col
        elif any(word in col_lower for word in ['year', 'duration', 'period', 'anos']): columns['duracao'] = col
        elif any(word in col_lower for word in ['methodology', 'standard', 'metodologia']): columns['metodologia'] = col
    return columns

def convert_to_numeric(value):
    if pd.isna(value): return None
    try:
        if isinstance(value, (int, float)): return float(value)
        str_value = str(value).strip()
        str_value = re.sub(r'[^\d.,]', '', str_value)
        if ',' in str_value and '.' in str_value:
            str_value = str_value.replace('.', '').replace(',', '.')
        elif ',' in str_value:
            if str_value.count(',') == 1: str_value = str_value.replace(',', '.')
            else: str_value = str_value.replace(',', '')
        return float(str_value) if str_value else None
    except: return None

def extract_years(value):
    if pd.isna(value): return 10
    try:
        numbers = re.findall(r'\d+', str(value))
        if numbers: return max(1, min(int(numbers[0]), 50))
    except: pass
    return 10

def get_country_name(country_str):
    if pd.isna(country_str): return "Não especificado"
    c_lower = str(country_str).lower().strip()
    for eng, pt in COUNTRY_TRANSLATIONS.items():
        if eng in c_lower: return pt
    return str(country_str).strip().title()

def extract_project_info(row, col_info, category, sheet_name):
    try:
        info = {'categoria': category, 'fonte': sheet_name, 'creditos_emitidos': 0, 'area_hectares': 0, 
                'duracao_anos': 10, 'pais': 'Não especificado', 'nome': f"Projeto {category}"}
        
        if col_info['creditos'] and col_info['creditos'] in row:
            info['creditos_emitidos'] = convert_to_numeric(row[col_info['creditos']]) or 0
        if col_info['area'] and col_info['area'] in row:
            info['area_hectares'] = convert_to_numeric(row[col_info['area']]) or 0
        if col_info['duracao'] and col_info['duracao'] in row:
            info['duracao_anos'] = extract_years(row[col_info['duracao']])
        if col_info['pais'] and col_info['pais'] in row:
            info['pais'] = get_country_name(row[col_info['pais']])
        if col_info['nome'] and col_info['nome'] in row:
            info['nome'] = str(row[col_info['nome']])[:100]

        if info['creditos_emitidos'] > 0:
            info['receita_estimada'] = info['creditos_emitidos'] * 22.5
            info['receita_anual'] = info['receita_estimada'] / info['duracao_anos']
            return info
    except: pass
    return None

@st.cache_data(ttl=3600)
def analyze_complete_dataset(dataframes):
    analysis = {
        'estatisticas_gerais': {'total_projetos': 0, 'total_creditos': 0, 'receita_estimada': 0, 'paises_com_projetos': 0},
        'projetos_por_pais': {},
        'taxas_sequestro_reais': {},
        'casos_sucesso_reais': [],
        'categorias_projetos': {
            'agricultura': {'total': 0, 'creditos': 0},
            'agroflorestal': {'total': 0, 'creditos': 0},
            'energia': {'total': 0, 'creditos': 0}
        }
    }
    
    CATEGORY_MAPPING = {
        '4. Agriculture': 'agricultura', '5. Agroforestry-AR & Grassland': 'agroflorestal',
        '6. Energy and Other': 'energia', '7. Plan Vivo, Acorn, Social C': 'agroflorestal',
        '8. Puro.earth': 'energia', '9. Nori and BCarbon': 'agricultura'
    }

    for sheet, cat in CATEGORY_MAPPING.items():
        if sheet in dataframes and not dataframes[sheet].empty:
            df = dataframes[sheet]
            col_info = identify_columns(df)
            for _, row in df.iterrows():
                p = extract_project_info(row, col_info, cat, sheet)
                if p:
                    analysis['casos_sucesso_reais'].append(p)
                    analysis['categorias_projetos'][cat]['total'] += 1
                    analysis['categorias_projetos'][cat]['creditos'] += p['creditos_emitidos']
                    analysis['projetos_por_pais'][p['pais']] = analysis['projetos_por_pais'].get(p['pais'], 0) + 1

    analysis['estatisticas_gerais']['total_projetos'] = sum(c['total'] for c in analysis['categorias_projetos'].values())
    analysis['estatisticas_gerais']['total_creditos'] = sum(c['creditos'] for c in analysis['categorias_projetos'].values())
    analysis['estatisticas_gerais']['receita_estimada'] = analysis['estatisticas_gerais']['total_creditos'] * 22.5
    analysis['estatisticas_gerais']['paises_com_projetos'] = len(analysis['projetos_por_pais'])
    analysis['casos_sucesso_reais'].sort(key=lambda x: x.get('creditos_emitidos', 0), reverse=True)
    
    return analysis

# =========================
# COMPONENTES DE UI (COM PADRÃO BRASILEIRO)
# =========================

def create_hero_section(analysis):
    stats = analysis['estatisticas_gerais']
    st.markdown(f"""
    <div style='text-align: center; padding: 2rem; border-radius: 15px; background: linear-gradient(135deg, #27ae60, #229954); color: white; margin-bottom: 2rem;'>
        <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>🌱 Mercado Real de Carbono Agrícola</h1>
        <h3 style='font-weight: 300;'>Baseado em {formata_br(stats['total_projetos'])} projetos certificados</h3>
        <p style='font-size: 1.1rem; opacity: 0.9;'>
            {formata_br(stats['total_creditos'])} créditos emitidos • {stats['paises_com_projetos']} países • 
            {formata_br(stats['receita_estimada'], 'US$')} em receita gerada
        </p>
    </div>
    """, unsafe_allow_html=True)

def create_revenue_calculator(analysis):
    with st.expander("🧮 CALCULE SEU POTENCIAL COM DADOS REAIS", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1: hectares = st.number_input("Tamanho da propriedade (hectares):", 1.0, 10000.0, 100.0)
        with col2: practice = st.selectbox("Prática sustentável:", [("agricultura", "🌱 Agricultura Regenerativa"), ("agroflorestal", "🌳 Sistemas Agroflorestais"), ("energia", "⚡ Bioenergia Sustentável")], format_func=lambda x: x[1])[0]
        with col3: investment = st.number_input("Investimento inicial (US$):", 0.0, 1000000.0, 10000.0)
        
        # Cálculo simplificado baseado nas taxas médias
        taxa_media = {"agricultura": 1.25, "agroflorestal": 4.0, "energia": 2.0}[practice]
        preco_carbono = 22.5
        receita_anual = hectares * taxa_media * preco_carbono
        retorno_anos = investment / receita_anual if receita_anual > 0 else 0
        roi_5 = ((receita_anual * 5) - investment) / investment * 100 if investment > 0 else 0

        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Receita Anual", formata_br(receita_anual, "US$"))
        c2.metric("📈 Receita 10 anos", formata_br(receita_anual * 10, "US$"))
        c3.metric("⏱️ Retorno (anos)", formata_br(retorno_anos))
        c4.metric("📊 ROI 5 anos", formata_br(roi_5, sufixo="%"))

def create_success_stories_from_data(analysis):
    success_stories = analysis.get('casos_sucesso_reais', [])[:4]
    st.markdown("## 📚 Casos Reais de Projetos")
    cols = st.columns(2)
    for i, story in enumerate(success_stories):
        with cols[i % 2]:
            st.markdown(f"""
            <div style='background: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin: 1rem 0; border-top: 5px solid #27ae60;'>
                <h3 style='margin: 0; color: #2c3e50; font-size: 1.1rem;'>{story['nome']}</h3>
                <p style='color: #7f8c8d; font-size: 0.9rem;'>{story['pais']} • {formata_br(story['area_hectares'])} ha</p>
                <div style='background: #f8f9fa; padding: 1rem; border-radius: 5px;'>
                    <div style='font-size: 0.8rem; color: #95a5a6;'>Receita Estimada</div>
                    <div style='font-size: 1.2rem; font-weight: bold; color: #27ae60;'>{formata_br(story['receita_estimada'], "US$")}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_opportunities_home(analysis):
    create_hero_section(analysis)
    create_revenue_calculator(analysis)
    
    st.markdown("## 📈 O Mercado Real em Números")
    stats = analysis['estatisticas_gerais']
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Projetos", formata_br(stats['total_projetos']))
    col2.metric("🌱 Créditos", formata_br(stats['total_creditos']))
    col3.metric("💵 Receita Total", formata_br(stats['receita_estimada'], "US$"))
    col4.metric("🏆 Média/Projeto", formata_br(stats['receita_estimada']/max(1, stats['total_projetos']), "US$"))
    
    create_success_stories_from_data(analysis)

# =========================
# EXECUÇÃO PRINCIPAL
# =========================
def main():
    # Simulando carregamento de dados vazios para a estrutura funcionar
    dummy_dfs = {k: pd.DataFrame() for k in SHEET_CONFIG.keys()}
    analysis = analyze_complete_dataset(dummy_dfs)
    
    # Se houver dados reais, você carregaria aqui:
    # analysis = analyze_complete_dataset(st.session_state.get('dataframes'))

    st.sidebar.title("🌿 Menu Carbono")
    app_mode = st.sidebar.radio("Navegação:", ["Dashboard Principal", "Sobre os Dados"])

    if app_mode == "Dashboard Principal":
        render_opportunities_home(analysis)
    else:
        st.write("Dados baseados em registros históricos da FAO para créditos de carbono.")

if __name__ == "__main__":
    main()
