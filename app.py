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

def upsert_live_draft(student_name: str, session_id: str, draft_text: str):
    try:
        word_count = len(draft_text.split()) if draft_text.strip() else 0
        sb = get_supabase()
        # Бар жазба бар ма тексеру
        res = sb.table("live_drafts")\
            .select("id")\
            .eq("session_id", session_id)\
            .execute()
        if res.data:
            sb.table("live_drafts")\
                .update({"draft_text": draft_text, "word_count": word_count,
                         "updated_at": datetime.utcnow().isoformat()})\
                .eq("session_id", session_id)\
                .execute()
        else:
            sb.table("live_drafts").insert({
                "student_name": student_name, "session_id": session_id,
                "draft_text": draft_text, "word_count": word_count,
            }).execute()
    except:
        pass

def delete_live_draft(session_id: str):
    try:
        get_supabase().table("live_drafts")\
            .delete().eq("session_id", session_id).execute()
    except:
        pass

def anticheat_timer_component(student_name: str, session_id: str):
    html = f"""
    <style>
        #timer-box {{
            position:fixed; top:16px; right:16px; z-index:9999;
            background:#EAF3DE; border:1.5px solid #639922; border-radius:12px;
            padding:10px 18px; text-align:center; min-width:100px;
            transition:background 0.5s,border-color 0.5s;
        }}
        #timer-label {{ font-size:11px; color:#3B6D11; text-transform:uppercase; margin-bottom:2px; }}
        #timer-display {{ font-size:26px; font-weight:600; color:#27500A; letter-spacing:1px; }}
        #timer-box.yellow {{ background:#FAEEDA; border-color:#EF9F27; }}
        #timer-box.yellow #timer-label {{ color:#854F0B; }}
        #timer-box.yellow #timer-display {{ color:#633806; }}
        #timer-box.red {{ background:#FCEBEB; border-color:#E24B4A; }}
        #timer-box.red #timer-label {{ color:#A32D2D; }}
        #timer-box.red #timer-display {{ color:#501313; }}
        #timer-box.done {{ background:#F09595; border-color:#E24B4A; animation:pulse 1s ease-in-out infinite; }}
        @keyframes pulse {{ 0%,100%{{transform:scale(1)}} 50%{{transform:scale(1.04)}} }}
        #ac-bar {{
            padding:10px 16px; border-radius:8px; background:#EAF3DE;
            border-left:4px solid #639922; font-size:13px; color:#3B6D11;
            display:flex; align-items:center; gap:8px; transition:all 0.3s;
        }}
        .ac-dot {{ width:10px; height:10px; border-radius:50%; background:#639922; flex-shrink:0; }}
    </style>
    <div id="timer-box"><div id="timer-label">Уақыт</div><div id="timer-display">20:00</div></div>
    <div id="ac-bar"><div class="ac-dot" id="ac-dot"></div><span id="ac-text">Античит белсенді — жұмысты адал орындаңыз</span></div>
    <script>
    (function(){{
        const STUDENT="{student_name}", SESSION="{session_id}", TOTAL=1200;
        let blur=0,paste=0,annulled=false,started=false,left=TOTAL,interval=null,expired=false;
        const tBox=document.getElementById('timer-box'), tDisp=document.getElementById('timer-display');
        const dot=document.getElementById('ac-dot'), txt=document.getElementById('ac-text');
        const bar=document.getElementById('ac-bar');

        function beep(f=880,d=0.4,t='square'){{
            try{{const c=new(window.AudioContext||window.webkitAudioContext)();
            const o=c.createOscillator(),g=c.createGain();
            o.connect(g);g.connect(c.destination);o.type=t;o.frequency.value=f;
            g.gain.setValueAtTime(0.3,c.currentTime);
            g.gain.exponentialRampToValueAtTime(0.001,c.currentTime+d);
            o.start(c.currentTime);o.stop(c.currentTime+d);}}catch(e){{}}
        }}
        function alarm(){{beep(440,0.3,'sawtooth');setTimeout(()=>beep(440,0.3,'sawtooth'),400);setTimeout(()=>beep(440,0.3,'sawtooth'),800);}}
        function send(ev){{window.parent.postMessage({{type:'streamlit:setComponentValue',
            value:{{student:STUDENT,session:SESSION,event_type:ev,blur_count:blur,
                    paste_count:paste,annulled:annulled?1:0,timer_expired:expired?1:0}}}},  '*');}}
        function status(msg,bg,bc,c,dc){{
            bar.style.background=bg;bar.style.borderColor=bc;bar.style.color=c;dot.style.background=dc;txt.textContent=msg;
        }}
        function doAnnul(){{
            annulled=true;if(interval)clearInterval(interval);
            beep(300,1.5,'sawtooth');
            status('ЖҰМЫС АННУЛИРЛЕНДІ — мұғалімге хабарланды','#F09595','#E24B4A','#501313','#E24B4A');
            tBox.className='done';tDisp.textContent='XXX';send('annulled');
        }}
        function fmt(s){{return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');}}
        function startTimer(){{
            if(started)return;started=true;send('timer_start');
            interval=setInterval(()=>{{
                if(annulled){{clearInterval(interval);return;}}
                left--;tDisp.textContent=fmt(left);
                tBox.className=left<=0?'done':left<=60?'red':left<=300?'yellow':'';
                if(left===60){{beep(660,0.5);status('1 минут қалды!','#FAEEDA','#EF9F27','#854F0B','#EF9F27');send('timer_warning');}}
                if(left<=0){{clearInterval(interval);expired=true;tDisp.textContent='00:00';
                    alarm();status('Уақыт бітті! Жұмысыңызды жіберіңіз.','#FCEBEB','#E24B4A','#A32D2D','#E24B4A');send('timer_expired');}}
            }},1000);
        }}
        function onBlur(){{
            if(annulled||expired)return;blur++;
            if(blur===1){{beep(660,0.5);status('Ескерту! Басқа бетке өтпеңіз! (1/3)','#FAEEDA','#EF9F27','#854F0B','#EF9F27');send('blur_1');}}
            else if(blur===2){{beep(440,0.7);status('ҚАТАҢ ЕСКЕРТУ! Тағы бір рет шықсаңыз аннулирленеді! (2/3)','#FCEBEB','#E24B4A','#A32D2D','#E24B4A');send('blur_2');}}
            else doAnnul();
        }}
        document.addEventListener('visibilitychange',()=>{{if(document.hidden)onBlur();}});
        window.addEventListener('blur',onBlur);
        document.addEventListener('paste',()=>{{if(annulled)return;paste++;beep(550,0.3);status('Ескерту! Мәтін қою анықталды!','#FAEEDA','#EF9F27','#854F0B','#EF9F27');send('paste');}});
        document.addEventListener('keydown',(e)=>{{if(!started&&!annulled&&e.key&&e.key.length===1)startTimer();}});

        // 5 секунд сайын мәтінді автосақтау
        setInterval(()=>{{
            if(annulled) return;
            const textarea = window.parent.document.querySelector('textarea');
            const text = textarea ? textarea.value : '';
            window.parent.postMessage({{
                type: 'streamlit:setComponentValue',
                value: {{ student: STUDENT, session: SESSION, event_type: 'autosave',
                          blur_count: blur, paste_count: paste,
                          annulled: annulled?1:0, timer_expired: expired?1:0,
                          draft_text: text }}
            }}, '*');
        }}, 5000);

        send('start');
    }})();
    </script>
    """
    return components.html(html, height=70)

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

    annul_key = f"annulled_{session_id}"
    expired_key = f"expired_{session_id}"
    if annul_key not in st.session_state: st.session_state[annul_key] = False
    if expired_key not in st.session_state: st.session_state[expired_key] = False

    ac_data = anticheat_timer_component(student_name.strip(), session_id)

    if ac_data and isinstance(ac_data, dict):
        ev = ac_data.get("event_type","")
        if ev == "autosave":
            draft_text = ac_data.get("draft_text", "")
            upsert_live_draft(student_name.strip(), session_id, draft_text)
        elif ev not in ("start",):
            save_anticheat(student_name.strip(), session_id, ev,
                           ac_data.get("blur_count",0), ac_data.get("paste_count",0),
                           ac_data.get("annulled",0))
        if ac_data.get("annulled",0): st.session_state[annul_key] = True
        if ac_data.get("timer_expired",0): st.session_state[expired_key] = True

    if st.session_state.get(annul_key, False):
        st.error("🚫 Жұмысыңыз аннулирленді. Мұғалімге хабарланды.")
        st.stop()

    anticheat_active = True
elif not student_name.strip():
    st.info("Алдымен аты-жөніңізді және тапсырма суретін жүктеңіз.")

essay_text = ""
if anticheat_active:
    timer_done = st.session_state.get(f"expired_{session_id}", False)
    if timer_done:
        st.warning("⏰ Уақыт бітті! Жұмысыңызды жіберіңіз.")

    essay_text = st.text_area("", height=280,
        placeholder="Жауабыңызды осында теріңіз...",
        label_visibility="collapsed")

    if st.button("📤 Жіберу" if timer_done else "✅ Тексеруге жіберу",
                 type="primary", use_container_width=True):
        if not essay_text.strip():
            st.error("Жауап мәтінін жазыңыз!")
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
                with st.spinner("Жұмысыңыз тексерілуде..."):
                    result = json.loads(model.generate_content([prompt, image, essay_text]).text)
                    save_result(student_name.strip(), result)
                    delete_live_draft(session_id)
                st.markdown("---")
                st.success("✅ Жұмысыңыз сәтті тексерілді!")
                st.markdown(f"<h2 style='text-align:center;color:#1E88E5;'>🏆 Overall Band: {result['overall']}</h2>", unsafe_allow_html=True)
                c1,c2,c3,c4 = st.columns(4)
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
