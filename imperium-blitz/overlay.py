import tkinter as tk
import mss
import pygetwindow as gw
from PIL import Image, ImageChops
import threading
import time
import math
import sys
import json
import os
import ctypes
from collections import deque
from threading import Lock

# --- CONFIGURATION ---
VIEWPORT = {"x1": 14, "y1": 180, "x2": 695, "y2": 705}
TEAMS = {
    "NPC": {"color": "#ffd700", "crossings": 2},
    "PLAYER": {"color": "#00e5ff", "crossings": 2}
}
CONFIG_FILE = "radar_config.json"
THEME = {
    "bg": "#1a1a2e",
    "fg": "#e0e0e0",
    "accent": "#5b7fff",
    "sep": "#2a2a3e",
    "btn_active": "#4a6fff",
    "btn_inactive": "#3a3a4e",
    "btn_stop": "#cc3333",
    "btn_save": "#339933",
    "font": ("Segoe UI", 9),
    "font_sm": ("Segoe UI", 8),
    "font_header": ("Segoe UI", 8, "bold"),
    "font_title": ("Segoe UI", 10, "bold"),
    "font_status": ("Segoe UI", 10, "bold"),
}

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class ImperiumRadar:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Imperium Radar")
        
        # Transparent UI Layer
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_w}x{screen_h}+0+0")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.configure(bg="black")
        
        self.canvas = tk.Canvas(self.root, width=screen_w, height=screen_h, bg="black", highlightthickness=0)
        self.canvas.pack()

        # State
        self.running = True
        self.online = False
        self.win_rect = None
        self.mobs = [] 
        self.fps_counter = 0

        # Control State
        self.is_scanning = True
        self.current_config = self.load_config()
        self.box_left = tk.IntVar(value=self.current_config.get("left", 20))
        self.box_right = tk.IntVar(value=self.current_config.get("right", 20))
        self.box_up = tk.IntVar(value=self.current_config.get("up", 20))
        self.box_down = tk.IntVar(value=self.current_config.get("down", 20))

        # Hitbox (Click Redirection) State
        self.hit_left = tk.IntVar(value=self.current_config.get("hit_l", 10))
        self.hit_right = tk.IntVar(value=self.current_config.get("hit_r", 10))
        self.hit_up = tk.IntVar(value=self.current_config.get("hit_u", 10))
        self.hit_down = tk.IntVar(value=self.current_config.get("hit_d", 10))

        self.show_visuals = tk.BooleanVar(value=self.current_config.get("show_v", True))
        self.enable_redirect = tk.BooleanVar(value=self.current_config.get("red_en", True))
        self.target_off_x = tk.IntVar(value=self.current_config.get("off_x", 0))
        self.target_off_y = tk.IntVar(value=self.current_config.get("off_y", 0))
        self.mouse_speed = tk.IntVar(value=self.current_config.get("m_speed", 1))
        self.redirect_cooldown = tk.IntVar(value=self.current_config.get("m_cool", 50))
        
        # Performance/Stability State
        self.last_redirect_time = 0
        self.canvas_objects = {} # {mob_id: {'dot', 'hit', 'txt'}}
        self.hitbox_map = {}     # {canvas_id: mob_id}
        self.panel_collapsed = False

        # Controls UI
        self.setup_ui()

        # Handlers
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        self.root.bind("<Escape>", lambda e: self.shutdown())
        self.canvas.bind("<Button-1>", self.on_click)
        
        # Start Threads
        self.thread = threading.Thread(target=self.scan_loop, daemon=True)
        self.thread.start()
        self.update_ui()

    def setup_ui(self):
        self.controls_frame = tk.Frame(self.canvas, bg=THEME["bg"], padx=8, pady=8)
        self.canvas.create_window(10, 80, window=self.controls_frame, anchor="nw")

        # Header row: title + collapse button
        header = tk.Frame(self.controls_frame, bg=THEME["bg"])
        header.pack(fill="x", pady=(0, 4))
        tk.Label(header, text="Imperium Radar", fg=THEME["accent"], bg=THEME["bg"], font=THEME["font_title"]).pack(side="left")
        self.btn_collapse = tk.Button(header, text="▲", command=self.toggle_collapse, fg=THEME["fg"], bg=THEME["bg"], bd=0, font=THEME["font_sm"], activebackground=THEME["bg"], activeforeground=THEME["accent"])
        self.btn_collapse.pack(side="right")

        # START/STOP button (always visible)
        self.btn_toggle = tk.Button(self.controls_frame, text="STOP", command=self.toggle_scan, bg=THEME["btn_stop"], fg="white", font=THEME["font_header"], width=8, bd=0, activebackground="#aa2222")
        self.btn_toggle.pack(pady=(0, 4))

        # Collapsible body
        self.panel_body = tk.Frame(self.controls_frame, bg=THEME["bg"])
        self.panel_body.pack(fill="x")

        # --- Checkbuttons ---
        self._sep(self.panel_body)
        for text, var in [("Visuales", self.show_visuals), ("Click Redir", self.enable_redirect)]:
            tk.Checkbutton(self.panel_body, text=text, variable=var, fg=THEME["fg"], bg=THEME["bg"], selectcolor=THEME["bg"], activebackground=THEME["bg"], activeforeground=THEME["accent"], font=THEME["font_sm"]).pack(anchor="w")

        # --- Dimensiones ---
        self._section(self.panel_body, "Dimensiones")
        self._grid2x2(self.panel_body, [("Izq", self.box_left), ("Der", self.box_right), ("Arr", self.box_up), ("Aba", self.box_down)])

        # --- Hitbox ---
        self._section(self.panel_body, "Hitbox")
        self._grid2x2(self.panel_body, [("H-I", self.hit_left), ("H-D", self.hit_right), ("H-Ar", self.hit_up), ("H-Ab", self.hit_down)])

        # --- Puntería ---
        self._section(self.panel_body, "Puntería")
        self._spinrow(self.panel_body, "X", self.target_off_x, -50, 50)
        self._spinrow(self.panel_body, "Y", self.target_off_y, -50, 50)

        # --- Mouse ---
        self._section(self.panel_body, "Mouse")
        self._spinrow(self.panel_body, "Velocidad", self.mouse_speed, 1, 20)
        self._spinrow(self.panel_body, "Cooldown", self.redirect_cooldown, 0, 1000)

        # --- Action buttons ---
        self._sep(self.panel_body)
        btn_row = tk.Frame(self.panel_body, bg=THEME["bg"])
        btn_row.pack(fill="x", pady=4)
        self.btn_save = tk.Button(btn_row, text="GUARDAR", command=self.save_config, bg=THEME["btn_save"], fg="white", font=THEME["font_header"], bd=0, width=8, activebackground="#227722")
        self.btn_save.pack(side="left", padx=(0, 4))
        tk.Button(btn_row, text="SALIR", command=self.shutdown, bg=THEME["btn_inactive"], fg=THEME["fg"], font=THEME["font_header"], bd=0, width=8, activebackground="#555").pack(side="left")

        # Status label
        self.status_label = self.canvas.create_text(20, 60, text="INIT", fill=THEME["fg"], anchor="w", font=THEME["font_status"])

    def _sep(self, parent):
        tk.Frame(parent, bg=THEME["sep"], height=1).pack(fill="x", pady=4)

    def _section(self, parent, title):
        self._sep(parent)
        tk.Label(parent, text=title, fg=THEME["accent"], bg=THEME["bg"], font=THEME["font_header"]).pack(anchor="w")

    def _grid2x2(self, parent, items):
        for i in range(0, len(items), 2):
            row = tk.Frame(parent, bg=THEME["bg"])
            row.pack(fill="x")
            for label, var in items[i:i+2]:
                tk.Label(row, text=label, fg=THEME["fg"], bg=THEME["bg"], font=THEME["font_sm"], width=4, anchor="e").pack(side="left")
                tk.Spinbox(row, from_=0, to=150, textvariable=var, width=3, font=THEME["font_sm"], bg=THEME["bg"], fg=THEME["fg"], buttonbackground=THEME["btn_inactive"], insertbackground=THEME["fg"]).pack(side="left", padx=(0, 6))

    def _spinrow(self, parent, label, var, lo, hi):
        row = tk.Frame(parent, bg=THEME["bg"])
        row.pack(fill="x")
        tk.Label(row, text=label, fg=THEME["fg"], bg=THEME["bg"], font=THEME["font_sm"]).pack(side="left")
        tk.Spinbox(row, from_=lo, to=hi, textvariable=var, width=4, font=THEME["font_sm"], bg=THEME["bg"], fg=THEME["fg"], buttonbackground=THEME["btn_inactive"], insertbackground=THEME["fg"]).pack(side="right")

    def toggle_collapse(self):
        self.panel_collapsed = not self.panel_collapsed
        if self.panel_collapsed:
            self.panel_body.pack_forget()
            self.btn_collapse.config(text="▼")
        else:
            self.panel_body.pack(fill="x")
            self.btn_collapse.config(text="▲")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: return json.load(f)
            except: pass
        return {"left": 20, "right": 20, "up": 20, "down": 20, "hit_l": 10, "hit_r": 10, "hit_u": 10, "hit_d": 10, "show_v": True, "red_en": True, "off_x": 0, "off_y": 0, "m_speed": 1, "m_cool": 50}

    def save_config(self):
        config = {
            "left": self.box_left.get(), "right": self.box_right.get(), "up": self.box_up.get(), "down": self.box_down.get(),
            "hit_l": self.hit_left.get(), "hit_r": self.hit_right.get(), "hit_u": self.hit_up.get(), "hit_d": self.hit_down.get(),
            "show_v": self.show_visuals.get(), "red_en": self.enable_redirect.get(), "off_x": self.target_off_x.get(), "off_y": self.target_off_y.get(),
            "m_speed": self.mouse_speed.get(), "m_cool": self.redirect_cooldown.get()
        }
        with open(CONFIG_FILE, "w") as f: json.dump(config, f)
        self.btn_save.config(text="LISTO!", bg="white", fg=THEME["bg"])
        self.root.after(1000, lambda: self.btn_save.config(text="GUARDAR", bg=THEME["btn_save"], fg="white"))

    def on_click(self, event):
        if not self.online or not self.win_rect or not self.enable_redirect.get(): return
        
        # Use canvas search for precision
        items = self.canvas.find_overlapping(event.x-1, event.y-1, event.x+1, event.y+1)
        for item in items:
            mob_id = self.hitbox_map.get(item)
            if mob_id:
                target_mob = next((m for m in self.mobs if id(m) == mob_id), None)
                if target_mob:
                    wx, wy = self.win_rect[0], self.win_rect[1]
                    vx, vy = wx + VIEWPORT["x1"], wy + VIEWPORT["y1"]
                    
                    # Target is BOX CENTER + CUSTOM OFFSET
                    l, r = self.box_left.get(), self.box_right.get()
                    u, d = self.box_up.get(), self.box_down.get()
                    
                    tx = vx + target_mob['cx'] + (r - l) // 2 + self.target_off_x.get()
                    ty = vy + target_mob['cy'] + (d - u) // 2 + self.target_off_y.get()
                    
                    threading.Thread(target=self.redirect_click, args=(tx, ty), daemon=True).start()
                    return

    def redirect_click(self, x, y):
        # Anti-spam cooldown check
        now = time.time()
        if now - self.last_redirect_time < (self.redirect_cooldown.get() / 1000.0):
            return
        self.last_redirect_time = now
        
        try:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            if not (0 <= x <= sw and 0 <= y <= sh): return

            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd: return
            
            old_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, old_style | WS_EX_TRANSPARENT)
            
            speed = self.mouse_speed.get()
            if speed <= 1:
                ctypes.windll.user32.SetCursorPos(x, y)
            else:
                # Smooth movement
                pt = POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                start_x, start_y = pt.x, pt.y
                
                # Number of steps (tuned for feel)
                steps = speed * 2
                for i in range(1, steps + 1):
                    # Linear interpolation
                    cur_x = int(start_x + (x - start_x) * i / steps)
                    cur_y = int(start_y + (y - start_y) * i / steps)
                    ctypes.windll.user32.SetCursorPos(cur_x, cur_y)
                    time.sleep(0.001) # Shortest possible delay
            
            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, old_style)
        except Exception as e: print(f"Redirect error: {e}")

    def process_image(self, img):
        try:
            w, h = img.size
            r, g, b = img.split()
            max_rg = ImageChops.lighter(r, g)
            diff_blue = ImageChops.subtract(b, max_rg)
            mask_player = diff_blue.point(lambda x: 255 if x > 25 else 0, mode='1')
            lum = img.convert("L")
            mask_bright = lum.point(lambda x: 255 if x > 105 else 0, mode='1')
            diff_rg = ImageChops.difference(r, g)
            diff_rb = ImageChops.difference(r, b)
            diff_gb = ImageChops.difference(g, b)
            sat = ImageChops.add(ImageChops.add(diff_rg, diff_rb), diff_gb)
            mask_low_sat = sat.point(lambda x: 255 if x < 50 else 0, mode='1')
            mask_npc = ImageChops.multiply(mask_bright, mask_low_sat)

            new_cands = []
            pix_p, pix_n = mask_player.load(), mask_npc.load()
            visited = set()
            
            # Regions
            regions = [{"rect": (0, 0, w, h), "step": 10}]
            for m in self.mobs:
                regions.append({"rect": (max(0, m['cx']-40), max(0, m['cy']-30), min(w, m['cx']+40), min(h, m['cy']+30)), "step": 3})

            for reg in regions:
                rx1, ry1, rx2, ry2 = reg["rect"]
                for y in range(ry1, ry2, reg["step"]):
                    for x in range(rx1, rx2, reg["step"]):
                        if (x, y) in visited: continue
                        t_type = "NPC" if pix_n[x,y] > 0 else "PLAYER" if pix_p[x,y] > 0 else None
                        if t_type:
                            cpix = pix_n if t_type == "NPC" else pix_p
                            visited.add((x, y))
                            q = deque([(x, y)])
                            min_x, max_x, min_y, max_y, count = x, x, y, y, 0
                            while q:
                                cx, cy = q.popleft(); count += 1
                                min_x, max_x = min(min_x, cx), max(max_x, cx)
                                min_y, max_y = min(min_y, cy), max(max_y, cy)
                                for dx, dy in [(-3,0), (3,0), (0,-2), (0,2), (-2,-2), (2,2)]:
                                    nx, ny = cx+dx, cy+dy
                                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited and cpix[nx, ny] > 0:
                                        visited.add((nx, ny)); q.append((nx, ny))
                                if count > 1200: break
                            cw, ch = max_x - min_x, max_y - min_y
                            if 12 < cw < 250 and 6 < ch < 30 and (cw/ch) >= 1.2:
                                crossings, last = 0, 0
                                for sx in range(min_x, max_x):
                                    if cpix[sx, min_y+ch//2] > 0 and last == 0: crossings += 1
                                    last = cpix[sx, min_y+ch//2]
                                if crossings >= 2: new_cands.append({'cx': min_x+cw//2, 'cy': min_y+ch//2, 'type': t_type})
            
            # Cleanup
            mask_player.close(); mask_npc.close(); r.close(); g.close(); b.close(); lum.close()
            return self.merge_candidates(new_cands)
        except Exception as e: print(f"Proc error: {e}"); return []

    def merge_candidates(self, candidates):
        if not candidates: return []
        candidates.sort(key=lambda c: (c['type'], c['cy'] // 10, c['cx']))
        merged, cluster = [], [candidates[0]]
        for i in range(1, len(candidates)):
            cand, prev = candidates[i], cluster[-1]
            if cand['type'] == prev['type'] and abs(cand['cy']-prev['cy']) < 12 and (cand['cx']-prev['cx']) < 55: cluster.append(cand)
            else: merged.append(self.resolve(cluster)); cluster = [cand]
        if cluster: merged.append(self.resolve(cluster))
        return merged

    def resolve(self, cluster):
        x1, x2 = min(c['cx'] for c in cluster), max(c['cx'] for c in cluster)
        y = sum(c['cy'] for c in cluster) // len(cluster)
        return {'cx': (x1+x2)//2, 'cy': y, 'type': cluster[0]['type'], 'ttl': 8}

    def update_mobs(self, candidates):
        survivors = [m for m in self.mobs if (m.update({'ttl': m['ttl']-1}) or True) and m['ttl'] > 0]
        final, matched = [], set()
        for mob in survivors:
            best, min_d = -1, 40
            for i, c in enumerate(candidates):
                if i not in matched and c['type'] == mob['type']:
                    d = math.sqrt((mob['cx']-c['cx'])**2 + (mob['cy']-c['cy'])**2)
                    if d < min_d: min_d, best = d, i
            if best != -1:
                mob.update({'cx': candidates[best]['cx'], 'cy': candidates[best]['cy'], 'ttl': 8})
                matched.add(best); final.append(mob)
            else: final.append(mob)
        for i, c in enumerate(candidates):
            if i not in matched and not any(math.sqrt((c['cx']-m['cx'])**2 + (c['cy']-m['cy'])**2) < 20 for m in final): final.append(c)
        self.mobs = final[:50]

    def scan_loop(self):
        with mss.mss() as sct:
            while self.running:
                if not self.is_scanning: time.sleep(0.5); continue
                self.fps_counter += 1
                if not self.online or self.fps_counter % 30 == 0:
                    wins = gw.getWindowsWithTitle("Imperium Classic 1.20")
                    if wins and not wins[0].isMinimized:
                        self.win_rect = (wins[0].left, wins[0].top, wins[0].width, wins[0].height)
                        self.online = True
                    else: self.online = False; self.mobs = []
                if self.online:
                    mon = {"left": int(self.win_rect[0]+VIEWPORT["x1"]), "top": int(self.win_rect[1]+VIEWPORT["y1"]), "width": int(VIEWPORT["x2"]-VIEWPORT["x1"]), "height": int(VIEWPORT["y2"]-VIEWPORT["y1"])}
                    try:
                        shot = sct.grab(mon)
                        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                        self.update_mobs(self.process_image(img))
                    except: pass
                time.sleep(0.01)

    def update_ui(self):
        if not self.running: return
        if self.online and self.win_rect:
            self.canvas.itemconfigure(self.status_label, text="RADAR ACTIVO", fill="#00ff00")
            vx, vy = self.win_rect[0] + VIEWPORT["x1"], self.win_rect[1] + VIEWPORT["y1"]
            active_ids, new_hit_map = set(), {}
            l, r, u, d = self.box_left.get(), self.box_right.get(), self.box_up.get(), self.box_down.get()
            hl, hr, hu, hd = self.hit_left.get(), self.hit_right.get(), self.hit_up.get(), self.hit_down.get()
            show, redir = self.show_visuals.get(), self.enable_redirect.get()
            for mob in self.mobs:
                mid = id(mob)
                active_ids.add(mid)
                cx, cy = vx + mob['cx'], vy + mob['cy']
                color = TEAMS[mob['type']]["color"]
                if mid not in self.canvas_objects:
                    self.canvas_objects[mid] = {
                        'hit': self.canvas.create_rectangle(0,0,0,0, outline="", tag="overlay"),
                        'dot': self.canvas.create_oval(0,0,0,0, fill="", outline="", tag="overlay"),
                        'txt': self.canvas.create_text(0,0, text="", font=("Small Fonts", 7), tag="overlay")
                    }
                objs = self.canvas_objects[mid]
                if redir:
                    self.canvas.coords(objs['hit'], cx-(l+hl), cy-(u+hu), cx+(r+hr), cy+(d+hd))
                    self.canvas.itemconfigure(objs['hit'], fill="#010101", stipple="gray12")
                    new_hit_map[objs['hit']] = mid
                else:
                    self.canvas.coords(objs['hit'], 0,0,0,0)

                if show:
                    # Dot: 6px diameter circle at entity center
                    self.canvas.coords(objs['dot'], cx-3, cy-3, cx+3, cy+3)
                    self.canvas.itemconfigure(objs['dot'], fill=color, outline=color)
                    # Label: above the dot
                    self.canvas.coords(objs['txt'], cx, cy-8)
                    self.canvas.itemconfigure(objs['txt'], text=mob['type'], fill=color)
                else:
                    self.canvas.coords(objs['dot'], 0,0,0,0)
                    self.canvas.coords(objs['txt'], 0,0)
            for mid in list(self.canvas_objects.keys()):
                if mid not in active_ids:
                    for oid in self.canvas_objects[mid].values(): self.canvas.delete(oid)
                    del self.canvas_objects[mid]
            self.hitbox_map = new_hit_map
        else:
            self.canvas.itemconfigure(self.status_label, text="ESPERANDO...", fill="#cc3333")
        self.root.after(20, self.update_ui)

    def toggle_scan(self):
        self.is_scanning = not self.is_scanning
        self.btn_toggle.config(text="STOP" if self.is_scanning else "START", bg=THEME["btn_stop"] if self.is_scanning else THEME["btn_active"])
        if not self.is_scanning: self.mobs = []; self.canvas.delete("overlay"); self.canvas_objects = {}

    def shutdown(self):
        self.running = False; self.root.destroy(); sys.exit(0)

if __name__ == "__main__":
    ImperiumRadar().root.mainloop()