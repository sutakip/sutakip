import time
import json
import schedule
import requests
from bs4 import BeautifulSoup
import urllib3
import re
from datetime import datetime
from openai import OpenAI
import os # <-- YENİ EKLENDİ: Şifreleri sistemden okumak için gerekli

# Güvenlik uyarılarını sustur
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- AYARLAR ---
DOSYA_ADI = "kesintiler.json"

# --- GÜVENLİK GÜNCELLEMESİ ---
# Anahtarı doğrudan buraya YAZMIYORUZ. Render'ın "Environment" kısmından okuyoruz.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Eğer anahtar yoksa kullanıcıyı uyar (Çökmemesi için)
if not OPENAI_API_KEY:
    print("⚠️ UYARI: OPENAI_API_KEY bulunamadı! Render Environment ayarlarını kontrol edin.")

URL_IZMIR_API = "https://openapi.izmir.bel.tr/api/izsu/arizakaynaklisukesintileri"
URL_IZMIR_WEB = "https://www.izsu.gov.tr/tr/Duyurular/263"
URL_ANKARA_WEB = "https://aski.gov.tr/tr/Kesinti.aspx"
URL_ISTANBUL_WEB = "https://www.iski.istanbul/web/tr-TR/ariza-kesinti"

def yapay_zeka_ile_parse_et(ham_metin, sehir_adi):
    # Anahtar yoksa veya metin boşsa işlem yapma
    if not OPENAI_API_KEY or not ham_metin:
        print(f"   ⚠️ {sehir_adi} için AI atlanıyor (Anahtar eksik veya veri yok)")
        return []

    print(f"   🤖 {sehir_adi} için AI analiz yapıyor (Derin Analiz Modu)...")
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # SADELEŞTİRİLMİŞ MOD - SADECE SONUÇ ODAKLI
        prompt = f"""
        Görevin: Aşağıdaki ham metni analiz et ve su kesintilerini JSON listesi olarak ver.
        
        !!! ANALİZ VE KARAR MEKANİZMASI (TİP BELİRLEME) !!!
        
        Sadece AÇIKLAMA kısmındaki olayın kök nedenine odaklan ve tipine karar ver (Ama nedeni çıktıya yazma):

        1. **PLANLI / SİSTEMSEL (TURUNCU):**
           - **Kapsam:** "Kuraklık", "Yoğun Su Kullanımı", "Basınç düşüklüğü", "Artan Nüfus", "Yatırım", "Bakım".
           - **KRİTİK:** "Basınç düşüklüğü" ifadesi bir ARIZA DEĞİLDİR. Bunu doğrudan **"PLANLI"** olarak etiketle.

        2. **ARIZA / KAZA (KIRMIZI):**
           - **Kapsam:** Sadece "Fiziksel hasar", "Boru patlağı", "Şebeke arızası", "Ana boru kırılması", "Plansız".
           - Yukarıdaki sistemsel sebepler yoksa ve fiziksel bir kırılma varsa **"ARIZA"** de.

        -------------------------------------------------------

        FORMATLAMA KURALLARI:
        1. **MAHALLELER:** "Etkilenen Yerler" listesini en alttan bul, virgülle ayırarak tam liste yap.
        2. **TARİH:** Tarihi sadeleştir. Yıl yazma. Sadece Gün ve Ay ismi kullan.
           - ÖRNEK: "20.12.2025" yerine -> **"20 Aralık"** yaz.
           - ÖRNEK SAAT: "20 Aralık, 14:00 - 18:00"
        3. **AYRIŞTIR:** Birden fazla farklı kesinti varsa, bunları ayrı maddeler yap.

        İstenen JSON Formatı (SADE):
        [
          {{
            "tip": "ARIZA" veya "PLANLI",
            "ilce": "İlçe Adı (Title Case)",
            "mahalle": "Mahalle Listesi (Tamamı)",
            "zaman": "20 Aralık, 14:00 - 18:00"
          }}
        ]
        
        ANALİZ EDİLECEK METİN:
        {ham_metin[:15000]} 
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        ai_cevabi = response.choices[0].message.content.strip()
        # Temizlik: Markdown kod bloklarını kaldır
        ai_cevabi = ai_cevabi.replace("```json", "").replace("```", "")
        
        # Olası hatalara karşı sadece [ ... ] arasını al
        match = re.search(r'\[.*\]', ai_cevabi, re.DOTALL)
        if match:
            ai_cevabi = match.group(0)
            
        return json.loads(ai_cevabi)

    except Exception as e:
        print(f"   ❌ AI JSON Hatası: {e}")
        return []

# --- ŞEHİR AJANLARI ---

def izmir_verilerini_al():
    print("⚡ [İzmir] Veriler toplanıyor...")
    liste = []
    # 1. API
    try:
        resp = requests.get(URL_IZMIR_API, verify=False, timeout=10)
        if resp.status_code == 200:
            for v in resp.json():
                mahalle = (v.get("Mahalleler") or v.get("Mahalle") or "Belirtilmemiş")
                if isinstance(mahalle, list): mahalle = ", ".join(mahalle)
                liste.append({
                    "sehir": "İzmir", "tip": "ARIZA",
                    "ilce": v.get("IlceAdi", "").strip(),
                    "mahalle": str(mahalle).strip(),
                    "zaman": v.get("KesintiSuresi", ""), "neden": v.get("ArizaNedeni", "")
                })
    except: pass
    
    # 2. WEB (Planlı)
    try:
        resp = requests.get(URL_IZMIR_WEB, verify=False, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            div = soup.find('div', id='divContent') or soup
            metin = div.get_text()
            zaman = "Belirtilen Saatler Arasında"
            z_bul = re.search(r'(\d{1,2}[:.]\d{2})\s*-\s*(\d{1,2}[:.]\d{2})', metin)
            if z_bul: zaman = z_bul.group(0)
            
            satirlar = div.get_text(separator="\n").split("\n")
            c_ilce, c_mah = "", ""
            for s in satirlar:
                s = s.strip()
                if not s or "tıklayınız" in s.lower() or "İZMİR SU VE KANALİZASYON" in s: continue
                if "İlçesi'nin" in s or "İlçesi;" in s:
                    if c_ilce and c_mah:
                        liste.append({"sehir": "İzmir", "tip": "PLANLI", "ilce": c_ilce, "mahalle": c_mah, "zaman": zaman, "neden": "Planlı Çalışma"})
                    parts = s.split(';')
                    c_ilce = parts[0].replace("İlçesi'nin", "").replace("İlçesi", "").strip()
                    c_mah = parts[1].strip() if len(parts)>1 else ""
                elif c_ilce:
                    c_mah += " " + s
            if c_ilce and c_mah:
                 liste.append({"sehir": "İzmir", "tip": "PLANLI", "ilce": c_ilce, "mahalle": c_mah, "zaman": zaman, "neden": "Planlı Çalışma"})
    except: pass
    
    return liste # HER ZAMAN LİSTE DÖNER

def ankara_verilerini_al():
    print("⚡ [Ankara] ASKİ taranıyor...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(URL_ANKARA_WEB, headers=headers, verify=False, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            tum_metin = soup.body.get_text(separator="\n")
            tum_metin = re.sub(r'\n+', '\n', tum_metin).strip()
            
            json_veri = yapay_zeka_ile_parse_et(tum_metin, "Ankara")
            for veri in json_veri: veri["sehir"] = "Ankara"
            return json_veri
    except Exception as e:
        print(f"   ❌ Ankara Hatası: {e}")
    return [] # HATA OLSA BİLE BOŞ LİSTE DÖNER

def istanbul_verilerini_al():
    print("⚡ [İstanbul] İSKİ taranıyor...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(URL_ISTANBUL_WEB, headers=headers, verify=False, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            ana_metin = soup.find('div', id='divArizaKesinti') or soup.body
            tum_metin = ana_metin.get_text(separator="\n").strip()
            
            json_veri = yapay_zeka_ile_parse_et(tum_metin, "İstanbul")
            for veri in json_veri: veri["sehir"] = "İstanbul"
            return json_veri
    except Exception as e:
        print(f"   ❌ İstanbul Hatası: {e}")
    
    return []

def gorev():
    print(f"\n🔄 GÜNCELLEME: {datetime.now().strftime('%H:%M:%S')}")
    izmir = izmir_verilerini_al() 
    ankara = ankara_verilerini_al()
    istanbul = istanbul_verilerini_al()
    
    # Artık hepsi liste olduğu için toplama işlemi güvenli
    tum_liste = izmir + ankara + istanbul
    
    try:
        with open(DOSYA_ADI, "w", encoding="utf-8") as f:
            json.dump(tum_liste, f, ensure_ascii=False, indent=4)
        print(f"💾 Veriler Güncellendi. Toplam: {len(tum_liste)}")
    except Exception as e:
        print(f"Kayıt Hatası: {e}")

# Başlat
print("🚀 Ajan Başlatıldı (Render Versiyonu)")

# İlk açılışta bir kez çalıştır
gorev()

# Sonra her 15 dakikada bir tekrarla
schedule.every(15).minutes.do(gorev)

while True:
    schedule.run_pending()
    time.sleep(1)