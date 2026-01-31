import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import BytesIO
from typing import Dict, List, Tuple
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

def formatar_br_inteiro(numero):
    """Formata números inteiros no padrão brasileiro: 1.234"""
    if pd.isna(numero):
        return "N/A"
    numero = int(round(numero, 0))
    return f"{numero:,}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_milhoes(numero):
    """Formata números grandes como milhões: 367,2 milhões"""
    if pd.isna(numero):
        return "N/A"
    if numero >= 1000000000:
        em_bilhoes = numero / 1000000000
        return f"{em_bilhoes:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " bilhões"
    elif numero >= 1000000:
        em_milhoes = numero / 1000000
        return f"{em_milhoes:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " milhões"
    elif numero >= 1000:
        em_mil = numero / 1000
        return f"{em_mil:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " mil"
    else:
        return formatar_br_inteiro(numero)

def formatar_moeda_curta(numero):
    """Formata valores monetários de forma curta"""
    if pd.isna(numero):
        return "N/A"
    numero = float(numero)
    if numero >= 1000000000:
        valor = numero / 1000000000
        return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " bilhões"
    elif numero >= 1000000:
        valor = numero / 1000000
        return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " milhões"
    elif numero >= 1000:
        valor = numero / 1000
        return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " mil"
    else:
        return f"{numero:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =========================
# CARGA DE DADOS
# =========================

@st.cache_data(ttl=3600)
def load_agriculture_data():
    """Carrega apenas a aba 4. Agriculture do dataset"""
    try:
        # URL do arquivo no GitHub
        url = "https://github.com/loopvinyl/tco2eq_v4/raw/main/Dataset.xlsx"
        response = requests.get(url)
        response.raise_for_status()
        
        # Ler a aba 4. Agriculture
        excel_file = BytesIO(response.content)
        df = pd.read_excel(excel_file, sheet_name='4. Agriculture')
        
        # Identificar colunas de créditos (ano a ano)
        credit_cols = {}
        
        # Procurar por colunas que contenham anos de 1996 a 2023
        for col in df.columns:
            col_str = str(col)
            # Verificar se é um ano
            year_match = re.search(r'(19[9][6-9]|20[0-2][0-9]|202[0-3])', col_str)
            if year_match:
                year = int(year_match.group(0))
                if 'retired' not in col_str.lower() and 'remaining' not in col_str.lower():
                    credit_cols[year] = col
        
        # Identificar colunas principais
        main_cols = {}
        for col in df.columns:
            col_str = str(col).lower()
            if 'project id' in col_str:
                main_cols['project_id'] = col
            elif 'project name' in col_str:
                main_cols['project_name'] = col
            elif 'voluntary status' in col_str:
                main_cols['status'] = col
            elif 'country' in col_str:
                main_cols['country'] = col
            elif 'type' in col_str:
                main_cols['type'] = col
            elif 'total credits issued' in col_str:
                main_cols['total_issued'] = col
            elif 'total credits retired' in col_str:
                main_cols['total_retired'] = col
            elif 'total credits remaining' in col_str:
                main_cols['total_remaining'] = col
            elif 'methodology' in col_str or 'protocol' in col_str:
                main_cols['methodology'] = col
        
        return df, credit_cols, main_cols
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return None, None, None

@st.cache_data
def analyze_credits(df, credit_cols, main_cols):
    """Analisa créditos emitidos, aposentados e remanescentes"""
    
    if df is None or df.empty:
        return {}
    
    analysis = {
        'total_projects': 0,
        'projects_with_credits': 0,
        'total_credits_issued': 0,
        'total_credits_retired': 0,
        'total_credits_remaining': 0,
        'retirement_rate': 0,
        'credits_by_year': {},
        'top_projects': [],
        'by_country': {},
        'by_type': {},
        'by_status': {}
    }
    
    # Calcular totais
    if 'total_issued' in main_cols:
        # Converter para numérico
        df[main_cols['total_issued']] = pd.to_numeric(df[main_cols['total_issued']], errors='coerce')
        analysis['total_credits_issued'] = df[main_cols['total_issued']].sum()
    
    if 'total_retired' in main_cols:
        df[main_cols['total_retired']] = pd.to_numeric(df[main_cols['total_retired']], errors='coerce')
        analysis['total_credits_retired'] = df[main_cols['total_retired']].sum()
    
    if 'total_remaining' in main_cols:
        df[main_cols['total_remaining']] = pd.to_numeric(df[main_cols['total_remaining']], errors='coerce')
        analysis['total_credits_remaining'] = df[main_cols['total_remaining']].sum()
    
    # Total de projetos
    analysis['total_projects'] = len(df)
    
    # Projetos com créditos emitidos
    if 'total_issued' in main_cols:
        projects_with_credits = df[df[main_cols['total_issued']] > 0]
        analysis['projects_with_credits'] = len(projects_with_credits)
    
    # Taxa de aposentadoria
    if analysis['total_credits_issued'] > 0:
        analysis['retirement_rate'] = (analysis['total_credits_retired'] / analysis['total_credits_issued']) * 100
    
    # Análise por ano (se tiver colunas de anos)
    if credit_cols:
        for year, col in credit_cols.items():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                analysis['credits_by_year'][year] = df[col].sum()
    
    # Top projetos por créditos emitidos
    if 'total_issued' in main_cols and 'project_name' in main_cols:
        top_df = df.nlargest(10, main_cols['total_issued'])
        for _, row in top_df.iterrows():
            project = {
                'name': row[main_cols['project_name']],
                'issued': row[main_cols['total_issued']] if pd.notna(row[main_cols['total_issued']]) else 0,
                'retired': row[main_cols['total_retired']] if 'total_retired' in main_cols and pd.notna(row[main_cols['total_retired']]) else 0,
                'remaining': row[main_cols['total_remaining']] if 'total_remaining' in main_cols and pd.notna(row[main_cols['total_remaining']]) else 0,
                'country': row[main_cols['country']] if 'country' in main_cols else 'N/A'
            }
            analysis['top_projects'].append(project)
    
    # Análise por país
    if 'country' in main_cols and 'total_issued' in main_cols:
        country_analysis = df.groupby(main_cols['country'])[main_cols['total_issued']].sum().reset_index()
        country_analysis.columns = ['country', 'total_issued']
        for _, row in country_analysis.iterrows():
            analysis['by_country'][row['country']] = row['total_issued']
    
    # Análise por tipo
    if 'type' in main_cols and 'total_issued' in main_cols:
        type_analysis = df.groupby(main_cols['type'])[main_cols['total_issued']].sum().reset_index()
        type_analysis.columns = ['type', 'total_issued']
        for _, row in type_analysis.iterrows():
            analysis['by_type'][row['type']] = row['total_issued']
    
    # Análise por status
    if 'status' in main_cols and 'total_issued' in main_cols:
        status_analysis = df.groupby(main_cols['status'])[main_cols['total_issued']].sum().reset_index()
        status_analysis.columns = ['status', 'total_issued']
        for _, row in status_analysis.iterrows():
            analysis['by_status'][row['status']] = row['total_issued']
    
    return analysis

# =========================
# FUNÇÕES DE VISUALIZAÇÃO
# =========================

def create_hero_section(analysis):
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
    
    st.markdown(f"""
    <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                background: linear-gradient(135deg, #27ae60, #229954); 
                color: white; margin-bottom: 2rem;'>
        <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>📊 Análise de Créditos de Carbono</h1>
        <h3 style='font-weight: 300;'>Baseado no Dataset FAO - Agricultura</h3>
        <div style='display: flex; justify-content: center; gap: 3rem; margin-top: 1.5rem;'>
            <div>
                <div style='font-size: 2.5rem; font-weight: bold;'>🌱</div>
                <div style='font-size: 1.5rem;'>{total_issued_fmt}</div>
                <div style='font-size: 0.9rem; opacity: 0.9;'>Créditos Emitidos</div>
            </div>
            <div>
                <div style='font-size: 2.5rem; font-weight: bold;'>💰</div>
                <div style='font-size: 1.5rem;'>{total_retired_fmt}</div>
                <div style='font-size: 0.9rem; opacity: 0.9;'>Créditos Aposentados</div>
            </div>
            <div>
                <div style='font-size: 2.5rem; font-weight: bold;'>📈</div>
                <div style='font-size: 1.5rem;'>{total_remaining_fmt}</div>
                <div style='font-size: 0.9rem; opacity: 0.9;'>Créditos Disponíveis</div>
            </div>
            <div>
                <div style='font-size: 2.5rem; font-weight: bold;'>📊</div>
                <div style='font-size: 1.5rem;'>{retirement_rate_fmt}</div>
                <div style='font-size: 0.9rem; opacity: 0.9;'>Taxa de Aposentadoria</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def create_main_metrics(analysis):
    """Cria seção de métricas principais"""
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "🌱 Créditos Emitidos",
            formatar_milhoes(analysis['total_credits_issued']),
            help="Total de créditos de carbono gerados (tCO₂eq)"
        )
    
    with col2:
        st.metric(
            "💰 Créditos Aposentados", 
            formatar_milhoes(analysis['total_credits_retired']),
            help="Créditos que foram utilizados/compensados",
            delta=f"{analysis['retirement_rate']:.2f}% do total"
        )
    
    with col3:
        st.metric(
            "📈 Créditos Disponíveis",
            formatar_milhoes(analysis['total_credits_remaining']),
            help="Créditos ainda disponíveis no mercado"
        )
    
    with col4:
        st.metric(
            "📊 Taxa de Aposentadoria",
            f"{analysis['retirement_rate']:.2f}%",
            help="Porcentagem de créditos emitidos que já foram aposentados"
        )

def create_comparison_chart(analysis):
    """Cria gráfico de comparação entre emitidos, aposentados e remanescentes"""
    
    labels = ['Emitidos', 'Aposentados', 'Disponíveis']
    values = [
        analysis['total_credits_issued'],
        analysis['total_credits_retired'], 
        analysis['total_credits_remaining']
    ]
    
    # Formatar para exibição
    formatted_values = [formatar_milhoes(v) for v in values]
    
    fig = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            text=formatted_values,
            textposition='auto',
            marker_color=['#2ecc71', '#e74c3c', '#3498db']
        )
    ])
    
    fig.update_layout(
        title='Comparação: Créditos Emitidos vs Aposentados vs Disponíveis',
        yaxis_title='Créditos (tCO₂eq)',
        plot_bgcolor='white',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_timeline_chart(analysis):
    """Cria gráfico de linha do tempo de créditos por ano"""
    
    if not analysis['credits_by_year']:
        st.info("📅 Dados por ano não disponíveis nesta aba")
        return
    
    # Converter para DataFrame
    years = sorted(analysis['credits_by_year'].keys())
    values = [analysis['credits_by_year'][year] for year in years]
    
    df = pd.DataFrame({
        'Ano': years,
        'Créditos Emitidos': values
    })
    
    fig = px.line(df, x='Ano', y='Créditos Emitidos',
                  title='Evolução de Créditos Emitidos por Ano',
                  markers=True)
    
    fig.update_layout(
        yaxis_title='Créditos (tCO₂eq)',
        plot_bgcolor='white',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_top_projects_table(analysis):
    """Cria tabela dos projetos com mais créditos"""
    
    if not analysis['top_projects']:
        return
    
    st.subheader("🏆 Top 10 Projetos por Créditos Emitidos")
    
    # Criar DataFrame
    data = []
    for i, project in enumerate(analysis['top_projects'], 1):
        data.append({
            'Rank': i,
            'Projeto': project['name'],
            'País': project['country'],
            'Emitidos': project['issued'],
            'Aposentados': project['retired'],
            'Disponíveis': project['remaining'],
            'Taxa Apos.': f"{(project['retired']/project['issued']*100):.1f}%" if project['issued'] > 0 else "0%"
        })
    
    df = pd.DataFrame(data)
    
    # Formatar números
    df['Emitidos'] = df['Emitidos'].apply(formatar_milhoes)
    df['Aposentados'] = df['Aposentados'].apply(formatar_milhoes)
    df['Disponíveis'] = df['Disponíveis'].apply(formatar_milhoes)
    
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

def create_country_chart(analysis):
    """Cria gráfico de créditos por país"""
    
    if not analysis['by_country']:
        return
    
    # Converter para DataFrame e pegar top 10
    country_df = pd.DataFrame(list(analysis['by_country'].items()), columns=['País', 'Créditos'])
    country_df = country_df.sort_values('Créditos', ascending=False).head(10)
    
    fig = px.bar(country_df, x='País', y='Créditos',
                 title='Top 10 Países por Créditos Emitidos',
                 color='Créditos',
                 color_continuous_scale='Greens')
    
    fig.update_layout(
        yaxis_title='Créditos (tCO₂eq)',
        xaxis_title='',
        plot_bgcolor='white',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_type_chart(analysis):
    """Cria gráfico de créditos por tipo de projeto"""
    
    if not analysis['by_type']:
        return
    
    type_df = pd.DataFrame(list(analysis['by_type'].items()), columns=['Tipo', 'Créditos'])
    type_df = type_df.sort_values('Créditos', ascending=False)
    
    fig = px.pie(type_df, values='Créditos', names='Tipo',
                 title='Distribuição de Créditos por Tipo de Projeto',
                 hole=0.3)
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    
    st.plotly_chart(fig, use_container_width=True)

def create_status_chart(analysis):
    """Cria gráfico de créditos por status"""
    
    if not analysis['by_status']:
        return
    
    status_df = pd.DataFrame(list(analysis['by_status'].items()), columns=['Status', 'Créditos'])
    
    fig = px.bar(status_df, x='Status', y='Créditos',
                 title='Créditos Emitidos por Status do Projeto',
                 color='Créditos',
                 color_continuous_scale='Blues')
    
    fig.update_layout(
        yaxis_title='Créditos (tCO₂eq)',
        xaxis_title='Status',
        plot_bgcolor='white',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

# =========================
# APLICAÇÃO PRINCIPAL
# =========================

def main():
    st.title("📊 Análise Detalhada de Créditos de Carbono")
    st.markdown("**Foco:** Projetos Agrícolas | **Fonte:** Dataset FAO | **Aba:** 4. Agriculture")
    
    # Carregar dados
    with st.spinner("Carregando dados do dataset FAO..."):
        df, credit_cols, main_cols = load_agriculture_data()
    
    if df is None:
        st.error("Não foi possível carregar os dados. Verifique a conexão ou o arquivo.")
        return
    
    # Analisar dados
    with st.spinner("Analisando créditos de carbono..."):
        analysis = analyze_credits(df, credit_cols, main_cols)
    
    # Seção Hero
    create_hero_section(analysis)
    
    # Métricas principais
    st.markdown("---")
    create_main_metrics(analysis)
    
    # Layout principal
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de comparação
        create_comparison_chart(analysis)
        
        # Top projetos
        create_top_projects_table(analysis)
        
        # Gráfico por tipo
        create_type_chart(analysis)
    
    with col2:
        # Timeline
        create_timeline_chart(analysis)
        
        # Gráfico por país
        create_country_chart(analysis)
        
        # Gráfico por status
        create_status_chart(analysis)
    
    # Definições
    st.markdown("---")
    st.subheader("📚 Definições")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 🌱 Créditos Emitidos
        Total de créditos de carbono gerados por projetos certificados, medidos em toneladas de CO₂ equivalente (tCO₂eq).
        Representa o potencial total de mitigação climática.
        """)
    
    with col2:
        st.markdown("""
        ### 💰 Créditos Aposentados
        Créditos que foram utilizados para compensar emissões ou vendidos no mercado. 
        Indicam demanda real e transações efetivas no mercado de carbono.
        """)
    
    with col3:
        st.markdown("""
        ### 📈 Créditos Disponíveis
        Créditos emitidos que ainda não foram aposentados. 
        Representam o estoque disponível para futuras transações no mercado.
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #7f8c8d; padding: 1rem;'>
        <p>📊 <strong>Análise baseada no dataset FAO de Mercados de Carbono Agrícola</strong></p>
        <p>🌱 Foco exclusivo em projetos agrícolas com créditos emitidos</p>
        <p>📈 Dados extraídos da aba "4. Agriculture" do Dataset.xlsx</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar com informações adicionais
    with st.sidebar:
        st.markdown("## ℹ️ Sobre a Análise")
        st.markdown("""
        Esta análise foca exclusivamente em:
        
        **1. Créditos Emitidos**  
        Total de créditos de carbono gerados
        
        **2. Créditos Aposentados**  
        Créditos que foram utilizados/compensados
        
        **3. Créditos Disponíveis**  
        Créditos ainda no mercado
        
        ---
        
        **Fonte dos dados:**  
        Dataset FAO Agrifood Carbon Markets  
        Aba: 4. Agriculture
        
        **Total de projetos analisados:**  
        {}
        
        **Projetos com créditos emitidos:**  
        {}
        """.format(
            formatar_br_inteiro(analysis['total_projects']),
            formatar_br_inteiro(analysis['projects_with_credits'])
        ))
        
        # Estatísticas rápidas
        st.markdown("---")
        st.markdown("### 📈 Estatísticas Rápidas")
        
        st.metric("Projetos com créditos", 
                 formatar_br_inteiro(analysis['projects_with_credits']))
        
        st.metric("Taxa de aposentadoria", 
                 f"{analysis['retirement_rate']:.2f}%")
        
        # Calcular receita estimada (US$22.5 por crédito)
        receita_estimada = analysis['total_credits_retired'] * 22.5
        st.metric("Receita estimada (vendidos)", 
                 f"US$ {formatar_moeda_curta(receita_estimada)}")

if __name__ == "__main__":
    main()
