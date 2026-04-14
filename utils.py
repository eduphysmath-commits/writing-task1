"""
utils.py — TEN IELTS ортақ модулі
"""
import re
import json
import time as _time
import streamlit as st
from supabase import create_client, Client


# ─────────────────────────────────────────
# SUPABASE
# ─────────────────────────────────────────

@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"],
    )


def get_latest_draft(session_id: str) -> dict | None:
    try:
        res = (
            get_supabase()
            .table("live_drafts")
            .select("*")
            .eq("session_id", session_id)
            .execute()
        )
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return None


def save_result(student_name: str, result: dict, session_id: str, task_type: str) -> None:
    """Нәтижені results кестесіне жазады. Сәтті болған соң ғана draft жояды."""
    try:
        ta_value = result.get("TA", result.get("TR", 0))
        get_supabase().table("results").insert({
            "student_name": student_name,
            "overall":      result["overall"],
            "ta":           ta_value,
            "cc":           result["CC"],
            "lr":           result["LR"],
            "gra":          result["GRA"],
            "main_errors":  result["main_errors"],
            "feedback":     result["feedback"],
            "task_type":    task_type,
        }).execute()
        # INSERT сәтті болса ғана draft жоямыз
        try:
            get_supabase().table("live_drafts").delete().eq("session_id", session_id).execute()
        except Exception:
            pass
    except Exception as e:
        st.warning(f"Сақтауда қате: {e}")


# ─────────────────────────────────────────
# УТИЛИТАЛАР
# ─────────────────────────────────────────

def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


# ─────────────────────────────────────────
# GEMINI RETRY
# ─────────────────────────────────────────

_RATE_KEYS   = ("429", "quota", "rate", "resource_exhausted")
_MAX_RETRIES = 5
_DELAYS      = [5, 10, 20, 30, 60]


def call_gemini_with_retry(model, contents: list) -> dict | None:
    last_err = None
    for attempt in range(_MAX_RETRIES):
        try:
            if attempt > 0:
                wait = _DELAYS[min(attempt - 1, len(_DELAYS) - 1)]
                st.info(f"⏳ Кезек күтілуде... {wait} сек ({attempt}/{_MAX_RETRIES})")
                _time.sleep(wait)
            raw    = model.generate_content(contents).text
            result = json.loads(clean_json(raw))
            return result
        except Exception as e:
            last_err = str(e)
            is_rate  = any(k in last_err.lower() for k in _RATE_KEYS)
            if not is_rate and attempt >= 1:
                break

    if last_err and any(k in last_err.lower() for k in _RATE_KEYS):
        st.error("⏳ Жүйе қазір бос емес. 1-2 минуттан кейін қайталаңыз.")
    elif last_err:
        st.error(f"Қате: {last_err}")
    return None


# ─────────────────────────────────────────
# НӘТИЖЕ БЕТІ
# ─────────────────────────────────────────

def show_result_page(result: dict, essay_text: str, task_type: str) -> None:
    is_t2       = task_type == "Task 2"
    first_label = "Task Response" if is_t2 else "Task Achievement"
    first_key   = "TR"            if is_t2 else "TA"

    st.success("✅ Жұмысыңыз сәтті тексерілді!")
    st.markdown(
        f"<h2 style='text-align:center;color:#1E88E5;'>"
        f"🏆 Overall Band: {result.get('overall','—')}</h2>",
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(first_label,  result.get(first_key, "—"))
    c2.metric("Coherence",  result.get("CC",  "—"))
    c3.metric("Lexical",    result.get("LR",  "—"))
    c4.metric("Grammar",    result.get("GRA", "—"))

    st.markdown("---")
    st.subheader("🛠 Жіберілген қателер")
    for e in result.get("main_errors", []):
        st.warning(f"• {e}")

    st.subheader("📝 Пікір")
    st.markdown(result.get("feedback", ""))

    if essay_text:
        st.markdown("---")
        st.subheader("📋 Жазған мәтініңіз")
        st.text_area("", value=essay_text, height=220, disabled=True,
                     label_visibility="collapsed",
                     key=f"saved_{task_type.replace(' ','_')}")
        import streamlit.components.v1 as _c
        _c.html(f"""
        <button onclick="navigator.clipboard.writeText({json.dumps(essay_text)}).then(()=>{{
            this.textContent='✅ Көшірілді!';this.style.background='#639922';
            setTimeout(()=>{{this.textContent='📋 Мәтінді көшіру';
            this.style.background='#1E88E5';}},2500);}})"
        style="width:100%;padding:10px;background:#1E88E5;color:#fff;
               border:none;border-radius:8px;font-size:14px;cursor:pointer;margin-top:4px;">
            📋 Мәтінді көшіру
        </button>""", height=55)


# ─────────────────────────────────────────
# WRITING COMPONENT HTML/JS
# ─────────────────────────────────────────

def build_writing_html(
    student_name: str,
    session_id:   str,
    sb_url:       str,
    sb_key:       str,
    total_seconds: int,
    min_words:     int,
    height:        int,
    teacher_name:  str = "Айнұр ұстазға",
) -> str:
    timer_init = f"{total_seconds // 60:02d}:00"
    return f"""
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:sans-serif;}}
body{{background:transparent;}}
#top-bar{{
  display:flex;align-items:center;justify-content:space-between;
  gap:8px;margin-bottom:10px;
}}
#timer-box{{
  background:#EAF3DE;border:1.5px solid #639922;
  border-radius:12px;padding:7px 16px;
  text-align:center;min-width:90px;flex-shrink:0;
  transition:background .5s,border-color .5s;
}}
#timer-label{{font-size:10px;color:#3B6D11;text-transform:uppercase;margin-bottom:1px;}}
#timer-display{{font-size:22px;font-weight:600;color:#27500A;letter-spacing:1px;}}
#timer-box.yellow{{background:#FAEEDA;border-color:#EF9F27;}}
#timer-box.yellow #timer-label{{color:#854F0B;}}
#timer-box.yellow #timer-display{{color:#633806;}}
#timer-box.red{{background:#FCEBEB;border-color:#E24B4A;}}
#timer-box.red #timer-label{{color:#A32D2D;}}
#timer-box.red #timer-display{{color:#501313;}}
#timer-box.done{{background:#F09595;border-color:#E24B4A;animation:pulse 1s ease-in-out infinite;}}
@keyframes pulse{{0%,100%{{transform:scale(1);}}50%{{transform:scale(1.04);}}}}
#ac-bar{{
  padding:10px 16px;border-radius:8px;flex:1;
  background:#EAF3DE;border-left:4px solid #639922;
  font-size:13px;color:#3B6D11;
  display:flex;align-items:center;gap:8px;transition:all .3s;
}}
.ac-dot{{width:10px;height:10px;border-radius:50%;background:#639922;flex-shrink:0;}}
#essay-box{{
  width:100%;height:{height}px;
  border:1px solid #ddd;border-radius:8px;
  padding:12px;font-size:15px;line-height:1.6;
  resize:vertical;outline:none;
  transition:border-color .3s;
  color:#333;background:white;
}}
#essay-box:focus{{border-color:#639922;}}
#essay-box:disabled{{background:#f5f5f5;color:#888;cursor:not-allowed;}}
#bottom-bar{{display:flex;justify-content:space-between;align-items:center;margin-top:8px;}}
#word-count{{font-size:12px;font-weight:500;color:#A32D2D;}}
#save-status{{font-size:11px;color:#aaa;}}
#teacher-btn{{
  padding:5px 12px;background:transparent;
  border:1px solid #ddd;border-radius:6px;
  font-size:12px;color:#555;cursor:pointer;
}}
/* Overlay — submit кезінде */
#ov{{
  display:none;position:fixed;inset:0;z-index:99999;
  background:rgba(255,255,255,.93);
  flex-direction:column;align-items:center;justify-content:center;gap:14px;
}}
#ov.show{{display:flex;}}
.sp{{
  width:42px;height:42px;border:4px solid #ddd;
  border-top-color:#639922;border-radius:50%;
  animation:spin .8s linear infinite;
}}
@keyframes spin{{to{{transform:rotate(360deg);}}}}
#ov-msg{{font-size:15px;font-weight:500;color:#27500A;text-align:center;padding:0 20px;}}
</style>

<div id="ov"><div class="sp"></div><div id="ov-msg">Сақталуда...</div></div>

<div id="top-bar">
  <div id="ac-bar">
    <div class="ac-dot" id="ac-dot"></div>
    <span id="ac-text">Античит белсенді — жұмысты адал орындаңыз</span>
  </div>
  <div id="timer-box">
    <div id="timer-label">Уақыт</div>
    <div id="timer-display">{timer_init}</div>
  </div>
</div>
<textarea id="essay-box" placeholder="Жауабыңызды осында теріңіз..."></textarea>
<div id="bottom-bar">
  <span id="word-count">0 сөз</span>
  <div style="display:flex;align-items:center;gap:8px;">
    <span id="save-status"></span>
    <button id="teacher-btn">👁 {teacher_name} көрсету</button>
  </div>
</div>

<script>
(function(){{
  const STUDENT  = {json.dumps(student_name)};
  const SESSION  = {json.dumps(session_id)};
  const SB_URL   = {json.dumps(sb_url)};
  const SB_KEY   = {json.dumps(sb_key)};
  const TOTAL    = {total_seconds};
  const MIN_W    = {min_words};
  const AS_MS    = 30000; // автосақтау интервалы

  let blurCnt=0, pasteCnt=0, annulled=false;
  let started=false, left=TOTAL, timerID=null, expired=false;
  let inserted=false, submitting=false;
  let aCtx=null, aOsc=null, aGain=null;
  let tBtnActive=false, asID=null;

  const tBox  = document.getElementById('timer-box');
  const tDisp = document.getElementById('timer-display');
  const dot   = document.getElementById('ac-dot');
  const acTxt = document.getElementById('ac-text');
  const bar   = document.getElementById('ac-bar');
  const essay = document.getElementById('essay-box');
  const wcEl  = document.getElementById('word-count');
  const saveEl= document.getElementById('save-status');
  const ov    = document.getElementById('ov');
  const ovMsg = document.getElementById('ov-msg');

  const H = {{
    'apikey': SB_KEY,
    'Authorization': 'Bearer '+SB_KEY,
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal'
  }};

  /* ── Supabase upsert ── */
  async function upsert(text, wc) {{
    const now = new Date().toISOString();
    try {{
      if (!inserted) {{
        // Ескі жазбаны алдымен жою (қайталанбасын)
        await fetch(SB_URL+'/rest/v1/live_drafts?session_id=eq.'+encodeURIComponent(SESSION),
          {{method:'DELETE', headers:H}});
        const r = await fetch(SB_URL+'/rest/v1/live_drafts',
          {{method:'POST', headers:H,
            body:JSON.stringify({{
              student_name:STUDENT, session_id:SESSION,
              draft_text:text, word_count:wc, submitted:0
            }})}});
        if (r.ok||r.status===201) inserted=true;
        return r.ok||r.status===201;
      }} else {{
        const r = await fetch(SB_URL+'/rest/v1/live_drafts?session_id=eq.'+encodeURIComponent(SESSION),
          {{method:'PATCH', headers:H,
            body:JSON.stringify({{draft_text:text, word_count:wc, updated_at:now}})}});
        return r.ok;
      }}
    }} catch(e) {{ return false; }}
  }}

  /* ── Автосақтау ── */
  let lastSavedText = '';
  function startAutoSave() {{
    if (asID) return;
    asID = setInterval(async ()=>{{
      const t = essay.value.trim();
      if (!t || annulled) return;
      if (t === lastSavedText) return; // мәтін өзгермесе — жібермейміз
      const wc = (t.match(/\b\w+\b/g)||[]).length;
      const ok = await upsert(t, wc);
      if (ok) lastSavedText = t;
      saveEl.textContent = ok
        ? '💾 '+new Date().toLocaleTimeString()
        : '⚠️ Желі қатесі';
    }}, AS_MS);
  }}

  // Бет жүктелгеннен 5 сек кейін автосақтауды бастаймыз —
  // таймер қосылмаса да, input болмаса да мәтін сақталады
  setTimeout(()=>startAutoSave(), 5000);

  /* ── Античит лог ── */
  async function logEv(ev) {{
    if (ev==='start') return;
    try {{
      await fetch(SB_URL+'/rest/v1/anticheat_events',
        {{method:'POST', headers:H,
          body:JSON.stringify({{
            student_name:STUDENT, session_id:SESSION,
            event_type:ev, blur_count:blurCnt,
            paste_count:pasteCnt,
            annulled:(ev==='annulled')?1:0
          }})}});
    }} catch(e) {{}}
  }}

  function setBar(msg,bg,bc,c,dc) {{
    bar.style.background=bg; bar.style.borderColor=bc;
    bar.style.color=c; dot.style.background=dc;
    acTxt.textContent=msg;
  }}

  /* ── Дыбыс ── */
  function startAlarm() {{
    if (left<TOTAL-600) return;
    try {{
      aCtx=new (window.AudioContext||window.webkitAudioContext)();
      aGain=aCtx.createGain(); aGain.gain.value=0.4;
      aGain.connect(aCtx.destination);
      function tone() {{
        if (!aCtx) return;
        aOsc=aCtx.createOscillator();
        aOsc.connect(aGain); aOsc.type='square';
        aOsc.frequency.setValueAtTime(880,aCtx.currentTime);
        aOsc.frequency.setValueAtTime(660,aCtx.currentTime+.3);
        aOsc.frequency.setValueAtTime(880,aCtx.currentTime+.6);
        aOsc.start(aCtx.currentTime);
        aOsc.stop(aCtx.currentTime+.9);
        aOsc.onended=()=>{{if(aCtx)tone();}};
      }}
      tone();
      setTimeout(()=>stopAlarm(), 3000);
    }} catch(e) {{}}
  }}
  function stopAlarm() {{
    try {{
      if (aOsc) {{aOsc.onended=null;aOsc.stop();aOsc=null;}}
      if (aCtx) {{aCtx.close();aCtx=null;}}
    }} catch(e) {{}}
  }}

  /* ── Аннулирлеу ── */
  function annul() {{
    annulled=true;
    if (timerID) clearInterval(timerID);
    if (asID)    clearInterval(asID);
    stopAlarm();
    essay.disabled=true;
    setBar('ЖҰМЫС АННУЛИРЛЕНДІ — мұғалімге хабарланды',
      '#F09595','#E24B4A','#501313','#E24B4A');
    tBox.className='done'; tDisp.textContent='XXX';
    logEv('annulled');
  }}

  /* ── Таймер ── */
  function fmt(s) {{
    return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');
  }}
  function startTimer() {{
    if (started) return;
    started=true;
    logEv('timer_start');
    startAutoSave();
    timerID=setInterval(()=>{{
      if (annulled) {{clearInterval(timerID);return;}}
      left--;
      tDisp.textContent=fmt(left);
      tBox.className=left<=0?'done':left<=60?'red':left<=300?'yellow':'';
      if (left===60) {{
        setBar('1 минут қалды! Жіберуге дайындалыңыз.',
          '#FAEEDA','#EF9F27','#854F0B','#EF9F27');
        logEv('timer_warning');
      }}
      if (left<=0) {{
        clearInterval(timerID); expired=true;
        tDisp.textContent='00:00';
        setBar('Уақыт бітті! Жұмысыңызды жіберіңіз.',
          '#FCEBEB','#E24B4A','#A32D2D','#E24B4A');
        logEv('timer_expired');
      }}
    }},1000);
  }}

  /* ── Blur ── */
  function onBlur() {{
    if (annulled||expired||submitting) return;
    blurCnt++;
    startAlarm();
    if (blurCnt===1) {{
      setBar('Ескерту! Басқа бетке өтпеңіз! (1/3)',
        '#FAEEDA','#EF9F27','#854F0B','#EF9F27');
      logEv('blur_1');
    }} else if (blurCnt===2) {{
      setBar('ҚАТАҢ ЕСКЕРТУ! Тағы бір рет шықсаңыз аннулирленеді! (2/3)',
        '#FCEBEB','#E24B4A','#A32D2D','#E24B4A');
      logEv('blur_2');
    }} else {{ annul(); }}
  }}
  function onFocus() {{ stopAlarm(); }}

  /* ── Мұғалімге жіберу ── */
  async function sendToTeacher() {{
    const t = essay.value.trim();
    if (!t) {{alert('Алдымен мәтін жазыңыз!');return;}}
    tBtnActive=true;
    setTimeout(()=>{{tBtnActive=false;}},2000);
    const wc=(t.match(/\b\w+\b/g)||[]).length;
    const btn=document.getElementById('teacher-btn');
    btn.disabled=true; btn.textContent='⏳ Жіберілуде...';
    const ok=await upsert(t,wc);
    if (ok) {{
      btn.textContent='✅ Жіберілді!';
      btn.style.cssText='background:#EAF3DE;color:#3B6D11;border-color:#639922;padding:5px 12px;border-radius:6px;font-size:12px;cursor:pointer;';
      saveEl.textContent='💾 '+new Date().toLocaleTimeString();
    }} else {{
      btn.textContent='❌ Қате — қайта басыңыз';
    }}
    setTimeout(()=>{{
      btn.disabled=false;
      btn.textContent='👁 {teacher_name} көрсету';
      btn.style.cssText='';
    }},3000);
  }}

  /* ── Submit: міндетті сақтау ──
     Streamlit "Тексеруге жіберу" батырмасы басылғанда Python submitDraft()
     деп іздемейді — submit тікелей жасалады.
     Бірақ submit алдында Streamlit app.py 3 сек күтеді (st.sleep(3)) —
     сол уақытта соңғы автосақтау жетеді.
     Сенімділік үшін submit_hook арқылы мәтінді алдын-ала жазамыз. */
  window.forceSave = async function() {{
    const t = essay.value.trim();
    if (!t) return false;
    ov.classList.add('show');
    ovMsg.textContent='💾 Жұмысыңыз сақталуда...';
    submitting=true;
    const wc=(t.match(/\b\w+\b/g)||[]).length;
    let ok=false;
    for (let i=0;i<4;i++) {{
      ok=await upsert(t,wc);
      if (ok) break;
      await new Promise(r=>setTimeout(r,1000));
    }}
    if (ok) {{
      ovMsg.textContent='✅ Сақталды! Тексерілуде...';
      saveEl.textContent='💾 '+new Date().toLocaleTimeString();
      await new Promise(r=>setTimeout(r,600));
    }} else {{
      ovMsg.textContent='❌ Сақтау сәтсіз! Интернетті тексеріп қайталаңыз.';
      await new Promise(r=>setTimeout(r,3500));
      submitting=false;
    }}
    ov.classList.remove('show');
    return ok;
  }};

  /* ── Textarea: input/keyup/change барлығы таймер қосады ── */
  function onTextChange() {{
    const words=(essay.value.match(/\b\w+\b/g)||[]).length;
    wcEl.textContent=words+' сөз';
    wcEl.style.color=words>=MIN_W?'#3B6D11':words>=Math.round(MIN_W*.6)?'#854F0B':'#A32D2D';
    if (!started&&!annulled&&words>0) startTimer();
  }}
  essay.addEventListener('input',  onTextChange);
  essay.addEventListener('keyup',  onTextChange);
  essay.addEventListener('change', onTextChange);

  essay.addEventListener('paste',(e)=>{{
    e.preventDefault(); // paste мүлде жұмыс істемейді
    if (annulled) return;
    pasteCnt++;
    setBar('⛔ Мәтін қою тыйым салынған!',
      '#FCEBEB','#E24B4A','#A32D2D','#E24B4A');
    logEv('paste');
    setTimeout(()=>{{
      if (!started&&!annulled&&essay.value.trim()) startTimer();
    }},150);
  }});

  // Тек visibilitychange — шынымен басқа бетке өткенде ғана blur саналады.
  // window blur алынып тасталды: scroll, бос жер басу, submit батырмасы —
  // бұлардың барлығы blur тудырып, оқушыны әділетсіз жазалап жатқан.
  document.addEventListener('visibilitychange',()=>{{
    if (document.hidden) {{
      if (tBtnActive||submitting) return;
      onBlur();
    }} else onFocus();
  }});
  window.addEventListener('focus', onFocus);
  document.getElementById('teacher-btn').addEventListener('click', sendToTeacher);
}})();
</script>
"""
