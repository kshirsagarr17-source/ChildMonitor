import os
import datetime
import csv
import io
from flask import (
    Flask, request, jsonify, render_template_string, 
    send_from_directory, redirect, url_for, session, Response
)
from werkzeug.utils import secure_filename
import database

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "shreeom-childmonitor-security-key-2026")

# पालक डॅशबोर्ड पासवर्ड
PARENT_PASSWORD = os.environ.get("PARENT_PASSWORD", "shreeom")

# डेटाबेस तयार / अपडेट करणे
database.init_db()

BASE_DATA_DIR = os.path.join(os.path.dirname(__file__), "Children_Data")
os.makedirs(BASE_DATA_DIR, exist_ok=True)

def get_safe_child_folder(child_id):
    """डिव्हाइससाठी सुरक्षित व एकसंध फोल्डर पाथ मिळवणे"""
    safe_id = "".join([c for c in str(child_id) if c.isalnum() or c in ("-", "_")])
    if not safe_id:
        safe_id = "device_default"
    folder_path = os.path.join(BASE_DATA_DIR, safe_id)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def save_text_backup(child_id, data_type, content):
    """डेटाबेससोबतच टेक्स्ट फाईलमध्ये बॅकअप ठेवणे"""
    try:
        child_folder = get_safe_child_folder(child_id)
        file_path = os.path.join(child_folder, f"{data_type}.txt")
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content + "\n")
    except Exception as e:
        print(f"[BACKUP ERROR] {e}")

# ================= AUTHENTICATION HELPERS =================

def is_authenticated():
    return session.get("authenticated") is True

# ================= LOGIN & LOGOUT ROUTES =================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>पालक लॉगिन - ChildMonitor</title>
    <style>
        :root {
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --bg: #0f172a;
            --card: #1e293b;
        }
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: radial-gradient(circle at top, #1e293b, #0f172a);
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .login-card {
            background: var(--card);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 35px 30px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            text-align: center;
        }
        .logo-icon {
            font-size: 50px;
            margin-bottom: 10px;
            display: inline-block;
        }
        h2 { margin: 0 0 8px 0; font-size: 24px; color: #ffffff; }
        p.subtitle { color: #94a3b8; font-size: 14px; margin-bottom: 25px; }
        .form-group { text-align: left; margin-bottom: 20px; }
        label { display: block; font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px; }
        input[type="password"] {
            width: 100%;
            padding: 12px 14px;
            background: #0f172a;
            border: 1px solid #475569;
            border-radius: 10px;
            color: white;
            font-size: 16px;
            outline: none;
            transition: 0.2s;
        }
        input[type="password"]:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.3);
        }
        .btn-submit {
            width: 100%;
            background: var(--primary);
            color: white;
            border: none;
            padding: 12px;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
        }
        .btn-submit:hover { background: var(--primary-dark); }
        .error-msg {
            background: rgba(220, 38, 38, 0.2);
            color: #f87171;
            border: 1px solid #dc2626;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .footer-text { margin-top: 25px; font-size: 12px; color: #64748b; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo-icon">🛡️</div>
        <h2>पालक नियंत्रण केंद्र</h2>
        <p class="subtitle">Child Safety & Parental Monitoring Dashboard</p>

        {% if error %}
        <div class="error-msg">⚠️ {{ error }}</div>
        {% endif %}

        <form method="POST" action="/login">
            <div class="form-group">
                <label for="password">पालक डॅशबोर्ड पासवर्ड (Password)</label>
                <input type="password" id="password" name="password" placeholder="पासवर्ड टाका..." required autofocus>
            </div>
            <button type="submit" class="btn-submit">🔐 प्रवेश करा (Login)</button>
        </form>

        <div class="footer-text">
            सुरक्षित बाल संरक्षण प्रणाली • ChildMonitor
        </div>
    </div>
</body>
</html>
"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_authenticated():
        return redirect(url_for('dashboard'))

    error = None
    if request.method == 'POST':
        entered_pw = request.form.get('password', '').strip()
        if entered_pw == PARENT_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('dashboard'))
        else:
            error = "चुकीचा पासवर्ड! कृपया योग्य पासवर्ड प्रविष्ट करा."

    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

# ================= CHILD APP API ENDPOINTS =================

@app.route('/get_commands/<child_id>', methods=['POST'])
def get_commands(child_id):
    """
    ॲप दर १५-३० सेकंदांनी सर्व्हरकडून नवीन आदेश मागवते.
    यासोबतच बॅटरी लेव्हल, चार्जिंग स्टेटस आणि वाय-फाय नाव अपडेट होते.
    """
    data = request.json or {}
    child_name = data.get('child_name', 'Unknown_Device')
    battery = data.get('battery_level', None)
    is_charging = data.get('is_charging', None)
    wifi_ssid = data.get('wifi_ssid', None)

    # डिव्हाइस डेटाबेसमध्ये नोंदवणे / अपडेट करणे
    database.register_or_update_device(
        device_id=child_id, 
        name=child_name, 
        battery=battery, 
        is_charging=is_charging, 
        wifi=wifi_ssid
    )

    # लो-बॅटरी अलर्ट (फक्त एकदाच, वारंवार स्पॅम न होता)
    if battery is not None and battery <= 15 and not is_charging:
        database.add_alert(
            device_id=child_id,
            alert_type="LOW_BATTERY",
            message=f"⚠️ {child_name} च्या मोबाईलची बॅटरी फक्त {battery}% शिल्लक आहे! चार्जिंगची गरज आहे."
        )

    controls = database.get_device_controls(child_id)
    if not controls:
        controls = {
            "device_id": child_id,
            "location_access": True,
            "message_access": False,
            "camera_access": "OFF",
            "audio_access": False,
            "gallery_access": False,
            "ring_alarm": False,
            "torch_access": False,
            "poll_interval": 30
        }

    return jsonify(controls), 200

@app.route('/update_location', methods=['POST'])
def update_location():
    """मुलाच्या फोनवरून GPS लोकेशन स्वीकारणे"""
    data = request.json or {}
    child_id = data.get('child_id')
    lat = data.get('latitude')
    lon = data.get('longitude')
    acc = data.get('accuracy', 0.0)
    time_str = data.get('time', database.now_str())

    if not child_id or lat is None or lon is None:
        return jsonify({"error": "Invalid data"}), 400

    try:
        lat = float(lat)
        lon = float(lon)
        acc = float(acc)
    except (ValueError, TypeError):
        return jsonify({"error": "Coordinates must be numbers"}), 400

    # डेटाबेसमध्ये लोकेशन साठवणे (जिओफेन्स सुरक्षित क्षेत्र आपोआप तपासले जाईल)
    database.add_location(child_id, lat, lon, acc, time_str)
    database.register_or_update_device(child_id)

    # टेक्स्ट फाईल बॅकअप
    log_entry = f"[{time_str}] -> Lat: {lat}, Lon: {lon}, Acc: {acc}m"
    save_text_backup(child_id, "location", log_entry)

    return jsonify({"status": "success"}), 200

@app.route('/log_sms', methods=['POST'])
def log_sms():
    """एसएमएस लॉग्स स्वीकारणे"""
    data = request.json or {}
    child_id = data.get('child_id')
    sender = data.get('sender', 'Unknown')
    message = data.get('message', '')
    time_str = data.get('time', database.now_str())

    if not child_id:
        return jsonify({"error": "child_id required"}), 400

    database.add_sms_log(child_id, sender, message, time_str)
    save_text_backup(child_id, "sms", f"[{time_str}] -> From: {sender} | Msg: {message}")

    return jsonify({"status": "success"}), 200

@app.route('/upload_camera_photo', methods=['POST'])
def upload_camera_photo():
    """कॅमेऱ्याने काढलेला फोटो स्वीकारणे"""
    if 'image' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['image']
    child_id = request.form.get('child_id')
    
    if not child_id:
        return jsonify({"error": "child_id required"}), 400

    filename = secure_filename(file.filename or f"capture_{int(datetime.datetime.now().timestamp())}.jpg")
    target_dir = os.path.join(get_safe_child_folder(child_id), "Camera_Captures")
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, filename)
    file.save(full_path)

    # डेटाबेसमध्ये नोंद
    database.add_media_record(child_id, "image", full_path, filename)

    # फोटो मिळताच कॅमेरा कमांड पुन्हा OFF करणे
    database.update_device_control(child_id, "camera_access", "OFF")

    return jsonify({"status": "success", "filename": filename}), 200

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    """रेकॉर्ड केलेला ऑडिओ स्वीकारणे"""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
    
    file = request.files['audio']
    child_id = request.form.get('child_id')

    if not child_id:
        return jsonify({"error": "child_id required"}), 400

    filename = secure_filename(file.filename or f"audio_{int(datetime.datetime.now().timestamp())}.m4a")
    target_dir = os.path.join(get_safe_child_folder(child_id), "Audio_Records")
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, filename)
    file.save(full_path)

    # डेटाबेसमध्ये नोंद
    database.add_media_record(child_id, "audio", full_path, filename)
    
    # ऑडिओ कमांड पुन्हा OFF करणे
    database.update_device_control(child_id, "audio_access", 0)

    return jsonify({"status": "success", "filename": filename}), 200

@app.route('/trigger_sos', methods=['POST'])
def trigger_sos():
    """मुलाने SOS बटण दाबल्यास तात्काळ अलर्ट आणि कमांड्स सक्रिय करणे"""
    data = request.json or {}
    child_id = data.get('child_id')
    lat = data.get('latitude')
    lon = data.get('longitude')
    
    if not child_id:
        return jsonify({"error": "child_id required"}), 400

    # तात्काळ हाय-प्रायॉरिटी आणीबाणी अलर्ट तयार करणे
    database.add_alert(
        device_id=child_id,
        alert_type="SOS",
        message="🚨 आणीबाणी (EMERGENCY SOS): मुलाने मदतीचा तात्काळ इशारा दिला आहे!",
        lat=lat,
        lon=lon
    )

    # तात्काळ कॅमेरा आणि ऑडिओ चालू करण्याचे आदेश देणे
    database.update_device_control(child_id, "location_access", 1)
    database.update_device_control(child_id, "camera_access", "FRONT")
    database.update_device_control(child_id, "audio_access", 1)

    print(f"[SOS TRIGGERED] Device: {child_id} at {lat}, {lon}")
    return jsonify({"status": "SOS received, emergency protocols activated"}), 200

# ================= MEDIA SERVING =================

@app.route('/media/<child_id>/<folder_type>/<filename>')
def serve_media(child_id, folder_type, filename):
    """डॅशबोर्डवर थेट फोटो पाहण्यासाठी आणि ऑडिओ ऐकण्यासाठी"""
    if not is_authenticated():
        return redirect(url_for('login'))

    allowed_folders = {"Camera_Captures", "Audio_Records"}
    if folder_type not in allowed_folders:
        return "Access denied", 403
    
    sec_filename = secure_filename(filename)
    safe_folder = get_safe_child_folder(child_id)
    folder_path = os.path.join(safe_folder, folder_type)

    if os.path.exists(os.path.join(folder_path, sec_filename)):
        return send_from_directory(folder_path, sec_filename)

    # जुन्या फोल्डर स्ट्रक्चरसाठी फॉलबॅक (Backward Compatibility)
    for prefix in ["My_Test_Phone_", "Device_", "Unknown_"]:
        alt_path = os.path.join(BASE_DATA_DIR, f"{prefix}{child_id}", folder_type)
        if os.path.exists(os.path.join(alt_path, sec_filename)):
            return send_from_directory(alt_path, sec_filename)

    return "File not found", 404

# ================= LIVE STATUS API (AJAX POLLING) =================

@app.route('/api/live_status')
def api_live_status():
    """डॅशबोर्ड संपूर्ण रिफ्रेश न करता डेटा थेट अपडेट करण्यासाठी AJAX API"""
    if not is_authenticated():
        return jsonify({"error": "Unauthorized"}), 401

    devices = database.get_all_devices()
    now_dt = datetime.datetime.now()

    result = []
    for d in devices:
        cid = d["id"]
        last_seen = d["last_seen"]
        diff_sec = 9999
        if isinstance(last_seen, str):
            try:
                last_seen_dt = datetime.datetime.strptime(last_seen, "%Y-%m-%d %H:%M:%S")
                diff_sec = (now_dt - last_seen_dt).total_seconds()
            except Exception:
                try:
                    last_seen_dt = datetime.datetime.fromisoformat(last_seen)
                    diff_sec = (now_dt - last_seen_dt).total_seconds()
                except Exception:
                    diff_sec = 9999

        status_str = "🟢 ONLINE" if diff_sec < 90 else ("🟡 IDLE" if diff_sec < 300 else "🔴 OFFLINE")
        latest_loc = database.get_latest_location(cid)

        result.append({
            "id": cid,
            "name": d["name"],
            "battery_level": d["battery_level"],
            "is_charging": bool(d["is_charging"]),
            "wifi_ssid": d["wifi_ssid"],
            "last_seen": str(d["last_seen"]),
            "status": status_str,
            "latest_loc": latest_loc,
            "camera_access": d.get("camera_access", "OFF"),
            "audio_access": bool(d.get("audio_access", 0)),
            "ring_alarm": bool(d.get("ring_alarm", 0)),
            "torch_access": bool(d.get("torch_access", 0))
        })

    active_alerts = database.get_active_alerts()
    return jsonify({
        "devices": result,
        "active_alerts": active_alerts,
        "server_time": database.now_str()
    })

# ================= WEB DASHBOARD =================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>पालक नियंत्रण व सुरक्षा केंद्र</title>
    <!-- Leaflet CSS & JS for OpenStreetMap -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        :root {
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --danger: #dc2626;
            --success: #16a34a;
            --warning: #ca8a04;
            --dark: #0f172a;
            --card-bg: #ffffff;
            --bg: #f8fafc;
        }
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: var(--bg); color: #334155; }
        header { background: linear-gradient(135deg, #1e293b, #0f172a); color: white; padding: 16px 25px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        header h1 { margin: 0; font-size: 20px; display: flex; align-items: center; gap: 10px; }
        .header-actions { display: flex; align-items: center; gap: 12px; }
        .stat-pill { background: rgba(255,255,255,0.12); padding: 6px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
        .btn-logout { background: #334155; color: white; border: none; padding: 7px 14px; border-radius: 8px; font-size: 13px; font-weight: 600; text-decoration: none; transition: 0.2s; }
        .btn-logout:hover { background: #475569; }

        .container { padding: 20px 25px; max-width: 1500px; margin: 0 auto; }

        /* Alerts Section */
        .alerts-wrapper { margin-bottom: 20px; }
        .alert-banner { background: #fee2e2; border-left: 6px solid var(--danger); padding: 12px 18px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 6px rgba(220,38,38,0.1); }
        .alert-banner b { color: var(--danger); font-size: 15px; }

        /* Grid Layout */
        .grid-main { display: grid; grid-template-columns: 370px 1fr; gap: 20px; }
        @media (max-width: 950px) {
            .grid-main { grid-template-columns: 1fr; }
        }

        /* Device Cards */
        .device-card { background: var(--card-bg); border-radius: 14px; padding: 18px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; margin-bottom: 18px; }
        .device-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 12px; }
        .device-name { font-size: 17px; font-weight: 700; color: #0f172a; }

        .badge { padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .badge-online { background: #dcfce7; color: #15803d; }
        .badge-idle { background: #fef9c3; color: #a16207; }
        .badge-offline { background: #fee2e2; color: #b91c1c; }

        .battery-meter { display: flex; align-items: center; gap: 8px; margin: 8px 0; font-size: 13px; }
        .battery-bar { width: 90px; height: 10px; background: #e2e8f0; border-radius: 5px; overflow: hidden; }
        .battery-fill { height: 100%; transition: width 0.3s; }

        .btn { display: inline-flex; align-items: center; justify-content: center; gap: 5px; padding: 7px 11px; font-size: 12px; font-weight: 600; border-radius: 8px; border: none; cursor: pointer; text-decoration: none; transition: 0.2s ease; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-dark); }
        .btn-success { background: var(--success); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-warning { background: var(--warning); color: white; }
        .btn-outline { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }
        .btn-outline:hover { background: #e2e8f0; }

        .controls-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
        .full-width-btn { grid-column: span 2; }

        /* Map Box */
        .map-container { height: 440px; border-radius: 14px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; margin-bottom: 20px; position: relative; }
        #map { height: 100%; width: 100%; }
        .map-hint { position: absolute; bottom: 10px; left: 10px; z-index: 1000; background: rgba(15,23,42,0.85); color: white; padding: 6px 12px; border-radius: 6px; font-size: 12px; pointer-events: none; }

        /* Tabs Section */
        .tabs-header { display: flex; gap: 8px; border-bottom: 2px solid #e2e8f0; margin-bottom: 18px; overflow-x: auto; }
        .tab-btn { padding: 10px 16px; background: none; border: none; font-size: 14px; font-weight: 600; color: #64748b; cursor: pointer; border-bottom: 3px solid transparent; white-space: nowrap; }
        .tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* Photo Gallery */
        .photo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; }
        .photo-card { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
        .photo-card img { width: 100%; height: 140px; object-fit: cover; cursor: pointer; transition: 0.3s; }
        .photo-card img:hover { transform: scale(1.03); }
        .photo-card .info { padding: 8px 10px; font-size: 11px; color: #64748b; }

        /* Audio List */
        .audio-item { background: white; border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #e2e8f0; flex-wrap: wrap; gap: 10px; }
        
        /* SMS List */
        .sms-item { background: white; border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; border-left: 4px solid var(--primary); box-shadow: 0 2px 4px rgba(0,0,0,0.03); }
        .sms-header { display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; margin-bottom: 5px; color: #0f172a; }
        .sms-body { font-size: 14px; color: #475569; }

        /* Geofence Form */
        .geofence-form { background: white; padding: 16px; border-radius: 10px; border: 1px solid #e2e8f0; margin-bottom: 18px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
        .geofence-form input { padding: 8px 12px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 13px; }

        /* Modal Lightbox */
        #imgModal { display: none; position: fixed; z-index: 9999; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); align-items: center; justify-content: center; }
        #imgModal img { max-width: 90%; max-height: 85%; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.8); }
    </style>
</head>
<body>
    <header>
        <h1>🛡️ पालक नियंत्रण व सुरक्षा केंद्र (ChildMonitor)</h1>
        <div class="header-actions">
            <span class="stat-pill">📱 डिव्हाइसेस: <b id="stat-devices-count">{{ devices|length }}</b></span>
            <span class="stat-pill">🚨 अलर्ट्स: <b id="stat-alerts-count">{{ active_alerts|length }}</b></span>
            <span class="stat-pill" style="background: rgba(22,163,74,0.25); color: #86efac;">● लाईव्ह मोड</span>
            <a href="/logout" class="btn-logout">🚪 बाहेर पडा (Logout)</a>
        </div>
    </header>

    <div class="container">
        <!-- सक्रिय आणीबाणी सूचना (Alerts Banner) -->
        <div id="alerts-container" class="alerts-wrapper">
            {% if active_alerts %}
            <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
                <a href="/resolve_all_alerts" class="btn btn-outline" style="font-size: 11px;">✓ सर्व अलर्ट्स मिटवा (Clear All)</a>
            </div>
            {% endif %}
            {% for alert in active_alerts %}
            <div class="alert-banner">
                <div>
                    <b>{{ alert.alert_type }}:</b> {{ alert.message }}
                    <span style="font-size: 12px; color: #64748b; margin-left: 10px;">({{ alert.timestamp }})</span>
                </div>
                <a href="/resolve_alert/{{ alert.id }}" class="btn btn-outline" style="background: white;">खूण मिटवा (Resolve)</a>
            </div>
            {% endfor %}
        </div>

        <div class="grid-main">
            <!-- डावी बाजू: जोडलेली उपकरणे व थेट नियंत्रणे -->
            <div class="devices-column">
                <h2 style="font-size: 17px; margin: 0 0 12px 0;">📱 नोंदणीकृत उपकरणे</h2>
                
                {% if not devices %}
                <div class="device-card" style="text-align: center; color: #64748b;">
                    <b>⚠️ कोणतेही डिव्हाइस जोडलेले नाही.</b><br>
                    मुलाच्या फोनवर ॲप सुरू होताच डिव्हाइस आपोआप येथे दिसेल.
                </div>
                {% endif %}

                {% for d in devices %}
                <div class="device-card" id="card-{{ d.id }}">
                    <div class="device-header">
                        <div>
                            <span class="device-name">{{ d.name }}</span>
                            <div style="font-size: 11px; color: #64748b;">ID: {{ d.id }}</div>
                        </div>
                        <span class="badge {{ 'badge-online' if status[d.id] == '🟢 ONLINE' else ('badge-idle' if status[d.id] == '🟡 IDLE' else 'badge-offline') }}" id="badge-{{ d.id }}">{{ status[d.id] }}</span>
                    </div>

                    <!-- बॅटरी आणि नेटवर्क माहिती -->
                    <div class="battery-meter">
                        <span>🔋 बॅटरी: <b>{{ d.battery_level }}%</b></span>
                        <div class="battery-bar">
                            <div class="battery-fill" style="width: {{ d.battery_level }}%; background-color: {{ '#16a34a' if d.battery_level > 30 else '#dc2626' }};"></div>
                        </div>
                        {% if d.is_charging %}<span>⚡ चार्जिंग</span>{% endif %}
                    </div>
                    <div style="font-size: 12px; color: #64748b; margin-bottom: 10px;">
                        📶 नेटवर्क: <b>{{ d.wifi_ssid }}</b> | 🕒 पाहिले: {{ d.last_seen }}
                    </div>

                    <!-- रिमोट नियंत्रणे (Remote Commands) -->
                    <div class="controls-grid">
                        <a href="/set_camera/{{ d.id }}/FRONT" class="btn btn-primary">
                            🤳 Front Cam
                        </a>
                        <a href="/set_camera/{{ d.id }}/BACK" class="btn btn-primary">
                            📷 Back Cam
                        </a>
                        <a href="/toggle/{{ d.id }}/audio_access" class="btn {{ 'btn-success' if d.audio_access else 'btn-outline' }}">
                            🎙️ आवाज {{ 'चालू' if d.audio_access else 'बंद' }}
                        </a>
                        <a href="/trigger_alarm/{{ d.id }}" class="btn {{ 'btn-danger' if d.ring_alarm else 'btn-warning' }}" onclick="return confirm('मुलाचा फोन मोठ्या आवाजात वाजवायचा आहे का?');">
                            🔔 {{ 'गजर चालू...' if d.ring_alarm else 'फोन वाजवा (Alarm)' }}
                        </a>
                        <a href="/toggle/{{ d.id }}/torch_access" class="btn {{ 'btn-success' if d.torch_access else 'btn-outline' }}">
                            💡 टॉर्च {{ 'चालू' if d.torch_access else 'बंद' }}
                        </a>
                        <a href="/toggle/{{ d.id }}/location_access" class="btn {{ 'btn-success' if d.location_access else 'btn-outline' }}">
                            📍 GPS {{ 'चालू' if d.location_access else 'बंद' }}
                        </a>
                        {% set loc = details[d.id].latest_loc %}
                        {% if loc %}
                        <a href="https://www.google.com/maps/search/?api=1&query={{ loc.latitude }},{{ loc.longitude }}" target="_blank" class="btn btn-outline full-width-btn" style="color: #2563eb;">
                            🗺️ Google Maps वर दिशा पहा
                        </a>
                        {% endif %}
                        <a href="/delete_device/{{ d.id }}" class="btn btn-outline full-width-btn" style="color: var(--danger); font-size: 11px;" onclick="return confirm('खात्री आहे? हे डिव्हाइस आणि त्याचा सर्व डेटा कायमचा काढला जाईल.');">
                            🗑️ डिव्हाइस हटवा
                        </a>
                    </div>
                </div>
                {% endfor %}
            </div>

            <!-- उजवी बाजू: थेट नकाशा आणि मल्टीमीडिया टॅब्स -->
            <div class="content-column">
                <!-- OpenStreetMap नकाशा -->
                <div class="map-container">
                    <div id="map"></div>
                    <div class="map-hint">💡 टीप: सुरक्षित झोन (Geofence) तयार करण्यासाठी नकाशावर कुठेही क्लिक करा.</div>
                </div>

                <!-- टॅब्स नेव्हिगेशन -->
                <div class="tabs-header">
                    <button class="tab-btn active" onclick="openTab(event, 'tab-photos')">📸 फोटो गॅलरी</button>
                    <button class="tab-btn" onclick="openTab(event, 'tab-audios')">🎙️ ऑडिओ रेकॉर्ड्स</button>
                    <button class="tab-btn" onclick="openTab(event, 'tab-sms')">💬 संदेश (SMS)</button>
                    <button class="tab-btn" onclick="openTab(event, 'tab-geofence')">🌐 सुरक्षित झोन (Geofence)</button>
                    <button class="tab-btn" onclick="openTab(event, 'tab-history')">📊 प्रवास इतिहास (History)</button>
                </div>

                <!-- टॅब १: फोटो गॅलरी -->
                <div id="tab-photos" class="tab-content active">
                    <div class="photo-grid">
                        {% set ns = namespace(found=false) %}
                        {% for d in devices %}
                            {% for photo in details[d.id].photos %}
                                {% set ns.found = true %}
                                <div class="photo-card">
                                    <img src="/media/{{ d.id }}/Camera_Captures/{{ photo.filename }}" alt="कॅमेरा फोटो" loading="lazy" onclick="showModal(this.src)">
                                    <div class="info">
                                        <b>{{ d.name }}</b><br>
                                        🕒 {{ photo.timestamp }}
                                    </div>
                                </div>
                            {% endfor %}
                        {% endfor %}
                        {% if not ns.found %}
                            <p style="color: #64748b; padding: 20px;">कोणतेही फोटो कॅप्चर झालेले नाहीत. डावीकडील 'Front Cam' किंवा 'Back Cam' बटण दाबून फोटो मागवा.</p>
                        {% endif %}
                    </div>
                </div>

                <!-- टॅब २: ऑडिओ रेकॉर्ड्स -->
                <div id="tab-audios" class="tab-content">
                    {% set ns2 = namespace(found=false) %}
                    {% for d in devices %}
                        {% for aud in details[d.id].audios %}
                            {% set ns2.found = true %}
                            <div class="audio-item">
                                <div>
                                    <b>{{ d.name }}</b> - <code>{{ aud.filename }}</code><br>
                                    <small style="color: #64748b;">🕒 {{ aud.timestamp }}</small>
                                </div>
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <audio controls src="/media/{{ d.id }}/Audio_Records/{{ aud.filename }}"></audio>
                                    <a href="/media/{{ d.id }}/Audio_Records/{{ aud.filename }}" download class="btn btn-outline" style="font-size: 11px;">⬇️ डाउनलोड</a>
                                </div>
                            </div>
                        {% endfor %}
                    {% endfor %}
                    {% if not ns2.found %}
                        <p style="color: #64748b; padding: 20px;">कोणतेही ऑडिओ रेकॉर्ड्स उपलब्ध नाहीत. 'आवाज चालू' वर क्लिक करून ऑडिओ मागवा.</p>
                    {% endif %}
                </div>

                <!-- टॅब ३: एसएमएस लॉग्स -->
                <div id="tab-sms" class="tab-content">
                    {% set ns3 = namespace(found=false) %}
                    {% for d in devices %}
                        {% for s in details[d.id].sms %}
                            {% set ns3.found = true %}
                            <div class="sms-item">
                                <div class="sms-header">
                                    <span>📲 {{ d.name }} &larr; प्रेषक: <b>{{ s.sender }}</b></span>
                                    <span style="font-weight: normal; color: #64748b;">{{ s.timestamp }}</span>
                                </div>
                                <div class="sms-body">{{ s.message }}</div>
                            </div>
                        {% endfor %}
                    {% endfor %}
                    {% if not ns3.found %}
                        <p style="color: #64748b; padding: 20px;">कोणतेही एसएमएस रेकॉर्ड्स नाहीत.</p>
                    {% endif %}
                </div>

                <!-- टॅब ४: जिओफेन्स (सुरक्षित क्षेत्रे) -->
                <div id="tab-geofence" class="tab-content">
                    {% for d in devices %}
                    <div style="margin-bottom: 25px;">
                        <h4 style="margin: 0 0 10px 0;">🛡️ {{ d.name }} साठी सुरक्षित झोन (Geofence) जोडा</h4>
                        <form action="/add_geofence" method="POST" class="geofence-form">
                            <input type="hidden" name="device_id" value="{{ d.id }}">
                            <input type="text" name="name" placeholder="झोनचे नाव (उदा. घर, शाळा)" required style="flex: 1; min-width: 140px;">
                            <input type="number" step="any" id="geo-lat-{{ d.id }}" name="latitude" placeholder="अक्षांश (Latitude)" required style="width: 120px;">
                            <input type="number" step="any" id="geo-lon-{{ d.id }}" name="longitude" placeholder="रेखांश (Longitude)" required style="width: 120px;">
                            <input type="number" name="radius_meters" placeholder="त्रिज्या (मी)" value="200" required style="width: 90px;">
                            <button type="submit" class="btn btn-primary">+ सुरक्षित झोन जोडा</button>
                        </form>

                        <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; font-size: 13px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                            <tr style="background: #f1f5f9; text-align: left;">
                                <th style="padding: 10px;">झोन नाव</th>
                                <th style="padding: 10px;">स्थान (Lat, Lon)</th>
                                <th style="padding: 10px;">त्रिज्या</th>
                                <th style="padding: 10px;">कृती</th>
                            </tr>
                            {% for f in details[d.id].geofences %}
                            <tr style="border-bottom: 1px solid #f1f5f9;">
                                <td style="padding: 10px;"><b>{{ f.name }}</b></td>
                                <td style="padding: 10px;">{{ f.latitude }}, {{ f.longitude }}</td>
                                <td style="padding: 10px;">{{ f.radius_meters }}m</td>
                                <td style="padding: 10px;">
                                    <a href="/delete_geofence/{{ f.id }}" style="color: var(--danger); text-decoration: none; font-weight: bold;" onclick="return confirm('सुरक्षित झोन काढायचा आहे का?');">हटवा</a>
                                </td>
                            </tr>
                            {% endfor %}
                        </table>
                    </div>
                    {% endfor %}
                </div>

                <!-- टॅब ५: प्रवास इतिहास (Location History & CSV) -->
                <div id="tab-history" class="tab-content">
                    {% for d in devices %}
                    <div style="margin-bottom: 25px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <h4 style="margin: 0;">📍 {{ d.name }} - प्रवास नोंदी</h4>
                            <a href="/export_locations/{{ d.id }}" class="btn btn-outline" style="font-size: 12px;">📊 CSV एक्सेल डाउनलोड करा</a>
                        </div>
                        <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; font-size: 13px;">
                            <tr style="background: #f1f5f9; text-align: left;">
                                <th style="padding: 8px 10px;">वेळ (Timestamp)</th>
                                <th style="padding: 8px 10px;">अक्षांश (Latitude)</th>
                                <th style="padding: 8px 10px;">रेखांश (Longitude)</th>
                                <th style="padding: 8px 10px;">अचूकता (Accuracy)</th>
                            </tr>
                            {% for loc in details[d.id].loc_history[-15:]|reverse %}
                            <tr style="border-bottom: 1px solid #f1f5f9;">
                                <td style="padding: 8px 10px;">{{ loc.timestamp }}</td>
                                <td style="padding: 8px 10px;">{{ loc.latitude }}</td>
                                <td style="padding: 8px 10px;">{{ loc.longitude }}</td>
                                <td style="padding: 8px 10px;">{{ loc.accuracy }}m</td>
                            </tr>
                            {% endfor %}
                        </table>
                    </div>
                    {% endfor %}
                </div>

            </div>
        </div>
    </div>

    <!-- Image Modal Lightbox -->
    <div id="imgModal" onclick="this.style.display='none'">
        <img id="modalImg" src="">
    </div>

    <script>
        // Leaflet Map Initialization
        var map = L.map('map').setView([19.0760, 72.8777], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap'
        }).addTo(map);

        var markers = {};
        var pathLayers = {};
        var bounds = [];

        // Distinct colors for multiple devices
        var colors = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c'];

        {% for d in devices %}
            {% set loc = details[d.id].latest_loc %}
            {% if loc %}
                markers['{{ d.id }}'] = L.marker([{{ loc.latitude }}, {{ loc.longitude }}]).addTo(map)
                    .bindPopup("<b>{{ d.name }}</b><br>🔋 {{ d.battery_level }}%<br>🕒 {{ loc.timestamp }}");
                bounds.push([{{ loc.latitude }}, {{ loc.longitude }}]);
            {% endif %}

            // Route Polyline
            var points_{{ loop.index }} = [
                {% for p in details[d.id].loc_history %}
                    [{{ p.latitude }}, {{ p.longitude }}],
                {% endfor %}
            ];
            if (points_{{ loop.index }}.length > 1) {
                var c = colors[{{ loop.index0 }} % colors.length];
                pathLayers['{{ d.id }}'] = L.polyline(points_{{ loop.index }}, {color: c, weight: 4, opacity: 0.75}).addTo(map);
            }

            // Geofence Circles
            {% for f in details[d.id].geofences %}
                L.circle([{{ f.latitude }}, {{ f.longitude }}], {
                    color: '#16a34a',
                    fillColor: '#86efac',
                    fillOpacity: 0.25,
                    radius: {{ f.radius_meters }}
                }).addTo(map).bindPopup("<b>सुरक्षित झोन: {{ f.name }}</b><br>त्रिज्या: {{ f.radius_meters }}m");
            {% endfor %}
        {% endfor %}

        if (bounds.length > 0) {
            map.fitBounds(bounds, {padding: [40, 40], maxZoom: 15});
        }

        // Click map to fill Geofence form coordinates
        map.on('click', function(e) {
            var lat = e.latlng.lat.toFixed(6);
            var lon = e.latlng.lng.toFixed(6);
            {% if devices %}
                var firstDevId = '{{ devices[0].id }}';
                var latInput = document.getElementById('geo-lat-' + firstDevId);
                var lonInput = document.getElementById('geo-lon-' + firstDevId);
                if (latInput && lonInput) {
                    latInput.value = lat;
                    lonInput.value = lon;
                    alert("📍 नकाशावरील स्थान निवडले गेले आहे:\\nLatitude: " + lat + "\\nLongitude: " + lon);
                }
            {% endif %}
        });

        // Tabs Switcher with LocalStorage memory
        function openTab(evt, tabId) {
            var tabcontents = document.getElementsByClassName("tab-content");
            for (var i = 0; i < tabcontents.length; i++) {
                tabcontents[i].classList.remove("active");
            }
            var tablinks = document.getElementsByClassName("tab-btn");
            for (var i = 0; i < tablinks.length; i++) {
                tablinks[i].classList.remove("active");
            }
            document.getElementById(tabId).classList.add("active");
            if (evt) evt.currentTarget.classList.add("active");
            localStorage.setItem("activeTab", tabId);
        }

        // Restore tab
        var savedTab = localStorage.getItem("activeTab");
        if (savedTab && document.getElementById(savedTab)) {
            var btn = document.querySelector("button[onclick*='" + savedTab + "']");
            if (btn) btn.click();
        }

        // Lightbox Modal
        function showModal(src) {
            document.getElementById('modalImg').src = src;
            document.getElementById('imgModal').style.display = 'flex';
        }

        // Real-Time AJAX Heartbeat Polling (No Full Page Reload!)
        setInterval(function() {
            fetch('/api/live_status')
                .then(r => r.json())
                .then(data => {
                    if (!data || !data.devices) return;
                    data.devices.forEach(d => {
                        var badge = document.getElementById('badge-' + d.id);
                        if (badge) {
                            badge.innerText = d.status;
                            badge.className = 'badge ' + (d.status.includes('ONLINE') ? 'badge-online' : (d.status.includes('IDLE') ? 'badge-idle' : 'badge-offline'));
                        }
                        if (d.latest_loc) {
                            var pos = [d.latest_loc.latitude, d.latest_loc.longitude];
                            if (markers[d.id]) {
                                markers[d.id].setLatLng(pos);
                            } else {
                                markers[d.id] = L.marker(pos).addTo(map).bindPopup("<b>" + d.name + "</b>");
                            }
                        }
                    });
                })
                .catch(err => console.log("Live poll error", err));
        }, 8000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    if not is_authenticated():
        return redirect(url_for('login'))

    devices = database.get_all_devices()
    now_dt = datetime.datetime.now()

    # डिव्हाइस ऑनलाइन / ऑफलाइन स्टेटस (९० सेकंदांची मर्यादा)
    devices_status = {}
    for d in devices:
        last_seen = d["last_seen"]
        diff_sec = 9999
        if isinstance(last_seen, str):
            try:
                last_seen_dt = datetime.datetime.strptime(last_seen, "%Y-%m-%d %H:%M:%S")
                diff_sec = (now_dt - last_seen_dt).total_seconds()
            except Exception:
                try:
                    last_seen_dt = datetime.datetime.fromisoformat(last_seen)
                    diff_sec = (now_dt - last_seen_dt).total_seconds()
                except Exception:
                    diff_sec = 9999

        devices_status[d["id"]] = "🟢 ONLINE" if diff_sec < 90 else ("🟡 IDLE" if diff_sec < 300 else "🔴 OFFLINE")

    # सक्रिय अलर्ट्स
    active_alerts = database.get_active_alerts()

    # प्रत्येक डिव्हाइसचे ताजे लोकेशन, फोटो, ऑडिओ आणि जिओफेन्स
    device_details = {}
    for d in devices:
        cid = d["id"]
        device_details[cid] = {
            "latest_loc": database.get_latest_location(cid),
            "loc_history": database.get_location_history(cid, limit=50),
            "photos": database.get_media_records(cid, media_type="image", limit=16),
            "audios": database.get_media_records(cid, media_type="audio", limit=12),
            "sms": database.get_sms_logs(cid, limit=15),
            "geofences": database.get_geofences(cid)
        }

    return render_template_string(
        DASHBOARD_HTML, 
        devices=devices, 
        status=devices_status, 
        details=device_details, 
        active_alerts=active_alerts
    )

# ================= ACTIONS & TOGGLES =================

@app.route('/toggle/<child_id>/<feature>')
def toggle_feature(child_id, feature):
    if not is_authenticated():
        return redirect(url_for('login'))
    controls = database.get_device_controls(child_id)
    if controls and feature in controls:
        curr = controls[feature]
        new_val = 0 if curr else 1
        database.update_device_control(child_id, feature, new_val)
    return redirect(url_for('dashboard'))

@app.route('/trigger_alarm/<child_id>')
def trigger_alarm(child_id):
    if not is_authenticated():
        return redirect(url_for('login'))
    controls = database.get_device_controls(child_id)
    if controls:
        curr = controls.get("ring_alarm", False)
        new_val = 0 if curr else 1
        database.update_device_control(child_id, "ring_alarm", new_val)
    return redirect(url_for('dashboard'))

@app.route('/set_camera/<child_id>/<mode>')
def set_camera(child_id, mode):
    if not is_authenticated():
        return redirect(url_for('login'))
    if mode in ["FRONT", "BACK", "OFF"]:
        database.update_device_control(child_id, "camera_access", mode)
    return redirect(url_for('dashboard'))

@app.route('/resolve_alert/<int:alert_id>')
def resolve_alert(alert_id):
    if not is_authenticated():
        return redirect(url_for('login'))
    database.resolve_alert(alert_id)
    return redirect(url_for('dashboard'))

@app.route('/resolve_all_alerts')
def resolve_all_alerts():
    if not is_authenticated():
        return redirect(url_for('login'))
    database.resolve_all_alerts()
    return redirect(url_for('dashboard'))

@app.route('/delete_device/<child_id>')
def delete_device(child_id):
    if not is_authenticated():
        return redirect(url_for('login'))
    database.delete_device(child_id)
    return redirect(url_for('dashboard'))

@app.route('/add_geofence', methods=['POST'])
def add_geofence():
    if not is_authenticated():
        return redirect(url_for('login'))
    device_id = request.form.get('device_id')
    name = request.form.get('name', 'Safe Zone').strip()
    try:
        lat = float(request.form.get('latitude', 0.0))
        lon = float(request.form.get('longitude', 0.0))
        radius = float(request.form.get('radius_meters', 200))
        if device_id and name and lat and lon:
            database.add_geofence(device_id, name, lat, lon, radius)
    except (ValueError, TypeError) as e:
        print("[GEOFENCE ERROR]", e)
    return redirect(url_for('dashboard'))

@app.route('/delete_geofence/<int:fence_id>')
def delete_geofence(fence_id):
    if not is_authenticated():
        return redirect(url_for('login'))
    database.delete_geofence(fence_id)
    return redirect(url_for('dashboard'))

@app.route('/export_locations/<child_id>')
def export_locations(child_id):
    """मुलाच्या प्रवासाचा इतिहास CSV एक्सेल फाईल स्वरूपात डाउनलोड करणे"""
    if not is_authenticated():
        return redirect(url_for('login'))
    
    locations = database.get_location_history(child_id, limit=500)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Device ID", "Latitude", "Longitude", "Accuracy (m)", "Timestamp"])
    for loc in locations:
        writer.writerow([loc.get("id"), child_id, loc.get("latitude"), loc.get("longitude"), loc.get("accuracy"), loc.get("timestamp")])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=locations_{child_id}.csv"}
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print("=" * 65)
    print("🛡️ पालक नियंत्रण व सुरक्षा सर्व्हर (ChildMonitor Server) सुरू झाला आहे")
    print(f"👉 ब्राऊझरमध्ये उघडा: http://127.0.0.1:{port}")
    print(f"🔐 पालक डॅशबोर्ड पासवर्ड: {PARENT_PASSWORD}")
    print("=" * 65)
    app.run(host='0.0.0.0', port=port, debug=False)
