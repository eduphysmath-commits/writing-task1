import streamlit as st
from supabase import create_client, Client
import time

st.set_page_config(page_title="TEN: Мұғалім мониторы", page_icon="🛡", layout="wide")

st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
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
    except Exception as e:
        st.error(f"Қате: {e}")
        return []

def get_results_data():
    try:
        res = get_supabase().table("results")\
            .select("*").order("checked_at", desc=True).limit(200).execute()
        return res.data or []
    except Exception as e:
        st.error(f"Қате: {e}")
        return []

def get_live_drafts():
    try:
        res = get_supabase().table("live_drafts")\
            .select("*").order("updated_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        st.error(f"Қате: {e}")
        return []

# ==========================================
# МҰҒАЛІМ МОНИТОРЫ
# ==========================================
col_title, col_refresh = st.columns([6, 1])
with col_title:
    st.title("🛡 Мұғалім мониторы")
with col_refresh:
    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
    if st.button("🔄 Жаңарту", use_container_width=True):
        st.rerun()

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "👁 Live мониторинг",
    "🔴 Античит оқиғалары",
    "📊 Тексеру нәтижелері",
    "📈 Статистика"
])

# ==========================================
# ТАБ 1: LIVE МОНИТОРИНГ
# ==========================================
with tab1:
    drafts = get_live_drafts()
    st.caption(f"Қазір жазып жатыр: {len(drafts)} оқушы · 5 сек сайын жаңарады")
    st.markdown("---")

    if not drafts:
        st.info("Қазір ешкім жазып жатқан жоқ.")
    else:
        for d in drafts:
            name = d.get("student_name", "—")
            word_count = d.get("word_count", 0)
            draft_text = d.get("draft_text", "")
            updated_at = (d.get("updated_at","") or "")[:19].replace("T"," ")

            # Сөз санына қарай прогресс (250 сөз — IELTS Task 1 минимум)
            progress = min(word_count / 250, 1.0)
            if word_count >= 250:
                badge, p_color = "🟢", "#639922"
            elif word_count >= 150:
                badge, p_color = "🟡", "#EF9F27"
            else:
                badge, p_color = "🔴", "#E24B4A"

            with st.expander(f"{badge} {name} · {word_count} сөз · Жаңартылды: {updated_at}"):
                # Прогресс жолағы
                st.markdown(f"""
                <div style="margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;font-size:12px;color:#888;margin-bottom:4px;">
                        <span>Сөз саны: <b style="color:{p_color}">{word_count}</b></span>
                        <span>Минимум: 250 сөз</span>
                    </div>
                    <div style="background:#f0f0f0;border-radius:6px;height:8px;overflow:hidden;">
                        <div style="width:{int(progress*100)}%;height:100%;background:{p_color};border-radius:6px;transition:width 0.5s;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Мәтін
                if draft_text.strip():
                    st.text_area(
                        "Жазылып жатқан мәтін:",
                        value=draft_text,
                        height=200,
                        disabled=True,
                        key=f"draft_{d.get('session_id','')}"
                    )
                else:
                    st.caption("Әлі мәтін жоқ...")

    # 5 сек сайын авто-жаңарту
    time.sleep(5)
    st.rerun()

# ==========================================
# ТАБ 2: АНТИЧИТ
# ==========================================
with tab2:
    events = get_anticheat_data()
    if not events:
        st.info("Әлі оқиға жоқ.")
    else:
        col_f1, col_f2 = st.columns([2, 2])
        with col_f1:
            names = sorted(set(e.get("student_name","") for e in events))
            selected_name = st.selectbox("Оқушы:", ["Барлығы"] + names)
        with col_f2:
            event_types = sorted(set(e.get("event_type","") for e in events))
            selected_type = st.selectbox("Оқиға:", ["Барлығы"] + event_types)

        filtered = events
        if selected_name != "Барлығы":
            filtered = [e for e in filtered if e.get("student_name") == selected_name]
        if selected_type != "Барлығы":
            filtered = [e for e in filtered if e.get("event_type") == selected_type]

        # autosave оқиғаларын жасыру (тым көп болады)
        filtered = [e for e in filtered if e.get("event_type") != "autosave"]

        st.caption(f"Барлығы: {len(filtered)} оқиға")
        st.markdown("---")

        for ev in filtered:
            name = ev.get("student_name", "—")
            event_type = ev.get("event_type", "—")
            blur = ev.get("blur_count", 0)
            paste = ev.get("paste_count", 0)
            annulled = ev.get("annulled", 0)
            created_at = (ev.get("created_at","") or "")[:16]

            if annulled:
                bg, border, color, icon, label = "#F09595","#E24B4A","#501313","🚫","АННУЛИРЛЕНДІ"
            elif blur >= 2 or paste >= 1:
                bg, border, color, icon, label = "#FAEEDA","#EF9F27","#854F0B","⚠️","КҮДІКТІ"
            elif event_type == "blur_1":
                bg, border, color, icon, label = "#FCEBEB","#E24B4A","#A32D2D","🔴","ЕСКЕРТУ"
            elif event_type == "timer_expired":
                bg, border, color, icon, label = "#E6F1FB","#378ADD","#042C53","⏰","УАҚЫТ БІТТІ"
            elif event_type == "timer_warning":
                bg, border, color, icon, label = "#FAEEDA","#EF9F27","#854F0B","⏱","1 МИН ҚАЛДЫ"
            elif event_type in ("start","timer_start"):
                bg, border, color, icon, label = "#EAF3DE","#639922","#27500A","✅","БАСТАДЫ"
            else:
                bg, border, color, icon, label = "#EAF3DE","#639922","#27500A","✅", event_type

            st.markdown(f"""
            <div style="background:{bg};border-left:4px solid {border};color:{color};
                border-radius:6px;padding:10px 16px;margin-bottom:6px;font-size:13px;">
                <b>{icon} {name}</b> &nbsp;·&nbsp; <b>{label}</b>
                &nbsp;·&nbsp; Blur: <b>{blur}</b>
                &nbsp;·&nbsp; Paste: <b>{paste}</b>
                &nbsp;·&nbsp; <span style="opacity:0.7;font-size:12px">{created_at}</span>
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# ТАБ 3: НӘТИЖЕЛЕР
# ==========================================
with tab3:
    results = get_results_data()
    if not results:
        st.info("Әлі нәтиже жоқ.")
    else:
        names_r = sorted(set(r.get("student_name","") for r in results))
        selected_r = st.selectbox("Оқушы:", ["Барлығы"] + names_r, key="res_filter")
        filtered_r = results if selected_r == "Барлығы" else \
            [r for r in results if r.get("student_name") == selected_r]

        st.caption(f"Барлығы: {len(filtered_r)} нәтиже")
        st.markdown("---")

        for r in filtered_r:
            name = r.get("student_name","—")
            overall = r.get("overall","—")
            ta = r.get("ta","—"); cc = r.get("cc","—")
            lr = r.get("lr","—"); gra = r.get("gra","—")
            checked_at = (r.get("checked_at","") or "")[:16]

            try:
                ov = float(overall)
                badge = "🟢" if ov >= 7.0 else "🟡" if ov >= 6.0 else "🔴"
            except: badge = "⚪"

            with st.expander(f"{badge} {name} · Overall: {overall} · {checked_at}"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("TA", ta); c2.metric("CC", cc)
                c3.metric("LR", lr); c4.metric("GRA", gra)
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
    results_all = get_results_data()
    events_all = get_anticheat_data()

    if not results_all:
        st.info("Статистика үшін деректер жоқ.")
    else:
        total_students = len(set(r.get("student_name","") for r in results_all))
        total_results = len(results_all)
        annulled_count = sum(1 for e in events_all if e.get("annulled", 0))
        avg_overall = round(sum(r.get("overall",0) for r in results_all) / len(results_all), 2)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Оқушылар саны", total_students)
        col2.metric("Тексерулер саны", total_results)
        col3.metric("Орташа балл", avg_overall)
        col4.metric("Аннулирленген", annulled_count)

        st.markdown("---")
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
                "TA": round(sum(vals["ta"])/len(vals["ta"]),1) if vals["ta"] else "—",
                "CC": round(sum(vals["cc"])/len(vals["cc"]),1) if vals["cc"] else "—",
                "LR": round(sum(vals["lr"])/len(vals["lr"]),1) if vals["lr"] else "—",
                "GRA": round(sum(vals["gra"])/len(vals["gra"]),1) if vals["gra"] else "—",
                "Тексеру саны": len(vals["overall"]),
            })

        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
