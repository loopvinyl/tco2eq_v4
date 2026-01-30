import pandas as pd
import numpy as np

# ============================================
# CONFIGURAÇÕES
# ============================================
EXCEL_PATH = 'caminho/do/seu/arquivo.xlsx'  # Substitua pelo caminho correto
PRECO_POR_CREDITO = 22.5  # Preço médio por crédito (US$)

# ============================================
# FUNÇÃO PARA FORMATAR NÚMEROS
# ============================================
def formatar_numero(valor):
    """Formata números para exibição"""
    if valor >= 1e9:
        return f"{valor/1e9:.1f} bilhões"
    elif valor >= 1e6:
        return f"{valor/1e6:.1f} milhões"
    elif valor >= 1e3:
        return f"{valor/1e3:.1f} mil"
    else:
        return f"{valor:.0f}"

# ============================================
# LEITURA E PROCESSAMENTO DAS ABAS
# ============================================
print("📚 Casos Reais de Projetos que Geram Créditos")
print("💡 Baseado nos projetos certificados do dataset FAO")
print()

# ABA 4: AGRICULTURE - para créditos emitidos e aposentados
try:
    df_agriculture = pd.read_excel(EXCEL_PATH, sheet_name='4. Agriculture')
    
    # Identificar colunas de créditos (baseado na estrutura do relatório)
    # Colunas de créditos emitidos por ano (1996-2023) - colunas 23-50 no Excel
    colunas_emitidas = []
    colunas_aposentadas = []
    
    # Procurar colunas de créditos por nome ou posição
    for col in df_agriculture.columns:
        if isinstance(col, str):
            if 'credits issued' in col.lower() or 'issued' in col.lower():
                # Encontrar as colunas de anos seguintes
                idx = list(df_agriculture.columns).index(col)
                # Pegar 28 colunas (1996-2023)
                colunas_emitidas = list(range(idx, idx + 28))
                # As colunas aposentadas estão 29 colunas depois (colunas 52-79 no Excel)
                colunas_aposentadas = list(range(idx + 29, idx + 57))
                break
    
    # Se não encontrou pelos nomes, usar índices padrão baseado no relatório
    if not colunas_emitidas:
        # Pelo relatório: coluna 23 é a primeira de créditos emitidos
        # No pandas, índices começam em 0, então coluna 22
        colunas_emitidas = list(range(22, 50))  # 28 colunas (1996-2023)
        colunas_aposentadas = list(range(51, 79))  # 28 colunas (1996-2023)
    
    # Calcular totais por projeto
    df_agriculture['Total Emitido'] = df_agriculture.iloc[:, colunas_emitidas].sum(axis=1)
    df_agriculture['Total Aposentado'] = df_agriculture.iloc[:, colunas_aposentadas].sum(axis=1)
    
    # Filtrar projetos com créditos emitidos e aposentados positivos
    df_filtrado = df_agriculture[
        (df_agriculture['Total Emitido'] > 0) &
        (df_agriculture['Total Aposentado'] > 0)
    ].copy()
    
    if len(df_filtrado) > 0:
        # Selecionar os 3 projetos com mais créditos aposentados (mais relevantes comercialmente)
        df_top3 = df_filtrado.nlargest(3, 'Total Aposentado')
        
        # Cálculo das receitas
        df_top3.loc[:, 'Receita Real (US$)'] = df_top3['Total Aposentado'] * PRECO_POR_CREDITO
        df_top3.loc[:, 'Receita Potencial (US$)'] = df_top3['Total Emitido'] * PRECO_POR_CREDITO
        
        # Exibir os projetos
        for idx, row in df_top3.iterrows():
            # Nome do projeto (segunda coluna baseado no relatório)
            nome_projeto = str(row.iloc[1]) if len(row) > 1 else "Projeto sem nome"
            
            # Evitar usar a linha de cabeçalho
            if nome_projeto.lower() in ['project name', 'nome do projeto', 'nan']:
                continue
                
            total_emitido = row['Total Emitido']
            total_aposentado = row['Total Aposentado']
            receita_real = row['Receita Real (US$)']
            receita_potencial = row['Receita Potencial (US$)']
            
            print('🌳')
            print(f'{nome_projeto}')
            print(f'Projeto certificado. Emitiu {formatar_numero(total_emitido)} créditos de carbono')
            print(f'com {formatar_numero(total_aposentado)} já aposentados (vendidos).')
            print()
            print('Receita Real (vendida)')
            print(f'US$ {receita_real/1e6:.1f} milhões')
            print('Receita Potencial')
            print(f'US$ {receita_potencial/1e6:.1f} milhões')
            print('Categoria: Agriculture • Fonte: 4. Agriculture')
            print()
            
    else:
        print("⚠️  Nenhum projeto com créditos emitidos e aposentados encontrado na aba Agriculture.")
        print()

except Exception as e:
    print(f"⚠️  Erro ao processar a aba Agriculture: {str(e)}")
    print()

# ============================================
# ABA 7: Plan Vivo, Acorn, Social C (mantendo o exemplo original)
# ============================================
try:
    df_plan_vivo = pd.read_excel(EXCEL_PATH, sheet_name='7. Plan Vivo, Acorn, Social C')
    
    # Filtrar projetos com créditos emitidos
    if 'Issued credits' in df_plan_vivo.columns:
        df_plan_vivo_filtrado = df_plan_vivo[df_plan_vivo['Issued credits'] > 0]
        
        if len(df_plan_vivo_filtrado) > 0:
            # Selecionar 2 projetos para exemplo
            projetos_exemplo = df_plan_vivo_filtrado.head(2)
            
            for idx, row in projetos_exemplo.iterrows():
                nome = row['Project name'] if 'Project name' in row else "Projeto sem nome"
                pais = row['Country'] if 'Country' in row else "País não especificado"
                area = row['Land covered (ha)'] if 'Land covered (ha)' in row else None
                creditos = row['Issued credits']
                
                receita_potencial = creditos * PRECO_POR_CREDITO
                
                print('🌳')
                print(f'{nome}')
                if area and not np.isnan(area):
                    print(f'Projeto certificado em {pais} com {area:,.0f} hectares. Emitiu {formatar_numero(creditos)} créditos de carbono')
                else:
                    print(f'Projeto certificado em {pais}. Emitiu {formatar_numero(creditos)} créditos de carbono')
                print()
                print('Receita Real (vendida)')
                print(f'US$ 0,0 milhões')  # Dados de aposentadoria não disponíveis nesta aba
                print('Receita Potencial')
                print(f'US$ {receita_potencial/1e6:.1f} milhões')
                print('Categoria: Agroflorestal • Fonte: 7. Plan Vivo, Acorn, Social C')
                print()
                
except Exception as e:
    print(f"⚠️  Erro ao processar a aba Plan Vivo: {str(e)}")
    print()

# ============================================
# ABA 9: Nori and BCarbon (exemplo adicional)
# ============================================
try:
    df_nori = pd.read_excel(EXCEL_PATH, sheet_name='9. Nori and BCarbon')
    
    # Filtrar projetos com créditos emitidos
    if 'Issued credits' in df_nori.columns:
        df_nori_filtrado = df_nori[df_nori['Issued credits'] > 0]
        
        if len(df_nori_filtrado) > 0:
            # Selecionar 1 projeto para exemplo
            projetos_exemplo = df_nori_filtrado.head(1)
            
            for idx, row in projetos_exemplo.iterrows():
                nome = row['Project name'] if 'Project name' in row else "Projeto sem nome"
                pais = row['Country'] if 'Country' in row else "País não especificado"
                creditos = row['Issued credits']
                
                receita_potencial = creditos * PRECO_POR_CREDITO
                
                print('🌳')
                print(f'{nome}')
                print(f'Projeto certificado em {pais}. Emitiu {formatar_numero(creditos)} créditos de carbono')
                print()
                print('Receita Real (vendida)')
                print(f'US$ 0,0 milhões')  # Dados de aposentadoria não disponíveis nesta aba
                print('Receita Potencial')
                print(f'US$ {receita_potencial/1e6:.1f} milhões')
                print('Categoria: Agricultura Sustentável • Fonte: 9. Nori and BCarbon')
                print()
                
except Exception as e:
    print(f"⚠️  Erro ao processar a aba Nori and BCarbon: {str(e)}")

print("=" * 60)
print("💡 Nota: Valores calculados com base no preço médio de US$ 22,50 por crédito")
print("📊 Dados extraídos do relatório completo do dataset FAO")
