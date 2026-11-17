"""Design system: CSS, SVG icons and small HTML components (all user text is escaped)."""
from __future__ import annotations

from html import escape

import streamlit as st

from core.rubric import DIMENSIONS, LABELS

CSS = """
:root{--bg:#0B1020;--s1:#121A33;--s2:#182244;--line:#26315A;--tx:#E8ECFF;--mu:#8B97C7;--pu:#7C5CFF;--bl:#3B82F6;--cy:#22D3EE;--grad:linear-gradient(135deg,#7C5CFF 0%,#3B82F6 100%);}
html,body,[class*="css"],.stApp{font-family:Arial,system-ui,sans-serif;color:var(--tx);}
.stApp{background:linear-gradient(135deg,#0B1020 0%,#111936 55%,#0B1020 100%);}
#MainMenu,footer,header[data-testid="stHeader"]{visibility:hidden;height:0}
.block-container{padding:2rem 2.4rem 4rem;max-width:1180px}
h1,h2,h3,h4{color:var(--tx);letter-spacing:-.02em}
a{color:var(--cy)}
section[data-testid="stSidebar"]{background:#0A0F1E;border-right:1px solid var(--line)}
section[data-testid="stSidebar"] .block-container{padding:1.4rem 1rem}
section[data-testid="stSidebar"] .stButton>button{justify-content:flex-start;background:transparent;border:1px solid transparent;color:var(--mu);font-weight:600;border-radius:10px;padding:.55rem .8rem;box-shadow:none;transition:background .15s,color .15s}
section[data-testid="stSidebar"] .stButton>button:hover{background:var(--s1);color:var(--tx);border-color:var(--line)}
section[data-testid="stSidebar"] .stButton>button[kind="primary"]{background:linear-gradient(135deg,rgba(124,92,255,.28),rgba(59,130,246,.18));color:#fff;border:1px solid rgba(124,92,255,.55)}
.brand{display:flex;align-items:center;gap:.6rem;font-weight:700;font-size:1.15rem;margin:.1rem 0 1.2rem}
.brand .logo{width:32px;height:32px;border-radius:9px;background:var(--grad);display:grid;place-items:center;box-shadow:0 6px 18px rgba(124,92,255,.35)}
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{border-radius:11px;font-weight:700;border:1px solid var(--line);background:var(--s1);color:var(--tx);padding:.55rem 1.1rem;transition:transform .15s,box-shadow .15s,border-color .15s}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--pu);transform:translateY(-1px);color:#fff}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"],.stFormSubmitButton>button{background:var(--grad);border:0;color:#fff;box-shadow:0 8px 22px rgba(80,90,255,.25)}
.stTextInput input,.stTextArea textarea,.stNumberInput input,div[data-baseweb="select"]>div{background:var(--s1)!important;border:1px solid var(--line)!important;border-radius:11px!important;color:var(--tx)!important}
.stTextArea textarea{line-height:1.55;font-size:.98rem}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:var(--pu)!important;box-shadow:0 0 0 3px rgba(124,92,255,.2)!important}
label,.stMarkdown p{color:inherit}
div[data-testid="stWidgetLabel"] p{color:var(--mu);font-weight:600;font-size:.86rem}
.stTabs [data-baseweb="tab-list"]{gap:.3rem;border-bottom:1px solid var(--line)}
.stTabs [data-baseweb="tab"]{background:transparent;color:var(--mu);font-weight:600;border-radius:9px 9px 0 0;padding:.5rem 1rem}
.stTabs [aria-selected="true"]{color:#fff!important}
.stTabs [data-baseweb="tab-highlight"]{background:var(--grad);height:3px}
div[data-testid="stExpander"]{background:var(--s1);border:1px solid var(--line);border-radius:14px}
div[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:12px;overflow:hidden}
.card{background:linear-gradient(180deg,#121A33,#0F1730);border:1px solid var(--line);border-radius:16px;padding:1.15rem 1.25rem;margin-bottom:1rem;transition:border-color .25s,transform .25s,box-shadow .25s;animation:riseIn .55s both}
.card.hover:hover{border-color:rgba(124,92,255,.7);transform:translateY(-3px);box-shadow:0 12px 30px rgba(0,0,0,.2)}
.card h4{margin:.1rem 0 .5rem;font-size:1rem}
.muted{color:var(--mu)}.small{font-size:.84rem}
.pagehead{display:flex;align-items:center;gap:.9rem;margin-bottom:1.4rem}
.pagehead .ic{width:44px;height:44px;border-radius:13px;background:var(--grad);display:grid;place-items:center}
.pagehead h1{margin:0;font-size:1.65rem}.pagehead p{margin:.1rem 0 0;color:var(--mu)}
.kpi{background:linear-gradient(180deg,var(--s1),#0F1730);border:1px solid var(--line);border-radius:16px;padding:1rem 1.15rem;height:100%}
.kpi .lb{display:flex;align-items:center;gap:.45rem;color:var(--mu);font-weight:600;font-size:.84rem}
.kpi .vl{font-size:2rem;font-weight:700;margin-top:.25rem;letter-spacing:-.03em}
.kpi .sb{color:var(--mu);font-size:.8rem;margin-top:.1rem}
.badge{display:inline-flex;align-items:center;gap:.35rem;padding:.2rem .6rem;border-radius:999px;font-size:.74rem;font-weight:700;border:1px solid var(--line);background:var(--s2);color:var(--mu);white-space:nowrap}
.badge.ok{color:#6EE7B7;border-color:rgba(52,211,153,.4);background:rgba(52,211,153,.1)}
.badge.warn{color:#FCD34D;border-color:rgba(251,191,36,.4);background:rgba(251,191,36,.1)}
.badge.info{color:#A5B4FF;border-color:rgba(124,92,255,.5);background:rgba(124,92,255,.14)}
.badge.err{color:#FCA5A5;border-color:rgba(248,113,113,.4);background:rgba(248,113,113,.1)}
.dim{margin:.65rem 0}.dim .top{display:flex;justify-content:space-between;font-size:.88rem;font-weight:600}
.dim .bar{height:8px;background:#1B2550;border-radius:99px;margin-top:.35rem;overflow:hidden}
.dim .bar i{display:block;height:100%;border-radius:99px;background:var(--grad)}
.dim .why{color:var(--mu);font-size:.82rem;margin-top:.3rem;line-height:1.45}
.ring{--p:0;width:118px;height:118px;border-radius:50%;background:conic-gradient(var(--pu) calc(var(--p)*1%),#1B2550 0);display:grid;place-items:center}
.ring>div{width:92px;height:92px;border-radius:50%;background:#0F1730;display:grid;place-items:center;text-align:center}
.ring b{font-size:1.7rem;line-height:1}.ring span{font-size:.7rem;color:var(--mu)}
.msg{display:flex;gap:.7rem;margin:.9rem 0;align-items:flex-start}
.msg .av{flex:0 0 34px;height:34px;border-radius:50%;display:grid;place-items:center;background:var(--grad)}
.msg .bub{background:var(--s1);border:1px solid var(--line);padding:.8rem 1rem;border-radius:4px 16px 16px 16px;max-width:86%;line-height:1.55}
.msg.me{flex-direction:row-reverse}.msg.me .av{background:#26315A}
.msg.me .bub{background:linear-gradient(135deg,rgba(124,92,255,.3),rgba(59,130,246,.22));border-color:rgba(124,92,255,.5);border-radius:16px 4px 16px 16px}
.msg .meta{font-size:.72rem;color:var(--mu);margin-bottom:.25rem;font-weight:600}
.mini{margin:.2rem 0 .2rem 2.7rem;padding:.55rem .8rem;border-left:3px solid var(--pu);background:rgba(124,92,255,.07);border-radius:0 10px 10px 0;font-size:.85rem;color:var(--mu)}
mark.mk-filler{background:rgba(251,191,36,.25);color:#FDE68A;border-radius:4px;padding:0 3px}
mark.mk-hedge{background:rgba(248,113,113,.2);color:#FECACA;border-radius:4px;padding:0 3px}
.star-row{display:flex;gap:.6rem;align-items:flex-start;padding:.55rem 0;border-bottom:1px solid var(--line)}
.star-row:last-child{border-bottom:0}.star-l{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;font-weight:700;flex:0 0 34px}
.star-ok{background:rgba(52,211,153,.15);color:#6EE7B7}.star-mid{background:rgba(251,191,36,.15);color:#FCD34D}.star-no{background:rgba(248,113,113,.15);color:#FCA5A5}
@keyframes riseIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.hero{animation:riseIn .65s both}.hero h1{font-size:3.1rem;line-height:1.08;margin:.3rem 0 1rem;max-width:15ch}
.hero p.lead{font-size:1.12rem;color:var(--mu);max-width:52ch;line-height:1.6}
.grad-text{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.empty{text-align:center;padding:2.2rem 1rem;border:1px dashed var(--line);border-radius:16px;color:var(--mu)}
.empty h4{color:var(--tx);margin:.6rem 0 .3rem}
ul.tight{margin:.2rem 0 .2rem 1.1rem;padding:0}ul.tight li{margin:.25rem 0;line-height:1.5}
.hero-shell{position:relative;border:1px solid rgba(124,92,255,.25);border-radius:24px;padding:1.5rem;background:linear-gradient(135deg,#121A33,#0F1730);overflow:hidden;box-shadow:0 16px 45px rgba(0,0,0,.18)}
.hero-visual{position:relative;min-height:310px;display:flex;align-items:center;justify-content:center;animation:floatCard 7s ease-in-out infinite}
.orbit{position:absolute;width:270px;height:270px;border:1px solid rgba(165,180,252,.22);border-radius:50%;animation:spin 24s linear infinite}
.orbit:before,.orbit:after{content:'';position:absolute;width:10px;height:10px;border-radius:50%;background:#22D3EE;top:36px;left:34px}
.orbit:after{background:#A78BFA;top:auto;left:auto;right:10px;bottom:65px}
@keyframes spin{to{transform:rotate(360deg)}}
.hero-panel{position:relative;z-index:1;width:min(100%,330px);padding:1.25rem;border-radius:18px;border:1px solid rgba(165,180,252,.25);background:#0B1020}
.signal{height:7px;border-radius:99px;background:#202B53;overflow:hidden;margin:.55rem 0}.signal i{display:block;height:100%;border-radius:99px;background:var(--grad);animation:signalLoad 2.2s ease-out both}
@keyframes signalLoad{from{width:0}}
.pill-live{display:inline-flex;align-items:center;gap:7px;color:#6EE7B7;font-size:.75rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
.pill-live:before{content:'';width:7px;height:7px;border-radius:50%;background:#34D399}
@keyframes floatCard{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
@media(max-width:820px){.block-container{padding:1.2rem 1rem 3rem}.hero h1{font-size:2.2rem}.msg .bub{max-width:100%}}
:focus-visible{outline:2px solid var(--cy);outline-offset:2px}
"""

_I = {
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "chart": '<line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>',
    "trend": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "alert": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "award": '<circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>',
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "bulb": '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "mic": '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    "inbox": '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
}


def icon(name: str, size: int = 18, color: str = "currentColor") -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_I[name]}</svg>')


def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def html(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def brand() -> str:
    return f'<div class="brand"><div class="logo">{icon("target", 18, "#fff")}</div>InterviewIQ</div>'


def page_header(title: str, subtitle: str, ic: str) -> None:
    html(f'<div class="pagehead"><div class="ic">{icon(ic, 22, "#fff")}</div><div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div></div>')


def kpi(label: str, value: str, sub: str = "", ic: str = "chart") -> str:
    return (f'<div class="kpi"><div class="lb">{icon(ic, 16, "#8B97C7")}{escape(label)}</div><div class="vl">{escape(str(value))}</div>'
            f'<div class="sb">{escape(sub)}</div></div>')


def badge(text: str, kind: str = "") -> str:
    return f'<span class="badge {kind}">{escape(text)}</span>'


def mode_badge(mode: str) -> str:
    return {"llm": badge("AI evaluation (LLM)", "ok"), "rule_based": badge("Rule-based fallback, not an LLM", "warn"),
            "mixed": badge("Mixed: LLM + rule-based", "warn")}.get(mode, "")


def card(inner: str, hover: bool = False) -> None:
    html(f'<div class="card{" hover" if hover else ""}">{inner}</div>')


def ring(score: float, caption: str = "/ 100") -> str:
    return f'<div class="ring" style="--p:{max(0, min(100, score)):.0f}"><div><div><b>{score:.0f}</b><br><span>{escape(caption)}</span></div></div></div>'


def dim_bar(dim: str, score, why: str = "") -> str:
    if score is None:
        return (f'<div class="dim"><div class="top"><span>{LABELS[dim]}</span><span class="muted">Not applicable</span></div>'
                f'<div class="bar"></div></div>')
    return (f'<div class="dim"><div class="top"><span>{LABELS[dim]}</span><span>{score:.1f}<span class="muted"> / 10</span></span></div>'
            f'<div class="bar"><i style="width:{score * 10:.0f}%"></i></div>'
            + (f'<div class="why">{escape(why)}</div>' if why else "") + '</div>')


def bullets(items: list[str]) -> str:
    return "<ul class='tight'>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>" if items else '<span class="muted small">Nothing to flag.</span>'


def empty(title: str, text: str, ic: str = "inbox") -> None:
    html(f'<div class="empty">{icon(ic, 30, "#7C5CFF")}<h4>{escape(title)}</h4><div>{escape(text)}</div></div>')


def go(page: str, **state) -> None:
    """Button callback: switch page (and optionally set other session keys)."""
    st.session_state.page = page
    for k, v in state.items():
        st.session_state[k] = v
