from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import re
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_FILE = "database.db"

# --- OTOMASYON AYARLARI (Yasaklı Kelimeler) ---
YASAKLI_KELIMELER = ["hack", "bypass", "admin_zorla", "sifre_cal", "root_erisimi"]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS rules (sektor TEXT PRIMARY KEY, limit_val REAL, anahtar TEXT, birim TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS stats (name TEXT PRIMARY KEY, value INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, tarih TEXT, sektor TEXT, mesaj TEXT, sonuc TEXT, notlar TEXT)')
    cursor.execute("INSERT OR IGNORE INTO stats VALUES ('TOTAL', 0), ('PASS', 0), ('BLOCK', 0)")
    cursor.execute("INSERT OR IGNORE INTO rules VALUES ('HAVACILIK', 0.5, 'basınç', 'psi')")
    conn.commit()
    conn.close()

init_db()

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Epistemic Gate - Automation Pro</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .card { padding: 20px; border-radius: 12px; text-align: center; font-weight: bold; background: #1e293b; border: 1px solid #334155; }
        .total-val { color: #3b82f6; font-size: 2em; } .pass-val { color: #10b981; font-size: 2em; } .block-val { color: #ef4444; font-size: 2em; }
        .section { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #334155; }
        button { background: #6366f1; color: white; padding: 12px; border-radius: 8px; border: none; cursor: pointer; font-weight: bold; }
        table { width: 100%; text-align: left; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; border-bottom: 1px solid #334155; font-size: 0.85em; }
        .status-success { color: #10b981; } .status-blocked { color: #ef4444; }
    </style>
</head>
<body>
    <h1>🛡️ Epistemic Gate™ <span style="color: #f59e0b;">(Automation Active)</span></h1>
    
    <div class="grid">
        <div class="card">TOPLAM<br><span class="total-val">{{ stats['TOTAL'] }}</span></div>
        <div class="card">ONAY<br><span class="pass-val">{{ stats['PASS'] }}</span></div>
        <div class="card">ENGEL<br><span class="block-val">{{ stats['BLOCK'] }}</span></div>
    </div>

    <div class="section" style="border: 2px solid #f59e0b;">
        <h3>🤖 Otomatik Denetim Testi</h3>
        <form action="/test_verify" method="POST">
            <select name="sektor" style="padding: 10px; border-radius: 5px;">
                {% for rule in rules %}<option value="{{ rule['sektor'] }}">{{ rule['sektor'] }}</option>{% endfor %}
            </select>
            <input type="text" name="mesaj" placeholder="Mesajı yaz (Örn: Hack isteği gönder)" style="width: 300px; padding: 10px; border-radius: 5px;" required>
            <button type="submit">Sistemi Tetikle</button>
        </form>
    </div>

    <div class="section">
        <h3>📜 Denetim Kayıtları (Audit Logs)</h3>
        <table>
            <tr><th>Zaman</th><th>Sektör</th><th>İçerik</th><th>Karar</th><th>Açıklama</th></tr>
            {% for log in logs %}
            <tr>
                <td>{{ log['tarih'] }}</td>
                <td>{{ log['sektor'] }}</td>
                <td>{{ log['mesaj'] }}</td>
                <td class="{{ 'status-success' if log['sonuc'] == 'SUCCESS' else 'status-blocked' }}">{{ log['sonuc'] }}</td>
                <td>{{ log['notlar'] }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row
    rules = conn.execute('SELECT * FROM rules').fetchall()
    stats = {row['name']: row['value'] for row in conn.execute('SELECT * FROM stats').fetchall()}
    logs = conn.execute('SELECT * FROM logs ORDER BY id DESC LIMIT 10').fetchall()
    conn.close()
    return render_template_string(DASHBOARD_HTML, stats=stats, rules=rules, logs=logs)

@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()
    mesaj = data.get("mesaj", "").lower()
    sektor = data.get("sektor", "").upper()
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row
    
    status, feedback = True, "Onaylandı"
    tarih = datetime.now().strftime("%H:%M:%S")

    # 1. OTOMASYON: Yasaklı Kelime Taraması
    for kelime in YASAKLI_KELIMELER:
        if kelime in mesaj:
            status, feedback = False, f"OTOMATİK ENGEL: Zararlı kelime ({kelime}) tespit edildi!"
            break

    # 2. SEKTÖREL DENETİM (Eğer kelime takılmadıysa)
    if status:
        kural = conn.execute('SELECT * FROM rules WHERE sektor = ?', (sektor,)).fetchone()
        if kural:
            if kural["anahtar"] not in mesaj:
                status, feedback = False, f"HATA: '{kural['anahtar']}' verisi eksik."
            else:
                sayilar = re.findall(r"[-+]?\d*\.\d+|\d+", mesaj)
                if sayilar and float(sayilar[0]) > kural["limit_val"]:
                    status, feedback = False, f"LİMİT AŞIMI: Maksimum {kural['limit_val']} olmalı."

    # Kayıt İşlemleri
    conn.execute('UPDATE stats SET value = value + 1 WHERE name = "TOTAL"')
    if status: conn.execute('UPDATE stats SET value = value + 1 WHERE name = "PASS"')
    else: conn.execute('UPDATE stats SET value = value + 1 WHERE name = "BLOCK"')
    conn.execute('INSERT INTO logs (tarih, sektor, mesaj, sonuc, notlar) VALUES (?, ?, ?, ?, ?)', 
                 (tarih, sektor, mesaj, "SUCCESS" if status else "BLOCKED", feedback))
    conn.commit(); conn.close()
    return jsonify({"status": "SUCCESS" if status else "BLOCKED", "feedback": feedback})

@app.route('/test_verify', methods=['POST'])
def test_verify():
    import requests
    sektor, mesaj = request.form.get("sektor"), request.form.get("mesaj")
    try:
        url = request.url_root + "verify"
        res = requests.post(url, json={"mesaj": mesaj, "sektor": sektor})
        return f'<html><script>alert("Karar: {res.json()["status"]}\\nNot: {res.json()["feedback"]}");window.location="/";</script></html>'
    except: return "Hata oluştu!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
