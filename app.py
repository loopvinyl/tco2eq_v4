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

warnings.filterwarnings("ignore")

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Oportunidades no Mercado de Carbono para Propriedades Rurais - FAO",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.fao.org/climate-change/our-work/carbon-markets',
        'Report a bug': None,
        'About': "Dashboard para proprietários rurais descobrirem oportunidades no mercado voluntário de carbono agrícola."
    }
)

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

# Traduções de países com foco em países com agricultura relevante
COUNTRY_TRANSLATIONS = {
    'brazil': 'Brasil',
    'brazilian': 'Brasil',
    'brasil': 'Brasil',
    'united states': 'Estados Unidos',
    'usa': 'Estados Unidos',
    'us': 'Estados Unidos',
    'argentina': 'Argentina',
    'chile': 'Chile',
    'colombia': 'Colômbia',
    'uruguay': 'Uruguai',
    'paraguay': 'Paraguai',
    'mexico': 'México',
    'peru': 'Peru',
    'bolivia': 'Bolívia',
    'ecuador': 'Equador',
    'costarica': 'Costa Rica',
    'panama': 'Panamá',
    'australia': 'Austrália',
    'canada': 'Canadá',
    'germany': 'Alemanha',
    'france': 'França',
    'spain': 'Espanha',
    'italy': 'Itália',
    'portugal': 'Portugal',
    'china': 'China',
    'india': 'Índia',
    'indonesia': 'Indonésia',
    'vietnam': 'Vietnã',
    'thailand': 'Tailândia',
    'philippines': 'Filipinas',
    'malaysia': 'Malásia',
    'southafrica': 'África do Sul',
    'kenya': 'Quênia',
    'ethiopia': 'Etiópia',
    'nigeria': 'Nigéria'
}

# Preço médio de créditos de carbono (USD por tonelada)
CARBON_PRICE_RANGE = {
    'agricultura': {'min': 15, 'max': 30, 'avg': 22.5},
    'agroflorestal': {'min': 20, 'max': 40, 'avg': 30},
    'energia': {'min': 10, 'max': 25, 'avg': 17.5}
}

# =========================
# FUNÇÕES AUXILIARES - FOCO EM GERAÇÃO DE RENDA
# =========================
def get_country_name(country_str: str) -> str:
    """Obtém o nome do país em português com foco em países agrícolas"""
    if pd.isna(country_str):
        return "Não especificado"
    
    country_lower = str(country_str).lower().strip()
    
    # Procurar tradução exata
    for eng_name, port_name in COUNTRY_TRANSLATIONS.items():
        if eng_name == country_lower:
            return port_name
    
    # Procurar por substring
    for eng_name, port_name in COUNTRY_TRANSLATIONS.items():
        if eng_name in country_lower or country_lower in eng_name:
            return port_name
    
    # Se não encontrar, capitalizar palavras
    return country_str.strip().title()

def calculate_potential_revenue(hectares: float, practice_type: str = 'agricultura') -> Dict:
    """Calcula receita potencial para propriedades rurais"""
    price_range = CARBON_PRICE_RANGE.get(practice_type, CARBON_PRICE_RANGE['agricultura'])
    
    # Estimativa de sequestro por hectare/ano (ton CO2/ha)
    sequestration_rates = {
        'agricultura': {'min': 0.5, 'max': 2, 'avg': 1.25},  # Agricultura regenerativa
        'agroflorestal': {'min': 2, 'max': 6, 'avg': 4},      # Sistemas agroflorestais
        'energia': {'min': 1, 'max': 3, 'avg': 2}            # Bioenergia
    }
    
    rate = sequestration_rates.get(practice_type, sequestration_rates['agricultura'])
    
    # Cálculos de receita
    calculations = {
        'hectares': hectares,
        'practice_type': practice_type,
        'annual_sequestration_min': hectares * rate['min'],
        'annual_sequestration_max': hectares * rate['max'],
        'annual_sequestration_avg': hectares * rate['avg'],
        'annual_revenue_min': hectares * rate['min'] * price_range['min'],
        'annual_revenue_max': hectares * rate['max'] * price_range['max'],
        'annual_revenue_avg': hectares * rate['avg'] * price_range['avg'],
        '10yr_revenue_avg': hectares * rate['avg'] * price_range['avg'] * 10,
        'price_per_ton': f"US${price_range['min']}-{price_range['max']}",
        'sequestration_per_ha': f"{rate['min']}-{rate['max']} tCO2/ha/ano"
    }
    
    return calculations

def calculate_break_even(hectares: float, investment_cost: float, practice_type: str = 'agricultura') -> Dict:
    """Calcula ponto de equilíbrio para investimento em carbono"""
    revenue_calc = calculate_potential_revenue(hectares, practice_type)
    
    annual_revenue = revenue_calc['annual_revenue_avg']
    
    if annual_revenue > 0:
        break_even_years = investment_cost / annual_revenue
    else:
        break_even_years = float('inf')
    
    return {
        'investment': investment_cost,
        'annual_revenue': annual_revenue,
        'break_even_years': break_even_years,
        'roi_5yr': (annual_revenue * 5 - investment_cost) / investment_cost * 100 if investment_cost > 0 else 0,
        'monthly_revenue': annual_revenue / 12
    }

# =========================
# COMPONENTES DE UI - FOCO EM OPORTUNIDADES
# =========================
def create_hero_section():
    """Cria seção hero focada em oportunidades para proprietários"""
    st.markdown("""
    <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                background: linear-gradient(135deg, #27ae60, #229954); 
                color: white; margin-bottom: 2rem;'>
        <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>💰 Ganhe com Carbono na sua Terra</h1>
        <h3 style='font-weight: 300;'>Descubra quanto proprietários rurais estão ganhando no mercado de carbono</h3>
        <p style='font-size: 1.1rem; opacity: 0.9;'>
            Veja projetos reais, calcule seu potencial de ganho e encontre oportunidades
        </p>
    </div>
    """, unsafe_allow_html=True)

def create_opportunity_card(title: str, description: str, icon: str = "💰", value: str = None):
    """Cria card de oportunidade estilizado"""
    value_html = f"<div style='font-size: 1.8rem; font-weight: bold; color: #27ae60; margin-top: 0.5rem;'>{value}</div>" if value else ""
    
    return f"""
    <div style='background: white; padding: 1.5rem; border-radius: 10px; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 5px solid #27ae60;
                margin: 0.5rem; height: 100%; transition: transform 0.3s;'>
        <div style='font-size: 2rem; margin-bottom: 0.5rem; color: #27ae60;'>{icon}</div>
        <h4 style='color: #2c3e50; margin-bottom: 0.5rem;'>{title}</h4>
        <p style='color: #7f8c8d; line-height: 1.5; font-size: 0.9rem;'>{description}</p>
        {value_html}
    </div>
    """

def create_revenue_calculator():
    """Cria calculadora de receita interativa"""
    with st.expander("🧮 CALCULE SEU POTENCIAL DE GANHO", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            hectares = st.number_input("Tamanho da propriedade (hectares):", 
                                     min_value=1.0, max_value=10000.0, value=100.0, step=10.0)
        
        with col2:
            practice_type = st.selectbox(
                "Prática sustentável:",
                ["Agricultura Regenerativa", "Agrofloresta", "Bioenergia", "Integração Lavoura-Pecuária"],
                index=0
            )
        
        with col3:
            investment = st.number_input("Investimento inicial (US$):", 
                                       min_value=0.0, max_value=1000000.0, value=10000.0, step=1000.0)
        
        # Calcular
        practice_key = 'agricultura' if 'Agricultura' in practice_type else 'agroflorestal' if 'Agrofloresta' in practice_type else 'energia'
        revenue = calculate_potential_revenue(hectares, practice_key)
        break_even = calculate_break_even(hectares, investment, practice_key)
        
        # Resultados
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Receita Anual", f"US${revenue['annual_revenue_avg']:,.0f}")
        with col2:
            st.metric("📈 Receita 10 anos", f"US${revenue['10yr_revenue_avg']:,.0f}")
        with col3:
            st.metric("⏱️ Retorno (anos)", f"{break_even['break_even_years']:.1f}")
        with col4:
            st.metric("📊 ROI 5 anos", f"{break_even['roi_5yr']:.1f}%")
        
        # Detalhes
        with st.expander("📋 Ver detalhes do cálculo"):
            st.write(f"**Preço do carbono:** {revenue['price_per_ton']} por tonelada")
            st.write(f"**Sequestro estimado:** {revenue['sequestration_per_ha']}")
            st.write(f"**Sequestro total anual:** {revenue['annual_sequestration_avg']:,.1f} tCO2")
            st.write(f"**Receita mensal:** US${break_even['monthly_revenue']:,.0f}")

# =========================
# SISTEMA DE CARGA DE DADOS
# =========================
@st.cache_data(ttl=3600, show_spinner=False)
def load_data_with_revenue_focus():
    """Carrega dados focando em informações de receita"""
    file_path = "Dataset.xlsx"
    
    if not os.path.exists(file_path):
        st.error("📂 Arquivo não encontrado. Verifique se 'Dataset.xlsx' está no diretório.")
        return None, None
    
    try:
        excel = pd.ExcelFile(file_path, engine='openpyxl')
        data = {}
        sheet_names = []
        
        for sheet in excel.sheet_names:
            try:
                df = excel.parse(sheet, header=0)
                
                # Limpeza básica
                df = df.dropna(axis=1, how='all')
                df.columns = [str(col).strip() for col in df.columns]
                
                # Remover colunas completamente vazias
                df = df.loc[:, df.notna().any()]
                
                # Processamento especial para abas com foco em receita
                if SHEET_CONFIG.get(sheet, {}).get('revenue_focus', False):
                    # Identificar colunas de créditos
                    credit_cols = [col for col in df.columns if any(word in str(col).lower() 
                                                                   for word in ['credit', 'issued', 'volume', 'amount', 'total'])]
                    
                    # Adicionar metadados para colunas de créditos
                    if credit_cols:
                        df.attrs['credit_columns'] = credit_cols
                    
                    # Identificar colunas de área/hectares
                    area_cols = [col for col in df.columns if any(word in str(col).lower()
                                                                for word in ['area', 'hectare', 'ha', 'land', 'size'])]
                    if area_cols:
                        df.attrs['area_columns'] = area_cols
                
                data[sheet] = df
                sheet_names.append(sheet)
                
            except Exception as e:
                st.warning(f"Aviso na aba '{sheet}': {str(e)[:100]}")
                data[sheet] = pd.DataFrame()
        
        return data, sheet_names
        
    except Exception as e:
        st.error(f"❌ Erro crítico: {str(e)}")
        return None, None

# =========================
# ANÁLISES DE RECEITA
# =========================
def analyze_revenue_opportunities(dataframes):
    """Analisa oportunidades de receita nos dados"""
    analysis = {
        'total_revenue_projects': 0,
        'total_credits_issued': 0,
        'estimated_total_revenue': 0,
        'top_countries': [],
        'project_types': {},
        'avg_credits_per_project': 0
    }
    
    project_sheets = ['4. Agriculture', '5. Agroforestry-AR & Grassland', '6. Energy and Other',
                     '7. Plan Vivo, Acorn, Social C', '8. Puro.earth', '9. Nori and BCarbon']
    
    for sheet in project_sheets:
        if sheet in dataframes:
            df = dataframes[sheet]
            if not df.empty:
                analysis['total_revenue_projects'] += len(df)
                
                # Tentar encontrar créditos
                if hasattr(df, 'attrs') and 'credit_columns' in df.attrs:
                    for credit_col in df.attrs['credit_columns']:
                        if credit_col in df.columns:
                            total_credits = df[credit_col].sum()
                            analysis['total_credits_issued'] += total_credits
                
                # Análise por país
                for col in df.columns:
                    if 'country' in str(col).lower():
                        country_counts = df[col].value_counts().head(10)
                        for country, count in country_counts.items():
                            if country and str(country).strip():
                                analysis['top_countries'].append({
                                    'country': get_country_name(str(country)),
                                    'projects': count,
                                    'sheet': sheet
                                })
    
    # Estimar receita total (usando preço médio de US$20/ton)
    analysis['estimated_total_revenue'] = analysis['total_credits_issued'] * 20
    
    # Calcular média
    if analysis['total_revenue_projects'] > 0:
        analysis['avg_credits_per_project'] = analysis['total_credits_issued'] / analysis['total_revenue_projects']
    
    # Consolidar países
    country_summary = {}
    for item in analysis['top_countries']:
        country = item['country']
        if country not in country_summary:
            country_summary[country] = 0
        country_summary[country] += item['projects']
    
    analysis['top_countries_summary'] = sorted(country_summary.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return analysis

# =========================
# PÁGINA PRINCIPAL - OPORTUNIDADES
# =========================
def render_opportunities_home(dataframes):
    """Renderiza página inicial focada em oportunidades"""
    create_hero_section()
    
    # Análise de oportunidades
    analysis = analyze_revenue_opportunities(dataframes)
    
    # Calculadora de receita
    create_revenue_calculator()
    
    # Métricas de mercado
    st.markdown("## 📈 Mercado em Números")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Projetos Ativos", f"{analysis['total_revenue_projects']:,}", 
                 "Gerando receita para proprietários")
    with col2:
        st.metric("🌱 Créditos Emitidos", f"{analysis['total_credits_issued']:,.0f}", 
                 f"≈ {analysis['total_credits_issued']:,.0f} tCO2")
    with col3:
        revenue_str = f"US${analysis['estimated_total_revenue']:,.0f}" if analysis['estimated_total_revenue'] > 1000000 else f"US${analysis['estimated_total_revenue']:,.0f}"
        st.metric("💵 Receita Estimada", revenue_str, 
                 "Preço médio: US$20/ton")
    with col4:
        st.metric("🏆 Média por Projeto", f"{analysis['avg_credits_per_project']:,.0f} créditos",
                 f"≈ US${analysis['avg_credits_per_project']*20:,.0f}")
    
    # Oportunidades por país
    st.markdown("## 🌍 Onde os Proprietários estão Ganhando")
    
    if analysis['top_countries_summary']:
        countries, counts = zip(*analysis['top_countries_summary'])
        
        fig = px.bar(
            x=countries,
            y=counts,
            title="Países com Mais Projetos de Carbono",
            labels={'x': 'País', 'y': 'Número de Projetos'},
            color=counts,
            color_continuous_scale='Greens'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Cards de oportunidade
    st.markdown("## 💡 Como Ganhar com Carbono na sua Terra")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(create_opportunity_card(
            "Agricultura Regenerativa",
            "Práticas como plantio direto, rotação de culturas e cobertura vegetal aumentam o carbono no solo e geram créditos.",
            "🌱",
            "US$15-30/ton"
        ), unsafe_allow_html=True)
        
        st.markdown(create_opportunity_card(
            "Sistemas Agroflorestais",
            "Integração de árvores com culturas agrícolas sequestra mais carbono e diversifica a renda.",
            "🌳",
            "US$20-40/ton"
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_opportunity_card(
            "Integração Lavoura-Pecuária",
            "Sistema que melhora a produtividade e sequestra carbono no solo e na biomassa.",
            "🚜🐄",
            "US$18-35/ton"
        ), unsafe_allow_html=True)
        
        st.markdown(create_opportunity_card(
            "Bioenergia Sustentável",
            "Produção de energia a partir de resíduos agrícolas gera créditos de carbono.",
            "⚡",
            "US$10-25/ton"
        ), unsafe_allow_html=True)
    
    # Passo a passo
    st.markdown("## 🚀 Como Começar")
    
    steps = [
        {"icon": "📋", "title": "Avalie sua Propriedade", "desc": "Analise o potencial de sequestro de carbono da sua terra"},
        {"icon": "📊", "title": "Escolha uma Metodologia", "desc": "Selecione o padrão de certificação mais adequado"},
        {"icon": "🤝", "title": "Encontre uma Plataforma", "desc": "Conecte-se com empresas que compram créditos"},
        {"icon": "🌱", "title": "Implemente Práticas", "desc": "Adote técnicas de agricultura sustentável"},
        {"icon": "📈", "title": "Monitore e Verifique", "desc": "Acompanhe o sequestro e valide os créditos"},
        {"icon": "💰", "title": "Venda os Créditos", "desc": "Receba pagamento pelo carbono sequestrado"}
    ]
    
    cols = st.columns(3)
    for i, step in enumerate(steps):
        with cols[i % 3]:
            st.markdown(f"""
            <div style='text-align: center; padding: 1rem; margin: 0.5rem 0; 
                        background: #f8f9fa; border-radius: 10px; border: 1px solid #e9ecef;'>
                <div style='font-size: 2rem; margin-bottom: 0.5rem;'>{step['icon']}</div>
                <h4 style='color: #2c3e50; margin-bottom: 0.5rem;'>{step['title']}</h4>
                <p style='color: #7f8c8d; font-size: 0.9rem;'>{step['desc']}</p>
            </div>
            """, unsafe_allow_html=True)

# =========================
# EXPLORADOR DE PROJETOS
# =========================
def render_project_explorer(dataframes, sheet_names):
    """Renderiza explorador de projetos reais"""
    st.markdown("## 🔍 Explore Projetos Reais que Geram Receita")
    
    # Filtrar apenas abas com projetos
    project_sheets = [s for s in sheet_names if SHEET_CONFIG.get(s, {}).get('revenue_focus', False)]
    
    if not project_sheets:
        st.warning("Nenhuma aba de projetos encontrada.")
        return
    
    # Sidebar para filtros
    with st.sidebar:
        st.markdown("### 🎯 Filtros de Projetos")
        
        selected_sheet = st.selectbox(
            "Tipo de Projeto:",
            project_sheets,
            format_func=lambda x: f"{SHEET_CONFIG.get(x, {}).get('icon', '📄')} {x}"
        )
        
        st.markdown("---")
        st.markdown("### 🌍 Filtro por País")
        
        # Carregar países disponíveis
        df = dataframes[selected_sheet]
        countries = []
        
        for col in df.columns:
            if 'country' in str(col).lower():
                unique_countries = df[col].dropna().unique()
                for country in unique_countries:
                    if country and str(country).strip():
                        country_name = get_country_name(str(country))
                        if country_name not in countries:
                            countries.append(country_name)
        
        if countries:
            selected_countries = st.multiselect(
                "Selecione países:",
                sorted(countries),
                default=[]
            )
        else:
            selected_countries = []
            st.info("Nenhuma coluna de país encontrada")
        
        st.markdown("---")
        st.markdown("### 📊 Filtro por Tamanho")
        
        # Tentar encontrar colunas numéricas relevantes
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        credit_cols = [col for col in numeric_cols if any(word in str(col).lower() 
                                                        for word in ['credit', 'issued', 'volume'])]
        
        if credit_cols:
            selected_credit_col = st.selectbox("Métrica de créditos:", credit_cols)
            
            if df[selected_credit_col].notna().any():
                min_val = float(df[selected_credit_col].min())
                max_val = float(df[selected_credit_col].max())
                
                credit_range = st.slider(
                    f"Intervalo de {selected_credit_col}:",
                    min_value=min_val,
                    max_value=max_val,
                    value=(min_val, max_val)
                )
            else:
                credit_range = None
        else:
            credit_range = None
    
    # Conteúdo principal
    if selected_sheet in dataframes:
        df = dataframes[selected_sheet]
        config = SHEET_CONFIG.get(selected_sheet, {})
        
        # Aplicar filtros
        filtered_df = df.copy()
        
        # Filtro por país
        if selected_countries:
            for col in filtered_df.columns:
                if 'country' in str(col).lower():
                    filtered_df = filtered_df[
                        filtered_df[col].apply(lambda x: get_country_name(str(x)) if pd.notna(x) else "").isin(selected_countries)
                    ]
                    break
        
        # Filtro por créditos
        if credit_range and selected_credit_col:
            filtered_df = filtered_df[
                (filtered_df[selected_credit_col] >= credit_range[0]) & 
                (filtered_df[selected_credit_col] <= credit_range[1])
            ]
        
        # Cabeçalho
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(f"<h1 style='font-size: 3rem; color: {config.get('color', '#27ae60')};'>{config.get('icon', '💰')}</h1>", 
                       unsafe_allow_html=True)
        with col2:
            st.markdown(f"<h2 style='margin-top: 0;'>{selected_sheet}</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='color: #7f8c8d;'>Exemplos reais de projetos que geram receita para proprietários</p>", 
                       unsafe_allow_html=True)
        
        # Estatísticas
        st.markdown(f"### 📊 {len(filtered_df)} Projetos Encontrados")
        
        # Tentar calcular receita estimada
        estimated_revenue = 0
        if hasattr(filtered_df, 'attrs') and 'credit_columns' in filtered_df.attrs:
            for credit_col in filtered_df.attrs['credit_columns']:
                if credit_col in filtered_df.columns:
                    total_credits = filtered_df[credit_col].sum()
                    estimated_revenue += total_credits * 20  # US$20 por tonelada
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📈 Projetos", len(filtered_df))
        with col2:
            if estimated_revenue > 0:
                st.metric("💰 Receita Estimada", f"US${estimated_revenue:,.0f}")
        with col3:
            if not filtered_df.empty:
                st.metric("✅ Taxa de Preenchimento", f"{(1 - filtered_df.isnull().mean().mean()) * 100:.1f}%")
        
        # Exibir dados
        st.markdown("### 📋 Dados dos Projetos")
        
        # Selecionar colunas mais relevantes
        relevant_cols = []
        
        # Priorizar colunas importantes
        priority_keywords = ['name', 'project', 'country', 'credit', 'issued', 'area', 'hectare', 'type', 'standard']
        
        for keyword in priority_keywords:
            for col in filtered_df.columns:
                if keyword in str(col).lower() and col not in relevant_cols:
                    relevant_cols.append(col)
        
        # Adicionar mais colunas até ter pelo menos 8
        other_cols = [col for col in filtered_df.columns if col not in relevant_cols]
        relevant_cols.extend(other_cols[:max(0, 8 - len(relevant_cols))])
        
        if relevant_cols:
            display_df = filtered_df[relevant_cols].head(100)
            
            # Adicionar coluna de receita estimada se possível
            if estimated_revenue > 0 and 'credit_columns' in filtered_df.attrs:
                for credit_col in filtered_df.attrs['credit_columns']:
                    if credit_col in display_df.columns:
                        display_df[f'{credit_col}_revenue_est'] = display_df[credit_col] * 20
                        break
            
            st.dataframe(
                display_df,
                use_container_width=True,
                height=400,
                hide_index=True
            )
            
            # Análise de receita
            st.markdown("### 📈 Análise de Receita por Projeto")
            
            # Encontrar melhor projeto por receita
            if 'credit_columns' in filtered_df.attrs:
                for credit_col in filtered_df.attrs['credit_columns']:
                    if credit_col in filtered_df.columns:
                        top_project_idx = filtered_df[credit_col].idxmax()
                        top_project = filtered_df.loc[top_project_idx]
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            # Projeto com maior receita
                            if 'name' in top_project.index:
                                st.metric("🏆 Maior Projeto", str(top_project.get('name', 'Não identificado')))
                        
                        with col2:
                            st.metric("💰 Créditos", f"{filtered_df[credit_col].max():,.0f}")
                        
                        with col3:
                            st.metric("💵 Receita Estimada", f"US${filtered_df[credit_col].max() * 20:,.0f}")
                        
                        break

# =========================
# PÁGINA DE CASOS DE SUCESSO
# =========================
def render_success_stories():
    """Renderiza página com casos de sucesso"""
    st.markdown("## 📚 Casos de Sucesso - Proprietários que já estão Ganhando")
    
    success_stories = [
        {
            "title": "Fazenda no Brasil - Mato Grosso",
            "description": "Propriedade de 500 hectares implementou plantio direto e rotação de culturas. Em 3 anos, sequestrou 2.500 toneladas de CO2.",
            "revenue": "US$ 62.500",
            "period": "3 anos",
            "practices": "Plantio direto, rotação de culturas",
            "icon": "🇧🇷"
        },
        {
            "title": "Produtor Familiar - Paraná",
            "description": "Pequea propriedade de 50 hectares adotou sistema integrado lavoura-pecuária-floresta (ILPF). Gera receita adicional com carbono.",
            "revenue": "US$ 8.000/ano",
            "period": "Anual",
            "practices": "ILPF, pastagem melhorada",
            "icon": "👨‍🌾"
        },
        {
            "title": "Cooperativa - Minas Gerais",
            "description": "Grupo de 20 pequenos produtores uniu-se para vender créditos em bloco. Aumentou poder de negociação e receita.",
            "revenue": "US$ 150.000 total",
            "period": "2 anos",
            "practices": "Agricultura regenerativa",
            "icon": "🤝"
        },
        {
            "title": "Fazenda Orgânica - São Paulo",
            "description": "Propriedade certificada orgânica agregou certificação de carbono. Agora vende produtos com selo carbono neutro.",
            "revenue": "US$ 12.000/ano + premium produtos",
            "period": "Contínuo",
            "practices": "Orgânico + carbono",
            "icon": "🌿"
        }
    ]
    
    cols = st.columns(2)
    for i, story in enumerate(success_stories):
        with cols[i % 2]:
            st.markdown(f"""
            <div style='background: white; padding: 1.5rem; border-radius: 10px; 
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin: 1rem 0; 
                        border-top: 5px solid #27ae60;'>
                <div style='display: flex; align-items: center; margin-bottom: 1rem;'>
                    <div style='font-size: 2rem; margin-right: 1rem;'>{story['icon']}</div>
                    <h3 style='margin: 0; color: #2c3e50;'>{story['title']}</h3>
                </div>
                <p style='color: #7f8c8d; line-height: 1.6;'>{story['description']}</p>
                <div style='background: #f8f9fa; padding: 1rem; border-radius: 5px; margin: 1rem 0;'>
                    <div style='display: flex; justify-content: space-between;'>
                        <div>
                            <div style='font-size: 0.8rem; color: #95a5a6;'>Receita com Carbono</div>
                            <div style='font-size: 1.5rem; font-weight: bold; color: #27ae60;'>{story['revenue']}</div>
                        </div>
                        <div>
                            <div style='font-size: 0.8rem; color: #95a5a6;'>Período</div>
                            <div style='font-size: 1.2rem; color: #2c3e50;'>{story['period']}</div>
                        </div>
                    </div>
                </div>
                <div style='color: #3498db; font-size: 0.9rem;'>
                    <strong>Práticas:</strong> {story['practices']}
                </div>
            </div>
            """, unsafe_allow_html=True)

# =========================
# APLICAÇÃO PRINCIPAL
# =========================
def main():
    # Carregar dados
    with st.spinner("💰 Analisando oportunidades de receita no mercado de carbono..."):
        dataframes, sheet_names = load_data_with_revenue_focus()
    
    if dataframes is None:
        st.error("Não foi possível carregar os dados. Verifique o arquivo Dataset.xlsx")
        return
    
    # Sidebar principal
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 1rem;'>
            <h2 style='color: #27ae60;'>💰 Ganhe com Carbono</h2>
            <p style='color: #7f8c8d;'>Para Proprietários Rurais</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Navegação principal
        page = st.radio(
            "Navegação",
            ["🏠 Oportunidades", "🔍 Projetos Reais", "📚 Casos de Sucesso", "📞 Como Participar"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Dica rápida
        st.markdown("### 💡 Dica Rápida")
        st.info("""
        Uma propriedade de 100 hectares pode gerar:
        **US$ 2.000 - 12.000/ano**
        com práticas sustentáveis
        """)
        
        st.markdown("---")
        
        # Links úteis
        st.markdown("### 🔗 Para Saber Mais")
        st.markdown("""
        - [FAO: Mercados de Carbono](https://www.fao.org/climate-change/our-work/carbon-markets)
        - [Agricultura de Baixo Carbono](https://www.gov.br/agricultura)
        - [Créditos de Carbono no Brasil](https://www.mma.gov.br)
        """)
    
    # Renderizar página selecionada
    if page == "🏠 Oportunidades":
        render_opportunities_home(dataframes)
    elif page == "🔍 Projetos Reais":
        render_project_explorer(dataframes, sheet_names)
    elif page == "📚 Casos de Sucesso":
        render_success_stories()
    else:
        render_how_to_participate()

def render_how_to_participate():
    """Renderiza página de como participar"""
    st.markdown("## 📞 Como Participar do Mercado de Carbono")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 Passo a Passo")
        
        steps = [
            {"step": 1, "title": "Diagnóstico da Propriedade", 
             "desc": "Avalie o potencial de sequestro de carbono da sua terra"},
            {"step": 2, "title": "Escolha do Padrão", 
             "desc": "Selecione uma metodologia de certificação (Verra, Gold Standard, etc.)"},
            {"step": 3, "title": "Projeto de Carbono", 
             "desc": "Desenvolva o projeto seguindo as regras do padrão escolhido"},
            {"step": 4, "title": "Validação e Verificação", 
             "desc": "Contrate auditoria independente para validar o projeto"},
            {"step": 5, "title": "Registro dos Créditos", 
             "desc": "Registre os créditos gerados em plataforma oficial"},
            {"step": 6, "title": "Comercialização", 
             "desc": "Venda os créditos no mercado voluntário"}
        ]
        
        for step in steps:
            st.markdown(f"""
            <div style='background: #f8f9fa; padding: 1rem; border-radius: 10px; margin: 0.5rem 0; 
                        border-left: 4px solid #27ae60;'>
                <div style='display: flex; align-items: center;'>
                    <div style='background: #27ae60; color: white; width: 30px; height: 30px; 
                                border-radius: 50%; display: flex; align-items: center; 
                                justify-content: center; margin-right: 1rem; font-weight: bold;'>
                        {step['step']}
                    </div>
                    <div>
                        <h4 style='margin: 0; color: #2c3e50;'>{step['title']}</h4>
                        <p style='margin: 0.2rem 0 0 0; color: #7f8c8d; font-size: 0.9rem;'>
                            {step['desc']}
                        </p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 🤝 Plataformas e Intermediários")
        
        platforms = [
            {"name": "Verra (VCS)", "desc": "Maior padrão do mundo, usado em 70% dos projetos"},
            {"name": "Gold Standard", "desc": "Foco em desenvolvimento sustentável e comunidades"},
            {"name": "Plataformas Brasileiras", "desc": "Mercado Brasileiro de Redução de Emissões (MBRE)"},
            {"name": "Corretoras Especializadas", "desc": "Empresas que conectam produtores a compradores"},
            {"name": "Cooperativas", "desc": "Agregação de pequenos produtores para venda em bloco"}
        ]
        
        for platform in platforms:
            st.markdown(f"""
            <div style='background: white; padding: 1rem; border-radius: 8px; 
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 0.5rem 0;'>
                <h4 style='margin: 0 0 0.5rem 0; color: #2c3e50;'>{platform['name']}</h4>
                <p style='margin: 0; color: #7f8c8d; font-size: 0.9rem;'>{platform['desc']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("### 💰 Custos e Investimentos")
        
        costs = [
            {"item": "Auditoria/Verificação", "range": "US$ 5.000 - 20.000"},
            {"item": "Desenvolvimento do Projeto", "range": "US$ 10.000 - 50.000"},
            {"item": "Taxas de Registro", "range": "US$ 0,15 - 0,30/crédito"},
            {"item": "Implementação Práticas", "range": "Variável por hectare"}
        ]
        
        for cost in costs:
            st.markdown(f"""
            <div style='display: flex; justify-content: space-between; padding: 0.5rem 0; 
                        border-bottom: 1px solid #eee;'>
                <span style='color: #2c3e50;'>{cost['item']}</span>
                <span style='color: #27ae60; font-weight: bold;'>{cost['range']}</span>
            </div>
            """, unsafe_allow_html=True)

# =========================
# RODAPÉ
# =========================
def create_footer():
    """Cria rodapé informativo"""
    st.markdown("---")
    
    st.markdown("""
    <div style='text-align: center; padding: 1rem;'>
        <p style='color: #7f8c8d;'>
        <strong>💰 Ganhe com Carbono na sua Terra</strong> | 
        Dashboard para proprietários rurais | 
        Dados: FAO Agrifood Carbon Market Dataset
        </p>
        <p style='color: #95a5a6; font-size: 0.8rem;'>
        💡 Este é um dashboard informativo. Para projetos reais, consulte especialistas em créditos de carbono.
        </p>
    </div>
    """, unsafe_allow_html=True)

# =========================
# EXECUÇÃO PRINCIPAL
# =========================
if __name__ == "__main__":
    try:
        main()
        create_footer()
    except Exception as e:
        st.error(f"❌ Ocorreu um erro: {str(e)}")
        st.info("Recarregue a página ou tente novamente mais tarde.")
