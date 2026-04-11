import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import json
import time as _time
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
            "task_type": "Task 1",
        }).execute()
        get_supabase().table("live_drafts")\
            .delete().eq("session_id", session_id).execute()
    except Exception as e:
        st.warning(f"Сақтауда қате: {e}")

def get_latest_draft(session_id: str):
    try:
        res = get_supabase().table("live_drafts")\
            .select("*").eq("session_id", session_id).execute()
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
            margin-top: 8px; margin-bottom: 4px;
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
    <div id="bottom-bar" style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;margin-bottom:4px;">
        <span id="word-count" style="font-size:12px;font-weight:500;color:#A32D2D;">0 сөз</span>
        <div style="display:flex;align-items:center;gap:8px;">
            <span id="save-status" style="font-size:11px;color:#aaa;"></span>
            <button id="show-teacher-btn" style="
                padding:5px 12px; background:transparent;
                border:1px solid #ddd; border-radius:6px;
                font-size:12px; color:#555; cursor:pointer;
            ">👁 Айнұр ұстазға көрсету</button>
        </div>
    </div>

    <script>
    (function() {{
        const STUDENT = "{student_name}";
        const SESSION = "{session_id}";
        const SB_URL  = '{sb_url}';
        const SB_KEY  = '{sb_key}';
        const TOTAL   = 1200;

        let blur = 0, paste = 0, annulled = false;
        let started = false, left = TOTAL, timerInterval = null, expired = false;
        let draftInserted = false, submitting = false;
        let alarmCtx = null, alarmOsc = null, alarmGain = null;

        const tBox   = document.getElementById('timer-box');
        const tDisp  = document.getElementById('timer-display');
        const dot    = document.getElementById('ac-dot');
        const txt    = document.getElementById('ac-text');
        const bar    = document.getElementById('ac-bar');
        const essay  = document.getElementById('essay-box');
        const wcEl   = document.getElementById('word-count');
        const saveEl = document.getElementById('save-status');

        // ---- Supabase helpers ----
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

        // ---- Античит логгер ----
        async function logEvent(ev) {{
            if (ev === 'start') return;
            await sbPost('anticheat_events', {{
                student_name: STUDENT, session_id: SESSION,
                event_type: ev, blur_count: blur,
                paste_count: paste,
                annulled: (ev === 'annulled') ? 1 : 0
            }});
        }}

        // ---- Статус ----
        function setStatus(msg, bg, bc, c, dc) {{
            bar.style.background = bg; bar.style.borderColor = bc;
            bar.style.color = c; dot.style.background = dc;
            txt.textContent = msg;
        }}

        // ---- Дыбыс (тек алғашқы 10 минутта) ----
        function startAlarm() {{
            if (left < TOTAL - 600) return;
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
                    alarmOsc.frequency.setValueAtTime(880, alarmCtx.currentTime);
                    alarmOsc.frequency.setValueAtTime(660, alarmCtx.currentTime + 0.3);
                    alarmOsc.frequency.setValueAtTime(880, alarmCtx.currentTime + 0.6);
                    alarmOsc.start(alarmCtx.currentTime);
                    alarmOsc.stop(alarmCtx.currentTime + 0.9);
                    alarmOsc.onended = () => {{ if (alarmCtx) playTone(); }};
                }}
                playTone();
                setTimeout(() => stopAlarm(), 3000);
            }} catch(e) {{}}
        }}

        function stopAlarm() {{
            try {{
                if (alarmOsc) {{ alarmOsc.onended = null; alarmOsc.stop(); alarmOsc = null; }}
                if (alarmCtx) {{ alarmCtx.close(); alarmCtx = null; }}
            }} catch(e) {{}}
        }}

        // ---- Аннулирлеу ----
        function doAnnul() {{
            annulled = true;
            if (timerInterval) clearInterval(timerInterval);
            stopAlarm();
            essay.disabled = true;
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
                    setStatus('1 минут қалды! Жіберуге дайындалыңыз.',
                        '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
                    logEvent('timer_warning');
                }}
                if (left <= 0) {{
                    clearInterval(timerInterval);
                    expired = true;
                    tDisp.textContent = '00:00';
                    setStatus('Уақыт бітті! Жұмысыңызды жіберіңіз.',
                        '#FCEBEB', '#E24B4A', '#A32D2D', '#E24B4A');
                    logEvent('timer_expired');
                }}
            }}, 1000);
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
                doAnnul();
            }}
        }}

        function onFocus() {{
            stopAlarm();
        }}

        // ---- Мұғалімге жіберу ----
        let teacherBtnActive = false;
        async function sendToTeacher() {{
            const text = essay.value.trim();
            if (!text) {{ alert('Алдымен мәтін жазыңыз!'); return; }}
            teacherBtnActive = true;
            setTimeout(() => {{ teacherBtnActive = false; }}, 2000);
            const wc = text.split(/ +/).length;
            const now = new Date().toISOString();
            const btn = document.getElementById('show-teacher-btn');
            btn.disabled = true;
            btn.textContent = 'Жіберілуде...';
            try {{
                console.log('SB_URL:', SB_URL);
                console.log('SB_KEY длина:', SB_KEY ? SB_KEY.length : 'БОС');
                console.log('Text длина:', text.length);
                console.log('draftInserted:', draftInserted);

                let fetchRes;
                if (!draftInserted) {{
                    fetchRes = await fetch(SB_URL + '/rest/v1/live_drafts', {{
                        method: 'POST', headers: HEADERS,
                        body: JSON.stringify({{
                            student_name: STUDENT, session_id: SESSION,
                            draft_text: text, word_count: wc, submitted: 0
                        }})
                    }});
                    console.log('POST статус:', fetchRes.status);
                    if (fetchRes.ok || fetchRes.status === 201) draftInserted = true;
                    else {{
                        const errText = await fetchRes.text();
                        console.error('POST қате:', errText);
                    }}
                }} else {{
                    fetchRes = await fetch(SB_URL + '/rest/v1/live_drafts?session_id=eq.' + SESSION, {{
                        method: 'PATCH', headers: HEADERS,
                        body: JSON.stringify({{ draft_text: text, word_count: wc, updated_at: now }})
                    }});
                    console.log('PATCH статус:', fetchRes.status);
                }}
                btn.textContent = '✅ Мұғалімге жіберілді';
                btn.style.background = '#EAF3DE';
                btn.style.color = '#3B6D11';
                btn.style.borderColor = '#639922';
                saveEl.textContent = 'Жіберілді: ' + new Date().toLocaleTimeString();
                setTimeout(() => {{
                    btn.disabled = false;
                    btn.textContent = '👁 Айнұр ұстазға көрсету';
                    btn.style.background = '';
                    btn.style.color = '';
                    btn.style.borderColor = '';
                }}, 3000);
            }} catch(e) {{
                console.error('sendToTeacher қате:', e);
                btn.disabled = false;
                btn.textContent = '👁 Айнұр ұстазға көрсету';
                alert('Қате: ' + e.message);
            }}
        }}

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
            setStatus('Ескерту! Мәтін қою анықталды!',
                '#FAEEDA', '#EF9F27', '#854F0B', '#EF9F27');
            logEvent('paste');
        }});

        document.addEventListener('visibilitychange', () => {{
            if (document.hidden) {{
                if (teacherBtnActive || submitting) return;
                onBlur();
            }} else onFocus();
        }});
        window.addEventListener('blur', () => {{
            setTimeout(() => {{
                if (teacherBtnActive || submitting) return;
                if (document.activeElement && document.activeElement.tagName === 'BUTTON') return;
                onBlur();
            }}, 100);
        }});
        window.addEventListener('focus', onFocus);

        // Батырмаға addEventListener арқылы тіркейміз
        document.getElementById('show-teacher-btn').addEventListener('click', sendToTeacher);

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

    annul_key      = f"annulled_{session_id}"
    done_key       = f"done_{session_id}"
    submitting_key = f"submitting_{session_id}"

    if annul_key      not in st.session_state: st.session_state[annul_key]      = False
    if done_key       not in st.session_state: st.session_state[done_key]       = False
    if submitting_key not in st.session_state: st.session_state[submitting_key] = False

    # Аннулирленді ме?
    if st.session_state.get(annul_key, False):
        st.error("🚫 Жұмысыңыз аннулирленді. Мұғалімге хабарланды.")
        st.stop()

    # Нәтиже бар ма?
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
            st.markdown(result["feedback"])

            # Мәтінді көшіру батырмасы
            st.markdown("---")
            essay_saved = st.session_state.get(f"essay_text_{session_id}", "")
            if essay_saved:
                st.subheader("📋 Жазған мәтініңіз")
                st.text_area("", value=essay_saved, height=200,
                             disabled=True, label_visibility="collapsed",
                             key="saved_essay_display")
                # JS арқылы clipboard-ке көшіру
                copy_html = f"""
                <button id="copy-btn" onclick="copyText()" style="
                    padding:10px 20px; background:#1E88E5; color:white;
                    border:none; border-radius:8px; font-size:14px;
                    cursor:pointer; width:100%; margin-top:4px;
                ">📋 Мәтінді көшіру</button>
                <span id="copy-msg" style="font-size:12px;color:#3B6D11;margin-left:8px;display:none;">✅ Көшірілді!</span>
                <script>
                function copyText() {{
                    const text = {json.dumps(essay_saved)};
                    navigator.clipboard.writeText(text).then(() => {{
                        document.getElementById('copy-msg').style.display = 'inline';
                        document.getElementById('copy-btn').textContent = '✅ Көшірілді!';
                        document.getElementById('copy-btn').style.background = '#639922';
                        setTimeout(() => {{
                            document.getElementById('copy-btn').textContent = '📋 Мәтінді көшіру';
                            document.getElementById('copy-btn').style.background = '#1E88E5';
                            document.getElementById('copy-msg').style.display = 'none';
                        }}, 3000);
                    }}).catch(() => {{
                        // Fallback
                        const ta = document.createElement('textarea');
                        ta.value = text;
                        document.body.appendChild(ta);
                        ta.select();
                        document.execCommand('copy');
                        document.body.removeChild(ta);
                        document.getElementById('copy-btn').textContent = '✅ Көшірілді!';
                        document.getElementById('copy-btn').style.background = '#639922';
                        setTimeout(() => {{
                            document.getElementById('copy-btn').textContent = '📋 Мәтінді көшіру';
                            document.getElementById('copy-btn').style.background = '#1E88E5';
                        }}, 3000);
                    }});
                }}
                </script>
                """
                import streamlit.components.v1 as _components
                _components.html(copy_html, height=60)
        st.stop()

    # Тексеру жүріп жатыр ма?
    if st.session_state.get(submitting_key, False):
        with st.spinner("⏳ Жұмысыңыз тексерілуде..."):
            # Supabase-тен мәтінді аламыз (макс 8 сек)
            draft = None
            for _ in range(4):
                draft = get_latest_draft(session_id)
                if draft and draft.get("draft_text","").strip():
                    break
                _time.sleep(2)

            essay_text = draft.get("draft_text","").strip() if draft else ""

            if not essay_text:
                st.session_state[submitting_key] = False
                st.error("Жауап табылмады. Жазып болғаннан кейін бірнеше секунд күтіп жіберіңіз!")
                st.rerun()
            else:
                MAX_RETRIES = 5
                RETRY_DELAYS = [5, 10, 20, 30, 60]

                genai.configure(api_key=st.secrets["gemini"]["api_key"])
                model = genai.GenerativeModel(
                    'gemini-2.5-flash',
                    generation_config={
                        "response_mime_type": "application/json",
                        "max_output_tokens": 8000,
                        "temperature": 0,
                    }
                )
                word_count = len(essay_text.split())
                prompt = f"""You are an expert and strict IELTS Writing Examiner. Evaluate the student's IELTS Academic Task 1 report based on the provided image.
CRITICAL RULES & SCORING PENALTIES (NEVER IGNORE):
The student's response is exactly {word_count} words long. Apply the following scoring rules based on length:
- Under 50 words: Maximum Overall Score is 2.5.
- 50 to 99 words: Maximum Overall Score is 4.5.
- 100 to 139 words: Maximum Overall Score is 6.5. Deduct up to 1.0 band from Task Achievement (TA) because short essays usually lack key details. However, evaluate CC, LR, and GRA completely normally based on the actual quality of the text written. Do not artificially lower them.
- 140+ words: Evaluate normally. Do not apply any length penalties.
GRADING CRITERIA:
1. Score each category (TA, CC, LR, GRA) using exact 0.5 increments only (e.g., 5.0, 5.5, 6.0).
2. Calculate the 'overall' score as the exact mathematical average of TA, CC, LR, and GRA. Round down to the nearest 0.5 if necessary.
LANGUAGE & FEEDBACK REQUIREMENT:
The 'main_errors' array and 'feedback' string MUST be written entirely in natural, professional, and grammatically correct Kazakh language.
Base your feedback strictly on the student's actual text. You MUST quote specific words or sentences the student used to prove your points.
OUTPUT FORMAT:
Return ONLY a valid JSON object. Do not include markdown formatting like ```json, do not include explanations, and do not write any text outside the JSON structure.
Use this exact JSON structure:
{{
  "overall": 0.0,
  "TA": 0.0,
  "CC": 0.0,
  "LR": 0.0,
  "GRA": 0.0,
  "main_errors": [
    "Бірінші нақты қате...",
    "Екінші нақты қате..."
  ],
  "feedback": "### 1. Task Achievement (Тапсырманың орындалуы): **[Score]**\n* [1-2 sentences explaining what key features were covered]\n* [1 sentence evaluating their Overview]\n\n### 2. Coherence and Cohesion (Логика және байланыс): **[Score]**\n* [Comment on paragraphing and logical flow]\n* [Quote and evaluate the linking words used]\n* **Ұсыныс:** [Actionable advice]\n\n### 3. Lexical Resource (Сөздік қор): **[Score]**\n* [Quote specific good vocabulary used]\n* [Point out precise errors in collocations or word choice]\n\n### 4. Grammatical Range and Accuracy (Грамматика): **[Score]**\n* [Comment on sentence structures]\n* [Point out specific grammatical errors]\n\n---\n### Қалай жақсартуға болады? (Tips for [Overall + 0.5]+)\n1. **[Specific Tip 1]:** [Actionable advice based on their mistakes]\n2. **[Specific Tip 2]:** [Actionable advice]\n\n**Қорытынды:** [Brief encouraging summary]"
}}"""

                last_error = None
                for attempt in range(MAX_RETRIES):
                    try:
                        if attempt > 0:
                            wait = RETRY_DELAYS[min(attempt-1, len(RETRY_DELAYS)-1)]
                            st.info(f"⏳ Кезек күтілуде... {wait} сек ({attempt}/{MAX_RETRIES})")
                            _time.sleep(wait)

                        raw = model.generate_content([prompt, image, essay_text]).text
                        # JSON блогін тазалаймыз
                        raw = raw.strip()
                        if raw.startswith("```"):
                            raw = raw.split("```")[1]
                            if raw.startswith("json"):
                                raw = raw[4:]
                        result = json.loads(raw.strip())
                        # Кілттерді қалыпқа келтіреміз
                        result["TA"]  = result.get("TA",  result.get("ta",  0))
                        result["CC"]  = result.get("CC",  result.get("cc",  0))
                        result["LR"]  = result.get("LR",  result.get("lr",  0))
                        result["GRA"] = result.get("GRA", result.get("gra", 0))
                        result["overall"] = result.get("overall", result.get("Overall", 0))
                        save_result(student_name.strip(), result, session_id)
                        st.session_state[f"result_{session_id}"] = result
                        st.session_state[f"essay_text_{session_id}"] = essay_text
                        st.session_state[done_key] = True
                        st.session_state[submitting_key] = False
                        st.rerun()
                        break

                    except Exception as e:
                        last_error = str(e)
                        if any(x in last_error.lower() for x in ["429","quota","rate","resource_exhausted"]):
                            if attempt < MAX_RETRIES - 1:
                                continue
                        else:
                            break

                if not st.session_state.get(done_key, False):
                    st.session_state[submitting_key] = False
                    if last_error and any(x in last_error.lower() for x in ["429","quota","rate"]):
                        st.error("⏳ Жүйе қазір бос емес. 1-2 минуттан кейін қайталаңыз.")
                    elif last_error:
                        st.error(f"Қате шықты: {last_error}")
                    st.rerun()

    else:
        # Жазу беті
        st.subheader("3. Жауабыңызды жазыңыз")
        st.caption("Жазуды бастағанда таймер автоматты қосылады. Уақыт: 20 минут.")
        writing_component(student_name.strip(), session_id)

        if st.button("✅ Тексеруге жіберу", type="primary",
                     use_container_width=True, key=f"submit_{session_id}"):
            st.session_state[submitting_key] = True
            st.rerun()

elif not student_name.strip():
    st.info("Алдымен аты-жөніңізді және тапсырма суретін жүктеңіз.")
