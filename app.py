import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import warnings
import os
import re

warnings.filterwarnings("ignore")

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="FAO Agrifood Carbon Market",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# CONSTANTES E CONFIGURAÇÕES
# =========================
SHEET_CONFIG = {
    "README": {"description": "Documentação e metadados do dataset"},
    "1. Standards": {"description": "Padrões e registros de carbono", "main_column": "Name of standard/registry/platform"},
    "2. Platforms": {"description": "Plataformas de mercado de carbono", "main_column": "Platform"},
    "3. Methodologies": {"description": "Metodologias de cálculo de carbono", "main_column": "Data sourced from methodology document (see reference in column AD)"},
    "4. Agriculture": {"description": "Projetos agrícolas", "has_yearly_data": True, "credit_column_pattern": "Credits issued by vintage"},
    "5. Agroforestry-AR & Grassland": {"description": "Projetos agroflorestais e pastagens", "has_yearly_data": True},
    "6. Energy and Other": {"description": "Projetos de energia e outros", "has_yearly_data": True},
    "7. Plan Vivo, Acorn, Social C": {"description": "Padrões específicos", "main_column": "Standard"},
    "8. Puro.earth": {"description": "Projetos Puro.earth", "main_column": "Unnamed: 0"},
    "9. Nori and BCarbon": {"description": "Projetos Nori e BCarbon", "main_column": "Standard"}
}

# =========================
# FUNÇÕES AUXILIARES
# =========================
def clean_column_name(col):
    """Limpa e padroniza nomes de colunas"""
    if pd.isna(col):
        return "coluna_sem_nome"
    
    col_str = str(col)
    # Remove caracteres especiais e espaços extras
    col_str = re.sub(r'[^\w\s]', ' ', col_str)
    col_str = re.sub(r'\s+', ' ', col_str).strip()
    
    # Se ficar vazio após limpeza
    if not col_str:
        return "coluna_sem_nome"
    
    # Limita o tamanho
    if len(col_str) > 50:
        col_str = col_str[:47] + "..."
    
    return col_str

def make_column_names_unique(columns):
    """Garante que todos os nomes de colunas sejam únicos"""
    unique_cols = []
    seen = {}
    
    for i, col in enumerate(columns):
        if col in seen:
            seen[col] += 1
            unique_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 1
            unique_cols.append(col)
    
    return unique_cols

# =========================
# LOAD DO EXCEL LOCAL (GITHUB)
# =========================
@st.cache_data(ttl=86400, show_spinner="Carregando dataset...")
def load_data():
    file_path = "Dataset.xlsx"
    
    if not os.path.exists(file_path):
        st.error("❌ Arquivo 'Dataset.xlsx' não encontrado!")
        st.info("Certifique-se de que o arquivo está na raiz do diretório.")
        return None, None
    
    try:
        excel = pd.ExcelFile(file_path, engine='openpyxl')
        data = {}
        
        for sheet in excel.sheet_names:
            try:
                df = excel.parse(sheet, header=0)
                
                # Limpeza básica de colunas
                df = df.dropna(axis=1, how='all')  # Remove colunas completamente vazias
                
                # Limpa e padroniza nomes de colunas
                df.columns = [clean_column_name(col) for col in df.columns]
                
                # Garante nomes únicos
                df.columns = make_column_names_unique(df.columns)
                
                # Identifica primeira linha como header se necessário
                if not df.empty:
                    # Verifica se a primeira linha parece ser header duplicado
                    first_row_str = df.iloc[0].astype(str).str.lower().str.cat(sep=' ')
                    header_indicators = ['project', 'name', 'standard', 'data', 'credit', 'method', 'total', 'description']
                    
                    if any(indicator in first_row_str for indicator in header_indicators):
                        # Usa a primeira linha como header e remove ela
                        new_columns = df.iloc[0]
                        # Limpa os novos nomes de colunas
                        new_columns = [clean_column_name(col) for col in new_columns]
                        new_columns = make_column_names_unique(new_columns)
                        
                        df.columns = new_columns
                        df = df[1:].reset_index(drop=True)
                
                data[sheet] = df
            except Exception as e:
                st.warning(f"Aviso: Erro ao processar aba '{sheet}': {str(e)[:100]}")
                data[sheet] = pd.DataFrame()
        
        if not data:
            st.error("Nenhuma aba pôde ser carregada do arquivo Excel.")
            return None, None
            
        return data, list(data.keys())
    except Exception as e:
        st.error(f"Erro crítico ao carregar arquivo: {e}")
        return None, None

# =========================
# FUNÇÕES DE ANÁLISE AVANÇADA
# =========================
def analyze_sheet_structure(df, sheet_name):
    """Analisa a estrutura da aba e fornece insights específicos"""
    insights = []
    
    if df.empty:
        insights.append("⚠️ DataFrame vazio")
        return insights
    
    # Informações básicas
    insights.append(f"📊 **Formato**: {df.shape[0]} linhas × {df.shape[1]} colunas")
    
    # Análise de tipos de dados
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    text_cols = df.select_dtypes(include=['object']).columns.tolist()
    
    insights.append(f"🔢 **Colunas numéricas**: {len(numeric_cols)}")
    insights.append(f"📝 **Colunas de texto**: {len(text_cols)}")
    
    # Análise de valores ausentes
    missing_percent = df.isnull().mean() * 100
    high_missing = missing_percent[missing_percent > 50].index.tolist()
    
    if high_missing:
        if len(high_missing) > 5:
            insights.append(f"⚠️ **{len(high_missing)} colunas têm mais de 50% de valores ausentes**")
        else:
            for col in high_missing[:5]:
                insights.append(f"⚠️ **{col}**: {missing_percent[col]:.1f}% ausente")
    
    # Detecção de colunas com dados temporais/anuais
    year_patterns = ['year', 'vintage', 'issued', 'retired', '20', '19']
    year_cols = [col for col in df.columns if any(pattern in str(col).lower() for pattern in year_patterns) 
                and df[col].dtype in [np.int64, np.float64]]
    
    if year_cols and len(year_cols) > 5:
        insights.append(f"📅 **Detectadas {len(year_cols)} colunas com dados anuais**")
    
    # Detecção de colunas com valores únicos (potenciais chaves)
    try:
        unique_counts = df.nunique()
        high_unique = unique_counts[unique_counts == df.shape[0]].index.tolist()
        if high_unique:
            # Converte para string e pega apenas os primeiros 3
            high_unique_str = [str(col) for col in high_unique[:3]]
            insights.append(f"🔑 **Colunas com valores únicos**: {', '.join(high_unique_str)}")
    except Exception:
        pass  # Ignora erros nesta análise
    
    return insights

def extract_yearly_data(df, sheet_name):
    """Extrai dados anuais de colunas que parecem conter dados temporais"""
    yearly_data = {}
    
    # Padrões de nomes de colunas que podem conter anos
    year_pattern = r'(19\d{2}|20\d{2})'
    
    for col in df.columns:
        col_str = str(col)
        # Procura por padrões de ano no nome da coluna
        if any(x in col_str.lower() for x in ['20', '19', 'vintage', 'issued', 'retired']):
            try:
                # Tenta extrair o ano do nome da coluna
                year_match = pd.Series([col_str]).str.extract(f'({year_pattern})')
                if not year_match.isna().all().all():
                    year = int(year_match.iloc[0, 0])
                    # Verifica se a coluna é numérica
                    if pd.api.types.is_numeric_dtype(df[col]):
                        yearly_data[year] = {
                            'value': df[col].sum(),
                            'non_zero_count': (df[col] > 0).sum(),
                            'mean': df[col].mean()
                        }
            except:
                continue
    
    return yearly_data

def create_projects_summary(df, sheet_name):
    """Cria um resumo dos projetos baseado na estrutura da aba"""
    summary = {}
    
    if sheet_name in ["4. Agriculture", "5. Agroforestry-AR & Grassland", "6. Energy and Other"]:
        # Identifica coluna de nome do projeto
        project_cols = [col for col in df.columns if 'name' in str(col).lower() or 'project' in str(col).lower()]
        
        if project_cols and not df.empty:
            project_col = project_cols[0]
            summary['total_projects'] = df[project_col].nunique()
            summary['sample_projects'] = df[project_col].dropna().unique()[:5].tolist()
            
            # Tenta identificar coluna de padrão/registro
            registry_cols = [col for col in df.columns if 'registry' in str(col).lower() or 'standard' in str(col).lower()]
            if registry_cols:
                registry_col = registry_cols[0]
                summary['registries'] = df[registry_col].value_counts().head().to_dict()
    
    return summary

def enhanced_smart_insights(df, sheet_name):
    """Insights avançados baseados na estrutura específica de cada aba"""
    insights = []
    
    if df.empty:
        insights.append("📭 **DataFrame vazio** - Nenhum dado disponível")
        return insights
    
    config = SHEET_CONFIG.get(sheet_name, {})
    
    # Insights específicos por tipo de aba
    if "Agriculture" in sheet_name or "Agroforestry" in sheet_name:
        # Procura por colunas de créditos
        credit_cols = [col for col in df.columns if 'credit' in str(col).lower()]
        if credit_cols:
            insights.append(f"💰 **Colunas de créditos identificadas**: {len(credit_cols)}")
            
            # Tenta encontrar colunas numéricas com valores significativos
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                # Encontra coluna com maior soma
                try:
                    col_sums = df[numeric_cols].sum()
                    if not col_sums.empty:
                        max_col = col_sums.idxmax()
                        max_value = col_sums.max()
                        if max_value > 0:
                            insights.append(f"📈 **Maior volume de créditos**: Coluna '{max_col}' com {max_value:,.0f} unidades")
                except Exception:
                    pass  # Ignora erros nesta análise
    
    elif "Methodologies" in sheet_name:
        # Análise para aba de metodologias
        insights.append("🔬 **Aba de metodologias** - Dados técnicos de cálculo de carbono")
        
    elif "Standards" in sheet_name or "Platforms" in sheet_name:
        insights.append("🏢 **Dados institucionais** - Padrões e plataformas do mercado")
        
        # Verifica coluna principal
        main_col = config.get('main_column')
        if main_col and main_col in df.columns:
            try:
                unique_vals = df[main_col].nunique()
                insights.append(f"🏛️ **{unique_vals} {main_col.split()[-1]} únicos**")
            except Exception:
                pass
    
    # Análise geral de qualidade
    try:
        missing_rate = df.isnull().mean().mean() * 100
        if missing_rate > 30:
            insights.append(f"⚠️ **Alta taxa de valores ausentes**: {missing_rate:.1f}%")
        elif missing_rate < 5:
            insights.append(f"✅ **Dados bem preenchidos**: apenas {missing_rate:.1f}% ausentes")
    except Exception:
        pass
    
    # Detecção de outliers em colunas numéricas
    try:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            for col in numeric_cols[:3]:  # Analisa apenas as primeiras 3 colunas
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    valid_data = df[col].dropna()
                    if len(valid_data) > 10:  # Tem dados suficientes
                        q1 = valid_data.quantile(0.25)
                        q3 = valid_data.quantile(0.75)
                        iqr = q3 - q1
                        if iqr > 0:  # Evita divisão por zero
                            outliers = ((valid_data < (q1 - 1.5 * iqr)) | (valid_data > (q3 + 1.5 * iqr))).sum()
                            if outliers > 0:
                                insights.append(f"🔍 **Possíveis outliers em '{col}'**: {outliers} valores")
    except Exception:
        pass  # Ignora erros na detecção de outliers
    
    return insights

# =========================
# FUNÇÕES DE VISUALIZAÇÃO
# =========================
def create_yearly_trend_chart(yearly_data):
    """Cria gráfico de tendência anual"""
    if not yearly_data:
        return None
    
    years = sorted(yearly_data.keys())
    values = [yearly_data[year]['value'] for year in years]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, 
        y=values,
        mode='lines+markers',
        name='Créditos',
        line=dict(color='#2ecc71', width=3),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title='Tendência Anual de Créditos',
        xaxis_title='Ano',
        yaxis_title='Total de Créditos',
        template='plotly_white',
        hovermode='x unified'
    )
    
    return fig

def create_data_quality_chart(df):
    """Cria gráfico de qualidade dos dados"""
    try:
        missing_percent = df.isnull().mean() * 100
        top_missing = missing_percent.sort_values(ascending=False).head(10)
        
        if len(top_missing) == 0:
            return None
        
        fig = px.bar(
            x=top_missing.values,
            y=top_missing.index,
            orientation='h',
            title='Top 10 Colunas com Mais Valores Ausentes',
            labels={'x': '% Ausente', 'y': 'Coluna'},
            color=top_missing.values,
            color_continuous_scale='RdYlGn_r'
        )
        
        fig.update_layout(showlegend=False)
        return fig
    except Exception:
        return None

def create_project_distribution_chart(df, sheet_name):
    """Cria gráfico de distribuição de projetos"""
    try:
        if sheet_name in SHEET_CONFIG:
            config = SHEET_CONFIG[sheet_name]
            main_col = config.get('main_column')
            
            if main_col and main_col in df.columns:
                value_counts = df[main_col].value_counts().head(10)
                
                if len(value_counts) > 0:
                    fig = px.bar(
                        x=value_counts.values,
                        y=value_counts.index,
                        orientation='h',
                        title=f'Top 10 {main_col[:30]}...' if len(main_col) > 30 else f'Top 10 {main_col}',
                        labels={'x': 'Contagem', 'y': main_col},
                        color=value_counts.values,
                        color_continuous_scale='Viridis'
                    )
                    return fig
    except Exception:
        pass
    
    return None

# =========================
# APP PRINCIPAL
# =========================
def main():
    st.title("🌱 FAO Agrifood Carbon Market Dashboard")
    st.markdown("### Análise Interativa do Mercado Voluntário de Carbono Agrícola")
    
    # ---------- LOAD ----------
    with st.spinner("Carregando dados do dataset FAO..."):
        dataframes, sheets = load_data()
    
    if dataframes is None:
        st.error("❌ Não foi possível carregar os dados!")
        st.info("Verifique se o arquivo 'Dataset.xlsx' está na raiz do projeto.")
        st.stop()
    
    # ---------- SIDEBAR ----------
    with st.sidebar:
        st.header("📂 Navegação")
        
        selected_sheet = st.selectbox(
            "Selecione a aba:",
            sheets,
            format_func=lambda x: f"{x} - {SHEET_CONFIG.get(x, {}).get('description', 'Sem descrição')}"
        )
        
        st.markdown("---")
        st.header("🚀 Ferramentas de Análise")
        
        show_summary = st.toggle("📊 Visão Geral do Dataset", True)
        show_insights = st.toggle("🧠 Insights Automáticos", True)
        show_quality = st.toggle("📈 Análise de Qualidade", False)
        show_yearly = st.toggle("📅 Dados Temporais", False)
        
        st.markdown("---")
        st.header("⚙️ Configurações")
        
        max_rows = st.slider("Máximo de linhas para visualizar:", 10, 500, 100)
    
    # ---------- VISÃO GERAL ----------
    if show_summary:
        st.subheader("📊 Visão Geral do Dataset")
        
        # Métricas principais
        total_rows = sum(df.shape[0] for df in dataframes.values() if not df.empty)
        total_cols = sum(df.shape[1] for df in dataframes.values() if not df.empty)
        total_sheets = len([df for df in dataframes.values() if not df.empty])
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Abas", total_sheets)
        col2.metric("Total de Registros", f"{total_rows:,}")
        col3.metric("Total de Colunas", total_cols)
        col4.metric("Tamanho Aprox.", f"{total_rows * total_cols / 1000:.0f}K células")
        
        # Tabela de resumo por aba
        summary_data = []
        for name, df in dataframes.items():
            if not df.empty:
                numeric_cols = len(df.select_dtypes(include=[np.number]).columns)
                missing_percent = df.isnull().mean().mean() * 100
                memory_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
                
                summary_data.append({
                    "Aba": name,
                    "Linhas": df.shape[0],
                    "Colunas": df.shape[1],
                    "Numéricas": numeric_cols,
                    "% Nulos": f"{missing_percent:.1f}%",
                    "Memória (MB)": f"{memory_mb:.1f}",
                    "Descrição": SHEET_CONFIG.get(name, {}).get("description", "-")
                })
        
        if summary_data:
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True, height=300)
    
    # ---------- ABA SELECIONADA ----------
    df = dataframes[selected_sheet]
    
    if df.empty:
        st.warning(f"A aba '{selected_sheet}' está vazia ou não pôde ser carregada.")
        return
    
    st.divider()
    st.header(f"📄 {selected_sheet}")
    st.caption(SHEET_CONFIG.get(selected_sheet, {}).get("description", ""))
    
    # Insights avançados
    if show_insights:
        with st.expander("🧠 Insights Inteligentes", expanded=True):
            try:
                insights = enhanced_smart_insights(df, selected_sheet)
                for insight in insights:
                    st.write(f"• {insight}")
                
                # Análise de estrutura
                structure_insights = analyze_sheet_structure(df, selected_sheet)
                if structure_insights:
                    st.markdown("---")
                    st.markdown("**Análise de Estrutura:**")
                    for insight in structure_insights:
                        st.write(f"• {insight}")
            except Exception as e:
                st.warning(f"Não foi possível gerar insights: {str(e)[:100]}")
    
    # TABS PRINCIPAIS
    tab1, tab2, tab3 = st.tabs(["📋 Dados", "📈 Visualizações", "🔍 Análises"])
    
    with tab1:
        st.subheader("Visualização dos Dados")
        
        # Filtros básicos
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            # Filtra colunas problemáticas
            available_columns = [col for col in df.columns if not pd.isna(col) and str(col).strip() != '']
            
            show_columns = st.multiselect(
                "Selecionar colunas:",
                available_columns,
                default=available_columns[:10] if len(available_columns) > 10 else available_columns
            )
        
        with col_filter2:
            if len(df) > 100:
                n_rows = st.slider("Número de linhas:", 10, min(500, len(df)), 100)
            else:
                n_rows = len(df)
        
        # Dataframe filtrado
        try:
            if show_columns:
                filtered_df = df[show_columns].head(n_rows)
            else:
                filtered_df = df.head(n_rows)
            
            # Exibe o dataframe com tratamento de erros
            st.dataframe(filtered_df, use_container_width=True, height=400)
        except Exception as e:
            st.error(f"Erro ao exibir dados: {str(e)[:200]}")
            # Tenta exibir as primeiras colunas como fallback
            try:
                fallback_cols = df.columns[:5].tolist()
                st.dataframe(df[fallback_cols].head(n_rows), use_container_width=True, height=400)
            except:
                st.dataframe(df.head(n_rows), use_container_width=True, height=400)
        
        # Estatísticas rápidas
        with st.expander("📊 Estatísticas Descritivas"):
            try:
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    st.dataframe(df[numeric_cols].describe().round(2), use_container_width=True)
                else:
                    st.info("Nenhuma coluna numérica para estatísticas.")
            except Exception:
                st.info("Não foi possível calcular estatísticas descritivas.")
    
    with tab2:
        st.subheader("Visualizações Gráficas")
        
        viz_col1, viz_col2 = st.columns(2)
        
        with viz_col1:
            # Gráfico 1: Distribuição de valores numéricos
            try:
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if numeric_cols:
                    selected_num_col = st.selectbox("Selecione coluna numérica:", numeric_cols)
                    
                    if pd.api.types.is_numeric_dtype(df[selected_num_col]):
                        fig = px.histogram(
                            df, 
                            x=selected_num_col,
                            title=f"Distribuição de {selected_num_col[:30]}..." if len(selected_num_col) > 30 else f"Distribuição de {selected_num_col}",
                            nbins=30,
                            color_discrete_sequence=['#2ecc71'],
                            opacity=0.8
                        )
                        fig.update_layout(bargap=0.1)
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Nenhuma coluna numérica para histograma.")
            except Exception:
                st.info("Não foi possível criar o histograma.")
        
        with viz_col2:
            # Gráfico 2: Qualidade dos dados
            if show_quality:
                try:
                    quality_fig = create_data_quality_chart(df)
                    if quality_fig:
                        st.plotly_chart(quality_fig, use_container_width=True)
                    else:
                        st.info("Informações de qualidade não disponíveis.")
                except Exception:
                    st.info("Não foi possível criar o gráfico de qualidade.")
            
            # Gráfico 3: Distribuição de projetos
            try:
                project_fig = create_project_distribution_chart(df, selected_sheet)
                if project_fig:
                    st.plotly_chart(project_fig, use_container_width=True)
            except Exception:
                pass
        
        # Gráfico de tendência anual (se aplicável)
        if show_yearly:
            try:
                yearly_data = extract_yearly_data(df, selected_sheet)
                if yearly_data:
                    trend_fig = create_yearly_trend_chart(yearly_data)
                    if trend_fig:
                        st.plotly_chart(trend_fig, use_container_width=True)
            except Exception:
                pass
    
    with tab3:
        st.subheader("Análises Avançadas")
        
        analysis_type = st.radio(
            "Tipo de análise:",
            ["Correlações", "Valores Ausentes", "Distribuição", "Sumário"]
        )
        
        if analysis_type == "Correlações":
            try:
                numeric_df = df.select_dtypes(include=[np.number])
                if numeric_df.shape[1] >= 2:
                    corr_matrix = numeric_df.corr()
                    
                    fig = go.Figure(data=go.Heatmap(
                        z=corr_matrix.values,
                        x=corr_matrix.columns,
                        y=corr_matrix.columns,
                        colorscale='RdBu',
                        zmid=0,
                        text=corr_matrix.round(2).values,
                        texttemplate='%{text}',
                        hoverongaps=False
                    ))
                    
                    fig.update_layout(
                        title='Matriz de Correlação',
                        width=600,
                        height=600
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Necessárias pelo menos 2 colunas numéricas para análise de correlação.")
            except Exception:
                st.warning("Não foi possível calcular a matriz de correlação.")
        
        elif analysis_type == "Valores Ausentes":
            try:
                missing_df = pd.DataFrame({
                    'Coluna': df.columns,
                    '% Ausente': (df.isnull().mean() * 100).round(2),
                    'Total Ausente': df.isnull().sum()
                }).sort_values('% Ausente', ascending=False)
                
                st.dataframe(missing_df, use_container_width=True, height=400)
                
                # Visualização de missing
                if len(missing_df) > 0:
                    fig = px.bar(
                        missing_df.head(20),
                        x='% Ausente',
                        y='Coluna',
                        orientation='h',
                        title='Top 20 Colunas com Valores Ausentes'
                    )
                    st.plotly_chart(fig, use_container_width=True)
            except Exception:
                st.warning("Não foi possível analisar valores ausentes.")
        
        elif analysis_type == "Distribuição":
            try:
                # Distribuição de valores únicos
                unique_counts = pd.DataFrame({
                    'Coluna': df.columns,
                    'Valores Únicos': df.nunique(),
                    'Tipo': df.dtypes.astype(str)
                }).sort_values('Valores Únicos', ascending=False)
                
                st.dataframe(unique_counts, use_container_width=True, height=400)
            except Exception:
                st.warning("Não foi possível analisar a distribuição de valores únicos.")
        
        else:  # Sumário
            try:
                # Buffer para análise detalhada
                buffer = []
                
                buffer.append(f"### 📋 Sumário da Aba: {selected_sheet}")
                buffer.append(f"- **Dimensões**: {df.shape[0]} linhas × {df.shape[1]} colunas")
                
                # Tipos de dados
                dtype_counts = df.dtypes.value_counts()
                buffer.append("\n**Tipos de dados:**")
                for dtype, count in dtype_counts.items():
                    buffer.append(f"  - {dtype}: {count} colunas")
                
                # Colunas com mais dados
                complete_cols = df.notna().sum().sort_values(ascending=False).head(5)
                buffer.append("\n**Colunas mais completas:**")
                for col, count in complete_cols.items():
                    percent = (count / len(df)) * 100
                    buffer.append(f"  - {col}: {count} valores ({percent:.1f}%)")
                
                # Exibe o sumário
                st.markdown("\n".join(buffer))
            except Exception:
                st.warning("Não foi possível gerar o sumário.")
    
    # ---------- RODAPÉ ----------
    st.divider()
    
    footer_col1, footer_col2, footer_col3 = st.columns(3)
    
    with footer_col1:
        st.caption(f"📅 Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    with footer_col2:
        st.caption(f"📊 Dados carregados: {len(dataframes)} abas, {df.shape[0]:,} registros")
    
    with footer_col3:
        st.caption("🌍 FAO Agrifood Carbon Market Dataset v1.0")

if __name__ == "__main__":
    main()
