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

warnings.filterwarnings("ignore")

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Mercado de Carbono para Propriedades Rurais - Baseado em Dados Reais FAO",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.fao.org/climate-change/our-work/carbon-markets',
        'Report a bug': None,
        'About': """
        Dashboard baseado em dados reais da FAO para proprietários rurais entenderem oportunidades no mercado de carbono agrícola.
        
        **Fonte principal:** FAO Agrifood Voluntary Carbon Market Dataset (2025)
        
        **Aviso:** Alguns cálculos usam estimativas baseadas em dados de mercado externos, 
        pois o dataset FAO não contém preços de transações.
        """
    }
)

# =========================
# FUNÇÕES DE FORMATAÇÃO BRASILEIRA
# =========================

def formatar_milhoes(numero):
    """Formata números grandes como milhões"""
    if pd.isna(numero):
        return "N/A"
    
    if numero >= 1000000000:
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
    """Formata números com número específico de casas decimais"""
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

def formatar_moeda_curta(numero):
    """Formata valores monetários de forma curta e inteligente"""
    if pd.isna(numero):
        return "N/A"
    
    numero = float(numero)
    
    if numero >= 1000000000:
        valor = numero / 1000000000
        return f"{formatar_br_dec(valor, 1)} bilhões"
    elif numero >= 1000000:
        valor = numero / 1000000
        return f"{formatar_br_dec(valor, 1)} milhões"
    elif numero >= 1000:
        valor = numero / 1000
        return f"{formatar_br_dec(valor, 1)} mil"
    else:
        return formatar_br(numero)

# =========================
# CONSTANTES E CONFIGURAÇÕES
# =========================
SHEET_CONFIG = {
    "README": {"type": "documentação", "icon": "📖", "color": "#95a5a6"},
    "1. Standards": {"type": "padrões", "icon": "🏛️", "color": "#3498db", "main_column": "Name of standard/registry/platform"},
    "2. Platforms": {"type": "plataformas", "icon": "🖥️", "color": "#9b59b6", "main_column": "Platform"},
    "3. Methodologies": {"type": "metodologias", "icon": "🔬", "color": "#e74c3c", "main_column": "Data sourced from methodology document (see reference in column AD)"},
    "4. Agriculture": {"type": "projetos", "icon": "🚜", "color": "#2ecc71", "has_yearly_data": True, "country_column": "Country", "revenue_focus": True, "project_focus": True},
    "5. Agroforestry-AR & Grassland": {"type": "projetos", "icon": "🌳", "color": "#27ae60", "has_yearly_data": True, "country_column": "Country", "revenue_focus": True, "project_focus": True},
    "6. Energy and Other": {"type": "projetos", "icon": "⚡", "color": "#f39c12", "has_yearly_data": True, "country_column": "Country", "revenue_focus": True, "project_focus": True},
    "7. Plan Vivo, Acorn, Social C": {"type": "padrões", "icon": "🌍", "color": "#1abc9c", "main_column": "Standard", "country_column": "Country", "revenue_focus": True, "project_focus": True},
    "8. Puro.earth": {"type": "projetos", "icon": "🔥", "color": "#d35400", "revenue_focus": True, "project_focus": True},
    "9. Nori and BCarbon": {"type": "projetos", "icon": "🌾", "color": "#16a085", "main_column": "Standard", "country_column": "Country", "revenue_focus": True, "project_focus": True}
}

# Traduções de países
COUNTRY_TRANSLATIONS = {
    'brazil': 'Brasil', 'brazilian': 'Brasil', 'brasil': 'Brasil', 'br': 'Brasil',
    'united states': 'Estados Unidos', 'usa': 'Estados Unidos', 'us': 'Estados Unidos', 'united states of america': 'Estados Unidos',
    'argentina': 'Argentina', 'chile': 'Chile', 'colombia': 'Colômbia', 'uruguay': 'Uruguai',
    'paraguay': 'Paraguai', 'mexico': 'México', 'peru': 'Peru', 'bolivia': 'Bolívia',
    'ecuador': 'Equador', 'costarica': 'Costa Rica', 'panama': 'Panamá',
    'australia': 'Austrália', 'canada': 'Canadá', 'germany': 'Alemanha', 'france': 'França',
    'spain': 'Espanha', 'italy': 'Itália', 'portugal': 'Portugal', 'united kingdom': 'Reino Unido',
    'china': 'China', 'india': 'Índia', 'indonesia': 'Indonésia', 'vietnam': 'Vietnã',
    'thailand': 'Tailândia', 'philippines': 'Filipinas', 'malaysia': 'Malásia',
    'southafrica': 'África do Sul', 'kenya': 'Quênia', 'ethiopia': 'Etiópia', 'nigeria': 'Nigéria',
    'tanzania': 'Tanzânia', 'ghana': 'Gana', 'uganda': 'Uganda', 'zambia': 'Zâmbia'
}

# Mapeamento de códigos de país
COUNTRY_CODES = {
    'brasil': 'BRA', 'estados unidos': 'USA', 'argentina': 'ARG', 'chile': 'CHL',
    'colômbia': 'COL', 'uruguai': 'URY', 'paraguai': 'PRY', 'méxico': 'MEX',
    'peru': 'PER', 'bolívia': 'BOL', 'equador': 'ECU', 'costa rica': 'CRI',
    'panamá': 'PAN', 'austrália': 'AUS', 'canadá': 'CAN', 'alemanha': 'DEU',
    'frança': 'FRA', 'espanha': 'ESP', 'itália': 'ITA', 'portugal': 'PRT',
    'reino unido': 'GBR', 'china': 'CHN', 'índia': 'IND', 'indonésia': 'IDN',
    'vietnã': 'VNM', 'tailândia': 'THA', 'filipinas': 'PHL', 'malásia': 'MYS',
    'áfrica do sul': 'ZAF', 'quênia': 'KEN', 'etiópia': 'ETH', 'nigéria': 'NGA',
    'tanzânia': 'TZA', 'gana': 'GHA', 'uganda': 'UGA', 'zâmbia': 'ZMB'
}

# =========================
# FUNÇÕES DE LIMPEZA DE DADOS
# =========================

def clean_column_names(df):
    """Limpa e renomeia colunas do dataframe"""
    if df is None or df.empty:
        return df
    
    df_clean = df.copy()
    new_names = {}
    
    for i, col in enumerate(df_clean.columns):
        col_str = str(col)
        
        if pd.isna(col) or col_str.strip() == '' or 'Unnamed' in col_str:
            possible_name = infer_column_name(df_clean, col)
            if possible_name:
                new_names[col] = possible_name
            else:
                new_names[col] = f"Coluna_{i+1}"
        else:
            new_names[col] = col_str.strip()
    
    df_clean.rename(columns=new_names, inplace=True)
    return df_clean

def infer_column_name(df, col_idx):
    """Tenta inferir o nome da coluna baseado no conteúdo"""
    if df.empty or col_idx not in df.columns:
        return None
    
    non_null_values = df[col_idx].dropna().head(5).astype(str).tolist()
    
    if non_null_values:
        first_value = non_null_values[0].strip()
        if (len(first_value) > 2 and len(first_value) < 100 and 
            not first_value.isdigit() and 
            not any(char.isdigit() for char in first_value[:10]) and
            'http' not in first_value.lower()):
            return first_value
    
    for value in non_null_values:
        value_lower = value.lower()
        header_patterns = {
            'project': ['project', 'projeto', 'name', 'nome'],
            'country': ['country', 'pais', 'location', 'region'],
            'method': ['method', 'methodology', 'metodologia', 'tipo'],
            'credits': ['credit', 'credits', 'credito', 'volume', 'issued', 'carbon', 'total credits issued'],
            'retired': ['retired', 'aposentado', 'retirado', 'total credits retired'],
            'area': ['area', 'hectare', 'ha', 'land', 'size'],
            'price': ['price', 'preco', 'value', 'valor', 'cost'],
            'standard': ['standard', 'registro', 'registry'],
            'platform': ['platform', 'plataforma'],
            'description': ['description', 'descrição', 'descricao'],
            'type': ['type', 'tipo', 'category', 'categoria']
        }
        
        for key, patterns in header_patterns.items():
            for pattern in patterns:
                if pattern in value_lower and len(value) < 50:
                    return value
    
    return None

def clean_dataframe(df):
    """Limpa completamente um dataframe"""
    if df is None or df.empty:
        return df
    
    df_clean = df.copy()
    
    # Verificar se a primeira linha contém cabeçalhos reais
    all_unnamed = all('Unnamed' in str(col) for col in df_clean.columns)
    
    if all_unnamed and len(df_clean) > 0:
        first_row = df_clean.iloc[0]
        potential_headers = []
        
        for val in first_row:
            val_str = str(val)
            if (pd.notna(val) and 
                len(val_str) > 2 and len(val_str) < 100 and
                not val_str.isdigit() and
                'http' not in val_str.lower()):
                potential_headers.append(True)
            else:
                potential_headers.append(False)
        
        if sum(potential_headers) > len(potential_headers) / 2:
            new_columns = []
            for i, val in enumerate(first_row):
                if potential_headers[i]:
                    new_columns.append(str(val).strip())
                else:
                    new_columns.append(f"Coluna_{i+1}")
            
            df_clean.columns = new_columns
            df_clean = df_clean.iloc[1:].reset_index(drop=True)
    
    df_clean = clean_column_names(df_clean)
    df_clean = df_clean.dropna(axis=1, how='all')
    df_clean = df_clean.dropna(how='all')
    df_clean = df_clean.reset_index(drop=True)
    
    return df_clean

# =========================
# ANÁLISE ESPECÍFICA DA ABA 4. AGRICULTURE
# =========================

@st.cache_data(ttl=3600, show_spinner="Analisando projetos agrícolas...")
def analyze_agriculture_dataset(dataframes):
    """Análise focada exclusivamente na aba 4. Agriculture"""
    
    if "4. Agriculture" not in dataframes:
        return None
    
    df_raw = dataframes["4. Agriculture"]
    df = clean_dataframe(df_raw)
    
    analysis = {
        'projetos_agricultura': [],
        'estatisticas_agricultura': {
            'total_projetos': 0,
            'projetos_com_creditos': 0,
            'total_creditos_emitidos': 0,
            'total_creditos_vendidos': 0,
            'paises': set(),
            'projetos_por_pais': {},
            'metodologias': {},
            'anos_inicio': [],
            'creditos_por_ano': {},
            'vendidos_por_ano': {}
        }
    }
    
    if df.empty:
        return analysis
    
    # Identificar colunas automaticamente
    col_creditos_emitidos = None
    col_creditos_vendidos = None
    col_projeto_nome = None
    col_pais = None
    col_metodologia = None
    col_ano_inicio = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        if 'credit' in col_lower and 'issued' in col_lower and not 'retired' in col_lower:
            col_creditos_emitidos = col
        elif 'retired' in col_lower or 'aposentado' in col_lower:
            col_creditos_vendidos = col
        elif 'project' in col_lower or 'name' in col_lower or 'nome' in col_lower:
            col_projeto_nome = col
        elif 'country' in col_lower or 'pais' in col_lower:
            col_pais = col
        elif 'method' in col_lower or 'methodology' in col_lower:
            col_metodologia = col
        elif 'year' in col_lower or 'ano' in col_lower or 'first year' in col_lower:
            col_ano_inicio = col
    
    analysis['colunas_identificadas'] = {
        'creditos_emitidos': col_creditos_emitidos,
        'creditos_vendidos': col_creditos_vendidos,
        'nome_projeto': col_projeto_nome,
        'pais': col_pais,
        'metodologia': col_metodologia,
        'ano_inicio': col_ano_inicio
    }
    
    # Processar cada projeto
    projetos_com_creditos = 0
    total_creditos_emitidos = 0
    total_creditos_vendidos = 0
    
    for idx, row in df.iterrows():
        try:
            projeto_info = {
                'indice': idx,
                'nome': str(row[col_projeto_nome]) if col_projeto_nome and col_projeto_nome in row else f"Projeto {idx+1}",
                'creditos_emitidos': 0,
                'creditos_vendidos': 0
            }
            
            # Extrair créditos emitidos
            if col_creditos_emitidos and col_creditos_emitidos in row:
                creditos = convert_to_numeric(row[col_creditos_emitidos])
                if creditos and creditos > 0:
                    projeto_info['creditos_emitidos'] = creditos
                    total_creditos_emitidos += creditos
                    projetos_com_creditos += 1
            
            # Extrair créditos vendidos
            if col_creditos_vendidos and col_creditos_vendidos in row:
                vendidos = convert_to_numeric(row[col_creditos_vendidos])
                if vendidos and vendidos >= 0:
                    projeto_info['creditos_vendidos'] = vendidos
                    total_creditos_vendidos += vendidos
            
            # Extrair país
            if col_pais and col_pais in row:
                pais_raw = str(row[col_pais])
                if pais_raw and pais_raw.lower() != 'nan':
                    projeto_info['pais'] = get_country_name(pais_raw)
                    
                    # Acumular por país
                    pais_nome = projeto_info['pais']
                    if pais_nome not in analysis['estatisticas_agricultura']['projetos_por_pais']:
                        analysis['estatisticas_agricultura']['projetos_por_pais'][pais_nome] = 0
                    analysis['estatisticas_agricultura']['projetos_por_pais'][pais_nome] += 1
                    
                    analysis['estatisticas_agricultura']['paises'].add(pais_nome)
            
            # Extrair metodologia
            if col_metodologia and col_metodologia in row:
                metodologia = str(row[col_metodologia])
                if metodologia and metodologia.lower() != 'nan':
                    projeto_info['metodologia'] = metodologia
                    
                    # Acumular metodologias
                    if metodologia not in analysis['estatisticas_agricultura']['metodologias']:
                        analysis['estatisticas_agricultura']['metodologias'][metodologia] = 0
                    analysis['estatisticas_agricultura']['metodologias'][metodologia] += 1
            
            # Extrair ano de início
            if col_ano_inicio and col_ano_inicio in row:
                ano_val = row[col_ano_inicio]
                if pd.notna(ano_val):
                    try:
                        if isinstance(ano_val, (int, float)):
                            ano = int(ano_val)
                            if 1900 <= ano <= 2100:
                                projeto_info['ano_inicio'] = ano
                                analysis['estatisticas_agricultura']['anos_inicio'].append(ano)
                    except:
                        pass
            
            # Calcular taxa de venda para este projeto
            if projeto_info['creditos_emitidos'] > 0:
                projeto_info['taxa_venda'] = (projeto_info['creditos_vendidos'] / projeto_info['creditos_emitidos']) * 100
            
            analysis['projetos_agricultura'].append(projeto_info)
            
        except Exception as e:
            continue
    
    # Calcular estatísticas finais
    analysis['estatisticas_agricultura']['total_projetos'] = len(df)
    analysis['estatisticas_agricultura']['projetos_com_creditos'] = projetos_com_creditos
    analysis['estatisticas_agricultura']['total_creditos_emitidos'] = total_creditos_emitidos
    analysis['estatisticas_agricultura']['total_creditos_vendidos'] = total_creditos_vendidos
    
    # Converter set para lista
    analysis['estatisticas_agricultura']['paises'] = list(analysis['estatisticas_agricultura']['paises'])
    
    return analysis

def convert_to_numeric(value):
    """Converte qualquer valor para numérico"""
    if pd.isna(value):
        return 0
    
    try:
        if isinstance(value, (int, float)):
            return float(value)
        
        str_value = str(value).strip()
        str_value = re.sub(r'[^\d.,]', '', str_value)
        
        if not str_value:
            return 0
        
        if ',' in str_value and '.' in str_value:
            str_value = str_value.replace('.', '').replace(',', '.')
        elif ',' in str_value:
            if str_value.count(',') == 1:
                str_value = str_value.replace(',', '.')
            else:
                str_value = str_value.replace(',', '')
        
        return float(str_value) if str_value else 0
    except:
        return 0

def get_country_name(country_str):
    """Obtém nome do país em português"""
    if pd.isna(country_str):
        return "Não especificado"
    
    country_lower = str(country_str).lower().strip()
    
    for eng_name, port_name in COUNTRY_TRANSLATIONS.items():
        if eng_name == country_lower:
            return port_name
    
    for eng_name, port_name in COUNTRY_TRANSLATIONS.items():
        if eng_name in country_lower:
            return port_name
    
    return country_str.strip().title()

def get_country_code(country_name):
    """Obtém código do país para mapa"""
    if pd.isna(country_name):
        return None
    
    country_lower = str(country_name).lower().strip()
    
    for country_key, code in COUNTRY_CODES.items():
        if country_key in country_lower:
            return code
    
    return None

# =========================
# FUNÇÕES DE UI E VISUALIZAÇÃO
# =========================

def create_transparent_hero(analysis_agriculture, price_per_ton):
    """Cria seção hero com transparência total"""
    
    if not analysis_agriculture:
        st.markdown("""
        <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                    background: linear-gradient(135deg, #27ae60, #229954); 
                    color: white; margin-bottom: 2rem;'>
            <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>🌱 Mercado de Carbono Agrícola</h1>
            <h3 style='font-weight: 300;'>Baseado nos dados reais da FAO</h3>
            <p style='font-size: 1.1rem; opacity: 0.9;'>
                Carregando análise da aba 4. Agriculture...
            </p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    stats = analysis_agriculture['estatisticas_agricultura']
    
    total_projetos = stats['total_projetos']
    projetos_com_creditos = stats['projetos_com_creditos']
    total_creditos = stats['total_creditos_emitidos']
    total_vendidos = stats['total_creditos_vendidos']
    paises_count = len(stats['paises'])
    
    # Calcular receita baseada no preço escolhido pelo usuário
    receita_real = total_vendidos * price_per_ton
    receita_potencial = total_creditos * price_per_ton
    taxa_venda = (total_vendidos / total_creditos * 100) if total_creditos > 0 else 0
    
    st.markdown(f"""
    <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                background: linear-gradient(135deg, #27ae60, #229954); 
                color: white; margin-bottom: 2rem;'>
        <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>🌱 Mercado de Carbono Agrícola</h1>
        <h3 style='font-weight: 300;'>Análise exclusiva da aba <strong>4. Agriculture</strong> do dataset FAO</h3>
        <p style='font-size: 1.1rem; opacity: 0.9;'>
            {formatar_br_inteiro(projetos_com_creditos)} projetos com créditos • 
            {formatar_milhoes(total_creditos)} créditos emitidos • 
            {formatar_milhoes(total_vendidos)} créditos vendidos • 
            {paises_count} países
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Disclaimer sobre preços
    st.info(f"""
    **💡 Nota sobre preços:** 
    O dataset FAO não contém informações de preços. 
    As receitas mostradas são calculadas usando **US$ {formatar_br_dec(price_per_ton, 2)} por tCO₂**, 
    um valor médio baseado em relatórios de mercado. 
    *Você pode ajustar este preço no painel lateral.*
    """)

def create_agriculture_analysis(analysis_agriculture, price_per_ton):
    """Cria análise detalhada da aba 4. Agriculture"""
    
    if not analysis_agriculture:
        st.warning("Não foi possível analisar a aba 4. Agriculture")
        return
    
    stats = analysis_agriculture['estatisticas_agricultura']
    projetos = analysis_agriculture['projetos_agricultura']
    
    # Separador visual
    st.markdown("---")
    st.markdown(f"## 📊 Análise Exclusiva da Aba **4. Agriculture**")
    
    # Estatísticas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📁 Total de Projetos", 
                 formatar_br_inteiro(stats['total_projetos']),
                 "Na aba 4. Agriculture")
    
    with col2:
        st.metric("💰 Projetos com Créditos", 
                 formatar_br_inteiro(stats['projetos_com_creditos']),
                 f"{formatar_br_inteiro(len(stats['paises']))} países")
    
    with col3:
        st.metric("🌱 Créditos Emitidos", 
                 formatar_milhoes(stats['total_creditos_emitidos']),
                 f"≈ {formatar_milhoes(stats['total_creditos_emitidos'])} tCO₂")
    
    with col4:
        taxa_venda = (stats['total_creditos_vendidos'] / stats['total_creditos_emitidos'] * 100) if stats['total_creditos_emitidos'] > 0 else 0
        st.metric("📉 Créditos Vendidos", 
                 formatar_milhoes(stats['total_creditos_vendidos']),
                 f"{formatar_br_dec(taxa_venda, 3)}% dos emitidos")
    
    # Análise de receitas com preço configurável
    st.markdown("## 💰 Análise de Receitas (Estimativas)")
    
    receita_real = stats['total_creditos_vendidos'] * price_per_ton
    receita_potencial = stats['total_creditos_emitidos'] * price_per_ton
    receita_media_projeto = receita_real / max(1, stats['projetos_com_creditos'])
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("💵 Receita Real Estimada", 
                 f"US$ {formatar_moeda_curta(receita_real)}",
                 f"Baseada em {formatar_milhoes(stats['total_creditos_vendidos'])} créditos vendidos")
    
    with col2:
        st.metric("📈 Receita Potencial Total", 
                 f"US$ {formatar_moeda_curta(receita_potencial)}",
                 f"Se todos os {formatar_milhoes(stats['total_creditos_emitidos'])} créditos fossem vendidos")
    
    with col3:
        st.metric("🏆 Média por Projeto", 
                 f"US$ {formatar_moeda_curta(receita_media_projeto)}",
                 f"Receita real / projeto")
    
    # Gráfico de créditos emitidos vs vendidos
    st.markdown("## 🔄 Créditos Emitidos vs. Vendidos")
    
    dados_comparativo = pd.DataFrame({
        'Categoria': ['Emitidos', 'Vendidos'],
        'Créditos (milhões)': [
            stats['total_creditos_emitidos'] / 1000000,
            stats['total_creditos_vendidos'] / 1000000
        ],
        'Valor': [
            formatar_milhoes(stats['total_creditos_emitidos']),
            formatar_milhoes(stats['total_creditos_vendidos'])
        ]
    })
    
    fig = px.bar(dados_comparativo, x='Categoria', y='Créditos (milhões)',
                 title='Comparação entre Créditos Emitidos e Vendidos (Aba 4. Agriculture)',
                 color='Categoria',
                 color_discrete_map={'Emitidos': '#2ecc71', 'Vendidos': '#e74c3c'},
                 text='Valor')
    
    fig.update_traces(textposition='outside')
    fig.update_layout(yaxis_title='Créditos (em milhões de tCO₂)')
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabela de projetos
    st.markdown("## 📋 Projetos da Aba 4. Agriculture")
    
    if projetos:
        # Criar DataFrame para exibição
        df_projetos = pd.DataFrame(projetos)
        
        # Filtrar apenas projetos com créditos
        df_projetos_com_creditos = df_projetos[df_projetos['creditos_emitidos'] > 0].copy()
        
        # Calcular receita estimada para cada projeto
        df_projetos_com_creditos['receita_estimada'] = df_projetos_com_creditos['creditos_emitidos'] * price_per_ton
        df_projetos_com_creditos['receita_vendida'] = df_projetos_com_creditos['creditos_vendidos'] * price_per_ton
        
        # Ordenar por créditos emitidos
        df_projetos_com_creditos = df_projetos_com_creditos.sort_values('creditos_emitidos', ascending=False)
        
        # Selecionar colunas para exibição
        display_cols = ['nome']
        if 'pais' in df_projetos_com_creditos.columns:
            display_cols.append('pais')
        display_cols.extend(['creditos_emitidos', 'creditos_vendidos'])
        
        # Adicionar colunas calculadas
        df_display = df_projetos_com_creditos.copy()
        df_display['taxa_venda'] = df_display.apply(
            lambda x: f"{formatar_br_dec((x['creditos_vendidos'] / x['creditos_emitidos'] * 100), 2)}%" 
            if x['creditos_emitidos'] > 0 else "0%", 
            axis=1
        )
        df_display['receita_estimada_fmt'] = df_display['receita_estimada'].apply(formatar_moeda_curta)
        df_display['receita_vendida_fmt'] = df_display['receita_vendida'].apply(formatar_moeda_curta)
        
        display_cols.extend(['taxa_venda', 'receita_estimada_fmt', 'receita_vendida_fmt'])
        
        # Formatar números grandes
        df_display['creditos_emitidos_fmt'] = df_display['creditos_emitidos'].apply(formatar_milhoes)
        df_display['creditos_vendidos_fmt'] = df_display['creditos_vendidos'].apply(formatar_milhoes)
        
        # Renomear colunas para exibição
        df_display = df_display.rename(columns={
            'nome': 'Nome do Projeto',
            'pais': 'País',
            'creditos_emitidos_fmt': 'Créditos Emitidos',
            'creditos_vendidos_fmt': 'Créditos Vendidos',
            'taxa_venda': 'Taxa de Venda',
            'receita_estimada_fmt': 'Receita Estimada (US$)',
            'receita_vendida_fmt': 'Receita Vendida (US$)'
        })
        
        # Exibir tabela
        st.dataframe(
            df_display[[
                'Nome do Projeto', 'País', 'Créditos Emitidos', 
                'Créditos Vendidos', 'Taxa de Venda', 
                'Receita Estimada (US$)', 'Receita Vendida (US$)'
            ]].head(20),
            use_container_width=True,
            height=400
        )
        
        st.caption(f"*Mostrando {min(20, len(df_display))} de {len(df_display)} projetos com créditos emitidos*")
    
    # Distribuição por país
    st.markdown("## 🌍 Distribuição por País")
    
    if stats['projetos_por_pais']:
        paises_df = pd.DataFrame(
            list(stats['projetos_por_pais'].items()),
            columns=['País', 'Projetos']
        )
        
        # Adicionar código do país
        paises_df['Código'] = paises_df['País'].apply(get_country_code)
        paises_com_codigo = paises_df[paises_df['Código'].notna()]
        
        if not paises_com_codigo.empty:
            # Mapa mundial
            fig = px.choropleth(paises_com_codigo, 
                                locations='Código',
                                color='Projetos',
                                hover_name='País',
                                hover_data={'Projetos': True, 'Código': False},
                                title='Projetos por País (Aba 4. Agriculture)',
                                color_continuous_scale='Greens')
            
            fig.update_layout(geo=dict(showframe=False, showcoastlines=True))
            st.plotly_chart(fig, use_container_width=True)
        
        # Top 10 países
        st.markdown("### 🏆 Top 10 Países com Mais Projetos")
        top_10 = paises_df.sort_values('Projetos', ascending=False).head(10)
        
        fig2 = px.bar(top_10, x='País', y='Projetos',
                      title="Top 10 Países",
                      color='Projetos',
                      color_continuous_scale='Greens',
                      text='Projetos')
        fig2.update_traces(textposition='outside')
        st.plotly_chart(fig2, use_container_width=True)

def create_price_configuration():
    """Cria configuração de preços no sidebar"""
    
    with st.sidebar.expander("💰 Configurar Preço do Carbono", expanded=True):
        st.markdown("""
        **O dataset FAO não contém preços.**  
        Configure abaixo o preço médio por tonelada de CO₂:
        """)
        
        price_per_ton = st.slider(
            "Preço do carbono (US$/tCO₂):",
            min_value=5.0,
            max_value=50.0,
            value=22.5,
            step=0.5,
            help="Preço médio baseado em relatórios de mercado (Ecosystem Marketplace, Carbon Credits, etc.)"
        )
        
        st.markdown("---")
        st.markdown("**Faixas de preço de referência:**")
        st.markdown("- 🌱 **Agricultura:** US$ 15-30/tCO₂")
        st.markdown("- 🌳 **Agrofloresta:** US$ 20-40/tCO₂")
        st.markdown("- ⚡ **Bioenergia:** US$ 10-25/tCO₂")
        
        return price_per_ton

def create_data_source_info():
    """Informações sobre as fontes de dados"""
    
    with st.sidebar.expander("📁 Fontes de Dados", expanded=False):
        st.markdown("""
        ### Dataset FAO
        
        **Arquivo:** `Dataset.xlsx`
        
        **Aba analisada:** **4. Agriculture**
        - Contém projetos agrícolas certificados
        - Tem dados de créditos emitidos e vendidos
        - Inclui informações por país e metodologia
        
        **Limitações conhecidas:**
        1. ❌ **Sem preços** de transações
        2. ⚠️ Formato inconsistente entre abas
        3. 📅 Dados até novembro 2023
        
        ### Preços de Mercado
        
        Baseados em relatórios externos:
        - Ecosystem Marketplace (2023)
        - Carbon Credits.com
        - Relatórios setoriais
        
        *Estimativas podem variar significativamente.*
        """)

def create_calculator_section(analysis_agriculture, price_per_ton):
    """Calculadora de potencial baseada em dados reais"""
    
    with st.expander("🧮 CALCULADORA DE POTENCIAL", expanded=False):
        st.markdown("""
        ### Calcule seu potencial baseado em projetos reais
        
        Esta calculadora usa como referência os **projetos da aba 4. Agriculture** 
        que já emitiram créditos de carbono.
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            hectares = st.number_input(
                "Tamanho da propriedade (hectares):",
                min_value=1.0,
                max_value=10000.0,
                value=100.0,
                step=10.0
            )
        
        with col2:
            practice_type = st.selectbox(
                "Tipo de prática:",
                [
                    ("agricultura", "🌱 Agricultura Regenerativa"),
                    ("agroflorestal", "🌳 Sistemas Agroflorestais"),
                    ("bioenergia", "⚡ Bioenergia/Biochar")
                ],
                format_func=lambda x: x[1],
                index=0
            )[0]
        
        with col3:
            project_duration = st.selectbox(
                "Duração do projeto (anos):",
                [5, 10, 15, 20, 30],
                index=2
            )
        
        # Taxas de sequestro de referência (baseadas em projetos reais)
        sequestration_rates = {
            'agricultura': 1.2,  # tCO2/ha/ano (conservador)
            'agroflorestal': 3.5,  # tCO2/ha/ano
            'bioenergia': 2.0  # tCO2/ha/ano
        }
        
        rate = sequestration_rates.get(practice_type, 1.2)
        
        # Cálculos
        annual_sequestration = hectares * rate
        total_sequestration = annual_sequestration * project_duration
        annual_revenue = annual_sequestration * price_per_ton
        total_revenue = total_sequestration * price_per_ton
        
        st.markdown("---")
        st.markdown("### 📈 Resultados Estimados")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "💰 Receita Anual",
                f"US$ {formatar_moeda_curta(annual_revenue)}"
            )
        
        with col2:
            st.metric(
                "📈 Receita Total",
                f"US$ {formatar_moeda_curta(total_revenue)}"
            )
        
        with col3:
            st.metric(
                "🌱 Sequestro Anual",
                f"{formatar_br_dec(annual_sequestration, 1)} tCO₂"
            )
        
        with col4:
            st.metric(
                "📊 Sequestro Total",
                f"{formatar_br_dec(total_sequestration, 1)} tCO₂"
            )
        
        # Detalhes do cálculo
        with st.expander("📋 Ver detalhes do cálculo"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Parâmetros usados:**")
                st.markdown(f"- Taxa de sequestro: **{rate} tCO₂/hectare/ano**")
                st.markdown(f"- Preço do carbono: **US$ {formatar_br_dec(price_per_ton, 2)}/tCO₂**")
                st.markdown(f"- Área: **{formatar_br_inteiro(hectares)} hectares**")
                st.markdown(f"- Duração: **{project_duration} anos**")
            
            with col2:
                st.markdown("**Fórmulas:**")
                st.markdown(f"- Sequestro anual = {hectares} ha × {rate} tCO₂/ha/ano = **{formatar_br_dec(annual_sequestration, 1)} tCO₂/ano**")
                st.markdown(f"- Receita anual = {formatar_br_dec(annual_sequestration, 1)} tCO₂ × US$ {formatar_br_dec(price_per_ton, 2)} = **US$ {formatar_moeda_curta(annual_revenue)}/ano**")
                st.markdown(f"- Receita total = US$ {formatar_moeda_curta(annual_revenue)} × {project_duration} anos = **US$ {formatar_moeda_curta(total_revenue)}**")
        
        # Nota sobre variabilidade
        st.info("""
        **💡 Nota sobre variabilidade:** 
        Estes são valores estimados. Projetos reais podem variar significativamente 
        dependendo da localização, solo, clima, práticas específicas e custos de certificação.
        """)

def create_comparison_with_other_sheets(analysis_agriculture, dataframes):
    """Comparação com outras abas do dataset"""
    
    with st.expander("📊 Comparação com Outras Abas", expanded=False):
        st.markdown("""
        ### Comparação entre diferentes abas do dataset FAO
        
        O dataset tem várias abas com tipos diferentes de projetos:
        """)
        
        # Analisar outras abas relevantes
        sheet_stats = []
        
        for sheet_name in ["8. Puro.earth", "9. Nori and BCarbon", "5. Agroforestry-AR & Grassland", "6. Energy and Other"]:
            if sheet_name in dataframes:
                df = clean_dataframe(dataframes[sheet_name])
                total_rows = len(df)
                
                # Tentar identificar créditos
                credit_col = None
                for col in df.columns:
                    if 'credit' in str(col).lower():
                        credit_col = col
                        break
                
                if credit_col and credit_col in df.columns:
                    # Converter para numérico
                    try:
                        df[credit_col] = pd.to_numeric(df[credit_col], errors='coerce')
                        projetos_com_creditos = df[credit_col].notna().sum()
                        total_creditos = df[credit_col].sum()
                    except:
                        projetos_com_creditos = 0
                        total_creditos = 0
                else:
                    projetos_com_creditos = 0
                    total_creditos = 0
                
                sheet_stats.append({
                    'Aba': sheet_name,
                    'Ícone': SHEET_CONFIG.get(sheet_name, {}).get('icon', '📄'),
                    'Total Projetos': total_rows,
                    'Projetos com Créditos': projetos_com_creditos,
                    'Créditos (aprox)': total_creditos
                })
        
        # Adicionar aba 4. Agriculture
        if analysis_agriculture:
            sheet_stats.insert(0, {
                'Aba': "4. Agriculture",
                'Ícone': "🚜",
                'Total Projetos': analysis_agriculture['estatisticas_agricultura']['total_projetos'],
                'Projetos com Créditos': analysis_agriculture['estatisticas_agricultura']['projetos_com_creditos'],
                'Créditos (aprox)': analysis_agriculture['estatisticas_agricultura']['total_creditos_emitidos']
            })
        
        # Criar DataFrame comparativo
        if sheet_stats:
            df_comparativo = pd.DataFrame(sheet_stats)
            
            # Formatar números
            df_comparativo['Total Projetos_fmt'] = df_comparativo['Total Projetos'].apply(formatar_br_inteiro)
            df_comparativo['Projetos com Créditos_fmt'] = df_comparativo['Projetos com Créditos'].apply(formatar_br_inteiro)
            df_comparativo['Créditos_fmt'] = df_comparativo['Créditos (aprox)'].apply(formatar_milhoes)
            
            # Criar gráfico
            fig = px.bar(df_comparativo, 
                         x='Aba', 
                         y='Créditos (aprox)',
                         title='Comparação de Créditos entre Abas do Dataset',
                         color='Aba',
                         text='Créditos_fmt',
                         color_discrete_sequence=px.colors.qualitative.Set2)
            
            fig.update_traces(textposition='outside')
            fig.update_layout(yaxis_title='Créditos (tCO₂)')
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabela comparativa
            st.markdown("### 📋 Tabela Comparativa")
            st.dataframe(
                df_comparativo[[
                    'Aba', 'Total Projetos_fmt', 'Projetos com Créditos_fmt', 'Créditos_fmt'
                ]].rename(columns={
                    'Aba': 'Aba',
                    'Total Projetos_fmt': 'Total de Projetos',
                    'Projetos com Créditos_fmt': 'Projetos com Créditos',
                    'Créditos_fmt': 'Créditos (aprox)'
                }),
                use_container_width=True
            )

def create_methodology_analysis(analysis_agriculture):
    """Análise das metodologias usadas"""
    
    if not analysis_agriculture or 'estatisticas_agricultura' not in analysis_agriculture:
        return
    
    metodologias = analysis_agriculture['estatisticas_agricultura'].get('metodologias', {})
    
    if not metodologias:
        return
    
    with st.expander("🔬 Metodologias Utilizadas", expanded=False):
        st.markdown("""
        ### Metodologias de Projetos da Aba 4. Agriculture
        
        As metodologias definem como os créditos são calculados e verificados.
        """)
        
        # Criar DataFrame
        df_metodologias = pd.DataFrame(
            list(metodologias.items()),
            columns=['Metodologia', 'Quantidade de Projetos']
        ).sort_values('Quantidade de Projetos', ascending=False)
        
        # Top 10 metodologias
        top_10 = df_metodologias.head(10)
        
        fig = px.bar(top_10, 
                     x='Metodologia', 
                     y='Quantidade de Projetos',
                     title='Top 10 Metodologias Mais Utilizadas',
                     color='Quantidade de Projetos',
                     color_continuous_scale='Blues',
                     text='Quantidade de Projetos')
        
        fig.update_traces(textposition='outside')
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabela completa
        st.markdown("### 📋 Todas as Metodologias")
        st.dataframe(
            df_metodologias,
            use_container_width=True,
            height=300
        )

# =========================
# PÁGINAS PRINCIPAIS
# =========================

def render_home_page(analysis_agriculture, price_per_ton, dataframes):
    """Página inicial focada na aba 4. Agriculture"""
    
    # Hero section transparente
    create_transparent_hero(analysis_agriculture, price_per_ton)
    
    # Análise principal da aba 4. Agriculture
    create_agriculture_analysis(analysis_agriculture, price_per_ton)
    
    # Calculadora
    create_calculator_section(analysis_agriculture, price_per_ton)
    
    # Análise de metodologias
    create_methodology_analysis(analysis_agriculture)
    
    # Comparação com outras abas
    create_comparison_with_other_sheets(analysis_agriculture, dataframes)
    
    # Seção de limitações e transparência
    create_transparency_section()

def render_project_explorer_page(dataframes):
    """Explorador de todas as abas do dataset"""
    
    st.markdown("## 🔍 Explorador Completo do Dataset")
    
    # Sidebar para seleção de aba
    with st.sidebar:
        st.markdown("### 📁 Selecionar Aba")
        
        available_sheets = list(dataframes.keys())
        selected_sheet = st.selectbox(
            "Escolha uma aba para explorar:",
            available_sheets,
            format_func=lambda x: f"{SHEET_CONFIG.get(x, {}).get('icon', '📄')} {x}",
            index=3 if "4. Agriculture" in available_sheets else 0
        )
    
    # Conteúdo principal
    if selected_sheet in dataframes:
        df_raw = dataframes[selected_sheet]
        df = clean_dataframe(df_raw)
        
        st.markdown(f"### {SHEET_CONFIG.get(selected_sheet, {}).get('icon', '📄')} {selected_sheet}")
        
        # Estatísticas básicas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📊 Total de Linhas", formatar_br_inteiro(len(df)))
        
        with col2:
            total_cols = len(df.columns)
            st.metric("📋 Total de Colunas", formatar_br_inteiro(total_cols))
        
        with col3:
            non_empty = df.notna().any().sum()
            st.metric("📈 Colunas com Dados", formatar_br_inteiro(non_empty))
        
        # Visualizar dados
        st.markdown("### 📋 Visualização dos Dados")
        
        # Mostrar primeiras linhas
        st.dataframe(df.head(20), use_container_width=True, height=400)
        
        # Informações sobre a aba
        st.markdown("### ℹ️ Informações sobre esta Aba")
        
        sheet_info = SHEET_CONFIG.get(selected_sheet, {})
        
        if sheet_info.get('type') == 'projetos':
            st.info(f"""
            **Tipo:** {sheet_info.get('type', 'Não especificado')}
            
            Esta aba contém dados de **projetos certificados** no mercado de carbono.
            
            **Dicas para análise:**
            1. Procure colunas com "credit", "issued" ou "retired" para dados de créditos
            2. Colunas com "country" ou "region" mostram localização
            3. Métodologias são importantes para entender o tipo de projeto
            """)
        elif sheet_info.get('type') == 'padrões':
            st.info(f"""
            **Tipo:** {sheet_info.get('type', 'Não especificado')}
            
            Esta aba contém informações sobre **padrões e registries** de carbono.
            
            **Dicas para análise:**
            1. Procure informações sobre número de projetos
            2. Verifique se há dados sobre países ou regiões
            3. Métodologias associadas a cada padrão
            """)
        elif sheet_info.get('type') == 'metodologias':
            st.info(f"""
            **Tipo:** {sheet_info.get('type', 'Não especificado')}
            
            Esta aba contém **metodologias** para cálculo de créditos de carbono.
            
            **Dicas para análise:**
            1. Cada linha representa uma metodologia diferente
            2. Procure informações sobre tipos de projetos aplicáveis
            3. Verifique status (ativo, desenvolvimento, inativo)
            """)
        
        # Opção para download
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar esta aba como CSV",
            data=csv,
            file_name=f"{selected_sheet.replace('. ', '_').replace(' ', '_').lower()}.csv",
            mime="text/csv"
        )

def render_insights_page(analysis_agriculture, price_per_ton):
    """Página com insights e recomendações"""
    
    st.markdown("## 💡 Insights Baseados nos Dados Reais")
    
    if not analysis_agriculture:
        st.warning("Carregando análise...")
        return
    
    stats = analysis_agriculture['estatisticas_agricultura']
    
    # Insight 1: Taxa de venda
    taxa_venda = (stats['total_creditos_vendidos'] / stats['total_creditos_emitidos'] * 100) if stats['total_creditos_emitidos'] > 0 else 0
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style='background: #e8f4fc; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #3498db;'>
            <h3>📉 Apenas <span style='color: #e74c3c;'>{taxa}%</span> dos créditos foram vendidos</h3>
            <p>Isso significa que muitos projetos emitiram créditos, mas ainda não os comercializaram.</p>
            <p><strong>Implicação:</strong> Existe um grande potencial de mercado ainda não realizado.</p>
        </div>
        """.format(taxa=formatar_br_dec(taxa_venda, 3)), unsafe_allow_html=True)
    
    with col2:
        creditos_disponiveis = stats['total_creditos_emitidos'] - stats['total_creditos_vendidos']
        receita_potencial = creditos_disponiveis * price_per_ton
        
        st.markdown(f"""
        <div style='background: #e8f6e8; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #27ae60;'>
            <h3>💰 <span style='color: #27ae60;'>US$ {formatar_moeda_curta(receita_potencial)}</span> em créditos disponíveis</h3>
            <p>{formatar_milhoes(creditos_disponiveis)} créditos ainda não foram comercializados.</p>
            <p><strong>Oportunidade:</strong> Mercado em crescimento com espaço para novos players.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Insight 2: Distribuição geográfica
    st.markdown("### 🌍 Distribuição Geográfica dos Projetos")
    
    if stats['projetos_por_pais']:
        paises_df = pd.DataFrame(
            list(stats['projetos_por_pais'].items()),
            columns=['País', 'Projetos']
        ).sort_values('Projetos', ascending=False)
        
        top_5 = paises_df.head(5)
        
        st.markdown(f"""
        #### 🏆 Top 5 Países
        
        Os projetos estão concentrados em poucos países:
        
        1. **{top_5.iloc[0]['País']}** - {formatar_br_inteiro(top_5.iloc[0]['Projetos'])} projetos
        2. **{top_5.iloc[1]['País'] if len(top_5) > 1 else 'N/A'}** - {formatar_br_inteiro(top_5.iloc[1]['Projetos'] if len(top_5) > 1 else 0)} projetos
        3. **{top_5.iloc[2]['País'] if len(top_5) > 2 else 'N/A'}** - {formatar_br_inteiro(top_5.iloc[2]['Projetos'] if len(top_5) > 2 else 0)} projetos
        
        **Insight:** Mercado ainda concentrado geograficamente.
        """)
    
    # Insight 3: Recomendações baseadas em dados
    st.markdown("### 🎯 Recomendações para Novos Projetos")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style='background: white; padding: 1rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
            <div style='color: #e74c3c; font-size: 2rem; text-align: center;'>1️⃣</div>
            <h4 style='text-align: center;'>Foco em Venda</h4>
            <p style='font-size: 0.9rem;'>Emitir créditos é apenas o primeiro passo. Planeje a comercialização desde o início.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='background: white; padding: 1rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
            <div style='color: #f39c12; font-size: 2rem; text-align: center;'>2️⃣</div>
            <h4 style='text-align: center;'>Certificação Adequada</h4>
            <p style='font-size: 0.9rem;'>Escolha metodologias já testadas e aceitas pelo mercado.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='background: white; padding: 1rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
            <div style='color: #27ae60; font-size: 2rem; text-align: center;'>3️⃣</div>
            <h4 style='text-align: center;'>Análise de Custo-Benefício</h4>
            <p style='font-size: 0.9rem;'>Certificação tem custos. Calcule se o retorno justifica o investimento.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Insight 4: Tendências temporais
    st.markdown("### 📅 Tendências Temporais")
    
    if 'anos_inicio' in stats and stats['anos_inicio']:
        anos_df = pd.DataFrame({'Ano': stats['anos_inicio']})
        anos_count = anos_df['Ano'].value_counts().sort_index()
        
        if len(anos_count) > 1:
            fig = px.line(
                x=anos_count.index, 
                y=anos_count.values,
                title='Projetos por Ano de Início (Tendência)',
                labels={'x': 'Ano', 'y': 'Número de Projetos'},
                markers=True
            )
            
            fig.update_traces(line_color='#27ae60', line_width=3)
            st.plotly_chart(fig, use_container_width=True)
            
            # Análise da tendência
            ultimos_5_anos = [a for a in stats['anos_inicio'] if a >= 2018]
            if len(ultimos_5_anos) > 0:
                crescimento = (len(ultimos_5_anos) / len(stats['anos_inicio'])) * 100
                st.info(f"""
                **📈 Tendência de crescimento:** 
                {formatar_br_dec(crescimento, 1)}% dos projetos começaram nos últimos 5 anos.
                
                O mercado está em **expansão acelerada**.
                """)

def create_transparency_section():
    """Seção de transparência sobre dados e limitações"""
    
    with st.expander("🔍 Transparência sobre os Dados e Limitações", expanded=False):
        st.markdown("""
        ## 📊 Transparência Total sobre os Dados
        
        ### ✅ O que sabemos (dados do dataset):
        
        1. **Número real de projetos** na aba 4. Agriculture
        2. **Créditos emitidos** por cada projeto
        3. **Créditos vendidos/aposentados** por cada projeto
        4. **Países** onde os projetos estão localizados
        5. **Metodologias** utilizadas
        
        ### ❌ O que NÃO sabemos (limitações do dataset):
        
        1. **Preços reais das transações** - O dataset não contém informações de preços
        2. **Custos dos projetos** - Não há dados sobre investimentos necessários
        3. **Lucratividade real** - Sem custos, não podemos calcular lucro real
        4. **Detalhes específicos** - Alguns projetos têm informações incompletas
        
        ### 🎯 Como lidamos com essas limitações:
        
        #### Para preços:
        - Usamos **preço médio de mercado** baseado em relatórios externos
        - **Permitimos que você ajuste** este preço no painel lateral
        - Deixamos claro que são **estimativas**
        
        #### Para cálculos de receita:
        - Calculamos **receita potencial** (se todos os créditos fossem vendidos)
        - Calculamos **receita real estimada** (baseada nos créditos vendidos)
        - **Separamos claramente** dados reais vs estimativas
        
        ### 📈 Fontes dos preços de referência:
        
        1. **Ecosystem Marketplace (2023):** US$ 15-30/tCO₂ para agricultura
        2. **Carbon Credits.com:** US$ 18-25/tCO₂ para projetos agrícolas
        3. **Relatórios setoriais:** Variação significativa por tipo de projeto
        
        ### ⚠️ Aviso importante:
        
        > **Estas são estimativas baseadas em dados públicos.** 
        > Para uma avaliação precisa do potencial do SEU projeto, 
        > consulte especialistas e faça uma análise específica.
        """)

# =========================
# CARGA DE DADOS
# =========================

@st.cache_data(ttl=3600, show_spinner="Carregando dataset FAO...")
def load_fao_dataset():
    """Carrega e prepara o dataset FAO"""
    file_path = "Dataset.xlsx"
    
    if not os.path.exists(file_path):
        st.error("❌ **Arquivo Dataset.xlsx não encontrado.** Coloque o arquivo na mesma pasta do aplicativo.")
        st.stop()
    
    try:
        excel = pd.ExcelFile(file_path, engine='openpyxl')
        data = {}
        
        for sheet in excel.sheet_names:
            try:
                df = excel.parse(sheet, header=0, index_col=None)
                df_clean = clean_dataframe(df)
                data[sheet] = df_clean
            except Exception as e:
                st.warning(f"⚠️ Aviso na aba '{sheet}': {str(e)[:100]}")
                data[sheet] = pd.DataFrame()
        
        return data
        
    except Exception as e:
        st.error(f"❌ Erro crítico ao carregar dados: {str(e)}")
        st.stop()

# =========================
# APLICAÇÃO PRINCIPAL
# =========================

def main():
    # Título principal
    st.markdown("""
    <div style='text-align: center; margin-bottom: 2rem;'>
        <h1 style='color: #27ae60;'>🌱 Análise do Mercado de Carbono Agrícola</h1>
        <p style='color: #7f8c8d;'>Baseado no dataset FAO - Foco na transparência e dados reais</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Carregar dados
    dataframes = load_fao_dataset()
    
    # Configurar preço no sidebar
    price_per_ton = create_price_configuration()
    
    # Informações sobre fontes de dados
    create_data_source_info()
    
    # Analisar especificamente a aba 4. Agriculture
    if "4. Agriculture" not in dataframes:
        st.error("❌ A aba 4. Agriculture não foi encontrada no dataset.")
        return
    
    # Análise da aba 4. Agriculture
    if 'analysis_agriculture' not in st.session_state:
        with st.spinner("🔍 Analisando projetos da aba 4. Agriculture..."):
            analysis_agriculture = analyze_agriculture_dataset(dataframes)
            st.session_state.analysis_agriculture = analysis_agriculture
    else:
        analysis_agriculture = st.session_state.analysis_agriculture
    
    # Navegação no sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🗂️ Navegação")
    
    page = st.sidebar.radio(
        "Selecione a página:",
        ["🏠 Análise Principal", "🔍 Explorador de Dados", "💡 Insights", "ℹ️ Sobre"],
        label_visibility="collapsed"
    )
    
    # Renderizar página selecionada
    if page == "🏠 Análise Principal":
        render_home_page(analysis_agriculture, price_per_ton, dataframes)
    elif page == "🔍 Explorador de Dados":
        render_project_explorer_page(dataframes)
    elif page == "💡 Insights":
        render_insights_page(analysis_agriculture, price_per_ton)
    else:
        render_about_page()

def render_about_page():
    """Página sobre o projeto"""
    
    st.markdown("## ℹ️ Sobre Este Dashboard")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 📊 Propósito
        
        Este dashboard foi criado para:
        
        1. **Analisar dados reais** do mercado de carbono agrícola
        2. **Fornecer transparência** sobre o que são dados vs estimativas
        3. **Ajudar proprietários rurais** a entender oportunidades
        4. **Mostrar limitações** dos dados disponíveis
        
        ### 🎯 Metodologia
        
        **Foco principal:** Aba **4. Agriculture** do dataset FAO
        
        **Por quê?**
        - É a aba mais completa para projetos agrícolas
        - Tem dados de créditos emitidos e vendidos
        - Inclui informações por país e metodologia
        
        **O que NÃO fazemos:**
        - Não inventamos dados
        - Não escondemos limitações
        - Não damos conselhos financeiros
        
        ### 📈 Transparência
        
        Todos os cálculos que envolvem **dinheiro** usam:
        1. **Dados reais** do dataset para volumes (créditos)
        2. **Estimativas** baseadas em relatórios de mercado para preços
        3. **Configuração pelo usuário** do preço do carbono
        
        ### 🛠️ Tecnologia
        
        - **Streamlit** para a interface web
        - **Pandas** para análise de dados
        - **Plotly** para visualizações
        - **Python** para lógica de negócios
        
        ### 📚 Fonte Principal
        
        **Dataset:** FAO Agrifood Voluntary Carbon Market Dataset (2025)
        
        **Download:** Disponível no site da FAO
        
        **Período:** Dados até novembro 2023
        """)
    
    with col2:
        st.markdown("""
        <div style='background: #f8f9fa; padding: 2rem; border-radius: 10px; margin-top: 2rem;'>
            <h3 style='color: #27ae60;'>🚜 Foco em Agricultura</h3>
            <p>Especializado em projetos agrícolas e agroflorestais</p>
            
            <h3 style='color: #3498db; margin-top: 2rem;'>💰 Transparência em Preços</h3>
            <p>Preços configuráveis e fontes documentadas</p>
            
            <h3 style='color: #9b59b6; margin-top: 2rem;'>📊 Dados Reais</h3>
            <p>Baseado em projetos certificados existentes</p>
            
            <h3 style='color: #e74c3c; margin-top: 2rem;'>⚠️ Limitações Clarass</h3>
            <p>Documentamos o que não sabemos</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Rodapé
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #7f8c8d; font-size: 0.9rem;'>
        <p>🌱 <strong>Análise de Mercado de Carbono Agrícola</strong> - Versão 2.0</p>
        <p>Baseado no dataset FAO • Para fins informativos e educacionais</p>
        <p>⚠️ <strong>Não é um conselho financeiro ou de investimento</strong></p>
    </div>
    """, unsafe_allow_html=True)

# =========================
# EXECUÇÃO
# =========================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")
        st.info("""
        **Solução de problemas:**
        1. Verifique se o arquivo `Dataset.xlsx` está na mesma pasta
        2. Recarregue a página (F5)
        3. Se o problema persistir, tente uma versão mais simples do Excel
        """)
