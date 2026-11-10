import time
import datetime
import requests
import uuid
import os
import ctypes

# सर्व्हरचा पत्ता (कॉम्प्युटरवर टेस्ट करण्यासाठी localhost)
SERVER_URL = "http://127.0.0.1:5000"
CHILD_NAME = "My_Test_Phone"
DEVICE_ID = "mock_device_01"

# प्राथमिक सिम्युलेटेड कोऑर्डिनेट्स (उदा. मुंबई)
current_lat = 19.0760
current_lon = 72.8777

def get_battery_info():
    """लॅपटॉपची खरी बॅटरी किंवा सिम्युलेटेड बॅटरी मिळवणे"""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            return int(battery.percent), bool(battery.power_plugged)
    except Exception:
        pass
    return 88, False

def record_audio_native(duration_sec=3, output_filename="mic_record.wav"):
    """Windows MCI वापरून लॅपटॉपच्या मायक्रोफोनमधून खरा आवाज रेकॉर्ड करणे"""
    try:
        winmm = ctypes.windll.winmm
        winmm.mciSendStringA(b"close recsound", None, 0, None)
        winmm.mciSendStringA(b"open new type waveaudio alias recsound", None, 0, None)
        winmm.mciSendStringA(b"record recsound", None, 0, None)
        time.sleep(duration_sec)
        cmd_save = f"save recsound {output_filename}".encode('utf-8')
        winmm.mciSendStringA(cmd_save, None, 0, None)
        winmm.mciSendStringA(b"close recsound", None, 0, None)
        return os.path.exists(output_filename) and os.path.getsize(output_filename) > 0
    except Exception as e:
        print("   ❌ मायक्रोफोन रेकॉर्डिंग एरर:", e)
        return False

print("=" * 60)
print("🛡️ ChildMonitor - सुधारित बनावट क्लायंट (Mock Client)")
print(f"📱 डिव्हाइस आयडी: {DEVICE_ID}")
print(f"👤 मुलाचे नाव: {CHILD_NAME}")
print(f"🌐 सर्व्हर पत्ता: {SERVER_URL}")
print("=" * 60)

step = 0

while True:
    step += 1
    battery_pct, is_charging = get_battery_info()
    
    url = f"{SERVER_URL}/get_commands/{DEVICE_ID}"
    payload = {
        "child_name": CHILD_NAME,
        "battery_level": battery_pct,
        "is_charging": is_charging,
        "wifi_ssid": "Home_WiFi_5G"
    }
    
    try:
        # सर्व्हरशी संपर्क साधून आदेश मागवणे
        response = requests.post(url, json=payload, timeout=6)
        if response.status_code == 200:
            commands = response.json()
            time_now = datetime.datetime.now().strftime('%H:%M:%S')
            print(f"[{time_now}] 📡 सर्व्हर प्रतिसाद: बॅटरी={battery_pct}% | चार्जिंग={is_charging}")
            
            # १. लोकेशन ट्रॅकिंग चालू असल्यास
            if commands.get("location_access") is True:
                try:
                    # नकाशावर हालचाल दिसण्यासाठी किंचित बदल सिम्युलेट करणे
                    current_lat += 0.00015
                    current_lon += 0.00010
                    
                    loc_url = f"{SERVER_URL}/update_location"
                    loc_payload = {
                        "child_id": DEVICE_ID,
                        "latitude": round(current_lat, 6),
                        "longitude": round(current_lon, 6),
                        "accuracy": 4.5,
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    requests.post(loc_url, json=loc_payload, timeout=5)
                    print(f"   📍 लोकेशन डेटा पाठवला: Lat {round(current_lat, 5)}, Lon {round(current_lon, 5)}")
                except Exception as loc_err:
                    print("   ❌ लोकेशन पाठवताना त्रुटी:", loc_err)
                
            # २. कॅमेरा ऑन करण्याचे आदेश आल्यास (लॅपटॉपचा वेबकॅम)
            if commands.get("camera_access") in ["FRONT", "BACK"]:
                mode = commands.get("camera_access")
                print(f"   📷 [REAL ACTION] वेबकॅम सक्रिय होत आहे ({mode})...")
                
                try:
                    import cv2
                    cap = cv2.VideoCapture(0)
                    if cap.isOpened():
                        for _ in range(5):
                            ret, frame = cap.read()
                            
                        if ret:
                            temp_filename = "laptop_capture.jpg"
                            cv2.imwrite(temp_filename, frame)
                            cap.release()
                            
                            with open(temp_filename, "rb") as img_file:
                                files = {"image": (f"capture_{int(time.time())}.jpg", img_file, "image/jpeg")}
                                data = {"child_id": DEVICE_ID}
                                requests.post(f"{SERVER_URL}/upload_camera_photo", data=data, files=files, timeout=10)
                            
                            if os.path.exists(temp_filename):
                                os.remove(temp_filename)
                            print("   🟢 [SUCCESS] लॅपटॉपच्या कॅमेऱ्याने फोटो काढून सर्व्हरवर अपलोड केला!")
                        else:
                            cap.release()
                            print("   ❌ कॅमेऱ्यातून इमेज मिळाली नाही.")
                    else:
                        print("   ❌ लॅपटॉपचा वेबकॅम ओपन होऊ शकला नाही.")
                except Exception as cam_err:
                    print("   ❌ कॅमेरा प्रोसेस एरर:", cam_err)

            # ३. ऑडिओ रेकॉर्डिंग आदेश आल्यास (लॅपटॉपचा मायक्रोफोन)
            if commands.get("audio_access") is True:
                print("   🎙️ [REAL ACTION] मायक्रोफोनद्वारे आजूबाजूचा आवाज रेकॉर्ड करत आहे (३ सेकंद)...")
                audio_file = f"audio_{int(time.time())}.wav"
                if record_audio_native(duration_sec=3, output_filename=audio_file):
                    try:
                        with open(audio_file, "rb") as af:
                            files = {"audio": (audio_file, af, "audio/wav")}
                            data = {"child_id": DEVICE_ID}
                            requests.post(f"{SERVER_URL}/upload_audio", data=data, files=files, timeout=10)
                        print("   🟢 [SUCCESS] ऑडिओ सर्व्हरवर यशस्वीरित्या अपलोड केला!")
                    except Exception as aud_err:
                        print("   ❌ ऑडिओ अपलोड एरर:", aud_err)
                    finally:
                        if os.path.exists(audio_file):
                            os.remove(audio_file)
                else:
                    print("   ❌ ऑडिओ रेकॉर्ड होऊ शकला नाही.")

            # ४. रिमोट गजर (Alarm Ring)
            if commands.get("ring_alarm") is True:
                print("   🔔🚨 [ALARM ACTIVE] पालकांनी फोन वाजवण्याचा आदेश दिला आहे!")
                try:
                    import winsound
                    winsound.Beep(1200, 400)
                except Exception:
                    pass

            # ५. टॉर्च (Torch)
            if commands.get("torch_access") is True:
                print("   💡 [TORCH ON] पालकांनी टॉर्च चालू केला आहे.")

            # ६. चाचणीसाठी दर काही वेळाने एखादा टेस्ट एसएमएस पाठवणे
            if commands.get("message_access") is True and step % 5 == 0:
                try:
                    sms_url = f"{SERVER_URL}/log_sms"
                    sms_payload = {
                        "child_id": DEVICE_ID,
                        "sender": "+91 98765 43210 (मित्र)",
                        "message": f"शाळेनंतर ग्राउंडवर खेळायला येतोयस का? [Step {step}]",
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    requests.post(sms_url, json=sms_payload, timeout=5)
                    print("   💬 [SMS] सिम्युलेटेड एसएमएस सर्व्हरला पाठवला.")
                except Exception as sms_err:
                    print("   ❌ एसएमएस एरर:", sms_err)

    except Exception as e:
        print("[ERROR] सर्व्हरशी संपर्क नाही:", e)
        
    time.sleep(5)
