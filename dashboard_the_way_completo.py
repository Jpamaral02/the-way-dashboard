import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib.pyplot as plt
import seaborn as sns
import io
from pathlib import Path
from datetime import datetime, timedelta
from scipy import stats

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard The Way - Completo", layout="wide", page_icon="👕")

# --- DICA DE OURO: FUNÇÃO DE CACHE ---
@st.cache_data
def carregar_dados(arquivo):
    """Lê o arquivo uma única vez e mantém na memória."""
    df = pd.read_excel(arquivo)
    df['data'] = pd.to_datetime(df['data'], format='mixed', dayfirst=True)
    return df

# --- SISTEMA DE LOGIN ---
SENHA_CORRETA = "theway2026"

def verificar_senha():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.title("🔐 Acesso Restrito - The Way")
        col_l, col_r = st.columns([1, 2])
        with col_l:
            senha_digitada = st.text_input("Digite a senha de acesso:", type="password")
            if st.button("Entrar"):
                if senha_digitada == SENHA_CORRETA:
                    st.session_state["autenticado"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta!")
        return False
    return True

# --- FUNÇÕES DE CÁLCULO DE ESTATÍSTICAS ---

def calcular_todas_estatisticas(df_bruto, df, hoje, dias_projecao):
    """Calcula todas as 33 estatísticas"""
    
    stats_dict = {}
    
    # 1. TOTAL DE VENDAS (quantidade de transações)
    stats_dict['total_vendas'] = len(df)
    
    # 2. FATURAMENTO TOTAL
    stats_dict['faturamento_total'] = df['valor'].sum()
    
    # 3. TICKET MÉDIO
    stats_dict['ticket_medio'] = df['valor'].mean()
    
    # 4. TICKET MEDIANO
    stats_dict['ticket_mediano'] = df['valor'].median()
    
    # 5. VALOR MÍNIMO
    stats_dict['valor_minimo'] = df['valor'].min()
    
    # 6. VALOR MÁXIMO
    stats_dict['valor_maximo'] = df['valor'].max()
    
    # 7. TOTAL DE CLIENTES ÚNICOS
    stats_dict['total_clientes'] = df['cliente_id'].nunique()
    
    # 8. CLIENTES RECORRENTES (2+ compras)
    cliente_compras = df.groupby('cliente_id').size()
    stats_dict['clientes_recorrentes'] = len(cliente_compras[cliente_compras >= 2])
    
    # 9. TAXA DE CLIENTES RECORRENTES
    stats_dict['taxa_recorrencia'] = (stats_dict['clientes_recorrentes'] / stats_dict['total_clientes'] * 100) if stats_dict['total_clientes'] > 0 else 0
    
    # 10. PRODUTO MAIS VENDIDO
    produto_vendas = df.groupby('produto')['valor'].sum().idxmax()
    stats_dict['produto_mais_vendido'] = produto_vendas
    stats_dict['valor_produto_mais_vendido'] = df.groupby('produto')['valor'].sum().max()
    
    # 11. PRODUTO MENOS VENDIDO
    produto_menos = df.groupby('produto')['valor'].sum().idxmin()
    stats_dict['produto_menos_vendido'] = produto_menos
    stats_dict['valor_produto_menos_vendido'] = df.groupby('produto')['valor'].sum().min()
    
    # 12. AOV (Average Order Value)
    stats_dict['aov'] = df.groupby('cliente_id')['valor'].sum().mean()
    
    # 13. LIFETIME VALUE (LTV) - Total gasto por cliente
    ltv_clientes = df_bruto.groupby('cliente_id')['valor'].sum().reset_index()
    stats_dict['ltv_medio'] = ltv_clientes['valor'].mean()
    stats_dict['ltv_max'] = ltv_clientes['valor'].max()
    
    # 14. FREQUÊNCIA MÉDIA DE COMPRA (dias entre compras)
    freq_compra = df.sort_values(['cliente_id', 'data']).groupby('cliente_id')['data'].diff().dt.days.mean()
    stats_dict['freq_compra_dias'] = freq_compra if pd.notna(freq_compra) else 0
    
    # 15. TAXA DE CHURN (180 dias)
    ultima_visita = df_bruto.groupby('cliente_id')['data'].max().reset_index()
    ultima_visita['dias_parado'] = (hoje - ultima_visita['data']).dt.days
    ultima_visita['status'] = ultima_visita['dias_parado'].apply(lambda x: 'Churn' if x > 180 else 'Ativo')
    stats_dict['taxa_churn'] = (len(ultima_visita[ultima_visita['status'] == 'Churn']) / len(ultima_visita) * 100) if len(ultima_visita) > 0 else 0
    
    # 16. TAXA DE RETENÇÃO
    stats_dict['taxa_retencao'] = 100 - stats_dict['taxa_churn']
    
    # 17. CLIENTES DORMENTES (90+ dias sem comprar)
    clientes_dormentes = len(ultima_visita[ultima_visita['dias_parado'] > 90])
    stats_dict['clientes_dormentes'] = clientes_dormentes
    stats_dict['taxa_dormentes'] = (clientes_dormentes / len(ultima_visita) * 100) if len(ultima_visita) > 0 else 0
    
    # 18. CLIENTES EM RISCO (30-90 dias)
    clientes_risco = len(ultima_visita[(ultima_visita['dias_parado'] > 30) & (ultima_visita['dias_parado'] <= 90)])
    stats_dict['clientes_risco'] = clientes_risco
    
    # 19. CLIENTE MELHOR PAGADOR
    cliente_top = df.groupby('cliente_id')['valor'].sum().idxmax()
    stats_dict['cliente_top'] = cliente_top
    stats_dict['valor_cliente_top'] = df.groupby('cliente_id')['valor'].sum().max()
    
    # 20. TOP 5 CLIENTES
    top_5_clientes = df.groupby('cliente_id')['valor'].sum().nlargest(5).reset_index()
    stats_dict['top_5_clientes'] = top_5_clientes
    
    # 21. CRESCIMENTO MOM (Mês a Mês)
    df_temp = df.copy()
    df_temp['mes_ano'] = df_temp['data'].dt.to_period('M')
    vendas_mensais = df_temp.groupby('mes_ano')['valor'].sum()
    if len(vendas_mensais) >= 2:
        crescimento_mom = ((vendas_mensais.iloc[-1] - vendas_mensais.iloc[-2]) / vendas_mensais.iloc[-2] * 100) if vendas_mensais.iloc[-2] > 0 else 0
    else:
        crescimento_mom = 0
    stats_dict['crescimento_mom'] = crescimento_mom
    
    # 22. SAZONALIDADE MENSAL
    stats_dict['vendas_mensais'] = vendas_mensais
    
    # 23. DISTRIBUIÇÃO POR DIA DA SEMANA
    df_temp['dia_semana'] = df_temp['data'].dt.day_name()
    stats_dict['vendas_por_dia_semana'] = df_temp.groupby('dia_semana')['valor'].sum()
    
    # 24. PROJEÇÃO FINANCEIRA
    imr_global = df.sort_values(['cliente_id', 'data']).groupby('cliente_id')['data'].diff().dt.days.mean()
    ultima_visita['prevista'] = ultima_visita['data'] + pd.to_timedelta(imr_global, unit='D')
    proximos = ultima_visita[(ultima_visita['prevista'] > hoje) & 
                             (ultima_visita['prevista'] <= hoje + pd.Timedelta(days=dias_projecao)) &
                             (ultima_visita['status'] == 'Ativo')]
    faturamento_por_cliente = df.groupby('cliente_id')['valor'].mean().reset_index()
    faturamento_proj = proximos.merge(faturamento_por_cliente, on='cliente_id')['valor'].sum()
    stats_dict['faturamento_projecao'] = faturamento_proj
    
    # 25. MATRIZ RFM (Recency, Frequency, Monetary)
    rfm = df_bruto.groupby('cliente_id').agg({
        'data': lambda x: (hoje - x.max()).days,
        'cliente_id': 'count',
        'valor': 'sum'
    }).rename(columns={'data': 'recency', 'cliente_id': 'frequency', 'valor': 'monetary'})
    stats_dict['rfm'] = rfm
    
    # 26. SEGMENTAÇÃO DE CLIENTES POR FAIXA DE GASTO
    ltv_clientes_seg = df_bruto.groupby('cliente_id')['valor'].sum().reset_index()
    ltv_clientes_seg['segmento'] = pd.cut(ltv_clientes_seg['valor'], 
                                           bins=[0, ltv_clientes_seg['valor'].quantile(0.33), 
                                                 ltv_clientes_seg['valor'].quantile(0.66), 
                                                 ltv_clientes_seg['valor'].max()],
                                           labels=['Básico', 'Standard', 'Premium'])
    stats_dict['segmentacao_clientes'] = ltv_clientes_seg['segmento'].value_counts()
    
    # 27. ELASTICIDADE DE PREÇO (variação de preço vs quantidade)
    produto_preco = df.groupby('produto').agg({'valor': ['mean', 'count']})
    stats_dict['elasticidade_preco'] = produto_preco
    
    # 28. PRODUTOS MAIS FREQUENTES
    produtos_freq = df['produto'].value_counts().head(5)
    stats_dict['produtos_frequentes'] = produtos_freq
    
    # 29. VARIÂNCIA DE VENDAS
    stats_dict['desvio_padrao'] = df['valor'].std()
    stats_dict['coeficiente_variacao'] = (stats_dict['desvio_padrao'] / stats_dict['ticket_medio'] * 100) if stats_dict['ticket_medio'] > 0 else 0
    
    # 30. PERCENTIS DE VENDA
    stats_dict['percentil_25'] = df['valor'].quantile(0.25)
    stats_dict['percentil_50'] = df['valor'].quantile(0.50)
    stats_dict['percentil_75'] = df['valor'].quantile(0.75)
    stats_dict['percentil_90'] = df['valor'].quantile(0.90)
    
    # 31. ÍNDICE DE CONCENTRAÇÃO (Curva ABC)
    abc = df.groupby('produto')['valor'].sum().sort_values(ascending=False).reset_index()
    abc['Participação %'] = (abc['valor'] / abc['valor'].sum() * 100).round(1)
    abc['Cumulative %'] = abc['Participação %'].cumsum()
    stats_dict['curva_abc'] = abc
    
    # 32. ANÁLISE DE COHORT (Clientes por período)
    df_cohort = df_bruto.copy()
    df_cohort['cohort_mes'] = df_cohort['data'].dt.to_period('M')
    stats_dict['cohort_periodo'] = df_cohort.groupby('cohort_mes')['cliente_id'].nunique()
    
    # 33. RECOMENDAÇÃO DE AÇÕES
    recomendacoes = []
    if stats_dict['taxa_churn'] > 30:
        recomendacoes.append("🔴 ALERTA: Taxa de churn acima de 30%! Foco em retenção.")
    if stats_dict['taxa_dormentes'] > 20:
        recomendacoes.append("🟡 AVISO: Mais de 20% de clientes dormentes. Campanhas de reativação necessárias.")
    if stats_dict['crescimento_mom'] < 0:
        recomendacoes.append("📉 Vendas em queda MoM. Revisar estratégia.")
    if stats_dict['taxa_recorrencia'] > 50:
        recomendacoes.append("✅ Excelente! Mais de 50% de clientes recorrentes.")
    if len(recomendacoes) == 0:
        recomendacoes.append("✅ Dashboard operacional. Monitore continuamente.")
    
    stats_dict['recomendacoes'] = recomendacoes
    
    return stats_dict

# --- EXECUÇÃO DO DASHBOARD ---
if verificar_senha():
    # Barra Lateral - Tentar carregar logo com fallback
    logo_path = Path("logo_the_way.png")
    if logo_path.exists():
        st.sidebar.image(str(logo_path), width=100)
    else:
        st.sidebar.markdown("## 👕 The Way")
    
    st.sidebar.title("⚙️ Menu de Gestão")
    
    arquivo_upload = st.sidebar.file_uploader("1. Suba o arquivo Excel", type=['xlsx'])

    if arquivo_upload is not None:
        # Chamada da função com Cache
        df_bruto = carregar_dados(arquivo_upload)
        hoje = df_bruto['data'].max()

        # Filtro de Produtos
        st.sidebar.markdown("---")
        lista_produtos = sorted(df_bruto['produto'].unique().tolist())
        produtos_selecionados = st.sidebar.multiselect(
            "2. Filtre por Produto:",
            options=lista_produtos,
            default=lista_produtos
        )

        # Slider de Projeção
        dias_projecao = st.sidebar.slider("3. Horizonte de Projeção (dias):", 7, 90, 30)

        # Filtro de Data
        st.sidebar.markdown("---")
        data_inicio = st.sidebar.date_input("Data Inicial:", value=df_bruto['data'].min())
        data_fim = st.sidebar.date_input("Data Final:", value=df_bruto['data'].max())

        # Aplicando Filtros
        df = df_bruto[(df_bruto['produto'].isin(produtos_selecionados)) & 
                      (df_bruto['data'].dt.date >= data_inicio) & 
                      (df_bruto['data'].dt.date <= data_fim)]

        # Calcular todas as estatísticas
        stats = calcular_todas_estatisticas(df_bruto, df, hoje, dias_projecao)

        # --- INTERFACE VISUAL ---
        st.title("📊 Dashboard Estratégico - The Way (COMPLETO)")
        st.markdown(f"**Período:** {data_inicio} a {data_fim} | **Produtos:** {len(produtos_selecionados)}")

        # --- SEÇÃO 1: RECOMENDAÇÕES E ALERTAS ---
        st.markdown("---")
        st.subheader("🎯 Recomendações e Alertas")
        for rec in stats['recomendacoes']:
            st.info(rec)

        # --- SEÇÃO 2: KPIs PRINCIPAIS ---
        st.markdown("---")
        st.subheader("📈 KPIs Principais")
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("💰 Faturamento Total", f"R$ {stats['faturamento_total']:,.2f}")
        kpi2.metric("🛍️ Total de Vendas", f"{stats['total_vendas']} transações")
        kpi3.metric("👥 Clientes Únicos", f"{stats['total_clientes']}")
        kpi4.metric("📊 Ticket Médio", f"R$ {stats['ticket_medio']:,.2f}")

        kpi5, kpi6, kpi7, kpi8 = st.columns(4)
        kpi5.metric("💹 Crescimento MoM", f"{stats['crescimento_mom']:.1f}%", delta_color="inverse")
        kpi6.metric("🔄 Taxa Recorrência", f"{stats['taxa_recorrencia']:.1f}%")
        kpi7.metric("📉 Taxa Churn", f"{stats['taxa_churn']:.1f}%", delta_color="inverse")
        kpi8.metric("✅ Taxa Retenção", f"{stats['taxa_retencao']:.1f}%")

        kpi9, kpi10, kpi11, kpi12 = st.columns(4)
        kpi9.metric("⏳ Freq. Compra (dias)", f"{stats['freq_compra_dias']:.0f} dias")
        kpi10.metric("💎 Lifetime Value Med.", f"R$ {stats['ltv_medio']:,.2f}")
        kpi11.metric("😴 Clientes Dormentes", f"{stats['clientes_dormentes']} ({stats['taxa_dormentes']:.1f}%)")
        kpi12.metric("⚠️ Clientes em Risco", f"{stats['clientes_risco']}")

        kpi13, kpi14, kpi15, kpi16 = st.columns(4)
        kpi13.metric("🏆 Melhor Produto", stats['produto_mais_vendido'][:15])
        kpi14.metric("📦 Produto + Fraco", stats['produto_menos_vendido'][:15])
        kpi15.metric("🎯 Projeção 30d", f"R$ {stats['faturamento_projecao']:,.2f}")
        kpi16.metric("👑 Melhor Cliente", f"R$ {stats['valor_cliente_top']:,.2f}")

        # --- SEÇÃO 3: ANÁLISE DE PRODUTOS ---
        st.markdown("---")
        st.subheader("👕 Análise de Produtos")
        
        col_prod1, col_prod2 = st.columns(2)

        with col_prod1:
            st.markdown("**Ranking de Produtos (Curva ABC)**")
            st.dataframe(stats['curva_abc'][['produto', 'valor', 'Participação %', 'Cumulative %']], use_container_width=True)

        with col_prod2:
            st.markdown("**Top 5 Produtos Mais Frequentes**")
            fig_prod = px.bar(x=stats['produtos_frequentes'].values, 
                             y=stats['produtos_frequentes'].index,
                             orientation='h', color_discrete_sequence=['#000000'])
            fig_prod.update_layout(title="", xaxis_title="Quantidade", yaxis_title="Produto", height=300)
            st.plotly_chart(fig_prod, use_container_width=True)

        # --- SEÇÃO 4: ANÁLISE DE CLIENTES ---
        st.markdown("---")
        st.subheader("👥 Análise de Clientes")
        
        col_cli1, col_cli2 = st.columns(2)

        with col_cli1:
            st.markdown("**Segmentação de Clientes por Gasto**")
            seg_data = pd.DataFrame(stats['segmentacao_clientes']).reset_index()
            seg_data.columns = ['Segmento', 'Quantidade']
            fig_seg = px.pie(seg_data, values='Quantidade', names='Segmento', 
                            color_discrete_map={'Básico':'#cccccc', 'Standard':'#666666', 'Premium':'#000000'})
            st.plotly_chart(fig_seg, use_container_width=True)

        with col_cli2:
            st.markdown("**Top 5 Clientes (LTV)**")
            st.dataframe(stats['top_5_clientes'].rename(columns={'cliente_id': 'Cliente', 'valor': 'Total Gasto'}), use_container_width=True)

        # --- SEÇÃO 5: TENDÊNCIAS TEMPORAIS ---
        st.markdown("---")
        st.subheader("📅 Tendências Temporais")
        
        col_temp1, col_temp2 = st.columns(2)

        with col_temp1:
            st.markdown("**Sazonalidade Mensal**")
            fig_saz = px.line(x=stats['vendas_mensais'].index.astype(str), 
                             y=stats['vendas_mensais'].values, 
                             markers=True, color_discrete_sequence=['#000000'])
            fig_saz.update_layout(title="", xaxis_title="Mês", yaxis_title="Faturamento (R$)", height=350)
            st.plotly_chart(fig_saz, use_container_width=True)

        with col_temp2:
            st.markdown("**Vendas por Dia da Semana**")
            fig_dia = px.bar(x=stats['vendas_por_dia_semana'].index, 
                            y=stats['vendas_por_dia_semana'].values,
                            color_discrete_sequence=['#000000'])
            fig_dia.update_layout(title="", xaxis_title="Dia", yaxis_title="Faturamento (R$)", height=350)
            st.plotly_chart(fig_dia, use_container_width=True)

        # --- SEÇÃO 6: ANÁLISE ESTATÍSTICA ---
        st.markdown("---")
        st.subheader("📊 Análise Estatística de Vendas")
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)

        with col_stat1:
            st.markdown("**Distribuição de Valores**")
            col_s1, col_s2 = st.columns(2)
            col_s1.metric("Valor Mínimo", f"R$ {stats['valor_minimo']:.2f}")
            col_s2.metric("Valor Máximo", f"R$ {stats['valor_maximo']:.2f}")
            col_s1.metric("Mediana", f"R$ {stats['ticket_mediano']:.2f}")
            col_s2.metric("Desvio Padrão", f"R$ {stats['desvio_padrao']:.2f}")

        with col_stat2:
            st.markdown("**Percentis**")
            col_p1, col_p2 = st.columns(2)
            col_p1.metric("P25", f"R$ {stats['percentil_25']:.2f}")
            col_p2.metric("P50", f"R$ {stats['percentil_50']:.2f}")
            col_p1.metric("P75", f"R$ {stats['percentil_75']:.2f}")
            col_p2.metric("P90", f"R$ {stats['percentil_90']:.2f}")

        with col_stat3:
            st.markdown("**Variabilidade**")
            st.metric("Coef. Variação", f"{stats['coeficiente_variacao']:.1f}%")
            st.info(f"**Interpretação:** Vendas com {stats['coeficiente_variacao']:.1f}% de variabilidade")

        # --- SEÇÃO 7: MATRIZ RFM ---
        st.markdown("---")
        st.subheader("🎯 Análise RFM (Recency, Frequency, Monetary)")
        st.dataframe(stats['rfm'].head(10), use_container_width=True)
        st.caption("Recency: dias desde última compra | Frequency: total de compras | Monetary: valor total gasto")

        # --- SEÇÃO 8: ANÁLISE DE CHURN E RETENÇÃO ---
        st.markdown("---")
        st.subheader("🔴 Análise de Churn e Retenção")
        
        col_churn1, col_churn2 = st.columns(2)

        with col_churn1:
            status_counts = pd.DataFrame({
                'Status': ['Ativo', 'Risco', 'Dormente', 'Churn'],
                'Quantidade': [
                    len(df_bruto[df_bruto.groupby('cliente_id')['data'].transform('max') > (hoje - pd.Timedelta(days=30))]),
                    stats['clientes_risco'],
                    stats['clientes_dormentes'],
                    int(stats['taxa_churn'] / 100 * stats['total_clientes'])
                ]
            })
            fig_status = px.pie(status_counts, values='Quantidade', names='Status',
                               color_discrete_map={'Ativo':'#000000', 'Risco':'#ffcc00', 'Dormente':'#ff9900', 'Churn':'#cccccc'})
            st.plotly_chart(fig_status, use_container_width=True)

        with col_churn2:
            st.markdown("**Clientes Precisam de Ação**")
            col_c1, col_c2, col_c3 = st.columns(3)
            col_c1.metric("Em Risco", f"{stats['clientes_risco']}", "30-90 dias")
            col_c2.metric("Dormentes", f"{stats['clientes_dormentes']}", "90+ dias")
            col_c3.metric("Churn", f"{int(stats['taxa_churn'] / 100 * stats['total_clientes'])}", f"{stats['taxa_churn']:.1f}%")

        # --- SEÇÃO 9: EXPORTAÇÃO ---
        st.markdown("---")
        st.subheader("📥 Exportação de Dados")

        # Preparar dados para exportação
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Vendas Filtradas', index=False)
            stats['curva_abc'].to_excel(writer, sheet_name='Curva ABC', index=False)
            stats['top_5_clientes'].to_excel(writer, sheet_name='Top Clientes', index=False)
            stats['rfm'].to_excel(writer, sheet_name='Matriz RFM')

        col_export1, col_export2, col_export3 = st.columns(3)
        
        with col_export1:
            st.download_button(
                label="📥 Exportar Excel Completo",
                data=buffer.getvalue(),
                file_name=f"relatorio_theway_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel"
            )

        with col_export2:
            csv = df.to_csv(index=False)
            st.download_button(
                label="📄 Exportar CSV",
                data=csv,
                file_name=f"vendas_theway_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

        with col_export3:
            st.sidebar.markdown("---")
            if st.sidebar.button("🚪 Log out"):
                st.session_state["autenticado"] = False
                st.rerun()

        # Footer
        st.markdown("---")
        st.caption(f"Dashboard The Way - Atualizado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Data máxima dos dados: {hoje.strftime('%d/%m/%Y')}")

    else:
        st.info("⏳ Aguardando upload do arquivo Excel para gerar os insights completos.")
        st.markdown("### 📋 Formato esperado do Excel:")
        st.markdown("""
        | data | cliente_id | produto | valor |
        |------|-----------|---------|-------|
        | 01/02/2026 | C001 | Camiseta Branca P | 59,90 |
        | 02/02/2026 | C002 | Camiseta Preta M | 79,90 |
        """)
