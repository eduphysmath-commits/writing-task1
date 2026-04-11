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

def save_result(student_name: str, result: dict, session_id: str):
    try:
        get_supabase().table("results").insert({
            "student_name": student_name,
            "overall": result["overall"],
            "ta": result["TA"], "cc": result["CC"],
            "lr": result["LR"], "gra": result["GRA"],
            "main_errors": result["main_errors"],
            "feedback": result["feedback"],
        }).execute()
        # live_drafts жойылады
        get_supabase().table("live_drafts")\
            .delete().eq("session_id", session_id).execute()
    except Exception as e:
        st.warning(f"Сақтауда қате: {e}")

def get_latest_draft(session_id: str):
    """Соңғы draft мәтінін қайтарады"""
    try:
        res = get_supabase().table("live_drafts")\
            .select("*")\
            .eq("session_id", session_id)\
            .execute()
        if res.data:
            return res.data[0]
    except:
        pass
    return None

def writing_component(student_name: str, session_id: str):
    sb_url = st.secrets["supabase"]["url"]
    sb_key = st.secrets["supabase"]["key"]

    html = f"""
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }}
        body {{ background: transparent; }}

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
            width: 100%; height: 280px;
            border: 1px solid #ddd; border-radius: 8px;
            padding: 12px; font-size: 15px; line-height: 1.6;
            resize: vertical; outline: none;
            transition: border-color 0.3s;
            font-family: sans-serif; color: #333;
            background: white;
        }}
        #essay-box:focus {{ border-color: #639922; }}
        #essay-box:disabled {{ background: #f5f5f5; color: #888; cursor: not-allowed; }}

        #bottom-bar {{
            display: flex; justify-content: space-between; align-items: center;
            margin-top: 8px; margin-bottom: 10px;
        }}
        #word-count {{ font-size: 12px; font-weight: 500; color: #A32D2D; }}
        #save-status {{ font-size: 11px; color: #aaa; }}


    </style>

    <div id="timer-box">
        <div id="timer-label">Уақыт</div>
        <div id="timer-display">20:00</div>
    </div>

    <div id="ac-bar">
        <div class="ac-dot" id="ac-dot"></div>
        <span id="ac-text">Античит белсенді — жұмысты адал орындаңыз</span>
    </div>

    <textarea id="essay-box" placeholder="Жауабыңызды осында теріңіз..."></textarea>

    <div id="bottom-bar">
        <span id="word-count">0 сөз</span>
        <span id="save-status">Сақталмаған</span>
    </div>



    <script>
    (function() {{
        const STUDENT = "{student_name}";
        const SESSION = "{session_id}";
        const SB_URL  = "{sb_url}";
        const SB_KEY  = "{sb_key}";
        const TOTAL   = 1200;

        let blur = 0, paste = 0, annulled = false;
        let started = false, left = TOTAL, timerInterval = null, expired = false;
        let draftInserted = false, submitting = false;

        const tBox   = document.getElementById('timer-box');
        const tDisp  = document.getElementById('timer-display');
        const dot    = document.getElementById('ac-dot');
        const txt    = document.getElementById('ac-text');
        const bar    = document.getElementById('ac-bar');
        const essay  = document.getElementById('essay-box');
        const wcEl   = document.getElementById('word-count');
        const saveEl = document.getElementById('save-status');

        // ---- Дыбыс ----
        function beep(f=880, d=0.4, t='square') {{
            try {{
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const o = ctx.createOscillator(), g = ctx.createGain();
                o.connect(g); g.connect(ctx.destination);
                o.type = t; o.frequency.value = f;
                g.gain.setValueAtTime(0.3, ctx.currentTime);
                g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + d);
                o.start(ctx.currentTime); o.stop(ctx.currentTime + d);
            }} catch(e) {{}}
        }}
        function alarm() {{
            beep(440, 0.3, 'sawtooth');
            setTimeout(() => beep(440, 0.3, 'sawtooth'), 400);
            setTimeout(() => beep(440, 0.3, 'sawtooth'), 800);
        }}

        // ---- Supabase fetch helpers ----
        const HEADERS = {{
            'apikey': SB_KEY, 'Authorization': 'Bearer ' + SB_KEY,
            'Content-Type': 'application/json', 'Prefer': 'return=minimal'
        }};

        async function sbPost(table, body) {{
            try {{
                await fetch(SB_URL + '/rest/v1/' + table, {{
                    method: 'POST', headers: HEADERS,
                    body: JSON.stringify(body)
                }});
            }} catch(e) {{}}
        }}

        async function sbPatch(table, filter, body) {{
            try {{
                await fetch(SB_URL + '/rest/v1/' + table + '?' + filter, {{
                    method: 'PATCH', headers: HEADERS,
                    body: JSON.stringify(body)
                }});
            }} catch(e) {{}}
        }}

        // ---- Античит оқиғасын сақтау ----
        async function logEvent(ev) {{
            if (ev === 'start') return;
            await sbPost('anticheat_events', {{
                student_name: STUDENT, session_id: SESSION,
                event_type: ev, blur_count: blur,
                paste_count: paste,
                annulled: (ev === 'annulled') ? 1 : 0
            }});
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
            essay.disabled = true;
            btn.disabled = true;
            beep(300, 1.5, 'sawtooth');
            setStatus('ЖҰМЫС АННУЛИРЛЕНДІ — мұғалімге хабарланды',
                '#F09595', '#E24B4A', '#501313', '#E24B4A');
            tBox.className = 'done'; tDisp.textContent = 'XXX';
            logEvent('annulled');
        }}

        // ---- Таймер ----
        function fmt(s) {{
            return String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0');
        }}

        function startTimer() {{
            if (started) return;
            started = true;
            logEvent('timer_start');
            timerInterval = setInterval(() => {{
                if (annulled) {{ clearInterval(timerInterval); return; }}
                left--;
                tDisp.textContent = fmt(left);
                tBox.className = left <= 0 ? 'done' : left <= 60 ? 'red' : left <= 300 ? 'yellow' : '';
                if (left === 60) {{
                    beep(660, 0.5);
                    setStatus('1 минут қалды! Жіберуге дайындалыңыз.',
                        '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
                    logEvent('timer_warning');
                }}
                if (left <= 0) {{
                    clearInterval(timerInterval);
                    expired = true;
                    tDisp.textContent = '00:00';
                    alarm();
                    setStatus('Уақыт бітті! Жұмысыңызды жіберіңіз.',
                        '#FCEBEB', '#E24B4A', '#A32D2D', '#E24B4A');
                    logEvent('timer_expired');
                }}
            }}, 1000);
        }}

        // ---- Үздіксіз дыбыс (беттен шыққанда) ----
        let alarmCtx = null;
        let alarmOsc = null;
        let alarmGain = null;

        function startAlarm() {{
            try {{
                alarmCtx = new (window.AudioContext || window.webkitAudioContext)();
                alarmGain = alarmCtx.createGain();
                alarmGain.gain.value = 0.4;
                alarmGain.connect(alarmCtx.destination);

                function playTone() {{
                    if (!alarmCtx) return;
                    alarmOsc = alarmCtx.createOscillator();
                    alarmOsc.connect(alarmGain);
                    alarmOsc.type = 'square';
                    // Жиілік ауысып тұрады — назар аудартады
                    alarmOsc.frequency.setValueAtTime(880, alarmCtx.currentTime);
                    alarmOsc.frequency.setValueAtTime(660, alarmCtx.currentTime + 0.3);
                    alarmOsc.frequency.setValueAtTime(880, alarmCtx.currentTime + 0.6);
                    alarmOsc.start(alarmCtx.currentTime);
                    alarmOsc.stop(alarmCtx.currentTime + 0.9);
                    alarmOsc.onended = () => {{
                        if (alarmCtx) playTone();
                    }};
                }}
                playTone();
            }} catch(e) {{}}
        }}

        function stopAlarm() {{
            try {{
                if (alarmOsc) {{ alarmOsc.onended = null; alarmOsc.stop(); alarmOsc = null; }}
                if (alarmCtx) {{ alarmCtx.close(); alarmCtx = null; }}
            }} catch(e) {{}}
        }}

        // ---- Blur ----
        function onBlur() {{
            if (annulled || expired) return;
            blur++;
            startAlarm();
            if (blur === 1) {{
                setStatus('Ескерту! Басқа бетке өтпеңіз! (1/3)',
                    '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
                logEvent('blur_1');
            }} else if (blur === 2) {{
                setStatus('ҚАТАҢ ЕСКЕРТУ! Тағы бір рет шықсаңыз аннулирленеді! (2/3)',
                    '#FCEBEB', '#E24B4A', '#A32D2D', '#E24B4A');
                logEvent('blur_2');
            }} else {{
                stopAlarm();
                doAnnul();
            }}
        }}

        function onFocus() {{
            stopAlarm();
        }}

        // ---- Autosave (5 сек) ----
        async function saveDraft() {{
            if (annulled || submitting) return;
            const text = essay.value;
            const wc = text.trim() ? text.trim().split(/ +/).length : 0;
            const now = new Date().toISOString();
            if (!draftInserted) {{
                const res = await fetch(SB_URL + '/rest/v1/live_drafts', {{
                    method: 'POST', headers: HEADERS,
                    body: JSON.stringify({{
                        student_name: STUDENT, session_id: SESSION,
                        draft_text: text, word_count: wc, submitted: 0
                    }})
                }});
                if (res.ok || res.status === 201) {{
                    draftInserted = true;
                    saveEl.textContent = 'Сақталды: ' + new Date().toLocaleTimeString();
                }}
            }} else {{
                await sbPatch('live_drafts', 'session_id=eq.' + SESSION, {{
                    draft_text: text, word_count: wc, updated_at: now
                }});
                saveEl.textContent = 'Сақталды: ' + new Date().toLocaleTimeString();
            }}
        }}

        // ---- Submit батырмасы жоқ — Streamlit батырмасын қолданамыз ----
        // Autosave мәтінді Supabase-ке жазып тұрады, Streamlit батырмасы оны оқиды

        // ---- Textarea оқиғалары ----
        essay.addEventListener('input', () => {{
            const words = essay.value.trim() ? essay.value.trim().split(/ +/).length : 0;
            wcEl.textContent = words + ' сөз';
            wcEl.style.color = words >= 250 ? '#3B6D11' : words >= 150 ? '#854F0B' : '#A32D2D';
            if (!started && !annulled) startTimer();
        }});

        essay.addEventListener('paste', () => {{
            if (annulled) return;
            paste++;
            beep(550, 0.3);
            setStatus('Ескерту! Мәтін қою анықталды!',
                '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
            logEvent('paste');
        }});

        // ---- Blur/visibility ----
        document.addEventListener('visibilitychange', () => {{
            if (document.hidden) onBlur();
            else onFocus();
        }});
        window.addEventListener('blur', onBlur);
        window.addEventListener('focus', onFocus);

        // ---- 5 сек autosave ----
        setInterval(saveDraft, 5000);

    }})();
    </script>
    """
    return components.html(html, height=380)

# ==========================================
# ОҚУШЫ БЕТІ
# ==========================================
st.title("✏️ IELTS Writing Task 1")
st.caption("Тапсырманы орындап, жауабыңызды жіберіңіз.")
st.markdown("---")

st.subheader("1. Аты-жөніңізді жазыңыз")
student_name = st.text_input("", placeholder="Мысалы: Айгерім Сейтқали",
                              label_visibility="collapsed")

st.subheader("2. Тапсырма суретін жүктеңіз")
uploaded_file = st.file_uploader("", type=["png", "jpg", "jpeg"],
                                  label_visibility="collapsed")
image = None
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Тапсырма", width=400)

if student_name.strip() and uploaded_file is not None:
    st.markdown("---")

    session_key = f"sid_{student_name.strip().replace(' ','_')}"
    if session_key not in st.session_state:
        st.session_state[session_key] = datetime.now().strftime("%Y%m%d%H%M%S")
    session_id = st.session_state[session_key]

    annul_key  = f"annulled_{session_id}"
    done_key   = f"done_{session_id}"
    if annul_key not in st.session_state: st.session_state[annul_key] = False
    if done_key  not in st.session_state: st.session_state[done_key]  = False

    # Аннулирленген болса тоқта
    if st.session_state.get(annul_key, False):
        st.error("🚫 Жұмысыңыз аннулирленді. Мұғалімге хабарланды.")
        st.stop()

    # Нәтиже көрсетілді ме
    if st.session_state.get(done_key, False):
        result = st.session_state.get(f"result_{session_id}", {})
        if result:
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
        st.stop()

    # Жіберу режимі — JS компонентін жасырамыз
    submitting_key = f"submitting_{session_id}"
    if submitting_key not in st.session_state:
        st.session_state[submitting_key] = False

    if not st.session_state.get(submitting_key, False):
        # JS компоненті — тек жазу кезінде көрінеді
        st.subheader("3. Жауабыңызды жазыңыз")
        st.caption("Жазуды бастағанда таймер автоматты қосылады. Уақыт: 20 минут.")
        writing_component(student_name.strip(), session_id)

        if st.button("✅ Тексеруге жіберу", type="primary", use_container_width=True,
                     key=f"submit_btn_{session_id}"):
            st.session_state[submitting_key] = True
            st.rerun()

    if st.session_state.get(submitting_key, False):
        with st.spinner("⏳ Жұмысыңыз тексерілуде..."):
            # Supabase-тен соңғы draft мәтінін аламыз
            draft = get_latest_draft(session_id)
            essay_text = draft.get("draft_text", "").strip() if draft else ""

            if not essay_text:
                st.session_state[submitting_key] = False
                st.error("Жауап табылмады. Алдымен мәтін жазыңыз (кемінде 5 секунд жазыңыз)!")
                st.rerun()
            else:
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
                    result = json.loads(
                        model.generate_content([prompt, image, essay_text]).text)
                    save_result(student_name.strip(), result, session_id)
                    st.session_state[f"result_{session_id}"] = result
                    st.session_state[done_key] = True
                    st.rerun()
                except Exception as e:
                    st.session_state[submitting_key] = False
                    st.error(f"Қате шықты: {e}")
                    st.rerun()

elif not student_name.strip():
    st.info("Алдымен аты-жөніңізді және тапсырма суретін жүктеңіз.")
