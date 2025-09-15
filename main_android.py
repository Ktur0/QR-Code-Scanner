# main_android.py
# App Kivy quét QR bằng ZBarCam (Android friendly) + gửi dữ liệu tới Google Apps Script Web App

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty
from datetime import datetime
import threading

# Thư viện gửi HTTP
try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False

# ---------------------
# CONFIG
# ---------------------
APPS_SCRIPT_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbz293pXol0nxj73B2wo1eeJR6X5JvEPasW4k55Y9SnnlEAUQh9bOlMe-03qVdUtn1Si6Q/exec"  # <-- thay URL Apps Script Web App của bạn

KV = '''
BoxLayout:
    orientation: 'vertical'
    padding: 10
    spacing: 10

    Label:
        text: 'QR Attendance (Android Version)'
        size_hint_y: None
        height: '40dp'

    ZBarCam:
        id: zbarcam
        # Camera preview
        size_hint_y: 0.7
        on_symbols: app.on_symbols(*args)

    Label:
        text: 'Last scanned:'
        size_hint_y: None
        height: '24dp'

    Label:
        text: app.last_data or 'Chưa quét'
        text_size: self.width, None
        size_hint_y: None
        height: '60dp'

    ScrollView:
        Label:
            id: log_label
            text: app.log_text
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
            valign: 'top'
            halign: 'left'
'''

ticked = set()  # tránh quét trùng

# ---------------------
# Main App
# ---------------------
class QRAndroidApp(App):
    last_data = StringProperty('')
    log_text = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scanning = False   # thêm dòng này để tránh lỗi


    def build(self):
        from kivy_garden.zbarcam import ZBarCam  # import ở đây để chắc chắn có garden
        self.title = "QR Attendance Android"
        return Builder.load_string(KV)

    def log(self, *parts):
        t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{t}] " + ' '.join(str(p) for p in parts)
        print(line)
        self.log_text = line + '\n' + self.log_text

    def on_symbols(self, instance, symbols):
        """Hàm callback khi ZBarCam phát hiện QR code"""
        if not symbols or self.scanning:
            return

        data_str = symbols[0].data.decode("utf-8").strip()
        if not data_str:
            return

        self.scanning = True  # khóa quét trong lúc xử lý

        if data_str in ticked:
            self.log(f"ID {data_str} đã quét rồi, bỏ qua")
        else:
            ticked.add(data_str)
            parts = data_str.split()
            idOnly = parts[0] if parts else data_str
            record = {"id": idOnly}

            self.last_data = record["id"]
            self.log(f"Đã quét: {data_str}")
            threading.Thread(target=self.send_record_to_sheet, args=(record,), daemon=True).start()

        # mở khóa sau 2 giây (có thể chỉnh)
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: setattr(self, "scanning", False), 2)

    def send_record_to_sheet(self, record: dict):
        if APPS_SCRIPT_WEBHOOK_URL and REQUESTS_AVAILABLE:
            try:
                r = requests.post(APPS_SCRIPT_WEBHOOK_URL, data=record, timeout=8)
                if r.status_code == 200:
                    self.log("Gửi thành công")
                    return True
                else:
                    self.log("Apps Script trả mã", r.status_code, r.text)
            except Exception as e:
                self.log("Lỗi gửi Apps Script:", e)
        return False

# ---------------------
# Run
# ---------------------
if __name__ == '__main__':
    QRAndroidApp().run()
