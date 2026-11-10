"""
ChildMonitor - Android Client Application
Clean, crash-proof, resilient mobile client for Child Safety Monitoring.
"""

import os
import sys
import json
import time
import uuid
import datetime
import threading
import urllib.request
import urllib.error
import ssl

from kivy.app import App
from kivy.clock import Clock
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

# Default server URL for local LAN
DEFAULT_SERVER_URL = "http://10.247.151.235:3375"

# Safe SSL Context (allows HTTP and self-signed HTTPS)
SAFE_SSL_CTX = ssl.create_default_context()
SAFE_SSL_CTX.check_hostname = False
SAFE_SSL_CTX.verify_mode = ssl.CERT_NONE


# ================= Safe Hardware Functions =================

def safe_get_device_name():
    """Retrieve Android Device Manufacturer and Model safely."""
    if platform == 'android':
        try:
            from jnius import autoclass
            Build = autoclass('android.os.Build')
            mfg = str(getattr(Build, 'MANUFACTURER', '')).capitalize()
            model = str(getattr(Build, 'MODEL', 'Phone'))
            if model.lower().startswith(mfg.lower()):
                return model.strip()
            return f"{mfg} {model}".strip()
        except Exception:
            pass
    return "Android_Device"


def safe_get_battery():
    """Retrieve Battery Percentage and Charging Status safely."""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = getattr(PythonActivity, 'mActivity', None)
            if activity:
                Intent = autoclass('android.content.Intent')
                IntentFilter = autoclass('android.content.IntentFilter')
                BatteryManager = autoclass('android.os.BatteryManager')
                ctx = activity.getApplicationContext()
                status_intent = ctx.registerReceiver(None, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
                if status_intent:
                    level = status_intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
                    scale = status_intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
                    status = status_intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                    pct = int((level / float(scale)) * 100) if scale > 0 else 100
                    charging = (status == BatteryManager.BATTERY_STATUS_CHARGING or status == BatteryManager.BATTERY_STATUS_FULL)
                    return pct, charging
        except Exception:
            pass
    return 88, False


def safe_get_location():
    """Retrieve Android GPS Location safely."""
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = getattr(PythonActivity, 'mActivity', None)
            if activity:
                Context = autoclass('android.content.Context')
                LocationManager = autoclass('android.location.LocationManager')
                ctx = activity.getApplicationContext()
                lm = ctx.getSystemService(Context.LOCATION_SERVICE)
                loc = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER)
                if not loc:
                    loc = lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
                if not loc:
                    loc = lm.getLastKnownLocation(LocationManager.PASSIVE_PROVIDER)
                if loc:
                    return float(loc.getLatitude()), float(loc.getLongitude()), float(loc.getAccuracy())
        except Exception:
            pass
    return None


def safe_http_post(url, json_data, timeout=8):
    """Post JSON using standard library urllib (zero external pip dependencies)."""
    try:
        body = json.dumps(json_data).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'ChildMonitorClient/2.0'
            }
        )
        with urllib.request.urlopen(req, timeout=timeout, context=SAFE_SSL_CTX) as resp:
            if resp.status == 200:
                raw = resp.read().decode('utf-8')
                return json.loads(raw)
    except Exception:
        pass
    return None


# ================= Main Application =================

class ChildMonitorApp(App):
    def build(self):
        self.title = "Device Health & Safety"
        self.server_url = DEFAULT_SERVER_URL
        self.child_name = "Child_Phone"
        self.device_id = str(uuid.uuid4())[:8]
        self.current_lat = 18.5204
        self.current_lon = 73.8567
        self.connection_status = "Initializing..."
        self.battery_val = 100
        self.is_charging = False

        # Main Layout
        self.root_layout = BoxLayout(orientation='vertical', padding=25, spacing=15)

        # Header Title
        self.title_label = Label(
            text="Device Health & Safety Service\n(Child Monitor Active)",
            font_size='18sp',
            bold=True,
            halign='center',
            size_hint=(1, 0.22)
        )
        self.root_layout.add_widget(self.title_label)

        # SOS Emergency Button
        self.sos_btn = Button(
            text="EMERGENCY SOS\n[ Tap for Help ]",
            font_size='18sp',
            bold=True,
            background_color=(0.85, 0.15, 0.15, 1),
            size_hint=(1, 0.35)
        )
        self.sos_btn.bind(on_press=self.on_sos_press)
        self.root_layout.add_widget(self.sos_btn)

        # Status Label
        self.status_label = Label(
            text="Connecting to Server...\nURL: " + self.server_url,
            font_size='14sp',
            halign='center',
            size_hint=(1, 0.28)
        )
        self.root_layout.add_widget(self.status_label)

        # Settings Button
        self.settings_btn = Button(
            text="Change Server URL (Settings)",
            font_size='13sp',
            background_color=(0.2, 0.45, 0.75, 1),
            size_hint=(1, 0.15)
        )
        self.settings_btn.bind(on_press=self.open_settings)
        self.root_layout.add_widget(self.settings_btn)

        return self.root_layout

    def on_start(self):
        """Called once the Android window and activity are fully established."""
        self.load_config()
        # Delay hardware and network access by 2 seconds to prevent native Android startup crash
        Clock.schedule_once(self.deferred_init, 2.0)

    def get_config_filepath(self):
        try:
            target_dir = self.user_data_dir
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            return os.path.join(target_dir, "child_config.json")
        except Exception:
            return None

    def load_config(self):
        try:
            cfg_path = self.get_config_filepath()
            if cfg_path and os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.server_url = data.get("server_url", DEFAULT_SERVER_URL)
                    self.child_name = data.get("child_name", self.child_name)
                    self.device_id = data.get("device_id", self.device_id)
            else:
                self.child_name = safe_get_device_name()
                self.save_config()
        except Exception:
            pass

    def save_config(self):
        try:
            cfg_path = self.get_config_filepath()
            if cfg_path:
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "server_url": self.server_url,
                        "child_name": self.child_name,
                        "device_id": self.device_id
                    }, f, indent=4)
        except Exception:
            pass

    def deferred_init(self, dt):
        """Safely request runtime permissions and start periodic polling."""
        self.request_permissions_safe()
        # Schedule periodic background sync every 8 seconds
        Clock.schedule_interval(lambda dt: self.trigger_bg_sync(), 8)
        self.trigger_bg_sync()

    def request_permissions_safe(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions
                request_permissions([
                    "android.permission.ACCESS_FINE_LOCATION",
                    "android.permission.ACCESS_COARSE_LOCATION",
                    "android.permission.CAMERA",
                    "android.permission.RECORD_AUDIO",
                    "android.permission.READ_PHONE_STATE"
                ])
            except Exception:
                pass

    def trigger_bg_sync(self):
        t = threading.Thread(target=self._sync_worker, daemon=True)
        t.start()

    def _sync_worker(self):
        if not self.server_url:
            return

        battery, charging = safe_get_battery()
        self.battery_val = battery
        self.is_charging = charging

        # 1. Heartbeat to server
        heartbeat_url = f"{self.server_url}/api/heartbeat"
        payload = {
            "device_id": self.device_id,
            "child_name": self.child_name,
            "battery_level": battery,
            "is_charging": charging
        }

        resp = safe_http_post(heartbeat_url, payload, timeout=6)
        if resp and resp.get("status") == "ok":
            self.connection_status = "Online (Connected to Server)"

            # 2. Update Location
            if resp.get("location_access", True):
                self._send_location()

            # 3. Handle Alarm command
            if resp.get("ring_alarm"):
                self._play_alarm(True)
            else:
                self._play_alarm(False)
        else:
            self.connection_status = "Searching for Server..."

        # Update UI safely on main thread
        Clock.schedule_once(lambda dt: self._update_ui(), 0)

    def _send_location(self):
        loc = safe_get_location()
        if loc:
            self.current_lat, self.current_lon, acc = loc
        else:
            acc = 15.0

        loc_url = f"{self.server_url}/api/location"
        loc_payload = {
            "child_id": self.device_id,
            "device_id": self.device_id,
            "latitude": self.current_lat,
            "longitude": self.current_lon,
            "accuracy": acc
        }
        safe_http_post(loc_url, loc_payload, timeout=6)

    def _play_alarm(self, active):
        if platform == 'android':
            try:
                from jnius import autoclass
                RingtoneManager = autoclass('android.media.RingtoneManager')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                act = getattr(PythonActivity, 'mActivity', None)
                if not act:
                    return
                ctx = act.getApplicationContext()
                if active:
                    if not hasattr(self, '_ringtone') or not self._ringtone:
                        uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
                        self._ringtone = RingtoneManager.getRingtone(ctx, uri)
                    if self._ringtone and not self._ringtone.isPlaying():
                        self._ringtone.play()
                else:
                    if hasattr(self, '_ringtone') and self._ringtone:
                        if self._ringtone.isPlaying():
                            self._ringtone.stop()
            except Exception:
                pass

    def _update_ui(self):
        if hasattr(self, 'status_label'):
            charge_str = " (Charging)" if self.is_charging else ""
            self.status_label.text = (
                f"Device: {self.child_name} | ID: {self.device_id}\n"
                f"Status: {self.connection_status}\n"
                f"Battery: {self.battery_val}%{charge_str}\n"
                f"Server: {self.server_url}"
            )

    def on_sos_press(self, instance):
        def sos_thread():
            try:
                safe_http_post(f"{self.server_url}/trigger_sos", {
                    "child_id": self.device_id,
                    "latitude": self.current_lat,
                    "longitude": self.current_lon
                }, timeout=8)
            except Exception:
                pass
        threading.Thread(target=sos_thread, daemon=True).start()

    def open_settings(self, instance):
        box = BoxLayout(orientation='vertical', padding=20, spacing=10)
        box.add_widget(Label(text="Enter Server URL:", size_hint=(1, 0.2)))
        txt_url = TextInput(text=self.server_url, multiline=False, size_hint=(1, 0.25))
        box.add_widget(txt_url)

        def save_and_close(btn):
            val = txt_url.text.strip()
            if val:
                self.server_url = val
                self.save_config()
            self.root_layout.clear_widgets()
            self.root_layout.add_widget(self.title_label)
            self.root_layout.add_widget(self.sos_btn)
            self.root_layout.add_widget(self.status_label)
            self.root_layout.add_widget(self.settings_btn)

        btn_save = Button(text="Save & Return", size_hint=(1, 0.25), background_color=(0.1, 0.7, 0.2, 1))
        btn_save.bind(on_press=save_and_close)
        box.add_widget(btn_save)

        self.root_layout.clear_widgets()
        self.root_layout.add_widget(box)

    def on_pause(self):
        # Keep running in background when paused
        return True

    def on_resume(self):
        pass


if __name__ == '__main__':
    ChildMonitorApp().run()
