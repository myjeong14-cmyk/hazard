import base64
import html
import io
import re
from datetime import date

import streamlit as st

import db
import utils

st.set_page_config(page_title="위험요소 지도 관리자탭", layout="wide")
db.init_db()

SECTION_LIST = ":material/format_list_bulleted: 목록"
SECTION_NEW = ":material/add_circle: 신규 등록"
PANE_HEIGHT = 820

# ---------------------------------------------------------------------------
# 현장 목록: 새 현장이 생기면 아래에 한 줄 추가하면 왼쪽 메뉴에 바로 나타난다.
#   id   : DB(hazards.site)에 저장되는 값 (영문/숫자, 한 번 정하면 바꾸지 않기)
#   name : 메뉴에 보이는 이름 / sub: 보조 설명
# 첫 번째 현장이 기본 현장이며, site 값이 비어 있는 기존 데이터는 기본 현장으로 본다.
# ---------------------------------------------------------------------------
SITES = [
    {"id": "gb-3f", "name": "경북지사", "sub": "3층 상설시험장", "org": "한국산업인력공단"},
    # {"id": "gb-ext1", "name": "OO고등학교", "sub": "외부시험장", "org": "한국산업인력공단"},
]
SITE_BY_ID = {s["id"]: s for s in SITES}
DEFAULT_SITE = SITES[0]["id"]
DONE_COLOR = "#43a047"  # 조치완료 표시 색(초록)
BLUE = "#2f6bed"  # 강조색 (레퍼런스의 파랑)


@st.cache_data(show_spinner=False)
def qr_png(hazard_id: int, url: str) -> bytes:
    """QR 이미지는 주소가 같으면 다시 만들지 않는다 (화면 갱신 속도 개선)."""
    import qrcode

    buf = io.BytesIO()
    qrcode.make(url).save(buf, "PNG")
    return buf.getvalue()


def render_html(markup: str):
    """줄 앞의 공백과 빈 줄을 제거해서 마크다운 파서가 코드블록/문단으로 오인하지 않게 한 뒤 렌더링."""
    cleaned = "\n".join(line.strip() for line in markup.strip().splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 표시용 도우미 (화면 표시만 담당, 데이터는 바꾸지 않음)
# ---------------------------------------------------------------------------
def _state(h) -> str:
    """목록 카드 색 구분용: 조치완료(Done) 또는 위험도(High/Medium/Low)."""
    if h.get("after_photo_path"):
        return "Done"
    return h.get("risk") if h.get("risk") in utils.RISK_LEVELS else "Low"


def _dday(value):
    """조치 예정일까지 남은 날짜 → (표시 글자, 색 구분). 날짜가 없거나 이상하면 None."""
    try:
        d = value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
    except Exception:  # noqa: BLE001
        return None
    diff = (d - date.today()).days
    if diff > 0:
        return f"D-{diff}", "soon" if diff <= 7 else "normal"
    if diff == 0:
        return "오늘", "soon"
    return f"지연 D+{-diff}", "late"


def _site_of(h) -> str:
    """항목의 현장 id. site 칸이 없거나 비어 있으면 기본 현장."""
    return h.get("site") or DEFAULT_SITE


def _site_label(site_id) -> str:
    s = SITE_BY_ID.get(site_id, SITES[0])
    return f"{s['name']} · {s['sub']}"


def _site_field() -> dict:
    """새로 등록할 때 저장할 현장 값. DB에 site 칸이 아직 없으면 넣지 않는다(기본 현장으로 처리됨)."""
    ss = st.session_state
    return {"site": ss.get("site", DEFAULT_SITE)} if ss.get("_site_col") else {}


def cb_site():
    """현장을 바꾸면 선택/펼침/수정 상태를 초기화한다."""
    ss = st.session_state
    ss.preview_id = None
    ss.open_id = None
    ss.editing_id = None


def _uid(ctx) -> str:
    return "hc_" + re.sub(r"[^0-9a-zA-Z]+", "_", str(ctx or "x"))


ICON_USER = (
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>'
)
ICON_PHONE = (
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg>'
)
ICON_CAL = (
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>'
)
ICON_CHECK = (
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
)



# ---------------------------------------------------------------------------
# 공통 스타일
# ---------------------------------------------------------------------------
def inject_css(max_width: int):
    """레퍼런스(라이트 KPI 대시보드) 스타일: 연회색 바탕, 흰 카드, 파란 강조색 하나, Pretendard(Inter 계열) 글꼴."""
    css = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
@property --n { syntax: '<integer>'; initial-value: 0; inherits: false; }
@property --p { syntax: '<number>'; initial-value: 0; inherits: false; }

:root {
  --font: 'Pretendard Variable', Pretendard, Inter, -apple-system, BlinkMacSystemFont, 'Malgun Gothic', sans-serif;
  --bg: #f4f5f7; --card: #ffffff; --line: #eceef2; --line-2: #e2e5ea;
  --ink: #111318; --ink-2: #3d4350; --mute: #7b8191;
  --blue: __BLUE__; --blue-2: #a9c3fb; --blue-soft: #edf2ff;
  --high: __HIGH__; --mid: __MID__; --low: __LOW__; --done: __DONE__;
  --radius: 14px;
  --ease: cubic-bezier(.22,.8,.26,1);
}

/* ---------- 글꼴: 아이콘(Material) 글꼴은 건드리지 않음 ---------- */
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp li,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp div, .stApp span:not([data-testid="stIconMaterial"]) {
  font-family: var(--font);
}
.stApp { background: var(--bg); color: var(--ink); font-size: 1.1rem; font-feature-settings: "tnum" 1, "ss01" 1; }
header[data-testid="stHeader"] { background: transparent; }
.stMarkdown p, .stMarkdown li, [data-testid="stWidgetLabel"] p,
.stButton>button p, .stDownloadButton>button p, [data-testid="stTab"] p,
.stRadio label p, .stCheckbox label p, [data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] span, .stAlert p { font-size: 1.06rem !important; }
.stCaption p { font-size: 1rem !important; color: var(--mute) !important; }
[data-testid="stWidgetLabel"] p { font-weight: 600; color: var(--ink-2); }
input, textarea, [data-baseweb="select"] div { font-size: 1.06rem !important; }
h1, h2, h3 { letter-spacing: -0.02em; }

.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: __MAXW__px; }
@media (max-width: 640px) { .block-container { padding-left: 14px; padding-right: 14px; padding-top: 3.2rem; } }

/* ---------- 움직임 ---------- */
@keyframes rise { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@keyframes count { from { --n: 0; } }
@keyframes fill { from { --p: 0; } }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 var(--pc); } 70% { box-shadow: 0 0 0 9px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }

/* ---------- 왼쪽 사이드바 ---------- */
section[data-testid="stSidebar"] { background: #fff; border-right: 1px solid var(--line); width: 250px !important; min-width: 250px !important; }
section[data-testid="stSidebar"] .block-container, section[data-testid="stSidebarContent"] { padding-top: 1.2rem; }
.brand { font-size: 1.85rem; font-weight: 700; letter-spacing: -0.04em; color: var(--ink); line-height: 1; margin: 6px 4px 4px; }
.brand b { color: var(--blue); font-weight: 700; }
.brand-sub { font-size: .9rem; color: var(--mute); margin: 0 4px 22px; }
.side-label { font-size: .8rem; font-weight: 600; color: var(--mute); letter-spacing: .04em; margin: 22px 12px 6px; padding-top: 16px; border-top: 1px solid var(--line); }
.st-key-site [role="radiogroup"] { gap: 2px; flex-direction: column; width: 100%; }
.st-key-site [role="radiogroup"] label { width: 100%; margin: 0 !important; padding: 9px 12px; border-radius: 10px; cursor: pointer; transition: background .2s var(--ease); }
.st-key-site [role="radiogroup"] label > div > div:first-child { display: none; }
.st-key-site [role="radiogroup"] label p { font-weight: 600; color: var(--ink-2); font-size: 1rem !important; line-height: 1.45; }
.st-key-site [role="radiogroup"] label p .stMarkdownColoredText { font-weight: 400; font-size: .88rem; }
.st-key-site [role="radiogroup"] label:hover { background: #f6f7f9; }
.st-key-site [role="radiogroup"] label[data-selected="true"] { background: var(--bg); }
.st-key-site [role="radiogroup"] label[data-selected="true"] p { color: var(--ink); font-weight: 700; }
[data-testid="stMain"] .st-key-site [role="radiogroup"] { flex-direction: row; flex-wrap: wrap; width: auto; }
[data-testid="stMain"] .st-key-site [role="radiogroup"] label { width: auto; background: #fff; }

/* 목록 / 신규 등록: 사이드바에서는 세로 메뉴, 본문에서는 알약 탭 */
.st-key-section [role="radiogroup"] { gap: 4px; }
.st-key-section [role="radiogroup"] label { margin: 0 !important; padding: 10px 12px; border-radius: 10px; cursor: pointer; transition: background .2s var(--ease); }
.st-key-section [role="radiogroup"] label > div > div:first-child { display: none; }
.st-key-section [role="radiogroup"] label p { font-weight: 600; color: var(--ink-2); }
.st-key-section [role="radiogroup"] label:hover { background: #f6f7f9; }
.st-key-section [role="radiogroup"] label[data-selected="true"] { background: var(--blue-soft); }
.st-key-section [role="radiogroup"] label[data-selected="true"] p,
.st-key-section [role="radiogroup"] label[data-selected="true"] [data-testid="stIconMaterial"] { color: var(--blue); }
section[data-testid="stSidebar"] .st-key-section, section[data-testid="stSidebar"] .st-key-site,
section[data-testid="stSidebar"] .st-key-section > div, section[data-testid="stSidebar"] .st-key-site > div { width: 100% !important; }
section[data-testid="stSidebar"] .st-key-section [role="radiogroup"] { flex-direction: column; width: 100%; }
section[data-testid="stSidebar"] .st-key-section [role="radiogroup"] label { width: 100%; }
[data-testid="stMain"] .st-key-section [role="radiogroup"] { display: inline-flex; background: #eef0f3; padding: 4px; border-radius: 12px; }
[data-testid="stMain"] .st-key-section [role="radiogroup"] label[data-selected="true"] { background: #fff; box-shadow: 0 1px 2px rgba(16,24,40,.06), 0 2px 6px rgba(16,24,40,.06); }

/* ---------- 상단 제목 줄 ---------- */
.page-h { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.page-h h1 { font-size: 1.75rem !important; font-weight: 700; margin: 0 !important; padding: 0 !important; color: var(--ink); }
.page-h > span { color: var(--mute); font-size: 1rem; }
.st-key-pagehead { border-bottom: 1px solid var(--line-2); padding-bottom: 16px !important; margin-bottom: 6px; }
.st-key-pagehead [data-testid="stMarkdownContainer"] { margin-bottom: 0; }
.st-key-split_view label[data-selected="true"] > div:first-of-type { background-color: var(--blue) !important; }

/* ---------- KPI 카드 ---------- */
.kpis { display: grid; grid-template-columns: 1.35fr 1.35fr 1fr; grid-template-rows: auto auto; gap: 14px; margin: 14px 0 18px; }
.kpi { background: var(--card); border-radius: var(--radius); padding: 16px 18px; animation: rise .5s var(--ease) both; transition: box-shadow .2s var(--ease), transform .2s var(--ease); }
.kpi:hover { box-shadow: 0 6px 18px rgba(16,24,40,.07); transform: translateY(-2px); }
.kpi.wide { grid-row: span 2; display: flex; flex-direction: column; }
.kpi:nth-child(2) { animation-delay: .05s; } .kpi:nth-child(3) { animation-delay: .1s; } .kpi:nth-child(4) { animation-delay: .13s; }
.kpi:nth-child(5) { animation-delay: .16s; } .kpi:nth-child(6) { animation-delay: .19s; } .kpi:nth-child(7) { animation-delay: .22s; } .kpi:nth-child(8) { animation-delay: .25s; }
.kpi-label { font-size: .95rem; font-weight: 500; color: var(--ink-2); }
.kpi-num { font-size: 1.75rem; font-weight: 700; color: var(--ink); line-height: 1.2; margin-top: 2px; letter-spacing: -0.02em;
  counter-reset: n var(--n); animation: count 1s .15s var(--ease) both; }
.kpi-num::before { content: counter(n); }
.kpi-num small { font-size: 1rem; font-weight: 600; color: var(--mute); margin-left: 3px; }
.kpi-num.late { color: var(--high); }
.kpi:not(.wide) { display: flex; flex-direction: column; justify-content: center; }
.kpi-hint { font-size: .86rem; color: var(--mute); margin-top: 2px; }
.kpi-body { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex: 1; margin-top: 8px; }
.legend { list-style: none; margin: 0; padding: 0; font-size: .86rem; color: var(--ink-2); }
.legend li { display: flex; align-items: center; gap: 7px; margin: 5px 0; white-space: nowrap; }
.legend i { width: 9px; height: 9px; border-radius: 3px; display: inline-block; flex: none; }
.legend b { font-weight: 600; color: var(--ink); }
.donut { --p: 1; width: 104px; height: 104px; border-radius: 50%; flex: none; position: relative;
  animation: fill 1.2s .2s var(--ease) both; }
.donut::after { content: ""; position: absolute; inset: 22px; border-radius: 50%; background: #fff; }
@media (max-width: 900px) {
  .kpis { grid-template-columns: 1fr 1fr; }
  .kpi.wide { grid-column: span 2; grid-row: auto; }
  .kpi.wide + .kpi.wide ~ .kpi { grid-column: auto; }
}

/* ---------- 좌우 구획 (흰 카드) ---------- */
.st-key-pane_admin, .st-key-pane_view { border: none !important; border-radius: var(--radius) !important; background: var(--card);
  animation: rise .55s .1s var(--ease) both; }
.st-key-pane_view { background: #fafbfc; }
.card-h { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 2px 2px 10px; border-bottom: 1px solid var(--line); margin-bottom: 4px; }
.card-h b { font-size: 1.08rem; font-weight: 600; color: var(--ink); }
.card-h span { font-size: .92rem; color: var(--mute); }

/* 탭: 알약 모양 (레퍼런스의 Overview 탭) */
[data-testid="stTabs"] [role="tablist"] { display: inline-flex; gap: 4px; background: #eef0f3; padding: 4px; border-radius: 12px; border: none; }
[data-testid="stTab"] { padding: 8px 16px !important; border-radius: 9px; transition: background .2s var(--ease); }
[data-testid="stTab"] p { font-weight: 600; color: var(--mute); }
[data-testid="stTab"][aria-selected="true"] { background: #fff; box-shadow: 0 1px 2px rgba(16,24,40,.06), 0 2px 6px rgba(16,24,40,.06); color: var(--blue) !important; }
[data-testid="stTab"][aria-selected="true"] p { color: var(--blue); }
[data-testid="stTab"] .react-aria-SelectionIndicator { display: none; }
[data-testid="stTabs"] [role="tablist"] { box-shadow: none !important; border-bottom: none !important; }
[data-testid="stTabs"] [role="tablist"]::after, [data-testid="stTabs"] [role="tablist"]::before { display: none !important; }

/* ---------- 목록 행 (레퍼런스의 Top Revenue 목록) ---------- */
.st-key-tl_todo, .st-key-tl_done { gap: 0; }
[class*="st-key-hzc_"] {
  position: relative; overflow: visible; background: transparent; border-radius: 12px;
  padding: 8px 10px 10px 58px; gap: 0; border-bottom: 1px solid var(--line);
  animation: rise .4s var(--ease) both; transition: background .18s var(--ease);
  --sc: var(--low); --st: #e9f6ea; --pc: transparent;
}
[class*="st-key-hzc_"]:nth-child(2) { animation-delay: .04s; } [class*="st-key-hzc_"]:nth-child(3) { animation-delay: .08s; }
[class*="st-key-hzc_"]:nth-child(4) { animation-delay: .12s; } [class*="st-key-hzc_"]:nth-child(n+5) { animation-delay: .16s; }
[class*="st-key-hzc_"][class*="_High_"] { --sc: var(--high); --st: #fdeceb; --pc: rgba(229,57,53,.4); }
[class*="st-key-hzc_"][class*="_Medium_"] { --sc: var(--mid); --st: #fff2e3; }
[class*="st-key-hzc_"][class*="_Low_"] { --sc: var(--low); --st: #e9f6ea; }
[class*="st-key-hzc_"][class*="_Done_"] { --sc: var(--done); --st: #e9f6ea; }
[class*="st-key-hzc_"]::before {
  content: ""; position: absolute; left: 12px; top: 16px; width: 36px; height: 36px; border-radius: 10px;
  background: radial-gradient(circle, var(--sc) 0 5px, transparent 5.6px), var(--st);
}
[class*="st-key-hzc_"][class*="_High_"]:not([class*="_Done_"])::before { animation: pulse 2s infinite; }
[class*="st-key-hzc_"]:hover { background: #f7f8fa; }
[class*="st-key-hzc_on_"] { background: var(--blue-soft) !important; border-bottom-color: transparent; }
[class*="st-key-hzc_"] > [data-testid="stElementContainer"],
[class*="st-key-hzc_"][class*="_shut_"] [data-testid="stElementContainer"],
[class*="st-key-hzc_"][class*="_shut_"] .stButton,
[class*="st-key-hzc_"][class*="_shut_"] .stButton>button { position: static; }
[class*="st-key-hzc_"][class*="_shut_"] .stButton>button::after { content: ""; position: absolute; inset: 0; border-radius: 12px; }
[class*="st-key-hzc_"] .stButton>button[kind="tertiary"] { justify-content: flex-start; text-align: left; border: none; background: transparent; padding: 0.35rem 5.5rem 0 0; width: 100%; box-shadow: none; min-height: 0; }
[class*="st-key-hzc_"] .stButton>button[kind="tertiary"] > div,
[class*="st-key-hzc_"] .stButton>button[kind="tertiary"] [data-testid="stMarkdownContainer"] { justify-content: flex-start; text-align: left; width: 100%; }
[class*="st-key-hzc_"] .stButton>button[kind="tertiary"] p { font-size: 1.1rem !important; font-weight: 600; color: var(--ink); }
[class*="st-key-hzc_"] .stButton>button[kind="tertiary"]:hover { transform: none; box-shadow: none; }
[class*="st-key-hzc_"] [data-testid="stMarkdownContainer"] { margin-bottom: 0; }
.hz-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; font-size: .95rem; color: var(--mute); padding-right: 5.5rem; }
.hz-meta .sep { color: #c9ced8; }
.hz-right { position: absolute; right: 16px; top: 22px; font-weight: 700; font-size: 1.05rem; color: var(--ink); }
.hz-right.soon { color: #c26a00; } .hz-right.late { color: var(--high); } .hz-right.done { color: var(--done); }

.pill { display: inline-flex; align-items: center; gap: 4px; padding: 2px 9px; border-radius: 6px; font-size: .86rem; font-weight: 600; line-height: 1.6; background: #f1f2f5; color: var(--ink-2); }
.pill.soon { background: #fff4e5; color: #b45f06; } .pill.late { background: #fdecec; color: #c62828; } .pill.done { background: #e8f5e9; color: #2e7d32; }

/* ---------- 버튼 / 입력칸 ---------- */
.stButton>button { border-radius: 9px; border: 1px solid var(--line-2); padding: 0.5rem 1rem; font-weight: 600; color: var(--ink-2); background: #fff;
  transition: transform .15s var(--ease), box-shadow .15s var(--ease), border-color .15s, color .15s, background .15s; }
.stButton>button:hover { border-color: var(--blue); color: var(--blue); box-shadow: 0 3px 10px rgba(47,107,237,.12); transform: translateY(-1px); }
.stButton>button:active { transform: scale(.98); }
.stButton>button[kind="primary"] { background: var(--high); border-color: var(--high); color: #fff; }
.stButton>button[kind="primary"]:hover { background: #c62828; border-color: #c62828; color: #fff; }
[class*="st-key-n_submit_"] button, [class*="st-key-e_save_"] button { background: var(--blue); border-color: var(--blue); color: #fff; }
[class*="st-key-n_submit_"] button p, [class*="st-key-e_save_"] button p { color: #fff; }
[class*="st-key-n_submit_"] button:hover, [class*="st-key-e_save_"] button:hover { background: #2357c9; border-color: #2357c9; color: #fff; }
.stDownloadButton>button { border-radius: 9px; font-weight: 600; border: 1px solid var(--line-2); color: var(--ink); background: #fff; }
.stDownloadButton>button:hover { border-color: var(--blue); color: var(--blue); }
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div, [data-testid="stFileUploaderDropzone"] {
  background: #fff !important; border: 1px solid var(--line-2) !important; border-radius: 9px !important; }
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea, [data-baseweb="base-input"] { background: #fff !important; }
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color: var(--blue) !important; box-shadow: 0 0 0 3px rgba(47,107,237,.14); }
[data-testid="stImage"] img { border-radius: 10px; }

/* ---------- 상세 정보 ---------- */
.info-box { margin-top: 4px; }
.info-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 11px 2px; border-bottom: 1px solid var(--line); font-size: 1.05rem; }
.info-row:last-child { border-bottom: none; }
.info-label { color: var(--mute); font-weight: 500; display: inline-flex; align-items: center; gap: 8px; }
.info-label svg { color: #a6adbb; flex: none; }
.info-value { color: var(--ink); font-weight: 600; text-align: right; }
.info-value a { color: var(--blue); text-decoration: none; }
.desc { background: var(--bg); border-radius: 10px; padding: 12px 14px; font-size: 1.05rem; color: var(--ink-2); line-height: 1.65; margin: 10px 0 6px; }
.badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 6px; font-size: .9rem; font-weight: 600; margin-right: 6px; }
.badge-category { background: #f1f2f5; color: var(--ink-2); }

/* ---------- 열람용 카드 ---------- */
.hc { position: relative; max-width: 480px; margin: 0 auto; background: #fff; border-radius: 18px; overflow: hidden;
  border: 1px solid var(--line); box-shadow: 0 1px 2px rgba(16,24,40,.04), 0 8px 24px rgba(16,24,40,.06); animation: rise .55s var(--ease) both; }
.hc-r { position: absolute; opacity: 0; pointer-events: none; }
.hc-head { padding: 18px 20px 12px; }
.hc-brand { display: flex; align-items: center; justify-content: space-between; font-size: .85rem; color: var(--mute); margin-bottom: 12px; }
.hc-brand b { font-size: 1.05rem; font-weight: 700; letter-spacing: -0.03em; color: var(--ink); }
.hc-tags { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.hc-risk { display: inline-flex; align-items: center; gap: 7px; padding: 4px 10px; border-radius: 7px; font-weight: 700; font-size: .95rem; color: var(--rc); background: var(--rt); }
.hc-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--rc); flex: none; }
.hc-dot.pulse { --pc: var(--rc); animation: pulse 1.8s infinite; }
.hc-title { margin: 0 !important; padding: 0 !important; font-size: 1.55rem !important; font-weight: 700; color: var(--ink); line-height: 1.3; letter-spacing: -0.02em; }
.hc-toggle { position: relative; display: grid; grid-template-columns: 1fr 1fr; margin: 4px 20px 12px; padding: 4px; border-radius: 12px; background: #eef0f3; }
.hc-thumb { position: absolute; top: 4px; left: 4px; bottom: 4px; width: calc(50% - 4px); border-radius: 9px; background: #fff;
  box-shadow: 0 1px 2px rgba(16,24,40,.08), 0 2px 8px rgba(16,24,40,.08); transition: transform .4s var(--ease); }
.hc-toggle label { position: relative; z-index: 1; text-align: center; padding: 9px 0; margin: 0; cursor: pointer; font-weight: 600; font-size: 1rem; color: var(--mute);
  transition: color .3s; user-select: none; -webkit-tap-highlight-color: transparent; }
.hc-toggle label.lb { color: var(--blue); }
.hc-ra:checked ~ .hc-toggle .hc-thumb { transform: translateX(100%); }
.hc-ra:checked ~ .hc-toggle label.lb { color: var(--mute); }
.hc-ra:checked ~ .hc-toggle label.la { color: var(--done); }
.hc-r:focus-visible ~ .hc-toggle { outline: 3px solid var(--blue-2); outline-offset: 2px; }
.hc-photo { position: relative; margin: 0 20px; height: 300px; border-radius: 12px; overflow: hidden; background: #f1f2f5; }
.hc-slide { position: absolute; inset: 0; transition: opacity .45s var(--ease), transform .6s var(--ease); }
.hc-slide .bg { position: absolute; inset: -20px; background-size: cover; background-position: center; filter: blur(18px); opacity: .5; }
.hc-slide img { position: relative; width: 100%; height: 100%; object-fit: contain; display: block; }
.hc-empty { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; color: #9aa2b1; font-size: 1rem; }
.hc-after { opacity: 0; transform: scale(1.04); }
.hc-ra:checked ~ .hc-photo .hc-after { opacity: 1; transform: none; }
.hc-ra:checked ~ .hc-photo .hc-before { opacity: 0; transform: scale(.97); }
.hc-cap { position: absolute; left: 10px; top: 10px; z-index: 2; padding: 3px 10px; border-radius: 7px; background: rgba(17,19,24,.62); color: #fff; font-size: .82rem; font-weight: 600; }
.hc-body { padding: 12px 20px 18px; }
.hc-foot { text-align: center; color: #9aa2b1; font-size: .92rem; margin: 14px 0 0; }
@media (max-width: 420px) { .hc-photo { height: 280px; margin: 0 14px; } .hc-toggle { margin: 4px 14px 12px; } .hc-head, .hc-body { padding-left: 16px; padding-right: 16px; } }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
</style>
"""
    for k, v in {
        "__MAXW__": str(max_width), "__BLUE__": BLUE, "__DONE__": DONE_COLOR,
        "__HIGH__": utils.RISK_COLOR["High"], "__MID__": utils.RISK_COLOR["Medium"], "__LOW__": utils.RISK_COLOR["Low"],
    }.items():
        css = css.replace(k, v)
    render_html(css)


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


def _slide(cls, label, src, empty_text):
    """사진 한 장. 사진 뒤에는 같은 사진을 흐리게 깔아 빈 여백을 채운다."""
    if src:
        esc = html.escape(src, quote=True)
        # 업로드 직후 미리보기(data URI)는 용량이 커서 배경 흐림을 생략
        bg = "" if src.startswith("data:") else f'<div class="bg" style="background-image:url(\'{esc}\')"></div>'
        body = f'{bg}<img src="{esc}" alt="{label} 사진">'
    else:
        body = f'<div class="hc-empty"><span style="font-size:1.8rem;">📷</span>{empty_text}</div>'
    return f'<div class="hc-slide {cls}">{body}<span class="hc-cap">{label}</span></div>'


@st.fragment
def hazard_card(d: dict, photo_src, after_src=None, draft: bool = False, ctx=None):
    """열람용 화면. d: risk/location/category/description/contact_name/contact_phone/action_date
    [조치 전 | 조치 후] 탭으로 사진을 전환한다 (화면 새로고침 없이 바로 전환).
    조치 후 사진이 있으면 조치 예정일 대신 '조치완료'를 표시한다."""
    risk = d.get("risk")
    # 조치 후 사진이 있으면(조치완료) 같은 아이콘을 초록색으로 표시
    risk_color = DONE_COLOR if after_src else utils.RISK_COLOR.get(risk, "#888")
    risk_label = utils.RISK_LABEL_KR.get(risk, risk or "")
    pulse = "pulse" if (risk == "High" and not after_src) else ""
    risk_text = f"조치완료 · 위험도 {risk_label}" if after_src else f"위험도 {risk_label}"

    location = html.escape(d.get("location") or ("(장소명을 입력하세요)" if draft else ""))
    category = html.escape(d.get("category") or "")
    description = html.escape(d.get("description") or "-").replace("\n", "<br>")
    contact_name = html.escape(d.get("contact_name") or "-")
    raw_phone = (d.get("contact_phone") or "").strip()
    if raw_phone:
        tel = re.sub(r"[^0-9+]", "", raw_phone)
        phone_html = f'<a href="tel:{tel}">{html.escape(raw_phone)}</a>'
    else:
        phone_html = "-"

    if after_src:
        date_row = (
            f'<div class="info-row"><span class="info-label">{ICON_CHECK}조치 상태</span>'
            '<span class="info-value"><span class="pill done">✓ 조치완료</span></span></div>'
        )
    else:
        action_date = html.escape(str(d.get("action_date") or "-"))
        dd = _dday(d.get("action_date"))
        dd_html = f' <span class="pill {dd[1]}">{dd[0]}</span>' if dd else ""
        date_row = (
            f'<div class="info-row"><span class="info-label">{ICON_CAL}조치 예정일</span>'
            f'<span class="info-value">{action_date}{dd_html}</span></div>'
        )

    uid = _uid(ctx)
    footer = "읽기 전용 화면입니다" if not draft else "✏️ 저장 전 미리보기입니다"
    render_html(
        f"""
        <div class="hc" style="--rc:{risk_color}; --rt:{risk_color}17;">
        <input type="radio" class="hc-r hc-rb" name="{uid}" id="{uid}_b" aria-label="조치 전 사진 보기">
        <input type="radio" class="hc-r hc-ra" name="{uid}" id="{uid}_a" aria-label="조치 후 사진 보기">
        <div class="hc-head">
        <div class="hc-brand"><b>achamap</b><span>위험요소 안내</span></div>
        <div class="hc-tags">
        <span class="hc-risk"><span class="hc-dot {pulse}"></span>{risk_text}</span>
        <span class="badge badge-category" style="margin:0;">{category}</span>
        </div>
        <h2 class="hc-title">{location}</h2>
        </div>
        <div class="hc-toggle"><span class="hc-thumb"></span>
        <label class="lb" for="{uid}_b">조치 전</label><label class="la" for="{uid}_a">조치 후</label>
        </div>
        <div class="hc-photo">
        {_slide("hc-before", "조치 전", photo_src, "등록된 사진 없음")}
        {_slide("hc-after", "조치 후", after_src, "조치완료 사진 없음")}
        </div>
        <div class="hc-body">
        <div class="desc">{description}</div>
        <div class="info-box">
        <div class="info-row"><span class="info-label">{ICON_USER}담당자</span><span class="info-value">{contact_name}</span></div>
        <div class="info-row"><span class="info-label">{ICON_PHONE}전화번호</span><span class="info-value">{phone_html}</span></div>
        {date_row}
        </div>
        </div>
        </div>
        <p class="hc-foot">{footer}</p>
        """
    )


def render_viewer(hazard_id):
    """QR 스캔으로 들어온 읽기 전용 화면."""
    try:
        hazard = db.get_hazard(int(hazard_id))
    except ValueError:
        hazard = None
    if not hazard:
        st.error("해당 위험요소 정보를 찾을 수 없습니다.")
        return
    hazard_card(hazard, hazard.get("photo_path"), hazard.get("after_photo_path"), ctx=("view", hazard["id"]))


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
                **_site_field(),
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


def cb_select(hid):
    """목록에서 항목을 클릭: 우측 미리보기를 그 항목으로 바꾸고 상세를 펼치거나 접는다."""
    ss = st.session_state
    ss.preview_id = hid
    ss.open_id = None if ss.open_id == hid else hid


def cb_start_edit(hid):
    st.session_state.editing_id = hid
    st.session_state.preview_id = hid
    st.session_state.open_id = hid


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
# 요약 카드
# ---------------------------------------------------------------------------
def render_kpis(hazards):
    total = len(hazards)
    done = sum(1 for h in hazards if h.get("after_photo_path"))
    todo = total - done
    open_items = [h for h in hazards if not h.get("after_photo_path")]
    high = sum(1 for h in open_items if h.get("risk") == "High")
    mid = sum(1 for h in open_items if h.get("risk") == "Medium")
    low = todo - high - mid
    states = [(_dday(h.get("action_date")) or ("", ""))[1] for h in open_items]
    late = states.count("late")
    soon = states.count("soon")
    rate = round(done / total * 100) if total else 0

    def pct(n, base):
        return round(n / base * 100) if base else 0

    # 도넛 1: 조치완료(파랑) / 조치 전(연파랑)
    d1 = f"conic-gradient(var(--blue) 0 calc(var(--p) * {rate}%), var(--blue-2) 0 calc(var(--p) * 100%), #eef0f3 0)"
    # 도넛 2: 미조치 위험도 분포 (위험도 색 유지)
    ph, pm = pct(high, todo), pct(mid, todo)
    d2 = (
        f"conic-gradient(var(--high) 0 calc(var(--p) * {ph}%), var(--mid) 0 calc(var(--p) * {ph + pm}%), "
        f"var(--low) 0 calc(var(--p) * 100%), #eef0f3 0)" if todo else "conic-gradient(#eef0f3 0 100%)"
    )

    def tile(label, n, unit="건", cls="", hint=""):
        return (
            f'<div class="kpi"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-num {cls}" style="--n:{n};" aria-label="{n}{unit}"><small>{unit}</small></div>'
            f'<div class="kpi-hint">{hint}</div></div>'
        )

    render_html(
        f"""
        <div class="kpis">
        <div class="kpi wide"><div class="kpi-label">전체 위험요소</div>
        <div class="kpi-num" style="--n:{total};" aria-label="{total}건"><small>건</small></div>
        <div class="kpi-body"><ul class="legend">
        <li><i style="background:var(--blue)"></i><b>{rate}%</b> 조치완료</li>
        <li><i style="background:var(--blue-2)"></i><b>{100 - rate if total else 0}%</b> 조치 전</li>
        </ul><div class="donut" style="background:{d1};" aria-hidden="true"></div></div></div>
        <div class="kpi wide"><div class="kpi-label">미조치 위험도</div>
        <div class="kpi-num" style="--n:{todo};" aria-label="{todo}건"><small>건</small></div>
        <div class="kpi-body"><ul class="legend">
        <li><i style="background:var(--high)"></i><b>{high}</b> 높음</li>
        <li><i style="background:var(--mid)"></i><b>{mid}</b> 중간</li>
        <li><i style="background:var(--low)"></i><b>{low}</b> 낮음</li>
        </ul><div class="donut" style="background:{d2};" aria-hidden="true"></div></div></div>
        {tile("기한 지남", late, "건", "late" if late else "", "조치 예정일이 지난 미조치 항목")}
        {tile("7일 내 마감", soon, "건", "", "오늘 ~ D-7 미조치 항목")}
        </div>
        """
    )


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
        if rc1.button("↺ 왼쪽으로 회전", key=f"n_rotl_{n}"):
            ss.new_rotation = (ss.new_rotation - 90) % 360
            st.rerun()
        if rc2.button("↻ 오른쪽으로 회전", key=f"n_rotr_{n}"):
            ss.new_rotation = (ss.new_rotation + 90) % 360
            st.rerun()
        if rc3.button("초기화", key=f"n_rot0_{n}"):
            ss.new_rotation = 0
            st.rerun()

    # form이 아니라 일반 위젯이라, 입력하는 즉시 우측 미리보기에 반영된다.
    st.text_input("장소명 / 제목", placeholder="예) 경북지사 상설시험장", key=f"n_loc_{n}")
    st.selectbox("위험 유형", utils.CATEGORIES, key=f"n_cat_{n}")
    st.selectbox("위험도", utils.RISK_LEVELS, key=f"n_risk_{n}")
    st.text_area("상세 설명", key=f"n_desc_{n}")
    c1, c2 = st.columns(2)
    c1.text_input("담당자 이름", key=f"n_cname_{n}")
    c2.text_input("담당자 연락처", placeholder="010-1234-5678", key=f"n_cphone_{n}")
    st.date_input("조치 예정일", value=date.today(), key=f"n_date_{n}")
    st.button("등록", key=f"n_submit_{n}", width="stretch", on_click=cb_create)


def render_edit_form(h, split: bool):
    ss = st.session_state
    hid = h["id"]
    st.text_input("장소명 / 제목", value=h["location"] or "", key=f"e_loc_{hid}")
    st.selectbox(
        "위험 유형", utils.CATEGORIES,
        index=utils.CATEGORIES.index(h["category"]) if h["category"] in utils.CATEGORIES else 0,
        key=f"e_cat_{hid}",
    )
    st.selectbox(
        "위험도", utils.RISK_LEVELS,
        index=utils.RISK_LEVELS.index(h["risk"]) if h["risk"] in utils.RISK_LEVELS else 0,
        key=f"e_risk_{hid}",
    )
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
    st.text_area("상세 설명", value=h.get("description") or "", key=f"e_desc_{hid}")
    st.text_input("담당자 이름", value=h.get("contact_name") or "", key=f"e_cname_{hid}")
    st.text_input("담당자 연락처", value=h.get("contact_phone") or "", key=f"e_cphone_{hid}")
    try:
        default_date = date.fromisoformat(h["action_date"]) if h.get("action_date") else date.today()
    except Exception:  # noqa: BLE001
        default_date = date.today()
    st.date_input("조치 예정일", value=default_date, key=f"e_date_{hid}")

    col_s, col_c = st.columns(2)
    col_s.button("저장", key=f"e_save_{hid}", width="stretch", on_click=cb_save_edit, args=(hid, h.get("photo_path"), h.get("after_photo_path")))
    col_c.button("취소", key=f"e_cancel_{hid}", width="stretch", on_click=cb_cancel_edit)


def _meta_html(h) -> str:
    """목록 행: 제목 아래 '위험유형 · 담당자 · 예정일', 오른쪽 끝에 D-day 또는 완료."""
    parts = [html.escape(h.get("category") or "-")]
    if h.get("contact_name"):
        parts.append(html.escape(h["contact_name"]))
    if h.get("after_photo_path"):
        right = '<span class="hz-right done">완료</span>'
    else:
        parts.append(f'~{html.escape(str(h.get("action_date") or "-"))}')
        dd = _dday(h.get("action_date"))
        right = f'<span class="hz-right {dd[1]}">{dd[0]}</span>' if dd else ""
    sep = '<span class="sep">·</span>'
    return f'<div class="hz-meta">{sep.join(f"<span>{p}</span>" for p in parts)}</div>{right}'


def render_hazard_item(h, split: bool):
    hid = h["id"]
    risk_color = DONE_COLOR if h.get("after_photo_path") else utils.RISK_COLOR.get(h["risk"], "#888")
    risk_label = utils.RISK_LABEL_KR.get(h["risk"], h["risk"])
    ss = st.session_state
    editing = ss.editing_id == hid
    selected = ss.preview_id == hid
    opened = editing or ss.open_id == hid

    # 카드 key에 선택/펼침/위험도 상태를 담아 CSS로 색과 모양을 바꾼다 (기능과 무관한 표시용 이름)
    card_key = f"hzc_{'on' if selected else 'off'}_{'open' if opened else 'shut'}_{_state(h)}_{hid}"
    with st.container(key=card_key):
        st.button(
            f"{h['location'] or '(제목 없음)'}",
            key=f"sel_{hid}", type="tertiary", width="stretch", on_click=cb_select, args=(hid,),
        )
        render_html(_meta_html(h))
        if not opened:
            return
        with st.container():
            render_html(
                f"""
                <div style="margin:10px 0 6px 0.6rem;">
                <span class="badge" style="background:{risk_color}1a; color:{risk_color}; border:1px solid {risk_color}55;">
                ● 위험도 {risk_label}
                </span>
                <span class="badge badge-category">{html.escape(h['category'] or '')}</span>
                </div>
                """
            )
            if editing:
                render_edit_form(h, split)
                return

            for kind, key_name, cap in (
                ("before", "photo_path", "조치 전"),
                ("after", "after_photo_path", "조치 후"),
            ):
                if h.get(key_name):
                    try:
                        st.image(h[key_name], caption=cap, width=250)
                        rc1, rc2 = st.columns(2)
                        if rc1.button("↺ 왼쪽 회전", key=f"rotL_{kind}_{hid}"):
                            _rotate(hid, -90, kind)
                        if rc2.button("↻ 오른쪽 회전", key=f"rotR_{kind}_{hid}"):
                            _rotate(hid, 90, kind)
                    except Exception:  # noqa: BLE001
                        pass

            description = html.escape(h.get("description") or "-").replace("\n", "<br>")
            contact_name = html.escape(h.get("contact_name") or "-")
            contact_phone = html.escape(h.get("contact_phone") or "-")
            if h.get("after_photo_path"):
                date_row = (
                    f'<div class="info-row"><span class="info-label">{ICON_CHECK}조치 상태</span>'
                    '<span class="info-value"><span class="pill done">✓ 조치완료</span></span></div>'
                )
            else:
                action_date = html.escape(h.get("action_date") or "-")
                dd = _dday(h.get("action_date"))
                dd_html = f' <span class="pill {dd[1]}">{dd[0]}</span>' if dd else ""
                date_row = (
                    f'<div class="info-row"><span class="info-label">{ICON_CAL}조치 예정일</span>'
                    f'<span class="info-value">{action_date}{dd_html}</span></div>'
                )
            render_html(
                f"""
                <div class="desc">{description}</div>
                <div class="info-box">
                <div class="info-row"><span class="info-label">{ICON_USER}담당자</span><span class="info-value">{contact_name}</span></div>
                <div class="info-row"><span class="info-label">{ICON_PHONE}전화번호</span><span class="info-value">{contact_phone}</span></div>
                {date_row}
                </div>
                """
            )

            url = utils.build_viewer_url(hid)
            png = qr_png(hid, url)
            render_html("<div style='margin-top:14px;'></div>")
            st.image(png, width=150, caption=url)
            st.download_button(
                "QR 이미지 다운로드", png, file_name=f"qr_{hid}.png", mime="image/png",
                key=f"dl_{hid}", width="stretch",
            )

            col_e, col_d = st.columns(2)
            col_e.button("수정", key=f"editbtn_{hid}", width="stretch", on_click=cb_start_edit, args=(hid,))
            col_d.button("삭제", key=f"delbtn_{hid}", type="primary", width="stretch", on_click=cb_delete, args=(hid,))


def _rotate(hid, degrees, kind="before"):
    """저장된 사진을 회전하고, 새 주소(캐시 방지 값 포함)를 DB에 반영해 바로 보이게 한다."""
    new_url = utils.rotate_saved_photo(hid, degrees, kind)
    if new_url:
        db.update_hazard(hid, {"after_photo_path" if kind == "after" else "photo_path": new_url})
        st.session_state.preview_id = hid
    st.rerun()


def render_admin(hazards, split: bool):
    _show_flash()
    # PC 분할 화면에서는 왼쪽 사이드바 메뉴로, 그 외(휴대폰 등)에서는 본문 상단 탭으로 표시
    where = st.sidebar if split else st
    section = where.radio(
        "구분", [SECTION_LIST, SECTION_NEW], key="section", horizontal=not split, label_visibility="collapsed"
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

    # 아직 아무것도 클릭하지 않았으면 '조치 전' 맨 위 항목을 미리보기 대상으로
    ss = st.session_state
    if ss.preview_id not in {h["id"] for h in hazards}:
        ss.preview_id = (todo or done)[0]["id"]
    tab_todo, tab_done = st.tabs([f"조치 전 {len(todo)}", f"조치완료 {len(done)}"])
    with tab_todo:
        if not todo:
            st.caption("조치 전 항목이 없습니다.")
        with st.container(key="tl_todo"):
            for h in todo:
                render_hazard_item(h, split)
    with tab_done:
        if not done:
            st.caption("조치완료 항목이 없습니다.")
        with st.container(key="tl_done"):
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
        st.caption("✏️ 입력 중인 내용이 실시간으로 반영됩니다 (아직 저장 전)")
        hazard_card(draft, ss.get("_new_preview_uri"), None, draft=True, ctx=("new", ss.nonce))
        return

    eid = ss.editing_id
    # 수정 중인 항목을 보고 있을 때만 '수정 중' 미리보기, 다른 항목을 클릭하면 그 항목을 보여준다.
    if eid in by_id and ss.preview_id in (eid, None):
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
        st.caption(f"✏️ 수정 중인 내용이 실시간으로 반영됩니다 (ID {eid}, 아직 저장 전)")
        after_src = ss.get("_edit_after_uri")
        if not after_src and not ss.get(f"e_delafter_{eid}"):
            after_src = h.get("after_photo_path")
        hazard_card(draft, ss.get("_edit_preview_uri") or h.get("photo_path"), after_src, draft=True, ctx=("edit", eid))
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
    ss.setdefault("open_id", None)
    ss.setdefault("section", SECTION_LIST)

    query_id = st.query_params.get("id")
    if query_id:  # QR 스캔: 읽기 전용 화면만
        inject_css(560)
        render_html('<style>header[data-testid="stHeader"]{display:none;} .block-container{padding-top:1.2rem;}</style>')
        render_viewer(query_id)
        return

    # PC에서는 분할 화면이 기본, 휴대폰에서는 관리자 화면만 기본
    ss.setdefault("split_view", not _is_mobile())
    split = ss.split_view
    inject_css(1500 if split else 760)

    # 콜백(등록/저장/삭제)은 이 스크립트 실행 전에 이미 처리되므로, 여기서 읽은 목록은 항상 최신이다.
    all_hazards = db.get_all_hazards()
    # DB에 site 칸이 있는지 (Supabase에서 칸을 추가하기 전에도 앱이 그대로 동작하도록)
    if all_hazards:
        ss["_site_col"] = "site" in all_hazards[0]
    if ss.get("site") not in SITE_BY_ID:
        ss["site"] = DEFAULT_SITE
    site = SITE_BY_ID[ss.site]
    hazards = [h for h in all_hazards if _site_of(h) == ss.site]

    if split:
        with st.sidebar:
            render_html('<div class="brand">acha<b>map</b></div><div class="brand-sub">위험요소 QR 관리</div>')

    with st.container(key="pagehead"):
        head, toggle = st.columns([5, 2], vertical_alignment="bottom")
        with head:
            render_html(
                f'<div class="page-h"><h1>위험요소 현황</h1>'
                f'<span>{html.escape(site["org"])} {html.escape(site["name"])} · {html.escape(site["sub"])}</span></div>'
            )
        toggle.toggle("화면 분할", key="split_view")

    # 휴대폰(분할 화면 끔)에서는 사이드바가 숨겨지므로, 현장이 2곳 이상일 때만 본문 위에 현장 선택을 보여준다.
    if not split and len(SITES) > 1:
        st.radio("현장", [s["id"] for s in SITES], key="site", format_func=_site_label,
                 horizontal=True, label_visibility="collapsed", on_change=cb_site)

    render_kpis(hazards)

    if not split:
        render_admin(hazards, split=False)
        return

    left, right = st.columns(2, gap="medium")
    with left:
        with st.container(height=PANE_HEIGHT, border=True, key="pane_admin"):
            render_html('<div class="card-h"><b>위험요소 목록</b><span>등록 · 수정 · QR 발급</span></div>')
            render_admin(hazards, split=True)
    with right:
        with st.container(height=PANE_HEIGHT, border=True, key="pane_view"):
            render_html('<div class="card-h"><b>열람용 미리보기</b><span>QR을 스캔하면 보이는 화면</span></div>')
            render_preview(hazards)

    with st.sidebar:
        render_html('<div class="side-label">현장</div>')
        st.radio("현장", [s["id"] for s in SITES], key="site", format_func=lambda i: f"{SITE_BY_ID[i]['name']}  \n:gray[{SITE_BY_ID[i]['sub']}]",
                 label_visibility="collapsed", on_change=cb_site)


main()
