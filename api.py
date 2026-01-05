from flask import Flask, jsonify
from flask_cors import CORS  # <--- YENİ EKLENEN KISIM
import json
import os

app = Flask(__name__)
# Tüm kaynaklardan gelen isteklere izin ver (Chrome artık engellemeyecek)
CORS(app) 

DOSYA_ADI = "kesintiler.json"

@app.route('/api/kesintiler', methods=['GET'])
def get_kesintiler():
    if not os.path.exists(DOSYA_ADI):
        return jsonify([]) # Dosya yoksa boş liste dön
    
    try:
        with open(DOSYA_ADI, "r", encoding="utf-8") as f:
            veriler = json.load(f)
        return jsonify(veriler)
    except Exception as e:
        return jsonify({"hata": str(e)}), 500

if __name__ == '__main__':
    # host='0.0.0.0' yaparak hem telefondan hem bilgisayardan erişimi açıyoruz
    app.run(debug=True, host='0.0.0.0', port=5000)