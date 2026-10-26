import base64
import html
import io
from datetime import date

import streamlit as st

import db
import utils

st.set_page_config(page_title="위험요소 지도 관리자탭", layout="wide")
db.init_db()

SECTION_LIST = "목록"
SECTION_NEW = "신규 등록"


def render_html(markup: str):
    """줄 앞의 공백을 모두 제거해서 마크다운 파서가 코드블록으로 오인하지 않게 한 뒤 렌더링."""
    cleaned = "\n".join(line.strip() for line in markup.strip().splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)


def _md_plain(text: str) -> str:
    """목록 제목에 들어가는 사용자 입력은 마크다운으로 해석되지 않게 한다."""
    return "".join("\\" + ch if ch in "\\`*_{}[]()#+-!|>" else ch for ch in text)


def risk_slug(risk, done: bool = False) -> str:
    if done:
        return "done"
    return {"High": "high", "Medium": "medium", "Low": "low"}.get(risk or "", "unknown")


def phone_html(raw) -> str:
    text = (raw or "").strip()
    if not text:
        return "-"
    shown = html.escape(text)
    digits = "".join(ch for ch in text if ch.isdigit() or ch == "+")
    if len(digits) >= 8:
        return f'<a href="tel:{html.escape(digits, quote=True)}">{shown}</a>'
    return shown


def kicker(text: str, first: bool = False):
    cls = "form-kicker first" if first else "form-kicker"
    render_html(f'<p class="{cls}">{html.escape(text)}</p>')


def badge_row(risk, category, done: bool) -> str:
    parts = []
    if done:
        parts.append('<span class="badge risk-done">조치완료</span>')
    if risk:
        label = html.escape(utils.RISK_LABEL_KR.get(risk, str(risk)))
        parts.append(f'<span class="badge risk-{risk_slug(risk)}">위험도 {label}</span>')
    if category:
        parts.append(f'<span class="badge cat">{html.escape(category)}</span>')
    return f'<div class="badge-row">{"".join(parts)}</div>'


def meta_rows(d: dict, done: bool) -> str:
    description = html.escape(d.get("description") or "-").replace("\n", "<br>")
    contact_name = html.escape(d.get("contact_name") or "-")
    contact_phone = phone_html(d.get("contact_phone"))
    if done:
        date_row = (
            '<div class="meta-row"><span class="meta-label">조치 상태</span>'
            '<span class="meta-value status-done">조치완료</span></div>'
        )
    else:
        action_date = html.escape(str(d.get("action_date") or "-"))
        date_row = (
            '<div class="meta-row"><span class="meta-label">조치 예정일</span>'
            f'<span class="meta-value">{action_date}</span></div>'
        )
    return (
        f'<div class="description">{description}</div>'
        '<div class="meta">'
        f'<div class="meta-row"><span class="meta-label">담당자</span><span class="meta-value">{contact_name}</span></div>'
        f'<div class="meta-row"><span class="meta-label">전화번호</span><span class="meta-value">{contact_phone}</span></div>'
        f"{date_row}</div>"
    )


def list_label(h: dict) -> str:
    loc = _md_plain(h.get("location") or "(장소명 없음)")
    if h.get("after_photo_path"):
        return f":green[조치완료] · {loc}"
    label = utils.RISK_LABEL_KR.get(h.get("risk"), h.get("risk") or "위험도")
    color = {"High": "red", "Medium": "orange", "Low": "green"}.get(h.get("risk"), "gray")
    cat = h.get("category") or ""
    cat_bit = f" · :gray[{_md_plain(cat)}]" if cat else ""
    return f":{color}[{label}]{cat_bit} · {loc}"


# ---------------------------------------------------------------------------
# 공통 스타일
# ---------------------------------------------------------------------------
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap');

:root {
    --ink: #1b2430;
    --muted: #5e6a78;
    --line: #dfe3e8;
    --line-soft: #e8edf2;
    --paper: #ffffff;
    --canvas: #f4f6f8;
    --navy: #1e4d86;
    --navy-press: #173e6c;
    --danger: #8e2218;
}

html, body, .stApp, [class*="css"] {
    font-family: "Noto Sans KR", "Malgun Gothic", sans-serif;
    color: var(--ink);
}
[data-testid="stMarkdown"], [data-testid="stMarkdown"] p,
button, input, textarea, label {
    font-family: "Noto Sans KR", "Malgun Gothic", sans-serif !important;
}
[data-testid="stAppViewContainer"],
header[data-testid="stHeader"],
[data-testid="stMain"] {
    background: var(--canvas);
}
.block-container {
    padding-top: 4.75rem;
    padding-bottom: 2.75rem;
    max-width: __MAX_WIDTH__px;
}
h1, h2, h3 { letter-spacing: -0.02em; }

p.app-title {
    margin: 0;
    font-size: 1.42rem !important;
    line-height: 1.3;
    font-weight: 700;
    color: var(--ink);
}
.app-title span {
    margin-left: 0.35rem;
    font-size: 1.02rem;
    font-weight: 500;
    color: #3e4c5e;
}
.app-header .org {
    margin: 3px 0 0;
    color: var(--muted);
    font-size: 0.84rem;
    font-weight: 500;
}
.viewer-header {
    max-width: 440px;
    margin-left: auto;
    margin-right: auto;
    padding-bottom: 12px;
    margin-bottom: 16px;
    border-bottom: 1px solid var(--line);
}
[data-testid="stHorizontalBlock"]:has(.app-header) {
    align-items: center;
    border-bottom: 1px solid var(--line);
    padding-bottom: 10px;
    margin-bottom: 16px;
}

.pane-label { margin: 0 0 12px; }
p.pane-title {
    margin: 0;
    font-size: 1rem !important;
    line-height: 1.35;
    font-weight: 700;
    color: var(--ink);
}
.pane-label p:not(.pane-title) {
    margin: 3px 0 0;
    color: var(--muted);
    font-size: 0.82rem !important;
    line-height: 1.45;
}
[data-testid="stHorizontalBlock"]:has(.pane-preview) {
    align-items: flex-start;
}
[data-testid="stColumn"]:has(.pane-preview) {
    position: sticky;
    top: 0.75rem;
    align-self: flex-start;
    max-height: calc(100vh - 1.5rem);
    overflow: auto;
}

p.form-kicker {
    margin: 1.15rem 0 0.45rem;
    padding-bottom: 0.28rem;
    border-bottom: 1px solid var(--line);
    font-size: 0.8rem !important;
    font-weight: 700;
    color: #3e4c5e;
}
.form-kicker.first { margin-top: 0.15rem; }

[data-testid="stWidgetLabel"] p {
    font-size: 0.84rem;
    font-weight: 600;
    color: #243040;
}
[data-testid="stCaptionContainer"],
[data-testid="stCaption"] {
    color: var(--muted);
}

button[data-testid^="stBaseButton"] {
    border-radius: 6px;
    font-weight: 600;
    transition: background-color 0.12s ease, border-color 0.12s ease, color 0.12s ease;
}
button[data-testid="stBaseButton-secondary"] {
    background: var(--paper);
    border: 1px solid #d5dbe3;
    color: var(--ink);
}
button[data-testid="stBaseButton-secondary"]:hover:not(:disabled) {
    border-color: var(--navy);
    color: var(--navy);
    background: #f7f9fc;
}
button[data-testid="stBaseButton-primary"] {
    background: var(--navy);
    border: 1px solid var(--navy);
    color: #fff;
}
button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {
    background: var(--navy-press);
    border-color: var(--navy-press);
    color: #fff;
}
button[data-testid^="stBaseButton"]:focus-visible,
[data-testid="stRadioOption"]:focus-visible,
[data-testid="stExpander"] details summary:focus-visible {
    outline: 2px solid var(--navy);
    outline-offset: 2px;
}
[class*="st-key-delbtn_"] button {
    background: var(--paper) !important;
    color: var(--danger) !important;
    border: 1px solid #e7c1bd !important;
}
[class*="st-key-delbtn_"] button:hover:not(:disabled) {
    background: var(--danger) !important;
    color: #fff !important;
    border-color: var(--danger) !important;
}
[class*="st-key-delbtn_"] button:focus-visible {
    outline-color: var(--danger);
}
[class*="st-key-rotL_"] button,
[class*="st-key-rotR_"] button,
[class*="st-key-n_rot"] button,
.st-key-photonav button {
    font-size: 0.84rem;
    font-weight: 600;
}

[data-testid="stButtonGroup"] { margin: 0 0 0.85rem; }
[data-testid="stButtonGroup"] button {
    background: #fff !important;
    border: 1px solid #d5dbe3 !important;
    color: var(--ink) !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"] {
    background: var(--navy) !important;
    border-color: var(--navy) !important;
    color: #fff !important;
}

[data-testid="stExpander"] {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--paper);
    margin-bottom: 8px;
    overflow: hidden;
    box-shadow: none;
}
[data-testid="stExpander"] details summary { font-weight: 600; }
[data-testid="stExpander"] details summary:hover { background: #f7f9fb; }

[data-testid="stTabs"] button[data-baseweb="tab"] { font-weight: 600; }
[data-testid="stAlert"] { border-radius: 8px; }

.st-key-photonav { max-width: 440px; margin: 0 auto 8px; }
.st-key-photonav [data-testid="stHorizontalBlock"] {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
}
.st-key-photonav [data-testid="stColumn"] {
    width: auto !important;
    min-width: 0 !important;
    flex: 1 1 0% !important;
}
.st-key-photonav [data-testid="stColumn"]:nth-child(2) {
    flex: 1.8 1 0% !important;
}
.photo-pager {
    text-align: center;
    font-weight: 700;
    font-size: 0.92rem;
    color: var(--ink);
    line-height: 2.2;
}
.photo-pager span { color: var(--muted); font-weight: 500; }

.hazard-card {
    max-width: 440px;
    margin: 0 auto;
    background: var(--paper);
    border: 1px solid var(--line);
    border-top: 3px solid var(--risk, #8b95a1);
    border-radius: 8px;
    overflow: hidden;
}
.hazard-card.risk-high { --risk: #c0392b; }
.hazard-card.risk-medium { --risk: #d97706; }
.hazard-card.risk-low,
.hazard-card.risk-done { --risk: #2e7d32; }
.hazard-card.risk-unknown { --risk: #8b95a1; }
.photo-frame {
    position: relative;
    height: 232px;
    background: #eef1f4;
}
.hazard-card.is-page .photo-frame { height: 280px; }
.photo-frame img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
}
.photo-empty {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--muted);
    font-size: 0.9rem;
    text-align: center;
    padding: 0 16px;
}
.photo-tag {
    position: absolute;
    top: 10px;
    left: 10px;
    background: rgba(22, 28, 36, 0.78);
    color: #fff;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
}
.card-body { padding: 16px 18px 18px; }
.badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 0 0 10px;
}
.badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 700;
    border: 1px solid transparent;
    line-height: 1.5;
}
.badge.risk-high { background: #fdecea; color: #8e2218; border-color: #f3c7c3; }
.badge.risk-medium { background: #fff6e8; color: #8a4b08; border-color: #f3ddb8; }
.badge.risk-low,
.badge.risk-done { background: #eaf6ec; color: #1b5e20; border-color: #c3e6c8; }
.badge.risk-unknown { background: #f4f6f8; color: #3e4c5e; border-color: #e1e6ec; }
.badge.cat {
    background: #f4f6f8;
    color: #3e4c5e;
    border-color: #e1e6ec;
    font-weight: 600;
}
p.place-name {
    margin: 0 0 12px;
    font-size: 1.28rem !important;
    line-height: 1.35;
    font-weight: 700;
    color: var(--ink);
}
.description {
    margin: 0 0 4px;
    font-size: 0.94rem;
    line-height: 1.65;
    color: #243040;
}
.meta { margin: 8px 0 0; }
.meta-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 16px;
    padding: 9px 0;
    border-top: 1px solid var(--line-soft);
    font-size: 0.9rem;
}
.meta-label { color: var(--muted); font-weight: 500; }
.meta-value {
    color: var(--ink);
    font-weight: 600;
    text-align: right;
}
.meta-value a {
    color: var(--navy);
    font-weight: 600;
    text-decoration: none;
}
.meta-value a:hover { text-decoration: underline; }
.status-done { color: #1b5e20; }
p.card-note, p.preview-note {
    color: var(--muted);
    font-size: 0.8rem !important;
    line-height: 1.45;
}
.card-note { text-align: center; margin: 10px 0 0; }
.preview-note { margin: 0 auto 8px; max-width: 440px; }
p.qr-url {
    margin: 0 0 8px;
    font-size: 0.78rem !important;
    line-height: 1.45;
    color: #3e4c5e;
    word-break: break-all;
}

@media (max-width: 860px) {
    .block-container {
        padding-top: 4.25rem;
        padding-left: 0.85rem;
        padding-right: 0.85rem;
    }
    [data-testid="stHorizontalBlock"]:has(.app-header),
    [data-testid="stHorizontalBlock"]:has(.pane-preview) {
        flex-direction: column;
        align-items: stretch;
    }
    [data-testid="stHorizontalBlock"]:has(.app-header) > [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"]:has(.pane-preview) > [data-testid="stColumn"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 0 !important;
    }
    [data-testid="stColumn"]:has(.pane-preview) {
        position: static;
        max-height: none;
        overflow: visible;
    }
    p.app-title { font-size: 1.28rem !important; }
    .app-title span {
        display: block;
        margin-left: 0;
        margin-top: 2px;
        font-size: 0.95rem;
    }
    .photo-frame,
    .hazard-card.is-page .photo-frame { height: 210px; }
    p.place-name { font-size: 1.16rem !important; }
    .card-body { padding: 14px 14px 16px; }
}
</style>
"""


def inject_css(max_width: int):
    render_html(_CSS.replace("__MAX_WIDTH__", str(max_width)))


# ---------------------------------------------------------------------------
# 열람용 카드 (QR 스캔 화면 / 분할 화면 우측 미리보기 공용)
# ---------------------------------------------------------------------------
def pil_to_data_uri(img) -> str:
    """업로드한 (아직 저장 안 된) 사진을 미리보기용 data URI로 변환."""
    img = img.copy()
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((900, 900))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _photo_block(label, src, empty_text):
    """사진 한 장. src가 없으면 안내 문구를 보여준다."""
    if src:
        body = (
            f'<img src="{html.escape(src, quote=True)}" alt="{html.escape(label)}">'
        )
    else:
        body = f'<div class="photo-empty">{empty_text}</div>'
    return (
        '<div class="photo-frame">'
        f"{body}"
        f'<span class="photo-tag">{label}</span>'
        "</div>"
    )


def _photo_prev():
    st.session_state.photo_idx = 0


def _photo_next():
    st.session_state.photo_idx = 1


def photo_nav(ctx) -> int:
    """이전/다음으로 조치 전(0) / 조치 후(1) 사진을 전환. ctx가 바뀌면 조치 전으로 돌아간다."""
    ss = st.session_state
    if ss.get("_photo_ctx") != ctx:
        ss["_photo_ctx"] = ctx
        ss["photo_idx"] = 0
    idx = ss.get("photo_idx", 0)
    with st.container(key="photonav"):
        c1, c2, c3 = st.columns([1, 2, 1], vertical_alignment="center")
        c1.button("이전", key="pn_prev", disabled=(idx == 0), on_click=_photo_prev, width="stretch")
        name = "조치 전" if idx == 0 else "조치 후"
        c2.markdown(
            f'<div class="photo-pager">{name} <span>({idx + 1}/2)</span></div>',
            unsafe_allow_html=True,
        )
        c3.button("다음", key="pn_next", disabled=(idx == 1), on_click=_photo_next, width="stretch")
    return idx


def hazard_card(d: dict, photo_src, after_src=None, draft: bool = False, ctx=None, page: bool = False):
    """열람용 화면. d: risk/location/category/description/contact_name/contact_phone/action_date
    사진 영역은 이전/다음으로 조치 전 ↔ 조치 후 사진을 전환한다.
    조치 후 사진이 있으면 조치 예정일 대신 '조치완료'를 표시한다."""
    risk = d.get("risk")
    done = bool(after_src)
    location = html.escape(d.get("location") or ("(장소명을 입력하세요)" if draft else ""))
    slug = risk_slug(risk, done)
    page_cls = " is-page" if page else ""

    idx = photo_nav(ctx)
    if idx == 0:
        photo_html = _photo_block("조치 전", photo_src, "등록된 사진 없음")
    else:
        photo_html = _photo_block("조치 후", after_src, "조치완료 사진 없음")

    footer = "읽기 전용 화면입니다" if not draft else "저장 전 미리보기입니다"
    render_html(
        f"""
        <article class="hazard-card risk-{slug}{page_cls}">
            {photo_html}
            <div class="card-body">
                {badge_row(risk, d.get("category"), done)}
                <p class="place-name">{location}</p>
                {meta_rows(d, done)}
            </div>
        </article>
        <p class="card-note">{footer}</p>
        """
    )


def render_viewer(hazard_id):
    """QR 스캔으로 들어온 읽기 전용 화면."""
    render_html(
        """
        <div class="app-header viewer-header">
            <p class="app-title">아차맵 <span>위험요소 QR 관리</span></p>
            <p class="org">한국산업인력공단 경북지사 · 3층 상설시험장</p>
        </div>
        """
    )
    try:
        hazard = db.get_hazard(int(hazard_id))
    except ValueError:
        hazard = None
    if not hazard:
        st.error("해당 위험요소 정보를 찾을 수 없습니다.")
        return
    hazard_card(
        hazard,
        hazard.get("photo_path"),
        hazard.get("after_photo_path"),
        ctx=("view", hazard["id"]),
        page=True,
    )


# ---------------------------------------------------------------------------
# 상태 / 콜백
# ---------------------------------------------------------------------------
def _is_mobile() -> bool:
    try:
        ua = st.context.headers.get("User-Agent", "").lower()
    except Exception:  # noqa: BLE001
        return False
    return any(k in ua for k in ("mobile", "android", "iphone", "ipad"))


def _flash(kind: str, text: str):
    st.session_state["_flash"] = (kind, text)


def _show_flash():
    flash = st.session_state.pop("_flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])


def cb_create():
    ss = st.session_state
    n = ss.nonce
    location = (ss.get(f"n_loc_{n}") or "").strip()
    if not location:
        _flash("warning", "장소명을 입력해주세요.")
        return
    photo = ss.get(f"n_photo_{n}")
    try:
        new_id = db.create_hazard(
            {
                "location": location,
                "category": ss.get(f"n_cat_{n}"),
                "risk": ss.get(f"n_risk_{n}"),
                "photo_path": None,
                "description": ss.get(f"n_desc_{n}") or "",
                "contact_name": ss.get(f"n_cname_{n}") or "",
                "contact_phone": ss.get(f"n_cphone_{n}") or "",
                "action_date": str(ss.get(f"n_date_{n}")),
            }
        )
        photo_url = utils.save_photo(photo, new_id, ss.new_rotation) if photo else None
        if photo_url:
            db.update_hazard(new_id, {"photo_path": photo_url})
        utils.generate_qr(new_id)
    except Exception as e:  # noqa: BLE001
        _flash("error", f"등록 중 오류가 발생했습니다: {e}")
        return
    ss.nonce += 1  # 입력칸을 새 키로 만들어 전부 비운다
    ss.new_rotation = 0
    ss.preview_id = new_id
    ss.section = SECTION_LIST
    _flash("success", f"등록 완료 (ID {new_id}). '목록'에서 QR코드를 다운로드하세요.")


def cb_start_edit(hid):
    st.session_state.editing_id = hid
    st.session_state.preview_id = hid


def cb_cancel_edit():
    st.session_state.editing_id = None


def cb_save_edit(hid, old_photo, old_after):
    ss = st.session_state
    photo = ss.get(f"e_photo_{hid}")
    after = ss.get(f"e_after_{hid}")
    try:
        photo_path = (utils.save_photo(photo, hid) if photo else None) or old_photo
        data = {
            "location": ss.get(f"e_loc_{hid}"),
            "category": ss.get(f"e_cat_{hid}"),
            "risk": ss.get(f"e_risk_{hid}"),
            "photo_path": photo_path,
            "description": ss.get(f"e_desc_{hid}") or "",
            "contact_name": ss.get(f"e_cname_{hid}") or "",
            "contact_phone": ss.get(f"e_cphone_{hid}") or "",
            "action_date": str(ss.get(f"e_date_{hid}")),
        }
        # after_photo_path 컬럼은 조치 후 사진을 올리거나 지울 때만 건드린다.
        if after:
            data["after_photo_path"] = utils.save_photo(after, hid, kind="after")
        elif ss.get(f"e_delafter_{hid}") and old_after:
            utils.delete_photo(hid, "after")
            data["after_photo_path"] = None
        db.update_hazard(hid, data)
    except Exception as e:  # noqa: BLE001
        _flash("error", f"수정 중 오류가 발생했습니다: {e}")
        return
    ss.editing_id = None
    ss.preview_id = hid
    _flash("success", "수정되었습니다.")


def cb_delete(hid):
    ss = st.session_state
    try:
        utils.delete_photo(hid)
        db.delete_hazard(hid)
    except Exception as e:  # noqa: BLE001
        _flash("error", f"삭제 중 오류가 발생했습니다: {e}")
        return
    if ss.preview_id == hid:
        ss.preview_id = None
    if ss.editing_id == hid:
        ss.editing_id = None
    _flash("success", "삭제되었습니다.")


# ---------------------------------------------------------------------------
# 관리자 (CRUD)
# ---------------------------------------------------------------------------
def render_new_form(split: bool):
    ss = st.session_state
    n = ss.nonce
    ss["_new_preview_uri"] = None

    photo = st.file_uploader("현장 사진", type=["png", "jpg", "jpeg"], key=f"n_photo_{n}")
    if photo is not None:
        preview_img = utils.get_preview_image(photo, ss.new_rotation)
        ss["_new_preview_uri"] = pil_to_data_uri(preview_img)
        if not split:
            st.image(preview_img, caption="미리보기 (등록될 모습)", width=300)
        rc1, rc2, rc3 = st.columns(3)
        if rc1.button("왼쪽 회전", key=f"n_rotl_{n}", width="stretch", wrap=True):
            ss.new_rotation = (ss.new_rotation - 90) % 360
            st.rerun()
        if rc2.button("오른쪽 회전", key=f"n_rotr_{n}", width="stretch", wrap=True):
            ss.new_rotation = (ss.new_rotation + 90) % 360
            st.rerun()
        if rc3.button("초기화", key=f"n_rot0_{n}", width="stretch", wrap=True):
            ss.new_rotation = 0
            st.rerun()

    # form이 아니라 일반 위젯이라, 입력하는 즉시 우측 미리보기에 반영된다.
    kicker("위험 정보")
    st.text_input("장소명 / 제목", placeholder="예) 경북지사 상설시험장", key=f"n_loc_{n}")
    st.selectbox("위험 유형", utils.CATEGORIES, key=f"n_cat_{n}")
    st.selectbox(
        "위험도",
        utils.RISK_LEVELS,
        format_func=lambda v: utils.RISK_LABEL_KR.get(v, v),
        key=f"n_risk_{n}",
    )
    st.text_area("상세 설명", key=f"n_desc_{n}")
    kicker("담당과 일정")
    c1, c2 = st.columns(2)
    c1.text_input("담당자 이름", key=f"n_cname_{n}")
    c2.text_input("담당자 연락처", placeholder="010-1234-5678", key=f"n_cphone_{n}")
    st.date_input("조치 예정일", value=date.today(), key=f"n_date_{n}")
    st.button("등록", key=f"n_submit_{n}", type="primary", width="stretch", on_click=cb_create)


def render_edit_form(h, split: bool):
    ss = st.session_state
    hid = h["id"]
    photo = st.file_uploader("현장 사진 교체 (선택)", type=["png", "jpg", "jpeg"], key=f"e_photo_{hid}")
    if photo is not None:
        img = utils.get_preview_image(photo)
        ss["_edit_preview_uri"] = pil_to_data_uri(img)
        if not split:
            st.image(img, caption="교체될 사진", width=250)
    after = st.file_uploader(
        "조치 후 사진 (올리면 '조치완료'로 표시됩니다)", type=["png", "jpg", "jpeg"], key=f"e_after_{hid}"
    )
    if after is not None:
        aimg = utils.get_preview_image(after)
        ss["_edit_after_uri"] = pil_to_data_uri(aimg)
        if not split:
            st.image(aimg, caption="조치 후 사진", width=250)
    if h.get("after_photo_path"):
        st.checkbox("기존 조치 후 사진 삭제 (조치 전 상태로 되돌리기)", key=f"e_delafter_{hid}")

    kicker("위험 정보")
    st.text_input("장소명 / 제목", value=h["location"] or "", key=f"e_loc_{hid}")
    st.selectbox(
        "위험 유형", utils.CATEGORIES,
        index=utils.CATEGORIES.index(h["category"]) if h["category"] in utils.CATEGORIES else 0,
        key=f"e_cat_{hid}",
    )
    st.selectbox(
        "위험도", utils.RISK_LEVELS,
        index=utils.RISK_LEVELS.index(h["risk"]) if h["risk"] in utils.RISK_LEVELS else 0,
        format_func=lambda v: utils.RISK_LABEL_KR.get(v, v),
        key=f"e_risk_{hid}",
    )
    st.text_area("상세 설명", value=h.get("description") or "", key=f"e_desc_{hid}")
    kicker("담당과 일정")
    st.text_input("담당자 이름", value=h.get("contact_name") or "", key=f"e_cname_{hid}")
    st.text_input("담당자 연락처", value=h.get("contact_phone") or "", key=f"e_cphone_{hid}")
    try:
        default_date = date.fromisoformat(h["action_date"]) if h.get("action_date") else date.today()
    except Exception:  # noqa: BLE001
        default_date = date.today()
    st.date_input("조치 예정일", value=default_date, key=f"e_date_{hid}")

    col_s, col_c = st.columns(2)
    col_s.button(
        "저장", key=f"e_save_{hid}", type="primary", width="stretch",
        on_click=cb_save_edit, args=(hid, h.get("photo_path"), h.get("after_photo_path")),
    )
    col_c.button("취소", key=f"e_cancel_{hid}", width="stretch", on_click=cb_cancel_edit)


def _photo_tools(h, hid, kind, key_name, cap):
    if not h.get(key_name):
        return
    kicker(cap)
    try:
        st.image(h[key_name], width=360)
    except Exception:  # noqa: BLE001
        st.caption("사진을 표시할 수 없습니다.")
    b1, b2 = st.columns(2)
    if b1.button("왼쪽 회전", key=f"rotL_{kind}_{hid}", width="stretch"):
        _rotate(hid, -90, kind)
    if b2.button("오른쪽 회전", key=f"rotR_{kind}_{hid}", width="stretch"):
        _rotate(hid, 90, kind)


def render_hazard_item(h, split: bool):
    hid = h["id"]
    editing = st.session_state.editing_id == hid
    done = bool(h.get("after_photo_path"))

    with st.expander(list_label(h), expanded=editing):
        render_html(badge_row(h.get("risk"), h.get("category"), done))
        if editing:
            render_edit_form(h, split)
            return

        for kind, key_name, cap in (
            ("before", "photo_path", "조치 전"),
            ("after", "after_photo_path", "조치 후"),
        ):
            _photo_tools(h, hid, kind, key_name, cap)

        render_html(meta_rows(h, done))

        qr_path, url = utils.generate_qr(hid)
        kicker("QR 코드")
        q1, q2 = st.columns([1, 1.45], vertical_alignment="center")
        q1.image(qr_path, width="stretch")
        with q2:
            render_html(f'<p class="qr-url">{html.escape(url)}</p>')
            with open(qr_path, "rb") as f:
                st.download_button(
                    "QR 이미지 다운로드", f, file_name=f"qr_{hid}.png", mime="image/png",
                    key=f"dl_{hid}", width="stretch",
                )

        col_e, col_d = st.columns(2)
        col_e.button("수정", key=f"editbtn_{hid}", width="stretch", on_click=cb_start_edit, args=(hid,))
        col_d.button(
            "삭제", key=f"delbtn_{hid}", width="stretch", on_click=cb_delete, args=(hid,),
            help="이 위험요소와 사진을 삭제합니다.",
        )


def _rotate(hid, degrees, kind="before"):
    """저장된 사진을 회전하고, 새 주소(캐시 방지 값 포함)를 DB에 반영해 바로 보이게 한다."""
    new_url = utils.rotate_saved_photo(hid, degrees, kind)
    if new_url:
        db.update_hazard(hid, {"after_photo_path" if kind == "after" else "photo_path": new_url})
        st.session_state.preview_id = hid
    st.rerun()


def render_admin(hazards, split: bool):
    _show_flash()
    section = st.segmented_control(
        "구분",
        [SECTION_LIST, SECTION_NEW],
        key="section",
        label_visibility="collapsed",
        width="stretch",
        required=True,
    )
    st.session_state["_edit_preview_uri"] = None
    st.session_state["_edit_after_uri"] = None

    if section == SECTION_NEW:
        render_new_form(split)
        return

    if not hazards:
        st.info("등록된 위험요소가 없습니다. '신규 등록'에서 추가하세요.")
        return

    # 조치 후 사진이 등록된 항목 = 조치완료
    todo = [h for h in hazards if not h.get("after_photo_path")]
    done = [h for h in hazards if h.get("after_photo_path")]
    tab_todo, tab_done = st.tabs([f":red[조치 전] ({len(todo)})", f":green[조치완료] ({len(done)})"])
    with tab_todo:
        if not todo:
            st.caption("조치 전 항목이 없습니다.")
        for h in todo:
            render_hazard_item(h, split)
    with tab_done:
        if not done:
            st.caption("조치완료 항목이 없습니다.")
        for h in done:
            render_hazard_item(h, split)


# ---------------------------------------------------------------------------
# 열람용 미리보기 (분할 화면 우측)
# ---------------------------------------------------------------------------
def render_preview(hazards):
    ss = st.session_state
    by_id = {h["id"]: h for h in hazards}

    if ss.get("section") == SECTION_NEW:
        n = ss.nonce
        draft = {
            "risk": ss.get(f"n_risk_{n}", utils.RISK_LEVELS[0]),
            "category": ss.get(f"n_cat_{n}", utils.CATEGORIES[0]),
            "location": ss.get(f"n_loc_{n}", ""),
            "description": ss.get(f"n_desc_{n}", ""),
            "contact_name": ss.get(f"n_cname_{n}", ""),
            "contact_phone": ss.get(f"n_cphone_{n}", ""),
            "action_date": ss.get(f"n_date_{n}", date.today()),
        }
        render_html('<p class="preview-note">입력 내용이 바로 반영됩니다. 아직 저장 전입니다.</p>')
        hazard_card(draft, ss.get("_new_preview_uri"), None, draft=True, ctx=("new", ss.nonce))
        return

    eid = ss.editing_id
    if eid in by_id:
        h = by_id[eid]
        draft = {
            "risk": ss.get(f"e_risk_{eid}", h["risk"]),
            "category": ss.get(f"e_cat_{eid}", h["category"]),
            "location": ss.get(f"e_loc_{eid}", h["location"]),
            "description": ss.get(f"e_desc_{eid}", h.get("description")),
            "contact_name": ss.get(f"e_cname_{eid}", h.get("contact_name")),
            "contact_phone": ss.get(f"e_cphone_{eid}", h.get("contact_phone")),
            "action_date": ss.get(f"e_date_{eid}", h.get("action_date")),
        }
        render_html(
            f'<p class="preview-note">수정 내용이 바로 반영됩니다. ID {eid}, 아직 저장 전입니다.</p>'
        )
        after_src = ss.get("_edit_after_uri")
        if not after_src and not ss.get(f"e_delafter_{eid}"):
            after_src = h.get("after_photo_path")
        hazard_card(
            draft,
            ss.get("_edit_preview_uri") or h.get("photo_path"),
            after_src,
            draft=True,
            ctx=("edit", eid),
        )
        return

    pid = ss.preview_id if ss.preview_id in by_id else (hazards[0]["id"] if hazards else None)
    if pid is None:
        st.info("미리볼 위험요소가 없습니다.")
        return
    h = by_id[pid]
    hazard_card(h, h.get("photo_path"), h.get("after_photo_path"), ctx=("view", pid))


# ---------------------------------------------------------------------------
def main():
    ss = st.session_state
    ss.setdefault("nonce", 0)
    ss.setdefault("new_rotation", 0)
    ss.setdefault("editing_id", None)
    ss.setdefault("preview_id", None)
    ss.setdefault("section", SECTION_LIST)

    query_id = st.query_params.get("id")
    if query_id:  # QR 스캔: 읽기 전용 화면만
        inject_css(520)
        render_viewer(query_id)
        return

    # PC에서는 분할 화면이 기본, 휴대폰에서는 관리자 화면만 기본
    ss.setdefault("split_view", not _is_mobile())
    split = ss.split_view
    inject_css(1120 if split else 760)

    head, toggle_col = st.columns([5, 2], vertical_alignment="center")
    with head:
        render_html(
            '<div class="app-header">'
            '<p class="app-title">아차맵 <span>위험요소 QR 관리</span></p>'
            '<p class="org">한국산업인력공단 경북지사 · 3층 상설시험장</p>'
            '</div>'
        )
    toggle_col.toggle(
        "화면 분할",
        key="split_view",
        help="관리 화면과 QR 미리보기를 나란히 봅니다.",
    )

    if not split:
        render_admin(db.get_all_hazards(), split=False)
        return

    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        render_html(
            '<div class="pane-label">'
            '<p class="pane-title">관리</p>'
            '<p>위험요소를 등록하고, 수정하고, QR을 발급합니다.</p>'
            '</div>'
        )
        # 콜백(저장/삭제)은 이 스크립트 실행 전에 이미 처리되므로, 아래 목록은 항상 최신이다.
        hazards = db.get_all_hazards()
        render_admin(hazards, split=True)
    with right:
        render_html(
            '<div class="pane-label pane-preview">'
            '<p class="pane-title">QR 미리보기</p>'
            '<p>QR을 스캔하면 현장에 이 화면이 열립니다.</p>'
            '</div>'
        )
        render_preview(hazards)


main()
