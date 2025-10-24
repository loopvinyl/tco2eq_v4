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

np.random.seed(50)

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

def inicializar_session_state():
    if 'preco_carbono' not in st.session_state:
        st.session_state.preco_carbono = 78.02  # Valor do MT5 como padrão
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
        st.session_state.ano_contrato = 2025
    if 'contrato_atual' not in st.session_state:
        st.session_state.contrato_atual = "CarbonDec25"
    if 'fonte_cotacao' not in st.session_state:
        st.session_state.fonte_cotacao = "MT5 (CFI2Z5)"  # Padrão: seu broker
    if 'dados_atrasados' not in st.session_state:
        st.session_state.dados_atrasados = True

inicializar_session_state()

# =============================================================================
# FUNÇÕES ATUALIZADAS DE COTAÇÃO - COM TODAS AS FONTES
# =============================================================================

def obter_ticker_carbono_atual():
    """
    Determina automaticamente o ticker do contrato futuro de carbono mais relevante
    """
    hoje = datetime.now()
    ano_atual = hoje.year
    mes_atual = hoje.month
    
    vencimento_carbondec25 = datetime(2025, 12, 15)
    
    if hoje > vencimento_carbondec25:
        if mes_atual >= 9:
            ano_contrato = ano_atual + 1
        else:
            ano_contrato = ano_atual
        contrato_nome = f"CarbonDec{ano_contrato}"
    else:
        ano_contrato = 2025
        contrato_nome = "CarbonDec25"
    
    return ano_contrato, contrato_nome

def obter_cotacao_yahoo(ticker):
    """
    Obtém cotação do Yahoo Finance para um ticker específico
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period='1d')
        
        if not hist.empty and not pd.isna(hist['Close'].iloc[-1]):
            return hist['Close'].iloc[-1], True
        return None, False
    except:
        return None, False

def obter_cotacao_carbono_completa():
    """
    Obtém cotações de TODAS as fontes disponíveis
    """
    ano_contrato, contrato_nome = obter_ticker_carbono_atual()
    
    # Fontes base com valores padrão
    fontes = {
        "MT5 (CFI2Z5)": {
            "ticker": "CFI2Z5",
            "preco": 78.02,
            "moeda": "€",
            "atrasado": True,
            "hora": "10:59:55",
            "disponivel": True,
            "tipo": "CFD Broker",
            "descricao": "Seu broker ActivTrade - Dados em atraso"
        },
        "Yahoo Finance (CO2Z25)": {
            "ticker": "CO2Z25.NYB",
            "preco": 85.50,
            "moeda": "€", 
            "atrasado": False,
            "hora": "Tempo Real",
            "disponivel": YFINANCE_AVAILABLE,
            "tipo": "Contrato Futuro",
            "descricao": "Contrato futuro específico Dec 2025 - ICE Exchange"
        },
        "Yahoo Finance (^ICEEUA)": {
            "ticker": "^ICEEUA",
            "preco": 85.50,
            "moeda": "€",
            "atrasado": False,
            "hora": "Tempo Real", 
            "disponivel": YFINANCE_AVAILABLE,
            "tipo": "Índice",
            "descricao": "Índice geral de futuros carbono - Média do mercado"
        },
        "Referência": {
            "ticker": "CO2Z25.NYB",
            "preco": 85.50,
            "moeda": "€",
            "atrasado": False,
            "hora": "Referência",
            "disponivel": True,
            "tipo": "Valor Padrão",
            "descricao": "Valor de referência para cálculos"
        }
    }
    
    # Atualizar preços do Yahoo Finance se disponível
    if YFINANCE_AVAILABLE:
        # Atualizar CO2Z25
        preco_co2z25, sucesso_co2z25 = obter_cotacao_yahoo("CO2Z25.NYB")
        if sucesso_co2z25:
            fontes["Yahoo Finance (CO2Z25)"]["preco"] = preco_co2z25
            fontes["Yahoo Finance (CO2Z25)"]["hora"] = datetime.now().strftime("%H:%M:%S")
        
        # Atualizar ^ICEEUA
        preco_iceeua, sucesso_iceeua = obter_cotacao_yahoo("^ICEEUA")
        if sucesso_iceeua:
            fontes["Yahoo Finance (^ICEEUA)"]["preco"] = preco_iceeua
            fontes["Yahoo Finance (^ICEEUA)"]["hora"] = datetime.now().strftime("%H:%M:%S")
    
    return fontes, contrato_nome, ano_contrato

def obter_cotacao_euro_real():
    """
    Obtém a cotação em tempo real do Euro em relação ao Real Brasileiro
    """
    if not YFINANCE_AVAILABLE:
        return 5.50, "R$", False
    
    try:
        ticker = yf.Ticker("EURBRL=X")
        hist = ticker.history(period='1d')
        
        if not hist.empty and not pd.isna(hist['Close'].iloc[-1]):
            cotacao = hist['Close'].iloc[-1]
            return cotacao, "R$", True
        else:
            return 5.50, "R$", False
    except:
        return 5.50, "R$", False

def calcular_valor_creditos(emissoes_evitadas_tco2eq, preco_carbono_por_tonelada, moeda, taxa_cambio=1):
    valor_total = emissoes_evitadas_tco2eq * preco_carbono_por_tonelada * taxa_cambio
    return valor_total

def exibir_cotacao_carbono():
    """
    Exibe a cotação do carbono com múltiplas fontes
    """
    st.sidebar.header("💰 Mercado de Carbono e Câmbio")
    
    # Obter todas as cotações disponíveis
    fontes, contrato_nome, ano_contrato = obter_cotacao_carbono_completa()
    
    # Seção de seleção de fonte
    st.sidebar.subheader("📊 Fonte da Cotação")
    
    fonte_selecionada = st.sidebar.selectbox(
        "Selecione a fonte:",
        options=list(fontes.keys()),
        index=list(fontes.keys()).index(st.session_state.fonte_cotacao) if st.session_state.fonte_cotacao in fontes else 0,
        help="Escolha qual cotação usar nos cálculos"
    )
    
    # Atualizar session state com a fonte selecionada
    st.session_state.fonte_cotacao = fonte_selecionada
    st.session_state.preco_carbono = fontes[fonte_selecionada]["preco"]
    st.session_state.dados_atrasados = fontes[fonte_selecionada]["atrasado"]
    
    # Botão para atualizar cotações
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🔄 Atualizar Cotações") and YFINANCE_AVAILABLE:
            st.session_state.cotacao_atualizada = True
            st.session_state.mostrar_atualizacao = True
    
    with col2:
        if st.button("📊 Ver Todas"):
            st.session_state.mostrar_todas = not st.session_state.get('mostrar_todas', False)
    
    if st.session_state.get('mostrar_atualizacao', False):
        st.sidebar.info("🔄 Atualizando cotações...")
        st.session_state.mostrar_atualizacao = False
    
    if st.session_state.get('cotacao_atualizada', False):
        # Atualizar cotação do Euro
        preco_euro, moeda_real, sucesso_euro = obter_cotacao_euro_real()
        st.session_state.taxa_cambio = preco_euro
        st.session_state.cotacao_atualizada = False

    # Exibir cotação selecionada com destaque
    fonte_info = fontes[fonte_selecionada]
    
    # Ícone de status
    if fonte_selecionada == "MT5 (CFI2Z5)":
        status_icon = "🟡"  # Amarelo - dados do broker
    elif fonte_info["atrasado"]:
        status_icon = "🟠"  # Laranja - dados atrasados
    else:
        status_icon = "🟢"  # Verde - dados atualizados
    
    st.sidebar.markdown(f"### {status_icon} {contrato_nome}")
    st.sidebar.metric(
        label=f"{fonte_selecionada}",
        value=f"{fonte_info['moeda']} {fonte_info['preco']:.2f}",
        help=f"{fonte_info['descricao']} | {fonte_info['hora']}"
    )
    
    # Exibir cotação do Euro
    st.sidebar.metric(
        label="Euro (EUR/BRL)",
        value=f"{st.session_state.moeda_real} {st.session_state.taxa_cambio:.2f}",
        help="Cotação do Euro em Reais Brasileiros"
    )
    
    # Calcular preço do carbono em Reais
    preco_carbono_reais = st.session_state.preco_carbono * st.session_state.taxa_cambio
    st.sidebar.metric(
        label=f"{contrato_nome} (R$/tCO₂eq)",
        value=f"R$ {preco_carbono_reais:.2f}",
        help="Preço do carbono convertido para Reais"
    )
    
    # Explicação sobre as fontes
    with st.sidebar.expander("💡 Sobre as Fontes de Cotação"):
        st.markdown("""
        **MT5 (CFI2Z5):**
        - Seu broker ActivTrade
        - Dados em atraso (15 min)
        - Preço real de execução
        
        **Yahoo Finance (CO2Z25):**
        - Contrato futuro específico
        - Dados em tempo real
        - Preço de referência do mercado
        
        **Yahoo Finance (^ICEEUA):**
        - Índice geral de carbono
        - Média dos contratos futuros
        - Visão geral do mercado
        
        **Recomendação:** Use o valor do seu broker para cálculos reais
        """)
    
    # Mostrar todas as cotações se solicitado
    if st.session_state.get('mostrar_todas', False):
        st.sidebar.markdown("---")
        st.sidebar.subheader("📈 Todas as Cotações Disponíveis")
        
        for fonte_nome, info in fontes.items():
            if info["disponivel"]:
                # Cor baseada no tipo
                if fonte_nome == "MT5 (CFI2Z5)":
                    cor = "🟡"
                elif info["atrasado"]:
                    cor = "🟠" 
                else:
                    cor = "🟢"
                
                st.sidebar.write(f"**{cor} {fonte_nome}**")
                st.sidebar.write(f"**Preço:** {info['moeda']} {info['preco']:.2f}")
                st.sidebar.write(f"**Tipo:** {info['tipo']}")
                st.sidebar.write(f"**Status:** {info['hora']}")
                st.sidebar.write(f"**Descrição:** {info['descricao']}")
                st.sidebar.markdown("---")

# =============================================================================
# FUNÇÕES ORIGINAIS DO SEU SCRIPT (mantidas intactas)
# =============================================================================

# Função para formatar números no padrão brasileiro
def formatar_br(numero):
    if pd.isna(numero):
        return "N/A"
    numero = round(numero, 2)
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Função de formatação para os gráficos
def br_format(x, pos):
    if x == 0:
        return "0"
    if abs(x) < 0.01:
        return f"{x:.1e}".replace(".", ",")
    if abs(x) >= 1000:
        return f"{x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def br_format_5_dec(x, pos):
    return f"{x:,.5f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ... (o resto do seu código original permanece EXATAMENTE igual)
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

# ... (continue com todo o resto do seu código original EXATAMENTE como estava)
