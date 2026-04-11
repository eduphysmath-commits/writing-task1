import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import json
from PIL import Image
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# 1. БЕТТІҢ БАПТАУЛАРЫ
# ==========================================
st.set_page_config(
    page_title="TEN: IELTS Checker",
    page_icon="📊",
    layout="centered"
)

# ==========================================
# 2. SUPABASE ҚОСЫЛЫМЫ
# ==========================================
# Streamlit Cloud-та st.secrets арқылы:
# [supabase]
# url = "https://xxxx.supabase.co"
# key = "your-anon-key"
#
# [gemini]
# api_key = "your-gemini-key"

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def save_result(student_name: str, result: dict):
    try:
        sb = get_supabase()
        sb.table("results").insert({
            "student_name": student_name,
            "overall": result["overall"],
            "ta": result["TA"],
            "cc": result["CC"],
            "lr": result["LR"],
            "gra": result["GRA"],
            "main_errors": result["main_errors"],
            "feedback": result["feedback"],
        }).execute()
    except Exception as e:
        st.warning(f"Нәтижені сақтауда қате: {e}")

def save_anticheat(student_name: str, session_id: str, event_type: str,
                   blur_count: int, paste_count: int, annulled: int):
    try:
        sb = get_supabase()
        sb.table("anticheat_events").insert({
            "student_name": student_name,
            "session_id": session_id,
            "event_type": event_type,
            "blur_count": blur_count,
            "paste_count": paste_count,
            "annulled": annulled,
        }).execute()
    except Exception as e:
        st.warning(f"Античит деректерін сақтауда қате: {e}")

def get_monitor_data() -> list:
    try:
        sb = get_supabase()
        res = sb.table("anticheat_events")\
            .select("*")\
            .order("created_at", desc=True)\
            .limit(100)\
            .execute()
        return res.data or []
    except Exception as e:
        st.error(f"Мониторды жүктеуде қате: {e}")
        return []

def get_results_data() -> list:
    try:
        sb = get_supabase()
        res = sb.table("results")\
            .select("*")\
            .order("checked_at", desc=True)\
            .limit(100)\
            .execute()
        return res.data or []
    except Exception as e:
        st.error(f"Нәтижелерді жүктеуде қате: {e}")
        return []

# ==========================================
# 3. АНТИЧИТ + ТАЙМЕР JS КОМПОНЕНТІ
# ==========================================
def anticheat_timer_component(student_name: str, session_id: str) -> dict | None:
    html_code = f"""
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }}

        #timer-box {{
            position: fixed;
            top: 16px;
            right: 16px;
            z-index: 9999;
            background: #EAF3DE;
            border: 1.5px solid #639922;
            border-radius: 12px;
            padding: 10px 18px;
            text-align: center;
            min-width: 100px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: background 0.5s, border-color 0.5s;
        }}
        #timer-label {{
            font-size: 11px;
            color: #3B6D11;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 2px;
        }}
        #timer-display {{
            font-size: 26px;
            font-weight: 600;
            color: #27500A;
            letter-spacing: 1px;
        }}
        #timer-box.yellow {{
            background: #FAEEDA;
            border-color: #EF9F27;
        }}
        #timer-box.yellow #timer-label {{ color: #854F0B; }}
        #timer-box.yellow #timer-display {{ color: #633806; }}
        #timer-box.red {{
            background: #FCEBEB;
            border-color: #E24B4A;
        }}
        #timer-box.red #timer-label {{ color: #A32D2D; }}
        #timer-box.red #timer-display {{ color: #501313; }}
        #timer-box.done {{
            background: #F09595;
            border-color: #E24B4A;
            animation: pulse 1s ease-in-out infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.04); }}
        }}

        #ac-bar {{
            padding: 10px 16px;
            border-radius: 8px;
            background: #EAF3DE;
            border-left: 4px solid #639922;
            font-size: 13px;
            color: #3B6D11;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s;
        }}
        #ac-bar.warn {{
            background: #FAEEDA;
            border-color: #EF9F27;
            color: #854F0B;
        }}
        #ac-bar.danger {{
            background: #FCEBEB;
            border-color: #E24B4A;
            color: #A32D2D;
        }}
        #ac-bar.dead {{
            background: #F09595;
            border-color: #E24B4A;
            color: #501313;
            font-weight: 600;
        }}
        .ac-dot {{
            width: 10px; height: 10px;
            border-radius: 50%;
            background: #639922;
            flex-shrink: 0;
            transition: background 0.3s;
        }}
    </style>

    <!-- Таймер (оң жақ бұрышта) -->
    <div id="timer-box">
        <div id="timer-label">Уақыт</div>
        <div id="timer-display">20:00</div>
    </div>

    <!-- Античит статус жолағы -->
    <div id="ac-bar">
        <div class="ac-dot" id="ac-dot"></div>
        <span id="ac-text">Античит белсенді — жұмысты адал орындаңыз</span>
    </div>

    <script>
    (function() {{
        const STUDENT = "{student_name}";
        const SESSION = "{session_id}";
        const TOTAL_SEC = 20 * 60;

        let blurCount = 0;
        let pasteCount = 0;
        let annulled = false;
        let timerStarted = false;
        let secondsLeft = TOTAL_SEC;
        let timerInterval = null;
        let timerExpired = false;

        const timerBox = document.getElementById('timer-box');
        const timerDisplay = document.getElementById('timer-display');
        const acBar = document.getElementById('ac-bar');
        const acDot = document.getElementById('ac-dot');
        const acText = document.getElementById('ac-text');

        // Дыбыс сигналы
        function playBeep(freq=880, dur=0.4, type='square') {{
            try {{
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = type;
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.3, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + dur);
            }} catch(e) {{}}
        }}

        function playAlarm() {{
            playBeep(440, 0.3, 'sawtooth');
            setTimeout(() => playBeep(440, 0.3, 'sawtooth'), 400);
            setTimeout(() => playBeep(440, 0.3, 'sawtooth'), 800);
        }}

        // Streamlit-ке жіберу
        function sendData(event_type) {{
            window.parent.postMessage({{
                type: 'streamlit:setComponentValue',
                value: {{
                    student: STUDENT,
                    session: SESSION,
                    event_type: event_type,
                    blur_count: blurCount,
                    paste_count: pasteCount,
                    annulled: annulled ? 1 : 0,
                    timer_expired: timerExpired ? 1 : 0
                }}
            }}, '*');
        }}

        // Античит статусын жаңарту
        function setAcStatus(msg, level='ok') {{
            acBar.className = level === 'ok' ? 'ac-bar' : level;
            acBar.className = `ac-bar ${{level === 'ok' ? '' : level}}`.trim();
            acBar.style.background = {{
                ok: '#EAF3DE', warn: '#FAEEDA', danger: '#FCEBEB', dead: '#F09595'
            }}[level];
            acBar.style.borderColor = {{
                ok: '#639922', warn: '#EF9F27', danger: '#E24B4A', dead: '#E24B4A'
            }}[level];
            acBar.style.color = {{
                ok: '#3B6D11', warn: '#854F0B', danger: '#A32D2D', dead: '#501313'
            }}[level];
            acDot.style.background = {{
                ok: '#639922', warn: '#EF9F27', danger: '#E24B4A', dead: '#E24B4A'
            }}[level];
            acText.textContent = msg;
        }}

        // Аннулирлеу
        function annul() {{
            annulled = true;
            if (timerInterval) clearInterval(timerInterval);
            playBeep(300, 1.5, 'sawtooth');
            setAcStatus('ЖҰМЫС АННУЛИРЛЕНДІ — мұғалімге хабарланды', 'dead');
            timerBox.classList.add('done');
            timerDisplay.textContent = 'XXX';
            sendData('annulled');
        }}

        // Таймер логикасы
        function formatTime(sec) {{
            const m = Math.floor(sec / 60);
            const s = sec % 60;
            return String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
        }}

        function updateTimerStyle(sec) {{
            timerBox.className = '';
            if (sec <= 0) {{
                timerBox.classList.add('done');
            }} else if (sec <= 60) {{
                timerBox.classList.add('red');
            }} else if (sec <= 300) {{
                timerBox.classList.add('yellow');
            }}
        }}

        function startTimer() {{
            if (timerStarted) return;
            timerStarted = true;
            sendData('timer_start');

            timerInterval = setInterval(() => {{
                if (annulled) {{ clearInterval(timerInterval); return; }}
                secondsLeft--;
                timerDisplay.textContent = formatTime(secondsLeft);
                updateTimerStyle(secondsLeft);

                // 1 минут қалғанда ескерту
                if (secondsLeft === 60) {{
                    playBeep(660, 0.5);
                    setAcStatus('1 минут қалды! Жұмысыңызды жіберуге дайындалыңыз.', 'warn');
                    sendData('timer_warning');
                }}

                // Уақыт бітті
                if (secondsLeft <= 0) {{
                    clearInterval(timerInterval);
                    timerExpired = true;
                    timerDisplay.textContent = '00:00';
                    playAlarm();
                    setAcStatus('Уақыт бітті! Жұмысыңызды жіберіңіз.', 'danger');
                    sendData('timer_expired');
                }}
            }}, 1000);
        }}

        // Беттен шығу оқиғасы
        function handleBlur() {{
            if (annulled || timerExpired) return;
            blurCount++;

            if (blurCount === 1) {{
                playBeep(660, 0.5);
                setAcStatus('Ескерту! Басқа бетке өтпеңіз! (1/3)', 'warn');
                sendData('blur_1');
            }} else if (blurCount === 2) {{
                playBeep(440, 0.7);
                setAcStatus('ҚАТАҢ ЕСКЕРТУ! Тағы бір рет шықсаңыз жұмыс аннулирленеді! (2/3)', 'danger');
                sendData('blur_2');
            }} else if (blurCount >= 3) {{
                annul();
            }}
        }}

        // Paste оқиғасы
        function handlePaste() {{
            if (annulled) return;
            pasteCount++;
            playBeep(550, 0.3);
            setAcStatus('Ескерту! Мәтін қою анықталды! Өз жұмысыңызды жазыңыз.', 'warn');
            sendData('paste');
        }}

        // Теру басталғанда таймер қосылады
        function handleKeydown(e) {{
            if (!timerStarted && !annulled && e.key && e.key.length === 1) {{
                startTimer();
            }}
        }}

        // Оқиғаларды тіркеу
        document.addEventListener('visibilitychange', () => {{
            if (document.hidden) handleBlur();
        }});
        window.addEventListener('blur', handleBlur);
        document.addEventListener('paste', handlePaste);
        document.addEventListener('keydown', handleKeydown);

        // Бастапқы хабарлама
        sendData('start');
    }})();
    </script>
    """
    result = components.html(html_code, height=70)
    return result

# ==========================================
# 4. НАВИГАЦИЯ
# ==========================================
st.sidebar.title("📊 TEN: IELTS")
page = st.sidebar.radio("Бөлім таңдаңыз:", [
    "✏️ Тексеру",
    "🛡 Мұғалім мониторы"
])

# ==========================================
# 5. ТЕКСЕРУ БЕТІ
# ==========================================
if page == "✏️ Тексеру":
    st.title("📊 TEN: IELTS Writing Task 1")
    st.markdown("Графикалық тапсырмаларды тексеруге арналған модуль.")
    st.markdown("---")

    # ҚАДАМ 1: Ат + Сурет
    st.subheader("1. Аты-жөніңізді жазыңыз")
    student_name = st.text_input("", placeholder="Мысалы: Айгерім Сейтқали", label_visibility="collapsed")

    st.subheader("2. Тапсырма суретін жүктеңіз")
    uploaded_file = st.file_uploader("", type=["png", "jpg", "jpeg"], label_visibility="collapsed")

    image = None
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="Жүктелген тапсырма", width=400)

    # ҚАДАМ 2: Античит + Таймер қосылады
    anticheat_active = False
    if student_name.strip() and uploaded_file is not None:
        st.markdown("---")
        st.subheader("3. Жауабыңызды жазыңыз")
        st.caption("Жазуды бастағанда таймер автоматты қосылады. Уақыт: 20 минут.")

        # Сессия ID
        session_key = f"sid_{student_name.strip().replace(' ', '_')}"
        if session_key not in st.session_state:
            st.session_state[session_key] = datetime.now().strftime("%Y%m%d%H%M%S")
        session_id = st.session_state[session_key]

        # Аннулирлеу / уақыт бітті күйі
        annul_key = f"annulled_{session_id}"
        expired_key = f"expired_{session_id}"
        if annul_key not in st.session_state:
            st.session_state[annul_key] = False
        if expired_key not in st.session_state:
            st.session_state[expired_key] = False

        # Античит + Таймер компоненті
        ac_data = anticheat_timer_component(student_name.strip(), session_id)

        # JS деректерін өңдеу
        if ac_data and isinstance(ac_data, dict):
            event_type = ac_data.get("event_type", "")
            blur_count = ac_data.get("blur_count", 0)
            paste_count = ac_data.get("paste_count", 0)
            annulled = ac_data.get("annulled", 0)
            timer_expired = ac_data.get("timer_expired", 0)

            if event_type not in ("start",):
                save_anticheat(
                    student_name.strip(), session_id, event_type,
                    blur_count, paste_count, annulled
                )

            if annulled:
                st.session_state[annul_key] = True
            if timer_expired:
                st.session_state[expired_key] = True

        # Аннулирленді ме?
        if st.session_state.get(annul_key, False):
            st.error("🚫 Жұмысыңыз аннулирленді. Мұғалімге хабарланды.")
            st.stop()

        anticheat_active = True

    # ҚАДАМ 3: Жазу аймағы
    essay_text = ""
    if anticheat_active:
        timer_done = st.session_state.get(f"expired_{st.session_state.get(session_key, '')}", False)

        essay_text = st.text_area(
            "",
            height=280,
            placeholder="Жауабыңызды осында теріңіз... (жазуды бастағанда таймер қосылады)",
            label_visibility="collapsed",
            disabled=timer_done and False  # уақыт бітсе де жіберуге болады
        )

        # Уақыт бітті ескертуі
        if timer_done:
            st.warning("⏰ Уақыт бітті! Жұмысыңызды жіберіңіз.")

    elif not student_name.strip():
        st.info("Алдымен аты-жөніңізді және тапсырма суретін жүктеңіз.")

    # ҚАДАМ 4: Тексеру батырмасы
    if anticheat_active:
        btn_label = "📤 Жіберу" if st.session_state.get(
            f"expired_{st.session_state.get(session_key, '')}", False
        ) else "✅ Тексеруге жіберу"

        if st.button(btn_label, type="primary", use_container_width=True):
            if not essay_text.strip():
                st.error("Жауап мәтінін жазыңыз!")
            else:
                try:
                    api_key = st.secrets["gemini"]["api_key"]
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(
                        'gemini-2.5-flash',
                        generation_config={"response_mime_type": "application/json"}
                    )

                    prompt = """
Act as an expert IELTS examiner. Look at the provided image (graph/map/diagram/process) and read the student's Task 1 report.
Evaluate it based on the official 9-band IELTS writing descriptors. Provide scores in exact 0.5 increments.

Evaluate the following 4 criteria:
1. Task Achievement (TA)
2. Coherence and Cohesion (CC)
3. Lexical Resource (LR)
4. Grammatical Range and Accuracy (GRA)

Calculate the Overall Band Score based on the exact average of these 4 criteria.

CRITICAL INSTRUCTION FOR FEEDBACK:
Write the 'main_errors' and 'feedback' sections IN KAZAKH LANGUAGE.
Speak directly to the student in a friendly, encouraging, and clear educational tone.
Explain why they got their scores and how to improve.

Return ONLY a valid JSON object strictly following this structure:
{
    "overall": 6.5,
    "TA": 6.0,
    "CC": 6.5,
    "LR": 7.0,
    "GRA": 6.5,
    "main_errors": ["Қате 1 және оны дұрыстау жолы", "Қате 2..."],
    "feedback": "Оқушыға арналған қазақ тіліндегі толық, мотивациялық әрі құрылымды пікір..."
}
"""
                    with st.spinner("Жұмысыңыз тексерілуде..."):
                        response = model.generate_content([prompt, image, essay_text])
                        result = json.loads(response.text)
                        save_result(student_name.strip(), result)

                    st.markdown("---")
                    st.success("✅ Жұмысыңыз тексерілді!")
                    st.markdown(
                        f"<h2 style='text-align:center;color:#1E88E5;'>🏆 Overall Band: {result['overall']}</h2>",
                        unsafe_allow_html=True
                    )
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Task Achievement", result["TA"])
                    col2.metric("Coherence", result["CC"])
                    col3.metric("Lexical", result["LR"])
                    col4.metric("Grammar", result["GRA"])
                    st.markdown("---")
                    st.subheader("🛠 Жіберілген қателер")
                    for error in result["main_errors"]:
                        st.warning(f"• {error}")
                    st.subheader("📝 Пікір")
                    st.info(result["feedback"])

                except Exception as e:
                    st.error(f"Қате шықты: {e}")

# ==========================================
# 6. МҰҒАЛІМ МОНИТОРЫ
# ==========================================
elif page == "🛡 Мұғалім мониторы":
    st.title("🛡 Мұғалім мониторы")
    st.markdown("---")

    col_r, col_t = st.columns([4, 1])
    with col_t:
        if st.button("🔄 Жаңарту"):
            st.rerun()

    tab1, tab2 = st.tabs(["🔴 Античит оқиғалары", "📊 Тексеру нәтижелері"])

    # АНТИЧИТ ОҚИҒАЛАРЫ
    with tab1:
        events = get_monitor_data()
        if not events:
            st.info("Әлі оқиға жоқ.")
        else:
            for ev in events:
                name = ev.get("student_name", "—")
                event_type = ev.get("event_type", "—")
                blur = ev.get("blur_count", 0)
                paste = ev.get("paste_count", 0)
                annulled = ev.get("annulled", 0)
                created_at = ev.get("created_at", "")[:16]

                if annulled:
                    bg, border, color, icon = "#F09595", "#E24B4A", "#501313", "🚫"
                    label = "АННУЛИРЛЕНДІ"
                elif blur >= 2 or paste >= 1:
                    bg, border, color, icon = "#FAEEDA", "#EF9F27", "#854F0B", "⚠️"
                    label = "КҮДІКТІ"
                elif event_type in ("blur_1",):
                    bg, border, color, icon = "#FCEBEB", "#E24B4A", "#A32D2D", "🔴"
                    label = "ЕСКЕРТУ"
                elif event_type == "timer_expired":
                    bg, border, color, icon = "#E6F1FB", "#378ADD", "#042C53", "⏰"
                    label = "УАҚЫТ БІТТІ"
                else:
                    bg, border, color, icon = "#EAF3DE", "#639922", "#27500A", "✅"
                    label = event_type

                st.markdown(f"""
                <div style="background:{bg};border-left:4px solid {border};color:{color};
                    border-radius:6px;padding:10px 14px;margin-bottom:6px;font-size:13px;">
                    <b>{icon} {name}</b> &nbsp;·&nbsp; {label}
                    &nbsp;·&nbsp; Blur: <b>{blur}</b>
                    &nbsp;·&nbsp; Paste: <b>{paste}</b>
                    &nbsp;·&nbsp; <span style="opacity:0.7">{created_at}</span>
                </div>
                """, unsafe_allow_html=True)

    # НӘТИЖЕЛЕР
    with tab2:
        results = get_results_data()
        if not results:
            st.info("Әлі нәтиже жоқ.")
        else:
            for r in results:
                name = r.get("student_name", "—")
                overall = r.get("overall", "—")
                ta = r.get("ta", "—")
                cc = r.get("cc", "—")
                lr = r.get("lr", "—")
                gra = r.get("gra", "—")
                checked_at = r.get("checked_at", "")[:16]

                with st.expander(f"👤 {name} · Overall: {overall} · {checked_at}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("TA", ta)
                    c2.metric("CC", cc)
                    c3.metric("LR", lr)
                    c4.metric("GRA", gra)
                    errors = r.get("main_errors", [])
                    if errors:
                        st.markdown("**Қателер:**")
                        for e in (errors if isinstance(errors, list) else []):
                            st.warning(f"• {e}")
                    feedback = r.get("feedback", "")
                    if feedback:
                        st.info(feedback)