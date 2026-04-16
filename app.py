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
"""

import streamlit as st
import datetime
import time
import logging
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("logiq")

from rca_engine import analyze_logs

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
    "active_tab":   "analyzer",
    "theme":        "light",       # "light" | "dark" | "system"
    "rca_result":   None,
    "rca_parsed":   None,
    "rca_elapsed":  0.0,
    "rca_model":    "",
    "chat_history": [],
    "history":      [],
    "log_text":     "",
    "last_file":    "",
    "auto_analyze": False,
    "logs_dirty":   False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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
section[data-testid="stSidebar"]{{display:none!important;}}
::-webkit-scrollbar{{width:4px;height:4px;}}
::-webkit-scrollbar-thumb{{background:{BORDER};border-radius:4px;}}

/* ── FADE-IN animation ── */
@keyframes fadeUp{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}
.fade-up{{animation:fadeUp .35s ease both;}}
.fade-in{{animation:fadeIn .3s ease both;}}

/* ══ TOPBAR ══ */
.topbar{{
    background:{SURFACE};border-bottom:1px solid {BORDER};
    padding:0 1.75rem;height:52px;
    display:flex;align-items:center;
    position:sticky;top:0;z-index:999;
    box-shadow:0 1px 4px rgba(0,0,0,0.07);
}}
.tb-logo{{display:flex;align-items:center;gap:8px;flex-shrink:0;}}
.tb-mark{{
    width:30px;height:30px;border-radius:7px;
    background:linear-gradient(135deg,#4f46e5,#7c3aed);
    display:flex;align-items:center;justify-content:center;font-size:14px;
    box-shadow:0 2px 6px rgba(79,70,229,.35);
    transition:transform .2s;
}}
.tb-mark:hover{{transform:scale(1.07);}}
.tb-brand{{font-size:.98rem;font-weight:800;color:{TEXT};letter-spacing:-.02em;margin-right:2rem;}}
.tb-brand em{{color:{ACCENT};font-style:normal;}}
.tb-tabs{{display:flex;align-items:stretch;height:52px;flex:1;}}
.tb-tab{{
    display:flex;align-items:center;gap:5px;padding:0 1rem;
    font-size:.8rem;font-weight:500;color:{TEXT2};
    border-bottom:2.5px solid transparent;cursor:pointer;
    transition:color .15s,border-color .15s,background .15s;white-space:nowrap;
}}
.tb-tab:hover{{color:{ACCENT};background:{'#f5f3ff' if theme=='light' else '#1e1a42'};}}
.tb-tab.on{{color:{ACCENT};border-bottom-color:{ACCENT};font-weight:700;}}
.tb-right{{margin-left:auto;display:flex;align-items:center;gap:6px;}}
.theme-select{{
    background:{SURFACE2};border:1px solid {BORDER};color:{TEXT};
    border-radius:8px;padding:4px 10px;font-size:.72rem;font-weight:600;
    cursor:pointer;outline:none;transition:border-color .15s;
}}
.theme-select:hover{{border-color:{ACCENT};}}

/* hide duplicate streamlit tab button row completely */
div.tabrow{{display:none!important;}}

/* ══ HERO ══ */
.hero{{
    background:{HERO_BG};
    padding:2rem 2rem 3.5rem;position:relative;overflow:hidden;
}}
.hero::before{{
    content:'';position:absolute;inset:0;
    background:radial-gradient(ellipse 50% 40% at 80% 10%,rgba(167,139,250,.15) 0%,transparent 60%);
}}
.hero::after{{
    content:'';position:absolute;bottom:-1px;left:0;right:0;
    height:40px;background:{BG};clip-path:ellipse(55% 100% at 50% 100%);
}}
.hero-inner{{position:relative;z-index:1;max-width:560px;}}
.hero-pill{{
    display:inline-flex;align-items:center;gap:6px;
    background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);
    color:#c7d2fe;padding:3px 11px;border-radius:20px;
    font-size:.65rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;margin-bottom:.8rem;
}}
.ldot{{width:6px;height:6px;border-radius:50%;background:#86efac;animation:ld 2s ease-in-out infinite;}}
@keyframes ld{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:.3;transform:scale(.5);}}}}
.hero-h1{{font-size:2rem;font-weight:800;color:#fff;line-height:1.1;letter-spacing:-.03em;margin-bottom:.6rem;}}
.hero-h1 .hl{{color:#a5b4fc;}}
.hero-sub{{font-size:.88rem;color:rgba(199,210,254,.85);line-height:1.7;margin-bottom:1.6rem;}}
.hstats{{display:flex;gap:1.8rem;flex-wrap:wrap;}}
.hs{{display:flex;flex-direction:column;gap:2px;}}
.hs-n{{font-size:1.2rem;font-weight:800;color:#fff;line-height:1;}}
.hs-l{{font-size:.6rem;font-weight:600;color:#818cf8;text-transform:uppercase;letter-spacing:.08em;}}

/* ══ FEATURE STRIP ══ */
.fstrip{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:{STRIP_BR};border-bottom:1px solid {STRIP_BR};}}
.fcell{{background:{STRIP_BG};padding:.85rem 1.1rem;display:flex;align-items:flex-start;gap:9px;transition:background .15s;}}
.fcell:hover{{background:{'#f5f3ff' if theme=='light' else '#1a1d2e'};}}
.ficon{{width:30px;height:30px;border-radius:7px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:14px;}}
.fi-i{{background:#ede9fe;}}.fi-b{{background:#dbeafe;}}.fi-g{{background:#dcfce7;}}.fi-a{{background:#fef9c3;}}
.ftit{{font-size:.76rem;font-weight:700;color:{TEXT};margin-bottom:1px;}}
.fsub{{font-size:.68rem;color:{TEXT2};line-height:1.35;}}

/* ══ BODY ══ */
.body{{padding:1.4rem 1.75rem 3rem;max-width:1380px;margin:0 auto;}}

/* ══ MICRO LABEL ══ */
.mlbl{{font-size:.6rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:{TEXT3};margin-bottom:.4rem;}}

/* ══ INPUT CARD ══ */
.icard{{background:{SURFACE};border:1px solid {BORDER};border-radius:12px;overflow:hidden;}}
.ich{{padding:.8rem 1.1rem;border-bottom:1px solid {BORDER};display:flex;align-items:center;gap:7px;}}
.ich-dot{{width:7px;height:7px;border-radius:50%;background:{ACCENT};flex-shrink:0;}}
.ich-t{{font-size:.82rem;font-weight:700;color:{TEXT};flex:1;}}
.ich-badge{{font-size:.58rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:2px 7px;border-radius:5px;background:#f0f9ff;color:#0369a1;border:1px solid #bae6fd;}}
.icb{{padding:.9rem 1.1rem;}}

/* ══ FILE UPLOADER ══ */
[data-testid="stFileUploader"]{{
    background:{INPUT_BG};border:1.5px dashed {BORDER};border-radius:9px;
    padding:3px 8px;transition:border-color .18s;
}}
[data-testid="stFileUploader"]:hover{{border-color:{ACCENT};}}
[data-testid="stFileUploader"] section{{padding:.35rem 0!important;}}

/* ══ TEXTAREA ══ */
.stTextArea textarea{{
    background:{INPUT_BG}!important;border:1.5px solid {BORDER}!important;
    border-radius:9px!important;color:{TEXT}!important;
    font-family:'JetBrains Mono',monospace!important;font-size:.77rem!important;
    line-height:1.78!important;padding:11px 13px!important;
    transition:border-color .18s,box-shadow .18s!important;resize:vertical!important;
}}
.stTextArea textarea:focus{{
    border-color:{ACCENT}!important;box-shadow:0 0 0 3px rgba(79,70,229,.09)!important;
    background:{SURFACE}!important;outline:none!important;
}}
.stTextArea textarea::placeholder{{color:{TEXT3}!important;font-family:'Inter',sans-serif!important;}}
.stTextArea label{{display:none!important;}}

/* ══ BUTTONS ══ */
.stButton>button{{
    background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%)!important;
    color:#fff!important;border:none!important;border-radius:10px!important;
    padding:.62rem 1.3rem!important;font-family:'Inter',sans-serif!important;
    font-weight:700!important;font-size:.84rem!important;width:100%!important;
    box-shadow:0 2px 10px rgba(79,70,229,.22)!important;
    transition:all .2s!important;cursor:pointer!important;
}}
.stButton>button:hover{{transform:translateY(-1px)!important;box-shadow:0 4px 16px rgba(79,70,229,.32)!important;}}
.stButton>button:active{{transform:translateY(0)!important;}}
.ghost .stButton>button{{
    background:{SURFACE}!important;color:{TEXT2}!important;
    border:1px solid {BORDER}!important;box-shadow:none!important;font-weight:500!important;
}}
.ghost .stButton>button:hover{{background:{SURFACE2}!important;transform:none!important;box-shadow:none!important;color:{TEXT}!important;}}

/* ══ PRE-BADGES ══ */
.pbadge{{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:600;}}
.pb-e{{background:#fef2f2;color:#991b1b;border:1px solid #fecaca;}}
.pb-w{{background:#fefce8;color:#854d0e;border:1px solid #fde68a;}}
.pb-ok{{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;}}

/* ══ LOG VIEWER ══ */
.logview{{
    background:{LOGBG};border-radius:9px;padding:.75rem 1rem;
    font-family:'JetBrains Mono',monospace;font-size:.72rem;line-height:1.85;
    overflow-x:auto;overflow-y:auto;max-height:165px;border:1px solid #1e2d45;
}}
.lv-fa{{color:#fb7185;font-weight:600;}}.lv-er{{color:#f87171;}}
.lv-wn{{color:#fbbf24;}}.lv-in{{color:#60a5fa;}}
.lv-db{{color:#6b7280;}}.lv-ok{{color:#34d399;}}.lv-df{{color:#94a3b8;}}

/* ══ TIPS ══ */
.tips{{
    background:{SURFACE2};border-left:3px solid {ACCENT};
    border-radius:0 8px 8px 0;padding:.65rem .9rem;
}}
.tips-h{{font-size:.6rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:{ACCENT};margin-bottom:.3rem;}}
.tips ul{{margin:0;padding-left:.9rem;font-size:.72rem;color:{TEXT2};line-height:1.88;}}

/* ══ EMPTY ══ */
.empty{{
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    padding:2.5rem 1rem;text-align:center;
    border:1.5px dashed {BORDER};border-radius:12px;background:{EMPTY_BG};min-height:220px;
}}
.empty-ico{{font-size:1.9rem;margin-bottom:.55rem;}}
.empty-t{{font-size:.88rem;font-weight:700;color:{TEXT};margin-bottom:.25rem;}}
.empty-s{{font-size:.76rem;color:{TEXT2};line-height:1.6;}}
.empty-step{{
    display:flex;align-items:center;gap:8px;
    font-size:.76rem;color:{TEXT2};margin-top:.4rem;
}}
.step-num{{
    width:20px;height:20px;border-radius:50%;
    background:{ACCENT};color:#fff;
    display:flex;align-items:center;justify-content:center;
    font-size:.62rem;font-weight:800;flex-shrink:0;
}}

/* ══ SEVERITY ROW ══ */
.sevrow{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:.75rem;align-items:center;}}
.sp{{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:.69rem;font-weight:700;}}
.sp-hi{{background:#fef2f2;color:#991b1b;border:1px solid #fecaca;}}
.sp-md{{background:#fefce8;color:#854d0e;border:1px solid #fde68a;}}
.sp-lo{{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;}}
.sp-cf{{background:#f5f3ff;color:#4c1d95;border:1px solid #ddd6fe;}}
.sp-tm{{background:#f0f9ff;color:#0369a1;border:1px solid #bae6fd;font-size:.63rem;}}

/* ══ RESULT CARDS ══ */
.rc{{
    background:{RC_BG};border:1px solid {BORDER};border-left:3px solid;
    border-radius:0 11px 11px 0;padding:.85rem 1.1rem;
    transition:box-shadow .16s,transform .16s;
}}
.rc:hover{{box-shadow:0 3px 12px rgba(0,0,0,{'0.12' if theme=='dark' else '0.05'});transform:translateY(-1px);}}
.rclbl{{font-size:.58rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.38rem;display:flex;align-items:center;gap:4px;}}
.rclbl::before{{content:'';display:inline-block;width:5px;height:5px;border-radius:50%;}}
.rc-root{{border-left-color:#ef4444;}}.rc-root .rclbl{{color:#dc2626;}}.rc-root .rclbl::before{{background:#dc2626;}}
.rc-expl{{border-left-color:#3b82f6;}}.rc-expl .rclbl{{color:#2563eb;}}.rc-expl .rclbl::before{{background:#2563eb;}}
.rc-sol{{border-left-color:#10b981;}}.rc-sol .rclbl{{color:#059669;}}.rc-sol .rclbl::before{{background:#059669;}}
.rc-prev{{border-left-color:#8b5cf6;}}.rc-prev .rclbl{{color:#7c3aed;}}.rc-prev .rclbl::before{{background:#7c3aed;}}
.rcbody{{font-size:.82rem;color:{TEXT};line-height:1.75;}}
.rcbody ul{{margin:.3rem 0 0;padding-left:.95rem;}}
.rcbody li{{margin-bottom:.25rem;}}

/* ══ STALE BANNER ══ */
.stale{{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:.45rem .9rem;font-size:.75rem;font-weight:600;color:#92400e;margin-bottom:.6rem;}}

/* ══ RAW OUTPUT ══ */
.raw-wrap{{background:{CODE_BG};border-radius:9px;border:1px solid #1e2d45;padding:.75rem 1rem;margin-top:.65rem;}}
.raw-lbl{{font-size:.58rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#4b5563;margin-bottom:.4rem;}}
.raw-body{{font-family:'JetBrains Mono',monospace;font-size:.7rem;color:#9ca3af;line-height:1.78;overflow-x:auto;white-space:pre-wrap;max-height:180px;overflow-y:auto;}}

/* ══ SPINNER ══ */
.spin-wrap{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2rem 1rem;gap:.7rem;}}
.sring{{width:38px;height:38px;border:3px solid {BORDER};border-top-color:#4f46e5;border-right-color:#7c3aed;border-radius:50%;animation:sp .8s linear infinite;}}
@keyframes sp{{to{{transform:rotate(360deg);}}}}
.stxt{{font-size:.8rem;font-weight:600;color:{ACCENT};animation:bth 1.4s ease-in-out infinite;}}
@keyframes bth{{0%,100%{{opacity:.4;}}50%{{opacity:1;}}}}
.stSpinner{{display:none!important;}}

/* ══ DOWNLOAD ══ */
[data-testid="stDownloadButton"]>button{{
    background:{DL_BG}!important;color:{DL_COLOR}!important;
    border:1.5px solid {DL_BORDER}!important;border-radius:9px!important;
    font-weight:700!important;font-size:.78rem!important;
    box-shadow:none!important;padding:.5rem 1rem!important;
}}
[data-testid="stDownloadButton"]>button:hover{{background:{'#eff6ff' if theme=='light' else '#1e1a42'}!important;transform:none!important;}}

/* ══ CHAT ══ */
.chat-shell{{background:{SURFACE};border:1px solid {BORDER};border-radius:13px;overflow:hidden;}}
.chat-head{{
    background:linear-gradient(135deg,#1e1b4b 0%,#4338ca 100%);
    padding:.7rem 1.1rem;display:flex;align-items:center;gap:7px;
}}
.ch-title{{font-size:.84rem;font-weight:700;color:#fff;flex:1;}}
.ch-sub{{font-size:.64rem;color:rgba(199,210,254,.8);}}
.chat-msgs{{min-height:130px;max-height:280px;overflow-y:auto;padding:.85rem;background:{CHAT_BG};}}
.chat-nil{{display:flex;align-items:center;justify-content:center;min-height:110px;font-size:.76rem;color:{TEXT3};text-align:center;line-height:1.6;}}
.cmsg{{display:flex;gap:7px;margin-bottom:.7rem;animation:fadeUp .18s ease;}}
.cav{{width:25px;height:25px;border-radius:6px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;margin-top:1px;}}
.cav-u{{background:#dbeafe;color:#1d4ed8;}}.cav-a{{background:#ede9fe;color:#5b21b6;}}
.cbbl{{border-radius:10px;padding:.45rem .8rem;font-size:.8rem;line-height:1.65;flex:1;}}
.cbbl-u{{background:#dbeafe;color:#1e3a5f;border-bottom-left-radius:3px;}}
.cbbl-a{{background:{SURFACE};color:{TEXT};border:1px solid {BORDER};border-bottom-left-radius:3px;}}
.chat-ft{{padding:.7rem 1rem;border-top:1px solid {BORDER};background:{SURFACE};}}

.stTextInput input{{
    background:{INPUT_BG}!important;border:1.5px solid {BORDER}!important;
    border-radius:9px!important;color:{TEXT}!important;
    font-family:'Inter',sans-serif!important;font-size:.82rem!important;
    padding:8px 12px!important;transition:border-color .18s,box-shadow .18s!important;
}}
.stTextInput input:focus{{
    border-color:{ACCENT}!important;box-shadow:0 0 0 3px rgba(79,70,229,.09)!important;
    background:{SURFACE}!important;outline:none!important;
}}
.stTextInput input::placeholder{{color:{TEXT3}!important;}}
.stTextInput label{{display:none!important;}}

/* ══ HOWTO ══ */
.howto{{background:{SURFACE};border:1px solid {BORDER};border-radius:13px;padding:1.1rem;}}
.howto-h{{font-size:.8rem;font-weight:700;color:{TEXT};margin-bottom:.75rem;padding-bottom:.5rem;border-bottom:1px solid {BORDER};}}
.step{{display:flex;gap:8px;align-items:flex-start;margin-bottom:.7rem;}}
.stepn{{width:22px;height:22px;border-radius:6px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;}}
.stept{{font-size:.77rem;font-weight:700;color:{TEXT};margin-bottom:1px;}}
.steps{{font-size:.71rem;color:{TEXT2};line-height:1.4;}}
.trybox{{background:{SURFACE2};border-radius:8px;border:1px solid {BORDER};padding:.65rem .85rem;margin-top:.3rem;}}
.trylbl{{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:{ACCENT};margin-bottom:.3rem;}}
.tryitems{{font-size:.74rem;color:{TEXT2};line-height:1.85;}}

/* ══ EXPANDER ══ */
div[data-testid="stExpander"]{{
    background:{SURFACE}!important;border:1px solid {BORDER}!important;
    border-radius:11px!important;margin-bottom:.45rem!important;
}}
div[data-testid="stExpander"]:hover{{border-color:{ACCENT2}!important;}}
div[data-testid="stExpander"] summary{{color:{TEXT}!important;font-size:.84rem!important;font-weight:600!important;}}
div[data-testid="stExpander"] p, div[data-testid="stExpander"] li{{color:{TEXT}!important;}}

/* ══ PAGE HEADER ══ */
.ph{{padding:1.3rem 0 .9rem;}}
.ph-h{{font-size:1.25rem;font-weight:800;color:{TEXT};margin-bottom:.2rem;}}
.ph-s{{font-size:.81rem;color:{TEXT2};}}

/* ══ ABOUT CARDS ══ */
.acard{{background:{SURFACE};border:1px solid {BORDER};border-radius:11px;padding:1.1rem;margin-bottom:.75rem;transition:box-shadow .16s;}}
.acard:hover{{box-shadow:0 3px 12px rgba(0,0,0,{'0.15' if theme=='dark' else '0.06'});}}
.acard-h{{font-size:.88rem;font-weight:700;color:{TEXT};margin-bottom:.5rem;display:flex;align-items:center;gap:6px;}}
.acard-p{{font-size:.8rem;color:{TEXT};line-height:1.74;}}
.acode{{
    background:{CODE_BG};color:#94a3b8;font-family:'JetBrains Mono',monospace;font-size:.71rem;
    border-radius:7px;padding:.7rem .9rem;margin:.55rem 0;
    overflow-x:auto;white-space:pre;border:1px solid #1e2d45;line-height:1.78;
}}
.atag{{display:inline-block;background:#f5f3ff;color:#4c1d95;padding:2px 7px;border-radius:5px;font-size:.65rem;font-weight:700;margin-right:3px;margin-bottom:3px;}}

/* ══ HISTORY ENTRIES ══ */
.hist-entry{{
    background:{SURFACE};border:1px solid {BORDER};border-radius:11px;
    padding:1rem 1.1rem;margin-bottom:.55rem;transition:border-color .15s,box-shadow .15s;
    cursor:pointer;
}}
.hist-entry:hover{{border-color:{ACCENT2};box-shadow:0 2px 10px rgba(79,70,229,{'0.15' if theme=='dark' else '0.08'});}}
.hist-ts{{font-size:.68rem;color:{TEXT3};font-weight:500;}}
.hist-rc{{font-size:.83rem;font-weight:600;color:{HIST_TEXT};margin-top:2px;}}
.hist-sev{{font-size:.67rem;font-weight:700;}}

/* ══ ALERT / BANNER ══ */
.banner{{display:flex;align-items:center;gap:7px;padding:.5rem .9rem;border-radius:8px;font-size:.77rem;font-weight:600;margin-bottom:.55rem;}}
.b-ok{{background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;}}
.b-warn{{background:#fffbeb;border:1px solid #fde68a;color:#92400e;}}
.b-err{{background:#fef2f2;border:1px solid #fecaca;color:#991b1b;}}
.b-info{{background:#f0f9ff;border:1px solid #bae6fd;color:#0369a1;}}

/* ══ SECTION DIVIDER ══ */
.sdiv{{height:1px;background:{BORDER};margin:1.2rem 0;}}

/* Streamlit alert overrides */
.stAlert{{border-radius:9px!important;}}
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
    """Return True if the text looks like actual system logs."""
    patterns = [
        r'\[\s*(error|warn|info|debug|fatal|critical)\s*\]',
        r'\d{4}-\d{2}-\d{2}',          # date
        r'\d{2}:\d{2}:\d{2}',          # time
        r'(exception|traceback|stacktrace)',
        r'(connection refused|timeout|failed|crashed)',
        r'(error code|exit code|errno)',
        r'at\s+\w+\.\w+\(',            # Java stack frame
        r'file ".+", line \d+',        # Python traceback
        r'(nginx|apache|docker|kubernetes|postgresql|mysql)',
        r'(http|https)://\S+',
        r'\b(500|404|403|401|503)\b',
    ]
    text_low = text.lower()
    score = sum(1 for p in patterns if re.search(p, text_low))
    # Also allow if text has ERROR/WARN/FATAL keywords
    if any(kw in text_low for kw in ["error", "warn", "fatal", "exception", "traceback", "crash", "fail"]):
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
        "ts":       datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "root":     parsed.get("Root Cause","—"),
        "severity": parsed.get("Severity","—"),
        "raw":      raw, "logs": logs, "parsed": parsed, "elapsed": elapsed,
    }
    st.session_state.history.insert(0, entry)
    if len(st.session_state.history) > 20:
        st.session_state.history = st.session_state.history[:20]

def build_report(logs, parsed, raw, elapsed):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (f"LogIQ — AI Root Cause Analysis Report\n"
            f"Generated  : {ts}\n"
            f"Elapsed    : {elapsed:.2f}s\n"
            f"{'='*56}\n\n"
            f"SEVERITY   : {parsed.get('Severity','—')}\n"
            f"CONFIDENCE : {parsed.get('Confidence','—')}\n\n"
            f"ROOT CAUSE\n{'-'*40}\n{parsed.get('Root Cause','—')}\n\n"
            f"EXPLANATION\n{'-'*40}\n{parsed.get('Explanation','—')}\n\n"
            f"SOLUTION\n{'-'*40}\n{parsed.get('Solution','—')}\n\n"
            f"PREVENTION\n{'-'*40}\n{parsed.get('Prevention','—')}\n\n"
            f"{'='*56}\nORIGINAL LOGS\n{'-'*40}\n{logs}\n\n"
            f"{'='*56}\nRAW AI OUTPUT\n{'-'*40}\n{raw}\n")

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
    ]
    return any(k in q.lower() for k in kws)

def render_results(p: dict, elapsed: float = 0.0):
    st.markdown(sev_html(p.get("Severity","Unknown"), p.get("Confidence",""), elapsed), unsafe_allow_html=True)
    st.markdown(
        f'<div class="rc rc-root fade-up" style="margin-bottom:.6rem;">'
        f'<div class="rclbl">Root Cause</div>'
        f'<div class="rcbody">{p.get("Root Cause","—")}</div></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="rc rc-expl fade-up" style="margin-bottom:.6rem;animation-delay:.05s">'
        f'<div class="rclbl">Explanation</div>'
        f'<div class="rcbody">{p.get("Explanation","—")}</div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="small")
    with c1:
        st.markdown(
            f'<div class="rc rc-sol fade-up" style="animation-delay:.1s">'
            f'<div class="rclbl">Solution</div>'
            f'<div class="rcbody">{bullets_html(p.get("Solution",""))}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(
            f'<div class="rc rc-prev fade-up" style="animation-delay:.15s">'
            f'<div class="rclbl">Prevention</div>'
            f'<div class="rcbody">{bullets_html(p.get("Prevention",""))}</div></div>', unsafe_allow_html=True)

MODEL = "Gemini 2.5 Flash"

def run_analysis(text: str):
    try:
        result = analyze_logs(text)
        if result and not result.startswith("❌"):
            return result, ""
        return "", result or "Unknown error"
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return "", str(e)


# ══════════════════════════════════════════════════════════════════════
#  TOPBAR  — logo left, visual tab labels, theme selector right
# ══════════════════════════════════════════════════════════════════════
t = st.session_state.active_tab

st.markdown(f"""
<div class="topbar">
  <div class="tb-logo">
    <div class="tb-mark">🔍</div>
    <span class="tb-brand">Log<em>IQ</em></span>
  </div>
  <div class="tb-tabs">
    <span class="tb-tab {'on' if t=='analyzer' else ''}">🔍 Analyzer</span>
    <span class="tb-tab {'on' if t=='history' else ''}">📂 History</span>
    <span class="tb-tab {'on' if t=='about' else ''}">💡 About LogIQ</span>
  </div>
  <div class="tb-right">
  </div>
</div>
""", unsafe_allow_html=True)

# Functional tab buttons (styled flat, visually hidden by tabrow CSS above)
# We render them in a hidden div — but we need them visible as the real click targets.
# Solution: render them below the visual topbar, styled to look like the topbar tabs.
st.markdown("""
<style>
div.real-tabs{
    background:var(--surface,#fff);
    display:flex;align-items:stretch;
    border-bottom:1px solid #e5e7eb;
    padding:0;gap:0;
}
div.real-tabs .stButton>button{
    background:transparent!important;color:#6b7280!important;
    border:none!important;border-radius:0!important;box-shadow:none!important;
    border-bottom:2.5px solid transparent!important;
    padding:.68rem 1.1rem!important;font-weight:500!important;
    font-size:.79rem!important;width:auto!important;min-width:85px!important;
    transition:all .15s!important;letter-spacing:0!important;
}
div.real-tabs .stButton>button:hover{
    color:#4f46e5!important;background:#f5f3ff!important;
    transform:none!important;box-shadow:none!important;
    border-bottom:2.5px solid #a5b4fc!important;
}
div.real-tabs .stButton>button[kind="primary"]{
    color:#4f46e5!important;border-bottom:2.5px solid #4f46e5!important;
    background:transparent!important;box-shadow:none!important;font-weight:700!important;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="real-tabs">', unsafe_allow_html=True)
_r1, _r2, _r3, _rsp, _rtheme = st.columns([1, 1, 1.3, 6, 1.2])
with _r1:
    if st.button("🔍 Analyzer", key="tb1", type="primary" if t=="analyzer" else "secondary", use_container_width=True):
        st.session_state.active_tab = "analyzer"; st.rerun()
with _r2:
    if st.button("📂 History",  key="tb2", type="primary" if t=="history"  else "secondary", use_container_width=True):
        st.session_state.active_tab = "history";  st.rerun()
with _r3:
    if st.button("💡 About LogIQ", key="tb3", type="primary" if t=="about" else "secondary", use_container_width=True):
        st.session_state.active_tab = "about";    st.rerun()
with _rtheme:
    theme_choice = st.selectbox(
        "Theme", ["🌞 Light","🌙 Dark","💻 System"],
        index=["light","dark","system"].index(st.session_state.theme),
        key="theme_sel", label_visibility="collapsed",
    )
    new_theme = {"🌞 Light":"light","🌙 Dark":"dark","💻 System":"light"}.get(theme_choice,"light")
    if new_theme != st.session_state.theme:
        st.session_state.theme = new_theme; st.rerun()
st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  ██  ANALYZER
# ══════════════════════════════════════════════════════════════════════════
if st.session_state.active_tab == "analyzer":

    # HERO
    st.markdown("""
    <div class="hero fade-in">
      <div class="hero-inner">
        <div class="hero-pill"><span class="ldot"></span>Live · AI Root Cause Analysis</div>
        <h1 class="hero-h1">Stop Guessing.<br><span class="hl">Find the Root Cause</span> in Seconds.</h1>
        <p class="hero-sub">Paste any system log — LogIQ's AI pinpoints exactly what failed, explains it clearly, and gives you a step-by-step fix.</p>
        <div class="hstats">
          <div class="hs"><span class="hs-n">~5s</span><span class="hs-l">Analysis</span></div>
          <div class="hs"><span class="hs-n">6</span><span class="hs-l">Output Fields</span></div>
          <div class="hs"><span class="hs-n">AI</span><span class="hs-l">Gemini</span></div>
          <div class="hs"><span class="hs-n">∞</span><span class="hs-l">Log Formats</span></div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # FEATURE STRIP
    st.markdown(f"""
    <div class="fstrip">
      <div class="fcell"><div class="ficon fi-i">🧠</div><div><p class="ftit">Root Cause Detection</p><p class="fsub">Pinpoints exact failure</p></div></div>
      <div class="fcell"><div class="ficon fi-b">📖</div><div><p class="ftit">Plain English</p><p class="fsub">Zero jargon explanation</p></div></div>
      <div class="fcell"><div class="ficon fi-g">🛠️</div><div><p class="ftit">Step-by-Step Fix</p><p class="fsub">Actionable solution</p></div></div>
      <div class="fcell"><div class="ficon fi-a">🛡️</div><div><p class="ftit">Prevention</p><p class="fsub">Stop recurrence</p></div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="body">', unsafe_allow_html=True)
    left, right = st.columns([1, 1.5], gap="large")

    # ── LEFT: INPUT ──────────────────────────────────────────────────
    with left:
        # Input card header
        st.markdown(f'<div class="icard"><div class="ich"><div class="ich-dot"></div><span class="ich-t">Paste or Upload Logs</span><span class="ich-badge">Any format</span></div><div class="icb">', unsafe_allow_html=True)

        # File uploader
        uploaded = st.file_uploader("Upload", type=["log","txt","csv"], label_visibility="collapsed", key="uploader")

        # Process new file immediately
        if uploaded and uploaded.name != st.session_state.last_file:
            try:
                content = uploaded.read().decode("utf-8", errors="ignore")
                if not content.strip():
                    st.markdown('<div class="banner b-err">⚠️ Uploaded file is empty.</div>', unsafe_allow_html=True)
                else:
                    if len(content) > 500_000:
                        content = content[:500_000]
                        st.markdown('<div class="banner b-warn">⚠️ File truncated to 500 KB.</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="banner b-ok">✅ Loaded <strong>{uploaded.name}</strong> · {len(content):,} chars</div>', unsafe_allow_html=True)
                    st.session_state.log_text    = content
                    st.session_state.last_file   = uploaded.name
                    st.session_state.auto_analyze = True
                    st.session_state.logs_dirty  = True
            except Exception as e:
                st.markdown(f'<div class="banner b-err">❌ Could not read file: {e}</div>', unsafe_allow_html=True)

        # Textarea
        prev = st.session_state.log_text
        logs = st.text_area(
            label="logs", value=st.session_state.log_text, height=200,
            key="logs_ta", label_visibility="collapsed",
            placeholder=(
                "Paste your system logs here…\n\n"
                "[ERROR] 2024-01-15 09:32:11 - Connection refused: db-host:5432\n"
                "[ERROR] 2024-01-15 09:32:12 - Max retries exceeded\n"
                "[FATAL] Application crashed with exit code 1"
            ),
        )
        if logs != prev:
            st.session_state.log_text  = logs
            st.session_state.logs_dirty = True

        st.markdown('</div></div>', unsafe_allow_html=True)

        # Pre-processing badges
        if logs and logs.strip():
            _, stats = preprocess_logs(logs)
            parts = []
            if stats["fatals"]   > 0: parts.append(f'<span class="pbadge pb-e">💀 {stats["fatals"]} FATAL</span>')
            if stats["errors"]   > 0: parts.append(f'<span class="pbadge pb-e">❌ {stats["errors"]} ERROR</span>')
            if stats["warnings"] > 0: parts.append(f'<span class="pbadge pb-w">⚠️ {stats["warnings"]} WARN</span>')
            if stats["dups"]     > 0: parts.append(f'<span class="pbadge pb-ok">🗑 {stats["dups"]} dupes removed</span>')
            if parts:
                st.markdown('<div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:.5rem;">' + "".join(parts) + '</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:.55rem'></div>", unsafe_allow_html=True)
        analyze_btn = st.button("🔍  Analyze Logs  →", key="abtn", use_container_width=True)

        # Log preview
        if logs and logs.strip():
            st.markdown(f'<p class="mlbl" style="margin-top:.85rem;">Log Preview</p><div class="logview">{highlight_logs(logs)}</div>', unsafe_allow_html=True)

        # Tips
        st.markdown("""
        <div class="tips" style="margin-top:.7rem;">
          <p class="tips-h">💡 Tips</p>
          <ul>
            <li>Include log levels (ERROR, WARN, FATAL)</li>
            <li>Paste full stack traces — don't truncate</li>
            <li>Add surrounding context lines</li>
            <li>Mention service name or environment</li>
          </ul>
        </div>
        """, unsafe_allow_html=True)

    # ── RIGHT: RESULTS ───────────────────────────────────────────────
    with right:
        st.markdown('<p class="mlbl">Analysis Results</p>', unsafe_allow_html=True)
        result_ph = st.empty()

        trigger = analyze_btn or st.session_state.auto_analyze
        if st.session_state.auto_analyze:
            st.session_state.auto_analyze = False

        if trigger:
            if not logs or not logs.strip():
                with result_ph.container():
                    st.markdown('<div class="banner b-err">⚠️ Please paste or upload some logs first.</div>', unsafe_allow_html=True)
            elif not looks_like_logs(logs):
                # Input doesn't look like actual logs
                with result_ph.container():
                    st.markdown(f"""
                    <div class="empty fade-in">
                      <div class="empty-ico">🚫</div>
                      <p class="empty-t">Input doesn't look like system logs</p>
                      <p class="empty-s" style="max-width:320px;">
                        LogIQ analyzes technical log files — not general text.<br><br>
                        Please paste actual system logs containing error messages,
                        stack traces, or log levels like ERROR, WARN, or FATAL.
                      </p>
                    </div>
                    """, unsafe_allow_html=True)
                    logger.info("Non-log input rejected at analysis stage.")
            else:
                # Valid logs — run analysis
                st.session_state.logs_dirty = False
                with result_ph.container():
                    st.markdown("""
                    <div class="spin-wrap">
                      <div class="sring"></div>
                      <div class="stxt">Analyzing your logs…</div>
                    </div>""", unsafe_allow_html=True)

                cleaned, _ = preprocess_logs(logs)
                t0 = time.perf_counter()
                raw, err = run_analysis(cleaned)
                elapsed = time.perf_counter() - t0

                if err:
                    result_ph.error(f"❌ Analysis failed: {err}")
                else:
                    parsed = parse_result(raw)
                    st.session_state.rca_result  = raw
                    st.session_state.rca_parsed  = parsed
                    st.session_state.rca_elapsed = elapsed
                    save_history(logs, parsed, raw, elapsed)
                    result_ph.empty()
                    st.rerun()

        # Show results
        if st.session_state.rca_parsed and not trigger:
            with result_ph.container():
                p = st.session_state.rca_parsed

                if st.session_state.logs_dirty:
                    st.markdown('<div class="stale">⚠️ Logs changed — re-analyze to refresh results.</div>', unsafe_allow_html=True)

                render_results(p, st.session_state.rca_elapsed)

                # Raw output — visible
                raw_text = st.session_state.rca_result or ""
                st.markdown(
                    f'<div class="raw-wrap fade-in">'
                    f'<div class="raw-lbl">Raw AI Output</div>'
                    f'<div class="raw-body">{raw_text}</div>'
                    f'</div>', unsafe_allow_html=True)

                st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
                dt = datetime.datetime.now().strftime("%Y-%m-%d")
                st.download_button(
                    "⬇️  Download Report (.txt)",
                    data=build_report(logs, p, raw_text, st.session_state.rca_elapsed),
                    file_name=f"logiq_report_{dt}.txt",
                    mime="text/plain", use_container_width=True,
                )
        elif not trigger and not st.session_state.rca_parsed:
            with result_ph.container():
                st.markdown(f"""
                <div class="empty fade-in">
                  <div class="empty-ico">🔬</div>
                  <p class="empty-t">Ready to analyze</p>
                  <div class="empty-step"><div class="step-num">1</div><span>Paste logs or upload a file on the left</span></div>
                  <div class="empty-step"><div class="step-num">2</div><span>Click <strong>Analyze Logs</strong></span></div>
                  <div class="empty-step"><div class="step-num">3</div><span>Get root cause, fix &amp; prevention</span></div>
                </div>
                """, unsafe_allow_html=True)

    # ── CHAT + HOWTO ─────────────────────────────────────────────────
    st.markdown('<div class="sdiv"></div>', unsafe_allow_html=True)

    chat_col, info_col = st.columns([2, 1], gap="large")

    with chat_col:
        st.markdown('<p class="mlbl">AI Follow-up Assistant</p>', unsafe_allow_html=True)
        st.markdown("""
        <div class="chat-shell">
          <div class="chat-head">
            <span style="font-size:13px;">✦</span>
            <span class="ch-title">Ask About This Error</span>
            <span class="ch-sub">Log &amp; error questions only · one answer</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.chat_history:
            msgs = "".join(
                f'<div class="cmsg"><div class="cav cav-u">U</div><div class="cbbl cbbl-u">{m}</div></div>'
                if r == "You" else
                f'<div class="cmsg"><div class="cav cav-a">✦</div><div class="cbbl cbbl-a">{m}</div></div>'
                for r, m in st.session_state.chat_history
            )
            st.markdown(f'<div class="chat-msgs">{msgs}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-msgs"><div class="chat-nil">Analyze some logs, then ask follow-up questions here.<br><span style="color:#818cf8;font-size:.68rem;display:block;margin-top:4px;">Only error &amp; debugging questions — one clear answer.</span></div></div>', unsafe_allow_html=True)

        st.markdown('<div class="chat-ft">', unsafe_allow_html=True)
        user_q = st.text_input(label="cq", key="chat_q", label_visibility="collapsed",
                               placeholder="e.g. How do I fix error 404 in VS Code? Why did this crash?")
        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.chat_history:
            _, cc = st.columns([6, 1])
            with cc:
                st.markdown('<div class="ghost">', unsafe_allow_html=True)
                if st.button("Clear", key="clrchat", use_container_width=True):
                    st.session_state.chat_history = []; st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        if user_q and user_q.strip():
            q = user_q.strip()
            if not is_log_related(q):
                st.session_state.chat_history.append(("You", q))
                st.session_state.chat_history.append((
                    "AI",
                    "⚠️ I only help with log analysis, error debugging, and system issues. "
                    "Please ask something related to your logs or the error you're investigating."
                ))
                logger.info("Off-topic chat rejected.")
                st.rerun()
            else:
                st.session_state.chat_history.append(("You", q))

                # Build a context-aware prompt that forces ONE concise answer
                log_ctx = f"\nContext (analyzed logs):\n{logs[:800]}\n" if (logs and logs.strip()) else ""
                prompt = (
                    f"You are a DevOps/SRE expert answering ONE question about a specific error or log issue.\n"
                    f"{log_ctx}\n"
                    f"Question: {q}\n\n"
                    f"IMPORTANT RULES:\n"
                    f"- Give exactly ONE clear, direct answer\n"
                    f"- Do NOT repeat the question\n"
                    f"- Do NOT give multiple variations or confidence levels\n"
                    f"- Be concise and practical (3-8 sentences or bullet points)\n"
                    f"- Focus only on solving the specific issue asked\n"
                )

                spin_ph = st.empty()
                spin_ph.markdown('<div class="spin-wrap" style="padding:.8rem"><div class="sring" style="width:30px;height:30px;border-width:2.5px"></div><div class="stxt" style="font-size:.74rem">Thinking…</div></div>', unsafe_allow_html=True)
                try:
                    resp = analyze_logs(prompt)
                    if not resp or resp.startswith("❌"):
                        resp = "❌ Could not generate a response. Please try again."
                except Exception as e:
                    resp = f"❌ Error: {e}"
                    logger.error(f"Chat error: {e}")
                spin_ph.empty()
                st.session_state.chat_history.append(("AI", resp))
                st.rerun()

    with info_col:
        st.markdown('<p class="mlbl">Assistant Guide</p>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="howto">
          <p class="howto-h">How to use the Assistant</p>
          <div class="step">
            <div class="stepn" style="background:#ede9fe;color:#5b21b6;">1</div>
            <div><p class="stept">Analyze first</p><p class="steps">Run log analysis so AI has full context</p></div>
          </div>
          <div class="step">
            <div class="stepn" style="background:#dbeafe;color:#1d4ed8;">2</div>
            <div><p class="stept">Ask follow-ups</p><p class="steps">Dive deeper into the analysis result</p></div>
          </div>
          <div class="step">
            <div class="stepn" style="background:#dcfce7;color:#166534;">3</div>
            <div><p class="stept">Get one clear answer</p><p class="steps">No multiple options — one direct solution</p></div>
          </div>
          <div class="trybox">
            <p class="trylbl">Try asking</p>
            <p class="tryitems">
              • "How do I fix error 404 in VS Code?"<br>
              • "Why did the DB connection fail?"<br>
              • "Give me the bash command to fix this"<br>
              • "Is this a known security issue?"
            </p>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # body


# ══════════════════════════════════════════════════════════════════════════
#  ██  HISTORY
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "history":
    st.markdown('<div class="body">', unsafe_allow_html=True)
    st.markdown('<div class="ph"><h2 class="ph-h">Analysis History</h2><p class="ph-s">Last 20 analyses — stored for this session</p></div>', unsafe_allow_html=True)

    if not st.session_state.history:
        st.markdown(f"""
        <div class="empty" style="margin-top:.25rem;">
          <div class="empty-ico">📂</div>
          <p class="empty-t">No history yet</p>
          <p class="empty-s">Run your first analysis in the Analyzer tab</p>
        </div>""", unsafe_allow_html=True)
    else:
        h1, h2 = st.columns([8, 1])
        with h2:
            st.markdown('<div class="ghost">', unsafe_allow_html=True)
            if st.button("🗑 Clear All", key="clrhist", use_container_width=True):
                st.session_state.history = []; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        for i, e in enumerate(st.session_state.history):
            sev = e.get("severity","").lower()
            dot  = "🔴" if "high" in sev else ("🟡" if "medium" in sev else "🟢")
            sev_color = "#dc2626" if "high" in sev else ("#d97706" if "medium" in sev else "#16a34a")
            rc   = (e["root"][:72]+"…") if len(e["root"])>72 else e["root"]
            # Use expander for each entry so full content is visible
            with st.expander(f"{dot}  [{e['ts']}]  {rc}", expanded=False):
                p = e.get("parsed",{})
                # Severity + time row
                st.markdown(sev_html(e.get("severity","—"), p.get("Confidence",""), e.get("elapsed",0)), unsafe_allow_html=True)
                # All 4 result cards
                render_results(p, e.get("elapsed",0))
                # Raw output
                if e.get("raw"):
                    st.markdown(
                        f'<div class="raw-wrap" style="margin-top:.55rem;">'
                        f'<div class="raw-lbl">Raw AI Output</div>'
                        f'<div class="raw-body">{e["raw"]}</div>'
                        f'</div>', unsafe_allow_html=True)
                st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
                dt = e["ts"].replace(" ","_").replace(":","-")
                st.download_button(
                    "⬇️  Download Report",
                    data=build_report(e["logs"], p, e.get("raw",""), e.get("elapsed",0)),
                    file_name=f"logiq_report_{dt}.txt",
                    mime="text/plain", use_container_width=True, key=f"dl_{i}",
                )

    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  ██  ABOUT LOGIQ  (replaces old Docs tab)
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "about":
    st.markdown('<div class="body">', unsafe_allow_html=True)
    st.markdown('<div class="ph"><h2 class="ph-h">About LogIQ</h2><p class="ph-s">What it does, how it works, and why it was built</p></div>', unsafe_allow_html=True)

    d1, d2 = st.columns([3, 2], gap="large")

    with d1:
        st.markdown(f"""
        <div class="acard fade-up">
          <h3 class="acard-h">🚀 What is LogIQ?</h3>
          <p class="acard-p">
            LogIQ is an AI-powered Root Cause Analysis tool built for developers, DevOps engineers,
            and SREs. You paste raw system logs — crash reports, stack traces, server errors — and
            it instantly tells you <strong>what broke, why it broke, how to fix it,
            and how to prevent it</strong>. No more spending hours digging through logs manually.
          </p>
        </div>

        <div class="acard fade-up" style="animation-delay:.05s">
          <h3 class="acard-h">🧠 How the AI Works</h3>
          <p class="acard-p">
            LogIQ uses <strong>Google Gemini 2.5 Flash</strong> via the official Python SDK.
            A carefully engineered prompt in <code style="background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:.76rem;">prompts.py</code>
            enforces a strict 6-section output schema — Severity, Confidence, Root Cause,
            Explanation, Solution, Prevention — so the parser always receives consistent,
            structured output.
          </p>
          <p class="acard-p" style="margin-top:.5rem;">
            Before every API call, a preprocessing layer deduplicates lines, removes empty
            lines, and detects error patterns — reducing token usage and improving quality.
          </p>
        </div>

        <div class="acard fade-up" style="animation-delay:.1s">
          <h3 class="acard-h">🏗️ System Architecture</h3>
          <div class="acode">User Input (logs / file upload)
    ↓
Preprocessing       ← deduplicate, clean, detect patterns
    ↓
Input Validation    ← reject non-log content early
    ↓
Prompt Builder      ← prompts.py: inject logs into template
    ↓
Gemini API Call     ← rca_engine.py: google.generativeai
    ↓
Output Parser       ← parse_result() → 6 structured fields
    ↓
UI Renderer         ← Severity · Root Cause · Fix · Prevention
    ↓
Session History     ← stored per session, downloadable as .txt</div>
        </div>

        <div class="acard fade-up" style="animation-delay:.15s">
          <h3 class="acard-h">📋 How to Use LogIQ</h3>
          <p class="acard-p"><strong>Step 1</strong> — Paste raw logs into the input box, or upload a .log / .txt / .csv file. Files are analyzed automatically on upload.</p>
          <p class="acard-p" style="margin-top:.4rem;"><strong>Step 2</strong> — Click <strong>Analyze Logs</strong>. The AI returns a structured analysis in ~5 seconds.</p>
          <p class="acard-p" style="margin-top:.4rem;"><strong>Step 3</strong> — Read the Root Cause, Explanation, Solution, and Prevention cards. Download the full report as .txt.</p>
          <p class="acard-p" style="margin-top:.4rem;"><strong>Step 4</strong> — Use the AI Assistant for follow-up questions about the specific error. Ask for bash commands, configs, or deeper explanations.</p>
        </div>
        """, unsafe_allow_html=True)

    with d2:
        st.markdown(f"""
        <div class="acard fade-up">
          <h3 class="acard-h">🗂️ Output Format</h3>
          <p class="acard-p">Every analysis returns exactly 6 structured fields:</p>
          <div class="acode">Severity    : High / Medium / Low
Confidence  : 0–100%
Root Cause  : One-line summary
Explanation : Plain-English description
Solution    : Bullet-point fix steps
Prevention  : Best practices to prevent</div>
        </div>

        <div class="acard fade-up" style="animation-delay:.05s">
          <h3 class="acard-h">🏗️ Project Files</h3>
          <div class="acode">logiq/
├── app.py          ← Streamlit UI
├── rca_engine.py   ← Gemini AI logic
├── prompts.py      ← Prompt templates
├── utils.py        ← Log cleaning
├── .env            ← API key (never commit)
├── .gitignore      ← Excludes .env
└── requirements.txt</div>
        </div>

        <div class="acard fade-up" style="animation-delay:.1s">
          <h3 class="acard-h">🔑 API Key Setup</h3>
          <p class="acard-p">Create a <code style="background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:.76rem;">.env</code> file:</p>
          <div class="acode">GEMINI_API_KEY=your_key_here</div>
          <p class="acard-p">Loaded via <code style="background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:.76rem;">python-dotenv</code>. Never hardcoded. Always in <code style="background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:.76rem;">.gitignore</code>.</p>
        </div>

        <div class="acard fade-up" style="animation-delay:.15s">
          <h3 class="acard-h">💡 Supported Log Types</h3>
          <div style="margin-top:.4rem;line-height:1.9;">
            <span class="atag">Python tracebacks</span><span class="atag">Nginx / Apache</span>
            <span class="atag">Docker / K8s</span><span class="atag">Java stacktraces</span>
            <span class="atag">PostgreSQL</span><span class="atag">MySQL</span>
            <span class="atag">Node.js</span><span class="atag">Systemd</span>
            <span class="atag">AWS CloudWatch</span><span class="atag">GitHub Actions</span>
            <span class="atag">VS Code errors</span><span class="atag">Android Studio</span>
          </div>
        </div>

        <div class="acard fade-up" style="animation-delay:.2s">
          <h3 class="acard-h">🛡️ Safety & Scope</h3>
          <p class="acard-p">
            LogIQ rejects non-log input (random text, general questions) before sending
            to the AI — saving tokens and giving instant feedback. The chat assistant
            only answers log/error-related questions and returns one direct answer per
            question — no repeated variations.
          </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)