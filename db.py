import os
from supabase import create_client

TABLE = "hazards"


def _get_secret(name):
    val = os.environ.get(name)
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def get_client():
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_KEY가 설정되어 있지 않습니다. "
            "Streamlit Secrets에 등록해주세요."
        )
    return create_client(url, key)


def init_db():
    # Supabase는 테이블을 SQL Editor에서 미리 만들어두는 구조라 별도 초기화 불필요.
    pass


def create_hazard(data: dict) -> int:
    client = get_client()
    res = client.table(TABLE).insert(data).execute()
    return res.data[0]["id"]


def update_hazard(hazard_id: int, data: dict):
    client = get_client()
    client.table(TABLE).update(data).eq("id", hazard_id).execute()


def delete_hazard(hazard_id: int):
    client = get_client()
    client.table(TABLE).delete().eq("id", hazard_id).execute()


def get_hazard(hazard_id: int):
    client = get_client()
    res = client.table(TABLE).select("*").eq("id", hazard_id).execute()
    return res.data[0] if res.data else None


def get_all_hazards():
    client = get_client()
    res = client.table(TABLE).select("*").order("id", desc=True).execute()
    return res.data
