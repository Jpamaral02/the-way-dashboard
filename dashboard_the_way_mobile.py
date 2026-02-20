import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io
from pathlib import Path
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DA PÁGINA (MOBILE FIRST) ---
st.set_page_config(
    page_title="The Way Mobile",
    layout="wide",
    page_icon="👕",
    initial_sidebar_state="collapsed"  # Sidebar colapsada por padrão em mobile
)

# --- CSS CUSTOMIZADO PARA MOBILE ---
st.markdown("""
<style>
    /* Ajustes para mobile */
    @media (max-width: 640px) {
        .main {
            padding: 0.5rem;
        }
        .metric-container {
            background-color: #f0f0f0;
            padding: 1rem;
            border-radius: 8px;
            margin: 0.5rem 0;
        }
        h1 { font-size: 1.5rem; }
        h2 { font-size: 1.2rem; }
        h3 { font-size: 1rem; }
    }
    
    /* Botões maior para mobile */
    button {
        min-height: 44px;
        font-size: 1rem;
    }
    
    /* Cards com melhor espaçamento */
    .stMetric {
        background-color: #f9f9f9;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #000000;
    }
    
    /* Abas móveis */
    .stTabs [role="tablist"] button {
        font-size: 0.85rem;
        padding: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

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
        st.title("🔐 The Way")
        st.subheader("Acesso Restrito")
        
        senha_digitada = st.text_input("Senha:", type="password", placeholder="Digite sua senha")
        
        if st.button("🔓 Entrar", use_container_width=True):
            if senha_digitada == SENHA_CORRETA:
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("❌ Senha incorreta!")
        return False
    return True

# --- FUNÇÕES DE CÁLCULO ---
def calcular_metricas_rapidas(df_bruto, df, hoje):
    """Calcula métricas principais de forma rápida"""
    
    metricas = {
        'faturamento': df['valor'].sum(),
        'total_vendas': len(df),
        'ticket_medio': df['valor'].mean(),
        'clientes': df['cliente_id'].nunique(),
        'produto_top': df.groupby('produto')['valor'].sum().idxmax(),
        'valor_top_produto': df.groupby('produto')['valor'].sum().max(),
    }
    
    # Churn simples
    ultima_visita = df_bruto.groupby('cliente_id')['data'].max()
    dias_parado = (hoje - ultima_visita).dt.days
    metricas['taxa_churn'] = (len(dias_parado[dias_parado > 180]) / len(dias_parado) * 100) if len(dias_parado) > 0 else 0
    
    # LTV
    ltv = df_bruto.groupby('cliente_id')['valor'].sum()
    metricas['ltv_medio'] = ltv.mean()
    metricas['cliente_top'] = ltv.idxmax()
    metricas['valor_cliente_top'] = ltv.max()
    
    # Top 5 produtos
    metricas['top_produtos'] = df.groupby('produto')['valor'].sum().nlargest(5)
    
    # Vendas por mês
    df_temp = df.copy()
    df_temp['mes'] = df_temp['data'].dt.to_period('M').astype(str)
    metricas['vendas_mes'] = df_temp.groupby('mes')['valor'].sum()
    
    return metricas

# --- EXECUÇÃO DO DASHBOARD ---
if verificar_senha():
    
    # Header Mobile
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("👕 The Way")
    with col2:
        if st.button("🚪", help="Sair"):
            st.session_state["autenticado"] = False
            st.rerun()
    
    # Upload de arquivo
    arquivo_upload = st.file_uploader(
        "📤 Suba seu Excel aqui",
        type=['xlsx'],
        help="Colunas necessárias: data, cliente_id, produto, valor"
    )

    if arquivo_upload is not None:
        df_bruto = carregar_dados(arquivo_upload)
        hoje = df_bruto['data'].max()

        # --- MENU COM ABAS MOBILE ---
        st.markdown("---")
        
        abas = st.tabs(["📊 Dashboard", "👕 Produtos", "👥 Clientes", "📈 Tendências", "⚙️ Filtros"])

        # --- ABA 1: DASHBOARD PRINCIPAL ---
        with abas[0]:
            st.subheader("Dashboard Principal")
            
            # Filtros rápidos (opcionais)
            if st.checkbox("Aplicar filtros?"):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    lista_produtos = sorted(df_bruto['produto'].unique().tolist())
                    produtos_selecionados = st.multiselect(
                        "Produtos:",
                        options=lista_produtos,
                        default=lista_produtos,
                        key="tab0_produtos"
                    )
                with col_f2:
                    dias_projecao = st.slider("Projeção (dias):", 7, 90, 30, key="tab0_dias")
                
                df = df_bruto[df_bruto['produto'].isin(produtos_selecionados)]
            else:
                df = df_bruto.copy()
                dias_projecao = 30

            metricas = calcular_metricas_rapidas(df_bruto, df, hoje)

            # KPIs em Stack (mobile-friendly)
            st.metric("💰 Faturamento", f"R$ {metricas['faturamento']:,.2f}")
            st.metric("🛍️ Vendas", f"{metricas['total_vendas']}")
            st.metric("👥 Clientes", f"{metricas['clientes']}")
            st.metric("📊 Ticket Médio", f"R$ {metricas['ticket_medio']:,.2f}")
            st.metric("💹 Churn", f"{metricas['taxa_churn']:.1f}%")
            st.metric("💎 LTV Médio", f"R$ {metricas['ltv_medio']:,.2f}")

            # Gráfico de Sazonalidade
            st.subheader("📈 Vendas Mensais")
            fig_saz = px.line(
                x=metricas['vendas_mes'].index.astype(str),
                y=metricas['vendas_mes'].values,
                markers=True,
                color_discrete_sequence=['#000000']
            )
            fig_saz.update_layout(
                title="",
                xaxis_title="Mês",
                yaxis_title="R$",
                height=300,
                margin=dict(l=40, r=20, t=20, b=40)
            )
            st.plotly_chart(fig_saz, use_container_width=True, config={'responsive': True})

        # --- ABA 2: PRODUTOS ---
        with abas[1]:
            st.subheader("👕 Análise de Produtos")
            
            # Filtro de produtos
            lista_produtos = sorted(df_bruto['produto'].unique().tolist())
            produtos_selecionados = st.multiselect(
                "Filtre produtos:",
                options=lista_produtos,
                default=lista_produtos,
                key="tab1_produtos"
            )
            
            df_prod = df_bruto[df_bruto['produto'].isin(produtos_selecionados)]
            
            # Top Produtos
            st.markdown("**Top 5 Produtos**")
            top_prod = df_prod.groupby('produto')['valor'].sum().nlargest(5).reset_index()
            
            for idx, row in top_prod.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{idx+1}. {row['produto']}")
                with col2:
                    st.write(f"R$ {row['valor']:,.0f}")
                st.progress(row['valor'] / top_prod['valor'].max())

            # Gráfico de Pizza
            st.markdown("**Distribuição de Vendas**")
            fig_pie = px.pie(
                top_prod,
                values='valor',
                names='produto',
                color_discrete_sequence=['#000000', '#333333', '#666666', '#999999', '#cccccc']
            )
            fig_pie.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_pie, use_container_width=True, config={'responsive': True})

        # --- ABA 3: CLIENTES ---
        with abas[2]:
            st.subheader("👥 Análise de Clientes")
            
            ltv_clientes = df_bruto.groupby('cliente_id')['valor'].sum().reset_index()
            ltv_clientes.columns = ['Cliente', 'Total Gasto']
            ltv_clientes = ltv_clientes.sort_values('Total Gasto', ascending=False)

            # Top 5 Clientes
            st.markdown("**Top 5 Clientes (LTV)**")
            for idx, row in ltv_clientes.head(5).iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"👤 {row['Cliente']}")
                with col2:
                    st.write(f"R$ {row['Total Gasto']:,.2f}")
                st.progress(row['Total Gasto'] / ltv_clientes['Total Gasto'].max())

            # Estatísticas de Clientes
            st.markdown("---")
            st.markdown("**Estatísticas Gerais**")
            col1, col2 = st.columns(2)
            
            with col1:
                total_clientes = df_bruto['cliente_id'].nunique()
                cliente_compras = df_bruto.groupby('cliente_id').size()
                recorrentes = len(cliente_compras[cliente_compras >= 2])
                st.metric("Total", total_clientes)
                st.metric("Recorrentes", recorrentes)
            
            with col2:
                st.metric("Taxa Recorrência", f"{(recorrentes/total_clientes*100):.1f}%")
                st.metric("Compra Média", f"{cliente_compras.mean():.1f}")

        # --- ABA 4: TENDÊNCIAS ---
        with abas[3]:
            st.subheader("📈 Tendências")
            
            lista_produtos = sorted(df_bruto['produto'].unique().tolist())
            produto_selecionado = st.selectbox("Selecione um produto:", lista_produtos, key="tab3_produto")
            
            df_trend = df_bruto[df_bruto['produto'] == produto_selecionado].copy()
            df_trend['data_dia'] = df_trend['data'].dt.date
            vendas_dia = df_trend.groupby('data_dia')['valor'].agg(['sum', 'count']).reset_index()
            vendas_dia.columns = ['Data', 'Faturamento', 'Quantidade']

            # Gráfico de Tendência
            fig_trend = px.bar(
                vendas_dia,
                x='Data',
                y='Faturamento',
                color_discrete_sequence=['#000000'],
                title=f"Vendas de {produto_selecionado}"
            )
            fig_trend.update_layout(
                height=300,
                margin=dict(l=40, r=20, t=40, b=40),
                xaxis_tickangle=-45
            )
            st.plotly_chart(fig_trend, use_container_width=True, config={'responsive': True})

            # Tabela resumida
            st.dataframe(vendas_dia, use_container_width=True)

        # --- ABA 5: FILTROS AVANÇADOS ---
        with abas[4]:
            st.subheader("⚙️ Filtros e Exportação")
            
            # Data Range
            col1, col2 = st.columns(2)
            with col1:
                data_inicio = st.date_input("Data Inicial:", value=df_bruto['data'].min())
            with col2:
                data_fim = st.date_input("Data Final:", value=df_bruto['data'].max())

            # Aplicar filtro
            df_filtrado = df_bruto[(df_bruto['data'].dt.date >= data_inicio) & 
                                   (df_bruto['data'].dt.date <= data_fim)]

            st.info(f"📊 {len(df_filtrado)} transações no período")

            # Exportar
            st.markdown("**Exportar Dados**")
            
            csv = df_filtrado.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"theway_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

            # Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_filtrado.to_excel(writer, sheet_name='Vendas', index=False)
            
            st.download_button(
                label="📊 Download Excel",
                data=buffer.getvalue(),
                file_name=f"theway_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )

        # Footer
        st.markdown("---")
        st.caption(f"The Way Mobile | {datetime.now().strftime('%d/%m/%Y')}")

    else:
        st.info("📤 Suba seu arquivo Excel para começar!")
