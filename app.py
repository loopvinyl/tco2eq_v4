# =========================
# NOVAS FUNÇÕES DE ANÁLISE ESTATÍSTICA
# =========================

@st.cache_data(ttl=3600, show_spinner=False)
def analyze_project_statistics(dataframes):
    """Analisa estatísticas reais dos projetos do dataset"""
    
    # Mapeamento de abas para tipos de prática
    PRACTICE_MAPPING = {
        '4. Agriculture': 'agricultura',
        '5. Agroforestry-AR & Grassland': 'agroflorestal', 
        '6. Energy and Other': 'energia',
        '7. Plan Vivo, Acorn, Social C': 'agroflorestal',
        '8. Puro.earth': 'energia',
        '9. Nori and BCarbon': 'agricultura'
    }
    
    statistics = {
        'agricultura': {'projects': 0, 'sequestration_rates': [], 'areas': [], 'credits': []},
        'agroflorestal': {'projects': 0, 'sequestration_rates': [], 'areas': [], 'credits': []},
        'energia': {'projects': 0, 'sequestration_rates': [], 'areas': [], 'credits': []}
    }
    
    for sheet_name, practice_type in PRACTICE_MAPPING.items():
        if sheet_name not in dataframes:
            continue
            
        df = dataframes[sheet_name]
        if df.empty:
            continue
        
        # Identificar colunas relevantes
        area_col = None
        credit_col = None
        duration_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            
            # Buscar coluna de área
            if any(keyword in col_lower for keyword in ['area', 'hectare', 'ha', 'land size']):
                area_col = col
            
            # Buscar coluna de créditos emitidos
            if any(keyword in col_lower for keyword in ['credit', 'issued', 'volume', 'amount']):
                credit_col = col
            
            # Buscar coluna de duração/projeto
            if any(keyword in col_lower for keyword in ['year', 'duration', 'period', 'lifetime']):
                duration_col = col
        
        # Processar linhas com dados completos
        for idx, row in df.iterrows():
            try:
                # Extrair valores
                if area_col and credit_col:
                    area = float(row[area_col]) if pd.notna(row[area_col]) else None
                    credits = float(row[credit_col]) if pd.notna(row[credit_col]) else None
                    
                    # Determinar duração (padrão: 10 anos se não especificado)
                    duration = 10  # default
                    if duration_col and pd.notna(row[duration_col]):
                        try:
                            duration = float(row[duration_col])
                        except:
                            duration = 10
                    
                    # Calcular taxa de sequestro anual por hectare
                    if area and area > 0 and credits and credits > 0:
                        annual_credits = credits / duration
                        sequestration_rate = annual_credits / area
                        
                        # Adicionar aos dados estatísticos
                        statistics[practice_type]['projects'] += 1
                        statistics[practice_type]['sequestration_rates'].append(sequestration_rate)
                        statistics[practice_type]['areas'].append(area)
                        statistics[practice_type]['credits'].append(credits)
                        
            except (ValueError, TypeError):
                continue
    
    # Calcular estatísticas sumarizadas
    for practice_type in statistics:
        rates = statistics[practice_type]['sequestration_rates']
        if rates:
            statistics[practice_type]['mean_rate'] = np.mean(rates)
            statistics[practice_type]['median_rate'] = np.median(rates)
            statistics[practice_type]['std_rate'] = np.std(rates)
            statistics[practice_type]['min_rate'] = np.min(rates)
            statistics[practice_type]['max_rate'] = np.max(rates)
            statistics[practice_type]['q25'] = np.percentile(rates, 25)
            statistics[practice_type]['q75'] = np.percentile(rates, 75)
        else:
            # Usar valores padrão se não houver dados
            statistics[practice_type]['mean_rate'] = {
                'agricultura': 1.25,
                'agroflorestal': 4.0,
                'energia': 2.0
            }[practice_type]
            statistics[practice_type]['median_rate'] = statistics[practice_type]['mean_rate']
            statistics[practice_type]['std_rate'] = statistics[practice_type]['mean_rate'] * 0.5
    
    return statistics

# =========================
# FUNÇÃO calculate_potential_revenue ATUALIZADA
# =========================

def calculate_potential_revenue(hectares: float, practice_type: str = 'agricultura', 
                               use_dataset_stats: bool = True) -> Dict:
    """Calcula receita potencial usando estatísticas do dataset quando disponível"""
    
    price_range = CARBON_PRICE_RANGE.get(practice_type, CARBON_PRICE_RANGE['agricultura'])
    
    # Taxas de sequestro baseadas em estatísticas do dataset
    if use_dataset_stats and 'project_statistics' in st.session_state:
        stats = st.session_state.project_statistics.get(practice_type, {})
        
        if stats.get('projects', 0) > 0:
            # Usar estatísticas reais do dataset
            rate_avg = stats['mean_rate']
            rate_min = max(0.1, stats['q25'])  # Usar percentil 25 como mínimo
            rate_max = stats['q75']  # Usar percentil 75 como máximo
            
            # Indicador de confiabilidade
            data_source = f"Baseado em {stats['projects']} projetos reais"
        else:
            # Fallback para valores padrão
            sequestration_rates = {
                'agricultura': {'min': 0.5, 'max': 2, 'avg': 1.25},
                'agroflorestal': {'min': 2, 'max': 6, 'avg': 4},
                'energia': {'min': 1, 'max': 3, 'avg': 2}
            }
            rate = sequestration_rates.get(practice_type, sequestration_rates['agricultura'])
            rate_min, rate_max, rate_avg = rate['min'], rate['max'], rate['avg']
            data_source = "Estimativa conservadora (dados limitados)"
    else:
        # Valores padrão
        sequestration_rates = {
            'agricultura': {'min': 0.5, 'max': 2, 'avg': 1.25},
            'agroflorestal': {'min': 2, 'max': 6, 'avg': 4},
            'energia': {'min': 1, 'max': 3, 'avg': 2}
        }
        rate = sequestration_rates.get(practice_type, sequestration_rates['agricultura'])
        rate_min, rate_max, rate_avg = rate['min'], rate['max'], rate['avg']
        data_source = "Estimativa padrão"
    
    # Cálculos de receita
    calculations = {
        'hectares': hectares,
        'practice_type': practice_type,
        'annual_sequestration_min': hectares * rate_min,
        'annual_sequestration_max': hectares * rate_max,
        'annual_sequestration_avg': hectares * rate_avg,
        'annual_revenue_min': hectares * rate_min * price_range['min'],
        'annual_revenue_max': hectares * rate_max * price_range['max'],
        'annual_revenue_avg': hectares * rate_avg * price_range['avg'],
        '10yr_revenue_avg': hectares * rate_avg * price_range['avg'] * 10,
        'price_per_ton': f"US${price_range['min']}-{price_range['max']}",
        'sequestration_per_ha': f"{rate_min:.2f}-{rate_max:.2f} tCO2/ha/ano",
        'data_source': data_source,
        'projects_count': stats.get('projects', 0) if use_dataset_stats and 'project_statistics' in st.session_state else 0
    }
    
    return calculations

# =========================
# ATUALIZAR A CALCULADORA DE RECEITA
# =========================

def create_revenue_calculator():
    """Cria calculadora de receita interativa com estatísticas reais"""
    with st.expander("🧮 CALCULE SEU POTENCIAL DE GANHO (COM DADOS REAIS)", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            hectares = st.number_input("Tamanho da propriedade (hectares):", 
                                     min_value=1.0, max_value=10000.0, value=100.0, step=10.0)
        
        with col2:
            practice_type = st.selectbox(
                "Prática sustentável:",
                ["Agricultura Regenerativa", "Agrofloresta", "Bioenergia", "Integração Lavoura-Pecuária"],
                index=0,
                key="calc_practice"
            )
        
        with col3:
            investment = st.number_input("Investimento inicial (US$):", 
                                       min_value=0.0, max_value=1000000.0, value=10000.0, step=1000.0,
                                       key="calc_investment")
        
        with col4:
            use_real_data = st.checkbox("Usar dados reais do mercado", value=True,
                                       help="Baseia os cálculos em projetos certificados existentes")
        
        # Mapear tipo selecionado para chave interna
        practice_map = {
            "Agricultura Regenerativa": "agricultura",
            "Agrofloresta": "agroflorestal",
            "Bioenergia": "energia",
            "Integração Lavoura-Pecuária": "agricultura"
        }
        practice_key = practice_map[practice_type]
        
        # Calcular com estatísticas reais
        revenue = calculate_potential_revenue(hectares, practice_key, use_real_data)
        break_even = calculate_break_even(hectares, investment, practice_key)
        
        # Exibir estatísticas de base de dados
        if use_real_data and revenue['projects_count'] > 0:
            st.info(f"📊 **Base estatística:** {revenue['data_source']} | Projetos analisados: {revenue['projects_count']}")
        
        # Resultados
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Receita Anual", f"US${revenue['annual_revenue_avg']:,.0f}",
                     delta=f"{revenue['annual_revenue_min']:,.0f}-{revenue['annual_revenue_max']:,.0f}")
        with col2:
            st.metric("📈 Receita 10 anos", f"US${revenue['10yr_revenue_avg']:,.0f}")
        with col3:
            st.metric("⏱️ Retorno (anos)", f"{break_even['break_even_years']:.1f}")
        with col4:
            st.metric("📊 ROI 5 anos", f"{break_even['roi_5yr']:.1f}%")
        
        # Detalhes expandidos
        with st.expander("📋 Ver detalhes do cálculo e estatísticas"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📈 Parâmetros de Cálculo")
                st.write(f"**Preço do carbono:** {revenue['price_per_ton']} por tonelada")
                st.write(f"**Sequestro estimado:** {revenue['sequestration_per_ha']}")
                st.write(f"**Fonte dos dados:** {revenue['data_source']}")
                
                if 'project_statistics' in st.session_state:
                    stats = st.session_state.project_statistics.get(practice_key, {})
                    if stats.get('projects', 0) > 0:
                        st.markdown("#### 📊 Estatísticas dos Projetos Reais")
                        st.write(f"**Número de projetos:** {stats['projects']}")
                        st.write(f"**Taxa média:** {stats['mean_rate']:.2f} tCO2/ha/ano")
                        st.write(f"**Variação (25%-75%):** {stats['q25']:.2f} - {stats['q75']:.2f} tCO2/ha/ano")
                        st.write(f"**Área média dos projetos:** {np.mean(stats['areas']):.1f} ha")
            
            with col2:
                st.markdown("#### 🧮 Cálculos Detalhados")
                st.write(f"**Sequestro total anual:** {revenue['annual_sequestration_avg']:,.1f} tCO2")
                st.write(f"**Receita mensal:** US${break_even['monthly_revenue']:,.0f}")
                st.write(f"**Receita anual mínima:** US${revenue['annual_revenue_min']:,.0f}")
                st.write(f"**Receita anual máxima:** US${revenue['annual_revenue_max']:,.0f}")
                
                # Adicionar gráfico de sensibilidade se houver dados estatísticos
                if 'project_statistics' in st.session_state and st.session_state.project_statistics.get(practice_key, {}).get('projects', 0) > 0:
                    st.markdown("#### 📊 Distribuição das Taxas de Sequestro")
                    
                    rates = st.session_state.project_statistics[practice_key]['sequestration_rates']
                    if len(rates) > 1:
                        fig = px.histogram(x=rates, nbins=20,
                                          title=f"Distribuição das Taxas ({practice_type})",
                                          labels={'x': 'tCO2/ha/ano', 'y': 'Número de Projetos'})
                        fig.add_vline(x=revenue['annual_sequestration_avg']/hectares, 
                                     line_dash="dash", line_color="red",
                                     annotation_text=f"Média: {revenue['annual_sequestration_avg']/hectares:.2f}")
                        st.plotly_chart(fig, use_container_width=True)

# =========================
# ATUALIZAR A FUNÇÃO MAIN PARA INCLUIR ANÁLISE
# =========================

def main():
    # Carregar dados
    with st.spinner("💰 Analisando oportunidades de receita no mercado de carbono..."):
        dataframes, sheet_names = load_data_with_revenue_focus()
    
    if dataframes is None:
        st.error("Não foi possível carregar os dados. Verifique o arquivo Dataset.xlsx")
        return
    
    # Analisar estatísticas dos projetos
    if 'project_statistics' not in st.session_state:
        with st.spinner("📊 Analisando estatísticas dos projetos reais..."):
            st.session_state.project_statistics = analyze_project_statistics(dataframes)
    
    # Sidebar principal (mantido igual)
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 1rem;'>
            <h2 style='color: #27ae60;'>💰 Ganhe com Carbono</h2>
            <p style='color: #7f8c8d;'>Para Proprietários Rurais</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Navegação principal
        page = st.radio(
            "Navegação",
            ["🏠 Oportunidades", "🔍 Projetos Reais", "📚 Casos de Sucesso", "📞 Como Participar", "📊 Estatísticas do Mercado"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Exibir estatísticas resumidas na sidebar
        st.markdown("### 📈 Estatísticas Reais")
        
        if 'project_statistics' in st.session_state:
            total_projects = sum(stats['projects'] for stats in st.session_state.project_statistics.values())
            st.info(f"**{total_projects}** projetos analisados")
            
            for practice, stats in st.session_state.project_statistics.items():
                if stats['projects'] > 0:
                    practice_name = {
                        'agricultura': '🌱 Agricultura',
                        'agroflorestal': '🌳 Agrofloresta',
                        'energia': '⚡ Energia'
                    }[practice]
                    
                    st.metric(practice_name, 
                             f"{stats['projects']} projetos",
                             f"{stats['mean_rate']:.1f} tCO2/ha/ano")
        
        st.markdown("---")
        
        # Links úteis
        st.markdown("### 🔗 Para Saber Mais")
        st.markdown("""
        - [FAO: Mercados de Carbono](https://www.fao.org/climate-change/our-work/carbon-markets)
        - [Agricultura de Baixo Carbono](https://www.gov.br/agricultura)
        - [Créditos de Carbono no Brasil](https://www.mma.gov.br)
        """)
    
    # Renderizar página selecionada
    if page == "🏠 Oportunidades":
        render_opportunities_home(dataframes)
    elif page == "🔍 Projetos Reais":
        render_project_explorer(dataframes, sheet_names)
    elif page == "📚 Casos de Sucesso":
        render_success_stories()
    elif page == "📊 Estatísticas do Mercado":
        render_market_statistics()
    else:
        render_how_to_participate()

# =========================
# NOVA PÁGINA: ESTATÍSTICAS DO MERCADO
# =========================

def render_market_statistics():
    """Renderiza página com estatísticas detalhadas do mercado"""
    st.markdown("## 📊 Estatísticas do Mercado Baseadas em Projetos Reais")
    
    if 'project_statistics' not in st.session_state:
        st.warning("Estatísticas ainda não foram calculadas. Aguarde...")
        return
    
    stats = st.session_state.project_statistics
    
    # Resumo geral
    total_projects = sum(data['projects'] for data in stats.values())
    st.metric("📈 Total de Projetos Analisados", total_projects)
    
    if total_projects == 0:
        st.info("Nenhum projeto com dados completos encontrado. Usando estimativas conservadoras.")
        return
    
    # Tabs para diferentes práticas
    tabs = st.tabs(["🌱 Agricultura", "🌳 Agrofloresta", "⚡ Energia", "📈 Comparativo"])
    
    with tabs[0]:
        if stats['agricultura']['projects'] > 0:
            display_practice_statistics(stats['agricultura'], "Agricultura Regenerativa")
        else:
            st.info("Dados insuficientes para agricultura")
    
    with tabs[1]:
        if stats['agroflorestal']['projects'] > 0:
            display_practice_statistics(stats['agroflorestal'], "Sistemas Agroflorestais")
        else:
            st.info("Dados insuficientes para agrofloresta")
    
    with tabs[2]:
        if stats['energia']['projects'] > 0:
            display_practice_statistics(stats['energia'], "Projetos de Energia")
        else:
            st.info("Dados insuficientes para energia")
    
    with tabs[3]:
        # Gráfico comparativo
        practices = []
        mean_rates = []
        project_counts = []
        
        for practice, data in stats.items():
            if data['projects'] > 0:
                practices.append({
                    'agricultura': 'Agricultura',
                    'agroflorestal': 'Agrofloresta',
                    'energia': 'Energia'
                }[practice])
                mean_rates.append(data['mean_rate'])
                project_counts.append(data['projects'])
        
        if practices:
            col1, col2 = st.columns(2)
            
            with col1:
                fig1 = px.bar(x=practices, y=mean_rates,
                            title="Taxa Média de Sequestro por Tipo de Projeto",
                            labels={'x': 'Tipo de Projeto', 'y': 'tCO2/ha/ano'},
                            color=practices)
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                fig2 = px.bar(x=practices, y=project_counts,
                            title="Número de Projetos por Categoria",
                            labels={'x': 'Tipo de Projeto', 'y': 'Número de Projetos'},
                            color=practices)
                st.plotly_chart(fig2, use_container_width=True)

def display_practice_statistics(data, title):
    """Exibe estatísticas detalhadas de uma prática específica"""
    st.markdown(f"### {title}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 Projetos Analisados", data['projects'])
    
    with col2:
        st.metric("📈 Taxa Média", f"{data['mean_rate']:.2f} tCO2/ha/ano")
    
    with col3:
        st.metric("🎯 Mediana", f"{data['median_rate']:.2f} tCO2/ha/ano")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        if len(data['sequestration_rates']) > 1:
            fig = px.histogram(x=data['sequestration_rates'], nbins=20,
                              title="Distribuição das Taxas de Sequestro",
                              labels={'x': 'tCO2/ha/ano', 'y': 'Frequência'})
            fig.add_vline(x=data['mean_rate'], line_dash="dash", line_color="red",
                         annotation_text=f"Média: {data['mean_rate']:.2f}")
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        if len(data['areas']) > 1:
            fig = px.box(y=data['areas'], title="Distribuição das Áreas dos Projetos (ha)")
            st.plotly_chart(fig, use_container_width=True)
    
    # Tabela de estatísticas
    st.markdown("#### 📋 Estatísticas Detalhadas")
    
    stats_df = pd.DataFrame({
        'Métrica': ['Mínimo', '25º Percentil', 'Média', 'Mediana', '75º Percentil', 'Máximo', 'Desvio Padrão'],
        'tCO2/ha/ano': [
            f"{data['min_rate']:.2f}",
            f"{data['q25']:.2f}",
            f"{data['mean_rate']:.2f}",
            f"{data['median_rate']:.2f}",
            f"{data['q75']:.2f}",
            f"{data['max_rate']:.2f}",
            f"{data['std_rate']:.2f}"
        ]
    })
    
    st.dataframe(stats_df, use_container_width=True, hide_index=True)
