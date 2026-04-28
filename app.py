"""
╔══════════════════════════════════════════════════════════════╗
║  SIA v5.0 — Telugu AI COMPANION                             ║
║  Not just a chatbot. A companion.                           ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, json, re, base64, datetime, asyncio
import threading, random
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq

try:
    import psutil
except:
    psutil = None

try:
    import requests
except:
    requests = None

try:
    import speech_recognition as sr
except:
    sr = None

try:
    from duckduckgo_search import DDGS
except:
    DDGS = None

try:
    from PIL import Image
    import io
except:
    Image = None
    io = None

st.set_page_config(page_title="SIA — Telugu AI Companion", page_icon="🕉️", layout="centered")

GROQ_API_KEY   = st.secrets.get("GROQ_API_KEY",   "your-groq-key")
SARVAM_API_KEY = st.secrets.get("SARVAM_API_KEY", "your-sarvam-key")
client         = Groq(api_key=GROQ_API_KEY)
CHAT_MODEL     = "llama3-8b-8192"
VISION_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"

MEMORY_FILE    = "sia_memory.json"
COUNTER_FILE   = "sia_counter.json"
HABITS_FILE    = "sia_habits.json"
EMERGENCY_FILE = "sia_emergency.json"

IS_ADMIN = st.query_params.get("admin","") == "true"

# ── Security ──
BLOCKED = ["ignore previous","ignore all","you are now","forget instructions",
           "new instructions","system prompt","reveal prompt","jailbreak","pretend you are"]

def is_safe(text): return not any(b in text.lower() for b in BLOCKED)

def check_rate_limit():
    count = st.session_state.get("msg_count",0)
    if count > 50: st.error("చాలా messages! కొంత సేపు ఆగండి 🙏"); return False
    st.session_state.msg_count = count+1; return True

# ── Counter ──
def load_counter():
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f: return json.load(f)
    return {"total_users":0,"total_messages":0,"daily":{},"dialects":{},"emotions":{}}

def save_counter(d):
    with open(COUNTER_FILE,"w") as f: json.dump(d,f)

def increment_counter(new_session=False,dialect="unknown",emotion="neutral"):
    d=load_counter(); d["total_messages"]+=1
    today=datetime.datetime.now().strftime("%Y-%m-%d")
    d["daily"][today]=d["daily"].get(today,0)+1
    if new_session: d["total_users"]+=1
    d["dialects"][dialect]=d["dialects"].get(dialect,0)+1
    d["emotions"][emotion]=d["emotions"].get(emotion,0)+1
    save_counter(d); return d

# ── Memory ──
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE,"r",encoding="utf-8") as f: return json.load(f)
    return {"sessions":[],"user_profile":{},"habits":[],"reminders":[]}

def save_full_memory(mem):
    with open(MEMORY_FILE,"w",encoding="utf-8") as f: json.dump(mem,f,ensure_ascii=False,indent=2)

def update_user_profile(key,value):
    mem=load_memory(); mem["user_profile"][key]=value
    mem["user_profile"]["last_seen"]=datetime.datetime.now().isoformat()
    save_full_memory(mem)

def save_session(title,messages):
    mem=load_memory()
    mem["sessions"].append({"id":datetime.datetime.now().isoformat(),"title":title,
        "date":datetime.datetime.now().strftime("%d %B %Y %I:%M %p"),"messages":messages[-20:]})
    mem["sessions"]=mem["sessions"][-30:]; save_full_memory(mem)

def get_memory_context():
    mem=load_memory(); ctx=""
    if mem.get("user_profile"):
        ctx+="\n\nUSER PROFILE:\n"
        for k,v in mem["user_profile"].items():
            if k!="last_seen": ctx+=f"  {k}: {v}\n"
    if mem.get("sessions"):
        ctx+="\nRECENT CHATS:\n"
        for s in mem["sessions"][-3:]:
            ctx+=f"  [{s['date'][:11]} — {s['title']}]\n"
            for m in s["messages"][-2:]:
                role="User" if m["role"]=="user" else "SIA"
                ctx+=f"    {role}: {m['content'][:80]}\n"
    return ctx

def auto_title(messages):
    if len(messages)<2: return "Quick Chat"
    snippet=" | ".join([m["content"][:50] for m in messages[:4]])
    try:
        r=client.chat.completions.create(model=CHAT_MODEL,
            messages=[{"role":"user","content":f"4-word title: {snippet}. Title only."}],max_tokens=15)
        return r.choices[0].message.content.strip()
    except: return datetime.datetime.now().strftime("%d %b %H:%M")

# ── Habit Tracker + Future Predictor ──
def load_habits():
    if os.path.exists(HABITS_FILE):
        with open(HABITS_FILE) as f: return json.load(f)
    return {"entries":[]}

def save_habits(d):
    with open(HABITS_FILE,"w") as f: json.dump(d,f,ensure_ascii=False)

def log_habit(emotion,activity,hour):
    d=load_habits()
    d["entries"].append({"emotion":emotion,"activity":activity[:50],"hour":hour,
        "day":datetime.datetime.now().strftime("%A"),"date":datetime.datetime.now().strftime("%Y-%m-%d")})
    d["entries"]=d["entries"][-200:]; save_habits(d)

def predict_future(messages):
    d=load_habits()
    if len(d["entries"])<5: return ""
    hour=datetime.datetime.now().hour; day=datetime.datetime.now().strftime("%A"); preds=[]
    stress_hours=[e["hour"] for e in d["entries"] if e["emotion"] in ["anxious","sad","lost"]]
    lazy_hours=[e["hour"] for e in d["entries"] if e["emotion"]=="lazy"]
    if stress_hours.count(hour)>=2: preds.append(f"⚠️ Pattern: మీరు {hour}:00 కి stressed అవుతారు. ఇప్పుడు break తీసుకోండి.")
    if lazy_hours.count(hour)>=2: preds.append(f"📚 Pattern: ఈ సమయంలో distracted అవుతారు. ఇప్పుడే 10 నిమిషాలు చదవండి!")
    recent=" ".join([m["content"] for m in messages[-10:]])
    if any(k in recent.lower() for k in ["exam","test","పరీక్ష","interview"]): preds.append("🎯 Exam/Interview mentioned. Start revision today!")
    return "\n".join(preds[:2])

# ── Dialect Engine ──
DIALECTS={
    "rayalaseema":{"triggers":["ఏంది","గని","చేత్తాండు","బిడ్డా","kadapa","kurnool","anantapur"],"slang":["గని","ఏంది","బిడ్డా","సర్లే గని"],"example":"ఏంది బ్రో! సర్లే గని!"},
    "godavari":   {"triggers":["గదరా","అంట","ఏంటే","అవునంట","ఒరేయ్","rajahmundry","kakinada","vizag"],"slang":["గదరా","అంట","సర్దా","ఒరేయ్"],"example":"అవునా బ్రో గదరా!"},
    "hyderabadi": {"triggers":["క్యా","యార్","బోలో","కర్తే","hyderabad","bhai","భాయ్"],"slang":["యార్","క్యా","బోలో","భాయ్"],"example":"అరే యార్! క్యా బాత్ హై!"},
    "telangana":  {"triggers":["ఏంరా","సర్లే రా","అట్లనే","మామా","warangal","nizamabad"],"slang":["రా","సర్లే","మామా","అట్లనే"],"example":"సర్లే రా మామా!"}
}

def detect_dialect(text):
    tl=text.lower(); scores={d:0 for d in DIALECTS}
    for d,data in DIALECTS.items():
        for t in data["triggers"]:
            if t.lower() in tl: scores[d]+=1
    best=max(scores,key=scores.get)
    return best if scores[best]>0 else "neutral"

# ── Emotion Engine ──
EMOTIONS={
    "anxious":  ["tension","exam","nervous","scared","fear","భయం","stress","ఒత్తిడి","worried"],
    "sad":      ["sad","crying","lonely","alone","hurt","pain","దుఃఖం","ఏడుపు","miss","depressed"],
    "excited":  ["happy","excited","great","amazing","wow","సంతోషం","yayyy","చాలా బాగుంది"],
    "lazy":     ["bore","బోర్","sleep","నిద్ర","tired","waste","youtube","instagram","netflix","పడుకున్న"],
    "lost":     ["don't know","తెలియడం లేదు","confused","ఏం చేయాలి","help","lost","no idea"],
    "motivated":["let's go","చేద్దాం","ready","start","study","work","hustle","నేను చేయగలను"],
    "sick":     ["sick","ill","fever","జ్వరం","unwell","pain","headache","నొప్పి","medicine"],
    "lonely":   ["alone","nobody","miss","loneliness","ఒంటరిగా","no friends"]
}

def detect_emotion(text):
    tl=text.lower()
    for emotion,kws in EMOTIONS.items():
        if any(k in tl for k in kws): return emotion
    return "neutral"

def detect_voice_mode(text):
    tl=text.lower()
    if any(k in tl for k in ["అమ్మమ్మ","నాన్నమ్మ","grandma","traditional","slow"]): return "grandma"
    if any(k in tl for k in ["genz","cool","bro","lit","vibe","పక్కా"]): return "genz"
    return st.session_state.get("voice_mode","normal")

# ── Cultural DB ──
STORIES={
    "ramayana":    "రామాయణం: రాముడు సీతను రావణుడి నుండి రక్షించాడు. ధర్మం నెగ్గింది.",
    "mahabharata": "మహాభారతం: కృష్ణుడు అర్జునుడికి భగవద్గీత చెప్పాడు. కర్మ యోగం.",
    "bhagavatgita":"గీత సారం: కర్మ చేయి ఫలితం ఆశించకు. ఆత్మ అమరం."
}

DEVOTIONAL={
    "గణేశుడు":    {"mantra":"ఓం గం గణపతయే నమః","stotra":"వక్రతుండ మహాకాయ సూర్యకోటి సమప్రభ","time":"బుధవారం"},
    "వెంకటేశ్వర": {"mantra":"ఓం నమో వేంకటేశాయ","stotra":"కౌసల్యా సుప్రజా రామ","time":"శుక్రవారం"},
    "శివుడు":     {"mantra":"ఓం నమః శివాయ","stotra":"కర్పూరగౌరం కరుణావతారం","time":"సోమవారం"},
    "లక్ష్మీదేవి": {"mantra":"ఓం శ్రీం మహాలక్ష్మ్యై నమః","stotra":"నమస్తేస్తు మహామాయే","time":"శుక్రవారం"},
    "సరస్వతి":   {"mantra":"ఓం ఐం సరస్వత్యై నమః","stotra":"యా కుందేందు తుషారహారధవళా","time":"విద్యారంభం"}
}

INTERNSHIP_TARGETS=[
    {"company":"Sarvam AI",    "role":"Indic AI Intern",   "email":"careers@sarvam.ai"},
    {"company":"AI4Bharat",    "role":"Research Intern",   "email":"ai4bharat.org/contact"},
    {"company":"Gnani.ai",     "role":"NLP Engineer",      "email":"careers@gnani.ai"},
    {"company":"Krutrim (Ola)","role":"AI Engineer",       "email":"krutrim.com/careers"},
    {"company":"Reverie Tech", "role":"Indic AI Engineer", "email":"careers@reverieinc.com"},
    {"company":"Sprinklr",     "role":"AI Engineer",       "email":"sprinklr.com/careers"},
    {"company":"Microsoft India","role":"Research Intern", "email":"careers.microsoft.com"},
    {"company":"Google India", "role":"STEP Intern",       "email":"careers.google.com"},
]

KNOWLEDGE_BITES=[
    "💡 తెలుగు భాష 2,000+ సంవత్సరాల పురాతనమైనది!",
    "💡 Sarvam AI — India's first full-stack Indic language AI company.",
    "💡 IndicWhisper — IIT Madras built Telugu speech recognition model.",
    "💡 అన్నమయ్య 32,000+ కీర్తనలు రాశాడు — world record!",
    "💡 Telugu is the fastest growing Indian language on the internet.",
    "💡 AI4Bharat built IndicBERT — multilingual model for 12 Indian languages.",
    "💡 82 million people speak Telugu worldwide.",
    "💡 Groq LLaMA3 is currently the world's fastest LLM inference engine.",
]

# ── Web Search ──
def search_web(query,n=3):
    if not DDGS: return ""
    try:
        with DDGS() as ddgs:
            results=ddgs.text(query,max_results=n)
            return " ".join([r["body"] for r in results])[:800]
    except: return ""

def get_panchangam():
    today=datetime.datetime.now().strftime("%B %d %Y")
    return search_web(f"Telugu panchangam today {today} nakshatra tithi rahukalam festival")

def get_realtime_sky():
    try:
        import ephem
        now=ephem.now(); obs=ephem.Observer()
        obs.lat="17.3850"; obs.lon="78.4867"; obs.date=now
        NAKS=["అశ్విని","భరణి","కృత్తిక","రోహిణి","మృగశిర","ఆర్ద్ర","పునర్వసు","పుష్యమి","ఆశ్లేష","మఖ","పుబ్బ","ఉత్తర","హస్త","చిత్త","స్వాతి","విశాఖ","అనూరాధ","జ్యేష్ఠ","మూల","పూర్వాషాఢ","ఉత్తరాషాఢ","శ్రవణం","ధనిష్ఠ","శతభిష","పూర్వాభాద్ర","ఉత్తరాభాద్ర","రేవతి"]
        RASIS=["మేషం","వృషభం","మిథునం","కర్కాటకం","సింహం","కన్య","తుల","వృశ్చికం","ధనుస్సు","మకరం","కుంభం","మీనం"]
        bodies={"☀️ సూర్యుడు":ephem.Sun(),"🌙 చంద్రుడు":ephem.Moon(),"🔴 కుజుడు":ephem.Mars(),"⚡ బుధుడు":ephem.Mercury(),"🟡 గురుడు":ephem.Jupiter(),"✨ శుక్రుడు":ephem.Venus(),"🪐 శని":ephem.Saturn()}
        result=f"🌌 లైవ్ గ్రహ స్థితులు — {datetime.datetime.now().strftime('%I:%M %p')}\n\n"
        for name,body in bodies.items():
            body.compute(obs); ra=float(body.ra)*180/3.14159265
            nak=int((ra/360)*27)%27; ras=int((ra/360)*12)%12
            alt=float(body.alt)*180/3.14159265
            vis="కనిపిస్తోంది 👁️" if alt>0 else "క్షితిజం కింద"
            result+=f"  {name}: {RASIS[ras]} · {NAKS[nak]} · {vis}\n"
        moon=ephem.Moon(now); moon.compute(obs); p=moon.phase
        phase="అమావాస్య 🌑" if p<10 else ("శుక్ల పక్షం 🌒" if p<45 else ("పౌర్ణమి 🌕" if p<55 else "కృష్ణ పక్షం 🌘"))
        result+=f"\n🌙 చంద్ర దశ: {phase} ({p:.1f}%)"
        return result
    except: return search_web("planet positions Vedic astrology today nakshatra Telugu")

# ── Battery ──
def get_battery():
    if not psutil: return (None,None)
    b=psutil.sensors_battery()
    return (b.percent,b.power_plugged) if b else (None,None)

def battery_alert():
    p,plugged=get_battery()
    if p and p<20 and not plugged: return f"URGENT: Battery {p}%! చార్జ్ పెట్టండి!"
    return ""

# ── Emergency ──
def load_emergency():
    if os.path.exists(EMERGENCY_FILE):
        with open(EMERGENCY_FILE) as f: return json.load(f)
    return {"contacts":[],"medicines":[]}

def check_medicine_reminder():
    em=load_emergency()
    if not em["medicines"]: return ""
    now=datetime.datetime.now(); alerts=[]
    for med in em["medicines"]:
        if now.hour==int(med.get("hour",8)) and now.minute<30:
            alerts.append(f"💊 {med['name']} తీసుకున్నారా?")
    return "\n".join(alerts)

# ── Mini Tools ──
def analyze_resume(text):
    try:
        r=client.chat.completions.create(model=CHAT_MODEL,
            messages=[{"role":"user","content":f"Analyze resume in Telugu. 3 strengths + 3 improvements:\n{text[:2000]}"}],
            max_tokens=300)
        return r.choices[0].message.content
    except: return "Resume విశ్లేషణ చేయలేకపోయాను."

def solve_doubt(question):
    try:
        r=client.chat.completions.create(model=CHAT_MODEL,
            messages=[{"role":"user","content":f"Solve student doubt simply in Telugu with example:\n{question}"}],
            max_tokens=250)
        return r.choices[0].message.content
    except: return "Doubt solve చేయలేకపోయాను."

# ── Voice ──
def sarvam_speak(text,voice="arvind"):
    try:
        clean=re.sub(r'[*_`#\[\]()]','',text)[:500]
        resp=requests.post("https://api.sarvam.ai/text-to-speech",
            json={"inputs":[clean],"target_language_code":"te-IN","speaker":voice,
                  "speech_sample_rate":22050,"enable_preprocessing":True,"model":"bulbul:v1"},
            headers={"api-subscription-key":SARVAM_API_KEY,"Content-Type":"application/json"},timeout=15)
        if resp.status_code==200:
            audio=base64.b64decode(resp.json()["audios"][0])
            with open("sia_voice.wav","wb") as f: f.write(audio)
            os.system("start sia_voice.wav" if os.name=="nt" else "aplay sia_voice.wav 2>/dev/null")
            return True
    except: pass
    return False

async def edge_async(text):
    try:
        import edge_tts
        await edge_tts.Communicate(re.sub(r'[*_`#]','',text),voice="te-IN-ShrutiNeural").save("sia_voice.mp3")
    except: pass

def fallback_speak(text):
    asyncio.run(edge_async(text))
    os.system("start sia_voice.mp3" if os.name=="nt" else "mpg123 sia_voice.mp3 2>/dev/null")

def speak(text,voice="arvind"):
    if not sarvam_speak(text,voice): fallback_speak(text)

def listen(timeout=8):
    if not sr: return ""
    r=sr.Recognizer(); r.energy_threshold=300; r.dynamic_energy_threshold=True
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source,duration=1)
        try:
            audio=r.listen(source,timeout=timeout,phrase_time_limit=20)
            try: return r.recognize_google(audio,language="te-IN")
            except: return r.recognize_google(audio,language="en-IN")
        except: return ""

def analyze_image(image_bytes,question):
    b64=base64.standard_b64encode(image_bytes).decode()
    try:
        r=client.chat.completions.create(model=VISION_MODEL,
            messages=[{"role":"user","content":[
                {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}},
                {"type":"text","text":f"Analyze. Question: {question}\nReply in Telugu."}
            ]}],max_tokens=600)
        return r.choices[0].message.content
    except Exception as e: return f"Image చదవడం కష్టం: {str(e)}"

# ── Intent Detection ──
def detect_intents(msg):
    m=msg.lower(); intents=[]
    if any(k in m for k in ["nakshatra","పంచాంగం","panchangam","rahukalam","festival","పండుగ","tithi"]): intents.append("panchangam")
    if any(k in m for k in ["planet","గ్రహం","star","rashi","రాశి","jupiter","saturn","moon","astrology"]): intents.append("sky")
    if any(k in m for k in ["mantra","మంత్రం","stotra","devotional","bhajan","కీర్తన","గణేశ","వెంకటేశ","శివ","లక్ష్మి","సరస్వతి"]): intents.append("devotional")
    if any(k in m for k in ["ramayana","రామాయణం","mahabharata","మహాభారత","gita","గీత","story","కథ"]): intents.append("story")
    if any(k in m for k in ["internship","job","career","company","apply","sarvam","ai4bharat"]): intents.append("career")
    if any(k in m for k in ["resume","cv","profile"]): intents.append("resume")
    if any(k in m for k in ["doubt","explain","solve","help me understand","అర్థం"]): intents.append("doubt")
    return intents

# ── System Prompt ──
def build_system(intents,dialect,emotion,voice_mode_val,messages,extra):
    now=datetime.datetime.now()
    hour=now.hour
    greet="శుభోదయం" if hour<12 else ("శుభ మధ్యాహ్నం" if hour<17 else "శుభ సాయంత్రం")

    dialect_slang=""
    if dialect in DIALECTS:
        dialect_slang="Use: "+", ".join(DIALECTS[dialect]["slang"])

    voice_map={"grandma":"Speak slowly, respectfully. Use అమ్మా నాయనా.","genz":"Cool Telugu+English. Use bro, lit, vibe.","normal":"Friendly Telugu."}

    emotion_map={"anxious":"Be calm, give 3 steps.","sad":"Be warm first, then advise.","excited":"Match energy!","lazy":"Call out lovingly, give 2-min challenge.","lost":"Give 3 clear steps.","motivated":"Fuel the energy!","sick":"Be caring, suggest remedy.","lonely":"Warm presence.","neutral":"Helpful and friendly."}

    prompt=f"""You are SIA — Telugu AI Companion. Smart, cultural, emotionally intelligent.
Time: {now.strftime('%I:%M %p')} · {greet}

ALWAYS reply in Telugu only.
Voice: {voice_map.get(voice_mode_val,'Friendly Telugu.')}
Dialect: {dialect} — {dialect_slang}
Emotion detected: {emotion} — {emotion_map.get(emotion,'')}

Be like a best friend. Max 3-4 lines. End with one clear action.
Remember past context naturally. Predict what user needs next.
Study coach: call out YouTube/Instagram/sleep waste lovingly.
Cultural: know festivals, mantras, panchangam, Telugu stories.

{extra[:500] if extra else ""}"""

    if "panchangam" in intents: prompt+=f"\nPanchangam: {get_panchangam()[:300]}"
    if "sky" in intents: prompt+=f"\nSky: {get_realtime_sky()[:300]}"
    return prompt

# ── Chat ──
def chat(user_msg,history,extra=""):
    dialect=detect_dialect(user_msg); emotion=detect_emotion(user_msg)
    intents=detect_intents(user_msg); vm=detect_voice_mode(user_msg)
    log_habit(emotion,user_msg[:50],datetime.datetime.now().hour)

    # Build simple short prompt
    now=datetime.datetime.now()
    hour=now.hour
    greet="శుభోదయం" if hour<12 else ("శుభ మధ్యాహ్నం" if hour<17 else "శుభ సాయంత్రం")
    dialect_slang=", ".join(DIALECTS[dialect]["slang"]) if dialect in DIALECTS else ""
    emotion_tips={"anxious":"calm and reassuring","sad":"warm and caring","excited":"energetic","lazy":"loving but firm","lost":"give clear steps","motivated":"fuel energy","neutral":"helpful"}

    system=f"You are SIA, a Telugu AI friend. Always reply in Telugu. {greet}! Dialect:{dialect} {dialect_slang}. Emotion:{emotion} - be {emotion_tips.get(emotion,'helpful')}. Max 3 lines. End with one action."

    # Add history (last 4 only)
    msgs=[{"role":"system","content":system}]
    for m in history[-4:]:
        msgs.append({"role":m["role"],"content":m["content"][:200]})
    msgs.append({"role":"user","content":user_msg[:500]})

    try:
        r=client.chat.completions.create(
            model=CHAT_MODEL,
            messages=msgs,
            max_tokens=200,
            temperature=0.85
        )
        reply=r.choices[0].message.content
    except Exception as e:
        reply=f"సియా ఇప్పుడు busy గా ఉంది. మళ్ళీ try చేయండి! 🙏"

    increment_counter(dialect=dialect,emotion=emotion)
    return reply,dialect,emotion,vm

# ══════════════════════════════════════════
#  UI
# ══════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tiro+Telugu&family=Outfit:wght@300;400;600;700&display=swap');
:root{--s:#FF6B35;--g:#FFD700;--d:#06040E;--c:#0E0C18;--b:#1C1828;--t:#F0EAF8;--m:#6A5A8A;}
html,body,[class*="css"]{background:var(--d)!important;color:var(--t)!important;font-family:'Outfit',sans-serif!important;}
.sia-wrap{text-align:center;padding:2rem 0 .5rem;}
.sia-om{font-size:2.2rem;display:block;animation:breathe 4s ease-in-out infinite;}
@keyframes breathe{0%,100%{transform:scale(1);opacity:1;}50%{transform:scale(1.15);opacity:.7;}}
.sia-name{font-family:'Tiro Telugu',serif;font-size:3.5rem;background:linear-gradient(135deg,var(--s),var(--g),#ff9966,var(--s));background-size:300%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:shimmer 5s linear infinite;letter-spacing:8px;}
@keyframes shimmer{0%{background-position:0%}100%{background-position:300%}}
.sia-sub{color:var(--m);font-size:.72rem;letter-spacing:3px;text-transform:uppercase;}
.companion-tag{display:inline-block;background:linear-gradient(135deg,#1a0a2a,#2a1040);border:1px solid #FF6B3533;border-radius:20px;padding:4px 16px;font-size:.62rem;color:var(--s);letter-spacing:2px;margin-top:.4rem;}
.badge{display:inline-block;padding:3px 12px;border-radius:20px;font-size:.65rem;margin:2px;letter-spacing:1px;}
.dialect-b{background:#1a1000;border:1px solid var(--s);color:var(--s);}
.emotion-b{background:#0a1a0a;border:1px solid #2a4a2a;color:#6aaa6a;}
.voice-b{background:#0a0a1a;border:1px solid #2a2a4a;color:#6a6aaa;}
.predict-card{background:linear-gradient(135deg,#0a0814,#140820);border:1px solid #FF6B3533;border-radius:12px;padding:.8rem 1rem;margin:.5rem 0;font-size:.75rem;color:var(--s);}
.kb-card{background:var(--c);border:1px solid var(--b);border-radius:10px;padding:.6rem 1rem;font-size:.72rem;color:#FF6B3588;margin-bottom:.5rem;}
[data-testid="stChatMessage"]{background:var(--c)!important;border:1px solid var(--b)!important;border-radius:16px!important;margin-bottom:.6rem!important;}
[data-testid="stChatInput"] textarea{background:var(--c)!important;border:1px solid var(--b)!important;color:var(--t)!important;border-radius:14px!important;}
.stButton>button{background:linear-gradient(135deg,var(--s),#aa3300)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;transition:all .2s!important;}
.stButton>button:hover{transform:scale(1.04)!important;}
[data-testid="stSidebar"]{background:#080614!important;border-right:1px solid var(--b)!important;}
.admin-box{background:linear-gradient(135deg,#0a0500,#150800);border:2px solid var(--s);border-radius:16px;padding:1.5rem;margin:1rem 0;}
hr{border-color:var(--b)!important;}
</style>
""",unsafe_allow_html=True)

st.markdown("""
<div class="sia-wrap">
  <span class="sia-om">🕉️</span>
  <div class="sia-name">SIA</div>
  <div class="sia-sub">స్మార్ట్ ఇండియన్ అసిస్టెంట్</div>
  <div class="companion-tag">✦ AI COMPANION · NOT JUST A CHATBOT ✦</div>
</div><hr>
""",unsafe_allow_html=True)

st.markdown(f'<div class="kb-card">{random.choice(KNOWLEDGE_BITES)}</div>',unsafe_allow_html=True)

# ── Admin Panel ──
if IS_ADMIN:
    stats=load_counter(); memory=load_memory(); percent,plugged=get_battery()
    st.markdown('<div class="admin-box">',unsafe_allow_html=True)
    st.markdown("### 🔐 Admin Panel — Only You See This")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("👥 Users",stats.get("total_users",0))
    c2.metric("💬 Messages",stats.get("total_messages",0))
    c3.metric("📚 Sessions",len(memory.get("sessions",[])))
    c4.metric("🔋 Battery",f"{percent}%" if percent else "N/A")
    if stats.get("emotions"):
        st.markdown("**Emotions:**")
        for e,cnt in stats["emotions"].items():
            if cnt>0: st.progress(min(cnt/max(stats["emotions"].values(),default=1),1.0),text=f"{e}: {cnt}")
    if stats.get("dialects"):
        st.markdown("**Dialects:**")
        for d,cnt in stats["dialects"].items():
            if cnt>0: st.progress(min(cnt/max(stats["dialects"].values(),default=1),1.0),text=f"{d}: {cnt}")
    if stats.get("daily"):
        days=list(stats["daily"].keys())[-7:]
        st.bar_chart({d:stats["daily"][d] for d in days})
    if st.button("🗑️ Clear All Data"):
        save_full_memory({"sessions":[],"user_profile":{},"habits":[],"reminders":[]})
        save_counter({"total_users":0,"total_messages":0,"daily":{},"dialects":{},"emotions":{}})
        st.success("Cleared!")
    st.markdown('</div>',unsafe_allow_html=True)

# ── Sidebar ──
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    voice_pref=st.selectbox("🗣️ Telugu Mode",["Normal","Grandma Mode","GenZ Mode"])
    st.session_state.voice_mode={"Normal":"normal","Grandma Mode":"grandma","GenZ Mode":"genz"}[voice_pref]
    sarvam_voice=st.selectbox("🔊 Voice",["arvind","amartya","diya","neel","maitreyi","pavithra"])
    auto_speak=st.toggle("Auto Speak",value=True)

    st.markdown("---")
    st.markdown("### 🎯 Career Opportunities")
    if st.button("Show All"):
        for t in INTERNSHIP_TARGETS:
            st.markdown(f"**{t['company']}** — {t['role']}\n{t['email']}")

    st.markdown("---")
    st.markdown("### 🌌 Live Sky")
    if st.button("🔭 Refresh"): st.session_state.sky=get_realtime_sky()
    if "sky" in st.session_state: st.code(st.session_state.sky,language=None)

    st.markdown("---")
    st.markdown("### 🧠 Memory")
    mem=load_memory()
    for s in reversed(mem.get("sessions",[])[-5:]):
        st.markdown(f"<div style='font-size:.65rem;color:#6A5A8A;padding:2px 0'>📌 {s['date'][:11]} — {s['title']}</div>",unsafe_allow_html=True)
    if st.button("🗑️ Clear Memory"):
        save_full_memory({"sessions":[],"user_profile":{},"habits":[],"reminders":[]}); st.success("Done!")

    st.markdown("---")
    st.markdown("### 💊 Medicine Reminder")
    med_name=st.text_input("Medicine")
    med_hour=st.number_input("Hour (24h)",0,23,8)
    if st.button("➕ Add Reminder") and med_name:
        em=load_emergency(); em["medicines"].append({"name":med_name,"hour":med_hour})
        with open(EMERGENCY_FILE,"w") as f: json.dump(em,f)
        st.success(f"Set for {med_name} at {med_hour}:00!")

    st.markdown("---")
    st.markdown("### 🕉️ Quick Mantras")
    deity=st.selectbox("Deity",list(DEVOTIONAL.keys()))
    if st.button("Show Mantra"):
        info=DEVOTIONAL[deity]
        st.markdown(f"**మంత్రం:** {info['mantra']}")
        st.markdown(f"**స్తోత్రం:** {info['stotra']}")
        st.caption(f"సమయం: {info['time']}")

    st.caption("SIA v5.0 · AI Companion · 8.8 CGPA")

# ── Session Init ──
if "messages" not in st.session_state:
    st.session_state.messages=[]; st.session_state.dialect="neutral"
    st.session_state.emotion="neutral"; st.session_state.voice_mode="normal"
    st.session_state.msg_count=0; st.session_state.active_tool=None
    increment_counter(new_session=True)
    now=datetime.datetime.now(); hour=now.hour
    greet="శుభోదయం" if hour<12 else ("శుభ మధ్యాహ్నం" if hour<17 else "శుభ సాయంత్రం")
    st.session_state.messages.append({"role":"assistant","content":
        f"{greet}! నేను సియా 🙏\n\n"
        f"మీ Telugu AI Companion — కేవలం chatbot కాదు, నిజమైన స్నేహితుడు.\n\n"
        f"అన్ని యాసలు · feelings · గతం · predictions — అన్నీ అర్థమవుతాయి!\n\n"
        f"💬 Type · 🎤 Mic · 📸 Photo · మాట్లాడు!"
    })

# ── Badges ──
d=st.session_state.get("dialect","neutral"); e=st.session_state.get("emotion","neutral"); vm=st.session_state.get("voice_mode","normal")
DNAMES={"rayalaseema":"🌶️ Rayalaseema","godavari":"🌊 Godavari","hyderabadi":"🏙️ Hyderabadi","telangana":"⭐ Telangana"}
ENAMES={"anxious":"😰 Anxious","sad":"💙 Sad","excited":"🔥 Excited","lazy":"😴 Lazy","lost":"🤔 Lost","motivated":"💪 Motivated","sick":"🤒 Sick","lonely":"💜 Lonely"}
VNAMES={"grandma":"👵 Grandma Mode","genz":"😎 GenZ Mode"}
badges=""
if d in DNAMES: badges+=f"<span class='badge dialect-b'>{DNAMES[d]}</span>"
if e in ENAMES: badges+=f"<span class='badge emotion-b'>{ENAMES[e]}</span>"
if vm in VNAMES: badges+=f"<span class='badge voice-b'>{VNAMES[vm]}</span>"
if badges: st.markdown(badges,unsafe_allow_html=True)

# ── Prediction Card ──
preds=predict_future(st.session_state.messages)
if preds: st.markdown(f"<div class='predict-card'>🔮 <b>SIA Prediction:</b><br>{preds}</div>",unsafe_allow_html=True)

# ── Anti-gravity when bored ──
if st.session_state.get("emotion")=="lazy":
    try:
        with open("sia_antigravity_v4.html","r",encoding="utf-8") as f: components.html(f.read(),height=360)
    except: pass

# ── Chat History ──
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.write(msg["content"])

# ── Mini Tools ──
with st.expander("🧰 Mini AI Tools"):
    t1,t2,t3,t4=st.columns(4)
    with t1:
        if st.button("📊 Resume"): st.session_state.active_tool="resume"
    with t2:
        if st.button("🔭 Sky"): st.session_state.sky=get_realtime_sky(); st.session_state.active_tool="sky"
    with t3:
        if st.button("💡 Fact"): st.info(random.choice(KNOWLEDGE_BITES))
    with t4:
        if st.button("🎯 Jobs"): st.session_state.active_tool="jobs"

    if st.session_state.get("active_tool")=="resume":
        rt=st.text_area("Paste resume here:")
        if st.button("Analyze") and rt:
            with st.spinner("Analyzing..."): result=analyze_resume(rt)
            st.write(result); st.session_state.active_tool=None

    if st.session_state.get("active_tool")=="jobs":
        for t in INTERNSHIP_TARGETS:
            st.markdown(f"**{t['company']}** — {t['role']} — `{t['email']}`")
        st.session_state.active_tool=None

    if st.session_state.get("active_tool")=="sky" and "sky" in st.session_state:
        st.code(st.session_state.sky,language=None); st.session_state.active_tool=None

# ── Input ──
c1,c2=st.columns([1,1])
with c1: mic_btn=st.button("🎤 Speak",use_container_width=True)
with c2: save_btn=st.button("💾 Save",use_container_width=True)

user_input=st.chat_input("SIA తో మాట్లాడు... (Telugu or English)")
uploaded=st.file_uploader("📎 Photo / Document",type=["jpg","jpeg","png","webp"],label_visibility="visible")

if mic_btn:
    with st.spinner("🎤 వింటున్నాను..."): spoken=listen()
    if spoken: user_input=spoken; st.info(f"🎤 {spoken}")
    else: st.warning("వినలేదు — మళ్ళీ try చేయి")

if save_btn and len(st.session_state.messages)>2:
    title=auto_title(st.session_state.messages)
    save_session(title,st.session_state.messages); st.success(f"✅ Saved: '{title}'")

extra=""
if uploaded:
    img_bytes=uploaded.read(); st.image(Image.open(io.BytesIO(img_bytes)),use_container_width=True)
    q=user_input or "ఈ image లో ఏముంది? Telugu లో చెప్పు."
    with st.spinner("🔍 Image చదువుతున్నాను..."): extra=analyze_image(img_bytes,q)
    if not user_input: user_input="ఈ image గురించి చెప్పు"

if user_input:
    intents=detect_intents(user_input)
    if "doubt"  in intents: extra+=f"\nDOUBT:\n{solve_doubt(user_input)}"
    if "career" in intents: extra+="\nCAREER:\n"+"\n".join([f"{t['company']}: {t['role']} — {t['email']}" for t in INTERNSHIP_TARGETS])
    if "devotional" in intents:
        for deity,info in DEVOTIONAL.items():
            if deity.lower() in user_input.lower():
                extra+=f"\n{deity}: మంత్రం: {info['mantra']}\nస్తోత్రం: {info['stotra']}\nసమయం: {info['time']}"

    if not check_rate_limit(): st.stop()
    if not is_safe(user_input): st.warning("ఆ message పంపలేను. Normal గా మాట్లాడండి 🙏"); st.stop()

    st.session_state.messages.append({"role":"user","content":user_input})
    with st.chat_message("user"): st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("సియా ఆలోచిస్తోంది..."):
            reply,dialect,emotion,vm=chat(user_input,st.session_state.messages,extra)
            st.session_state.dialect=dialect; st.session_state.emotion=emotion; st.session_state.voice_mode=vm
            st.write(reply)
            st.session_state.messages.append({"role":"assistant","content":reply})

    if auto_speak:
        voice_map={"grandma":"pavithra","genz":"neel","normal":sarvam_voice}
        threading.Thread(target=speak,args=(reply,voice_map.get(vm,sarvam_voice)),daemon=True).start()

if len(st.session_state.messages)>0 and len(st.session_state.messages)%10==0:
    save_session(auto_title(st.session_state.messages),st.session_state.messages)
