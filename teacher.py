import streamlit as st
from datetime import datetime
from supabase import create_client, Client
import pandas as pd

st.set_page_config(page_title="TEN: Мұғалім мониторы", page_icon="🛡", layout="wide")

st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
    .block-container { padding-top: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

def get_anticheat_data():
    try:
        res = get_supabase().table("anticheat_events")\
            .select("*").order("created_at", desc=True).limit(200).execute()
        return res.data or []
    except:
        return []

def get_results_data():
    try:
        res = get_supabase().table("results")\
            .select("*").order("checked_at", desc=True).limit(200).execute()
        return res.data or []
    except:
        return []

def get_live_drafts():
    try:
        res = get_supabase().table("live_drafts")            .select("*")            .eq("submitted", 0)            .order("updated_at", desc=True)            .execute()
        return res.data or []
    except:
        return []

# Session state — бет ашылғанда автоматты жүктейміз
if "data_loaded" not in st.session_state:
    st.session_state["data_loaded"] = False

if not st.session_state["data_loaded"]:
    st.session_state["live_drafts_cache"] = get_live_drafts()
    st.session_state["ac_cache"] = get_anticheat_data()
    st.session_state["results_cache"] = get_results_data()
    st.session_state["live_last_updated"] = datetime.now().strftime("%H:%M:%S")
    st.session_state["data_loaded"] = True

for key, val in [
    ("live_drafts_cache", []),
    ("live_last_updated", "—"),
    ("ac_cache", []),
    ("results_cache", []),
]:
    if key not in st.session_state:
        st.session_state[key] = val

# ==========================================
# HEADER
# ==========================================
col_h1, col_h2 = st.columns([6, 1])
with col_h1:
    st.markdown("<h1 style='font-size:22px;font-weight:500;margin:0 0 4px;'>Мұғалім мониторы</h1>",
                unsafe_allow_html=True)
with col_h2:
    if st.button("🔄 Жаңарту", use_container_width=True):
        st.session_state["live_drafts_cache"] = get_live_drafts()
        st.session_state["ac_cache"] = get_anticheat_data()
        st.session_state["results_cache"] = get_results_data()
        st.session_state["live_last_updated"] = datetime.now().strftime("%H:%M:%S")
        st.rerun()

# ==========================================
# МЕТРИКА КАРТОЧКАЛАРЫ
# ==========================================
drafts_all  = st.session_state["live_drafts_cache"]
events_all  = st.session_state["ac_cache"]
results_all = st.session_state["results_cache"]

writing_count  = len(drafts_all)
checked_count  = len(results_all)
suspect_count  = len(set(
    e.get("student_name") for e in events_all
    if e.get("blur_count", 0) >= 2 or e.get("paste_count", 0) >= 1
))
annulled_count = len(set(
    e.get("student_name") for e in events_all
    if e.get("annulled", 0)
))

m1, m2, m3, m4 = st.columns(4)
def metric_card(col, label, value, color=None):
    color_style = f"color:{color};" if color else ""
    col.markdown(f"""
    <div style="background:var(--color-background-secondary);border-radius:8px;
                padding:14px 12px;text-align:center;">
        <p style="margin:0 0 4px;font-size:12px;color:var(--color-text-secondary);">{label}</p>
        <p style="margin:0;font-size:24px;font-weight:500;{color_style}">{value}</p>
    </div>
    """, unsafe_allow_html=True)

metric_card(m1, "Жазып жатыр", writing_count)
metric_card(m2, "Тексерілді", checked_count)
metric_card(m3, "Күдікті", suspect_count, "#A32D2D" if suspect_count else None)
metric_card(m4, "Аннулирленді", annulled_count, "#A32D2D" if annulled_count else None)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ==========================================
# ҚОЙЫНДЫЛАР
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "👁 Live мониторинг",
    "🔴 Античит",
    "📊 Нәтижелер",
    "📈 Статистика"
])

# ==========================================
# ТАБ 1: LIVE
# ==========================================
with tab1:
    col_l1, col_l2 = st.columns([5, 1])
    with col_l1:
        st.caption(f"Соңғы жаңарту: {st.session_state['live_last_updated']} · {len(drafts_all)} оқушы жазып жатыр")
    with col_l2:
        if st.button("🔄", key="live_ref", help="Тек live жаңарту"):
            st.session_state["live_drafts_cache"] = get_live_drafts()
            st.session_state["live_last_updated"] = datetime.now().strftime("%H:%M:%S")
            st.rerun()

    if not drafts_all:
        st.markdown("""
        <div style="text-align:center;padding:2rem;color:var(--color-text-secondary);font-size:14px;">
            Жаңарту батырмасын басыңыз
        </div>
        """, unsafe_allow_html=True)
    else:
        for d in drafts_all:
            name       = d.get("student_name", "—")
            word_count = d.get("word_count", 0)
            draft_text = d.get("draft_text", "")
            updated_at = (d.get("updated_at","") or "")[:19].replace("T"," ")
            progress   = min(word_count / 250, 1.0)

            if word_count >= 250:
                p_color, badge_bg, badge_color = "#639922", "#EAF3DE", "#3B6D11"
            elif word_count >= 150:
                p_color, badge_bg, badge_color = "#EF9F27", "#FAEEDA", "#854F0B"
            else:
                p_color, badge_bg, badge_color = "#E24B4A", "#FCEBEB", "#A32D2D"

            st.markdown(f"""
            <div style="background:var(--color-background-primary);
                        border:0.5px solid var(--color-border-tertiary);
                        border-radius:12px;padding:12px 16px;margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-size:14px;font-weight:500;color:var(--color-text-primary);">{name}</span>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:11px;background:{badge_bg};color:{badge_color};
                                     padding:2px 10px;border-radius:20px;">{word_count} сөз</span>
                        <span style="font-size:11px;color:var(--color-text-secondary);">{updated_at}</span>
                    </div>
                </div>
                <div style="background:var(--color-background-secondary);border-radius:4px;height:5px;overflow:hidden;">
                    <div style="width:{int(progress*100)}%;height:100%;background:{p_color};border-radius:4px;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:11px;
                            color:var(--color-text-secondary);margin-top:4px;">
                    <span style="color:{p_color};font-weight:500;">{int(progress*100)}%</span>
                    <span>Минимум: 150 сөз</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if draft_text.strip():
                with st.expander("Мәтінді көру"):
                    st.text_area("", value=draft_text, height=180, disabled=True,
                                 key=f"dt_{d.get('session_id','')}", label_visibility="collapsed")

# ==========================================
# ТАБ 2: АНТИЧИТ
# ==========================================
with tab2:
    events = st.session_state["ac_cache"]
    clean  = [e for e in events if e.get("event_type") not in ("autosave","start","timer_start")]

    if not clean:
        st.info("Жаңарту батырмасын басыңыз немесе оқиға жоқ.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            names = sorted(set(e.get("student_name","") for e in clean))
            sel_name = st.selectbox("Оқушы:", ["Барлығы"] + names)
        with col_f2:
            etypes = sorted(set(e.get("event_type","") for e in clean))
            sel_type = st.selectbox("Оқиға:", ["Барлығы"] + etypes)

        filtered = clean
        if sel_name != "Барлығы":
            filtered = [e for e in filtered if e.get("student_name") == sel_name]
        if sel_type != "Барлығы":
            filtered = [e for e in filtered if e.get("event_type") == sel_type]

        st.caption(f"Барлығы: {len(filtered)} оқиға")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        for ev in filtered:
            name       = ev.get("student_name", "—")
            event_type = ev.get("event_type", "—")
            blur       = ev.get("blur_count", 0)
            paste      = ev.get("paste_count", 0)
            annulled   = ev.get("annulled", 0)
            created_at = (ev.get("created_at","") or "")[:16]

            if annulled:
                bg, border, color, label = "#F09595","#E24B4A","#501313","АННУЛИРЛЕНДІ"
                badge_bg, badge_color = "#E24B4A", "#FCEBEB"
            elif blur >= 2 or paste >= 1:
                bg, border, color, label = "#FAEEDA","#EF9F27","#854F0B","КҮДІКТІ"
                badge_bg, badge_color = "#EF9F27", "#FAEEDA"
            elif event_type == "blur_1":
                bg, border, color, label = "#FCEBEB","#E24B4A","#A32D2D","ЕСКЕРТУ"
                badge_bg, badge_color = "#E24B4A", "#FCEBEB"
            elif event_type == "timer_expired":
                bg, border, color, label = "#E6F1FB","#378ADD","#042C53","УАҚЫТ БІТТІ"
                badge_bg, badge_color = "#378ADD", "#E6F1FB"
            else:
                bg, border, color, label = "#EAF3DE","#639922","#27500A", event_type
                badge_bg, badge_color = "#639922", "#EAF3DE"

            st.markdown(f"""
            <div style="background:{bg};border-left:4px solid {border};color:{color};
                border-radius:0 8px 8px 0;padding:10px 16px;margin-bottom:6px;
                display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <span style="font-size:13px;font-weight:500;">{name}</span>
                    <span style="font-size:12px;margin-left:8px;">
                        Blur: <b>{blur}</b> · Paste: <b>{paste}</b>
                    </span>
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <span style="font-size:11px;background:{badge_color};color:{badge_bg};
                                 padding:2px 10px;border-radius:20px;font-weight:500;">{label}</span>
                    <span style="font-size:11px;opacity:0.6;">{created_at}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# ТАБ 3: НӘТИЖЕЛЕР
# ==========================================
with tab3:
    results = st.session_state["results_cache"]
    if not results:
        st.info("Жаңарту батырмасын басыңыз немесе нәтиже жоқ.")
    else:
        names_r  = sorted(set(r.get("student_name","") for r in results))
        sel_r    = st.selectbox("Оқушы:", ["Барлығы"] + names_r, key="res_filter")
        filtered_r = results if sel_r == "Барлығы" else \
            [r for r in results if r.get("student_name") == sel_r]

        st.caption(f"Барлығы: {len(filtered_r)} нәтиже")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        for r in filtered_r:
            name       = r.get("student_name","—")
            overall    = r.get("overall","—")
            ta         = r.get("ta","—")
            cc         = r.get("cc","—")
            lr         = r.get("lr","—")
            gra        = r.get("gra","—")
            checked_at = (r.get("checked_at","") or "")[:16]

            try:
                ov = float(overall)
                if ov >= 7.0:   ov_color, ov_bg = "#27500A", "#EAF3DE"
                elif ov >= 6.0: ov_color, ov_bg = "#854F0B", "#FAEEDA"
                else:           ov_color, ov_bg = "#A32D2D", "#FCEBEB"
            except:
                ov_color, ov_bg = "#3C3489", "#EEEDFE"

            with st.expander(f"{name} · Overall: {overall} · {checked_at}"):
                st.markdown(f"""
                <div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-bottom:12px;">
                    <div style="background:{ov_bg};border-radius:8px;padding:12px;text-align:center;">
                        <p style="margin:0 0 2px;font-size:11px;color:{ov_color};">Overall</p>
                        <p style="margin:0;font-size:22px;font-weight:500;color:{ov_color};">{overall}</p>
                    </div>
                    <div style="background:var(--color-background-secondary);border-radius:8px;padding:12px;text-align:center;">
                        <p style="margin:0 0 2px;font-size:11px;color:var(--color-text-secondary);">TA</p>
                        <p style="margin:0;font-size:22px;font-weight:500;color:var(--color-text-primary);">{ta}</p>
                    </div>
                    <div style="background:var(--color-background-secondary);border-radius:8px;padding:12px;text-align:center;">
                        <p style="margin:0 0 2px;font-size:11px;color:var(--color-text-secondary);">CC</p>
                        <p style="margin:0;font-size:22px;font-weight:500;color:var(--color-text-primary);">{cc}</p>
                    </div>
                    <div style="background:var(--color-background-secondary);border-radius:8px;padding:12px;text-align:center;">
                        <p style="margin:0 0 2px;font-size:11px;color:var(--color-text-secondary);">LR</p>
                        <p style="margin:0;font-size:22px;font-weight:500;color:var(--color-text-primary);">{lr}</p>
                    </div>
                    <div style="background:var(--color-background-secondary);border-radius:8px;padding:12px;text-align:center;">
                        <p style="margin:0 0 2px;font-size:11px;color:var(--color-text-secondary);">GRA</p>
                        <p style="margin:0;font-size:22px;font-weight:500;color:var(--color-text-primary);">{gra}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                errors = r.get("main_errors", [])
                if errors:
                    st.markdown("**Қателер:**")
                    for e in (errors if isinstance(errors, list) else []):
                        st.warning(f"• {e}")
                if r.get("feedback"):
                    st.info(r["feedback"])

# ==========================================
# ТАБ 4: СТАТИСТИКА
# ==========================================
with tab4:
    if not results_all:
        st.info("Жаңарту батырмасын басыңыз немесе деректер жоқ.")
    else:
        total_st  = len(set(r.get("student_name","") for r in results_all))
        total_res = len(results_all)
        avg_ov    = round(sum(r.get("overall",0) for r in results_all) / len(results_all), 1)

        st.markdown(f"""
        <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:1.5rem;">
            <div style="background:var(--color-background-secondary);border-radius:8px;padding:14px;text-align:center;">
                <p style="margin:0 0 4px;font-size:12px;color:var(--color-text-secondary);">Оқушылар</p>
                <p style="margin:0;font-size:24px;font-weight:500;color:var(--color-text-primary);">{total_st}</p>
            </div>
            <div style="background:var(--color-background-secondary);border-radius:8px;padding:14px;text-align:center;">
                <p style="margin:0 0 4px;font-size:12px;color:var(--color-text-secondary);">Тексерулер</p>
                <p style="margin:0;font-size:24px;font-weight:500;color:var(--color-text-primary);">{total_res}</p>
            </div>
            <div style="background:var(--color-background-secondary);border-radius:8px;padding:14px;text-align:center;">
                <p style="margin:0 0 4px;font-size:12px;color:var(--color-text-secondary);">Орташа балл</p>
                <p style="margin:0;font-size:24px;font-weight:500;color:var(--color-text-primary);">{avg_ov}</p>
            </div>
            <div style="background:var(--color-background-secondary);border-radius:8px;padding:14px;text-align:center;">
                <p style="margin:0 0 4px;font-size:12px;color:var(--color-text-secondary);">Аннулирленді</p>
                <p style="margin:0;font-size:24px;font-weight:500;color:{'#A32D2D' if annulled_count else 'var(--color-text-primary)'};">{annulled_count}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Оқушы бойынша орташа баллдар")

        student_stats = {}
        for r in results_all:
            n = r.get("student_name","—")
            if n not in student_stats:
                student_stats[n] = {"overall":[], "ta":[], "cc":[], "lr":[], "gra":[]}
            for key in ["overall","ta","cc","lr","gra"]:
                v = r.get(key)
                if v is not None:
                    student_stats[n][key].append(v)

        rows = []
        for name, vals in sorted(student_stats.items()):
            rows.append({
                "Оқушы": name,
                "Overall": round(sum(vals["overall"])/len(vals["overall"]),1) if vals["overall"] else "—",
                "TA":      round(sum(vals["ta"])/len(vals["ta"]),1)      if vals["ta"]      else "—",
                "CC":      round(sum(vals["cc"])/len(vals["cc"]),1)      if vals["cc"]      else "—",
                "LR":      round(sum(vals["lr"])/len(vals["lr"]),1)      if vals["lr"]      else "—",
                "GRA":     round(sum(vals["gra"])/len(vals["gra"]),1)    if vals["gra"]     else "—",
                "Тексеру саны": len(vals["overall"]),
            })

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
