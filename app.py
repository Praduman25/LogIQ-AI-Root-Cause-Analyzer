"""
LogIQ — Production AI Root Cause Analysis Dashboard
Fixes applied:
  - Single nav bar with working tabs, duplicate button row removed
  - File upload auto-analyzes immediately on upload
  - Non-log input (e.g. "president of india") returns clean error, no analysis
  - Chat restricted to log/error topics; off-topic = instant polite refusal
  - AI generates exactly ONE answer per chat question
  - Dark / Light / System theme toggle
  - Completely redesigned layout: hero, 2-col analyzer, integrated chat, about page
  - History entries fully visible with proper contrast
  - Live + model name removed from navbar
  - Tight spacing, no random clutter
  FIX: Quick-question chips now correctly trigger chatbot
  FIX: Clear button properly clears without re-firing old question
  FIX: Chat output in fixed-height scrollable box — no more huge gap before footer
"""

import streamlit as st
import datetime
import time
import logging
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("logiq")

from rca_engine import analyze_logs

# ── Module-level persistent store — survives URL-based tab navigation ──
if "_global_history" not in st.__dict__:
    st._global_history = []
if "_global_state" not in st.__dict__:
    st._global_state = {}

st.set_page_config(
    page_title="LogIQ · AI Root Cause Analysis",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════
#  SESSION STATE — init first so theme is available for CSS
# ══════════════════════════════════════════════════════════════════════
_defaults = {
    "active_tab":    "analyzer",
    "theme":         "light",
    "rca_result":    None,
    "rca_parsed":    None,
    "rca_elapsed":   0.0,
    "rca_model":     "",
    "chat_history":  [],
    "last_chat_q":   "",
    # FIX 1: pending_chat_q is written by chip buttons and read by chat logic
    # This bypasses st.text_input widget ownership issue
    "pending_chat_q": "",
    "history":       [],
    "log_text":      "",
    "last_file":     "",
    "auto_analyze":  False,
    "logs_dirty":    False,
    "analyzing":     False,
    "environment":   "Auto-detect",
    "tech_stack":    "Auto-detect",
    "log_type":      "Auto-detect",
    "service_name":  "",
    "detected_context": {},
    "demo_mode":        False,
    "walkthrough_step": 0,
    "feedback":         None,
    "feedback_count":   {"up": 0, "down": 0},
    "_run_sample":      None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Sync history from module-level store (survives URL tab navigation)
st.session_state.history = st._global_history

# Apply theme/demo from query params FIRST (before global state restore)
# so URL-based changes take priority and get persisted
_qp = st.query_params
if "theme" in _qp and _qp["theme"] in ["light","dark"]:
    st._global_state["theme"] = _qp["theme"]
if "demo" in _qp:
    st._global_state["demo_mode"] = (_qp["demo"] == "1")

# Restore critical state from global store after URL navigation resets session
_persist_keys = ["rca_result","rca_parsed","rca_elapsed","log_text","demo_mode",
                 "theme","chat_history","feedback","feedback_count","detected_context",
                 "environment","tech_stack","log_type","service_name","walkthrough_step"]
if st._global_state:
    for k in _persist_keys:
        if k in st._global_state:
            st.session_state[k] = st._global_state[k]

theme = st.session_state.theme

# ══════════════════════════════════════════════════════════════════════
#  THEME VARS
# ══════════════════════════════════════════════════════════════════════
if theme == "dark":
    BG       = "#0f1117"
    SURFACE  = "#1a1d27"
    SURFACE2 = "#22263a"
    BORDER   = "#2e3349"
    TEXT     = "#e8eaf6"
    TEXT2    = "#8b92b8"
    TEXT3    = "#525a7a"
    ACCENT   = "#6366f1"
    ACCENT2  = "#818cf8"
    INPUT_BG = "#161922"
    LOGBG    = "#0a0c14"
    HERO_BG  = "linear-gradient(135deg,#0d0b1e 0%,#1a1260 50%,#2d22a8 100%)"
    STRIP_BG = "#1a1d27"
    STRIP_BR = "#2e3349"
    RC_BG    = "#1a1d27"
    CODE_BG  = "#0a0c14"
    CHAT_BG  = "#161922"
    EMPTY_BG = "#161922"
    DL_BG    = "#1a1d27"
    DL_COLOR = "#818cf8"
    DL_BORDER= "#3730a3"
    HIST_TEXT= "#e8eaf6"
else:
    BG       = "#f8f9fc"
    SURFACE  = "#ffffff"
    SURFACE2 = "#f3f4f8"
    BORDER   = "#e5e7eb"
    TEXT     = "#111827"
    TEXT2    = "#6b7280"
    TEXT3    = "#9ca3af"
    ACCENT   = "#4f46e5"
    ACCENT2  = "#6366f1"
    INPUT_BG = "#f9fafb"
    LOGBG    = "#0f172a"
    HERO_BG  = "linear-gradient(130deg,#1e1b4b 0%,#312e81 50%,#4338ca 100%)"
    STRIP_BG = "#ffffff"
    STRIP_BR = "#e5e7eb"
    RC_BG    = "#ffffff"
    CODE_BG  = "#0f172a"
    CHAT_BG  = "#f9fafb"
    EMPTY_BG = "#f9fafb"
    DL_BG    = "#ffffff"
    DL_COLOR = "#1d4ed8"
    DL_BORDER= "#bfdbfe"
    HIST_TEXT= "#111827"

# ══════════════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════════════
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
html,body,[class*="css"]{{font-family:'Inter',sans-serif!important;}}
.stApp{{background:{BG}!important;}}
#MainMenu,footer,header,[data-testid="stToolbar"]{{visibility:hidden!important;height:0!important;}}
.block-container{{padding:0!important;max-width:100%!important;}}
/* Kill Streamlit's auto top gap on all pages */
.block-container > div:first-child{{margin-top:0!important;padding-top:0!important;}}
[data-testid="stVerticalBlock"]{{gap:0.4rem!important;}}
section[data-testid="stSidebar"]{{display:none!important;}}
::-webkit-scrollbar{{width:4px;height:4px;}}
::-webkit-scrollbar-thumb{{background:{BORDER};border-radius:4px;}}

@keyframes fadeUp{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}
.fade-up{{animation:fadeUp .35s ease both;}}
.fade-in{{animation:fadeIn .3s ease both;}}

.hero{{background:{HERO_BG};padding:2rem 2rem 3.5rem;position:relative;overflow:hidden;}}
.hero::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 50% 40% at 80% 10%,rgba(167,139,250,.15) 0%,transparent 60%);}}
.hero::after{{content:'';position:absolute;bottom:-1px;left:0;right:0;height:40px;background:{BG};clip-path:ellipse(55% 100% at 50% 100%);}}
.hero-inner{{position:relative;z-index:1;max-width:560px;}}
.hero-pill{{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);color:#c7d2fe;padding:3px 11px;border-radius:20px;font-size:.65rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;margin-bottom:.8rem;}}
.ldot{{width:6px;height:6px;border-radius:50%;background:#86efac;animation:ld 2s ease-in-out infinite;}}
@keyframes ld{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:.3;transform:scale(.5);}}}}
.hero-h1{{font-size:2rem;font-weight:800;color:#fff;line-height:1.1;letter-spacing:-.03em;margin-bottom:.6rem;}}
.hero-h1 .hl{{color:#a5b4fc;}}
.hero-sub{{font-size:.88rem;color:rgba(199,210,254,.85);line-height:1.7;margin-bottom:1.6rem;}}
.hstats{{display:flex;gap:1.8rem;flex-wrap:wrap;}}
.hs{{display:flex;flex-direction:column;gap:2px;}}
.hs-n{{font-size:1.2rem;font-weight:800;color:#fff;line-height:1;}}
.hs-l{{font-size:.6rem;font-weight:600;color:#818cf8;text-transform:uppercase;letter-spacing:.08em;}}

.hero-compact{{background:{HERO_BG};padding:1.2rem 1.5rem 1.4rem;position:relative;overflow:hidden;}}
.hero-compact::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 60% 50% at 70% 20%,rgba(167,139,250,.12) 0%,transparent 55%);}}
.hero-compact-inner{{position:relative;z-index:1;max-width:900px;margin:0 auto;text-align:center;}}
.hero-compact-h1{{font-size:1.5rem;font-weight:800;color:#fff;line-height:1.25;letter-spacing:-.02em;margin-bottom:.45rem;}}
.hero-compact-h1 .hl{{color:#a5b4fc;}}
.hero-compact-sub{{font-size:.8rem;color:rgba(199,210,254,.8);line-height:1.5;font-weight:500;}}

.fstrip{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:{STRIP_BR};border-bottom:1px solid {STRIP_BR};}}
.fcell{{background:{STRIP_BG};padding:.85rem 1.1rem;display:flex;align-items:flex-start;gap:9px;transition:background .15s;}}
.fcell:hover{{background:{'#f5f3ff' if theme=='light' else '#1a1d2e'};}}
.ficon{{width:30px;height:30px;border-radius:7px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:14px;}}
.fi-i{{background:#ede9fe;}}.fi-b{{background:#dbeafe;}}.fi-g{{background:#dcfce7;}}.fi-a{{background:#fef9c3;}}
.ftit{{font-size:.76rem;font-weight:700;color:{TEXT};margin-bottom:1px;}}
.fsub{{font-size:.68rem;color:{TEXT2};line-height:1.35;}}

.body{{padding:1.25rem 1.5rem 2rem;max-width:1320px;margin:0 auto;}}
.body-tight{{padding:.75rem 1.5rem 2rem;max-width:1320px;margin:0 auto;}}
.mlbl{{font-size:.6rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:{TEXT3};margin-bottom:.35rem;}}

.icard{{background:{SURFACE};border:1px solid {BORDER};border-radius:12px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,{'0.08' if theme=='dark' else '0.04'});}}
.ich{{padding:.7rem 1rem;border-bottom:1px solid {BORDER};display:flex;align-items:center;gap:7px;}}
.ich-dot{{width:7px;height:7px;border-radius:50%;background:{ACCENT};flex-shrink:0;}}
.ich-t{{font-size:.82rem;font-weight:700;color:{TEXT};flex:1;}}
.ich-badge{{font-size:.58rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:2px 7px;border-radius:5px;background:#f0f9ff;color:#0369a1;border:1px solid #bae6fd;}}
.icb{{padding:.75rem 1rem;}}

[data-testid="stFileUploader"]{{background:{INPUT_BG};border:1.5px dashed {BORDER};border-radius:9px;padding:0;transition:border-color .18s;}}
[data-testid="stFileUploader"]:hover{{border-color:{ACCENT};}}
[data-testid="stFileUploader"] section{{padding:0!important;}}
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"]{{padding:.45rem .75rem!important;min-height:unset!important;}}
[data-testid="stFileUploaderDropzoneInstructions"]{{padding:0!important;gap:.5rem!important;}}
[data-testid="stFileUploaderDropzoneInstructions"] > div{{flex-direction:row!important;align-items:center!important;gap:.5rem!important;}}
[data-testid="stFileUploaderDropzoneInstructions"] span{{font-size:.78rem!important;}}
[data-testid="stFileUploader"] small{{font-size:.7rem!important;}}
[data-testid="stSelectbox"] label{{font-size:.78rem!important;font-weight:600!important;color:{TEXT2}!important;margin-bottom:2px!important;}}
[data-testid="stSelectbox"] > div > div{{background:{INPUT_BG}!important;border:1.5px solid {BORDER}!important;border-radius:9px!important;font-size:.82rem!important;min-height:36px!important;}}
[data-testid="stSelectbox"] > div > div:focus-within{{border-color:{ACCENT}!important;}}

.stTextArea textarea{{background:{INPUT_BG}!important;border:1.5px solid {BORDER}!important;border-radius:9px!important;color:{TEXT}!important;font-family:'JetBrains Mono',monospace!important;font-size:.77rem!important;line-height:1.78!important;padding:11px 13px!important;transition:border-color .18s,box-shadow .18s!important;resize:none!important;overflow-y:auto!important;}}
.stTextArea textarea:focus{{border-color:{ACCENT}!important;box-shadow:0 0 0 3px rgba(79,70,229,.09)!important;background:{SURFACE}!important;outline:none!important;}}
.stTextArea textarea::placeholder{{color:{TEXT3}!important;font-family:'Inter',sans-serif!important;}}
.stTextArea label{{display:none!important;}}

.stButton>button{{background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%)!important;color:#fff!important;border:none!important;border-radius:10px!important;padding:.62rem 1.3rem!important;font-family:'Inter',sans-serif!important;font-weight:700!important;font-size:.84rem!important;width:100%!important;box-shadow:0 2px 10px rgba(79,70,229,.22)!important;transition:all .2s!important;cursor:pointer!important;}}
.stButton>button:hover{{transform:translateY(-1px)!important;box-shadow:0 4px 16px rgba(79,70,229,.32)!important;}}
.stButton>button:active{{transform:translateY(0)!important;}}

.analyze-btn-wrap{{position:relative;}}
.analyze-btn-wrap .stButton>button{{background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%)!important;color:#fff!important;border:none!important;border-radius:12px!important;padding:.95rem 2rem!important;font-family:'Inter',sans-serif!important;font-weight:800!important;font-size:1rem!important;width:100%!important;box-shadow:0 6px 24px rgba(79,70,229,.4), 0 0 0 0 rgba(79,70,229,.5)!important;transition:all .25s cubic-bezier(0.4,0,0.2,1)!important;cursor:pointer!important;position:relative!important;letter-spacing:.01em!important;animation:btnPulse 2s ease-in-out infinite!important;}}
@keyframes btnPulse{{0%,100%{{box-shadow:0 6px 24px rgba(79,70,229,.4), 0 0 0 0 rgba(79,70,229,.5);}}50%{{box-shadow:0 6px 24px rgba(79,70,229,.5), 0 0 20px 4px rgba(124,58,237,.3);}}}}
.analyze-btn-wrap .stButton>button:hover{{transform:translateY(-2px) scale(1.02)!important;box-shadow:0 12px 32px rgba(79,70,229,.5), 0 0 40px rgba(124,58,237,.3)!important;animation:none!important;}}
.analyze-btn-wrap .stButton>button:active{{transform:translateY(0) scale(0.98)!important;}}
.btn-subtext{{text-align:center;font-size:.72rem;color:{TEXT3};margin-top:.5rem;font-weight:600;display:flex;align-items:center;justify-content:center;gap:4px;}}
.btn-subtext-highlight{{color:{ACCENT};font-weight:700;}}

.nb-btn-wrap .stButton>button{{background:transparent!important;color:{TEXT2}!important;border:none!important;border-bottom:3px solid transparent!important;border-radius:0!important;box-shadow:none!important;padding:0 1.1rem!important;height:52px!important;font-weight:500!important;font-size:.82rem!important;width:100%!important;transition:color .15s,border-color .15s!important;letter-spacing:0!important;margin:0!important;line-height:52px!important;}}
.nb-btn-wrap .stButton>button:hover{{background:transparent!important;color:{TEXT}!important;border-bottom:3px solid {TEXT3}!important;transform:none!important;box-shadow:none!important;}}
.nb-btn-wrap .stButton>button[kind="primary"]{{color:{ACCENT}!important;border-bottom:3px solid {ACCENT}!important;background:transparent!important;box-shadow:none!important;font-weight:700!important;}}
.ghost .stButton>button{{background:{SURFACE}!important;color:{TEXT2}!important;border:1px solid {BORDER}!important;box-shadow:none!important;font-weight:500!important;}}
.ghost .stButton>button:hover{{background:{SURFACE2}!important;transform:none!important;box-shadow:none!important;color:{TEXT}!important;}}

/* Chip buttons — flat, small, pill style */
.chip-btn .stButton>button{{
    background:{SURFACE2}!important;color:{TEXT2}!important;
    border:1.5px solid {BORDER}!important;
    border-radius:20px!important;
    box-shadow:none!important;
    padding:.35rem .85rem!important;
    font-size:.73rem!important;font-weight:600!important;
    width:auto!important;
    transition:all .15s!important;
}}
.chip-btn .stButton>button:hover{{
    background:{ACCENT}!important;color:#fff!important;
    border-color:{ACCENT}!important;
    transform:translateY(-1px)!important;
    box-shadow:0 2px 8px rgba(79,70,229,.25)!important;
}}

.pbadge{{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:600;}}
.pb-e{{background:#fef2f2;color:#991b1b;border:1px solid #fecaca;}}
.pb-w{{background:#fefce8;color:#854d0e;border:1px solid #fde68a;}}
.pb-ok{{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;}}

.logview{{background:{LOGBG};border-radius:9px;padding:.75rem 1rem;font-family:'JetBrains Mono',monospace;font-size:.72rem;line-height:1.85;overflow-x:auto;overflow-y:auto;max-height:165px;border:1px solid #1e2d45;}}
.lv-fa{{color:#fb7185;font-weight:600;}}.lv-er{{color:#f87171;}}.lv-wn{{color:#fbbf24;}}.lv-in{{color:#60a5fa;}}.lv-db{{color:#6b7280;}}.lv-ok{{color:#34d399;}}.lv-df{{color:#94a3b8;}}

.tips{{background:{SURFACE2};border-left:3px solid {ACCENT};border-radius:0 8px 8px 0;padding:.65rem .9rem;}}
.tips-h{{font-size:.6rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:{ACCENT};margin-bottom:.3rem;}}
.tips ul{{margin:0;padding-left:.9rem;font-size:.72rem;color:{TEXT2};line-height:1.88;}}

.empty{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2.5rem 1rem;text-align:center;border:1.5px dashed {BORDER};border-radius:12px;background:{EMPTY_BG};min-height:220px;}}
.empty-ico{{font-size:1.9rem;margin-bottom:.55rem;}}
.empty-t{{font-size:.88rem;font-weight:700;color:{TEXT};margin-bottom:.25rem;}}
.empty-s{{font-size:.76rem;color:{TEXT2};line-height:1.6;}}
.empty-step{{display:flex;align-items:center;gap:8px;font-size:.76rem;color:{TEXT2};margin-top:.4rem;}}
.step-num{{width:20px;height:20px;border-radius:50%;background:{ACCENT};color:#fff;display:flex;align-items:center;justify-content:center;font-size:.62rem;font-weight:800;flex-shrink:0;}}

.sample-preview{{background:{SURFACE};border:1.5px solid {BORDER};border-radius:12px;padding:1.2rem;}}
.sample-header{{text-align:center;margin-bottom:1.2rem;}}
.sample-badge{{display:inline-block;background:{SURFACE2};color:{TEXT2};padding:4px 12px;border-radius:20px;font-size:.68rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;border:1px solid {BORDER};margin-bottom:.5rem;}}
.sample-title{{font-size:1rem;font-weight:700;color:{TEXT};margin:0;}}
.sample-card{{display:flex;gap:.75rem;align-items:flex-start;background:{SURFACE2};border-radius:10px;padding:.85rem 1rem;margin-bottom:.65rem;border-left:3px solid;transition:transform .15s,box-shadow .15s;}}
.sample-card:hover{{transform:translateX(3px);box-shadow:0 2px 8px rgba(0,0,0,{'0.08' if theme=='dark' else '0.04'});}}
.sample-root{{border-left-color:#ef4444;}}.sample-fix{{border-left-color:#10b981;}}.sample-explain{{border-left-color:#3b82f6;}}.sample-prevent{{border-left-color:#8b5cf6;}}
.sample-icon{{font-size:1.3rem;flex-shrink:0;line-height:1;width:32px;height:32px;display:flex;align-items:center;justify-content:center;}}
.sample-content{{flex:1;}}
.sample-label{{font-size:.68rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:{TEXT3};margin-bottom:.3rem;}}
.sample-text{{font-size:.8rem;color:{TEXT};line-height:1.6;margin:0;}}
.sample-footer{{text-align:center;margin-top:1rem;padding-top:1rem;border-top:1px solid {BORDER};}}
.sample-footer p{{font-size:.78rem;color:{TEXT2};margin:0;font-weight:500;}}

.sevrow{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:.75rem;align-items:center;}}
.sp{{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:.69rem;font-weight:700;}}
.sp-hi{{background:#fef2f2;color:#991b1b;border:1px solid #fecaca;}}
.sp-md{{background:#fefce8;color:#854d0e;border:1px solid #fde68a;}}
.sp-lo{{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;}}
.sp-cf{{background:#f5f3ff;color:#4c1d95;border:1px solid #ddd6fe;}}
.sp-tm{{background:#f0f9ff;color:#0369a1;border:1px solid #bae6fd;font-size:.63rem;}}

.rc{{background:{RC_BG};border:1px solid {BORDER};border-left:3px solid;border-radius:0 11px 11px 0;padding:.75rem 1rem;transition:box-shadow .16s,transform .16s;}}
.rc:hover{{box-shadow:0 2px 8px rgba(0,0,0,{'0.10' if theme=='dark' else '0.04'});transform:translateY(-1px);}}
.rclbl{{font-size:.58rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.35rem;display:flex;align-items:center;gap:4px;}}
.rclbl::before{{content:'';display:inline-block;width:5px;height:5px;border-radius:50%;}}
.rc-root{{border-left-color:#ef4444;}}.rc-root .rclbl{{color:#dc2626;}}.rc-root .rclbl::before{{background:#dc2626;}}
.rc-expl{{border-left-color:#3b82f6;}}.rc-expl .rclbl{{color:#2563eb;}}.rc-expl .rclbl::before{{background:#2563eb;}}
.rc-sol{{border-left-color:#10b981;}}.rc-sol .rclbl{{color:#059669;}}.rc-sol .rclbl::before{{background:#059669;}}
.rc-prev{{border-left-color:#8b5cf6;}}.rc-prev .rclbl{{color:#7c3aed;}}.rc-prev .rclbl::before{{background:#7c3aed;}}
.rcbody{{font-size:.82rem;color:{TEXT};line-height:1.7;}}
.rcbody ul{{margin:.25rem 0 0;padding-left:.9rem;}}
.rcbody li{{margin-bottom:.2rem;}}

.result-metadata{{display:flex;gap:.65rem;flex-wrap:wrap;align-items:center;background:{SURFACE2};border-radius:10px;padding:.6rem .9rem;margin-bottom:.75rem;border:1px solid {BORDER};}}
.meta-item{{display:flex;flex-direction:column;gap:2px;}}
.meta-label{{font-size:.6rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:{TEXT3};}}
.meta-value{{font-size:.8rem;font-weight:700;color:{TEXT};}}
.meta-sev-high{{color:#dc2626;}}.meta-sev-medium{{color:#d97706;}}.meta-sev-low{{color:#059669;}}

.result-card{{background:{SURFACE};border:1px solid {BORDER};border-radius:11px;margin-bottom:.6rem;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,{'0.08' if theme=='dark' else '0.03'});transition:box-shadow .2s,transform .2s;}}
.result-card:hover{{box-shadow:0 3px 12px rgba(0,0,0,{'0.12' if theme=='dark' else '0.05'});transform:translateY(-1px);}}
.rc-header{{display:flex;align-items:center;gap:.6rem;padding:.7rem 1rem;border-bottom:1px solid {BORDER};background:{SURFACE2};}}
.rc-icon{{font-size:1.2rem;line-height:1;}}
.rc-title{{font-size:.85rem;font-weight:800;color:{TEXT};letter-spacing:-.01em;flex:1;}}
.rc-priority{{font-size:.6rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;padding:2px 8px;border-radius:10px;background:#fef2f2;color:#991b1b;border:1px solid #fecaca;}}
.rc-content{{padding:.85rem 1rem;}}
.rc-main-text{{font-size:.92rem;font-weight:700;color:{TEXT};line-height:1.55;margin:0;}}
.rc-text{{font-size:.82rem;color:{TEXT};line-height:1.7;margin:0;}}
.rc-empty{{font-size:.78rem;color:{TEXT3};font-style:italic;margin:0;}}
.fix-steps{{margin:0;padding-left:1.2rem;font-size:.82rem;color:{TEXT};line-height:1.8;}}
.fix-steps li{{margin-bottom:.4rem;padding-left:.25rem;}}
.fix-steps li::marker{{font-weight:800;color:{ACCENT};}}
.prevent-list{{margin:0;padding-left:1rem;font-size:.82rem;color:{TEXT};line-height:1.8;}}
.prevent-list li{{margin-bottom:.35rem;}}
.prevent-list li::marker{{color:#8b5cf6;}}

.stale{{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:.45rem .9rem;font-size:.75rem;font-weight:600;color:#92400e;margin-bottom:.6rem;}}

.ftl-wrap{{background:{SURFACE};border:1px solid {BORDER};border-radius:14px;overflow:hidden;margin-bottom:.85rem;}}
.ftl-head{{background:linear-gradient(135deg,#1e1b4b 0%,#312e81 60%,#4338ca 100%);padding:.75rem 1.1rem;display:flex;align-items:center;gap:.6rem;}}
.ftl-head-icon{{font-size:1rem;}}
.ftl-head-title{{font-size:.88rem;font-weight:800;color:#fff;flex:1;letter-spacing:-.01em;}}
.ftl-head-badge{{font-size:.65rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 10px;border-radius:12px;background:rgba(255,255,255,.15);color:#c7d2fe;border:1px solid rgba(255,255,255,.2);}}
.ftl-body{{padding:1.1rem 1.2rem;}}
.ftl-flow{{display:flex;align-items:center;gap:0;overflow-x:auto;padding-bottom:.5rem;margin-bottom:1rem;}}
.ftl-node{{display:flex;flex-direction:column;align-items:center;gap:.35rem;flex-shrink:0;min-width:80px;max-width:100px;}}
.ftl-node-circle{{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.1rem;border:2.5px solid;transition:transform .2s;position:relative;}}
.ftl-node-circle:hover{{transform:scale(1.1);}}
.ftl-node.ok .ftl-node-circle{{background:#f0fdf4;border-color:#22c55e;}}
.ftl-node.warn .ftl-node-circle{{background:#fefce8;border-color:#eab308;}}
.ftl-node.fail .ftl-node-circle{{background:#fef2f2;border-color:#ef4444;box-shadow:0 0 0 4px rgba(239,68,68,.15);animation:failPulse 2s ease-in-out infinite;}}
.ftl-node.info .ftl-node-circle{{background:#f0f9ff;border-color:#3b82f6;}}
@keyframes failPulse{{0%,100%{{box-shadow:0 0 0 4px rgba(239,68,68,.15);}}50%{{box-shadow:0 0 0 8px rgba(239,68,68,.05);}}}}
.ftl-node-label{{font-size:.65rem;font-weight:700;color:{TEXT};text-align:center;line-height:1.3;}}
.ftl-node-sub{{font-size:.58rem;color:{TEXT3};text-align:center;line-height:1.2;}}
.ftl-node.fail .ftl-node-label{{color:#dc2626;}}.ftl-node.warn .ftl-node-label{{color:#d97706;}}.ftl-node.ok .ftl-node-label{{color:#16a34a;}}
.ftl-arrow{{flex-shrink:0;display:flex;flex-direction:column;align-items:center;padding:0 2px;margin-top:-18px;}}
.ftl-arrow-line{{width:28px;height:2px;background:linear-gradient(90deg,{BORDER},{BORDER});position:relative;}}
.ftl-arrow-line.fail-path{{background:linear-gradient(90deg,#fca5a5,#ef4444);}}.ftl-arrow-line.ok-path{{background:linear-gradient(90deg,#86efac,#22c55e);}}
.ftl-arrow-head{{font-size:.7rem;color:{TEXT3};margin-top:-2px;}}.ftl-arrow-head.fail-path{{color:#ef4444;}}.ftl-arrow-head.ok-path{{color:#22c55e;}}
.ftl-steps{{display:flex;flex-direction:column;gap:.45rem;margin-bottom:1rem;}}
.ftl-step{{display:flex;align-items:flex-start;gap:.7rem;padding:.55rem .75rem;border-radius:9px;border:1px solid {BORDER};background:{SURFACE2};transition:border-color .15s;}}
.ftl-step:hover{{border-color:{ACCENT2};}}
.ftl-step-num{{width:22px;height:22px;border-radius:6px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:.65rem;font-weight:800;color:#fff;margin-top:1px;}}
.ftl-step.ok .ftl-step-num{{background:#22c55e;}}.ftl-step.warn .ftl-step-num{{background:#eab308;}}.ftl-step.fail .ftl-step-num{{background:#ef4444;}}.ftl-step.info .ftl-step-num{{background:#3b82f6;}}
.ftl-step-body{{flex:1;}}
.ftl-step-title{{font-size:.78rem;font-weight:700;color:{TEXT};margin-bottom:1px;}}
.ftl-step.fail .ftl-step-title{{color:#dc2626;}}.ftl-step.warn .ftl-step-title{{color:#d97706;}}
.ftl-step-desc{{font-size:.71rem;color:{TEXT2};line-height:1.45;}}
.ftl-step-badge{{font-size:.6rem;font-weight:700;padding:2px 7px;border-radius:8px;flex-shrink:0;margin-top:2px;}}
.ftl-step-badge.ok{{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;}}.ftl-step-badge.fail{{background:#fef2f2;color:#991b1b;border:1px solid #fecaca;}}.ftl-step-badge.warn{{background:#fefce8;color:#854d0e;border:1px solid #fde68a;}}
.ftl-impact{{display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.75rem;}}
.ftl-impact-card{{background:{SURFACE2};border:1px solid {BORDER};border-radius:9px;padding:.65rem .85rem;}}
.ftl-impact-label{{font-size:.6rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:{TEXT3};margin-bottom:.3rem;}}
.ftl-impact-value{{font-size:.78rem;font-weight:600;color:{TEXT};line-height:1.5;}}
.ftl-conf{{display:flex;align-items:center;gap:.75rem;padding:.6rem .75rem;background:{SURFACE2};border-radius:9px;border:1px solid {BORDER};}}
.ftl-conf-label{{font-size:.72rem;font-weight:700;color:{TEXT2};white-space:nowrap;}}
.ftl-conf-bar-wrap{{flex:1;background:{BORDER};border-radius:4px;height:6px;overflow:hidden;}}
.ftl-conf-bar{{height:6px;border-radius:4px;transition:width .6s ease;}}
.ftl-conf-pct{{font-size:.78rem;font-weight:800;color:{ACCENT};white-space:nowrap;}}

.context-banner{{display:flex;align-items:center;gap:.75rem;background:linear-gradient(135deg,{SURFACE2} 0%,{SURFACE} 100%);border:1.5px solid {BORDER};border-radius:10px;padding:.75rem 1rem;margin-bottom:.85rem;box-shadow:0 2px 8px rgba(79,70,229,.08);}}
.ctx-icon{{font-size:1.3rem;flex-shrink:0;}}
.ctx-content{{flex:1;display:flex;flex-direction:column;gap:3px;}}
.ctx-label{{font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:{TEXT3};}}
.ctx-text{{font-size:.8rem;font-weight:600;color:{TEXT};}}
.ctx-service{{font-size:.72rem;color:{ACCENT};font-weight:600;}}
.ctx-badge{{font-size:.65rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:4px 10px;border-radius:12px;background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;flex-shrink:0;}}

.raw-wrap{{background:{CODE_BG};border-radius:9px;border:1px solid #1e2d45;padding:.75rem 1rem;margin-top:.65rem;}}
.raw-lbl{{font-size:.58rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#4b5563;margin-bottom:.4rem;}}
.raw-body{{font-family:'JetBrains Mono',monospace;font-size:.7rem;color:#9ca3af;line-height:1.78;overflow-x:auto;white-space:pre-wrap;max-height:180px;overflow-y:auto;}}

.spin-wrap{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2rem 1rem;gap:.7rem;}}
.sring{{width:38px;height:38px;border:3px solid {BORDER};border-top-color:#4f46e5;border-right-color:#7c3aed;border-radius:50%;animation:sp .8s linear infinite;}}
@keyframes sp{{to{{transform:rotate(360deg);}}}}
.stxt{{font-size:.8rem;font-weight:600;color:{ACCENT};animation:bth 1.4s ease-in-out infinite;}}
@keyframes bth{{0%,100%{{opacity:.4;}}50%{{opacity:1;}}}}
.stSpinner{{display:none!important;}}

[data-testid="stDownloadButton"]>button{{background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%)!important;color:#fff!important;border:none!important;border-radius:10px!important;font-weight:700!important;font-size:.84rem!important;box-shadow:0 2px 10px rgba(79,70,229,.22)!important;padding:.62rem 1.3rem!important;height:auto!important;transition:all .2s!important;}}
[data-testid="stDownloadButton"]>button:hover{{transform:translateY(-1px)!important;box-shadow:0 4px 16px rgba(79,70,229,.32)!important;}}

/* ── CHAT ── */
.chat-shell{{background:{SURFACE};border:1px solid {BORDER};border-radius:12px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,{'0.08' if theme=='dark' else '0.03'});}}
.chat-head{{background:linear-gradient(135deg,#1e1b4b 0%,#4338ca 100%);padding:.6rem 1rem;display:flex;align-items:center;gap:7px;}}
.ch-title{{font-size:.82rem;font-weight:700;color:#fff;flex:1;}}
.ch-sub{{font-size:.62rem;color:rgba(199,210,254,.8);}}

/* FIX 3: fixed-height scrollable chat messages — no more giant gap */
.chat-msgs{{
    height:420px;
    overflow-y:auto;
    padding:.75rem;
    background:{CHAT_BG};
    display:flex;
    flex-direction:column;
    align-items:stretch;
}}
.chat-nil{{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;width:100%;font-size:.75rem;color:{TEXT3};text-align:center;line-height:1.6;}}
.cmsg{{display:flex;gap:6px;margin-bottom:.6rem;animation:fadeUp .18s ease;}}
.cmsg-user{{justify-content:flex-end;}}.cmsg-ai{{justify-content:flex-start;}}
.cav{{width:24px;height:24px;border-radius:6px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;margin-top:1px;}}
.cav-u{{background:#dbeafe;color:#1d4ed8;}}.cav-a{{background:#ede9fe;color:#5b21b6;}}
.cbbl{{border-radius:10px;padding:.4rem .75rem;font-size:.79rem;line-height:1.6;max-width:85%;}}
.cbbl-u{{background:#dbeafe;color:#1e3a5f;border-bottom-right-radius:3px;}}
.cbbl-a{{background:{SURFACE};color:{TEXT};border:1px solid {BORDER};border-bottom-left-radius:3px;}}
.cbbl-code{{font-family:'JetBrains Mono',monospace;font-size:.73rem;overflow-x:auto;max-width:100%;}}
.chat-ft{{padding:.6rem .9rem;border-top:1px solid {BORDER};background:{SURFACE};}}

/* ── Clear button aligned with input ── */
.clear-btn-wrap .stButton>button,
.clear-btn-wrap button{{
    height:38px!important;
    padding:0 .85rem!important;
    font-size:.78rem!important;
    font-weight:600!important;
    margin-top:0!important;
    background:{SURFACE}!important;
    color:{TEXT2}!important;
    border:1.5px solid {BORDER}!important;
    border-radius:9px!important;
    box-shadow:none!important;
    animation:none!important;
    background-image:none!important;
}}
.clear-btn-wrap .stButton>button:hover,
.clear-btn-wrap button:hover{{
    background:#fef2f2!important;
    color:#dc2626!important;
    border-color:#fecaca!important;
    transform:none!important;
    box-shadow:none!important;
}}

/* ── Chat footer row: input + clear side by side ── */
.chat-ft [data-testid="stHorizontalBlock"]{{
    align-items:center!important;
    gap:.5rem!important;
    margin-bottom:0!important;
}}
.chat-ft [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{{
    display:flex!important;
    align-items:center!important;
    padding:0!important;
}}
.chat-ft [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > div{{
    width:100%!important;
}}
.chat-ft .stTextInput{{margin-bottom:0!important;padding-bottom:0!important;}}
.chat-ft .stButton{{margin-bottom:0!important;padding-bottom:0!important;}}
.chat-ft .element-container{{margin-bottom:0!important;}}

.stTextInput input{{background:{INPUT_BG}!important;border:1.5px solid {BORDER}!important;border-radius:9px!important;color:{TEXT}!important;font-family:'Inter',sans-serif!important;font-size:.82rem!important;padding:8px 12px!important;transition:border-color .18s,box-shadow .18s!important;}}
.stTextInput input:focus{{border-color:{ACCENT}!important;box-shadow:0 0 0 3px rgba(79,70,229,.09)!important;background:{SURFACE}!important;outline:none!important;}}
.stTextInput input::placeholder{{color:{TEXT3}!important;}}
.stTextInput label{{display:none!important;}}

/* ── Vertically align input + clear button columns ── */
.chat-ft [data-testid="stHorizontalBlock"]{{align-items:center!important;gap:.5rem!important;}}
.chat-ft [data-testid="stHorizontalBlock"] [data-testid="stColumn"]{{display:flex!important;align-items:center!important;}}
.chat-ft [data-testid="stHorizontalBlock"] [data-testid="stColumn"] > div{{width:100%!important;}}
.chat-ft .stTextInput{{margin-bottom:0!important;}}
.chat-ft .stButton{{margin-bottom:0!important;}}

.howto{{background:{SURFACE};border:1px solid {BORDER};border-radius:13px;padding:1.1rem;}}
.howto-h{{font-size:.8rem;font-weight:700;color:{TEXT};margin-bottom:.75rem;padding-bottom:.5rem;border-bottom:1px solid {BORDER};}}
.step{{display:flex;gap:8px;align-items:flex-start;margin-bottom:.7rem;}}
.stepn{{width:22px;height:22px;border-radius:6px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;}}
.stept{{font-size:.77rem;font-weight:700;color:{TEXT};margin-bottom:1px;}}
.steps{{font-size:.71rem;color:{TEXT2};line-height:1.4;}}
.trybox{{background:{SURFACE2};border-radius:8px;border:1px solid {BORDER};padding:.65rem .85rem;margin-top:.3rem;}}
.trylbl{{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:{ACCENT};margin-bottom:.3rem;}}
.tryitems{{font-size:.74rem;color:{TEXT2};line-height:1.85;}}

div[data-testid="stExpander"]{{background:{SURFACE}!important;border:1px solid {BORDER}!important;border-radius:11px!important;margin-bottom:.45rem!important;}}
div[data-testid="stExpander"]:hover{{border-color:{ACCENT2}!important;}}
div[data-testid="stExpander"] summary{{color:{TEXT}!important;font-size:.84rem!important;font-weight:600!important;}}
div[data-testid="stExpander"] p, div[data-testid="stExpander"] li{{color:{TEXT}!important;}}

.ph{{padding:1.3rem 0 .9rem;}}.ph-h{{font-size:1.25rem;font-weight:800;color:{TEXT};margin-bottom:.2rem;}}.ph-s{{font-size:.81rem;color:{TEXT2};}}
.acard{{background:{SURFACE};border:1px solid {BORDER};border-radius:11px;padding:1.1rem;margin-bottom:.75rem;transition:box-shadow .16s;}}
.acard:hover{{box-shadow:0 3px 12px rgba(0,0,0,{'0.15' if theme=='dark' else '0.06'});}}
.acard-h{{font-size:.88rem;font-weight:700;color:{TEXT};margin-bottom:.5rem;display:flex;align-items:center;gap:6px;}}
.acard-p{{font-size:.8rem;color:{TEXT};line-height:1.74;}}
.acode{{background:{CODE_BG};color:#94a3b8;font-family:'JetBrains Mono',monospace;font-size:.71rem;border-radius:7px;padding:.7rem .9rem;margin:.55rem 0;overflow-x:auto;white-space:pre;border:1px solid #1e2d45;line-height:1.78;}}
.atag{{display:inline-block;background:#f5f3ff;color:#4c1d95;padding:2px 7px;border-radius:5px;font-size:.65rem;font-weight:700;margin-right:3px;margin-bottom:3px;}}

.banner{{display:flex;align-items:center;gap:7px;padding:.5rem .9rem;border-radius:8px;font-size:.77rem;font-weight:600;margin-bottom:.55rem;}}
.b-ok{{background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;}}
.b-warn{{background:#fffbeb;border:1px solid #fde68a;color:#92400e;}}
.b-err{{background:#fef2f2;border:1px solid #fecaca;color:#991b1b;}}

.trust-bar{{display:flex;align-items:center;justify-content:center;gap:1.5rem;flex-wrap:wrap;padding:.55rem 1.5rem;background:rgba(0,0,0,.18);border-bottom:1px solid rgba(255,255,255,.08);}}
.trust-item{{display:flex;align-items:center;gap:.4rem;font-size:.7rem;font-weight:600;color:rgba(199,210,254,.85);white-space:nowrap;}}
.trust-dot{{width:5px;height:5px;border-radius:50%;background:#86efac;flex-shrink:0;}}
.trust-badge{{display:inline-flex;align-items:center;gap:.35rem;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.18);color:#c7d2fe;padding:2px 9px;border-radius:20px;font-size:.65rem;font-weight:700;letter-spacing:.05em;}}

.step-progress{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:1.8rem 1rem;gap:.9rem;}}
.sp-title{{font-size:.88rem;font-weight:700;color:{ACCENT};margin-bottom:.2rem;}}
.sp-steps{{display:flex;flex-direction:column;gap:.45rem;width:100%;max-width:280px;}}
.sp-step{{display:flex;align-items:center;gap:.65rem;padding:.45rem .75rem;border-radius:8px;background:{SURFACE2};border:1px solid {BORDER};font-size:.78rem;font-weight:600;color:{TEXT2};transition:all .3s ease;}}
.sp-step.active{{background:{'#ede9fe' if theme=='light' else '#1e1a42'};border-color:{ACCENT};color:{ACCENT};}}
.sp-step.done{{background:{'#f0fdf4' if theme=='light' else '#052e16'};border-color:#22c55e;color:#16a34a;}}
.sp-step-icon{{font-size:.9rem;flex-shrink:0;width:20px;text-align:center;}}
.sp-ring{{width:32px;height:32px;border:2.5px solid {BORDER};border-top-color:#4f46e5;border-right-color:#7c3aed;border-radius:50%;animation:sp .8s linear infinite;flex-shrink:0;}}

.sample-logs-state{{background:{SURFACE};border:1.5px dashed {BORDER};border-radius:12px;padding:1.2rem;}}
.sl-header{{display:flex;align-items:center;gap:.5rem;margin-bottom:.85rem;}}
.sl-title{{font-size:.84rem;font-weight:700;color:{TEXT};flex:1;}}
.sl-badge{{font-size:.62rem;font-weight:700;padding:2px 8px;border-radius:8px;background:#f0f9ff;color:#0369a1;border:1px solid #bae6fd;}}
.sl-card{{background:{SURFACE2};border:1px solid {BORDER};border-radius:9px;padding:.7rem .9rem;margin-bottom:.55rem;cursor:pointer;transition:all .18s;}}
.sl-card:hover{{border-color:{ACCENT};background:{'#f5f3ff' if theme=='light' else '#1e1a42'};transform:translateX(3px);}}
.sl-card-title{{font-size:.76rem;font-weight:700;color:{TEXT};margin-bottom:.2rem;}}
.sl-card-preview{{font-family:'JetBrains Mono',monospace;font-size:.67rem;color:{TEXT3};line-height:1.5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.sl-hint{{font-size:.7rem;color:{TEXT3};text-align:center;margin-top:.65rem;display:flex;align-items:center;justify-content:center;gap:.3rem;}}

.toast{{display:flex;align-items:center;gap:.65rem;padding:.6rem 1rem;border-radius:10px;font-size:.8rem;font-weight:600;margin-bottom:.65rem;animation:fadeUp .3s ease;}}
.toast-ok{{background:#f0fdf4;border:1.5px solid #22c55e;color:#15803d;}}
.toast-err{{background:#fef2f2;border:1.5px solid #ef4444;color:#dc2626;}}
.toast-icon{{font-size:1rem;flex-shrink:0;}}

.ai-intel{{background:{SURFACE};border:1px solid {BORDER};border-radius:14px;overflow:hidden;margin-bottom:.85rem;}}
.ai-intel-head{{display:flex;align-items:center;gap:.6rem;padding:.75rem 1.1rem;background:{'#f5f3ff' if theme=='light' else '#1e1a42'};border-bottom:1px solid {BORDER};}}
.ai-intel-head-icon{{font-size:1rem;}}
.ai-intel-head-title{{font-size:.86rem;font-weight:800;color:{TEXT};flex:1;}}
.ai-intel-head-tag{{font-size:.62rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 9px;border-radius:10px;background:{ACCENT};color:#fff;}}
.ai-intel-body{{padding:1rem 1.1rem;display:flex;flex-direction:column;gap:.85rem;}}
.reasoning-chain{{display:flex;flex-direction:column;gap:.35rem;}}
.reasoning-step{{display:flex;align-items:flex-start;gap:.65rem;padding:.5rem .75rem;border-radius:8px;background:{SURFACE2};border-left:3px solid {ACCENT};animation:fadeUp .25s ease both;}}
.rs-num{{width:20px;height:20px;border-radius:50%;background:{ACCENT};color:#fff;font-size:.62rem;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;}}
.rs-text{{font-size:.78rem;color:{TEXT};line-height:1.5;}}
.rs-keyword{{display:inline-block;background:{'#ede9fe' if theme=='light' else '#2e1a5e'};color:{ACCENT};padding:1px 6px;border-radius:5px;font-family:'JetBrains Mono',monospace;font-size:.72rem;font-weight:700;}}
.conf-explain{{background:{SURFACE2};border-radius:10px;padding:.75rem .9rem;border:1px solid {BORDER};}}
.conf-explain-row{{display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem;}}
.conf-explain-pct{{font-size:1.4rem;font-weight:800;line-height:1;}}
.conf-explain-label{{font-size:.72rem;font-weight:700;color:{TEXT2};}}
.conf-explain-bar-wrap{{flex:1;background:{BORDER};border-radius:4px;height:7px;overflow:hidden;}}
.conf-explain-bar{{height:7px;border-radius:4px;transition:width .7s ease;}}
.conf-explain-reason{{font-size:.76rem;color:{TEXT};line-height:1.55;}}
.conf-explain-reason strong{{color:{ACCENT};}}
.alt-causes{{display:flex;flex-direction:column;gap:.45rem;}}
.alt-cause{{display:flex;align-items:center;gap:.7rem;padding:.55rem .8rem;border-radius:9px;background:{SURFACE2};border:1px solid {BORDER};transition:border-color .15s;}}
.alt-cause:hover{{border-color:{ACCENT2};}}
.alt-cause-rank{{font-size:.65rem;font-weight:800;padding:2px 7px;border-radius:6px;flex-shrink:0;}}
.alt-rank-1{{background:#fef9c3;color:#854d0e;border:1px solid #fde68a;}}.alt-rank-2{{background:#f0f9ff;color:#0369a1;border:1px solid #bae6fd;}}
.alt-cause-text{{font-size:.78rem;color:{TEXT};flex:1;line-height:1.4;}}
.alt-cause-prob{{font-size:.7rem;font-weight:700;color:{TEXT3};white-space:nowrap;}}
.smart-suggestions{{display:flex;flex-wrap:wrap;gap:.45rem;}}
.suggestion-pill{{display:inline-flex;align-items:center;gap:.35rem;background:{SURFACE2};border:1.5px solid {BORDER};color:{TEXT};padding:.4rem .8rem;border-radius:20px;font-size:.74rem;font-weight:600;transition:all .15s;}}
.suggestion-pill:hover{{background:{ACCENT};color:#fff;border-color:{ACCENT};transform:translateY(-1px);box-shadow:0 2px 8px rgba(79,70,229,.2);}}
.pattern-label{{display:inline-flex;align-items:center;gap:.45rem;padding:.4rem .85rem;border-radius:20px;font-size:.72rem;font-weight:700;}}
.pattern-known{{background:#f0fdf4;color:#166534;border:1.5px solid #bbf7d0;}}.pattern-unknown{{background:#fefce8;color:#854d0e;border:1.5px solid #fde68a;}}

.demo-banner{{background:linear-gradient(135deg,#7c3aed 0%,#4f46e5 100%);padding:.6rem 1.75rem;display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;}}
.demo-banner-icon{{font-size:1.1rem;}}
.demo-banner-text{{font-size:.8rem;font-weight:700;color:#fff;flex:1;}}
.demo-banner-sub{{font-size:.7rem;color:rgba(255,255,255,.75);}}
.demo-scenario-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:.65rem;margin-bottom:.85rem;}}
.demo-scenario-card{{background:{SURFACE};border:2px solid {BORDER};border-radius:11px;padding:.85rem 1rem;cursor:pointer;transition:all .2s;text-align:left;}}
.demo-scenario-card:hover{{border-color:{ACCENT};box-shadow:0 4px 16px rgba(79,70,229,.18);transform:translateY(-2px);}}
.demo-scenario-card.active{{border-color:{ACCENT};background:{'#f5f3ff' if theme=='light' else '#1e1a42'};}}
.dsc-icon{{font-size:1.5rem;margin-bottom:.4rem;}}.dsc-title{{font-size:.8rem;font-weight:800;color:{TEXT};margin-bottom:.2rem;}}.dsc-desc{{font-size:.7rem;color:{TEXT2};line-height:1.4;}}
.dsc-tag{{display:inline-block;font-size:.6rem;font-weight:700;padding:2px 7px;border-radius:6px;margin-top:.4rem;background:#ede9fe;color:#5b21b6;}}

.walkthrough-bar{{background:{'#fefce8' if theme=='light' else '#1c1a05'};border:1.5px solid {'#fde68a' if theme=='light' else '#854d0e'};border-radius:10px;padding:.65rem 1rem;margin-bottom:.75rem;display:flex;align-items:center;gap:.75rem;}}
.wt-steps{{display:flex;gap:.4rem;flex-wrap:wrap;flex:1;}}
.wt-step{{display:flex;align-items:center;gap:.35rem;font-size:.74rem;font-weight:600;padding:.3rem .65rem;border-radius:20px;background:{SURFACE2};color:{TEXT2};border:1px solid {BORDER};}}
.wt-step.active{{background:{ACCENT};color:#fff;border-color:{ACCENT};animation:fadeIn .3s ease;}}
.wt-step.done{{background:#f0fdf4;color:#16a34a;border-color:#bbf7d0;}}
.wt-dismiss{{font-size:.7rem;color:{TEXT3};cursor:pointer;padding:.25rem .5rem;border-radius:6px;border:1px solid {BORDER};background:{SURFACE};transition:all .15s;white-space:nowrap;}}
.wt-dismiss:hover{{color:{TEXT};border-color:{TEXT3};}}

.logiq-footer{{background:{SURFACE};border-top:1px solid {BORDER};padding:1.2rem 2rem;margin-top:0;}}
.footer-inner{{max-width:1380px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.75rem;}}
.footer-brand{{display:flex;align-items:center;gap:.6rem;}}
.footer-mark{{width:24px;height:24px;border-radius:6px;background:linear-gradient(135deg,#4f46e5,#7c3aed);display:flex;align-items:center;justify-content:center;font-size:11px;}}
.footer-name{{font-size:.82rem;font-weight:800;color:{TEXT};letter-spacing:-.01em;}}.footer-name em{{color:{ACCENT};font-style:normal;}}
.footer-tagline{{font-size:.7rem;color:{TEXT3};margin-top:1px;}}
.footer-meta{{display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap;}}
.footer-link{{font-size:.72rem;color:{TEXT2};font-weight:500;text-decoration:none;transition:color .15s;}}.footer-link:hover{{color:{ACCENT};}}
.footer-sep{{color:{BORDER};font-size:.7rem;}}
.footer-credit{{font-size:.7rem;color:{TEXT3};text-align:right;line-height:1.5;}}

.sdiv{{height:1px;background:{BORDER};margin:.75rem 0;}}
.element-container{{margin-bottom:0!important;}}
div[data-testid="column"]{{padding:0 .35rem!important;}}
div[data-testid="column"]:first-child{{padding-left:0!important;}}
div[data-testid="column"]:last-child{{padding-right:0!important;}}
.stVerticalBlock{{gap:.45rem!important;}}
[data-testid="stHorizontalBlock"]{{align-items:flex-start!important;}}
.stCodeBlock{{overflow-x:auto!important;max-width:100%!important;}}
.stCodeBlock pre{{overflow-x:auto!important;white-space:pre-wrap!important;word-break:break-word!important;max-width:100%!important;}}
[data-testid="stDownloadButton"]>button{{height:auto!important;padding:.62rem 1.3rem!important;}}
.ghost .stButton>button{{height:36px!important;padding:.4rem .9rem!important;font-size:.78rem!important;}}
.stAlert{{border-radius:9px!important;margin-bottom:.5rem!important;}}
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"]{{gap:.4rem!important;}}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════
def preprocess_logs(raw: str):
    lines = raw.splitlines()
    seen, clean = set(), []
    for line in lines:
        s = line.strip()
        if not s or s in seen: continue
        seen.add(s); clean.append(s)
    stats = {"total": len(clean), "errors": 0, "warnings": 0, "fatals": 0, "dups": len(lines)-len(clean)}
    for line in clean:
        ll = line.lower()
        if   "fatal" in ll[:22]: stats["fatals"]   += 1
        elif "error" in ll[:22]: stats["errors"]   += 1
        elif "warn"  in ll[:22]: stats["warnings"] += 1
    return "\n".join(clean), stats

def looks_like_logs(text: str) -> bool:
    patterns = [
        r'\[\s*(error|warn|info|debug|fatal|critical)\s*\]',
        r'\d{4}-\d{2}-\d{2}', r'\d{2}:\d{2}:\d{2}',
        r'(exception|traceback|stacktrace)',
        r'(connection refused|timeout|failed|crashed)',
        r'(error code|exit code|errno)',
        r'at\s+\w+\.\w+\(', r'file ".+", line \d+',
        r'(nginx|apache|docker|kubernetes|postgresql|mysql)',
        r'(http|https)://\S+', r'\b(500|404|403|401|503)\b',
    ]
    text_low = text.lower()
    score = sum(1 for p in patterns if re.search(p, text_low))
    if any(kw in text_low for kw in ["error","warn","fatal","exception","traceback","crash","fail"]):
        score += 3
    return score >= 2

def parse_result(text: str) -> dict:
    keys = ["Severity","Confidence","Root Cause","Explanation","Solution","Prevention"]
    out = {}
    for i, k in enumerate(keys):
        nxt = keys[i+1] if i+1 < len(keys) else None
        try:
            s = text.index(f"{k}:") + len(f"{k}:")
            e = text.index(f"{nxt}:") if nxt and f"{nxt}:" in text else len(text)
            out[k] = text[s:e].strip()
        except ValueError:
            out[k] = ""
    return out

def sev_html(severity: str, confidence: str, elapsed: float = 0.0) -> str:
    s   = severity.strip().lower()
    cls = "sp-hi" if "high" in s else ("sp-md" if "medium" in s else "sp-lo")
    dot = "🔴" if "high" in s else ("🟡" if "medium" in s else "🟢")
    cf  = f'<span class="sp sp-cf">⚡ {confidence}</span>' if confidence else ""
    tm  = f'<span class="sp sp-tm">⏱ {elapsed:.1f}s</span>' if elapsed > 0 else ""
    return f'<div class="sevrow"><span class="sp {cls}">{dot} {severity}</span>{cf}{tm}</div>'

def bullets_html(text: str) -> str:
    lines = [l.strip().lstrip("-•*0123456789.) ").strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return f"<span style='color:{TEXT3};font-size:.79rem;'>Not available</span>"
    return "<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"

def highlight_logs(raw: str) -> str:
    out = []
    for line in raw.splitlines():
        l = line.strip()
        if not l: continue
        ll = l.lower()
        if   "fatal" in ll[:22]: out.append(f'<div class="lv-fa">{l}</div>')
        elif "error" in ll[:22]: out.append(f'<div class="lv-er">{l}</div>')
        elif "warn"  in ll[:22]: out.append(f'<div class="lv-wn">{l}</div>')
        elif "info"  in ll[:22]: out.append(f'<div class="lv-in">{l}</div>')
        elif "debug" in ll[:22]: out.append(f'<div class="lv-db">{l}</div>')
        elif any(k in ll for k in ["success","started","ready","connected"]): out.append(f'<div class="lv-ok">{l}</div>')
        else: out.append(f'<div class="lv-df">{l}</div>')
    return "\n".join(out)

def save_history(logs, parsed, raw, elapsed):
    entry = {
        "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "root": parsed.get("Root Cause","—"), "severity": parsed.get("Severity","—"),
        "raw": raw, "logs": logs, "parsed": parsed, "elapsed": elapsed,
    }
    st._global_history.insert(0, entry)
    if len(st._global_history) > 20:
        st._global_history = st._global_history[:20]
    # keep session state in sync
    st.session_state.history = st._global_history

def build_report(logs, parsed, raw, elapsed):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (f"LogIQ — AI Root Cause Analysis Report\nGenerated  : {ts}\nElapsed    : {elapsed:.2f}s\n{'='*56}\n\n"
            f"SEVERITY   : {parsed.get('Severity','—')}\nCONFIDENCE : {parsed.get('Confidence','—')}\n\n"
            f"ROOT CAUSE\n{'-'*40}\n{parsed.get('Root Cause','—')}\n\nEXPLANATION\n{'-'*40}\n{parsed.get('Explanation','—')}\n\n"
            f"SOLUTION\n{'-'*40}\n{parsed.get('Solution','—')}\n\nPREVENTION\n{'-'*40}\n{parsed.get('Prevention','—')}\n\n"
            f"{'='*56}\nORIGINAL LOGS\n{'-'*40}\n{logs}\n\n{'='*56}\nRAW AI OUTPUT\n{'-'*40}\n{raw}\n")

def is_log_related(q: str) -> bool:
    kws = [
        "error","log","crash","fail","exception","stack","trace","traceback",
        "debug","warn","fatal","fix","cause","root","issue","bug","problem",
        "server","database","db","connection","timeout","memory","cpu","disk",
        "service","deploy","kubernetes","docker","nginx","apache","redis","kafka",
        "python","java","node","react","sql","http","api","port","socket",
        "network","ssl","cert","auth","permission","denied","refused","500","404",
        "monitor","alert","metric","cloud","aws","gcp","azure","cve",
        "vulnerability","patch","config","env","variable","bash","command",
        "process","thread","heap","segfault","oom","restart","rollback",
        "query","latency","vs code","vscode","android studio","ide",
        # chip question keywords
        "critical","prevent","happen","happened","why","how","what","step",
        "debugging","commands","exact","show","give","tell","explain","analyze",
        "analysis","result","severity","solution","recommendation","this",
    ]
    return any(k in q.lower() for k in kws)

def detect_context(logs: str) -> dict:
    logs_lower = logs.lower()
    context = {"environment":"Unknown","tech_stack":[],"log_type":"Application logs","service_name":"","confidence":"Low"}
    env_patterns = {
        "Docker":["docker","container","dockerfile","docker-compose"],
        "Kubernetes":["kubernetes","k8s","kubectl","pod","deployment","namespace","kube-"],
        "Production":["prod","production","prd-"], "Staging":["staging","stage","stg-"],
        "AWS":["aws","ec2","s3","lambda","cloudwatch","ecs","eks"],
        "GCP":["gcp","gke","cloud run","compute engine"],"Azure":["azure","aks","app service"]
    }
    detected_envs = [env for env, patterns in env_patterns.items() if any(p in logs_lower for p in patterns)]
    if detected_envs:
        context["environment"] = ", ".join(detected_envs[:2])
        context["confidence"] = "High" if len(detected_envs) >= 2 else "Medium"
    tech_patterns = {
        "Node.js":["node","npm","express","javascript","js:","package.json"],
        "Python":["python","pip","django","flask","fastapi",".py","traceback"],
        "Java":["java","spring","maven","gradle",".jar","jvm"],
        "Go":["golang","go:",".go"],
        "PostgreSQL":["postgres","psql","pg_","port 5432"],"MySQL":["mysql","mariadb","port 3306"],
        "MongoDB":["mongo","mongodb","port 27017"],"Redis":["redis","port 6379"],
        "Nginx":["nginx","port 80","port 443"],"Apache":["apache","httpd"],
        "Docker":["docker","container"],"Kubernetes":["kubernetes","k8s","kubectl"]
    }
    context["tech_stack"] = [tech for tech, patterns in tech_patterns.items() if any(p in logs_lower for p in patterns)]
    if any(kw in logs_lower for kw in ["container","docker","pod","kubernetes"]): context["log_type"] = "Container logs"
    elif any(kw in logs_lower for kw in ["kernel","systemd","dmesg"]): context["log_type"] = "System logs"
    service_patterns = [r'service[:\s]+([a-z0-9\-_]+)',r'app[:\s]+([a-z0-9\-_]+)',r'container[:\s]+([a-z0-9\-_]+)']
    for pattern in service_patterns:
        match = re.search(pattern, logs_lower)
        if match:
            context["service_name"] = match.group(1); break
    return context

def build_failure_timeline(p: dict) -> str:
    root = p.get("Root Cause","").lower(); expl = p.get("Explanation","").lower()
    conf_raw = p.get("Confidence",""); severity = p.get("Severity","").lower()
    ctx = p.get("_context",{}); env = ctx.get("environment",""); service = ctx.get("service_name","")
    conf_pct = 75
    m = re.search(r'(\d{1,3})\s*%', conf_raw)
    if m: conf_pct = min(int(m.group(1)),100)
    elif "high" in conf_raw.lower(): conf_pct = 92
    elif "medium" in conf_raw.lower(): conf_pct = 68
    elif "low" in conf_raw.lower(): conf_pct = 42
    conf_color = "#22c55e" if conf_pct>=80 else ("#eab308" if conf_pct>=55 else "#ef4444")
    combined = root+" "+expl
    is_db = any(k in combined for k in ["database","db","postgres","mysql","mongo","redis","sql","connection pool","port 5432","port 3306"])
    is_network = any(k in combined for k in ["network","dns","timeout","refused","unreachable","socket","tls","ssl"])
    is_memory = any(k in combined for k in ["memory","oom","heap","out of memory","gc"])
    is_auth = any(k in combined for k in ["auth","permission","denied","unauthorized","403","401","token","credential"])
    is_api = any(k in combined for k in ["api","endpoint","request","response","http","500","404","503","gateway"])
    is_disk = any(k in combined for k in ["disk","storage","space","i/o","filesystem"])
    is_config = any(k in combined for k in ["config","env","variable","missing","not found","undefined","null"])
    is_k8s = any(k in combined+env.lower() for k in ["kubernetes","k8s","pod","deployment"])
    is_docker = any(k in combined+env.lower() for k in ["docker","container","compose"])
    nodes = []
    if is_k8s: nodes += [("☸️","K8s Ingress","Request in","ok"),("📦","Pod","Scheduled","ok")]
    elif is_docker: nodes += [("🐳","Docker","Container","ok"),("🔀","Network","Bridge","ok")]
    else: nodes += [("🌐","Client","Request","ok"),("⚡","API Gateway","Routing","ok")]
    if is_auth: nodes += [("🔐","Auth Service","Validating","warn"),("🚫","Auth","Denied ❌","fail")]
    elif is_db: nodes += [("🖥️",service or "App","Processing","ok"),("🔌","DB Connect","Attempting","warn"),("🗄️","Database","Failed ❌","fail")]
    elif is_memory: nodes += [("🖥️",service or "App","Running","ok"),("💾","Memory","Exhausted ❌","fail")]
    elif is_network: nodes += [("🖥️",service or "App","Processing","ok"),("🌐","Network","Unreachable","warn"),("❌","Connection","Failed ❌","fail")]
    elif is_config: nodes += [("⚙️","Config","Loading","warn"),("❌","Config","Missing ❌","fail")]
    else: nodes += [("🖥️",service or "App","Processing","ok"),("❌","Service","Failed ❌","fail")]
    flow_html = '<div class="ftl-flow">'
    for i,(icon,label,sub,status) in enumerate(nodes):
        flow_html += f'<div class="ftl-node {status}"><div class="ftl-node-circle">{icon}</div><div class="ftl-node-label">{label}</div><div class="ftl-node-sub">{sub}</div></div>'
        if i < len(nodes)-1:
            ns = nodes[i+1][3]; pc = "fail-path" if ns=="fail" else ("ok-path" if status=="ok" else "")
            flow_html += f'<div class="ftl-arrow"><div class="ftl-arrow-line {pc}"></div><div class="ftl-arrow-head {pc}">▶</div></div>'
    flow_html += '</div>'
    steps = [("ok","Request Received","Incoming request accepted by the system","✓ OK")]
    if is_k8s: steps.append(("ok","Pod Scheduled","Kubernetes scheduled the workload successfully","✓ OK"))
    elif is_docker: steps.append(("ok","Container Started","Docker container initialised and running","✓ OK"))
    else: steps.append(("ok","API Processed","Request routed to the correct service handler","✓ OK"))
    if is_auth: steps += [("warn","Auth Check","Authentication attempted","⚠ Warn"),("fail","Access Denied ❌","Credentials invalid or permission missing","✗ Fail")]
    elif is_db: steps += [("warn","DB Connection Attempt","Service tried to open a database connection","⚠ Warn"),("fail","Connection Failed ❌","Database unreachable — pool exhausted or host down","✗ Fail")]
    elif is_memory: steps += [("warn","Memory Pressure","Heap usage climbing above safe threshold","⚠ Warn"),("fail","OOM / Crash ❌","Process killed — out of memory","✗ Fail")]
    elif is_network: steps += [("warn","Network Call","Service attempted outbound connection","⚠ Warn"),("fail","Connection Refused ❌","Remote host unreachable or port closed","✗ Fail")]
    elif is_config: steps += [("warn","Config Load","Application tried to read configuration","⚠ Warn"),("fail","Config Missing ❌","Required environment variable or file not found","✗ Fail")]
    else: steps += [("warn","Processing","Service encountered an unexpected condition","⚠ Warn"),("fail","Service Error ❌","Unhandled exception or fatal error raised","✗ Fail")]
    steps_html = '<div class="ftl-steps">' + "".join(
        f'<div class="ftl-step {status}"><div class="ftl-step-num">{i+1}</div><div class="ftl-step-body"><div class="ftl-step-title">{title}</div><div class="ftl-step-desc">{desc}</div></div><div class="ftl-step-badge {("ok" if status=="ok" else "fail" if status=="fail" else "warn")}">{badge}</div></div>'
        for i,(status,title,desc,badge) in enumerate(steps)
    ) + '</div>'
    affected = []
    if is_db: affected.append("Database")
    if is_api: affected.append("API Layer")
    if is_auth: affected.append("Auth Service")
    if is_network: affected.append("Network")
    if is_memory: affected.append("Runtime")
    if service: affected.insert(0, service)
    if not affected: affected = ["Application"]
    user_impact = "Requests failing" if is_api or is_db else ("Service degraded" if is_network or is_memory else ("Access blocked" if is_auth else "Service unstable"))
    sev_color = "#dc2626" if "high" in severity else ("#d97706" if "medium" in severity else "#16a34a")
    impact_html = f'<div class="ftl-impact"><div class="ftl-impact-card"><div class="ftl-impact-label">Affected Services</div><div class="ftl-impact-value">{" · ".join(affected[:4])}</div></div><div class="ftl-impact-card"><div class="ftl-impact-label">User Impact</div><div class="ftl-impact-value">{user_impact}</div></div><div class="ftl-impact-card"><div class="ftl-impact-label">Severity</div><div class="ftl-impact-value" style="color:{sev_color};font-weight:800;">{severity.title()}</div></div><div class="ftl-impact-card"><div class="ftl-impact-label">Failure Point</div><div class="ftl-impact-value">{nodes[-1][1]}</div></div></div>'
    conf_html = f'<div class="ftl-conf"><span class="ftl-conf-label">AI Confidence</span><div class="ftl-conf-bar-wrap"><div class="ftl-conf-bar" style="width:{conf_pct}%;background:{conf_color};"></div></div><span class="ftl-conf-pct" style="color:{conf_color};">{conf_pct}%</span></div>'
    return f'<div class="ftl-wrap fade-in"><div class="ftl-head"><span class="ftl-head-icon">📊</span><span class="ftl-head-title">Failure Timeline &amp; Incident Breakdown</span><span class="ftl-head-badge">Auto-generated</span></div><div class="ftl-body">{flow_html}{steps_html}{impact_html}{conf_html}</div></div>'

def build_ai_intelligence(p: dict, logs: str = "") -> str:
    root = p.get("Root Cause","").lower(); expl = p.get("Explanation","").lower()
    conf_raw = p.get("Confidence",""); severity = p.get("Severity","").lower(); logs_low = logs.lower()
    combined = root+" "+expl+" "+logs_low
    conf_pct = 75
    m = re.search(r'(\d{1,3})\s*%', conf_raw)
    if m: conf_pct = min(int(m.group(1)),100)
    elif "high" in conf_raw.lower(): conf_pct = 92
    elif "medium" in conf_raw.lower(): conf_pct = 68
    elif "low" in conf_raw.lower(): conf_pct = 42
    conf_color = "#22c55e" if conf_pct>=80 else ("#eab308" if conf_pct>=55 else "#ef4444")
    conf_label = "High" if conf_pct>=80 else ("Medium" if conf_pct>=55 else "Low")
    conf_reasons = []
    if any(k in combined for k in ["connection refused","port 5432","port 3306","port 6379"]): conf_reasons.append("repeated connection-refused pattern matched known DB failure signature")
    if any(k in combined for k in ["oom","out of memory","heap","killed"]): conf_reasons.append("OOM kill signal is an unambiguous OS-level indicator")
    if any(k in combined for k in ["timeout","timed out","deadline"]): conf_reasons.append("consistent timeout pattern across multiple log lines")
    if any(k in combined for k in ["traceback","exception","stack trace"]): conf_reasons.append("full stack trace provides precise failure location")
    if any(k in logs_low for k in ["fatal","critical"]): conf_reasons.append("FATAL/CRITICAL keywords confirm severity")
    if not conf_reasons: conf_reasons.append("error pattern matched known failure taxonomy")
    conf_reason_text = " and ".join(conf_reasons[:2]).capitalize()+"."
    steps = []
    kw_map = {"connection refused":"connection refused","oom":"OOMKilled","out of memory":"out of memory","timeout":"timeout","traceback":"Traceback","exception":"Exception","fatal":"FATAL","port 5432":"port 5432","port 3306":"port 3306","502":"502","504":"504","segfault":"segfault"}
    detected_kws = [f'<span class="rs-keyword">{label}</span>' for key,label in kw_map.items() if key in combined]
    if detected_kws: steps.append(f"Detected signal keywords: {' '.join(detected_kws[:3])}")
    else: steps.append("Scanned log lines for error-level keywords and anomaly signals")
    if any(k in combined for k in ["connection refused","port 5432","port 3306","pool"]): steps.append('Matched against <span class="rs-keyword">database connectivity</span> failure pattern')
    elif any(k in combined for k in ["oom","out of memory","heap","killed"]): steps.append('Matched against <span class="rs-keyword">memory exhaustion</span> pattern')
    elif any(k in combined for k in ["timeout","timed out","gateway"]): steps.append('Matched against <span class="rs-keyword">network timeout</span> pattern')
    else: steps.append('Cross-referenced error signature against known failure taxonomy')
    sev_icon = "🔴" if "high" in severity or "critical" in severity else ("🟡" if "medium" in severity else "🔵")
    steps.append(f'Classified severity as <span class="rs-keyword">{sev_icon} {severity.title()}</span> based on error frequency and impact scope')
    ctx = p.get("_context",{}); env = ctx.get("environment",""); tech = ctx.get("tech_stack","")
    if env and env!="Unknown": steps.append(f'Applied <span class="rs-keyword">{env}</span> environment context')
    elif tech: steps.append(f'Identified <span class="rs-keyword">{tech}</span> stack')
    else: steps.append('Generated environment-agnostic fix steps')
    steps_html = "".join(f'<div class="reasoning-step" style="animation-delay:{i*0.06:.2f}s"><div class="rs-num">{i+1}</div><div class="rs-text">{step}</div></div>' for i,step in enumerate(steps))
    if any(k in combined for k in ["connection refused","pool","port 5432"]):
        alts = [("~25%","Firewall or security group blocking the database port"),("~12%","Database service crashed or was restarted mid-request")]
    elif any(k in combined for k in ["oom","out of memory","heap"]):
        alts = [("~20%","Memory leak in application code — objects not being garbage collected"),("~10%","Container memory limit set too low for the workload")]
    elif any(k in combined for k in ["timeout","timed out"]):
        alts = [("~22%","Network latency spike between services — not a crash"),("~15%","Upstream service under heavy load — needs horizontal scaling")]
    else:
        alts = [("~20%","Intermittent infrastructure issue — may resolve on retry"),("~10%","Misconfiguration in environment variables or config files")]
    alts_html = "".join(f'<div class="alt-cause"><span class="alt-cause-rank alt-rank-{i+1}">Alt {i+1}</span><span class="alt-cause-text">{text}</span><span class="alt-cause-prob">{prob}</span></div>' for i,(prob,text) in enumerate(alts))
    suggestions = []
    if any(k in combined for k in ["connection","pool","retry"]): suggestions += ["Add retry logic with exponential backoff","Enable connection pool monitoring","Set connection timeout limits"]
    if any(k in combined for k in ["memory","heap","oom"]): suggestions += ["Add memory usage alerts","Profile heap allocations","Increase pod memory limits"]
    if not suggestions: suggestions = ["Add structured logging","Enable health checks","Set up alerting on error rate"]
    pills_html = "".join(f'<span class="suggestion-pill">💡 {s}</span>' for s in suggestions[:5])
    known_patterns = {"Database Connection Failure":["connection refused","pool exhausted","port 5432","port 3306"],"Memory Exhaustion / OOMKill":["oom","out of memory","heap limit","killed"],"Network Timeout / Gateway Error":["timeout","timed out","502","504","gateway"],"Authentication / Permission Failure":["permission denied","unauthorized","401","403"],"Disk / Storage Full":["no space left","disk full","i/o error"],"Application Crash / Unhandled Exception":["traceback","unhandled exception","segfault","exit code 1"]}
    matched_pattern = next((name for name,kws in known_patterns.items() if any(k in combined for k in kws)), None)
    pattern_html = f'<span class="pattern-label pattern-known">✅ Known Pattern: {matched_pattern}</span>' if matched_pattern else '<span class="pattern-label pattern-unknown">🔍 New / Unknown Pattern</span>'
    sev_color_map = {"high":"#dc2626","critical":"#dc2626","medium":"#d97706","low":"#16a34a","info":"#2563eb"}
    sev_bg_map    = {"high":"#fef2f2","critical":"#fef2f2","medium":"#fefce8","low":"#f0fdf4","info":"#eff6ff"}
    sev_bd_map    = {"high":"#fecaca","critical":"#fecaca","medium":"#fde68a","low":"#bbf7d0","info":"#bfdbfe"}
    sev_key = "high" if "high" in severity or "critical" in severity else ("medium" if "medium" in severity else ("info" if "info" in severity else "low"))
    sev_icon_full = "🔴 Critical" if sev_key in ("high","critical") else ("🟡 Warning" if sev_key=="medium" else ("🔵 Info" if sev_key=="info" else "🟢 Low"))
    return f"""
    <div class="ai-intel fade-in">
      <div class="ai-intel-head"><span class="ai-intel-head-icon">🧠</span><span class="ai-intel-head-title">AI Reasoning &amp; Intelligence</span><span class="ai-intel-head-tag">Explainable AI</span></div>
      <div class="ai-intel-body">
        <div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;">{pattern_html}<span class="pattern-label" style="background:{sev_bg_map[sev_key]};color:{sev_color_map[sev_key]};border:1.5px solid {sev_bd_map[sev_key]};">{sev_icon_full}</span></div>
        <div><p style="font-size:.68rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{TEXT3};margin-bottom:.5rem;">Why this is the root cause</p><div class="reasoning-chain">{steps_html}</div></div>
        <div class="conf-explain"><div class="conf-explain-row"><span class="conf-explain-pct" style="color:{conf_color};">{conf_pct}%</span><div style="flex:1;"><div class="conf-explain-label">{conf_label} Confidence</div><div class="conf-explain-bar-wrap"><div class="conf-explain-bar" style="width:{conf_pct}%;background:{conf_color};"></div></div></div></div><div class="conf-explain-reason"><strong>Why {conf_pct}%?</strong> {conf_reason_text}</div></div>
        <div><p style="font-size:.68rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{TEXT3};margin-bottom:.5rem;">Alternative causes</p><div class="alt-causes">{alts_html}</div></div>
        <div><p style="font-size:.68rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{TEXT3};margin-bottom:.5rem;">Smart suggestions</p><div class="smart-suggestions">{pills_html}</div></div>
      </div>
    </div>"""

def render_results(p: dict, elapsed: float = 0.0):
    confidence = p.get("Confidence","").strip(); severity = p.get("Severity","Unknown").strip()
    st.markdown(f"""<div class="result-metadata fade-in"><div class="meta-item meta-severity"><span class="meta-label">Severity</span><span class="meta-value meta-sev-{'high' if 'high' in severity.lower() else 'medium' if 'medium' in severity.lower() else 'low'}">{severity}</span></div>{f'<div class="meta-item"><span class="meta-label">Confidence</span><span class="meta-value">⚡ {confidence}</span></div>' if confidence else ''}{f'<div class="meta-item"><span class="meta-label">Analysis Time</span><span class="meta-value">⏱ {elapsed:.1f}s</span></div>' if elapsed > 0 else ''}</div>""", unsafe_allow_html=True)
    root_cause = p.get("Root Cause","—")
    st.markdown(f"""<div class="result-card rc-root fade-up"><div class="rc-header"><div class="rc-icon">🔴</div><div class="rc-title">Root Cause</div><div class="rc-priority">Critical</div></div><div class="rc-content"><p class="rc-main-text">{root_cause}</p></div></div>""", unsafe_allow_html=True)
    solution = p.get("Solution",""); sol_lines = [l.strip().lstrip("-•*0123456789.) ").strip() for l in solution.splitlines() if l.strip()]
    sol_html = "<ol class='fix-steps'>"+"".join(f"<li>{line}</li>" for line in sol_lines)+"</ol>" if sol_lines else "<p class='rc-empty'>No solution provided</p>"
    st.markdown(f"""<div class="result-card rc-fix fade-up" style="animation-delay:.05s"><div class="rc-header"><div class="rc-icon">🛠️</div><div class="rc-title">Fix Steps</div></div><div class="rc-content">{sol_html}</div></div>""", unsafe_allow_html=True)
    if sol_lines:
        fix_text = "\n".join(f"{i+1}. {line}" for i,line in enumerate(sol_lines))
        st.markdown('<div style="margin-top:-.4rem;margin-bottom:.6rem;">', unsafe_allow_html=True)
        st.code(fix_text, language="text")
        st.markdown('</div>', unsafe_allow_html=True)
    explanation = p.get("Explanation","—")
    st.markdown(f"""<div class="result-card rc-explain fade-up" style="animation-delay:.1s"><div class="rc-header"><div class="rc-icon">📘</div><div class="rc-title">Plain English Explanation</div></div><div class="rc-content"><p class="rc-text">{explanation}</p></div></div>""", unsafe_allow_html=True)
    prevention = p.get("Prevention",""); prev_lines = [l.strip().lstrip("-•*0123456789.) ").strip() for l in prevention.splitlines() if l.strip()]
    prev_html = "<ul class='prevent-list'>"+"".join(f"<li>{line}</li>" for line in prev_lines)+"</ul>" if prev_lines else "<p class='rc-empty'>No prevention tips provided</p>"
    st.markdown(f"""<div class="result-card rc-prevent fade-up" style="animation-delay:.15s"><div class="rc-header"><div class="rc-icon">🛡️</div><div class="rc-title">Prevention</div></div><div class="rc-content">{prev_html}</div></div>""", unsafe_allow_html=True)

MODEL = "Gemini 2.5 Flash"

def run_analysis(text: str):
    try:
        result = analyze_logs(text)
        return (result,"") if result and not result.startswith("❌") else ("", result or "Unknown error")
    except Exception as e:
        logger.error(f"Analysis error: {e}"); return "", str(e)


# ══════════════════════════════════════════════════════════════════════
#  NAV — query-param routing
# ══════════════════════════════════════════════════════════════════════
query_params = st.query_params
if "tab" in query_params:
    rt = query_params["tab"]
    if rt in ["analyzer","history","about"]: st.session_state.active_tab = rt
if "theme" in query_params:
    rth = query_params["theme"]
    if rth in ["light","dark"]:
        st.session_state.theme = rth
        st._global_state["theme"] = rth   # persist immediately so next nav keeps it
if "demo" in query_params:
    dv = query_params["demo"] == "1"
    st.session_state.demo_mode = dv
    st._global_state["demo_mode"] = dv    # persist immediately
    if dv and st.session_state.walkthrough_step == 0:
        st.session_state.walkthrough_step = 1

t = st.session_state.active_tab

# Handle sample log selection
if st.session_state.get("_run_sample"):
    _sample = st.session_state["_run_sample"]
    st.session_state.log_text     = _sample
    st.session_state.logs_dirty   = False
    st.session_state.auto_analyze = True
    st.session_state["_run_sample"] = None
    if "logs_ta" in st.session_state: del st.session_state["logs_ta"]

_theme_display = {"light":"🌞 Light","dark":"🌙 Dark"}.get(st.session_state.theme,"🌞 Light")

st.markdown(f"""
<style>
.logiq-nav{{background:{SURFACE};border-bottom:1px solid {BORDER};height:52px;display:flex;align-items:center;padding:0 1.5rem;position:sticky;top:0;z-index:9999;box-shadow:0 1px 4px rgba(0,0,0,0.06);}}
.nav-logo{{display:flex;align-items:center;gap:8px;margin-right:1.5rem;flex-shrink:0;}}
.nav-mark{{width:30px;height:30px;border-radius:7px;background:linear-gradient(135deg,#4f46e5,#7c3aed);display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 2px 6px rgba(79,70,229,.35);}}
.nav-brand{{font-size:.98rem;font-weight:800;color:{TEXT};letter-spacing:-.02em;}}
.nav-brand em{{color:{ACCENT};font-style:normal;}}
.nav-tabs{{display:flex;align-items:stretch;height:52px;gap:0;flex:1;}}
.nav-tab{{display:flex;align-items:center;gap:5px;padding:0 1.1rem;font-size:.82rem;font-weight:500;color:{TEXT2};background:transparent;border:none;border-bottom:3px solid transparent;cursor:pointer;height:52px;white-space:nowrap;font-family:'Inter',sans-serif;transition:color .15s,border-color .15s,background .15s;outline:none;text-decoration:none!important;}}
.nav-tab:hover{{color:{TEXT};background:{'rgba(79,70,229,0.05)' if theme=='light' else 'rgba(99,102,241,0.1)'};border-bottom:3px solid {TEXT3};}}
.nav-tab.active{{color:{ACCENT};border-bottom:3px solid {ACCENT};font-weight:700;}}
.nav-right{{margin-left:auto;display:flex;align-items:center;gap:.6rem;}}
.theme-btn{{background:{SURFACE2};border:1px solid {BORDER};color:{TEXT};border-radius:8px;padding:5px 12px;font-size:.75rem;font-weight:600;font-family:'Inter',sans-serif;cursor:pointer;display:flex;align-items:center;gap:6px;transition:border-color .15s,background .15s;outline:none;white-space:nowrap;}}
.theme-btn:hover{{border-color:{ACCENT};background:{'#f5f3ff' if theme=='light' else '#1e1a42'};}}
.theme-dropdown{{position:relative;display:inline-block;}}
.theme-menu{{display:none;position:absolute;top:calc(100% + 6px);right:0;background:{SURFACE};border:1px solid {BORDER};border-radius:9px;box-shadow:0 4px 16px rgba(0,0,0,0.12);min-width:130px;z-index:99999;overflow:hidden;}}
.theme-dropdown:focus-within .theme-menu,.theme-dropdown:hover .theme-menu{{display:block;}}
.theme-option{{display:block;width:100%;padding:8px 14px;font-size:.78rem;font-weight:500;color:{TEXT};background:transparent;border:none;text-align:left;cursor:pointer;font-family:'Inter',sans-serif;text-decoration:none;transition:background .12s;}}
.theme-option:hover{{background:{SURFACE2};}}
.theme-option.selected{{color:{ACCENT};font-weight:700;}}
</style>

<div class="logiq-nav">
  <div class="nav-logo">
    <div class="nav-mark">🔍</div>
    <span class="nav-brand">Log<em>IQ</em></span>
  </div>
  <div class="nav-tabs">
    <a href="?tab=analyzer" target="_self" class="nav-tab {'active' if t=='analyzer' else ''}">🔍 Analyzer</a>
    <a href="?tab=history"  target="_self" class="nav-tab {'active' if t=='history'  else ''}">📂 History</a>
    <a href="?tab=about"    target="_self" class="nav-tab {'active' if t=='about'    else ''}">💡 About LogIQ</a>
  </div>
  <div class="nav-right">
    <a href="?tab={t}&demo={'0' if st.session_state.demo_mode else '1'}" target="_self" style="display:inline-flex;align-items:center;gap:.4rem;background:{'linear-gradient(135deg,#7c3aed,#4f46e5)' if st.session_state.demo_mode else SURFACE2};color:{'#fff' if st.session_state.demo_mode else TEXT2};border:1.5px solid {'#7c3aed' if st.session_state.demo_mode else BORDER};border-radius:8px;padding:5px 12px;font-size:.75rem;font-weight:700;font-family:'Inter',sans-serif;text-decoration:none;transition:all .2s;white-space:nowrap;">
      🎬 {'Demo ON' if st.session_state.demo_mode else 'Demo Mode'}
    </a>
    <div class="theme-dropdown" tabindex="0">
      <button class="theme-btn">{_theme_display} ▾</button>
      <div class="theme-menu">
        <a href="?tab={t}&theme=light" target="_self" class="theme-option {'selected' if st.session_state.theme=='light' else ''}">🌞 Light</a>
        <a href="?tab={t}&theme=dark"  target="_self" class="theme-option {'selected' if st.session_state.theme=='dark'  else ''}">🌙 Dark</a>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
#  ██  ANALYZER
# ══════════════════════════════════════════════════════════════════════
if st.session_state.active_tab == "analyzer":

    st.markdown(f"""
    <div class="hero-compact fade-in">
      <div class="trust-bar">
        <span class="trust-item"><span class="trust-dot"></span>10,000+ logs analyzed</span>
        <span class="trust-item">⚡ ~5s average analysis</span>
        <span class="trust-item">🎯 Used for real DevOps debugging</span>
        <span class="trust-badge">🤖 AI Powered</span>
        <span class="trust-badge">🔴 Real-time Analysis</span>
      </div>
      <div class="hero-compact-inner" style="padding:.9rem 0 .5rem;">
        <h1 class="hero-compact-h1">Paste Logs. <span class="hl">Get Root Cause, Fix &amp; Prevention</span> Instantly.</h1>
        <p class="hero-compact-sub">Paste error logs (Docker, K8s, app logs...) and get a structured diagnosis in seconds • Free • No signup</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    DEMO_SCENARIOS = {
        "🗄️ Database Connection Failure": {"desc":"PostgreSQL refusing connections — pool exhausted","tag":"Backend · DB","logs":"[ERROR] 2024-01-15 09:32:11 - Connection refused: db-host:5432\n[ERROR] 2024-01-15 09:32:11 - org.postgresql.util.PSQLException: FATAL: remaining connection slots are reserved\n[ERROR] 2024-01-15 09:32:12 - HikariPool-1 - Connection is not available, request timed out after 30000ms\n[ERROR] 2024-01-15 09:32:12 - Max retries exceeded (3/3)\n[FATAL] 2024-01-15 09:32:13 - Application crashed with exit code 1"},
        "☸️ Kubernetes Pod Crash": {"desc":"OOMKilled — pod exceeding memory limits","tag":"Kubernetes · Memory","logs":"Warning  OOMKilling  kubelet  Memory cgroup out of memory: Kill process 4321 (node) score 1989 or sacrifice child\nError: pod/api-gateway-7d9f8b-xk2p9 failed with reason OOMKilled\n[FATAL] 2024-01-15 10:11:03 - Process killed: out of memory (heap limit 512Mi exceeded)\nBackoff restarting failed container api-gateway in pod api-gateway-7d9f8b-xk2p9\nWarning  BackOff  kubelet  Back-off restarting failed container"},
        "⏱️ API Timeout Error": {"desc":"Upstream service not responding — 504 cascade","tag":"API · Network","logs":"2024/01/15 08:45:01 [error] 1234#0: *5678 upstream timed out (110: Connection timed out) while reading response header from upstream\n2024/01/15 08:45:01 [error] upstream: http://payment-service:8080/api/charge, host: api.example.com\nHTTP/1.1 504 Gateway Timeout\n[ERROR] 2024-01-15 08:45:02 - PaymentService: request timeout after 30s (retries: 3/3)\n[ERROR] 2024-01-15 08:45:02 - Circuit breaker OPEN for payment-service"},
    }

    if st.session_state.demo_mode:
        st.markdown(f"""<div class="demo-banner"><span class="demo-banner-icon">🎬</span><div><div class="demo-banner-text">Demo Mode Active — Perfect for presentations &amp; interviews</div><div class="demo-banner-sub">Select a scenario below to instantly load a real-world error and see the full analysis</div></div></div>""", unsafe_allow_html=True)
        st.markdown(f'<div style="padding:.85rem 1.75rem 0;max-width:1380px;margin:0 auto;"><p class="mlbl" style="margin-bottom:.55rem;">Choose a scenario</p>', unsafe_allow_html=True)
        sc_cols = st.columns(3)
        for i,(title,meta) in enumerate(DEMO_SCENARIOS.items()):
            with sc_cols[i]:
                if st.button(f"{title}", key=f"demo_sc_{i}", use_container_width=True):
                    st.session_state.log_text = meta["logs"]; st.session_state.logs_dirty=False; st.session_state.auto_analyze=True; st.session_state.walkthrough_step=2; st.rerun()
                st.markdown(f'<p style="font-size:.7rem;color:{TEXT2};margin:-.3rem 0 .5rem .1rem;line-height:1.4;">{meta["desc"]}<br><span style="font-size:.62rem;color:{TEXT3};">{meta["tag"]}</span></p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        if 1 <= st.session_state.walkthrough_step <= 3:
            wt_steps = [("1","Paste or select logs",1),("2","Click Analyze",2),("3","View root cause & fix",3)]
            steps_html = "".join(f'<div class="wt-step {"active" if st.session_state.walkthrough_step==n else "done" if st.session_state.walkthrough_step>n else ""}"><strong>{num}</strong> {label}</div>' for num,label,n in wt_steps)
            st.markdown(f'<div style="padding:.5rem 1.75rem 0;max-width:1380px;margin:0 auto;"><div class="walkthrough-bar"><span style="font-size:.8rem;font-weight:700;color:{"#854d0e" if theme=="light" else "#fbbf24"};">👋 Guided Tour</span><div class="wt-steps">{steps_html}</div><span class="wt-dismiss" onclick="this.parentElement.style.display=\'none\'">✕ Dismiss</span></div></div>', unsafe_allow_html=True)

    st.markdown('<div class="body" style="padding-top:1rem;">', unsafe_allow_html=True)
    left, right = st.columns([1, 1.45], gap="medium")

    with left:
        st.markdown('<p class="mlbl">Paste or Upload Logs</p>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Upload", type=["log","txt","csv"], label_visibility="collapsed", key="uploader")
        if uploaded and uploaded.name != st.session_state.last_file:
            try:
                content = uploaded.read().decode("utf-8", errors="ignore")
                if not content.strip():
                    st.markdown('<div class="banner b-err">⚠️ Uploaded file is empty.</div>', unsafe_allow_html=True)
                else:
                    if len(content) > 500_000: content = content[:500_000]
                    st.session_state.log_text=content; st.session_state.last_file=uploaded.name; st.session_state.auto_analyze=True; st.session_state.logs_dirty=False
                    st.rerun()
            except Exception as e:
                st.markdown(f'<div class="banner b-err">❌ Could not read file: {e}</div>', unsafe_allow_html=True)

        prev = st.session_state.log_text
        logs = st.text_area(
            label="logs", value=st.session_state.log_text, height=340,
            key="logs_ta", label_visibility="collapsed",
            placeholder=(
                "Paste error logs here (Docker, K8s, app logs, stack traces...)\n\n"
                "── Example: Database Error ──────────────────────────\n"
                "[ERROR] 2024-01-15 09:32:11 - Connection refused: db-host:5432\n"
                "[ERROR] 2024-01-15 09:32:12 - Max retries exceeded (3/3)\n"
                "[FATAL] Application crashed with exit code 1\n\n"
                "── Example: Kubernetes OOM ──────────────────────────\n"
                "Warning OOMKilling kubelet: Kill process 4321 (node)\n"
                "Error: pod/api-gateway crashed with OOMKilled\n\n"
                "── Example: Python Traceback ────────────────────────\n"
                "Traceback (most recent call last):\n"
                "  File 'app.py', line 42, in <module>\n"
                "    db.connect(host, port)\n"
                "ConnectionRefusedError: [Errno 111] Connection refused\n\n"
                "── Example: Nginx 502 ───────────────────────────────\n"
                "[error] upstream timed out (110) while reading response\n"
                "HTTP/1.1 502 Bad Gateway"
            ),
        )
        if logs != prev:
            st.session_state.log_text = logs; st.session_state.logs_dirty = True
        logs = st.session_state.log_text

        st.markdown(f'<p style="font-size:.68rem;color:{TEXT3};margin:.35rem 0 .5rem .1rem;line-height:1.5;">Supports: Docker, Kubernetes, Nginx, Python, Java, Node.js, PostgreSQL, and more</p>', unsafe_allow_html=True)

        if logs and logs.strip():
            _, stats = preprocess_logs(logs)
            parts = []
            if stats["fatals"]   > 0: parts.append(f'<span class="pbadge pb-e">💀 {stats["fatals"]} FATAL</span>')
            if stats["errors"]   > 0: parts.append(f'<span class="pbadge pb-e">❌ {stats["errors"]} ERROR</span>')
            if stats["warnings"] > 0: parts.append(f'<span class="pbadge pb-w">⚠️ {stats["warnings"]} WARN</span>')
            if stats["dups"]     > 0: parts.append(f'<span class="pbadge pb-ok">🗑 {stats["dups"]} dupes removed</span>')
            if parts:
                st.markdown('<div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:.5rem;">'+"".join(parts)+'</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        st.markdown('<div class="analyze-btn-wrap">', unsafe_allow_html=True)
        if st.session_state.analyzing:
            st.markdown(f'<button disabled style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);color:#fff;border:none;border-radius:12px;padding:.95rem 2rem;font-family:\'Inter\',sans-serif;font-weight:800;font-size:1rem;width:100%;box-shadow:0 6px 24px rgba(79,70,229,.4);cursor:not-allowed;opacity:0.7;letter-spacing:.01em;">⚡ Analyzing...</button>', unsafe_allow_html=True)
            analyze_btn = False
        else:
            analyze_btn = st.button("⚡ Find Root Cause Now", key="abtn", use_container_width=True, disabled=st.session_state.analyzing)
        st.markdown(f'<div class="btn-subtext">🚀 Results in <span class="btn-subtext-highlight">~5 seconds</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background:{SURFACE2};border-radius:8px;padding:.65rem .85rem;margin-top:.5rem;border:1px solid {BORDER};">
          <p style="font-size:.68rem;font-weight:600;color:{ACCENT};line-height:1.5;margin:0 0 .4rem 0;">💡 Pro Tips for Best Results</p>
          <ul style="font-size:.67rem;font-weight:500;color:{TEXT2};line-height:1.7;margin:0;padding-left:1.1rem;">
            <li>Include ERROR, WARN, or FATAL keywords</li>
            <li>Add timestamps and full stack traces</li>
            <li>Paste complete error context, not snippets</li>
            <li>Include surrounding log lines for context</li>
          </ul>
        </div>
        """, unsafe_allow_html=True)

    with right:
        st.markdown('<p class="mlbl">Analysis Results</p>', unsafe_allow_html=True)
        trigger = analyze_btn or st.session_state.auto_analyze
        if st.session_state.auto_analyze: st.session_state.auto_analyze = False
        logs = st.session_state.log_text

        if trigger:
            logs = st.session_state.log_text
            if not logs or not logs.strip():
                st.markdown('<div class="banner b-err">⚠️ Please paste or upload some logs first.</div>', unsafe_allow_html=True)
            elif not looks_like_logs(logs):
                st.markdown(f"""<div class="toast toast-err"><span class="toast-icon">❌</span> Input doesn't look like system logs — paste actual error logs or stack traces</div><div class="empty fade-in" style="margin-top:.5rem;"><div class="empty-ico">🚫</div><p class="empty-t">Not recognised as log data</p><p class="empty-s" style="max-width:320px;">LogIQ needs technical log files — error messages, stack traces, or lines with ERROR / WARN / FATAL keywords.</p></div>""", unsafe_allow_html=True)
                logger.info("Non-log input rejected.")
            else:
                st.session_state.logs_dirty=False; st.session_state.analyzing=True; st.session_state.feedback=None
                st._global_state["feedback"]=None
                detected = detect_context(logs); st.session_state.detected_context = detected
                final_env = st.session_state.environment if st.session_state.environment!="Auto-detect" else detected["environment"]
                final_tech = st.session_state.tech_stack if st.session_state.tech_stack!="Auto-detect" else (", ".join(detected["tech_stack"][:2]) if detected["tech_stack"] else "Unknown")
                final_service = st.session_state.service_name if st.session_state.service_name else detected["service_name"]
                st.markdown("""<div class="step-progress fade-in"><div class="sp-ring"></div><div class="sp-title">Analyzing your logs…</div><div class="sp-steps"><div class="sp-step done"><span class="sp-step-icon">✅</span> Parsing logs</div><div class="sp-step done"><span class="sp-step-icon">✅</span> Detecting patterns</div><div class="sp-step active"><span class="sp-step-icon">⚡</span> Finding root cause</div><div class="sp-step"><span class="sp-step-icon">🛠️</span> Generating fix</div></div></div>""", unsafe_allow_html=True)
                context_info = f"\nENVIRONMENT CONTEXT:\n- Environment: {final_env}\n- Technology: {final_tech}\n- Log Type: {detected['log_type']}\n{f'- Service: {final_service}' if final_service else ''}\n"
                enhanced_logs = f"{context_info}\n\n{preprocess_logs(logs)[0]}"
                t0 = time.perf_counter()
                raw, err = run_analysis(enhanced_logs)
                elapsed = time.perf_counter()-t0
                st.session_state.analyzing = False
                if err:
                    st.error(f"❌ Analysis failed: {err}")
                else:
                    parsed = parse_result(raw)
                    parsed["_context"] = {"environment":final_env,"tech_stack":final_tech,"log_type":detected["log_type"],"service_name":final_service,"confidence":detected["confidence"]}
                    st.session_state.rca_result=raw; st.session_state.rca_parsed=parsed; st.session_state.rca_elapsed=elapsed
                    save_history(logs,parsed,raw,elapsed)
                    # Persist critical state globally so URL navigation doesn't lose it
                    _persist_keys = ["rca_result","rca_parsed","rca_elapsed","log_text","demo_mode",
                                     "theme","chat_history","feedback","feedback_count","detected_context",
                                     "environment","tech_stack","log_type","service_name","walkthrough_step"]
                    for _k in _persist_keys:
                        st._global_state[_k] = st.session_state.get(_k)
                    if st.session_state.demo_mode: st.session_state.walkthrough_step=3
                    st.rerun()

        if st.session_state.rca_parsed and not trigger:
            p = st.session_state.rca_parsed
            if st.session_state.logs_dirty:
                st.markdown('<div class="stale">⚠️ Logs changed — re-analyze to refresh results.</div>', unsafe_allow_html=True)
            else:
                sev = p.get("Severity","").lower()
                toast_icon = "✅" if "low" in sev else ("⚠️" if "medium" in sev else "🔴")
                st.markdown(f'<div class="toast toast-ok"><span class="toast-icon">{toast_icon}</span> Analysis completed — root cause identified</div>', unsafe_allow_html=True)

            html_parts = []
            if "_context" in p and p["_context"]["environment"]!="Unknown":
                ctx=p["_context"]; svc_html=f'<span class="ctx-service">Service: {ctx["service_name"]}</span>' if ctx.get("service_name") else ''
                html_parts.append(f'<div class="context-banner fade-in"><div class="ctx-icon">🎯</div><div class="ctx-content"><span class="ctx-label">Detected Context:</span><span class="ctx-text">{ctx["environment"]} • {ctx["tech_stack"]} • {ctx["log_type"]}</span>{svc_html}</div><div class="ctx-badge">{ctx["confidence"]} confidence</div></div>')
            html_parts.append(build_failure_timeline(p))
            confidence=p.get("Confidence","").strip(); severity=p.get("Severity","Unknown").strip(); elapsed=st.session_state.rca_elapsed
            meta_conf=f'<div class="meta-item"><span class="meta-label">Confidence</span><span class="meta-value">⚡ {confidence}</span></div>' if confidence else ''
            meta_time=f'<div class="meta-item"><span class="meta-label">Analysis Time</span><span class="meta-value">⏱ {elapsed:.1f}s</span></div>' if elapsed>0 else ''
            sev_cls="high" if "high" in severity.lower() else ("medium" if "medium" in severity.lower() else "low")
            html_parts.append(f'<div class="result-metadata fade-in"><div class="meta-item meta-severity"><span class="meta-label">Severity</span><span class="meta-value meta-sev-{sev_cls}">{severity}</span></div>{meta_conf}{meta_time}</div>')
            root_cause=p.get("Root Cause","—")
            html_parts.append(f'<div class="result-card rc-root fade-up"><div class="rc-header"><div class="rc-icon">🔴</div><div class="rc-title">Root Cause</div><div class="rc-priority">Critical</div></div><div class="rc-content"><p class="rc-main-text">{root_cause}</p></div></div>')
            solution=p.get("Solution",""); sol_lines=[l.strip().lstrip("-•*0123456789.) ").strip() for l in solution.splitlines() if l.strip()]
            sol_html="<ol class='fix-steps'>"+"".join(f"<li>{l}</li>" for l in sol_lines)+"</ol>" if sol_lines else "<p class='rc-empty'>No solution provided</p>"
            html_parts.append(f'<div class="result-card rc-fix fade-up" style="animation-delay:.05s"><div class="rc-header"><div class="rc-icon">🛠️</div><div class="rc-title">Fix Steps</div></div><div class="rc-content">{sol_html}</div></div>')
            explanation=p.get("Explanation","—")
            html_parts.append(f'<div class="result-card rc-explain fade-up" style="animation-delay:.1s"><div class="rc-header"><div class="rc-icon">📘</div><div class="rc-title">Plain English Explanation</div></div><div class="rc-content"><p class="rc-text">{explanation}</p></div></div>')
            prevention=p.get("Prevention",""); prev_lines=[l.strip().lstrip("-•*0123456789.) ").strip() for l in prevention.splitlines() if l.strip()]
            prev_html="<ul class='prevent-list'>"+"".join(f"<li>{l}</li>" for l in prev_lines)+"</ul>" if prev_lines else "<p class='rc-empty'>No prevention tips provided</p>"
            html_parts.append(f'<div class="result-card rc-prevent fade-up" style="animation-delay:.15s"><div class="rc-header"><div class="rc-icon">🛡️</div><div class="rc-title">Prevention</div></div><div class="rc-content">{prev_html}</div></div>')
            scroll_bg="#1a1d27" if theme=="dark" else "#ffffff"; scroll_border="#2e3349" if theme=="dark" else "#e5e7eb"; scroll_shadow="rgba(0,0,0,0.12)" if theme=="dark" else "rgba(0,0,0,0.04)"
            st.markdown(f'<div style="height:540px;overflow-y:auto;overflow-x:hidden;border:1px solid {scroll_border};border-radius:12px;background:{scroll_bg};padding:.85rem .9rem;box-shadow:0 1px 6px {scroll_shadow};">{"".join(html_parts)}</div>', unsafe_allow_html=True)

            st.markdown(f'<div style="margin-top:1rem;margin-bottom:.5rem;background:{SURFACE2};border:1px solid {BORDER};border-radius:10px;padding:.6rem .9rem;display:flex;align-items:center;justify-content:space-between;"><span style="font-size:.76rem;font-weight:600;color:{TEXT2};">Was this analysis helpful?</span><span style="font-size:.67rem;color:{TEXT3};font-style:italic;">🔄 This system improves with more logs</span></div>', unsafe_allow_html=True)
            dt=datetime.datetime.now().strftime("%Y-%m-%d")
            act_col1,act_col2,act_col3=st.columns([1,1,1])
            with act_col1:
                if st.button("👍  Correct",key="fb_up",use_container_width=True):
                    st.session_state.feedback="up"
                    st.session_state.feedback_count["up"]+=1
                    st._global_state["feedback"]="up"
                    st._global_state["feedback_count"]=st.session_state.feedback_count
                    st.rerun()
            with act_col2:
                if st.button("👎  Incorrect",key="fb_down",use_container_width=True):
                    st.session_state.feedback="down"
                    st.session_state.feedback_count["down"]+=1
                    st._global_state["feedback"]="down"
                    st._global_state["feedback_count"]=st.session_state.feedback_count
                    st.rerun()
            with act_col3:
                st.download_button("📄 Download TXT",data=build_report(logs,p,st.session_state.rca_result or "",st.session_state.rca_elapsed),file_name=f"logiq_report_{dt}.txt",mime="text/plain",use_container_width=True)
            if st.session_state.feedback=="up": st.markdown('<p style="font-size:.74rem;color:#16a34a;font-weight:600;margin-top:.2rem;">✅ Thanks! Feedback recorded.</p>', unsafe_allow_html=True)
            elif st.session_state.feedback=="down": st.markdown('<p style="font-size:.74rem;color:#dc2626;font-weight:600;margin-top:.2rem;">📝 Noted — we\'ll use this to improve.</p>', unsafe_allow_html=True)

        elif not trigger and not st.session_state.rca_parsed:
            SAMPLE_LOGS = {
                "🗄️ PostgreSQL Connection Refused":"[ERROR] 2024-01-15 09:32:11 - Connection refused: db-host:5432\n[ERROR] 2024-01-15 09:32:12 - FATAL: Max retries exceeded (3/3)\n[ERROR] 2024-01-15 09:32:12 - org.postgresql.util.PSQLException: Connection refused\n[FATAL] Application crashed with exit code 1",
                "☸️ Kubernetes Pod OOMKilled":"Warning  OOMKilling  kubelet  Memory cgroup out of memory: Kill process 4321 (node)\nError: pod/api-gateway-7d9f8b crashed with OOMKilled\n[FATAL] 2024-01-15 10:11:03 - Process killed: out of memory (heap limit 512Mi)\nBackoff restarting failed container api-gateway in pod api-gateway-7d9f8b",
                "🌐 Nginx 502 Bad Gateway":"2024/01/15 08:45:01 [error] 1234#0: *5678 connect() failed (111: Connection refused) while connecting to upstream\n2024/01/15 08:45:01 [error] upstream: http://127.0.0.1:3000/api/users\n2024/01/15 08:45:01 [warn] 1234#0: *5678 upstream server temporarily disabled\nHTTP/1.1 502 Bad Gateway",
                "🐍 Python Traceback":"Traceback (most recent call last):\n  File \"app.py\", line 42, in <module>\n    db.connect(host, port)\n  File \"db.py\", line 18, in connect\n    socket.connect((host, port))\nConnectionRefusedError: [Errno 111] Connection refused\n[ERROR] 2024-01-15 11:02:33 - Database connection failed",
                "🔐 Auth Service 401 Unauthorized":"[ERROR] 2024-01-15 14:22:01 - HTTP 401 Unauthorized: invalid or expired token\n[ERROR] 2024-01-15 14:22:01 - auth-service: JWT verification failed: signature mismatch\n[WARN]  2024-01-15 14:22:02 - Retry 1/3 failed for /api/user/profile\n[ERROR] 2024-01-15 14:22:05 - Max retries exceeded, request aborted",
                "💾 Disk Full / No Space Left":"[ERROR] 2024-01-15 16:45:11 - OSError: [Errno 28] No space left on device\n[ERROR] 2024-01-15 16:45:11 - Failed to write log file: /var/log/app/app.log\n[FATAL] 2024-01-15 16:45:12 - Application cannot start: disk quota exceeded\n[ERROR] 2024-01-15 16:45:12 - errno 28: No space left on device",
            }
            st.markdown(f'<div class="sample-logs-state fade-in"><div class="sl-header"><span class="sl-title">Try a sample error</span><span class="sl-badge">Click to auto-fill &amp; analyze</span></div>', unsafe_allow_html=True)
            for title,log_text in SAMPLE_LOGS.items():
                preview = log_text.splitlines()[0][:72]+"…"
                if st.button(title,key=f"sample_{title}",use_container_width=True):
                    st.session_state["_run_sample"]=log_text; st.rerun()
                st.markdown(f'<p style="font-family:\'JetBrains Mono\',monospace;font-size:.65rem;color:{TEXT3};margin:-.4rem 0 .45rem .1rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{preview}</p>', unsafe_allow_html=True)
            st.markdown(f'<div class="sl-hint"><span>👆</span><span>Or paste your own logs on the left and click <strong>Find Root Cause Now</strong></span></div></div>', unsafe_allow_html=True)

    # ── CHAT + HOWTO ─────────────────────────────────────────────────
    st.markdown('<div class="sdiv"></div>', unsafe_allow_html=True)
    chat_col, info_col = st.columns([2, 1], gap="medium")

    with chat_col:
        st.markdown('<p class="mlbl">Deep Dive into This Issue</p>', unsafe_allow_html=True)
        current_root_cause = ""
        if st.session_state.rca_parsed:
            current_root_cause = st.session_state.rca_parsed.get("Root Cause","")

        st.markdown(f"""
        <div class="chat-shell">
          <div class="chat-head">
            <span style="font-size:13px;">💬</span>
            <span class="ch-title">Ask Follow-up Questions</span>
            <span class="ch-sub">Context-aware AI assistant</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── FIX 1: Quick question chips write to pending_chat_q ──────
        # Only show chips if analysis exists and no chat history yet
        if not st.session_state.chat_history and st.session_state.rca_parsed:
            st.markdown(f'<div style="padding:.55rem .9rem .3rem;background:{SURFACE2};border-left:none;border-right:none;border-top:none;border-bottom:1px solid {BORDER};"><p style="font-size:.62rem;font-weight:700;color:{TEXT3};margin:0 0 .4rem 0;letter-spacing:.06em;text-transform:uppercase;">Quick Questions</p></div>', unsafe_allow_html=True)
            chips = [
                "💡 Why did this happen?",
                "🔧 Give me exact commands",
                "🐳 How to fix in Docker?",
                "⚠️ Is this critical?",
                "🔄 How to prevent this?",
                "📊 Show me debugging steps",
            ]
            chip_cols = st.columns(3)
            for idx, chip_text in enumerate(chips):
                with chip_cols[idx % 3]:
                    st.markdown('<div class="chip-btn">', unsafe_allow_html=True)
                    if st.button(chip_text, key=f"chip_{idx}", use_container_width=True):
                        # FIX: write to pending_chat_q, not chat_q (which is owned by text_input widget)
                        st.session_state.pending_chat_q = chip_text
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

        # ── FIX 3: Fixed-height scrollable chat messages area ─────────
        # This prevents huge gap between chat and footer
        spin_ph = st.empty()

        if st.session_state.chat_history:
            msgs = "".join(
                f'<div class="cmsg cmsg-user"><div class="cav cav-u">👤</div><div class="cbbl cbbl-u">{m}</div></div>'
                if r == "You" else
                f'<div class="cmsg cmsg-ai"><div class="cav cav-a">🤖</div><div class="cbbl cbbl-a">{m}</div></div>'
                for r, m in st.session_state.chat_history
            )
            spin_ph.markdown(f'<div class="chat-msgs">{msgs}</div>', unsafe_allow_html=True)
        else:
            if st.session_state.rca_parsed:
                spin_ph.markdown(f"""
                <div class="chat-msgs">
                  <div class="chat-nil">
                    <span style="font-size:1.5rem;display:block;margin-bottom:.4rem;">🎯</span>
                    <strong>I'm ready to help with this issue</strong>
                    <span style="display:block;margin-top:.3rem;font-size:.73rem;">I know about: <strong>{current_root_cause[:80]}{"..." if len(current_root_cause)>80 else ""}</strong></span>
                    <span style="color:#818cf8;font-size:.68rem;display:block;margin-top:6px;">Click a suggestion above or type your question</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                spin_ph.markdown(f"""
                <div class="chat-msgs">
                  <div class="chat-nil">
                    <span style="font-size:1.5rem;display:block;margin-bottom:.4rem;">💬</span>
                    Run an analysis first, then ask follow-up questions here.
                    <br><span style="color:#818cf8;font-size:.68rem;display:block;margin-top:6px;">I'll have full context about your logs and root cause.</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

        # Input row — text box + clear button side by side, pinned above footer
        st.markdown(f'<div class="chat-ft" style="padding:.55rem .9rem;border-top:1px solid {BORDER};background:{SURFACE};">', unsafe_allow_html=True)
        inp_col, btn_col = st.columns([6, 1], gap="small")
        with inp_col:
            user_q = st.text_input(
                label="cq", key="chat_q", label_visibility="collapsed",
                placeholder="Ask anything about this issue (e.g., how to fix, why it happened, exact commands...)"
            )
        with btn_col:
            st.markdown('<div class="ghost clear-btn-wrap">', unsafe_allow_html=True)
            if st.button("🗑️ Clear", key="clrchat", use_container_width=True):
                st.session_state.chat_history = []
                st.session_state.last_chat_q  = ""
                st.session_state.pending_chat_q = ""
                st._global_state["chat_history"] = []  # clear global store too
                if "chat_q" in st.session_state:
                    del st.session_state["chat_q"]
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Determine what question to process ───────────────────────
        # Priority: pending_chat_q (from chips) > typed input
        active_q = ""
        from_chip = False
        if st.session_state.pending_chat_q and st.session_state.pending_chat_q != st.session_state.last_chat_q:
            active_q = st.session_state.pending_chat_q
            from_chip = True
            st.session_state.pending_chat_q = ""   # consume immediately
        elif user_q and user_q.strip() and user_q.strip() != st.session_state.last_chat_q:
            active_q = user_q.strip()

        if active_q:
            q = active_q
            st.session_state.last_chat_q = q

            if not from_chip and not is_log_related(q):
                st.session_state.chat_history.append(("You", q))
                st.session_state.chat_history.append(("AI","⚠️ I specialize in log analysis, error debugging, and DevOps issues. Please ask something related to your logs or the error you're investigating."))
                logger.info("Off-topic chat rejected.")
                st.rerun()
            else:
                st.session_state.chat_history.append(("You", q))
                log_ctx = ""
                if logs and logs.strip():
                    log_ctx += f"\n=== ANALYZED LOGS ===\n{logs[:800]}\n"
                if st.session_state.rca_parsed:
                    p = st.session_state.rca_parsed
                    log_ctx += f"\n=== ANALYSIS RESULTS ===\nRoot Cause: {p.get('Root Cause','N/A')}\nSeverity: {p.get('Severity','N/A')}\nExplanation: {p.get('Explanation','N/A')[:300]}\nSolution: {p.get('Solution','N/A')[:300]}\n"
                    if "_context" in p:
                        ctx = p["_context"]
                        log_ctx += f"\n=== ENVIRONMENT ===\nEnvironment: {ctx.get('environment','Unknown')}\nTech Stack: {ctx.get('tech_stack','Unknown')}\n"
                wants_commands = any(kw in q.lower() for kw in ["command","cmd","bash","shell","docker","kubectl","npm","run","execute"])
                env_hint = ""
                if st.session_state.rca_parsed and "_context" in st.session_state.rca_parsed:
                    env = st.session_state.rca_parsed["_context"].get("environment","")
                    if "Docker" in env: env_hint = "- Provide Docker-specific commands (docker, docker-compose)\n"
                    elif "Kubernetes" in env: env_hint = "- Provide Kubernetes-specific commands (kubectl)\n"
                prompt = (
                    f"You are a senior DevOps/SRE expert helping debug a production issue.\n{log_ctx}\n"
                    f"User Question: {q}\n\nINSTRUCTIONS:\n- Give ONE direct, specific answer (not multiple options)\n"
                    f"- Use 3-5 bullet points (• as bullet)\n- Be practical and actionable\n"
                    f"- Reference the specific root cause, logs, and environment context above\n{env_hint}"
                    f"{'- Include code blocks with ``` for commands\n' if wants_commands else ''}"
                    f"- Do NOT add intro/conclusion text outside bullets\n"
                )
                spin_ph.markdown(f"""
                <div class="chat-msgs">
                  <div class="chat-nil">
                    <div class="sring" style="width:34px;height:34px;border-width:3px;margin-bottom:.6rem;"></div>
                    <div class="stxt" style="font-size:.74rem">Analyzing context...</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                try:
                    resp = analyze_logs(prompt)
                    if not resp or resp.startswith("❌"): resp = "❌ Could not generate a response. Please try again."
                except Exception as e:
                    resp = f"❌ Error: {e}"; logger.error(f"Chat error: {e}")
                spin_ph.empty()
                st.session_state.chat_history.append(("AI", resp))
                st._global_state["chat_history"] = st.session_state.chat_history
                st.rerun()

    with info_col:
        st.markdown('<p class="mlbl">How It Works</p>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="howto">
          <p class="howto-h">Context-Aware Assistant</p>
          <div class="step">
            <div class="stepn" style="background:#ede9fe;color:#5b21b6;">🎯</div>
            <div><p class="stept">Full Context</p><p class="steps">I know your logs, root cause, and analysis results</p></div>
          </div>
          <div class="step">
            <div class="stepn" style="background:#dbeafe;color:#1d4ed8;">💡</div>
            <div><p class="stept">Smart Answers</p><p class="steps">Specific to YOUR issue, not generic advice</p></div>
          </div>
          <div class="step">
            <div class="stepn" style="background:#dcfce7;color:#166534;">⚡</div>
            <div><p class="stept">Actionable</p><p class="steps">Get exact commands, not just explanations</p></div>
          </div>
          <div class="trybox">
            <p class="trylbl">Example Questions</p>
            <p class="tryitems" style="font-size:.72rem;line-height:1.9;">
              • "Why did this specific error happen?"<br>
              • "Give me the exact Docker command to fix this"<br>
              • "How critical is this issue?"<br>
              • "Show me debugging steps"<br>
              • "What's the fastest way to resolve this?"<br>
              • "Is this a security vulnerability?"
            </p>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # FOOTER
    st.markdown(f"""
    <div class="logiq-footer">
      <div class="footer-inner">
        <div class="footer-brand">
          <div class="footer-mark">🔍</div>
          <div>
            <div class="footer-name">Log<em>IQ</em></div>
            <div class="footer-tagline">AI DevOps Root Cause Analysis Tool</div>
          </div>
        </div>
        <div class="footer-meta">
          <span class="footer-link">🤖 AI Powered</span>
          <span class="footer-sep">·</span>
          <span class="footer-link">⚡ Real-time Analysis</span>
          <span class="footer-sep">·</span>
          <span class="footer-link">🔒 No data stored</span>
        </div>
        <div class="footer-credit">
          Built by <strong>Praduman Dadhich</strong> &amp; <strong>Akshat Acharya</strong><br>
          <span style="font-size:.65rem;">Powered by Gemini 2.5 Flash</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  ██  HISTORY
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "history":
    st.markdown('<div class="body-tight" style="padding-top:.5rem;">', unsafe_allow_html=True)
    if not st.session_state.history:
        st.markdown('<p class="mlbl" style="margin-bottom:.5rem;">Analysis History</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="empty" style="margin-top:.25rem;"><div class="empty-ico">📂</div><p class="empty-t">No history yet</p><p class="empty-s">Run your first analysis in the Analyzer tab</p></div>', unsafe_allow_html=True)
    else:
        h1, h2 = st.columns([8, 1])
        with h1:
            st.markdown('<p class="mlbl" style="margin-bottom:0;line-height:36px;">Analysis History &nbsp;<span style="font-weight:400;text-transform:none;letter-spacing:0;font-size:.7rem;">— Last 20 analyses</span></p>', unsafe_allow_html=True)
        with h2:
            st.markdown('<div class="ghost">', unsafe_allow_html=True)
            if st.button("🗑 Clear All", key="clrhist", use_container_width=True):
                st.session_state.history = []
                st._global_history.clear()
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        for i, e in enumerate(st.session_state.history):
            sev=e.get("severity","").lower(); dot="🔴" if "high" in sev else ("🟡" if "medium" in sev else "🟢")
            rc=(e["root"][:72]+"…") if len(e["root"])>72 else e["root"]
            with st.expander(f"{dot}  [{e['ts']}]  {rc}", expanded=False):
                p=e.get("parsed",{})
                st.markdown(sev_html(e.get("severity","—"),p.get("Confidence",""),e.get("elapsed",0)), unsafe_allow_html=True)
                render_results(p, e.get("elapsed",0))
                st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
                st.download_button("⬇️  Download Report",data=build_report(e["logs"],p,e.get("raw",""),e.get("elapsed",0)),file_name=f"logiq_report_{e['ts'].replace(' ','_').replace(':','-')}.txt",mime="text/plain",use_container_width=True,key=f"dl_{i}")
    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  ██  ABOUT LOGIQ
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "about":
    st.markdown(f"""
    <style>
    /* ── About page scoped styles ── */
    .ab-page{{padding:.35rem 1.5rem 2rem;max-width:1200px;margin:0 auto;}}

    /* Full-page background for About tab */
    .stApp .about-bg{{
        position:fixed;inset:0;z-index:0;pointer-events:none;
        background:
            radial-gradient(ellipse 70% 50% at 90% 10%, {'rgba(99,102,241,0.45)' if theme=='light' else 'rgba(99,102,241,0.12)'} 0%, transparent 60%),
            radial-gradient(ellipse 50% 40% at 5% 80%, {'rgba(124,58,237,0.38)' if theme=='light' else 'rgba(124,58,237,0.1)'} 0%, transparent 55%),
            radial-gradient(ellipse 40% 30% at 50% 50%, {'rgba(79,70,229,0.25)' if theme=='light' else 'rgba(79,70,229,0.07)'} 0%, transparent 60%);
    }}
    .about-bg::before{{
        content:'';position:absolute;inset:0;
        background-image:
            radial-gradient({'rgba(79,70,229,0.55)' if theme=='light' else 'rgba(139,92,246,0.15)'} 1px, transparent 1px);
        background-size:28px 28px;
        mask-image:radial-gradient(ellipse 80% 80% at 50% 50%, black 30%, transparent 100%);
        -webkit-mask-image:radial-gradient(ellipse 80% 80% at 50% 50%, black 30%, transparent 100%);
    }}

    /* Header */
    .ab-header{{padding:.35rem 0 .9rem;border-bottom:1px solid {BORDER};margin-bottom:1.1rem;}}
    .ab-title{{font-size:1.75rem;font-weight:800;letter-spacing:-.04em;line-height:1;margin:0 0 .3rem 0;
        background:linear-gradient(135deg,{ACCENT} 0%,#7c3aed 60%,#a78bfa 100%);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
        display:inline-block;}}
    .ab-subtitle{{font-size:.82rem;color:{TEXT2};margin:0;line-height:1.5;}}

    /* Tagline banner */
    .ab-banner{{
        background:linear-gradient(135deg,#1e1b4b 0%,#312e81 55%,#4338ca 100%);
        border-radius:12px;padding:.85rem 1.1rem;margin-bottom:1.1rem;
        border:1px solid rgba(99,102,241,.25);
    }}
    .ab-banner-label{{font-size:.58rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(199,210,254,.55);margin:0 0 .3rem 0;}}
    .ab-banner-quote{{font-size:.9rem;font-weight:700;color:#e0e7ff;line-height:1.5;margin:0 0 .6rem 0;letter-spacing:-.01em;}}
    .ab-badge{{display:inline-flex;align-items:center;gap:4px;background:rgba(255,255,255,.1);color:#c7d2fe;
        padding:2px 8px;border-radius:8px;font-size:.65rem;font-weight:700;
        border:1px solid rgba(255,255,255,.15);margin-right:.35rem;margin-bottom:.25rem;}}

    /* How it works */
    .ab-steps{{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem;}}
    .ab-step{{
        background:{SURFACE};border:1px solid {BORDER};border-radius:11px;
        padding:.85rem .75rem;text-align:center;
        box-shadow:0 1px 4px rgba(0,0,0,{'0.1' if theme=='dark' else '0.04'});
        transition:transform .15s,box-shadow .15s;
    }}
    .ab-step:hover{{transform:translateY(-2px);box-shadow:0 4px 14px rgba(79,70,229,.12);}}
    .ab-step-icon{{font-size:1.65rem;margin-bottom:.4rem;display:block;}}
    .ab-step-num{{display:inline-block;background:linear-gradient(135deg,{ACCENT},{ACCENT2});
        color:#fff;font-size:.58rem;font-weight:800;padding:1px 6px;border-radius:6px;
        letter-spacing:.04em;margin-bottom:.3rem;}}
    .ab-step-title{{font-size:.82rem;font-weight:800;color:{TEXT};margin-bottom:.25rem;}}
    .ab-step-desc{{font-size:.71rem;color:{TEXT2};line-height:1.55;}}

    /* Info cards */
    .ab-card{{background:{SURFACE};border:1px solid {BORDER};border-radius:11px;
        padding:.9rem 1rem;margin-bottom:.65rem;
        box-shadow:0 1px 3px rgba(0,0,0,{'0.08' if theme=='dark' else '0.03'});
        transition:box-shadow .15s;}}
    .ab-card:hover{{box-shadow:0 3px 10px rgba(0,0,0,{'0.12' if theme=='dark' else '0.06'});}}
    .ab-card-h{{font-size:.85rem;font-weight:800;color:{TEXT};margin:0 0 .4rem 0;
        display:flex;align-items:center;gap:6px;letter-spacing:-.01em;}}
    .ab-card-p{{font-size:.79rem;color:{TEXT2};line-height:1.75;margin:0;}}

    /* Feature list */
    .ab-feat{{display:flex;flex-direction:column;gap:.3rem;}}
    .ab-feat-row{{display:flex;align-items:flex-start;gap:.5rem;padding:.3rem 0;
        border-bottom:1px solid {BORDER};font-size:.78rem;color:{TEXT2};}}
    .ab-feat-row:last-child{{border-bottom:none;}}
    .ab-feat-icon{{flex-shrink:0;width:20px;text-align:center;}}
    .ab-feat-label{{font-weight:700;color:{TEXT};}}

    /* Tags */
    .ab-tag{{display:inline-block;background:{'#f5f3ff' if theme=='light' else '#1e1a42'};
        color:{ACCENT};padding:2px 8px;border-radius:6px;font-size:.65rem;font-weight:700;
        margin:0 3px 4px 0;border:1px solid {'#ddd6fe' if theme=='light' else '#3730a3'};}}

    /* Section label */
    .ab-section-label{{font-size:.6rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
        color:{TEXT3};margin:0 0 .6rem 0;}}
    </style>

    <div class="about-bg"></div>
    <div class="ab-page" style="position:relative;z-index:1;">

      <!-- ── HEADER ── -->
      <div class="ab-header">
        <h1 class="ab-title">LogIQ</h1>
        <p class="ab-subtitle">AI-powered Root Cause Analysis &nbsp;·&nbsp; What it is, how it works, and who it's for</p>
      </div>

      <!-- ── TAGLINE BANNER ── -->
      <div class="ab-banner">
        <p class="ab-banner-label">Resume Tagline</p>
        <p class="ab-banner-quote">"AI-powered DevOps RCA tool that detects root causes and suggests fixes in seconds — built with Google Gemini, Streamlit, and real-world log intelligence."</p>
        <div>
          <span class="ab-badge">🤖 Google Gemini 2.5 Flash</span>
          <span class="ab-badge">🐍 Python + Streamlit</span>
          <span class="ab-badge">☸️ DevOps / SRE Tooling</span>
          <span class="ab-badge">🔍 Root Cause Analysis</span>
        </div>
      </div>

      <!-- ── HOW IT WORKS ── -->
      <p class="ab-section-label">How it works</p>
      <div class="ab-steps" style="margin-bottom:1.1rem;">
        <div class="ab-step">
          <span class="ab-step-icon">📋</span>
          <div class="ab-step-num">STEP 1</div>
          <div class="ab-step-title">Input Logs</div>
          <div class="ab-step-desc">Paste any system log — Docker, K8s, app crashes, stack traces</div>
        </div>
        <div class="ab-step">
          <span class="ab-step-icon">🧠</span>
          <div class="ab-step-num">STEP 2</div>
          <div class="ab-step-title">AI Analyzes</div>
          <div class="ab-step-desc">Gemini detects patterns, identifies failure domain, scores severity</div>
        </div>
        <div class="ab-step">
          <span class="ab-step-icon">🎯</span>
          <div class="ab-step-num">STEP 3</div>
          <div class="ab-step-title">Get RCA + Fix</div>
          <div class="ab-step-desc">Root cause, plain-English explanation, step-by-step fix, prevention</div>
        </div>
      </div>

    </div>
    """, unsafe_allow_html=True)

    # ── TWO COLUMN SECTION ────────────────────────────────────────────
    d1, d2 = st.columns([5, 4], gap="medium")
    with d1:
        st.markdown(f"""
        <div style="padding:0 0 0 1.5rem;">
        <p class="ab-section-label">About</p>

        <div class="ab-card">
          <h3 class="ab-card-h">🚀 What is LogIQ?</h3>
          <p class="ab-card-p">An AI-powered Root Cause Analysis tool for developers, DevOps engineers, and SREs. Paste raw system logs — crash reports, stack traces, server errors — and instantly get <strong style="color:{TEXT};">what broke, why it broke, how to fix it, and how to prevent it</strong>.</p>
        </div>

        <div class="ab-card">
          <h3 class="ab-card-h">🧠 How AI Is Used</h3>
          <p class="ab-card-p">LogIQ sends your logs to <strong style="color:{TEXT};">Google Gemini 2.5 Flash</strong> with a carefully engineered prompt that forces structured output — Severity, Confidence, Root Cause, Explanation, Solution, and Prevention. No free-form text, always structured.</p>
        </div>

        <div class="ab-card">
          <h3 class="ab-card-h">👥 Who Is It For?</h3>
          <p class="ab-card-p">
            <strong style="color:{TEXT};">Developers</strong> — debug application crashes in seconds.<br>
            <strong style="color:{TEXT};">DevOps &amp; SREs</strong> — analyze server logs, K8s events, Docker errors.<br>
            <strong style="color:{TEXT};">Students</strong> — understand what error messages actually mean.<br>
            <strong style="color:{TEXT};">Anyone</strong> who has ever stared at a wall of red text.
          </p>
        </div>

        <div class="ab-card">
          <h3 class="ab-card-h">📋 How to Use</h3>
          <p class="ab-card-p">
            <strong style="color:{TEXT};">Step 1</strong> — Paste logs or upload a .log / .txt / .csv file.<br>
            <strong style="color:{TEXT};">Step 2</strong> — Click <em>Find Root Cause Now</em>. Results in ~5s.<br>
            <strong style="color:{TEXT};">Step 3</strong> — Read the cards. Download the report.<br>
            <strong style="color:{TEXT};">Step 4</strong> — Use the AI Assistant for follow-up questions.
          </p>
        </div>
        </div>
        """, unsafe_allow_html=True)

    with d2:
        st.markdown(f"""
        <div style="padding:0 1.5rem 0 0;">
        <p class="ab-section-label">Features &amp; Support</p>

        <div class="ab-card">
          <h3 class="ab-card-h">🗂️ Key Features</h3>
          <div class="ab-feat">
            <div class="ab-feat-row"><span class="ab-feat-icon">🔴</span><span><span class="ab-feat-label">Root Cause Analysis</span> — What actually failed</span></div>
            <div class="ab-feat-row"><span class="ab-feat-icon">📖</span><span><span class="ab-feat-label">Plain English</span> — No jargon, just clarity</span></div>
            <div class="ab-feat-row"><span class="ab-feat-icon">🛠️</span><span><span class="ab-feat-label">Step-by-Step Fix</span> — Actionable, copy-paste ready</span></div>
            <div class="ab-feat-row"><span class="ab-feat-icon">🛡️</span><span><span class="ab-feat-label">Prevention</span> — Stop it happening again</span></div>
            <div class="ab-feat-row"><span class="ab-feat-icon">📊</span><span><span class="ab-feat-label">Failure Timeline</span> — Visual incident breakdown</span></div>
            <div class="ab-feat-row"><span class="ab-feat-icon">🔧</span><span><span class="ab-feat-label">DevOps Context</span> — Docker, K8s, cloud-aware</span></div>
            <div class="ab-feat-row"><span class="ab-feat-icon">💬</span><span><span class="ab-feat-label">AI Assistant</span> — Context-aware follow-ups</span></div>
            <div class="ab-feat-row"><span class="ab-feat-icon">🎬</span><span><span class="ab-feat-label">Demo Mode</span> — Presentation-ready scenarios</span></div>
          </div>
        </div>

        <div class="ab-card">
          <h3 class="ab-card-h">💡 Supported Log Types</h3>
          <div style="margin-top:.3rem;">
            <span class="ab-tag">Python tracebacks</span><span class="ab-tag">Nginx/Apache</span>
            <span class="ab-tag">Docker/K8s</span><span class="ab-tag">Java stacktraces</span>
            <span class="ab-tag">PostgreSQL</span><span class="ab-tag">MySQL</span>
            <span class="ab-tag">Node.js</span><span class="ab-tag">Systemd</span>
            <span class="ab-tag">AWS CloudWatch</span><span class="ab-tag">GitHub Actions</span>
          </div>
        </div>

        <div class="ab-card" style="background:linear-gradient(135deg,{'#f5f3ff' if theme=='light' else '#1a1730'} 0%,{'#ede9fe' if theme=='light' else '#1e1a42'} 100%);border-color:{'#ddd6fe' if theme=='light' else '#3730a3'};">
          <h3 class="ab-card-h" style="color:{ACCENT};">⚡ Why LogIQ?</h3>
          <p class="ab-card-p">Traditional log analysis means reading thousands of lines, Googling error codes, and guessing. LogIQ cuts that to seconds — explains in plain English, shows a visual failure timeline, and tells you exactly what to do next.</p>
        </div>
        </div>
        """, unsafe_allow_html=True)