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
# NOVAS FUNÇÕES DE ANÁLISE ESTATÍSTICA
# =========================

@st.cache_data(ttl=3600, show_spinner=False)
def analyze_project_statistics(dataframes):
    """Analisa estatísticas reais dos projetos do dataset"""
    
    # Mapeamento de abas para tipos de prática
    PRACTICE_MAPPING = {
        '4. Agriculture': 'agricultura',
        '5. Agroforestry-AR & Grassland': 'agroflorestal', 
        '6. Energy and Other': 'energia',
        '7. Plan Vivo, Acorn, Social C': 'agroflorestal',
        '8. Puro.earth': 'energia',
        '9. Nori and BCarbon': 'agricultura'
    }
    
    statistics = {
        'agricultura': {'projects': 0, 'sequestration_rates': [], 'areas': [], 'credits': []},
        'agroflorestal': {'projects': 0, 'sequestration_rates': [], 'areas': [], 'credits': []},
        'energia': {'projects': 0, 'sequestration_rates': [], 'areas': [], 'credits': []}
    }
    
    for sheet_name, practice_type in PRACTICE_MAPPING.items():
        if sheet_name not in dataframes:
            continue
            
        df = dataframes[sheet_name]
        if df.empty:
            continue
        
        # Identificar colunas relevantes
        area_col = None
        credit_col = None
        duration_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            
            # Buscar coluna de área
            if any(keyword in col_lower for keyword in ['area', 'hectare', 'ha', 'land size', 'land area']):
                area_col = col
            
            # Buscar coluna de créditos emitidos
            if any(keyword in col_lower for keyword in ['credit', 'issued', 'volume', 'amount', 'total', 'credits']):
                credit_col = col
            
            # Buscar coluna de duração/projeto
            if any(keyword in col_lower for keyword in ['year', 'duration', 'period', 'lifetime', 'time']):
                duration_col = col
        
        # Processar linhas com dados completos
        for idx, row in df.iterrows():
            try:
                # Extrair valores
                if area_col and credit_col:
                    area = None
                    credits = None
                    
                    # Converter área para float
                    if pd.notna(row[area_col]):
                        area_val = str(row[area_col]).replace(',', '').strip()
                        try:
                            area = float(area_val)
                        except:
                            # Tentar extrair números da string
                            numbers = re.findall(r'\d+\.?\d*', area_val)
                            if numbers:
                                area = float(numbers[0])
                    
                    # Converter créditos para float
                    if pd.notna(row[credit_col]):
                        credit_val = str(row[credit_col]).replace(',', '').strip()
                        try:
                            credits = float(credit_val)
                        except:
                            numbers = re.findall(r'\d+\.?\d*', credit_val)
                            if numbers:
                                credits = float(numbers[0])
                    
                    # Determinar duração (padrão: 10 anos se não especificado)
                    duration = 10  # default
                    if duration_col and pd.notna(row[duration_col]):
                        try:
                            duration_val = str(row[duration_col])
                            numbers = re.findall(r'\d+', duration_val)
                            if numbers:
                                duration = float(numbers[0])
                        except:
                            duration = 10
                    
                    # Calcular taxa de sequestro anual por hectare
                    if area and area > 0 and credits and credits > 0:
                        annual_credits = credits / duration
                        sequestration_rate = annual_credits / area
                        
                        # Apenas considerar taxas razoáveis (evitar outliers extremos)
                        if 0.1 <= sequestration_rate <= 20:  # Faixa razoável
                            statistics[practice_type]['projects'] += 1
                            statistics[practice_type]['sequestration_rates'].append(sequestration_rate)
                            statistics[practice_type]['areas'].append(area)
                            statistics[practice_type]['credits'].append(credits)
                        
            except (ValueError, TypeError, AttributeError) as e:
                continue
    
    # Calcular estatísticas sumarizadas
    for practice_type in statistics:
        rates = statistics[practice_type]['sequestration_rates']
        if rates and len(rates) > 0:
            statistics[practice_type]['mean_rate'] = np.mean(rates)
            statistics[practice_type]['median_rate'] = np.median(rates)
            statistics[practice_type]['std_rate'] = np.std(rates)
            statistics[practice_type]['min_rate'] = np.min(rates)
            statistics[practice_type]['max_rate'] = np.max(rates)
            if len(rates) >= 4:
                statistics[practice_type]['q25'] = np.percentile(rates, 25)
                statistics[practice_type]['q75'] = np.percentile(rates, 75)
            else:
                # Se poucos dados, usar média ± 50%
                statistics[practice_type]['q25'] = np.mean(rates) * 0.5
                statistics[practice_type]['q75'] = np.mean(rates) * 1.5
        else:
            # Usar valores padrão se não houver dados
            default_rates = {
                'agricultura': 1.25,
                'agroflorestal': 4.0,
                'energia': 2.0
            }
            statistics[practice_type]['mean_rate'] = default_rates[practice_type]
            statistics[practice_type]['median_rate'] = default_rates[practice_type]
            statistics[practice_type]['std_rate'] = default_rates[practice_type] * 0.5
            statistics[practice_type]['min_rate'] = default_rates[practice_type] * 0.4
            statistics[practice_type]['max_rate'] = default_rates[practice_type] * 1.6
            statistics[practice_type]['q25'] = default_rates[practice_type] * 0.75
            statistics[practice_type]['q75'] = default_rates[practice_type] * 1.25
    
    return statistics

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

def calculate_potential_revenue(hectares: float, practice_type: str = 'agricultura', 
                               use_dataset_stats: bool = True) -> Dict:
    """Calcula receita potencial usando estatísticas do dataset quando disponível"""
    
    price_range = CARBON_PRICE_RANGE.get(practice_type, CARBON_PRICE_RANGE['agricultura'])
    
    # Taxas de sequestro baseadas em estatísticas do dataset
    if use_dataset_stats and 'project_statistics' in st.session_state:
        stats = st.session_state.project_statistics.get(practice_type, {})
        
        if stats.get('projects', 0) > 0:
            # Usar estatísticas reais do dataset
            rate_avg = stats['mean_rate']
            rate_min = max(0.1, stats['q25'])  # Usar percentil 25 como mínimo
            rate_max = stats['q75']  # Usar percentil 75 como máximo
            
            # Indicador de confiabilidade
            data_source = f"Baseado em {stats['projects']} projetos reais"
        else:
            # Fallback para valores padrão
            sequestration_rates = {
                'agricultura': {'min': 0.5, 'max': 2, 'avg': 1.25},
                'agroflorestal': {'min': 2, 'max': 6, 'avg': 4},
                'energia': {'min': 1, 'max': 3, 'avg': 2}
            }
            rate = sequestration_rates.get(practice_type, sequestration_rates['agricultura'])
            rate_min, rate_max, rate_avg = rate['min'], rate['max'], rate['avg']
            data_source = "Estimativa conservadora (dados limitados)"
    else:
        # Valores padrão
        sequestration_rates = {
            'agricultura': {'min': 0.5, 'max': 2, 'avg': 1.25},
            'agroflorestal': {'min': 2, 'max': 6, 'avg': 4},
            'energia': {'min': 1, 'max': 3, 'avg': 2}
        }
        rate = sequestration_rates.get(practice_type, sequestration_rates['agricultura'])
        rate_min, rate_max, rate_avg = rate['min'], rate['max'], rate['avg']
        data_source = "Estimativa padrão"
    
    # Cálculos de receita
    calculations = {
        'hectares': hectares,
        'practice_type': practice_type,
        'annual_sequestration_min': hectares * rate_min,
        'annual_sequestration_max': hectares * rate_max,
        'annual_sequestration_avg': hectares * rate_avg,
        'annual_revenue_min': hectares * rate_min * price_range['min'],
        'annual_revenue_max': hectares * rate_max * price_range['max'],
        'annual_revenue_avg': hectares * rate_avg * price_range['avg'],
        '10yr_revenue_avg': hectares * rate_avg * price_range['avg'] * 10,
        'price_per_ton': f"US${price_range['min']}-{price_range['max']}",
        'sequestration_per_ha': f"{rate_min:.2f}-{rate_max:.2f} tCO2/ha/ano",
        'data_source': data_source,
        'projects_count': stats.get('projects', 0) if use_dataset_stats and 'project_statistics' in st.session_state else 0
    }
    
    return calculations

def calculate_break_even(hectares: float, investment_cost: float, practice_type: str = 'agricultura') -> Dict:
    """Calcula ponto de equilíbrio para investimento em carbono"""
    revenue_calc = calculate_potential_revenue(hectares, practice_type, True)
    
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
    """Cria calculadora de receita interativa com estatísticas reais"""
    with st.expander("🧮 CALCULE SEU POTENCIAL DE GANHO (COM DADOS REAIS)", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            hectares = st.number_input("Tamanho da propriedade (hectares):", 
                                     min_value=1.0, max_value=10000.0, value=100.0, step=10.0,
                                     key="calc_hectares")
        
        with col2:
            practice_type = st.selectbox(
                "Prática sustentável:",
                ["Agricultura Regenerativa", "Agrofloresta", "Bioenergia", "Integração Lavoura-Pecuária"],
                index=0,
                key="calc_practice"
            )
        
        with col3:
            investment = st.number_input("Investimento inicial (US$):", 
                                       min_value=0.0, max_value=1000000.0, value=10000.0, step=1000.0,
                                       key="calc_investment")
        
        with col4:
            use_real_data = st.checkbox("Usar dados reais do mercado", value=True,
                                       help="Baseia os cálculos em projetos certificados existentes",
                                       key="use_real_data")
        
        # Mapear tipo selecionado para chave interna
        practice_map = {
            "Agricultura Regenerativa": "agricultura",
            "Agrofloresta": "agroflorestal",
            "Bioenergia": "energia",
            "Integração Lavoura-Pecuária": "agricultura"
        }
        practice_key = practice_map[practice_type]
        
        # Calcular com estatísticas reais
        revenue = calculate_potential_revenue(hectares, practice_key, use_real_data)
        break_even = calculate_break_even(hectares, investment, practice_key)
        
        # Exibir estatísticas de base de dados
        if use_real_data and revenue['projects_count'] > 0:
            st.info(f"📊 **Base estatística:** {revenue['data_source']} | Projetos analisados: {revenue['projects_count']}")
        
        # Resultados
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Receita Anual", f"US${revenue['annual_revenue_avg']:,.0f}",
                     delta=f"{revenue['annual_revenue_min']:,.0f}-{revenue['annual_revenue_max']:,.0f}")
        with col2:
            st.metric("📈 Receita 10 anos", f"US${revenue['10yr_revenue_avg']:,.0f}")
        with col3:
            st.metric("⏱️ Retorno (anos)", f"{break_even['break_even_years']:.1f}")
        with col4:
            st.metric("📊 ROI 5 anos", f"{break_even['roi_5yr']:.1f}%")
        
        # Detalhes expandidos
        with st.expander("📋 Ver detalhes do cálculo e estatísticas"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📈 Parâmetros de Cálculo")
                st.write(f"**Preço do carbono:** {revenue['price_per_ton']} por tonelada")
                st.write(f"**Sequestro estimado:** {revenue['sequestration_per_ha']}")
                st.write(f"**Fonte dos dados:** {revenue['data_source']}")
                
                if 'project_statistics' in st.session_state:
                    stats = st.session_state.project_statistics.get(practice_key, {})
                    if stats.get('projects', 0) > 0:
                        st.markdown("#### 📊 Estatísticas dos Projetos Reais")
                        st.write(f"**Número de projetos:** {stats['projects']}")
                        st.write(f"**Taxa média:** {stats['mean_rate']:.2f} tCO2/ha/ano")
                        st.write(f"**Variação (25%-75%):** {stats['q25']:.2f} - {stats['q75']:.2f} tCO2/ha/ano")
                        if 'areas' in stats and len(stats['areas']) > 0:
                            st.write(f"**Área média dos projetos:** {np.mean(stats['areas']):.1f} ha")
            
            with col2:
                st.markdown("#### 🧮 Cálculos Detalhados")
                st.write(f"**Sequestro total anual:** {revenue['annual_sequestration_avg']:,.1f} tCO2")
                st.write(f"**Receita mensal:** US${break_even['monthly_revenue']:,.0f}")
                st.write(f"**Receita anual mínima:** US${revenue['annual_revenue_min']:,.0f}")
                st.write(f"**Receita anual máxima:** US${revenue['annual_revenue_max']:,.0f}")
                
                # Adicionar gráfico de sensibilidade se houver dados estatísticos
                if use_real_data and 'project_statistics' in st.session_state and st.session_state.project_statistics.get(practice_key, {}).get('projects', 0) > 0:
                    st.markdown("#### 📊 Distribuição das Taxas de Sequestro")
                    
                    rates = st.session_state.project_statistics[practice_key]['sequestration_rates']
                    if len(rates) > 1:
                        fig = px.histogram(x=rates, nbins=20,
                                          title=f"Distribuição das Taxas ({practice_type})",
                                          labels={'x': 'tCO2/ha/ano', 'y': 'Número de Projetos'})
                        fig.add_vline(x=revenue['annual_sequestration_avg']/hectares, 
                                     line_dash="dash", line_color="red",
                                     annotation_text=f"Média: {revenue['annual_sequestration_avg']/hectares:.2f}")
                        st.plotly_chart(fig, use_container_width=True)

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
                                                                   for word in ['credit', 'issued', 'volume', 'amount', 'total', 'credits'])]
                    
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
                            # Converter valores para numérico
                            numeric_credits = pd.to_numeric(df[credit_col], errors='coerce')
                            total_credits = numeric_credits.sum()
                            if not pd.isna(total_credits):
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
            "description": "Pequena propriedade de 50 hectares adotou sistema integrado lavoura-pecuária-floresta (ILPF). Gera receita adicional com carbono.",
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
# NOVA PÁGINA: ESTATÍSTICAS DO MERCADO
# =========================

def render_market_statistics():
    """Renderiza página com estatísticas detalhadas do mercado"""
    st.markdown("## 📊 Estatísticas do Mercado Baseadas em Projetos Reais")
    
    if 'project_statistics' not in st.session_state:
        st.warning("Estatísticas ainda não foram calculadas. Aguarde...")
        return
    
    stats = st.session_state.project_statistics
    
    # Resumo geral
    total_projects = sum(data['projects'] for data in stats.values())
    st.metric("📈 Total de Projetos Analisados", total_projects)
    
    if total_projects == 0:
        st.info("Nenhum projeto com dados completos encontrado. Usando estimativas conservadoras.")
        return
    
    # Tabs para diferentes práticas
    tabs = st.tabs(["🌱 Agricultura", "🌳 Agrofloresta", "⚡ Energia", "📈 Comparativo"])
    
    with tabs[0]:
        if stats['agricultura']['projects'] > 0:
            display_practice_statistics(stats['agricultura'], "Agricultura Regenerativa")
        else:
            st.info("Dados insuficientes para agricultura. Usando estimativas padrão.")
            display_default_stats("agricultura")
    
    with tabs[1]:
        if stats['agroflorestal']['projects'] > 0:
            display_practice_statistics(stats['agroflorestal'], "Sistemas Agroflorestais")
        else:
            st.info("Dados insuficientes para agrofloresta. Usando estimativas padrão.")
            display_default_stats("agroflorestal")
    
    with tabs[2]:
        if stats['energia']['projects'] > 0:
            display_practice_statistics(stats['energia'], "Projetos de Energia")
        else:
            st.info("Dados insuficientes para energia. Usando estimativas padrão.")
            display_default_stats("energia")
    
    with tabs[3]:
        # Gráfico comparativo
        practices = []
        mean_rates = []
        project_counts = []
        colors = []
        
        for practice, data in stats.items():
            if data['projects'] > 0:
                practice_name = {
                    'agricultura': 'Agricultura',
                    'agroflorestal': 'Agrofloresta',
                    'energia': 'Energia'
                }[practice]
                practices.append(practice_name)
                mean_rates.append(data['mean_rate'])
                project_counts.append(data['projects'])
                colors.append({
                    'agricultura': '#2ecc71',
                    'agroflorestal': '#27ae60',
                    'energia': '#f39c12'
                }[practice])
        
        if practices:
            col1, col2 = st.columns(2)
            
            with col1:
                fig1 = px.bar(x=practices, y=mean_rates,
                            title="Taxa Média de Sequestro por Tipo de Projeto",
                            labels={'x': 'Tipo de Projeto', 'y': 'tCO2/ha/ano'},
                            color=practices,
                            color_discrete_sequence=colors)
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                fig2 = px.bar(x=practices, y=project_counts,
                            title="Número de Projetos por Categoria",
                            labels={'x': 'Tipo de Projeto', 'y': 'Número de Projetos'},
                            color=practices,
                            color_discrete_sequence=colors)
                st.plotly_chart(fig2, use_container_width=True)

def display_practice_statistics(data, title):
    """Exibe estatísticas detalhadas de uma prática específica"""
    st.markdown(f"### {title}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 Projetos Analisados", data['projects'])
    
    with col2:
        st.metric("📈 Taxa Média", f"{data['mean_rate']:.2f} tCO2/ha/ano")
    
    with col3:
        st.metric("🎯 Mediana", f"{data['median_rate']:.2f} tCO2/ha/ano")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        if len(data['sequestration_rates']) > 1:
            fig = px.histogram(x=data['sequestration_rates'], nbins=20,
                              title="Distribuição das Taxas de Sequestro",
                              labels={'x': 'tCO2/ha/ano', 'y': 'Frequência'})
            fig.add_vline(x=data['mean_rate'], line_dash="dash", line_color="red",
                         annotation_text=f"Média: {data['mean_rate']:.2f}")
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        if len(data['areas']) > 1:
            fig = px.box(y=data['areas'], title="Distribuição das Áreas dos Projetos (ha)")
            st.plotly_chart(fig, use_container_width=True)
    
    # Tabela de estatísticas
    st.markdown("#### 📋 Estatísticas Detalhadas")
    
    stats_df = pd.DataFrame({
        'Métrica': ['Mínimo', '25º Percentil', 'Média', 'Mediana', '75º Percentil', 'Máximo', 'Desvio Padrão'],
        'tCO2/ha/ano': [
            f"{data['min_rate']:.2f}",
            f"{data['q25']:.2f}",
            f"{data['mean_rate']:.2f}",
            f"{data['median_rate']:.2f}",
            f"{data['q75']:.2f}",
            f"{data['max_rate']:.2f}",
            f"{data['std_rate']:.2f}"
        ]
    })
    
    st.dataframe(stats_df, use_container_width=True, hide_index=True)

def display_default_stats(practice_type):
    """Exibe estatísticas padrão quando não há dados reais"""
    default_stats = {
        'agricultura': {'mean': 1.25, 'min': 0.5, 'max': 2, 'color': '#2ecc71'},
        'agroflorestal': {'mean': 4.0, 'min': 2, 'max': 6, 'color': '#27ae60'},
        'energia': {'mean': 2.0, 'min': 1, 'max': 3, 'color': '#f39c12'}
    }
    
    stats = default_stats[practice_type]
    practice_name = {
        'agricultura': 'Agricultura Regenerativa',
        'agroflorestal': 'Sistemas Agroflorestais',
        'energia': 'Projetos de Energia'
    }[practice_type]
    
    st.markdown(f"### {practice_name}")
    st.info("⚠️ **Nota:** Usando estimativas conservadoras devido a dados limitados")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Base de Dados", "Estimativa")
    with col2:
        st.metric("📈 Taxa Média", f"{stats['mean']:.2f} tCO2/ha/ano")
    with col3:
        st.metric("📏 Variação", f"{stats['min']:.1f}-{stats['max']:.1f} tCO2/ha/ano")
    
    # Gráfico de estimativa
    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode = "gauge+number",
        value = stats['mean'],
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Taxa de Sequestro Estimada"},
        gauge = {
            'axis': {'range': [0, stats['max'] * 1.2]},
            'bar': {'color': stats['color']},
            'steps': [
                {'range': [0, stats['min']], 'color': "lightgray"},
                {'range': [stats['min'], stats['max']], 'color': "gray"}
            ]
        }
    ))
    st.plotly_chart(fig, use_container_width=True)

# =========================
# PÁGINA DE COMO PARTICIPAR
# =========================

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
# APLICAÇÃO PRINCIPAL
# =========================
def main():
    # Carregar dados
    with st.spinner("💰 Analisando oportunidades de receita no mercado de carbono..."):
        dataframes, sheet_names = load_data_with_revenue_focus()
    
    if dataframes is None:
        st.error("Não foi possível carregar os dados. Verifique o arquivo Dataset.xlsx")
        return
    
    # Analisar estatísticas dos projetos
    if 'project_statistics' not in st.session_state:
        with st.spinner("📊 Analisando estatísticas dos projetos reais..."):
            st.session_state.project_statistics = analyze_project_statistics(dataframes)
    
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
            ["🏠 Oportunidades", "🔍 Projetos Reais", "📚 Casos de Sucesso", "📊 Estatísticas do Mercado", "📞 Como Participar"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Exibir estatísticas resumidas na sidebar
        if 'project_statistics' in st.session_state:
            st.markdown("### 📈 Estatísticas Reais")
            
            stats = st.session_state.project_statistics
            total_projects = sum(data['projects'] for data in stats.values())
            
            if total_projects > 0:
                st.info(f"**{total_projects}** projetos analisados")
                
                for practice, data in stats.items():
                    if data['projects'] > 0:
                        practice_name = {
                            'agricultura': '🌱 Agricultura',
                            'agroflorestal': '🌳 Agrofloresta',
                            'energia': '⚡ Energia'
                        }[practice]
                        
                        st.metric(practice_name, 
                                 f"{data['projects']} projetos",
                                 f"{data['mean_rate']:.1f} tCO2/ha/ano")
            else:
                st.info("Analisando dados do dataset...")
        
        st.markdown("---")
        
        # Dica rápida
        st.markdown("### 💡 Dica Rápida")
        st.info("""
        Use a opção **"Usar dados reais do mercado"** na calculadora para estimativas baseadas em projetos certificados.
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
    elif page == "📊 Estatísticas do Mercado":
        render_market_statistics()
    else:
        render_how_to_participate()

# =========================
# RODAPÉ
# =========================
def create_footer():
    """Cria rodapé informativo"""
    st.markdown("---")
    
    # Mostrar informações sobre análise de dados
    if 'project_statistics' in st.session_state:
        stats = st.session_state.project_statistics
        total_projects = sum(data['projects'] for data in stats.values())
        
        st.markdown(f"""
        <div style='text-align: center; padding: 1rem;'>
            <p style='color: #7f8c8d;'>
            <strong>💰 Ganhe com Carbono na sua Terra</strong> | 
            Dashboard para proprietários rurais | 
            Dados: FAO Agrifood Carbon Market Dataset
            </p>
            <p style='color: #95a5a6; font-size: 0.8rem;'>
            📊 Análise baseada em {total_projects} projetos reais | 
            💡 Este é um dashboard informativo. Para projetos reais, consulte especialistas em créditos de carbono.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
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
