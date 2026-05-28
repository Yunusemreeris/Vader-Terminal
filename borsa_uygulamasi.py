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
import asyncio
import os

# Yeni Nesil Ultra Gerçekçi Ses Motoru Kalkanı
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

# --- 1. SİTE KONFİGÜRASYONU VE GÜVENLİK KALKANI ---
st.set_page_config(page_title="Vader Analiz Terminali", layout="wide", initial_sidebar_state="expanded")

gizleme_kodu = """
            <style>
            #MainMenu {visibility: hidden !important;}
            footer {visibility: hidden !important;}
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

# --- 4. YARDIMCI FONKSİYONLAR VE AI SKORLAMA ---
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

def gelismis_temel_analiz_skoru(info):
    skorlar = {'Değerleme': 5, 'Kârlılık': 5, 'Büyüme': 5, 'Sağlık': 5, 'Temettü': 5}
    
    fk = info.get('trailingPE')
    pddd = info.get('priceToBook')
    fk_puan, pddd_puan = 5, 5
    if fk: fk_puan = 10 if 0 < fk < 10 else (8 if 10 <= fk <= 15 else (5 if 15 < fk <= 25 else (0 if fk <= 0 else 2))) 
    if pddd: pddd_puan = 10 if 0 < pddd < 1.5 else (8 if 1.5 <= pddd <= 3 else (5 if 3 < pddd <= 6 else (0 if pddd <= 0 else 2)))
    skorlar['Değerleme'] = (fk_puan + pddd_puan) / 2

    roe = info.get('returnOnEquity')
    marj = info.get('profitMargins')
    roe_puan, marj_puan = 5, 5
    if roe: roe_puan = 10 if roe > 0.20 else (8 if roe > 0.10 else (4 if roe > 0 else 0))
    if marj: marj_puan = 10 if marj > 0.15 else (8 if marj > 0.05 else (4 if marj > 0 else 0))
    skorlar['Kârlılık'] = (roe_puan + marj_puan) / 2

    cb = info.get('revenueGrowth')
    kb = info.get('earningsGrowth')
    cb_puan, kb_puan = 5, 5
    if cb: cb_puan = 10 if cb > 0.20 else (8 if cb > 0.05 else (4 if cb > -0.05 else 0))
    if kb: kb_puan = 10 if kb > 0.20 else (8 if kb > 0.05 else (4 if kb > -0.05 else 0))
    skorlar['Büyüme'] = (cb_puan + kb_puan) / 2

    co = info.get('currentRatio')
    bo = info.get('debtToEquity')
    co_puan, bo_puan = 5, 5
    if co: co_puan = 10 if co > 1.5 else (7 if co > 1.0 else 2)
    if bo: bo_puan = 10 if bo < 50 else (7 if bo < 100 else 2) 
    skorlar['Sağlık'] = (co_puan + bo_puan) / 2

    div = info.get('dividendYield')
    if div: skorlar['Temettü'] = 10 if div > 0.04 else (8 if div > 0.02 else (5 if div > 0 else 2))
    else: skorlar['Temettü'] = 2 

    genel_skor = sum(skorlar.values()) / len(skorlar)
    return skorlar, genel_skor

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

@st.cache_data(ttl=60) 
def genel_piyasa_haberleri():
    haberler = []
    try:
        url = "https://news.google.com/rss/search?q=borsa+ekonomi+finans+hisse+when:1d&hl=tr&gl=TR&ceid=TR:tr"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        xml_data = urllib.request.urlopen(req).read()
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:15]: 
            haberler.append({
                'title': item.find('title').text, 
                'link': item.find('link').text, 
                'publisher': item.find('source').text if item.find('source') is not None else "Google Haberler", 
                'custom_time': item.find('pubDate').text
            })
    except: pass
    return haberler

@st.cache_data(ttl=30) 
def son_dakika_haberleri(sembol):
    haberler = []
    if ".IS" in sembol:
        try:
            arama_terimi = sembol.replace(".IS", "") + " hisse haber when:1d"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(arama_terimi)}&hl=tr&gl=TR&ceid=TR:tr"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
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
        <div class="footer">Bu belge otomatik üretilmiştir. Tarayıcınızda Ctrl+P yaparak PDF kaydedebilirsiniz.</div>
    </body></html>
    """
    b64 = base64.b64encode(html_icerik.encode()).decode()
    return f'<a href="data:text/html;base64,{b64}" download="VADER_Rapor_{hisse}.html" style="background-color:#00FFCC; color:black; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold;">📄 Raporu İndir (HTML/PDF)</a>'

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
    "📰 Piyasa Haberleri",
    "⏳ Zaman Makinesi (DCA)", 
    "⭐ İzleme Listem",
    "⚔️ Rakip Analizi",
    "📡 Piyasa Radarı & Yeni Nesil Eklentiler",
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
    st.warning("Temel analiz araçları tamamen ücretsizdir. Yapay zeka, Monte Carlo ve Şirket Skorlama özellikleri Premium Abonelik gerektirir.")
    footer_ekle()

# --- SAYFA: CANLI ANALİZ VE GELİŞMİŞ MONTE CARLO VE ŞİRKET KARNESİ ---
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
            
            def ai_teknik_yorum_fonk(df, rsi, macd, signal):
                yorumlar = []
                fiyat = df['Close'].iloc[-1]
                sma20 = df['Close'].rolling(20).mean().iloc[-1]
                sma50 = df['Close'].rolling(50).mean().iloc[-1]
                if fiyat > sma20 and fiyat > sma50: yorumlar.append("🟢 Güçlü Yükseliş Trendi.")
                elif fiyat < sma20 and fiyat < sma50: yorumlar.append("🔴 Güçlü Düşüş Trendi.")
                else: yorumlar.append("🟡 Yatay Seyir (Konsolidasyon).")
                return yorumlar
                
            ai_yorum_listesi = ai_teknik_yorum_fonk(df, anlik_rsi, anlik_macd, anlik_signal)
            
            c_h, c_r = st.columns([3, 1])
            with c_r:
                st.markdown(rapor_olustur_html(hisse_kod, fiyat, yuzde, anlik_rsi, ai_yorum_listesi), unsafe_allow_html=True)

            m1, m2, m3, m4 = st.columns(4)
            para_birimi = "₺" if ".IS" in sembol else "$"
            m1.metric("Anlık Fiyat", f"{para_birimi}{fiyat:,.2f}", f"{degisim:+.2f} ({yuzde:+.2f}%)")
            m2.metric("Günlük Hacim", f"{int(df['Volume'].iloc[-1]):,}")
            m3.metric("Haftalık Getiri", f"%{haftalik_getiri:.2f}", "Teknik Veri")
            m4.metric("Üyelik Seviyesi", "💎 Premium" if is_premium else "👤 Ücretsiz")

            t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(["📈 Teknik Grafikler", "⚙️ Al-Sat Sinyalleri", "🤖 AI Teknik Röntgen", "🔮 Pro Simülasyon 💎", "📰 Haberler", "📑 Finansallar", "💬 Vader AI", "🕸️ Şirket Karnesi (Skor) 💎"])
            
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
                st.subheader("🔮 Gelişmiş Pro Monte Carlo Simülasyonu")
                if is_premium:
                    st.markdown("Geometrik Brownian Hareketi (GBM) ile binlerce farklı paralel evren yaratarak gelecekteki olası fiyat dağılımını hesaplar.")
                    c_m1, c_m2 = st.columns(2)
                    mc_gun = c_m1.slider("Simülasyon Süresi (Gün):", min_value=10, max_value=365, value=30, step=10)
                    mc_senaryo = c_m2.selectbox("Senaryo (Paralel Evren) Sayısı:", [100, 500, 1000, 5000], index=2)
                    
                    if st.button("🚀 Monte Carlo'yu Çalıştır"):
                        with st.spinner(f"Vader {mc_senaryo} farklı senaryo hesaplıyor..."):
                            log_returns = np.log(1 + df['Close'].pct_change()).dropna()
                            u, var, stdev = log_returns.mean(), log_returns.var(), log_returns.std()
                            drift = u - (0.5 * var)
                            
                            sims = np.zeros((mc_gun, mc_senaryo))
                            sims[0] = fiyat
                            np.random.seed(42)
                            
                            for t in range(1, mc_gun): 
                                sims[t] = sims[t - 1] * np.exp(drift + stdev * np.random.standard_normal(mc_senaryo))
                            
                            med = np.percentile(sims, 50, axis=1)
                            iyi = np.percentile(sims, 95, axis=1)
                            kotu = np.percentile(sims, 5, axis=1)
                            tarihler = pd.date_range(start=df.index[-1] + timedelta(days=1), periods=mc_gun)
                            
                            fig_mc = go.Figure()
                            for i in range(min(20, mc_senaryo)):
                                fig_mc.add_trace(go.Scatter(x=tarihler, y=sims[:, i], line=dict(color='rgba(255,255,255,0.05)', width=1), showlegend=False))
                                
                            fig_mc.add_trace(go.Scatter(x=df.index[-60:], y=df['Close'].iloc[-60:], line=dict(color='gray', width=2), name='Gerçek Geçmiş'))
                            fig_mc.add_trace(go.Scatter(x=tarihler, y=iyi, line=dict(color='rgba(0, 255, 0, 0.6)', dash='dot', width=2), name='%95 İyimser Zirve'))
                            fig_mc.add_trace(go.Scatter(x=tarihler, y=kotu, fill='tonexty', fillcolor='rgba(128,128,128,0.1)', line=dict(color='rgba(255, 0, 0, 0.6)', dash='dot', width=2), name='%5 Kötümser Dip (VaR)'))
                            fig_mc.add_trace(go.Scatter(x=tarihler, y=med, line=dict(color='#00FFCC', width=3), name='Beklenen Medyan Rota'))
                            fig_mc.update_layout(template=tema, height=450, hovermode="x unified", title=f"{mc_gun} Günlük Gelecek Projeksiyonu")
                            st.plotly_chart(fig_mc, use_container_width=True)
                            
                            son_gun_fiyatlari = sims[-1, :]
                            beklenen_fiyat = np.median(son_gun_fiyatlari)
                            var_95 = np.percentile(son_gun_fiyatlari, 5)
                            maks_potansiyel = np.max(son_gun_fiyatlari)
                            
                            st.markdown("### 📊 Simülasyon İstatistikleri")
                            col_s1, col_s2, col_s3 = st.columns(3)
                            col_s1.metric(f"{mc_gun} Gün Sonrası Beklenen (Medyan)", f"{para_birimi}{beklenen_fiyat:,.2f}", f"{(beklenen_fiyat-fiyat)/fiyat*100:+.2f}%")
                            col_s2.metric("Maksimum Görülen Zirve", f"{para_birimi}{maks_potansiyel:,.2f}", "Uç Senaryo")
                            col_s3.metric("Riske Maruz Değer (VaR %5)", f"{para_birimi}{var_95:,.2f}", "Kötü Senaryo Dibi", delta_color="inverse")
                            st.info(f"💡 **Fon Yöneticisi Özeti:** {mc_gun} gün sonra paranızın {para_birimi}{var_95:,.2f} seviyesinin altına düşme ihtimali sadece %5'tir. En olası hedef fiyat ise {para_birimi}{beklenen_fiyat:,.2f} olarak hesaplanmıştır.")
                else: st.error("🔒 Kurumsal Seviye Monte Carlo özelliği sadece Premium Abonelere özeldir.")

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
                        y_v = h.get('custom_time', datetime.fromtimestamp(h.get('providerPublishTime', 0)).strftime('%d.%m.%Y %H:%M') if h.get('providerPublishTime') else "Yeni")
                        with st.expander(f"{duygu_analizi(b)} | {b}"):
                            st.write(f"**Kaynak:** {h.get('publisher', 'Bilinmeyen')} | **Tarih:** {y_v}")
                            st.write(f"[Haberi Oku]({h.get('link', '#')})")
                else: st.info("Son 24 saat içinde bu varlık için önemli bir haber düşmedi.")

            with t6:
                st.subheader("📑 Finansal Tablolar ve Bilanço")
                tablo_secim = st.radio("İncelemek İstediğiniz Tabloyu Seçin:", ["Yıllık Bilanço", "Dönem İçi (Çeyreklik)", "Gelir Tablosu"], horizontal=True)
                aktif_t = bilanco if tablo_secim == "Yıllık Bilanço" else (ceyreklik_bilanco if tablo_secim == "Dönem İçi (Çeyreklik)" else gelir)
                if not aktif_t.empty:
                    aktif_t.columns = [str(col).split()[0] for col in aktif_t.columns]
                    try: st.dataframe(aktif_t.map(rakam_formatla), use_container_width=True)
                    except AttributeError: st.dataframe(aktif_t.applymap(rakam_formatla), use_container_width=True)
                else: st.warning("⚠️ Finansal veriler Yahoo Finance tarafından anlık olarak gizlenmiş olabilir.")

            with t7: 
                st.subheader(f"🧠 Vader AI - {hisse_kod} Özel Asistanı")
                st.markdown("Bana hissenin güncel durumu hakkında teknik sorular sorabilirsin.")
                k_s = st.text_input("Vader'a Sor:", placeholder="Örn: Bu hissenin grafiği nasıl, yönü ne?")
                if st.button("Analiz Et"):
                    cevap = f"**Vader'ın Teknik Analizi:**\n\n- Hissenin anlık RSI puanı **{anlik_rsi:.2f}**.\n"
                    cevap += "- 🚨 Aşırı Alım bölgesinde! Riskli.\n" if anlik_rsi > 70 else ("- 🟢 Aşırı Satım bölgesinde! Ucuz.\n" if anlik_rsi < 30 else "- ⚪ Hisse şu an nötr bölgede.\n")
                    cevap += "- Kısa vadeli MACD sinyali AL veriyor.\n" if anlik_macd > anlik_signal else "- Kısa vadeli MACD sinyali SAT veriyor.\n"
                    st.info(cevap)

            # --- YENİ EKLENTİ: ŞİRKET KARNESİ (SKORLAMA RADARI) ---
            with t8:
                st.subheader("🕸️ Vader AI Şirket Karnesi")
                if is_premium:
                    st.markdown("Şirketin değerleme, kârlılık, büyüme, finansal sağlık ve temettü verilerini inceler. **Kusursuz şirket 10 üzerinden 10 alır.**")
                    with st.spinner("Bilanço taranıyor, mali tablolar analiz ediliyor..."):
                        skor_dict, genel_skor = gelismis_temel_analiz_skoru(info)
                        
                        col_k1, col_k2 = st.columns([1, 2])
                        with col_k1:
                            st.markdown(f"### Genel Skor: **{genel_skor}/10**")
                            if genel_skor >= 8: st.success("🟢 Güçlü Temel! Uzun vade için oldukça güvenli bir liman.")
                            elif genel_skor >= 6: st.info("🟡 Kabul Edilebilir. Kendi sektörüne göre incelenmeli.")
                            else: st.error("🔴 Zayıf Temel! Temel verilerde ciddi kırmızı bayraklar var.")
                            
                            st.markdown("---")
                            for metrik, puan in skor_dict.items():
                                st.write(f"**{metrik}:** {puan}/10")
                                
                        with col_k2:
                            fig_radar = go.Figure(data=go.Scatterpolar(
                                r=list(skor_dict.values()),
                                theta=list(skor_dict.keys()),
                                fill='toself',
                                marker=dict(color='#00FFCC'),
                                line=dict(color='#00FFCC')
                            ))
                            fig_radar.update_layout(
                                polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
                                showlegend=False,
                                template="plotly_dark",
                                height=400,
                                margin=dict(l=40, r=40, t=20, b=20)
                            )
                            st.plotly_chart(fig_radar, use_container_width=True)
                            
                        st.info("💡 **Not:** Puanlamada negatif büyüme veya eksi (-F/K) durumları acımasızca **0** ile cezalandırılır. Grafiğin merkeze çöktüğü alanlar şirketin en zayıf karnıdır.")
                else: st.error("🔒 Yapay Zeka Şirket Skorlama özelliği sadece Premium Abonelere özeldir.")

        else: st.error("Veri çekilemedi. Hatalı kod girdiniz veya Yahoo kısıtlaması var.")
    except Exception as e: st.error(f"Sistem Hatası: {e}")
    footer_ekle()

# --- YENİ SAYFA: ZAMAN MAKİNESİ (DCA SİMÜLATÖRÜ) ---
elif sayfa == "⏳ Zaman Makinesi (DCA)":
    st.title("⏳ Zaman Makinesi (DCA Simülatörü)")
    st.markdown("Geçmişte yatırım yapsaydınız bugün neyiniz olurdu? Düzenli alım (Dolar/Maliyet Ortalaması) gücünü test edin.")
    
    col1, col2, col3 = st.columns(3)
    dca_sembol = col1.text_input("Hisse Sembolü (Örn: THYAO.IS, BTC-USD):", "THYAO.IS").upper()
    dca_aylik_miktar = col2.number_input("Aylık Yatırım Miktarı:", min_value=100.0, value=1000.0, step=100.0)
    dca_yil = col3.selectbox("Kaç Yıl Önce Başladınız?", [1, 2, 3, 5, 10], index=2)
    
    if st.button("⏳ Simülasyonu Başlat"):
        with st.spinner("Zaman makinesi geçmişe gidiyor..."):
            try:
                # Geçmiş veriyi çek
                df_dca = yf.Ticker(dca_sembol).history(period=f"{dca_yil}y")
                if not df_dca.empty and len(df_dca) > 20:
                    # Aylık ilk işlem günlerini bul
                    df_aylik = df_dca.resample('MS').first().dropna()
                    
                    df_aylik['Yatirilan_Miktar'] = dca_aylik_miktar
                    df_aylik['Alinan_Lot'] = df_aylik['Yatirilan_Miktar'] / df_aylik['Close']
                    df_aylik['Kumbara_Lot'] = df_aylik['Alinan_Lot'].cumsum()
                    df_aylik['Toplam_Maliyet'] = df_aylik['Yatirilan_Miktar'].cumsum()
                    df_aylik['Guncel_Portfoy_Degeri'] = df_aylik['Kumbara_Lot'] * df_aylik['Close']
                    
                    toplam_yatirilan = df_aylik['Toplam_Maliyet'].iloc[-1]
                    son_deger = df_aylik['Guncel_Portfoy_Degeri'].iloc[-1]
                    net_kar = son_deger - toplam_yatirilan
                    kar_orani = (net_kar / toplam_yatirilan) * 100
                    
                    st.markdown("### 📈 Simülasyon Sonuçları")
                    c_s1, c_s2, c_s3 = st.columns(3)
                    para_b = "₺" if ".IS" in dca_sembol else "$"
                    c_s1.metric("Cebinizden Çıkan Toplam Para", f"{para_b}{toplam_yatirilan:,.2f}")
                    c_s2.metric("Portföyün Bugünkü Değeri", f"{para_b}{son_deger:,.2f}", f"%{kar_orani:,.2f} Getiri")
                    c_s3.metric("Net Kâr", f"{para_b}{net_kar:,.2f}")
                    
                    # Grafiği Çiz
                    fig_dca = go.Figure()
                    fig_dca.add_trace(go.Scatter(x=df_aylik.index, y=df_aylik['Toplam_Maliyet'], line=dict(color='gray', width=2, dash='dash'), name='Toplam Yatırılan Para'))
                    fig_dca.add_trace(go.Scatter(x=df_aylik.index, y=df_aylik['Guncel_Portfoy_Degeri'], line=dict(color='#00FFCC', width=3), fill='tozeroy', fillcolor='rgba(0, 255, 204, 0.1)', name='Portföy Değeri'))
                    fig_dca.update_layout(template="plotly_dark", height=450, hovermode="x unified", title=f"{dca_yil} Yıllık Düzenli Alım Büyümesi")
                    st.plotly_chart(fig_dca, use_container_width=True)
                    
                    st.info("💡 **DCA (Dollar Cost Averaging) Mantığı:** Düşüşlerde daha fazla lot alarak maliyetinizi düşürdünüz. Borsa düşse bile düzenli alım uzun vadede kazanır.")
                else:
                    st.error("Bu sembol için yeterli geçmiş veri bulunamadı.")
            except Exception as e:
                st.error(f"Simülasyon hatası: {e}")
    footer_ekle()

# --- SAYFA: PİYASA HABERLERİ & DİNAMİK SESLİ BRİFİNG ---
elif sayfa == "📰 Piyasa Haberleri":
    st.title("📰 Piyasa Haber Merkezi & AI Brifing")
    st.markdown("Global piyasaların nabzını ve yapay zeka destekli güncel sesli özetleri takip edin.")
    
    tab_genel, tab_izleme, tab_podcast = st.tabs(["🌍 Genel Piyasa Gündemi", "⭐ İzleme Listem Haberleri", "🎧 Vader Sesli Brifing"])
    
    with tab_genel:
        c1, c2 = st.columns([4, 1])
        c1.subheader("Borsa, Ekonomi ve Finans")
        if c2.button("🔄 Gündemi Yenile", key="genel_h_yenile"):
            genel_piyasa_haberleri.clear()
            st.rerun()
            
        g_haberler = genel_piyasa_haberleri()
        if g_haberler:
            for h in g_haberler:
                with st.expander(f"📰 {h.get('title', 'Başlık Yok')}"):
                    st.write(f"**Kaynak:** {h.get('publisher', 'Bilinmeyen')} | **Tarih:** {h.get('custom_time', 'Yeni')}")
                    st.write(f"[Habere Git]({h.get('link', '#')})")
        else:
            st.info("Şu an genel piyasa haberi çekilemedi.")
            
    with tab_izleme:
        st.subheader("Sadece Takip Ettiğiniz Varlıkların Haberleri")
        if st.session_state.kullanici:
            try:
                liste = supabase.table("izleme_listesi").select("sembol").eq("user_id", st.session_state.user_id).execute()
                if liste.data:
                    if st.button("🔄 İzleme Haberlerini Yenile", key="izleme_h_yenile"):
                        son_dakika_haberleri.clear()
                        st.rerun()
                        
                    for kalem in liste.data:
                        s = kalem['sembol']
                        st.markdown(f"### 📌 {s} Analiz ve Gündem")
                        s_haberler = son_dakika_haberleri(s)
                        if s_haberler:
                            for h in s_haberler[:3]:
                                b = h.get('title', 'Başlık Yok')
                                y_v = h.get('custom_time', datetime.fromtimestamp(h.get('providerPublishTime', 0)).strftime('%d.%m.%Y %H:%M') if h.get('providerPublishTime') else "Yeni")
                                with st.expander(f"{duygu_analizi(b)} | {b}"):
                                    st.write(f"**Kaynak:** {h.get('publisher', 'Bilinmeyen')} | **Tarih:** {y_v}")
                                    st.write(f"[Haberi Oku]({h.get('link', '#')})")
                        else:
                            st.info(f"{s} için son 24 saatte yeni haber düşmedi.")
                        st.markdown("---")
                else:
                    st.warning("İzleme listeniz boş.")
            except Exception as e:
                st.error("Veritabanına bağlanılırken bir hata oluştu.")
        else:
            st.error("Giriş yapmalısınız.")
            
    with tab_podcast:
        st.subheader("🎧 Vader Günlük Sesli Piyasa Özeti")
        st.markdown("Yapay zeka; güncel haberleri ve piyasada en çok hareket eden TOP 10 hisseyi (5 Artan, 5 Düşen) sizin için derleyip okur.")
        
        if st.button("🎙️ Bugünkü Podcast'i Oluştur"):
            if not HAS_EDGE_TTS:
                st.error("⚠️ Ses motoru eksik! Lütfen GitHub'daki 'requirements.txt' dosyasına 'edge-tts' ekleyip kaydedin.")
            else:
                with st.spinner("Vader piyasayı tarayıp stüdyoya giriyor... (Veri çekimi 10-15 saniye sürebilir)"):
                    try:
                        g_haberler = genel_piyasa_haberleri()
                        haber_metni = "Bugün için önemli bir haber akışı bulunmuyor."
                        if g_haberler:
                            basliklar = [h.get('title', '').split(' - ')[0] for h in g_haberler[:4]]
                            haber_metni = "Günün öne çıkan önemli gelişmeleri şöyle. " + ". ".join(basliklar) + "."
                            
                        ana_hisseler = ["THYAO.IS", "SASA.IS", "EREGL.IS", "TUPRS.IS", "FROTO.IS", "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "KCHOL.IS", "SAHOL.IS", "ASELS.IS", "BIMAS.IS", "SISE.IS", "TOASO.IS", "PGSUS.IS", "ENKAI.IS", "GARAN.IS", "TCELL.IS", "KRDMD.IS", "PETKM.IS", "ASTOR.IS", "HEKTS.IS"]
                        degisimler = {}
                        
                        for s in ana_hisseler:
                            try:
                                hist = yf.Ticker(s).history(period="5d")
                                if len(hist) >= 2:
                                    son = float(hist['Close'].iloc[-1])
                                    eski = float(hist['Close'].iloc[-2])
                                    yuzde = ((son - eski) / eski) * 100
                                    degisimler[s.replace('.IS', '')] = yuzde
                            except: pass
                            
                        piyasa_metni = ""
                        if degisimler:
                            sirali = sorted(degisimler.items(), key=lambda x: x[1], reverse=True)
                            en_cok_artanlar = sirali[:5]
                            en_cok_dusenler = sirali[-5:]
                            
                            piyasa_metni = "Piyasada en çok dikkat çeken on hisseye gelirsek. En çok kazandıran beş hisse sırasıyla; "
                            for h, y in en_cok_artanlar:
                                piyasa_metni += f"yüzde {y:.1f} artışla {h}, "
                                
                            piyasa_metni += ". En çok kaybettiren beş hisse ise; "
                            for h, y in en_cok_dusenler:
                                piyasa_metni += f"yüzde {abs(y):.1f} düşüşle {h}, "
                                
                        metin = f"Vader analiz terminaline hoş geldiniz patron. {haber_metni} {piyasa_metni} Benim analizlerim şimdilik bu kadar. Lütfen risk yönetiminizi yapmayı unutmayın. Bol kazançlar dilerim."
                        
                        ses_dosyasi = "vader_brifing.mp3"
                        
                        async def ses_olustur():
                            communicate = edge_tts.Communicate(metin, "tr-TR-AhmetNeural", rate="+10%")
                            await communicate.save(ses_dosyasi)
                        
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(ses_olustur())
                        loop.close()
                        
                        st.audio(ses_dosyasi)
                        st.success("✅ Podcast hazır! Yukarıdaki oynatıcıdan dinleyebilirsiniz.")
                    except Exception as e:
                        st.error(f"Ses oluşturulurken hata: {e}")
            
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
                        son, eski = d['Close'].iloc[-1], d['Close'].iloc[-2]
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
                    else:
                        c1, c2 = st.columns([3, 1])
                        c1.warning(f"⚠️ **{s}** sembolü için veri alınamıyor (Borsa kapalı veya kod hatalı).")
                        if c2.button("❌ Hatalı Kodu Sil", key=f"delfav_hata_{s}"):
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
    colA, colB = st.columns(2)
    with colA: h1 = st.text_input("1. Varlık (Örn: FROTO.IS):", "FROTO.IS").upper()
    with colB: h2 = st.text_input("2. Varlık (Örn: TOASO.IS):", "TOASO.IS").upper()
    if st.button("Çarpıştır ⚡"):
        try:
            df1, _, _, _, _ = veri_motoru(h1, "1y", "1d")
            df2, _, _, _, _ = veri_motoru(h2, "1y", "1d")
            if not df1.empty and not df2.empty:
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
                
                df1['Normalize'] = (df1['Close'] / df1['Close'].iloc[0] - 1) * 100
                df2['Normalize'] = (df2['Close'] / df2['Close'].iloc[0] - 1) * 100
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Scatter(x=df1.index, y=df1['Normalize'], name=h1, line=dict(color='#00FFCC', width=2)))
                fig_comp.add_trace(go.Scatter(x=df2.index, y=df2['Normalize'], name=h2, line=dict(color='orange', width=2)))
                fig_comp.update_layout(template="plotly_dark", height=400, yaxis_title="Getiri (%)", hovermode="x unified")
                st.plotly_chart(fig_comp, use_container_width=True)
            else: st.error("Varlıklardan birinin verisi çekilemedi.")
        except: st.error("Hata oluştu.")
    footer_ekle()

# --- SAYFA: PİYASA RADARI ---
elif sayfa == "📡 Piyasa Radarı & Yeni Nesil Eklentiler":
    st.title("🗺️ Piyasa Radarı & Eklentiler")
    
    tab_harita, tab_balina, tab_duygu = st.tabs(["🗺️ Isı Haritası", "🐳 Balina Radarı", "🌡️ Piyasa Duygu Ölçer"])
    radar_listesi = ["THYAO.IS", "SASA.IS", "EREGL.IS", "TUPRS.IS", "FROTO.IS", "BTC-USD", "ETH-USD", "GC=F", "AAPL", "NVDA", "TSLA"]
    
    with tab_harita:
        st.markdown("Piyasanın genel durumunu ısı haritası üzerinde görselleştirin.")
        if st.button("🚀 Haritayı Çalıştır"):
            with st.spinner("Piyasa röntgeni çekiliyor..."):
                harita_datalari = []
                for sembol in radar_listesi:
                    try:
                        df = yf.Ticker(sembol).history(period="5d")
                        if len(df) >= 2:
                            son, eski = df['Close'].iloc[-1], df['Close'].iloc[-2]
                            harita_datalari.append({
                                "Hisse": sembol.replace(".IS", ""), "Degisim": round(((son - eski) / eski) * 100, 2),
                                "Hacim": df['Volume'].iloc[-1], "Fiyat": round(son, 2), 
                                "Grup": "Kripto" if "-USD" in sembol else ("ABD" if not ".IS" in sembol and "F" not in sembol else "BIST")
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

    with tab_balina:
        st.subheader("🐳 Balina Radarı (Anormal Hacim Avcısı)")
        st.markdown("Son 20 günlük ortalama işlem hacminin **1.5 katından fazla** işlem gören varlıkları tespit eder.")
        if st.button("🐳 Balinaları Tara"):
            with st.spinner("Derin denizler taranıyor, dev işlemler aranıyor..."):
                balinalar = []
                for s in radar_listesi:
                    try:
                        d = yf.Ticker(s).history(period="1mo")
                        if len(d) > 20:
                            avg_vol = d['Volume'].iloc[-21:-1].mean()
                            last_vol = d['Volume'].iloc[-1]
                            if last_vol > (avg_vol * 1.5): 
                                artise_orani = last_vol / avg_vol
                                balinalar.append({"Sembol": s, "Ortalama Hacim": int(avg_vol), "Son Hacim": int(last_vol), "Artış Çarpanı": f"{artise_orani:.1f}x"})
                    except: pass
                if balinalar:
                    st.success(f"{len(balinalar)} adet anormal hacim hareketi tespit edildi! Balinalar hareket halinde.")
                    st.table(pd.DataFrame(balinalar).set_index("Sembol"))
                else:
                    st.info("Şu an piyasada olağandışı bir balina hareketi tespit edilmedi.")

    with tab_duygu:
        st.subheader("🌡️ Piyasa Duygu Ölçer (Korku ve Açgözlülük)")
        st.markdown("Ana piyasa yapıcı varlıkların momentumu analiz edilerek **Korku** ve **Açgözlülük** endeksi hesaplanır.")
        if st.button("🌡️ Psikolojiyi Ölç"):
            with st.spinner("Yatırımcı psikolojisi analiz ediliyor..."):
                rsi_degerleri = []
                for s in ["THYAO.IS", "BTC-USD", "AAPL", "TUPRS.IS"]: 
                    try:
                        d = yf.Ticker(s).history(period="1mo")
                        if len(d) > 15:
                            delta = d['Close'].diff()
                            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                            rs = gain / loss
                            rsi = 100 - (100 / (1 + rs.iloc[-1]))
                            rsi_degerleri.append(rsi)
                    except: pass
                
                if rsi_degerleri:
                    avg_rsi = sum(rsi_degerleri) / len(rsi_degerleri)
                    fig_gauge = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = avg_rsi,
                        title = {'text': "Korku / Açgözlülük İbresi"},
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        gauge = {
                            'axis': {'range': [0, 100]},
                            'bar': {'color': "darkblue"},
                            'steps': [
                                {'range': [0, 40], 'color': "red"},
                                {'range': [40, 60], 'color': "yellow"},
                                {'range': [60, 100], 'color': "green"}],
                            'threshold' : {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': avg_rsi}
                        }
                    ))
                    fig_gauge.update_layout(template="plotly_dark", height=400)
                    st.plotly_chart(fig_gauge, use_container_width=True)
                    
                    if avg_rsi < 40: 
                        st.error("🚨 **Piyasa Durumu: AŞIRI KORKU**\nKanlı sokaklar... Büyük paranın dipten toplama alanı.")
                    elif avg_rsi > 60: 
                        st.success("🤑 **Piyasa Durumu: AŞIRI AÇGÖZLÜLÜK**\nZirve coşkusu hakim. Herkes alım yapıyor.")
                    else: 
                        st.warning("⚖️ **Piyasa Durumu: NÖTR**\nYatırımcılar yön arayışında.")
                else:
                    st.error("Duygu ölçer için yeterli veri alınamadı.")
    footer_ekle()

# --- SAYFA: PORTFÖYÜM & KORELASYON MATRİSİ ---
elif sayfa == "💼 Portföyüm":
    st.title("💼 Şahsi Bulut Portföyünüz")
    if st.session_state.kullanici is None: st.warning("Bu sayfayı görüntülemek için giriş yapmalısınız.")
    else:
        with st.expander("➕ Portföye Yeni Hisse Ekle", expanded=False):
            with st.form("hisse_ekle_form"):
                yeni_kod = st.text_input("Varlık Kodu (Örn: SASA.IS, AAPL):").upper()
                yeni_maliyet = st.number_input("Maliyet (Birim Fiyat)", min_value=0.0, step=1.0)
                yeni_lot = st.number_input("Adet (Lot)", min_value=1.0, step=0.1)
                if st.form_submit_button("Kaydet") and yeni_kod:
                    try:
                        supabase.table("portfoyler").insert({"user_id": st.session_state.user_id, "hisse_kod": yeni_kod, "maliyet": yeni_maliyet, "lot": yeni_lot}).execute()
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
                    
                    # --- PORTFÖY RİSK VE KORELASYON MATRİSİ ---
                    st.subheader("🕸️ Portföy Risk ve Korelasyon Matrisi")
                    benzersiz_hisseler = list(set(pasta_etiketler))
                    if is_premium:
                        if len(benzersiz_hisseler) > 1:
                            st.markdown("Sepetinizdeki varlıkların birbiriyle uyumunu ölçer. Korelasyon **1'e yaklaştıkça** hisseler aynı anda hareket eder (Yüksek risk). **0 veya eksi** değerler, portföyünüzün krizlere karşı daha dirençli olduğunu gösterir (Çeşitlendirme).")
                            with st.spinner("Korelasyon motoru çalışıyor..."):
                                dfs = []
                                valid_tickers = []
                                for t in benzersiz_hisseler:
                                    try:
                                        d = yf.Ticker(t).history(period="1y")['Close']
                                        if not d.empty:
                                            d.name = t
                                            dfs.append(d)
                                            valid_tickers.append(t)
                                    except: pass
                                
                                if len(dfs) > 1:
                                    port_df = pd.concat(dfs, axis=1).pct_change().dropna()
                                    corr_matrix = port_df.corr()
                                    fig_corr = px.imshow(corr_matrix, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                                    fig_corr.update_layout(template="plotly_dark", height=400)
                                    st.plotly_chart(fig_corr, use_container_width=True)
                                    
                                    yuksek_risk = False
                                    for i in range(len(corr_matrix.columns)):
                                        for j in range(i+1, len(corr_matrix.columns)):
                                            if corr_matrix.iloc[i, j] > 0.8: yuksek_risk = True
                                            
                                    if yuksek_risk:
                                        st.error("🚨 **Uyarı:** Portföyünüzdeki bazı hisseler birbiriyle çok yüksek korelasyona sahip (>0.80). Piyasada olası bir çöküşte hepsi aynı anda düşebilir. Farklı sektörler ekleyerek riskinizi dağıtmayı düşünebilirsiniz.")
                                    else:
                                        st.success("✅ **Harika:** Portföyünüz iyi çeşitlendirilmiş görünüyor. Risk dağılımınız sağlıklı.")
                        else:
                            st.warning("Korelasyon analizi yapabilmek için portföyünüzde en az 2 farklı varlık bulunmalıdır.")
                    else:
                        st.error("🔒 Yapay Zeka Korelasyon Matrisi sadece Premium Abonelere özeldir.")

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

# --- SAYFA: HESABIM & HAKKIMDA ---
elif sayfa == "👤 Hesabım":
    st.title("Profil ve Üyelik Yönetimi")
    if st.session_state.kullanici:
        st.markdown(f"**E-posta Adresi:** {st.session_state.kullanici}")
        st.markdown(f"**Mevcut Paket:** {'💎 Premium' if is_premium else '👤 Ücretsiz'}")
    else: st.warning("Giriş yapmalısınız.")
    footer_ekle()

elif sayfa == "📩 Hakkımda & İletişim":
    st.title("👨‍💻 Geliştirici Hakkında")
    st.markdown("**Vader Analiz Terminali**, Bursa Uludağ Üniversitesi İİBF öğrencisi **Yunus Emre Eriş** tarafından geliştirilmiştir.\n\nİletişim: yunusemreeris787@gmail.com")
    footer_ekle()
