import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
import warnings

warnings.filterwarnings("ignore")

# =================================================================
# CONFIGURAÇÃO DA PÁGINA
# =================================================================
st.set_page_config(
    page_title="Dashboard FAO - Mercado de Carbono Agrícola",
    page_icon="🌱",
    layout="wide"
)

# =================================================================
# FUNÇÕES DE FORMATAÇÃO E LIMPEZA
# =================================================================

def formatar_br(valor):
    if pd.isna(valor) or valor == 0: return "0,00"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_moeda(valor):
    return f"US$ {formatar_br(valor)}"

def clean_column_names(df):
    """Limpa os nomes das colunas removendo espaços e caracteres especiais."""
    df.columns = [str(c).strip().replace("\n", " ") for c in df.columns]
    return df

# =================================================================
# LÓGICA DE PROCESSAMENTO DE DADOS (BASEADA NOS FICHEIROS FAO)
# =================================================================

def process_fao_data(uploaded_files):
    """Processa os ficheiros carregados e consolida as métricas."""
    dataframes = {}
    stats = {
        'total_projetos': 0,
        'total_emitido': 0,
        'total_aposentado': 0,
        'projetos_por_aba': {},
        'paises': {}
    }
    
    # Mapeamento de colunas cruciais encontradas no relatório txt
    col_emitidos = ['Issued carbon credits', 'Issued credits', 'Total Credits Issued', 'Sum of all issued credits']
    col_aposentados = ['Total Credits Retired', 'Credits retired', 'Total credits retired']
    col_pais = ['Country', 'Region']

    for file in uploaded_files:
        df = pd.read_csv(file)
        df = clean_column_names(df)
        aba_nome = file.name.split('-')[-1].replace('.csv', '').strip()
        
        # Identificar colunas de dados
        c_emit = next((c for c in df.columns if any(x in c for x in col_emitidos)), None)
        c_ret = next((c for c in df.columns if any(x in c for x in col_aposentados)), None)
        c_pais = next((c for c in df.columns if any(x in c for x in col_pais)), None)
        
        # Converter para numérico
        if c_emit: df[c_emit] = pd.to_numeric(df[c_emit], errors='coerce').fillna(0)
        if c_ret: df[c_ret] = pd.to_numeric(df[c_ret], errors='coerce').fillna(0)
        
        # Acumular estatísticas
        stats['total_projetos'] += len(df)
        if c_emit: stats['total_emitido'] += df[c_emit].sum()
        if c_ret: stats['total_aposentado'] += df[c_ret].sum()
        stats['projetos_por_aba'][aba_nome] = len(df)
        
        if c_pais:
            counts = df[c_pais].value_counts().to_dict()
            for p, v in counts.items():
                stats['paises'][p] = stats['paises'].get(p, 0) + v
        
        dataframes[aba_nome] = df

    return dataframes, stats

# =================================================================
# INTERFACE PRINCIPAL
# =================================================================

def main():
    st.sidebar.image("https://www.fao.org/images/corporatelibraries/fao-logo/fao-logo-en.svg?sfvrsn=4b2b1b1_2", width=150)
    st.sidebar.title("Configurações")
    
    uploaded_files = st.sidebar.file_uploader(
        "Carregue os CSVs do Dataset (Abas 4 a 9)", 
        accept_multiple_files=True, 
        type=['csv']
    )

    st.title("🌱 Dashboard de Mercado de Carbono Agrícola")
    st.markdown("---")

    if not uploaded_files:
        st.warning("Aguardando o carregamento dos ficheiros CSV para iniciar a análise...")
        # Exibe placeholders de exemplo
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Projetos", "0")
        col2.metric("Créditos Emitidos", "0")
        return

    data, stats = process_fao_data(uploaded_files)

    # 1. KPIs PRINCIPAIS
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de Projetos", f"{stats['total_projetos']:,}")
    with col2:
        st.metric("Créditos Emitidos", formatar_br(stats['total_emitido']))
    with col3:
        st.metric("Créditos Aposentados", formatar_br(stats['total_aposentado']))
    with col4:
        taxa = (stats['total_aposentado'] / stats['total_emitido'] * 100) if stats['total_emitido'] > 0 else 0
        st.metric("Liquidez (Taxa de Retiro)", f"{taxa:.2f}%")

    st.markdown("---")

    # 2. ANÁLISE GRÁFICA
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Distribuição por Categoria (Aba)")
        df_abas = pd.DataFrame(list(stats['projetos_por_aba'].items()), columns=['Categoria', 'Quantidade'])
        fig_pie = px.pie(df_abas, values='Quantidade', names='Categoria', hole=0.4,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.subheader("Top 10 Países por Projetos")
        df_paises = pd.DataFrame(list(stats['paises'].items()), columns=['País', 'Projetos']).sort_values('Projetos', ascending=False).head(10)
        fig_bar = px.bar(df_paises, x='Projetos', y='País', orientation='h',
                         color='Projetos', color_continuous_scale='Greens')
        st.plotly_chart(fig_bar, use_container_width=True)

    # 3. CALCULADORA DE VIABILIDADE (COM DADOS INDIGO/FAO)
    st.markdown("---")
    st.subheader("🧮 Simulador de Receita para o Produtor")
    
    with st.expander("Calcular potencial de ganho baseado em dados reais", expanded=True):
        col_s1, col_s2, col_s3 = st.columns(3)
        
        with col_s1:
            area = st.number_input("Área da Propriedade (Hectares)", min_value=1, value=500)
            preco_carbono = st.number_input("Preço do Crédito (US$/tCO2e)", value=22.50)
            
        with col_s2:
            taxa_seq = st.slider("Taxa de Sequestro (tCO2e/ha/ano)", 0.1, 5.0, 1.2)
            repasse = st.slider("Repasse ao Produtor (%)", 50, 90, 75)
            
        with col_s3:
            total_t = area * taxa_seq
            receita_bruta = total_t * preco_carbono
            receita_liquida = receita_bruta * (repasse / 100)
            
            st.metric("Receita Estimada Anual (Líquida)", formatar_moeda(receita_liquida))
            st.caption(f"Total de {total_t:,.0f} créditos gerados por ano.")

    # 4. EXPLORADOR DE DADOS
    st.markdown("---")
    st.subheader("🔍 Explorador de Dados Brutos")
    aba_selecionada = st.selectbox("Selecione uma aba para visualizar:", list(data.keys()))
    if aba_selecionada:
        st.dataframe(data[aba_selecionada], use_container_width=True)

if __name__ == "__main__":
    main()
