import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from supabase import create_client, Client
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# --- 1. SİTE KONFİGÜRASYONU VE VERİTABANI BAĞLANTISI ---
st.set_page_config(page_title="Vader Analiz Terminali", layout="wide", initial_sidebar_state="expanded")

if 'kullanici' not in st.session_state:
    st.session_state.kullanici = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

@st.cache_resource
def supabase_baglan():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        return None

supabase = supabase_baglan()

# --- 2. PROFESYONEL NAVİGASYON MENÜSÜ ---
st.sidebar.markdown(f"<h2 style='text-align: center; color: #00FFCC;'>🛸 VADER PRO</h2>", unsafe_allow_html=True)

if st.session_state.kullanici:
    st.sidebar.success(f"👤 Aktif Kullanıcı:\n{st.session_state.kullanici}")
    if st.sidebar.button("🚪 Çıkış Yap"):
        st.session_state.kullanici = None
        st.session_state.user_id = None
        st.rerun()

sayfa = st.sidebar.radio("SİTE MENÜSÜ", ["🏠 Ana Sayfa & Giriş", "📈 Canlı Analiz Terminali", "💼 Portföyüm & Takip", "📩 Hakkımda & İletişim"])

st.sidebar.markdown("---")
st.sidebar.info("📢 **Reklam Alanı**\nBuraya Google AdSense veya Sponsor ilanları yerleştirilebilir.")

ingilizce_turkce_sozluk = {
    "Total Revenue": "Toplam Gelir (Satışlar)", "Gross Profit": "Brüt Kar", "Net Income": "Net Kar",
    "Total Assets": "Toplam Varlıklar", "Total Liabilities Net Minority Interest": "Toplam Borçlar",
    "Stockholders Equity": "Özkaynaklar", "Cash And Cash Equivalents": "Nakit"
}

# --- 3. GÜÇLENDİRİLMİŞ VERİ MOTORLARI VE FİLTRELER ---

# GÜNCELLEME: Rakam Kısaltıcı Filtre (Büyük Sayıları Formatlar)
def rakam_formatla(deger):
    try:
        sayi = float(deger)
        if pd.isna(sayi): return "Veri Yok"
        if abs(sayi) >= 1_000_000_000:
            return f"₺{sayi / 1_000_000_000:,.2f} Mlr"
        elif abs(sayi) >= 1_000_000:
            return f"₺{sayi / 1_000_000:,.2f} Mly"
        else:
            return f"₺{sayi:,.2f}"
    except:
        return deger

@st.cache_data(ttl=300)
def veri_motoru(sembol, p="2y", i="1d"):
    h = yf.Ticker(sembol)
    try: df = h.history(period=p, interval=i)
    except: df = pd.DataFrame()
    
    try: df_endeks = yf.Ticker("XU100.IS").history(period=p, interval=i)
    except: df_endeks = pd.DataFrame()
    
    try:
        ham_gelir = h.financials
        gelir = ham_gelir[ham_gelir.index.isin(ingilizce_turkce_sozluk.keys())].rename(index=ingilizce_turkce_sozluk) if ham_gelir is not None else pd.DataFrame()
    except: gelir = pd.DataFrame()
        
    try:
        ham_bilanco = h.balance_sheet
        bilanco = ham_bilanco[ham_bilanco.index.isin(ingilizce_turkce_sozluk.keys())].rename(index=ingilizce_turkce_sozluk) if ham_bilanco is not None else pd.DataFrame()
    except: bilanco = pd.DataFrame()
    
    try: bilgi = h.info
    except: bilgi = {}
    
    return bilgi, df, df_endeks, gelir, bilanco

@st.cache_data(ttl=60)
def son_dakika_haberleri(sembol):
    haberler = []
    if ".IS" in sembol:
        try:
            arama_terimi = sembol.replace(".IS", "") + " hisse haber"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(arama_terimi)}&hl=tr&gl=TR&ceid=TR:tr"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            xml_data = urllib.request.urlopen(req).read()
            root = ET.fromstring(xml_data)
            
            for item in root.findall('./channel/item')[:5]:
                haberler.append({
                    'title': item.find('title').text,
                    'link': item.find('link').text,
                    'publisher': item.find('source').text if item.find('source') is not None else "Google Haberler",
                    'custom_time': item.find('pubDate').text
                })
            return haberler
        except: pass

    try:
        yh_news = yf.Ticker(sembol).news
        if yh_news:
            for h in yh_news:
                if 'title' in h and h['title']: 
                    haberler.append(h)
    except: pass
    return haberler[:5]

@st.cache_data(ttl=900)
def watchlist_verisi_getir(sembol):
    return yf.Ticker(sembol).history(period="5d")

def ai_bilanco_yorumu(bilgi):
    y = []
    fk, cari, marj = bilgi.get('trailingPE', 0), bilgi.get('currentRatio', 0), bilgi.get('profitMargins', 0)
    if fk and fk > 0: y.append("🟢 **Değerleme:** Şirketin F/K oranı düşük." if fk < 10 else ("🔴 **Değerleme:** F/K oranı yüksek." if fk > 25 else "🟡 **Değerleme:** F/K oranı sektör ortalamalarında."))
    if cari: y.append("🟢 **Borçluluk:** Kısa vadeli nakit durumu güçlü." if cari >= 1.5 else "🔴 **Borçluluk:** Nakit akışı ve borç ödeme kapasitesi sınırda.")
    if marj: y.append("🟢 **Karlılık:** Kar marjı sağlıklı (%15+)." if marj > 0.15 else "🔴 **Karlılık:** Kar marjı düşük.")
    return y if y else ["AI yorumu üretilemedi."]

def duygu_analizi(metin):
    m = str(metin).lower()
    p_k = ['artış', 'kâr', 'büyüme', 'anlaşma', 'yükseliş', 'pozitif', 'up', 'profit', 'growth', 'dividend', 'success']
    n_k = ['zarar', 'düşüş', 'ceza', 'risk', 'negatif', 'down', 'loss', 'penalty', 'debt', 'fail']
    p_s = sum(1 for k in p_k if k in m)
    n_s = sum(1 for k in n_k if k in m)
    if p_s > n_s: return "🟢 Pozitif Etki"
    elif n_s > p_s: return "🔴 Negatif Etki"
    else: return "⚪ Nötr Haber"

def footer_ekle():
    st.markdown("---")
    st.markdown(f"<p style='text-align: center; color: gray;'>Copyright © {datetime.now().year} Yunus Emre Eriş - Vader Analiz Terminali | Tüm Hakları Saklıdır.</p>", unsafe_allow_html=True)

# --- 4. SAYFA TASARIMLARI ---

if sayfa == "🏠 Ana Sayfa & Giriş":
    st.title("Vader Analiz Dünyasına Hoş Geldiniz")
    st.markdown("Borsa İstanbul analizi için geliştirilmiş en kapsamlı yerli terminal.")
    
    if supabase is None:
        st.error("Veritabanı bağlantısı kurulamadı. Lütfen Streamlit Secrets ayarlarını kontrol edin.")
    elif st.session_state.kullanici is None:
        col_login, col_reg = st.columns(2)
        with col_login:
            st.subheader("🔑 Üye Girişi")
            l_m = st.text_input("E-posta", key="log_mail")
            l_p = st.text_input("Şifre", type="password", key="log_pw")
            if st.button("Giriş Yap"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": l_m, "password": l_p})
                    st.session_state.kullanici, st.session_state.user_id = res.user.email, res.user.id
                    st.success("Başarılı!")
                    st.rerun()
                except: st.error("Giriş başarısız!")
        with col_reg:
            st.subheader("📝 Yeni Kayıt Ol")
            r_m = st.text_input("E-posta Adresi", key="reg_mail")
            r_p = st.text_input("Yeni Şifre", type="password", key="reg_pw")
            if st.button("Üyeliği Tamamla"):
                try:
                    supabase.auth.sign_up({"email": r_m, "password": r_p})
                    st.success("Kayıt başarılı!")
                except: st.error("Kayıt hatası.")
    else:
        st.success(f"Giriş yapıldı: **{st.session_state.kullanici}**")
    footer_ekle()

elif sayfa == "📈 Canlı Analiz Terminali":
    hisse_kod = st.sidebar.text_input("Analiz Edilecek Hisse (Örn: THYAO):", "THYAO").upper()
    sembol = hisse_kod + ".IS"
    zaman_secimi = st.sidebar.selectbox("Grafik Zaman Dilimi:", ["Günlük (Son 2 Yıl)", "Saatlik (Son 1 Ay)", "15 Dakikalık (Son 5 Gün)", "5 Dakikalık (Son 5 Gün)", "1 Dakikalık (Son 1 Gün)"])
    
    if zaman_secimi == "Günlük (Son 2 Yıl)": p, i = "2y", "1d"
    elif zaman_secimi == "Saatlik (Son 1 Ay)": p, i = "1mo", "1h"
    elif zaman_secimi == "15 Dakikalık (Son 5 Gün)": p, i = "5d", "15m"
    elif zaman_secimi == "5 Dakikalık (Son 5 Gün)": p, i = "5d", "5m"
    elif zaman_secimi == "1 Dakikalık (Son 1 Gün)": p, i = "1d", "1m"

    studyo = st.sidebar.checkbox("YouTube Stüdyo Modu")
    tema = "plotly_dark"
    renk = '#00FFCC' if studyo else 'lime'
    
    if studyo: st.markdown("<style>h1, h2 { color: #00FFCC !important; }</style>", unsafe_allow_html=True)

    try:
        bilgi, df, df_e, gelir, bilanco = veri_motoru(sembol, p, i)
        haberler = son_dakika_haberleri(sembol)
        
        if not df.empty:
            fiyat = bilgi.get('currentPrice', df['Close'].iloc[-1])
            onceki = bilgi.get('previousClose', df['Close'].iloc[-2] if len(df)>1 else fiyat)
            degisim = fiyat - onceki
            yuzde = (degisim / onceki) * 100 if onceki > 0 else 0
            
            st.header(f"⚡ {bilgi.get('longName', hisse_kod)}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Anlık Fiyat", f"₺{fiyat:,.2f}", f"{degisim:+.2f} TL ({yuzde:+.2f}%)")
            m2.metric("Günlük Hacim", f"{bilgi.get('volume', int(df['Volume'].iloc[-1])):,}")
            m3.metric("F/K Oranı", round(bilgi.get('trailingPE', 0), 2) if bilgi.get('trailingPE') else "N/A")
            m4.metric("Piyasa Değeri", f"₺{bilgi.get('marketCap', 0):,}")

            t1, t2, t3, t4, t5, t6 = st.tabs(["📈 Grafikler", "⚙️ Robot", "🤖 AI Yorum", "🎯 Tahmin", "📰 Haberler", "📑 Finansallar"])
            
            with t1:
                goster_bollinger = st.checkbox("Bollinger Bantları")
                goster_rsi = st.checkbox("RSI")
                goster_macd = st.checkbox("MACD")
                
                if goster_bollinger:
                    df['SMA20_B'] = df['Close'].rolling(20).mean()
                    df['STD20_B'] = df['Close'].rolling(20).std()
                    df['Upper'], df['Lower'] = df['SMA20_B'] + (df['STD20_B'] * 2), df['SMA20_B'] - (df['STD20_B'] * 2)

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color=renk if degisim >= 0 else 'red', width=2), name='Fiyat'))
                if goster_bollinger:
                    fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='gray', width=1, dash='dash'), name='Üst Bant'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='gray', width=1, dash='dash'), name='Alt Bant', fill='tonexty', fillcolor='rgba(128,128,128,0.1)'))
                fig.update_layout(title=f"Ana Grafik ({zaman_secimi})", template=tema, height=450, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
                
                if goster_rsi:
                    d = df['Close'].diff()
                    rs = (d.where(d > 0, 0)).rolling(14).mean() / (-d.where(d < 0, 0)).rolling(14).mean()
                    df['RSI'] = 100 - (100 / (1 + rs))
                    fig_rsi = go.Figure(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='orange')))
                    fig_rsi.add_hline(y=70, line_dash="dot", line_color="red")
                    fig_rsi.add_hline(y=30, line_dash="dot", line_color="green")
                    fig_rsi.update_layout(title="RSI", template=tema, height=250)
                    st.plotly_chart(fig_rsi, use_container_width=True)

                if goster_macd:
                    df['MACD'] = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()
                    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                    fig_macd = go.Figure()
                    fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='blue'), name='MACD'))
                    fig_macd.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='orange'), name='Sinyal'))
                    fig_macd.add_bar(x=df.index, y=df['MACD'] - df['Signal'], name='Hist')
                    fig_macd.update_layout(title="MACD", template=tema, height=250)
                    st.plotly_chart(fig_macd, use_container_width=True)

            with t2:
                df['SMA20'], df['SMA50'] = df['Close'].rolling(20).mean(), df['Close'].rolling(50).mean()
                df['Pozisyon'] = np.where(df['SMA20'] > df['SMA50'], 1, 0)
                df['Pozisyon'] = df['Pozisyon'].diff()
                
                fig3 = go.Figure()
                fig3.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='gray', width=1), name='Fiyat'))
                fig3.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange', width=1.5), name='SMA 20'))
                fig3.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='blue', width=1.5), name='SMA 50'))
                
                al, sat = df[df['Pozisyon'] == 1], df[df['Pozisyon'] == -1]
                fig3.add_trace(go.Scatter(x=al.index, y=al['SMA20'], mode='markers', marker=dict(color='green', size=10, symbol='triangle-up'), name='AL'))
                fig3.add_trace(go.Scatter(x=sat.index, y=sat['SMA50'], mode='markers', marker=dict(color='red', size=10, symbol='triangle-down'), name='SAT'))
                fig3.update_layout(template=tema, height=500)
                st.plotly_chart(fig3, use_container_width=True)

            with t3:
                for y in ai_bilanco_yorumu(bilgi): st.write(y)
                c1, c2, c3 = st.columns(3)
                c1.metric("PD/DD", round(bilgi.get('priceToBook', 0), 2) if bilgi.get('priceToBook') else "Yok")
                c2.metric("ROE", f"%{round(bilgi.get('returnOnEquity', 0)*100, 2)}" if bilgi.get('returnOnEquity') else "Yok")
                c3.metric("Cari Oran", round(bilgi.get('currentRatio', 0), 2) if bilgi.get('currentRatio') else "Yok")

            with t4:
                log_r = np.log(1 + df['Close'].pct_change())
                u, var, std = log_r.mean(), log_r.var(), log_r.std()
                drift = u - (0.5 * var)
                np.random.seed(int(fiyat * 100))
                t_g = np.exp(drift + std * np.random.standard_normal(30))
                t_f = np.zeros_like(t_g)
                t_f[0] = fiyat
                for t in range(1, 30): t_f[t] = t_f[t - 1] * t_g[t]
                np.random.seed()
                
                g_t = pd.date_range(start=df.index[-1], periods=30)
                fig_mc = go.Figure()
                fig_mc.add_trace(go.Scatter(x=df.index[-60:], y=df['Close'].iloc[-60:], line=dict(color='gray'), name='Geçmiş'))
                fig_mc.add_trace(go.Scatter(x=g_t, y=t_f, line=dict(color='#00FFCC', dash='dot'), name='Tahmin'))
                fig_mc.update_layout(template=tema, height=350)
                st.plotly_chart(fig_mc, use_container_width=True)
                
                eps = bilgi.get('trailingEps', 0)
                b_b = st.slider("Tahmini Büyüme (%):", 1, 50, 15)
                if eps > 0: st.info(f"Graham Ederi: **₺{eps * (8.5 + (2 * b_b)):,.2f}**")
                
                yat = st.slider("1 Yıl Önce Yatırsaydım:", 1000, 1000000, 10000, 1000)
                g_f = df['Close'].iloc[-252] if len(df) >= 252 else df['Close'].iloc[0]
                st.success(f"Bugünkü Değer: **₺{(yat / g_f) * fiyat:,.2f}**")

            with t5:
                if haberler:
                    for h in haberler[:5]:
                        b = h.get('title', 'Başlık Yok')
                        y_v = h.get('custom_time', datetime.fromtimestamp(h.get('providerPublishTime', 0)).strftime('%d.%m.%Y %H:%M') if h.get('providerPublishTime') else "Zaman Bilinmiyor")
                        with st.expander(f"{duygu_analizi(b)} | {b}"):
                            st.write(f"**Kaynak:** {h.get('publisher', 'Bilinmeyen')} | **Tarih:** {y_v}")
                            st.write(f"[Haberi Oku]({h.get('link', '#')})")
                else: st.info("Haber bulunamadı.")

            with t6:
                if not bilanco.empty:
                    bilanco.columns = [str(c).split()[0] for c in bilanco.columns]
                    # GÜNCELLEME: Pandas dataframe'indeki tüm rakamları kısaltıcı filtreye sokuyoruz
                    formatli_bilanco = bilanco.applymap(rakam_formatla)
                    st.dataframe(formatli_bilanco, use_container_width=True)
                else: st.info("Veri yok.")
        else: st.error("Hisse verisi çekilemedi.")
    except Exception as e: st.error(f"Hata: {e}")
    footer_ekle()

elif sayfa == "💼 Portföyüm & Takip":
    st.title("💼 Bulut Portföy")
    if st.session_state.kullanici is None: st.warning("Giriş yapın.")
    else:
        with st.expander("➕ Hisse Ekle", expanded=True):
            with st.form("h_e"):
                y_k, y_m, y_l = st.text_input("Kod:").upper(), st.number_input("Maliyet:", min_value=0.0), st.number_input("Lot:", min_value=1)
                if st.form_submit_button("Kaydet") and y_k:
                    supabase.table("portfoyler").insert({"user_id": st.session_state.user_id, "hisse_kod": y_k, "maliyet": y_m, "lot": y_l}).execute()
                    st.rerun()

        st.subheader("📊 Varlıklarım")
        v = supabase.table("portfoyler").select("*").eq("user_id", st.session_state.user_id).execute()
        if v.data:
            for r in v.data:
                try:
                    a_f = watchlist_verisi_getir(r['hisse_kod'] + ".IS")['Close'].iloc[-1]
                    k = (a_f - r['maliyet']) * r['lot']
                    c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 2.5, 1])
                    c1.write(f"**{r['hisse_kod']}**")
                    c2.write(f"Maliyet: ₺{r['maliyet']:,.2f}")
                    c3.write(f"Lot: {r['lot']}")
                    c4.metric("Güncel Değer", f"₺{a_f * r['lot']:,.2f}", f"₺{k:,.2f}")
                    if c5.button("Sil", key=f"d_{r['id']}"):
                        supabase.table("portfoyler").delete().eq("id", r['id']).execute()
                        st.rerun()
                except: pass
        else: st.info("Portföy boş.")
        
        st.markdown("---")
        st.subheader("📋 İzleme Listesi")
        f = st.text_input("Hisseler (Virgülle ayırın):", "SASA, EREGL").upper().split(",")
        c = st.columns(len(f) if f else 1)
        for i, s in enumerate(f):
            try:
                d = watchlist_verisi_getir(s.strip() + ".IS")
                c[i % len(c)].metric(s.strip(), f"₺{d['Close'].iloc[-1]:,.2f}", f"{(d['Close'].iloc[-1]-d['Close'].iloc[-2])/d['Close'].iloc[-2]*100:+.2f}%")
            except: pass
    footer_ekle()

elif sayfa == "📩 Hakkımda & İletişim":
    st.title("👨‍💻 Geliştirici")
    st.markdown("""**Vader Analiz Terminali**, Uludağ Üniversitesi İİBF öğrencisi **Yunus Emre Eriş** tarafından geliştirilmiştir.\n\n**İletişim:** yunusemreeris787@gmail.com""")
    footer_ekle()
