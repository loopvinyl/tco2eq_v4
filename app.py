import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import requests

# Configuração da página
st.set_page_config(
    page_title="Análise de Créditos de Carbono - Agricultura",
    page_icon="🌱",
    layout="wide"
)

# Título e introdução
st.title("🌱 Análise de Projetos de Créditos de Carbono - Setor Agrícola")
st.markdown("""
Esta aplicação analisa projetos de créditos de carbono do setor agrícola baseados no 
**Berkeley Voluntary Registry Offsets Database v8**.
""")

# Função para carregar dados
@st.cache_data
def load_data():
    # URL do arquivo Excel no GitHub (raw URL)
    url = "https://raw.githubusercontent.com/loopvinyl/tco2eq_v4/main/Dataset.xlsx"
    
    try:
        # Baixar o arquivo
        response = requests.get(url)
        response.raise_for_status()
        
        # Ler a aba específica (4.Agriculture)
        excel_file = BytesIO(response.content)
        
        # Tentar ler com diferentes nomes de aba
        try:
            df = pd.read_excel(excel_file, sheet_name='4.Agriculture')
        except:
            # Tentar encontrar o nome correto da aba
            xls = pd.ExcelFile(excel_file)
            st.info(f"Abas disponíveis: {xls.sheet_names}")
            
            # Procurar por aba que contenha 'Agriculture'
            for sheet in xls.sheet_names:
                if 'agriculture' in sheet.lower() or 'Agriculture' in sheet:
                    df = pd.read_excel(excel_file, sheet_name=sheet)
                    break
            else:
                # Se não encontrar, usar a primeira aba
                df = pd.read_excel(excel_file, sheet_name=0)
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        # Carregar dados de exemplo se não conseguir baixar
        return None

# Carregar dados
df = load_data()

if df is not None:
    st.success(f"Dados carregados com sucesso! Total de {len(df)} projetos.")
    
    # Renomear colunas importantes para facilitar o acesso
    column_mapping = {
        'Project ID': 'Project_ID',
        'Project Name': 'Project_Name',
        'Voluntary Registry': 'Voluntary_Registry',
        'ARB <br>Project': 'ARB_Project',
        'Voluntary Status': 'Voluntary_Status',
        'Scope': 'Scope',
        'Type': 'Type',
        'Reduction / Removal': 'Reduction_Removal',
        'Methodology / Protocol': 'Methodology_Protocol',
        'Region': 'Region',
        'Country': 'Country',
        'State': 'State',
        'Country classification by Income level': 'Income_Level',
        'Total Credits <br>Issued': 'Total_Credits_Issued',
        'Total Credits <br>Retired': 'Total_Credits_Retired',
        'Total Credits Remaining': 'Total_Credits_Remaining',
        'Total Buffer <br>Pool Deposits': 'Total_Buffer_Pool_Deposits'
    }
    
    # Aplicar renomeação apenas para colunas existentes
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns:
            df.rename(columns={old_name: new_name}, inplace=True)
    
    # Converter colunas numéricas
    numeric_columns = ['Total_Credits_Issued', 'Total_Credits_Retired', 'Total_Credits_Remaining']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Sidebar com filtros
    st.sidebar.header("🔍 Filtros")
    
    # Filtro por status
    if 'Voluntary_Status' in df.columns:
        status_options = ['Todos'] + sorted(df['Voluntary_Status'].dropna().unique().tolist())
        selected_status = st.sidebar.multiselect(
            "Status do Projeto",
            options=status_options,
            default=['Registered', 'Completed']
        )
        
        if 'Todos' not in selected_status:
            df_filtered = df[df['Voluntary_Status'].isin(selected_status)]
        else:
            df_filtered = df.copy()
    else:
        df_filtered = df.copy()
        st.sidebar.warning("Coluna 'Voluntary_Status' não encontrada")
    
    # Filtro por registro voluntário
    if 'Voluntary_Registry' in df.columns:
        registry_options = ['Todos'] + sorted(df_filtered['Voluntary_Registry'].dropna().unique().tolist())
        selected_registry = st.sidebar.multiselect(
            "Registro Voluntário",
            options=registry_options,
            default=['Todos']
        )
        
        if 'Todos' not in selected_registry:
            df_filtered = df_filtered[df_filtered['Voluntary_Registry'].isin(selected_registry)]
    
    # Filtro por país
    if 'Country' in df.columns:
        country_options = ['Todos'] + sorted(df_filtered['Country'].dropna().unique().tolist())
        selected_country = st.sidebar.multiselect(
            "País",
            options=country_options,
            default=['Todos']
        )
        
        if 'Todos' not in selected_country:
            df_filtered = df_filtered[df_filtered['Country'].isin(selected_country)]
    
    # Filtro por tipo de projeto
    if 'Type' in df.columns:
        type_options = ['Todos'] + sorted(df_filtered['Type'].dropna().unique().tolist())
        selected_type = st.sidebar.multiselect(
            "Tipo de Projeto",
            options=type_options,
            default=['Todos']
        )
        
        if 'Todos' not in selected_type:
            df_filtered = df_filtered[df_filtered['Type'].isin(selected_type)]
    
    # Filtro por créditos emitidos > 0
    show_only_with_credits = st.sidebar.checkbox("Apenas projetos com créditos emitidos > 0", value=True)
    if show_only_with_credits and 'Total_Credits_Issued' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Total_Credits_Issued'] > 0]
    
    # Métricas principais
    st.header("📊 Métricas Principais")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_projects = len(df_filtered)
        st.metric("Total de Projetos", f"{total_projects:,}")
    
    with col2:
        if 'Total_Credits_Issued' in df_filtered.columns:
            total_issued = df_filtered['Total_Credits_Issued'].sum()
            st.metric("Créditos Emitidos (tCO₂eq)", f"{total_issued:,.0f}")
    
    with col3:
        if 'Total_Credits_Retired' in df_filtered.columns:
            total_retired = df_filtered['Total_Credits_Retired'].sum()
            st.metric("Créditos Aposentados (tCO₂eq)", f"{total_retired:,.0f}")
    
    with col4:
        if 'Total_Credits_Remaining' in df_filtered.columns:
            total_remaining = df_filtered['Total_Credits_Remaining'].sum()
            st.metric("Créditos Disponíveis (tCO₂eq)", f"{total_remaining:,.0f}")
    
    # Taxa de aposentadoria
    if 'Total_Credits_Issued' in df_filtered.columns and 'Total_Credits_Retired' in df_filtered.columns:
        total_issued = df_filtered['Total_Credits_Issued'].sum()
        total_retired = df_filtered['Total_Credits_Retired'].sum()
        if total_issued > 0:
            retirement_rate = (total_retired / total_issued) * 100
            st.metric("Taxa de Aposentadoria", f"{retirement_rate:.1f}%")
    
    # Tabs para diferentes visualizações
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Tabela de Projetos", "📈 Análise por Categoria", "🗺️ Mapa Geográfico", "📊 Insights"])
    
    with tab1:
        st.subheader("Tabela de Projetos Detalhada")
        
        # Selecionar colunas para exibir
        default_columns = [
            'Project_ID', 'Project_Name', 'Voluntary_Registry', 'Voluntary_Status',
            'Country', 'Type', 'Total_Credits_Issued', 'Total_Credits_Retired',
            'Total_Credits_Remaining'
        ]
        
        # Filtrar apenas colunas existentes
        available_columns = [col for col in default_columns if col in df_filtered.columns]
        
        # Exibir dataframe
        st.dataframe(
            df_filtered[available_columns],
            use_container_width=True,
            height=400
        )
        
        # Opção para download
        csv = df_filtered[available_columns].to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="projetos_carbono_agricultura.csv",
            mime="text/csv"
        )
    
    with tab2:
        st.subheader("Análise por Categoria")
        
        # Gráficos de análise
        col1, col2 = st.columns(2)
        
        with col1:
            if 'Voluntary_Registry' in df_filtered.columns:
                # Créditos por registro
                registry_credits = df_filtered.groupby('Voluntary_Registry')['Total_Credits_Issued'].sum().reset_index()
                registry_credits = registry_credits.sort_values('Total_Credits_Issued', ascending=False)
                
                fig1 = px.bar(
                    registry_credits.head(10),
                    x='Voluntary_Registry',
                    y='Total_Credits_Issued',
                    title='Créditos Emitidos por Registro (Top 10)',
                    labels={'Total_Credits_Issued': 'Créditos (tCO₂eq)', 'Voluntary_Registry': 'Registro'}
                )
                st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            if 'Type' in df_filtered.columns:
                # Projetos por tipo
                type_counts = df_filtered['Type'].value_counts().reset_index()
                type_counts.columns = ['Type', 'Count']
                
                fig2 = px.pie(
                    type_counts,
                    values='Count',
                    names='Type',
                    title='Distribuição por Tipo de Projeto',
                    hole=0.3
                )
                st.plotly_chart(fig2, use_container_width=True)
        
        # Gráfico de status
        if 'Voluntary_Status' in df_filtered.columns:
            status_credits = df_filtered.groupby('Voluntary_Status')[['Total_Credits_Issued', 'Total_Credits_Retired']].sum().reset_index()
            
            fig3 = go.Figure(data=[
                go.Bar(name='Emitidos', x=status_credits['Voluntary_Status'], y=status_credits['Total_Credits_Issued']),
                go.Bar(name='Aposentados', x=status_credits['Voluntary_Status'], y=status_credits['Total_Credits_Retired'])
            ])
            
            fig3.update_layout(
                title='Créditos por Status do Projeto',
                barmode='group',
                xaxis_title="Status",
                yaxis_title="Créditos (tCO₂eq)"
            )
            st.plotly_chart(fig3, use_container_width=True)
    
    with tab3:
        st.subheader("Distribuição Geográfica")
        
        if 'Country' in df_filtered.columns:
            # Mapa por país
            country_credits = df_filtered.groupby('Country')['Total_Credits_Issued'].sum().reset_index()
            country_credits = country_credits.sort_values('Total_Credits_Issued', ascending=False)
            
            # Exibir tabela
            st.dataframe(
                country_credits,
                column_config={
                    "Country": "País",
                    "Total_Credits_Issued": st.column_config.NumberColumn(
                        "Créditos Emitidos",
                        help="Total de créditos emitidos em tCO₂eq",
                        format="%d"
                    )
                },
                use_container_width=True,
                height=300
            )
            
            # Gráfico de barras por país
            fig4 = px.bar(
                country_credits.head(15),
                x='Country',
                y='Total_Credits_Issued',
                title='Top 15 Países por Créditos Emitidos',
                labels={'Total_Credits_Issued': 'Créditos (tCO₂eq)', 'Country': 'País'}
            )
            st.plotly_chart(fig4, use_container_width=True)
    
    with tab4:
        st.subheader("Insights e Análises")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🔍 Principais Conclusões")
            
            if 'Total_Credits_Issued' in df_filtered.columns and len(df_filtered) > 0:
                # Projeto com mais créditos
                max_credits_idx = df_filtered['Total_Credits_Issued'].idxmax()
                max_project = df_filtered.loc[max_credits_idx]
                
                st.info(f"""
                **Projeto com mais créditos:**  
                {max_project.get('Project_Name', 'N/A')}  
                **Créditos emitidos:** {max_project.get('Total_Credits_Issued', 0):,.0f} tCO₂eq  
                **Registro:** {max_project.get('Voluntary_Registry', 'N/A')}
                """)
                
                # Taxa média de aposentadoria
                df_with_issued = df_filtered[df_filtered['Total_Credits_Issued'] > 0]
                if len(df_with_issued) > 0:
                    avg_retirement_rate = (df_with_issued['Total_Credits_Retired'].sum() / 
                                          df_with_issued['Total_Credits_Issued'].sum()) * 100
                    st.metric("Taxa Média de Aposentadoria", f"{avg_retirement_rate:.1f}%")
        
        with col2:
            st.markdown("### 📈 Estatísticas")
            
            if 'Total_Credits_Issued' in df_filtered.columns:
                stats_df = pd.DataFrame({
                    'Métrica': ['Média', 'Mediana', 'Máximo', 'Mínimo'],
                    'Créditos Emitidos (tCO₂eq)': [
                        df_filtered['Total_Credits_Issued'].mean(),
                        df_filtered['Total_Credits_Issued'].median(),
                        df_filtered['Total_Credits_Issued'].max(),
                        df_filtered['Total_Credits_Issued'].min()
                    ]
                })
                
                st.dataframe(stats_df, use_container_width=True)
        
        # Análise por metodologia
        if 'Methodology_Protocol' in df_filtered.columns:
            st.markdown("### 🧪 Metodologias mais Utilizadas")
            
            methodology_counts = df_filtered['Methodology_Protocol'].value_counts().head(10)
            methodology_df = methodology_counts.reset_index()
            methodology_df.columns = ['Metodologia', 'Número de Projetos']
            
            st.dataframe(methodology_df, use_container_width=True, height=300)
    
    # Seção de explicação
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    ### ℹ️ Sobre os Dados
    
    **Fonte:** Berkeley Voluntary Registry Offsets Database v8  
    **Setor:** Agricultura  
    **Aba:** 4.Agriculture
    
    **Definições:**
    - **Créditos Emitidos:** Total de créditos de carbono gerados (tCO₂eq)
    - **Créditos Aposentados:** Créditos que foram utilizados/compensados
    - **Créditos Remanescentes:** Créditos ainda disponíveis no mercado
    """)
    
else:
    st.error("Não foi possível carregar os dados. Verifique a conexão com a internet.")
    
    # Código de exemplo para desenvolvimento offline
    st.info("""
    Para desenvolvimento offline, você pode:
    1. Baixar o arquivo Dataset.xlsx localmente
    2. Modificar o código para ler do arquivo local:
    
    ```python
    df = pd.read_excel('Dataset.xlsx', sheet_name='4.Agriculture')
    ```
    """)
