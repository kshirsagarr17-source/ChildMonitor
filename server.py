import os
import sys
import datetime
import socket

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename
import database

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "childmonitor-secure-key-2026")
PARENT_PASSWORD = os.environ.get("PARENT_PASSWORD", "Indiansk@5460")
SERVER_PORT = int(os.environ.get("PORT", 3375))

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "Captured_Photos")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# डेटाबेस तयार करणे
database.init_db()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "10.247.151.235"

def is_auth():
    return session.get("authenticated") is True

# ================= HTML TEMPLATES =================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>लॉगिन - ChildMonitor</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: radial-gradient(circle at top, #1e293b, #0f172a);
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }
        .card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 35px 30px;
            width: 100%;
            max-width: 400px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        h2 { font-size: 22px; margin-bottom: 8px; color: #fff; }
        p { font-size: 13px; color: #94a3b8; margin-bottom: 25px; }
        input[type="password"] {
            width: 100%;
            padding: 12px 14px;
            background: #0f172a;
            border: 1px solid #475569;
            border-radius: 10px;
            color: white;
            font-size: 16px;
            outline: none;
            margin-bottom: 18px;
        }
        input[type="password"]:focus {
            border-color: #2563eb;
            box-shadow: 0 0 0 3px rgba(37,99,235,0.3);
        }
        button {
            width: 100%;
            padding: 12px;
            background: #2563eb;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: 0.2s;
        }
        button:hover { background: #1d4ed8; }
        .error {
            background: rgba(220,38,38,0.2);
            border: 1px solid #dc2626;
            color: #f87171;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="card">
        <div style="font-size: 48px; margin-bottom: 10px;">🛡️</div>
        <h2>पालक नियंत्रण केंद्र</h2>
        <p>Child Safety & Remote Parental Dashboard</p>

        {% if error %}
        <div class="error">⚠️ {{ error }}</div>
        {% endif %}

        <form method="POST" action="/login">
            <input type="password" name="password" placeholder="पासवर्ड टाका..." required autofocus>
            <button type="submit">🔐 प्रवेश करा (Login)</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ChildMonitor - पालक नियंत्रण केंद्र</title>
    <!-- Leaflet OpenStreetMap -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        :root {
            --primary: #2563eb;
            --success: #16a34a;
            --danger: #dc2626;
            --warning: #ca8a04;
            --dark: #0f172a;
            --card: #ffffff;
            --bg: #f8fafc;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: var(--bg);
            color: #334155;
        }
        header {
            background: linear-gradient(135deg, #1e293b, #0f172a);
            color: white;
            padding: 15px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        header h1 { font-size: 20px; display: flex; align-items: center; gap: 10px; }
        .header-actions { display: flex; align-items: center; gap: 12px; }
        .pill { background: rgba(255,255,255,0.12); padding: 6px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }
        .btn-logout { background: #334155; color: white; padding: 7px 14px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: bold; }
        
        .container { max-width: 1400px; margin: 20px auto; padding: 0 20px; }
        .grid { display: grid; grid-template-columns: 360px 1fr; gap: 20px; }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }

        /* Device Cards */
        .device-card {
            background: white;
            border-radius: 14px;
            padding: 18px;
            border: 1px solid #e2e8f0;
            margin-bottom: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
        .device-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 10px;
            margin-bottom: 10px;
        }
        .device-title { font-size: 17px; font-weight: bold; color: #0f172a; }
        .badge { padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        .badge-online { background: #dcfce7; color: #15803d; }
        .badge-idle { background: #fef9c3; color: #a16207; }
        .badge-offline { background: #fee2e2; color: #b91c1c; }

        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            border: none;
            cursor: pointer;
            text-decoration: none;
            transition: 0.2s;
        }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: #1d4ed8; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-warning { background: var(--warning); color: white; }
        .btn-outline { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }
        .btn-outline:hover { background: #e2e8f0; }

        /* Map Box */
        .map-box { height: 420px; border-radius: 14px; overflow: hidden; border: 1px solid #e2e8f0; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
        #map { height: 100%; width: 100%; }

        /* Photos Section */
        .photo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px; margin-top: 15px; }
        .photo-card { background: white; border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 2px 6px rgba(0,0,0,0.04); }
        .photo-card img { width: 100%; height: 140px; object-fit: cover; cursor: pointer; }
        .photo-card .meta { padding: 8px; font-size: 11px; color: #64748b; }

        /* Modal Lightbox */
        #imgModal { display: none; position: fixed; z-index: 9999; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); align-items: center; justify-content: center; }
        #imgModal img { max-width: 90%; max-height: 85%; border-radius: 8px; }
    </style>
</head>
<body>
    <header>
        <h1>🛡️ पालक नियंत्रण केंद्र (ChildMonitor)</h1>
        <div class="header-actions">
            <span class="pill">📱 उपकरणे: <b>{{ devices|length }}</b></span>
            <span class="pill" style="background: rgba(22,163,74,0.25); color: #86efac;">🌐 IP: {{ local_ip }}:{{ port }}</span>
            <a href="/logout" class="btn-logout">🚪 बाहेर पडा</a>
        </div>
    </header>

    <div class="container">
        <div class="grid">
            <!-- डावी बाजू: जोडलेली उपकरणे -->
            <div>
                <h2 style="font-size: 17px; margin-bottom: 12px;">📱 जोडलेली उपकरणे</h2>

                {% if not devices %}
                <div class="device-card" style="text-align: center; color: #64748b; padding: 30px 15px;">
                    <div style="font-size: 40px; margin-bottom: 10px;">📲</div>
                    <b>कोणतेही डिव्हाइस जोडलेले नाही.</b><br>
                    <small>मोबाईल ॲप सुरू होताच डिव्हाइस आपोआप येथे दिसेल.</small>
                </div>
                {% endif %}

                {% for d in devices %}
                <div class="device-card">
                    <div class="device-header">
                        <div>
                            <div class="device-title">{{ d.name }}</div>
                            <div style="font-size: 11px; color: #64748b;">ID: {{ d.id }}</div>
                        </div>
                        <span class="badge {{ 'badge-online' if d.status == '🟢 ONLINE' else ('badge-idle' if d.status == '🟡 IDLE' else 'badge-offline') }}">{{ d.status }}</span>
                    </div>

                    <div style="font-size: 13px; margin: 8px 0;">
                        🔋 बॅटरी: <b>{{ d.battery }}%</b> {% if d.is_charging %}⚡ चार्जिंग{% endif %}
                    </div>
                    <div style="font-size: 12px; color: #64748b; margin-bottom: 10px;">
                        🕒 शेवटचे अपडेट: {{ d.last_seen }}
                    </div>

                    <!-- नियंत्रणे बटणे -->
                    <div class="btn-grid">
                        <a href="/command/{{ d.id }}/camera/FRONT" class="btn btn-primary">🤳 Front Cam</a>
                        <a href="/command/{{ d.id }}/camera/BACK" class="btn btn-primary">📷 Back Cam</a>
                        <a href="/command/{{ d.id }}/alarm/toggle" class="btn {{ 'btn-danger' if d.ring_alarm else 'btn-warning' }}" onclick="return confirm('मुलाच्या फोनवर अलार्म वाजवायचा आहे का?');">
                            🔔 {{ 'गजर चालू...' if d.ring_alarm else 'फोन वाजवा (Alarm)' }}
                        </a>
                        <a href="/delete_device/{{ d.id }}" class="btn btn-outline" style="color: var(--danger);" onclick="return confirm('डिव्हाइस कायमचे काढायचे आहे का?');">
                            🗑️ हटवा
                        </a>
                    </div>
                </div>
                {% endfor %}
            </div>

            <!-- उजवी बाजू: नकाशा आणि फोटो गॅलरी -->
            <div>
                <h2 style="font-size: 17px; margin-bottom: 12px;">🗺️ थेट स्थान (Live GPS Location)</h2>
                <div class="map-box">
                    <div id="map"></div>
                </div>

                <h2 style="font-size: 17px; margin: 20px 0 12px 0;">📸 कॅमेरा फोटो गॅलरी</h2>
                {% if not photos %}
                <p style="color: #64748b; font-size: 13px;">अद्याप कोणताही फोटो आलेला नाही. डावीकडील 'Front Cam' किंवा 'Back Cam' बटण दाबून फोटो मागवा.</p>
                {% else %}
                <div class="photo-grid">
                    {% for p in photos %}
                    <div class="photo-card">
                        <img src="/media/{{ p.filename }}" alt="Snapshot" onclick="showModal(this.src)" loading="lazy">
                        <div class="meta">
                            <b>{{ p.name }}</b><br>
                            🕒 {{ p.timestamp }}
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
        </div>
    </div>

    <!-- Lightbox Modal -->
    <div id="imgModal" onclick="this.style.display='none'">
        <img id="modalImg" src="">
    </div>

    <script>
        // Leaflet Map Init
        var map = L.map('map').setView([18.5204, 73.8567], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(map);

        var markers = {};
        {% for d in devices %}
            {% if d.latest_loc %}
                var pos = [{{ d.latest_loc.latitude }}, {{ d.latest_loc.longitude }}];
                markers['{{ d.id }}'] = L.marker(pos).addTo(map).bindPopup("<b>{{ d.name }}</b><br>अपडेट: {{ d.latest_loc.timestamp }}");
                map.setView(pos, 15);
            {% endif %}
        {% endfor %}

        function showModal(src) {
            document.getElementById('modalImg').src = src;
            document.getElementById('imgModal').style.display = 'flex';
        }

        // 5 सेकंदांनी डॅशबोर्ड आपोआप रीलोड करणे (Realtime Heartbeat)
        setInterval(function() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    if (data && data.devices) {
                        data.devices.forEach(d => {
                            if (d.latest_loc) {
                                var p = [d.latest_loc.latitude, d.latest_loc.longitude];
                                if (markers[d.id]) {
                                    markers[d.id].setLatLng(p);
                                } else {
                                    markers[d.id] = L.marker(p).addTo(map).bindPopup("<b>" + d.name + "</b>");
                                }
                            }
                        });
                    }
                })
                .catch(e => console.log(e));
        }, 6000);
    </script>
</body>
</html>
"""

# ================= AUTHENTICATION =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        pwd = request.form.get("password", "")
        if pwd == PARENT_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for('dashboard'))
        else:
            error = "चुकीचा पासवर्ड! कृपया पुन्हा प्रयत्न करा."
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def dashboard():
    if not is_auth():
        return redirect(url_for('login'))
    devices = database.get_devices()
    photos = database.get_photos(limit=30)
    return render_template_string(
        DASHBOARD_HTML,
        devices=devices,
        photos=photos,
        local_ip=get_local_ip(),
        port=SERVER_PORT
    )

# ================= PARENT COMMANDS =================

@app.route('/command/<device_id>/camera/<mode>')
def cmd_camera(device_id, mode):
    if not is_auth():
        return redirect(url_for('login'))
    database.set_command(device_id, "camera_mode", mode)
    return redirect(url_for('dashboard'))

@app.route('/command/<device_id>/alarm/toggle')
def cmd_alarm(device_id):
    if not is_auth():
        return redirect(url_for('login'))
    cmds = database.get_commands(device_id)
    new_val = 0 if cmds.get("ring_alarm") else 1
    database.set_command(device_id, "ring_alarm", new_val)
    return redirect(url_for('dashboard'))

@app.route('/delete_device/<device_id>')
def delete_device(device_id):
    if not is_auth():
        return redirect(url_for('login'))
    database.delete_device(device_id)
    return redirect(url_for('dashboard'))

# ================= ANDROID MOBILE APP APIS =================

@app.route('/api/heartbeat', methods=['POST'])
@app.route('/get_commands/<device_id>', methods=['POST'])  # Backwards compatible
def api_heartbeat(device_id=None):
    """मोबाईल ॲप दर ५-१० सेकंदांनी हे कॉल करते"""
    data = request.get_json(silent=True) or {}
    dev_id = device_id or data.get("device_id") or "device_default"
    dev_name = data.get("child_name") or data.get("name") or "Child_Phone"
    battery = data.get("battery_level") or data.get("battery")
    is_charging = data.get("is_charging")

    # डेटाबेस अपडेट
    database.update_device_heartbeat(dev_id, dev_name, battery, is_charging)

    # आदेश तपासणे
    cmds = database.get_commands(dev_id)
    return jsonify({
        "status": "ok",
        "device_id": dev_id,
        "camera_access": cmds.get("camera_mode", "OFF"),
        "ring_alarm": bool(cmds.get("ring_alarm", 0)),
        "location_access": True
    })

@app.route('/api/location', methods=['POST'])
@app.route('/update_location', methods=['POST'])  # Backwards compatible
def api_location():
    """मोबाईल ॲपकडून GPS स्थान घेणे"""
    data = request.get_json(silent=True) or {}
    dev_id = data.get("child_id") or data.get("device_id")
    lat = data.get("latitude")
    lon = data.get("longitude")
    acc = data.get("accuracy", 10.0)

    if dev_id and lat and lon:
        database.save_location(dev_id, lat, lon, acc)
        return jsonify({"status": "success"})
    return jsonify({"error": "invalid data"}), 400

@app.route('/api/upload_photo', methods=['POST'])
@app.route('/upload_camera_photo', methods=['POST'])  # Backwards compatible
def api_upload_photo():
    """मोबाईल कॅमेरा फोटो अपलोड करणे"""
    dev_id = request.form.get("child_id") or request.form.get("device_id") or "device_default"
    if 'image' in request.files:
        file = request.files['image']
        sec_name = f"{dev_id}_{int(datetime.datetime.now().timestamp())}.jpg"
        save_path = os.path.join(UPLOAD_DIR, sec_name)
        file.save(save_path)
        database.save_photo(dev_id, sec_name)
        database.clear_camera_command(dev_id)
        return jsonify({"status": "photo uploaded"})
    return jsonify({"error": "no file"}), 400

@app.route('/media/<filename>')
def serve_media(filename):
    return send_from_directory(UPLOAD_DIR, secure_filename(filename))

@app.route('/api/status')
def api_status():
    devices = database.get_devices()
    return jsonify({"devices": devices})

# ================= RUN SERVER =================

if __name__ == '__main__':
    port = SERVER_PORT
    print("=" * 65)
    print("🛡️ ChildMonitor Fresh Server सुरू झाला आहे!")
    print(f"👉 ब्राऊझर URL: http://127.0.0.1:{port}")
    print(f"👉 स्थानिक IP (Local LAN): http://{get_local_ip()}:{port}")
    print(f"🔐 पासवर्ड: {PARENT_PASSWORD}")
    print("=" * 65)
    app.run(host='0.0.0.0', port=port, debug=False)
