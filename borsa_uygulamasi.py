import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client, Client
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import extra_streamlit_components as stx
import time
import base64
import streamlit.components.v1 as components

# --- 1. SİTE KONFİGÜRASYONU VE GÜVENLİK KALKANI ---
st.set_page_config(page_title="Vader Analiz Terminali", layout="wide", initial_sidebar_state="expanded")

# Akıllı Gizleme Kalkanı (Menü açma tuşunu bozmaz, sadece sağ üstü temizler)
gizleme_kodu = """
            <style>
            #MainMenu {visibility: hidden !important;}
            footer {visibility: hidden !important;}
            header [data-testid="stToolbar"] {display: none !important;}
            .stDeployButton {display: none !important;}
            </style>
            """
st.markdown(gizleme_kodu, unsafe_allow_html=True)

# --- 2. SUPABASE BAĞLANTISI ---
@st.cache_resource
def supabase_baglan():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception: return None

supabase = supabase_baglan()

# --- 3. KUSURSUZ ÇEREZ VE PROFİL MOTORU ---
cookie_manager = stx.CookieManager(key="vader_master_pro")

if 'kullanici' not in st.session_state: st.session_state.kullanici = None
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'uyelik_tipi' not in st.session_state: st.session_state.uyelik_tipi = "free"

tum_cerezler = cookie_manager.get_all()

if tum_cerezler is not None and st.session_state.kullanici is None:
    k_mail = tum_cerezler.get("vader_mail")
    k_id = tum_cerezler.get("vader_id")
    if k_mail:
        st.session_state.kullanici = k_mail
        st.session_state.user_id = k_id
        try:
            rol = supabase.table("kullanici_profilleri").select("uyelik_tipi").eq("user_id", k_id).execute()
            st.session_state.uyelik_tipi = rol.data[0]['uyelik_tipi'] if rol.data else "free"
        except: pass
        st.rerun()

is_premium = True if (st.session_state.uyelik_tipi == "premium" or st.session_state.kullanici == "erisyunusemre985@gmail.com") else False

# --- 4. YARDIMCI FONKSİYONLAR ---
ingilizce_turkce_sozluk = {
    "Total Revenue": "Toplam Gelir (Satışlar)", "Operating Revenue": "Faaliyet Geliri",
    "Gross Profit": "Brüt Kar", "Net Income": "Net Kar", "Total Assets": "Toplam Varlıklar", 
    "Current Assets": "Dönen Varlıklar", "Total Non Current Assets": "Duran Varlıklar",
    "Total Liabilities Net Minority Interest": "Toplam Borçlar", "Current Liabilities": "Kısa Vadeli Borçlar",
    "Total Non Current Liabilities Net Minority Interest": "Uzun Vadeli Borçlar", "Total Debt": "Toplam Finansal Borç",
    "Stockholders Equity": "Özkaynaklar", "Cash And Cash Equivalents": "Nakit", "Inventory": "Stoklar"
}

def rakam_formatla(deger):
    try:
        sayi = float(deger)
        if pd.isna(sayi): return "Veri Yok"
        if abs(sayi) >= 1_000_000_000: return f"{sayi / 1_000_000_000:,.2f} Mlr"
        elif abs(sayi) >= 1_000_000: return f"{sayi / 1_000_000:,.2f} Mly"
        else: return f"{sayi:,.2f}"
    except: return deger

@st.cache_data(ttl=300)
def veri_motoru(sembol, p="2y", i="1d"):
    h = yf.Ticker(sembol)
    try: df = h.history(period=p, interval=i)
    except: df = pd.DataFrame()
    try: info = h.info
    except: info = {}
    try:
        ham_gelir = h.financials
        gelir = ham_gelir[ham_gelir.index.isin(ingilizce_turkce_sozluk.keys())].rename(index=ingilizce_turkce_sozluk) if ham_gelir is not None else pd.DataFrame()
    except: gelir = pd.DataFrame()
    try:
        ham_bilanco = h.balance_sheet
        bilanco = ham_bilanco[ham_bilanco.index.isin(ingilizce_turkce_sozluk.keys())].rename(index=ingilizce_turkce_sozluk) if ham_bilanco is not None else pd.DataFrame()
    except: bilanco = pd.DataFrame()
    try:
        ham_ceyrek = h.quarterly_balance_sheet
        ceyreklik_bilanco = ham_ceyrek[ham_ceyrek.index.isin(ingilizce_turkce_sozluk.keys())].rename(index=ingilizce_turkce_sozluk) if ham_ceyrek is not None else pd.DataFrame()
    except: ceyreklik_bilanco = pd.DataFrame()
    return df, info, gelir, bilanco, ceyreklik_bilanco

@st.cache_data(ttl=1800)
def piyasa_alarmlari():
    alarmlar = []
    demirbaslar = ["THYAO.IS", "BTC-USD", "GC=F", "AAPL"]
    for s in demirbaslar:
        try:
            d = yf.Ticker(s).history(period="10d")
            if len(d) >= 2:
                deg = ((d['Close'].iloc[-1] - d['Close'].iloc[-2]) / d['Close'].iloc[-2]) * 100
                if deg <= -3.0: alarmlar.append(f"🚨 {s} %{abs(deg):.1f} düştü! Fırsat olabilir.")
                elif deg >= 3.0: alarmlar.append(f"🚀 {s} %{deg:.1f} yükseldi!")
        except: pass
    return alarmlar if alarmlar else ["Piyasa şu an sakin, olağanüstü bir hareket yok."]

@st.cache_data(ttl=30) 
def son_dakika_haberleri(sembol):
    haberler = []
    if ".IS" in sembol:
        try:
            arama_terimi = sembol.replace(".IS", "") + " hisse haber when:1d"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(arama_terimi)}&hl=tr&gl=TR&ceid=TR:tr"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            xml_data = urllib.request.urlopen(req).read()
            root = ET.fromstring(xml_data)
            
            for item in root.findall('./channel/item')[:8]: 
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
                if 'title' in h and h['title']: haberler.append(h)
    except: pass
    
    return haberler[:8]

def duygu_analizi(metin):
    metin = str(metin).lower()
    poz_skor = sum(1 for k in ['artış', 'kâr', 'büyüme', 'anlaşma', 'yükseliş', 'pozitif', 'up'] if k in metin)
    neg_skor = sum(1 for k in ['zarar', 'düşüş', 'ceza', 'risk', 'negatif', 'down'] if k in metin)
    if poz_skor > neg_skor: return "🟢 Pozitif Etki"
    elif neg_skor > poz_skor: return "🔴 Negatif Etki"
    else: return "⚪ Nötr Haber"

def rapor_olustur_html(hisse, fiyat, degisim_yuzde, rsi, yorumlar):
    renk = "#00FFCC" if degisim_yuzde >= 0 else "#FF4B4B"
    html_icerik = f"""
    <html><head><meta charset="utf-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1E1E1E; color: #FFFFFF; padding: 40px; }}
        h1 {{ color: #00FFCC; border-bottom: 2px solid #00FFCC; padding-bottom: 10px; }}
        .kutu {{ background-color: #2D2D2D; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
        .metrik {{ font-size: 24px; font-weight: bold; color: {renk}; }}
        .footer {{ margin-top: 50px; text-align: center; font-size: 12px; color: #888; }}
    </style></head><body>
        <h1>🛸 VADER PRO - Teknik Analiz Raporu</h1>
        <div class="kutu">
            <h2>Varlık: {hisse}</h2>
            <p>Rapor Tarihi: {datetime.now().strftime("%d.%m.%Y %H:%M")}</p>
            <p>Anlık Fiyat: <span class="metrik">{fiyat:,.2f} ({degisim_yuzde:+.2f}%)</span></p>
            <p>Teknik RSI (Göreceli Güç Endeksi): <b>{rsi:.2f}</b></p>
        </div>
        <div class="kutu">
            <h2>🧠 Vader AI Algoritmik Yorumu</h2>
            <ul>{''.join([f'<li>{y}</li>' for y in yorumlar])}</ul>
        </div>
        <div class="footer">Bu belge Vader Analiz Terminali (Yunus Emre Eriş) tarafından otomatik üretilmiştir. Tarayıcınızda Ctrl+P yaparak PDF olarak kaydedebilirsiniz.</div>
    </body></html>
    """
    b64 = base64.b64encode(html_icerik.encode()).decode()
    return f'<a href="data:text/html;base64,{b64}" download="VADER_Rapor_{hisse}.html" style="background-color:#00FFCC; color:black; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold;">📄 Raporu İndir (HTML/PDF)</a>'

def ai_teknik_yorum(df, rsi, macd, signal):
    yorumlar = []
    fiyat = df['Close'].iloc[-1]
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    sma50 = df['Close'].rolling(50).mean().iloc[-1]

    if fiyat > sma20 and fiyat > sma50: yorumlar.append("🟢 **Trend Analizi:** Fiyat, hem 20 hem de 50 günlük hareketli ortalamalarının üzerinde. Güçlü bir Yükseliş Trendi (Boğa) hakim.")
    elif fiyat < sma20 and fiyat < sma50: yorumlar.append("🔴 **Trend Analizi:** Fiyat ortalamaların altında eziliyor. Güçlü bir Düşüş Trendi (Ayı) var.")
    else: yorumlar.append("🟡 **Trend Analizi:** Fiyat ortalamalar arasında sıkışmış. Yön arayışı sürüyor (Konsolidasyon).")

    if rsi > 70: yorumlar.append("🔴 **Momentum (RSI):** RSI 70'in üzerinde (Aşırı Alım). Piyasada FOMO var, düzeltme gelebilir.")
    elif rsi < 30: yorumlar.append("🟢 **Momentum (RSI):** RSI 30'un altında (Aşırı Satım). Panik satışı olmuş, tepki fırsatı olabilir.")
    else: yorumlar.append("⚪ **Momentum (RSI):** RSI dengeli bir bölgede ilerliyor.")

    if macd > signal: yorumlar.append("🟢 **İvme (MACD):** MACD sinyal çizgisini yukarı kesmiş, pozitif ivme var.")
    else: yorumlar.append("🔴 **İvme (MACD):** MACD sinyal çizgisinin altında, satış baskısı devam ediyor.")
    return yorumlar

def footer_ekle():
    st.markdown("---")
    st.markdown(f"<p style='text-align: center; color: gray;'>Copyright © {datetime.now().year} Yunus Emre Eriş - Vader Analiz Terminali | Tüm Hakları Saklıdır.</p>", unsafe_allow_html=True)

# --- 5. PROFESYONEL NAVİGASYON MENÜSÜ ---
st.sidebar.markdown(f"<h2 style='text-align: center; color: #00FFCC;'>🛸 VADER PRO</h2>", unsafe_allow_html=True)

if st.session_state.kullanici:
    if st.session_state.kullanici == "erisyunusemre985@gmail.com":
        st.sidebar.success(f"👑 KURUCU / ADMİN:\n{st.session_state.kullanici}")
    elif is_premium:
        st.sidebar.warning(f"💎 PREMIUM ÜYE:\n{st.session_state.kullanici}")
    else:
        st.sidebar.info(f"👤 Ücretsiz Kullanıcı:\n{st.session_state.kullanici}")
        
    if st.sidebar.button("🚪 Çıkış Yap"):
        try:
            cookie_manager.delete("vader_mail", key="cikis_1")
            cookie_manager.delete("vader_id", key="cikis_2")
        except: pass
        st.session_state.kullanici = None
        st.session_state.user_id = None
        st.session_state.uyelik_tipi = "free"
        
        time.sleep(1.5)
        st.rerun()

sayfa = st.sidebar.radio("SİTE MENÜSÜ", [
    "🏠 Ana Sayfa & Giriş", 
    "📈 Canlı Analiz Terminali", 
    "⭐ İzleme Listem",
    "⚔️ Rakip Analizi",
    "📡 Piyasa Radarı & Isı Haritası",
    "💼 Portföyüm", 
    "👤 Hesabım",
    "📩 Hakkımda & İletişim"
])

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔔 PİYASA RADARI")
for alarm in piyasa_alarmlari():
    st.sidebar.warning(alarm)

# --- SAYFA: ANA SAYFA ---
if sayfa == "🏠 Ana Sayfa & Giriş":
    st.title("Vader Analiz Dünyasına Hoş Geldiniz")
    st.markdown("Borsa İstanbul ve Küresel Piyasalar için geliştirilmiş yapay zeka destekli terminal.")
    
    if supabase is None:
        st.error("Veritabanı bağlantısı kurulamadı. Lütfen Streamlit Secrets ayarlarını kontrol edin.")
    elif st.session_state.kullanici is None:
        col_login, col_reg = st.columns(2)
        with col_login:
            st.subheader("🔑 Üye Girişi")
            log_mail = st.text_input("E-posta", key="log_mail")
            log_pw = st.text_input("Şifre", type="password", key="log_pw")
            if st.button("Giriş Yap"):
                try:
                    response = supabase.auth.sign_in_with_password({"email": log_mail, "password": log_pw})
                    st.session_state.kullanici = response.user.email
                    st.session_state.user_id = response.user.id
                    try:
                        rol_getir = supabase.table("kullanici_profilleri").select("uyelik_tipi").eq("user_id", response.user.id).execute()
                        if rol_getir.data: st.session_state.uyelik_tipi = rol_getir.data[0]['uyelik_tipi']
                        else: st.session_state.uyelik_tipi = "free"
                    except: st.session_state.uyelik_tipi = "free"
                    
                    try:
                        cookie_manager.set("vader_mail", response.user.email, max_age=2592000, key="giris_1")
                        cookie_manager.set("vader_id", response.user.id, max_age=2592000, key="giris_2")
                    except: pass
                    
                    st.success("Giriş başarılı! Yönlendiriliyorsunuz...")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e: st.error("Giriş başarısız! E-posta veya şifre hatalı olabilir.")
                
        with col_reg:
            st.subheader("📝 Yeni Kayıt Ol")
            reg_mail = st.text_input("E-posta Adresi", key="reg_mail")
            reg_pw = st.text_input("Yeni Şifre (En az 6 hane)", type="password", key="reg_pw")
            if st.button("Üyeliği Tamamla"):
                try:
                    res = supabase.auth.sign_up({"email": reg_mail, "password": reg_pw})
                    if res and res.user:
                        try: supabase.table("kullanici_profilleri").insert({"user_id": res.user.id, "uyelik_tipi": "free"}).execute()
                        except: pass
                    st.success("Kayıt başarılı! Şimdi sol taraftan giriş yapabilirsiniz.")
                except Exception as e: st.error(f"Kayıt hatası: Bu e-posta zaten kayıtlı olabilir.")
    else:
        st.success(f"Sisteme başarıyla giriş yaptınız: **{st.session_state.kullanici}**")
        st.info("İzleme Listeniz ve Portföyünüz bulutla senkronize edildi.")

    st.markdown("### 📢 Duyurular")
    st.warning("Temel analiz araçları tamamen ücretsizdir. Yapay zeka ve Monte Carlo özellikleri Premium Abonelik gerektirir.")
    footer_ekle()

# --- SAYFA: CANLI ANALİZ ---
elif sayfa == "📈 Canlı Analiz Terminali":
    hisse_kod = st.sidebar.text_input("Sembol (Örn: THYAO.IS, BTC-USD, AAPL):", "THYAO.IS").upper()
    sembol = hisse_kod
    studyo = st.sidebar.checkbox("YouTube Stüdyo Modu (Neon)")
    zaman_secimi = st.sidebar.selectbox("Grafik Zaman Dilimi:", ["Günlük (Son 2 Yıl)", "Saatlik (Son 1 Ay)", "15 Dakikalık (Son 5 Gün)", "5 Dakikalık (Son 5 Gün)", "1 Dakikalık (Son 1 Gün)"])
    
    if zaman_secimi == "Günlük (Son 2 Yıl)": p, i = "2y", "1d"
    elif zaman_secimi == "Saatlik (Son 1 Ay)": p, i = "1mo", "1h"
    elif zaman_secimi == "15 Dakikalık (Son 5 Gün)": p, i = "5d", "15m"
    elif zaman_secimi == "5 Dakikalık (Son 5 Gün)": p, i = "5d", "5m"
    else: p, i = "1d", "1m"

    tema = "plotly_dark"
    renk = '#00FFCC' if studyo else 'lime'
    if studyo: st.markdown("<style>h1, h2 { color: #00FFCC !important; }</style>", unsafe_allow_html=True)

    try:
        df, info, gelir, bilanco, ceyreklik_bilanco = veri_motoru(sembol, p, i)
        haberler = son_dakika_haberleri(sembol)
        
        if not df.empty:
            fiyat = df['Close'].iloc[-1]
            onceki = df['Close'].iloc[-2] if len(df)>1 else fiyat
            degisim = fiyat - onceki
            yuzde = (degisim / onceki) * 100 if onceki > 0 else 0
            
            haftalik_getiri = ((fiyat - df['Close'].iloc[-5]) / df['Close'].iloc[-5]) * 100 if len(df) >= 5 else 0
            aylik_getiri = ((fiyat - df['Close'].iloc[-20]) / df['Close'].iloc[-20]) * 100 if len(df) >= 20 else 0
            
            c_header, c_fav = st.columns([4, 1])
            c_header.header(f"⚡ {info.get('longName', hisse_kod)}")
            
            if st.session_state.kullanici:
                with c_fav:
                    st.write("")
                    try:
                        var_mi = supabase.table("izleme_listesi").select("*").eq("user_id", st.session_state.user_id).eq("sembol", sembol).execute()
                        if var_mi.data:
                            if st.button("⭐ Listeden Çıkar", key="cikar"):
                                supabase.table("izleme_listesi").delete().eq("user_id", st.session_state.user_id).eq("sembol", sembol).execute()
                                st.rerun()
                        else:
                            if st.button("⭐ İzlemeye Ekle", key="ekle"):
                                supabase.table("izleme_listesi").insert({"user_id": st.session_state.user_id, "sembol": sembol}).execute()
                                st.rerun()
                    except: pass

            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            anlik_rsi = df['RSI'].iloc[-1]
            
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            anlik_macd = macd.iloc[-1]
            anlik_signal = signal.iloc[-1]
            
            ai_yorum_listesi = ai_teknik_yorum(df, anlik_rsi, anlik_macd, anlik_signal)
            
            c_h, c_r = st.columns([3, 1])
            with c_r:
                st.markdown(rapor_olustur_html(hisse_kod, fiyat, yuzde, anlik_rsi, ai_yorum_listesi), unsafe_allow_html=True)

            m1, m2, m3, m4 = st.columns(4)
            para_birimi = "₺" if ".IS" in sembol else "$"
            m1.metric("Anlık Fiyat", f"{para_birimi}{fiyat:,.2f}", f"{degisim:+.2f} ({yuzde:+.2f}%)")
            m2.metric("Günlük Hacim", f"{int(df['Volume'].iloc[-1]):,}")
            m3.metric("Haftalık Getiri", f"%{haftalik_getiri:.2f}", "Teknik Veri")
            m4.metric("Üyelik Seviyesi", "💎 Premium" if is_premium else "👤 Ücretsiz")

            t1, t2, t3, t4, t5, t6, t7 = st.tabs(["📈 Teknik Grafikler", "⚙️ Al-Sat Sinyalleri", "🤖 AI Teknik Röntgen", "🔮 Pro Simülasyon 💎", "📰 Haberler", "📑 Finansallar", "💬 Vader AI 💎"])
            
            with t1:
                goster_bollinger = st.checkbox("Bollinger Bantlarını Göster")
                goster_rsi = st.checkbox("RSI Göster")
                goster_macd = st.checkbox("MACD Göster")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color=renk if degisim >= 0 else 'red', width=2), name='Fiyat'))
                if goster_bollinger:
                    df['SMA20'] = df['Close'].rolling(20).mean()
                    df['STD20_B'] = df['Close'].rolling(20).std()
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'] + (df['STD20_B'] * 2), line=dict(color='gray', width=1, dash='dash'), name='Üst Bant'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'] - (df['STD20_B'] * 2), line=dict(color='gray', width=1, dash='dash'), name='Alt Bant', fill='tonexty', fillcolor='rgba(128,128,128,0.1)'))
                fig.update_layout(title=f"Ana Fiyat Grafiği ({zaman_secimi})", template=tema, height=450, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
                
                if goster_rsi:
                    fig_rsi = go.Figure()
                    fig_rsi.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='orange', width=2), name='RSI (14)'))
                    fig_rsi.add_hline(y=70, line_dash="dot", line_color="red")
                    fig_rsi.add_hline(y=30, line_dash="dot", line_color="green")
                    fig_rsi.update_layout(title="RSI İndikatörü", template=tema, height=250)
                    st.plotly_chart(fig_rsi, use_container_width=True)

                if goster_macd:
                    fig_macd = go.Figure()
                    fig_macd.add_trace(go.Scatter(x=df.index, y=macd, line=dict(color='blue', width=2), name='MACD'))
                    fig_macd.add_trace(go.Scatter(x=df.index, y=signal, line=dict(color='orange', width=2), name='Sinyal'))
                    fig_macd.add_bar(x=df.index, y=macd - signal, name='Histogram', marker_color='gray')
                    fig_macd.update_layout(title="MACD İndikatörü", template=tema, height=250)
                    st.plotly_chart(fig_macd, use_container_width=True)

            with t2:
                df['SMA20'] = df['Close'].rolling(20).mean()
                df['SMA50'] = df['Close'].rolling(50).mean()
                df['Sinyal_Rob'] = np.where(df['SMA20'] > df['SMA50'], 1, 0)
                df['Pozisyon'] = df['Sinyal_Rob'].diff()
                fig3 = go.Figure()
                fig3.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='gray', width=1), name='Fiyat'))
                fig3.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange', width=1.5), name='SMA 20'))
                fig3.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='blue', width=1.5), name='SMA 50'))
                al = df[df['Pozisyon'] == 1]
                sat = df[df['Pozisyon'] == -1]
                fig3.add_trace(go.Scatter(x=al.index, y=al['SMA20'], mode='markers', marker=dict(color='green', size=10, symbol='triangle-up'), name='AL'))
                fig3.add_trace(go.Scatter(x=sat.index, y=sat['SMA50'], mode='markers', marker=dict(color='red', size=10, symbol='triangle-down'), name='SAT'))
                fig3.update_layout(template=tema, height=500, hovermode="x unified")
                st.plotly_chart(fig3, use_container_width=True)

            with t3: 
                for y in ai_yorum_listesi: st.write(y)
                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                zirve_52 = df['Close'].max()
                dip_52 = df['Close'].min()
                zirveye_uzaklik = ((fiyat - zirve_52) / zirve_52) * 100
                dibe_uzaklik = ((fiyat - dip_52) / dip_52) * 100
                c1.metric("Peryodun En Yüksek", f"{para_birimi}{zirve_52:.2f}", f"Zirveye Uzaklık: %{zirveye_uzaklik:.2f}")
                c2.metric("Peryodun En Düşük", f"{para_birimi}{dip_52:.2f}", f"Dipten Uzaklık: %{dibe_uzaklik:+.2f}")
                c3.metric("Anlık Volatilite", f"{para_birimi}{df['Close'].tail(20).std():.2f}")

            with t4: 
                st.subheader("🔮 Yapay Zeka Gelecek Simülasyonu (Pro Monte Carlo)")
                if is_premium:
                    st.markdown("Hissenin son 1 yıllık hareketleri kullanılarak aynı anda **100 farklı paralel evren** simüle edilmiş ve yüksek ihtimalli rota hesaplanmıştır.")
                    log_returns = np.log(1 + df['Close'].pct_change()).dropna()
                    u = log_returns.mean()
                    var = log_returns.var()
                    stdev = log_returns.std()
                    
                    son_20_getiri = (df['Close'].iloc[-1] / df['Close'].iloc[-20]) - 1 if len(df) >= 20 else 0
                    drift = (u - (0.5 * var)) * 0.4 + ((son_20_getiri / 20) * 0.6)

                    gun = 30
                    sims = np.zeros((gun, 100))
                    sims[0] = fiyat
                    
                    np.random.seed(int(fiyat * 100))
                    for t in range(1, gun): sims[t] = sims[t - 1] * np.exp(drift + stdev * np.random.standard_normal(100))
                    np.random.seed()
                    
                    med = np.percentile(sims, 50, axis=1)
                    iyi = np.percentile(sims, 95, axis=1)
                    kotu = np.percentile(sims, 5, axis=1)
                    tarihler = pd.date_range(start=df.index[-1] + timedelta(days=1), periods=gun)
                    
                    fig_mc = go.Figure()
                    fig_mc.add_trace(go.Scatter(x=df.index[-60:], y=df['Close'].iloc[-60:], line=dict(color='gray', width=2), name='Geçmiş'))
                    fig_mc.add_trace(go.Scatter(x=tarihler, y=iyi, line=dict(color='rgba(0, 255, 0, 0.4)', dash='dot'), name='İyimser'))
                    fig_mc.add_trace(go.Scatter(x=tarihler, y=kotu, fill='tonexty', fillcolor='rgba(128,128,128,0.1)', line=dict(color='rgba(255, 0, 0, 0.4)', dash='dot'), name='Kötümser'))
                    fig_mc.add_trace(go.Scatter(x=tarihler, y=med, line=dict(color='#00FFCC', width=3), name='Medyan Rota'))
                    fig_mc.update_layout(template=tema, height=450, hovermode="x unified")
                    st.plotly_chart(fig_mc, use_container_width=True)
                    
                    st.markdown("---")
                    st.subheader("🎯 Yatırım Zaman Makinesi")
                    yatirim = st.slider("1 Yıl Önce Ne Kadar Yatırsaydım:", 1000, 1000000, 10000, 1000)
                    g_f = df['Close'].iloc[-252] if len(df) >= 252 else df['Close'].iloc[0]
                    st.success(f"1 yıl önce **{para_birimi}{g_f:.2f}** fiyattan alınan varlığın bugünkü değeri: **{para_birimi}{(yatirim / g_f) * fiyat:,.2f}**")
                else:
                    st.error("🔒 Bu özellik sadece Premium Abonelere özeldir.")
                    st.write("Yapay Zeka (Monte Carlo) simülasyonları ile hissenin rotasını görmek için Premium'a geçmelisiniz.")
                    if st.button("💎 Premium Satın Al"): st.info("İletişim: yunusemreeris787@gmail.com")

            with t5:
                c_hab1, c_hab2 = st.columns([3, 1])
                c_hab1.subheader("📡 Canlı Haber Radarı")
                
                if c_hab2.button("🔄 Radarı Yenile", key="haber_yenile_btn"):
                    son_dakika_haberleri.clear() 
                    st.rerun() 
                
                st.markdown("---")
                
                if haberler:
                    for h in haberler[:8]:
                        b = h.get('title', 'Başlık Yok')
                        if 'custom_time' in h:
                            y_v = h['custom_time']
                        else:
                            y_v = datetime.fromtimestamp(h.get('providerPublishTime', 0)).strftime('%d.%m.%Y %H:%M') if h.get('providerPublishTime') else "Yeni"
                            
                        with st.expander(f"{duygu_analizi(b)} | {b}"):
                            st.write(f"**Kaynak:** {h.get('publisher', 'Bilinmeyen')} | **Tarih:** {y_v}")
                            st.write(f"[Haberi Oku]({h.get('link', '#')})")
                else: 
                    st.info("Son 24 saat içinde bu varlık için önemli bir haber düşmedi.")

            with t6:
                st.subheader("📑 Finansal Tablolar ve Bilanço")
                tablo_secim = st.radio("İncelemek İstediğiniz Tabloyu Seçin:", ["Yıllık Bilanço", "Dönem İçi (Çeyreklik)", "Gelir Tablosu"], horizontal=True)
                
                aktif_t = bilanco if tablo_secim == "Yıllık Bilanço" else (ceyreklik_bilanco if tablo_secim == "Dönem İçi (Çeyreklik)" else gelir)
                if not aktif_t.empty:
                    aktif_t.columns = [str(col).split()[0] for col in aktif_t.columns]
                    try: st.dataframe(aktif_t.map(rakam_formatla), use_container_width=True)
                    except AttributeError: st.dataframe(aktif_t.applymap(rakam_formatla), use_container_width=True)
                else: st.warning("⚠️ Seçilen finansal veriler, Yahoo Finance tarafından anlık olarak gizlenmiş veya kısıtlanmış olabilir.")

            with t7: 
                st.subheader(f"🧠 Vader AI - {hisse_kod} Özel Asistanı")
                if is_premium:
                    st.markdown("Bana hissenin güncel durumu hakkında teknik sorular sorabilirsin.")
                    k_s = st.text_input("Vader'a Sor:", placeholder="Örn: Bu hissenin grafiği nasıl, yönü ne?")
                    if st.button("Analiz Et"):
                        if k_s:
                            s = k_s.lower()
                            cevap = f"**Vader'ın Teknik Analizi:**\n\n- Hissenin anlık RSI puanı **{anlik_rsi:.2f}**.\n"
                            if anlik_rsi > 70: cevap += "- 🚨 Aşırı Alım bölgesinde! Riskli (Pahalı).\n"
                            elif anlik_rsi < 30: cevap += "- 🟢 Aşırı Satım bölgesinde! Dip seviyelerde (Ucuz).\n"
                            else: cevap += "- ⚪ Hisse şu an nötr bölgede.\n"
                            if anlik_macd > anlik_signal: cevap += "- Kısa vadeli MACD sinyali AL veriyor.\n"
                            else: cevap += "- Kısa vadeli MACD sinyali SAT veriyor.\n"
                            st.info(cevap)
                else:
                    st.error("🔒 Vader AI Asistanı sadece Premium Abonelere özeldir.")
                    st.write("Yapay zekaya hisse hakkında dilediğinizi sormak için Premium'a geçmelisiniz.")

        else:
            st.error("Veri çekilemedi. Hatalı kod girdiniz veya Yahoo kısıtlaması var.")
    except Exception as e:
        st.error(f"Sistem Hatası: {e}")
    footer_ekle()

# --- SAYFA: İZLEME LİSTEM ---
elif sayfa == "⭐ İzleme Listem":
    st.title("Kişisel İzleme Listeniz")
    st.markdown("Favoriye aldığınız tüm varlıkları tek ekranda takip edin.")
    if st.session_state.kullanici:
        try:
            liste = supabase.table("izleme_listesi").select("sembol").eq("user_id", st.session_state.user_id).execute()
            if liste.data:
                for kalem in liste.data:
                    s = kalem['sembol']
                    d = yf.Ticker(s).history(period="2d")
                    if not d.empty and len(d) >= 2:
                        son = d['Close'].iloc[-1]
                        eski = d['Close'].iloc[-2]
                        yuzde = ((son - eski) / eski) * 100
                        para_b = "₺" if ".IS" in s else "$"
                        
                        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                        c1.markdown(f"<h3 style='color: #00FFCC;'>{s}</h3>", unsafe_allow_html=True)
                        c2.metric("Anlık Fiyat", f"{para_b}{son:,.2f}", f"{son-eski:+.2f} ({yuzde:+.2f}%)")
                        
                        renk = "green" if yuzde >= 0 else "red"
                        fig = go.Figure(go.Scatter(y=d['Close'], mode='lines', line=dict(color=renk, width=3)))
                        fig.update_layout(height=80, margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                        with c3: st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                        
                        with c4:
                            st.write("")
                            if st.button("❌", key=f"delfav_{s}"):
                                supabase.table("izleme_listesi").delete().eq("user_id", st.session_state.user_id).eq("sembol", s).execute()
                                st.rerun()
                        st.markdown("---")
            else: st.info("İzleme listeniz boş. Canlı Analiz kısmından yıldızla ekleyin.")
        except Exception as e: st.error(f"Bağlantı hatası: {e}")
    else: st.warning("Bu özelliği kullanmak için giriş yapmalısınız.")
    footer_ekle()

# --- SAYFA: RAKİP ANALİZİ ---
elif sayfa == "⚔️ Rakip Analizi":
    st.title("⚔️ Sektörel Çarpışma: Rakip Analizi")
    st.markdown("İki farklı şirketi veya varlığı aynı ringe çıkarın.")
    
    colA, colB = st.columns(2)
    with colA: h1 = st.text_input("1. Varlık (Örn: FROTO.IS):", "FROTO.IS").upper()
    with colB: h2 = st.text_input("2. Varlık (Örn: TOASO.IS):", "TOASO.IS").upper()
    
    if st.button("Çarpıştır ⚡"):
        try:
            df1, _, _, _, _ = veri_motoru(h1, "1y", "1d")
            df2, _, _, _, _ = veri_motoru(h2, "1y", "1d")
            
            if not df1.empty and not df2.empty:
                st.subheader("📊 Teknik Veri Karşılaştırması")
                getiri1 = ((df1['Close'].iloc[-1] - df1['Close'].iloc[0]) / df1['Close'].iloc[0]) * 100
                getiri2 = ((df2['Close'].iloc[-1] - df2['Close'].iloc[0]) / df2['Close'].iloc[0]) * 100
                
                def calc_rsi(d):
                    delta = d['Close'].diff()
                    rs = (delta.where(delta > 0, 0)).rolling(14).mean() / (-delta.where(delta < 0, 0)).rolling(14).mean()
                    return 100 - (100 / (1 + rs.iloc[-1]))

                comp_data = {
                    "Metrik": ["Anlık Fiyat", "Son 1 Yıl Getirisi", "RSI (Momentum)", "Günlük Hacim"],
                    h1: [f"{df1['Close'].iloc[-1]:,.2f}", f"%{getiri1:.2f}", f"{calc_rsi(df1):.2f}", f"{int(df1['Volume'].iloc[-1]):,}"],
                    h2: [f"{df2['Close'].iloc[-1]:,.2f}", f"%{getiri2:.2f}", f"{calc_rsi(df2):.2f}", f"{int(df2['Volume'].iloc[-1]):,}"]
                }
                st.table(pd.DataFrame(comp_data).set_index("Metrik"))
                
                st.subheader("📈 Performans Çarpışması (Son 1 Yıl Normalize Getiri)")
                df1['Normalize'] = (df1['Close'] / df1['Close'].iloc[0] - 1) * 100
                df2['Normalize'] = (df2['Close'] / df2['Close'].iloc[0] - 1) * 100
                
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Scatter(x=df1.index, y=df1['Normalize'], name=h1, line=dict(color='#00FFCC', width=2)))
                fig_comp.add_trace(go.Scatter(x=df2.index, y=df2['Normalize'], name=h2, line=dict(color='orange', width=2)))
                fig_comp.update_layout(template="plotly_dark", height=400, yaxis_title="Getiri (%)", hovermode="x unified")
                st.plotly_chart(fig_comp, use_container_width=True)
            else: st.error("Varlıklardan birinin verisi çekilemedi.")
        except: st.error("Hata oluştu. Doğru yazdığınızdan emin olun.")
    footer_ekle()

# --- SAYFA: PİYASA RADARI ---
elif sayfa == "📡 Piyasa Radarı & Isı Haritası":
    st.title("🗺️ Piyasa Isı Haritası & Radar")
    st.markdown("Yeşil kutular yükselişi, kırmızı kutular düşüşü temsil eder.")
    
    radar_listesi = ["THYAO.IS", "SASA.IS", "EREGL.IS", "TUPRS.IS", "FROTO.IS", "BTC-USD", "ETH-USD", "GC=F", "AAPL", "NVDA", "TSLA"]
    
    if st.button("🚀 Haritayı & Radarı Çalıştır"):
        with st.spinner("Piyasa röntgeni çekiliyor..."):
            harita_datalari = []
            for sembol in radar_listesi:
                try:
                    df = yf.Ticker(sembol).history(period="5d")
                    if len(df) >= 2:
                        son = df['Close'].iloc[-1]
                        eski = df['Close'].iloc[-2]
                        yuzde = ((son - eski) / eski) * 100
                        hacim = df['Volume'].iloc[-1]
                        grup = "Kripto" if "-USD" in sembol else ("ABD" if not ".IS" in sembol and "F" not in sembol else "BIST")
                        
                        harita_datalari.append({
                            "Hisse": sembol.replace(".IS", ""), "Degisim": round(yuzde, 2),
                            "Hacim": hacim, "Fiyat": round(son, 2), "Grup": grup
                        })
                except: pass
            
            if harita_datalari:
                df_hm = pd.DataFrame(harita_datalari)
                fig_hm = px.treemap(df_hm, path=['Grup', 'Hisse'], values='Hacim', color='Degisim', color_continuous_scale='RdYlGn', color_continuous_midpoint=0, custom_data=['Fiyat', 'Degisim'])
                fig_hm.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>%{customdata[1]:.2f}%", textposition="middle center")
                fig_hm.update_layout(template="plotly_dark", height=600, margin=dict(t=10, l=10, r=10, b=10))
                st.plotly_chart(fig_hm, use_container_width=True)
                st.dataframe(df_hm.sort_values(by="Degisim", ascending=False), use_container_width=True)
            else: st.error("Veri çekilemedi.")
    footer_ekle()

# --- SAYFA: PORTFÖYÜM ---
elif sayfa == "💼 Portföyüm":
    st.title("💼 Şahsi Bulut Portföyünüz")
    if st.session_state.kullanici is None: st.warning("Bu sayfayı görüntülemek için giriş yapmalısınız.")
    else:
        with st.expander("➕ Portföye Yeni Hisse Ekle", expanded=False):
            with st.form("hisse_ekle_form"):
                yeni_kod = st.text_input("Varlık Kodu (Örn: SASA.IS, AAPL):").upper()
                yeni_maliyet = st.number_input("Maliyet (Birim Fiyat)", min_value=0.0, step=1.0)
                yeni_lot = st.number_input("Adet (Lot)", min_value=1.0, step=0.1)
                ekle_btn = st.form_submit_button("Veritabanına Kaydet")
                if ekle_btn and yeni_kod:
                    try:
                        veri = {"user_id": st.session_state.user_id, "hisse_kod": yeni_kod, "maliyet": yeni_maliyet, "lot": yeni_lot}
                        supabase.table("portfoyler").insert(veri).execute()
                        st.success("Kaydedildi!")
                        st.rerun()
                    except Exception as e: st.error(f"Hata: {e}")

        st.subheader("📊 Portföy Analizi ve Varlıklarınız")
        try:
            veriler = supabase.table("portfoyler").select("*").eq("user_id", st.session_state.user_id).execute()
            if veriler.data:
                df_port = pd.DataFrame(veriler.data)
                
                toplam_maliyet_genel, toplam_guncel_genel, toplam_temettu = 0, 0, 0
                pasta_etiketler, pasta_degerler, gecerli_veriler = [], [], []

                for index, row in df_port.iterrows():
                    try:
                        h = yf.Ticker(row['hisse_kod'])
                        anlik_fiyat = h.history(period="5d")['Close'].iloc[-1]
                        try:
                            div_yield = h.info.get('dividendYield', 0)
                            if div_yield: toplam_temettu += (anlik_fiyat * div_yield) * row['lot']
                        except: pass
                        guncel_deger = anlik_fiyat * row['lot']
                        toplam_maliyet = row['maliyet'] * row['lot']
                        kar = guncel_deger - toplam_maliyet
                        kar_yuzde = (kar / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
                        toplam_maliyet_genel += toplam_maliyet
                        toplam_guncel_genel += guncel_deger
                        pasta_etiketler.append(row['hisse_kod'])
                        pasta_degerler.append(guncel_deger)
                        gecerli_veriler.append({'id': row['id'], 'hisse_kod': row['hisse_kod'], 'maliyet': row['maliyet'], 'lot': row['lot'], 'guncel_deger': guncel_deger, 'kar': kar, 'kar_yuzde': kar_yuzde})
                    except: pass
                
                if gecerli_veriler:
                    st.markdown("---")
                    ozet_col, pie_col = st.columns([1, 1.5])
                    with ozet_col:
                        st.markdown("### 💰 Toplam Portföy Durumu")
                        toplam_kar_genel = toplam_guncel_genel - toplam_maliyet_genel
                        toplam_kar_yuzde = (toplam_kar_genel / toplam_maliyet_genel) * 100 if toplam_maliyet_genel > 0 else 0
                        st.metric("Toplam Yatırım Maliyeti", f"{toplam_maliyet_genel:,.2f}")
                        st.metric("Toplam Güncel Bakiye", f"{toplam_guncel_genel:,.2f}")
                        st.metric("Total Net Kâr / Zarar", f"{toplam_kar_genel:+,.2f} ({toplam_kar_yuzde:+.2f}%)")
                        st.markdown("---")
                        st.markdown("### 💸 Temettü Simülatörü")
                        st.success(f"Tahmini Yıllık Pasif Gelir: **{toplam_temettu:,.2f}**")

                    with pie_col:
                        fig_pie = go.Figure(data=[go.Pie(labels=pasta_etiketler, values=pasta_degerler, hole=.4, textinfo='label+percent')])
                        fig_pie.update_layout(title_text="💼 Varlık Dağılımı", template="plotly_dark", height=350, margin=dict(t=40, b=10, l=10, r=10))
                        st.plotly_chart(fig_pie, use_container_width=True)
                    
                    st.markdown("---")
                    st.subheader("🧠 Vader Portföy Röntgeni")
                    if is_premium:
                        if len(pasta_etiketler) <= 2: st.warning("⚠️ **Risk Uyarısı:** Varlık sayınız çok az. Çeşitliliği artırmanı öneririm.")
                        else: st.info(f"✅ **Dağılım Başarılı:** Sepetinizde {len(pasta_etiketler)} farklı varlık var.")
                        en_buyuk_index = np.argmax(pasta_degerler)
                        st.write(f"- En büyük ağırlık **%{ (pasta_degerler[en_buyuk_index] / sum(pasta_degerler)) * 100 :.1f}** ile **{pasta_etiketler[en_buyuk_index]}**.")
                        if toplam_kar_genel > 0: st.write("- 🟢 Yatırım stratejiniz kârlı ilerliyor.")
                        else: st.write("- 🔴 Genel portföy şu an zararda. Maliyet düşürmek değerlendirilebilir.")
                    else:
                        st.error("🔒 Yapay Zeka Portföy Röntgeni sadece Premium Abonelere özeldir.")

                    st.markdown("---")
                    st.markdown("### 📋 Varlık Detayları")
                    for v in gecerli_veriler:
                        c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 2.5, 1])
                        c1.write(f"**{v['hisse_kod']}**")
                        c2.write(f"Maliyet: {v['maliyet']:,.2f}")
                        c3.write(f"Lot: {v['lot']}")
                        c4.metric("Güncel & Kar", f"{v['guncel_deger']:,.2f}", f"{v['kar']:+,.2f} ({v['kar_yuzde']:+.2f}%)")
                        if c5.button("Sil", key=f"del_port_{v['id']}"):
                            supabase.table("portfoyler").delete().eq("id", v['id']).execute()
                            st.rerun()
                        st.markdown("---")
            else: st.info("Portföy boş.")
        except Exception as e: st.error(f"Hata: {e}")
    footer_ekle()

# --- SAYFA: HESABIM ---
elif sayfa == "👤 Hesabım":
    st.title("Profil ve Üyelik Yönetimi")
    if st.session_state.kullanici:
        st.markdown(f"""
        ### Hesap Bilgileri
        - **E-posta Adresi:** {st.session_state.kullanici}
        - **Kayıt ID:** {st.session_state.user_id[:8]}...
        - **Mevcut Paket:** {'💎 Premium (Tam Erişim)' if is_premium else '👤 Ücretsiz (Free)'}
        """)
        
        st.markdown("---")
        if not is_premium:
            st.error("🔒 Hesabınız Standart (Ücretsiz) Planda.")
            st.markdown("""
            **Premium Avantajları:**
            * Yapay Zeka (Vader AI) ile anında sohbet ve teknik analiz asistanı
            * Çoklu Evren (Monte Carlo) Algoritması ile gelecek projeksiyonu
            * Portföyünüz için Profesyonel Yapay Zeka Röntgeni ve Tavsiyeler
            """)
            if st.button("💎 Premium'a Yükselt"):
                st.success("Satın alım sayfasına yönlendiriliyorsunuz... (Yakında aktif!)")
                st.info("Bu süreçte yükseltme için bana yazabilirsin: yunusemreeris787@gmail.com")
        else:
            st.success("👑 VIP Ayrıcalığı: Hesabınızda Tüm Premium özellikler aktiftir.")
            
    else: st.warning("Bu sayfayı görmek için giriş yapmalısınız.")
    footer_ekle()

# --- SAYFA: HAKKIMDA ---
elif sayfa == "📩 Hakkımda & İletişim":
    st.title("👨‍💻 Geliştirici Hakkında")
    st.markdown(f"""
    **Vader Analiz Terminali**, Bursa Uludağ Üniversitesi İİBF öğrencisi **Yunus Emre Eriş** tarafından geliştirilmiş profesyonel bir borsa ve global piyasalar analiz projesidir.
    
    ### Vizyonumuz
    Yatırımcılara şeffaf, hızlı ve yapay zeka destekli analiz araçları sunarak finansal okuryazarlığı artırmak ve bilgiye dayalı kararlar almalarını sağlamak.
    
    ### İletişim & İş Birliği
    Reklam, sponsorluk veya teknik destek için:
    - **E-posta:** yunusemreeris787@gmail.com
    """)
    footer_ekle()
