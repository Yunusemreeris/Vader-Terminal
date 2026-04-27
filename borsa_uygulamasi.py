import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

# --- 1. SİTE KONFİGÜRASYONU ---
st.set_page_config(page_title="Vader Analiz Terminali", layout="wide", initial_sidebar_state="expanded")

# --- 2. PROFESYONEL NAVİGASYON MENÜSÜ ---
st.sidebar.markdown(f"<h2 style='text-align: center; color: #00FFCC;'>🛸 VADER PRO</h2>", unsafe_allow_html=True)
sayfa = st.sidebar.radio("SİTE MENÜSÜ", ["🏠 Ana Sayfa & Giriş", "📈 Canlı Analiz Terminali", "💼 Portföyüm & Takip", "📩 Hakkımda & İletişim"])

st.sidebar.markdown("---")
st.sidebar.info("📢 **Reklam Alanı**\nBuraya Google AdSense veya Sponsor ilanları yerleştirilebilir.")

ingilizce_turkce_sozluk = {
    "Total Revenue": "Toplam Gelir (Satışlar)", "Gross Profit": "Brüt Kar", "Net Income": "Net Kar",
    "Total Assets": "Toplam Varlıklar", "Total Liabilities Net Minority Interest": "Toplam Borçlar",
    "Stockholders Equity": "Özkaynaklar", "Cash And Cash Equivalents": "Nakit"
}

# --- 3. FONKSİYONLAR (GİZLİ MOTORLAR) ---
@st.cache_data(ttl=60)
def veri_motoru(sembol):
    h = yf.Ticker(sembol)
    df = h.history(period="2y")
    df_endeks = yf.Ticker("XU100.IS").history(period="2y")
    ham_gelir = h.financials
    ham_bilanco = h.balance_sheet
    gelir = ham_gelir[ham_gelir.index.isin(ingilizce_turkce_sozluk.keys())].rename(index=ingilizce_turkce_sozluk) if ham_gelir is not None else pd.DataFrame()
    bilanco = ham_bilanco[ham_bilanco.index.isin(ingilizce_turkce_sozluk.keys())].rename(index=ingilizce_turkce_sozluk) if ham_bilanco is not None else pd.DataFrame()
    
    # Haberleri Çekme (Hata verirse boş liste döner)
    try: haberler = h.news
    except: haberler = []
    
    return h.info, df, df_endeks, gelir, bilanco, haberler

def ai_bilanco_yorumu(bilgi):
    yorumlar = []
    fk, cari, marj = bilgi.get('trailingPE', 0), bilgi.get('currentRatio', 0), bilgi.get('profitMargins', 0)
    if fk and fk > 0:
        yorumlar.append("🟢 **Değerleme:** Şirketin F/K oranı düşük, ucuz görünüyor." if fk < 10 else ("🔴 **Değerleme:** F/K oranı yüksek, piyasa şu an pahalı fiyatlıyor." if fk > 25 else "🟡 **Değerleme:** F/K oranı sektör ortalamalarında."))
    if cari:
        yorumlar.append("🟢 **Borçluluk:** Kısa vadeli nakit durumu güçlü." if cari >= 1.5 else "🔴 **Borçluluk:** Nakit akışı ve borç ödeme kapasitesi sınırda.")
    if marj:
        yorumlar.append("🟢 **Karlılık:** Kar marjı sağlıklı (%15+)." if marj > 0.15 else "🔴 **Karlılık:** Kar marjı düşük, kasaya az nakit giriyor.")
    return yorumlar if yorumlar else ["Yeterli veri bulunamadı."]

def duygu_analizi(metin):
    metin = str(metin).lower()
    pozitif_kelimeler = ['artış', 'kâr', 'büyüme', 'anlaşma', 'yükseliş', 'pozitif', 'up', 'profit', 'growth', 'dividend', 'success']
    negatif_kelimeler = ['zarar', 'düşüş', 'ceza', 'risk', 'negatif', 'down', 'loss', 'penalty', 'debt', 'fail']
    
    poz_skor = sum(1 for k in pozitif_kelimeler if k in metin)
    neg_skor = sum(1 for k in negatif_kelimeler if k in metin)
    
    if poz_skor > neg_skor: return "🟢 Pozitif Etki"
    elif neg_skor > poz_skor: return "🔴 Negatif Etki"
    else: return "⚪ Nötr Haber"

def footer_ekle():
    st.markdown("---")
    # BURASI GÜNCELLENDİ: Senin ismin eklendi.
    st.markdown(f"<p style='text-align: center; color: gray;'>Copyright © {datetime.now().year} Yunus Emre Eriş - Vader Analiz Terminali | Tüm Hakları Saklıdır.</p>", unsafe_allow_html=True)

# --- 4. SAYFA TASARIMLARI ---

# ==========================================
# SAYFA 1: ANA SAYFA & GİRİŞ
# ==========================================
if sayfa == "🏠 Ana Sayfa & Giriş":
    st.title("Vader Analiz Dünyasına Hoş Geldiniz")
    st.markdown("Borsa İstanbul analizi için geliştirilmiş en kapsamlı yerli terminal.")
    
    col_login, col_reg = st.columns(2)
    with col_login:
        st.subheader("🔑 Üye Girişi")
        user = st.text_input("Kullanıcı Adı veya E-posta")
        pw = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap"): st.success(f"Hoş geldin {user}! (Supabase bağlantısı bekleniyor...)")
            
    with col_reg:
        st.subheader("📝 Kayıt Ol")
        new_user = st.text_input("Ad Soyad")
        new_mail = st.text_input("E-posta Adresi")
        new_pw = st.text_input("Yeni Şifre", type="password")
        if st.button("Üyeliği Tamamla"): st.info("Kayıt talebiniz alındı. Veritabanı entegrasyonu aktif edildiğinde onaylanacaktır.")

    st.markdown("### 📢 Duyurular")
    st.warning("Tüm analiz araçlarını sol menüdeki 'Canlı Analiz Terminali' sekmesinden ücretsiz kullanabilirsiniz.")
    footer_ekle()

# ==========================================
# SAYFA 2: CANLI ANALİZ TERMİNALİ
# ==========================================
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

            # 6 DEV SEKME
            t1, t2, t3, t4, t5, t6 = st.tabs(["📈 Gelişmiş Grafikler", "⚙️ Al-Sat Robotu", "🤖 AI Yorum & Sağlık", "🎯 Değerleme & Tahmin", "📰 Haberler & Duygu", "📑 Finansallar"])
            
            with t1:
                st.markdown("**İleri Düzey Teknik İndikatörler Paneli**")
                goster_bollinger = st.checkbox("Bollinger Bantlarını Göster")
                goster_rsi = st.checkbox("RSI (Göreceli Güç Endeksi) Göster")
                goster_macd = st.checkbox("MACD (Trend Göstergesi) Göster")
                
                # Bollinger Hesabı
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
                
                # RSI Grafiği
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

                # MACD Grafiği
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
                st.markdown("Hissenin tarihsel oynaklığına (volatilite) dayalı olarak önümüzdeki 30 gün için tahmini fiyat rotası simüle edilmiştir. *(Yatırım tavsiyesi değildir)*")
                
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

                yatirim = st.slider("1 Yıl Önce Ne Kadar Yatırsaydım:", 1000, 1000000, 10000, 1000)
                gecmis_fiyat = df['Close'].iloc[-252] if len(df) >= 252 else df['Close'].iloc[0]
                bugunku_deger = (yatirim / gecmis_fiyat) * fiyat
                st.success(f"1 yıl önce **₺{gecmis_fiyat:.2f}** fiyattan alınan hisselerin bugünkü değeri: **₺{bugunku_deger:,.2f}**")

            with t5:
                st.subheader("📰 Son Dakika Haberleri & Algoritmik Duygu Analizi")
                st.markdown("Uluslararası/Yerel ajanslardan çekilen haber başlıkları ve kelime bazlı psikolojik etki skoru:")
                if haberler:
                    for haber in haberler[:5]:
                        baslik = haber.get('title', 'Başlık Yok')
                        link = haber.get('link', '#')
                        yayin = haber.get('publisher', 'Bilinmeyen Kaynak')
                        duygu = duygu_analizi(baslik)
                        
                        with st.expander(f"{duygu} | {baslik} ({yayin})"):
                            st.write(f"Haberin tamamını oku: [Bağlantıya Git]({link})")
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
    except Exception as e:
        st.error(f"Hisse verisi çekilemedi. Detay: {e}")
    footer_ekle()

# ==========================================
# SAYFA 3: PORTFÖYÜM & TAKİP
# ==========================================
elif sayfa == "💼 Portföyüm & Takip":
    st.title("💼 Şahsi Portföy & İzleme Listesi")
    
    st.subheader("📊 Anlık Kar/Zarar Hesaplayıcı")
    h_kod = st.text_input("Portföyünüzdeki Hisse Kodu:", "THYAO").upper() + ".IS"
    col_p1, col_p2 = st.columns(2)
    maliyet = col_p1.number_input("Maliyetiniz", min_value=0.0, step=1.0)
    lot = col_p2.number_input("Adet (Lot)", min_value=0, step=1)
    
    if maliyet > 0 and lot > 0:
        try:
            anlik = yf.Ticker(h_kod).history(period="1d")['Close'].iloc[-1]
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
            fav_df = yf.Ticker(fav_sembol).history(period="5d")
            fav_fiyat = fav_df['Close'].iloc[-1]
            fav_onceki = fav_df['Close'].iloc[-2]
            fav_yuzde = ((fav_fiyat - fav_onceki) / fav_onceki) * 100
            with cols[idx % len(cols)]:
                st.metric(fav_sembol.replace('.IS', ''), f"₺{fav_fiyat:,.2f}", f"{fav_yuzde:+.2f}%")
        except:
            pass
    footer_ekle()

# ==========================================
# SAYFA 4: HAKKIMDA & İLETİŞİM (GÜNCELLENDİ)
# ==========================================
elif sayfa == "📩 Hakkımda & İletişim":
    st.title("👨‍💻 Geliştirici Hakkında")
    
    # BURASI GÜNCELLENDİ: Senin ismin ve e-postan eklendi.
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