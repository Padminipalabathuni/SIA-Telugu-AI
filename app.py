"""
SIA v7.0 — Telugu AI Companion
Complete Perfect Version
✅ Voice output (Sarvam + Edge TTS)
✅ Live sky / stars
✅ Anti-gravity when bored
✅ Memory with titles + user profile
✅ Asks name/age on first visit
✅ Image understanding (text in images)
✅ Dialect detection + slang
✅ Emotion detection + predictions
✅ Visual explainer
✅ Admin panel (secret)
✅ Never crashes
"""

import os, json, re, base64, datetime
import asyncio, threading, random
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq

try:    import psutil
except: psutil = None
try:    import requests
except: requests = None
try:    import speech_recognition as sr
except: sr = None
try:    from duckduckgo_search import DDGS
except: DDGS = None
try:    from PIL import Image; import io
except: Image = None; io = None

# ══════════════════════
#  CONFIG
# ══════════════════════
st.set_page_config(page_title="SIA — Telugu AI", page_icon="🕉️", layout="centered")

GROQ_API_KEY   = st.secrets.get("GROQ_API_KEY",   "")
SARVAM_API_KEY = st.secrets.get("SARVAM_API_KEY", "")
CHAT_MODEL     = "llama-3.3-70b-versatile"
VISION_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"

try:    client = Groq(api_key=GROQ_API_KEY)
except: client = None

MEMORY_FILE  = "sia_memory.json"
COUNTER_FILE = "sia_counter.json"
IS_ADMIN     = st.query_params.get("admin","") == "true"

# ══════════════════════
#  SECURITY
# ══════════════════════
BLOCKED = ["ignore previous","ignore all","you are now","forget instructions","jailbreak","pretend you are"]
def is_safe(t): return not any(b in t.lower() for b in BLOCKED)
def check_rate():
    c = st.session_state.get("msg_count",0)
    if c>50: st.error("చాలా messages! ఆగండి 🙏"); return False
    st.session_state.msg_count=c+1; return True

# ══════════════════════
#  COUNTER
# ══════════════════════
def load_counter():
    try:
        if os.path.exists(COUNTER_FILE):
            with open(COUNTER_FILE) as f: return json.load(f)
    except: pass
    return {"total_users":0,"total_messages":0,"daily":{}}

def inc_counter(new=False):
    try:
        d=load_counter(); d["total_messages"]+=1
        today=datetime.datetime.now().strftime("%Y-%m-%d")
        d["daily"][today]=d["daily"].get(today,0)+1
        if new: d["total_users"]+=1
        with open(COUNTER_FILE,"w") as f: json.dump(d,f)
        return d
    except: return {"total_users":0,"total_messages":0}

# ══════════════════════
#  MEMORY SYSTEM
# ══════════════════════
def load_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except: pass
    return {"sessions":[],"user_profile":{}}

def save_memory(mem):
    try:
        with open(MEMORY_FILE,"w",encoding="utf-8") as f:
            json.dump(mem,f,ensure_ascii=False,indent=2)
    except: pass

def save_session(title, messages):
    mem=load_memory()
    mem["sessions"].append({
        "title":    title,
        "date":     datetime.datetime.now().strftime("%d %B %Y %I:%M %p"),
        "messages": messages[-15:]
    })
    mem["sessions"]=mem["sessions"][-25:]
    save_memory(mem)

def update_profile(key,val):
    mem=load_memory()
    mem["user_profile"][key]=val
    save_memory(mem)

def get_profile():
    return load_memory().get("user_profile",{})

def get_memory_context():
    mem=load_memory()
    ctx=""
    p=mem.get("user_profile",{})
    if p:
        ctx+="\nUSER PROFILE:\n"
        for k,v in p.items(): ctx+=f"  {k}: {v}\n"
    sessions=mem.get("sessions",[])
    if sessions:
        ctx+="\nRECENT CHATS:\n"
        for s in sessions[-3:]:
            ctx+=f"  [{s['date'][:11]} — {s['title']}]\n"
            for m in s["messages"][-2:]:
                r="User" if m["role"]=="user" else "SIA"
                ctx+=f"    {r}: {m['content'][:80]}\n"
    return ctx

def auto_title(messages):
    try:
        if len(messages)<2: return "Quick Chat"
        for m in messages:
            if m["role"]=="user" and len(m["content"])>5:
                return m["content"][:35]+"..."
        return datetime.datetime.now().strftime("%d %b %H:%M")
    except: return "Chat"

# ══════════════════════
#  DIALECT ENGINE
# ══════════════════════
DIALECTS = {
    "rayalaseema":{
        "triggers":["ఏంది","గని","బిడ్డా","చేత్తాండు","పోతాండు","kadapa","kurnool","anantapur","chittoor","అనంతపురం","కడప","కర్నూలు"],
        "slang":["గని","ఏంది","బిడ్డా","అట్లుండు","సర్లే గని"],
        "example":"ఏంది బ్రో! సర్లే గని చెప్పు!"
    },
    "godavari":{
        "triggers":["గదరా","అంట","ఏంటే","అవునంట","ఒరేయ్","rajahmundry","kakinada","vizag","రాజమండ్రి","కాకినాడ","విశాఖ"],
        "slang":["గదరా","అంట","సర్దా","ఒరేయ్","పోదాం గదరా"],
        "example":"అవునా బ్రో! ఏం జరిగింది గదరా?"
    },
    "hyderabadi":{
        "triggers":["క్యా","యార్","బోలో","కర్తే","హై","hyderabad","హైదరాబాద్","bhai","భాయ్","matlab"],
        "slang":["యార్","క్యా","బోలో","భాయ్","మతలబ్"],
        "example":"అరే యార్! క్యా బాత్ హై బోలో!"
    },
    "telangana":{
        "triggers":["ఏంరా","సర్లే రా","అట్లనే","పోదాం రా","మామా","warangal","nizamabad","వరంగల్","నిజామాబాద్"],
        "slang":["రా","సర్లే","మామా","ఒరే","అట్లనే"],
        "example":"సర్లే రా మామా! ఏంరా విషయం?"
    }
}

def detect_dialect(text):
    tl=text.lower()
    for d,data in DIALECTS.items():
        if any(t.lower() in tl for t in data["triggers"]): return d
    return "neutral"

# ══════════════════════
#  EMOTION ENGINE
# ══════════════════════
EMOTIONS={
    "anxious":  ["exam","nervous","scared","stress","భయం","worried","tension","anxiety"],
    "sad":      ["sad","crying","alone","hurt","దుఃఖం","miss","depressed","lonely"],
    "excited":  ["happy","excited","wow","great","సంతోషం","amazing","yayyy","thrilled"],
    "lazy":     ["bore","బోర్","sleep","నిద్ర","youtube","instagram","netflix","tired","అలసట","పడుకున్న"],
    "lost":     ["don't know","తెలియడం లేదు","confused","ఏం చేయాలి","help","lost","no idea"],
    "motivated":["let's go","చేద్దాం","ready","start","study","hustle","నేను చేయగలను"],
    "sick":     ["sick","fever","జ్వరం","pain","medicine","unwell","headache"],
}

def detect_emotion(text):
    tl=text.lower()
    for e,kws in EMOTIONS.items():
        if any(k in tl for k in kws): return e
    return "neutral"

def detect_intents(text):
    m=text.lower(); i=[]
    if any(k in m for k in ["nakshatra","పంచాంగం","panchangam","rahukalam","festival","పండుగ","tithi"]): i.append("panchangam")
    if any(k in m for k in ["planet","గ్రహం","star","rashi","రాశి","jupiter","saturn","moon","astrology"]): i.append("sky")
    if any(k in m for k in ["mantra","మంత్రం","stotra","devotional","bhajan","కీర్తన","గణేశ","వెంకటేశ","శివ","లక్ష్మి","సరస్వతి"]): i.append("devotional")
    if any(k in m for k in ["internship","job","career","sarvam","apply","ai4bharat"]): i.append("career")
    return i

# ══════════════════════
#  PREDICT FUTURE
# ══════════════════════
def predict_future(messages):
    try:
        hour=datetime.datetime.now().hour
        day=datetime.datetime.now().strftime("%A")
        recent=" ".join([m["content"] for m in messages[-10:]])
        preds=[]
        lazy_count=sum(1 for m in messages if detect_emotion(m["content"])=="lazy")
        if lazy_count>=2: preds.append(f"⚠️ Pattern: చాలాసార్లు distracted అవుతున్నావు. Focus చేయి!")
        if any(k in recent.lower() for k in ["exam","పరీక్ష","interview","test"]): preds.append("🎯 Exam/Interview detected! Start revision now!")
        if day in ["Saturday","Sunday"] and hour>14: preds.append("🌅 Weekend afternoon — study 30 mins before evening!")
        return "\n".join(preds[:2])
    except: return ""

# ══════════════════════
#  DEVOTIONAL DB
# ══════════════════════
DEVOTIONAL={
    "గణేశుడు":   "మంత్రం: ఓం గం గణపతయే నమః\nస్తోత్రం: వక్రతుండ మహాకాయ సూర్యకోటి సమప్రభ\nసమయం: బుధవారం ఉదయం",
    "వెంకటేశ్వర":"మంత్రం: ఓం నమో వేంకటేశాయ\nస్తోత్రం: కౌసల్యా సుప్రజా రామ పూర్వాసంధ్యా ప్రవర్తతే\nసమయం: శుక్రవారం బ్రహ్మ మూహూర్తం",
    "శివుడు":    "మంత్రం: ఓం నమః శివాయ\nస్తోత్రం: కర్పూరగౌరం కరుణావతారం\nసమయం: సోమవారం ప్రదోష కాలం",
    "లక్ష్మీదేవి":"మంత్రం: ఓం శ్రీం మహాలక్ష్మ్యై నమః\nస్తోత్రం: నమస్తేస్తు మహామాయే\nసమయం: శుక్రవారం సాయంత్రం",
    "సరస్వతి":  "మంత్రం: ఓం ఐం సరస్వత్యై నమః\nస్తోత్రం: యా కుందేందు తుషారహారధవళా\nసమయం: విద్యారంభం నవరాత్రి"
}

KNOWLEDGE_BITES=[
    "💡 తెలుగు భాష 2000+ సంవత్సరాల పురాతనమైనది!",
    "💡 Sarvam AI — India's first full-stack Indic AI company.",
    "💡 82 million people speak Telugu worldwide.",
    "💡 అన్నమయ్య 32,000+ కీర్తనలు రాశాడు — world record!",
    "💡 AI4Bharat built IndicWhisper for Telugu speech.",
    "💡 Telugu is called the Italian of the East!",
    "💡 Groq LLaMA3 is the world's fastest LLM inference.",
]

INTERNSHIP_TARGETS=[
    {"company":"Sarvam AI",    "email":"careers@sarvam.ai"},
    {"company":"AI4Bharat",    "email":"ai4bharat.org/contact"},
    {"company":"Gnani.ai",     "email":"careers@gnani.ai"},
    {"company":"Krutrim (Ola)","email":"krutrim.com/careers"},
    {"company":"Reverie Tech", "email":"careers@reverieinc.com"},
]

# ══════════════════════
#  WEB SEARCH
# ══════════════════════
def search_web(q,n=3):
    try:
        if not DDGS: return ""
        with DDGS() as ddgs:
            r=ddgs.text(q,max_results=n)
            return " ".join([x["body"] for x in r])[:600]
    except: return ""

def get_panchangam():
    today=datetime.datetime.now().strftime("%B %d %Y")
    return search_web(f"Telugu panchangam {today} nakshatra tithi rahukalam festival")

def get_sky():
    try:
        import ephem
        now=ephem.now()
        obs=ephem.Observer(); obs.lat="17.3850"; obs.lon="78.4867"; obs.date=now
        NAKS=["అశ్విని","భరణి","కృత్తిక","రోహిణి","మృగశిర","ఆర్ద్ర","పునర్వసు","పుష్యమి","ఆశ్లేష","మఖ","పుబ్బ","ఉత్తర","హస్త","చిత్త","స్వాతి","విశాఖ","అనూరాధ","జ్యేష్ఠ","మూల","పూర్వాషాఢ","ఉత్తరాషాఢ","శ్రవణం","ధనిష్ఠ","శతభిష","పూర్వాభాద్ర","ఉత్తరాభాద్ర","రేవతి"]
        RASIS=["మేషం","వృషభం","మిథునం","కర్కాటకం","సింహం","కన్య","తుల","వృశ్చికం","ధనుస్సు","మకరం","కుంభం","మీనం"]
        bodies={"☀️ సూర్యుడు":ephem.Sun(),"🌙 చంద్రుడు":ephem.Moon(),"🔴 కుజుడు":ephem.Mars(),"⚡ బుధుడు":ephem.Mercury(),"🟡 గురుడు":ephem.Jupiter(),"✨ శుక్రుడు":ephem.Venus(),"🪐 శని":ephem.Saturn()}
        result=f"🌌 లైవ్ గ్రహ స్థితులు — {datetime.datetime.now().strftime('%I:%M %p')}\n\n"
        for name,body in bodies.items():
            body.compute(obs)
            ra=float(body.ra)*180/3.14159265
            nak=int((ra/360)*27)%27; ras=int((ra/360)*12)%12
            alt=float(body.alt)*180/3.14159265
            vis="కనిపిస్తోంది 👁️" if alt>0 else "క్షితిజం కింద"
            result+=f"  {name}: {RASIS[ras]} · {NAKS[nak]} · {vis}\n"
        moon=ephem.Moon(now); moon.compute(obs); p=moon.phase
        phase="అమావాస్య 🌑" if p<10 else("శుక్ల పక్షం 🌒" if p<45 else("పౌర్ణమి 🌕" if p<55 else "కృష్ణ పక్షం 🌘"))
        result+=f"\n🌙 చంద్ర దశ: {phase} ({p:.1f}%)"
        return result
    except: return search_web(f"planet positions Vedic astrology today Telugu nakshatra")

# ══════════════════════
#  BATTERY
# ══════════════════════
def get_battery():
    try:
        if not psutil: return None,None
        b=psutil.sensors_battery()
        return (b.percent,b.power_plugged) if b else (None,None)
    except: return None,None

# ══════════════════════
#  VOICE OUTPUT
# ══════════════════════
def sarvam_speak(text,voice="arvind"):
    try:
        if not requests or not SARVAM_API_KEY or SARVAM_API_KEY=="your-sarvam-key": return False
        clean=re.sub(r'[*_`#\[\]()]','',text)[:400]
        resp=requests.post("https://api.sarvam.ai/text-to-speech",
            json={"inputs":[clean],"target_language_code":"te-IN","speaker":voice,
                  "speech_sample_rate":22050,"enable_preprocessing":True,"model":"bulbul:v1"},
            headers={"api-subscription-key":SARVAM_API_KEY,"Content-Type":"application/json"},timeout=15)
        if resp.status_code==200:
            audio=base64.b64decode(resp.json()["audios"][0])
            with open("sia_voice.wav","wb") as f: f.write(audio)
            if os.name=="nt": os.system("start sia_voice.wav")
            else: os.system("aplay sia_voice.wav 2>/dev/null")
            return True
    except: pass
    return False

async def edge_async(text):
    try:
        import edge_tts
        clean=re.sub(r'[*_`#]','',text)
        await edge_tts.Communicate(clean,voice="te-IN-ShrutiNeural").save("sia_voice.mp3")
    except: pass

def fallback_speak(text):
    try:
        asyncio.run(edge_async(text))
        if os.name=="nt": os.system("start sia_voice.mp3")
        else: os.system("mpg123 sia_voice.mp3 2>/dev/null")
    except: pass

def speak(text,voice="arvind"):
    if not sarvam_speak(text,voice): fallback_speak(text)

# ══════════════════════
#  VOICE INPUT
# ══════════════════════
def listen():
    try:
        if not sr: return ""
        r=sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source,duration=1)
            audio=r.listen(source,timeout=6,phrase_time_limit=15)
            try: return r.recognize_google(audio,language="te-IN")
            except: return r.recognize_google(audio,language="en-IN")
    except: return ""

# ══════════════════════
#  IMAGE UNDERSTANDING
# ══════════════════════
def analyze_image(image_bytes,question):
    try:
        if not client: return "API key missing"
        b64=base64.standard_b64encode(image_bytes).decode()
        r=client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{"role":"user","content":[
                {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}},
                {"type":"text","text":f"""Analyze this image carefully.
1. Read ALL text visible in the image (OCR)
2. Describe what you see
3. Answer the question: {question}
Reply in Telugu. Be detailed."""}
            ]}],max_tokens=500)
        return r.choices[0].message.content
    except Exception as e: return f"Image చదవడం కష్టంగా ఉంది: {str(e)[:60]}"

# ══════════════════════
#  ANTI-GRAVITY HTML
# ══════════════════════
def get_antigravity():
    return """
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#04020C;width:100%;height:320px;overflow:hidden;cursor:crosshair;}
canvas{position:absolute;top:0;left:0;width:100%;height:100%;}
#msg{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#FF6B35;font-family:serif;font-size:1rem;text-align:center;pointer-events:none;opacity:0.7;letter-spacing:2px;transition:opacity 1s;}
#controls{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);display:flex;gap:6px;z-index:10;}
.btn{background:#FF6B3511;border:1px solid #FF6B3544;color:#FF6B35;padding:4px 12px;border-radius:20px;font-size:0.6rem;cursor:pointer;font-family:sans-serif;transition:all 0.2s;letter-spacing:1px;}
.btn:hover,.btn.on{background:#FF6B35;color:#000;}
</style>
<canvas id="c"></canvas>
<div id="msg">బోర్ గా ఉందా? ఆడుకో! 🎮<br><small style="font-size:0.55rem;opacity:0.5;letter-spacing:2px">CLICK · DRAG · PLAY</small></div>
<div id="controls">
  <button class="btn on" onclick="go('float')">🌊 Float</button>
  <button class="btn"    onclick="go('vortex')">🌀 Vortex</button>
  <button class="btn"    onclick="go('fire')">🔥 Fire</button>
  <button class="btn"    onclick="go('matrix')">⬇ Matrix</button>
  <button class="btn"    onclick="bang()">💥 Bang!</button>
</div>
<script>
const cv=document.getElementById('c'),ctx=cv.getContext('2d'),msg=document.getElementById('msg');
let W=cv.width=window.innerWidth,H=cv.height=320;
let mouse={x:W/2,y:H/2,down:false},mode='float',parts=[];
const WORDS=["చదువు","గెలుపు","ఆశ","కల","శక్తి","నీవు","గొప్ప","SIA","🔥","⭐","💪","🙏","✨","🌟","💫","🚀","తెలుగు","విజయం","ధైర్యం","ప్రయత్నం"];
const COLS=['#FF6B35','#FFD700','#FF9966','#FFB347','#FFCC44','#FF8C42','#FFA07A'];
class P{
  constructor(x,y,w,o={}){
    this.x=x??Math.random()*W;this.y=y??Math.random()*H;
    this.w=w??WORDS[~~(Math.random()*WORDS.length)];
    this.sz=o.sz??(12+Math.random()*24);
    this.col=o.col??COLS[~~(Math.random()*COLS.length)];
    this.vx=o.vx??(Math.random()-.5)*4;this.vy=o.vy??(Math.random()-.5)*4;
    this.rot=Math.random()*Math.PI*2;this.rs=(Math.random()-.5)*.08;
    this.a=0;this.ta=.6+Math.random()*.4;this.life=1;this.dec=o.dec??0;
    this.pulse=Math.random()*Math.PI*2;this.wob=Math.random()*Math.PI*2;
  }
  update(){
    if(this.a<this.ta)this.a=Math.min(this.a+.03,this.ta);
    this.pulse+=.05;this.wob+=.03;this.rot+=this.rs;
    if(mode==='float'){this.vy-=.018;this.vx+=Math.sin(this.wob)*.04;}
    else if(mode==='vortex'){const dx=this.x-W/2,dy=this.y-H/2,d=Math.sqrt(dx*dx+dy*dy)||1,ang=Math.atan2(dy,dx),spd=Math.min(130/d,4);this.vx+=Math.cos(ang+Math.PI/2)*spd*.045-(dx/d)*.12;this.vy+=Math.sin(ang+Math.PI/2)*spd*.045-(dy/d)*.12;}
    else if(mode==='fire'){this.vy-=.06+Math.random()*.04;this.vx+=(Math.random()-.5)*.15;if(!this.dec)this.dec=.004+Math.random()*.006;}
    else if(mode==='matrix'){this.vy=3.5+this.sz*.07;this.vx=Math.sin(this.wob)*.25;if(this.y>H+30){this.y=-15;this.x=Math.random()*W;}}
    const dx=this.x-mouse.x,dy=this.y-mouse.y,d=Math.sqrt(dx*dx+dy*dy)||1;
    if(mouse.down&&d<120){this.vx-=(dx/d)*2.5;this.vy-=(dy/d)*2.5;}
    else if(d<80){this.vx+=(dx/d)*.6;this.vy+=(dy/d)*.6;}
    this.x+=this.vx;this.y+=this.vy;this.vx*=.97;this.vy*=.97;
    if(!['matrix'].includes(mode)){
      if(this.x<8){this.x=8;this.vx=Math.abs(this.vx)*.7;}if(this.x>W-8){this.x=W-8;this.vx=-Math.abs(this.vx)*.7;}
      if(this.y<8){this.y=8;this.vy=Math.abs(this.vy)*.7;}if(this.y>H-8){this.y=H-8;this.vy=-Math.abs(this.vy)*.7;}
    }
    if(this.dec>0){this.life-=this.dec;this.a=this.life*this.ta;}
    return this.life>.02;
  }
  draw(){
    ctx.save();ctx.translate(this.x,this.y);ctx.rotate(this.rot);
    const sc=1+Math.sin(this.pulse)*.1;ctx.scale(sc,sc);
    ctx.shadowBlur=this.glow?40:12;ctx.shadowColor=this.col;
    ctx.globalAlpha=this.a;ctx.fillStyle=this.col;
    ctx.font=this.sz+'px serif';ctx.textAlign='center';ctx.textBaseline='middle';
    ctx.fillText(this.w,0,0);ctx.restore();
  }
}
function spawn(n=12){for(let i=0;i<n;i++)setTimeout(()=>parts.push(new P()),i*100);}
function explode(x,y){
  msg.style.opacity='0';
  parts.forEach(p=>{const dx=p.x-x,dy=p.y-y,d=Math.sqrt(dx*dx+dy*dy)||1,f=(200-Math.min(d,200))/200*10;p.vx+=(dx/d)*f;p.vy+=(dy/d)*f;});
  for(let i=0;i<8;i++){const a=Math.PI*2*i/8,s=4+Math.random()*8;parts.push(new P(x,y,WORDS[~~(Math.random()*WORDS.length)],{vx:Math.cos(a)*s,vy:Math.sin(a)*s,sz:10+Math.random()*18,dec:.014}));}
  const r=document.createElement('div');r.style.cssText=`position:fixed;left:${x}px;top:${y}px;border-radius:50%;border:2px solid #FFD700;pointer-events:none;animation:rip .7s ease-out forwards;margin:-90px;`;document.body.appendChild(r);setTimeout(()=>r.remove(),700);
}
function bang(){parts.forEach(p=>{const a=Math.random()*Math.PI*2,s=5+Math.random()*15;p.vx=Math.cos(a)*s;p.vy=Math.sin(a)*s;p.dec=.006;});setTimeout(()=>{parts=[];spawn(18);},1800);}
function go(m){mode=m;document.querySelectorAll('.btn').forEach(b=>b.classList.remove('on'));event.target.classList.add('on');if(m==='matrix')parts.forEach(p=>{p.x=Math.random()*W;p.y=Math.random()*H;p.vx=0;p.vy=0;});if(m==='fire')parts=[];}
let ft=0;
function loop(){
  ctx.fillStyle='rgba(4,2,12,.22)';ctx.fillRect(0,0,W,H);ft++;
  if(mode==='fire'&&ft%5===0)for(let i=0;i<3;i++)parts.push(new P(W*.15+Math.random()*W*.7,H-10,WORDS[~~(Math.random()*WORDS.length)],{vx:(Math.random()-.5)*2,vy:-(3+Math.random()*5),sz:10+Math.random()*20}));
  parts=parts.filter(p=>p.update());parts.forEach(p=>p.draw());
  if(['float','vortex'].includes(mode)&&parts.length<10)spawn(4);
  if(mode==='matrix'&&parts.length<20)for(let i=0;i<3;i++)parts.push(new P(Math.random()*W,-10));
  requestAnimationFrame(loop);
}
cv.addEventListener('click',e=>{const r=cv.getBoundingClientRect();explode(e.clientX-r.left,e.clientY-r.top);});
cv.addEventListener('mousemove',e=>{const r=cv.getBoundingClientRect();mouse.x=e.clientX-r.left;mouse.y=e.clientY-r.top;});
cv.addEventListener('mousedown',()=>mouse.down=true);cv.addEventListener('mouseup',()=>mouse.down=false);
cv.addEventListener('touchstart',e=>{e.preventDefault();const r=cv.getBoundingClientRect(),t=e.touches[0];mouse.x=t.clientX-r.left;mouse.y=t.clientY-r.top;mouse.down=true;explode(mouse.x,mouse.y);},{passive:false});
cv.addEventListener('touchmove',e=>{e.preventDefault();const r=cv.getBoundingClientRect(),t=e.touches[0];mouse.x=t.clientX-r.left;mouse.y=t.clientY-r.top;},{passive:false});
cv.addEventListener('touchend',()=>mouse.down=false);
window.addEventListener('resize',()=>{W=cv.width=window.innerWidth;});
const s=document.createElement('style');s.textContent='@keyframes rip{0%{width:0;height:0;opacity:.8}100%{width:180px;height:180px;opacity:0}}';document.head.appendChild(s);
spawn(16);loop();
</script>
"""

# ══════════════════════
#  CHAT ENGINE
# ══════════════════════
def chat(user_msg, history):
    if not client:
        return "GROQ_API_KEY missing in Streamlit Secrets! 🙏", "neutral", "neutral", "normal"

    dialect = detect_dialect(user_msg)
    emotion = detect_emotion(user_msg)
    intents = detect_intents(user_msg)
    profile = get_profile()

    # Voice mode
    tl = user_msg.lower()
    if any(k in tl for k in ["అమ్మమ్మ","grandma","slow","పెద్దవారు"]): vm="grandma"
    elif any(k in tl for k in ["genz","cool","bro mode","slang"]): vm="genz"
    else: vm=st.session_state.get("voice_mode","normal")

    # Detect if user sharing name/age
    if any(k in tl for k in ["నా పేరు","my name is","నేను","i am","నా వయసు","my age"]):
        import re as re2
        name_match = re2.search(r'(?:నా పేరు|my name is|i am|నేను)\s+(\w+)', tl)
        age_match  = re2.search(r'(?:నా వయసు|my age|age is|వయసు)\s*(\d+)', tl)
        if name_match: update_profile("name", name_match.group(1))
        if age_match:  update_profile("age",  age_match.group(1))

    # Extra context
    extra=""
    for deity,info in DEVOTIONAL.items():
        if deity.lower() in tl: extra+=f"\n{deity}: {info}"
    if "career" in intents: extra+="\nJobs: "+" | ".join([t["company"] for t in INTERNSHIP_TARGETS])
    if "panchangam" in intents: extra+=f"\nPanchangam: {get_panchangam()[:300]}"
    if "sky" in intents: extra+=f"\nSky: {get_sky()[:400]}"

    # Predictions
    preds=predict_future(history)

    # User name
    name=profile.get("name","")
    name_str=f"User's name: {name}. " if name else ""

    # Voice styles
    voice_map={"grandma":"Speak slowly, respectfully. Use అమ్మా నాయనా. No slang.","genz":"Cool Telugu+English. Use bro, lit, vibe, పక్కా.","normal":"Friendly natural Telugu."}

    # Emotion styles
    emotion_map={
        "anxious":"Be calm, reassuring. Give 3 simple steps.",
        "sad":"Be warm FIRST. Listen before advising.",
        "excited":"Match energy! Celebrate!",
        "lazy":"Call out lovingly in their dialect. Give 2-min challenge.",
        "lost":"Give 3 clear steps.",
        "motivated":"Fuel that energy!",
        "sick":"Be gentle. Suggest Telugu home remedy.",
        "neutral":"Helpful and friendly."
    }

    # Dialect instructions
    dialect_str=""
    if dialect in DIALECTS:
        dialect_str=f"Dialect: {dialect}. Use these slang words naturally: {', '.join(DIALECTS[dialect]['slang'])}. Example: {DIALECTS[dialect]['example']}"
    else:
        dialect_str="Use clean neutral Telugu."

    system=f"""You are SIA — Telugu AI Companion. Smart, cultural, emotionally intelligent best friend.
{name_str}
ALWAYS reply in Telugu only.
{dialect_str}
Voice style: {voice_map.get(vm,'Friendly Telugu.')}
Emotion detected: {emotion}. {emotion_map.get(emotion,'')}
Remember past context naturally like a real friend.
Predict what user needs next.
Max 4 lines. End with one clear action.{extra}
{f'Predictions: {preds}' if preds else ''}
Memory:{get_memory_context()[:400]}"""

    messages=[{"role":"system","content":system}]
    for m in history[-6:]:
        messages.append({"role":m["role"],"content":m["content"][:300]})
    messages.append({"role":"user","content":user_msg[:500]})

    try:
        r=client.chat.completions.create(model=CHAT_MODEL,messages=messages,max_tokens=250,temperature=0.85)
        reply=r.choices[0].message.content
        inc_counter()
        return reply,dialect,emotion,vm
    except Exception as e:
        err=str(e)
        if "decommissioned" in err: return f"Model error: {err[:100]}",dialect,emotion,vm
        return "సియా ఇప్పుడు busy! మళ్ళీ try చేయి 🙏",dialect,emotion,vm

# ══════════════════════
#  UI CSS
# ══════════════════════
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
.tag{display:inline-block;background:linear-gradient(135deg,#1a0a2a,#2a1040);border:1px solid #FF6B3533;border-radius:20px;padding:4px 16px;font-size:.62rem;color:var(--s);letter-spacing:2px;margin-top:.4rem;}
.badge{display:inline-block;padding:3px 12px;border-radius:20px;font-size:.65rem;margin:2px;letter-spacing:1px;}
.db{background:#1a1000;border:1px solid var(--s);color:var(--s);}
.eb{background:#0a1a0a;border:1px solid #2a4a2a;color:#6aaa6a;}
.kb{background:var(--c);border:1px solid var(--b);border-radius:10px;padding:.6rem 1rem;font-size:.72rem;color:#FF6B3588;margin-bottom:.5rem;}
.pred{background:linear-gradient(135deg,#0a0814,#140820);border:1px solid #FF6B3533;border-radius:12px;padding:.8rem 1rem;margin:.5rem 0;font-size:.75rem;color:var(--s);}
[data-testid="stChatMessage"]{background:var(--c)!important;border:1px solid var(--b)!important;border-radius:16px!important;margin-bottom:.6rem!important;}
[data-testid="stChatInput"] textarea{background:var(--c)!important;border:1px solid var(--b)!important;color:var(--t)!important;border-radius:14px!important;}
.stButton>button{background:linear-gradient(135deg,var(--s),#aa3300)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;transition:all .2s!important;}
.stButton>button:hover{transform:scale(1.04)!important;}
[data-testid="stSidebar"]{background:#080614!important;border-right:1px solid var(--b)!important;}
.mem-pill{font-size:.65rem;color:#6A5A8A;padding:3px 0;display:block;}
.admin-box{background:linear-gradient(135deg,#0a0500,#150800);border:2px solid var(--s);border-radius:16px;padding:1.5rem;margin:1rem 0;}
hr{border-color:var(--b)!important;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════
#  HEADER
# ══════════════════════
st.markdown("""
<div class="sia-wrap">
  <span class="sia-om">🕉️</span>
  <div class="sia-name">SIA</div>
  <div class="sia-sub">స్మార్ట్ ఇండియన్ అసిస్టెంట్</div>
  <div class="tag">✦ AI COMPANION · NOT JUST A CHATBOT ✦</div>
</div><hr>
""", unsafe_allow_html=True)

st.markdown(f'<div class="kb">{random.choice(KNOWLEDGE_BITES)}</div>', unsafe_allow_html=True)

# ══════════════════════
#  ADMIN PANEL
# ══════════════════════
if IS_ADMIN:
    stats=load_counter(); mem=load_memory(); pct,plug=get_battery()
    st.markdown('<div class="admin-box">', unsafe_allow_html=True)
    st.markdown("### 🔐 Admin Panel — Only You See This")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("👥 Users",   stats.get("total_users",0))
    c2.metric("💬 Messages",stats.get("total_messages",0))
    c3.metric("📚 Sessions",len(mem.get("sessions",[])))
    c4.metric("🔋 Battery", f"{pct}%" if pct else "N/A")
    if stats.get("daily"):
        days=list(stats["daily"].keys())[-7:]
        st.bar_chart({d:stats["daily"][d] for d in days})
    st.markdown("**Profile:**")
    st.json(mem.get("user_profile",{}))
    st.markdown("**Sessions:**")
    for s in reversed(mem.get("sessions",[])[-10:]):
        st.markdown(f"📌 `{s['date'][:11]}` — {s['title']}")
    if st.button("🗑️ Clear All"):
        save_memory({"sessions":[],"user_profile":{}})
        with open(COUNTER_FILE,"w") as f: json.dump({"total_users":0,"total_messages":0,"daily":{}},f)
        st.success("Cleared!")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════
#  SIDEBAR
# ══════════════════════
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    vp=st.selectbox("🗣️ Mode",["Normal","Grandma Mode","GenZ Mode"])
    st.session_state.voice_mode={"Normal":"normal","Grandma Mode":"grandma","GenZ Mode":"genz"}[vp]
    sv=st.selectbox("🔊 Voice",["arvind","amartya","diya","neel","maitreyi","pavithra"])
    auto_speak=st.toggle("Auto Speak",value=True)

    st.markdown("---")
    st.markdown("### 🧠 Memory")
    mem=load_memory()
    profile=mem.get("user_profile",{})
    if profile:
        st.markdown("**Profile:**")
        for k,v in profile.items():
            st.markdown(f"<span class='mem-pill'>👤 {k}: {v}</span>",unsafe_allow_html=True)
    if mem.get("sessions"):
        st.markdown("**Past Chats:**")
        for s in reversed(mem["sessions"][-8:]):
            st.markdown(f"<span class='mem-pill'>📌 {s['date'][:11]} — {s['title']}</span>",unsafe_allow_html=True)
    if st.button("🗑️ Clear Memory"):
        save_memory({"sessions":[],"user_profile":{}})
        st.success("Cleared!")

    st.markdown("---")
    st.markdown("### 🌌 Live Sky")
    if st.button("🔭 Refresh"):
        with st.spinner("Loading..."): st.session_state.sky=get_sky()
    if "sky" in st.session_state: st.code(st.session_state.sky,language=None)

    st.markdown("---")
    st.markdown("### 🕉️ Mantras")
    deity=st.selectbox("Deity",list(DEVOTIONAL.keys()))
    if st.button("Show"): st.info(DEVOTIONAL[deity])

    st.markdown("---")
    st.markdown("### 🎯 Apply Here")
    for t in INTERNSHIP_TARGETS:
        st.markdown(f"**{t['company']}** — {t['email']}")

    pct,plug=get_battery()
    if pct:
        col="green" if pct>50 else("orange" if pct>20 else "red")
        st.markdown(f"{'🔌' if plug else '🔋'} Battery: <span style='color:{col}'>{pct}%</span>",unsafe_allow_html=True)

    st.caption("SIA v7.0 · Telugu AI · 8.8 CGPA")

# ══════════════════════
#  SESSION INIT
# ══════════════════════
if "messages" not in st.session_state:
    st.session_state.messages=[]; st.session_state.dialect="neutral"
    st.session_state.emotion="neutral"; st.session_state.voice_mode="normal"
    st.session_state.msg_count=0; st.session_state.onboarded=False
    inc_counter(new=True)

    profile=get_profile()
    has_name=bool(profile.get("name"))

    now=datetime.datetime.now(); hour=now.hour
    greet="శుభోదయం" if hour<12 else("శుభ మధ్యాహ్నం" if hour<17 else "శుభ సాయంత్రం")

    if not has_name:
        # Ask name and age first time
        first_msg=(
            f"{greet}! నేను సియా 🙏\n\n"
            f"మీ Telugu AI Companion — నిజమైన స్నేహితుడు.\n\n"
            f"మీ పేరు మరియు వయసు చెప్పండి, నేను మిమ్మల్ని గుర్తుంచుకుంటాను!\n\n"
            f"Example: నా పేరు రాహుల్, నా వయసు 21"
        )
    else:
        name=profile["name"]
        first_msg=(
            f"{greet} {name}! నేను సియా 🙏\n\n"
            f"మళ్ళీ కలిసినందుకు సంతోషం! ఏం చేస్తున్నావు?\n\n"
            f"💬 Type · 🎤 Mic · 📸 Photo · మాట్లాడు!"
        )

    st.session_state.messages.append({"role":"assistant","content":first_msg})

# ══════════════════════
#  BADGES + PREDICTIONS
# ══════════════════════
d=st.session_state.get("dialect","neutral"); e=st.session_state.get("emotion","neutral")
DNAMES={"rayalaseema":"🌶️ Rayalaseema","godavari":"🌊 Godavari","hyderabadi":"🏙️ Hyderabadi","telangana":"⭐ Telangana"}
ENAMES={"anxious":"😰 Anxious","sad":"💙 Sad","excited":"🔥 Excited","lazy":"😴 Lazy","lost":"🤔 Lost","motivated":"💪 Motivated","sick":"🤒 Sick"}
badges=""
if d in DNAMES: badges+=f"<span class='badge db'>{DNAMES[d]}</span>"
if e in ENAMES: badges+=f"<span class='badge eb'>{ENAMES[e]}</span>"
if badges: st.markdown(badges,unsafe_allow_html=True)

# Predictions
preds=predict_future(st.session_state.messages)
if preds: st.markdown(f"<div class='pred'>🔮 <b>SIA Prediction:</b><br>{preds}</div>",unsafe_allow_html=True)

# Anti-gravity when bored/lazy
if st.session_state.get("emotion")=="lazy":
    components.html(get_antigravity(), height=340)

# ══════════════════════
#  CHAT HISTORY
# ══════════════════════
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ══════════════════════
#  MINI TOOLS
# ══════════════════════
with st.expander("🧰 Mini AI Tools"):
    t1,t2,t3,t4=st.columns(4)
    with t1:
        if st.button("💡 Fact"): st.info(random.choice(KNOWLEDGE_BITES))
    with t2:
        if st.button("🎯 Jobs"):
            for t in INTERNSHIP_TARGETS: st.markdown(f"**{t['company']}** — {t['email']}")
    with t3:
        if st.button("🕉️ Mantra"): st.info(random.choice(list(DEVOTIONAL.values())))
    with t4:
        if st.button("🌌 Sky"):
            with st.spinner("Loading..."): st.code(get_sky(),language=None)

# ══════════════════════
#  INPUT CONTROLS
# ══════════════════════
c1,c2=st.columns([1,1])
with c1: mic_btn=st.button("🎤 Speak",use_container_width=True)
with c2: save_btn=st.button("💾 Save", use_container_width=True)

user_input=st.chat_input("SIA తో మాట్లాడు... (Telugu or English)")
uploaded=st.file_uploader("📎 Photo / Document (text in images supported!)",type=["jpg","jpeg","png","webp"],label_visibility="visible")

if mic_btn:
    with st.spinner("🎤 వింటున్నాను..."):
        spoken=listen()
    if spoken: user_input=spoken; st.info(f"🎤 {spoken}")
    else: st.warning("వినలేదు — మళ్ళీ try చేయి")

if save_btn and len(st.session_state.messages)>2:
    title=auto_title(st.session_state.messages)
    save_session(title,st.session_state.messages)
    st.success(f"✅ Saved: '{title}'")

# Image upload
img_context=""
if uploaded and Image and io:
    img_bytes=uploaded.read()
    st.image(Image.open(io.BytesIO(img_bytes)),use_container_width=True)
    q=user_input or "ఈ image లో ఏముంది? Text ఉంటే చదువు. Telugu లో వివరంగా చెప్పు."
    with st.spinner("🔍 Image చదువుతున్నాను... (text కూడా చదువుతున్నాను)"): 
        img_context=analyze_image(img_bytes,q)
    if not user_input: user_input="ఈ image గురించి చెప్పు"

# ══════════════════════
#  PROCESS MESSAGE
# ══════════════════════
if user_input:
    if not is_safe(user_input):
        st.warning("ఆ message పంపలేను 🙏"); st.stop()
    if not check_rate(): st.stop()

    # Add image context to message if present
    full_msg=user_input
    if img_context: full_msg=f"{user_input}\n\n[Image content: {img_context[:300]}]"

    st.session_state.messages.append({"role":"user","content":full_msg})
    with st.chat_message("user"): st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("సియా ఆలోచిస్తోంది..."):
            reply,dialect,emotion,vm=chat(full_msg,st.session_state.messages)
            st.session_state.dialect=dialect; st.session_state.emotion=emotion
            st.session_state.voice_mode=vm
            st.write(reply)
            st.session_state.messages.append({"role":"assistant","content":reply})

    # Voice output
    if auto_speak:
        voice_map={"grandma":"pavithra","genz":"neel","normal":sv}
        threading.Thread(target=speak,args=(reply,voice_map.get(vm,sv)),daemon=True).start()

    # Auto-refresh badges
    st.rerun()

# Auto save every 10 messages
if len(st.session_state.messages)>0 and len(st.session_state.messages)%10==0:
    save_session(auto_title(st.session_state.messages),st.session_state.messages)
