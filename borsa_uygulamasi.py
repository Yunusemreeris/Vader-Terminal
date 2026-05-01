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
        <h1>🛸 VADER PRO - Teknik Analiz Raporu</h1>
        <div class="kutu">
            <h2>Hisse: {hisse}</h2>
            <p>Rapor Tarihi: {datetime.now().strftime("%d.%m.%Y %H:%M")}</p>
            <p>Anlık Fiyat: <span class="metrik">₺{fiyat:,.2f} ({degisim_yuzde:+.2f}%)</span></p>
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

# --- YENİ AI YORUM MOTORU (Sadece Teknik Verilere Bakar) ---
def ai_teknik_yorum(df, rsi, macd, signal):
    yorumlar = []
    fiyat = df['Close'].iloc[-1]
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    sma50 = df['Close'].rolling(50).mean().iloc[-1]

    if fiyat > sma20 and fiyat > sma50:
        yorumlar.append("🟢 **Trend Analizi:** Fiyat, hem 20 hem de 50 günlük hareketli ortalamalarının üzerinde. Güçlü bir Yükseliş Trendi (Boğa) hakim.")
    elif fiyat < sma20 and fiyat < sma50:
        yorumlar.append("🔴 **Trend Analizi:** Fiyat ortalamaların altında eziliyor. Güçlü bir Düşüş Trendi (Ayı) var.")
    else:
        yorumlar.append("🟡 **Trend Analizi:** Fiyat ortalamalar arasında sıkışmış. Yön arayışı sürüyor (Konsolidasyon).")

    if rsi > 70: yorumlar.append("🔴 **Momentum (RSI):** RSI 70'in üzerinde (Aşırı Alım). Piyasada FOMO var, düzeltme gelebilir.")
    elif rsi < 30: yorumlar.append("🟢 **Momentum (RSI):** RSI 30'un altında (Aşırı Satım). Hissede panik satışı olmuş, tepki fırsatı olabilir.")
    else: yorumlar.append("⚪ **Momentum (RSI):** RSI dengeli bir bölgede ilerliyor.")

    if macd > signal: yorumlar.append("🟢 **İvme (MACD):** MACD sinyal çizgisini yukarı kesmiş, kısa vadeli pozitif ivme var.")
    else: yorumlar.append("🔴 **İvme (MACD):** MACD sinyal çizgisinin altında, satış baskısı devam ediyor.")
    
    return yorumlar

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

@st.cache_data(ttl=300)
def veri_motoru(sembol, p="2y", i="1d"):
    # ARTIK SADECE ÇALIŞAN FIYAT VE HACİM VERİSİNİ ÇEKİYORUZ, BİLANÇO ZORLAMASI YOK!
    h = yf.Ticker(sembol)
    try: df = h.history(period=p, interval=i)
    except: df = pd.DataFrame()
    
    try: info = h.info
    except: info = {}
    
    return df, info

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
    return haberler

@st.cache_data(ttl=900)
def watchlist_verisi_getir(sembol):
    return yf.Ticker(sembol).history(period="5d")

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
        df, info = veri_motoru(sembol, p, i)
        haberler = son_dakika_haberleri(sembol)
        
        if not df.empty:
            fiyat = df['Close'].iloc[-1]
            onceki = df['Close'].iloc[-2] if len(df)>1 else fiyat
            degisim = fiyat - onceki
            yuzde = (degisim / onceki) * 100 if onceki > 0 else 0
            
            # TEKNİK METRİKLER (Yahoo kapatsa bile biz kendimiz hesaplıyoruz)
            haftalik_getiri = ((fiyat - df['Close'].iloc[-5]) / df['Close'].iloc[-5]) * 100 if len(df) >= 5 else 0
            aylik_getiri = ((fiyat - df['Close'].iloc[-20]) / df['Close'].iloc[-20]) * 100 if len(df) >= 20 else 0
            
            c_header, c_rapor = st.columns([3, 1])
            c_header.header(f"⚡ {info.get('longName', hisse_kod)}")
            
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
            
            with c_rapor:
                st.write("") 
                st.markdown(rapor_olustur_html(hisse_kod, fiyat, yuzde, anlik_rsi, ai_yorum_listesi), unsafe_allow_html=True)

            # EKSİKSİZ VE 100% ÇALIŞAN TEPELİK METRİKLER (Sayısal Analiz)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Anlık Fiyat", f"₺{fiyat:,.2f}", f"{degisim:+.2f} TL ({yuzde:+.2f}%)")
            m2.metric("Günlük Hacim", f"{int(df['Volume'].iloc[-1]):,}")
            m3.metric("Haftalık Getiri", f"%{haftalik_getiri:.2f}", "Teknik Veri")
            m4.metric("Aylık Getiri", f"%{aylik_getiri:.2f}", "Teknik Veri")

            t1, t2, t3, t4, t5, t6 = st.tabs(["📈 Teknik Grafikler", "⚙️ Al-Sat Sinyalleri", "🤖 AI Teknik Röntgen", "🔮 Gelecek Simülasyonu", "📰 Haberler", "💬 Vader AI"])
            
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

            with t3: # YEPYENİ 100% ÇALIŞAN TEKNİK ÖZET SEKMESİ
                for y in ai_yorum_listesi: st.write(y)
                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                
                zirve_52 = df['Close'].max()
                dip_52 = df['Close'].min()
                zirveye_uzaklik = ((fiyat - zirve_52) / zirve_52) * 100
                dibe_uzaklik = ((fiyat - dip_52) / dip_52) * 100
                
                c1.metric("Peryodun En Yüksek Fiyatı", f"₺{zirve_52:.2f}", f"Zirveye Uzaklık: %{zirveye_uzaklik:.2f}")
                c2.metric("Peryodun En Düşük Fiyatı", f"₺{dip_52:.2f}", f"Dipten Uzaklık: %{dibe_uzaklik:+.2f}")
                c3.metric("Anlık Volatilite (Standart Sapma)", f"₺{df['Close'].tail(20).std():.2f}")

            with t4: # MÜKEMMEL ÇALIŞAN MONTE CARLO
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
                st.subheader("🎯 Yatırım Zaman Makinesi")
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
                st.subheader(f"🧠 Vader AI - {hisse_kod} Özel Asistanı")
                st.markdown("Bana hissenin güncel durumu hakkında teknik sorular sorabilirsin.")
                kullanici_sorusu = st.text_input("Vader'a Sor:", placeholder="Örn: Bu hissenin grafiği nasıl, teknik yönü ne?")
                if st.button("Analiz Et"):
                    if kullanici_sorusu:
                        s = kullanici_sorusu.lower()
                        cevap = f"**Vader'ın {hisse_kod} Teknik Analizi:**\n\n"
                        if any(x in s for x in ['teknik', 'rsi', 'grafik', 'yön', 'alınır']):
                            cevap += f"- Hissenin anlık RSI puanı **{anlik_rsi:.2f}**.\n"
                            if anlik_rsi > 70: cevap += "- 🚨 Aşırı Alım bölgesinde! Teknik olarak riskli bölgede (Pahalı).\n"
                            elif anlik_rsi < 30: cevap += "- 🟢 Aşırı Satım bölgesinde! Dip seviyelerde geziniyor (Ucuz).\n"
                            else: cevap += "- ⚪ Hisse şu an nötr bölgede, stabil bir trend izliyor.\n"
                            
                            if anlik_macd > anlik_signal: cevap += "- Kısa vadeli MACD sinyali şu an AL veriyor, ivme yukarı yönlü.\n"
                            else: cevap += "- Kısa vadeli MACD sinyali SAT veriyor, düşüş baskısı var.\n"
                        else:
                            cevap += "Sorduğun soru temel algoritmamın dışında. Lütfen 'Hisse yönü ne?', 'Teknik durumu nasıl?' veya 'RSI kaç?' gibi sorular sor."
                        st.info(cevap)

        else:
            st.error("Hisse verisi çekilemedi. Hatalı kod girdiniz veya Yahoo kısıtlaması devam ediyor.")
    except Exception as e:
        st.error(f"Sistem Hatası: {e}")
    footer_ekle()

# ==========================================
# SAYFA: RAKİP ANALİZİ (YENİ TEKNİK KIYASLAMA)
# ==========================================
elif sayfa == "⚔️ Rakip Analizi (Karşılaştırma)":
    st.title("⚔️ Sektörel Çarpışma: Rakip Analizi")
    st.markdown("İki farklı şirketi aynı ringe çıkarın ve Teknik/Performans durumlarını karşılaştırın.")
    
    colA, colB = st.columns(2)
    with colA: h1 = st.text_input("1. Hisse (Örn: FROTO):", "FROTO").upper()
    with colB: h2 = st.text_input("2. Hisse (Örn: TOASO):", "TOASO").upper()
    
    if st.button("Çarpıştır ⚡"):
        try:
            df1, info1 = veri_motoru(h1 + ".IS", "1y", "1d")
            df2, info2 = veri_motoru(h2 + ".IS", "1y", "1d")
            
            if not df1.empty and not df2.empty:
                st.subheader("📊 Teknik Veri Karşılaştırması")
                
                # Sadece çalışan teknik ve getiri metriklerini kıyasla
                getiri_1y_1 = ((df1['Close'].iloc[-1] - df1['Close'].iloc[0]) / df1['Close'].iloc[0]) * 100
                getiri_1y_2 = ((df2['Close'].iloc[-1] - df2['Close'].iloc[0]) / df2['Close'].iloc[0]) * 100
                
                delta1 = df1['Close'].diff()
                rs1 = (delta1.where(delta1 > 0, 0)).rolling(window=14).mean() / (-delta1.where(delta1 < 0, 0)).rolling(window=14).mean()
                rsi1 = 100 - (100 / (1 + rs1.iloc[-1]))
                
                delta2 = df2['Close'].diff()
                rs2 = (delta2.where(delta2 > 0, 0)).rolling(window=14).mean() / (-delta2.where(delta2 < 0, 0)).rolling(window=14).mean()
                rsi2 = 100 - (100 / (1 + rs2.iloc[-1]))

                comp_data = {
                    "Metrik": ["Anlık Fiyat", "Son 1 Yıl Getirisi", "RSI (Momentum)", "Günlük Hacim"],
                    h1: [f"₺{df1['Close'].iloc[-1]:,.2f}", f"%{getiri_1y_1:.2f}", f"{rsi1:.2f}", f"{int(df1['Volume'].iloc[-1]):,}"],
                    h2: [f"₺{df2['Close'].iloc[-1]:,.2f}", f"%{getiri_1y_2:.2f}", f"{rsi2:.2f}", f"{int(df2['Volume'].iloc[-1]):,}"]
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
                    color='Degisim', color_continuous_scale='RdYlGn', color_continuous_midpoint=0,
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
                        st.warning("⚠️ **Risk Uyarısı:** Portföyündeki hisse sayısı çok az. Olası bir sektör krizinde sermayen yara alabilir. Çeşitliliği artırmanı öneririm.")
                    else:
                        st.info(f"✅ **Dağılım Başarılı:** Sepetinde toplam {len(pasta_etiketler)} farklı varlık var. Bu, riskin dağıtıldığı anlamına gelir.")
                    
                    en_buyuk_index = np.argmax(pasta_degerler)
                    st.write(f"- Portföyünün en büyük ağırlığı **%{ (pasta_degerler[en_buyuk_index] / sum(pasta_degerler)) * 100 :.1f}** ile **{pasta_etiketler[en_buyuk_index]}** hissesinde.")
                    
                    if toplam_kar_genel > 0: st.write("- 🟢 Genel olarak yatırım stratejin **kârlı** ilerliyor. Temel hedefin bu yeşil tabloyu korumak olmalı.")
                    else: st.write("- 🔴 Genel portföy şu an **zararda**. Maliyet düşürmek için ekleme yapabilir veya stop-loss seviyelerini gözden geçirebilirsin.")

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
