from flask import Flask, jsonify
from flask_cors import CORS
import json
import os
import threading
import time
import smart_agent  # <--- smart_agent.py aynı klasörde olmalı

app = Flask(__name__)
CORS(app) # Tüm kaynaklardan erişime izin ver

DOSYA_ADI = "kesintiler.json"

# --- ARKA PLAN GÖREVİ (Zamanlayıcı) ---
def arka_plan_zamanlayici():
    """
    Sunucu ayakta kaldığı sürece her 15 dakikada bir veriyi yeniler.
    """
    while True:
        try:
            time.sleep(900) # 15 dakika bekle
            print("⏰ Otomatik güncelleme tetiklendi...")
            smart_agent.gorev()
        except Exception as e:
            print(f"Zamanlayıcı hatası: {e}")

# Arka plan işçisini başlat (Daemon=True: Ana program kapanırsa bu da kapansın)
threading.Thread(target=arka_plan_zamanlayici, daemon=True).start()

@app.route('/api/kesintiler', methods=['GET'])
def get_kesintiler():
    # 1. SENARYO: Dosya yoksa veya bozuksa (Lazy Loading)
    if not os.path.exists(DOSYA_ADI) or os.path.getsize(DOSYA_ADI) < 5:
        print("⚠️ Veri dosyası yok! Kullanıcı için anlık oluşturuluyor...")
        try:
            # Akıllı ajanı çalıştır ve dönen veriyi DİREKT al
            # (Dosyadan okumak yerine hafızadan alıyoruz -> Daha Güvenli)
            taze_veri = smart_agent.gorev()
            return jsonify(taze_veri)
        except Exception as e:
            return jsonify({"hata": f"Veri oluşturulamadı: {str(e)}"}), 500

    # 2. SENARYO: Dosya varsa, oku ve gönder
    try:
        with open(DOSYA_ADI, "r", encoding="utf-8") as f:
            veriler = json.load(f)
        return jsonify(veriler)
    except Exception as e:
        print(f"Dosya okuma hatası: {e}")
        # Hata olsa bile boş liste dön ki uygulama çökmesin
        return jsonify([]), 200

if __name__ == '__main__':
    # Render'da burası çalışmaz (gunicorn devreye girer), yerel test içindir.
    app.run(host='0.0.0.0', port=5000)
