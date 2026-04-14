import base64
import streamlit as st
import streamlit.components.v1 as components
import requests
import time as _time
from PIL import Image
from datetime import datetime

from utils import (
    get_supabase, get_latest_draft,
    show_result_page, build_writing_html,
)

st.set_page_config(page_title="TEN: IELTS Task 1", page_icon="✏️", layout="centered")
st.markdown("""
<style>
  [data-testid="stSidebar"]{display:none;}
  [data-testid="collapsedControl"]{display:none;}
</style>
""", unsafe_allow_html=True)


def writing_component(student_name: str, session_id: str):
    html = build_writing_html(
        student_name=student_name, session_id=session_id,
        sb_url=st.secrets["supabase"]["url"],
        sb_key=st.secrets["supabase"]["key"],
        total_seconds=1200, min_words=150, height=280,
    )
    components.html(html, height=400)


def call_edge(payload: dict) -> dict | None:
    """Edge Function шақырады. Нәтиже dict немесе None."""
    url = st.secrets["supabase"]["url"].rstrip("/") + "/functions/v1/grade"
    key = st.secrets["supabase"]["service_key"]
    try:
        resp = requests.post(
            url, json=payload,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            timeout=120,
        )
        if resp.ok:
            return resp.json()
        st.error(f"Edge Function қатесі ({resp.status_code}): {resp.text}")
    except Exception as e:
        st.error(f"Байланыс қатесі: {e}")
    return None


def fetch_result_from_db(session_id: str) -> dict | None:
    """results кестесінен нәтижені тікелей оқиды."""
    try:
        res = (get_supabase().table("results")
               .select("*").eq("session_id", session_id)
               .order("checked_at", desc=True).limit(1).execute())
        if res.data:
            r = res.data[0]
            return {
                "TA":          r.get("ta", 0),
                "CC":          r.get("cc", 0),
                "LR":          r.get("lr", 0),
                "GRA":         r.get("gra", 0),
                "overall":     r.get("overall", 0),
                "main_errors": r.get("main_errors", []),
                "feedback":    r.get("feedback", ""),
            }
    except Exception:
        pass
    return None


# ──────────────────────────────────────────
st.title("✏️ IELTS Writing Task 1")
st.caption("Тапсырманы орындап, жауабыңызды жіберіңіз.")
st.markdown("---")

st.subheader("1. Аты-жөніңізді жазыңыз")
student_name = st.text_input("", placeholder="Мысалы: Айгерім Сейтқали",
                              label_visibility="collapsed")

st.subheader("2. Тапсырма суретін жүктеңіз")
uploaded_file = st.file_uploader("", type=["png","jpg","jpeg"],
                                  label_visibility="collapsed")
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Тапсырма", width=400)

if student_name.strip() and uploaded_file is not None:
    st.markdown("---")

    skey = f"sid_{student_name.strip().replace(' ','_')}"
    if skey not in st.session_state:
        st.session_state[skey] = datetime.now().strftime("%Y%m%d%H%M%S")
    sid = st.session_state[skey]

    annul_key = f"annulled_{sid}"
    done_key  = f"done_{sid}"
    sub_key   = f"submitting_{sid}"
    st.session_state.setdefault(annul_key, False)
    st.session_state.setdefault(done_key,  False)
    st.session_state.setdefault(sub_key,   False)

    if st.session_state[annul_key]:
        st.error("🚫 Жұмысыңыз аннулирленді. Мұғалімге хабарланды.")
        st.stop()

    if st.session_state[done_key]:
        result = st.session_state.get(f"result_{sid}", {})
        essay  = st.session_state.get(f"essay_{sid}",  "")
        if result:
            show_result_page(result, essay, "Task 1")
        st.stop()

    if st.session_state[sub_key]:
        with st.spinner("⏳ Жұмысыңыз тексерілуде..."):

            # 1. Мәтінді Supabase-тен аламыз (макс 25 сек)
            _time.sleep(3)
            draft = None
            for _ in range(25):
                draft = get_latest_draft(sid)
                if draft and draft.get("draft_text","").strip():
                    break
                _time.sleep(1)

            essay_text = (draft or {}).get("draft_text","").strip()

            if not essay_text:
                st.session_state[sub_key] = False
                st.error(
                    "⚠️ **Мәтін табылмады.**\n\n"
                    "1. Беттi жаңартпаңыз\n"
                    "2. **👁 Айнұр ұстазға көрсету** батырмасын басыңыз\n"
                    "3. ✅ деп шыққан соң — **Тексеруге жіберу** батырмасын қайта басыңыз"
                )
                st.rerun()

            # 2. Суретті base64-ке айналдырамыз
            uploaded_file.seek(0)
            img_bytes  = uploaded_file.read()
            img_b64    = base64.b64encode(img_bytes).decode()
            img_mime   = uploaded_file.type or "image/jpeg"

            # 3. Edge Function-ға жіберемыз
            # Streamlit CPU жұмсамайды — Supabase сервері Gemini шақырады
            data = call_edge({
                "session_id":   sid,
                "student_name": student_name.strip(),
                "essay_text":   essay_text,
                "task_type":    "Task 1",
                "image_base64": img_b64,
                "image_mime":   img_mime,
            })

            result = None
            if data:
                if data.get("status") in ("ok", "already_graded"):
                    result = data.get("result")
                # already_graded жағдайда нәтиже data["result"]-та келеді
                # ok жағдайда да сол

            # 4. Нәтиже Edge-тен келмесе — DB-тен тікелей оқимыз (fallback)
            if not result:
                result = fetch_result_from_db(sid)

            if result and not st.session_state.get(done_key, False):
                result["TA"]      = result.get("TA",      result.get("ta",      0))
                result["CC"]      = result.get("CC",      result.get("cc",      0))
                result["LR"]      = result.get("LR",      result.get("lr",      0))
                result["GRA"]     = result.get("GRA",     result.get("gra",     0))
                result["overall"] = result.get("overall", result.get("Overall", 0))
                st.session_state[f"result_{sid}"] = result
                st.session_state[f"essay_{sid}"]  = essay_text
                st.session_state[done_key] = True
                st.session_state[sub_key]  = False
            else:
                st.session_state[sub_key] = False

            st.rerun()

    else:
        st.subheader("3. Жауабыңызды жазыңыз")
        st.caption("Жазуды бастағанда таймер автоматты қосылады. Уақыт: 20 минут.")
        writing_component(student_name.strip(), sid)
        st.info(
            "💡 Жіберер алдында **👁 Айнұр ұстазға көрсету** батырмасын "
            "бір рет басыңыз — мәтін сенімді сақталады.",
            icon="ℹ️",
        )
        if st.button("✅ Тексеруге жіберу", type="primary",
                     use_container_width=True, key=f"sub_{sid}",
                     disabled=st.session_state.get(sub_key, False)):
            st.session_state[sub_key] = True
            st.rerun()

elif not student_name.strip():
    st.info("Алдымен аты-жөніңізді және тапсырма суретін жүктеңіз.")
