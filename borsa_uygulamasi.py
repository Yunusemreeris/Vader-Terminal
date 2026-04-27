import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from supabase import create_client, Client

# --- 1. SİTE KONFİGÜRASYONU VE ELİT CSS ---
st.set_page_config(page_title="Vader Analiz Terminali", layout="wide", initial_sidebar_state="expanded")

def inject_custom_css():
    st.markdown("""
        <style>
        [data-testid="stAppViewContainer"] { background-color: #0e1117; }
        .main { font-family: 'Inter', sans-serif; }
        [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
        div[data-testid="metric-container"] {
            background-color: #1c2128; border: 1px solid #30363d; padding: 15px; border-radius: 12px;
        }
        h1, h2, h3 { color: #00f2ff !important; }
        .stButton>button { border-radius: 8px; background-color: #238636; color: white; border: none; }
        .stButton>button:hover { background-color: #2ea043; box-shadow: 0 0 15px #2ea043; }
        .stTabs [aria-selected="true"] { background-color: #00f2ff !important; color: #0e1117 !important; }
        </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- 2. VERİTABANI VE OTURUM ---
if 'kullanici' not in st.session_state: st.session_state.kullanici = None
if 'user_id' not in st.session_state: st.session_state.user_id = None

@st.cache_resource
def supabase_baglan():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = supabase_baglan()

# --- 3. NAVİGASYON ---
with st.sidebar:
    st.markdown(f"<h1 style='text-align: center; color: #00f2ff;'>🛸 VADER</h1>", unsafe_allow_html=True)
    if st.session_state.kullanici:
        st.markdown(f"---")
        st.success(f"👤 **{st.session_state.kullanici}**")
        if st.button("Çıkış Yap"):
            st.session_state.kullanici = None
            st.session_state.user_id = None
            st.rerun()
    st.markdown("---")
    sayfa = st.radio("MENÜ", ["🏠 Ana Sayfa", "📈 Analiz Terminali", "💼 Bulut Portföyüm", "📩 İletişim"])

# --- 4. MOTORLAR (ANTI-BAN & ANALİZ) ---
@st.cache_data(ttl=900)
def veri_motoru(sembol):
    h = yf.Ticker(sembol)
    try:
        df = h.history(period="2y")
        bilgi = h.info
        gelir = h.financials
        bilanco = h.balance_sheet
        haberler = h.news
        return bilgi, df, gelir, bilanco, haberler
    except: return {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), []

def ai_bilanco_yorumu(bilgi):
    y = []
    fk, cari, marj = bilgi.get('trailingPE', 0), bilgi.get('currentRatio', 0), bilgi.get('profitMargins', 0)
    if fk: y.append("🟢 F/K Düşük: İskontolu." if fk < 12 else "🔴 F/K Yüksek.")
    if cari: y.append("🟢 Likidite Güçlü." if cari >= 1.5 else "🔴 Borç Riski.")
    return y

def duygu_analizi(metin):
    m = str(metin).lower()
    if any(k in m for k in ['artış', 'kâr', 'büyüme', 'pozitif']): return "🟢 Pozitif"
    if any(k in m for k in ['zarar', 'düşüş', 'risk', 'negatif']): return "🔴 Negatif"
    return "⚪ Nötr"

# --- 5. SAYFALAR ---

if sayfa == "🏠 Ana Sayfa":
    st.title("Vader Finansal Terminal")
    if st.session_state.kullanici is None:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🔑 Giriş")
            m = st.text_input("E-posta")
            p = st.text_input("Şifre", type="password")
            if st.button("GİRİŞ YAP"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": m, "password": p})
                    st.session_state.kullanici, st.session_state.user_id = res.user.email, res.user.id
                    st.rerun()
                except: st.error("Hatalı giriş.")
        with c2:
            st.subheader("📝 Kayıt")
            rm = st.text_input("Yeni E-posta")
            rp = st.text_input("Yeni Şifre")
            if st.button("KAYIT OL"):
                try:
                    supabase.auth.sign_up({"email": rm, "password": rp})
                    st.success("Kayıt başarılı!")
                except: st.error("Hata oluştu.")
    else:
        st.success(f"Hoş geldin {st.session_state.kullanici}. Terminal aktif.")

elif sayfa == "📈 Analiz Terminali":
    h_k = st.sidebar.text_input("Hisse:", "THYAO").upper()
    try:
        bilgi, df, gelir, bilanco, haberler = veri_motoru(h_k + ".IS")
        f = bilgi.get('currentPrice', df['Close'].iloc[-1])
        st.header(f"⚡ {bilgi.get('longName', h_k)}")
        
        # Metrikler
        m1, m2, m3 = st.columns(3)
        m1.metric("Anlık", f"₺{f:,.2f}")
        m2.metric("F/K", round(bilgi.get('trailingPE', 0), 2) if bilgi.get('trailingPE') else "N/A")
        m3.metric("Piyasa Değeri", f"₺{bilgi.get('marketCap', 0):,}")

        t1, t2, t3, t4, t5 = st.tabs(["📊 Grafikler", "⚙️ Teknik İndikatörler", "🤖 AI & Tahmin", "📰 Haberler", "📑 Finansallar"])
        
        with t1:
            fig = go.Figure(data=[go.Scatter(x=df.index, y=df['Close'], line=dict(color='#00f2ff'), fill='tozeroy')])
            fig.update_layout(template="plotly_dark", title="Fiyat Grafiği")
            st.plotly_chart(fig, use_container_width=True)

        with t2:
            st.subheader("📐 Teknik Göstergeler")
            # RSI, MACD, Bollinger Hesaplamaları
            df['SMA20'] = df['Close'].rolling(20).mean()
            df['STD20'] = df['Close'].rolling(20).std()
            df['Upper'] = df['SMA20'] + (df['STD20'] * 2)
            df['Lower'] = df['SMA20'] - (df['STD20'] * 2)
            
            fig_ind = go.Figure()
            fig_ind.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Fiyat', opacity=0.5))
            fig_ind.add_trace(go.Scatter(x=df.index, y=df['Upper'], name='Üst Bant', line=dict(dash='dash')))
            fig_ind.add_trace(go.Scatter(x=df.index, y=df['Lower'], name='Alt Bant', line=dict(dash='dash')))
            fig_ind.update_layout(template="plotly_dark")
            st.plotly_chart(fig_ind, use_container_width=True)

        with t3:
            st.subheader("🔮 30 Günlük Monte Carlo Simülasyonu")
            returns = df['Close'].pct_change()
            last_price = df['Close'].iloc[-1]
            sim_returns = np.random.normal(returns.mean(), returns.std(), 30)
            sim_prices = last_price * (1 + sim_returns).cumprod()
            fig_sim = go.Figure(go.Scatter(y=sim_prices, line=dict(color='#ff00ff', dash='dot')))
            fig_sim.update_layout(template="plotly_dark", title="AI Fiyat Projeksiyonu")
            st.plotly_chart(fig_sim, use_container_width=True)
            for r in ai_bilanco_yorumu(bilgi): st.write(r)

        with t4:
            for h in haberler[:5]:
                st.write(f"{duygu_analizi(h['title'])} | **{h['title']}**")
                st.caption(f"[Kaynağa Git]({h['link']})")

        with t5:
            st.dataframe(bilanco, use_container_width=True)

    except Exception as e: st.error(f"Hata: {e}")

elif sayfa == "💼 Bulut Portföyüm":
    st.title("💼 Portföy Yönetimi")
    if st.session_state.kullanici:
        with st.form("ekle"):
            c1, c2, c3 = st.columns(3)
            k = c1.text_input("Hisse:").upper()
            m = c2.number_input("Maliyet:")
            l = c3.number_input("Lot:", min_value=1)
            if st.form_submit_button("KAYDET"):
                supabase.table("portfoyler").insert({"user_id": st.session_state.user_id, "hisse_kod": k, "maliyet": m, "lot": l}).execute()
                st.rerun()
        
        v = supabase.table("portfoyler").select("*").eq("user_id", st.session_state.user_id).execute()
        for r in v.data:
            col1, col2 = st.columns([4,1])
            col1.write(f"**{r['hisse_kod']}** | Maliyet: {r['maliyet']} | Lot: {r['lot']}")
            if col2.button("Sil", key=f"s_{r['id']}"):
                supabase.table("portfoyler").delete().eq("id", r['id']).execute()
                st.rerun()
    else: st.warning("Giriş yapmalısınız.")

elif sayfa == "📩 İletişim":
    st.title("Geliştirici: Yunus Emre Eriş")
    st.write("E-posta: yunusemreeris787@gmail.com")
