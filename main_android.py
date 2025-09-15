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
APPS_SCRIPT_WEBHOOK_URL = "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec"  # <-- thay URL Apps Script Web App của bạn

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

# ---------------------
# Main App
# ---------------------
class QRAndroidApp(App):
    last_data = StringProperty('')
    log_text = StringProperty('')
    ticked = set()   # tránh quét trùng

    def build(self):
        from kivy_garden.zbarcam import ZBarCam  # import ở đây để chắc chắn có garden
        self.title = "QR Attendance Android"
        return Builder.load_string(KV)

    def log(self, *parts):
        t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{t}] " + ' '.join(str(p) for p in parts)
        print(line)
        # append cuối log
        self.log_text = self.log_text + '\n' + line if self.log_text else line

    def on_symbols(self, instance, symbols):
        """Hàm callback khi ZBarCam phát hiện QR code"""
        if not symbols:
            return
        data_str = symbols[0].data.decode("utf-8")
        if data_str in self.ticked:
            self.log(f"ID {data_str} đã quét rồi, bỏ qua")
            return
        self.ticked.add(data_str)

        now = datetime.now()
        record = {
            "id": data_str,
            "timestamp": now.isoformat(),
            "day": now.strftime("%d-%m")  # để Apps Script dễ xử lý cột ngày
        }
        self.last_data = f"{record['id']} ({record['day']})"
        self.log(f"Đã quét: {record['id']}")
        threading.Thread(target=self.send_record_to_sheet, args=(record,), daemon=True).start()

    def send_record_to_sheet(self, record: dict):
        if APPS_SCRIPT_WEBHOOK_URL and REQUESTS_AVAILABLE:
            try:
                r = requests.post(APPS_SCRIPT_WEBHOOK_URL, data=record, timeout=8)
                if r.status_code == 200:
                    self.log("Gửi thành công:", r.text)
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
