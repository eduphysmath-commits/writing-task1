import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import json
from PIL import Image
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(page_title="TEN: IELTS Task 1", page_icon="✏️", layout="centered")

st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

def save_result(student_name: str, result: dict):
    try:
        get_supabase().table("results").insert({
            "student_name": student_name,
            "overall": result["overall"],
            "ta": result["TA"], "cc": result["CC"],
            "lr": result["LR"], "gra": result["GRA"],
            "main_errors": result["main_errors"],
            "feedback": result["feedback"],
        }).execute()
    except Exception as e:
        st.warning(f"Сақтауда қате: {e}")

def save_anticheat(student_name, session_id, event_type, blur_count, paste_count, annulled):
    try:
        get_supabase().table("anticheat_events").insert({
            "student_name": student_name, "session_id": session_id,
            "event_type": event_type, "blur_count": blur_count,
            "paste_count": paste_count, "annulled": annulled,
        }).execute()
    except:
        pass

def delete_live_draft(session_id: str):
    try:
        get_supabase().table("live_drafts")\
            .delete().eq("session_id", session_id).execute()
    except:
        pass

def writing_component(student_name: str, session_id: str):
    """
    Textarea + Античит + Таймер + Live autosave — бәрі бір JS компонентінде.
    Streamlit-ке мәтінді submit батырмасы басылғанда ғана жібереді.
    """
    sb_url = st.secrets["supabase"]["url"]
    sb_key = st.secrets["supabase"]["key"]

    html = f"""
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }}

        #timer-box {{
            position: fixed; top: 16px; right: 16px; z-index: 9999;
            background: #EAF3DE; border: 1.5px solid #639922;
            border-radius: 12px; padding: 10px 18px;
            text-align: center; min-width: 100px;
            transition: background 0.5s, border-color 0.5s;
        }}
        #timer-label {{ font-size: 11px; color: #3B6D11; text-transform: uppercase; margin-bottom: 2px; }}
        #timer-display {{ font-size: 26px; font-weight: 600; color: #27500A; letter-spacing: 1px; }}
        #timer-box.yellow {{ background: #FAEEDA; border-color: #EF9F27; }}
        #timer-box.yellow #timer-label {{ color: #854F0B; }}
        #timer-box.yellow #timer-display {{ color: #633806; }}
        #timer-box.red {{ background: #FCEBEB; border-color: #E24B4A; }}
        #timer-box.red #timer-label {{ color: #A32D2D; }}
        #timer-box.red #timer-display {{ color: #501313; }}
        #timer-box.done {{ background: #F09595; border-color: #E24B4A; animation: pulse 1s ease-in-out infinite; }}
        @keyframes pulse {{ 0%,100% {{ transform: scale(1); }} 50% {{ transform: scale(1.04); }} }}

        #ac-bar {{
            padding: 10px 16px; border-radius: 8px; margin-bottom: 10px;
            background: #EAF3DE; border-left: 4px solid #639922;
            font-size: 13px; color: #3B6D11;
            display: flex; align-items: center; gap: 8px; transition: all 0.3s;
        }}
        .ac-dot {{ width: 10px; height: 10px; border-radius: 50%; background: #639922; flex-shrink: 0; }}

        #essay-box {{
            width: 100%; height: 300px;
            border: 1px solid #ddd; border-radius: 8px;
            padding: 12px; font-size: 15px; line-height: 1.6;
            resize: vertical; outline: none;
            transition: border-color 0.3s;
            font-family: sans-serif;
            color: #333;
        }}
        #essay-box:focus {{ border-color: #639922; }}
        #essay-box:disabled {{ background: #f5f5f5; color: #888; cursor: not-allowed; }}

        #word-bar {{
            display: flex; justify-content: space-between;
            font-size: 12px; color: #888; margin-top: 6px; margin-bottom: 10px;
        }}
        #word-count {{ font-weight: 500; }}

        #submit-btn {{
            width: 100%; padding: 12px;
            background: #1E88E5; color: white;
            border: none; border-radius: 8px;
            font-size: 15px; font-weight: 500;
            cursor: pointer; transition: background 0.2s;
        }}
        #submit-btn:hover {{ background: #1565C0; }}
        #submit-btn:disabled {{ background: #aaa; cursor: not-allowed; }}
        #submit-btn.expired {{ animation: btnPulse 1s ease-in-out infinite; background: #E24B4A; }}
        @keyframes btnPulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.75; }} }}

        #save-status {{ font-size: 11px; color: #aaa; text-align: right; margin-top: 4px; }}
    </style>

    <!-- Таймер (оң жақ бұрышта) -->
    <div id="timer-box">
        <div id="timer-label">Уақыт</div>
        <div id="timer-display">20:00</div>
    </div>

    <!-- Античит статус -->
    <div id="ac-bar">
        <div class="ac-dot" id="ac-dot"></div>
        <span id="ac-text">Античит белсенді — жұмысты адал орындаңыз</span>
    </div>

    <!-- Автосақтау статусы -->
    <div id="save-status" style="font-size:11px;color:#aaa;text-align:right;margin-top:4px;">Сақталмаған</div>

    <script>
    (function() {{
        const STUDENT = "{student_name}";
        const SESSION = "{session_id}";
        const SB_URL  = "{sb_url}";
        const SB_KEY  = "{sb_key}";
        const TOTAL   = 1200;

        let blur = 0, paste = 0, annulled = false;
        let started = false, left = TOTAL, timerInterval = null, expired = false;
        let draftInserted = false;

        const tBox  = document.getElementById('timer-box');
        const tDisp = document.getElementById('timer-display');
        const dot   = document.getElementById('ac-dot');
        const txt   = document.getElementById('ac-text');
        const bar   = document.getElementById('ac-bar');
        // essay — Streamlit textarea-сы

        const saveStatus = document.getElementById('save-status');


        // ---- Дыбыс ----
        function beep(f=880, d=0.4, t='square') {{
            try {{
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator(), gain = ctx.createGain();
                osc.connect(gain); gain.connect(ctx.destination);
                osc.type = t; osc.frequency.value = f;
                gain.gain.setValueAtTime(0.3, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + d);
                osc.start(ctx.currentTime); osc.stop(ctx.currentTime + d);
            }} catch(e) {{}}
        }}
        function alarm() {{
            beep(440, 0.3, 'sawtooth');
            setTimeout(() => beep(440, 0.3, 'sawtooth'), 400);
            setTimeout(() => beep(440, 0.3, 'sawtooth'), 800);
        }}

        // ---- Античит оқиғаларын тікелей Supabase-ке жіберу ----
        const SKIP_EVENTS = new Set(['start', 'timer_start', 'timer_warning', 'timer_expired']);
        async function send(ev) {{
            if (SKIP_EVENTS.has(ev)) return;
            try {{
                await fetch(SB_URL + '/rest/v1/anticheat_events', {{
                    method: 'POST',
                    headers: {{
                        'apikey': SB_KEY,
                        'Authorization': 'Bearer ' + SB_KEY,
                        'Content-Type': 'application/json',
                        'Prefer': 'return=minimal'
                    }},
                    body: JSON.stringify({{
                        student_name: STUDENT,
                        session_id: SESSION,
                        event_type: ev,
                        blur_count: blur,
                        paste_count: paste,
                        annulled: (annulled || ev === 'annulled') ? 1 : 0
                    }})
                }});
            }} catch(e) {{}}
        }}

        // ---- Статус жолағы ----
        function setStatus(msg, bg, bc, c, dc) {{
            bar.style.background = bg; bar.style.borderColor = bc;
            bar.style.color = c; dot.style.background = dc;
            txt.textContent = msg;
        }}

        // ---- Аннулирлеу ----
        function doAnnul() {{
            annulled = true;
            if (timerInterval) clearInterval(timerInterval);
            beep(300, 1.5, 'sawtooth');
            setStatus('ЖҰМЫС АННУЛИРЛЕНДІ — мұғалімге хабарланды', '#F09595', '#E24B4A', '#501313', '#E24B4A');
            tBox.className = 'done'; tDisp.textContent = 'XXX';
            send('annulled');
        }}

        // ---- Таймер ----
        function fmt(s) {{
            return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
        }}

        function startTimer() {{
            if (started) return;
            started = true;
            send('timer_start');
            timerInterval = setInterval(() => {{
                if (annulled) {{ clearInterval(timerInterval); return; }}
                left--;
                tDisp.textContent = fmt(left);
                tBox.className = left <= 0 ? 'done' : left <= 60 ? 'red' : left <= 300 ? 'yellow' : '';
                if (left === 60) {{
                    beep(660, 0.5);
                    setStatus('1 минут қалды! Жұмысыңызды жіберуге дайындалыңыз.', '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
                    send('timer_warning');
                }}
                if (left <= 0) {{
                    clearInterval(timerInterval);
                    expired = true;
                    tDisp.textContent = '00:00';
                    alarm();
                    setStatus('Уақыт бітті! Жұмысыңызды жіберіңіз.', '#FCEBEB', '#E24B4A', '#A32D2D', '#E24B4A');

                    send('timer_expired');
                }}
            }}, 1000);
        }}

        // ---- Беттен шығу ----
        function onBlur() {{
            if (annulled || expired) return;
            blur++;
            if (blur === 1) {{
                beep(660, 0.5);
                setStatus('Ескерту! Басқа бетке өтпеңіз! (1/3)', '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
                send('blur_1');
            }} else if (blur === 2) {{
                beep(440, 0.7);
                setStatus('ҚАТАҢ ЕСКЕРТУ! Тағы бір рет шықсаңыз аннулирленеді! (2/3)', '#FCEBEB', '#E24B4A', '#A32D2D', '#E24B4A');
                send('blur_2');
            }} else {{
                doAnnul();
            }}
        }}

        // ---- Supabase-ке тікелей сақтау ----
        async function saveDraft() {{
            if (annulled) return;
            // Streamlit textarea мәнін sessionStorage арқылы аламыз
            const ta = window.parent.document.querySelector('[data-testid="stTextArea"] textarea');
            const text = ta ? ta.value : '';
            const wordCount = text.trim() ? text.trim().split(/[ \t\r\n]+/).length : 0;
            const now = new Date().toISOString();
            try {{
                if (!draftInserted) {{
                    const res = await fetch(SB_URL + '/rest/v1/live_drafts', {{
                        method: 'POST',
                        headers: {{
                            'apikey': SB_KEY,
                            'Authorization': 'Bearer ' + SB_KEY,
                            'Content-Type': 'application/json',
                            'Prefer': 'return=minimal'
                        }},
                        body: JSON.stringify({{
                            student_name: STUDENT, session_id: SESSION,
                            draft_text: text, word_count: wordCount
                        }})
                    }});
                    if (res.ok || res.status === 201) {{
                        draftInserted = true;
                        saveStatus.textContent = 'Сақталды: ' + new Date().toLocaleTimeString();
                    }}
                }} else {{
                    await fetch(SB_URL + '/rest/v1/live_drafts?session_id=eq.' + SESSION, {{
                        method: 'PATCH',
                        headers: {{
                            'apikey': SB_KEY,
                            'Authorization': 'Bearer ' + SB_KEY,
                            'Content-Type': 'application/json',
                            'Prefer': 'return=minimal'
                        }},
                        body: JSON.stringify({{
                            draft_text: text, word_count: wordCount, updated_at: now
                        }})
                    }});
                    saveStatus.textContent = 'Сақталды: ' + new Date().toLocaleTimeString();
                }}
            }} catch(e) {{
                saveStatus.textContent = 'Сақтауда қате';
            }}
        }}

        // ---- Жіберу — sessionStorage арқылы ----
        function submitEssay() {{
            const text = essay.value.trim();
            if (!text) {{ alert('Жауап мәтінін жазыңыз!'); return; }}
            // Мәтінді sessionStorage-ке сақтап, Streamlit-ке хабар береміз
            window.parent.sessionStorage.setItem('essay_' + SESSION, text);
            window.parent.postMessage({{
                type: 'streamlit:setComponentValue',
                value: {{ student: STUDENT, session: SESSION,
                          event_type: 'submit',
                          blur_count: blur, paste_count: paste,
                          annulled: 0, timer_expired: expired ? 1 : 0,
                          essay_text: text }}
            }}, '*');
            btn.disabled = true;
            btn.textContent = 'Жіберілуде...';
        }}

        // ---- Streamlit textarea оқиғалары ----
        function watchTextarea() {{
            const ta = window.parent.document.querySelector('[data-testid="stTextArea"] textarea');
            if (!ta) {{ setTimeout(watchTextarea, 500); return; }}
            ta.addEventListener('input', () => {{
                if (!started && !annulled) startTimer();
            }});
            ta.addEventListener('paste', () => {{
                if (annulled) return;
                paste++;
                beep(550, 0.3);
                setStatus('Ескерту! Мәтін қою анықталды!', '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
                send('paste');
            }});
        }}
        watchTextarea();

        // ---- Blur/visibility ----
        document.addEventListener('visibilitychange', () => {{ if (document.hidden) onBlur(); }});
        window.addEventListener('blur', onBlur);

        // ---- 5 сек автосақтау ----
        setInterval(saveDraft, 5000);

        send('start');
    }})();
    </script>
    """
    components.html(html, height=420)

# ==========================================
# ОҚУШЫ БЕТІ
# ==========================================
st.title("✏️ IELTS Writing Task 1")
st.caption("Тапсырманы орындап, жауабыңызды жіберіңіз.")
st.markdown("---")

st.subheader("1. Аты-жөніңізді жазыңыз")
student_name = st.text_input("", placeholder="Мысалы: Айгерім Сейтқали", label_visibility="collapsed")

st.subheader("2. Тапсырма суретін жүктеңіз")
uploaded_file = st.file_uploader("", type=["png", "jpg", "jpeg"], label_visibility="collapsed")
image = None
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Тапсырма", width=400)

anticheat_active = False
session_id = ""

if student_name.strip() and uploaded_file is not None:
    st.markdown("---")
    st.subheader("3. Жауабыңызды жазыңыз")
    st.caption("Жазуды бастағанда таймер автоматты қосылады. Уақыт: 20 минут.")

    session_key = f"sid_{student_name.strip().replace(' ','_')}"
    if session_key not in st.session_state:
        st.session_state[session_key] = datetime.now().strftime("%Y%m%d%H%M%S")
    session_id = st.session_state[session_key]

    annul_key   = f"annulled_{session_id}"
    submit_key  = f"submitted_{session_id}"
    essay_key   = f"essay_{session_id}"

    if annul_key  not in st.session_state: st.session_state[annul_key]  = False
    if submit_key not in st.session_state: st.session_state[submit_key] = False
    if essay_key  not in st.session_state: st.session_state[essay_key]  = ""

    # Аннулирленген болса тоқта
    if st.session_state.get(annul_key, False):
        st.error("🚫 Жұмысыңыз аннулирленді. Мұғалімге хабарланды.")
        st.stop()

    # Жіберілген болса нәтижені көрсет
    if st.session_state.get(submit_key, False):
        essay_text = st.session_state.get(essay_key, "")
        if essay_text:
            try:
                genai.configure(api_key=st.secrets["gemini"]["api_key"])
                model = genai.GenerativeModel('gemini-2.5-flash',
                    generation_config={"response_mime_type": "application/json"})
                prompt = """Act as an expert IELTS examiner. Look at the provided image and read the student's Task 1 report.
Evaluate based on official 9-band IELTS descriptors. Scores in 0.5 increments.
Criteria: TA, CC, LR, GRA. Calculate Overall as exact average.
Write 'main_errors' and 'feedback' IN KAZAKH LANGUAGE. Friendly, encouraging tone.
Return ONLY valid JSON:
{"overall":6.5,"TA":6.0,"CC":6.5,"LR":7.0,"GRA":6.5,
"main_errors":["Қате 1...","Қате 2..."],
"feedback":"Қазақ тіліндегі пікір..."}"""
                with st.spinner("Жұмысыңыз тексерілуде..."):
                    result = json.loads(model.generate_content([prompt, image, essay_text]).text)
                    save_result(student_name.strip(), result)
                    delete_live_draft(session_id)

                st.markdown("---")
                st.success("✅ Жұмысыңыз сәтті тексерілді!")
                st.markdown(
                    f"<h2 style='text-align:center;color:#1E88E5;'>🏆 Overall Band: {result['overall']}</h2>",
                    unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Task Achievement", result["TA"])
                c2.metric("Coherence", result["CC"])
                c3.metric("Lexical", result["LR"])
                c4.metric("Grammar", result["GRA"])
                st.markdown("---")
                st.subheader("🛠 Жіберілген қателер")
                for e in result["main_errors"]: st.warning(f"• {e}")
                st.subheader("📝 Пікір")
                st.info(result["feedback"])
            except Exception as e:
                st.error(f"Қате шықты: {e}")
        st.stop()

    # JS компоненті — textarea + античит + таймер + autosave
    writing_component(student_name.strip(), session_id)

    # Мәтін жазу аймағы (Streamlit) — JS autosave жұмыс істеп тұрады
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    essay_text = st.text_area(
        "Жауабыңыз:",
        height=280,
        placeholder="Жауабыңызды осында теріңіз...",
        key=f"essay_input_{session_id}",
        label_visibility="collapsed"
    )

    # Сөз санауыш
    word_count = len(essay_text.split()) if essay_text.strip() else 0
    wc_color = "#3B6D11" if word_count >= 250 else "#854F0B" if word_count >= 150 else "#A32D2D"
    st.markdown(
        f"<p style='font-size:12px;color:{wc_color};text-align:right;margin-top:4px'>"
        f"{word_count} сөз (минимум 150, ұсынылады 250+)</p>",
        unsafe_allow_html=True
    )

    if st.button("✅ Тексеруге жіберу", type="primary", use_container_width=True,
                 key=f"submit_{session_id}"):
        if not essay_text.strip():
            st.error("Жауап мәтінін жазыңыз!")
        else:
            st.session_state[essay_key]  = essay_text
            st.session_state[submit_key] = True
            save_anticheat(student_name.strip(), session_id, "submit", 0, 0, 0)
            st.rerun()

elif not student_name.strip():
    st.info("Алдымен аты-жөніңізді және тапсырма суретін жүктеңіз.")
