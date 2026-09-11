import socket
import os
import base64
import qrcode
from PIL import Image, ImageOps

QR_DIR = os.path.join(os.path.dirname(__file__), "qrcodes")
PHOTO_DIR = os.path.join(os.path.dirname(__file__), "photos")

os.makedirs(QR_DIR, exist_ok=True)
os.makedirs(PHOTO_DIR, exist_ok=True)

CATEGORIES = ["미끄럼/걸림", "추락", "낙하물", "감전", "기타"]
RISK_LEVELS = ["High", "Medium", "Low"]
RISK_COLOR = {"High": "#e53935", "Medium": "#fb8c00", "Low": "#43a047"}
RISK_LABEL_KR = {"High": "높음", "Medium": "중간", "Low": "낮음"}


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def get_current_port():
    """Streamlit이 실제로 바인딩한 포트를 읽어온다 (8501이 사용 중이면 자동으로 다른 포트로 뜨는 경우 대응)."""
    try:
        import streamlit as st
        port = st.get_option("server.port")
        if port:
            return port
    except Exception:
        pass
    return 8501


def get_base_url(port=None):
    if port is None:
        port = get_current_port()
    return f"http://{get_local_ip()}:{port}"


def build_viewer_url(hazard_id, port=None):
    return f"{get_base_url(port)}/?id={hazard_id}"


def generate_qr(hazard_id, port=None):
    url = build_viewer_url(hazard_id, port)
    img = qrcode.make(url)
    path = os.path.join(QR_DIR, f"qr_{hazard_id}.png")
    img.save(path)
    return path, url


def _auto_orient(img):
    """휴대폰 카메라의 EXIF 방향 정보를 반영해 실제 보이는 방향으로 보정."""
    return ImageOps.exif_transpose(img)


def get_preview_image(uploaded_file, manual_rotation=0):
    """등록 폼에서 업로드 직후 미리보기용 이미지를 반환 (파일은 저장하지 않음)."""
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    img = _auto_orient(img)
    if manual_rotation:
        img = img.rotate(-manual_rotation, expand=True)  # 양수 = 시계방향
    return img


def save_photo(uploaded_file, hazard_id, manual_rotation=0):
    """업로드된 사진을 EXIF 자동보정 + 수동 회전값을 반영해 JPEG로 저장."""
    if uploaded_file is None:
        return None
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    img = _auto_orient(img)
    if manual_rotation:
        img = img.rotate(-manual_rotation, expand=True)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    path = os.path.join(PHOTO_DIR, f"photo_{hazard_id}.jpg")
    img.save(path, "JPEG", quality=90)
    return path


def rotate_saved_photo(photo_path, degrees):
    """이미 저장된 사진 파일을 지정 각도(시계방향)만큼 회전해 같은 경로에 덮어쓴다."""
    if not photo_path or not os.path.exists(photo_path):
        return None
    img = Image.open(photo_path)
    img = img.rotate(-degrees, expand=True)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(photo_path, "JPEG", quality=90)
    return photo_path


def image_to_data_uri(path):
    """이미지 파일을 <img> 태그에 바로 넣을 수 있는 base64 data URI로 변환."""
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/jpeg;base64,{b64}"
