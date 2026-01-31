import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import warnings
import re
import requests
from io import BytesIO
import base64

warnings.filterwarnings("ignore")

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Mercado de Carbono Agrícola - Análise de Projetos",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# FUNÇÕES DE FORMATAÇÃO
# =========================

def formatar_milhoes(numero):
    """Formata números grandes como milhões: 367,2 milhões"""
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
    """Formata números no padrão brasileiro: 1.234,56"""
    if pd.isna(numero):
        return "N/A"
    
    numero = round(numero, 2)
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_br_dec(numero, decimais=2):
    """Formata números no padrão brasileiro com número específico de casas decimais"""
    if pd.isna(numero):
        return "N/A"
    
    numero = round(numero, decimais)
    return f"{numero:,.{decimais}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_br_inteiro(numero):
    """Formata números inteiros no padrão brasileiro: 1.234"""
    if pd.isna(numero):
        return "N/A"
    
    numero = int(round(numero, 0))
    return f"{numero:,}".replace(",", "X").replace(".", ",").replace("X", ".")

# =========================
# CARGA DE DADOS - MÚLTIPLAS OPÇÕES
# =========================

@st.cache_data(show_spinner=False)
def load_dataset_from_github(github_url):
    """Carrega o dataset datasetAgriculture.xlsx do GitHub"""
    try:
        response = requests.get(github_url)
        response.raise_for_status()
        
        excel_data = BytesIO(response.content)
        df = pd.read_excel(excel_data, engine='openpyxl')
        
        return df, f"✅ Dataset carregado do GitHub ({len(df)} registros)"
        
    except requests.exceptions.RequestException as e:
        return None, f"❌ Erro ao baixar do GitHub: {e}"
    except Exception as e:
        return None, f"❌ Erro ao processar o dataset: {e}"

def identify_columns(df):
    """Identifica automaticamente as colunas importantes no dataset"""
    col_map = {}
    colunas = [str(col).strip() for col in df.columns]
    
    # Padrões de busca para cada tipo de coluna
    padroes = {
        'creditos_emitidos': ['total credits issued', 'credits issued', 'total issued'],
        'creditos_aposentados': ['total credits retired', 'credits retired', 'total retired'],
        'creditos_restantes': ['total credits remaining', 'credits remaining', 'remaining'],
        'status': ['voluntary status', 'status', 'project status'],
        'nome': ['project name', 'name', 'project', 'nome do projeto'],
        'pais': ['country', 'country name', 'pais', 'location'],
        'tipo': ['type', 'project type', 'tipo', 'category'],
        'registro': ['voluntary registry', 'registry', 'registro'],
        'id': ['project id', 'id', 'project code']
    }
    
    # Procurar por cada padrão
    for chave, padroes_list in padroes.items():
        for padrao in padroes_list:
            for col in colunas:
                if padrao.lower() in col.lower():
                    # Encontre o nome original da coluna
                    col_original = df.columns[[str(c).strip().lower() for c in df.columns].index(col.lower())]
                    col_map[chave] = col_original
                    break
            if chave in col_map:
                break
    
    return col_map

@st.cache_data(show_spinner=False)
def analyze_valid_projects(df):
    """Analisa projetos válidos que emitiram créditos de carbono"""
    
    analysis = {
        'estatisticas_gerais': {},
        'projetos_por_pais': {},
        'projetos_por_tipo': {},
        'projetos_por_registro': {},
        'projetos_por_status': {},
        'projetos_validos': [],
        'timeline_emissao': {},
        'timeline_aposentadoria': {},
        'comparativo': {
            'total_emitido': 0,
            'total_aposentado': 0,
            'taxa_aposentadoria': 0,
            'creditos_disponiveis': 0
        },
        'projetos_detalhados': [],
        'colunas_identificadas': {}
    }
    
    if df is None or df.empty:
        return analysis
    
    # Identificar colunas
    col_map = identify_columns(df)
    analysis['colunas_identificadas'] = col_map
    
    # Verificar se temos a coluna essencial de créditos emitidos
    if 'creditos_emitidos' not in col_map:
        return analysis
    
    # Filtrar projetos com créditos emitidos > 0
    col_creditos = col_map['creditos_emitidos']
    
    # Converter para numérico
    df[col_creditos] = pd.to_numeric(df[col_creditos], errors='coerce')
    df_valid = df[df[col_creditos] > 0].copy()
    
    if df_valid.empty:
        return analysis
    
    # Coletar estatísticas básicas
    total_emitido = df_valid[col_creditos].sum()
    
    # Créditos aposentados
    total_aposentado = 0
    if 'creditos_aposentados' in col_map:
        col_aposentados = col_map['creditos_aposentados']
        df_valid[col_aposentados] = pd.to_numeric(df_valid[col_aposentados], errors='coerce')
        total_aposentado = df_valid[col_aposentados].sum()
    
    # Créditos restantes
    total_restantes = 0
    if 'creditos_restantes' in col_map:
        col_restantes = col_map['creditos_restantes']
        df_valid[col_restantes] = pd.to_numeric(df_valid[col_restantes], errors='coerce')
        total_restantes = df_valid[col_restantes].sum()
    else:
        total_restantes = total_emitido - total_aposentado
    
    # Taxa de aposentadoria
    taxa_aposentadoria = (total_aposentado / total_emitido * 100) if total_emitido > 0 else 0
    
    # Coletar dados por categoria
    if 'pais' in col_map:
        for pais, count in df_valid[col_map['pais']].value_counts().items():
            if pd.notna(pais):
                analysis['projetos_por_pais'][str(pais)] = int(count)
    
    if 'tipo' in col_map:
        for tipo, count in df_valid[col_map['tipo']].value_counts().items():
            if pd.notna(tipo):
                analysis['projetos_por_tipo'][str(tipo)] = int(count)
    
    if 'registro' in col_map:
        for registro, count in df_valid[col_map['registro']].value_counts().items():
            if pd.notna(registro):
                analysis['projetos_por_registro'][str(registro)] = int(count)
    
    if 'status' in col_map:
        for status, count in df_valid[col_map['status']].value_counts().items():
            if pd.notna(status):
                analysis['projetos_por_status'][str(status)] = int(count)
    
    # Projetos detalhados
    for idx, row in df_valid.head(1000).iterrows():  # Limitar a 1000 para performance
        projeto = {}
        
        for chave, coluna in col_map.items():
            if coluna in row:
                valor = row[coluna]
                if pd.isna(valor):
                    projeto[chave] = None
                else:
                    projeto[chave] = valor
        
        # Calcular taxa de aposentadoria do projeto
        if (projeto.get('creditos_emitidos') and 
            projeto.get('creditos_aposentados') and 
            projeto['creditos_emitidos'] > 0):
            projeto['taxa_aposentadoria_projeto'] = (
                projeto['creditos_aposentados'] / projeto['creditos_emitidos'] * 100
            )
        
        analysis['projetos_detalhados'].append(projeto)
    
    # Analisar colunas anuais (1996-2023)
    anos_emissao = {}
    anos_aposentadoria = {}
    
    for col in df_valid.columns:
        col_str = str(col).strip()
        
        # Procurar colunas de ano
        if col_str.isdigit() and 1996 <= int(col_str) <= 2023:
            try:
                # Converter para numérico
                dados_ano = pd.to_numeric(df_valid[col], errors='coerce')
                total_ano = dados_ano.sum()
                
                if pd.notna(total_ano) and total_ano > 0:
                    # Tentar identificar se é emissão ou aposentadoria baseado na posição
                    # (Simplificação - na prática precisa verificar o contexto)
                    if len(anos_emissao) < 14:  # Primeiros anos são emissão
                        anos_emissao[int(col_str)] = float(total_ano)
                    else:
                        anos_aposentadoria[int(col_str)] = float(total_ano)
            except:
                pass
    
    analysis['timeline_emissao'] = dict(sorted(anos_emissao.items()))
    analysis['timeline_aposentadoria'] = dict(sorted(anos_aposentadoria.items()))
    
    # Estatísticas gerais
    analysis['estatisticas_gerais'] = {
        'total_projetos_validos': len(df_valid),
        'total_creditos_emitidos': total_emitido,
        'total_creditos_aposentados': total_aposentado,
        'total_creditos_restantes': total_restantes,
        'taxa_aposentadoria_geral': taxa_aposentadoria,
        'media_creditos_por_projeto': total_emitido / len(df_valid) if len(df_valid) > 0 else 0,
        'paises_com_projetos': len(analysis['projetos_por_pais']),
        'tipos_de_projeto': len(analysis['projetos_por_tipo']),
        'registros_utilizados': len(analysis['projetos_por_registro'])
    }
    
    analysis['comparativo'] = {
        'total_emitido': total_emitido,
        'total_aposentado': total_aposentado,
        'taxa_aposentadoria': taxa_aposentadoria,
        'creditos_disponiveis': total_restantes
    }
    
    return analysis

# =========================
# COMPONENTES DE VISUALIZAÇÃO
# =========================

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
            formatar_milhoes(stats.get('total_creditos_emitidos', 0))
        )
    
    with col3:
        st.metric(
            "💰 Créditos Aposentados",
            formatar_milhoes(stats.get('total_creditos_aposentados', 0)),
            f"{formatar_br_dec(stats.get('taxa_aposentadoria_geral', 0), 1)}%"
        )
    
    with col4:
        st.metric(
            "💎 Créditos Disponíveis",
            formatar_milhoes(stats.get('total_creditos_restantes', 0))
        )

def create_comparison_chart(analysis):
    """Cria gráfico comparando créditos emitidos vs aposentados"""
    comparativo = analysis.get('comparativo', {})
    
    if not comparativo or comparativo.get('total_emitido', 0) == 0:
        return
    
    dados = pd.DataFrame({
        'Categoria': ['Emitidos', 'Aposentados', 'Disponíveis'],
        'Valor (tCO₂eq)': [
            comparativo.get('total_emitido', 0),
            comparativo.get('total_aposentado', 0),
            comparativo.get('creditos_disponiveis', 0)
        ]
    })
    
    fig = px.bar(
        dados,
        x='Categoria',
        y='Valor (tCO₂eq)',
        color='Categoria',
        color_discrete_map={
            'Emitidos': '#2ecc71',
            'Aposentados': '#3498db',
            'Disponíveis': '#f39c12'
        },
        title='Comparação de Créditos'
    )
    
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

def create_country_chart(analysis):
    """Cria gráfico de projetos por país"""
    paises = analysis.get('projetos_por_pais', {})
    
    if not paises:
        return
    
    df_paises = pd.DataFrame(
        list(paises.items()),
        columns=['País', 'Número de Projetos']
    ).sort_values('Número de Projetos', ascending=False).head(10)
    
    fig = px.bar(
        df_paises,
        x='País',
        y='Número de Projetos',
        title='Top 10 Países com Mais Projetos',
        color='Número de Projetos',
        color_continuous_scale='Viridis'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_timeline_chart(analysis):
    """Cria gráfico de timeline"""
    emissao = analysis.get('timeline_emissao', {})
    aposentadoria = analysis.get('timeline_aposentadoria', {})
    
    if not emissao and not aposentadoria:
        return
    
    # Preparar dados
    dados = []
    anos = sorted(set(list(emissao.keys()) + list(aposentadoria.keys())))
    
    for ano in anos:
        dados.append({
            'Ano': ano,
            'Emissões': emissao.get(ano, 0),
            'Aposentadorias': aposentadoria.get(ano, 0)
        })
    
    df_timeline = pd.DataFrame(dados)
    
    if df_timeline.empty:
        return
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_timeline['Ano'],
        y=df_timeline['Emissões'],
        mode='lines+markers',
        name='Créditos Emitidos',
        line=dict(color='#2ecc71', width=3)
    ))
    
    fig.add_trace(go.Scatter(
        x=df_timeline['Ano'],
        y=df_timeline['Aposentadorias'],
        mode='lines+markers',
        name='Créditos Aposentados',
        line=dict(color='#3498db', width=3)
    ))
    
    fig.update_layout(
        title='Timeline de Créditos',
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
    
    st.markdown("### 📋 Detalhes dos Projetos (Primeiros 50)")
    
    # Converter para DataFrame
    df_projetos = pd.DataFrame(projetos)
    
    # Selecionar colunas relevantes
    colunas_interesse = ['id', 'nome', 'pais', 'tipo', 'registro', 'status', 
                        'creditos_emitidos', 'creditos_aposentados']
    
    colunas_disponiveis = [col for col in colunas_interesse if col in df_projetos.columns]
    
    if not colunas_disponiveis:
        return
    
    df_display = df_projetos[colunas_disponiveis].head(50).copy()
    
    # Formatar números
    for col in ['creditos_emitidos', 'creditos_aposentados']:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(
                lambda x: formatar_br_inteiro(x) if pd.notna(x) else 'N/A'
            )
    
    st.dataframe(df_display, use_container_width=True, height=300)
    
    # Botão para baixar
    if st.button("📥 Baixar todos os projetos (CSV)"):
        csv = pd.DataFrame(projetos).to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="projetos_carbono.csv">Clique para baixar</a>'
        st.markdown(href, unsafe_allow_html=True)

# =========================
# PÁGINA PRINCIPAL
# =========================

def main():
    st.title("🌱 Dashboard de Análise de Projetos de Carbono Agrícola")
    st.markdown("### Baseado em dados reais de projetos certificados")
    
    # Sidebar para carregamento de dados
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 1rem;'>
            <h3 style='color: #27ae60;'>📁 Carregar Dados</h3>
        </div>
        """, unsafe_allow_html=True)
        
        opcao = st.radio(
            "Escolha a fonte dos dados:",
            ["📤 Upload de arquivo", "🔗 URL do GitHub", "🧪 Dados de exemplo"]
        )
        
        df = None
        mensagem = ""
        
        if opcao == "📤 Upload de arquivo":
            arquivo = st.file_uploader(
                "Faça upload do arquivo Excel (datasetAgriculture.xlsx)",
                type=['xlsx', 'xls']
            )
            
            if arquivo is not None:
                try:
                    df = pd.read_excel(arquivo, engine='openpyxl')
                    mensagem = f"✅ Arquivo carregado ({len(df)} registros)"
                except Exception as e:
                    mensagem = f"❌ Erro ao ler o arquivo: {e}"
        
        elif opcao == "🔗 URL do GitHub":
            github_url = st.text_input(
                "Cole a URL do arquivo no GitHub (raw link):",
                value=""
            )
            
            if github_url:
                if "raw.githubusercontent.com" in github_url:
                    with st.spinner("Carregando do GitHub..."):
                        df, mensagem = load_dataset_from_github(github_url)
                else:
                    mensagem = "❌ URL inválida. Use um link 'raw' do GitHub."
        
        else:  # Dados de exemplo
            if st.button("Carregar dados de exemplo"):
                # Criar dados de exemplo para demonstração
                st.info("⚠️ Carregando dados de exemplo para demonstração")
                
                # Criar um DataFrame de exemplo
                dados_exemplo = {
                    'Project ID': ['ACR103', 'CAR1459', 'GS11222', 'VCS2072'],
                    'Project Name': ['Projeto A', 'Projeto B', 'Projeto C', 'Projeto D'],
                    'Voluntary Registry': ['ACR', 'CAR', 'GOLD', 'VCS'],
                    'Voluntary Status': ['Completed', 'Registered', 'Completed', 'Registered'],
                    'Country': ['United States', 'United States', 'China', 'United Kingdom'],
                    'Type': ['Agriculture', 'Agriculture', 'Agriculture', 'Agriculture'],
                    'Total Credits Issued': [44202, 111645, 709594, 3303],
                    'Total Credits Retired': [44202, 83585, 118452, 109],
                    'Total Credits Remaining': [0, 28060, 591142, 3194],
                    'First Year of Project': [2003, 2018, 2020, 2019]
                }
                
                df = pd.DataFrame(dados_exemplo)
                mensagem = "✅ Dados de exemplo carregados"
        
        st.markdown("---")
        
        if df is not None:
            # Analisar dados
            with st.spinner("Analisando projetos..."):
                analysis = analyze_valid_projects(df)
                st.session_state.df = df
                st.session_state.analysis = analysis
                st.session_state.mensagem = mensagem
            
            # Mostrar informações básicas
            st.markdown("### 📊 Informações do Dataset")
            st.write(f"**Registros:** {len(df)}")
            st.write(f"**Colunas:** {len(df.columns)}")
            
            if analysis['colunas_identificadas']:
                st.write("**Colunas identificadas:**")
                for chave, coluna in analysis['colunas_identificadas'].items():
                    st.write(f"  - {chave}: `{coluna}`")
    
    # Conteúdo principal
    if 'analysis' not in st.session_state:
        st.info("👈 **Carregue seus dados na barra lateral para começar a análise**")
        st.markdown("""
        ### 📌 Como usar este dashboard:
        
        1. **Carregue seus dados** usando uma das opções na barra lateral
        2. **Visualize as estatísticas** de projetos válidos
        3. **Analise créditos emitidos vs aposentados**
        4. **Explore a distribuição** por país e tipo de projeto
        
        ### 📁 Formatos suportados:
        - Arquivo Excel (.xlsx, .xls) - preferencialmente `datasetAgriculture.xlsx`
        - URL do GitHub (link raw)
        - Dados de exemplo para teste
        """)
        return
    
    # Mostrar mensagem de carregamento
    if 'mensagem' in st.session_state:
        if "✅" in st.session_state.mensagem:
            st.success(st.session_state.mensagem)
        else:
            st.warning(st.session_state.mensagem)
    
    analysis = st.session_state.analysis
    
    # Cartões de resumo
    create_summary_cards(analysis)
    
    st.markdown("---")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        create_comparison_chart(analysis)
    
    with col2:
        create_country_chart(analysis)
    
    # Timeline
    st.markdown("### 📅 Evolução Temporal")
    create_timeline_chart(analysis)
    
    # Tabela de projetos
    create_projects_table(analysis)
    
    # Informações técnicas
    with st.expander("🔍 Informações Técnicas"):
        st.markdown("""
        ### Sobre a Análise
        
        **Projetos considerados válidos:**
        - Projetos que emitiram créditos de carbono (`Total Credits Issued` > 0)
        
        **Métricas calculadas:**
        1. **Créditos Emitidos:** Total de tCO₂eq gerados
        2. **Créditos Aposentados:** Créditos vendidos/retirados do mercado
        3. **Créditos Disponíveis:** Emitidos - Aposentados
        4. **Taxa de Aposentadoria:** % de créditos já vendidos
        
        **Limitações:**
        - A análise depende da identificação automática das colunas
        - Algumas colunas podem ter nomes diferentes no seu arquivo
        - Dados históricos podem estar incompletos
        """)
        
        # Mostrar estatísticas detalhadas
        if analysis['estatisticas_gerais']:
            st.markdown("### 📈 Estatísticas Detalhadas")
            for chave, valor in analysis['estatisticas_gerais'].items():
                if isinstance(valor, (int, float)):
                    if valor >= 1000:
                        valor_fmt = formatar_milhoes(valor)
                    else:
                        valor_fmt = formatar_br_dec(valor, 2)
                    st.write(f"**{chave.replace('_', ' ').title()}:** {valor_fmt}")
                else:
                    st.write(f"**{chave.replace('_', ' ').title()}:** {valor}")

if __name__ == "__main__":
    main()
