import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# =================================================================
# CONFIGURAÇÃO DA PÁGINA (ESTILO ORIGINAL)
# =================================================================
st.set_page_config(
    page_title="Dashboard Mercado de Carbono - FAO/GitHub",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =================================================================
# FUNÇÕES DE FORMATAÇÃO (ESTILO ORIGINAL)
# =================================================================
def formatar_br(numero):
    if pd.isna(numero): return "0,00"
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_moeda(numero):
    return f"US$ {formatar_br(numero)}"

# =================================================================
# CARREGAMENTO DE DADOS (DIRETO DO GITHUB/EXCEL)
# =================================================================
@st.cache_data
def carregar_dados_github(url):
    # Lendo todas as abas conforme a estrutura do arquivo FAO
    dict_abas = pd.read_excel(url, sheet_name=None)
    return dict_abas

# URL do seu repositório (substitua pelo link 'raw' do seu arquivo .xlsx)
URL_EXCEL = "https://github.com/SEU_USUARIO/SEU_REPOSITORIO/raw/main/Dataset.xlsx"

# =================================================================
# INTERFACE PRINCIPAL (IDÊNTICA AO SEU MODELO)
# =================================================================
def main():
    st.title("📊 Dashboard de Carbono Agrícola - Dados FAO 2025")
    
    try:
        # Carregando os dados
        abas = carregar_dados_github(URL_EXCEL)
        
        # Consolidação de métricas globais (Exemplo usando abas 4, 7, 8 e 9)
        total_emitido = 0
        total_projetos = 0
        
        # Soma de créditos de abas específicas (exemplo Nori e Puro)
        if '9. Nori and BCarbon' in abas:
            df9 = abas['9. Nori and BCarbon']
            total_emitido += df9['Issued credits'].sum()
            total_projetos += len(df9)
            
        if '8. Puro.earth' in abas:
            df8 = abas['8. Puro.earth']
            total_emitido += df8['Sum of all issued credits'].sum()
            total_projetos += len(df8)

        # =========================
        # KPIs DE TOPO
        # =========================
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total de Projetos", f"{total_projetos}")
        with col2:
            st.metric("Créditos Emitidos", f"{total_emitido:,.0f}".replace(",", "."))
        with col3:
            preco_referencia = 22.50 # Média FAO para agrifood
            st.metric("Preço Médio", f"US$ {preco_referencia}")
        with col4:
            faturamento = total_emitido * preco_referencia
            st.metric("Potencial de Mercado", f"US$ {faturamento/1e6:.1f}M")

        st.markdown("---")

        # =========================
        # GRÁFICOS E SIMULADOR
        # =========================
        g1, g2 = st.columns(2)

        with g1:
            st.subheader("Simulador de Ganho (Produtor)")
            area = st.number_input("Tamanho da Área (Hectares)", value=1000)
            taxa_seq = st.slider("Sequestro (tCO2e/ha/ano)", 0.5, 3.0, 1.2)
            repasse_indigo = 0.75 # 75% de repasse líquido
            
            ganho_anual = (area * taxa_seq) * preco_referencia * repasse_indigo
            st.success(f"Estimativa de Ganho Líquido: {formatar_moeda(ganho_anual)} / ano")
            st.caption("Baseado em modelos reais de mercado (75% de repasse ao produtor).")

        with g2:
            st.subheader("Distribuição por País")
            # Exemplo rápido com a aba Nori (ajustar conforme necessidade)
            if '9. Nori and BCarbon' in abas:
                df_p = abas['9. Nori and BCarbon']['Country'].value_counts().reset_index()
                fig = px.pie(df_p, values='count', names='Country', hole=0.4, 
                             color_discrete_sequence=px.colors.qualitative.Prism)
                st.plotly_chart(fig, use_container_width=True)

        # =========================
        # TABELA DE DADOS
        # =========================
        st.markdown("---")
        st.subheader("Explorar Detalhes do Dataset")
        aba_escolhida = st.selectbox("Escolha a Aba para Visualizar", list(abas.keys()))
        st.dataframe(abas[aba_escolhida], use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao conectar com o GitHub: {e}")
        st.info("Verifique se o link do Excel no código está correto e no formato 'raw'.")

if __name__ == "__main__":
    main()
