import base64
import html
import io
from datetime import date

import streamlit as st

import db
import utils

st.set_page_config(page_title="위험요소 지도 관리자탭", layout="wide")
db.init_db()

SECTION_LIST = "📋 목록"
SECTION_NEW = "➕ 신규 등록"
PANE_HEIGHT = 820
DONE_COLOR = "#43a047"  # 조치완료 표시 색(초록)


def render_html(markup: str):
    """줄 앞의 공백을 모두 제거해서 마크다운 파서가 코드블록으로 오인하지 않게 한 뒤 렌더링."""
    cleaned = "\n".join(line.strip() for line in markup.strip().splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 공통 스타일
# ---------------------------------------------------------------------------
def inject_css(max_width: int):
    render_html(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Noto Sans KR', -apple-system, 'Malgun Gothic', sans-serif;
        }}
        .block-container {{
            padding-top: 2.2rem;
            padding-bottom: 3rem;
            max-width: {max_width}px;
        }}
        h1, h2, h3 {{ letter-spacing: -0.3px; }}

        /* 버튼 */
        .stButton>button {{
            border-radius: 8px;
            border: 1px solid #e2e5e9;
            padding: 0.45rem 1rem;
            font-weight: 600;
            color: #333;
            background: #fff;
            transition: all 0.15s ease;
        }}
        .stButton>button:hover {{
            border-color: #1a73e8;
            color: #1a73e8;
        }}
        .stButton>button[kind="primary"] {{
            background: #e53935;
            border-color: #e53935;
            color: white;
        }}
        .stButton>button[kind="primary"]:hover {{
            background: #c62828;
            border-color: #c62828;
            color: white;
        }}
        .stDownloadButton>button {{
            border-radius: 8px;
            font-weight: 600;
            border: 1px solid #1a73e8;
            color: #1a73e8;
            background: white;
        }}

        /* 사진 이전/다음 버튼 줄: 휴대폰에서도 한 줄 유지 */
        .st-key-photonav {{
            max-width: 480px;
            margin: 0 auto;
        }}
        .st-key-photonav [data-testid="stHorizontalBlock"] {{
            flex-wrap: nowrap !important;
            gap: 0.5rem;
        }}
        .st-key-photonav [data-testid="stColumn"] {{
            min-width: 0 !important;
        }}
        .st-key-photonav .stButton>button {{
            font-size: 1.1rem;
            padding: 0.3rem 0;
        }}

        /* expander (목록 카드) */
        div[data-testid="stExpander"] {{
            border: 1px solid #ececec;
            border-radius: 14px;
            margin-bottom: 12px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        }}
        div[data-testid="stExpander"] summary {{
            font-weight: 600;
            padding: 0.9rem 1rem;
        }}

        /* 정보 그리드 */
        .info-box {{ margin-top: 10px; }}
        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 9px 2px;
            border-bottom: 1px solid #f2f2f2;
            font-size: 0.92rem;
        }}
        .info-row:last-child {{ border-bottom: none; }}
        .info-label {{ color: #8a8f98; font-weight: 500; }}
        .info-value {{ color: #1a1a1a; font-weight: 600; text-align: right; }}

        .badge {{
            display: inline-block;
            padding: 3px 11px;
            border-radius: 20px;
            font-size: 0.76rem;
            font-weight: 700;
            margin-right: 6px;
        }}
        .badge-category {{
            background: #f0f2f5;
            color: #556;
        }}
        </style>
        """
    )


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
            f'<img src="{html.escape(src, quote=True)}" '
            'style="width:100%; height:100%; object-fit:contain; display:block;">'
        )
    else:
        body = (
            '<div style="height:100%; display:flex; align-items:center; justify-content:center; '
            f'color:#aaa; font-size:0.9rem;">{empty_text}</div>'
        )
    return (
        '<div style="position:relative; height:300px; background:#f5f6f8;">'
        f'{body}'
        '<span style="position:absolute; top:10px; left:10px; background:rgba(0,0,0,0.6); color:#fff; '
        f'padding:3px 10px; border-radius:14px; font-size:0.75rem; font-weight:700;">{label}</span>'
        '</div>'
    )


def _photo_prev():
    st.session_state.photo_idx = 0


def _photo_next():
    st.session_state.photo_idx = 1


def photo_nav(ctx) -> int:
    """◀ ▶ 버튼으로 조치 전(0) / 조치 후(1) 사진을 전환. ctx가 바뀌면(다른 항목) 조치 전으로 돌아간다."""
    ss = st.session_state
    if ss.get("_photo_ctx") != ctx:
        ss["_photo_ctx"] = ctx
        ss["photo_idx"] = 0
    idx = ss.get("photo_idx", 0)
    with st.container(key="photonav"):
        c1, c2, c3 = st.columns([1, 3, 1], vertical_alignment="center")
        c1.button("❮", key="pn_prev", disabled=(idx == 0), on_click=_photo_prev, width="stretch")
        name = "조치 전" if idx == 0 else "조치 후"
        c2.markdown(
            f'<div style="text-align:center; font-weight:700; font-size:0.95rem;">{name} '
            f'<span style="color:#999; font-weight:500;">({idx + 1}/2)</span></div>',
            unsafe_allow_html=True,
        )
        c3.button("❯", key="pn_next", disabled=(idx == 1), on_click=_photo_next, width="stretch")
    return idx


def hazard_card(d: dict, photo_src, after_src=None, draft: bool = False, ctx=None):
    """열람용 화면. d: risk/location/category/description/contact_name/contact_phone/action_date
    사진 영역은 ❮ ❯ 버튼으로 조치 전 ↔ 조치 후 사진을 전환한다.
    조치 후 사진이 있으면 조치 예정일 대신 '조치완료'를 표시한다."""
    risk = d.get("risk")
    # 조치 후 사진이 있으면(조치완료) 같은 아이콘을 초록색으로 표시
    risk_color = DONE_COLOR if after_src else utils.RISK_COLOR.get(risk, "#888")
    risk_label = utils.RISK_LABEL_KR.get(risk, risk or "")

    location = html.escape(d.get("location") or ("(장소명을 입력하세요)" if draft else ""))
    category = html.escape(d.get("category") or "")
    description = html.escape(d.get("description") or "-").replace("\n", "<br>")
    contact_name = html.escape(d.get("contact_name") or "-")
    contact_phone = html.escape(d.get("contact_phone") or "-")

    if after_src:
        date_row = (
            '<div class="info-row"><span class="info-label">조치 상태</span>'
            '<span class="info-value" style="color:#2e7d32;">✅ 조치완료</span></div>'
        )
    else:
        action_date = html.escape(str(d.get("action_date") or "-"))
        date_row = (
            '<div class="info-row"><span class="info-label">조치 예정일</span>'
            f'<span class="info-value">{action_date}</span></div>'
        )

    idx = photo_nav(ctx)
    if idx == 0:
        photo_html = _photo_block("조치 전", photo_src, "등록된 사진 없음")
    else:
        photo_html = _photo_block("조치 후", after_src, "조치완료 사진 없음")

    footer = "읽기 전용 화면입니다" if not draft else "✏️ 저장 전 미리보기입니다"
    render_html(
        f"""
        <div style="max-width:480px; margin:0 auto; background:white; border-radius:18px;
            overflow:hidden; border:1px solid #ececec; box-shadow:0 4px 20px rgba(0,0,0,0.06);">

            {photo_html}

            <div style="padding:20px 22px 22px 22px;">
                <div style="margin-bottom:10px;">
                    <span class="badge" style="background:{risk_color}1a; color:{risk_color}; border:1px solid {risk_color}55;">
                        ● 위험도 {risk_label}
                    </span>
                    <span class="badge badge-category">{category}</span>
                </div>
                <h2 style="margin:0 0 14px 0; font-size:1.35rem; color:#111;">{location}</h2>

                <div style="background:#f8f9fb; border-radius:10px; padding:12px 14px; font-size:0.92rem;
                    color:#333; line-height:1.55; margin-bottom:14px;">
                    {description}
                </div>

                <div class="info-box">
                    <div class="info-row"><span class="info-label">담당자</span><span class="info-value">{contact_name}</span></div>
                    <div class="info-row"><span class="info-label">전화번호</span><span class="info-value">{contact_phone}</span></div>
                    {date_row}
                </div>
            </div>
        </div>
        <p style="text-align:center; color:#aaa; font-size:0.78rem; margin-top:14px;">{footer}</p>
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


def render_hazard_item(h, split: bool):
    hid = h["id"]
    risk_color = DONE_COLOR if h.get("after_photo_path") else utils.RISK_COLOR.get(h["risk"], "#888")
    risk_label = utils.RISK_LABEL_KR.get(h["risk"], h["risk"])
    editing = st.session_state.editing_id == hid

    with st.expander(f"{h['location']}", expanded=editing):
        with st.container(border=True):
            render_html(
                f"""
                <div style="margin:0 0 10px 0;">
                    <span class="badge" style="background:{risk_color}1a; color:{risk_color}; border:1px solid {risk_color}55;">
                        ● {risk_label}
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
                    '<div class="info-row"><span class="info-label">조치 상태</span>'
                    '<span class="info-value" style="color:#2e7d32;">✅ 조치완료</span></div>'
                )
            else:
                action_date = html.escape(h.get("action_date") or "-")
                date_row = (
                    '<div class="info-row"><span class="info-label">조치 예정일</span>'
                    f'<span class="info-value">{action_date}</span></div>'
                )
            render_html(
                f"""
                <div style="background:#f8f9fb; border-radius:10px; padding:12px 14px; font-size:0.9rem;
                    color:#333; line-height:1.55; margin:10px 0;">
                    {description}
                </div>
                <div class="info-box">
                    <div class="info-row"><span class="info-label">담당자</span><span class="info-value">{contact_name}</span></div>
                    <div class="info-row"><span class="info-label">전화번호</span><span class="info-value">{contact_phone}</span></div>
                    {date_row}
                </div>
                """
            )

            qr_path, url = utils.generate_qr(hid)
            render_html("<div style='margin-top:14px;'></div>")
            st.image(qr_path, width=150, caption=url)
            with open(qr_path, "rb") as f:
                st.download_button(
                    "QR 이미지 다운로드", f, file_name=f"qr_{hid}.png", mime="image/png",
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
    section = st.radio(
        "구분", [SECTION_LIST, SECTION_NEW], key="section", horizontal=True, label_visibility="collapsed"
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
    tab_todo, tab_done = st.tabs([f":red[●] 조치 전 ({len(todo)})", f":green[●] 조치완료 ({len(done)})"])
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
        st.caption("✏️ 입력 중인 내용이 실시간으로 반영됩니다 (아직 저장 전)")
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
    st.caption(f"QR로 접속하면 아래 화면이 노출됩니다.")
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
        inject_css(700)
        render_viewer(query_id)
        return

    # PC에서는 분할 화면이 기본, 휴대폰에서는 관리자 화면만 기본
    ss.setdefault("split_view", not _is_mobile())
    split = ss.split_view
    inject_css(1500 if split else 700)

    head, toggle = st.columns([4, 2], vertical_alignment="center")
    with head:
        render_html(
            '<h1 style="font-size:1.6rem; margin-bottom:0;">아차맵 : 위험요소QR 관리</h1>'
            '<p style="color:#888; margin-top:4px; font-size:0.92rem;">한국산업인력공단 경북지사 3층 상설시험장</p>'
        )
    toggle.toggle("화면 분할", key="split_view")

    if not split:
        render_admin(db.get_all_hazards(), split=False)
        return

    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown("#### 🛠️ 관리자")
        with st.container(height=PANE_HEIGHT, border=True):
            # 콜백(저장/삭제)은 이 스크립트 실행 전에 이미 처리되므로, 아래 목록은 항상 최신이다.
            hazards = db.get_all_hazards()
            render_admin(hazards, split=True)
    with right:
        st.markdown("#### 👁️ 열람용")
        with st.container(height=PANE_HEIGHT, border=True):
            render_preview(hazards)


main()
