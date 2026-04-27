import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from supabase import create_client, Client

# --- 1. SİTE KONFİGÜRASYONU VE VERİTABANI BAĞLANTISI ---
st.set_page_config(page_title="Vader Analiz Terminali", layout="wide", initial_sidebar_state="expanded")

# Oturum Yönetimi (Kullanıcı Giriş Yaptı mı?)
if 'kullanici' not in st.session_state:
    st.session_state.kullanici = None

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
        st.rerun()

sayfa = st.sidebar.radio("SİTE MENÜSÜ", ["🏠 Ana Sayfa & Giriş", "📈 Canlı Analiz Terminali", "💼 Portföyüm & Takip", "📩 Hakkımda & İletişim"])

st.sidebar.markdown("---")
st.sidebar.info("📢 **Reklam Alanı**\nBuraya Google AdSense veya Sponsor ilanları yerleştirilebilir.")

ingilizce_turkce_sozluk = {
    "Total Revenue": "Toplam Gelir (Satışlar)", "Gross Profit": "Brüt Kar", "Net Income": "Net Kar",
    "Total Assets": "Toplam Varlıklar", "Total Liabilities Net Minority Interest": "Toplam Borçlar",
    "Stockholders Equity": "Özkaynaklar", "Cash And Cash Equivalents": "Nakit"
}

# --- 3. GÜÇLENDİRİLMİŞ VERİ MOTORLARI (ANTI-BAN SİSTEMİ) ---
# Verileri 15 dakika (900 saniye) hafızada tutarak Yahoo'nun engellemesini önler
@st.cache_data(ttl=900)
def veri_motoru(sembol):
    h = yf.Ticker(sembol)
    
    try: df = h.history(period="2y")
    except: df = pd.DataFrame()
    
    try: df_endeks = yf.Ticker("XU100.IS").history(period="2y")
    except: df_endeks = pd.DataFrame()
    
    try:
        ham_gelir = h.financials
        gelir = ham_gelir[ham_gelir.index.isin(ingilizce_turkce_sozluk.keys())].rename(index=ingilizce_turkce_sozluk) if ham_gelir is not None else pd.DataFrame()
    except: gelir = pd.DataFrame()
        
    try:
        ham_bilanco = h.balance_sheet
        bilanco = ham_bilanco[ham_bilanco.index.isin(ingilizce_turkce_sozluk.keys())].rename(index=ingilizce_turkce_sozluk) if ham_bilanco is not None else pd.DataFrame()
    except: bilanco = pd.DataFrame()
    
    try: haberler = h.news
    except: haberler = []
    
    try: bilgi = h.info
    except: bilgi = {}
    
    return bilgi, df, df_endeks, gelir, bilanco, haberler

@st.cache_data(ttl=900)
def watchlist_verisi_getir(sembol):
    # Watchlist için sadece çok hafif bir veri çekiyoruz
    df = yf.Ticker(sembol).history(period="5d")
    return df

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
        st.info("Sol menüden analiz araçlarını kullanmaya başlayabilirsiniz.")

    st.markdown("### 📢 Duyurular")
    st.warning("Tüm analiz araçlarını sol menüdeki 'Canlı Analiz Terminali' sekmesinden ücretsiz kullanabilirsiniz. Portföy kaydı için giriş yapmanız gereklidir.")
    footer_ekle()

elif sayfa == "📈 Canlı Analiz Terminali":
    hisse_kod = st.sidebar.text_input("Analiz Edilecek Hisse (Örn: THYAO):", "THYAO").upper()
    sembol = hisse_kod + ".IS"
    studyo = st.sidebar.checkbox("YouTube Stüdyo Modu (Neon)")
    tema = "plotly_dark"
    renk = '#00FFCC' if studyo else 'lime'
    
    if studyo: st.markdown("<style>h1, h2 { color: #00FFCC !important; }</style>", unsafe_allow_html=True)

    try:
        bilgi, df, df_endeks, gelir, bilanco, haberler = veri_motoru(sembol)
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

            t1, t2, t3, t4, t5, t6 = st.tabs(["📈 Gelişmiş Grafikler", "⚙️ Al-Sat Robotu", "🤖 AI Yorum & Sağlık", "🎯 Değerleme & Tahmin", "📰 Haberler & Duygu", "📑 Finansallar"])
            
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

                fig.update_layout(title="Ana Fiyat Grafiği", template=tema, height=450, hovermode="x unified")
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
                tahmin_getiri = np.exp(drift + stdev * np.random.standard_normal(gun))
                tahmin_fiyat = np.zeros_like(tahmin_getiri)
                tahmin_fiyat[0] = fiyat
                for t in range(1, gun): tahmin_fiyat[t] = tahmin_fiyat[t - 1] * tahmin_getiri[t]
                
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
                if eps and eps > 0:
                    icsel = eps * (8.5 + (2 * (beklenen_buyume / 100) * 100))
                    st.info(f"Hesaplanan Gerçek Eder (Graham): **₺{icsel:,.2f}** (Anlık Fiyat: ₺{fiyat:,.2f})")
                else:
                    st.error("EPS verisi eksik olduğu için hesaplanamıyor.")

            with t5:
                st.subheader("📰 Son Dakika Haberleri & Algoritmik Duygu Analizi")
                if haberler:
                    for haber in haberler[:5]:
                        baslik = haber.get('title', 'Başlık Yok')
                        link = haber.get('link', '#')
                        duygu = duygu_analizi(baslik)
                        with st.expander(f"{duygu} | {baslik}"):
                            st.write(f"[Haberi Oku]({link})")
                else:
                    st.info("Bu şirket için güncel haber verisi bulunamadı.")

            with t6:
                st.subheader("📑 Finansal Tablolar (Excel'e İndir)")
                if not bilanco.empty:
                    bilanco.columns = [str(col).split()[0] for col in bilanco.columns]
                    st.dataframe(bilanco, use_container_width=True)
                    st.download_button("📥 Bilançoyu İndir (CSV)", bilanco.to_csv(encoding='utf-8-sig'), f"{hisse_kod}_bilanco.csv", "text/csv")
                else:
                    st.info("Veri yok.")
        else:
            st.error("Hisse verisi çekilemedi. Hatalı kod girdiniz veya Yahoo kısıtlaması devam ediyor (Lütfen birkaç dakika bekleyin).")
    except Exception as e:
        st.error(f"Sistem Hatası: {e}")
    footer_ekle()

elif sayfa == "💼 Portföyüm & Takip":
    st.title("💼 Şahsi Portföy & İzleme Listesi")
    
    if st.session_state.kullanici is None:
        st.warning("Bu sayfayı görüntülemek ve kendi portföyünüzü oluşturmak için lütfen Ana Sayfa üzerinden giriş yapın veya kayıt olun.")
    else:
        st.subheader("📊 Anlık Kar/Zarar Hesaplayıcı")
        h_kod = st.text_input("Portföyünüzdeki Hisse Kodu:", "THYAO").upper() + ".IS"
        col_p1, col_p2 = st.columns(2)
        maliyet = col_p1.number_input("Maliyetiniz", min_value=0.0, step=1.0)
        lot = col_p2.number_input("Adet (Lot)", min_value=0, step=1)
        
        if maliyet > 0 and lot > 0:
            try:
                # Hafif veri çekimi
                anlik_df = watchlist_verisi_getir(h_kod)
                if not anlik_df.empty:
                    anlik = anlik_df['Close'].iloc[-1]
                    kar_zarar = (anlik * lot) - (maliyet * lot)
                    st.success(f"Güncel Değer: ₺{anlik * lot:,.2f} | Net Kar/Zarar: ₺{kar_zarar:,.2f}")
            except:
                st.error("Hisse bulunamadı.")
                
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
