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

MAX_HZ    = 8000
W, H      = 1920, 1080
ARC_START = 225
ARC_SWEEP = -270

# ── Layout constants ──────────────────────────────────────────────────────────
# Left panel: x 0..860   — gauge, stats, reset
# Divider:    x 860..900
# Right panel: x 900..1920 — detection zone
DIVX      = 880          # x of vertical divider
GCX, GCY  = 430, 450     # gauge centre
GR        = 270          # gauge radius

def arc_pos(cx, cy, r, angle_deg):
    rad = math.radians(angle_deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)

def hz_to_angle(hz):
    return ARC_START + ARC_SWEEP * min(hz / MAX_HZ, 1.0)

def classify(hz):
    if hz >= 7000: return TEAL,     "8000 Hz TIER"
    if hz >= 3500: return CYAN,     "4000 Hz TIER"
    if hz >= 1800: return GREEN,    "2000 Hz TIER"
    if hz >= 900:  return "#a3e635","1000 Hz TIER"
    if hz >= 450:  return YELLOW,   "500 Hz TIER"
    if hz >= 225:  return ORANGE,   "250 Hz TIER"
    return               PINK,      "125 Hz TIER"

def round_rect(canvas, x1, y1, x2, y2, r=14, **kw):
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
        self.trail    = deque(maxlen=160)
        self.mx = self.my = -999

        self._build()
        self._tick()
        self._anim()
        self.root.bind("<Motion>", self._motion)

    # ─────────────────────────────────────────────────────────────────────────
    def _build(self):
        c = tk.Canvas(self.root, width=W, height=H,
                      bg=BG, highlightthickness=0)
        c.pack()
        self.c = c

        # ── Full-width top accent bar ────────────────────────────────────────
        for i in range(6):
            col = lerp_col(P2, P1, i/5)
            c.create_rectangle(0, i, W, i+1, fill=col, outline="")

        # ── Header (full width) ──────────────────────────────────────────────
        c.create_text(W//2, 32,
            text="BANDIL'S POLLING RATE DETECTOR",
            font=("Segoe UI", 13, "bold"), fill=DIM)

        # Fading separator
        steps = 120
        seg_w = (W - 120) / steps
        for i in range(steps):
            t = 1.0 - abs(i - steps/2) / (steps/2)
            col = lerp_col(BG, BORDER, t * 0.85)
            x = 60 + i * seg_w
            c.create_rectangle(x, 54, x+seg_w, 55, fill=col, outline="")

        # ── Vertical divider ─────────────────────────────────────────────────
        for dy in range(70, H, 2):
            t = 0.5 + 0.5 * math.sin(dy * 0.03)
            col = lerp_col(BG, BORDER, t * 0.7)
            c.create_rectangle(DIVX, dy, DIVX+1, dy+2, fill=col, outline="")

        # ════════════════════════════════════════════════════════════════════
        # LEFT PANEL — gauge
        # ════════════════════════════════════════════════════════════════════

        # Background glow blob behind gauge
        self._glow_bg = c.create_oval(
            GCX-GR-60, GCY-GR-60, GCX+GR+60, GCY+GR+60,
            fill=lerp_col(BG, P1, 0.05), outline="")

        # Outer decorative rings
        c.create_oval(GCX-GR-26, GCY-GR-26, GCX+GR+26, GCY+GR+26,
            outline=DIMMER, fill="", width=1)
        c.create_oval(GCX-GR-31, GCY-GR-31, GCX+GR+31, GCY+GR+31,
            outline=lerp_col(BG, BORDER, 0.35), fill="", width=1)

        # Track arc halos
        for pad, w, a in [(12,32,0.02),(7,26,0.05),(3,20,0.10)]:
            c.create_arc(GCX-GR-pad, GCY-GR-pad, GCX+GR+pad, GCY+GR+pad,
                start=ARC_START, extent=ARC_SWEEP,
                style='arc', outline=lerp_col(BG, BORDER, a), width=w)

        # Track arc — main
        c.create_arc(GCX-GR, GCY-GR, GCX+GR, GCY+GR,
            start=ARC_START, extent=ARC_SWEEP,
            style='arc', outline=DIMMER, width=18)

        # Track inner highlight
        c.create_arc(GCX-GR+9, GCY-GR+9, GCX+GR-9, GCY+GR-9,
            start=ARC_START, extent=ARC_SWEEP,
            style='arc', outline=lerp_col(DIMMER, CARD2, 0.5), width=1)

        # Tick marks + labels
        ticks = [(1000,"1k"),(2000,"2k"),(4000,"4k"),(8000,"8k")]
        for hz, lbl in ticks:
            ang = hz_to_angle(hz)
            ix, iy = arc_pos(GCX, GCY, GR-14, ang)
            ox, oy = arc_pos(GCX, GCY, GR+16, ang)
            c.create_line(ix, iy, ox, oy, fill=DIM, width=2, capstyle='round')
            lx, ly = arc_pos(GCX, GCY, GR+36, ang)
            c.create_text(lx, ly, text=lbl,
                font=("Segoe UI", 10, "bold"), fill=DIM, anchor="center")

        # Minor ticks every 500 Hz
        tick_hz_set = {h for h,_ in ticks}
        for hz in range(500, MAX_HZ, 500):
            if hz not in tick_hz_set:
                ang = hz_to_angle(hz)
                ix, iy = arc_pos(GCX, GCY, GR-5, ang)
                ox, oy = arc_pos(GCX, GCY, GR+5, ang)
                c.create_line(ix, iy, ox, oy, fill=BORDER, width=1)

        # Progress arc glow halos
        self._arc_glows = []
        for pad, w, a in [(12,38,0.04),(7,28,0.11),(3,22,0.22)]:
            ag = c.create_arc(GCX-GR-pad, GCY-GR-pad, GCX+GR+pad, GCY+GR+pad,
                start=ARC_START, extent=0,
                style='arc', outline=lerp_col(BG, P1, a), width=w)
            self._arc_glows.append((ag, a))

        # Progress arc main
        self._arc_main = c.create_arc(GCX-GR, GCY-GR, GCX+GR, GCY+GR,
            start=ARC_START, extent=0,
            style='arc', outline=P1, width=14)

        # Arc tip
        self._arc_tip_glow = c.create_oval(0,0,1,1, fill=P1, outline="", state="hidden")
        self._arc_tip      = c.create_oval(0,0,1,1, fill=WHITE, outline="", state="hidden")

        # Gauge face
        face_r = GR - 24
        c.create_oval(GCX-face_r, GCY-face_r, GCX+face_r, GCY+face_r,
            fill=BG, outline=lerp_col(BG, BORDER, 0.6), width=1)
        face_r2 = face_r - 12
        c.create_oval(GCX-face_r2, GCY-face_r2, GCX+face_r2, GCY+face_r2,
            fill="", outline=DIMMER, width=1)

        # Hz number shadows + main
        self._num_shadows = []
        for dx, dy, a in [(4,4,0.04),(2,2,0.09),(1,1,0.18)]:
            sh = c.create_text(GCX+dx, GCY-20+dy, text="---",
                font=("Segoe UI Light", 130), fill=lerp_col(BG, P1, a),
                anchor="center")
            self._num_shadows.append(sh)

        self._num = c.create_text(GCX, GCY-20, text="---",
            font=("Segoe UI Light", 130), fill=WHITE, anchor="center")

        self._hz_lbl = c.create_text(GCX, GCY+72,
            text="Hz", font=("Segoe UI", 18, "bold"), fill=DIM)

        # Tier badge
        self._tier_bg = c.create_rectangle(0, 0, 1, 1,
            fill=DIMMEST, outline=BORDER, width=1)
        self._tier_tx = c.create_text(GCX, GCY+108,
            text="MOVE MOUSE TO DETECT",
            font=("Segoe UI", 12, "bold"), fill=DIM)

        # ── Stats cards (left panel, below gauge) ────────────────────────────
        sy     = GCY + GR + 55
        cw     = 210
        gap    = 14
        card_h = 80
        total  = 3*cw + 2*gap
        sx0    = GCX - total//2

        self._stats = {}
        accent_cols = [P1, "#2563eb", "#0d9488"]

        for i, label in enumerate(["CURRENT", "PEAK", "TIER"]):
            cx2 = sx0 + i*(cw+gap) + cw//2
            round_rect(c, cx2-cw//2+4, sy+4, cx2+cw//2+4, sy+card_h+4, r=14,
                fill="#020105", outline="")
            round_rect(c, cx2-cw//2, sy, cx2+cw//2, sy+card_h, r=14,
                fill=CARD2, outline=BORDER, width=1)
            round_rect(c, cx2-cw//2, sy, cx2+cw//2, sy+5, r=14,
                fill=accent_cols[i], outline="")
            c.create_rectangle(cx2-cw//2, sy+2, cx2+cw//2, sy+5,
                fill=accent_cols[i], outline="")
            c.create_text(cx2, sy+22, text=label,
                font=("Segoe UI", 9, "bold"), fill=DIM)
            val = c.create_text(cx2, sy+52, text="---",
                font=("Segoe UI", 22, "bold"), fill=DIM)
            self._stats[label] = val

        # ── Reset button ─────────────────────────────────────────────────────
        ry = sy + card_h + 28
        self._btn_bg = round_rect(c, GCX-100, ry-22, GCX+100, ry+22, r=22,
            fill=DIMMEST, outline=BORDER, width=1)
        self._btn_tx = c.create_text(GCX, ry,
            text="⟳  RESET PEAK",
            font=("Segoe UI", 11, "bold"), fill=DIM)

        for item in [self._btn_bg, self._btn_tx]:
            c.tag_bind(item, "<Button-1>", lambda e: self._reset())
            c.tag_bind(item, "<Enter>",
                lambda e: [c.itemconfig(self._btn_bg, fill=CARD2, outline=P3),
                           c.itemconfig(self._btn_tx, fill=P2)])
            c.tag_bind(item, "<Leave>",
                lambda e: [c.itemconfig(self._btn_bg, fill=DIMMEST, outline=BORDER),
                           c.itemconfig(self._btn_tx, fill=DIM)])

        # ════════════════════════════════════════════════════════════════════
        # RIGHT PANEL — detection zone
        # ════════════════════════════════════════════════════════════════════
        zx1, zy1 = DIVX + 28, 72
        zx2, zy2 = W - 28, H - 30
        self._zx1, self._zy1, self._zx2, self._zy2 = zx1, zy1, zx2, zy2

        # Zone shadow
        round_rect(c, zx1+6, zy1+6, zx2+6, zy2+6, r=22,
            fill="#020105", outline="")

        # Zone body
        round_rect(c, zx1, zy1, zx2, zy2, r=22,
            fill=CARD, outline=BORDER, width=1)

        # Top header strip inside zone
        round_rect(c, zx1, zy1, zx2, zy1+60, r=22, fill=CARD2, outline="")
        c.create_rectangle(zx1, zy1+38, zx2, zy1+60, fill=CARD2, outline="")
        c.create_line(zx1+22, zy1+60, zx2-22, zy1+60, fill=BORDER, width=1)

        # "DETECTION ZONE" label in strip
        c.create_text((zx1+zx2)//2, zy1+32,
            text="DETECTION ZONE",
            font=("Segoe UI", 11, "bold"), fill=DIM)

        # Dot grid
        for gx in range(zx1+30, zx2-10, 34):
            for gy in range(zy1+30, zy2-10, 34):
                c.create_oval(gx-1.4, gy-1.4, gx+1.4, gy+1.4,
                    fill=BORDER, outline="")

        # Corner brackets
        cs = 28
        for bx, by, sx, sy2 in [(zx1,zy1,1,1),(zx2,zy1,-1,1),
                                  (zx1,zy2,1,-1),(zx2,zy2,-1,-1)]:
            c.create_line(bx+sx*10, by, bx+sx*cs, by,
                fill=P2, width=3, capstyle='round')
            c.create_line(bx, by+sy2*10, bx, by+sy2*cs,
                fill=P2, width=3, capstyle='round')
            c.create_oval(bx-4, by-4, bx+4, by+4, fill=P1, outline="")

        # Animated border
        self._zborder = [c.create_line(0,0,0,0, fill=P1, width=3)
                         for _ in range(2)]

        # Zone hint text
        self._zone_hint = c.create_text(
            (zx1+zx2)//2, (zy1+zy2)//2,
            text="MOVE MOUSE HERE",
            font=("Segoe UI", 22, "bold"), fill=BORDER)

        # Trail + cursor
        self._trail_dots = [
            c.create_oval(0,0,0,0, fill=P1, outline="", state="hidden")
            for _ in range(160)]
        self._cur_ring2 = c.create_oval(0,0,0,0, outline=P3, width=2, state="hidden")
        self._cur_ring  = c.create_oval(0,0,0,0, outline=P2, width=3, state="hidden")
        self._cur_dot   = c.create_oval(0,0,0,0, fill=WHITE, outline="", state="hidden")

    # ── Events ───────────────────────────────────────────────────────────────
    def _motion(self, event):
        self.mx, self.my = event.x, event.y
        if self._in_zone(event.x, event.y):
            self.trail.append((event.x, event.y, time.perf_counter()))

    def _in_zone(self, x, y):
        return self._zx1 < x < self._zx2 and self._zy1 < y < self._zy2

    # ── Data tick ────────────────────────────────────────────────────────────
    def _tick(self):
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
                    bb[0]-12, bb[1]-7, bb[2]+12, bb[3]+7)

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
                    bb[0]-12, bb[1]-7, bb[2]+12, bb[3]+7)
            for sh in self._num_shadows:
                self.c.itemconfig(sh, text="---", fill=DIMMER)

        self.root.after(45, self._tick)

    # ── Animation tick ───────────────────────────────────────────────────────
    def _anim(self):
        self.phase += 0.028
        now = time.perf_counter()
        col, _ = classify(self.current) if self.current > 0 else (P1, "")

        # Smooth arc
        self._disp_hz += (self.current - self._disp_hz) * 0.10
        frac   = min(self._disp_hz / MAX_HZ, 1.0)
        extent = ARC_SWEEP * frac

        # Glow halos
        for ag, base_a in self._arc_glows:
            self.c.itemconfig(ag, extent=extent,
                outline=lerp_col(BG, col, base_a))

        # Main arc
        self.c.itemconfig(self._arc_main, extent=extent, outline=col)

        # Arc tip dot
        if frac > 0.005:
            tip_ang = ARC_START + extent
            tx, ty  = arc_pos(GCX, GCY, GR, tip_ang)
            self.c.coords(self._arc_tip_glow, tx-14, ty-14, tx+14, ty+14)
            self.c.coords(self._arc_tip,      tx-6,  ty-6,  tx+6,  ty+6)
            self.c.itemconfig(self._arc_tip_glow,
                fill=lerp_col(BG, col, 0.5), state="normal")
            self.c.itemconfig(self._arc_tip,
                fill=lerp_col(col, WHITE, 0.75), state="normal")
        else:
            self.c.itemconfig(self._arc_tip,      state="hidden")
            self.c.itemconfig(self._arc_tip_glow, state="hidden")

        # Background glow pulse
        pulse = 0.5 + 0.5 * math.sin(self.phase * 0.4)
        self.c.itemconfig(self._glow_bg,
            fill=lerp_col(lerp_col(BG, P1, 0.04),
                          lerp_col(BG, col, 0.08), pulse))

        # Travelling zone border
        zx1,zy1,zx2,zy2 = self._zx1, self._zy1, self._zx2, self._zy2
        perim = 2*((zx2-zx1)+(zy2-zy1))

        def bpt(d):
            d %= perim
            ww = zx2-zx1; hh = zy2-zy1
            if d < ww: return zx1+d, zy1
            d -= ww
            if d < hh: return zx2, zy1+d
            d -= hh
            if d < ww: return zx2-d, zy2
            d -= ww
            return zx1, zy2-d

        for i, seg in enumerate(self._zborder):
            off = (self.phase*0.28 + i*0.5) % 1.0
            sd  = off * perim
            p1  = bpt(sd)
            p2  = bpt(sd + perim*0.12)
            bright = 0.4 + 0.6*math.sin(self.phase*1.6 + i*math.pi)
            self.c.coords(seg, p1[0],p1[1], p2[0],p2[1])
            self.c.itemconfig(seg, fill=lerp_col(BORDER, col, bright*0.8))

        # Trail
        fade_win  = 0.50
        trail_vis = [(x,y,t) for x,y,t in self.trail if now-t < fade_win]
        for i, dot in enumerate(self._trail_dots):
            if i < len(trail_vis):
                x, y, ts = trail_vis[i]
                age = (now-ts) / fade_win
                r   = max(1, int(8*(1-age)**1.4))
                self.c.coords(dot, x-r,y-r,x+r,y+r)
                self.c.itemconfig(dot,
                    fill=lerp_col(CARD, col, (1-age)**1.8), state="normal")
                self.c.tag_raise(dot)
            else:
                self.c.itemconfig(dot, state="hidden")

        # Cursor
        x, y = self.mx, self.my
        if self._in_zone(x, y):
            p2 = 0.5 + 0.5*math.sin(self.phase*2.5)
            r1 = 16 + p2*6
            r2 = 28 + p2*5
            self.c.coords(self._cur_ring,  x-r1,y-r1,x+r1,y+r1)
            self.c.coords(self._cur_ring2, x-r2,y-r2,x+r2,y+r2)
            self.c.coords(self._cur_dot,   x-4,y-4,x+4,y+4)
            rc = lerp_col(P1, col, p2)
            self.c.itemconfig(self._cur_ring,  outline=rc, state="normal")
            self.c.itemconfig(self._cur_ring2,
                outline=lerp_col(BG, rc, 0.4), state="normal")
            self.c.itemconfig(self._cur_dot, fill=WHITE, state="normal")
            for item in [self._cur_ring2, self._cur_ring, self._cur_dot]:
                self.c.tag_raise(item)
            self.c.itemconfig(self._zone_hint, text="")
        else:
            for item in [self._cur_ring, self._cur_ring2, self._cur_dot]:
                self.c.itemconfig(item, state="hidden")
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
