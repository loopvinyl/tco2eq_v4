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
        'About': "Dashboard baseado em dados reais da FAO para proprietários rurais entenderem oportunidades no mercado de carbono agrícola."
    }
)

# =========================
# CONSTANTES BASEADAS NA ANÁLISE DO DATASET
# =========================

# Dados consolidados da análise do dataset (baseado no relatório analise_completa_dataset.txt)
DATASET_STATS = {
    'total_projetos': 672,  # Total de projetos identificados
    'total_creditos_emitidos': 4754781,  # Total de créditos emitidos
    'total_creditos_aposentados': 8244,  # Total de créditos aposentados
    'taxa_aposentadoria': 0.17,  # Porcentagem de créditos aposentados
    'abas_com_projetos': ['4. Agriculture', '5. Agroforestry-AR & Grassland', '6. Energy and Other', 
                          '7. Plan Vivo, Acorn, Social C', '8. Puro.earth', '9. Nori and BCarbon']
}

# Mapeamento específico de colunas baseado na análise
ABA_COLUMN_MAPPING = {
    '4. Agriculture': {
        'nome': 'Unnamed: 1',
        'creditos': 'Credits issued by vintage year (when reduction/removals occurred)',
        'creditos_retirados': 'Credits retired in:',
        'pais': 'Unnamed: 9',  # Coluna Region que pode ser usada como país
        'project_count': 439
    },
    '5. Agroforestry-AR & Grassland': {
        'nome': 'Unnamed: 1',
        'creditos': 'Credits issued by vintage year (when reduction/removals occurred)',
        'creditos_retirados': 'Credits retired in:',
        'pais': 'Unnamed: 9',
        'project_count': 87
    },
    '6. Energy and Other': {
        'nome': 'Unnamed: 1',
        'creditos': 'Credits issued by vintage year (when reduction/removals occurred)',
        'creditos_retirados': 'Credits retired in:',
        'pais': 'Unnamed: 9',
        'project_count': 7
    },
    '7. Plan Vivo, Acorn, Social C': {
        'nome': 'Project name',
        'creditos': 'Issued credits',
        'pais': 'Country',
        'project_count': 23,
        'creditos_emitidos_total': 4588110  # Total específico desta aba
    },
    '8. Puro.earth': {
        'nome': 'Unnamed: 0',
        'creditos': 'Total Issued Credits (CORC)',
        'creditos_retirados': 'Retired Credits',
        'pais': 'Unnamed: 3',  # Country
        'project_count': 33,
        'creditos_emitidos_total': 2989,
        'creditos_retirados_total': 2256
    },
    '9. Nori and BCarbon': {
        'nome': 'Project name',
        'creditos': 'Issued credits',
        'pais': 'Country',
        'project_count': 23,
        'creditos_emitidos_total': 155698
    }
}

# Mapeamento de categorias
CATEGORY_MAPPING = {
    '4. Agriculture': 'agricultura',
    '5. Agroforestry-AR & Grassland': 'agroflorestal',
    '6. Energy and Other': 'energia',
    '7. Plan Vivo, Acorn, Social C': 'agroflorestal',
    '8. Puro.earth': 'agricultura',  # Biochar é agricultura
    '9. Nori and BCarbon': 'agricultura'
}

# =========================
# FUNÇÕES DE FORMATAÇÃO BRASILEIRA
# =========================

def formatar_milhoes(numero):
    """
    Formata números grandes como milhões: 367,2 milhões
    """
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
    """
    Formata números no padrão brasileiro: 1.234,56
    """
    if pd.isna(numero):
        return "N/A"
    
    # Arredonda para 2 casas decimais
    numero = round(numero, 2)
    
    # Formata como string e substitui o ponto pela vírgula
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_br_dec(numero, decimais=2):
    """
    Formata números no padrão brasileiro com número específico de casas decimais
    """
    if pd.isna(numero):
        return "N/A"
    
    # Arredonda para o número de casas decimais especificado
    numero = round(numero, decimais)
    
    # Formata como string e substitui o ponto pela vírgula
    return f"{numero:,.{decimais}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_br_inteiro(numero):
    """
    Formata números inteiros no padrão brasileiro: 1.234
    """
    if pd.isna(numero):
        return "N/A"
    
    # Arredonda para inteiro
    numero = int(round(numero, 0))
    
    # Formata como string
    return f"{numero:,}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_moeda_curta(numero):
    """
    Formata valores monetários de forma curta e inteligente:
    - > 1.000.000: X,X milhões
    - > 1.000: X,X mil
    - < 1.000: valor normal
    """
    if pd.isna(numero):
        return "N/A"
    
    numero = float(numero)
    
    if numero >= 1000000000:  # Bilhões
        valor = numero / 1000000000
        return f"{formatar_br_dec(valor, 1)} bilhões"
    elif numero >= 1000000:  # Milhões
        valor = numero / 1000000
        return f"{formatar_br_dec(valor, 1)} milhões"
    elif numero >= 1000:  # Mil
        valor = numero / 1000
        return f"{formatar_br_dec(valor, 1)} mil"
    else:
        return formatar_br(numero)

# =========================
# FUNÇÕES DE LIMPEZA DE DADOS - OTIMIZADAS
# =========================

def clean_column_names(df):
    """
    Limpa e renomeia colunas do dataframe baseado na análise anterior
    """
    if df is None or df.empty:
        return df
    
    df_clean = df.copy()
    new_names = {}
    
    for col in df_clean.columns:
        col_str = str(col)
        
        # Se for coluna Unnamed, tentar encontrar nome baseado no conteúdo
        if pd.isna(col) or col_str.strip() == '' or 'Unnamed' in col_str:
            # Verificar primeira linha não nula
            first_valid = df_clean[col].dropna().iloc[0] if not df_clean[col].dropna().empty else None
            
            if first_valid and isinstance(first_valid, str) and len(first_valid) < 100:
                # Verificar se parece um cabeçalho (não é URL, não é muito longo)
                if 'http' not in first_valid.lower() and not first_valid.startswith('http'):
                    # Limpar a string
                    clean_name = first_valid.strip().replace('\n', ' ').replace('  ', ' ')
                    if len(clean_name) > 0:
                        new_names[col] = clean_name[:80]  # Limitar tamanho
                        continue
            
            # Se não encontrou, manter original
            new_names[col] = col_str
        else:
            # Limpar espaços e caracteres especiais
            new_names[col] = col_str.strip()
    
    # Aplicar novos nomes
    df_clean.rename(columns=new_names, inplace=True)
    
    return df_clean

def clean_dataframe(df):
    """
    Limpa completamente um dataframe
    """
    if df is None or df.empty:
        return df
    
    df_clean = df.copy()
    
    # 1. Limpar nomes das colunas
    df_clean = clean_column_names(df_clean)
    
    # 2. Remover colunas completamente vazias
    df_clean = df_clean.dropna(axis=1, how='all')
    
    # 3. Remover linhas que são cabeçalhos duplicados
    # Identificar linhas que parecem ser cabeçalhos (valores textuais curtos em muitas colunas)
    if len(df_clean) > 1:
        # Contar quantas colunas têm strings curtas em cada linha
        is_header_row = []
        for idx, row in df_clean.iterrows():
            count_text = 0
            for val in row.values:
                if isinstance(val, str) and 2 <= len(val.strip()) <= 100:
                    if not val.strip().replace('.', '', 1).isdigit():  # Não é número
                        count_text += 1
            
            # Se mais da metade das colunas têm texto curto, pode ser cabeçalho
            is_header_row.append(count_text > len(row) / 2)
        
        # Remover linhas identificadas como cabeçalhos (exceto a primeira)
        if sum(is_header_row) > 1:
            # Manter a primeira linha que parece cabeçalho (se houver)
            first_header_idx = next((i for i, x in enumerate(is_header_row) if x), None)
            if first_header_idx is not None:
                # Remover outras linhas de cabeçalho
                rows_to_remove = [i for i, x in enumerate(is_header_row) if x and i != first_header_idx]
                if rows_to_remove:
                    df_clean = df_clean.drop(rows_to_remove).reset_index(drop=True)
    
    # 4. Resetar índice
    df_clean = df_clean.reset_index(drop=True)
    
    return df_clean

# =========================
# SISTEMA DE ANÁLISE COMPLETA DO DATASET - OTIMIZADO
# =========================

@st.cache_data(ttl=3600, show_spinner="Analisando dataset FAO...")
def analyze_complete_dataset(dataframes):
    """Análise completa e estruturada de TODO o dataset - OTIMIZADA"""
    
    analysis = {
        'estatisticas_gerais': DATASET_STATS.copy(),
        'projetos_por_pais': {},
        'taxas_sequestro_reais': {},
        'casos_sucesso_reais': [],
        'precos_mercado': {},
        'metodologias_populares': {},
        'standards_mais_utilizados': {},
        'comparativo_emitidos_vs_aposentados': {
            'total_emitido': DATASET_STATS['total_creditos_emitidos'],
            'total_aposentado': DATASET_STATS['total_creditos_aposentados']
        },
        'timeline_data': {'anos': [], 'registrados': [], 'emitidos': [], 'aposentados': []},
        'categorias_projetos': {
            'agricultura': {'total': 0, 'creditos': 0, 'area_total': 0, 'projetos_com_creditos': 0},
            'agroflorestal': {'total': 0, 'creditos': 0, 'area_total': 0, 'projetos_com_creditos': 0},
            'energia': {'total': 0, 'creditos': 0, 'area_total': 0, 'projetos_com_creditos': 0}
        }
    }
    
    # 1. ANALISAR ABAS DE PROJETOS USANDO MAPEAMENTO ESPECÍFICO
    for sheet_name in DATASET_STATS['abas_com_projetos']:
        if sheet_name not in dataframes or dataframes[sheet_name].empty:
            continue
            
        df = dataframes[sheet_name]
        df_clean = clean_dataframe(df)
        
        # Obter mapeamento para esta aba
        col_mapping = ABA_COLUMN_MAPPING.get(sheet_name, {})
        categoria = CATEGORY_MAPPING.get(sheet_name, 'agricultura')
        
        # Contar projetos nesta categoria
        project_count = col_mapping.get('project_count', 0)
        analysis['categorias_projetos'][categoria]['total'] += project_count
        
        # Processar cada projeto
        projetos_processados = 0
        
        for idx, row in df_clean.iterrows():
            try:
                # Extrair informações usando mapeamento específico
                projeto_info = extract_project_info_with_mapping(row, col_mapping, categoria, sheet_name)
                
                if projeto_info and projeto_info.get('creditos_emitidos', 0) > 0:
                    projetos_processados += 1
                    analysis['categorias_projetos'][categoria]['projetos_com_creditos'] += 1
                    
                    # Adicionar aos casos de sucesso
                    if projeto_info.get('creditos_emitidos', 0) > 1000:
                        analysis['casos_sucesso_reais'].append(projeto_info)
                    
                    # Acumular estatísticas por país
                    pais = projeto_info.get('pais', 'Não especificado')
                    if pais not in analysis['projetos_por_pais']:
                        analysis['projetos_por_pais'][pais] = 0
                    analysis['projetos_por_pais'][pais] += 1
                    
                    # Acumular créditos por categoria
                    creditos = projeto_info.get('creditos_emitidos', 0)
                    analysis['categorias_projetos'][categoria]['creditos'] += creditos
                    
                    # Área (se disponível)
                    area = projeto_info.get('area_hectares', 0)
                    analysis['categorias_projetos'][categoria]['area_total'] += area
                    
                    # Calcular taxa de sequestro se tiver dados
                    if area > 0 and creditos > 0:
                        duracao = projeto_info.get('duracao_anos', 10)
                        taxa = (creditos / duracao / area) if duracao > 0 else 0
                        
                        if categoria not in analysis['taxas_sequestro_reais']:
                            analysis['taxas_sequestro_reais'][categoria] = []
                        analysis['taxas_sequestro_reais'][categoria].append(taxa)
                    
            except Exception as e:
                continue
        
        # Adicionar créditos específicos da aba se disponível
        if 'creditos_emitidos_total' in col_mapping:
            analysis['categorias_projetos'][categoria]['creditos'] += col_mapping['creditos_emitidos_total']
    
    # 2. ANALISAR STANDARDS (aba 1. Standards)
    if "1. Standards" in dataframes:
        df_standards = clean_dataframe(dataframes["1. Standards"])
        for idx, row in df_standards.iterrows():
            try:
                # Procurar coluna de nome do standard
                standard_col = None
                for col in df_standards.columns:
                    if isinstance(col, str) and 'standard' in col.lower():
                        standard_col = col
                        break
                
                if standard_col and standard_col in row:
                    standard_name = str(row[standard_col])
                    if standard_name and standard_name.strip() and standard_name.lower() != 'totals':
                        # Procurar coluna de total de projetos
                        total_col = None
                        for col in df_standards.columns:
                            if isinstance(col, str) and ('total' in col.lower() and 'project' in col.lower()):
                                total_col = col
                                break
                        
                        total_projetos = 0
                        if total_col and total_col in row:
                            try:
                                total_projetos = int(float(str(row[total_col])))
                            except:
                                pass
                        
                        if total_projetos > 0:
                            analysis['standards_mais_utilizados'][standard_name] = {
                                'total_projetos': total_projetos,
                                'projetos_agrifood': 0  # Não temos essa info
                            }
            except:
                continue
    
    # 3. CALCULAR ESTATÍSTICAS GERAIS
    total_projetos = DATASET_STATS['total_projetos']
    total_projetos_com_creditos = sum(cat['projetos_com_creditos'] for cat in analysis['categorias_projetos'].values())
    total_creditos = DATASET_STATS['total_creditos_emitidos']
    total_aposentado = DATASET_STATS['total_creditos_aposentados']
    
    # Usar taxa do dataset ou recalcular
    taxa_aposentadoria = DATASET_STATS['taxa_aposentadoria']
    
    # Preço médio realista
    preco_medio = 22.5  # US$/tCO2
    
    # CALCULAR RECEITAS
    receita_potencial = total_creditos * preco_medio
    receita_real = total_aposentado * preco_medio
    receita_media_por_projeto = receita_real / max(1, total_projetos_com_creditos) if total_projetos_com_creditos > 0 else 0
    
    analysis['estatisticas_gerais'].update({
        'total_projetos': total_projetos,
        'total_projetos_com_creditos': total_projetos_com_creditos,
        'total_creditos': total_creditos,
        'total_aposentado': total_aposentado,
        'receita_potencial': receita_potencial,
        'receita_real': receita_real,
        'receita_media_por_projeto': receita_media_por_projeto,
        'paises_com_projetos': len(analysis['projetos_por_pais']),
        'casos_sucesso_encontrados': len(analysis['casos_sucesso_reais']),
        'taxa_aposentadoria': taxa_aposentadoria,
        'creditos_emitidos': total_creditos,
        'creditos_aposentados': total_aposentado,
        'preco_medio': preco_medio
    })
    
    # 4. CALCULAR MÉDIAS DAS TAXAS DE SEQUESTRO
    for categoria, taxas in analysis['taxas_sequestro_reais'].items():
        if taxas:
            taxas_validas = [t for t in taxas if t > 0]
            if taxas_validas:
                analysis['taxas_sequestro_reais'][categoria] = {
                    'media': np.mean(taxas_validas),
                    'mediana': np.median(taxas_validas),
                    'min': np.min(taxas_validas),
                    'max': np.max(taxas_validas),
                    'q25': np.percentile(taxas_validas, 25) if len(taxas_validas) > 1 else taxas_validas[0],
                    'q75': np.percentile(taxas_validas, 75) if len(taxas_validas) > 1 else taxas_validas[0],
                    'amostra': len(taxas_validas)
                }
    
    # 5. ORDENAR CASOS DE SUCESSO
    analysis['casos_sucesso_reais'].sort(key=lambda x: x.get('creditos_emitidos', 0), reverse=True)
    
    # 6. PREÇOS DO MERCADO (baseados em dados conhecidos)
    analysis['precos_mercado'] = {
        'agricultura': {'min': 15, 'max': 30, 'avg': 22.5, 'fonte': 'Média de mercado'},
        'agroflorestal': {'min': 20, 'max': 40, 'avg': 30, 'fonte': 'Média de mercado'},
        'energia': {'min': 10, 'max': 25, 'avg': 17.5, 'fonte': 'Média de mercado'}
    }
    
    return analysis

def extract_project_info_with_mapping(row, col_mapping, categoria, sheet_name):
    """Extrai informações de projeto usando mapeamento específico"""
    try:
        info = {
            'categoria': categoria,
            'fonte': sheet_name,
            'creditos_emitidos': 0,
            'creditos_retirados': 0,
            'area_hectares': 0,
            'duracao_anos': 10,
            'pais': 'Não especificado',
            'nome': f"Projeto {categoria}",
            'metodologia': 'Não especificada',
            'standard': 'Não especificado',
            'ano_inicio': None
        }
        
        # Extrair nome do projeto
        nome_col = col_mapping.get('nome')
        if nome_col and nome_col in row:
            nome_val = row[nome_col]
            if pd.notna(nome_val):
                info['nome'] = str(nome_val)[:100] + "..." if len(str(nome_val)) > 100 else str(nome_val)
        
        # Extrair créditos emitidos
        creditos_col = col_mapping.get('creditos')
        if creditos_col and creditos_col in row:
            creditos_val = row[creditos_col]
            if pd.notna(creditos_val):
                try:
                    info['creditos_emitidos'] = float(creditos_val)
                except:
                    pass
        
        # Extrair créditos retirados
        retirados_col = col_mapping.get('creditos_retirados')
        if retirados_col and retirados_col in row:
            retirados_val = row[retirados_col]
            if pd.notna(retirados_val):
                try:
                    info['creditos_retirados'] = float(retirados_val)
                except:
                    pass
        
        # Extrair país
        pais_col = col_mapping.get('pais')
        if pais_col and pais_col in row:
            pais_val = row[pais_col]
            if pd.notna(pais_val):
                pais_str = str(pais_val)
                # Traduzir país
                pais_lower = pais_str.lower()
                if 'brazil' in pais_lower or 'brasil' in pais_lower:
                    info['pais'] = 'Brasil'
                elif 'united states' in pais_lower or 'usa' in pais_lower:
                    info['pais'] = 'Estados Unidos'
                elif 'argentina' in pais_lower:
                    info['pais'] = 'Argentina'
                elif 'chile' in pais_lower:
                    info['pais'] = 'Chile'
                elif 'colombia' in pais_lower:
                    info['pais'] = 'Colômbia'
                elif 'mexico' in pais_lower:
                    info['pais'] = 'México'
                elif 'peru' in pais_lower:
                    info['pais'] = 'Peru'
                elif 'india' in pais_lower:
                    info['pais'] = 'Índia'
                elif 'china' in pais_lower:
                    info['pais'] = 'China'
                elif 'indonesia' in pais_lower:
                    info['pais'] = 'Indonésia'
                elif 'kenya' in pais_lower:
                    info['pais'] = 'Quênia'
                else:
                    info['pais'] = pais_str.title()
        
        # Calcular métricas derivadas
        if info['area_hectares'] > 0 and info['creditos_emitidos'] > 0:
            info['taxa_sequestro'] = info['creditos_emitidos'] / info['duracao_anos'] / info['area_hectares']
            info['receita_estimada'] = info['creditos_emitidos'] * 22.5
            info['receita_anual'] = info['receita_estimada'] / info['duracao_anos']
            info['receita_por_hectare'] = info['receita_anual'] / info['area_hectares'] if info['area_hectares'] > 0 else 0
        
        # Calcular taxa de aposentadoria
        if info['creditos_emitidos'] > 0:
            info['taxa_aposentadoria_projeto'] = (info['creditos_retirados'] / info['creditos_emitidos']) * 100
        
        return info if info['creditos_emitidos'] > 0 else None
        
    except Exception as e:
        return None

def calculate_potential_revenue(hectares, practice_type, analysis):
    """Calcula receita potencial baseada em dados reais do dataset"""
    
    # Obter taxas reais da análise
    taxas = analysis.get('taxas_sequestro_reais', {}).get(practice_type, {})
    
    # Obter preços reais
    precos = analysis.get('precos_mercado', {}).get(practice_type, {'avg': 22.5})
    
    if taxas and 'media' in taxas:
        # Usar dados reais
        rate_avg = taxas['media']
        rate_min = taxas.get('q25', rate_avg * 0.7)
        rate_max = taxas.get('q75', rate_avg * 1.3)
        
        data_source = f"Baseado em {taxas.get('amostra', 0)} projetos reais"
        preco_avg = precos.get('avg', 22.5)
    else:
        # Fallback para estimativas conservadoras baseadas no dataset
        default_rates = {
            'agricultura': 0.5,  # Conservador para agricultura
            'agroflorestal': 3.0,  # Conservador para agrofloresta
            'energia': 1.5  # Conservador para energia
        }
        rate_avg = default_rates.get(practice_type, 0.5)
        rate_min = rate_avg * 0.6
        rate_max = rate_avg * 1.4
        preco_avg = 22.5
        data_source = "Estimativa conservadora baseada em dados do mercado"
    
    calculations = {
        'hectares': hectares,
        'practice_type': practice_type,
        'annual_sequestration_avg': hectares * rate_avg,
        'annual_revenue_avg': hectares * rate_avg * preco_avg,
        '10yr_revenue_avg': hectares * rate_avg * preco_avg * 10,
        'price_per_ton': f"US${formatar_br(preco_avg)} (média do mercado)",
        'sequestration_per_ha': f"{formatar_br_dec(rate_min, 1)}-{formatar_br_dec(rate_max, 1)} tCO2/ha/ano",
        'data_source': data_source,
        'projects_analyzed': taxas.get('amostra', 0) if taxas else 0
    }
    
    return calculations

def calculate_break_even(hectares, investment_cost, practice_type, analysis):
    """Calcula ponto de equilibrio baseado em dados reais"""
    revenue = calculate_potential_revenue(hectares, practice_type, analysis)
    
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
# COMPONENTES DE UI - REFINADOS
# =========================

def create_hero_section(analysis):
    """Cria seção hero com dados reais do dataset"""
    
    if not analysis or 'estatisticas_gerais' not in analysis:
        st.markdown(f"""
        <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                    background: linear-gradient(135deg, #27ae60, #229954); 
                    color: white; margin-bottom: 2rem;'>
            <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>🌱 Mercado Real de Carbono Agrícola</h1>
            <h3 style='font-weight: 300;'>Baseado em dados reais da FAO</h3>
        </div>
        """, unsafe_allow_html=True)
        return
    
    stats = analysis['estatisticas_gerais']
    
    # Formatar valores para exibição
    total_projetos_com_creditos = stats.get('total_projetos_com_creditos', 0)
    total_creditos = stats.get('total_creditos', 0)
    total_aposentado = stats.get('total_aposentado', 0)
    paises_com_projetos = stats.get('paises_com_projetos', 0)
    receita_real = stats.get('receita_real', 0)
    taxa_aposentadoria = stats.get('taxa_aposentadoria', 0)
    
    total_creditos_fmt = formatar_milhoes(total_creditos)
    total_aposentado_fmt = formatar_milhoes(total_aposentado)
    receita_real_fmt = formatar_moeda_curta(receita_real)
    
    st.markdown(f"""
    <div style='text-align: center; padding: 2rem; border-radius: 15px; 
                background: linear-gradient(135deg, #27ae60, #229954); 
                color: white; margin-bottom: 2rem;'>
        <h1 style='font-size: 3rem; margin-bottom: 0.5rem;'>🌱 Mercado Real de Carbono Agrícola</h1>
        <h3 style='font-weight: 300;'>Baseado em {formatar_br_inteiro(total_projetos_com_creditos)} projetos que emitiram créditos (FAO)</h3>
        <p style='font-size: 1.1rem; opacity: 0.9;'>
            {total_creditos_fmt} créditos emitidos • {total_aposentado_fmt} vendidos • {paises_com_projetos} países • 
            US$ {receita_real_fmt} em receita real • 
            {formatar_br_dec(taxa_aposentadoria, 3)}% dos créditos já vendidos
        </p>
    </div>
    """, unsafe_allow_html=True)

def create_revenue_calculator(analysis):
    """Calculadora baseada em dados reais do dataset"""
    with st.expander("🧮 CALCULE SEU POTENCIAL COM DADOS REAIS", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            hectares = st.number_input("Tamanho da propriedade (hectares):", 
                                     min_value=1.0, max_value=10000.0, value=100.0, step=10.0)
        
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
            investment = st.number_input("Investimento inicial (US$):", 
                                       min_value=0.0, max_value=1000000.0, value=10000.0, step=1000.0)
        
        # Calcular com dados reais
        revenue = calculate_potential_revenue(hectares, practice_type, analysis)
        break_even = calculate_break_even(hectares, investment, practice_type, analysis)
        
        # Mostrar base de dados
        if revenue['projects_analyzed'] > 0:
            st.info(f"📊 **Baseado em {formatar_br_inteiro(revenue['projects_analyzed'])} projetos certificados** • {revenue['data_source']}")
        else:
            st.info(f"📊 **Baseado em dados de mercado consolidados** • {revenue['data_source']}")
        
        # Resultados
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Receita Anual", f"US$ {formatar_moeda_curta(revenue['annual_revenue_avg'])}")
        with col2:
            st.metric("📈 Receita 10 anos", f"US$ {formatar_moeda_curta(revenue['10yr_revenue_avg'])}")
        with col3:
            st.metric("⏱️ Retorno (anos)", f"{formatar_br_dec(break_even['break_even_years'], 1)}")
        with col4:
            st.metric("📊 ROI 5 anos", f"{formatar_br_dec(break_even['roi_5yr'], 1)}%")
        
        # Detalhes
        with st.expander("📋 Ver detalhes do cálculo"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Preço do carbono:** {revenue['price_per_ton']}")
                st.write(f"**Sequestro estimado:** {revenue['sequestration_per_ha']}")
                st.write(f"**Fonte dos dados:** {revenue['data_source']}")
                
                # Mostrar estatísticas reais se disponíveis
                taxas = analysis.get('taxas_sequestro_reais', {}).get(practice_type, {})
                if taxas and 'media' in taxas:
                    st.write(f"**Taxa real média:** {formatar_br_dec(taxas.get('media', 0), 2)} tCO2/ha/ano")
                    st.write(f"**Variação real:** {formatar_br_dec(taxas.get('min', 0), 2)} - {formatar_br_dec(taxas.get('max', 0), 2)} tCO2/ha/ano")
            
            with col2:
                st.write(f"**Sequestro total anual:** {formatar_br_dec(revenue['annual_sequestration_avg'], 1)} tCO2")
                st.write(f"**Receita mensal:** US$ {formatar_moeda_curta(break_even['monthly_revenue'])}")
                st.write(f"**Investimento inicial:** US$ {formatar_moeda_curta(investment)}")

# =========================
# PÁGINAS PRINCIPAIS - REFINADAS
# =========================

def render_opportunities_home(dataframes, analysis):
    """Página inicial com tudo baseado em dados reais do dataset"""
    create_hero_section(analysis)
    
    # Calculadora de receita
    create_revenue_calculator(analysis)
    
    # Métricas reais do mercado
    st.markdown("## 📈 O Mercado Real em Números")
    
    if not analysis or 'estatisticas_gerais' not in analysis:
        st.warning("Carregando estatísticas...")
        return
    
    stats = analysis['estatisticas_gerais']
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🌱 Projetos com Créditos", 
                 formatar_br_inteiro(stats.get('total_projetos_com_creditos', 0)), 
                 f"{stats.get('paises_com_projetos', 0)} países")
    
    with col2:
        st.metric("💰 Créditos Emitidos", 
                 formatar_milhoes(stats.get('total_creditos', 0)), 
                 f"≈ {formatar_milhoes(stats.get('total_creditos', 0))} tCO2")
    
    with col3:
        st.metric("💵 Créditos Vendidos", 
                 formatar_milhoes(stats.get('total_aposentado', 0)), 
                 f"{formatar_br_dec(stats.get('taxa_aposentadoria', 0), 3)}% dos emitidos")
    
    with col4:
        st.metric("📊 Receita Real", 
                 f"US$ {formatar_moeda_curta(stats.get('receita_real', 0))}", 
                 f"Média: US$ {formatar_moeda_curta(stats.get('receita_media_por_projeto', 0))}/projeto")
    
    # Comparativo créditos emitidos vs aposentados
    st.markdown("## 🔄 Créditos Emitidos vs. Vendidos")
    
    emitidos = stats.get('total_creditos', 0)
    aposentados = stats.get('total_aposentado', 0)
    disponiveis = emitidos - aposentados
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📈 Total Emitido", formatar_milhoes(emitidos))
    with col2:
        st.metric("📉 Total Vendido", formatar_milhoes(aposentados))
    with col3:
        st.metric("💎 Disponíveis para Venda", formatar_milhoes(disponiveis))
    
    # Gráfico de pizza
    dados_pizza = pd.DataFrame({
        'Status': ['Emitidos e Disponíveis', 'Vendidos'],
        'Créditos': [disponiveis, aposentados],
        'Cor': ['#2ecc71', '#e74c3c']
    })
    
    fig = px.pie(dados_pizza, values='Créditos', names='Status',
                 title='Distribuição de Créditos por Status',
                 color='Status',
                 color_discrete_map={'Emitidos e Disponíveis': '#2ecc71', 'Vendidos': '#e74c3c'})
    
    fig.update_traces(textinfo='percent+label')
    st.plotly_chart(fig, use_container_width=True)
    
    # Distribuição por categoria
    st.markdown("## 📊 Distribuição por Tipo de Projeto")
    
    categorias = analysis.get('categorias_projetos', {})
    if categorias:
        cat_data = []
        for cat_name, cat_info in categorias.items():
            if cat_info['projetos_com_creditos'] > 0:
                cat_data.append({
                    'Categoria': cat_name.title(),
                    'Projetos': cat_info['projetos_com_creditos'],
                    'Créditos (milhões)': cat_info['creditos'] / 1000000,
                    'Créditos': cat_info['creditos']
                })
        
        if cat_data:
            cat_df = pd.DataFrame(cat_data)
            
            # Gráfico de barras
            fig = px.bar(cat_df, x='Categoria', y='Créditos (milhões)',
                         title='Créditos Emitidos por Categoria',
                         color='Categoria',
                         color_discrete_sequence=['#2ecc71', '#27ae60', '#f39c12'],
                         text='Créditos (milhões)')
            
            fig.update_traces(texttemplate='%{text:.2f}M', textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabela detalhada
            with st.expander("📋 Ver detalhes por categoria"):
                display_df = cat_df.copy()
                display_df['Projetos_formatado'] = display_df['Projetos'].apply(formatar_br_inteiro)
                display_df['Créditos_formatado'] = display_df['Créditos'].apply(formatar_milhoes)
                
                st.dataframe(
                    display_df[['Categoria', 'Projetos_formatado', 'Créditos_formatado']].rename(
                        columns={'Projetos_formatado': 'Projetos', 'Créditos_formatado': 'Créditos'}
                    ),
                    use_container_width=True,
                    hide_index=True
                )
    
    # Distribuição por país
    st.markdown("## 🌍 Distribuição por País")
    
    paises = analysis.get('projetos_por_pais', {})
    if paises:
        # Criar DataFrame para o gráfico
        paises_df = pd.DataFrame(list(paises.items()), columns=['País', 'Projetos'])
        paises_df = paises_df.sort_values('Projetos', ascending=False).head(15)
        
        # Gráfico de barras
        fig = px.bar(paises_df, x='País', y='Projetos',
                     title='Top 15 Países com Mais Projetos',
                     color='Projetos',
                     color_continuous_scale='Greens',
                     text='Projetos')
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    
    # Standards mais utilizados
    st.markdown("## 🏛️ Standards Mais Utilizados")
    
    standards = analysis.get('standards_mais_utilizados', {})
    if standards:
        standards_df = pd.DataFrame([
            {'Standard': k, 'Total Projetos': v.get('total_projetos', 0)}
            for k, v in standards.items()
        ])
        
        if not standards_df.empty:
            standards_df = standards_df.sort_values('Total Projetos', ascending=False).head(10)
            
            fig = px.bar(standards_df, x='Standard', y='Total Projetos',
                         title='Top 10 Standards por Número de Projetos',
                         color='Total Projetos',
                         color_continuous_scale='Blues')
            
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

def render_project_explorer(dataframes, sheet_names, analysis):
    """Explorador de projetos reais do dataset"""
    st.markdown("## 🔍 Explore Projetos Reais do Dataset")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Selecionar tipo de projeto
        project_types = [
            ("4. Agriculture", "🌱 Agricultura"),
            ("5. Agroforestry-AR & Grassland", "🌳 Agrofloresta"),
            ("6. Energy and Other", "⚡ Energia"),
            ("7. Plan Vivo, Acorn, Social C", "🌍 Plan Vivo/Acorn"),
            ("8. Puro.earth", "🔥 Biochar (Puro.earth)"),
            ("9. Nori and BCarbon", "🌾 Nori/BCarbon")
        ]
        
        selected_type = st.selectbox(
            "Tipo de Projeto:",
            project_types,
            format_func=lambda x: x[1],
            index=0
        )[0]
    
    with col2:
        # Filtro por mínimo de créditos
        min_creditos = st.number_input("Mínimo de créditos:", 
                                      min_value=0, value=1000, step=100)
    
    with col3:
        # Ordenação
        sort_by = st.selectbox(
            "Ordenar por:",
            ["Créditos (maior primeiro)", "Créditos (menor primeiro)", "Nome (A-Z)", "Nome (Z-A)"]
        )
    
    # Carregar e processar dados da aba selecionada
    if selected_type in dataframes:
        df = dataframes[selected_type]
        df_clean = clean_dataframe(df)
        
        # Obter mapeamento de colunas
        col_mapping = ABA_COLUMN_MAPPING.get(selected_type, {})
        
        # Processar dados
        projetos = []
        for idx, row in df_clean.iterrows():
            try:
                projeto_info = extract_project_info_with_mapping(row, col_mapping, 
                                                                 CATEGORY_MAPPING.get(selected_type, 'agricultura'), 
                                                                 selected_type)
                if projeto_info and projeto_info.get('creditos_emitidos', 0) >= min_creditos:
                    projetos.append(projeto_info)
            except:
                continue
        
        # Ordenar
        if sort_by == "Créditos (maior primeiro)":
            projetos.sort(key=lambda x: x.get('creditos_emitidos', 0), reverse=True)
        elif sort_by == "Créditos (menor primeiro)":
            projetos.sort(key=lambda x: x.get('creditos_emitidos', 0))
        elif sort_by == "Nome (A-Z)":
            projetos.sort(key=lambda x: x.get('nome', '').lower())
        elif sort_by == "Nome (Z-A)":
            projetos.sort(key=lambda x: x.get('nome', '').lower(), reverse=True)
        
        # Exibir resultados
        st.markdown(f"### 📊 {len(projetos)} projetos encontrados")
        
        if projetos:
            # Tabela resumida
            table_data = []
            for projeto in projetos[:100]:  # Limitar a 100 para performance
                table_data.append({
                    'Nome': projeto.get('nome', ''),
                    'País': projeto.get('pais', ''),
                    'Créditos': formatar_milhoes(projeto.get('creditos_emitidos', 0)),
                    'Vendidos': formatar_milhoes(projeto.get('creditos_retirados', 0)),
                    'Categoria': projeto.get('categoria', '').title(),
                    'Fonte': projeto.get('fonte', '')
                })
            
            if table_data:
                table_df = pd.DataFrame(table_data)
                st.dataframe(table_df, use_container_width=True, height=400)
                
                # Botão para baixar
                csv = table_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Baixar dados (CSV)",
                    data=csv,
                    file_name=f"projetos_{selected_type.replace('. ', '_').replace(' ', '_').lower()}.csv",
                    mime="text/csv"
                )
        else:
            st.info("Nenhum projeto encontrado com os critérios selecionados.")
    else:
        st.warning(f"A aba '{selected_type}' não foi encontrada no dataset.")

def render_market_statistics(analysis):
    """Estatísticas detalhadas do mercado"""
    st.markdown("## 📊 Estatísticas Detalhadas do Dataset")
    
    if not analysis:
        st.warning("Carregando análise...")
        return
    
    stats = analysis['estatisticas_gerais']
    
    # Resumo
    st.markdown("### 📈 Resumo do Mercado")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🌱 Projetos com Créditos", formatar_br_inteiro(stats.get('total_projetos_com_creditos', 0)))
    with col2:
        st.metric("💰 Créditos Totais", formatar_milhoes(stats.get('total_creditos', 0)))
    with col3:
        st.metric("💵 Receita Real", f"US$ {formatar_moeda_curta(stats.get('receita_real', 0))}")
    with col4:
        st.metric("📊 Taxa de Venda", f"{formatar_br_dec(stats.get('taxa_aposentadoria', 0), 3)}%")
    
    # Detalhes financeiros
    st.markdown("### 💰 Detalhes Financeiros")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💎 Receita Potencial", 
                 f"US$ {formatar_moeda_curta(stats.get('receita_potencial', 0))}",
                 "Se todos os créditos fossem vendidos")
    
    with col2:
        st.metric("🏆 Média por Projeto", 
                 f"US$ {formatar_moeda_curta(stats.get('receita_media_por_projeto', 0))}",
                 "Receita real / projeto")
    
    with col3:
        st.metric("🏷️ Preço Médio", 
                 f"US$ {formatar_br_dec(stats.get('preco_medio', 0), 2)}/tCO2",
                 "Baseado em dados de mercado")
    
    # Taxas de sequestro
    st.markdown("### 📈 Taxas Reais de Sequestro")
    
    taxas = analysis.get('taxas_sequestro_reais', {})
    if taxas:
        for categoria, dados in taxas.items():
            if 'media' in dados:
                st.markdown(f"#### {categoria.title()}")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Média", f"{formatar_br_dec(dados.get('media', 0), 2)} tCO2/ha/ano")
                with col2:
                    st.metric("Mín-Máx", f"{formatar_br_dec(dados.get('min', 0), 2)}-{formatar_br_dec(dados.get('max', 0), 2)}")
                with col3:
                    st.metric("25%-75%", f"{formatar_br_dec(dados.get('q25', 0), 2)}-{formatar_br_dec(dados.get('q75', 0), 2)}")
                with col4:
                    st.metric("Amostra", formatar_br_inteiro(dados.get('amostra', 0)))
    
    # Preços do mercado
    st.markdown("### 💰 Preços do Mercado por Categoria")
    
    precos = analysis.get('precos_mercado', {})
    for categoria, dados in precos.items():
        if 'avg' in dados:
            st.write(f"**{categoria.title()}:** US${formatar_br_dec(dados.get('avg', 22.5), 1)}/tCO2 ({dados.get('fonte', 'Média de mercado')})")

def render_how_to_participate():
    """Como participar baseado nos padrões do dataset"""
    st.markdown("## 📞 Como Participar (Baseado em Projetos Reais)")
    
    st.markdown("""
    ### 📋 Passos Baseados em Projetos Existentes
    
    1. **Escolha um padrão certificado** (Verra, Gold Standard, Plan Vivo, etc.)
    2. **Implemente práticas sustentáveis** documentadas nas metodologias
    3. **Monitore e reporte** seguindo protocolos estabelecidos
    4. **Submeta para verificação** por auditoria independente
    5. **Registre e venda** seus créditos em plataformas certificadas
    
    ### 💡 Dicas Baseadas em Dados Reais
    
    - **Estude projetos similares** ao seu na mesma região
    - **Considere o custo de certificação** (US$ 10.000 - 50.000 para projetos pequenos)
    - **Calcule com dados reais** usando nossa calculadora
    - **Comece pequeno** e expanda gradualmente
    
    ### 🏛️ Principais Padrões Encontrados no Dataset
    
    - **Verra (VCS):** Maior padrão do mundo, usado em 2133+ projetos
    - **Gold Standard:** Foco em desenvolvimento sustentável
    - **Plan Vivo:** Foco em comunidades e pequenos produtores
    - **Puro.earth:** Especializado em biochar
    - **Nori/BCarbon:** Especializados em carbono no solo
    
    *💡 Baseado em análise de {formatar_br_inteiro(DATASET_STATS['total_projetos'])} projetos reais do dataset FAO*
    """)

# =========================
# CARGA DE DADOS - OTIMIZADA
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
        
        # Carregar apenas as abas relevantes
        abas_para_carregar = DATASET_STATS['abas_com_projetos'] + ['1. Standards']
        
        for sheet in excel.sheet_names:
            if sheet in abas_para_carregar:
                try:
                    # Carregar sem definir índice automático
                    df = excel.parse(sheet, header=0, index_col=None)
                    
                    # Aplicar limpeza básica
                    df_clean = clean_dataframe(df)
                    
                    data[sheet] = df_clean
                    sheet_names.append(sheet)
                    
                except Exception as e:
                    st.warning(f"⚠️ Aviso na aba '{sheet}': {str(e)[:100]}")
                    data[sheet] = pd.DataFrame()
        
        return data, sheet_names
        
    except Exception as e:
        st.error(f"❌ Erro crítico ao carregar dados: {str(e)}")
        return None, None

# =========================
# APLICAÇÃO PRINCIPAL - REFINADA
# =========================

def main():
    # Carregar dados
    dataframes, sheet_names = load_fao_dataset()
    
    if dataframes is None:
        st.error("Não foi possível continuar sem o dataset.")
        return
    
    # Analisar dataset
    if 'complete_analysis' not in st.session_state:
        try:
            with st.spinner("🔍 Analisando dados do dataset FAO..."):
                analysis = analyze_complete_dataset(dataframes)
                st.session_state.complete_analysis = analysis
                st.session_state.dataframes = dataframes
                st.session_state.sheet_names = sheet_names
        except Exception as e:
            st.error(f"Erro ao analisar o dataset: {str(e)}")
            # Usar dados consolidados como fallback
            analysis = {
                'estatisticas_gerais': DATASET_STATS.copy(),
                'projetos_por_pais': {},
                'taxas_sequestro_reais': {},
                'casos_sucesso_reais': [],
                'precos_mercado': {},
                'metodologias_populares': {},
                'standards_mais_utilizados': {},
                'comparativo_emitidos_vs_aposentados': {
                    'total_emitido': DATASET_STATS['total_creditos_emitidos'],
                    'total_aposentado': DATASET_STATS['total_creditos_aposentados']
                },
                'timeline_data': {'anos': [], 'registrados': [], 'emitidos': [], 'aposentados': []},
                'categorias_projetos': {
                    'agricultura': {'total': 0, 'creditos': 0, 'area_total': 0, 'projetos_com_creditos': 0},
                    'agroflorestal': {'total': 0, 'creditos': 0, 'area_total': 0, 'projetos_com_creditos': 0},
                    'energia': {'total': 0, 'creditos': 0, 'area_total': 0, 'projetos_com_creditos': 0}
                }
            }
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
        if analysis and 'estatisticas_gerais' in analysis:
            stats = analysis['estatisticas_gerais']
            total_projetos_com_creditos = stats.get('total_projetos_com_creditos', 0)
            total_creditos = stats.get('total_creditos', 0)
            total_aposentado = stats.get('total_aposentado', 0)
            taxa_aposentadoria = stats.get('taxa_aposentadoria', 0)
            
            st.markdown("### 📈 Dados Reais")
            st.info(f"""
            **{formatar_br_inteiro(total_projetos_com_creditos)}** projetos com créditos  
            **{formatar_milhoes(total_creditos)}** créditos emitidos  
            **{formatar_milhoes(total_aposentado)}** créditos vendidos  
            **{formatar_br_dec(taxa_aposentadoria, 3)}%** taxa de venda
            """)
        
        st.markdown("---")
        st.markdown("### 📁 Fonte dos Dados")
        st.markdown("""
        - **Dataset:** FAO Agrifood Carbon Markets
        - **Projetos:** {total_projetos} certificados
        - **Créditos:** {total_creditos} emitidos
        - **Foco:** Dados reais de mercado
        """.format(
            total_projetos=formatar_br_inteiro(DATASET_STATS['total_projetos']),
            total_creditos=formatar_milhoes(DATASET_STATS['total_creditos_emitidos'])
        ))
    
    # Renderizar página
    if page == "🏠 Mercado Real":
        render_opportunities_home(dataframes, analysis)
    elif page == "🔍 Projetos":
        render_project_explorer(dataframes, sheet_names, analysis)
    elif page == "📊 Estatísticas":
        render_market_statistics(analysis)
    else:
        render_how_to_participate()
    
    # Rodapé
    create_footer(analysis)

def create_footer(analysis):
    """Rodapé informativo"""
    st.markdown("---")
    
    if analysis and 'estatisticas_gerais' in analysis:
        stats = analysis['estatisticas_gerais']
        
        st.markdown(f"""
        <div style='text-align: center; padding: 1rem;'>
            <p style='color: #7f8c8d;'>
            <strong>🌱 Dashboard Baseado em Dados Reais FAO</strong> | 
            {formatar_br_inteiro(stats.get('total_projetos_com_creditos', 0))} projetos analisados | 
            {formatar_milhoes(stats.get('total_creditos', 0))} créditos emitidos |
            {formatar_br_dec(stats.get('taxa_aposentadoria', 0), 3)}% taxa de venda
            </p>
            <p style='color: #95a5a6; font-size: 0.8rem;'>
            💰 <strong>Receita Real:</strong> US$ {formatar_moeda_curta(stats.get('receita_real', 0))} | 
            📈 <strong>Receita Potencial:</strong> US$ {formatar_moeda_curta(stats.get('receita_potencial', 0))}
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
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")
        st.info("Recarregue a página ou verifique o arquivo Dataset.xlsx")
