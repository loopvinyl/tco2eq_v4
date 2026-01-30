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
import locale

warnings.filterwarnings("ignore")

# Configurar locale para Brasil (mas manter ponto como separador de milhar)
# locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Mercado de Carbono para Propriedades Rurais - FAO",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.fao.org/climate-change/our-work/carbon-markets',
        'Report a bug': None,
        'About': "Dashboard baseado em dados reais da FAO para proprietários rurais."
    }
)

# =========================
# FUNÇÕES DE FORMATAÇÃO BRASILEIRA
# =========================

def formatar_numero_br(valor, casas_decimais=0, prefixo="", sufixo=""):
    """
    Formata números no padrão brasileiro: 1.234.567,89
    
    Args:
        valor: Número a ser formatado
        casas_decimais: Número de casas decimais
        prefixo: Prefixo (ex: "R$", "US$")
        sufixo: Sufixo (ex: "ha", "tCO2")
    
    Returns:
        String formatada no padrão brasileiro
    """
    if valor is None or pd.isna(valor):
        return f"{prefixo} - {sufixo}".strip()
    
    try:
        # Converter para float se for string
        if isinstance(valor, str):
            # Tentar converter string no formato brasileiro para float
            valor = float(valor.replace('.', '').replace(',', '.'))
        
        # Arredondar para o número de casas decimais
        valor_arredondado = round(float(valor), casas_decimais)
        
        # Formatar parte inteira com separadores de milhar
        parte_inteira = int(abs(valor_arredondado))
        parte_inteira_str = f"{parte_inteira:,}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        # Adicionar parte decimal se necessário
        if casas_decimais > 0:
            parte_decimal = abs(valor_arredondado) - parte_inteira
            parte_decimal_str = f"{parte_decimal:.{casas_decimais}f}"[2:]  # Remove "0."
            
            # Garantir que tenha o número correto de casas
            if len(parte_decimal_str) < casas_decimais:
                parte_decimal_str = parte_decimal_str.ljust(casas_decimais, '0')
            
            numero_formatado = f"{parte_inteira_str},{parte_decimal_str}"
        else:
            numero_formatado = parte_inteira_str
        
        # Adicionar sinal negativo se necessário
        if valor_arredondado < 0:
            numero_formatado = f"-{numero_formatado}"
        
        # Adicionar prefixo e sufixo
        resultado = f"{prefixo}{numero_formatado}"
        if sufixo:
            resultado = f"{resultado} {sufixo}"
        
        return resultado
        
    except Exception:
        return f"{prefixo}-{sufixo}".strip()

def formatar_moeda_br(valor, moeda="US$"):
    """Formata valores monetários no padrão brasileiro"""
    return formatar_numero_br(valor, casas_decimais=2, prefixo=f"{moeda} ")

def formatar_area_br(valor):
    """Formata áreas em hectares no padrão brasileiro"""
    return formatar_numero_br(valor, casas_decimais=1, sufixo="ha")

def formatar_toneladas_br(valor):
    """Formata toneladas de CO2 no padrão brasileiro"""
    return formatar_numero_br(valor, casas_decimais=1, sufixo="tCO₂")

def formatar_percentual_br(valor, casas_decimais=1):
    """Formata percentuais no padrão brasileiro"""
    return f"{formatar_numero_br(valor, casas_decimais)}%"

def parse_numero_br(numero_str):
    """
    Converte string no formato brasileiro para float
    
    Exemplos:
        "1.234,56" → 1234.56
        "1.234" → 1234.0
        "123,45" → 123.45
    """
    if pd.isna(numero_str):
        return None
    
    try:
        # Se já for número
        if isinstance(numero_str, (int, float)):
            return float(numero_str)
        
        # Converter string
        str_valor = str(numero_str).strip()
        
        # Remover símbolos não numéricos (exceto ponto, vírgula e negativo)
        str_valor = re.sub(r'[^\d.,\-]', '', str_valor)
        
        # Verificar se está vazio
        if not str_valor:
            return None
        
        # Verificar se tem separador decimal (vírgula)
        if ',' in str_valor:
            # Remover pontos de milhar
            str_valor = str_valor.replace('.', '')
            # Substituir vírgula decimal por ponto
            str_valor = str_valor.replace(',', '.')
        
        # Converter para float
        return float(str_valor)
        
    except Exception:
        return None

# =========================
# CONSTANTES E CONFIGURAÇÕES
# =========================
SHEET_CONFIG = {
    "README": {"type": "documentação", "icon": "📖", "color": "#95a5a6"},
    "1. Standards": {"type": "padrões", "icon": "🏛️", "color": "#3498db", "main_column": "Name of standard/registry/platform"},
    "2. Platforms": {"type": "plataformas", "icon": "🖥️", "color": "#9b59b6", "main_column": "Platform"},
    "3. Methodologies": {"type": "metodologias", "icon": "🔬", "color": "#e74c3c", "main_column": "Data sourced from methodology document (see reference in column AD)"},
    "4. Agriculture": {"type": "projetos", "icon": "🚜", "color": "#2ecc71", "has_yearly_data": True, "country_column": "Country", "revenue_focus": True},
    "5. Agroforestry-AR & Grassland": {"type": "projetos", "icon": "🌳", "color": "#27ae60", "has_yearly_data": True, "country_column": "Country", "revenue_focus": True},
    "6. Energy and Other": {"type": "projetos", "icon": "⚡", "color": "#f39c12", "has_yearly_data": True, "country_column": "Country", "revenue_focus": True},
    "7. Plan Vivo, Acorn, Social C": {"type": "padrões", "icon": "🌍", "color": "#1abc9c", "main_column": "Standard", "country_column": "Country", "revenue_focus": True},
    "8. Puro.earth": {"type": "projetos", "icon": "🔥", "color": "#d35400", "main_column": "Unnamed: 0", "revenue_focus": True},
    "9. Nori and BCarbon": {"type": "projetos", "icon": "🌾", "color": "#16a085", "main_column": "Standard", "country_column": "Country", "revenue_focus": True}
}

# Traduções de países
COUNTRY_TRANSLATIONS = {
    'brazil': 'Brasil', 'brazilian': 'Brasil', 'brasil': 'Brasil',
    'united states': 'Estados Unidos', 'usa': 'Estados Unidos', 'us': 'Estados Unidos',
    'argentina': 'Argentina', 'chile': 'Chile', 'colombia': 'Colômbia',
    'uruguay': 'Uruguai', 'paraguay': 'Paraguai', 'mexico': 'México',
    'peru': 'Peru', 'bolivia': 'Bolívia', 'ecuador': 'Equador',
    'costarica': 'Costa Rica', 'panama': 'Panamá', 'australia': 'Austrália',
    'canada': 'Canadá', 'germany': 'Alemanha', 'france': 'França',
    'spain': 'Espanha', 'italy': 'Itália', 'portugal': 'Portugal',
    'china': 'China', 'india': 'Índia', 'indonesia': 'Indonésia',
    'vietnam': 'Vietnã', 'thailand': 'Tailândia', 'philippines': 'Filipinas',
    'malaysia': 'Malásia', 'southafrica': 'África do Sul', 'kenya': 'Quênia',
    'ethiopia': 'Etiópia', 'nigeria': 'Nigéria'
}

# =========================
# ANÁLISE COMPLETA DO DATASET
# =========================

@st.cache_data(ttl=3600, show_spinner="Analisando dataset FAO...")
def analyze_complete_dataset(dataframes):
    """Análise completa e estruturada de TODO o dataset"""
    
    analysis = {
        'estatisticas_gerais': {},
        'projetos_por_pais': {},
        'taxas_sequestro_reais': {},
        'casos_sucesso_reais': [],
        'precos_mercado': {},
        'categorias_projetos': {
            'agricultura': {'total': 0, 'creditos': 0, 'area_total': 0},
            'agroflorestal': {'total': 0, 'creditos': 0, 'area_total': 0},
            'energia': {'total': 0, 'creditos': 0, 'area_total': 0}
        }
    }
    
    # Mapeamento de abas para categorias
    CATEGORY_MAPPING = {
        '4. Agriculture': 'agricultura',
        '5. Agroforestry-AR & Grassland': 'agroflorestal',
        '6. Energy and Other': 'energia',
        '7. Plan Vivo, Acorn, Social C': 'agroflorestal',
        '8. Puro.earth': 'energia',
        '9. Nori and BCarbon': 'agricultura'
    }
    
    # 1. ANÁLISE POR PROJETO
    for sheet_name, category in CATEGORY_MAPPING.items():
        if sheet_name not in dataframes or dataframes[sheet_name].empty:
            continue
            
        df = dataframes[sheet_name]
        analysis['categorias_projetos'][category]['total'] += len(df)
        
        # Identificar colunas automaticamente
        col_info = identificar_colunas(df)
        
        # Processar cada projeto
        for idx, row in df.iterrows():
            try:
                projeto_info = extrair_info_projeto(row, col_info, category, sheet_name)
                
                if projeto_info:
                    # Adicionar aos casos de sucesso
                    if (projeto_info.get('creditos_emitidos', 0) > 1000 and 
                        projeto_info.get('area_hectares', 0) > 10):
                        analysis['casos_sucesso_reais'].append(projeto_info)
                    
                    # Acumular estatísticas por país
                    pais = projeto_info.get('pais', 'Não especificado')
                    if pais not in analysis['projetos_por_pais']:
                        analysis['projetos_por_pais'][pais] = 0
                    analysis['projetos_por_pais'][pais] += 1
                    
                    # Acumular créditos por categoria
                    analysis['categorias_projetos'][category]['creditos'] += projeto_info.get('creditos_emitidos', 0)
                    analysis['categorias_projetos'][category]['area_total'] += projeto_info.get('area_hectares', 0)
                    
                    # Calcular taxa de sequestro
                    if (projeto_info.get('area_hectares', 0) > 0 and 
                        projeto_info.get('creditos_emitidos', 0) > 0 and
                        projeto_info.get('duracao_anos', 10) > 0):
                        
                        taxa = (projeto_info['creditos_emitidos'] / 
                                projeto_info['duracao_anos'] / 
                                projeto_info['area_hectares'])
                        
                        if category not in analysis['taxas_sequestro_reais']:
                            analysis['taxas_sequestro_reais'][category] = []
                        analysis['taxas_sequestro_reais'][category].append(taxa)
                        
            except Exception:
                continue
    
    # 2. CALCULAR ESTATÍSTICAS GERAIS
    total_projetos = sum(cat['total'] for cat in analysis['categorias_projetos'].values())
    total_creditos = sum(cat['creditos'] for cat in analysis['categorias_projetos'].values())
    
    analysis['estatisticas_gerais'] = {
        'total_projetos': total_projetos,
        'total_creditos': total_creditos,
        'receita_estimada': total_creditos * 22.5,
        'paises_com_projetos': len(analysis['projetos_por_pais']),
        'casos_sucesso_encontrados': len(analysis['casos_sucesso_reais'])
    }
    
    # 3. CALCULAR MÉDIAS DAS TAXAS DE SEQUESTRO
    for categoria, taxas in analysis['taxas_sequestro_reais'].items():
        if taxas:
            analysis['taxas_sequestro_reais'][categoria] = {
                'media': np.mean(taxas),
                'mediana': np.median(taxas),
                'min': np.min(taxas),
                'max': np.max(taxas),
                'q25': np.percentile(taxas, 25),
                'q75': np.percentile(taxas, 75),
                'amostra': len(taxas)
            }
    
    # 4. ORDENAR CASOS DE SUCESSO
    analysis['casos_sucesso_reais'].sort(key=lambda x: x.get('creditos_emitidos', 0), reverse=True)
    
    return analysis

def identificar_colunas(df):
    """Identifica automaticamente as colunas relevantes"""
    columns = {
        'nome': None,
        'pais': None,
        'area': None,
        'creditos': None,
        'duracao': None,
        'metodologia': None,
        'preco': None
    }
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        if any(word in col_lower for word in ['name', 'project', 'title', 'nome', 'projeto']):
            columns['nome'] = col
        elif any(word in col_lower for word in ['country', 'pais', 'location', 'region']):
            columns['pais'] = col
        elif any(word in col_lower for word in ['area', 'hectare', 'ha', 'land', 'size', 'hectares']):
            columns['area'] = col
        elif any(word in col_lower for word in ['credit', 'issued', 'volume', 'amount', 'total', 'credits']):
            columns['creditos'] = col
        elif any(word in col_lower for word in ['year', 'duration', 'period', 'lifetime', 'time', 'anos']):
            columns['duracao'] = col
        elif any(word in col_lower for word in ['methodology', 'standard', 'type', 'practice', 'metodologia']):
            columns['metodologia'] = col
        elif any(word in col_lower for word in ['price', 'value', 'cost', 'preco', 'valor']):
            columns['preco'] = col
    
    return columns

def extrair_info_projeto(row, col_info, category, sheet_name):
    """Extrai informações de um projeto específico"""
    try:
        info = {
            'categoria': category,
            'fonte': sheet_name,
            'creditos_emitidos': 0,
            'area_hectares': 0,
            'duracao_anos': 10,
            'pais': 'Não especificado',
            'nome': f"Projeto {category}",
            'metodologia': 'Não especificada'
        }
        
        # Extrair créditos
        if col_info['creditos'] and col_info['creditos'] in row:
            creditos = parse_numero_br(row[col_info['creditos']])
            if creditos and creditos > 0:
                info['creditos_emitidos'] = creditos
        
        # Extrair área
        if col_info['area'] and col_info['area'] in row:
            area = parse_numero_br(row[col_info['area']])
            if area and area > 0:
                info['area_hectares'] = area
        
        # Extrair duração
        if col_info['duracao'] and col_info['duracao'] in row:
            duracao = extrair_anos(row[col_info['duracao']])
            if duracao and duracao > 0:
                info['duracao_anos'] = duracao
        
        # Extrair país
        if col_info['pais'] and col_info['pais'] in row:
            pais_raw = str(row[col_info['pais']])
            if pais_raw and pais_raw.lower() != 'nan':
                info['pais'] = get_country_name(pais_raw)
        
        # Extrair nome
        if col_info['nome'] and col_info['nome'] in row:
            nome = str(row[col_info['nome']])
            if nome and nome.lower() != 'nan':
                info['nome'] = nome[:100] + "..." if len(nome) > 100 else nome
        
        # Extrair metodologia
        if col_info['metodologia'] and col_info['metodologia'] in row:
            metodologia = str(row[col_info['metodologia']])
            if metodologia and metodologia.lower() != 'nan':
                info['metodologia'] = metodologia
        
        # Calcular métricas derivadas
        if info['area_hectares'] > 0 and info['creditos_emitidos'] > 0:
            info['taxa_sequestro'] = info['creditos_emitidos'] / info['duracao_anos'] / info['area_hectares']
            info['receita_estimada'] = info['creditos_emitidos'] * 22.5
            info['receita_anual'] = info['receita_estimada'] / info['duracao_anos']
            info['receita_por_hectare'] = info['receita_anual'] / info['area_hectares'] if info['area_hectares'] > 0 else 0
        
        return info if info['creditos_emitidos'] > 0 else None
        
    except Exception:
        return None

def extrair_anos(value):
    """Extrai número de anos de uma string"""
    if pd.isna(value):
        return 10
    
    try:
        str_value = str(value).lower()
        numbers = re.findall(r'\d+', str_value)
        if numbers:
            anos = int(numbers[0])
            if 'month' in str_value or 'mes' in str_value:
                anos = anos / 12
            elif 'day' in str_value or 'dia' in str_value:
                anos = anos / 365
            return max(1, min(anos, 50))
    except:
        pass
    
    return 10

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

# =========================
# FUNÇÕES DE CÁLCULO
# =========================

def calcular_receita_potencial(hectares, practice_type, analysis):
    """Calcula receita potencial baseada em dados reais"""
    
    taxas = analysis.get('taxas_sequestro_reais', {}).get(practice_type, {})
    preco_medio = 22.5  # US$/tCO2
    
    if taxas and 'media' in taxas:
        rate_avg = taxas['media']
        rate_min = taxas.get('q25', rate_avg * 0.7)
        rate_max = taxas.get('q75', rate_avg * 1.3)
        data_source = f"Baseado em {taxas.get('amostra', 0)} projetos reais"
    else:
        default_rates = {
            'agricultura': 1.25,
            'agroflorestal': 4.0,
            'energia': 2.0
        }
        rate_avg = default_rates.get(practice_type, 1.25)
        rate_min = rate_avg * 0.6
        rate_max = rate_avg * 1.4
        data_source = "Estimativa conservadora"
    
    calculations = {
        'hectares': hectares,
        'practice_type': practice_type,
        'annual_sequestration_avg': hectares * rate_avg,
        'annual_revenue_avg': hectares * rate_avg * preco_medio,
        '10yr_revenue_avg': hectares * rate_avg * preco_medio * 10,
        'price_per_ton': f"US$ {formatar_numero_br(preco_medio, 1)}/tCO₂ (média)",
        'sequestration_per_ha': f"{formatar_numero_br(rate_min, 1)}-{formatar_numero_br(rate_max, 1)} tCO₂/ha/ano",
        'data_source': data_source,
        'projects_analyzed': taxas.get('amostra', 0) if taxas else 0
    }
    
    return calculations

def calcular_ponto_equilibrio(hectares, investment_cost, practice_type, analysis):
    """Calcula ponto de equilíbrio"""
    revenue = calcular_receita_potencial(hectares, practice_type, analysis)
    annual_revenue = revenue['annual_revenue_avg']
    
    if annual_revenue > 0:
        break_even_years = investment_cost / annual_revenue
        roi_5yr = ((annual_revenue * 5) - investment_cost) / investment_cost * 100
    else:
        break_even_years = float('inf')
        roi_5yr = 0
    
    return {
        'break_even_years': break_even_years,
        'roi_5yr': roi_5yr,
        'monthly_revenue': annual_revenue / 12
    }

# =========================
# COMPONENTES DE UI COM FORMATAÇÃO BR
# =========================

def criar_hero_section(analysis):
    """Cria seção hero com dados reais formatados"""
    
    stats = analysis['estatisticas_gerais']
    
    st.markdown(f"""
    <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                background: linear-gradient(135deg, #27ae60, #229954); 
                color: white; margin-bottom: 2rem;'>
        <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>🌱 Mercado Real de Carbono Agrícola</h1>
        <h3 style='font-weight: 300;'>Baseado em {formatar_numero_br(stats['total_projetos'])} projetos certificados da FAO</h3>
        <p style='font-size: 1.1rem; opacity: 0.9;'>
            {formatar_numero_br(stats['total_creditos'])} créditos emitidos • 
            {formatar_numero_br(stats['paises_com_projetos'])} países • 
            {formatar_moeda_br(stats['receita_estimada'])} em receita gerada
        </p>
    </div>
    """, unsafe_allow_html=True)

def criar_calculadora_receita(analysis):
    """Calculadora com formatação brasileira"""
    with st.expander("🧮 CALCULE SEU POTENCIAL COM DADOS REAIS", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            hectares_input = st.text_input(
                "Tamanho da propriedade (hectares):",
                value="100,00",
                help="Use vírgula para decimais (ex: 150,50)"
            )
            hectares = parse_numero_br(hectares_input) or 100.0
        
        with col2:
            practice_type = st.selectbox(
                "Prática sustentável:",
                [
                    ("agricultura", "🌱 Agricultura Regenerativa"),
                    ("agroflorestal", "🌳 Sistemas Agroflorestais"),
                    ("energia", "⚡ Bioenergia Sustentável")
                ],
                format_func=lambda x: x[1],
                index=0
            )[0]
        
        with col3:
            investment_input = st.text_input(
                "Investimento inicial (US$):",
                value="10.000,00",
                help="Use ponto para milhar e vírgula para decimais"
            )
            investment = parse_numero_br(investment_input) or 10000.0
        
        # Calcular
        revenue = calcular_receita_potencial(hectares, practice_type, analysis)
        break_even = calcular_ponto_equilibrio(hectares, investment, practice_type, analysis)
        
        # Mostrar base de dados
        if revenue['projects_analyzed'] > 0:
            st.info(f"📊 **Baseado em {formatar_numero_br(revenue['projects_analyzed'])} projetos certificados** • {revenue['data_source']}")
        
        # Resultados formatados
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Receita Anual", formatar_moeda_br(revenue['annual_revenue_avg']))
        with col2:
            st.metric("📈 Receita 10 anos", formatar_moeda_br(revenue['10yr_revenue_avg']))
        with col3:
            st.metric("⏱️ Retorno (anos)", formatar_numero_br(break_even['break_even_years'], 1))
        with col4:
            st.metric("📊 ROI 5 anos", formatar_percentual_br(break_even['roi_5yr'], 1))
        
        # Detalhes formatados
        with st.expander("📋 Ver detalhes do cálculo"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Preço do carbono:** {revenue['price_per_ton']}")
                st.write(f"**Sequestro estimado:** {revenue['sequestration_per_ha']}")
                st.write(f"**Fonte dos dados:** {revenue['data_source']}")
                
                taxas = analysis.get('taxas_sequestro_reais', {}).get(practice_type, {})
                if taxas:
                    st.write(f"**Taxa real média:** {formatar_numero_br(taxas.get('media', 0), 2)} tCO₂/ha/ano")
                    st.write(f"**Variação real:** {formatar_numero_br(taxas.get('min', 0), 2)} - {formatar_numero_br(taxas.get('max', 0), 2)} tCO₂/ha/ano")
            
            with col2:
                st.write(f"**Sequestro total anual:** {formatar_toneladas_br(revenue['annual_sequestration_avg'])}")
                st.write(f"**Receita mensal:** {formatar_moeda_br(break_even['monthly_revenue'])}")
                st.write(f"**Investimento inicial:** {formatar_moeda_br(investment)}")
                st.write(f"**Área da propriedade:** {formatar_area_br(hectares)}")

def criar_casos_sucesso_reais(analysis):
    """Cria casos de sucesso com formatação brasileira"""
    
    success_stories = analysis.get('casos_sucesso_reais', [])
    
    if not success_stories:
        st.warning("📊 **Analisando projetos...** Em breve mostraremos casos reais baseados no dataset.")
        return
    
    top_stories = success_stories[:4]
    
    st.markdown("## 📚 Casos Reais de Projetos que Geram Créditos")
    st.info(f"💡 **Baseado em {formatar_numero_br(len(success_stories))} projetos certificados do dataset FAO**")
    
    cols = st.columns(2)
    for i, story in enumerate(top_stories):
        with cols[i % 2]:
            icon_map = {
                'agricultura': '🌱',
                'agroflorestal': '🌳',
                'energia': '⚡'
            }
            icon = icon_map.get(story['categoria'], '✅')
            
            descricao = f"Projeto certificado em {story.get('pais', 'Não especificado')}"
            if story.get('area_hectares', 0) > 0:
                descricao += f" com {formatar_area_br(story['area_hectares'])}"
            if story.get('creditos_emitidos', 0) > 0:
                descricao += f". Emitiu {formatar_numero_br(story['creditos_emitidos'])} créditos de carbono"
            
            receita = story.get('receita_estimada', 0)
            receita_anual = story.get('receita_anual', 0)
            
            st.markdown(f"""
            <div style='background: white; padding: 1.5rem; border-radius: 10px; 
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin: 1rem 0; 
                        border-top: 5px solid #27ae60;'>
                <div style='display: flex; align-items: center; margin-bottom: 1rem;'>
                    <div style='font-size: 2rem; margin-right: 1rem;'>{icon}</div>
                    <h3 style='margin: 0; color: #2c3e50; font-size: 1.1rem;'>{story.get('nome', 'Projeto Certificado')}</h3>
                </div>
                <p style='color: #7f8c8d; line-height: 1.6; font-size: 0.9rem;'>{descricao}</p>
                <div style='background: #f8f9fa; padding: 1rem; border-radius: 5px; margin: 1rem 0;'>
                    <div style='display: flex; justify-content: space-between;'>
                        <div>
                            <div style='font-size: 0.8rem; color: #95a5a6;'>Receita Estimada</div>
                            <div style='font-size: 1.2rem; font-weight: bold; color: #27ae60;'>{formatar_moeda_br(receita)}</div>
                        </div>
                        <div>
                            <div style='font-size: 0.8rem; color: #95a5a6;'>Receita Anual</div>
                            <div style='font-size: 1rem; color: #2c3e50;'>{formatar_moeda_br(receita_anual)}/ano</div>
                        </div>
                    </div>
                </div>
                <div style='color: #3498db; font-size: 0.8rem;'>
                    <strong>Categoria:</strong> {story.get('categoria', 'Não especificada').title()} • 
                    <strong>Fonte:</strong> {story.get('fonte', 'Dataset FAO')}
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    if len(success_stories) > 4:
        st.markdown(f"*📈 E outros {formatar_numero_br(len(success_stories) - 4)} projetos certificados...*")

# =========================
# PÁGINAS PRINCIPAIS
# =========================

def render_opportunities_home(dataframes, analysis):
    """Página inicial com formatação brasileira"""
    criar_hero_section(analysis)
    
    # Calculadora
    criar_calculadora_receita(analysis)
    
    # Métricas reais
    st.markdown("## 📈 O Mercado Real em Números")
    
    stats = analysis['estatisticas_gerais']
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Projetos Certificados", formatar_numero_br(stats['total_projetos']), 
                 f"{formatar_numero_br(stats['paises_com_projetos'])} países")
    with col2:
        st.metric("🌱 Créditos Emitidos", formatar_numero_br(stats['total_creditos']), 
                 f"≈ {formatar_numero_br(stats['total_creditos'])} tCO₂")
    with col3:
        st.metric("💵 Receita Gerada", formatar_moeda_br(stats['receita_estimada']), 
                 "Preço médio: US$ 22,5/tCO₂")
    with col4:
        receita_media = stats['receita_estimada'] / max(1, stats['total_projetos'])
        st.metric("🏆 Média por Projeto", formatar_moeda_br(receita_media))
    
    # Casos de sucesso
    criar_casos_sucesso_reais(analysis)
    
    # Distribuição por país
    st.markdown("## 🌍 Onde os Projetos Estão Acontecendo")
    
    paises = analysis['projetos_por_pais']
    if paises:
        paises_df = pd.DataFrame(list(paises.items()), columns=['País', 'Projetos'])
        paises_df = paises_df.sort_values('Projetos', ascending=False).head(10)
        
        # Formatar números no gráfico
        paises_df['Projetos_formatado'] = paises_df['Projetos'].apply(lambda x: formatar_numero_br(x))
        
        fig = px.bar(paises_df, x='País', y='Projetos',
                    title="Top 10 Países com Mais Projetos Certificados",
                    text='Projetos_formatado',
                    color='Projetos',
                    color_continuous_scale='Greens')
        fig.update_traces(textposition='outside')
        fig.update_layout(yaxis_title='Número de Projetos')
        st.plotly_chart(fig, use_container_width=True)
    
    # Comparativo entre categorias
    st.markdown("## 📊 Comparativo por Tipo de Projeto")
    
    categorias = analysis['categorias_projetos']
    if categorias:
        cat_df = pd.DataFrame([
            {'Categoria': 'Agricultura', 'Projetos': categorias['agricultura']['total'], 
             'Créditos': categorias['agricultura']['creditos']},
            {'Categoria': 'Agrofloresta', 'Projetos': categorias['agroflorestal']['total'], 
             'Créditos': categorias['agroflorestal']['creditos']},
            {'Categoria': 'Energia', 'Projetos': categorias['energia']['total'], 
             'Créditos': categorias['energia']['creditos']}
        ])
        
        # Formatar para tooltips
        cat_df['Projetos_formatado'] = cat_df['Projetos'].apply(lambda x: formatar_numero_br(x))
        cat_df['Créditos_formatado'] = cat_df['Créditos'].apply(lambda x: formatar_numero_br(x))
        
        col1, col2 = st.columns(2)
        with col1:
            fig1 = px.pie(cat_df, values='Projetos', names='Categoria',
                         title="Distribuição de Projetos por Categoria",
                         hover_data=['Projetos_formatado'])
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            fig2 = px.bar(cat_df, x='Categoria', y='Créditos',
                         title="Créditos Emitidos por Categoria",
                         text='Créditos_formatado',
                         color='Categoria')
            fig2.update_traces(textposition='outside')
            st.plotly_chart(fig2, use_container_width=True)

def render_project_explorer(dataframes, sheet_names, analysis):
    """Explorador de projetos com formatação brasileira"""
    st.markdown("## 🔍 Explore Projetos Certificados Reais")
    
    project_sheets = [s for s in sheet_names if SHEET_CONFIG.get(s, {}).get('revenue_focus', False)]
    
    if not project_sheets:
        st.warning("Nenhuma aba de projetos encontrada.")
        return
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🎯 Filtros")
        
        selected_sheet = st.selectbox(
            "Tipo de Projeto:",
            project_sheets,
            format_func=lambda x: f"{SHEET_CONFIG.get(x, {}).get('icon', '📄')} {x}"
        )
        
        # Filtro por país
        st.markdown("---")
        st.markdown("### 🌍 Filtrar por País")
        
        df = dataframes[selected_sheet]
        paises_disponiveis = []
        
        for col in df.columns:
            if any(word in str(col).lower() for word in ['country', 'pais']):
                paises_unicos = df[col].dropna().unique()
                for pais in paises_unicos:
                    if pais and str(pais).strip():
                        pais_nome = get_country_name(str(pais))
                        if pais_nome not in paises_disponiveis:
                            paises_disponiveis.append(pais_nome)
        
        if paises_disponiveis:
            selected_countries = st.multiselect(
                "Selecione países:",
                sorted(paises_disponiveis),
                default=[]
            )
        else:
            selected_countries = []
    
    # Conteúdo principal
    if selected_sheet in dataframes:
        df = dataframes[selected_sheet]
        config = SHEET_CONFIG.get(selected_sheet, {})
        
        # Aplicar filtros
        filtered_df = df.copy()
        
        if selected_countries:
            for col in filtered_df.columns:
                if any(word in str(col).lower() for word in ['country', 'pais']):
                    filtered_df = filtered_df[
                        filtered_df[col].apply(lambda x: get_country_name(str(x)) if pd.notna(x) else "").isin(selected_countries)
                    ]
                    break
        
        # Cabeçalho
        st.markdown(f"### {config.get('icon', '📊')} {selected_sheet}")
        st.markdown(f"**{formatar_numero_br(len(filtered_df))} projetos encontrados** • Dados extraídos do dataset FAO")
        
        # Encontrar colunas numéricas para formatar
        relevant_cols = []
        priority_words = ['name', 'project', 'country', 'credit', 'issued', 'area', 'hectare', 'type', 'standard']
        
        for word in priority_words:
            for col in df.columns:
                if word in str(col).lower() and col not in relevant_cols:
                    relevant_cols.append(col)
        
        # Mostrar dados com formatação brasileira
        if relevant_cols:
            display_df = filtered_df[relevant_cols].head(50).copy()
            
            # Formatar colunas numéricas
            for col in display_df.columns:
                if any(word in str(col).lower() for word in ['credit', 'issued', 'amount', 'total', 'volume']):
                    # Coluna de créditos - formatar como número brasileiro
                    display_df[col] = display_df[col].apply(
                        lambda x: formatar_numero_br(parse_numero_br(x)) if pd.notna(x) else x
                    )
                elif any(word in str(col).lower() for word in ['area', 'hectare', 'ha', 'size']):
                    # Coluna de área - formatar como área
                    display_df[col] = display_df[col].apply(
                        lambda x: formatar_area_br(parse_numero_br(x)) if pd.notna(x) else x
                    )
                elif any(word in str(col).lower() for word in ['price', 'value', 'cost']):
                    # Coluna de preço - formatar como moeda
                    display_df[col] = display_df[col].apply(
                        lambda x: formatar_moeda_br(parse_numero_br(x)) if pd.notna(x) else x
                    )
            
            st.dataframe(
                display_df,
                use_container_width=True,
                height=400,
                hide_index=True
            )

def render_market_statistics(analysis):
    """Estatísticas detalhadas com formatação brasileira"""
    st.markdown("## 📊 Estatísticas Detalhadas Baseadas em Projetos Reais")
    
    if not analysis:
        st.warning("Carregando análise...")
        return
    
    # Resumo
    stats = analysis['estatisticas_gerais']
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📈 Projetos Analisados", formatar_numero_br(stats['total_projetos']))
    with col2:
        st.metric("💰 Créditos Totais", formatar_numero_br(stats['total_creditos']))
    with col3:
        st.metric("🌍 Países", formatar_numero_br(stats['paises_com_projetos']))
    
    # Taxas de sequestro reais
    st.markdown("### 📈 Taxas Reais de Sequestro (tCO₂/ha/ano)")
    
    taxas = analysis.get('taxas_sequestro_reais', {})
    if taxas:
        for categoria, dados in taxas.items():
            if 'media' in dados:
                st.markdown(f"#### {categoria.title()}")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Média", formatar_numero_br(dados['media'], 2))
                with col2:
                    st.metric("Min-Max", 
                             f"{formatar_numero_br(dados.get('min', 0), 2)}-{formatar_numero_br(dados.get('max', 0), 2)}")
                with col3:
                    st.metric("25%-75%", 
                             f"{formatar_numero_br(dados.get('q25', 0), 2)}-{formatar_numero_br(dados.get('q75', 0), 2)}")
                with col4:
                    st.metric("Amostra", formatar_numero_br(dados.get('amostra', 0)))

def render_how_to_participate():
    """Como participar"""
    st.markdown("## 📞 Como Participar do Mercado de Carbono")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 Passo a Passo")
        
        steps = [
            {"step": 1, "title": "Diagnóstico da Propriedade", 
             "desc": "Avalie o potencial de sequestro de carbono da sua terra"},
            {"step": 2, "title": "Escolha do Padrão", 
             "desc": "Selecione uma metodologia de certificação (Verra, Gold Standard, etc.)"},
            {"step": 3, "title": "Projeto de Carbono", 
             "desc": "Desenvolva o projeto seguindo as regras do padrão escolhido"},
            {"step": 4, "title": "Validação e Verificação", 
             "desc": "Contrate auditoria independente para validar o projeto"},
            {"step": 5, "title": "Registro dos Créditos", 
             "desc": "Registre os créditos gerados em plataforma oficial"},
            {"step": 6, "title": "Comercialização", 
             "desc": "Venda os créditos no mercado voluntário"}
        ]
        
        for step in steps:
            st.markdown(f"""
            <div style='background: #f8f9fa; padding: 1rem; border-radius: 10px; margin: 0.5rem 0; 
                        border-left: 4px solid #27ae60;'>
                <div style='display: flex; align-items: center;'>
                    <div style='background: #27ae60; color: white; width: 30px; height: 30px; 
                                border-radius: 50%; display: flex; align-items: center; 
                                justify-content: center; margin-right: 1rem; font-weight: bold;'>
                        {step['step']}
                    </div>
                    <div>
                        <h4 style='margin: 0; color: #2c3e50;'>{step['title']}</h4>
                        <p style='margin: 0.2rem 0 0 0; color: #7f8c8d; font-size: 0.9rem;'>
                            {step['desc']}
                        </p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 💰 Custos e Investimentos")
        
        costs = [
            {"item": "Auditoria/Verificação", "range": "US$ 5.000 - 20.000"},
            {"item": "Desenvolvimento do Projeto", "range": "US$ 10.000 - 50.000"},
            {"item": "Taxas de Registro", "range": "US$ 0,15 - 0,30/crédito"},
            {"item": "Implementação Práticas", "range": "Variável por hectare"}
        ]
        
        for cost in costs:
            st.markdown(f"""
            <div style='display: flex; justify-content: space-between; padding: 0.5rem 0; 
                        border-bottom: 1px solid #eee;'>
                <span style='color: #2c3e50;'>{cost['item']}</span>
                <span style='color: #27ae60; font-weight: bold;'>{cost['range']}</span>
            </div>
            """, unsafe_allow_html=True)

# =========================
# CARGA DE DADOS
# =========================

@st.cache_data(ttl=3600, show_spinner="Carregando dataset FAO...")
def load_fao_dataset():
    """Carrega e prepara o dataset FAO"""
    file_path = "Dataset.xlsx"
    
    if not os.path.exists(file_path):
        st.error("❌ **Arquivo Dataset.xlsx não encontrado.** Coloque o arquivo na mesma pasta do aplicativo.")
        return None, None
    
    try:
        excel = pd.ExcelFile(file_path, engine='openpyxl')
        data = {}
        sheet_names = []
        
        for sheet in excel.sheet_names:
            try:
                df = excel.parse(sheet, header=0)
                
                # Limpeza básica
                df = df.dropna(axis=1, how='all')
                df.columns = [str(col).strip() for col in df.columns]
                df = df.loc[:, df.notna().any()]
                
                data[sheet] = df
                sheet_names.append(sheet)
                
            except Exception as e:
                st.warning(f"⚠️ Aviso na aba '{sheet}': {str(e)[:100]}")
                data[sheet] = pd.DataFrame()
        
        return data, sheet_names
        
    except Exception as e:
        st.error(f"❌ Erro crítico ao carregar dados: {str(e)}")
        return None, None

# =========================
# APLICAÇÃO PRINCIPAL
# =========================

def main():
    # Carregar dados
    dataframes, sheet_names = load_fao_dataset()
    
    if dataframes is None:
        st.error("Não foi possível continuar sem o dataset.")
        return
    
    # Analisar dataset
    if 'complete_analysis' not in st.session_state:
        with st.spinner("🔍 Analisando todos os projetos do dataset FAO..."):
            analysis = analyze_complete_dataset(dataframes)
            st.session_state.complete_analysis = analysis
            st.session_state.dataframes = dataframes
            st.session_state.sheet_names = sheet_names
    else:
        analysis = st.session_state.complete_analysis
        dataframes = st.session_state.dataframes
        sheet_names = st.session_state.sheet_names
    
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 1rem;'>
            <h2 style='color: #27ae60;'>🌱 Carbono Real</h2>
            <p style='color: #7f8c8d;'>Baseado em dados FAO</p>
        </div>
        """, unsafe_allow_html=True)
        
        page = st.radio(
            "Navegação",
            ["🏠 Mercado Real", "🔍 Projetos", "📊 Estatísticas", "📞 Como Participar"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Estatísticas rápidas
        if analysis:
            stats = analysis['estatisticas_gerais']
            st.markdown("### 📈 Dados Reais")
            st.info(f"""
            **{formatar_numero_br(stats['total_projetos'])}** projetos analisados  
            **{formatar_numero_br(stats['total_creditos'])}** créditos emitidos  
            **{formatar_numero_br(stats['paises_com_projetos'])}** países
            """)
        
        st.markdown("---")
        st.markdown("### 📁 Formato dos Números")
        st.markdown("""
        - **Milhar:** ponto (1.000)
        - **Decimal:** vírgula (1.000,50)
        - **Moeda:** US$ 1.000,50
        - **Área:** 1.000,5 ha
        - **Toneladas:** 1.000,5 tCO₂
        """)

def criar_rodape(analysis):
    """Rodapé informativo"""
    st.markdown("---")
    
    if analysis:
        stats = analysis['estatisticas_gerais']
        st.markdown(f"""
        <div style='text-align: center; padding: 1rem;'>
            <p style='color: #7f8c8d;'>
            <strong>🌱 Análise Baseada em Dados Reais FAO</strong> | 
            {formatar_numero_br(stats['total_projetos'])} projetos certificados | 
            {formatar_numero_br(stats['total_creditos'])} créditos emitidos |
            {formatar_numero_br(stats['paises_com_projetos'])} países
            </p>
            <p style='color: #95a5a6; font-size: 0.8rem;'>
            💡 Todos os valores formatados no padrão brasileiro (ponto milhar, vírgula decimal).
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='text-align: center; padding: 1rem;'>
            <p style='color: #7f8c8d;'>
            <strong>🌱 Dashboard de Análise de Mercado de Carbono</strong> | 
            Baseado em dados FAO | Para fins informativos
            </p>
        </div>
        """, unsafe_allow_html=True)

# =========================
# EXECUÇÃO
# =========================

if __name__ == "__main__":
    try:
        main()
        if 'complete_analysis' in st.session_state:
            criar_rodape(st.session_state.complete_analysis)
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")
        st.info("Recarregue a página ou verifique o arquivo Dataset.xlsx")
