from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import re
import sqlite3
import os
import requests

app = Flask(__name__)
CORS(app)

DB_FILE = "database.db"

# --- VERİTABANI SİSTEMİ ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Kurallar Tablosu
    cursor.execute('''CREATE TABLE IF NOT EXISTS rules 
                      (sektor TEXT PRIMARY KEY, limit_val REAL, anahtar TEXT, birim TEXT)''')
    # İstatistik Tablosu
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats 
                      (name TEXT PRIMARY KEY, value INTEGER)''')
    
    cursor.execute("INSERT OR IGNORE INTO stats VALUES ('TOTAL', 0), ('PASS', 0), ('BLOCK', 0)")
    cursor.execute("INSERT OR IGNORE INTO rules VALUES ('HAVACILIK', 0.5, 'basınç', 'psi')")
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

init_db()

# --- GÖRSEL PANEL (DASHBOARD) ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Epistemic Gate Pro v2.0</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .card { padding: 20px; border-radius: 12px; text-align: center; font-weight: bold; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); }
        .total { background: #3b82f6; } .pass { background: #10b981; } .block { background: #ef4444; }
        .section { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #334155; }
        input, button, select { padding: 12px; margin: 5px; border-radius: 8px; border: none; outline: none; }
        button { background: #6366f1; color: white; cursor: pointer; font-weight: bold; transition: 0.2s; }
        button:hover { opacity: 0.8; }
        table { width: 100%; text-align: left; margin-top: 10px; border-collapse: collapse; }
        th, td { padding: 12px; border-bottom: 1px solid #334155; }
        tr:hover { background: #1e293b; }
    </style>
</head>
<body>
    <h1>🛡️ Epistemic Gate™ Control Center</h1>
    <p style="color: #94a3b8;">Sistem Durumu: 🟢 Aktif (Database: Connected)</p>
    
    <div class="grid">
        <div class="card total">TOPLAM ANALİZ<br><span style="font-size: 2em;">{{ stats['TOTAL'] }}</span></div>
        <div class="card pass">GÜVENLİ (PASS)<br><span style="font-size: 2em;">{{ stats['PASS'] }}</span></div>
        <div class="card block">ENGEL (BLOCK)<br><span style="font-size: 2em;">{{ stats['BLOCK'] }}</span></div>
    </div>

    <div class="section">
        <h3>🧪 Hızlı Test Et</h3>
        <form action="/test_verify" method="POST">
            <select name="sektor">
                {% for rule in rules %}
                <option value="{{ rule['sektor'] }}">{{ rule['sektor'] }}</option>
                {% endfor %}
            </select>
            <input type="text" name="mesaj" placeholder="Denetlenecek mesajı buraya yazın..." style="width: 400px;" required>
            <button type="submit" style="background: #f59e0b;">Şimdi Denetle</button>
        </form>
    </div>

    <div class="section">
        <h3>➕ Yeni Kural Tanımla</h3>
        <form action="/add_rule" method="POST">
            <input type="text" name="sektor" placeholder="Sektör (Örn: BANKA)" required>
            <input type="number" step="0.1" name="limit" placeholder="Limit" required>
            <input type="text" name="anahtar" placeholder="Kritik Kelime" required>
            <input type="text" name="birim" placeholder="Birim (TL, kg, %)">
            <button type="submit">Sisteme Kaydet</button>
        </form>
    </div>

    <div class="section">
        <h3>📜 Aktif Denetim Kuralları</h3>
        <table>
            <tr><th>Sektör</th><th>Eşik Değeri</th><th>Kontrol Kelimesi</th></tr>
            {% for rule in rules %}
            <tr><td>{{ rule['sektor'] }}</td><td>{{ rule['limit_val'] }} {{ rule['birim'] }}</td><td>{{ rule['anahtar'] }}</td></tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    conn = get_db_connection()
    rules = conn.execute('SELECT * FROM rules').fetchall()
    stats_rows = conn.execute('SELECT * FROM stats').fetchall()
    stats_dict = {row['name']: row['value'] for row in stats_rows}
    conn.close()
    return render_template_string(DASHBOARD_HTML, stats=stats_dict, rules=rules)

@app.route('/add_rule', methods=['POST'])
def add_rule():
    sektor = request.form.get("sektor").upper()
    limit = float(request.form.get("limit"))
    anahtar = request.form.get("anahtar").lower()
    birim = request.form.get("birim", "")
    
    conn = get_db_connection()
    conn.execute('INSERT OR REPLACE INTO rules VALUES (?, ?, ?, ?)', (sektor, limit, anahtar, birim))
    conn.commit()
    conn.close()
    return f"<html><script>alert('{sektor} kuralı veritabanına işlendi!'); window.location='/';</script></html>"

@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()
    mesaj = data.get("mesaj", "").lower()
    sektor = data.get("sektor", "").upper()
    
    conn = get_db_connection()
    kural = conn.execute('SELECT * FROM rules WHERE sektor = ?', (sektor,)).fetchone()
    
    status = False
    feedback = "Tanımlı kural bulunamadı."
    
    if kural:
        if kural["anahtar"] not in mesaj:
            feedback = f"KRİTİK HATA: Mesajda '{kural['anahtar']}' verisi eksik!"
        else:
            sayilar = re.findall(r"[-+]?\d*\.\d+|\d+", mesaj)
            if sayilar:
                deger = float(sayilar[0])
                if deger <= kural["limit_val"]:
                    status = True
                    feedback = "GÜVENLİ: Veri limitler dahilinde."
                else:
                    fark = round(deger - kural["limit_val"], 2)
                    feedback = f"BLOKLANDI: Limit {fark} {kural['birim']} aşıldı! (Maks: {kural['limit_val']})"
            else:
                feedback = "HATA: Sayısal değer tespit edilemedi."

    conn.execute('UPDATE stats SET value = value + 1 WHERE name = "TOTAL"')
    if status: conn.execute('UPDATE stats SET value = value + 1 WHERE name = "PASS"')
    else: conn.execute('UPDATE stats SET value = value + 1 WHERE name = "BLOCK"')
    
    conn.commit()
    conn.close()
    return jsonify({"status": "SUCCESS" if status else "BLOCKED", "feedback": feedback})

@app.route('/test_verify', methods=['POST'])
def test_verify():
    sektor = request.form.get("sektor")
    mesaj = request.form.get("mesaj")
    base_url = request.host_url 
    
    try:
        res = requests.post(f"{base_url}verify", json={"mesaj": mesaj, "sektor": sektor})
        data = res.json()
        return f"<html><script>alert('SONUÇ: {data['status']}\\nNOT: {data['feedback']}'); window.location='/';</script></html>"
    except Exception as e:
        return f"Sistem hatası: {str(e)}"

if __name__ == '__main__':
    # Render ve yerel çalışma için port ayarı
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
