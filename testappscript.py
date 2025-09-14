import requests
import datetime

# Link Web App Apps Script (phải deploy dạng web app)
URL = "https://script.google.com/macros/s/AKfycbwkOcQuB2gzFKbf6dg_pXnGx5AiqAK-yAxJ2lAF0hqzy1eggOgKxa4LAdZFx13zTg14gA/exec"

# ID giả lập (ví dụ sinh viên có mã số 12345)
id_test = "2"

# Tạo timestamp hiện tại (theo giờ VN)
now = datetime.datetime.now()
timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

# Payload gửi đi
payload = {
    "id": id_test,
    "timestamp": timestamp
}

# Gửi request POST
resp = requests.post(URL, json=payload)

print("Request gửi:", payload)
print("Response nhận:", resp.text)
