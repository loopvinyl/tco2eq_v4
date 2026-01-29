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
    "README": {"description": "Documentação e metadados do dataset", "has_filters": False},
    "1. Standards": {"description": "Padrões e registros de carbono", "main_column": "Name of standard/registry/platform", "has_filters": True},
    "2. Platforms": {"description": "Plataformas de mercado de carbono", "main_column": "Platform", "has_filters": True},
    "3. Methodologies": {"description": "Metodologias de cálculo de carbono", "main_column": "Data sourced from methodology document (see reference in column AD)", "has_filters": True},
    "4. Agriculture": {"description": "Projetos agrícolas", "has_yearly_data": True, "credit_column_pattern": "Credits issued by vintage", "has_filters": True, "country_column": "Country"},
    "5. Agroforestry-AR & Grassland": {"description": "Projetos agroflorestais e pastagens", "has_yearly_data": True, "has_filters": True, "country_column": "Country"},
    "6. Energy and Other": {"description": "Projetos de energia e outros", "has_yearly_data": True, "has_filters": True, "country_column": "Country"},
    "7. Plan Vivo, Acorn, Social C": {"description": "Padrões específicos", "main_column": "Standard", "has_filters": True, "country_column": "Country"},
    "8. Puro.earth": {"description": "Projetos Puro.earth", "main_column": "Unnamed: 0", "has_filters": True},
    "9. Nori and BCarbon": {"description": "Projetos Nori e BCarbon", "main_column": "Standard", "has_filters": True, "country_column": "Country"}
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

def detect_filter_columns(df, sheet_name):
    """Detecta automaticamente colunas adequadas para filtragem"""
    filter_columns = {}
    
    if df.empty or sheet_name == "README":
        return filter_columns
    
    # Configuração específica da aba
    config = SHEET_CONFIG.get(sheet_name, {})
    
    # Primeiro, verificar se há uma coluna de país configurada
    country_column = config.get('country_column')
    if country_column:
        # Verificar variações possíveis do nome da coluna
        possible_country_names = [
            country_column,
            'country',
            'countries',
            'país',
            'países',
            'nation',
            'location',
            'region'
        ]
        
        for col in df.columns:
            col_lower = str(col).lower()
            if any(country_name.lower() in col_lower for country_name in possible_country_names):
                if not df[col].isna().all():
                    unique_vals = df[col].nunique()
                    if 1 < unique_vals < 200:  # Países geralmente têm entre 1 e 200 valores únicos
                        filter_columns['country'] = col
                        break
    
    # Padrões para diferentes tipos de filtros
    patterns = {
        'standard': ['standard', 'registry', 'platform', 'protocol', 'verra', 'gold', 'carbon'],
        'type': ['type', 'tipo', 'category', 'class', 'classification', 'sector'],
        'methodology': ['methodology', 'method', 'metodologia', 'approach', 'protocol'],
        'year': ['year', 'ano', 'vintage', 'date', 'period', 'issued'],
        'credits': ['credit', 'credito', 'volume', 'amount', 'quantity', 'total', 'issued', 'retired'],
        'project': ['project', 'projeto', 'name', 'title', 'id'],
        'status': ['status', 'state', 'condition', 'phase', 'stage']
    }
    
    # Buscar outros filtros
    for filter_type, keywords in patterns.items():
        # Se já encontramos esse tipo, pular
        if filter_type in filter_columns:
            continue
            
        matching_cols = []
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in keywords):
                # Verifica se a coluna tem dados razoáveis para filtro
                if not df[col].isna().all():
                    unique_vals = df[col].nunique()
                    total_vals = len(df[col])
                    
                    # Critérios para ser um bom filtro
                    is_good_filter = (
                        1 < unique_vals < 100 and  # Não muito único, nem muito repetido
                        total_vals > 5 and  # Tem dados suficientes
                        df[col].notna().sum() > total_vals * 0.1  # Pelo menos 10% preenchido
                    )
                    
                    if is_good_filter:
                        matching_cols.append((col, unique_vals))
        
        if matching_cols:
            # Ordena pelo número de valores únicos (menos é melhor para filtros)
            matching_cols.sort(key=lambda x: x[1])
            filter_columns[filter_type] = matching_cols[0][0]
    
    return filter_columns

def extract_countries_from_dataframe(df, country_column):
    """Extrai e limpa lista de países do DataFrame"""
    if country_column not in df.columns:
        return []
    
    # Extrair países únicos
    countries = df[country_column].dropna().astype(str).unique()
    
    # Limpar os nomes dos países
    cleaned_countries = []
    for country in countries:
        # Remover espaços extras e caracteres especiais
        country_clean = str(country).strip()
        # Remover números e caracteres especiais no início
        country_clean = re.sub(r'^\d+\.\s*', '', country_clean)
        country_clean = re.sub(r'^[^a-zA-Z]+', '', country_clean)
        
        if country_clean and len(country_clean) > 1:
            cleaned_countries.append(country_clean)
    
    # Remover duplicados após limpeza
    unique_countries = list(set(cleaned_countries))
    
    # Ordenar alfabeticamente
    unique_countries.sort(key=lambda x: x.lower())
    
    return unique_countries

def get_country_names_in_portuguese(country_name):
    """Traduz nomes de países para português quando conhecidos"""
    country_translations = {
        'brazil': 'Brasil',
        'united states': 'Estados Unidos',
        'united kingdom': 'Reino Unido',
        'mexico': 'México',
        'canada': 'Canadá',
        'germany': 'Alemanha',
        'france': 'França',
        'spain': 'Espanha',
        'portugal': 'Portugal',
        'italy': 'Itália',
        'china': 'China',
        'india': 'Índia',
        'japan': 'Japão',
        'australia': 'Austrália',
        'argentina': 'Argentina',
        'chile': 'Chile',
        'colombia': 'Colômbia',
        'peru': 'Peru',
        'uruguay': 'Uruguai',
        'paraguay': 'Paraguai',
        'bolivia': 'Bolívia',
        'venezuela': 'Venezuela',
        'ecuador': 'Equador',
        'costarica': 'Costa Rica',
        'panama': 'Panamá',
        'nicaragua': 'Nicarágua',
        'honduras': 'Honduras',
        'guatemala': 'Guatemala',
        'elsalvador': 'El Salvador',
        'cuba': 'Cuba',
        'dominicanrepublic': 'República Dominicana',
        'puertorico': 'Porto Rico'
    }
    
    country_lower = str(country_name).lower().strip()
    for eng_name, port_name in country_translations.items():
        if eng_name in country_lower or country_lower in eng_name:
            return port_name
    
    # Se não encontrar tradução, retorna o nome original capitalizado
    return country_name.strip().title()

def apply_filters(df, filters):
    """Aplica filtros ao DataFrame"""
    if not filters:
        return df.copy()
    
    filtered_df = df.copy()
    
    for filter_col, filter_value in filters.items():
        if filter_value and filter_col in df.columns:
            try:
                if filter_col in ['year', 'credits'] and isinstance(filter_value, tuple):
                    # Filtro de intervalo numérico
                    min_val, max_val = filter_value
                    if min_val is not None and max_val is not None:
                        filtered_df = filtered_df[
                            (filtered_df[filter_col] >= min_val) & 
                            (filtered_df[filter_col] <= max_val)
                        ]
                elif isinstance(filter_value, list) and filter_value:
                    # Filtro de múltiplos valores
                    # Converter para string para comparação robusta
                    filter_values_str = [str(v).strip().lower() for v in filter_value]
                    filtered_df = filtered_df[
                        filtered_df[filter_col].astype(str).str.strip().str.lower().isin(filter_values_str)
                    ]
                elif filter_value != 'Todos':
                    # Filtro de valor único
                    filter_value_str = str(filter_value).strip().lower()
                    filtered_df = filtered_df[
                        filtered_df[filter_col].astype(str).str.strip().str.lower() == filter_value_str
                    ]
            except Exception as e:
                st.warning(f"Erro ao aplicar filtro na coluna '{filter_col}': {str(e)[:100]}")
                continue
    
    return filtered_df

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
                    header_indicators = ['project', 'name', 'standard', 'data', 'credit', 'method', 'total', 'description', 'country']
                    
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

def enhanced_smart_insights(df, sheet_name):
    """Insights avançados baseados na estrutura específica de cada aba"""
    insights = []
    
    if df.empty:
        insights.append("📭 **DataFrame vazio** - Nenhum dado disponível")
        return insights
    
    config = SHEET_CONFIG.get(sheet_name, {})
    
    # Insights específicos por tipo de aba
    if "Agriculture" in sheet_name or "Agroforestry" in sheet_name or "Energy" in sheet_name:
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
        
        # Verificar se há dados de países
        country_column = config.get('country_column')
        if country_column:
            # Buscar coluna de país por nome aproximado
            for col in df.columns:
                if 'country' in str(col).lower():
                    unique_countries = df[col].dropna().nunique()
                    if unique_countries > 0:
                        insights.append(f"🌍 **{unique_countries} países diferentes** identificados")
                        # Mostrar alguns exemplos
                        sample_countries = df[col].dropna().unique()[:5]
                        country_list = ", ".join([str(c) for c in sample_countries])
                        insights.append(f"   Exemplos: {country_list}")
                    break
    
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

def create_country_distribution_chart(df, country_column):
    """Cria gráfico de distribuição por país"""
    try:
        if country_column in df.columns:
            # Contar ocorrências por país
            country_counts = df[country_column].value_counts().head(15)
            
            if len(country_counts) > 0:
                # Traduzir nomes de países para português
                country_names = [get_country_names_in_portuguese(country) for country in country_counts.index]
                
                fig = px.bar(
                    x=country_counts.values,
                    y=country_names,
                    orientation='h',
                    title='Distribuição por País (Top 15)',
                    labels={'x': 'Número de Projetos/Registros', 'y': 'País'},
                    color=country_counts.values,
                    color_continuous_scale='Blues'
                )
                
                fig.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    height=500
                )
                
                return fig
    except Exception:
        pass
    
    return None

def create_filter_metrics(df_filtered, df_original, active_filters):
    """Cria métricas de filtro aplicado"""
    if df_filtered.empty or df_original.empty:
        return None
    
    total_original = len(df_original)
    total_filtered = len(df_filtered)
    reduction_pct = ((total_original - total_filtered) / total_original * 100) if total_original > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Registros Totais", f"{total_original:,}")
    with col2:
        st.metric("🔍 Registros Filtrados", f"{total_filtered:,}", 
                 delta=f"-{reduction_pct:.1f}%" if reduction_pct > 0 else None)
    with col3:
        active_count = sum(1 for v in active_filters.values() if v and v != 'Todos')
        st.metric("⚙️ Filtros Ativos", active_count)
    
    if active_filters:
        with st.expander("📋 Filtros Aplicados", expanded=False):
            for filter_name, filter_value in active_filters.items():
                if filter_value and filter_value != 'Todos':
                    if isinstance(filter_value, tuple):
                        st.write(f"**{filter_name}**: {filter_value[0]} a {filter_value[1]}")
                    elif isinstance(filter_value, list):
                        st.write(f"**{filter_name}**: {', '.join(map(str, filter_value[:3]))}")
                        if len(filter_value) > 3:
                            st.write(f"... e mais {len(filter_value) - 3} valores")
                    else:
                        st.write(f"**{filter_name}**: {filter_value}")

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
        st.header("⚙️ Configurações de Visualização")
        
        max_rows = st.slider("Máximo de linhas para visualizar:", 10, 500, 100)
    
    # ---------- ABA SELECIONADA ----------
    df = dataframes[selected_sheet]
    
    if df.empty:
        st.warning(f"A aba '{selected_sheet}' está vazia ou não pôde ser carregada.")
        return
    
    # Detecta colunas para filtragem (exceto para README)
    config = SHEET_CONFIG.get(selected_sheet, {})
    has_filters = config.get('has_filters', True)
    
    if has_filters and selected_sheet != "README":
        filter_columns = detect_filter_columns(df, selected_sheet)
    else:
        filter_columns = {}
    
    # ---------- FILTROS NA SIDEBAR ----------
    if has_filters and selected_sheet != "README":
        with st.sidebar:
            st.markdown("---")
            st.header("🔍 Filtros da Aba")
            
            filters = {}
            active_filters = {}
            
            if filter_columns:
                # Filtro de País (prioridade máxima)
                if 'country' in filter_columns:
                    country_col = filter_columns['country']
                    if country_col in df.columns:
                        # Extrair e limpar lista de países
                        countries_raw = extract_countries_from_dataframe(df, country_col)
                        
                        if countries_raw:
                            # Traduzir alguns países para português para facilitar
                            countries_display = []
                            countries_mapping = {}
                            
                            for country in countries_raw:
                                display_name = get_country_names_in_portuguese(country)
                                countries_display.append(display_name)
                                countries_mapping[display_name] = country
                            
                            # Ordenar por nome em português
                            sorted_indices = np.argsort(countries_display)
                            countries_display_sorted = [countries_display[i] for i in sorted_indices]
                            countries_raw_sorted = [countries_raw[sorted_indices[i]] for i in range(len(sorted_indices))]
                            
                            selected_countries_display = st.multiselect(
                                "🌍 País(es):",
                                options=["Todos"] + countries_display_sorted,
                                default=["Todos"],
                                help="Selecione 'Todos' para ver todos os países, ou escolha países específicos"
                            )
                            
                            if "Todos" not in selected_countries_display and selected_countries_display:
                                # Mapear de volta para os nomes originais
                                selected_countries_raw = []
                                for display_name in selected_countries_display:
                                    # Encontrar o nome original correspondente
                                    for i, disp in enumerate(countries_display_sorted):
                                        if disp == display_name:
                                            selected_countries_raw.append(countries_raw_sorted[i])
                                            break
                                
                                if selected_countries_raw:
                                    filters[country_col] = selected_countries_raw
                                    active_filters['País'] = selected_countries_display
                
                # Filtro de Padrão/Registro
                if 'standard' in filter_columns:
                    standard_col = filter_columns['standard']
                    if standard_col in df.columns:
                        standards = df[standard_col].dropna().unique().tolist()
                        if standards:
                            standards = ['Todos'] + sorted([str(s) for s in standards])
                            selected_standard = st.selectbox(
                                "🏛️ Padrão/Registro:",
                                standards,
                                index=0
                            )
                            if selected_standard != 'Todos':
                                filters[standard_col] = selected_standard
                                active_filters['Padrão'] = selected_standard
                
                # Filtro de Tipo
                if 'type' in filter_columns:
                    type_col = filter_columns['type']
                    if type_col in df.columns:
                        types = df[type_col].dropna().unique().tolist()
                        if types:
                            types = sorted([str(t) for t in types])
                            selected_types = st.multiselect(
                                "📋 Tipo(s):",
                                types,
                                default=[]
                            )
                            if selected_types:
                                filters[type_col] = selected_types
                                active_filters['Tipo'] = selected_types
                
                # Filtro de Ano (intervalo) - apenas para abas com dados anuais
                if 'year' in filter_columns and config.get('has_yearly_data', False):
                    year_col = filter_columns['year']
                    if year_col in df.columns and pd.api.types.is_numeric_dtype(df[year_col]):
                        year_data = df[year_col].dropna()
                        if not year_data.empty:
                            min_year = int(year_data.min())
                            max_year = int(year_data.max())
                            year_range = st.slider(
                                "📅 Intervalo de Anos:",
                                min_value=min_year,
                                max_value=max_year,
                                value=(min_year, max_year)
                            )
                            if year_range != (min_year, max_year):
                                filters[year_col] = year_range
                                active_filters['Ano'] = year_range
                
                # Filtro de Créditos (intervalo)
                if 'credits' in filter_columns:
                    credit_col = filter_columns['credits']
                    if credit_col in df.columns and pd.api.types.is_numeric_dtype(df[credit_col]):
                        credit_data = df[credit_col].dropna()
                        if not credit_data.empty:
                            min_credit = float(credit_data.min())
                            max_credit = float(credit_data.max())
                            
                            # Se houver muita variação, usar escala logarítmica
                            if max_credit / min_credit > 1000 and min_credit > 0:
                                min_credit = float(np.log10(min_credit))
                                max_credit = float(np.log10(max_credit))
                                credit_range = st.slider(
                                    "💰 Intervalo de Créditos (escala log):",
                                    min_value=min_credit,
                                    max_value=max_credit,
                                    value=(min_credit, max_credit),
                                    step=0.1
                                )
                                credit_range = (10**credit_range[0], 10**credit_range[1])
                            else:
                                credit_range = st.slider(
                                    "💰 Intervalo de Créditos:",
                                    min_value=min_credit,
                                    max_value=max_credit,
                                    value=(min_credit, max_credit)
                                )
                            
                            if credit_range != (min_credit, max_credit):
                                filters[credit_col] = credit_range
                                active_filters['Créditos'] = credit_range
                
                # Botão para limpar filtros
                if filters:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🧹 Limpar Filtros", use_container_width=True):
                            st.session_state['filters'] = {}
                            st.rerun()
                    with col2:
                        if st.button("💾 Salvar Filtros", use_container_width=True):
                            st.session_state['saved_filters'] = filters
                            st.success("Filtros salvos!")
            
            else:
                st.info("ℹ️ Não foram detectadas colunas adequadas para filtragem nesta aba.")
    else:
        filters = {}
        active_filters = {}
    
    # ---------- APLICA FILTROS ----------
    if filters:
        df_filtered = apply_filters(df, filters)
    else:
        df_filtered = df.copy()
    
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
        for name, df_sheet in dataframes.items():
            if not df_sheet.empty:
                numeric_cols = len(df_sheet.select_dtypes(include=[np.number]).columns)
                missing_percent = df_sheet.isnull().mean().mean() * 100
                memory_mb = df_sheet.memory_usage(deep=True).sum() / 1024 / 1024
                
                summary_data.append({
                    "Aba": name,
                    "Linhas": df_sheet.shape[0],
                    "Colunas": df_sheet.shape[1],
                    "Numéricas": numeric_cols,
                    "% Nulos": f"{missing_percent:.1f}%",
                    "Memória (MB)": f"{memory_mb:.1f}",
                    "Descrição": SHEET_CONFIG.get(name, {}).get("description", "-")
                })
        
        if summary_data:
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True, height=300)
    
    # ---------- CABEÇALHO DA ABA ----------
    st.divider()
    st.header(f"📄 {selected_sheet}")
    st.caption(SHEET_CONFIG.get(selected_sheet, {}).get("description", ""))
    
    # Mostra métricas de filtro se aplicável
    if has_filters and selected_sheet != "README" and filters:
        create_filter_metrics(df_filtered, df, active_filters)
        st.markdown("---")
    
    # Insights avançados
    if show_insights:
        with st.expander("🧠 Insights Inteligentes", expanded=True):
            try:
                insights = enhanced_smart_insights(df_filtered, selected_sheet)
                for insight in insights:
                    st.write(f"• {insight}")
                
                # Análise de estrutura
                structure_insights = analyze_sheet_structure(df_filtered, selected_sheet)
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
            available_columns = [col for col in df_filtered.columns if not pd.isna(col) and str(col).strip() != '']
            
            show_columns = st.multiselect(
                "Selecionar colunas:",
                available_columns,
                default=available_columns[:10] if len(available_columns) > 10 else available_columns
            )
        
        with col_filter2:
            if len(df_filtered) > 100:
                n_rows = st.slider("Número de linhas:", 10, min(500, len(df_filtered)), 100)
            else:
                n_rows = len(df_filtered)
        
        # Dataframe filtrado
        try:
            if show_columns:
                display_df = df_filtered[show_columns].head(n_rows)
            else:
                display_df = df_filtered.head(n_rows)
            
            # Exibe o dataframe com tratamento de erros
            st.dataframe(display_df, use_container_width=True, height=400)
        except Exception as e:
            st.error(f"Erro ao exibir dados: {str(e)[:200]}")
            # Tenta exibir as primeiras colunas como fallback
            try:
                fallback_cols = df_filtered.columns[:5].tolist()
                st.dataframe(df_filtered[fallback_cols].head(n_rows), use_container_width=True, height=400)
            except:
                st.dataframe(df_filtered.head(n_rows), use_container_width=True, height=400)
        
        # Estatísticas rápidas
        with st.expander("📊 Estatísticas Descritivas"):
            try:
                numeric_cols = df_filtered.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    st.dataframe(df_filtered[numeric_cols].describe().round(2), use_container_width=True)
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
                numeric_cols = df_filtered.select_dtypes(include=[np.number]).columns.tolist()
                if numeric_cols:
                    selected_num_col = st.selectbox("Selecione coluna numérica:", numeric_cols)
                    
                    if pd.api.types.is_numeric_dtype(df_filtered[selected_num_col]):
                        fig = px.histogram(
                            df_filtered, 
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
                    quality_fig = create_data_quality_chart(df_filtered)
                    if quality_fig:
                        st.plotly_chart(quality_fig, use_container_width=True)
                    else:
                        st.info("Informações de qualidade não disponíveis.")
                except Exception:
                    st.info("Não foi possível criar o gráfico de qualidade.")
            
            # Gráfico 3: Distribuição de projetos
            try:
                project_fig = create_project_distribution_chart(df_filtered, selected_sheet)
                if project_fig:
                    st.plotly_chart(project_fig, use_container_width=True)
            except Exception:
                pass
        
        # Gráfico de distribuição por país (se houver coluna de país)
        if 'country' in filter_columns:
            country_col = filter_columns['country']
            if country_col in df_filtered.columns:
                country_chart = create_country_distribution_chart(df_filtered, country_col)
                if country_chart:
                    st.plotly_chart(country_chart, use_container_width=True)
        
        # Gráfico de tendência anual (se aplicável)
        if show_yearly:
            try:
                yearly_data = extract_yearly_data(df_filtered, selected_sheet)
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
                numeric_df = df_filtered.select_dtypes(include=[np.number])
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
                    'Coluna': df_filtered.columns,
                    '% Ausente': (df_filtered.isnull().mean() * 100).round(2),
                    'Total Ausente': df_filtered.isnull().sum()
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
                    'Coluna': df_filtered.columns,
                    'Valores Únicos': df_filtered.nunique(),
                    'Tipo': df_filtered.dtypes.astype(str)
                }).sort_values('Valores Únicos', ascending=False)
                
                st.dataframe(unique_counts, use_container_width=True, height=400)
            except Exception:
                st.warning("Não foi possível analisar a distribuição de valores únicos.")
        
        else:  # Sumário
            try:
                # Buffer para análise detalhada
                buffer = []
                
                buffer.append(f"### 📋 Sumário da Aba: {selected_sheet}")
                buffer.append(f"- **Dimensões**: {df_filtered.shape[0]} linhas × {df_filtered.shape[1]} colunas")
                
                # Tipos de dados
                dtype_counts = df_filtered.dtypes.value_counts()
                buffer.append("\n**Tipos de dados:**")
                for dtype, count in dtype_counts.items():
                    buffer.append(f"  - {dtype}: {count} colunas")
                
                # Colunas com mais dados
                complete_cols = df_filtered.notna().sum().sort_values(ascending=False).head(5)
                buffer.append("\n**Colunas mais completas:**")
                for col, count in complete_cols.items():
                    percent = (count / len(df_filtered)) * 100
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
        st.caption(f"📊 Dados carregados: {len(dataframes)} abas, {df_filtered.shape[0]:,} registros")
    
    with footer_col3:
        st.caption("🌍 FAO Agrifood Carbon Market Dataset v1.0")

if __name__ == "__main__":
    main()
    
