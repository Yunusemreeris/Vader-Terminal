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

# --- 1. SİTE KONFİGÜRASYONU VE VERİTABANI BAĞLANTISI ---
st.set_page_config(page_title="Vader Analiz Terminali", layout="wide", initial_sidebar_state="expanded")

if "cookie_manager" not in st.session_state:
    st.session_state.cookie_manager = stx.CookieManager(key="vader_cookies")
cookie_manager = st.session_state.cookie_manager

if 'cerez_kontrol_edildi' not in st.session_state:
    st.session_state.cerez_kontrol_edildi = True
    with st.spinner("🔐 Güvenli oturum kontrol ediliyor, lütfen bekleyin..."):
        time.sleep(0.6)  
    st.rerun()           

kayitli_mail = cookie_manager.get(cookie="vader_mail")
kayitli_id = cookie_manager.get(cookie="vader_id")

if 'kullanici' not in st.session_state:
    st.session_state.kullanici = kayitli_mail if kayitli_mail else None
if 'user_id' not in st.session_state:
    st.session_state.user_id = kayitli_id if kayitli_id else None

@st.cache_resource
def supabase_baglan():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        return None

supabase = supabase_baglan()

# --- YARDIMCI FONKSİYONLAR VE MOTORLAR ---
@st.cache_data(ttl=1800)
def piyasa_alarmlari():
    alarmlar = []
    demirbaslar = ["THYAO.IS", "SASA.IS", "EREGL.IS", "TUPRS.IS"]
    for sembol in demirbaslar:
        try:
            df = yf.Ticker(sembol).history(period="10d")
            if len(df) >= 2:
                degisim = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                if degisim <= -3.0: alarmlar.append(f"🚨 {sembol[:5]} bugün %{abs(degisim):.1f} düştü! Fırsat olabilir.")
                elif degisim >= 4.0: alarmlar.append(f"🚀 {sembol[:5]} yükselişte! (+%{degisim:.1f})")
        except: pass
    if not alarmlar: alarmlar.append("Piyasa şu an sakin, olağanüstü bir hareket yok.")
    return alarmlar

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
        <h1>🛸 VADER PRO - Kurumsal Analiz Raporu</h1>
        <div class="kutu">
            <h2>Hisse: {hisse}</h2>
            <p>Rapor Tarihi: {datetime.now().strftime("%d.%m.%Y %H:%M")}</p>
            <p>Anlık Fiyat: <span class="metrik">₺{fiyat:,.2f} ({degisim_yuzde:+.2f}%)</span></p>
            <p>Teknik RSI (Göreceli Güç Endeksi): <b>{rsi:.2f}</b></p>
        </div>
        <div class="kutu">
            <h2>🧠 Vader AI Temel Analiz Yorumu</h2>
            <ul>{''.join([f'<li>{y}</li>' for y in yorumlar])}</ul>
        </div>
        <div class="footer">Bu belge Vader Analiz Terminali (Yunus Emre Eriş) tarafından otomatik üretilmiştir. Tarayıcınızda Ctrl+P yaparak PDF olarak kaydedebilirsiniz.</div>
    </body></html>
    """
    b64 = base64.b64encode(html_icerik.encode()).decode()
    return f'<a href="data:text/html;base64,{b64}" download="VADER_Rapor_{hisse}.html" style="background-color:#00FFCC; color:black; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold;">📄 Raporu İndir (HTML/PDF)</a>'

# --- 2. PROFESYONEL NAVİGASYON MENÜSÜ ---
st.sidebar.markdown(f"<h2 style='text-align: center; color: #00FFCC;'>🛸 VADER PRO</h2>", unsafe_allow_html=True)

if st.session_state.kullanici:
    st.sidebar.success(f"👤 Aktif Kullanıcı:\n{st.session_state.kullanici}")
    if st.sidebar.button("🚪 Çıkış Yap"):
        cookie_manager.delete("vader_mail")
        cookie_manager.delete("vader_id")
        st.session_state.kullanici = None
        st.session_state.user_id = None
        time.sleep(0.5) 
        st.rerun()

sayfa = st.sidebar.radio("SİTE MENÜSÜ", [
    "🏠 Ana Sayfa & Giriş", 
    "📈 Canlı Analiz Terminali", 
    "⚔️ Rakip Analizi (Karşılaştırma)",
    "📡 Piyasa Radarı & Isı Haritası",
    "💼 Portföyüm & Yapay Zeka Röntgeni", 
    "📩 Hakkımda & İletişim"
])

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔔 PİYASA ALARMLARI")
for alarm in piyasa_alarmlari():
    st.sidebar.warning(alarm)

ingilizce_turkce_sozluk = {
    "Total Revenue": "Toplam Gelir", "Gross Profit": "Brüt Kar", "Net Income": "Net Kar",
    "Total Assets": "Toplam Varlıklar", "Total Liabilities Net Minority Interest": "Toplam Borçlar",
    "Stockholders Equity": "Özkaynaklar", "Cash And Cash Equivalents": "Nakit"
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
    
    try:
        ham_ceyrek = h.quarterly_balance_sheet
        ceyreklik_bilanco = ham_ceyrek[ham_ceyrek.index.isin(ingilizce_turkce_sozluk.keys())].rename(index=ingilizce_turkce_sozluk) if ham_ceyrek is not None else pd.DataFrame()
    except: ceyreklik_bilanco = pd.DataFrame()
    
    try: bilgi = h.info
    except: bilgi = {}
    
    return bilgi, df, df_endeks, gelir, bilanco, ceyreklik_bilanco

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
                haberler.append({'title': item.find('title').text, 'link': item.find('link').text, 'publisher': item.find('source').text if item.find('source') is not None else "Google Haberler", 'custom_time': item.find('pubDate').text})
            return haberler
        except: pass
    try:
        yh_news = yf.Ticker(sembol).news
        if yh_news:
            for h in yh_news:
                if 'title' in h and h['title']: haberler.append(h)
    except: pass
    return haberler[:5]

@st.cache_data(ttl=900)
def watchlist_verisi_getir(sembol):
    return yf.Ticker(sembol).history(period="5d")

def ai_bilanco_yorumu(bilgi):
    yorumlar = []
    fk, cari, marj = bilgi.get('trailingPE', 0), bilgi.get('currentRatio', 0), bilgi.get('profitMargins', 0)
    if fk and fk > 0:
        yorumlar.append("🟢 **Değerleme:** Şirketin F/K oranı düşük, ucuz görünüyor." if fk < 10 else ("🔴 **Değerleme:** F/K oranı yüksek, piyasa şu an pahalı fiyatlıyor." if fk > 25 else "🟡 **Değerleme:** F/K oranı sektör ortalamalarında."))
    if cari:
        yorumlar.append("🟢 **Borçluluk:** Kısa vadeli nakit durumu güçlü." if cari >= 1.5 else "🔴 **Borçluluk:** Nakit akışı ve borç ödeme kapasitesi sınırda.")
    if marj:
        yorumlar.append("🟢 **Karlılık:** Kar marjı sağlıklı (%15+)." if marj > 0.15 else "🔴 **Karlılık:** Kar marjı düşük, kasaya az nakit giriyor.")
    
    # YENİ: Profesyonel Hata Kapatıcı
    return yorumlar if yorumlar else ["⚠️ **Veri Kısıtlaması:** Yahoo Finance, Türkiye hisseleri için bilanço temel verilerini (F/K, Cari Oran vb.) gizlediği için Vader AI şu an bu hisseye not veremiyor."]

def duygu_analizi(metin):
    metin = str(metin).lower()
    poz_skor = sum(1 for k in ['artış', 'kâr', 'büyüme', 'anlaşma', 'yükseliş', 'pozitif', 'up'] if k in metin)
    neg_skor = sum(1 for k in ['zarar', 'düşüş', 'ceza', 'risk', 'negatif', 'down'] if k in metin)
    if poz_skor > neg_skor: return "🟢 Pozitif Etki"
    elif neg_skor > poz_skor: return "🔴 Negatif Etki"
    else: return "⚪ Nötr Haber"

def footer_ekle():
    st.markdown("---")
    st.markdown(f"<p style='text-align: center; color: gray;'>Copyright © {datetime.now().year} Yunus Emre Eriş - Vader Analiz Terminali | Tüm Hakları Saklıdır.</p>", unsafe_allow_html=True)


# --- SAYFA TASARIMLARI ---

if sayfa == "🏠 Ana Sayfa & Giriş":
    st.title("Vader Analiz Dünyasına Hoş Geldiniz")
    st.markdown("Borsa İstanbul analizi için geliştirilmiş en kapsamlı yerli terminal.")
    
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
                    cookie_manager.set("vader_mail", response.user.email, max_age=2592000)
                    cookie_manager.set("vader_id", response.user.id, max_age=2592000)
                    st.success("Giriş başarılı! Yönlendiriliyorsunuz...")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error("Giriş başarısız! E-posta veya şifre hatalı olabilir.")
                
        with col_reg:
            st.subheader("📝 Yeni Kayıt Ol")
            reg_mail = st.text_input("E-posta Adresi", key="reg_mail")
            reg_pw = st.text_input("Yeni Şifre (En az 6 hane)", type="password", key="reg_pw")
            if st.button("Üyeliği Tamamla"):
                try:
                    supabase.auth.sign_up({"email": reg_mail, "password": reg_pw})
                    st.success("Kayıt başarılı! Şimdi sol taraftan giriş yapabilirsiniz.")
                except Exception as e:
                    st.error(f"Kayıt hatası: Şifre çok kısa olabilir veya bu e-posta zaten kayıtlı.")
    else:
        st.success(f"Sisteme başarıyla giriş yaptınız: **{st.session_state.kullanici}**")
        st.info("Sistem kimliğinizi hatırlıyor. Sayfayı yenileseniz dahi oturumunuz açık kalacaktır.")

    st.markdown("### 📢 Duyurular")
    st.warning("Tüm analiz araçlarını sol menüdeki 'Canlı Analiz Terminali' sekmesinden ücretsiz kullanabilirsiniz. Portföy kaydı için giriş yapmanız gereklidir.")
    footer_ekle()

elif sayfa == "📈 Canlı Analiz Terminali":
    hisse_kod = st.sidebar.text_input("Analiz Edilecek Hisse (Örn: THYAO):", "THYAO").upper()
    sembol = hisse_kod + ".IS"
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
        bilgi, df, df_endeks, gelir, bilanco, ceyreklik_bilanco = veri_motoru(sembol, p, i)
        haberler = son_dakika_haberleri(sembol)
        
        if not df.empty:
            fiyat = bilgi.get('currentPrice', df['Close'].iloc[-1])
            onceki = bilgi.get('previousClose', df['Close'].iloc[-2] if len(df)>1 else fiyat)
            degisim = fiyat - onceki
            yuzde = (degisim / onceki) * 100 if onceki > 0 else 0
            
            c_header, c_rapor = st.columns([3, 1])
            c_header.header(f"⚡ {bilgi.get('longName', hisse_kod)}")
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            anlik_rsi = df['RSI'].iloc[-1]
            
            with c_rapor:
                st.write("") 
                st.markdown(rapor_olustur_html(hisse_kod, fiyat, yuzde, anlik_rsi, ai_bilanco_yorumu(bilgi)), unsafe_allow_html=True)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Anlık Fiyat", f"₺{fiyat:,.2f}", f"{degisim:+.2f} TL ({yuzde:+.2f}%)")
            m2.metric("Günlük Hacim", f"{bilgi.get('volume', int(df['Volume'].iloc[-1])):,}")
            # YENİ: Profesyonel Veri Gizleme Formatı
            m3.metric("F/K Oranı", round(bilgi.get('trailingPE'), 2) if bilgi.get('trailingPE') else "Bilinmiyor")
            m4.metric("Piyasa Değeri", f"₺{bilgi.get('marketCap', 0):,}" if bilgi.get('marketCap') else "Bilinmiyor")

            t1, t2, t3, t4, t5, t6, t7 = st.tabs(["📈 Gelişmiş Grafikler", "⚙️ Al-Sat Robotu", "🤖 AI Yorum & Sağlık", "🎯 Değerleme & Tahmin", "📰 Haberler", "📑 Finansallar", "💬 Vader AI (İnteraktif)"])
            
            with t1:
                goster_bollinger = st.checkbox("Bollinger Bantlarını Göster")
                goster_rsi = st.checkbox("RSI (Göreceli Güç Endeksi) Göster")
                goster_macd = st.checkbox("MACD (Trend Göstergesi) Göster")
                
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
                    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
                    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
                    df['MACD'] = exp1 - exp2
                    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                    fig_macd = go.Figure()
                    fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='blue', width=2), name='MACD'))
                    fig_macd.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='orange', width=2), name='Sinyal'))
                    fig_macd.add_bar(x=df.index, y=df['MACD'] - df['Signal'], name='Histogram', marker_color='gray')
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
                for y in ai_bilanco_yorumu(bilgi): st.write(y)
                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                # YENİ: Profesyonel Veri Gizleme Formatı
                c1.metric("PD/DD", round(bilgi.get('priceToBook', 0), 2) if bilgi.get('priceToBook') else "Gizli / Veri Yok")
                c2.metric("Özkaynak Karlılığı (ROE)", f"%{round(bilgi.get('returnOnEquity', 0)*100, 2)}" if bilgi.get('returnOnEquity') else "Gizli / Veri Yok")
                c3.metric("Cari Oran", round(bilgi.get('currentRatio', 0), 2) if bilgi.get('currentRatio') else "Gizli / Veri Yok")

            with t4: 
                st.subheader("🔮 Yapay Zeka Gelecek Tahmini (Monte Carlo)")
                st.markdown("Hissenin tarihsel oynaklığına dayalı önümüzdeki 30 gün için tahmini rotası simüle edilmiştir.")
                
                log_returns = np.log(1 + df['Close'].pct_change())
                u, var, stdev = log_returns.mean(), log_returns.var(), log_returns.std()
                drift = u - (0.5 * var)
                gun = 30
                np.random.seed(int(fiyat * 100))
                tahmin_getiri = np.exp(drift + stdev * np.random.standard_normal(gun))
                tahmin_fiyat = np.zeros_like(tahmin_getiri)
                tahmin_fiyat[0] = fiyat
                for t in range(1, gun): tahmin_fiyat[t] = tahmin_fiyat[t - 1] * tahmin_getiri[t]
                np.random.seed()
                
                gelecek_tarihler = pd.date_range(start=df.index[-1], periods=gun)
                fig_mc = go.Figure()
                fig_mc.add_trace(go.Scatter(x=df.index[-60:], y=df['Close'].iloc[-60:], line=dict(color='gray', width=2), name='Geçmiş Fiyat'))
                fig_mc.add_trace(go.Scatter(x=gelecek_tarihler, y=tahmin_fiyat, line=dict(color='#00FFCC', width=2, dash='dot'), name='AI Tahmini (30 Gün)'))
                fig_mc.update_layout(template=tema, height=350, title="30 Günlük Matematiksel Projeksiyon")
                st.plotly_chart(fig_mc, use_container_width=True)
                
                st.markdown("---")
                st.subheader("🎯 İçsel Değer & Zaman Makinesi")
                eps = bilgi.get('trailingEps', 0)
                beklenen_buyume = st.slider("Tahmini Yıllık Büyüme (%):", 1, 50, 15)
                
                # YENİ: Hata yerine sarı profesyonel uyarı kutusu
                if eps and eps > 0:
                    icsel = eps * (8.5 + (2 * (beklenen_buyume / 100) * 100))
                    st.info(f"Hesaplanan Gerçek Eder (Graham): **₺{icsel:,.2f}** (Anlık Fiyat: ₺{fiyat:,.2f})")
                else:
                    st.warning("⚠️ **Sistem Uyarısı:** Yahoo Finance bu hissenin EPS (Hisse Başına Kâr) verisini dışarıya kapattığı için 'Gerçek Eder' hesaplaması yapılamıyor.")

                yatirim = st.slider("1 Yıl Önce Ne Kadar Yatırsaydım:", 1000, 1000000, 10000, 1000)
                gecmis_fiyat = df['Close'].iloc[-252] if len(df) >= 252 else df['Close'].iloc[0]
                bugunku_deger = (yatirim / gecmis_fiyat) * fiyat
                st.success(f"1 yıl önce **₺{gecmis_fiyat:.2f}** fiyattan alınan hisselerin bugünkü değeri: **₺{bugunku_deger:,.2f}**")

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
                tablo_secim = st.radio("İncelemek İstediğiniz Tablo Periyodunu Seçin:", ["Yıllık Bilanço", "Dönem İçi (Çeyreklik) Bilanço"], horizontal=True)
                aktif_tablo = bilanco if tablo_secim == "Yıllık Bilanço" else ceyreklik_bilanco
                if not aktif_tablo.empty:
                    aktif_tablo.columns = [str(col).split()[0] for col in aktif_tablo.columns]
                    try: f_b = aktif_tablo.map(rakam_formatla)
                    except AttributeError: f_b = aktif_tablo.applymap(rakam_formatla)
                    st.dataframe(f_b, use_container_width=True)
                else: st.info(f"{tablo_secim} verisi bulunamadı.")

            with t7: 
                st.subheader(f"🧠 Vader AI - {hisse_kod} Özel Asistanı")
                st.markdown("Bana hissenin güncel temel verileri, pahalılığı veya teknik durumu hakkında sorular sorabilirsin.")
                kullanici_sorusu = st.text_input("Vader'a Sor:", placeholder="Örn: Bu hisse alınır mı?")
                if st.button("Analiz Et"):
                    if kullanici_sorusu:
                        s = kullanici_sorusu.lower()
                        cevap = f"**Vader'ın {hisse_kod} Analizi:**\n\n"
                        if any(x in s for x in ['pahalı', 'ucuz', 'alınır', 'değer', 'f/k']):
                            fk = bilgi.get('trailingPE', 0)
                            pd_dd = bilgi.get('priceToBook', 0)
                            if fk > 0:
                                if fk < 10: cevap += f"- F/K oranı {fk:.2f} seviyesinde. Şirket piyasada **ucuz** (iskontolu) fiyatlanıyor.\n"
                                elif fk > 25: cevap += f"- F/K oranı {fk:.2f} ile yüksek. Piyasa aşırı beklenti yüklemiş, **pahalı** görünüyor.\n"
                                else: cevap += f"- F/K oranı {fk:.2f} ile makul seviyelerde, ederi civarında.\n"
                            if pd_dd > 0: cevap += f"- PD/DD oranı {pd_dd:.2f}. Defter değerinin yaklaşık {int(pd_dd)} katından işlem görüyor.\n"
                        elif any(x in s for x in ['teknik', 'rsi', 'grafik', 'macd']):
                            cevap += f"- Teknik tarafta hissenin RSI puanı **{anlik_rsi:.2f}**.\n"
                            if anlik_rsi > 70: cevap += "- 🚨 Aşırı Alım bölgesinde! Piyasada FOMO var, bir düzeltme gelebilir.\n"
                            elif anlik_rsi < 30: cevap += "- 🟢 Aşırı Satım bölgesinde! Herkes satmış, hisse dip arayışında olabilir.\n"
                            else: cevap += "- ⚪ Hisse şu an nötr bölgede, stabil bir trend izliyor.\n"
                        elif any(x in s for x in ['borç', 'sağlık', 'iflas', 'nakit']):
                            cari = bilgi.get('currentRatio', 0)
                            if cari:
                                if cari >= 1.5: cevap += f"- Cari oran {cari:.2f}. Kısa vadeli borç ödeme gücü yüksek. **Sağlığı güçlü.**\n"
                                else: cevap += f"- Dikkat! Cari oran {cari:.2f}. Kısa vadeli borç ödemeleri nakdini zorlayabilir.\n"
                        else:
                            cevap += "Sorun temel algoritmamın dışında. Lütfen 'Pahalı mı?' veya 'RSI nasıl?' gibi spesifik sorular sor."
                        st.info(cevap)

        else:
            st.error("Hisse verisi çekilemedi. Hatalı kod girdiniz veya Yahoo kısıtlaması devam ediyor.")
    except Exception as e:
        st.error(f"Sistem Hatası: {e}")
    footer_ekle()

# ==========================================
# SAYFA: RAKİP ANALİZİ
# ==========================================
elif sayfa == "⚔️ Rakip Analizi (Karşılaştırma)":
    st.title("⚔️ Sektörel Çarpışma: Rakip Analizi")
    st.markdown("İki farklı şirketi aynı ringe çıkarın ve finansal/teknik durumlarını karşılaştırın.")
    
    colA, colB = st.columns(2)
    with colA: h1 = st.text_input("1. Hisse (Örn: FROTO):", "FROTO").upper()
    with colB: h2 = st.text_input("2. Hisse (Örn: TOASO):", "TOASO").upper()
    
    if st.button("Çarpıştır ⚡"):
        try:
            b1, d1, _, _, _, _ = veri_motoru(h1 + ".IS", "1y", "1d")
            b2, d2, _, _, _, _ = veri_motoru(h2 + ".IS", "1y", "1d")
            
            if not d1.empty and not d2.empty:
                st.subheader("📊 Temel Veri Karşılaştırması")
                comp_data = {
                    "Metrik": ["Anlık Fiyat", "Piyasa Değeri", "F/K Oranı (Değerleme)", "PD/DD", "Kar Marjı"],
                    h1: [
                        f"₺{b1.get('currentPrice', d1['Close'].iloc[-1]):,.2f}", rakam_formatla(b1.get('marketCap', 0)),
                        round(b1.get('trailingPE', 0), 2) if b1.get('trailingPE') else "Yok",
                        round(b1.get('priceToBook', 0), 2) if b1.get('priceToBook') else "Yok",
                        f"%{round(b1.get('profitMargins', 0)*100, 2)}" if b1.get('profitMargins') else "Yok"
                    ],
                    h2: [
                        f"₺{b2.get('currentPrice', d2['Close'].iloc[-1]):,.2f}", rakam_formatla(b2.get('marketCap', 0)),
                        round(b2.get('trailingPE', 0), 2) if b2.get('trailingPE') else "Yok",
                        round(b2.get('priceToBook', 0), 2) if b2.get('priceToBook') else "Yok",
                        f"%{round(b2.get('profitMargins', 0)*100, 2)}" if b2.get('profitMargins') else "Yok"
                    ]
                }
                st.table(pd.DataFrame(comp_data).set_index("Metrik"))
                
                st.subheader("📈 Performans Çarpışması (Son 1 Yıl Normalize Getiri)")
                d1['Normalize'] = (d1['Close'] / d1['Close'].iloc[0] - 1) * 100
                d2['Normalize'] = (d2['Close'] / d2['Close'].iloc[0] - 1) * 100
                
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Scatter(x=d1.index, y=d1['Normalize'], name=h1, line=dict(color='#00FFCC', width=2)))
                fig_comp.add_trace(go.Scatter(x=d2.index, y=d2['Normalize'], name=h2, line=dict(color='orange', width=2)))
                fig_comp.update_layout(template="plotly_dark", height=400, yaxis_title="Getiri (%)", hovermode="x unified")
                st.plotly_chart(fig_comp, use_container_width=True)
            else:
                st.error("Hisselerden birinin veya ikisinin verisi çekilemedi.")
        except Exception as e:
            st.error("Çarpıştırma sırasında hata oluştu. Hisselerin doğru yazıldığından emin olun.")
    footer_ekle()

# ==========================================
# SAYFA: PİYASA RADARI & ISI HARİTASI
# ==========================================
elif sayfa == "📡 Piyasa Radarı & Isı Haritası":
    st.title("🗺️ BİST Piyasa Isı Haritası & Radar")
    st.markdown("Piyasaya yukarıdan bakın. Yeşil kutular yükselişi, kırmızı kutular düşüşü temsil eder.")
    
    radar_listesi = ["THYAO.IS", "SASA.IS", "EREGL.IS", "TUPRS.IS", "FROTO.IS", "KCHOL.IS", "AKBNK.IS", "ISCTR.IS", "ASELS.IS", "BIMAS.IS", "GARAN.IS", "SISE.IS", "ENKAI.IS", "TCELL.IS"]
    
    if st.button("🚀 Haritayı & Radarı Çalıştır"):
        with st.spinner("Piyasa röntgeni çekiliyor, veriler yükleniyor..."):
            harita_datalari = []
            for sembol in radar_listesi:
                try:
                    df = yf.Ticker(sembol).history(period="5d")
                    if len(df) >= 2:
                        son = df['Close'].iloc[-1]
                        eski = df['Close'].iloc[-2]
                        yuzde = ((son - eski) / eski) * 100
                        hacim = df['Volume'].iloc[-1]
                        
                        harita_datalari.append({
                            "Hisse": sembol.replace(".IS", ""), "Degisim": round(yuzde, 2),
                            "Hacim": hacim, "Fiyat": round(son, 2), "Grup": "BİST Demirbaş"
                        })
                except: pass
            
            if harita_datalari:
                df_hm = pd.DataFrame(harita_datalari)
                
                fig_hm = px.treemap(
                    df_hm, path=['Grup', 'Hisse'], values='Hacim',
                    color='Degisim', color_continuous_scale='RdYlGn',
                    color_continuous_midpoint=0,
                    custom_data=['Fiyat', 'Degisim']
                )
                fig_hm.update_traces(texttemplate="<b>%{label}</b><br>₺%{customdata[0]}<br>%{customdata[1]:.2f}%", textposition="middle center")
                fig_hm.update_layout(template="plotly_dark", height=600, margin=dict(t=10, l=10, r=10, b=10))
                st.plotly_chart(fig_hm, use_container_width=True)
                
                st.markdown("### 📋 Sayısal Radar Tablosu")
                st.dataframe(df_hm.sort_values(by="Degisim", ascending=False), use_container_width=True)
            else:
                st.error("Veri çekilemedi. Yahoo kısıtlaması var.")
    footer_ekle()


# ==========================================
# SAYFA 3: PORTFÖYÜM & YAPAY ZEKA RÖNTGENİ
# ==========================================
elif sayfa == "💼 Portföyüm & Yapay Zeka Röntgeni":
    st.title("💼 Şahsi Bulut Portföyünüz")
    if st.session_state.kullanici is None: st.warning("Bu sayfayı görüntülemek için giriş yapmalısınız.")
    else:
        with st.expander("➕ Portföye Yeni Hisse Ekle", expanded=False):
            with st.form("hisse_ekle_form"):
                yeni_kod = st.text_input("Hisse Kodu (Örn: SASA):").upper()
                yeni_maliyet = st.number_input("Maliyet (TL)", min_value=0.0, step=1.0)
                yeni_lot = st.number_input("Adet (Lot)", min_value=1, step=1)
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
                
                toplam_maliyet_genel = 0
                toplam_guncel_genel = 0
                toplam_temettu = 0 
                pasta_etiketler = []
                pasta_degerler = []
                gecerli_veriler = []

                for index, row in df_port.iterrows():
                    try:
                        h = yf.Ticker(row['hisse_kod'] + ".IS")
                        anlik_fiyat = h.history(period="5d")['Close'].iloc[-1]
                        
                        try:
                            div_yield = h.info.get('dividendYield', 0)
                            if div_yield:
                                tahmini_yillik_temettu = (anlik_fiyat * div_yield) * row['lot']
                                toplam_temettu += tahmini_yillik_temettu
                        except: pass

                        guncel_deger = anlik_fiyat * row['lot']
                        toplam_maliyet = row['maliyet'] * row['lot']
                        kar = guncel_deger - toplam_maliyet
                        kar_yuzde = (kar / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
                        
                        toplam_maliyet_genel += toplam_maliyet
                        toplam_guncel_genel += guncel_deger
                        
                        pasta_etiketler.append(row['hisse_kod'])
                        pasta_degerler.append(guncel_deger)
                        
                        gecerli_veriler.append({
                            'id': row['id'], 'hisse_kod': row['hisse_kod'], 'maliyet': row['maliyet'],
                            'lot': row['lot'], 'guncel_deger': guncel_deger, 'kar': kar, 'kar_yuzde': kar_yuzde
                        })
                    except: pass
                
                if gecerli_veriler:
                    st.markdown("---")
                    ozet_col, pie_col = st.columns([1, 1.5])
                    
                    with ozet_col:
                        st.markdown("### 💰 Toplam Portföy Durumu")
                        toplam_kar_genel = toplam_guncel_genel - toplam_maliyet_genel
                        toplam_kar_yuzde = (toplam_kar_genel / toplam_maliyet_genel) * 100 if toplam_maliyet_genel > 0 else 0
                        st.metric("Toplam Yatırım Maliyeti", f"₺{toplam_maliyet_genel:,.2f}")
                        st.metric("Toplam Güncel Bakiye", f"₺{toplam_guncel_genel:,.2f}")
                        st.metric("Total Net Kâr / Zarar", f"{toplam_kar_genel:+,.2f} TL ({toplam_kar_yuzde:+.2f}%)")
                        
                        st.markdown("---")
                        st.markdown("### 💸 Temettü (Pasif Gelir) Simülatörü")
                        st.success(f"Portföyünüzün Şirketlerden Alacağı Tahmini Yıllık Pasif Gelir: **₺{toplam_temettu:,.2f}**")
                        st.caption("*Not: Şirketlerin güncel temettü verimliliğine göre kabaca simüle edilmiştir.*")

                    with pie_col:
                        fig_pie = go.Figure(data=[go.Pie(labels=pasta_etiketler, values=pasta_degerler, hole=.4, textinfo='label+percent', marker=dict(line=dict(color='#000000', width=2)))])
                        fig_pie.update_layout(title_text="💼 Varlık Dağılımı (Çember Grafik)", template="plotly_dark", height=350, margin=dict(t=40, b=10, l=10, r=10))
                        st.plotly_chart(fig_pie, use_container_width=True)
                    
                    st.markdown("---")
                    st.subheader("🧠 Vader Portföy Röntgeni")
                    if len(pasta_etiketler) <= 2:
                        st.warning("⚠️ **Risk Uyarısı:** Portföyündeki hisse sayısı çok az. Tüm yumurtaları aynı sepete koymuşsun. Olası bir şirket veya sektör krizinde sermayen büyük yara alabilir. Çeşitliliği artırmanı öneririm.")
                    else:
                        st.info(f"✅ **Dağılım Başarılı:** Sepetinde toplam {len(pasta_etiketler)} farklı varlık var. Bu, riskin dağıtıldığı anlamına gelir.")
                    
                    en_buyuk_index = np.argmax(pasta_degerler)
                    st.write(f"- Portföyünün en büyük ağırlığı **%{ (pasta_degerler[en_buyuk_index] / sum(pasta_degerler)) * 100 :.1f}** ile **{pasta_etiketler[en_buyuk_index]}** hissesinde.")
                    
                    if toplam_kar_genel > 0:
                        st.write("- 🟢 Genel olarak yatırım stratejin **kârlı** ilerliyor. Temel hedefin bu yeşil tabloyu korumak olmalı.")
                    else:
                        st.write("- 🔴 Genel portföy şu an **zararda**. Maliyet düşürmek için ekleme yapabilir veya stop-loss (zarar kes) seviyelerini gözden geçirebilirsin.")

                    st.markdown("---")
                    st.markdown("### 📋 Varlık Detayları")
                    for varlik in gecerli_veriler:
                        c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 2.5, 1])
                        c1.write(f"**{varlik['hisse_kod']}**")
                        c2.write(f"Maliyet: ₺{varlik['maliyet']:,.2f}")
                        c3.write(f"Lot: {varlik['lot']}")
                        c4.metric("Güncel Değer & Kar", f"₺{varlik['guncel_deger']:,.2f}", f"{varlik['kar']:+,.2f} TL ({varlik['kar_yuzde']:+.2f}%)")
                        if c5.button("Sil", key=f"del_{varlik['id']}"):
                            supabase.table("portfoyler").delete().eq("id", varlik['id']).execute()
                            st.rerun()
                        st.markdown("---")
            else: st.info("Portföy boş.")
        except Exception as e: st.error(f"Hata: {e}")
            
    footer_ekle()

elif sayfa == "📩 Hakkımda & İletişim":
    st.title("👨‍💻 Geliştirici Hakkında")
    st.markdown(f"""
    **Vader Analiz Terminali**, Bursa Uludağ Üniversitesi İİBF öğrencisi **Yunus Emre Eriş** tarafından geliştirilmiş profesyonel bir borsa analiz projesidir.
    
    ### Vizyonumuz
    Borsa İstanbul yatırımcılarına şeffaf, hızlı ve yapay zeka destekli analiz araçları sunarak finansal okuryazarlığı artırmak.
    
    ### İletişim & İş Birliği
    Reklam, sponsorluk veya teknik destek için:
    - **E-posta:** yunusemreeris787@gmail.com
    """)
    footer_ekle()
