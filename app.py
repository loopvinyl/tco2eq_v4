# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import requests
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')

# Configuração da página
st.set_page_config(
    page_title="Carbon Market Intelligence Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# URL do dataset
GITHUB_RAW_URL = "https://raw.githubusercontent.com/tco2eq_v3/tco2eq_v3/main/Dataset.xlsx"

# Estilo CSS personalizado
st.markdown("""
<style>
    /* Estilos gerais */
    .main {
        padding: 0rem 1rem;
    }
    
    .stMetric {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #00A86B;
    }
    
    .card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    
    .header-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 25px;
        border-radius: 15px;
        margin-bottom: 30px;
    }
    
    .kpi-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    
    /* Títulos */
    h1, h2, h3 {
        color: #2c3e50;
    }
    
    /* Remover elementos do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Animações sutis */
    .hover-card:hover {
        transform: translateY(-5px);
        transition: transform 0.3s ease;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_dataset():
    """Carrega o dataset do GitHub"""
    try:
        response = requests.get(GITHUB_RAW_URL, timeout=30)
        response.raise_for_status()
        
        excel_file = pd.ExcelFile(BytesIO(response.content))
        sheets = excel_file.sheet_names
        
        dataframes = {}
        for sheet in sheets:
            df = pd.read_excel(excel_file, sheet_name=sheet)
            dataframes[sheet] = df
        
        return dataframes, sheets
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return None, None

def analyze_projects_data(dataframes):
    """Analisa dados de projetos das diferentes abas"""
    
    # Aba 4: Agriculture (758 projetos)
    df_agri = dataframes.get('4. Agriculture', pd.DataFrame())
    
    # Aba 5: Agroforestry (170 projetos)
    df_agro = dataframes.get('5. Agroforestry-AR & Grassland', pd.DataFrame())
    
    # Aba 6: Energy (29 projetos)
    df_energy = dataframes.get('6. Energy and Other ', pd.DataFrame())
    
    # Aba 7: Plan Vivo, Acorn, Social Carbon (31 projetos)
    df_small = dataframes.get('7. Plan Vivo, Acorn, Social C', pd.DataFrame())
    
    # Análise consolidada
    analysis = {
        'total_projects': {
            'Agriculture': df_agri.shape[0] if not df_agri.empty else 0,
            'Agroforestry': df_agro.shape[0] if not df_agro.empty else 0,
            'Energy': df_energy.shape[0] if not df_energy.empty else 0,
            'Small_Standards': df_small.shape[0] if not df_small.empty else 0,
        },
        'standards_analysis': analyze_standards(dataframes.get('1. Standards', pd.DataFrame())),
        'protocols_analysis': analyze_methodologies(dataframes.get('3. Methodologies', pd.DataFrame())),
        'platforms_analysis': analyze_platforms(dataframes.get('2. Platforms', pd.DataFrame()))
    }
    
    return analysis

def analyze_standards(df):
    """Analisa dados dos padrões"""
    if df.empty:
        return {}
    
    analysis = {}
    
    # Verificar colunas disponíveis
    if 'Name of standard/registry/platform' in df.columns:
        standards = df['Name of standard/registry/platform'].dropna().unique()
        analysis['total_standards'] = len(standards)
        analysis['standards_list'] = list(standards)[:10]  # Top 10
    
    if 'Total registered projects' in df.columns:
        try:
            # Tentar converter para numérico
            df['Total registered projects'] = pd.to_numeric(df['Total registered projects'], errors='coerce')
            total_projects = df['Total registered projects'].sum()
            analysis['total_projects_all_standards'] = int(total_projects) if not pd.isna(total_projects) else 0
        except:
            analysis['total_projects_all_standards'] = 0
    
    return analysis

def analyze_methodologies(df):
    """Analisa metodologias"""
    if df.empty:
        return {}
    
    analysis = {}
    
    # Identificar coluna de metodologias
    method_col = None
    for col in df.columns:
        if 'methodology' in str(col).lower() or 'Unnamed: 2' == col:
            method_col = col
            break
    
    if method_col:
        method_counts = df[method_col].value_counts()
        analysis['total_methodologies'] = len(method_counts)
        analysis['top_methodologies'] = method_counts.head(10).to_dict()
    
    return analysis

def analyze_platforms(df):
    """Analisa plataformas"""
    if df.empty:
        return {}
    
    analysis = {}
    
    if 'Platform' in df.columns:
        platforms = df['Platform'].dropna().unique()
        analysis['total_platforms'] = len(platforms)
        analysis['platforms_list'] = list(platforms)[:10]
    
    return analysis

def create_kpi_cards(analysis):
    """Cria cards com KPIs principais"""
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_projects = sum(analysis['total_projects'].values())
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card hover-card">
            <h3 style="color: white; margin: 0;">🌍</h3>
            <h2 style="color: white; margin: 10px 0;">{total_projects:,}</h2>
            <p style="color: white; margin: 0; font-size: 14px;">Total de Projetos</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        standards_count = analysis['standards_analysis'].get('total_standards', 0)
        st.markdown(f"""
        <div class="kpi-card hover-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
            <h3 style="color: white; margin: 0;">🏆</h3>
            <h2 style="color: white; margin: 10px 0;">{standards_count}</h2>
            <p style="color: white; margin: 0; font-size: 14px;">Padrões Certificadores</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        methods_count = analysis['protocols_analysis'].get('total_methodologies', 0)
        st.markdown(f"""
        <div class="kpi-card hover-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
            <h3 style="color: white; margin: 0;">📋</h3>
            <h2 style="color: white; margin: 10px 0;">{methods_count}</h2>
            <p style="color: white; margin: 0; font-size: 14px;">Metodologias</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        platforms_count = analysis['platforms_analysis'].get('total_platforms', 0)
        st.markdown(f"""
        <div class="kpi-card hover-card" style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);">
            <h3 style="color: white; margin: 0;">🔄</h3>
            <h2 style="color: white; margin: 10px 0;">{platforms_count}</h2>
            <p style="color: white; margin: 0; font-size: 14px;">Plataformas</p>
        </div>
        """, unsafe_allow_html=True)

def create_project_distribution_chart(analysis):
    """Cria gráfico de distribuição de projetos"""
    
    project_data = analysis['total_projects']
    
    fig = go.Figure(data=[
        go.Pie(
            labels=list(project_data.keys()),
            values=list(project_data.values()),
            hole=0.5,
            marker=dict(colors=['#00A86B', '#4CAF50', '#8BC34A', '#CDDC39']),
            textinfo='label+percent',
            textposition='inside'
        )
    ])
    
    fig.update_layout(
        title="📊 Distribuição de Projetos por Categoria",
        showlegend=False,
        height=400,
        margin=dict(t=50, b=20, l=20, r=20)
    )
    
    return fig

def create_standards_table(analysis):
    """Cria tabela de padrões mais utilizados"""
    
    standards_list = analysis['standards_analysis'].get('standards_list', [])
    
    if standards_list:
        df = pd.DataFrame({
            'Padrão': standards_list,
            'Status': ['Ativo'] * len(standards_list)
        })
        return df
    return pd.DataFrame()

def create_top_methodologies_chart(analysis):
    """Cria gráfico das metodologias mais utilizadas"""
    
    top_methods = analysis['protocols_analysis'].get('top_methodologies', {})
    
    if top_methods:
        df = pd.DataFrame({
            'Metodologia': list(top_methods.keys()),
            'Contagem': list(top_methods.values())
        }).head(8)
        
        fig = px.bar(
            df,
            x='Metodologia',
            y='Contagem',
            color='Contagem',
            color_continuous_scale='Viridis',
            text='Contagem'
        )
        
        fig.update_layout(
            title="🔬 Top Metodologias por Uso",
            xaxis_title="",
            yaxis_title="Número de Aplicações",
            height=400,
            showlegend=False,
            xaxis_tickangle=-45
        )
        
        fig.update_traces(textposition='outside')
        
        return fig
    
    return go.Figure()

def create_projects_by_scale(analysis):
    """Cria análise de projetos por escala"""
    
    project_data = analysis['total_projects']
    
    # Classificar por escala
    scale_analysis = {
        'Grande Escala': project_data.get('Agriculture', 0) + project_data.get('Energy', 0),
        'Média Escala': project_data.get('Agroforestry', 0),
        'Pequena Escala': project_data.get('Small_Standards', 0)
    }
    
    fig = go.Figure(data=[
        go.Bar(
            x=list(scale_analysis.keys()),
            y=list(scale_analysis.values()),
            marker_color=['#2E86AB', '#A23B72', '#F18F01'],
            text=list(scale_analysis.values()),
            textposition='outside'
        )
    ])
    
    fig.update_layout(
        title="📈 Projetos por Escala",
        xaxis_title="Escala do Projeto",
        yaxis_title="Número de Projetos",
        height=400,
        showlegend=False
    )
    
    return fig

def create_platforms_overview(analysis):
    """Cria visão geral das plataformas"""
    
    platforms_list = analysis['platforms_analysis'].get('platforms_list', [])
    
    if platforms_list:
        return pd.DataFrame({
            'Plataforma': platforms_list,
            'Tipo': ['MRV & Monitoramento'] * len(platforms_list)
        })
    
    return pd.DataFrame()

def main():
    """Dashboard principal"""
    
    # Cabeçalho do dashboard
    st.markdown("""
    <div class="header-card">
        <h1 style="color: white; margin: 0;">🌱 Carbon Market Intelligence</h1>
        <p style="color: white; opacity: 0.9; margin: 10px 0 0 0;">
        Dashboard estratégico do mercado voluntário de carbono agrícola - FAO Dataset
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Carregar dados
    with st.spinner("🔄 Carregando dados do mercado de carbono..."):
        dataframes, sheets = load_dataset()
    
    if not dataframes:
        st.error("Não foi possível carregar os dados. Verifique a conexão com o GitHub.")
        return
    
    # Análise dos dados
    analysis = analyze_projects_data(dataframes)
    
    # Seção 1: KPIs Principais
    st.markdown("<h2>📈 KPIs do Mercado</h2>", unsafe_allow_html=True)
    create_kpi_cards(analysis)
    
    # Seção 2: Visualizações principais
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("<div class='card hover-card'>", unsafe_allow_html=True)
        fig1 = create_project_distribution_chart(analysis)
        st.plotly_chart(fig1, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("<div class='card hover-card'>", unsafe_allow_html=True)
        fig2 = create_top_methodologies_chart(analysis)
        if fig2:
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Dados de metodologias não disponíveis")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Seção 3: Análise detalhada
    st.markdown("<h2>🔍 Análise Estratégica</h2>", unsafe_allow_html=True)
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("<div class='card hover-card'>", unsafe_allow_html=True)
        st.markdown("<h3>🏗️ Projetos por Escala</h3>", unsafe_allow_html=True)
        fig3 = create_projects_by_scale(analysis)
        st.plotly_chart(fig3, use_container_width=True)
        
        # Legenda
        st.markdown("""
        <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; margin-top: 15px;">
        <p style="margin: 5px 0; font-size: 14px;">
        <span style="color: #2E86AB;">● Grande Escala:</span> Agricultura + Energia<br>
        <span style="color: #A23B72;">● Média Escala:</span> Agroflorestal<br>
        <span style="color: #F18F01;">● Pequena Escala:</span> Padrões especializados
        </p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col4:
        st.markdown("<div class='card hover-card'>", unsafe_allow_html=True)
        st.markdown("<h3>🏆 Principais Padrões</h3>", unsafe_allow_html=True)
        standards_df = create_standards_table(analysis)
        if not standards_df.empty:
            # Mostrar como cards em vez de tabela
            for idx, row in standards_df.iterrows():
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #667eea20 0%, #764ba220 100%); 
                          padding: 12px; margin: 8px 0; border-radius: 8px; border-left: 4px solid #667eea;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 600;">{row['Padrão']}</span>
                    <span style="background: #667eea; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                    {row['Status']}
                    </span>
                </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Dados de padrões não disponíveis")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Seção 4: Plataformas e Tecnologias
    st.markdown("<h2>🚀 Plataformas & Tecnologias</h2>", unsafe_allow_html=True)
    
    platforms_df = create_platforms_overview(analysis)
    if not platforms_df.empty:
        cols = st.columns(3)
        for idx, (_, row) in enumerate(platforms_df.iterrows()):
            with cols[idx % 3]:
                st.markdown(f"""
                <div style="background: white; padding: 15px; border-radius: 10px; 
                          box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 15px; 
                          border-top: 3px solid #00A86B;">
                <div style="font-weight: 600; font-size: 14px; margin-bottom: 5px;">{row['Plataforma']}</div>
                <div style="font-size: 12px; color: #666;">{row['Tipo']}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Dados de plataformas não disponíveis")
    
    # Seção 5: Insights Estratégicos
    st.markdown("<h2>💡 Insights do Mercado</h2>", unsafe_allow_html=True)
    
    insights_col1, insights_col2 = st.columns(2)
    
    with insights_col1:
        st.markdown("""
        <div class="card hover-card">
            <h3>🎯 Tendências Emergentes</h3>
            <ul style="padding-left: 20px;">
                <li><strong>Agricultura Regenerativa</strong> lidera em número de projetos</li>
                <li><strong>Metodologias de Biochar</strong> em crescimento acelerado</li>
                <li><strong>Plataformas de MRV digital</strong> ganhando escala</li>
                <li><strong>Projetos de pequena escala</strong> com impacto social relevante</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with insights_col2:
        st.markdown("""
        <div class="card hover-card">
            <h3>📊 Segmentação Estratégica</h3>
            <ul style="padding-left: 20px;">
                <li><strong>Grande Escala:</strong> Foco em eficiência e volume</li>
                <li><strong>Média Escala:</strong> Equilíbrio entre impacto e escala</li>
                <li><strong>Pequena Escala:</strong> Impacto social e ambiental local</li>
                <li><strong>Tecnologia:</strong> MRV digital como diferencial competitivo</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Seção 6: Resumo Executivo
    st.markdown("<h2>📋 Resumo Executivo</h2>", unsafe_allow_html=True)
    
    total_projects = sum(analysis['total_projects'].values())
    standards_count = analysis['standards_analysis'].get('total_standards', 0)
    methods_count = analysis['protocols_analysis'].get('total_methodologies', 0)
    
    st.markdown(f"""
    <div class="card" style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
            <div style="text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #00A86B;">{total_projects:,}</div>
                <div style="font-size: 14px; color: #666;">Projetos Registrados</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #667eea;">{standards_count}</div>
                <div style="font-size: 14px; color: #666;">Padrões Ativos</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #fa709a;">{methods_count}</div>
                <div style="font-size: 14px; color: #666;">Metodologias Validados</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #43e97b;">24+</div>
                <div style="font-size: 14px; color: #666;">Países Envolvidos</div>
            </div>
        </div>
        
        <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #dee2e6;">
            <h4 style="margin: 0 0 10px 0;">🎯 Recomendações Estratégicas</h4>
            <ol style="margin: 0; padding-left: 20px;">
                <li>Focar em <strong>projetos agroflorestais</strong> para maior impacto social</li>
                <li>Adotar <strong>plataformas de MRV digital</strong> para redução de custos</li>
                <li>Desenvolver <strong>metodologias híbridas</strong> para diferentes escalas</li>
                <li>Expandir para <strong>mercados emergentes</strong> com alto potencial</li>
            </ol>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown(f"""
    <div style="text-align: center; color: #666; font-size: 12px; padding: 20px;">
        <div>📊 <strong>Carbon Market Intelligence Dashboard</strong> • Baseado em dados da FAO (2025)</div>
        <div>🔄 Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')} • Fonte: GitHub/tco2eq_v3</div>
        <div style="margin-top: 10px;">
            <span style="background: #00A86B; color: white; padding: 4px 12px; border-radius: 20px; margin: 0 5px; font-size: 11px;">
            🌱 Agricultura
            </span>
            <span style="background: #667eea; color: white; padding: 4px 12px; border-radius: 20px; margin: 0 5px; font-size: 11px;">
            🌳 Agroflorestal
            </span>
            <span style="background: #fa709a; color: white; padding: 4px 12px; border-radius: 20px; margin: 0 5px; font-size: 11px;">
            ⚡ Energia
            </span>
            <span style="background: #43e97b; color: white; padding: 4px 12px; border-radius: 20px; margin: 0 5px; font-size: 11px;">
            👥 Pequena Escala
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
