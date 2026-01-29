# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from io import BytesIO
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Carbon Market Dashboard",
    page_icon="📊",
    layout="wide"
)

# URL do dataset
GITHUB_RAW_URL = "https://raw.githubusercontent.com/tco2eq_v3/tco2eq_v3/main/Dataset.xlsx"

# Carregar dados
@st.cache_data(ttl=3600)
def load_data():
    try:
        response = requests.get(GITHUB_RAW_URL, timeout=30)
        response.raise_for_status()
        
        excel_file = pd.ExcelFile(BytesIO(response.content))
        sheets = excel_file.sheet_names
        
        dataframes = {}
        for sheet in sheets:
            df = pd.read_excel(excel_file, sheet_name=sheet)
            dataframes[sheet] = df
        
        return dataframes, sheets
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return {}, []

# Interface principal
def main():
    st.title("🌱 Mercado de Carbono Agrícola - FAO")
    st.markdown("Dashboard de análise estratégica")
    
    # Carregar dados
    dataframes, sheets = load_data()
    
    if not dataframes:
        st.warning("Não foi possível carregar os dados.")
        return
    
    # KPIs principais
    st.markdown("---")
    st.subheader("📈 KPIs Principais")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Calcular métricas básicas
    total_projects = 0
    if '4. Agriculture' in dataframes:
        total_projects += dataframes['4. Agriculture'].shape[0]
    if '5. Agroforestry-AR & Grassland' in dataframes:
        total_projects += dataframes['5. Agroforestry-AR & Grassland'].shape[0]
    if '6. Energy and Other ' in dataframes:
        total_projects += dataframes['6. Energy and Other '].shape[0]
    
    with col1:
        st.metric("Total de Projetos", f"{total_projects:,}")
    
    with col2:
        if '1. Standards' in dataframes:
            standards = len(dataframes['1. Standards'])
            st.metric("Padrões", standards)
        else:
            st.metric("Padrões", "N/A")
    
    with col3:
        if '3. Methodologies' in dataframes:
            methodologies = dataframes['3. Methodologies'].shape[0]
            st.metric("Metodologias", methodologies)
        else:
            st.metric("Metodologias", "N/A")
    
    with col4:
        if '2. Platforms' in dataframes:
            platforms = dataframes['2. Platforms'].shape[0]
            st.metric("Plataformas", platforms)
        else:
            st.metric("Plataformas", "N/A")
    
    # Distribuição de projetos
    st.markdown("---")
    st.subheader("📊 Distribuição de Projetos")
    
    project_data = {
        'Agricultura': dataframes.get('4. Agriculture', pd.DataFrame()).shape[0],
        'Agroflorestal': dataframes.get('5. Agroforestry-AR & Grassland', pd.DataFrame()).shape[0],
        'Energia': dataframes.get('6. Energy and Other ', pd.DataFrame()).shape[0],
        'Pequena Escala': dataframes.get('7. Plan Vivo, Acorn, Social C', pd.DataFrame()).shape[0]
    }
    
    # Gráfico de pizza
    fig = px.pie(
        values=list(project_data.values()),
        names=list(project_data.keys()),
        title="Projetos por Categoria",
        hole=0.4,
        color_discrete_sequence=px.colors.sequential.Greens_r
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Análise por escala
    st.markdown("---")
    st.subheader("🏗️ Projetos por Escala")
    
    scale_data = {
        'Grande Escala': project_data['Agricultura'] + project_data['Energia'],
        'Média Escala': project_data['Agroflorestal'],
        'Pequena Escala': project_data['Pequena Escala']
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig2 = px.bar(
            x=list(scale_data.keys()),
            y=list(scale_data.values()),
            title="Distribuição por Escala",
            color=list(scale_data.values()),
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    with col2:
        # Métricas de escala
        st.markdown("### 📋 Resumo por Escala")
        for scale, count in scale_data.items():
            percentage = (count / total_projects * 100) if total_projects > 0 else 0
            st.markdown(f"**{scale}:** {count:,} projetos ({percentage:.1f}%)")
        
        st.markdown("---")
        st.markdown("**Definição:**")
        st.markdown("- **Grande:** Agricultura + Energia")
        st.markdown("- **Média:** Agroflorestal")
        st.markdown("- **Pequena:** Plan Vivo, Acorn, Social Carbon")
    
    # Principais padrões
    st.markdown("---")
    st.subheader("🏆 Principais Padrões")
    
    if '1. Standards' in dataframes:
        df_standards = dataframes['1. Standards']
        if 'Name of standard/registry/platform' in df_standards.columns:
            st.markdown("### Padrões Ativos no Mercado")
            
            standards_list = df_standards['Name of standard/registry/platform'].dropna().unique()
            
            cols = st.columns(2)
            for idx, standard in enumerate(standards_list[:6]):
                with cols[idx % 2]:
                    st.markdown(f"""
                    <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-left: 4px solid #00A86B;'>
                        <strong>{standard}</strong>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Insights estratégicos
    st.markdown("---")
    st.subheader("💡 Insights Estratégicos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Tendências")
        st.markdown("""
        1. **Agricultura lidera** em número de projetos
        2. Crescimento em **projetos agroflorestais**
        3. **MRV digital** em expansão
        4. **Biochar** como tecnologia emergente
        """)
    
    with col2:
        st.markdown("### 📈 Oportunidades")
        st.markdown("""
        1. **Projetos integrados** (agro+energia)
        2. **Mercados emergentes** com alto potencial
        3. **Tecnologias de monitoramento** remoto
        4. **Metodologias híbridas** para diferentes escalas
        """)
    
    # Footer
    st.markdown("---")
    st.markdown(f"""
    <div style='text-align: center; color: #666; font-size: 12px;'>
        📊 Carbon Market Dashboard • Dados FAO 2025 • {datetime.now().strftime('%d/%m/%Y')}
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
