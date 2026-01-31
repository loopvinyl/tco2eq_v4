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
import requests
from io import BytesIO

warnings.filterwarnings("ignore")

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Mercado de Carbono Agrícola - Baseado em Dados Reais de Projetos",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.fao.org/climate-change/our-work/carbon-markets',
        'Report a bug': None,
        'About': "Dashboard baseado em dados reais de projetos agrícolas de carbono para proprietários rurais entenderem oportunidades no mercado."
    }
)

# =========================
# FUNÇÕES DE FORMATAÇÃO BRASILEIRA - ATUALIZADAS
# =========================

def formatar_milhoes(numero):
    """
    Formata números grandes como milhões: 367,2 milhões
    """
    if pd.isna(numero):
        return "N/A"
    
    if numero >= 1000000000:  # Bilhões
        em_bilhoes = numero / 1000000000
        return f"{formatar_br_dec(em_bilhoes, 1)} bilhões"
    elif numero >= 1000000:
        em_milhoes = numero / 1000000
        return f"{formatar_br_dec(em_milhoes, 1)} milhões"
    elif numero >= 1000:
        em_mil = numero / 1000
        return f"{formatar_br_dec(em_mil, 1)} mil"
    else:
        return formatar_br_inteiro(numero)

def formatar_br(numero):
    """
    Formata números no padrão brasileiro: 1.234,56
    """
    if pd.isna(numero):
        return "N/A"
    
    # Arredonda para 2 casas decimais
    numero = round(numero, 2)
    
    # Formata como string e substitui o ponto pela vírgula
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_br_dec(numero, decimais=2):
    """
    Formata números no padrão brasileiro com número específico de casas decimais
    """
    if pd.isna(numero):
        return "N/A"
    
    # Arredonda para o número de casas decimais especificado
    numero = round(numero, decimais)
    
    # Formata como string e substitui o ponto pela vírgula
    return f"{numero:,.{decimais}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_br_inteiro(numero):
    """
    Formata números inteiros no padrão brasileiro: 1.234
    """
    if pd.isna(numero):
        return "N/A"
    
    # Arredonda para inteiro
    numero = int(round(numero, 0))
    
    # Formata como string
    return f"{numero:,}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_moeda_curta(numero):
    """
    Formata valores monetários de forma curta e inteligente:
    - > 1.000.000: X,X milhões
    - > 1.000: X,X mil
    - < 1.000: valor normal
    """
    if pd.isna(numero):
        return "N/A"
    
    numero = float(numero)
    
    if numero >= 1000000000:  # Bilhões
        valor = numero / 1000000000
        return f"{formatar_br_dec(valor, 1)} bilhões"
    elif numero >= 1000000:  # Milhões
        valor = numero / 1000000
        return f"{formatar_br_dec(valor, 1)} milhões"
    elif numero >= 1000:  # Mil
        valor = numero / 1000
        return f"{formatar_br_dec(valor, 1)} mil"
    else:
        return formatar_br(numero)

# =========================
# CARGA DE DADOS DO GITHUB
# =========================

@st.cache_data(ttl=3600, show_spinner="Carregando dataset do GitHub...")
def load_dataset_from_github():
    """Carrega o dataset datasetAgriculture.xlsx do GitHub"""
    
    # URL do arquivo no GitHub (raw)
    github_url = "https://raw.githubusercontent.com/seu_usuario/seu_repositorio/main/datasetAgriculture.xlsx"
    
    try:
        # Baixar o arquivo do GitHub
        response = requests.get(github_url)
        response.raise_for_status()  # Verifica se houve erro na requisição
        
        # Ler o Excel do conteúdo baixado
        excel_data = BytesIO(response.content)
        excel_file = pd.ExcelFile(excel_data, engine='openpyxl')
        
        # Carregar a planilha principal
        sheet_name = 'Planilha1'  # Nome da planilha no arquivo
        
        if sheet_name not in excel_file.sheet_names:
            # Tentar o primeiro sheet se Planilha1 não existir
            sheet_name = excel_file.sheet_names[0]
        
        df = pd.read_excel(excel_data, sheet_name=sheet_name, header=0)
        
        st.success(f"✅ Dataset carregado com sucesso! {len(df)} registros encontrados.")
        
        # Mostrar informações básicas
        st.info(f"""
        **Informações do Dataset:**
        - Total de projetos: {len(df)}
        - Colunas disponíveis: {len(df.columns)}
        - Colunas principais: {', '.join(df.columns[:10].tolist())}...
        """)
        
        return df
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro ao baixar o arquivo do GitHub: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Erro ao processar o dataset: {e}")
        return None

# =========================
# ANÁLISE DE PROJETOS VÁLIDOS
# =========================

@st.cache_data(ttl=3600, show_spinner="Analisando projetos válidos...")
def analyze_valid_projects(df):
    """
    Analisa projetos válidos que emitiram créditos de carbono
    
    Critérios:
    1. Projeto deve ter "Total Credits Issued" > 0
    2. Projeto deve ter status válido (Completed, Registered, etc.)
    """
    
    analysis = {
        'estatisticas_gerais': {},
        'projetos_por_pais': {},
        'projetos_por_tipo': {},
        'projetos_por_registro': {},
        'projetos_validos': [],
        'timeline_emissao': {},
        'timeline_aposentadoria': {},
        'comparativo_emitidos_vs_aposentados': {
            'total_emitido': 0,
            'total_aposentado': 0,
            'taxa_aposentadoria': 0,
            'creditos_disponiveis': 0
        },
        'projetos_detalhados': []
    }
    
    if df is None or df.empty:
        return analysis
    
    # Identificar colunas importantes
    colunas = df.columns.tolist()
    
    # Procurar colunas por padrões (case insensitive)
    col_map = {}
    
    for col in colunas:
        col_lower = str(col).lower()
        
        # Mapear colunas importantes
        if 'total credits issued' in col_lower:
            col_map['creditos_emitidos'] = col
        elif 'total credits retired' in col_lower:
            col_map['creditos_aposentados'] = col
        elif 'total credits remaining' in col_lower:
            col_map['creditos_restantes'] = col
        elif 'voluntary status' in col_lower:
            col_map['status'] = col
        elif 'project name' in col_lower:
            col_map['nome'] = col
        elif 'country' in col_lower:
            col_map['pais'] = col
        elif 'type' in col_lower:
            col_map['tipo'] = col
        elif 'voluntary registry' in col_lower:
            col_map['registro'] = col
        elif 'project id' in col_lower:
            col_map['id'] = col
    
    st.write("**Colunas identificadas:**", col_map)
    
    # Verificar se temos as colunas mínimas necessárias
    if 'creditos_emitidos' not in col_map:
        st.warning("⚠️ Coluna 'Total Credits Issued' não encontrada. Tentando identificar automaticamente...")
        # Tentar encontrar coluna com 'issued' ou 'credit' no nome
        for col in colunas:
            col_lower = str(col).lower()
            if 'issued' in col_lower or 'credit' in col_lower and 'retired' not in col_lower:
                col_map['creditos_emitidos'] = col
                break
    
    if 'creditos_emitidos' not in col_map:
        st.error("❌ Não foi possível identificar a coluna de créditos emitidos.")
        return analysis
    
    # Filtrar projetos válidos
    df_valid = df.copy()
    
    # Converter coluna de créditos emitidos para numérico
    try:
        df_valid[col_map['creditos_emitidos']] = pd.to_numeric(
            df_valid[col_map['creditos_emitidos']], errors='coerce'
        )
    except:
        st.error("❌ Erro ao converter créditos emitidos para numérico.")
        return analysis
    
    # Filtrar projetos com créditos emitidos > 0
    df_valid = df_valid[df_valid[col_map['creditos_emitidos']] > 0]
    
    if df_valid.empty:
        st.warning("⚠️ Nenhum projeto com créditos emitidos encontrado.")
        return analysis
    
    # Identificar status válidos
    status_validos = ['Completed', 'Registered', 'Gold Standard Certified Project', 
                     'Gold Standard Certified Design', 'Under validation', 'Registered']
    
    if 'status' in col_map:
        # Normalizar status
        df_valid['status_normalizado'] = df_valid[col_map['status']].astype(str).str.strip()
        df_valid = df_valid[df_valid['status_normalizado'].isin(status_validos)]
    
    st.success(f"✅ Encontrados {len(df_valid)} projetos válidos que emitiram créditos.")
    
    # Coletar estatísticas básicas
    total_emitido = df_valid[col_map['creditos_emitidos']].sum()
    
    if 'creditos_aposentados' in col_map:
        df_valid[col_map['creditos_aposentados']] = pd.to_numeric(
            df_valid[col_map['creditos_aposentados']], errors='coerce'
        )
        total_aposentado = df_valid[col_map['creditos_aposentados']].sum()
        taxa_aposentadoria = (total_aposentado / total_emitido * 100) if total_emitido > 0 else 0
        creditos_disponiveis = total_emitido - total_aposentado
    else:
        total_aposentado = 0
        taxa_aposentadoria = 0
        creditos_disponiveis = total_emitido
    
    # Projetos por país
    if 'pais' in col_map:
        paises = df_valid[col_map['pais']].value_counts()
        for pais, count in paises.items():
            if pd.notna(pais):
                analysis['projetos_por_pais'][str(pais)] = int(count)
    
    # Projetos por tipo
    if 'tipo' in col_map:
        tipos = df_valid[col_map['tipo']].value_counts()
        for tipo, count in tipos.items():
            if pd.notna(tipo):
                analysis['projetos_por_tipo'][str(tipo)] = int(count)
    
    # Projetos por registro
    if 'registro' in col_map:
        registros = df_valid[col_map['registro']].value_counts()
        for registro, count in registros.items():
            if pd.notna(registro):
                analysis['projetos_por_registro'][str(registro)] = int(count)
    
    # Coletar projetos detalhados
    for idx, row in df_valid.iterrows():
        projeto = {
            'id': row[col_map['id']] if 'id' in col_map else f"Projeto_{idx}",
            'nome': row[col_map['nome']] if 'nome' in col_map else f"Projeto {idx}",
            'creditos_emitidos': float(row[col_map['creditos_emitidos']]),
            'creditos_aposentados': float(row[col_map['creditos_aposentados']]) if 'creditos_aposentados' in col_map else 0,
            'pais': str(row[col_map['pais']]) if 'pais' in col_map else 'Não especificado',
            'tipo': str(row[col_map['tipo']]) if 'tipo' in col_map else 'Não especificado',
            'registro': str(row[col_map['registro']]) if 'registro' in col_map else 'Não especificado',
            'status': str(row[col_map['status']]) if 'status' in col_map else 'Não especificado'
        }
        
        # Calcular taxa de aposentadoria do projeto
        if projeto['creditos_emitidos'] > 0:
            projeto['taxa_aposentadoria'] = (projeto['creditos_aposentados'] / projeto['creditos_emitidos']) * 100
        else:
            projeto['taxa_aposentadoria'] = 0
        
        analysis['projetos_detalhados'].append(projeto)
    
    # Analisar colunas anuais
    year_columns = []
    
    # Identificar colunas que são anos (1996, 1997, etc.)
    for col in colunas:
        try:
            # Tentar converter para número
            if isinstance(col, (int, float)):
                year = int(col)
                if 1990 <= year <= 2030:  # Faixa razoável de anos
                    year_columns.append(col)
            elif str(col).isdigit():
                year = int(str(col))
                if 1990 <= year <= 2030:
                    year_columns.append(col)
        except:
            continue
    
    # Separar colunas de emissão vs aposentadoria
    # Vamos assumir que as primeiras colunas de anos são emissões e as últimas são aposentadorias
    # Isso é uma simplificação - no dataset real precisamos analisar melhor
    half = len(year_columns) // 2
    emission_years = year_columns[:half]
    retirement_years = year_columns[half:] if len(year_columns) > half else []
    
    # Coletar dados da timeline
    for year in emission_years:
        if year in df_valid.columns:
            try:
                year_data = pd.to_numeric(df_valid[year], errors='coerce')
                total_year = year_data.sum()
                if pd.notna(total_year) and total_year > 0:
                    analysis['timeline_emissao'][int(year)] = float(total_year)
            except:
                pass
    
    for year in retirement_years:
        if year in df_valid.columns:
            try:
                year_data = pd.to_numeric(df_valid[year], errors='coerce')
                total_year = year_data.sum()
                if pd.notna(total_year) and total_year > 0:
                    analysis['timeline_aposentadoria'][int(year)] = float(total_year)
            except:
                pass
    
    # Estatísticas gerais
    analysis['estatisticas_gerais'] = {
        'total_projetos_validos': len(df_valid),
        'total_creditos_emitidos': total_emitido,
        'total_creditos_aposentados': total_aposentado,
        'taxa_aposentadoria_geral': taxa_aposentadoria,
        'creditos_disponiveis': creditos_disponiveis,
        'media_creditos_por_projeto': total_emitido / len(df_valid) if len(df_valid) > 0 else 0,
        'paises_com_projetos': len(analysis['projetos_por_pais']),
        'tipos_de_projeto': len(analysis['projetos_por_tipo']),
        'registros_utilizados': len(analysis['projetos_por_registro'])
    }
    
    # Comparativo
    analysis['comparativo_emitidos_vs_aposentados'] = {
        'total_emitido': total_emitido,
        'total_aposentado': total_aposentado,
        'taxa_aposentadoria': taxa_aposentadoria,
        'creditos_disponiveis': creditos_disponiveis
    }
    
    return analysis

# =========================
# COMPONENTES DE UI
# =========================

def create_hero_section(analysis):
    """Cria seção hero com dados reais"""
    
    if not analysis or 'estatisticas_gerais' not in analysis:
        st.markdown(f"""
        <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                    background: linear-gradient(135deg, #27ae60, #229954); 
                    color: white; margin-bottom: 2rem;'>
            <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>🌱 Mercado de Carbono Agrícola</h1>
            <h3 style='font-weight: 300;'>Baseado em dados reais de projetos certificados</h3>
            <p style='font-size: 1.1rem; opacity: 0.9;'>
                Carregando análise...
            </p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    stats = analysis['estatisticas_gerais']
    
    # Formatar valores para exibição
    total_projetos = stats.get('total_projetos_validos', 0)
    total_emitido = stats.get('total_creditos_emitidos', 0)
    total_aposentado = stats.get('total_creditos_aposentados', 0)
    taxa_aposentadoria = stats.get('taxa_aposentadoria_geral', 0)
    
    total_emitido_fmt = formatar_milhoes(total_emitido)
    total_aposentado_fmt = formatar_milhoes(total_aposentado)
    
    st.markdown(f"""
    <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                background: linear-gradient(135deg, #27ae60, #229954); 
                color: white; margin-bottom: 2rem;'>
        <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>🌱 Mercado de Carbono Agrícola</h1>
        <h3 style='font-weight: 300;'>Baseado em {formatar_br_inteiro(total_projetos)} projetos que emitiram créditos de carbono</h3>
        <p style='font-size: 1.1rem; opacity: 0.9;'>
            {total_emitido_fmt} créditos emitidos • {total_aposentado_fmt} créditos aposentados • 
            {formatar_br_dec(taxa_aposentadoria, 2)}% taxa de aposentadoria
        </p>
    </div>
    """, unsafe_allow_html=True)

def create_summary_cards(analysis):
    """Cria cartões com resumo das estatísticas"""
    
    if not analysis or 'estatisticas_gerais' not in analysis:
        return
    
    stats = analysis['estatisticas_gerais']
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📊 Projetos Válidos",
            formatar_br_inteiro(stats.get('total_projetos_validos', 0)),
            f"{stats.get('paises_com_projetos', 0)} países"
        )
    
    with col2:
        st.metric(
            "🌱 Créditos Emitidos",
            formatar_milhoes(stats.get('total_creditos_emitidos', 0)),
            "tCO₂eq"
        )
    
    with col3:
        st.metric(
            "💰 Créditos Aposentados",
            formatar_milhoes(stats.get('total_creditos_aposentados', 0)),
            f"{formatar_br_dec(stats.get('taxa_aposentadoria_geral', 0), 2)}%"
        )
    
    with col4:
        st.metric(
            "💎 Créditos Disponíveis",
            formatar_milhoes(stats.get('creditos_disponiveis', 0)),
            "Para venda"
        )

def create_emission_vs_retirement_chart(analysis):
    """Cria gráfico comparando créditos emitidos vs aposentados"""
    
    comparativo = analysis.get('comparativo_emitidos_vs_aposentados', {})
    
    if not comparativo or comparativo.get('total_emitido', 0) == 0:
        return
    
    # Preparar dados para o gráfico
    dados = pd.DataFrame({
        'Tipo': ['Emitidos', 'Aposentados', 'Disponíveis'],
        'Créditos (tCO₂eq)': [
            comparativo.get('total_emitido', 0),
            comparativo.get('total_aposentado', 0),
            comparativo.get('creditos_disponiveis', 0)
        ]
    })
    
    # Formatar valores para exibição
    dados['Formatado'] = dados['Créditos (tCO₂eq)'].apply(formatar_milhoes)
    
    # Criar gráfico de barras
    fig = px.bar(
        dados,
        x='Tipo',
        y='Créditos (tCO₂eq)',
        color='Tipo',
        color_discrete_map={
            'Emitidos': '#2ecc71',
            'Aposentados': '#3498db',
            'Disponíveis': '#f39c12'
        },
        text='Formatado',
        title='Comparação de Créditos Emitidos vs Aposentados'
    )
    
    fig.update_traces(textposition='outside')
    fig.update_layout(
        yaxis_title='Créditos (tCO₂eq)',
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_projects_by_country_chart(analysis):
    """Cria gráfico de projetos por país"""
    
    paises = analysis.get('projetos_por_pais', {})
    
    if not paises:
        return
    
    # Converter para DataFrame
    df_paises = pd.DataFrame(
        list(paises.items()),
        columns=['País', 'Projetos']
    ).sort_values('Projetos', ascending=False).head(15)
    
    # Gráfico de barras
    fig = px.bar(
        df_paises,
        x='País',
        y='Projetos',
        color='Projetos',
        color_continuous_scale='Greens',
        title='Top 15 Países com Mais Projetos'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_projects_by_type_chart(analysis):
    """Cria gráfico de projetos por tipo"""
    
    tipos = analysis.get('projetos_por_tipo', {})
    
    if not tipos:
        return
    
    # Converter para DataFrame
    df_tipos = pd.DataFrame(
        list(tipos.items()),
        columns=['Tipo', 'Projetos']
    ).sort_values('Projetos', ascending=False)
    
    # Gráfico de pizza
    fig = px.pie(
        df_tipos,
        values='Projetos',
        names='Tipo',
        title='Distribuição de Projetos por Tipo',
        hole=0.3
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_timeline_charts(analysis):
    """Cria gráficos de timeline de emissões e aposentadorias"""
    
    timeline_emissao = analysis.get('timeline_emissao', {})
    timeline_aposentadoria = analysis.get('timeline_aposentadoria', {})
    
    if not timeline_emissao and not timeline_aposentadoria:
        return
    
    # Preparar dados
    years = sorted(set(list(timeline_emissao.keys()) + list(timeline_aposentadoria.keys())))
    
    dados = []
    for year in years:
        dados.append({
            'Ano': year,
            'Emissões': timeline_emissao.get(year, 0),
            'Aposentadorias': timeline_aposentadoria.get(year, 0)
        })
    
    df_timeline = pd.DataFrame(dados)
    
    # Gráfico de linha
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_timeline['Ano'],
        y=df_timeline['Emissões'],
        mode='lines+markers',
        name='Créditos Emitidos',
        line=dict(color='#2ecc71', width=3),
        marker=dict(size=8)
    ))
    
    fig.add_trace(go.Scatter(
        x=df_timeline['Ano'],
        y=df_timeline['Aposentadorias'],
        mode='lines+markers',
        name='Créditos Aposentados',
        line=dict(color='#3498db', width=3),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title='Timeline de Créditos Emitidos vs Aposentados',
        xaxis_title='Ano',
        yaxis_title='Créditos (tCO₂eq)',
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_projects_table(analysis):
    """Cria tabela de projetos detalhados"""
    
    projetos = analysis.get('projetos_detalhados', [])
    
    if not projetos:
        return
    
    st.markdown("### 📋 Detalhes dos Projetos")
    
    # Converter para DataFrame
    df_projetos = pd.DataFrame(projetos)
    
    # Selecionar colunas para exibição
    display_cols = ['id', 'nome', 'pais', 'tipo', 'registro', 'creditos_emitidos', 
                   'creditos_aposentados', 'taxa_aposentadoria']
    
    # Filtrar colunas disponíveis
    available_cols = [col for col in display_cols if col in df_projetos.columns]
    
    if not available_cols:
        return
    
    df_display = df_projetos[available_cols].copy()
    
    # Formatar colunas numéricas
    if 'creditos_emitidos' in df_display.columns:
        df_display['creditos_emitidos'] = df_display['creditos_emitidos'].apply(
            lambda x: formatar_br_inteiro(x) if pd.notna(x) else 'N/A'
        )
    
    if 'creditos_aposentados' in df_display.columns:
        df_display['creditos_aposentados'] = df_display['creditos_aposentados'].apply(
            lambda x: formatar_br_inteiro(x) if pd.notna(x) else 'N/A'
        )
    
    if 'taxa_aposentadoria' in df_display.columns:
        df_display['taxa_aposentadoria'] = df_display['taxa_aposentadoria'].apply(
            lambda x: f"{formatar_br_dec(x, 2)}%" if pd.notna(x) else 'N/A'
        )
    
    # Renomear colunas para exibição
    col_names = {
        'id': 'ID',
        'nome': 'Nome do Projeto',
        'pais': 'País',
        'tipo': 'Tipo',
        'registro': 'Registro',
        'creditos_emitidos': 'Créditos Emitidos',
        'creditos_aposentados': 'Créditos Aposentados',
        'taxa_aposentadoria': 'Taxa de Aposentadoria'
    }
    
    df_display = df_display.rename(columns=col_names)
    
    # Mostrar tabela
    st.dataframe(
        df_display.head(50),  # Limitar a 50 linhas
        use_container_width=True,
        height=400
    )
    
    # Botão para baixar dados
    csv = df_projetos.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar todos os projetos (CSV)",
        data=csv,
        file_name="projetos_carbono_agricola.csv",
        mime="text/csv"
    )

# =========================
# PÁGINAS PRINCIPAIS
# =========================

def render_dashboard(df, analysis):
    """Página principal do dashboard"""
    
    create_hero_section(analysis)
    
    # Cartões de resumo
    create_summary_cards(analysis)
    
    # Gráficos principais
    col1, col2 = st.columns(2)
    
    with col1:
        create_emission_vs_retirement_chart(analysis)
    
    with col2:
        create_projects_by_type_chart(analysis)
    
    # Timeline
    st.markdown("## 📅 Timeline de Emissões e Aposentadorias")
    create_timeline_charts(analysis)
    
    # Projetos por país
    st.markdown("## 🌍 Distribuição por País")
    create_projects_by_country_chart(analysis)
    
    # Tabela de projetos
    create_projects_table(analysis)
    
    # Informações técnicas
    with st.expander("🔍 Informações Técnicas"):
        st.markdown("""
        ### Sobre a Análise
        
        **Critérios para projetos válidos:**
        1. Projeto deve ter emitido créditos de carbono (Total Credits Issued > 0)
        2. Projeto deve ter status válido (Completed, Registered, etc.)
        
        **Métricas calculadas:**
        - **Créditos emitidos:** Total de créditos de carbono gerados pelo projeto
        - **Créditos aposentados:** Créditos que foram vendidos/retirados do mercado
        - **Taxa de aposentadoria:** Percentual de créditos vendidos em relação aos emitidos
        - **Créditos disponíveis:** Créditos emitidos que ainda não foram vendidos
        
        **Fonte dos dados:** datasetAgriculture.xlsx (GitHub)
        """)

def render_data_explorer(df):
    """Explorador de dados brutos"""
    
    st.markdown("## 🔍 Explorador de Dados Brutos")
    
    if df is None or df.empty:
        st.warning("Nenhum dado disponível para explorar.")
        return
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filtrar por coluna
        coluna_filtro = st.selectbox(
            "Selecionar coluna para filtrar:",
            options=[""] + df.columns.tolist()
        )
    
    with col2:
        if coluna_filtro:
            valores_unicos = df[coluna_filtro].dropna().unique()
            valor_filtro = st.selectbox(
                f"Valor em {coluna_filtro}:",
                options=[""] + [str(v) for v in valores_unicos[:100]]  # Limitar a 100 valores
            )
    
    with col3:
        # Limitar número de linhas
        n_linhas = st.slider(
            "Número de linhas a mostrar:",
            min_value=10,
            max_value=500,
            value=100,
            step=10
        )
    
    # Aplicar filtros
    df_filtrado = df.copy()
    
    if coluna_filtro and valor_filtro:
        try:
            df_filtrado = df_filtrado[df_filtrado[coluna_filtro].astype(str) == valor_filtro]
        except:
            st.warning(f"Não foi possível aplicar o filtro na coluna {coluna_filtro}")
    
    # Mostrar dados
    st.dataframe(
        df_filtrado.head(n_linhas),
        use_container_width=True,
        height=400
    )
    
    # Estatísticas
    st.markdown("### 📊 Estatísticas das Colunas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total de Linhas", formatar_br_inteiro(len(df_filtrado)))
    
    with col2:
        st.metric("Total de Colunas", formatar_br_inteiro(len(df_filtrado.columns)))
    
    with col3:
        # Contar valores não nulos
        valores_nao_nulos = df_filtrado.count().sum()
        st.metric("Valores Não Nulos", formatar_br_inteiro(valores_nao_nulos))
    
    # Informações sobre as colunas
    with st.expander("📋 Informações das Colunas"):
        colunas_info = []
        
        for col in df_filtrado.columns:
            tipo = str(df_filtrado[col].dtype)
            nao_nulos = df_filtrado[col].count()
            nulos = len(df_filtrado) - nao_nulos
            percentual_nao_nulos = (nao_nulos / len(df_filtrado)) * 100 if len(df_filtrado) > 0 else 0
            
            colunas_info.append({
                'Coluna': col,
                'Tipo': tipo,
                'Não Nulos': nao_nulos,
                '% Não Nulos': f"{percentual_nao_nulos:.1f}%",
                'Valores Únicos': df_filtrado[col].nunique()
            })
        
        df_colunas = pd.DataFrame(colunas_info)
        st.dataframe(df_colunas, use_container_width=True)

# =========================
# APLICAÇÃO PRINCIPAL
# =========================

def main():
    st.title("🌱 Dashboard de Análise de Mercado de Carbono Agrícola")
    st.markdown("### Baseado em dados reais de projetos certificados")
    
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 1rem;'>
            <h2 style='color: #27ae60;'>📊 Análise de Projetos</h2>
            <p style='color: #7f8c8d;'>Dashboard interativo</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Seletor de página
        page = st.radio(
            "Navegação",
            ["📈 Dashboard", "🔍 Explorador de Dados", "ℹ️ Sobre"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Configurações
        st.markdown("### ⚙️ Configurações")
        
        # Opção de recarregar dados
        if st.button("🔄 Recarregar Dados"):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        
        # Informações
        st.markdown("### 📚 Sobre os Dados")
        st.markdown("""
        **Fonte:** datasetAgriculture.xlsx  
        **Conteúdo:** Projetos agrícolas de carbono  
        **Métrica:** tCO₂eq (toneladas de CO₂ equivalente)  
        **Status:** Projetos que emitiram créditos
        """)
    
    # Carregar dados
    if 'df' not in st.session_state:
        with st.spinner("Carregando dados do GitHub..."):
            df = load_dataset_from_github()
            if df is not None:
                st.session_state.df = df
                # Analisar dados
                analysis = analyze_valid_projects(df)
                st.session_state.analysis = analysis
            else:
                st.error("Não foi possível carregar os dados.")
                return
    else:
        df = st.session_state.df
        analysis = st.session_state.analysis
    
    # Renderizar página selecionada
    if page == "📈 Dashboard":
        if analysis and analysis.get('estatisticas_gerais'):
            render_dashboard(df, analysis)
        else:
            st.warning("Análise em andamento...")
    
    elif page == "🔍 Explorador de Dados":
        render_data_explorer(df)
    
    else:  # Sobre
        st.markdown("""
        ## ℹ️ Sobre este Dashboard
        
        ### Objetivo
        Este dashboard tem como objetivo analisar projetos agrícolas de carbono que 
        efetivamente emitiram créditos de carbono, baseando-se em dados reais.
        
        ### Funcionalidades
        
        1. **Identificação de projetos válidos:** Projetos que emitiram créditos de carbono
        2. **Análise de créditos emitidos:** Quantidade total de créditos gerados
        3. **Análise de créditos aposentados:** Créditos que foram vendidos/retirados
        4. **Cálculo de disponibilidade:** Créditos ainda disponíveis para venda
        5. **Distribuição geográfica:** Projetos por país
        6. **Análise por tipo:** Tipos de projetos agrícolas
        7. **Timeline:** Evolução temporal das emissões e aposentadorias
        
        ### Metodologia
        
        **Critérios de validação:**
        - Projeto deve ter "Total Credits Issued" > 0
        - Projeto deve ter status válido (Completed, Registered, etc.)
        
        **Cálculos:**
        - Taxa de aposentadoria = (Créditos Aposentados / Créditos Emitidos) × 100
        - Créditos Disponíveis = Créditos Emitidos - Créditos Aposentados
        
        ### Fonte dos Dados
        Os dados são extraídos do arquivo `datasetAgriculture.xlsx` hospedado no GitHub,
        que contém informações detalhadas sobre projetos agrícolas de carbono.
        
        ### Tecnologias Utilizadas
        - **Streamlit:** Interface web interativa
        - **Pandas:** Processamento de dados
        - **Plotly:** Visualizações gráficas
        - **GitHub:** Hospedagem dos dados
        
        ### Limitações
        1. A análise depende da qualidade e completude dos dados originais
        2. Algumas colunas podem ter nomes diferentes, requerendo ajustes manuais
        3. Dados históricos podem estar incompletos para alguns projetos
        
        ### Contato
        Para sugestões ou reportar problemas, entre em contato através do GitHub.
        """)

# =========================
# EXECUÇÃO
# =========================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")
        st.info("Recarregue a página ou verifique a conexão com o GitHub.")
