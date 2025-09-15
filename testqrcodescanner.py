# main.py
# Demo Kivy app: Quản lý quản QR điểm danh + gửi dữ liệu tạo Google Sheet
# - Hướng chạy trên Desktop: camera (OpenCV) + pyzbar
# - Gải pháp ghi trợ giúp cho Android: POST tạo Google Apps Script Web App (URL)
# Lưu ý: file `credentials.json` và URL Apps Script nên đươc cảm 
#           và thay thế trưởng MY_APPS_SCRIPT_URL

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty
from datetime import datetime
import threading
import json
import base64
import io

# Optional imports - may fail on Android if not installed, handle gracefully
try:
    import cv2
    from pyzbar.pyzbar import decode
    from PIL import Image
    OPENCV_AVAILABLE = True
except Exception as e:
    OPENCV_AVAILABLE = False

# For HTTP POST
try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False

# ---------------------
# CONFIG
# ---------------------
# If you deploy a Google Apps Script Web App that accepts POST and appends to your Sheet,
# put its URL here. This is recommended for mobile (APK) because shipping Service Account
# credentials in an APK is not secure.
APPS_SCRIPT_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbz293pXol0nxj73B2wo1eeJR6X5JvEPasW4k55Y9SnnlEAUQh9bOlMe-03qVdUtn1Si6Q/exec"  # <-- Thay URL của bạn

# If you want to use gspread (service account) directly (desktop use), set to True and
# place credentials.json next to the app. NOTE: Not recommended for public APKs.
USE_GSPREAD = False

# ---------------------
# Kivy UI
# ---------------------
KV = '''
BoxLayout:
    orientation: 'vertical'
    padding: 10
    spacing: 10

    Label:
        text: 'Demo App: QR Attendance (Core features)'
        size_hint_y: None
        height: '40dp'

    BoxLayout:
        size_hint_y: None
        height: '40dp'
        spacing: 8

        Button:
            text: 'Start Camera (Desktop)'
            on_release: app.start_camera()
            disabled: not app.opencv_available

        Button:
            text: 'Stop Camera'
            on_release: app.stop_camera()
            disabled: not app.camera_running

    BoxLayout:
        size_hint_y: None
        height: '40dp'
        spacing: 8

        Button:
            text: 'Scan Image File'
            on_release: app.scan_image_file()
            disabled: not app.pyzbar_available

        Button:
            text: 'Manual Send Last'
            on_release: app.send_last_record()
            disabled: not app.last_data

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

ticked = set() 

# --------------------- 
# Helper functions
# ---------------------

def decode_pil_image(pil_img):
    """Decode QR from a PIL Image, return list of data strings"""
    try:
        decoded = decode(pil_img)
        return [d.data.decode('utf-8') for d in decoded]
    except Exception as e:
        return []

# ---------------------
# Main App
# ---------------------
class QRAttendanceApp(App):
    last_data = StringProperty('')
    log_text = StringProperty('')
    camera_running = BooleanProperty(False)
    opencv_available = BooleanProperty(OPENCV_AVAILABLE)
    pyzbar_available = BooleanProperty(OPENCV_AVAILABLE)

    def build(self):
        self.title = "QR Attendance"
        self.capture = None
        self.camera_thread = None
        self._stop_event = threading.Event()
        return Builder.load_string(KV)

    def log(self, *parts):
        t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{t}] " + ' '.join(str(p) for p in parts)
        print(line)
        self.log_text = line + '\n' + self.log_text

    # ---------------------
    # Camera (desktop) using OpenCV + pyzbar
    # ---------------------
    def start_camera(self):
        if not OPENCV_AVAILABLE:
            self.log('OpenCV/pyzbar not available on this platform.')
            return
        if self.camera_running:
            self.log('Camera already running')
            return
        self._stop_event.clear()
        self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self.camera_thread.start()
        self.camera_running = True
        self.log('Camera started')

    def _camera_loop(self):
        self.capture = cv2.VideoCapture(0)
        if not self.capture.isOpened():
            self.log('Không mở được camera')
            self.camera_running = False
            return
        while not self._stop_event.is_set():
            ret, frame = self.capture.read()
            if not ret:
                continue
            # Decode
            try:
                pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                decoded = decode_pil_image(pil_img)
                if decoded:
                    for d in decoded:
                        self.on_qr_scanned(d)
                        # sleep to avoid multiple same reads
                        cv2.waitKey(1000)
            except Exception as e:
                self.log('Mã QR không tồn tại')
        self.capture.release()
        self.camera_running = False
        self.log('Camera stopped loop')

    def stop_camera(self):
        if not self.camera_running:
            self.log('Camera not running')
            return
        self._stop_event.set()
        if self.camera_thread:
            self.camera_thread.join(timeout=2)
        self.camera_running = False
        self.log('Camera stop requested')

    # ---------------------
    # Scan image file (desktop) - opens file dialog via tkinter (blocking)
    # ---------------------
    def scan_image_file(self):
        # Use tkinter filedialog to choose image
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename(title='Select image file',
                                                   filetypes=[('Image files', '*.png *.jpg *.jpeg *.bmp')])
            root.destroy()
        except Exception as e:
            self.log('File dialog not available:', e)
            return
        if not file_path:
            self.log('No file selected')
            return
        try:
            pil = Image.open(file_path)
            decoded = decode_pil_image(pil)
            if decoded:
                for d in decoded:
                    self.on_qr_scanned(d)
            else:
                self.log('Không tìm thấy QR trong ảnh')
        except Exception as e:
            self.log('Lấi ói lỗi mở ảnh:', e)

    # ---------------------
    # QR scanned handler
    # ---------------------
    def on_qr_scanned(self, data_str):
        # Data structure expected: either "ID|Name" or any string you choose
        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')  # ISO 8601
        record = {'data': data_str, 'timestamp': now}
        self.last_data = json.dumps(record, ensure_ascii=False)
        if data_str in ticked:
            self.log(f"Học sinh mang id số {data_str} đã quét rồi, bỏ qua")
            return  # Skip if already scanned
        else:
            ticked.add(data_str)  # Mark as scanned
            self.log(f"Đã quét: {data_str}")
        # Auto send to sheet (non-blocking)
        threading.Thread(target=self.send_record_to_sheet, args=(record,), daemon=True).start()

    # ---------------------
    # Sending to Google Sheet
    # Option A: POST to Apps Script Web App (recommended for mobile)
    # Option B: Use gspread directly (desktop only)
    # ---------------------
    def send_record_to_sheet(self, record: dict):
        # Try Apps Script first
        if APPS_SCRIPT_WEBHOOK_URL and APPS_SCRIPT_WEBHOOK_URL.startswith('https') and REQUESTS_AVAILABLE:
            rawData = record.get('data', '')
            idOnly = rawData.split(' - ')[0]

            try:
                payload = {
                    'id': idOnly
                }
                # gửi dạng form-data, không phải JSON
                r = requests.post(
                    APPS_SCRIPT_WEBHOOK_URL,
                    data=payload,   # <--- KHÁC so với json.dumps(payload)
                    timeout=8
                )
                if r.status_code == 200:
                    self.log('Điểm danh thành công')
                    return True
                else:
                    self.log('Apps Script trả mã', r.status_code, r.text)
            except Exception as e:
                self.log('Lỗi gửi tới Apps Script:', e)


        # fallback nếu Apps Script fail
        if USE_GSPREAD:
            try:
                import gspread
                from oauth2client.service_account import ServiceAccountCredentials
                scope = ["https://spreadsheets.google.com/feeds",
                        "https://www.googleapis.com/auth/drive"]
                creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
                client = gspread.authorize(creds)
                sheet = client.open('DiemDanh').sheet1
                sheet.append_row([record['data'], record['timestamp']])
                self.log('Ghi vào Google Sheet qua gspread thành công')
                return True
            except Exception as e:
                self.log('Lỗi gspread:', e)

        return False


    def send_last_record(self):
        if not self.last_data:
            self.log('Chưa có record để gửi')
            return
        record = json.loads(self.last_data)
        threading.Thread(target=self.send_record_to_sheet, args=(record,), daemon=True).start()

# ---------------------
# Run
# ---------------------
if __name__ == '__main__':
    QRAttendanceApp().run()
