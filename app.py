# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io
import warnings
import requests
from io import BytesIO
import zipfile
warnings.filterwarnings('ignore')

# Configuração da página
st.set_page_config(
    page_title="FAO Agrifood Carbon Market Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configurações
GITHUB_USER = "tco2eq_v3"
GITHUB_REPO = "tco2eq_v3"
DATASET_PATH = "Dataset.xlsx"
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{DATASET_PATH}"

# Inicializar session state
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'dataframes' not in st.session_state:
    st.session_state.dataframes = {}
if 'sheets' not in st.session_state:
    st.session_state.sheets = []
if 'selected_sheet' not in st.session_state:
    st.session_state.selected_sheet = None

@st.cache_data(ttl=86400)
def load_data_from_github(url):
    """Carrega dados do GitHub"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        excel_file = pd.ExcelFile(BytesIO(response.content))
        sheets = excel_file.sheet_names
        dataframes = {}
        
        for sheet in sheets:
            df = pd.read_excel(excel_file, sheet_name=sheet)
            dataframes[sheet] = df
        
        return dataframes, sheets
    except Exception as e:
        st.error(f"Erro ao carregar do GitHub: {str(e)}")
        return {}, []

@st.cache_data
def load_excel_from_upload(file):
    """Carrega dados de upload"""
    try:
        excel_file = pd.ExcelFile(file)
        sheets = excel_file.sheet_names
        dataframes = {}
        
        for sheet in sheets:
            df = pd.read_excel(excel_file, sheet_name=sheet)
            dataframes[sheet] = df
        
        return dataframes, sheets
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {str(e)}")
        return {}, []

def show_welcome():
    """Tela de boas-vindas"""
    st.title("🌱 FAO Agrifood Carbon Market Dashboard")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 📋 Sobre o Dataset
        
        **Agrifood Voluntary Carbon Market Dataset** (FAO, 2025)
        
        • **10 abas** temáticas  
        • **1,000+ projetos** de carbono  
        • Dados de **1996-2023**  
        • **Padrões globais** (Verra, Gold Standard, etc.)  
        • **89 metodologias** documentadas  
        • **Plataformas** de MRV
        """)
    
    with col2:
        st.markdown("""
        ### 🎯 Análises Disponíveis
        
        **1. Padrões & Certificações**  
        - Comparação entre padrões  
        - Projetos registrados  
        
        **2. Projetos por Categoria**  
        - Agricultura (758 projetos)  
        - Agroflorestal (170 projetos)  
        - Energia (29 projetos)  
        
        **3. Plataformas Especializadas**  
        - Plan Vivo, Acorn, Social Carbon  
        - Puro.earth (biochar)  
        - Nori, BCarbon
        
        **4. Metodologias**  
        - 89 metodologias documentadas
        """)
    
    st.info("👈 **Selecione a fonte de dados na barra lateral para começar**")

def create_sidebar():
    """Cria a barra lateral"""
    with st.sidebar:
        st.header("⚙️ Configuração")
        
        data_source = st.radio(
            "Fonte de dados:",
            ["GitHub Automático", "Upload Manual"],
            index=0
        )
        
        if data_source == "GitHub Automático":
            st.info(f"Repositório: {GITHUB_USER}/{GITHUB_REPO}")
            
            if st.button("🔄 Carregar Dados do GitHub", type="primary"):
                with st.spinner("Carregando..."):
                    dataframes, sheets = load_data_from_github(GITHUB_RAW_URL)
                    if dataframes:
                        st.session_state.data_loaded = True
                        st.session_state.dataframes = dataframes
                        st.session_state.sheets = sheets
                        st.session_state.selected_sheet = sheets[1] if len(sheets) > 1 else sheets[0]
                        st.success("✅ Dados carregados!")
                        st.rerun()
                    else:
                        st.error("❌ Falha ao carregar dados")
        
        else:
            uploaded_file = st.file_uploader(
                "Faça upload do Dataset.xlsx",
                type=['xlsx', 'xls']
            )
            
            if uploaded_file and st.button("📤 Processar Arquivo", type="primary"):
                with st.spinner("Processando..."):
                    dataframes, sheets = load_excel_from_upload(uploaded_file)
                    if dataframes:
                        st.session_state.data_loaded = True
                        st.session_state.dataframes = dataframes
                        st.session_state.sheets = sheets
                        st.session_state.selected_sheet = sheets[1] if len(sheets) > 1 else sheets[0]
                        st.success("✅ Arquivo processado!")
                        st.rerun()
        
        if st.session_state.data_loaded:
            st.markdown("---")
            st.header("📂 Navegação")
            
            # Seletor de aba
            selected = st.selectbox(
                "Selecione a aba:",
                st.session_state.sheets,
                index=st.session_state.sheets.index(st.session_state.selected_sheet) 
                if st.session_state.selected_sheet in st.session_state.sheets else 0
            )
            
            if selected != st.session_state.selected_sheet:
                st.session_state.selected_sheet = selected
                st.rerun()
            
            st.markdown("---")
            st.header("🚀 Ações Rápidas")
            
            if st.button("📊 Resumo Geral"):
                st.session_state.show_summary = True
                st.rerun()
            
            if st.button("🔄 Limpar Cache"):
                st.cache_data.clear()
                st.success("Cache limpo!")
                st.rerun()

def show_data_analysis():
    """Mostra análise dos dados"""
    if not st.session_state.data_loaded:
        show_welcome()
        return
    
    dataframes = st.session_state.dataframes
    sheets = st.session_state.sheets
    selected_sheet = st.session_state.selected_sheet
    
    if selected_sheet not in dataframes:
        st.error("Aba selecionada não encontrada")
        return
    
    df = dataframes[selected_sheet]
    
    # Título
    st.title(f"📄 {selected_sheet}")
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Registros", df.shape[0])
    with col2:
        st.metric("Colunas", df.shape[1])
    with col3:
        numeric_cols = len(df.select_dtypes(include=[np.number]).columns)
        st.metric("Colunas Numéricas", numeric_cols)
    with col4:
        null_percentage = (df.isnull().sum().sum() / (df.shape[0] * df.shape[1]) * 100)
        st.metric("Dados Preenchidos", f"{100 - null_percentage:.1f}%")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Dados", "🔍 Análise", "📈 Visualizações", "💾 Exportar"])
    
    with tab1:
        st.subheader("Visualização dos Dados")
        
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            columns_to_show = st.multiselect(
                "Colunas:",
                df.columns.tolist(),
                default=df.columns.tolist()[:min(8, len(df.columns))]
            )
        with col2:
            rows_to_show = st.slider("Linhas:", 10, min(200, df.shape[0]), 50)
        
        # Tabela
        if columns_to_show:
            display_df = df[columns_to_show].head(rows_to_show)
        else:
            display_df = df.head(rows_to_show)
        
        st.dataframe(display_df, use_container_width=True, height=400)
    
    with tab2:
        st.subheader("Análise Detalhada")
        
        # Valores ausentes
        st.write("### 🔍 Valores Ausentes")
        missing_df = pd.DataFrame({
            'Coluna': df.columns,
            'Ausentes': df.isnull().sum(),
            '%': (df.isnull().sum() / len(df) * 100).round(2)
        }).sort_values('%', ascending=False)
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.dataframe(missing_df[missing_df['Ausentes'] > 0], use_container_width=True)
        
        with col2:
            if len(missing_df[missing_df['Ausentes'] > 0]) > 0:
                fig = px.bar(
                    missing_df.head(15),
                    x='Coluna',
                    y='%',
                    title='Colunas com Valores Ausentes',
                    color='%',
                    color_continuous_scale='Reds'
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        
        # Estatísticas
        st.write("### 📊 Estatísticas")
        numeric_df = df.select_dtypes(include=[np.number])
        if not numeric_df.empty:
            st.dataframe(numeric_df.describe(), use_container_width=True)
    
    with tab3:
        st.subheader("Visualizações")
        
        # Gráficos
        chart_type = st.selectbox("Tipo:", ["Histograma", "Barras", "Dispersão"])
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        
        if chart_type == "Histograma" and numeric_cols:
            col_selected = st.selectbox("Coluna numérica:", numeric_cols)
            if col_selected:
                fig = px.histogram(df, x=col_selected, nbins=30, 
                                 title=f"Distribuição de {col_selected}")
                st.plotly_chart(fig, use_container_width=True)
        
        elif chart_type == "Barras" and categorical_cols:
            col_selected = st.selectbox("Coluna categórica:", categorical_cols)
            if col_selected:
                top_n = st.slider("Top N:", 5, 20, 10)
                counts = df[col_selected].value_counts().head(top_n)
                fig = px.bar(x=counts.index, y=counts.values,
                           title=f"Top {top_n} {col_selected}")
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        
        elif chart_type == "Dispersão" and len(numeric_cols) >= 2:
            col_x = st.selectbox("Eixo X:", numeric_cols)
            col_y = st.selectbox("Eixo Y:", numeric_cols)
            if col_x and col_y:
                fig = px.scatter(df, x=col_x, y=col_y, trendline="ols",
                               title=f"{col_y} vs {col_x}")
                st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("Exportação")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV da aba atual
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 CSV desta aba",
                data=csv,
                file_name=f"{selected_sheet.replace(' ', '_')}.csv",
                mime="text/csv"
            )
        
        with col2:
            # Todas as abas em ZIP
            if st.button("📚 Todas as abas (ZIP)"):
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zf:
                    for sheet_name, sheet_df in dataframes.items():
                        csv_data = sheet_df.to_csv(index=False)
                        zf.writestr(f"{sheet_name.replace(' ', '_')}.csv", csv_data)
                
                zip_buffer.seek(0)
                st.download_button(
                    label="⬇️ Download ZIP",
                    data=zip_buffer,
                    file_name="dataset_completo.zip",
                    mime="application/zip"
                )
    
    # Resumo geral (se solicitado)
    if st.session_state.get('show_summary', False):
        st.markdown("---")
        st.subheader("📊 Resumo do Dataset")
        
        summary_data = []
        for sheet in sheets:
            sheet_df = dataframes[sheet]
            summary_data.append({
                'Aba': sheet,
                'Registros': sheet_df.shape[0],
                'Colunas': sheet_df.shape[1],
                '% Preenchido': round(100 - (sheet_df.isnull().sum().sum() / (sheet_df.shape[0] * sheet_df.shape[1]) * 100), 1)
            })
        
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True)
        
        # Limpar flag
        st.session_state.show_summary = False

def main():
    """Função principal"""
    create_sidebar()
    
    if not st.session_state.data_loaded:
        show_welcome()
    else:
        show_data_analysis()
    
    # Footer
    st.markdown("---")
    st.caption(f"""
    📊 **FAO Agrifood Carbon Market Dashboard** • 
    Dados: [{GITHUB_USER}/{GITHUB_REPO}](https://github.com/{GITHUB_USER}/{GITHUB_REPO}) • 
    {datetime.now().strftime('%d/%m/%Y %H:%M')}
    """)

if __name__ == "__main__":
    main()
