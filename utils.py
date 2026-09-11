import socket
import os
import io
import qrcode
from PIL import Image, ImageOps

import db

QR_DIR = os.path.join(os.path.dirname(__file__), "qrcodes")
os.makedirs(QR_DIR, exist_ok=True)

BUCKET = "photos"

CATEGORIES = ["미끄럼/걸림", "추락", "낙하물", "감전", "기타"]
RISK_LEVELS = ["High", "Medium", "Low"]
RISK_COLOR = {"High": "#e53935", "Medium": "#fb8c00", "Low": "#43a047"}
RISK_LABEL_KR = {"High": "높음", "Medium": "중간", "Low": "낮음"}


# ---------------------------------------------------------------------------
# 서버 주소 / QR
# ---------------------------------------------------------------------------
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
    """배포 환경(Streamlit Cloud 등)에서는 PUBLIC_BASE_URL을 우선 사용하고,
    없으면 로컬 개발용 IP:PORT 방식으로 자동 감지한다."""
    public_url = os.environ.get("PUBLIC_BASE_URL")
    if not public_url:
        try:
            import streamlit as st
            public_url = st.secrets.get("PUBLIC_BASE_URL")
        except Exception:
            public_url = None
    if public_url:
        return public_url.rstrip("/")

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


# ---------------------------------------------------------------------------
# 이미지 처리 (회전/보정/압축)
# ---------------------------------------------------------------------------
def _auto_orient(img):
    """휴대폰 카메라의 EXIF 방향 정보를 반영해 실제 보이는 방향으로 보정."""
    return ImageOps.exif_transpose(img)


def _resize_for_storage(img, max_dim=1600):
    """저장 용량을 줄이기 위해 긴 변 기준 max_dim을 넘지 않도록 축소."""
    w, h = img.size
    if max(w, h) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    return img


def get_preview_image(uploaded_file, manual_rotation=0):
    """등록 폼에서 업로드 직후 미리보기용 이미지를 반환 (업로드/저장은 하지 않음)."""
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    img = _auto_orient(img)
    if manual_rotation:
        img = img.rotate(-manual_rotation, expand=True)
    return img


def _to_jpeg_bytes(img):
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img = _resize_for_storage(img)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Supabase Storage 사진 저장 (영구 저장 — Streamlit Cloud 재시작에도 유지됨)
# ---------------------------------------------------------------------------
def _storage_path(hazard_id):
    return f"hazard_{hazard_id}.jpg"


def get_public_url(hazard_id):
    client = db.get_client()
    return client.storage.from_(BUCKET).get_public_url(_storage_path(hazard_id))


def save_photo(uploaded_file, hazard_id, manual_rotation=0):
    """업로드된 사진을 EXIF 자동보정 + 수동 회전 + 압축 후 Supabase Storage에 업로드."""
    if uploaded_file is None:
        return None
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    img = _auto_orient(img)
    if manual_rotation:
        img = img.rotate(-manual_rotation, expand=True)
    jpeg_bytes = _to_jpeg_bytes(img)

    client = db.get_client()
    path = _storage_path(hazard_id)
    client.storage.from_(BUCKET).upload(
        path, jpeg_bytes, {"content-type": "image/jpeg", "upsert": "true"}
    )
    return get_public_url(hazard_id)


def rotate_saved_photo(hazard_id, degrees):
    """Storage에 저장된 사진을 내려받아 지정 각도(시계방향)만큼 회전 후 같은 자리에 다시 업로드."""
    client = db.get_client()
    path = _storage_path(hazard_id)
    try:
        data = client.storage.from_(BUCKET).download(path)
    except Exception:
        return None

    img = Image.open(io.BytesIO(data))
    if degrees:
        img = img.rotate(-degrees, expand=True)
    jpeg_bytes = _to_jpeg_bytes(img)

    client.storage.from_(BUCKET).upload(
        path, jpeg_bytes, {"content-type": "image/jpeg", "upsert": "true"}
    )
    return get_public_url(hazard_id)


def delete_photo(hazard_id):
    try:
        client = db.get_client()
        client.storage.from_(BUCKET).remove([_storage_path(hazard_id)])
    except Exception:
        pass
