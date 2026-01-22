import json
import requests
from bs4 import BeautifulSoup
import urllib3
import re
from datetime import datetime
from openai import OpenAI
import os

# Güvenlik uyarılarını sustur
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- AYARLAR ---
DOSYA_ADI = "kesintiler.json"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

URL_IZMIR_API = "https://openapi.izmir.bel.tr/api/izsu/arizakaynaklisukesintileri"
URL_IZMIR_WEB = "https://www.izsu.gov.tr/tr/Duyurular/263"
URL_ANKARA_WEB = "https://aski.gov.tr/tr/Kesinti.aspx"
URL_ISTANBUL_WEB = "https://www.iski.istanbul/web/tr-TR/ariza-kesinti"

# --- YARDIMCI FONKSİYONLAR ---

def yapay_zeka_ile_parse_et(ham_metin, sehir_adi):
    # Anahtar yoksa veya metin boşsa işlem yapma
    if not OPENAI_API_KEY or not ham_metin:
        print(f"   ⚠️ {sehir_adi} için AI atlanıyor (Anahtar eksik veya veri yok)")
        return []

    print(f"   🤖 {sehir_adi} için AI analiz yapıyor...")
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        prompt = f"""
        Görevin: Aşağıdaki ham metni analiz et ve su kesintilerini JSON listesi olarak ver.
        Sadece kök nedene odaklan:
        1. PLANLI (Bakım, Yatırım, Basınç düşüklüğü)
        2. ARIZA (Boru patlağı, Hasar)
        
        Tarihleri sadeleştir (örn: "20 Aralık").
        İstenen JSON Formatı:
        [{{ "tip": "ARIZA", "ilce": "...", "mahalle": "...", "zaman": "..." }}]
        
        METİN: {ham_metin[:10000]}
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
            return json.loads(match.group(0))
        return []

    except Exception as e:
        print(f"   ❌ AI JSON Hatası: {e}")
        return []

# --- ŞEHİR VERİLERİNİ ÇEKEN FONKSİYONLAR ---

def izmir_verilerini_al():
    print("⚡ [İzmir] Veriler toplanıyor...")
    liste = []
    # 1. API (Arızalar)
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
    
    # 2. WEB (Planlı Çalışmalar - Orijinal Kodun)
    try:
        resp = requests.get(URL_IZMIR_WEB, verify=False, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            div = soup.find('div', id='divContent') or soup
            metin = div.get_text()
            
            # Zamanı bul
            zaman = "Belirtilen Saatler Arasında"
            z_bul = re.search(r'(\d{1,2}[:.]\d{2})\s*-\s*(\d{1,2}[:.]\d{2})', metin)
            if z_bul: zaman = z_bul.group(0)
            
            # Satır satır analiz (Senin orijinal mantığın)
            satirlar = div.get_text(separator="\n").split("\n")
            c_ilce, c_mah = "", ""
            for s in satirlar:
                s = s.strip()
                if not s or "tıklayınız" in s.lower() or "İZMİR SU VE KANALİZASYON" in s: continue
                
                if "İlçesi'nin" in s or "İlçesi;" in s:
                    # Önceki ilçeyi kaydet
                    if c_ilce and c_mah:
                        liste.append({"sehir": "İzmir", "tip": "PLANLI", "ilce": c_ilce, "mahalle": c_mah, "zaman": zaman, "neden": "Planlı Çalışma"})
                    
                    # Yeni ilçeyi parse et
                    parts = s.split(';')
                    c_ilce = parts[0].replace("İlçesi'nin", "").replace("İlçesi", "").strip()
                    c_mah = parts[1].strip() if len(parts)>1 else ""
                elif c_ilce:
                    # Devam eden satırları mahalleye ekle
                    c_mah += " " + s
            
            # Son kalanı ekle
            if c_ilce and c_mah:
                 liste.append({"sehir": "İzmir", "tip": "PLANLI", "ilce": c_ilce, "mahalle": c_mah, "zaman": zaman, "neden": "Planlı Çalışma"})
    except: pass
    
    return liste

def ankara_verilerini_al():
    print("⚡ [Ankara] ASKİ taranıyor...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(URL_ANKARA_WEB, headers=headers, verify=False, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            tum_metin = soup.body.get_text(separator="\n").strip()
            data = yapay_zeka_ile_parse_et(tum_metin, "Ankara")
            for d in data: d["sehir"] = "Ankara"
            return data
    except: pass
    return []

def istanbul_verilerini_al():
    print("⚡ [İstanbul] İSKİ taranıyor...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(URL_ISTANBUL_WEB, headers=headers, verify=False, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            div = soup.find('div', id='divArizaKesinti') or soup.body
            tum_metin = div.get_text(separator="\n").strip()
            data = yapay_zeka_ile_parse_et(tum_metin, "İstanbul")
            for d in data: d["sehir"] = "İstanbul"
            return data
    except: pass
    return []

# --- ANA GÖREV FONKSİYONU ---
def gorev():
    print(f"\n🔄 Veri Çekme Başladı: {datetime.now().strftime('%H:%M:%S')}")
    
    izmir = izmir_verilerini_al() 
    ankara = ankara_verilerini_al()
    istanbul = istanbul_verilerini_al()
    
    tum_liste = izmir + ankara + istanbul
    
    # Dosyaya kaydet
    try:
        with open(DOSYA_ADI, "w", encoding="utf-8") as f:
            json.dump(tum_liste, f, ensure_ascii=False, indent=4)
        print(f"✅ Veriler Kaydedildi. Toplam: {len(tum_liste)}")
    except Exception as e:
        print(f"❌ Kayıt Hatası: {e}")
        
    return tum_liste

# Doğrudan çalıştırılırsa test et, import edilirse çalışma
if __name__ == "__main__":
    gorev()
