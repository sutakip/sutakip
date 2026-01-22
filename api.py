from flask import Flask, jsonify
from flask_cors import CORS
import json
import os
import threading
import time
import smart_agent  # <--- ÖNEMLİ: Veri çeken ajanımızı buraya çağırıyoruz

app = Flask(__name__)
CORS(app)

DOSYA_ADI = "kesintiler.json"

# --- ARKA PLAN GÖREVİ (Zamanlayıcı) ---
def arka_plan_zamanlayici():
    """Sistemi canlı tutar ve her 15 dakikada bir veriyi yeniler."""
    while True:
        try:
            time.sleep(900) # 15 dakika bekle (900 saniye)
            print("⏰ Otomatik güncelleme tetiklendi...")
            smart_agent.gorev()
        except Exception as e:
            print(f"Zamanlayıcı hatası: {e}")

# Uygulama başlarken zamanlayıcıyı ayrı bir iş parçacığı (thread) olarak başlat
# Daemon=True demek, ana program kapanırsa bu da kapansın demektir.
threading.Thread(target=arka_plan_zamanlayici, daemon=True).start()

@app.route('/api/kesintiler', methods=['GET'])
def get_kesintiler():
    # 1. KONTROL: Dosya yoksa veya içi boşsa (Lazy Loading)
    # Bu sayede 'Shell' komutu kullanmadan, ilk istekte veri oluşur.
    if not os.path.exists(DOSYA_ADI) or os.path.getsize(DOSYA_ADI) < 5:
        print("⚠️ Veri dosyası bulunamadı! İlk kez oluşturuluyor (Kullanıcı Bekliyor)...")
        try:
            # Aşçıyı dürt, yemeği pişirsin
            smart_agent.gorev()
        except Exception as e:
            return jsonify({"hata": f"Veri oluşturulamadı: {str(e)}"}), 500

    # 2. OKUMA: Dosyayı oku ve müşteriye sun
    try:
        with open(DOSYA_ADI, "r", encoding="utf-8") as f:
            veriler = json.load(f)
        return jsonify(veriler)
    except Exception as e:
        # Eğer okuma hatası olursa boş liste dön (Uygulama çökmesin diye)
        print(f"Okuma hatası: {e}")
        return jsonify([]), 200

if __name__ == '__main__':
    # Render'da Gunicorn kullanıldığı için burası çalışmaz, yerelde test için kalabilir.
    app.run(host='0.0.0.0', port=5000)
