import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client, Client
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import extra_streamlit_components as stx  # YENİ: Çerez Yönetici Kütüphanesi

# --- 1. SİTE KONFİGÜRASYONU VE VERİTABANI BAĞLANTISI ---
st.set_page_config(page_title="Vader Analiz Terminali", layout="wide", initial_sidebar_state="expanded")

# --- YENİ: ÇEREZ (COOKIE) YÖNETİCİSİ ---
@st.cache_resource(experimental_allow_widgets=True)
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()
kayitli_mail = cookie_manager.get(cookie="vader_mail")
kayitli_id = cookie_manager.get(cookie="vader_id")

# Oturum Yönetimi (Kullanıcı Giriş Yaptı mı?)
if 'kullanici' not in st.session_state:
    st.session_state.kullanici = kayitli_mail if kayitli_mail else None
if 'user_id' not in st.session_state:
    st.session_state.user_id = kayitli_id if kayitli_id else None

# Supabase Bağlantısı
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
        cookie_manager.delete("vader_mail")
        cookie_manager.delete("vader_id")
        st.rerun()

sayfa = st.sidebar.radio("SİTE MENÜSÜ", ["🏠 Ana Sayfa & Giriş", "📈 Canlı Analiz Terminali", "💼 Portföyüm & Takip", "📩 Hakkımda & İletişim"])

st.sidebar.markdown("---")
st.sidebar.info("📢 **Reklam Alanı**\nBuraya Google AdSense veya Sponsor ilanları yerleştirilebilir.")

ingilizce_turkce_sozluk = {
    "Total Revenue": "Toplam Gelir (Satışlar)", "Gross Profit": "Brüt Kar", "Net Income": "Net Kar",
    "Total Assets": "Toplam Varlıklar", "Total Liabilities Net Minority Interest": "Toplam Borçlar",
    "Stockholders Equity": "Özkaynaklar", "Cash And Cash Equivalents": "Nakit"
}

def rakam_formatla(deger):
    try:
        sayi = float(deger)
        if pd.isna(sayi): return "Veri Yok"
        if abs(sayi) >= 1_000_000_000:
            return f"{sayi / 1_000_000_000:,.2f} Mlr"
        elif abs(sayi) >= 1_000_000:
            return f"{sayi / 1_000_000:,.2f} Mly"
        else:
            return f"{sayi:,.2f}"
    except:
        return deger

# --- 3. GÜÇLENDİRİLMİŞ VERİ MOTORLARI ---
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
    return yorumlar if yorumlar else ["Veri kısıtlaması nedeniyle AI yorumu üretilemedi."]

def duygu_analizi(metin):
    metin = str(metin).lower()
    poz_kelimeler = ['artış', 'kâr', 'büyüme', 'anlaşma', 'yükseliş', 'pozitif', 'up', 'profit', 'growth', 'dividend', 'success']
    neg_kelimeler = ['zarar', 'düşüş', 'ceza', 'risk', 'negatif', 'down', 'loss', 'penalty', 'debt', 'fail']
    
    poz_skor = sum(1 for k in poz_kelimeler if k in metin)
    neg_skor = sum(1 for k in neg_kelimeler if k in metin)
    
    if poz_skor > neg_skor: return "🟢 Pozitif Etki"
    elif neg_skor > poz_skor: return "🔴 Negatif Etki"
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
            log_mail = st.text_input("E-posta", key="log_mail")
            log_pw = st.text_input("Şifre", type="password", key="log_pw")
            if st.button("Giriş Yap"):
                try:
                    response = supabase.auth.sign_in_with_password({"email": log_mail, "password": log_pw})
                    st.session_state.kullanici = response.user.email
                    st.session_state.user_id = response.user.id
                    
                    # YENİ: Başarılı girişte bilgileri Cookie'ye kaydet (30 Gün Geçerli)
                    cookie_manager.set("vader_mail", response.user.email, expires_at=datetime.now() + timedelta(days=30))
                    cookie_manager.set("vader_id", response.user.id, expires_at=datetime.now() + timedelta(days=30))
                    
                    st.success("Giriş başarılı! Yönlendiriliyorsunuz...")
                    st.rerun()
                except Exception as e:
                    st.error("Giriş başarısız! E-posta veya şifre hatalı olabilir.")
                
        with col_reg:
            st.subheader("📝 Yeni Kayıt Ol")
            reg_mail = st.text_input("E-posta Adresi", key="reg_mail")
            reg_pw = st.text_input("Yeni Şifre (En az 6 hane)", type="password", key="reg_pw")
            if st.button("Üyeliği Tamamla"):
                try:
                    response = supabase.auth.sign_up({"email": reg_mail, "password": reg_pw})
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
    
    zaman_secimi = st.sidebar.selectbox(
        "Grafik Zaman Dilimi:", 
        ["Günlük (Son 2 Yıl)", "Saatlik (Son 1 Ay)", "15 Dakikalık (Son 5 Gün)", "5 Dakikalık (Son 5 Gün)", "1 Dakikalık (Son 1 Gün)"]
    )
    if zaman_secimi == "Günlük (Son 2 Yıl)": p, i = "2y", "1d"
    elif zaman_secimi == "Saatlik (Son 1 Ay)": p, i = "1mo", "1h"
    elif zaman_secimi == "15 Dakikalık (Son 5 Gün)": p, i = "5d", "15m"
    elif zaman_secimi == "5 Dakikalık (Son 5 Gün)": p, i = "5d", "5m"
    elif zaman_secimi == "1 Dakikalık (Son 1 Gün)": p, i = "1d", "1m"

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
            
            st.header(f"⚡ {bilgi.get('longName', hisse_kod)}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Anlık Fiyat", f"₺{fiyat:,.2f}", f"{degisim:+.2f} TL ({yuzde:+.2f}%)")
            m2.metric("Günlük Hacim", f"{bilgi.get('volume', int(df['Volume'].iloc[-1])):,}")
            m3.metric("F/K Oranı", round(bilgi.get('trailingPE', 0), 2) if bilgi.get('trailingPE') else "N/A")
            m4.metric("Piyasa Değeri", f"₺{bilgi.get('marketCap', 0):,}")

            t1, t2, t3, t4, t5, t6 = st.tabs(["📈 Gelişmiş Grafikler", "⚙️ Al-Sat Robotu", "🤖 AI Yorum & Sağlık", "🎯 Değerleme & Tahmin", "📰 Haberler", "📑 Finansallar"])
            
            with t1:
                st.markdown("**İleri Düzey Teknik İndikatörler Paneli**")
                goster_bollinger = st.checkbox("Bollinger Bantlarını Göster")
                goster_rsi = st.checkbox("RSI (Göreceli Güç Endeksi) Göster")
                goster_macd = st.checkbox("MACD (Trend Göstergesi) Göster")
                
                if goster_bollinger:
                    df['SMA20_B'] = df['Close'].rolling(20).mean()
                    df['STD20_B'] = df['Close'].rolling(20).std()
                    df['Upper'] = df['SMA20_B'] + (df['STD20_B'] * 2)
                    df['Lower'] = df['SMA20_B'] - (df['STD20_B'] * 2)

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color=renk if degisim >= 0 else 'red', width=2), name='Fiyat'))
                
                if goster_bollinger:
                    fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='gray', width=1, dash='dash'), name='Üst Bant'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='gray', width=1, dash='dash'), name='Alt Bant', fill='tonexty', fillcolor='rgba(128,128,128,0.1)'))

                fig.update_layout(title=f"Ana Fiyat Grafiği ({zaman_secimi})", template=tema, height=450, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
                
                if goster_rsi:
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    df['RSI'] = 100 - (100 / (1 + rs))
                    
                    fig_rsi = go.Figure()
                    fig_rsi.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='orange', width=2), name='RSI (14)'))
                    fig_rsi.add_hline(y=70, line_dash="dot", line_color="red", annotation_text="Aşırı Alım (Pahalı)")
                    fig_rsi.add_hline(y=30, line_dash="dot", line_color="green", annotation_text="Aşırı Satım (Ucuz)")
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
                st.subheader("⚙️ 20 ve 50 Günlük Ortalama Kesişim Robotu")
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
                st.subheader("🧠 Yapay Zeka Bilanço Yorumcusu")
                for y in ai_bilanco_yorumu(bilgi): st.write(y)
                
                st.markdown("---")
                st.subheader("🩺 Muhasebe Oranları & DuPont")
                c1, c2, c3 = st.columns(3)
                c1.metric("PD/DD", round(bilgi.get('priceToBook', 0), 2) if bilgi.get('priceToBook') else "Yok")
                c2.metric("Özkaynak Karlılığı (ROE)", f"%{round(bilgi.get('returnOnEquity', 0)*100, 2)}" if bilgi.get('returnOnEquity') else "Yok")
                c3.metric("Cari Oran", round(bilgi.get('currentRatio', 0), 2) if bilgi.get('currentRatio') else "Yok")

            with t4:
                st.subheader("🔮 Yapay Zeka Gelecek Tahmini (Monte Carlo)")
                st.markdown("Hissenin tarihsel oynaklığına (volatilite) dayalı olarak önümüzdeki 30 gün için tahmini fiyat rotası simüle edilmiştir.")
                
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
                fig_mc.update_layout(template=tema, height=350, title="30 Günlük Matematiksel Projeksiyon (Tutarlı)")
                st.plotly_chart(fig_mc, use_container_width=True)
                
                st.markdown("---")
                st.subheader("🎯 İçsel Değer & Zaman Makinesi")
                eps = bilgi.get('trailingEps', 0)
                beklenen_buyume = st.slider("Tahmini Yıllık Büyüme (%):", 1, 50, 15)
                if eps and eps > 0:
                    icsel = eps * (8.5 + (2 * (beklenen_buyume / 100) * 100))
                    st.info(f"Hesaplanan Gerçek Eder (Graham): **₺{icsel:,.2f}** (Anlık Fiyat: ₺{fiyat:,.2f})")
                else:
                    st.error("EPS verisi eksik olduğu için hesaplanamıyor.")

                yatirim = st.slider("1 Yıl Önce Ne Kadar Yatırsaydım:", 1000, 1000000, 10000, 1000)
                gecmis_fiyat = df['Close'].iloc[-252] if len(df) >= 252 else df['Close'].iloc[0]
                bugunku_deger = (yatirim / gecmis_fiyat) * fiyat
                st.success(f"1 yıl önce **₺{gecmis_fiyat:.2f}** fiyattan alınan hisselerin bugünkü değeri: **₺{bugunku_deger:,.2f}**")

            with t5:
                st.subheader("📰 Son Dakika Haberleri & Algoritmik Duygu Analizi")
                if haberler:
                    for haber in haberler[:5]:
                        baslik = haber.get('title', 'Başlık Yok')
                        link = haber.get('link', '#')
                        yayin = haber.get('publisher', 'Bilinmeyen Kaynak')
                        
                        if 'custom_time' in haber:
                            yayin_vakti = haber['custom_time']
                        else:
                            zaman_damgasi = haber.get('providerPublishTime', 0)
                            yayin_vakti = datetime.fromtimestamp(zaman_damgasi).strftime('%d.%m.%Y %H:%M') if zaman_damgasi else "Zaman Bilinmiyor"

                        duygu = duygu_analizi(baslik)
                        with st.expander(f"{duygu} | {baslik}"):
                            st.write(f"**Kaynak:** {yayin} | **Tarih:** {yayin_vakti}")
                            st.write(f"[Haberi Oku]({link})")
                else:
                    st.info("Bu şirket için güncel haber verisi bulunamadı.")

            with t6:
                st.subheader("📑 Finansal Tablolar (Excel'e İndir)")
                tablo_secim = st.radio("Lütfen İncelemek İstediğiniz Tablo Periyodunu Seçin:", ["Yıllık Bilanço", "Dönem İçi (Çeyreklik) Bilanço"], horizontal=True)
                
                aktif_tablo = bilanco if tablo_secim == "Yıllık Bilanço" else ceyreklik_bilanco
                
                if not aktif_tablo.empty:
                    aktif_tablo.columns = [str(col).split()[0] for col in aktif_tablo.columns]
                    try:
                        formatli_bilanco = aktif_tablo.map(rakam_formatla)
                    except AttributeError:
                        formatli_bilanco = aktif_tablo.applymap(rakam_formatla)
                        
                    st.dataframe(formatli_bilanco, use_container_width=True)
                    st.download_button(f"📥 {tablo_secim}yu İndir (CSV)", aktif_tablo.to_csv(encoding='utf-8-sig'), f"{hisse_kod}_{tablo_secim.replace(' ', '_')}.csv", "text/csv")
                else:
                    st.info(f"Seçili şirket için {tablo_secim} verisi bulunamadı veya Yahoo Finance kısıtlaması yaşanıyor.")
        else:
            st.error("Hisse verisi çekilemedi. Hatalı kod girdiniz veya Yahoo kısıtlaması devam ediyor.")
    except Exception as e:
        st.error(f"Sistem Hatası: {e}")
    footer_ekle()

# ==========================================
# SAYFA 3: PORTFÖYÜM & TAKİP
# ==========================================
elif sayfa == "💼 Portföyüm & Takip":
    st.title("💼 Şahsi Bulut Portföyünüz")
    
    if st.session_state.kullanici is None:
        st.warning("Bu sayfayı görüntülemek ve kendi portföyünüzü kalıcı olarak oluşturmak için lütfen Ana Sayfa üzerinden giriş yapın veya kayıt olun.")
    else:
        with st.expander("➕ Portföye Yeni Hisse Ekle", expanded=True):
            with st.form("hisse_ekle_form"):
                yeni_kod = st.text_input("Hisse Kodu (Örn: SASA):").upper()
                yeni_maliyet = st.number_input("Maliyet (TL)", min_value=0.0, step=1.0)
                yeni_lot = st.number_input("Adet (Lot)", min_value=1, step=1)
                ekle_btn = st.form_submit_button("Veritabanına Kaydet")
                
                if ekle_btn and yeni_kod:
                    try:
                        veri = {
                            "user_id": st.session_state.user_id,
                            "hisse_kod": yeni_kod,
                            "maliyet": yeni_maliyet,
                            "lot": yeni_lot
                        }
                        supabase.table("portfoyler").insert(veri).execute()
                        st.success(f"{yeni_kod} portföyünüze başarıyla kaydedildi!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Veritabanına yazılırken bir hata oluştu. Supabase'deki SQL tablosunu oluşturduğunuzdan emin olun.")

        st.subheader("📊 Kayıtlı Varlıklarınız ve Kar/Zarar")
        try:
            veriler = supabase.table("portfoyler").select("*").eq("user_id", st.session_state.user_id).execute()
            
            if veriler.data:
                df_port = pd.DataFrame(veriler.data)
                for index, row in df_port.iterrows():
                    try:
                        anlik_df = watchlist_verisi_getir(row['hisse_kod'] + ".IS")
                        anlik_fiyat = anlik_df['Close'].iloc[-1]
                        guncel_deger = anlik_fiyat * row['lot']
                        toplam_maliyet = row['maliyet'] * row['lot']
                        kar = guncel_deger - toplam_maliyet
                        kar_yuzde = (kar / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
                        
                        c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 2.5, 1])
                        c1.write(f"**{row['hisse_kod']}**")
                        c2.write(f"Maliyet: ₺{row['maliyet']:,.2f}")
                        c3.write(f"Lot: {row['lot']}")
                        c4.metric("Güncel Değer & Kar", f"₺{guncel_deger:,.2f}", f"₺{kar:,.2f} ({kar_yuzde:+.2f}%)")
                        if c5.button("Sil", key=f"del_{row['id']}"):
                            supabase.table("portfoyler").delete().eq("id", row['id']).execute()
                            st.rerun()
                        st.markdown("---")
                    except:
                        st.warning(f"{row['hisse_kod']} verisi şu an çekilemiyor.")
            else:
                st.info("Henüz veritabanınıza bir hisse eklemediniz. Yukarıdaki formu kullanabilirsiniz.")
        except Exception as e:
            st.error("Veritabanına bağlanılamadı veya tablo henüz oluşturulmadı.")
            
        st.markdown("---")
        st.subheader("📋 Canlı İzleme Listesi")
        favs = st.text_input("Takip ettiğiniz hisseler (Virgülle ayırın):", "SASA, EREGL, FROTO")
        favoriler = [x.strip().upper() + ".IS" for x in favs.split(",") if x.strip()]
        
        cols = st.columns(len(favoriler) if len(favoriler) > 0 else 1)
        for idx, fav_sembol in enumerate(favoriler):
            try:
                fav_df = watchlist_verisi_getir(fav_sembol)
                if not fav_df.empty:
                    fav_fiyat = fav_df['Close'].iloc[-1]
                    fav_onceki = fav_df['Close'].iloc[-2] if len(fav_df) > 1 else fav_fiyat
                    fav_yuzde = ((fav_fiyat - fav_onceki) / fav_onceki) * 100 if fav_onceki > 0 else 0
                    with cols[idx % len(cols)]:
                        st.metric(fav_sembol.replace('.IS', ''), f"₺{fav_fiyat:,.2f}", f"{fav_yuzde:+.2f}%")
            except:
                pass
    footer_ekle()

# ==========================================
# SAYFA 4: HAKKIMDA & İLETİŞİM
# ==========================================
elif sayfa == "📩 Hakkımda & İletişim":
    st.title("👨‍💻 Geliştirici Hakkında")
    
    st.markdown(f"""
    **Vader Analiz Terminali**, Bursa Uludağ Üniversitesi İİBF öğrencisi **Yunus Emre Eriş** tarafından geliştirilmiş profesyonel bir borsa analiz projesidir.
    
    ### Vizyonumuz
    Borsa İstanbul yatırımcılarına şeffaf, hızlı ve yapay zeka destekli analiz araçları sunarak finansal okuryazarlığı artırmak.
    
    ### İletişim & İş Birliği
    Reklam, sponsorluk veya teknik destek için:
    - **E-posta:** yunusemreeris787@gmail.com
    - **Konum:** Bursa Uludağ Üniversitesi Yerleşkesi
    """)
    footer_ekle()
