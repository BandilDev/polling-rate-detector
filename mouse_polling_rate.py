import tkinter as tk
import time
import math
import ctypes
import ctypes.wintypes as wt
import threading
from collections import deque

# ── Windows low-level mouse hook ──────────────────────────────────────────────
WH_MOUSE_LL  = 14
WM_MOUSEMOVE = 0x0200
SAMPLE_WIN   = 1.0

_lock       = threading.Lock()
_timestamps = deque()

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD),
                ("flags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

_HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wt.WPARAM, wt.LPARAM)

def _make_hook():
    def _proc(nCode, wParam, lParam):
        if nCode >= 0 and wParam == WM_MOUSEMOVE:
            with _lock:
                _timestamps.append(time.perf_counter())
        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
    cb   = _HOOKPROC(_proc)
    hook = ctypes.windll.user32.SetWindowsHookExW(WH_MOUSE_LL, cb, None, 0)
    msg  = wt.MSG()
    while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
        ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
    ctypes.windll.user32.UnhookWindowsHookEx(hook)

def start_hook():
    threading.Thread(target=_make_hook, daemon=True).start()

# ── Colour helpers ────────────────────────────────────────────────────────────
def _rgb(h):
    h = h.lstrip("#")
    return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)

def lerp_col(c1, c2, t):
    r1,g1,b1 = _rgb(c1); r2,g2,b2 = _rgb(c2)
    t = max(0.0, min(1.0, t))
    return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = "#07060f"
CARD    = "#0d0b1a"
CARD2   = "#110e22"
BORDER  = "#1c1438"
P1      = "#9333ea"
P2      = "#c084fc"
P3      = "#7c3aed"
PINK    = "#ec4899"
CYAN    = "#22d3ee"
GREEN   = "#4ade80"
YELLOW  = "#facc15"
ORANGE  = "#fb923c"
TEAL    = "#00ffd0"
WHITE   = "#f0eeff"
DIM     = "#4a3d7a"
DIMMER  = "#1e1835"
DIMMEST = "#0e0c1c"
RED     = "#ef4444"

MAX_HZ    = 16000
W, H      = 2560, 1440
ARC_START = 225
ARC_SWEEP = -270

# ── Layout ────────────────────────────────────────────────────────────────────
DIVX = 1160
GCX  = 570
GCY  = 530
GR   = 320

def arc_pos(cx, cy, r, angle_deg):
    rad = math.radians(angle_deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)

def hz_to_angle(hz):
    return ARC_START + ARC_SWEEP * min(hz / MAX_HZ, 1.0)

def classify(hz):
    if hz >= 14000: return "#ff6ef7",  "16000 Hz TIER"
    if hz >= 7000:  return TEAL,       "8000 Hz TIER"
    if hz >= 3500:  return CYAN,       "4000 Hz TIER"
    if hz >= 1800:  return GREEN,      "2000 Hz TIER"
    if hz >= 900:   return "#a3e635",  "1000 Hz TIER"
    if hz >= 450:   return YELLOW,     "500 Hz TIER"
    if hz >= 225:   return ORANGE,     "250 Hz TIER"
    return                PINK,        "125 Hz TIER"

def round_rect(canvas, x1, y1, x2, y2, r=16, **kw):
    return canvas.create_polygon(
        x1+r, y1,   x2-r, y1,
        x2,   y1,   x2,   y1+r,
        x2,   y2-r, x2,   y2,
        x2-r, y2,   x1+r, y2,
        x1,   y2,   x1,   y2-r,
        x1,   y1+r, x1,   y1,
        smooth=True, **kw)

# ── App ───────────────────────────────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Bandil's Polling Rate Detector")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.geometry(f"{W}x{H}+0+0")

        self.peak     = 0
        self.current  = 0
        self._disp_hz = 0.0
        self.phase    = 0.0
        self.paused   = False
        self.trail    = deque(maxlen=200)
        self.mx = self.my = -999

        self._build()
        self._tick()
        self._anim()
        self.root.bind("<Motion>", self._motion)
        self.root.bind("<space>", lambda e: self._toggle_pause())

    # ─────────────────────────────────────────────────────────────────────────
    def _build(self):
        c = tk.Canvas(self.root, width=W, height=H,
                      bg=BG, highlightthickness=0)
        c.pack()
        self.c = c

        # ── Top accent bar ───────────────────────────────────────────────────
        for i in range(7):
            c.create_rectangle(0, i, W, i+1,
                fill=lerp_col(P2, P1, i/6), outline="")

        # ── Header ──────────────────────────────────────────────────────────
        c.create_text(W//2, 38,
            text="BANDIL'S POLLING RATE DETECTOR",
            font=("Segoe UI", 16, "bold"), fill=DIM)

        # Separator
        steps = 160
        seg_w = (W - 160) / steps
        for i in range(steps):
            t = 1.0 - abs(i - steps/2) / (steps/2)
            x = 80 + i * seg_w
            c.create_rectangle(x, 64, x+seg_w, 65,
                fill=lerp_col(BG, BORDER, t*0.85), outline="")

        # ── Vertical divider ─────────────────────────────────────────────────
        for dy in range(80, H, 2):
            t = 0.5 + 0.5*math.sin(dy*0.025)
            c.create_rectangle(DIVX, dy, DIVX+1, dy+2,
                fill=lerp_col(BG, BORDER, t*0.65), outline="")

        # ════════════════════════════════════════════════════════════════════
        # LEFT PANEL
        # ════════════════════════════════════════════════════════════════════

        # Background glow
        self._glow_bg = c.create_oval(
            GCX-GR-70, GCY-GR-70, GCX+GR+70, GCY+GR+70,
            fill=lerp_col(BG, P1, 0.05), outline="")

        # Outer rings
        c.create_oval(GCX-GR-30, GCY-GR-30, GCX+GR+30, GCY+GR+30,
            outline=DIMMER, fill="", width=1)
        c.create_oval(GCX-GR-36, GCY-GR-36, GCX+GR+36, GCY+GR+36,
            outline=lerp_col(BG, BORDER, 0.3), fill="", width=1)

        # Track halos
        for pad, w, a in [(14,36,0.02),(8,28,0.05),(4,22,0.10)]:
            c.create_arc(GCX-GR-pad, GCY-GR-pad, GCX+GR+pad, GCY+GR+pad,
                start=ARC_START, extent=ARC_SWEEP,
                style='arc', outline=lerp_col(BG, BORDER, a), width=w)

        # Track main
        c.create_arc(GCX-GR, GCY-GR, GCX+GR, GCY+GR,
            start=ARC_START, extent=ARC_SWEEP,
            style='arc', outline=DIMMER, width=20)

        # Track inner
        c.create_arc(GCX-GR+10, GCY-GR+10, GCX+GR-10, GCY+GR-10,
            start=ARC_START, extent=ARC_SWEEP,
            style='arc', outline=lerp_col(DIMMER, CARD2, 0.5), width=1)

        # Tick marks
        ticks = [(2000,"2k"),(4000,"4k"),(8000,"8k"),(16000,"16k")]
        for hz, lbl in ticks:
            ang = hz_to_angle(hz)
            ix, iy = arc_pos(GCX, GCY, GR-15, ang)
            ox, oy = arc_pos(GCX, GCY, GR+18, ang)
            c.create_line(ix, iy, ox, oy, fill=DIM, width=2, capstyle='round')
            lx, ly = arc_pos(GCX, GCY, GR+42, ang)
            c.create_text(lx, ly, text=lbl,
                font=("Segoe UI", 11, "bold"), fill=DIM, anchor="center")

        # Minor ticks every 1000 Hz
        tick_set = {h for h,_ in ticks}
        for hz in range(1000, MAX_HZ, 1000):
            if hz not in tick_set:
                ang = hz_to_angle(hz)
                ix, iy = arc_pos(GCX, GCY, GR-6, ang)
                ox, oy = arc_pos(GCX, GCY, GR+6, ang)
                c.create_line(ix, iy, ox, oy, fill=BORDER, width=1)

        # Progress arc glows
        self._arc_glows = []
        for pad, w, a in [(14,44,0.04),(8,32,0.11),(4,25,0.22)]:
            ag = c.create_arc(GCX-GR-pad, GCY-GR-pad, GCX+GR+pad, GCY+GR+pad,
                start=ARC_START, extent=0,
                style='arc', outline=lerp_col(BG, P1, a), width=w)
            self._arc_glows.append((ag, a))

        # Progress arc main
        self._arc_main = c.create_arc(GCX-GR, GCY-GR, GCX+GR, GCY+GR,
            start=ARC_START, extent=0,
            style='arc', outline=P1, width=16)

        # Arc tip
        self._arc_tip_glow = c.create_oval(0,0,1,1, fill=P1, outline="", state="hidden")
        self._arc_tip      = c.create_oval(0,0,1,1, fill=WHITE, outline="", state="hidden")

        # Gauge face
        face_r = GR - 26
        c.create_oval(GCX-face_r, GCY-face_r, GCX+face_r, GCY+face_r,
            fill=BG, outline=lerp_col(BG, BORDER, 0.6), width=1)
        c.create_oval(GCX-face_r+14, GCY-face_r+14,
                      GCX+face_r-14, GCY+face_r-14,
            fill="", outline=DIMMER, width=1)

        # Hz number
        self._num_shadows = []
        for dx, dy, a in [(5,5,0.04),(3,3,0.09),(1,1,0.18)]:
            sh = c.create_text(GCX+dx, GCY-24+dy, text="---",
                font=("Segoe UI Light", 160), fill=lerp_col(BG, P1, a),
                anchor="center")
            self._num_shadows.append(sh)

        self._num = c.create_text(GCX, GCY-24, text="---",
            font=("Segoe UI Light", 160), fill=WHITE, anchor="center")

        self._hz_lbl = c.create_text(GCX, GCY+88,
            text="Hz", font=("Segoe UI", 22, "bold"), fill=DIM)

        # Tier badge
        self._tier_bg = c.create_rectangle(0, 0, 1, 1,
            fill=DIMMEST, outline=BORDER, width=1)
        self._tier_tx = c.create_text(GCX, GCY+130,
            text="MOVE MOUSE TO DETECT",
            font=("Segoe UI", 14, "bold"), fill=DIM)

        # ── Stats cards ──────────────────────────────────────────────────────
        sy     = GCY + GR + 68
        cw     = 248
        gap    = 16
        card_h = 90
        total  = 3*cw + 2*gap
        sx0    = GCX - total//2
        self._stats = {}
        accent_cols = [P1, "#2563eb", "#0d9488"]

        for i, label in enumerate(["CURRENT", "PEAK", "TIER"]):
            cx2 = sx0 + i*(cw+gap) + cw//2
            round_rect(c, cx2-cw//2+5, sy+5, cx2+cw//2+5, sy+card_h+5, r=16,
                fill="#020105", outline="")
            round_rect(c, cx2-cw//2, sy, cx2+cw//2, sy+card_h, r=16,
                fill=CARD2, outline=BORDER, width=1)
            round_rect(c, cx2-cw//2, sy, cx2+cw//2, sy+6, r=16,
                fill=accent_cols[i], outline="")
            c.create_rectangle(cx2-cw//2, sy+3, cx2+cw//2, sy+6,
                fill=accent_cols[i], outline="")
            c.create_text(cx2, sy+24, text=label,
                font=("Segoe UI", 10, "bold"), fill=DIM)
            val = c.create_text(cx2, sy+60, text="---",
                font=("Segoe UI", 26, "bold"), fill=DIM)
            self._stats[label] = val

        # ── Reset button ─────────────────────────────────────────────────────
        ry = sy + card_h + 32
        self._btn_bg = round_rect(c, GCX-110, ry-25, GCX+110, ry+25, r=25,
            fill=DIMMEST, outline=BORDER, width=1)
        self._btn_tx = c.create_text(GCX, ry,
            text="⟳  RESET PEAK",
            font=("Segoe UI", 13, "bold"), fill=DIM)
        for item in [self._btn_bg, self._btn_tx]:
            c.tag_bind(item, "<Button-1>", lambda e: self._reset())
            c.tag_bind(item, "<Enter>",
                lambda e: [c.itemconfig(self._btn_bg, fill=CARD2, outline=P3),
                           c.itemconfig(self._btn_tx, fill=P2)])
            c.tag_bind(item, "<Leave>",
                lambda e: [c.itemconfig(self._btn_bg, fill=DIMMEST, outline=BORDER),
                           c.itemconfig(self._btn_tx, fill=DIM)])

        # ── Pause toggle (spacebar) ───────────────────────────────────────────
        py = ry + 66
        self._pause_bg = round_rect(c, GCX-160, py-25, GCX+160, py+25, r=25,
            fill=DIMMEST, outline=BORDER, width=1)
        self._pause_tx = c.create_text(GCX, py,
            text="▶  SPACE  —  PAUSE READING",
            font=("Segoe UI", 12, "bold"), fill=DIM)
        for item in [self._pause_bg, self._pause_tx]:
            c.tag_bind(item, "<Button-1>", lambda e: self._toggle_pause())

        # ════════════════════════════════════════════════════════════════════
        # RIGHT PANEL — detection zone
        # ════════════════════════════════════════════════════════════════════
        zx1, zy1 = DIVX + 32, 84
        zx2, zy2 = W - 32, H - 32
        self._zx1, self._zy1, self._zx2, self._zy2 = zx1, zy1, zx2, zy2

        round_rect(c, zx1+7, zy1+7, zx2+7, zy2+7, r=26, fill="#020105", outline="")
        round_rect(c, zx1, zy1, zx2, zy2, r=26, fill=CARD, outline=BORDER, width=1)

        # Header strip
        round_rect(c, zx1, zy1, zx2, zy1+70, r=26, fill=CARD2, outline="")
        c.create_rectangle(zx1, zy1+44, zx2, zy1+70, fill=CARD2, outline="")
        c.create_line(zx1+26, zy1+70, zx2-26, zy1+70, fill=BORDER, width=1)
        c.create_text((zx1+zx2)//2, zy1+38,
            text="DETECTION ZONE",
            font=("Segoe UI", 13, "bold"), fill=DIM)

        # Dot grid
        for gx in range(zx1+36, zx2-10, 38):
            for gy in range(zy1+36, zy2-10, 38):
                c.create_oval(gx-1.5, gy-1.5, gx+1.5, gy+1.5,
                    fill=BORDER, outline="")

        # Corner brackets
        cs = 34
        for bx, by, sx, sy2 in [(zx1,zy1,1,1),(zx2,zy1,-1,1),
                                  (zx1,zy2,1,-1),(zx2,zy2,-1,-1)]:
            c.create_line(bx+sx*12, by, bx+sx*cs, by,
                fill=P2, width=3, capstyle='round')
            c.create_line(bx, by+sy2*12, bx, by+sy2*cs,
                fill=P2, width=3, capstyle='round')
            c.create_oval(bx-5, by-5, bx+5, by+5, fill=P1, outline="")

        # Animated border
        self._zborder = [c.create_line(0,0,0,0, fill=P1, width=4)
                         for _ in range(2)]

        # Hint text
        self._zone_hint = c.create_text(
            (zx1+zx2)//2, (zy1+zy2)//2,
            text="MOVE MOUSE HERE",
            font=("Segoe UI", 28, "bold"), fill=BORDER)

        # Paused overlay (hidden by default)
        self._pause_overlay = c.create_text(
            (zx1+zx2)//2, (zy1+zy2)//2,
            text="⏸  PAUSED\nPress SPACE to resume",
            font=("Segoe UI", 36, "bold"), fill=RED,
            justify="center", state="hidden")

        # Trail + cursor
        self._trail_dots = [
            c.create_oval(0,0,0,0, fill=P1, outline="", state="hidden")
            for _ in range(200)]
        self._cur_ring2 = c.create_oval(0,0,0,0, outline=P3, width=2, state="hidden")
        self._cur_ring  = c.create_oval(0,0,0,0, outline=P2, width=3, state="hidden")
        self._cur_dot   = c.create_oval(0,0,0,0, fill=WHITE, outline="", state="hidden")

    # ── Pause toggle ─────────────────────────────────────────────────────────
    def _toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.c.itemconfig(self._pause_bg, fill=lerp_col(RED, BG, 0.7), outline=RED)
            self.c.itemconfig(self._pause_tx,
                text="⏸  SPACE  —  RESUME READING", fill=RED)
            self.c.itemconfig(self._pause_overlay, state="normal")
            self.c.itemconfig(self._zone_hint, text="")
        else:
            self.c.itemconfig(self._pause_bg, fill=DIMMEST, outline=BORDER)
            self.c.itemconfig(self._pause_tx,
                text="▶  SPACE  —  PAUSE READING", fill=DIM)
            self.c.itemconfig(self._pause_overlay, state="hidden")

    # ── Events ───────────────────────────────────────────────────────────────
    def _motion(self, event):
        self.mx, self.my = event.x, event.y
        if not self.paused and self._in_zone(event.x, event.y):
            self.trail.append((event.x, event.y, time.perf_counter()))

    def _in_zone(self, x, y):
        return self._zx1 < x < self._zx2 and self._zy1 < y < self._zy2

    # ── Data tick ────────────────────────────────────────────────────────────
    def _tick(self):
        if not self.paused:
            now    = time.perf_counter()
            cutoff = now - SAMPLE_WIN
            with _lock:
                while _timestamps and _timestamps[0] < cutoff:
                    _timestamps.popleft()
                count = len(_timestamps)
                span  = (_timestamps[-1] - _timestamps[0]) if count >= 2 else 0

            if count >= 2 and span > 0:
                rate = int(round((count-1) / span))
                self.current = rate
                if rate > self.peak:
                    self.peak = rate

                col,  tier = classify(rate)
                pcol, _    = classify(self.peak)

                self.c.itemconfig(self._num, text=str(rate), fill=col)
                self.c.itemconfig(self._hz_lbl, fill=col)
                for i, sh in enumerate(self._num_shadows):
                    self.c.itemconfig(sh, text=str(rate),
                        fill=lerp_col(BG, col, [0.04,0.09,0.18][i]))

                self.c.itemconfig(self._tier_tx, text=f"  {tier}  ", fill=col)
                self.c.itemconfig(self._tier_bg, outline=col)
                bb = self.c.bbox(self._tier_tx)
                if bb:
                    self.c.coords(self._tier_bg,
                        bb[0]-14, bb[1]-8, bb[2]+14, bb[3]+8)

                self.c.itemconfig(self._stats["CURRENT"], text=f"{rate} Hz",      fill=col)
                self.c.itemconfig(self._stats["PEAK"],    text=f"{self.peak} Hz", fill=pcol)
                self.c.itemconfig(self._stats["TIER"],    text=tier,              fill=col)
            else:
                self.current = 0
                self.c.itemconfig(self._num,     text="---", fill=WHITE)
                self.c.itemconfig(self._hz_lbl,  fill=DIM)
                self.c.itemconfig(self._tier_tx, text="MOVE MOUSE TO DETECT", fill=DIM)
                self.c.itemconfig(self._tier_bg, outline=BORDER)
                bb = self.c.bbox(self._tier_tx)
                if bb:
                    self.c.coords(self._tier_bg,
                        bb[0]-14, bb[1]-8, bb[2]+14, bb[3]+8)
                for sh in self._num_shadows:
                    self.c.itemconfig(sh, text="---", fill=DIMMER)

        self.root.after(45, self._tick)

    # ── Animation tick ───────────────────────────────────────────────────────
    def _anim(self):
        self.phase += 0.028
        now = time.perf_counter()
        col, _ = classify(self.current) if self.current > 0 else (P1, "")

        if not self.paused:
            self._disp_hz += (self.current - self._disp_hz) * 0.10
        frac   = min(self._disp_hz / MAX_HZ, 1.0)
        extent = ARC_SWEEP * frac

        for ag, base_a in self._arc_glows:
            self.c.itemconfig(ag, extent=extent,
                outline=lerp_col(BG, col, base_a))
        self.c.itemconfig(self._arc_main, extent=extent, outline=col)

        if frac > 0.005:
            tip_ang = ARC_START + extent
            tx, ty  = arc_pos(GCX, GCY, GR, tip_ang)
            self.c.coords(self._arc_tip_glow, tx-16, ty-16, tx+16, ty+16)
            self.c.coords(self._arc_tip,      tx-7,  ty-7,  tx+7,  ty+7)
            self.c.itemconfig(self._arc_tip_glow,
                fill=lerp_col(BG, col, 0.5), state="normal")
            self.c.itemconfig(self._arc_tip,
                fill=lerp_col(col, WHITE, 0.75), state="normal")
        else:
            self.c.itemconfig(self._arc_tip,      state="hidden")
            self.c.itemconfig(self._arc_tip_glow, state="hidden")

        pulse = 0.5 + 0.5*math.sin(self.phase*0.4)
        self.c.itemconfig(self._glow_bg,
            fill=lerp_col(lerp_col(BG, P1, 0.04),
                          lerp_col(BG, col, 0.08), pulse))

        # Travelling border
        zx1,zy1,zx2,zy2 = self._zx1,self._zy1,self._zx2,self._zy2
        perim = 2*((zx2-zx1)+(zy2-zy1))
        def bpt(d):
            d %= perim
            ww=zx2-zx1; hh=zy2-zy1
            if d<ww: return zx1+d, zy1
            d-=ww
            if d<hh: return zx2, zy1+d
            d-=hh
            if d<ww: return zx2-d, zy2
            d-=ww
            return zx1, zy2-d

        bdr_col = lerp_col(DIMMER, RED, 0.6) if self.paused else col
        for i, seg in enumerate(self._zborder):
            off = (self.phase*0.25 + i*0.5) % 1.0
            sd  = off * perim
            p1  = bpt(sd);  p2 = bpt(sd + perim*0.10)
            bright = 0.4 + 0.6*math.sin(self.phase*1.6 + i*math.pi)
            self.c.coords(seg, p1[0],p1[1], p2[0],p2[1])
            self.c.itemconfig(seg, fill=lerp_col(BORDER, bdr_col, bright*0.8))

        # Trail
        if not self.paused:
            fade_win  = 0.55
            trail_vis = [(x,y,t) for x,y,t in self.trail if now-t < fade_win]
            for i, dot in enumerate(self._trail_dots):
                if i < len(trail_vis):
                    x, y, ts = trail_vis[i]
                    age = (now-ts)/fade_win
                    r   = max(1, int(9*(1-age)**1.4))
                    self.c.coords(dot, x-r,y-r,x+r,y+r)
                    self.c.itemconfig(dot,
                        fill=lerp_col(CARD, col, (1-age)**1.8), state="normal")
                    self.c.tag_raise(dot)
                else:
                    self.c.itemconfig(dot, state="hidden")
        else:
            for dot in self._trail_dots:
                self.c.itemconfig(dot, state="hidden")

        # Cursor
        x, y = self.mx, self.my
        if not self.paused and self._in_zone(x, y):
            p2 = 0.5 + 0.5*math.sin(self.phase*2.5)
            r1 = 18 + p2*7;  r2 = 32 + p2*6
            self.c.coords(self._cur_ring,  x-r1,y-r1,x+r1,y+r1)
            self.c.coords(self._cur_ring2, x-r2,y-r2,x+r2,y+r2)
            self.c.coords(self._cur_dot,   x-5,y-5,x+5,y+5)
            rc = lerp_col(P1, col, p2)
            self.c.itemconfig(self._cur_ring,  outline=rc, state="normal")
            self.c.itemconfig(self._cur_ring2,
                outline=lerp_col(BG, rc, 0.4), state="normal")
            self.c.itemconfig(self._cur_dot, fill=WHITE, state="normal")
            for item in [self._cur_ring2, self._cur_ring, self._cur_dot]:
                self.c.tag_raise(item)
            if not self.paused:
                self.c.itemconfig(self._zone_hint, text="")
        else:
            for item in [self._cur_ring, self._cur_ring2, self._cur_dot]:
                self.c.itemconfig(item, state="hidden")
            if not self.paused:
                if self.current == 0:
                    p2 = 0.35 + 0.25*math.sin(self.phase*0.8)
                    self.c.itemconfig(self._zone_hint,
                        text="MOVE MOUSE HERE",
                        fill=lerp_col(DIMMER, DIM, p2))
                else:
                    self.c.itemconfig(self._zone_hint, text="")

        self.root.after(16, self._anim)

    def _reset(self):
        self.peak = 0
        self.c.itemconfig(self._stats["PEAK"], text="---", fill=DIM)


def main():
    start_hook()
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
