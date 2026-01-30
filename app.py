import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import warnings
import re

warnings.filterwarnings("ignore")

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Mercado de Carbono Rural - FAO 2025",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# FUNÇÕES DE FORMATAÇÃO (IDÊNTICAS)
# =========================
def formatar_br(numero):
    if pd.isna(numero): return "0,00"
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_moeda(numero):
    return f"US$ {formatar_br(numero)}"

# =========================
# PROCESSAMENTO DE DADOS (ADAPTADO AOS NOMES DOS CSVs)
# =========================
def clean_dataframe(df):
    # Remove linhas vazias e limpa cabeçalhos
    df = df.dropna(how='all').reset_index(drop=True)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def identify_columns(df):
    cols = df.columns
    mapping = {
        'creditos': None,
        'pais': None,
        'nome': None
    }
    
    # Busca por padrões nos nomes das colunas da FAO
    for c in cols:
        c_lower = c.lower()
        if any(x in c_lower for x in ['issued credits', 'sum of all issued', 'total credits issued']):
            mapping['creditos'] = c
        if any(x in c_lower for x in ['country', 'region']):
            mapping['pais'] = c
        if any(x in c_lower for x in ['project name', 'name of standard']):
            mapping['nome'] = c
    return mapping

# =========================
# INTERFACE PRINCIPAL
# =========================
def main():
    st.title("📊 Dashboard de Carbono Agrícola (Dados Reais FAO)")
    
    # Sidebar para upload idêntico
    st.sidebar.header("Upload de Dados")
    uploaded_files = st.sidebar.file_uploader("Arraste os ficheiros CSV aqui", accept_multiple_files=True, type=['csv'])

    if not uploaded_files:
        st.info("Por favor, carregue os ficheiros CSV (Abas 4 a 9) para visualizar a análise.")
        return

    # Consolidação de dados
    all_data = []
    total_emitido = 0
    total_projetos = 0
    paises_dist = {}

    for file in uploaded_files:
        df = pd.read_csv(file)
        df = clean_dataframe(df)
        mapping = identify_columns(df)
        
        total_projetos += len(df)
        
        if mapping['creditos']:
            # Converte para numérico removendo vírgulas de milhar
            creditos_col = pd.to_numeric(df[mapping['creditos']].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            total_emitido += creditos_col.sum()
        
        if mapping['pais']:
            counts = df[mapping['pais']].value_counts().to_dict()
            for p, v in counts.items():
                paises_dist[p] = paises_dist.get(p, 0) + v

    # =========================
    # LAYOUT DE KPIs (IDÊNTICO)
    # =========================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Projetos", f"{total_projetos:,}")
    with col2:
        st.metric("Créditos Emitidos (tCO2e)", f"{total_emitido:,.0f}".replace(",", "."))
    with col3:
        preco_fao = 22.50
        st.metric("Preço Médio (FAO)", f"US$ {preco_fao:.2/f}")
    with col4:
        receita_potencial = total_emitido * preco_fao
        st.metric("Receita Estimada", f"US$ {receita_potencial/1e6:.1f}M")

    st.markdown("---")

    # =========================
    # GRÁFICOS (IDÊNTICOS)
    # =========================
    g1, g2 = st.columns(2)

    with g1:
        st.subheader("Top Países com Projetos")
        if paises_dist:
            df_paises = pd.DataFrame(list(paises_dist.items()), columns=['País', 'Qtd']).sort_values('Qtd', ascending=False).head(10)
            fig = px.bar(df_paises, x='Qtd', y='País', orientation='h', color='Qtd', color_continuous_scale='Greens')
            st.plotly_chart(fig, use_container_width=True)

    with g2:
        st.subheader("Simulador para o Produtor (Indigo/FAO)")
        area = st.number_input("Área (Hectares)", value=1000)
        taxa = st.slider("Sequestro (tCO2e/ha/ano)", 0.5, 3.0, 1.2)
        repasse = 0.75 # 75% conforme relatório
        
        ganho = (area * taxa) * preco_fao * repasse
        st.info(f"Ganho Líquido Estimado para o Produtor: **{formatar_moeda(ganho)} / ano**")
        st.caption("Cálculo baseado em 75% de repasse líquido (Referência Indigo/Carbon).")

    # Tabela detalhada
    st.markdown("---")
    st.subheader("Explorar Dados Carregados")
    for file in uploaded_files:
        with st.expander(f"Ver dados: {file.name}"):
            st.write(pd.read_csv(file).head(10))

if __name__ == "__main__":
    main()
