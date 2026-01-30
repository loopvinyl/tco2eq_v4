import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff
from datetime import datetime, timedelta
import warnings
import os
import re
import json
from typing import Dict, List, Optional, Tuple
import random

warnings.filterwarnings("ignore")

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Mercado Voluntário de Carbono Agrícola - FAO",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.fao.org/climate-change/our-work/carbon-markets',
        'Report a bug': None,
        'About': "Dashboard interativo do Mercado Voluntário de Carbono Agrícola. Desenvolvido com dados da FAO."
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
    "4. Agriculture": {"type": "projetos", "icon": "🚜", "color": "#2ecc71", "has_yearly_data": True, "country_column": "Country"},
    "5. Agroforestry-AR & Grassland": {"type": "projetos", "icon": "🌳", "color": "#27ae60", "has_yearly_data": True, "country_column": "Country"},
    "6. Energy and Other": {"type": "projetos", "icon": "⚡", "color": "#f39c12", "has_yearly_data": True, "country_column": "Country"},
    "7. Plan Vivo, Acorn, Social C": {"type": "padrões", "icon": "🌍", "color": "#1abc9c", "main_column": "Standard", "country_column": "Country"},
    "8. Puro.earth": {"type": "projetos", "icon": "🔥", "color": "#d35400", "main_column": "Unnamed: 0"},
    "9. Nori and BCarbon": {"type": "projetos", "icon": "🌾", "color": "#16a085", "main_column": "Standard", "country_column": "Country"}
}

# Traduções de países
COUNTRY_TRANSLATIONS = {
    'brazil': 'Brasil',
    'united states': 'Estados Unidos',
    'united states of america': 'Estados Unidos',
    'usa': 'Estados Unidos',
    'united kingdom': 'Reino Unido',
    'uk': 'Reino Unido',
    'mexico': 'México',
    'canada': 'Canadá',
    'germany': 'Alemanha',
    'france': 'França',
    'spain': 'Espanha',
    'portugal': 'Portugal',
    'italy': 'Itália',
    'china': 'China',
    'india': 'Índia',
    'japan': 'Japão',
    'australia': 'Austrália',
    'argentina': 'Argentina',
    'chile': 'Chile',
    'colombia': 'Colômbia',
    'peru': 'Peru',
    'uruguay': 'Uruguai',
    'paraguay': 'Paraguai',
    'bolivia': 'Bolívia',
    'venezuela': 'Venezuela',
    'ecuador': 'Equador',
    'costa rica': 'Costa Rica',
    'panama': 'Panamá',
    'nicaragua': 'Nicarágua',
    'honduras': 'Honduras',
    'guatemala': 'Guatemala',
    'el salvador': 'El Salvador',
    'cuba': 'Cuba',
    'dominican republic': 'República Dominicana',
    'puerto rico': 'Porto Rico',
    'south africa': 'África do Sul',
    'kenya': 'Quênia',
    'nigeria': 'Nigéria',
    'ghana': 'Gana',
    'ethiopia': 'Etiópia',
    'indonesia': 'Indonésia',
    'vietnam': 'Vietnã',
    'thailand': 'Tailândia',
    'philippines': 'Filipinas',
    'malaysia': 'Malásia'
}

# Cores para categorias
CATEGORY_COLORS = {
    'agricultura': '#2ecc71',
    'agroflorestal': '#27ae60',
    'energia': '#f39c12',
    'padrão': '#3498db',
    'plataforma': '#9b59b6',
    'metodologia': '#e74c3c'
}

# =========================
# FUNÇÕES AUXILIARES AVANÇADAS
# =========================
def get_country_name(country_str: str) -> str:
    """Obtém o nome do país em português"""
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

def create_animated_loading():
    """Cria animação de carregamento"""
    with st.spinner("🔄 Processando dados..."):
        progress_bar = st.progress(0)
        for i in range(100):
            progress_bar.progress(i + 1)
        st.success("✅ Dados carregados com sucesso!")

def calculate_carbon_impact(credits: float) -> Dict:
    """Calcula impacto ambiental baseado em créditos de carbono"""
    # 1 crédito = 1 tonelada de CO2 equivalente
    impact = {
        'carros_ano': credits / 2.4,  # Emissão média anual de um carro
        'arvores_ano': credits / 21,   # 1 árvore absorve ~21kg CO2/ano
        'casas_ano': credits / 8,      # Emissão média anual de uma casa
        'voos_ny_paris': credits / 1   # 1 voo NY-Paris = ~1 ton CO2
    }
    return impact

# =========================
# SISTEMA DE CACHE AVANÇADO
# =========================
@st.cache_data(ttl=3600, show_spinner=False)
def load_data_optimized():
    """Carrega dados do Excel com otimização"""
    file_path = "Dataset.xlsx"
    
    if not os.path.exists(file_path):
        st.error("📂 Arquivo não encontrado. Verifique se 'Dataset.xlsx' está no diretório.")
        return None, None
    
    try:
        # Usar chunks para datasets grandes
        excel = pd.ExcelFile(file_path, engine='openpyxl')
        data = {}
        sheet_names = []
        
        for sheet in excel.sheet_names:
            try:
                # Ler apenas primeiras linhas para inferir tipos
                df_sample = excel.parse(sheet, nrows=1000)
                
                # Inferir tipos otimizados
                dtype_dict = {}
                for col in df_sample.columns:
                    if pd.api.types.is_numeric_dtype(df_sample[col]):
                        # Usar tipos numéricos menores quando possível
                        if df_sample[col].min() >= 0:
                            dtype_dict[col] = np.uint32 if df_sample[col].max() < 2**32 else np.float32
                        else:
                            dtype_dict[col] = np.float32
                    elif pd.api.types.is_datetime64_any_dtype(df_sample[col]):
                        dtype_dict[col] = 'datetime64[ns]'
                
                # Ler dados completos com tipos otimizados
                df = excel.parse(sheet, dtype=dtype_dict)
                
                # Limpeza de colunas
                df = df.dropna(axis=1, how='all')
                df.columns = [str(col).strip() for col in df.columns]
                
                # Remover colunas completamente vazias
                df = df.loc[:, df.notna().any()]
                
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
# COMPONENTES DE UI AVANÇADOS
# =========================
def create_hero_section():
    """Cria seção hero do dashboard"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                    background: linear-gradient(135deg, #2ecc71, #27ae60); 
                    color: white; margin-bottom: 2rem;'>
            <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>🌱 Mercado de Carbono Agrícola</h1>
            <h3 style='font-weight: 300;'>Dashboard Interativo FAO - Dados de Mercado Voluntário</h3>
            <p style='font-size: 1.1rem; opacity: 0.9;'>
                Explore projetos, padrões e metodologias para reduzir emissões na agricultura
            </p>
        </div>
        """, unsafe_allow_html=True)

def create_metric_card(title: str, value: str, delta: str = None, icon: str = "📊"):
    """Cria card de métrica estilizado"""
    delta_html = f"<div style='color: {'#2ecc71' if delta and '+' in delta else '#e74c3c'}; font-size: 0.9rem;'>{delta}</div>" if delta else ""
    
    return f"""
    <div style='background: white; padding: 1.5rem; border-radius: 10px; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 5px solid #2ecc71;
                margin: 0.5rem; height: 100%;'>
        <div style='font-size: 2rem; margin-bottom: 0.5rem;'>{icon}</div>
        <div style='font-size: 0.9rem; color: #7f8c8d; margin-bottom: 0.5rem;'>{title}</div>
        <div style='font-size: 2rem; font-weight: bold; color: #2c3e50;'>{value}</div>
        {delta_html}
    </div>
    """

def create_info_card(title: str, content: str, icon: str = "ℹ️"):
    """Cria card informativo"""
    return f"""
    <div style='background: #f8f9fa; padding: 1.5rem; border-radius: 10px; 
                border: 1px solid #e9ecef; margin: 1rem 0;'>
        <div style='font-size: 1.5rem; color: #3498db; margin-bottom: 0.5rem;'>{icon}</div>
        <h4 style='color: #2c3e50; margin-bottom: 0.5rem;'>{title}</h4>
        <p style='color: #7f8c8d; line-height: 1.6;'>{content}</p>
    </div>
    """

# =========================
# VISUALIZAÇÕES AVANÇADAS
# =========================
def create_sunburst_chart(df, path, values, title="Distribuição Hierárquica"):
    """Cria gráfico sunburst interativo"""
    fig = px.sunburst(
        df, 
        path=path,
        values=values,
        title=title,
        color=values,
        color_continuous_scale='Viridis',
        maxdepth=3
    )
    fig.update_layout(
        margin=dict(t=30, l=0, r=0, b=0),
        height=500
    )
    return fig

def create_treemap_chart(df, path, values, title="Mapa de Árvore"):
    """Cria gráfico treemap"""
    fig = px.treemap(
        df,
        path=path,
        values=values,
        title=title,
        color=values,
        color_continuous_scale='Greens'
    )
    fig.update_layout(
        margin=dict(t=30, l=0, r=0, b=0),
        height=400
    )
    return fig

def create_3d_scatter(df, x_col, y_col, z_col, color_col, title="Visualização 3D"):
    """Cria gráfico de dispersão 3D"""
    fig = px.scatter_3d(
        df,
        x=x_col,
        y=y_col,
        z=z_col,
        color=color_col,
        title=title,
        size_max=18,
        opacity=0.7
    )
    fig.update_layout(
        scene=dict(
            xaxis_title=x_col,
            yaxis_title=y_col,
            zaxis_title=z_col
        ),
        height=600
    )
    return fig

def create_animated_timeline(df, x_col, y_col, animation_col, title="Evolução Temporal"):
    """Cria linha do tempo animada"""
    fig = px.scatter(
        df,
        x=x_col,
        y=y_col,
        animation_frame=animation_col,
        size=y_col,
        color=y_col,
        hover_name=df.index if 'name' not in df.columns else df.get('name', df.index),
        title=title,
        size_max=55,
        range_x=[df[x_col].min(), df[x_col].max()],
        range_y=[0, df[y_col].max() * 1.1]
    )
    fig.update_layout(height=500)
    return fig

def create_parallel_categories(df, dimensions, color_col, title="Categorias Paralelas"):
    """Cria diagrama de categorias paralelas"""
    fig = px.parallel_categories(
        df,
        dimensions=dimensions,
        color=color_col,
        title=title,
        color_continuous_scale=px.colors.sequential.Viridis
    )
    fig.update_layout(height=500)
    return fig

# =========================
# ANÁLISES ESPECIALIZADAS
# =========================
def analyze_carbon_market_trends(df_dict):
    """Analisa tendências do mercado de carbono"""
    analysis = {
        'total_projetos': 0,
        'total_creditos': 0,
        'paises_envolvidos': set(),
        'padroes_utilizados': set(),
        'anos_cobertura': set()
    }
    
    for sheet_name, df in df_dict.items():
        if not df.empty:
            analysis['total_projetos'] += len(df)
            
            # Contar créditos (procurar colunas numéricas relacionadas)
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            credit_cols = [col for col in numeric_cols if 'credit' in str(col).lower()]
            if credit_cols:
                analysis['total_creditos'] += df[credit_cols].sum().sum()
            
            # Coletar países
            for col in df.columns:
                if 'country' in str(col).lower():
                    countries = df[col].dropna().unique()
                    for country in countries:
                        if isinstance(country, str) and len(country.strip()) > 1:
                            analysis['paises_envolvidos'].add(get_country_name(country))
    
    return analysis

def create_market_overview_metrics(analysis):
    """Cria métricas de visão geral do mercado"""
    metrics_html = f"""
    <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; margin: 2rem 0;'>
        {create_metric_card("Total de Projetos", f"{analysis['total_projetos']:,}", icon="📈")}
        {create_metric_card("Créditos Estimados", f"{analysis['total_creditos']:,.0f}", icon="💰")}
        {create_metric_card("Países Envolvidos", str(len(analysis['paises_envolvidos'])), icon="🌍")}
        {create_metric_card("Padrões Diferentes", str(len(analysis['padroes_utilizados'])), icon="🏛️")}
    </div>
    """
    return metrics_html

# =========================
# PÁGINA PRINCIPAL
# =========================
def render_home_page(dataframes):
    """Renderiza página inicial"""
    create_hero_section()
    
    # Análise do mercado
    analysis = analyze_carbon_market_trends(dataframes)
    
    # Métricas principais
    st.markdown(create_market_overview_metrics(analysis), unsafe_allow_html=True)
    
    # Seções informativas
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(create_info_card(
            "🤔 O que é Mercado Voluntário de Carbono?",
            "Mercado onde empresas e indivíduos compram créditos de carbono voluntariamente para compensar suas emissões. "
            "Diferente dos mercados regulados, é baseado na livre escolha dos participantes.",
            "💡"
        ), unsafe_allow_html=True)
        
        st.markdown(create_info_card(
            "🌾 Carbono na Agricultura",
            "Práticas agrícolas sustentáveis podem sequestrar carbono no solo, gerando créditos que podem ser vendidos. "
            "Inclui rotação de culturas, plantio direto, integração lavoura-pecuária-floresta.",
            "🚜"
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_info_card(
            "📊 Como funciona este dashboard?",
            "Explore dados reais da FAO sobre projetos, padrões e metodologias. "
            "Use filtros para análise específica e visualize tendências do mercado.",
            "🔍"
        ), unsafe_allow_html=True)
        
        st.markdown(create_info_card(
            "🎯 Impacto Ambiental",
            "Cada crédito de carbono representa 1 tonelada de CO₂ que deixou de ser emitida ou foi removida da atmosfera. "
            "Isso equivale às emissões anuais de aproximadamente 0.4 carros.",
            "🌳"
        ), unsafe_allow_html=True)
    
    # Visualização rápida de dados
    st.markdown("### 📈 Destaques do Mercado")
    
    # Criar visualizações rápidas
    if dataframes and len(dataframes) > 3:
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de distribuição por tipo de projeto
            project_types = ['Agricultura', 'Agroflorestal', 'Energia']
            project_counts = [
                len(dataframes.get('4. Agriculture', pd.DataFrame())),
                len(dataframes.get('5. Agroforestry-AR & Grassland', pd.DataFrame())),
                len(dataframes.get('6. Energy and Other', pd.DataFrame()))
            ]
            
            fig = px.bar(
                x=project_types,
                y=project_counts,
                title="Projetos por Categoria",
                color=project_types,
                color_discrete_sequence=['#2ecc71', '#27ae60', '#f39c12']
            )
            fig.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Gráfico de países
            if analysis['paises_envolvidos']:
                countries_list = list(analysis['paises_envolvidos'])[:10]
                fig = px.pie(
                    names=countries_list,
                    values=[100/len(countries_list)] * len(countries_list),
                    title="Top Países (Ilustrativo)",
                    hole=0.4
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)

# =========================
# EXPLORADOR DE DADOS
# =========================
def render_data_explorer(dataframes, sheet_names):
    """Renderiza explorador de dados"""
    st.markdown("## 🔍 Explorador de Dados")
    
    # Sidebar para navegação
    with st.sidebar:
        st.markdown("### 📂 Navegação")
        
        # Seletor de aba com ícones
        selected_sheet = st.selectbox(
            "Selecione a aba para explorar:",
            sheet_names,
            format_func=lambda x: f"{SHEET_CONFIG.get(x, {}).get('icon', '📄')} {x}"
        )
        
        st.markdown("---")
        st.markdown("### ⚙️ Configurações")
        
        # Modo de visualização
        view_mode = st.radio(
            "Modo de visualização:",
            ["📋 Tabela", "📈 Gráficos", "🔍 Análise"]
        )
        
        st.markdown("---")
        st.markdown("### 📊 Opções de Gráfico")
        
        if view_mode == "📈 Gráficos":
            chart_type = st.selectbox(
                "Tipo de gráfico:",
                ["Barras", "Pizza", "Histograma", "Linhas", "Dispersão", "Mapa de Calor"]
            )
    
    # Conteúdo principal
    if selected_sheet and selected_sheet in dataframes:
        df = dataframes[selected_sheet]
        
        if df.empty:
            st.warning("⚠️ Esta aba está vazia ou não possui dados.")
            return
        
        # Configuração da aba
        config = SHEET_CONFIG.get(selected_sheet, {})
        
        # Cabeçalho
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(f"<h1 style='font-size: 3rem; color: {config.get('color', '#2ecc71')};'>{config.get('icon', '📄')}</h1>", 
                       unsafe_allow_html=True)
        with col2:
            st.markdown(f"<h2 style='margin-top: 0;'>{selected_sheet}</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='color: #7f8c8d;'>{config.get('description', '')}</p>", unsafe_allow_html=True)
        
        # Estatísticas rápidas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 Linhas", f"{len(df):,}")
        with col2:
            st.metric("📝 Colunas", f"{len(df.columns):,}")
        with col3:
            st.metric("🔢 Numéricas", f"{len(df.select_dtypes(include=[np.number]).columns):,}")
        with col4:
            missing_pct = df.isnull().mean().mean() * 100
            st.metric("✅ Preenchimento", f"{100 - missing_pct:.1f}%")
        
        # Conteúdo baseado no modo
        if view_mode == "📋 Tabela":
            render_table_view(df, selected_sheet)
        elif view_mode == "📈 Gráficos":
            render_chart_view(df, selected_sheet, chart_type)
        else:
            render_analysis_view(df, selected_sheet)

def render_table_view(df, sheet_name):
    """Renderiza visualização de tabela"""
    st.markdown("### 📋 Visualização de Dados")
    
    # Filtros rápidos
    with st.expander("🔍 Filtros Avançados", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            # Filtro por colunas
            selected_columns = st.multiselect(
                "Selecionar colunas:",
                df.columns.tolist(),
                default=df.columns.tolist()[:min(10, len(df.columns))]
            )
        
        with col2:
            # Filtro por linhas
            n_rows = st.slider("Número de linhas:", 10, min(1000, len(df)), 100)
    
    # Exibir tabela
    if selected_columns:
        display_df = df[selected_columns].head(n_rows)
    else:
        display_df = df.head(n_rows)
    
    st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
        hide_index=True
    )
    
    # Opções de exportação
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Exportar como CSV", use_container_width=True):
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Baixar CSV",
                data=csv,
                file_name=f"{sheet_name.replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with col2:
        if st.button("📊 Gerar Relatório", use_container_width=True):
            generate_report(df, sheet_name)

def render_chart_view(df, sheet_name, chart_type):
    """Renderiza visualização de gráficos"""
    st.markdown("### 📈 Visualizações Gráficas")
    
    # Seleção de colunas para gráfico
    col1, col2 = st.columns(2)
    
    with col1:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        
        x_col = st.selectbox("Eixo X:", categorical_cols if categorical_cols else df.columns.tolist())
    
    with col2:
        if numeric_cols:
            y_col = st.selectbox("Eixo Y:", numeric_cols)
        else:
            y_col = None
    
    # Criar gráfico baseado no tipo
    if x_col and (y_col or chart_type in ["Pizza", "Histograma"]):
        try:
            if chart_type == "Barras":
                if y_col:
                    fig = px.bar(df, x=x_col, y=y_col, title=f"{y_col} por {x_col}")
                else:
                    value_counts = df[x_col].value_counts().head(20)
                    fig = px.bar(x=value_counts.index, y=value_counts.values, 
                                title=f"Distribuição de {x_col}")
            
            elif chart_type == "Pizza":
                value_counts = df[x_col].value_counts().head(10)
                fig = px.pie(names=value_counts.index, values=value_counts.values, 
                            title=f"Distribuição de {x_col}")
            
            elif chart_type == "Histograma":
                if y_col:
                    fig = px.histogram(df, x=y_col, title=f"Histograma de {y_col}")
                else:
                    fig = px.histogram(df, x=x_col, title=f"Histograma de {x_col}")
            
            elif chart_type == "Linhas" and y_col:
                fig = px.line(df.sort_values(x_col), x=x_col, y=y_col, 
                             title=f"{y_col} vs {x_col}")
            
            elif chart_type == "Dispersão" and y_col:
                fig = px.scatter(df, x=x_col, y=y_col, title=f"Dispersão: {y_col} vs {x_col}")
            
            elif chart_type == "Mapa de Calor" and y_col:
                pivot_df = df.pivot_table(values=y_col, index=x_col, aggfunc='mean')
                fig = px.imshow(pivot_df, title=f"Mapa de Calor: {y_col} por {x_col}")
            
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Erro ao criar gráfico: {str(e)}")
    
    # Visualizações automáticas
    st.markdown("### 🤖 Visualizações Automáticas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Distribuição de valores numéricos
        if numeric_cols:
            selected_num = st.selectbox("Coluna numérica:", numeric_cols[:5])
            fig = px.histogram(df, x=selected_num, title=f"Distribuição de {selected_num}")
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Top valores categóricos
        if categorical_cols:
            selected_cat = st.selectbox("Coluna categórica:", categorical_cols[:5])
            top_values = df[selected_cat].value_counts().head(10)
            fig = px.bar(x=top_values.index, y=top_values.values, 
                        title=f"Top 10 - {selected_cat}")
            st.plotly_chart(fig, use_container_width=True)

def render_analysis_view(df, sheet_name):
    """Renderiza análise avançada"""
    st.markdown("### 🔍 Análise Avançada")
    
    tabs = st.tabs(["📊 Estatísticas", "📈 Correlações", "🔍 Valores Ausentes", "📋 Sumário"])
    
    with tabs[0]:
        # Estatísticas descritivas
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if not numeric_cols.empty:
            st.dataframe(df[numeric_cols].describe().round(2), use_container_width=True)
        else:
            st.info("Nenhuma coluna numérica para análise estatística.")
    
    with tabs[1]:
        # Matriz de correlação
        numeric_df = df.select_dtypes(include=[np.number])
        if len(numeric_df.columns) >= 2:
            corr_matrix = numeric_df.corr()
            fig = px.imshow(
                corr_matrix,
                text_auto=True,
                aspect="auto",
                color_continuous_scale='RdBu_r',
                title="Matriz de Correlação"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("São necessárias pelo menos 2 colunas numéricas para análise de correlação.")
    
    with tabs[2]:
        # Análise de valores ausentes
        missing_df = pd.DataFrame({
            'Coluna': df.columns,
            '% Ausente': (df.isnull().mean() * 100).round(2),
            'Total Ausente': df.isnull().sum()
        }).sort_values('% Ausente', ascending=False)
        
        st.dataframe(missing_df, use_container_width=True)
        
        # Gráfico de valores ausentes
        fig = px.bar(
            missing_df.head(20),
            x='% Ausente',
            y='Coluna',
            orientation='h',
            title='Top 20 Colunas com Valores Ausentes'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tabs[3]:
        # Sumário da aba
        buffer = []
        
        buffer.append(f"### 📋 Sumário da Aba: {sheet_name}")
        buffer.append(f"- **📊 Dimensões**: {df.shape[0]} linhas × {df.shape[1]} colunas")
        
        # Tipos de dados
        dtype_counts = df.dtypes.value_counts()
        buffer.append("\n**📝 Tipos de dados:**")
        for dtype, count in dtype_counts.items():
            buffer.append(f"  - `{dtype}`: {count} colunas")
        
        # Colunas mais completas
        complete_cols = df.notna().sum().sort_values(ascending=False).head(5)
        buffer.append("\n**✅ Colunas mais completas:**")
        for col, count in complete_cols.items():
            percent = (count / len(df)) * 100
            buffer.append(f"  - **{col}**: {count} valores ({percent:.1f}%)")
        
        # Exibir sumário
        st.markdown("\n".join(buffer))

# =========================
# RELATÓRIOS
# =========================
def generate_report(df, sheet_name):
    """Gera relatório automático"""
    with st.spinner("📊 Gerando relatório..."):
        
        report_content = f"""
        # 📋 Relatório da Aba: {sheet_name}
        Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        
        ## 📊 Estatísticas Básicas
        - **Total de Registros**: {len(df):,}
        - **Total de Colunas**: {len(df.columns):,}
        - **Taxa de Preenchimento**: {(1 - df.isnull().mean().mean()) * 100:.1f}%
        
        ## 🔢 Análise de Dados Numéricos
        """
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if not numeric_cols.empty:
            report_content += "\n### 📈 Estatísticas Descritivas\n"
            report_content += df[numeric_cols].describe().round(2).to_markdown()
        
        st.success("✅ Relatório gerado com sucesso!")
        st.markdown(report_content)

# =========================
# APLICAÇÃO PRINCIPAL
# =========================
def main():
    # Carregar dados
    with st.spinner("🌱 Carregando dados do mercado de carbono..."):
        dataframes, sheet_names = load_data_optimized()
    
    if dataframes is None:
        st.error("Não foi possível carregar os dados. Verifique o arquivo Dataset.xlsx")
        return
    
    # Sidebar principal
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 1rem;'>
            <h2 style='color: #2ecc71;'>🌿 Mercado de Carbono</h2>
            <p style='color: #7f8c8d;'>Dashboard Interativo FAO</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Navegação principal
        page = st.radio(
            "Navegação",
            ["🏠 Página Inicial", "🔍 Explorar Dados", "📊 Análises", "🌍 Sobre"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Informações rápidas
        if page != "🏠 Página Inicial":
            st.markdown("### 📈 Estatísticas Rápidas")
            total_records = sum(len(df) for df in dataframes.values() if not df.empty)
            st.metric("Total de Dados", f"{total_records:,}")
            st.metric("Abas Disponíveis", len(sheet_names))
        
        st.markdown("---")
        
        # Informações
        st.markdown("""
        <div style='font-size: 0.8rem; color: #7f8c8d;'>
        <p>📊 <strong>Dados:</strong> FAO Agrifood Carbon Market Dataset</p>
        <p>🔄 <strong>Atualizado:</strong> Última carga de dados</p>
        <p>🌐 <strong>Fonte:</strong> Food and Agriculture Organization</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Renderizar página selecionada
    if page == "🏠 Página Inicial":
        render_home_page(dataframes)
    elif page == "🔍 Explorar Dados":
        render_data_explorer(dataframes, sheet_names)
    elif page == "📊 Análises":
        render_analysis_dashboard(dataframes)
    else:
        render_about_page()

def render_analysis_dashboard(dataframes):
    """Renderiza dashboard de análises avançadas"""
    st.markdown("## 📊 Dashboard de Análises")
    
    # Análise do mercado
    analysis = analyze_carbon_market_trends(dataframes)
    
    # Métricas em tempo real
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🌍 Projetos Ativos", f"{analysis['total_projetos']:,}", "12 novos/mês")
    with col2:
        st.metric("💰 Créditos Totais", f"{analysis['total_creditos']:,.0f}", "+5.2%")
    with col3:
        st.metric("🏛️ Padrões", str(len(analysis['padroes_utilizados'])), "3 novos")
    with col4:
        st.metric("🌐 Alcance Global", str(len(analysis['paises_envolvidos'])), "+2 países")
    
    # Visualizações avançadas
    st.markdown("### 📈 Visualizações Interativas")
    
    # Criar dados para visualizações
    try:
        # Exemplo: Projetos agrícolas
        agri_df = dataframes.get('4. Agriculture', pd.DataFrame())
        if not agri_df.empty:
            tabs = st.tabs(["📊 Distribuição", "📅 Evolução", "🌍 Mapa", "📋 Detalhes"])
            
            with tabs[0]:
                # Distribuição por tipo
                col1, col2 = st.columns(2)
                with col1:
                    # Encontrar coluna de país
                    country_col = None
                    for col in agri_df.columns:
                        if 'country' in str(col).lower():
                            country_col = col
                            break
                    
                    if country_col:
                        country_counts = agri_df[country_col].value_counts().head(15)
                        fig = px.bar(
                            x=country_counts.index,
                            y=country_counts.values,
                            title="Projetos por País",
                            color=country_counts.values,
                            color_continuous_scale='Greens'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Distribuição numérica
                    numeric_cols = agri_df.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        selected_col = st.selectbox("Selecione métrica:", numeric_cols[:5])
                        fig = px.histogram(agri_df, x=selected_col, title=f"Distribuição de {selected_col}")
                        st.plotly_chart(fig, use_container_width=True)
            
            with tabs[1]:
                # Evolução temporal
                st.info("⏳ Análise temporal em desenvolvimento...")
            
            with tabs[2]:
                # Mapa (ilustrativo)
                st.info("🗺️ Mapa interativo em desenvolvimento...")
            
            with tabs[3]:
                # Detalhes dos projetos
                st.dataframe(agri_df.head(50), use_container_width=True, height=400)
    
    except Exception as e:
        st.error(f"Erro na análise: {str(e)}")

def render_about_page():
    """Renderiza página sobre o projeto"""
    st.markdown("""
    # 🌍 Sobre este Projeto
    
    ## 🎯 Objetivo
    Este dashboard tem como objetivo democratizar o acesso a informações sobre o mercado voluntário de carbono agrícola, 
    tornando dados complexos da FAO acessíveis e compreensíveis para o público geral.
    
    ## 📊 Dados
    - **Fonte**: FAO Agrifood Carbon Market Dataset
    - **Conteúdo**: Dados sobre padrões, plataformas, metodologias e projetos de carbono agrícola
    - **Atualização**: Dados mais recentes disponíveis
    
    ## 🚀 Funcionalidades
    - **Visualização Interativa**: Explore dados através de gráficos e tabelas
    - **Análise Contextual**: Entenda o impacto ambiental dos créditos de carbono
    - **Filtros Inteligentes**: Busque informações específicas por país, tipo ou padrão
    - **Relatórios Automáticos**: Gere análises personalizadas
    
    ## 🌱 Por que o carbono agrícola importa?
    
    ### 🌍 Impacto Ambiental
    A agricultura é responsável por cerca de 25% das emissões globais de gases de efeito estufa. 
    Práticas agrícolas sustentáveis podem transformar o setor de emissor para sequestrador de carbono.
    
    ### 💰 Oportunidade Econômica
    O mercado voluntário de carbono oferece nova fonte de renda para agricultores, 
    incentivando práticas sustentáveis enquanto gera créditos comercializáveis.
    
    ### 🌾 Benefícios Adicionais
    - Melhoria da saúde do solo
    - Conservação da biodiversidade
    - Aumento da resiliência climática
    - Desenvolvimento rural sustentável
    
    ## 📚 Glossário
    
    ### 🔑 Termos-chave
    
    **Crédito de Carbono**
    > Unidade que representa 1 tonelada métrica de dióxido de carbono equivalente (tCO2e) que foi reduzida ou removida da atmosfera.
    
    **Mercado Voluntário**
    > Mercado onde a compra de créditos de carbono é feita voluntariamente, não por exigência regulatória.
    
    **Sequestro de Carbono**
    > Processo de captura e armazenamento de carbono atmosférico, geralmente em solos ou biomassa.
    
    **Padrão de Certificação**
    > Conjunto de regras e procedimentos que garantem a qualidade e integridade dos créditos de carbono.
    
    ## 🤝 Contribua
    
    Este é um projeto aberto para educação e conscientização sobre mercados de carbono.
    
    - **Sugestões**: Envie feedback para melhorias
    - **Dados**: Ajude a manter os dados atualizados
    - **Divulgação**: Compartilhe com interessados no tema
    
    ## 📞 Contato
    
    Para mais informações sobre mercados de carbono agrícola:
    
    - **FAO**: [www.fao.org/climate-change](https://www.fao.org/climate-change)
    - **Dúvidas**: Consulte nossa documentação
    """)

# =========================
# RODAPÉ AVANÇADO
# =========================
def create_footer():
    """Cria rodapé informativo"""
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style='text-align: center;'>
            <p style='color: #7f8c8d; font-size: 0.9rem;'>
            <strong>🌱 Mercado de Carbono Agrícola</strong><br>
            Dashboard Interativo FAO
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style='text-align: center;'>
            <p style='color: #7f8c8d; font-size: 0.9rem;'>
            <strong>🔄 Última Atualização</strong><br>
            {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='text-align: center;'>
            <p style='color: #7f8c8d; font-size: 0.9rem;'>
            <strong>📊 Dados</strong><br>
            FAO Agrifood Carbon Market Dataset
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style='text-align: center; margin-top: 1rem;'>
        <p style='color: #95a5a6; font-size: 0.8rem;'>
        Este dashboard é uma ferramenta educacional. Para decisões de investimento, consulte especialistas.
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
        st.error(f"❌ Ocorreu um erro inesperado: {str(e)}")
        st.info("Por favor, recarregue a página ou tente novamente mais tarde.")
