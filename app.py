import html
import streamlit as st
from datetime import date
import db
import utils

st.set_page_config(page_title="현장 위험요소 관리", page_icon="🦺", layout="centered")
db.init_db()

query_id = st.query_params.get("id")


def render_html(markup: str):
    """줄 앞의 공백을 모두 제거해서 마크다운 파서가 코드블록으로 오인하지 않게 한 뒤 렌더링."""
    cleaned = "\n".join(line.strip() for line in markup.strip().splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)



# ---------------------------------------------------------------------------
# 공통 스타일
# ---------------------------------------------------------------------------
def inject_css():
    render_html(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Noto Sans KR', -apple-system, 'Malgun Gothic', sans-serif;
        }
        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 3rem;
            max-width: 700px;
        }
        h1, h2, h3 { letter-spacing: -0.3px; }

        /* 탭 */
        .stTabs [data-baseweb="tab-list"] { gap: 6px; }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            padding: 10px 18px;
            font-weight: 600;
            color: #666;
        }
        .stTabs [aria-selected="true"] { color: #1a73e8 !important; }

        /* 버튼 */
        .stButton>button {
            border-radius: 8px;
            border: 1px solid #e2e5e9;
            padding: 0.45rem 1rem;
            font-weight: 600;
            color: #333;
            background: #fff;
            transition: all 0.15s ease;
        }
        .stButton>button:hover {
            border-color: #1a73e8;
            color: #1a73e8;
        }
        .stButton>button[kind="primary"] {
            background: #e53935;
            border-color: #e53935;
            color: white;
        }
        .stButton>button[kind="primary"]:hover {
            background: #c62828;
            border-color: #c62828;
            color: white;
        }
        .stDownloadButton>button {
            border-radius: 8px;
            font-weight: 600;
            border: 1px solid #1a73e8;
            color: #1a73e8;
            background: white;
        }

        /* 폼 컨테이너 */
        div[data-testid="stForm"] {
            border: 1px solid #ececec;
            border-radius: 14px;
            padding: 1.6rem 1.6rem 1.2rem 1.6rem;
            background: #fbfbfc;
        }

        /* expander (목록 카드) */
        div[data-testid="stExpander"] {
            border: 1px solid #ececec;
            border-radius: 14px;
            margin-bottom: 12px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        }
        div[data-testid="stExpander"] summary {
            font-weight: 600;
            padding: 0.9rem 1rem;
        }

        /* 정보 그리드 */
        .info-box { margin-top: 10px; }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 9px 2px;
            border-bottom: 1px solid #f2f2f2;
            font-size: 0.92rem;
        }
        .info-row:last-child { border-bottom: none; }
        .info-label { color: #8a8f98; font-weight: 500; }
        .info-value { color: #1a1a1a; font-weight: 600; text-align: right; }

        .badge {
            display: inline-block;
            padding: 3px 11px;
            border-radius: 20px;
            font-size: 0.76rem;
            font-weight: 700;
            margin-right: 6px;
        }
        .badge-category {
            background: #f0f2f5;
            color: #556;
        }
        </style>
        """
    )


# ---------------------------------------------------------------------------
# 뷰어 모드 (QR 스캔 -> 읽기 전용)
# ---------------------------------------------------------------------------
def render_viewer(hazard_id):
    hazard = db.get_hazard(int(hazard_id))
    if not hazard:
        st.error("해당 위험요소 정보를 찾을 수 없습니다.")
        return

    risk = hazard["risk"]
    risk_color = utils.RISK_COLOR.get(risk, "#888")
    risk_label = utils.RISK_LABEL_KR.get(risk, risk)

    location = html.escape(hazard["location"] or "")
    category = html.escape(hazard["category"] or "")
    description = html.escape(hazard.get("description") or "-").replace("\n", "<br>")
    contact_name = html.escape(hazard.get("contact_name") or "-")
    contact_phone = html.escape(hazard.get("contact_phone") or "-")
    action_date = html.escape(hazard.get("action_date") or "-")

    photo_uri = utils.image_to_data_uri(hazard.get("photo_path"))
    photo_html = (
        f'<img src="{photo_uri}" style="width:100%; display:block;">'
        if photo_uri
        else (
            '<div style="height:160px; display:flex; align-items:center; justify-content:center; '
            'background:#f5f6f8; color:#aaa; font-size:0.85rem;">등록된 사진 없음</div>'
        )
    )

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
                    <div class="info-row"><span class="info-label">조치 예정일</span><span class="info-value">{action_date}</span></div>
                </div>
            </div>
        </div>
        <p style="text-align:center; color:#aaa; font-size:0.78rem; margin-top:14px;">읽기 전용 화면입니다</p>
        """
    )


# ---------------------------------------------------------------------------
# 관리자 모드 (CRUD)
# ---------------------------------------------------------------------------
def render_admin():
    render_html(
        '<h1 style="font-size:1.6rem; margin-bottom:0;">🦺 현장 위험요소 관리</h1>'
        '<p style="color:#888; margin-top:4px; font-size:0.92rem;">등록 · QR 발급 · 수정 · 삭제</p>'
    )

    tab_list, tab_new = st.tabs(["📋 목록", "➕ 신규 등록"])

    with tab_new:
        if "new_photo_rotation" not in st.session_state:
            st.session_state.new_photo_rotation = 0
        if "new_photo_uploader_key" not in st.session_state:
            st.session_state.new_photo_uploader_key = 0

        photo = st.file_uploader(
            "현장 사진",
            type=["png", "jpg", "jpeg"],
            key=f"new_photo_{st.session_state.new_photo_uploader_key}",
        )

        if photo is not None:
            preview_img = utils.get_preview_image(photo, st.session_state.new_photo_rotation)
            st.image(preview_img, caption="미리보기 (등록될 모습)", width=300)
            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                if st.button("↺ 왼쪽으로 회전"):
                    st.session_state.new_photo_rotation = (st.session_state.new_photo_rotation - 90) % 360
                    st.rerun()
            with rc2:
                if st.button("↻ 오른쪽으로 회전"):
                    st.session_state.new_photo_rotation = (st.session_state.new_photo_rotation + 90) % 360
                    st.rerun()
            with rc3:
                if st.button("초기화"):
                    st.session_state.new_photo_rotation = 0
                    st.rerun()

        with st.form("create_form", clear_on_submit=True):
            location = st.text_input("장소명 / 제목", placeholder="예) 경북지사 상설시험장")
            category = st.selectbox("위험 유형", utils.CATEGORIES)
            risk = st.selectbox("위험도", utils.RISK_LEVELS)
            description = st.text_area("상세 설명")
            col1, col2 = st.columns(2)
            with col1:
                contact_name = st.text_input("담당자 이름")
            with col2:
                contact_phone = st.text_input("담당자 연락처", placeholder="010-1234-5678")
            action_date = st.date_input("조치 예정일", value=date.today())

            submitted = st.form_submit_button("등록", use_container_width=True)
            if submitted:
                if not location:
                    st.warning("장소명을 입력해주세요.")
                else:
                    new_id = db.create_hazard(
                        {
                            "location": location,
                            "category": category,
                            "risk": risk,
                            "photo_path": None,
                            "description": description,
                            "contact_name": contact_name,
                            "contact_phone": contact_phone,
                            "action_date": str(action_date),
                        }
                    )
                    photo_path = utils.save_photo(photo, new_id, st.session_state.new_photo_rotation)
                    if photo_path:
                        db.update_hazard(new_id, {**db.get_hazard(new_id), "photo_path": photo_path})
                    utils.generate_qr(new_id)
                    st.session_state.new_photo_rotation = 0
                    st.session_state.new_photo_uploader_key += 1
                    st.success(f"등록 완료 (ID {new_id}). '목록' 탭에서 QR코드를 다운로드하세요.")
                    st.rerun()

    with tab_list:
        hazards = db.get_all_hazards()
        if not hazards:
            st.info("등록된 위험요소가 없습니다. '신규 등록' 탭에서 추가하세요.")
        for h in hazards:
            risk_color = utils.RISK_COLOR.get(h["risk"], "#888")
            risk_label = utils.RISK_LABEL_KR.get(h["risk"], h["risk"])
            header = f"[{h['id']}] {h['location']}  ·  {h['category']}  ·  {risk_label}"
            with st.expander(header):
                edit_key = f"edit_mode_{h['id']}"
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = False

                if not st.session_state[edit_key]:
                    if h.get("photo_path"):
                        try:
                            st.image(h["photo_path"], width=250)
                            rc1, rc2 = st.columns(2)
                            with rc1:
                                if st.button("↺ 사진 왼쪽 회전", key=f"rotL_{h['id']}"):
                                    utils.rotate_saved_photo(h["photo_path"], -90)
                                    st.rerun()
                            with rc2:
                                if st.button("↻ 사진 오른쪽 회전", key=f"rotR_{h['id']}"):
                                    utils.rotate_saved_photo(h["photo_path"], 90)
                                    st.rerun()
                        except Exception:
                            pass

                    description = html.escape(h.get("description") or "-").replace("\n", "<br>")
                    contact_name = html.escape(h.get("contact_name") or "-")
                    contact_phone = html.escape(h.get("contact_phone") or "-")
                    action_date = html.escape(h.get("action_date") or "-")

                    render_html(
                        f"""
                        <div style="background:#f8f9fb; border-radius:10px; padding:12px 14px; font-size:0.9rem;
                            color:#333; line-height:1.55; margin:10px 0;">
                            {description}
                        </div>
                        <div class="info-box">
                            <div class="info-row"><span class="info-label">담당자</span><span class="info-value">{contact_name}</span></div>
                            <div class="info-row"><span class="info-label">전화번호</span><span class="info-value">{contact_phone}</span></div>
                            <div class="info-row"><span class="info-label">조치 예정일</span><span class="info-value">{action_date}</span></div>
                        </div>
                        """
                    )

                    qr_path, url = utils.generate_qr(h["id"])
                    render_html("<div style='margin-top:14px;'></div>")
                    st.image(qr_path, width=150, caption=url)
                    with open(qr_path, "rb") as f:
                        st.download_button(
                            "QR 이미지 다운로드",
                            f,
                            file_name=f"qr_{h['id']}.png",
                            mime="image/png",
                            key=f"dl_{h['id']}",
                            use_container_width=True,
                        )

                    col_e, col_d = st.columns(2)
                    with col_e:
                        if st.button("수정", key=f"editbtn_{h['id']}", use_container_width=True):
                            st.session_state[edit_key] = True
                            st.rerun()
                    with col_d:
                        if st.button("삭제", key=f"delbtn_{h['id']}", type="primary", use_container_width=True):
                            db.delete_hazard(h["id"])
                            st.success("삭제되었습니다.")
                            st.rerun()
                else:
                    with st.form(f"edit_form_{h['id']}"):
                        location = st.text_input("장소명 / 제목", value=h["location"])
                        category = st.selectbox(
                            "위험 유형", utils.CATEGORIES,
                            index=utils.CATEGORIES.index(h["category"]) if h["category"] in utils.CATEGORIES else 0,
                        )
                        risk = st.selectbox(
                            "위험도", utils.RISK_LEVELS,
                            index=utils.RISK_LEVELS.index(h["risk"]) if h["risk"] in utils.RISK_LEVELS else 0,
                        )
                        photo = st.file_uploader("현장 사진 교체 (선택)", type=["png", "jpg", "jpeg"], key=f"photo_{h['id']}")
                        description = st.text_area("상세 설명", value=h.get("description") or "")
                        contact_name = st.text_input("담당자 이름", value=h.get("contact_name") or "")
                        contact_phone = st.text_input("담당자 연락처", value=h.get("contact_phone") or "")
                        try:
                            default_date = date.fromisoformat(h["action_date"]) if h.get("action_date") else date.today()
                        except Exception:
                            default_date = date.today()
                        action_date = st.date_input("조치 예정일", value=default_date)

                        col_s, col_c = st.columns(2)
                        with col_s:
                            save = st.form_submit_button("저장", use_container_width=True)
                        with col_c:
                            cancel = st.form_submit_button("취소", use_container_width=True)

                        if save:
                            photo_path = utils.save_photo(photo, h["id"]) or h.get("photo_path")
                            db.update_hazard(
                                h["id"],
                                {
                                    "location": location,
                                    "category": category,
                                    "risk": risk,
                                    "photo_path": photo_path,
                                    "description": description,
                                    "contact_name": contact_name,
                                    "contact_phone": contact_phone,
                                    "action_date": str(action_date),
                                },
                            )
                            st.session_state[edit_key] = False
                            st.success("수정되었습니다.")
                            st.rerun()
                        if cancel:
                            st.session_state[edit_key] = False
                            st.rerun()


# ---------------------------------------------------------------------------
inject_css()

if query_id:
    render_viewer(query_id)
else:
    render_admin()
