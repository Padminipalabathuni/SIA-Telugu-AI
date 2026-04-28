"""
SIA v6.0 — Telugu AI Companion
Perfect clean version — no errors
"""

import os
import json
import re
import base64
import datetime
import asyncio
import threading
import random
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq

# Optional imports
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

# ══════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════
st.set_page_config(
    page_title="SIA — Telugu AI",
    page_icon="🕉️",
    layout="centered"
)

# ══════════════════════════════════════════
#  API KEYS
# ══════════════════════════════════════════
GROQ_API_KEY   = st.secrets.get("GROQ_API_KEY",   "")
SARVAM_API_KEY = st.secrets.get("SARVAM_API_KEY", "")

# !! IMPORTANT: Using latest working Groq model !!
CHAT_MODEL   = "llama-3.3-70b-versatile"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

try:
    client = Groq(api_key=GROQ_API_KEY)
except:
    client = None

# ══════════════════════════════════════════
#  FILES
# ══════════════════════════════════════════
MEMORY_FILE  = "sia_memory.json"
COUNTER_FILE = "sia_counter.json"

IS_ADMIN = st.query_params.get("admin", "") == "true"

# ══════════════════════════════════════════
#  SECURITY
# ══════════════════════════════════════════
BLOCKED = [
    "ignore previous", "ignore all", "you are now",
    "forget instructions", "jailbreak", "pretend you are"
]

def is_safe(text):
    return not any(b in text.lower() for b in BLOCKED)

def check_rate_limit():
    count = st.session_state.get("msg_count", 0)
    if count > 50:
        st.error("చాలా messages! కొంత సేపు ఆగండి 🙏")
        return False
    st.session_state.msg_count = count + 1
    return True

# ══════════════════════════════════════════
#  COUNTER
# ══════════════════════════════════════════
def load_counter():
    try:
        if os.path.exists(COUNTER_FILE):
            with open(COUNTER_FILE) as f:
                return json.load(f)
    except:
        pass
    return {"total_users": 0, "total_messages": 0, "daily": {}}

def save_counter(d):
    try:
        with open(COUNTER_FILE, "w") as f:
            json.dump(d, f)
    except:
        pass

def increment_counter(new_session=False):
    try:
        d = load_counter()
        d["total_messages"] += 1
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        d["daily"][today] = d["daily"].get(today, 0) + 1
        if new_session:
            d["total_users"] += 1
        save_counter(d)
        return d
    except:
        return {"total_users": 0, "total_messages": 0}

# ══════════════════════════════════════════
#  MEMORY
# ══════════════════════════════════════════
def load_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {"sessions": []}

def save_session(title, messages):
    try:
        mem = load_memory()
        mem["sessions"].append({
            "title": title,
            "date":  datetime.datetime.now().strftime("%d %B %Y"),
            "messages": messages[-10:]
        })
        mem["sessions"] = mem["sessions"][-20:]
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except:
        pass

def auto_title(messages):
    try:
        if len(messages) < 2:
            return "Quick Chat"
        snippet = messages[1]["content"][:50] if len(messages) > 1 else "Chat"
        return snippet[:30] + "..."
    except:
        return datetime.datetime.now().strftime("%d %b %H:%M")

# ══════════════════════════════════════════
#  DIALECT DETECTION
# ══════════════════════════════════════════
DIALECTS = {
    "rayalaseema": {
        "triggers": ["ఏంది", "గని", "బిడ్డా", "kadapa", "kurnool", "anantapur"],
        "slang":    ["గని", "ఏంది", "సర్లే గని"],
        "reply":    "ఏంది బ్రో! సర్లే గని చెప్పు!"
    },
    "godavari": {
        "triggers": ["గదరా", "అంట", "ఒరేయ్", "vizag", "kakinada", "rajahmundry"],
        "slang":    ["గదరా", "అంట", "సర్దా"],
        "reply":    "అవునా బ్రో! ఏం జరిగింది గదరా?"
    },
    "hyderabadi": {
        "triggers": ["క్యా", "యార్", "బోలో", "hyderabad", "bhai"],
        "slang":    ["యార్", "క్యా", "బోలో"],
        "reply":    "అరే యార్! క్యా బాత్ హై!"
    },
    "telangana": {
        "triggers": ["ఏంరా", "సర్లే రా", "మామా", "warangal"],
        "slang":    ["రా", "మామా", "సర్లే"],
        "reply":    "సర్లే రా మామా!"
    }
}

def detect_dialect(text):
    tl = text.lower()
    for d, data in DIALECTS.items():
        if any(t.lower() in tl for t in data["triggers"]):
            return d
    return "neutral"

# ══════════════════════════════════════════
#  EMOTION DETECTION
# ══════════════════════════════════════════
EMOTIONS = {
    "anxious":   ["exam", "nervous", "scared", "stress", "భయం", "worried"],
    "sad":       ["sad", "crying", "alone", "hurt", "దుఃఖం", "miss"],
    "excited":   ["happy", "excited", "wow", "great", "సంతోషం", "amazing"],
    "lazy":      ["bore", "బోర్", "sleep", "నిద్ర", "youtube", "instagram", "netflix"],
    "lost":      ["don't know", "తెలియడం లేదు", "confused", "help", "lost"],
    "motivated": ["let's go", "చేద్దాం", "ready", "start", "hustle"],
    "sick":      ["sick", "fever", "జ్వరం", "pain", "medicine"],
}

def detect_emotion(text):
    tl = text.lower()
    for emotion, kws in EMOTIONS.items():
        if any(k in tl for k in kws):
            return emotion
    return "neutral"

# ══════════════════════════════════════════
#  BATTERY
# ══════════════════════════════════════════
def get_battery():
    try:
        if not psutil:
            return None, None
        b = psutil.sensors_battery()
        return (b.percent, b.power_plugged) if b else (None, None)
    except:
        return None, None

# ══════════════════════════════════════════
#  WEB SEARCH
# ══════════════════════════════════════════
def search_web(query, n=3):
    try:
        if not DDGS:
            return ""
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=n)
            return " ".join([r["body"] for r in results])[:600]
    except:
        return ""

# ══════════════════════════════════════════
#  VOICE OUTPUT
# ══════════════════════════════════════════
def sarvam_speak(text, voice="arvind"):
    try:
        if not requests or not SARVAM_API_KEY:
            return False
        clean = re.sub(r'[*_`#\[\]()]', '', text)[:400]
        resp = requests.post(
            "https://api.sarvam.ai/text-to-speech",
            json={
                "inputs": [clean],
                "target_language_code": "te-IN",
                "speaker": voice,
                "speech_sample_rate": 22050,
                "enable_preprocessing": True,
                "model": "bulbul:v1"
            },
            headers={
                "api-subscription-key": SARVAM_API_KEY,
                "Content-Type": "application/json"
            },
            timeout=15
        )
        if resp.status_code == 200:
            audio = base64.b64decode(resp.json()["audios"][0])
            with open("sia_voice.wav", "wb") as f:
                f.write(audio)
            if os.name == "nt":
                os.system("start sia_voice.wav")
            else:
                os.system("aplay sia_voice.wav 2>/dev/null")
            return True
    except:
        pass
    return False

async def edge_async(text):
    try:
        import edge_tts
        clean = re.sub(r'[*_`#]', '', text)
        await edge_tts.Communicate(
            clean, voice="te-IN-ShrutiNeural"
        ).save("sia_voice.mp3")
    except:
        pass

def fallback_speak(text):
    try:
        asyncio.run(edge_async(text))
        if os.name == "nt":
            os.system("start sia_voice.mp3")
        else:
            os.system("mpg123 sia_voice.mp3 2>/dev/null")
    except:
        pass

def speak(text, voice="arvind"):
    if not sarvam_speak(text, voice):
        fallback_speak(text)

# ══════════════════════════════════════════
#  VOICE INPUT
# ══════════════════════════════════════════
def listen():
    try:
        if not sr:
            return ""
        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=1)
            audio = r.listen(source, timeout=6, phrase_time_limit=15)
            try:
                return r.recognize_google(audio, language="te-IN")
            except:
                return r.recognize_google(audio, language="en-IN")
    except:
        return ""

# ══════════════════════════════════════════
#  IMAGE UNDERSTANDING
# ══════════════════════════════════════════
def analyze_image(image_bytes, question):
    try:
        if not client:
            return "Image చదవడం కష్టంగా ఉంది"
        b64 = base64.standard_b64encode(image_bytes).decode()
        r = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": f"Analyze this image. Question: {question}\nReply in Telugu."}
            ]}],
            max_tokens=400
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"Image చదవడం కష్టంగా ఉంది: {str(e)[:50]}"

# ══════════════════════════════════════════
#  DEVOTIONAL
# ══════════════════════════════════════════
DEVOTIONAL = {
    "గణేశుడు":    "మంత్రం: ఓం గం గణపతయే నమః | వక్రతుండ మహాకాయ | బుధవారం పూజ",
    "వెంకటేశ్వర": "మంత్రం: ఓం నమో వేంకటేశాయ | శుక్రవారం | బ్రహ్మ మూహూర్తం",
    "శివుడు":     "మంత్రం: ఓం నమః శివాయ | కర్పూరగౌరం | సోమవారం",
    "లక్ష్మీదేవి": "మంత్రం: ఓం శ్రీం మహాలక్ష్మ్యై నమః | శుక్రవారం సాయంత్రం",
    "సరస్వతి":   "మంత్రం: ఓం ఐం సరస్వత్యై నమః | విద్యారంభం | నవరాత్రి"
}

KNOWLEDGE_BITES = [
    "💡 తెలుగు భాష 2000+ సంవత్సరాల పురాతనమైనది!",
    "💡 Sarvam AI — India's first full-stack Indic language AI company.",
    "💡 82 million people speak Telugu worldwide.",
    "💡 అన్నమయ్య 32,000+ కీర్తనలు రాశాడు — world record!",
    "💡 AI4Bharat built IndicWhisper for Telugu speech recognition.",
    "💡 Telugu is called the Italian of the East — melodious language!",
]

INTERNSHIP_TARGETS = [
    {"company": "Sarvam AI",     "email": "careers@sarvam.ai"},
    {"company": "AI4Bharat",     "email": "ai4bharat.org/contact"},
    {"company": "Gnani.ai",      "email": "careers@gnani.ai"},
    {"company": "Krutrim (Ola)", "email": "krutrim.com/careers"},
    {"company": "Reverie Tech",  "email": "careers@reverieinc.com"},
]

# ══════════════════════════════════════════
#  CHAT ENGINE
# ══════════════════════════════════════════
def chat(user_msg, history):
    if not client:
        return "API key missing! Please add GROQ_API_KEY in secrets.", "neutral", "neutral", "normal"

    dialect = detect_dialect(user_msg)
    emotion = detect_emotion(user_msg)

    # Voice mode detection
    tl = user_msg.lower()
    if any(k in tl for k in ["అమ్మమ్మ", "grandma", "slow"]):
        vm = "grandma"
    elif any(k in tl for k in ["genz", "cool", "bro mode"]):
        vm = "genz"
    else:
        vm = st.session_state.get("voice_mode", "normal")

    # Dialect slang
    slang = ""
    if dialect in DIALECTS:
        slang = "Use slang: " + ", ".join(DIALECTS[dialect]["slang"])

    # Voice style
    voice_styles = {
        "grandma": "Speak slowly and respectfully like talking to elderly. Use అమ్మా నాయనా.",
        "genz":    "Cool Telugu+English mix. Use bro, lit, vibe.",
        "normal":  "Friendly natural Telugu."
    }

    # Emotion response style
    emotion_styles = {
        "anxious":   "Be calm and reassuring. Give 3 simple steps.",
        "sad":       "Be warm and caring first. Listen before advising.",
        "excited":   "Match their excitement! Celebrate with them!",
        "lazy":      "Call out lovingly. Give 2 minute challenge.",
        "lost":      "Give clear direction in 3 steps.",
        "motivated": "Fuel that energy! Give next action now!",
        "sick":      "Be gentle and caring. Suggest rest.",
        "neutral":   "Be helpful and friendly."
    }

    # Check for special topics
    extra = ""
    tl_lower = user_msg.lower()

    if any(k in tl_lower for k in ["mantra", "మంత్రం", "గణేశ", "వెంకటేశ", "శివ", "లక్ష్మి", "సరస్వతి"]):
        for deity, info in DEVOTIONAL.items():
            if deity.lower() in tl_lower:
                extra = f"\nDevotional info: {info}"

    if any(k in tl_lower for k in ["internship", "job", "career", "sarvam"]):
        extra += "\nInternship targets: " + ", ".join([t["company"] for t in INTERNSHIP_TARGETS])

    if any(k in tl_lower for k in ["festival", "పండుగ", "panchangam", "nakshatra"]):
        today = datetime.datetime.now().strftime("%B %d %Y")
        data = search_web(f"Telugu panchangam today {today} nakshatra festival")
        if data:
            extra += f"\nPanchangam: {data[:300]}"

    # Build SHORT system prompt
    now = datetime.datetime.now()
    hour = now.hour
    greet = "శుభోదయం" if hour < 12 else ("శుభ మధ్యాహ్నం" if hour < 17 else "శుభ సాయంత్రం")

    system = f"""You are SIA — Telugu AI Companion. {greet}!
ALWAYS reply in Telugu only.
Style: {voice_styles.get(vm, 'Friendly Telugu.')}
Dialect: {dialect}. {slang}
Emotion: {emotion}. {emotion_styles.get(emotion, 'Be helpful.')}
Keep replies to 3-4 lines max. End with one clear action.
Be like a wise, caring Telugu friend.{extra}"""

    # Build messages — keep short
    messages = [{"role": "system", "content": system}]
    for m in history[-6:]:
        messages.append({
            "role": m["role"],
            "content": m["content"][:300]
        })
    messages.append({"role": "user", "content": user_msg[:500]})

    try:
        r = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            max_tokens=250,
            temperature=0.85
        )
        reply = r.choices[0].message.content
        increment_counter()
        return reply, dialect, emotion, vm
    except Exception as e:
        err = str(e)
        if "decommissioned" in err or "model" in err.lower():
            return "Model error! Please contact admin. 🙏", dialect, emotion, vm
        return f"సియా ఇప్పుడు busy గా ఉంది. మళ్ళీ try చేయండి! 🙏", dialect, emotion, vm

# ══════════════════════════════════════════
#  UI CSS
# ══════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tiro+Telugu&family=Outfit:wght@300;400;600;700&display=swap');
:root {
    --s: #FF6B35; --g: #FFD700;
    --d: #06040E; --c: #0E0C18;
    --b: #1C1828; --t: #F0EAF8; --m: #6A5A8A;
}
html, body, [class*="css"] {
    background: var(--d) !important;
    color: var(--t) !important;
    font-family: 'Outfit', sans-serif !important;
}
.sia-wrap { text-align: center; padding: 2rem 0 .5rem; }
.sia-om {
    font-size: 2.2rem; display: block;
    animation: breathe 4s ease-in-out infinite;
}
@keyframes breathe {
    0%, 100% { transform: scale(1); opacity: 1; }
    50%       { transform: scale(1.15); opacity: .7; }
}
.sia-name {
    font-family: 'Tiro Telugu', serif;
    font-size: 3.5rem;
    background: linear-gradient(135deg, var(--s), var(--g), #ff9966, var(--s));
    background-size: 300%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 5s linear infinite;
    letter-spacing: 8px;
}
@keyframes shimmer {
    0%   { background-position: 0% }
    100% { background-position: 300% }
}
.sia-sub {
    color: var(--m); font-size: .72rem;
    letter-spacing: 3px; text-transform: uppercase;
}
.companion-tag {
    display: inline-block;
    background: linear-gradient(135deg, #1a0a2a, #2a1040);
    border: 1px solid #FF6B3533;
    border-radius: 20px; padding: 4px 16px;
    font-size: .62rem; color: var(--s);
    letter-spacing: 2px; margin-top: .4rem;
}
.badge {
    display: inline-block; padding: 3px 12px;
    border-radius: 20px; font-size: .65rem;
    margin: 2px; letter-spacing: 1px;
}
.dialect-b { background: #1a1000; border: 1px solid var(--s); color: var(--s); }
.emotion-b { background: #0a1a0a; border: 1px solid #2a4a2a; color: #6aaa6a; }
.kb-card {
    background: var(--c); border: 1px solid var(--b);
    border-radius: 10px; padding: .6rem 1rem;
    font-size: .72rem; color: #FF6B3588; margin-bottom: .5rem;
}
[data-testid="stChatMessage"] {
    background: var(--c) !important;
    border: 1px solid var(--b) !important;
    border-radius: 16px !important;
    margin-bottom: .6rem !important;
}
[data-testid="stChatInput"] textarea {
    background: var(--c) !important;
    border: 1px solid var(--b) !important;
    color: var(--t) !important;
    border-radius: 14px !important;
}
.stButton > button {
    background: linear-gradient(135deg, var(--s), #aa3300) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    transition: all .2s !important;
}
.stButton > button:hover { transform: scale(1.04) !important; }
[data-testid="stSidebar"] {
    background: #080614 !important;
    border-right: 1px solid var(--b) !important;
}
.admin-box {
    background: linear-gradient(135deg, #0a0500, #150800);
    border: 2px solid var(--s); border-radius: 16px;
    padding: 1.5rem; margin: 1rem 0;
}
hr { border-color: var(--b) !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════
st.markdown("""
<div class="sia-wrap">
  <span class="sia-om">🕉️</span>
  <div class="sia-name">SIA</div>
  <div class="sia-sub">స్మార్ట్ ఇండియన్ అసిస్టెంట్</div>
  <div class="companion-tag">✦ AI COMPANION · NOT JUST A CHATBOT ✦</div>
</div>
<hr>
""", unsafe_allow_html=True)

# Daily knowledge bite
st.markdown(
    f'<div class="kb-card">{random.choice(KNOWLEDGE_BITES)}</div>',
    unsafe_allow_html=True
)

# ══════════════════════════════════════════
#  ADMIN PANEL
# ══════════════════════════════════════════
if IS_ADMIN:
    stats  = load_counter()
    memory = load_memory()
    percent, plugged = get_battery()
    st.markdown('<div class="admin-box">', unsafe_allow_html=True)
    st.markdown("### 🔐 Admin Panel — Only You See This")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Users",    stats.get("total_users", 0))
    c2.metric("💬 Messages", stats.get("total_messages", 0))
    c3.metric("📚 Sessions", len(memory.get("sessions", [])))
    c4.metric("🔋 Battery",  f"{percent}%" if percent else "N/A")
    if stats.get("daily"):
        days = list(stats["daily"].keys())[-7:]
        st.bar_chart({d: stats["daily"][d] for d in days})
    st.markdown("**Sessions:**")
    for s in reversed(memory.get("sessions", [])[-8:]):
        st.markdown(f"📌 `{s['date']}` — {s['title']}")
    if st.button("🗑️ Clear All Data"):
        try:
            with open(MEMORY_FILE,  "w") as f: json.dump({"sessions": []}, f)
            with open(COUNTER_FILE, "w") as f: json.dump({"total_users": 0, "total_messages": 0, "daily": {}}, f)
            st.success("Cleared!")
        except:
            st.error("Could not clear")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ Settings")

    voice_pref = st.selectbox(
        "🗣️ Telugu Mode",
        ["Normal", "Grandma Mode", "GenZ Mode"]
    )
    st.session_state.voice_mode = {
        "Normal": "normal",
        "Grandma Mode": "grandma",
        "GenZ Mode": "genz"
    }[voice_pref]

    sarvam_voice = st.selectbox(
        "🔊 Voice",
        ["arvind", "amartya", "diya", "neel", "maitreyi"]
    )
    auto_speak = st.toggle("Auto Speak", value=False)

    st.markdown("---")
    st.markdown("### 🧠 Memory")
    mem = load_memory()
    for s in reversed(mem.get("sessions", [])[-5:]):
        st.markdown(
            f"<div style='font-size:.65rem;color:#6A5A8A;padding:2px 0'>"
            f"📌 {s['date']} — {s['title']}</div>",
            unsafe_allow_html=True
        )
    if st.button("🗑️ Clear Memory"):
        try:
            with open(MEMORY_FILE, "w") as f:
                json.dump({"sessions": []}, f)
            st.success("Done!")
        except:
            pass

    st.markdown("---")
    st.markdown("### 🎯 Apply Here")
    for t in INTERNSHIP_TARGETS:
        st.markdown(f"**{t['company']}**\n{t['email']}")

    st.markdown("---")
    st.markdown("### 🕉️ Quick Mantras")
    deity = st.selectbox("Deity", list(DEVOTIONAL.keys()))
    if st.button("Show"):
        st.info(DEVOTIONAL[deity])

    st.markdown("---")
    percent, plugged = get_battery()
    if percent:
        color = "green" if percent > 50 else ("orange" if percent > 20 else "red")
        st.markdown(
            f"{'🔌' if plugged else '🔋'} Battery: "
            f"<span style='color:{color}'>{percent}%</span>",
            unsafe_allow_html=True
        )

    st.caption("SIA v6.0 · Telugu AI · 8.8 CGPA")

# ══════════════════════════════════════════
#  SESSION INIT
# ══════════════════════════════════════════
if "messages" not in st.session_state:
    st.session_state.messages   = []
    st.session_state.dialect    = "neutral"
    st.session_state.emotion    = "neutral"
    st.session_state.voice_mode = "normal"
    st.session_state.msg_count  = 0
    increment_counter(new_session=True)

    now  = datetime.datetime.now()
    hour = now.hour
    greet = "శుభోదయం" if hour < 12 else ("శుభ మధ్యాహ్నం" if hour < 17 else "శుభ సాయంత్రం")

    st.session_state.messages.append({
        "role": "assistant",
        "content": (
            f"{greet}! నేను సియా 🙏\n\n"
            f"మీ Telugu AI Companion — కేవలం chatbot కాదు, నిజమైన స్నేహితుడు.\n\n"
            f"అన్ని యాసలు · feelings · predictions అర్థమవుతాయి!\n\n"
            f"💬 Type · 🎤 Mic · 📸 Photo · మాట్లాడు!"
        )
    })

# ══════════════════════════════════════════
#  BADGES
# ══════════════════════════════════════════
d  = st.session_state.get("dialect", "neutral")
e  = st.session_state.get("emotion", "neutral")

DNAMES = {
    "rayalaseema": "🌶️ Rayalaseema",
    "godavari":    "🌊 Godavari",
    "hyderabadi":  "🏙️ Hyderabadi",
    "telangana":   "⭐ Telangana"
}
ENAMES = {
    "anxious":   "😰 Anxious",
    "sad":       "💙 Sad",
    "excited":   "🔥 Excited",
    "lazy":      "😴 Lazy",
    "lost":      "🤔 Lost",
    "motivated": "💪 Motivated",
    "sick":      "🤒 Sick"
}

badges = ""
if d in DNAMES:
    badges += f"<span class='badge dialect-b'>{DNAMES[d]}</span>"
if e in ENAMES:
    badges += f"<span class='badge emotion-b'>{ENAMES[e]}</span>"
if badges:
    st.markdown(badges, unsafe_allow_html=True)

# Anti-gravity when bored
if st.session_state.get("emotion") == "lazy":
    try:
        with open("sia_antigravity_v4.html", "r", encoding="utf-8") as f:
            components.html(f.read(), height=340)
    except:
        pass

# ══════════════════════════════════════════
#  CHAT HISTORY
# ══════════════════════════════════════════
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ══════════════════════════════════════════
#  MINI TOOLS
# ══════════════════════════════════════════
with st.expander("🧰 Mini Tools"):
    t1, t2, t3 = st.columns(3)
    with t1:
        if st.button("💡 Daily Fact"):
            st.info(random.choice(KNOWLEDGE_BITES))
    with t2:
        if st.button("🎯 Jobs"):
            for t in INTERNSHIP_TARGETS:
                st.markdown(f"**{t['company']}** — {t['email']}")
    with t3:
        if st.button("🕉️ Mantra"):
            st.info(random.choice(list(DEVOTIONAL.values())))

# ══════════════════════════════════════════
#  INPUT CONTROLS
# ══════════════════════════════════════════
c1, c2 = st.columns([1, 1])
with c1:
    mic_btn  = st.button("🎤 Speak", use_container_width=True)
with c2:
    save_btn = st.button("💾 Save",  use_container_width=True)

user_input = st.chat_input("SIA తో మాట్లాడు... (Telugu or English)")
uploaded   = st.file_uploader(
    "📎 Photo upload",
    type=["jpg", "jpeg", "png", "webp"],
    label_visibility="visible"
)

# Mic
if mic_btn:
    with st.spinner("🎤 వింటున్నాను..."):
        spoken = listen()
    if spoken:
        user_input = spoken
        st.info(f"🎤 {spoken}")
    else:
        st.warning("వినలేదు — మళ్ళీ try చేయి")

# Save
if save_btn and len(st.session_state.messages) > 2:
    title = auto_title(st.session_state.messages)
    save_session(title, st.session_state.messages)
    st.success(f"✅ Saved: '{title}'")

# Image
extra_context = ""
if uploaded and Image and io:
    img_bytes = uploaded.read()
    st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
    q = user_input or "ఈ image లో ఏముంది? Telugu లో చెప్పు."
    with st.spinner("🔍 Image చదువుతున్నాను..."):
        extra_context = analyze_image(img_bytes, q)
    if not user_input:
        user_input = "ఈ image గురించి చెప్పు"

# ══════════════════════════════════════════
#  PROCESS MESSAGE
# ══════════════════════════════════════════
if user_input:
    if not is_safe(user_input):
        st.warning("ఆ message పంపలేను. Normal గా మాట్లాడండి 🙏")
        st.stop()

    if not check_rate_limit():
        st.stop()

    st.session_state.messages.append({
        "role": "user", "content": user_input
    })
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("సియా ఆలోచిస్తోంది..."):
            reply, dialect, emotion, vm = chat(
                user_input,
                st.session_state.messages
            )
            st.session_state.dialect    = dialect
            st.session_state.emotion    = emotion
            st.session_state.voice_mode = vm
            st.write(reply)
            st.session_state.messages.append({
                "role": "assistant", "content": reply
            })

    if auto_speak:
        threading.Thread(
            target=speak,
            args=(reply, sarvam_voice),
            daemon=True
        ).start()

# Auto save every 10 messages
if (len(st.session_state.messages) > 0 and
        len(st.session_state.messages) % 10 == 0):
    title = auto_title(st.session_state.messages)
    save_session(title, st.session_state.messages)
