import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import BytesIO
from typing import Dict, List, Tuple, Any
import re

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Análise de Créditos de Carbono - FAO Dataset",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# FUNÇÕES DE FORMATAÇÃO BRASILEIRA
# =========================

def formatar_br_inteiro(numero: Any) -> str:
    """Formata números inteiros no padrão brasileiro: 1.234"""
    if pd.isna(numero):
        return "N/A"
    try:
        numero = int(round(float(numero), 0))
        return f"{numero:,}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "N/A"

def formatar_milhoes(numero: Any) -> str:
    """Formata números grandes como milhões: 367,2 milhões"""
    if pd.isna(numero):
        return "N/A"
    try:
        numero = float(numero)
        if numero >= 1000000000:
            em_bilhoes = numero / 1000000000
            return f"{em_bilhoes:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " bilhões"
        elif numero >= 1000000:
            em_milhoes = numero / 1000000000 if numero >= 1000000000 else numero / 1000000
            return f"{em_milhoes:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " milhões"
        elif numero >= 1000:
            em_mil = numero / 1000
            return f"{em_mil:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " mil"
        else:
            return formatar_br_inteiro(numero)
    except:
        return "N/A"

def formatar_moeda_curta(numero: Any) -> str:
    """Formata valores monetários de forma curta"""
    if pd.isna(numero):
        return "N/A"
    try:
        numero = float(numero)
        if numero >= 1000000000:
            valor = numero / 1000000000
            return f"US$ {valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " bilhões"
        elif numero >= 1000000:
            valor = numero / 1000000
            return f"US$ {valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " milhões"
        elif numero >= 1000:
            valor = numero / 1000
            return f"US$ {valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " mil"
        else:
            return f"US$ {numero:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "N/A"

# =========================
# CARGA DE DADOS - VERSÃO REFINADA
# =========================

@st.cache_data(ttl=3600)
def load_agriculture_data() -> Tuple[pd.DataFrame, Dict, Dict, Dict]:
    """Carrega a aba 4. Agriculture identificando créditos emitidos e aposentados por ano"""
    try:
        # URL do arquivo no GitHub
        url = "https://github.com/loopvinyl/tco2eq_v4/raw/main/Dataset.xlsx"
        response = requests.get(url)
        response.raise_for_status()
        
        # Ler o arquivo Excel
        excel_file = BytesIO(response.content)
        
        # Ler as primeiras linhas para identificar a estrutura
        df_preview = pd.read_excel(excel_file, sheet_name='4. Agriculture', nrows=5)
        
        # Voltar ao início do arquivo
        excel_file.seek(0)
        
        # Identificar se temos múltiplos cabeçalhos (linhas 1 e 2)
        # A linha 1: "Credits issued in:" e "Credits retired in:" 
        # A linha 2: anos para cada tipo
        
        # Ler com header=[0, 1] para capturar ambas as linhas
        df = pd.read_excel(excel_file, sheet_name='4. Agriculture', header=[0, 1])
        
        # Renomear colunas para facilitar o processamento
        new_columns = []
        for col in df.columns:
            if isinstance(col, tuple):
                # Juntar os dois níveis do cabeçalho
                if pd.isna(col[1]):
                    new_columns.append(str(col[0]))
                else:
                    new_columns.append(f"{col[0]}_{col[1]}")
            else:
                new_columns.append(str(col))
        
        df.columns = new_columns
        
        # Identificar colunas de créditos emitidos por ano
        issued_cols = {}
        retired_cols = {}
        
        for col in df.columns:
            col_str = str(col)
            
            # Procurar por colunas de créditos emitidos
            if 'Credits issued' in col_str or 'issued' in col_str.lower():
                # Extrair ano
                year_match = re.search(r'(19[9][6-9]|20[0-2][0-9]|202[0-3])', col_str)
                if year_match:
                    year = int(year_match.group(0))
                    issued_cols[year] = col
            
            # Procurar por colunas de créditos aposentados
            elif 'Credits retired' in col_str or 'retired' in col_str.lower():
                # Extrair ano
                year_match = re.search(r'(19[9][6-9]|20[0-2][0-9]|202[0-3])', col_str)
                if year_match:
                    year = int(year_match.group(0))
                    retired_cols[year] = col
        
        # Identificar colunas principais
        main_cols = {}
        col_mapping = {
            'project_id': ['project id', 'id'],
            'project_name': ['project name', 'nome do projeto', 'project'],
            'status': ['voluntary status', 'status', 'estado'],
            'country': ['country', 'país', 'country name'],
            'type': ['type', 'tipo', 'project type'],
            'total_issued': ['total credits issued', 'total issued', 'créditos emitidos total'],
            'total_retired': ['total credits retired', 'total retired', 'créditos aposentados total'],
            'total_remaining': ['total credits remaining', 'total remaining', 'remaining credits', 'créditos restantes'],
            'methodology': ['methodology', 'protocol', 'methodology/protocol']
        }
        
        for col in df.columns:
            col_lower = str(col).lower()
            for key, patterns in col_mapping.items():
                for pattern in patterns:
                    if pattern in col_lower:
                        main_cols[key] = col
                        break
        
        # Garantir que temos as colunas essenciais
        essential_cols = ['project_name', 'total_issued', 'total_retired']
        missing = [col for col in essential_cols if col not in main_cols]
        if missing:
            st.warning(f"Colunas essenciais não encontradas: {missing}")
            
        return df, issued_cols, retired_cols, main_cols
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        st.error("Verifique a estrutura do arquivo Excel. O script espera cabeçalhos nas linhas 1 e 2.")
        return None, {}, {}, {}

@st.cache_data
def analyze_credits(df: pd.DataFrame, issued_cols: Dict, retired_cols: Dict, main_cols: Dict) -> Dict:
    """Analisa créditos emitidos, aposentados e remanescentes com detalhamento anual"""
    
    if df is None or df.empty:
        return {}
    
    analysis = {
        'total_projects': 0,
        'projects_with_credits': 0,
        'total_credits_issued': 0,
        'total_credits_retired': 0,
        'total_credits_remaining': 0,
        'retirement_rate': 0,
        'issued_by_year': {},
        'retired_by_year': {},
        'net_by_year': {},
        'top_projects': [],
        'by_country': {},
        'by_type': {},
        'by_status': {},
        'annual_summary': []
    }
    
    # Converter colunas numéricas
    def safe_convert(series):
        return pd.to_numeric(series, errors='coerce')
    
    # Calcular totais principais
    if 'total_issued' in main_cols:
        df[main_cols['total_issued']] = safe_convert(df[main_cols['total_issued']])
        analysis['total_credits_issued'] = df[main_cols['total_issued']].sum()
    
    if 'total_retired' in main_cols:
        df[main_cols['total_retired']] = safe_convert(df[main_cols['total_retired']])
        analysis['total_credits_retired'] = df[main_cols['total_retired']].sum()
    
    if 'total_remaining' in main_cols:
        df[main_cols['total_remaining']] = safe_convert(df[main_cols['total_remaining']])
        analysis['total_credits_remaining'] = df[main_cols['total_remaining']].sum()
    else:
        # Calcular remanescentes como diferença
        analysis['total_credits_remaining'] = max(0, analysis['total_credits_issued'] - analysis['total_credits_retired'])
    
    # Total de projetos
    analysis['total_projects'] = len(df)
    
    # Projetos com créditos emitidos
    if 'total_issued' in main_cols:
        projects_with_credits = df[df[main_cols['total_issued']] > 0]
        analysis['projects_with_credits'] = len(projects_with_credits)
    
    # Taxa de aposentadoria
    if analysis['total_credits_issued'] > 0:
        analysis['retirement_rate'] = (analysis['total_credits_retired'] / analysis['total_credits_issued']) * 100
    else:
        analysis['retirement_rate'] = 0
    
    # Análise por ano - Créditos Emitidos
    if issued_cols:
        for year, col in issued_cols.items():
            if col in df.columns:
                df[col] = safe_convert(df[col])
                analysis['issued_by_year'][year] = df[col].sum()
    
    # Análise por ano - Créditos Aposentados
    if retired_cols:
        for year, col in retired_cols.items():
            if col in df.columns:
                df[col] = safe_convert(df[col])
                analysis['retired_by_year'][year] = df[col].sum()
    
    # Calcular net por ano (emitidos - aposentados)
    all_years = sorted(set(list(analysis['issued_by_year'].keys()) + list(analysis['retired_by_year'].keys())))
    for year in all_years:
        issued = analysis['issued_by_year'].get(year, 0)
        retired = analysis['retired_by_year'].get(year, 0)
        analysis['net_by_year'][year] = issued - retired
        
        # Adicionar ao resumo anual
        analysis['annual_summary'].append({
            'year': year,
            'issued': issued,
            'retired': retired,
            'net': issued - retired,
            'retirement_rate': (retired / issued * 100) if issued > 0 else 0
        })
    
    # Top projetos por créditos emitidos
    if 'total_issued' in main_cols and 'project_name' in main_cols:
        top_df = df.nlargest(15, main_cols['total_issued'])
        for _, row in top_df.iterrows():
            project = {
                'name': row[main_cols['project_name']] if pd.notna(row[main_cols['project_name']]) else 'Sem nome',
                'issued': row[main_cols['total_issued']] if pd.notna(row[main_cols['total_issued']]) else 0,
                'retired': row[main_cols['total_retired']] if 'total_retired' in main_cols and pd.notna(row[main_cols['total_retired']]) else 0,
                'remaining': row[main_cols['total_remaining']] if 'total_remaining' in main_cols and pd.notna(row[main_cols['total_remaining']]) else 0,
                'country': row[main_cols['country']] if 'country' in main_cols and pd.notna(row[main_cols['country']]) else 'N/A',
                'type': row[main_cols['type']] if 'type' in main_cols and pd.notna(row[main_cols['type']]) else 'N/A',
                'status': row[main_cols['status']] if 'status' in main_cols and pd.notna(row[main_cols['status']]) else 'N/A'
            }
            # Calcular taxa de aposentadoria do projeto
            if project['issued'] > 0:
                project['retirement_rate'] = (project['retired'] / project['issued']) * 100
            else:
                project['retirement_rate'] = 0
            analysis['top_projects'].append(project)
    
    # Análise por país
    if 'country' in main_cols and 'total_issued' in main_cols:
        country_analysis = df.groupby(main_cols['country'])[main_cols['total_issued']].sum().reset_index()
        country_analysis.columns = ['country', 'total_issued']
        country_analysis = country_analysis.sort_values('total_issued', ascending=False)
        for _, row in country_analysis.iterrows():
            analysis['by_country'][row['country']] = row['total_issued']
    
    # Análise por tipo
    if 'type' in main_cols and 'total_issued' in main_cols:
        type_analysis = df.groupby(main_cols['type'])[main_cols['total_issued']].sum().reset_index()
        type_analysis.columns = ['type', 'total_issued']
        type_analysis = type_analysis.sort_values('total_issued', ascending=False)
        for _, row in type_analysis.iterrows():
            analysis['by_type'][row['type']] = row['total_issued']
    
    # Análise por status
    if 'status' in main_cols and 'total_issued' in main_cols:
        status_analysis = df.groupby(main_cols['status'])[main_cols['total_issued']].sum().reset_index()
        status_analysis.columns = ['status', 'total_issued']
        status_analysis = status_analysis.sort_values('total_issued', ascending=False)
        for _, row in status_analysis.iterrows():
            analysis['by_status'][row['status']] = row['total_issued']
    
    # Ordenar resumo anual
    analysis['annual_summary'] = sorted(analysis['annual_summary'], key=lambda x: x['year'])
    
    return analysis

# =========================
# FUNÇÕES DE VISUALIZAÇÃO REFINADAS
# =========================

def create_hero_section(analysis: Dict) -> None:
    """Cria seção hero com métricas principais"""
    
    if not analysis:
        st.markdown("""
        <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                    background: linear-gradient(135deg, #27ae60, #229954); 
                    color: white; margin-bottom: 2rem;'>
            <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>📊 Análise de Créditos de Carbono</h1>
            <h3 style='font-weight: 300;'>Baseado no Dataset FAO - Agricultura</h3>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Formatar valores
    total_issued_fmt = formatar_milhoes(analysis['total_credits_issued'])
    total_retired_fmt = formatar_milhoes(analysis['total_credits_retired'])
    total_remaining_fmt = formatar_milhoes(analysis['total_credits_remaining'])
    retirement_rate_fmt = f"{analysis['retirement_rate']:.2f}%"
    
    # Calcular valor de mercado estimado (US$ 15 por crédito como referência)
    market_value = analysis['total_credits_retired'] * 15
    market_value_fmt = formatar_moeda_curta(market_value)
    
    st.markdown(f"""
    <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                background: linear-gradient(135deg, #1a5276, #2e86c1); 
                color: white; margin-bottom: 2rem;'>
        <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>🌱 Análise de Mercado de Carbono</h1>
        <h3 style='font-weight: 300;'>Dataset FAO - Projetos Agrícolas</h3>
        <div style='display: flex; justify-content: center; gap: 3rem; margin-top: 2rem; flex-wrap: wrap;'>
            <div style='flex: 1; min-width: 200px;'>
                <div style='font-size: 2.5rem; font-weight: bold;'>📦</div>
                <div style='font-size: 1.8rem; font-weight: bold;'>{total_issued_fmt}</div>
                <div style='font-size: 0.9rem; opacity: 0.9;'>Créditos Emitidos</div>
            </div>
            <div style='flex: 1; min-width: 200px;'>
                <div style='font-size: 2.5rem; font-weight: bold;'>💰</div>
                <div style='font-size: 1.8rem; font-weight: bold;'>{total_retired_fmt}</div>
                <div style='font-size: 0.9rem; opacity: 0.9;'>Créditos Negociados</div>
            </div>
            <div style='flex: 1; min-width: 200px;'>
                <div style='font-size: 2.5rem; font-weight: bold;'>📈</div>
                <div style='font-size: 1.8rem; font-weight: bold;'>{total_remaining_fmt}</div>
                <div style='font-size: 0.9rem; opacity: 0.9;'>Disponíveis no Mercado</div>
            </div>
            <div style='flex: 1; min-width: 200px;'>
                <div style='font-size: 2.5rem; font-weight: bold;'>📊</div>
                <div style='font-size: 1.8rem; font-weight: bold;'>{retirement_rate_fmt}</div>
                <div style='font-size: 0.9rem; opacity: 0.9;'>Taxa de Negociação</div>
            </div>
            <div style='flex: 1; min-width: 200px;'>
                <div style='font-size: 2.5rem; font-weight: bold;'>💵</div>
                <div style='font-size: 1.5rem; font-weight: bold;'>{market_value_fmt}</div>
                <div style='font-size: 0.8rem; opacity: 0.9;'>Valor Estimado (US$ 15/tCO₂eq)</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def create_main_metrics(analysis: Dict) -> None:
    """Cria seção de métricas principais com mais detalhes"""
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "📦 Total Emitido",
            formatar_milhoes(analysis['total_credits_issued']),
            help="Total de créditos de carbono gerados (tCO₂eq)"
        )
    
    with col2:
        st.metric(
            "💰 Total Negociado", 
            formatar_milhoes(analysis['total_credits_retired']),
            help="Créditos que foram comercializados/compensados",
            delta=f"{analysis['retirement_rate']:.2f}% do total"
        )
    
    with col3:
        st.metric(
            "📈 Disponível",
            formatar_milhoes(analysis['total_credits_remaining']),
            help="Créditos ainda disponíveis para transação",
            delta=f"{analysis['retirement_rate']:.1f}% já negociados"
        )
    
    with col4:
        projects_with_credits = analysis.get('projects_with_credits', 0)
        total_projects = analysis.get('total_projects', 1)
        active_rate = (projects_with_credits / total_projects * 100) if total_projects > 0 else 0
        st.metric(
            "🏗️ Projetos Ativos",
            formatar_br_inteiro(projects_with_credits),
            delta=f"{active_rate:.1f}% do total",
            help=f"Projetos com créditos emitidos de um total de {formatar_br_inteiro(total_projects)}"
        )
    
    with col5:
        # Valor médio por crédito negociado
        avg_value = 15  # US$ por tCO₂eq (valor de referência)
        total_value = analysis['total_credits_retired'] * avg_value
        st.metric(
            "💵 Valor Mercado",
            formatar_moeda_curta(total_value),
            help=f"Valor estimado baseado em US$ {avg_value} por crédito"
        )

def create_timeline_comparison(analysis: Dict) -> None:
    """Cria gráfico comparativo de créditos emitidos vs aposentados por ano"""
    
    if not analysis['issued_by_year'] and not analysis['retired_by_year']:
        st.info("📅 Dados anuais não disponíveis na estrutura atual")
        return
    
    # Preparar dados para o gráfico
    years = sorted(set(list(analysis['issued_by_year'].keys()) + list(analysis['retired_by_year'].keys())))
    
    issued_values = [analysis['issued_by_year'].get(year, 0) for year in years]
    retired_values = [analysis['retired_by_year'].get(year, 0) for year in years]
    net_values = [analysis['net_by_year'].get(year, 0) for year in years]
    
    # Criar figura com barras agrupadas
    fig = go.Figure()
    
    # Barras para créditos emitidos
    fig.add_trace(go.Bar(
        x=years,
        y=issued_values,
        name='Créditos Emitidos',
        marker_color='#27ae60',
        text=[formatar_milhoes(v) for v in issued_values],
        textposition='auto',
    ))
    
    # Barras para créditos aposentados/negociados
    fig.add_trace(go.Bar(
        x=years,
        y=retired_values,
        name='Créditos Negociados',
        marker_color='#e74c3c',
        text=[formatar_milhoes(v) for v in retired_values],
        textposition='auto',
    ))
    
    # Linha para o saldo líquido
    fig.add_trace(go.Scatter(
        x=years,
        y=net_values,
        name='Saldo Líquido',
        mode='lines+markers',
        line=dict(color='#3498db', width=3),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title='📈 Evolução Anual: Créditos Emitidos vs Negociados',
        xaxis_title='Ano',
        yaxis_title='Volume de Créditos (tCO₂eq)',
        yaxis2=dict(
            title='Saldo Líquido (tCO₂eq)',
            overlaying='y',
            side='right'
        ),
        barmode='group',
        plot_bgcolor='white',
        height=450,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_market_dynamics_chart(analysis: Dict) -> None:
    """Cria gráfico de dinâmica de mercado com acumulados"""
    
    if not analysis['annual_summary']:
        st.info("📊 Dados insuficientes para análise de dinâmica de mercado")
        return
    
    df_annual = pd.DataFrame(analysis['annual_summary'])
    
    # Calcular acumulados
    df_annual['issued_cum'] = df_annual['issued'].cumsum()
    df_annual['retired_cum'] = df_annual['retired'].cumsum()
    df_annual['remaining_cum'] = df_annual['issued_cum'] - df_annual['retired_cum']
    
    fig = go.Figure()
    
    # Área acumulada para créditos emitidos
    fig.add_trace(go.Scatter(
        x=df_annual['year'],
        y=df_annual['issued_cum'],
        name='Total Emitido (Acumulado)',
        fill='tozeroy',
        fillcolor='rgba(39, 174, 96, 0.3)',
        line=dict(color='#27ae60', width=3),
        stackgroup='one'
    ))
    
    # Área acumulada para créditos negociados
    fig.add_trace(go.Scatter(
        x=df_annual['year'],
        y=df_annual['retired_cum'],
        name='Total Negociado (Acumulado)',
        fill='tonexty',
        fillcolor='rgba(231, 76, 60, 0.3)',
        line=dict(color='#e74c3c', width=3),
        stackgroup='one'
    ))
    
    # Linha para créditos disponíveis
    fig.add_trace(go.Scatter(
        x=df_annual['year'],
        y=df_annual['remaining_cum'],
        name='Disponível no Mercado',
        mode='lines+markers',
        line=dict(color='#3498db', width=3, dash='dash'),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title='📊 Dinâmica do Mercado: Acumulado ao Longo do Tempo',
        xaxis_title='Ano',
        yaxis_title='Créditos Acumulados (tCO₂eq)',
        plot_bgcolor='white',
        height=450,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_retirement_rate_chart(analysis: Dict) -> None:
    """Cria gráfico da taxa de negociação por ano"""
    
    if not analysis['annual_summary']:
        return
    
    df_annual = pd.DataFrame(analysis['annual_summary'])
    
    # Calcular média móvel da taxa de negociação
    df_annual['retirement_rate_ma'] = df_annual['retirement_rate'].rolling(window=3, center=True).mean()
    
    fig = go.Figure()
    
    # Barras para taxa anual
    fig.add_trace(go.Bar(
        x=df_annual['year'],
        y=df_annual['retirement_rate'],
        name='Taxa Anual',
        marker_color='#9b59b6',
        opacity=0.7,
        text=[f"{v:.1f}%" for v in df_annual['retirement_rate']],
        textposition='auto',
    ))
    
    # Linha para média móvel
    fig.add_trace(go.Scatter(
        x=df_annual['year'],
        y=df_annual['retirement_rate_ma'],
        name='Média Móvel (3 anos)',
        mode='lines+markers',
        line=dict(color='#2c3e50', width=3),
        marker=dict(size=8)
    ))
    
    # Linha para taxa média global
    fig.add_trace(go.Scatter(
        x=[df_annual['year'].min(), df_annual['year'].max()],
        y=[analysis['retirement_rate'], analysis['retirement_rate']],
        name=f'Taxa Média Global ({analysis["retirement_rate"]:.1f}%)',
        mode='lines',
        line=dict(color='#e74c3c', width=2, dash='dash'),
    ))
    
    fig.update_layout(
        title='📈 Taxa de Negociação por Ano (%)',
        xaxis_title='Ano',
        yaxis_title='Taxa de Negociação (%)',
        plot_bgcolor='white',
        height=400,
        yaxis=dict(range=[0, max(100, df_annual['retirement_rate'].max() * 1.1)]),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_top_projects_table(analysis: Dict) -> None:
    """Cria tabela detalhada dos projetos com mais créditos"""
    
    if not analysis['top_projects']:
        st.info("📋 Nenhum dado de projeto disponível")
        return
    
    st.subheader("🏆 Top 15 Projetos por Créditos Emitidos")
    
    # Criar DataFrame
    data = []
    for i, project in enumerate(analysis['top_projects'], 1):
        data.append({
            'Rank': i,
            'Projeto': project['name'][:50] + ('...' if len(project['name']) > 50 else ''),
            'País': project['country'],
            'Tipo': project['type'],
            'Status': project['status'],
            'Emitidos': project['issued'],
            'Negociados': project['retired'],
            'Disponíveis': project['remaining'],
            'Taxa Neg.': f"{project['retirement_rate']:.1f}%" if project.get('retirement_rate') else "N/A"
        })
    
    df = pd.DataFrame(data)
    
    # Formatar números
    df['Emitidos'] = df['Emitidos'].apply(formatar_milhoes)
    df['Negociados'] = df['Negociados'].apply(formatar_milhoes)
    df['Disponíveis'] = df['Disponíveis'].apply(formatar_milhoes)
    
    # Exibir tabela com estilo
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Projeto": st.column_config.TextColumn(width="large"),
            "País": st.column_config.TextColumn(width="small"),
            "Tipo": st.column_config.TextColumn(width="medium"),
            "Status": st.column_config.TextColumn(width="medium"),
        }
    )

def create_country_analysis(analysis: Dict) -> None:
    """Cria análise detalhada por país"""
    
    if not analysis['by_country']:
        return
    
    # Converter para DataFrame
    country_df = pd.DataFrame(list(analysis['by_country'].items()), columns=['País', 'Créditos'])
    country_df = country_df.sort_values('Créditos', ascending=False)
    
    # Top 15 países
    top_countries = country_df.head(15)
    
    # Gráfico de barras
    fig = px.bar(
        top_countries, 
        x='País', 
        y='Créditos',
        title='🌍 Top 15 Países por Créditos Emitidos',
        color='Créditos',
        color_continuous_scale='Viridis',
        text=[formatar_milhoes(x) for x in top_countries['Créditos']]
    )
    
    fig.update_layout(
        yaxis_title='Créditos Emitidos (tCO₂eq)',
        xaxis_title='',
        plot_bgcolor='white',
        height=400,
        xaxis_tickangle=-45
    )
    
    fig.update_traces(textposition='outside')
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🌎 Distribuição")
        st.metric(
            "Total de Países",
            formatar_br_inteiro(len(country_df))
        )
        st.metric(
            "Top 5 Concentração",
            f"{(top_countries.head(5)['Créditos'].sum() / country_df['Créditos'].sum() * 100):.1f}%"
        )
        
        # Lista rápida top 5
        st.markdown("**Top 5:**")
        for i, row in top_countries.head(5).iterrows():
            st.markdown(f"{row['País']}: {formatar_milhoes(row['Créditos'])}")

def create_type_analysis(analysis: Dict) -> None:
    """Cria análise por tipo de projeto"""
    
    if not analysis['by_type']:
        return
    
    type_df = pd.DataFrame(list(analysis['by_type'].items()), columns=['Tipo', 'Créditos'])
    type_df = type_df.sort_values('Créditos', ascending=False)
    
    # Gráfico de pizza
    fig = px.pie(
        type_df, 
        values='Créditos', 
        names='Tipo',
        title='📋 Distribuição por Tipo de Projeto',
        hole=0.4
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>%{value:,.0f} créditos<br>%{percent}'
    )
    
    fig.update_layout(
        height=400,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.05
        )
    )
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📊 Estatísticas")
        st.metric(
            "Tipos Diferentes",
            formatar_br_inteiro(len(type_df))
        )
        
        # Tipos mais comuns
        st.markdown("**Principais Tipos:**")
        for _, row in type_df.head(5).iterrows():
            percentage = (row['Créditos'] / type_df['Créditos'].sum() * 100)
            st.markdown(f"• {row['Tipo']}: {percentage:.1f}%")

def create_status_analysis(analysis: Dict) -> None:
    """Cria análise por status do projeto"""
    
    if not analysis['by_status']:
        return
    
    status_df = pd.DataFrame(list(analysis['by_status'].items()), columns=['Status', 'Créditos'])
    status_df = status_df.sort_values('Créditos', ascending=False)
    
    # Gráfico de barras horizontais
    fig = px.bar(
        status_df, 
        x='Créditos', 
        y='Status',
        orientation='h',
        title='📝 Créditos por Status do Projeto',
        color='Créditos',
        color_continuous_scale='Blues',
        text=[formatar_milhoes(x) for x in status_df['Créditos']]
    )
    
    fig.update_layout(
        xaxis_title='Créditos Emitidos (tCO₂eq)',
        yaxis_title='Status',
        plot_bgcolor='white',
        height=300,
        yaxis={'categoryorder':'total ascending'}
    )
    
    st.plotly_chart(fig, use_container_width=True)

# =========================
# APLICAÇÃO PRINCIPAL
# =========================

def main():
    # Cabeçalho principal
    st.markdown("""
    <div style='text-align: center; margin-bottom: 2rem;'>
        <h1 style='color: #1a5276;'>🌱 Dashboard de Mercado de Carbono Agrícola</h1>
        <p style='color: #5d6d7e; font-size: 1.1rem;'>
        Análise detalhada de créditos de carbono emitidos e negociados em projetos agrícolas
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Carregar dados
    with st.spinner("🔍 Carregando dados do dataset FAO..."):
        df, issued_cols, retired_cols, main_cols = load_agriculture_data()
    
    if df is None:
        st.error("🚨 Não foi possível carregar os dados. Verifique:")
        st.error("1. A conexão com a internet")
        st.error("2. O formato do arquivo Excel")
        st.error("3. Se a aba '4. Agriculture' existe")
        return
    
    # Informações sobre a estrutura encontrada
    with st.expander("ℹ️ Informações sobre a Estrutura de Dados", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Colunas de Créditos Emitidos", len(issued_cols))
        with col2:
            st.metric("Colunas de Créditos Negociados", len(retired_cols))
        with col3:
            st.metric("Total de Projetos", len(df))
        
        if issued_cols:
            st.write(f"**Anos de créditos emitidos:** {sorted(issued_cols.keys())}")
        if retired_cols:
            st.write(f"**Anos de créditos negociados:** {sorted(retired_cols.keys())}")
        if main_cols:
            st.write(f"**Colunas principais identificadas:** {list(main_cols.keys())}")
    
    # Analisar dados
    with st.spinner("📊 Analisando créditos de carbono..."):
        analysis = analyze_credits(df, issued_cols, retired_cols, main_cols)
    
    # Seção Hero
    create_hero_section(analysis)
    
    # Métricas principais
    st.markdown("---")
    create_main_metrics(analysis)
    
    # Layout principal
    st.markdown("## 📈 Análise Temporal")
    col1, col2 = st.columns(2)
    
    with col1:
        create_timeline_comparison(analysis)
    
    with col2:
        create_market_dynamics_chart(analysis)
    
    # Taxa de negociação
    st.markdown("## 📊 Taxa de Negociação")
    create_retirement_rate_chart(analysis)
    
    # Análise por projeto
    st.markdown("## 🏗️ Análise por Projeto")
    create_top_projects_table(analysis)
    
    # Análises geográficas e categorias
    st.markdown("## 🌍 Análise por Categoria")
    col1, col2 = st.columns(2)
    
    with col1:
        create_country_analysis(analysis)
    
    with col2:
        create_type_analysis(analysis)
    
    # Status dos projetos
    st.markdown("## 📝 Status dos Projetos")
    create_status_analysis(analysis)
    
    # Insights e conclusões
    st.markdown("---")
    st.markdown("## 💡 Principais Insights")
    
    insights_col1, insights_col2, insights_col3 = st.columns(3)
    
    with insights_col1:
        st.markdown("""
        ### 📦 Volume do Mercado
        • **Total emitido:** Indica o potencial total do setor  
        • **Taxa de negociação:** Mostra a liquidez do mercado  
        • **Crescimento anual:** Evolução do mercado ao longo do tempo
        """)
    
    with insights_col2:
        st.markdown("""
        ### 🌍 Distribuição Geográfica
        • **Concentração:** Identifica países líderes  
        • **Diversificação:** Distribuição por regiões  
        • **Potencial:** Países com menor participação
        """)
    
    with insights_col3:
        st.markdown("""
        ### 🏗️ Tipos de Projetos
        • **Eficiência:** Quais tipos geram mais créditos  
        • **Diversificação:** Variedade de abordagens  
        • **Inovação:** Novas metodologias emergentes
        """)
    
    # Definições técnicas
    st.markdown("---")
    st.subheader("📚 Definições Técnicas")
    
    def_col1, def_col2, def_col3 = st.columns(3)
    
    with def_col1:
        st.markdown("""
        ### 📦 Créditos Emitidos
        Volume total de créditos de carbono gerados por projetos certificados, medidos em toneladas de CO₂ equivalente (tCO₂eq). Representa o potencial total de mitigação climática do setor agrícola.
        """)
    
    with def_col2:
        st.markdown("""
        ### 💰 Créditos Negociados (Aposentados)
        Créditos que foram efetivamente comercializados no mercado, utilizados para compensação de emissões ou retirados de circulação. Indicam demanda real e transações efetivas.
        """)
    
    with def_col3:
        st.markdown("""
        ### 📈 Créditos Disponíveis
        Saldo de créditos emitidos que permanecem disponíveis para transação. Representa o estoque do mercado disponível para futuras negociações e compensações.
        """)
    
    # Footer informativo
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #5d6d7e; padding: 1rem; font-size: 0.9rem;'>
        <p><strong>📊 Dashboard de Análise de Mercado de Carbono Agrícola</strong></p>
        <p>🌱 Baseado no dataset FAO "Agrifood Carbon Markets" | Aba: 4. Agriculture</p>
        <p>📈 Dados processados em tempo real | Atualização automática</p>
        <p>🔍 Identificação automática de estrutura: Créditos emitidos vs negociados por ano</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar com informações adicionais
    with st.sidebar:
        st.markdown("## 📋 Informações do Dataset")
        
        st.metric("Total de Projetos", 
                 formatar_br_inteiro(analysis['total_projects']))
        
        st.metric("Projetos com Créditos", 
                 formatar_br_inteiro(analysis['projects_with_credits']))
        
        st.metric("Taxa de Negociação", 
                 f"{analysis['retirement_rate']:.2f}%")
        
        # Análise de eficiência
        if analysis['projects_with_credits'] > 0:
            avg_credits_per_project = analysis['total_credits_issued'] / analysis['projects_with_credits']
            st.metric("Média por Projeto", 
                     formatar_milhoes(avg_credits_per_project))
        
        st.markdown("---")
        st.markdown("### 💰 Análise Financeira")
        
        # Valores de referência
        preco_min = 10  # US$ por tCO₂eq
        preco_med = 15  # US$ por tCO₂eq
        preco_max = 25  # US$ por tCO₂eq
        
        # Calcular valores
        valor_min = analysis['total_credits_retired'] * preco_min
        valor_med = analysis['total_credits_retired'] * preco_med
        valor_max = analysis['total_credits_retired'] * preco_max
        
        st.markdown(f"**Valor de mercado estimado:**")
        st.markdown(f"• Mínimo (US${preco_min}/tCO₂eq): {formatar_moeda_curta(valor_min)}")
        st.markdown(f"• Médio (US${preco_med}/tCO₂eq): {formatar_moeda_curta(valor_med)}")
        st.markdown(f"• Máximo (US${preco_max}/tCO₂eq): {formatar_moeda_curta(valor_max)}")
        
        st.markdown("---")
        st.markdown("### ⚙️ Configurações")
        
        # Filtro de visualização
        view_option = st.selectbox(
            "Nível de Detalhe",
            ["Visão Geral", "Detalhado", "Técnico"]
        )
        
        if st.checkbox("Mostrar dados brutos"):
            st.dataframe(df.head(20))
        
        st.markdown("---")
        st.markdown("""
        **Fonte dos dados:**  
        FAO Agrifood Carbon Markets Dataset  
        **Versão:** v4  
        **Última atualização:** Automática  
        **Aba analisada:** 4. Agriculture
        """)

if __name__ == "__main__":
    main()
