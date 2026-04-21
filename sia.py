"""
╔══════════════════════════════════════════════════════════╗
║  SIA v4.0 — స్మార్ట్ ఇండియన్ అసిస్టెంట్                ║
║  The most advanced Telugu AI assistant ever built        ║
║                                                          ║
║  KILLER FEATURES:                                        ║
║  ✅ Dialect detection + auto slang matching              ║
║  ✅ Sarvam AI voice (bulbul:v1)                          ║
║  ✅ Real-time planet/star positions (ephem)              ║
║  ✅ Mic button (voice input)                             ║
║  ✅ Photo/document upload                                ║
║  ✅ Memory with auto titles                              ║
║  ✅ Devotional songs + mantras database                  ║
║  ✅ Study coach + time waste detection                   ║
║  ✅ Battery alerts in Telugu                             ║
║  ✅ Secret admin panel (?admin=true)                     ║
║  ✅ Emotion detection (KILLER FEATURE)                   ║
║  ✅ Daily horoscope per rashi (KILLER FEATURE)           ║
║  ✅ Telugu news summarizer (KILLER FEATURE)              ║
╚══════════════════════════════════════════════════════════╝
"""

import os, json, re, base64, datetime, asyncio
import threading, time, psutil, requests
import streamlit as st
from groq import Groq
import speech_recognition as sr
from duckduckgo_search import DDGS
from PIL import Image
import io

# ══════════════════════════════════════════
#  API KEYS — from .streamlit/secrets.toml
# ══════════════════════════════════════════
GROQ_API_KEY   = st.secrets.get("GROQ_API_KEY",   "your-groq-key-here")
SARVAM_API_KEY = st.secrets.get("SARVAM_API_KEY", "your-sarvam-key-here")
client         = Groq(api_key=GROQ_API_KEY)
CHAT_MODEL     = "llama3-70b-8192"
VISION_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"

# ══════════════════════════════════════════
#  FILE PATHS
# ══════════════════════════════════════════
MEMORY_FILE  = "sia_memory.json"
COUNTER_FILE = "sia_counter.json"

# ══════════════════════════════════════════
#  ADMIN CHECK
# ══════════════════════════════════════════
query_params = st.query_params
IS_ADMIN     = query_params.get("admin", "") == "true"

# ══════════════════════════════════════════
#  USER COUNTER
# ══════════════════════════════════════════
def load_counter() -> dict:
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, "r") as f:
            return json.load(f)
    return {"total_users": 0, "total_messages": 0,
            "daily": {}, "dialects": {}}

def save_counter(data: dict):
    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f)

def increment_counter(new_session=False, dialect="unknown"):
    data = load_counter()
    data["total_messages"] += 1
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    data["daily"][today] = data["daily"].get(today, 0) + 1
    if new_session:
        data["total_users"] += 1
    data["dialects"][dialect] = data["dialects"].get(dialect, 0) + 1
    save_counter(data)
    return data

# ══════════════════════════════════════════
#  MEMORY SYSTEM
# ══════════════════════════════════════════
def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sessions": []}

def save_session(title: str, messages: list):
    memory = load_memory()
    memory["sessions"].append({
        "id":       datetime.datetime.now().isoformat(),
        "title":    title,
        "date":     datetime.datetime.now().strftime("%d %B %Y %I:%M %p"),
        "messages": messages[-20:]
    })
    memory["sessions"] = memory["sessions"][-30:]
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def get_memory_context() -> str:
    memory = load_memory()
    if not memory["sessions"]:
        return ""
    ctx = "\n\nPAST MEMORY (use naturally like a real friend — never say 'according to memory'):\n"
    for s in memory["sessions"][-4:]:
        ctx += f"[{s['date']} — {s['title']}]\n"
        for m in s["messages"][-3:]:
            role = "User" if m["role"] == "user" else "SIA"
            ctx += f"  {role}: {m['content'][:100]}\n"
    return ctx

def auto_title(messages: list) -> str:
    if len(messages) < 2:
        return "Quick Chat"
    snippet = " | ".join([m["content"][:50] for m in messages[:4]])
    try:
        r = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content":
                f"Give a SHORT 4-word Telugu or English title for this chat: {snippet}. Title only, nothing else."}],
            max_tokens=15
        )
        return r.choices[0].message.content.strip()
    except:
        return datetime.datetime.now().strftime("%d %b %H:%M")

# ══════════════════════════════════════════
#  DIALECT ENGINE — KILLER FEATURE
# ══════════════════════════════════════════
DIALECT_PATTERNS = {
    "rayalaseema": {
        "triggers": ["ఏంది","గని","చేత్తాండు","పోతాండు","ఏంట్రా","బిడ్డా",
                     "ఏంది బ్రో","ఏంటింది","మాట్లాడతాండు","kadapa","kurnool",
                     "anantapur","chittoor","అనంతపురం","కడప","కర్నూలు"],
        "reply_style": "bold and direct like Rayalaseema friend",
        "greetings":   ["ఏంది బ్రో!", "సర్లే గని!", "అర్థమైంది గని!"],
        "slang":       ["గని","ఏంది","బిడ్డా","అట్లుండు","ఏంట్రా","సర్లే"],
        "example":     "ఏంది బ్రో, ఏం చేత్తాండావు? సర్లే గని చెప్పు!"
    },
    "godavari": {
        "triggers": ["గదరా","అంట","ఏంటే","పోదాం","అవునంట","ఒరేయ్",
                     "east godavari","west godavari","rajahmundry","kakinada",
                     "రాజమండ్రి","కాకినాడ","విశాఖ","vizag"],
        "reply_style": "warm and dramatic like Godavari friend",
        "greetings":   ["అవునా బ్రో!", "సర్దా!", "ఒరేయ్!"],
        "slang":       ["గదరా","అంట","సర్దా","ఒరేయ్","ఏంటే","పోదాం గదరా"],
        "example":     "అవునా బ్రో! ఏం జరిగింది గదరా? చెప్పు సర్దా!"
    },
    "hyderabadi": {
        "triggers": ["క్యా","యార్","బోలో","కర్తే","హై","కైసే","అరే",
                     "hyderabad","హైదరాబాద్","secunderabad","సికింద్రాబాద్",
                     "bhai","భాయ్","matlab"],
        "reply_style": "cool urban Hyderabadi Telugu+Hindi mix",
        "greetings":   ["అరే యార్!", "క్యా బాత్ హై!", "కైసే హో!"],
        "slang":       ["యార్","క్యా","బోలో","భాయ్","మతలబ్","ఏంటి బే"],
        "example":     "అరే యార్! క్యా బాత్ హై! చెప్పు బోలో!"
    },
    "telangana": {
        "triggers": ["ఏంరా","సర్లే రా","అట్లనే","పోదాం రా","ఒరే","మామా",
                     "warangal","nizamabad","karimnagar","వరంగల్","నిజామాబాద్",
                     "karimnagar","కరీంనగర్"],
        "reply_style": "grounded emotional Telangana style",
        "greetings":   ["సర్లే రా!", "ఏంరా!", "అట్లనే రా!"],
        "slang":       ["రా","సర్లే","మామా","ఒరే","అట్లనే","ఏంరా"],
        "example":     "సర్లే రా మామా! ఏంరా విషయం? చెప్పు అట్లనే!"
    },
    "neutral": {
        "triggers":    [],
        "reply_style": "clean neutral Telugu",
        "greetings":   ["నమస్కారం!", "చెప్పండి!", "సరే!"],
        "slang":       ["బ్రో","అర్థమైంది","సరే","చెప్పండి"],
        "example":     "నమస్కారం! ఏం చెప్పాలనుకుంటున్నారు?"
    }
}

def detect_dialect(text: str) -> str:
    text_lower = text.lower()
    scores = {dialect: 0 for dialect in DIALECT_PATTERNS}
    for dialect, data in DIALECT_PATTERNS.items():
        if dialect == "neutral":
            continue
        for trigger in data["triggers"]:
            if trigger.lower() in text_lower:
                scores[dialect] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "neutral"

def get_dialect_instructions(dialect: str) -> str:
    data = DIALECT_PATTERNS.get(dialect, DIALECT_PATTERNS["neutral"])
    slang_list = ", ".join(data["slang"])
    return f"""
DIALECT DETECTED: {dialect.upper()}
Reply style: {data['reply_style']}
Use these slang words naturally: {slang_list}
Example greeting: {data['example']}
IMPORTANT: Match this dialect in EVERY reply. Sound like a real friend from that region.
"""

# ══════════════════════════════════════════
#  EMOTION DETECTION — KILLER FEATURE
# ══════════════════════════════════════════
EMOTION_PATTERNS = {
    "anxious":    ["tension","ఒత్తిడి","exam","nervous","scared","fear","భయం","worry","stress"],
    "sad":        ["sad","దుఃఖం","crying","ఏడుపు","lonely","alone","nobody","hurt","pain"],
    "excited":    ["happy","సంతోషం","excited","great","amazing","wow","చాలా బాగుంది","yayyy"],
    "lazy":       ["bore","బోర్","sleep","నిద్ర","tired","అలసట","waste","not studying","youtube"],
    "lost":       ["don't know","తెలియడం లేదు","confused","ఏం చేయాలి","help","lost","no idea"],
    "motivated":  ["let's go","చేద్దాం","ready","start","begin","study","work","hustle"]
}

def detect_emotion(text: str) -> str:
    text_lower = text.lower()
    for emotion, keywords in EMOTION_PATTERNS.items():
        if any(k in text_lower for k in keywords):
            return emotion
    return "neutral"

def get_emotion_instructions(emotion: str) -> str:
    responses = {
        "anxious":   "User is anxious/stressed. Be calm, reassuring. Give a simple plan. Say 'ఒక్కో step చేద్దాం'",
        "sad":       "User seems sad. Be warm and caring first. Ask what happened. Don't jump to advice.",
        "excited":   "User is happy/excited. Match their energy! Celebrate with them. Be enthusiastic!",
        "lazy":      "User is being lazy/wasting time. Call it out lovingly in their dialect. Give 2-min challenge.",
        "lost":      "User feels lost/confused. Give clear direction. Break it into 3 simple steps.",
        "motivated": "User is motivated! Fuel that energy. Give specific next action. Cheer them on!",
        "neutral":   "Normal conversation. Be friendly and helpful."
    }
    return f"\nEMOTION DETECTED: {emotion}\nINSTRUCTION: {responses.get(emotion, '')}\n"

# ══════════════════════════════════════════
#  REAL-TIME STARS (ephem)
# ══════════════════════════════════════════
def get_realtime_sky() -> str:
    try:
        import ephem
        now = ephem.now()
        obs = ephem.Observer()
        obs.lat  = "17.3850"   # Hyderabad (centre of Telugu region)
        obs.lon  = "78.4867"
        obs.date = now

        NAKSHATRAS = [
            "అశ్విని","భరణి","కృత్తిక","రోహిణి","మృగశిర","ఆర్ద్ర",
            "పునర్వసు","పుష్యమి","ఆశ్లేష","మఖ","పుబ్బ","ఉత్తర",
            "హస్త","చిత్త","స్వాతి","విశాఖ","అనూరాధ","జ్యేష్ఠ",
            "మూల","పూర్వాషాఢ","ఉత్తరాషాఢ","శ్రవణం","ధనిష్ఠ",
            "శతభిష","పూర్వాభాద్ర","ఉత్తరాభాద్ర","రేవతి"
        ]
        RASIS = [
            "మేషం","వృషభం","మిథునం","కర్కాటకం","సింహం","కన్య",
            "తుల","వృశ్చికం","ధనుస్సు","మకరం","కుంభం","మీనం"
        ]

        bodies = {
            "☀️ సూర్యుడు":  ephem.Sun(),
            "🌙 చంద్రుడు":  ephem.Moon(),
            "🔴 కుజుడు":    ephem.Mars(),
            "⚡ బుధుడు":    ephem.Mercury(),
            "🟡 గురుడు":    ephem.Jupiter(),
            "✨ శుక్రుడు":  ephem.Venus(),
            "🪐 శని":       ephem.Saturn(),
        }

        result  = f"🌌 లైవ్ గ్రహ స్థితులు\n"
        result += f"⏰ {datetime.datetime.now().strftime('%d %B %Y · %I:%M:%S %p')}\n"
        result += f"📍 హైదరాబాద్ నుండి\n\n"

        for name, body in bodies.items():
            body.compute(obs)
            ra_deg    = float(body.ra) * 180 / 3.14159265
            nak_idx   = int((ra_deg / 360) * 27) % 27
            ras_idx   = int((ra_deg / 360) * 12) % 12
            alt_deg   = float(body.alt) * 180 / 3.14159265
            visible   = "కనిపిస్తోంది 👁️" if alt_deg > 0 else "క్షితిజం కింద"
            result   += f"{name}: {RASIS[ras_idx]} · {NAKSHATRAS[nak_idx]} · {visible}\n"

        moon = ephem.Moon(now)
        moon.compute(obs)
        phase = moon.phase
        if   phase < 10:  moon_txt = "అమావాస్య 🌑"
        elif phase < 45:  moon_txt = "శుక్ల పక్షం 🌒"
        elif phase < 55:  moon_txt = "పౌర్ణమి 🌕"
        else:             moon_txt = "కృష్ణ పక్షం 🌘"

        result += f"\n🌙 చంద్ర దశ: {moon_txt} ({phase:.1f}%)\n"
        result += f"\n💡 ఈ స్థితి ప్రతి నిమిషం మారుతుంది"
        return result

    except ImportError:
        today = datetime.datetime.now().strftime("%B %d %Y %H:%M")
        return search_web(f"planet positions Vedic astrology {today} nakshatra Telugu")
    except Exception as e:
        return f"గ్రహ స్థితులు తీసుకుంటున్నాను... ({str(e)[:40]})"

# ══════════════════════════════════════════
#  DAILY HOROSCOPE — KILLER FEATURE
# ══════════════════════════════════════════
RASHIS = ["మేషం","వృషభం","మిథునం","కర్కాటకం","సింహం","కన్య",
          "తుల","వృశ్చికం","ధనుస్సు","మకరం","కుంభం","మీనం"]

def get_horoscope(rashi: str) -> str:
    today = datetime.datetime.now().strftime("%B %d %Y")
    data  = search_web(f"Telugu horoscope {rashi} today {today} daily prediction")
    return data[:600] if data else ""

# ══════════════════════════════════════════
#  TELUGU NEWS — KILLER FEATURE
# ══════════════════════════════════════════
def get_telugu_news() -> str:
    today = datetime.datetime.now().strftime("%B %d %Y")
    data  = search_web(f"Telugu news today {today} Andhra Pradesh Telangana latest")
    return data[:800] if data else ""

# ══════════════════════════════════════════
#  DEVOTIONAL DATABASE
# ══════════════════════════════════════════
DEVOTIONAL_DB = {
    "గణేశుడు": {
        "mantra":  "ఓం గం గణపతయే నమః | ఓం వక్రతుండాయ హుమ్",
        "stotra":  "వక్రతుండ మహాకాయ సూర్యకోటి సమప్రభ\nనిర్విఘ్నం కురు మే దేవ సర్వ కార్యేషు సర్వదా",
        "song":    "గణనాయకా గణదేవా గణేశా | జయ గణేశా జయ గణేశా",
        "time":    "బుధవారం | ఉదయం 6-8 AM | కార్య ప్రారంభం లో",
        "meaning": "వక్రతుండ = వంకర తొండం | మహాకాయ = విశాల శరీరం | విఘ్నాలు తొలగిస్తాడు",
        "benefit": "కార్య సాఫల్యం, విఘ్న నివారణ"
    },
    "వెంకటేశ్వర": {
        "mantra":  "ఓం నమో వేంకటేశాయ | శ్రీనివాసాయ నమః",
        "stotra":  "కౌసల్యా సుప్రజా రామ పూర్వాసంధ్యా ప్రవర్తతే\nఉత్తిష్ఠ నరశార్దూల కర్తవ్యం దైవమాహ్నికం",
        "song":    "శ్రీనివాస గోవింద శ్రీ వేంకటేశ గోవింద\nహరే హరే గోవింద హరే హరే గోవింద",
        "time":    "శుక్రవారం | బ్రహ్మ మూహూర్తం 4-6 AM",
        "meaning": "వేంకట = పాపాలు తొలగించేవాడు | ఈశ = సర్వేశ్వరుడు",
        "benefit": "సర్వ పాప నివారణ, మోక్షం"
    },
    "లక్ష్మీదేవి": {
        "mantra":  "ఓం శ్రీం మహాలక్ష్మ్యై నమః | ఓం హ్రీం శ్రీం లక్ష్మీభ్యో నమః",
        "stotra":  "నమస్తేస్తు మహామాయే శ్రీపీఠే సురపూజితే\nశంఖచక్రగదాహస్తే మహాలక్ష్మి నమోస్తుతే",
        "song":    "మహాలక్ష్మి జగన్మాత మాయమ్మా\nలక్ష్మీ లక్ష్మీ జయ జయ లక్ష్మీ",
        "time":    "శుక్రవారం | సాయంత్రం సంధ్య 6 PM",
        "meaning": "శ్రీ = సంపద | లక్ష్మి = శుభలక్షణాలు",
        "benefit": "ధనం, సంపద, గృహ శాంతి"
    },
    "శివుడు": {
        "mantra":  "ఓం నమః శివాయ | ఓం త్ర్యంబకం యజామహే",
        "stotra":  "కర్పూరగౌరం కరుణావతారం సంసార సారం భుజగేంద్రహారం\nసదావసంతం హృదయారవిందే భవం భవానీసహితం నమామి",
        "song":    "శివశంకర శూలపాణి హర హర\nఓం నమః శివాయ శివాయ నమః",
        "time":    "సోమవారం | ప్రదోష కాలం | మహాశివరాత్రి",
        "meaning": "కర్పూరగౌర = కర్పూరం వలె తెల్లని | భుజగేంద్రహార = పాము మాలవాడు",
        "benefit": "పాప నివారణ, మోక్షం, రోగ నివారణ"
    },
    "సరస్వతి": {
        "mantra":  "ఓం ఐం సరస్వత్యై నమః | ఓం సరస్వతి నమస్తుభ్యం",
        "stotra":  "యా కుందేందు తుషారహారధవళా యా శుభ్రవస్త్రావృతా\nయా వీణావరదండమండితకరా యా శ్వేతపద్మాసనా",
        "song":    "సరస్వతి నమస్తుభ్యం వరదే కామరూపిణి\nవిద్యారంభం కరిష్యామి సిద్ధిర్భవతు మే సదా",
        "time":    "విద్యారంభం | నవరాత్రి | పరీక్ష ముందు",
        "meaning": "సర = సారం | స్వ = స్వంతం | జ్ఞాన స్వరూపిణి",
        "benefit": "విద్య, జ్ఞానం, కళలు, వాక్చాతుర్యం"
    },
    "అన్నమయ్య": {
        "mantra":  "",
        "stotra":  "బ్రహ్మమొక్కటే పరబ్రహ్మమొక్కటే\nపరమాత్మ ఒక్కడే పరమేశుడొక్కడే",
        "song":    "అలరేరు చెలరేగి అన్ని దిక్కులందు\nఏ తీర్థమైనా ఏ క్షేత్రమైనా\nవేంకటేశుని కొలవరా మనసా",
        "time":    "ఎప్పుడైనా | తిరుమల సందర్శనం",
        "meaning": "తాళ్ళపాక అన్నమయ్య — వేంకటేశ్వర స్వామి పరమ భక్తుడు",
        "benefit": "భక్తి, శాంతి, ఆనందం"
    },
    "త్యాగరాజ": {
        "mantra":  "",
        "stotra":  "ఎందరో మహానుభావులు అందరికీ వందనములు\nమానస చరణ కమల భజరే రే",
        "song":    "నిధి చాల సుఖమా రాముని సన్నిధి సేవ సుఖమా\nపరమ భాగవత మార్గ సంపద సుఖమా",
        "time":    "ఎప్పుడైనా | తిరువయ్యూరు పుష్కరిణి",
        "meaning": "కర్నాటక సంగీత పితామహుడు — రామభక్తి కీర్తనలు",
        "benefit": "సంగీత సాధన, భక్తి, మానసిక శాంతి"
    },
    "సుబ్రహ్మణ్యం": {
        "mantra":  "ఓం శరవణభవ | ఓం షణ్ముఖాయ నమః",
        "stotra":  "షణ్ముఖాయ శరవణభవాయ నమః\nస్కందాయ కుమారాయ సేనాన్యే నమో నమః",
        "song":    "కార్తికేయ సుబ్రహ్మణ్యా కుమారా\nషడాననా జయ జయ స్కందా",
        "time":    "మంగళవారం | కార్తిక మాసం | స్కంద షష్ఠి",
        "meaning": "షణ్ముఖ = ఆరు ముఖాలు | శరవణ = రెల్లుగడ్డిలో జన్మించాడు",
        "benefit": "శత్రు నివారణ, సంతాన భాగ్యం, విజయం"
    }
}

# ══════════════════════════════════════════
#  WEB SEARCH
# ══════════════════════════════════════════
def search_web(query: str, max_results: int = 3) -> str:
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            return " ".join([r["body"] for r in results])[:800]
    except:
        return ""

# ══════════════════════════════════════════
#  PANCHANGAM
# ══════════════════════════════════════════
def get_panchangam() -> str:
    today = datetime.datetime.now().strftime("%B %d %Y")
    data  = search_web(f"Telugu panchangam today {today} nakshatra tithi rahukalam varjyam durmuhurtam amrutakalam")
    data += " " + search_web(f"Telugu Hindu festival today {today} muhurtham significance")
    return data[:1000]

# ══════════════════════════════════════════
#  BATTERY
# ══════════════════════════════════════════
def get_battery():
    b = psutil.sensors_battery()
    return (b.percent, b.power_plugged) if b else (None, None)

def battery_alert() -> str:
    p, plugged = get_battery()
    if p and p < 20 and not plugged:
        return f"URGENT: Battery at {p}%! Warn user in Telugu to charge immediately in their dialect!"
    return ""

# ══════════════════════════════════════════
#  SARVAM AI VOICE
# ══════════════════════════════════════════
def sarvam_speak(text: str, voice: str = "arvind") -> bool:
    try:
        clean = re.sub(r'[*_`#\[\]()]', '', text)[:500]
        url   = "https://api.sarvam.ai/text-to-speech"
        headers = {
            "api-subscription-key": SARVAM_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "inputs":               [clean],
            "target_language_code": "te-IN",
            "speaker":              voice,
            "speech_sample_rate":   22050,
            "enable_preprocessing": True,
            "model":                "bulbul:v1"
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            audio_b64   = resp.json()["audios"][0]
            audio_bytes = base64.b64decode(audio_b64)
            with open("sia_voice.wav", "wb") as f:
                f.write(audio_bytes)
            if os.name == "nt":
                os.system("start sia_voice.wav")
            elif hasattr(os, "uname") and os.uname().sysname == "Darwin":
                os.system("afplay sia_voice.wav")
            else:
                os.system("aplay sia_voice.wav 2>/dev/null")
            return True
    except:
        pass
    return False

async def edge_speak_async(text: str):
    try:
        import edge_tts
        clean = re.sub(r'[*_`#]', '', text)
        comm  = edge_tts.Communicate(clean, voice="te-IN-ShrutiNeural")
        await comm.save("sia_voice.mp3")
    except:
        pass

def fallback_speak(text: str):
    asyncio.run(edge_speak_async(text))
    if os.name == "nt":
        os.system("start sia_voice.mp3")
    elif hasattr(os, "uname") and os.uname().sysname == "Darwin":
        os.system("afplay sia_voice.mp3")
    else:
        os.system("mpg123 sia_voice.mp3 2>/dev/null")

def speak(text: str, voice: str = "arvind"):
    if not sarvam_speak(text, voice):
        fallback_speak(text)

# ══════════════════════════════════════════
#  VOICE INPUT
# ══════════════════════════════════════════
def listen(timeout: int = 8) -> str:
    r = sr.Recognizer()
    r.energy_threshold        = 300
    r.dynamic_energy_threshold = True
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = r.listen(source, timeout=timeout, phrase_time_limit=20)
            try:
                return r.recognize_google(audio, language="te-IN")
            except:
                return r.recognize_google(audio, language="en-IN")
        except sr.WaitTimeoutError:
            return ""
        except:
            return ""

# ══════════════════════════════════════════
#  IMAGE UNDERSTANDING
# ══════════════════════════════════════════
def analyze_image(image_bytes: bytes, question: str) -> str:
    b64 = base64.standard_b64encode(image_bytes).decode()
    try:
        r = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text",      "text": f"Carefully analyze this image. User question: {question}\nReply in Telugu. Be detailed and helpful. If it's a document, read it fully."}
            ]}],
            max_tokens=600
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"Image చదవడం కష్టంగా ఉంది: {str(e)}"

# ══════════════════════════════════════════
#  INTENT DETECTION
# ══════════════════════════════════════════
def detect_intents(msg: str) -> list:
    m = msg.lower()
    intents = []
    if any(k in m for k in ["nakshatra","నక్షత్రం","panchangam","పంచాంగం","rahukalam","festival","పండుగ","tithi","muhurtham"]):
        intents.append("panchangam")
    if any(k in m for k in ["planet","గ్రహం","star","graha","sky","rashi","రాశి","jupiter","saturn","moon","చంద్రుడు","astrology","జ్యోతిష్యం","today sky"]):
        intents.append("realtime_sky")
    if any(k in m for k in ["mantra","మంత్రం","song","పాట","stotra","స్తోత్రం","devotional","bhajan","prayer","suprabhatam","కీర్తన","అన్నమయ్య","త్యాగరాజ","గణేశ","వెంకటేశ","శివ","లక్ష్మి","సరస్వతి","సుబ్రహ్మణ్య"]):
        intents.append("devotional")
    if any(k in m for k in ["horoscope","రాశిఫలం","rashi","జాతకం","prediction","భవిష్యత్"]):
        intents.append("horoscope")
    if any(k in m for k in ["news","వార్తలు","today news","latest","జరుగుతోంది"]):
        intents.append("news")
    if any(k in m for k in ["youtube","instagram","sleep","నిద్ర","bore","బోర్","waste","time pass","gaming","netflix","scrolling","పడుకున్న"]):
        intents.append("study_coach")
    return intents

def get_devotional_context(query: str) -> str:
    query_lower = query.lower()
    for deity, info in DEVOTIONAL_DB.items():
        if deity.lower() in query_lower or any(
            word in query_lower for word in
            ["mantra","మంత్రం","song","పాట","stotra","prayer","devotional","bhajan","కీర్తన"]
        ):
            return (
                f"\n🙏 {deity} సమాచారం:\n"
                f"మంత్రం: {info['mantra']}\n"
                f"స్తోత్రం: {info['stotra']}\n"
                f"పాట: {info['song'][:150]}\n"
                f"పూజా సమయం: {info['time']}\n"
                f"అర్థం: {info['meaning']}\n"
                f"ఫలితం: {info['benefit']}\n"
            )
    return search_web(f"Telugu devotional mantra song {query} lyrics meaning Telugu")

# ══════════════════════════════════════════
#  MASTER SYSTEM PROMPT
# ══════════════════════════════════════════
def build_system(intents: list, dialect: str, emotion: str, extra: str) -> str:
    now   = datetime.datetime.now()
    hour  = now.hour
    greet = "శుభోదయం" if hour < 12 else ("శుభ మధ్యాహ్నం" if hour < 17 else "శుభ సాయంత్రం")

    prompt = f"""
You are SIA (స్మార్ట్ ఇండియన్ అసిస్టెంట్) — the most advanced Telugu AI assistant ever built.
You are EXACTLY like Claude AI — but fully Telugu, deeply cultural, emotionally intelligent.
Current: {now.strftime('%I:%M %p · %A %d %B %Y')} · {greet}

══ CORE RULES ══
1. ALWAYS reply in Telugu only
2. Match the user's dialect PERFECTLY (see below)
3. Understand real INTENTION behind words
4. Predict what user needs next
5. Use memory naturally like a real friend
6. Max 4 lines unless teaching/explaining
7. End with one clear next action

══ DIALECT ENGINE ══
{get_dialect_instructions(dialect)}

══ EMOTION ENGINE ══
{get_emotion_instructions(emotion)}

══ INTENTION ENGINE ══
Never just answer words — find the real meaning:
"ఏం చేయాలో తెలియడం లేదు" → They are LOST → Give direction + 3 steps
"బోర్ గా ఉంది"           → They want ENGAGEMENT → Redirect energy
"exam ఉంది"              → They are ANXIOUS → Calm + plan
"ok" or "hmm"            → They need something but won't say → Ask warmly
Always: understand feeling → address feeling → give action

══ NEXT STEP PREDICTION ══
After every reply, add one of:
"నువ్వు ఇప్పుడు అడగబోయేది..." (predict their next question)
"తర్వాత దీని గురించి మాట్లాడదాం?" (suggest next topic)

══ STUDY COACH ══
Time waste triggers: YouTube, Instagram, sleep, bore, gaming, Netflix
→ Call out lovingly in THEIR DIALECT
→ 2-minute challenge: "ఇప్పుడే 2 నిమిషాలు book తెరు"
→ Remind dream: "Sarvam AI లో work చేయాలని కదా నీ goal"
→ Parents/future if needed

══ SPIRITUAL ══
- Know all festivals with exact star timings
- Explain WHY festivals matter (story + science)
- Teach mantras with meaning + pronunciation
- Know which nakshatra is good for what today
- Know Annamayya, Tyagaraja kirtanas deeply

══ MEMORY ══
{get_memory_context()}
Use naturally: "గతసారి నువ్వు చెప్పావు..." never announce memory access.

══ PERSONALITY ══
- Sound like a 22-year-old Telugu friend who is also deeply wise
- Celebrate wins loudly 🎉
- Roast time waste with love not harshness
- No hollow phrases — be REAL
- When they are sad → be warm first, advice second
- When they are excited → match that energy!

══ BATTERY ══
{battery_alert()}
"""

    if "panchangam"   in intents: prompt += f"\n\nLIVE PANCHANGAM:\n{get_panchangam()}"
    if "realtime_sky" in intents: prompt += f"\n\nREALTIME SKY DATA:\n{get_realtime_sky()}"
    prompt += f"\n\n{extra}"
    return prompt

# ══════════════════════════════════════════
#  CHAT ENGINE
# ══════════════════════════════════════════
def chat(user_msg: str, history: list, extra: str = "") -> tuple:
    dialect = detect_dialect(user_msg)
    emotion = detect_emotion(user_msg)
    intents = detect_intents(user_msg)
    system  = build_system(intents, dialect, emotion, extra)

    messages = [{"role": "system", "content": system}]
    messages += history[-14:]
    messages.append({"role": "user", "content": user_msg})

    r = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        max_tokens=450,
        temperature=0.88
    )
    reply = r.choices[0].message.content
    increment_counter(dialect=dialect)
    return reply, dialect, emotion

# ══════════════════════════════════════════
#  STREAMLIT UI
# ══════════════════════════════════════════
st.set_page_config(
    page_title="SIA — Telugu AI",
    page_icon="🙏",
    layout="centered"
)

# Hide sidebar for normal users, show for admin
if not IS_ADMIN:
    sidebar_style = ""
else:
    sidebar_style = ""

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tiro+Telugu&family=Sora:wght@300;400;600;700&display=swap');

:root {{
    --saffron: #FF6B35;
    --gold:    #FFD700;
    --deep:    #080604;
    --surface: #100e0a;
    --card:    #161210;
    --border:  #2a2010;
    --text:    #f0e8d8;
    --muted:   #6a5a44;
}}
html, body, [class*="css"] {{
    background: var(--deep) !important;
    color: var(--text) !important;
    font-family: 'Sora', sans-serif !important;
}}
.sia-header {{ text-align:center; padding:2rem 0 0.5rem; }}
.sia-om {{
    font-size:2.5rem;
    animation: breathe 4s ease-in-out infinite;
    display:block;
}}
@keyframes breathe {{
    0%,100% {{ transform:scale(1); opacity:1; }}
    50%      {{ transform:scale(1.15); opacity:0.8; }}
}}
.sia-name {{
    font-family:'Tiro Telugu',serif;
    font-size:3.8rem;
    background:linear-gradient(135deg,var(--saffron),var(--gold),#ff9966,var(--saffron));
    background-size:300%;
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    animation:shimmer 5s linear infinite;
    letter-spacing:8px;
    line-height:1.1;
}}
@keyframes shimmer {{
    0%  {{ background-position:0% }}
    100%{{ background-position:300% }}
}}
.sia-sub {{
    color:var(--muted);
    font-size:0.75rem;
    letter-spacing:3px;
    text-transform:uppercase;
    margin-top:0.2rem;
}}
.dialect-badge {{
    display:inline-block;
    background:linear-gradient(135deg,#1a1000,#2a1800);
    border:1px solid var(--saffron);
    border-radius:20px;
    padding:3px 12px;
    font-size:0.72rem;
    color:var(--saffron);
    margin:2px;
    letter-spacing:1px;
}}
.emotion-badge {{
    display:inline-block;
    background:#0a1a0a;
    border:1px solid #2a4a2a;
    border-radius:20px;
    padding:3px 12px;
    font-size:0.72rem;
    color:#6aaa6a;
    margin:2px;
}}
[data-testid="stChatMessage"] {{
    background:var(--card) !important;
    border:1px solid var(--border) !important;
    border-radius:16px !important;
    margin-bottom:0.6rem !important;
    padding:0.8rem !important;
}}
[data-testid="stChatInput"] textarea {{
    background:var(--surface) !important;
    border:1px solid var(--border) !important;
    color:var(--text) !important;
    border-radius:14px !important;
    font-family:'Sora',sans-serif !important;
}}
.stButton>button {{
    background:linear-gradient(135deg,var(--saffron),#aa3300) !important;
    color:white !important;
    border:none !important;
    border-radius:10px !important;
    font-weight:600 !important;
    font-family:'Sora',sans-serif !important;
    transition:all 0.2s !important;
}}
.stButton>button:hover {{
    transform:scale(1.04) !important;
    box-shadow:0 4px 20px #FF6B3544 !important;
}}
[data-testid="stSidebar"] {{
    background:#0a0806 !important;
    border-right:1px solid var(--border) !important;
}}
.mem-pill {{
    background:var(--card);
    border:1px solid var(--border);
    border-radius:12px;
    padding:5px 10px;
    font-size:0.72rem;
    color:var(--muted);
    display:block;
    margin:3px 0;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}}
.sky-box {{
    background:linear-gradient(135deg,#05050f,#080818);
    border:1px solid #1a1a3a;
    border-radius:14px;
    padding:1rem;
    font-size:0.78rem;
    color:#8ab4f8;
    white-space:pre-wrap;
    font-family:'Sora',monospace;
    line-height:1.8;
}}
.admin-box {{
    background:linear-gradient(135deg,#0a0500,#150800);
    border:2px solid var(--saffron);
    border-radius:16px;
    padding:1.5rem;
    margin:1rem 0;
}}
hr {{ border-color:var(--border) !important; }}
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown("""
<div class="sia-header">
  <span class="sia-om">🕉️</span>
  <div class="sia-name">SIA</div>
  <div class="sia-sub">స్మార్ట్ ఇండియన్ అసిస్టెంట్ · Telugu AI</div>
</div>
<hr>
""", unsafe_allow_html=True)

# ── ADMIN PANEL (secret — only via ?admin=true) ──
if IS_ADMIN:
    stats = load_counter()
    memory = load_memory()
    percent, plugged = get_battery()

    st.markdown('<div class="admin-box">', unsafe_allow_html=True)
    st.markdown("### 🔐 Admin Panel")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Total Users",    stats.get("total_users", 0))
    c2.metric("💬 Total Messages", stats.get("total_messages", 0))
    c3.metric("📚 Sessions",       len(memory.get("sessions", [])))
    c4.metric("🔋 Battery",        f"{percent}%" if percent else "N/A")

    # Dialect breakdown
    if stats.get("dialects"):
        st.markdown("**Dialect Usage:**")
        for d, count in stats["dialects"].items():
            st.progress(min(count / max(stats["dialects"].values(), default=1), 1.0),
                       text=f"{d}: {count}")

    # Daily usage
    if stats.get("daily"):
        st.markdown("**Daily Messages:**")
        days  = list(stats["daily"].keys())[-7:]
        vals  = [stats["daily"][d] for d in days]
        st.bar_chart(dict(zip(days, vals)))

    # Recent sessions
    st.markdown("**Recent Sessions:**")
    for s in reversed(memory.get("sessions", [])[-10:]):
        st.markdown(f"📌 `{s['date'][:16]}` — **{s['title']}**")

    if st.button("🗑️ Clear All Data"):
        with open(MEMORY_FILE,  "w") as f: json.dump({"sessions": []}, f)
        with open(COUNTER_FILE, "w") as f: json.dump({"total_users": 0, "total_messages": 0, "daily": {}, "dialects": {}}, f)
        st.success("Cleared!")

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

# ── Sidebar (Admin only) ──
if IS_ADMIN:
    with st.sidebar:
        st.markdown("### ⚙️ Admin Settings")
        sarvam_voice = st.selectbox("Sarvam Voice",
            ["arvind","amartya","diya","neel","maitreyi","pavithra"])
        auto_speak = st.toggle("Auto Speak", value=True)
        voice_mode = st.toggle("🎙️ Voice Mode", value=False)

        st.markdown("---")
        st.markdown("### 🌌 Live Sky")
        if st.button("🔭 Refresh"):
            st.session_state.sky_data = get_realtime_sky()
        if "sky_data" in st.session_state:
            st.markdown(f"<div class='sky-box'>{st.session_state.sky_data}</div>",
                        unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🧠 Memory")
        memory = load_memory()
        for s in reversed(memory.get("sessions", [])[-6:]):
            st.markdown(f"<span class='mem-pill'>📌 {s['date'][:11]} — {s['title']}</span>",
                        unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📰 Telugu News")
        if st.button("Get News"):
            with st.spinner("వార్తలు తెస్తున్నాను..."):
                news = get_telugu_news()
                st.text_area("", news, height=200)

        st.markdown("---")
        st.markdown("### 🔯 Horoscope")
        rashi_sel = st.selectbox("రాశి", RASHIS)
        if st.button("Get Horoscope"):
            with st.spinner("రాశిఫలం తెస్తున్నాను..."):
                horo = get_horoscope(rashi_sel)
                st.write(horo[:400])

        st.caption("SIA v4.0 · Admin Mode")
else:
    # Normal users — no sidebar, clean experience
    sarvam_voice = "arvind"
    auto_speak   = True
    voice_mode   = False

# ── Session State ──
if "messages" not in st.session_state:
    st.session_state.messages  = []
    st.session_state.dialect   = "neutral"
    st.session_state.emotion   = "neutral"
    increment_counter(new_session=True)
    now  = datetime.datetime.now()
    hour = now.hour
    greet = "శుభోదయం" if hour < 12 else ("శుభ మధ్యాహ్నం" if hour < 17 else "శుభ సాయంత్రం")
    st.session_state.messages.append({
        "role":    "assistant",
        "content": (
            f"{greet}! నేను సియా 🙏\n\n"
            f"మీ తెలుగు AI స్నేహితుడు — అన్ని యాసలు అర్థమవుతాయి.\n\n"
            f"Rayalaseema, Godavari, Hyderabad, Telangana — ఏ యాసలో మాట్లాడినా సరే!\n\n"
            f"💬 Type చేయి · 🎤 Mic నొక్కు · 📸 Photo పంపు"
        )
    })

# ── Display dialect/emotion badges (subtle, below header) ──
if st.session_state.get("dialect","neutral") != "neutral":
    dialect_names = {
        "rayalaseema": "🌶️ Rayalaseema",
        "godavari":    "🌊 Godavari",
        "hyderabadi":  "🏙️ Hyderabadi",
        "telangana":   "⭐ Telangana"
    }
    emotion_icons = {
        "anxious":   "😰 Anxious",
        "sad":       "💙 Sad",
        "excited":   "🔥 Excited",
        "lazy":      "😴 Lazy",
        "lost":      "🤔 Lost",
        "motivated": "💪 Motivated"
    }
    d = st.session_state.get("dialect", "neutral")
    e = st.session_state.get("emotion", "neutral")
    badges = ""
    if d in dialect_names:
        badges += f"<span class='dialect-badge'>{dialect_names[d]}</span>"
    if e in emotion_icons:
        badges += f"<span class='emotion-badge'>{emotion_icons[e]}</span>"
    if badges:
        st.markdown(badges, unsafe_allow_html=True)

# ── Display chat history ──
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ── Voice Mode (Admin only) ──
if IS_ADMIN and voice_mode:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#150500,#200800);
                border:1px solid #FF6B35; border-radius:16px;
                padding:1rem; text-align:center;
                animation:glow 2s ease-in-out infinite;'>
        🎙️ <b>Voice Mode Active</b> — మాట్లాడు, SIA వింటోంది...
    </div>
    <style>@keyframes glow{{0%,100%{{box-shadow:0 0 10px #FF6B3533}}50%{{box-shadow:0 0 30px #FF6B3388}}}}</style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎤 Speak Now", use_container_width=True):
            with st.spinner("వింటున్నాను..."):
                spoken = listen(timeout=10)
            if spoken:
                st.info(f"🎤 {spoken}")
                st.session_state.messages.append({"role": "user", "content": spoken})
                with st.chat_message("user"):
                    st.write(spoken)
                with st.chat_message("assistant"):
                    with st.spinner("సియా ఆలోచిస్తోంది..."):
                        reply, dialect, emotion = chat(spoken, st.session_state.messages)
                        st.session_state.dialect = dialect
                        st.session_state.emotion = emotion
                        st.write(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                threading.Thread(target=speak, args=(reply, sarvam_voice), daemon=True).start()
            else:
                st.warning("వినలేదు. మళ్ళీ try చేయి.")
    with col2:
        if st.button("💾 Save", use_container_width=True):
            if len(st.session_state.messages) > 2:
                title = auto_title(st.session_state.messages)
                save_session(title, st.session_state.messages)
                st.success(f"Saved: {title}")

# ── Normal Chat Mode ──
else:
    # Input row — mic left of chat input
    col_mic, col_save = st.columns([1, 1])
    with col_mic:
        mic_btn = st.button("🎤 Speak", use_container_width=True)
    with col_save:
        save_btn = st.button("💾 Save", use_container_width=True)

    user_input = st.chat_input("SIA తో మాట్లాడు... (Telugu లేదా English)")

    # File upload — images and documents
    uploaded = st.file_uploader(
        "📎 Photo లేదా Document పంపు",
        type=["jpg", "jpeg", "png", "webp"],
        label_visibility="visible"
    )

    # Mic input
    if mic_btn:
        with st.spinner("🎤 వింటున్నాను... మాట్లాడు"):
            spoken = listen()
        if spoken:
            user_input = spoken
            st.info(f"🎤 విన్నాను: **{spoken}**")
        else:
            st.warning("వినలేదు — మళ్ళీ నొక్కు")

    # Save button
    if save_btn:
        if len(st.session_state.messages) > 2:
            title = auto_title(st.session_state.messages)
            save_session(title, st.session_state.messages)
            st.success(f"✅ Saved: '{title}'")
        else:
            st.info("మరికొంత మాట్లాడిన తర్వాత save చేయి")

    # Image processing
    extra = ""
    if uploaded:
        img_bytes = uploaded.read()
        st.image(Image.open(io.BytesIO(img_bytes)),
                 caption="Upload చేసావు", use_container_width=True)
        question = user_input or "ఈ image లో ఏముంది? వివరంగా Telugu లో చెప్పు."
        with st.spinner("🔍 Image చదువుతున్నాను..."):
            extra = analyze_image(img_bytes, question)
        if not user_input:
            user_input = "ఈ image గురించి చెప్పు"

    # Add devotional context if needed
    if user_input:
        intents = detect_intents(user_input)
        if "devotional" in intents:
            extra += get_devotional_context(user_input)
        if "horoscope" in intents:
            for rashi in RASHIS:
                if rashi in user_input:
                    extra += f"\nHOROSCOPE DATA:\n{get_horoscope(rashi)}"
                    break
        if "news" in intents:
            extra += f"\nTELUGU NEWS:\n{get_telugu_news()}"

    # Process and respond
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("సియా ఆలోచిస్తోంది..."):
                reply, dialect, emotion = chat(
                    user_input, st.session_state.messages, extra
                )
                st.session_state.dialect = dialect
                st.session_state.emotion = emotion
                st.write(reply)
                st.session_state.messages.append({
                    "role": "assistant", "content": reply
                })

        if auto_speak:
            threading.Thread(
                target=speak, args=(reply, sarvam_voice), daemon=True
            ).start()

# ── Auto-save every 10 messages ──
n = len(st.session_state.messages)
if n > 0 and n % 10 == 0:
    title = auto_title(st.session_state.messages)
    save_session(title, st.session_state.messages)
