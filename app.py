import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import seaborn as sns
from scipy import stats
from scipy.signal import fftconvolve
from joblib import Parallel, delayed
import warnings
from matplotlib.ticker import FuncFormatter
from SALib.sample.sobol import sample
from SALib.analyze.sobol import analyze

# Tentar importar yfinance com fallback
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

np.random.seed(50)  # Garante reprodutibilidade

# Configurações iniciais
st.set_page_config(page_title="Simulador de Emissões CO₂eq", layout="wide")
warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
np.seterr(divide='ignore', invalid='ignore')
plt.rcParams['figure.dpi'] = 150
plt.rcParams['font.size'] = 10
sns.set_style("whitegrid")

# =============================================================================
# INICIALIZAÇÃO DA SESSION STATE
# =============================================================================

# Inicializar todas as variáveis de session state necessárias
def inicializar_session_state():
    if 'preco_carbono' not in st.session_state:
        st.session_state.preco_carbono = 85.50
    if 'moeda_carbono' not in st.session_state:
        st.session_state.moeda_carbono = "€"
    if 'taxa_cambio' not in st.session_state:
        st.session_state.taxa_cambio = 5.50
    if 'moeda_real' not in st.session_state:
        st.session_state.moeda_real = "R$"
    if 'cotacao_atualizada' not in st.session_state:
        st.session_state.cotacao_atualizada = False
    if 'run_simulation' not in st.session_state:
        st.session_state.run_simulation = False
    if 'mostrar_atualizacao' not in st.session_state:
        st.session_state.mostrar_atualizacao = False
    if 'ano_contrato' not in st.session_state:
        st.session_state.ano_contrato = 2025  # Inicia com CarbonDec25
    if 'contrato_atual' not in st.session_state:
        st.session_state.contrato_atual = "CarbonDec25"

# Chamar a inicialização
inicializar_session_state()

# Título do aplicativo
st.title("Simulador de Emissões de tCO₂eq")
st.markdown("""
Esta ferramenta projeta os Créditos de Carbono ao calcular as emissões de gases de efeito estufa para dois contextos de gestão de resíduos
""")

# =============================================================================
# FUNÇÕES DE COTAÇÃO AUTOMÁTICA DO CARBONO E CÂMBIO
# =============================================================================

def obter_ticker_carbono_atual():
    """
    Determina automaticamente o ticker do contrato futuro de carbono mais relevante
    Começa com CarbonDec25 e migra automaticamente após o vencimento
    """
    hoje = datetime.now()
    ano_atual = hoje.year
    mes_atual = hoje.month
    
    # VERIFICAR SE O CONTRATO CarbonDec25 JÁ VENCEU
    # O contrato CarbonDec25 vence em dezembro de 2025
    vencimento_carbondec25 = datetime(2025, 12, 15)  # Data aproximada de vencimento
    
    if hoje > vencimento_carbondec25:
        # CarbonDec25 já venceu, usar próximo contrato
        if mes_atual >= 9:
            ano_contrato = ano_atual + 1
        else:
            ano_contrato = ano_atual
        contrato_nome = f"CarbonDec{ano_contrato}"
    else:
        # CarbonDec25 ainda está válido
        ano_contrato = 2025
        contrato_nome = "CarbonDec25"
    
    # Formata o ano para 2 dígitos (25, 26, etc.)
    ano_2_digitos = str(ano_contrato)[-2:]
    
    ticker = f'CO2Z{ano_2_digitos}.NYB'
    return ticker, ano_contrato, contrato_nome

def obter_cotacao_carbono():
    """
    Obtém a cotação em tempo real do contrato futuro de carbono atual
    """
    if not YFINANCE_AVAILABLE:
        ticker_atual, ano_contrato, contrato_nome = obter_ticker_carbono_atual()
        return 85.50, "€", f"EUA {contrato_nome} (yfinance não disponível)", False
    
    try:
        # Obtém o ticker atual automaticamente
        ticker_atual, ano_contrato, contrato_nome = obter_ticker_carbono_atual()
        ano_2_digitos = str(ano_contrato)[-2:]
        
        simbolos_tentativas = [
            ticker_atual,                    # Contrato atual (ex: CO2Z25.NYB)
            f'CFIZ{ano_2_digitos}.NYB',     # Alternativa com mesmo ano
            'CARBON-FUTURE',                # Genérico
        ]
        
        cotacao = None
        simbolo_usado = None
        
        for simbolo in simbolos_tentativas:
            try:
                ticker = yf.Ticker(simbolo)
                hist = ticker.history(period='1d')
                
                if not hist.empty and not pd.isna(hist['Close'].iloc[-1]):
                    cotacao = hist['Close'].iloc[-1]
                    simbolo_usado = simbolo
                    break
                    
            except Exception as e:
                continue
        
        if cotacao is None:
            # Fallback para dados de exemplo
            return 85.50, "€", f"EUA {contrato_nome} (Referência)", False
        
        return cotacao, "€", f"EUA {contrato_nome}", True
        
    except Exception as e:
        ticker_atual, ano_contrato, contrato_nome = obter_ticker_carbono_atual()
        return 85.50, "€", f"EUA {contrato_nome} (Erro)", False

def obter_cotacao_euro_real():
    """
    Obtém a cotação em tempo real do Euro em relação ao Real Brasileiro
    """
    if not YFINANCE_AVAILABLE:
        return 5.50, "R$", False
    
    try:
        # Ticker para EUR/BRL (Euro para Real Brasileiro)
        ticker = yf.Ticker("EURBRL=X")
        hist = ticker.history(period='1d')
        
        if not hist.empty and not pd.isna(hist['Close'].iloc[-1]):
            cotacao = hist['Close'].iloc[-1]
            return cotacao, "R$", True
        else:
            # Fallback para valor de referência
            return 5.50, "R$", False
            
    except Exception as e:
        return 5.50, "R$", False

def calcular_valor_creditos(emissoes_evitadas_tco2eq, preco_carbono_por_tonelada, moeda, taxa_cambio=1):
    """
    Calcula o valor financeiro das emissões evitadas baseado no preço do carbono
    """
    valor_total = emissoes_evitadas_tco2eq * preco_carbono_por_tonelada * taxa_cambio
    return valor_total

def verificar_migracao_contrato():
    """
    Verifica se precisa migrar para um novo contrato e atualiza o session state
    """
    ticker_atual, ano_contrato, contrato_nome = obter_ticker_carbono_atual()
    
    # Verificar se houve mudança no contrato
    if st.session_state.ano_contrato != ano_contrato or st.session_state.contrato_atual != contrato_nome:
        st.session_state.ano_contrato = ano_contrato
        st.session_state.contrato_atual = contrato_nome
        return True
    return False

def exibir_cotacao_carbono():
    """
    Exibe a cotação do carbono com informações sobre o contrato atual
    """
    st.sidebar.header("💰 Mercado de Carbono e Câmbio")
    
    if not YFINANCE_AVAILABLE:
        st.sidebar.warning("⚠️ **yfinance não instalado**")
        st.sidebar.info("Para cotações em tempo real, execute:")
        st.sidebar.code("pip install yfinance")
    
    # Verificar migração automática de contrato
    if verificar_migracao_contrato():
        st.sidebar.info(f"🔄 Migração automática: {st.session_state.contrato_atual}")
    
    # Botão para atualizar cotações
    if st.sidebar.button("🔄 Atualizar Cotações"):
        st.session_state.cotacao_atualizada = True
        st.session_state.mostrar_atualizacao = True

    # Obtém informações do contrato atual
    ticker_atual, ano_contrato, contrato_nome = obter_ticker_carbono_atual()
    
    # Mostrar mensagem de atualização se necessário
    if st.session_state.get('mostrar_atualizacao', False):
        st.sidebar.info("🔄 Atualizando cotações...")
        st.session_state.mostrar_atualizacao = False
    
    if st.session_state.get('cotacao_atualizada', False):
        # Obter cotação do carbono
        preco_carbono, moeda, contrato_info, sucesso_carbono = obter_cotacao_carbono()
        
        # Obter cotação do Euro
        preco_euro, moeda_real, sucesso_euro = obter_cotacao_euro_real()
        
        # Mostrar resultados
        if sucesso_carbono:
            st.sidebar.success(f"**{contrato_info}**")
        else:
            st.sidebar.info(f"**{contrato_info}**")
        
        if sucesso_euro:
            st.sidebar.success(f"**EUR/BRL Atualizado**")
        else:
            st.sidebar.info(f"**EUR/BRL Referência**")
        
        # Atualizar session state
        st.session_state.preco_carbono = preco_carbono
        st.session_state.moeda_carbono = moeda
        st.session_state.taxa_cambio = preco_euro
        st.session_state.moeda_real = moeda_real
        
        # Resetar flag
        st.session_state.cotacao_atualizada = False

    # Exibe cotação atual do carbono
    st.sidebar.metric(
        label=f"{st.session_state.contrato_atual} (tCO₂eq)",
        value=f"{st.session_state.moeda_carbono} {st.session_state.preco_carbono:.2f}",
        help=f"Contrato futuro com vencimento Dezembro {st.session_state.ano_contrato}"
    )
    
    # Exibe cotação atual do Euro
    st.sidebar.metric(
        label="Euro (EUR/BRL)",
        value=f"{st.session_state.moeda_real} {st.session_state.taxa_cambio:.2f}",
        help="Cotação do Euro em Reais Brasileiros"
    )
    
    # Calcular preço do carbono em Reais
    preco_carbono_reais = st.session_state.preco_carbono * st.session_state.taxa_cambio
    
    st.sidebar.metric(
        label=f"{st.session_state.contrato_atual} (R$/tCO₂eq)",
        value=f"R$ {preco_carbono_reais:.2f}",
        help="Preço do carbono convertido para Reais Brasileiros"
    )
    
    # Informações adicionais
    with st.sidebar.expander("📅 Sobre os Vencimentos e Câmbio"):
        st.markdown(f"""
        **Contrato Atual:** {st.session_state.contrato_atual}
        **Ticker:** `{ticker_atual}`
        
        **Status do CarbonDec25:**
        - {'⏳ **VÁLIDO** (em vigor)' if st.session_state.contrato_atual == 'CarbonDec25' else '✅ **VENCIDO** (migrado para próximo contrato)'}
        - Vencimento: Dezembro 2025
        - Migração automática após vencimento
        
        **Câmbio Atual:**
        - 1 Euro = R$ {st.session_state.taxa_cambio:.2f}
        - Carbon em Reais: R$ {preco_carbono_reais:.2f}/tCO₂eq
        
        **Ciclo dos Contratos:**
        - Dez 2024 → CO2Z24.NYB
        - Dez 2025 → CO2Z25.NYB (Atual) 
        - Dez 2026 → CO2Z26.NYB
        - Dez 2027 → CO2Z27.NYB
        
        **Migração Automática:**
        - CarbonDec25 vigente até dezembro/2025
        - Após vencimento: migra automaticamente
        - Sem necessidade de atualização manual
        """)

# =============================================================================
# FUNÇÕES ORIGINAIS DO SEU SCRIPT
# =============================================================================

# Função para formatar números no padrão brasileiro
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

# Função de formatação para os gráficos
def br_format(x, pos):
    """
    Função de formatação para eixos de gráficos (padrão brasileiro)
    """
    if x == 0:
        return "0"
    
    # Para valores muito pequenos, usa notação científica
    if abs(x) < 0.01:
        return f"{x:.1e}".replace(".", ",")
    
    # Para valores grandes, formata com separador de milhar
    if abs(x) >= 1000:
        return f"{x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    # Para valores menores, mostra duas casas decimais
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def br_format_5_dec(x, pos):
    """
    Função de formatação para eixos de gráficos (padrão brasileiro com 5 decimais)
    """
    return f"{x:,.5f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =============================================================================
# SIDEBAR COM PARÂMETROS
# =============================================================================

# Seção de cotação do carbono
exibir_cotacao_carbono()

# Seção original de parâmetros
with st.sidebar:
    st.header("Parâmetros de Entrada")
    
    # Entrada principal de resíduos
    residuos_kg_dia = st.slider("Quantidade de resíduos (kg/dia)", 
                               min_value=10, max_value=1000, value=100, step=10)
    
    st.subheader("Parâmetros Operacionais")
    
    # Umidade com formatação brasileira (0,85 em vez de 0.85)
    umidade_valor = st.slider("Umidade do resíduo", 50, 95, 85, 1)
    umidade = umidade_valor / 100.0
    st.write(f"Umidade selecionada: {formatar_br(umidade_valor)}%")
    
    massa_exposta_kg = st.slider("Massa exposta na frente de trabalho (kg)", 50, 200, 100, 10)
    h_exposta = st.slider("Horas expostas por dia", 4, 24, 8, 1)
    
    st.subheader("Configuração de Simulação")
    anos_simulacao = st.slider("Anos de simulação", 5, 50, 20, 5)
    n_simulations = st.slider("Número de simulações Monte Carlo", 50, 1000, 100, 50)
    n_samples = st.slider("Número de amostras Sobol", 32, 256, 64, 16)
    
    if st.button("Executar Simulação"):
        st.session_state.run_simulation = True

# =============================================================================
# PARÂMETROS FIXOS (DO CÓDIGO ORIGINAL)
# =============================================================================

T = 25  # Temperatura média (ºC)
DOC = 0.15  # Carbono orgânico degradável (fração)
DOCf_val = 0.0147 * T + 0.28
MCF = 1  # Fator de correção de metano
F = 0.5  # Fração de metano no biogás
OX = 0.1  # Fator de oxidação
Ri = 0.0  # Metano recuperado

# Constante de decaimento (fixa como no script anexo)
k_ano = 0.06  # Constante de decaimento anual

# Vermicompostagem (Yang et al. 2017) - valores fixos
TOC_YANG = 0.436  # Fração de carbono orgânico total
TN_YANG = 14.2 / 1000  # Fração de nitrogênio total
CH4_C_FRAC_YANG = 0.13 / 100  # Fração do TOC emitida como CH4-C (fixo)
N2O_N_FRAC_YANG = 0.92 / 100  # Fração do TN emitida como N2O-N (fixo)
DIAS_COMPOSTAGEM = 50  # Período total de compostagem

# Perfil temporal de emissões baseado em Yang et al. (2017)
PERFIL_CH4_VERMI = np.array([
    0.02, 0.02, 0.02, 0.03, 0.03,  # Dias 1-5
    0.04, 0.04, 0.05, 0.05, 0.06,  # Dias 6-10
    0.07, 0.08, 0.09, 0.10, 0.09,  # Dias 11-15
    0.08, 0.07, 0.06, 0.05, 0.04,  # Dias 16-20
    0.03, 0.02, 0.02, 0.01, 0.01,  # Dias 21-25
    0.01, 0.01, 0.01, 0.01, 0.01,  # Dias 26-30
    0.005, 0.005, 0.005, 0.005, 0.005,  # Dias 31-35
    0.005, 0.005, 0.005, 0.005, 0.005,  # Dias 36-40
    0.002, 0.002, 0.002, 0.002, 0.002,  # Dias 41-45
    0.001, 0.001, 0.001, 0.001, 0.001   # Dias 46-50
])
PERFIL_CH4_VERMI /= PERFIL_CH4_VERMI.sum()

PERFIL_N2O_VERMI = np.array([
    0.15, 0.10, 0.20, 0.05, 0.03,  # Dias 1-5 (pico no dia 3)
    0.03, 0.03, 0.04, 0.05, 0.06,  # Dias 6-10
    0.08, 0.09, 0.10, 0.08, 0.07,  # Dias 11-15
    0.06, 0.05, 0.04, 0.03, 0.02,  # Dias 16-20
    0.01, 0.01, 0.005, 0.005, 0.005,  # Dias 21-25
    0.005, 0.005, 0.005, 0.005, 0.005,  # Dias 26-30
    0.002, 0.002, 0.002, 0.002, 0.002,  # Dias 31-35
    0.001, 0.001, 0.001, 0.001, 0.001,  # Dias 36-40
    0.001, 0.001, 0.001, 0.001, 0.001,  # Dias 41-45
    0.001, 0.001, 0.001, 0.001, 0.001   # Dias 46-50
])
PERFIL_N2O_VERMI /= PERFIL_N2O_VERMI.sum()

# Emissões pré-descarte (Feng et al. 2020)
CH4_pre_descarte_ugC_por_kg_h_min = 0.18
CH4_pre_descarte_ugC_por_kg_h_max = 5.38
CH4_pre_descarte_ugC_por_kg_h_media = 2.78

fator_conversao_C_para_CH4 = 16/12
CH4_pre_descarte_ugCH4_por_kg_h_media = CH4_pre_descarte_ugC_por_kg_h_media * fator_conversao_C_para_CH4
CH4_pre_descarte_g_por_kg_dia = CH4_pre_descarte_ugCH4_por_kg_h_media * 24 / 1_000_000

N2O_pre_descarte_mgN_por_kg = 20.26
N2O_pre_descarte_mgN_por_kg_dia = N2O_pre_descarte_mgN_por_kg / 3
N2O_pre_descarte_g_por_kg_dia = N2O_pre_descarte_mgN_por_kg_dia * (44/28) / 1000

PERFIL_N2O_PRE_DESCARTE = {1: 0.8623, 2: 0.10, 3: 0.0377}

# GWP (IPCC AR6)
GWP_CH4_20 = 79.7
GWP_N2O_20 = 273

# Período de Simulação
dias = anos_simulacao * 365
ano_inicio = datetime.now().year
data_inicio = datetime(ano_inicio, 1, 1)
datas = pd.date_range(start=data_inicio, periods=dias, freq='D')

# Perfil temporal N2O (Wang et al. 2017)
PERFIL_N2O = {1: 0.10, 2: 0.30, 3: 0.40, 4: 0.15, 5: 0.05}

# Valores específicos para compostagem termofílica (Yang et al. 2017) - valores fixos
CH4_C_FRAC_THERMO = 0.006  # Fixo
N2O_N_FRAC_THERMO = 0.0196  # Fixo

PERFIL_CH4_THERMO = np.array([
    0.01, 0.02, 0.03, 0.05, 0.08,  # Dias 1-5
    0.12, 0.15, 0.18, 0.20, 0.18,  # Dias 6-10 (pico termofílico)
    0.15, 0.12, 0.10, 0.08, 0.06,  # Dias 11-15
    0.05, 0.04, 0.03, 0.02, 0.02,  # Dias 16-20
    0.01, 0.01, 0.01, 0.01, 0.01,  # Dias 21-25
    0.005, 0.005, 0.005, 0.005, 0.005,  # Dias 26-30
    0.002, 0.002, 0.002, 0.002, 0.002,  # Dias 31-35
    0.001, 0.001, 0.001, 0.001, 0.001,  # Dias 36-40
    0.001, 0.001, 0.001, 0.001, 0.001,  # Dias 41-45
    0.001, 0.001, 0.001, 0.001, 0.001   # Dias 46-50
])
PERFIL_CH4_THERMO /= PERFIL_CH4_THERMO.sum()

PERFIL_N2O_THERMO = np.array([
    0.10, 0.08, 0.15, 0.05, 0.03,  # Dias 1-5
    0.04, 0.05, 0.07, 0.10, 0.12,  # Dias 6-10
    0.15, 0.18, 0.20, 0.18, 0.15,  # Dias 11-15 (pico termofílico)
    0.12, 0.10, 0.08, 0.06, 0.05,  # Dias 16-20
    0.04, 0.03, 0.02, 0.02, 0.01,  # Dias 21-25
    0.01, 0.01, 0.01, 0.01, 0.01,  # Dias 26-30
    0.005, 0.005, 0.005, 0.005, 0.005,  # Dias 31-35
    0.002, 0.002, 0.002, 0.002, 0.002,  # Dias 36-40
    0.001, 0.001, 0.001, 0.001, 0.001,  # Dias 41-45
    0.001, 0.001, 0.001, 0.001, 0.001,   # Dias 46-50
])
PERFIL_N2O_THERMO /= PERFIL_N2O_THERMO.sum()

# =============================================================================
# FUNÇÕES DE CÁLCULO (ADAPTADAS DO SCRIPT ANEXO)
# =============================================================================

def ajustar_emissoes_pre_descarte(O2_concentracao):
    ch4_ajustado = CH4_pre_descarte_g_por_kg_dia

    if O2_concentracao == 21:
        fator_n2o = 1.0
    elif O2_concentracao == 10:
        fator_n2o = 11.11 / 20.26
    elif O2_concentracao == 1:
        fator_n2o = 7.86 / 20.26
    else:
        fator_n2o = 1.0

    n2o_ajustado = N2O_pre_descarte_g_por_kg_dia * fator_n2o
    return ch4_ajustado, n2o_ajustado

def calcular_emissoes_pre_descarte(O2_concentracao, dias_simulacao=dias):
    ch4_ajustado, n2o_ajustado = ajustar_emissoes_pre_descarte(O2_concentracao)

    emissoes_CH4_pre_descarte_kg = np.full(dias_simulacao, residuos_kg_dia * ch4_ajustado / 1000)
    emissoes_N2O_pre_descarte_kg = np.zeros(dias_simulacao)

    for dia_entrada in range(dias_simulacao):
        for dias_apos_descarte, fracao in PERFIL_N2O_PRE_DESCARTE.items():
            dia_emissao = dia_entrada + dias_apos_descarte - 1
            if dia_emissao < dias_simulacao:
                emissoes_N2O_pre_descarte_kg[dia_emissao] += (
                    residuos_kg_dia * n2o_ajustado * fracao / 1000
                )

    return emissoes_CH4_pre_descarte_kg, emissoes_N2O_pre_descarte_kg

def calcular_emissoes_aterro(params, dias_simulacao=dias):
    umidade_val, temp_val, doc_val = params

    fator_umid = (1 - umidade_val) / (1 - 0.55)
    f_aberto = np.clip((massa_exposta_kg / residuos_kg_dia) * (h_exposta / 24), 0.0, 1.0)
    docf_calc = 0.0147 * temp_val + 0.28

    potencial_CH4_por_kg = doc_val * docf_calc * MCF * F * (16/12) * (1 - Ri) * (1 - OX)
    potencial_CH4_lote_diario = residuos_kg_dia * potencial_CH4_por_kg

    t = np.arange(1, dias_simulacao + 1, dtype=float)
    kernel_ch4 = np.exp(-k_ano * (t - 1) / 365.0) - np.exp(-k_ano * t / 365.0)
    entradas_diarias = np.ones(dias_simulacao, dtype=float)
    emissoes_CH4 = fftconvolve(entradas_diarias, kernel_ch4, mode='full')[:dias_simulacao]
    emissoes_CH4 *= potencial_CH4_lote_diario

    E_aberto = 1.91
    E_fechado = 2.15
    E_medio = f_aberto * E_aberto + (1 - f_aberto) * E_fechado
    E_medio_ajust = E_medio * fator_umid
    emissao_diaria_N2O = (E_medio_ajust * (44/28) / 1_000_000) * residuos_kg_dia

    kernel_n2o = np.array([PERFIL_N2O.get(d, 0) for d in range(1, 6)], dtype=float)
    emissoes_N2O = fftconvolve(np.full(dias_simulacao, emissao_diaria_N2O), kernel_n2o, mode='full')[:dias_simulacao]

    O2_concentracao = 21
    emissoes_CH4_pre_descarte_kg, emissoes_N2O_pre_descarte_kg = calcular_emissoes_pre_descarte(O2_concentracao, dias_simulacao)

    total_ch4_aterro_kg = emissoes_CH4 + emissoes_CH4_pre_descarte_kg
    total_n2o_aterro_kg = emissoes_N2O + emissoes_N2O_pre_descarte_kg

    return total_ch4_aterro_kg, total_n2o_aterro_kg

def calcular_emissoes_vermi(params, dias_simulacao=dias):
    umidade_val, temp_val, doc_val = params
    fracao_ms = 1 - umidade_val
    
    # Usando valores fixos para CH4_C_FRAC_YANG e N2O_N_FRAC_YANG
    ch4_total_por_lote = residuos_kg_dia * (TOC_YANG * CH4_C_FRAC_YANG * (16/12) * fracao_ms)
    n2o_total_por_lote = residuos_kg_dia * (TN_YANG * N2O_N_FRAC_YANG * (44/28) * fracao_ms)

    emissoes_CH4 = np.zeros(dias_simulacao)
    emissoes_N2O = np.zeros(dias_simulacao)

    for dia_entrada in range(dias_simulacao):
        for dia_compostagem in range(len(PERFIL_CH4_VERMI)):
            dia_emissao = dia_entrada + dia_compostagem
            if dia_emissao < dias_simulacao:
                emissoes_CH4[dia_emissao] += ch4_total_por_lote * PERFIL_CH4_VERMI[dia_compostagem]
                emissoes_N2O[dia_emissao] += n2o_total_por_lote * PERFIL_N2O_VERMI[dia_compostagem]

    return emissoes_CH4, emissoes_N2O

def calcular_emissoes_compostagem(params, dias_simulacao=dias, dias_compostagem=50):
    umidade, T, DOC = params
    fracao_ms = 1 - umidade
    
    # Usando valores fixos para CH4_C_FRAC_THERMO e N2O_N_FRAC_THERMO
    ch4_total_por_lote = residuos_kg_dia * (TOC_YANG * CH4_C_FRAC_THERMO * (16/12) * fracao_ms)
    n2o_total_por_lote = residuos_kg_dia * (TN_YANG * N2O_N_FRAC_THERMO * (44/28) * fracao_ms)

    emissoes_CH4 = np.zeros(dias_simulacao)
    emissoes_N2O = np.zeros(dias_simulacao)

    for dia_entrada in range(dias_simulacao):
        for dia_compostagem in range(len(PERFIL_CH4_THERMO)):
            dia_emissao = dia_entrada + dia_compostagem
            if dia_emissao < dias_simulacao:
                emissoes_CH4[dia_emissao] += ch4_total_por_lote * PERFIL_CH4_THERMO[dia_compostagem]
                emissoes_N2O[dia_emissao] += n2o_total_por_lote * PERFIL_N2O_THERMO[dia_compostagem]

    return emissoes_CH4, emissoes_N2O

def executar_simulacao_completa(parametros):
    umidade, T, DOC = parametros
    
    ch4_aterro, n2o_aterro = calcular_emissoes_aterro([umidade, T, DOC])
    ch4_vermi, n2o_vermi = calcular_emissoes_vermi([umidade, T, DOC])

    total_aterro_tco2eq = (ch4_aterro * GWP_CH4_20 + n2o_aterro * GWP_N2O_20) / 1000
    total_vermi_tco2eq = (ch4_vermi * GWP_CH4_20 + n2o_vermi * GWP_N2O_20) / 1000

    reducao_tco2eq = total_aterro_tco2eq.sum() - total_vermi_tco2eq.sum()
    return reducao_tco2eq

def executar_simulacao_unfccc(parametros):
    umidade, T, DOC = parametros

    ch4_aterro, n2o_aterro = calcular_emissoes_aterro([umidade, T, DOC])
    total_aterro_tco2eq = (ch4_aterro * GWP_CH4_20 + n2o_aterro * GWP_N2O_20) / 1000

    ch4_compost, n2o_compost = calcular_emissoes_compostagem([umidade, T, DOC], dias_simulacao=dias, dias_compostagem=50)
    total_compost_tco2eq = (ch4_compost * GWP_CH4_20 + n2o_compost * GWP_N2O_20) / 1000

    reducao_tco2eq = total_aterro_tco2eq.sum() - total_compost_tco2eq.sum()
    return reducao_tco2eq

# =============================================================================
# EXECUÇÃO DA SIMULAÇÃO
# =============================================================================

# Executar simulação quando solicitado
if st.session_state.get('run_simulation', False):
    with st.spinner('Executando simulação...'):
        # Executar modelo base
        params_base = [umidade, T, DOC]

        ch4_aterro_dia, n2o_aterro_dia = calcular_emissoes_aterro(params_base)
        ch4_vermi_dia, n2o_vermi_dia = calcular_emissoes_vermi(params_base)

        # Construir DataFrame
        df = pd.DataFrame({
            'Data': datas,
            'CH4_Aterro_kg_dia': ch4_aterro_dia,
            'N2O_Aterro_kg_dia': n2o_aterro_dia,
            'CH4_Vermi_kg_dia': ch4_vermi_dia,
            'N2O_Vermi_kg_dia': n2o_vermi_dia,
        })

        for gas in ['CH4_Aterro', 'N2O_Aterro', 'CH4_Vermi', 'N2O_Vermi']:
            df[f'{gas}_tCO2eq'] = df[f'{gas}_kg_dia'] * (GWP_CH4_20 if 'CH4' in gas else GWP_N2O_20) / 1000

        df['Total_Aterro_tCO2eq_dia'] = df['CH4_Aterro_tCO2eq'] + df['N2O_Aterro_tCO2eq']
        df['Total_Vermi_tCO2eq_dia'] = df['CH4_Vermi_tCO2eq'] + df['N2O_Vermi_tCO2eq']

        df['Total_Aterro_tCO2eq_acum'] = df['Total_Aterro_tCO2eq_dia'].cumsum()
        df['Total_Vermi_tCO2eq_acum'] = df['Total_Vermi_tCO2eq_dia'].cumsum()
        df['Reducao_tCO2eq_acum'] = df['Total_Aterro_tCO2eq_acum'] - df['Total_Vermi_tCO2eq_acum']

        # Resumo anual
        df['Year'] = df['Data'].dt.year
        df_anual_revisado = df.groupby('Year').agg({
            'Total_Aterro_tCO2eq_dia': 'sum',
            'Total_Vermi_tCO2eq_dia': 'sum',
        }).reset_index()

        df_anual_revisado['Emission reductions (t CO₂eq)'] = df_anual_revisado['Total_Aterro_tCO2eq_dia'] - df_anual_revisado['Total_Vermi_tCO2eq_dia']
        df_anual_revisado['Cumulative reduction (t CO₂eq)'] = df_anual_revisado['Emission reductions (t CO₂eq)'].cumsum()

        df_anual_revisado.rename(columns={
            'Total_Aterro_tCO2eq_dia': 'Baseline emissions (t CO₂eq)',
            'Total_Vermi_tCO2eq_dia': 'Project emissions (t CO₂eq)',
        }, inplace=True)

        # Cenário UNFCCC
        ch4_compost_UNFCCC, n2o_compost_UNFCCC = calcular_emissoes_compostagem(
            params_base, dias_simulacao=dias, dias_compostagem=50
        )
        ch4_compost_unfccc_tco2eq = ch4_compost_UNFCCC * GWP_CH4_20 / 1000
        n2o_compost_unfccc_tco2eq = n2o_compost_UNFCCC * GWP_N2O_20 / 1000
        total_compost_unfccc_tco2eq_dia = ch4_compost_unfccc_tco2eq + n2o_compost_unfccc_tco2eq

        df_comp_unfccc_dia = pd.DataFrame({
            'Data': datas,
            'Total_Compost_tCO2eq_dia': total_compost_unfccc_tco2eq_dia
        })
        df_comp_unfccc_dia['Year'] = df_comp_unfccc_dia['Data'].dt.year

        df_comp_anual_revisado = df_comp_unfccc_dia.groupby('Year').agg({
            'Total_Compost_tCO2eq_dia': 'sum'
        }).reset_index()

        df_comp_anual_revisado = pd.merge(df_comp_anual_revisado,
                                          df_anual_revisado[['Year', 'Baseline emissions (t CO₂eq)']],
                                          on='Year', how='left')

        df_comp_anual_revisado['Emission reductions (t CO₂eq)'] = df_comp_anual_revisado['Baseline emissions (t CO₂eq)'] - df_comp_anual_revisado['Total_Compost_tCO2eq_dia']
        df_comp_anual_revisado['Cumulative reduction (t CO₂eq)'] = df_comp_anual_revisado['Emission reductions (t CO₂eq)'].cumsum()
        df_comp_anual_revisado.rename(columns={'Total_Compost_tCO2eq_dia': 'Project emissions (t CO₂eq)'}, inplace=True)

        # =============================================================================
        # EXIBIÇÃO DOS RESULTADOS COM COTAÇÃO DO CARBONO E REAL
        # =============================================================================

        # Exibir resultados
        st.header("Resultados da Simulação")
        
        # Obter valores totais
        total_evitado_tese = df['Reducao_tCO2eq_acum'].iloc[-1]
        total_evitado_unfccc = df_comp_anual_revisado['Cumulative reduction (t CO₂eq)'].iloc[-1]
        
        # Obter preço do carbono e taxa de câmbio da session state
        preco_carbono = st.session_state.preco_carbono
        moeda = st.session_state.moeda_carbono
        taxa_cambio = st.session_state.taxa_cambio
        ano_contrato = st.session_state.ano_contrato
        contrato_atual = st.session_state.contrato_atual
        
        # Calcular valores financeiros em Euros
        valor_tese_eur = calcular_valor_creditos(total_evitado_tese, preco_carbono, moeda)
        valor_unfccc_eur = calcular_valor_creditos(total_evitado_unfccc, preco_carbono, moeda)
        
        # Calcular valores financeiros em Reais
        valor_tese_brl = calcular_valor_creditos(total_evitado_tese, preco_carbono, "R$", taxa_cambio)
        valor_unfccc_brl = calcular_valor_creditos(total_evitado_unfccc, preco_carbono, "R$", taxa_cambio)
        
        # NOVA SEÇÃO: VALOR FINANCEIRO DAS EMISSÕES EVITADAS
        st.subheader("💰 Valor Financeiro das Emissões Evitadas")
        
        if not YFINANCE_AVAILABLE:
            st.warning("⚠️ **Cotações em modo offline** - Instale yfinance para valores em tempo real")
        
        # Primeira linha: Euros
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                f"Preço {contrato_atual} (Euro)", 
                f"{moeda} {preco_carbono:.2f}/tCO₂eq",
                help=f"Cotação do contrato futuro para Dezembro {ano_contrato}"
            )
        with col2:
            st.metric(
                "Valor Tese (Euro)", 
                f"{moeda} {formatar_br(valor_tese_eur)}",
                help=f"Baseado em {formatar_br(total_evitado_tese)} tCO₂eq evitadas"
            )
        with col3:
            st.metric(
                "Valor UNFCCC (Euro)", 
                f"{moeda} {formatar_br(valor_unfccc_eur)}",
                help=f"Baseado em {formatar_br(total_evitado_unfccc)} tCO₂eq evitadas"
            )
        
        # Segunda linha: Reais
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                f"Preço {contrato_atual} (R$)", 
                f"R$ {formatar_br(preco_carbono * taxa_cambio)}/tCO₂eq",
                help="Preço do carbono convertido para Reais"
            )
        with col2:
            st.metric(
                "Valor Tese (R$)", 
                f"R$ {formatar_br(valor_tese_brl)}",
                help=f"Baseado em {formatar_br(total_evitado_tese)} tCO₂eq evitadas"
            )
        with col3:
            st.metric(
                "Valor UNFCCC (R$)", 
                f"R$ {formatar_br(valor_unfccc_brl)}",
                help=f"Baseado em {formatar_br(total_evitado_unfccc)} tCO₂eq evitadas"
            )
        
        # Status do contrato
        status_contrato = "⏳ **VÁLIDO** (em vigor)" if contrato_atual == "CarbonDec25" else "✅ **VENCIDO** (migrado automaticamente)"
        
        # Explicação sobre compra e venda
        with st.expander(f"💡 Como funciona a comercialização no mercado de carbono? - {status_contrato}"):
            st.markdown(f"""
            **Para o {contrato_atual}:**
            - **Status:** {status_contrato}
            - **Preço em Euro:** {moeda} {preco_carbono:.2f}/tCO₂eq
            - **Preço em Real:** R$ {formatar_br(preco_carbono * taxa_cambio)}/tCO₂eq
            - **Taxa de câmbio:** 1 Euro = R$ {taxa_cambio:.2f}
            
            **📈 Comprar créditos (compensação):**
            - Custo em Euro: **{moeda} {formatar_br(valor_tese_eur)}**
            - Custo em Real: **R$ {formatar_br(valor_tese_brl)}**
            
            **📉 Vender créditos (comercialização):**  
            - Receita em Euro: **{moeda} {formatar_br(valor_tese_eur)}**
            - Receita em Real: **R$ {formatar_br(valor_tese_brl)}**
            
            **Contrato {contrato_atual}:**
            - Cada contrato = 1.000 tCO₂eq
            - Vencimento: Dezembro {ano_contrato}
            - Mercado: ICE Exchange
            - Moeda original: Euros (€)
            - Ticker no Yahoo Finance: `CO2Z{str(ano_contrato)[-2:]}.NYB`
            - **Migração automática:** Após vencimento em dezembro/2025
            """)
        
        # Métricas originais de emissões
        st.subheader("📊 Resumo das Emissões Evitadas")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total de emissões evitadas (Tese)", f"{formatar_br(total_evitado_tese)} tCO₂eq")
        with col2:
            st.metric("Total de emissões evitadas (UNFCCC)", f"{formatar_br(total_evitado_unfccc)} tCO₂eq")

        # Gráfico comparativo
        st.subheader("Comparação Anual das Emissões Evitadas")
        df_evitadas_anual = pd.DataFrame({
            'Year': df_anual_revisado['Year'],
            'Proposta da Tese': df_anual_revisado['Emission reductions (t CO₂eq)'],
            'UNFCCC (2012)': df_comp_anual_revisado['Emission reductions (t CO₂eq)']
        })

        fig, ax = plt.subplots(figsize=(10, 6))
        br_formatter = FuncFormatter(br_format)
        x = np.arange(len(df_evitadas_anual['Year']))
        bar_width = 0.35

        ax.bar(x - bar_width/2, df_evitadas_anual['Proposta da Tese'], width=bar_width,
                label='Proposta da Tese', edgecolor='black')
        ax.bar(x + bar_width/2, df_evitadas_anual['UNFCCC (2012)'], width=bar_width,
                label='UNFCCC (2012)', edgecolor='black', hatch='//')

        # Adicionar valores formatados em cima das barras
        for i, (v1, v2) in enumerate(zip(df_evitadas_anual['Proposta da Tese'], 
                                         df_evitadas_anual['UNFCCC (2012)'])):
            ax.text(i - bar_width/2, v1 + max(v1, v2)*0.01, 
                    formatar_br(v1), ha='center', fontsize=9, fontweight='bold')
            ax.text(i + bar_width/2, v2 + max(v1, v2)*0.01, 
                    formatar_br(v2), ha='center', fontsize=9, fontweight='bold')

        ax.set_xlabel('Ano')
        ax.set_ylabel('Emissões Evitadas (t CO₂eq)')
        ax.set_title('Comparação Anual das Emissões Evitadas: Proposta da Tese vs UNFCCC (2012)')
        
        # Ajustar o eixo x para ser igual ao do gráfico de redução acumulada
        ax.set_xticks(x)
        ax.set_xticklabels(df_anual_revisado['Year'], fontsize=8)

        ax.legend(title='Metodologia')
        ax.yaxis.set_major_formatter(br_formatter)
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        st.pyplot(fig)

        # Gráfico de redução acumulada
        st.subheader("Redução de Emissões Acumulada")
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(df['Data'], df['Total_Aterro_tCO2eq_acum'], 'r-', label='Cenário Base (Aterro Sanitário)', linewidth=2)
        ax.plot(df['Data'], df['Total_Vermi_tCO2eq_acum'], 'g-', label='Projeto (Compostagem em reatores com minhocas)', linewidth=2)
        ax.fill_between(df['Data'], df['Total_Vermi_tCO2eq_acum'], df['Total_Aterro_tCO2eq_acum'],
                        color='skyblue', alpha=0.5, label='Emissões Evitadas')
        ax.set_title('Redução de Emissões em {} Anos'.format(anos_simulacao))
        ax.set_xlabel('Ano')
        ax.set_ylabel('tCO₂eq Acumulado')
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.yaxis.set_major_formatter(br_formatter)

        st.pyplot(fig)

        # Análise de Sensibilidade Global (Sobol) - PROPOSTA DA TESE
        st.subheader("Análise de Sensibilidade Global (Sobol) - Proposta da Tese")
        br_formatter_sobol = FuncFormatter(br_format)

        np.random.seed(50)  
        
        problem_tese = {
            'num_vars': 3,
            'names': ['umidade', 'T', 'DOC'],
            'bounds': [
                [0.5, 0.85],         # umidade
                [25.0, 45.0],       # temperatura
                [0.15, 0.50],       # doc
            ]
        }

        param_values_tese = sample(problem_tese, n_samples)
        results_tese = Parallel(n_jobs=-1)(delayed(executar_simulacao_completa)(params) for params in param_values_tese)
        Si_tese = analyze(problem_tese, np.array(results_tese), print_to_console=False)
        
        sensibilidade_df_tese = pd.DataFrame({
            'Parâmetro': problem_tese['names'],
            'S1': Si_tese['S1'],
            'ST': Si_tese['ST']
        }).sort_values('ST', ascending=False)

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(x='ST', y='Parâmetro', data=sensibilidade_df_tese, palette='viridis', ax=ax)
        ax.set_title('Sensibilidade Global dos Parâmetros (Índice Sobol Total) - Proposta da Tese')
        ax.set_xlabel('Índice ST')
        ax.set_ylabel('')
        ax.grid(axis='x', linestyle='--', alpha=0.7)
        ax.xaxis.set_major_formatter(br_formatter_sobol) # Adiciona formatação ao eixo x
        st.pyplot(fig)

        # Análise de Sensibilidade Global (Sobol) - CENÁRIO UNFCCC
        st.subheader("Análise de Sensibilidade Global (Sobol) - Cenário UNFCCC")

        np.random.seed(50)
        
        problem_unfccc = {
            'num_vars': 3,
            'names': ['umidade', 'T', 'DOC'],
            'bounds': [
                [0.5, 0.85],  # Umidade
                [25, 45],     # Temperatura
                [0.15, 0.50], # DOC
            ]
        }

        param_values_unfccc = sample(problem_unfccc, n_samples)
        results_unfccc = Parallel(n_jobs=-1)(delayed(executar_simulacao_unfccc)(params) for params in param_values_unfccc)
        Si_unfccc = analyze(problem_unfccc, np.array(results_unfccc), print_to_console=False)
        
        sensibilidade_df_unfccc = pd.DataFrame({
            'Parâmetro': problem_unfccc['names'],
            'S1': Si_unfccc['S1'],
            'ST': Si_unfccc['ST']
        }).sort_values('ST', ascending=False)

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(x='ST', y='Parâmetro', data=sensibilidade_df_unfccc, palette='viridis', ax=ax)
        ax.set_title('Sensibilidade Global dos Parâmetros (Índice Sobol Total) - Cenário UNFCCC')
        ax.set_xlabel('Índice ST')
        ax.set_ylabel('')
        ax.grid(axis='x', linestyle='--', alpha=0.7)
        ax.xaxis.set_major_formatter(br_formatter_sobol) # Adiciona formatação ao eixo x
        st.pyplot(fig)

        # Análise de Incerteza (Monte Carlo) - PROPOSTA DA TESE
        st.subheader("Análise de Incerteza (Monte Carlo) - Proposta da Tese")

        
        def gerar_parametros_mc_tese(n):
            np.random.seed(50)
            umidade_vals = np.random.uniform(0.75, 0.90, n)
            temp_vals = np.random.normal(25, 3, n)
            doc_vals = np.random.triangular(0.12, 0.15, 0.18, n)
            
            return umidade_vals, temp_vals, doc_vals

        umidade_vals, temp_vals, doc_vals = gerar_parametros_mc_tese(n_simulations)
        
        results_mc_tese = []
        for i in range(n_simulations):
            params_tese = [umidade_vals[i], temp_vals[i], doc_vals[i]]
            results_mc_tese.append(executar_simulacao_completa(params_tese))

        results_array_tese = np.array(results_mc_tese)
        media_tese = np.mean(results_array_tese)
        intervalo_95_tese = np.percentile(results_array_tese, [2.5, 97.5])

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.histplot(results_array_tese, kde=True, bins=30, color='skyblue', ax=ax)
        ax.axvline(media_tese, color='red', linestyle='--', label=f'Média: {formatar_br(media_tese)} tCO₂eq')
        ax.axvline(intervalo_95_tese[0], color='green', linestyle=':', label='IC 95%')
        ax.axvline(intervalo_95_tese[1], color='green', linestyle=':')
        ax.set_title('Distribuição das Emissões Evitadas (Simulação Monte Carlo) - Proposta da Tese')
        ax.set_xlabel('Emissões Evitadas (tCO₂eq)')
        ax.set_ylabel('Frequência')
        ax.legend()
        ax.grid(alpha=0.3)
        ax.xaxis.set_major_formatter(br_formatter)
        st.pyplot(fig)

        # Análise de Incerteza (Monte Carlo) - CENÁRIO UNFCCC
        st.subheader("Análise de Incerteza (Monte Carlo) - Cenário UNFCCC")
        
        def gerar_parametros_mc_unfccc(n):
            np.random.seed(50)
            umidade_vals = np.random.uniform(0.75, 0.90, n)
            temp_vals = np.random.normal(25, 3, n)
            doc_vals = np.random.triangular(0.12, 0.15, 0.18, n)
            
            return umidade_vals, temp_vals, doc_vals

        umidade_vals, temp_vals, doc_vals = gerar_parametros_mc_unfccc(n_simulations)
        
        results_mc_unfccc = []
        for i in range(n_simulations):
            params_unfccc = [umidade_vals[i], temp_vals[i], doc_vals[i]]
            results_mc_unfccc.append(executar_simulacao_unfccc(params_unfccc))

        results_array_unfccc = np.array(results_mc_unfccc)
        media_unfccc = np.mean(results_array_unfccc)
        intervalo_95_unfccc = np.percentile(results_array_unfccc, [2.5, 97.5])

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.histplot(results_array_unfccc, kde=True, bins=30, color='coral', ax=ax)
        ax.axvline(media_unfccc, color='red', linestyle='--', label=f'Média: {formatar_br(media_unfccc)} tCO₂eq')
        ax.axvline(intervalo_95_unfccc[0], color='green', linestyle=':', label='IC 95%')
        ax.axvline(intervalo_95_unfccc[1], color='green', linestyle=':')
        ax.set_title('Distribuição das Emissões Evitadas (Simulação Monte Carlo) - Cenário UNFCCC')
        ax.set_xlabel('Emissões Evitadas (tCO₂eq)')
        ax.set_ylabel('Frequência')
        ax.legend()
        ax.grid(alpha=0.3)
        ax.xaxis.set_major_formatter(br_formatter)
        st.pyplot(fig)

        # Análise Estatística de Comparação
        st.subheader("Análise Estatística de Comparação")
        
        # Teste de normalidade para as diferenças
        diferencas = results_array_tese - results_array_unfccc
        _, p_valor_normalidade_diff = stats.normaltest(diferencas)
        st.write(f"Teste de normalidade das diferenças (p-value): **{p_valor_normalidade_diff:.5f}**")

        # Teste T pareado
        ttest_pareado, p_ttest_pareado = stats.ttest_rel(results_array_tese, results_array_unfccc)
        st.write(f"Teste T pareado: Estatística t = **{ttest_pareado:.5f}**, P-valor = **{p_ttest_pareado:.5f}**")

        # Teste de Wilcoxon para amostras pareadas
        wilcoxon_stat, p_wilcoxon = stats.wilcoxon(results_array_tese, results_array_unfccc)
        st.write(f"Teste de Wilcoxon (pareado): Estatística = **{wilcoxon_stat:.5f}**, P-valor = **{p_wilcoxon:.5f}**")

        # Tabela de resultados anuais - Proposta da Tese
        st.subheader("Resultados Anuais - Proposta da Tese")

        # Criar uma cópia para formatação
        df_anual_formatado = df_anual_revisado.copy()
        for col in df_anual_formatado.columns:
            if col != 'Year':
                df_anual_formatado[col] = df_anual_formatado[col].apply(formatar_br)

        st.dataframe(df_anual_formatado)

        # Tabela de resultados anuais - Metodologia UNFCCC
        st.subheader("Resultados Anuais - Metodologia UNFCCC")

        # Criar uma cópia para formatação
        df_comp_formatado = df_comp_anual_revisado.copy()
        for col in df_comp_formatado.columns:
            if col != 'Year':
                df_comp_formatado[col] = df_comp_formatado[col].apply(formatar_br)

        st.dataframe(df_comp_formatado)

else:
    st.info("Ajuste os parâmetros na barra lateral e clique em 'Executar Simulação' para ver os resultados.")

# Rodapé
st.markdown("---")
st.markdown("""

**Referências por Cenário:**

**Cenário de Baseline (Aterro Sanitário):**
- Metano: IPCC (2006), UNFCCC (2016) e Wang et al. (2023) 
- Óxido Nitroso: Wang et al. (2017)
- Metano e Óxido Nitroso no pré-descarte: Feng et al. (2020)

**Proposta da Tese (Compostagem em reatores com minhocas):**
- Metano e Óxido Nitroso: Yang et al. (2017)

**Cenário UNFCCC (Compostagem sem minhocas a céu aberto):**
- Protocolo AMS-III.F: UNFCCC (2016)
- Fatores de emissões: Yang et al. (2017)
""")
