from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import re
import requests

app = Flask(__name__)
CORS(app)

# --- VERİ VE İSTATİSTİK MERKEZİ ---
stats = {"PASS": 0, "BLOCK": 0, "TOTAL": 0}
ANAYASA = {
    "HAVACILIK": {"limit": 0.5, "birim": "psi", "anahtar": "basınç"}
}

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Epistemic Gate Pro</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .card { padding: 20px; border-radius: 12px; text-align: center; font-weight: bold; }
        .total { background: #3b82f6; } .pass { background: #10b981; } .block { background: #ef4444; }
        .section { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #334155; }
        input, button, select { padding: 10px; margin: 5px; border-radius: 6px; border: none; outline: none; }
        button { background: #6366f1; color: white; cursor: pointer; font-weight: bold; transition: 0.3s; }
        button:hover { background: #4f46e5; }
        table { width: 100%; text-align: left; margin-top: 10px; border-collapse: collapse; }
        th, td { padding: 12px; border-bottom: 1px solid #334155; }
    </style>
</head>
<body>
    <h1>🛡️ Epistemic Gate™ Control Center</h1>
    
    <div class="grid">
        <div class="card total">TOPLAM SORGULAMA: {{ stats.TOTAL }}</div>
        <div class="card pass">ONAY (PASS): {{ stats.PASS }}</div>
        <div class="card block">ENGEL (BLOCK): {{ stats.BLOCK }}</div>
    </div>

    <div class="section">
        <h3>🧪 Hızlı Test Et (Sisteme Ateş Et!)</h3>
        <form action="/test_verify" method="POST">
            <select name="sektor">
                {% for isim in kurallar.keys() %}
                <option value="{{ isim }}">{{ isim }}</option>
                {% endfor %}
            </select>
            <input type="text" name="mesaj" placeholder="Mesajı yaz (Örn: Basınç 0.8 psi)" style="width: 350px;" required>
            <button type="submit" style="background: #f59e0b;">Denetle</button>
        </form>
    </div>

    <div class="section">
        <h3>➕ Yeni Kural Ekle</h3>
        <form action="/add_rule" method="POST">
            <input type="text" name="sektor" placeholder="Sektör Adı" required>
            <input type="number" step="0.1" name="limit" placeholder="Limit Değeri" required>
            <input type="text" name="anahtar" placeholder="Anahtar Kelime" required>
            <input type="text" name="birim" placeholder="Birim (psi, TL, kg)">
            <button type="submit">Sisteme Tanımla</button>
        </form>
    </div>

    <div class="section">
        <h3>📜 Aktif Kurallar</h3>
        <table>
            <tr><th>Sektör</th><th>Limit</th><th>Anahtar</th></tr>
            {% for isim, detay in kurallar.items() %}
            <tr><td>{{ isim }}</td><td>{{ detay.limit }} {{ detay.birim }}</td><td>{{ detay.anahtar }}</td></tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML, stats=stats, kurallar=ANAYASA)

@app.route('/add_rule', methods=['POST'])
def add_rule():
    sektor = request.form.get("sektor").upper()
    ANAYASA[sektor] = {
        "limit": float(request.form.get("limit")),
        "anahtar": request.form.get("anahtar").lower(),
        "birim": request.form.get("birim", "")
    }
    return f"<html><script>alert('{sektor} Kuralı Eklendi!'); window.location='/';</script></html>"

@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()
    mesaj = data.get("mesaj", "").lower()
    sektor = data.get("sektor", "").upper()
    
    kural = ANAYASA.get(sektor)
    status = False
    feedback = "Sektör veya kural tanımlı değil."
    
    if kural:
        if kural["anahtar"] not in mesaj:
            feedback = f"HATA: '{kural['anahtar']}' kelimesi mesajda geçmiyor."
        else:
            sayilar = re.findall(r"[-+]?\d*\.\d+|\d+", mesaj)
            if sayilar:
                deger = float(sayilar[0])
                if deger <= kural["limit"]:
                    status = True
                    feedback = "Güvenli geçiş onaylandı."
                else:
                    fark = round(deger - kural["limit"], 2)
                    feedback = f"BLOK: Limit {fark} birim aşıldı! Maksimum: {kural['limit']}"
            else:
                feedback = "HATA: Mesajda sayısal bir değer bulunamadı."

    stats["TOTAL"] += 1
    if status: stats["PASS"] += 1
    else: stats["BLOCK"] += 1
    
    return jsonify({"status": "SUCCESS" if status else "BLOCKED", "feedback": feedback})

@app.route('/test_verify', methods=['POST'])
def test_verify():
    sektor = request.form.get("sektor")
    mesaj = request.form.get("mesaj")
    try:
        res = requests.post("http://127.0.0.1:5000/verify", json={"mesaj": mesaj, "sektor": sektor})
        data = res.json()
        return f"<html><script>alert('KARAR: {data['status']}\\nNOT: {data['feedback']}'); window.location='/';</script></html>"
    except Exception as e:
        return f"Hata oluştu: {str(e)}"

if __name__ == '__main__':
    app.run(port=5000, debug=True)