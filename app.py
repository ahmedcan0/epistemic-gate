from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import re
import sqlite3
import os

app = Flask(__name__)
CORS(app)

DB_FILE = "database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS rules (sektor TEXT PRIMARY KEY, limit_val REAL, anahtar TEXT, birim TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS stats (name TEXT PRIMARY KEY, value INTEGER)')
    cursor.execute("INSERT OR IGNORE INTO stats VALUES ('TOTAL', 0), ('PASS', 0), ('BLOCK', 0)")
    cursor.execute("INSERT OR IGNORE INTO rules VALUES ('HAVACILIK', 0.5, 'basınç', 'psi')")
    conn.commit()
    conn.close()

init_db()

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Epistemic Gate Pro</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .card { padding: 20px; border-radius: 12px; text-align: center; font-weight: bold; background: #1e293b; border: 1px solid #334155; }
        .total-val { color: #3b82f6; font-size: 2em; } .pass-val { color: #10b981; font-size: 2em; } .block-val { color: #ef4444; font-size: 2em; }
        .section { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #334155; }
        input, button, select { padding: 12px; margin: 5px; border-radius: 8px; border: none; }
        button { background: #6366f1; color: white; cursor: pointer; font-weight: bold; }
        table { width: 100%; text-align: left; border-collapse: collapse; }
        th, td { padding: 12px; border-bottom: 1px solid #334155; }
    </style>
</head>
<body>
    <h1>🛡️ Epistemic Gate™ Control Center</h1>
    <div class="grid">
        <div class="card">TOPLAM<br><span class="total-val">{{ stats['TOTAL'] }}</span></div>
        <div class="card">ONAY<br><span class="pass-val">{{ stats['PASS'] }}</span></div>
        <div class="card">BLOK<br><span class="block-val">{{ stats['BLOCK'] }}</span></div>
    </div>
    <div class="section">
        <h3>🧪 Hızlı Test Et</h3>
        <form action="/test_verify" method="POST">
            <select name="sektor">{% for rule in rules %}<option value="{{ rule['sektor'] }}">{{ rule['sektor'] }}</option>{% endfor %}</select>
            <input type="text" name="mesaj" placeholder="Test mesajı..." style="width: 300px;" required>
            <button type="submit">Denetle</button>
        </form>
    </div>
    <div class="section">
        <h3>➕ Kural Ekle</h3>
        <form action="/add_rule" method="POST">
            <input type="text" name="sektor" placeholder="Sektör" required>
            <input type="number" step="0.1" name="limit" placeholder="Limit" required>
            <input type="text" name="anahtar" placeholder="Kelime" required>
            <button type="submit" style="background: #10b981;">Kaydet</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row
    rules = conn.execute('SELECT * FROM rules').fetchall()
    stats = {row['name']: row['value'] for row in conn.execute('SELECT * FROM stats').fetchall()}
    conn.close()
    return render_template_string(DASHBOARD_HTML, stats=stats, rules=rules)

@app.route('/add_rule', methods=['POST'])
def add_rule():
    sektor, limit, anahtar = request.form.get("sektor").upper(), float(request.form.get("limit")), request.form.get("anahtar").lower()
    conn = sqlite3.connect(DB_FILE)
    conn.execute('INSERT OR REPLACE INTO rules VALUES (?, ?, ?, ?)', (sektor, limit, anahtar, 'birim'))
    conn.commit(); conn.close()
    return '<html><script>alert("Eklendi");window.location="/";</script></html>'

@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()
    mesaj, sektor = data.get("mesaj", "").lower(), data.get("sektor", "").upper()
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row
    kural = conn.execute('SELECT * FROM rules WHERE sektor = ?', (sektor,)).fetchone()
    status, feedback = False, "Hata"
    if kural:
        if kural["anahtar"] in mesaj:
            sayilar = re.findall(r"[-+]?\d*\.\d+|\d+", mesaj)
            if sayilar and float(sayilar[0]) <= kural["limit_val"]: status, feedback = True, "Başarılı"
            else: feedback = "Limit aşıldı"
        else: feedback = "Anahtar kelime yok"
    
    conn.execute('UPDATE stats SET value = value + 1 WHERE name = "TOTAL"')
    if status: conn.execute('UPDATE stats SET value = value + 1 WHERE name = "PASS"')
    else: conn.execute('UPDATE stats SET value = value + 1 WHERE name = "BLOCK"')
    conn.commit(); conn.close()
    return jsonify({"status": "SUCCESS" if status else "BLOCKED", "feedback": feedback})

@app.route('/test_verify', methods=['POST'])
def test_verify():
    import requests
    sektor, mesaj = request.form.get("sektor"), request.form.get("mesaj")
    # Kendi kendine istek atmak için en sağlam yöntem
    try:
        url = request.url_root + "verify"
        res = requests.post(url, json={"mesaj": mesaj, "sektor": sektor})
        return f'<html><script>alert("Sonuç: {res.json()["status"]}");window.location="/";</script></html>'
    except:
        return "Bağlantı hatası!"

if __name__ == '__main__':
    # Yerel bilgisayarında 5000 portunda çalışır
    app.run(host='127.0.0.1', port=5000, debug=True)
