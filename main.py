"""
Daily Habit Tracker
-------------------
Features
  * Add as many habits as you like, and delete the ones you no longer want
  * Five daily prayers with editable times, tick-off and a "x/5 prayed" counter
  * Tick box on the LEFT of every habit
  * Weekly report: table, daily completion chart and summary (browse past weeks)
  * Optional time for every habit of your own
  * A flower that grows and blooms as you complete your day (11 to choose from)
  * Light theme (off-white + terracotta) and Dark theme (navy + neon green)

Run:  python main.py
Data is stored next to this file in habits.db
"""

import math
import re
import sqlite3
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

DB_PATH = Path(__file__).parent / "habits.db"

# --------------------------------------------------------------------------- #
#  THEMES  (change the hex codes here to restyle the whole app)
# --------------------------------------------------------------------------- #
LIGHT = dict(
    bg="#FAF7F2",        # off white
    card="#F1ECE4",
    text="#111111",      # black
    muted="#6B645C",
    accent="#C8643C",    # terracotta
    accent_hover="#B0522D",
    border="#DDD5CA",
    on_accent="#FFFFFF",
    soil="#B58B63",
    stem="#3E8E41",
    leaf="#5DB85C",
)
DARK = dict(
    bg="#0F172A",        # deep navy
    card="#1A2540",
    text="#E8ECF4",
    muted="#8A94AB",
    accent="#39FF14",    # neon green  (try amber: "#FFB000")
    accent_hover="#2BD60F",  # (amber hover: "#E09B00")
    border="#2A3556",
    on_accent="#0F172A",
    soil="#7A5A3C",
    stem="#2FA84F",
    leaf="#3BBF5A",
)


def pair(key):
    """(light, dark) colour tuple - CustomTkinter switches automatically."""
    return (LIGHT[key], DARK[key])


DEFAULT_PRAYERS = [
    ("Fajr", "05:25"),
    ("Dhuhr", "12:10"),
    ("Asr", "15:20"),
    ("Maghrib", "17:35"),
    ("Isha", "19:00"),
]
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


# --------------------------------------------------------------------------- #
#  FLOWERS  (drawn with plain canvas shapes - no image files needed)
# --------------------------------------------------------------------------- #
CANVAS_W, CANVAS_H = 270, 300
GROUND_Y = CANVAS_H - 34
STEM_FULL = 150

# rings = (petal count, length factor, angle offset in degrees, colour)
FLOWERS = {
    "Jasmine": dict(  # national flower of Pakistan
        rings=[(5, 1.0, 0, "#FFFFFF"), (5, 0.6, 36, "#F8F4E9")],
        length=58, width=0.62, shape="pointed", outline="#D9D2BE",
        center="#F2C94C", center_r=6, base=0.6,
    ),
    "Rose": dict(
        rings=[(7, 1.0, 0, "#A50F33"), (6, 0.78, 25, "#C41A44"),
               (5, 0.58, 10, "#DD3860"), (4, 0.38, 40, "#F26A8D")],
        length=56, width=0.95, shape="round", outline="#7E0B26",
        center="#7E0B26", center_r=4, base=0.5,
    ),
    "Sunflower": dict(
        rings=[(16, 1.0, 0, "#F5B700"), (16, 0.9, 11, "#FFD43B")],
        length=58, width=0.34, shape="pointed", outline="#C98F00",
        center="#6B4423", center_r=24, base=0.7, seeds=True,
    ),
    "Lotus": dict(
        rings=[(8, 1.0, 0, "#F27BA6"), (8, 0.82, 22, "#F59BBD"),
               (6, 0.6, 10, "#F9BCD3")],
        length=62, width=0.55, shape="pointed", outline="#D45A88",
        center="#F4D03F", center_r=9, base=0.5, vein="#E0608F",
    ),
    "Cherry Blossom": dict(
        rings=[(5, 1.0, 0, "#FFC2D7"), (5, 0.5, 36, "#FFDCE8")],
        length=50, width=0.95, shape="round", outline="#F29BB8",
        center="#E0457B", center_r=5, base=0.4,
    ),
    "Daisy": dict(
        rings=[(21, 1.0, 0, "#FFFFFF")],
        length=56, width=0.2, shape="oval", outline="#D5D5D5",
        center="#FFCE1B", center_r=14, base=0.7,
    ),
    "Lily": dict(
        rings=[(6, 1.0, 0, "#FF8A3D"), (3, 0.7, 60, "#FFA866")],
        length=68, width=0.46, shape="pointed", outline="#C9561A",
        center="#7A2E0E", center_r=5, base=0.4, vein="#C9561A",
    ),
    "Marigold": dict(
        rings=[(12, 1.0, 0, "#F08A00"), (12, 0.82, 15, "#F5A31A"),
               (10, 0.62, 0, "#FBB93F"), (8, 0.42, 20, "#FFCB66")],
        length=52, width=0.5, shape="round", outline="#C26A00",
        center="#B85F00", center_r=4, base=0.5,
    ),
    "Hibiscus": dict(
        rings=[(5, 1.0, 0, "#E5173F"), (5, 0.55, 36, "#FF4D6D")],
        length=62, width=1.0, shape="round", outline="#A60F2D",
        center="#FFD166", center_r=6, base=0.3,
    ),
    "Tulip": dict(
        kind="tulip", front="#FF5D73", side="#E63946", side2="#C1121F",
        outline="#8E0E1B",
    ),
    "Lavender": dict(
        kind="spike", florets=16,
        shades=["#9B7EDE", "#B49BE8", "#8A63D2"], outline="#6F4BB5",
    ),
}


def _petal(cx, cy, theta, r0, length, width, shape):
    """Polygon points of one petal starting r0 away from (cx, cy)."""
    side_a, side_b = [], []
    steps = 8
    for i in range(steps + 1):
        t = i / steps
        if shape == "pointed":
            w = math.sin(math.pi * t) ** 1.1
        elif shape == "round":
            w = math.sin(math.pi * t) ** 0.55
        else:
            w = math.sin(math.pi * t) ** 0.8
        r = r0 + t * length
        off = w * width / 2
        side_a.append((r, off))
        side_b.append((r, -off))
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    pts = []
    for r, off in side_a + side_b[::-1]:
        pts.append(cx + r * cos_t - off * sin_t)
        pts.append(cy + r * sin_t + off * cos_t)
    return pts


def draw_flower(cv, name, p, pal):
    """Draw flower `name` on canvas `cv`. p = 0..1 growth/bloom progress."""
    cv.delete("all")
    p = max(0.0, min(1.0, p))
    cx = CANVAS_W // 2
    spec = FLOWERS[name]
    stem, leaf = pal["stem"], pal["leaf"]

    cv.create_oval(cx - 74, GROUND_Y - 9, cx + 74, GROUND_Y + 20,
                   fill=pal["soil"], outline="")

    if p <= 0:  # nothing done yet: a tiny sprout
        top_y = GROUND_Y - 16
        cv.create_line(cx, GROUND_Y, cx, top_y, fill=stem, width=4,
                       capstyle="round")
        for side in (-1, 1):
            cv.create_polygon(cx, top_y, cx + side * 18, top_y - 10,
                              cx + side * 8, top_y + 4, smooth=True,
                              fill=leaf, outline=stem)
        return

    grow = min(1.0, p / 0.35)                 # stem + bud
    bloom = max(0.0, (p - 0.35) / 0.65)       # petals opening
    stem_h = STEM_FULL * (0.12 + 0.88 * grow)
    top_y = GROUND_Y - stem_h
    cv.create_line(cx, GROUND_Y, cx, top_y, fill=stem, width=5,
                   capstyle="round")

    leaf_s = min(1.0, p / 0.3)
    for side, frac in ((-1, 0.30), (1, 0.52)):
        ly = GROUND_Y - stem_h * frac
        ln = 40 * leaf_s
        cv.create_polygon(
            cx, ly, cx + side * ln * 0.5, ly - 17 * leaf_s,
            cx + side * ln, ly - 8 * leaf_s, cx + side * ln * 0.5,
            ly + 5 * leaf_s, smooth=True, fill=leaf, outline=stem)

    kind = spec.get("kind", "radial")

    if kind == "spike":                       # lavender
        total = spec["florets"]
        n = max(1, round(total * p))
        base_y = top_y + 12
        top = base_y - 100 * ((n - 1) / (total - 1))
        cv.create_line(cx, base_y, cx, top, fill=stem, width=4)
        for i in range(n):
            t = i / (total - 1)
            y = base_y - 100 * t
            side = -1 if i % 2 == 0 else 1
            rx, ry = 9 - 4 * t, 6 - 2 * t
            x = cx + side * (7 - 3 * t)
            cv.create_oval(x - rx, y - ry, x + rx, y + ry,
                           fill=spec["shades"][i % 3], outline=spec["outline"])

    elif kind == "tulip":
        s = 0.35 + 0.65 * bloom
        spread = 6 + 34 * bloom               # petals open outwards
        base_y = top_y + 8
        for ang, color in ((-spread, spec["side"]), (spread, spec["side2"]),
                           (0, spec["front"])):
            theta = math.radians(-90 + ang)
            pts = _petal(cx, base_y, theta, 0, 72 * s, 42 * s, "oval")
            cv.create_polygon(pts, smooth=True, fill=color,
                              outline=spec["outline"])

    else:                                     # radial flowers
        s = 0.18 + 0.82 * bloom
        crs = spec["center_r"] * (0.3 + 0.7 * s)
        r0 = crs * spec["base"]
        cv.create_oval(cx - 8, top_y - 8, cx + 8, top_y + 8,
                       fill=leaf, outline=stem)           # green bud base
        for ring_no, (n, lf, off, color) in enumerate(spec["rings"]):
            length = spec["length"] * lf * s
            width = max(4, length * spec["width"])
            for i in range(n):
                theta = math.radians(off) + i * 2 * math.pi / n - math.pi / 2
                pts = _petal(cx, top_y, theta, r0, length, width,
                             spec["shape"])
                cv.create_polygon(pts, smooth=True, fill=color,
                                  outline=spec["outline"])
                if ring_no == 0 and spec.get("vein"):
                    cv.create_line(
                        cx + r0 * math.cos(theta), top_y + r0 * math.sin(theta),
                        cx + (r0 + length * 0.8) * math.cos(theta),
                        top_y + (r0 + length * 0.8) * math.sin(theta),
                        fill=spec["vein"])
        cv.create_oval(cx - crs, top_y - crs, cx + crs, top_y + crs,
                       fill=spec["center"], outline=spec["outline"])
        if spec.get("seeds") and s > 0.5:
            for k in range(1, 56):
                r = crs * 0.9 * math.sqrt(k / 55)
                a = k * 2.39996
                x, y = cx + r * math.cos(a), top_y + r * math.sin(a)
                cv.create_oval(x - 1.7, y - 1.7, x + 1.7, y + 1.7,
                               fill="#3A2410", outline="")

    if p >= 0.995:                            # fully bloomed: sparkles
        for x, y in ((48, 64), (222, 84), (36, 168), (234, 176), (135, 20)):
            cv.create_text(x, y, text="✦", fill=pal["accent"],
                           font=("Segoe UI Symbol", 13))


# --------------------------------------------------------------------------- #
#  DATABASE
# --------------------------------------------------------------------------- #
class Database:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.executescript(
            """
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'custom',
                prayer_time TEXT,
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS logs (
                habit_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                PRIMARY KEY (habit_id, day)
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        has_prayers = self.con.execute(
            "SELECT COUNT(*) FROM habits WHERE kind='prayer'"
        ).fetchone()[0]
        if not has_prayers:
            today = date.today().isoformat()
            for name, t in DEFAULT_PRAYERS:
                self.con.execute(
                    "INSERT INTO habits(name, kind, prayer_time, created) "
                    "VALUES (?, 'prayer', ?, ?)",
                    (name, t, today),
                )
            self.con.commit()

    # habits
    def habits(self):
        rows = self.con.execute(
            "SELECT id, name, kind, prayer_time, created FROM habits "
            "ORDER BY CASE kind WHEN 'prayer' THEN 0 ELSE 1 END, "
            "CASE WHEN prayer_time IS NULL THEN 1 ELSE 0 END, prayer_time, id"
        ).fetchall()
        return [
            dict(id=r[0], name=r[1], kind=r[2], time=r[3], created=r[4])
            for r in rows
        ]

    def name_exists(self, name):
        r = self.con.execute(
            "SELECT 1 FROM habits WHERE LOWER(name)=LOWER(?)", (name,)
        ).fetchone()
        return r is not None

    def add_habit(self, name, time=None):
        self.con.execute(
            "INSERT INTO habits(name, kind, prayer_time, created) "
            "VALUES (?, 'custom', ?, ?)",
            (name, time, date.today().isoformat()),
        )
        self.con.commit()

    def delete_habit(self, habit_id):
        self.con.execute("DELETE FROM logs WHERE habit_id=?", (habit_id,))
        self.con.execute(
            "DELETE FROM habits WHERE id=? AND kind='custom'", (habit_id,)
        )
        self.con.commit()

    def set_time(self, habit_id, t):
        self.con.execute(
            "UPDATE habits SET prayer_time=? WHERE id=?", (t, habit_id)
        )
        self.con.commit()

    # logs
    def done_on(self, day_iso):
        rows = self.con.execute(
            "SELECT habit_id FROM logs WHERE day=?", (day_iso,)
        ).fetchall()
        return {r[0] for r in rows}

    def done_between(self, start_iso, end_iso):
        rows = self.con.execute(
            "SELECT habit_id, day FROM logs WHERE day BETWEEN ? AND ?",
            (start_iso, end_iso),
        ).fetchall()
        return {(r[0], r[1]) for r in rows}

    def set_done(self, habit_id, day_iso, done):
        if done:
            self.con.execute(
                "INSERT OR IGNORE INTO logs(habit_id, day) VALUES (?, ?)",
                (habit_id, day_iso),
            )
        else:
            self.con.execute(
                "DELETE FROM logs WHERE habit_id=? AND day=?",
                (habit_id, day_iso),
            )
        self.con.commit()

    # settings
    def get_setting(self, key, default=None):
        r = self.con.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return r[0] if r else default

    def set_setting(self, key, value):
        self.con.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
            (key, value),
        )
        self.con.commit()


# --------------------------------------------------------------------------- #
#  APP
# --------------------------------------------------------------------------- #
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.db = Database(DB_PATH)

        saved = self.db.get_setting("theme", "Light")
        ctk.set_appearance_mode(saved)

        self.title("Daily Habit Tracker")
        self.geometry("1060x780")
        self.minsize(920, 660)
        self.configure(fg_color=pair("bg"))

        self.f_title = ctk.CTkFont(size=24, weight="bold")
        self.f_head = ctk.CTkFont(size=17, weight="bold")
        self.f_body = ctk.CTkFont(size=15)
        self.f_small = ctk.CTkFont(size=12)

        self.week_offset = 0          # 0 = week ending today
        self.current_day = date.today()
        self.chart_canvas = None

        saved_flower = self.db.get_setting("flower", "Jasmine")
        self.flower_name = saved_flower if saved_flower in FLOWERS else "Jasmine"
        self.flower_shown = 0.0       # what is drawn right now
        self.flower_target = 0.0      # where the animation is heading
        self.flower_job = None

        self._build_header()
        self._build_today_page()
        self._build_weekly_page()
        self.show_page("today")
        self.after(60_000, self._minute_tick)

    # ------------------------------------------------------------------ #
    #  helpers
    # ------------------------------------------------------------------ #
    def card(self, parent, **kw):
        return ctk.CTkFrame(
            parent, fg_color=pair("card"), corner_radius=14,
            border_width=1, border_color=pair("border"), **kw
        )

    def button(self, parent, text, command, **kw):
        opts = dict(
            fg_color=pair("accent"), hover_color=pair("accent_hover"),
            text_color=pair("on_accent"), corner_radius=10, font=self.f_body,
            height=36,
        )
        opts.update(kw)
        return ctk.CTkButton(parent, text=text, command=command, **opts)

    def label(self, parent, text, font=None, muted=False, **kw):
        return ctk.CTkLabel(
            parent, text=text, font=font or self.f_body,
            text_color=pair("muted" if muted else "text"), **kw
        )

    @staticmethod
    def palette():
        return DARK if ctk.get_appearance_mode() == "Dark" else LIGHT

    # ------------------------------------------------------------------ #
    #  header + page switching
    # ------------------------------------------------------------------ #
    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(18, 6))

        left = ctk.CTkFrame(head, fg_color="transparent")
        left.pack(side="left")
        self.label(left, "Daily Habit Tracker", self.f_title).pack(anchor="w")
        self.date_label = self.label(left, "", muted=True)
        self.date_label.pack(anchor="w")

        self.theme_switch = ctk.CTkSwitch(
            head, text="Dark mode", font=self.f_body,
            text_color=pair("text"),
            progress_color=pair("accent"),
            button_color=pair("text"), button_hover_color=pair("muted"),
            fg_color=pair("border"),
            command=self.on_theme_switch,
        )
        self.theme_switch.pack(side="right")
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=24, pady=(6, 8))
        self.btn_today = ctk.CTkButton(
            nav, text="Today", width=140, height=36, corner_radius=10,
            font=self.f_body, command=lambda: self.show_page("today"),
        )
        self.btn_today.pack(side="left", padx=(0, 8))
        self.btn_week = ctk.CTkButton(
            nav, text="Weekly Report", width=160, height=36, corner_radius=10,
            font=self.f_body, command=lambda: self.show_page("week"),
        )
        self.btn_week.pack(side="left")

        self.page_holder = ctk.CTkFrame(self, fg_color="transparent")
        self.page_holder.pack(fill="both", expand=True, padx=24, pady=(0, 18))

        self._update_date_label()

    def _update_date_label(self):
        self.date_label.configure(
            text=date.today().strftime("%A, %d %B %Y")
        )

    def show_page(self, name):
        self.page = name
        self.today_page.pack_forget()
        self.week_page.pack_forget()
        active = dict(
            fg_color=pair("accent"), hover_color=pair("accent_hover"),
            text_color=pair("on_accent"),
        )
        inactive = dict(
            fg_color=pair("card"), hover_color=pair("border"),
            text_color=pair("text"),
        )
        if name == "today":
            self.today_page.pack(fill="both", expand=True)
            self.btn_today.configure(**active)
            self.btn_week.configure(**inactive)
            self.refresh_today()
        else:
            self.week_page.pack(fill="both", expand=True)
            self.btn_week.configure(**active)
            self.btn_today.configure(**inactive)
            self.refresh_weekly()

    def on_theme_switch(self):
        mode = "Dark" if self.theme_switch.get() else "Light"
        ctk.set_appearance_mode(mode)
        self.db.set_setting("theme", mode)
        self._paint_flower()
        self.after(80, self._paint_flower)
        self.after(80, self.refresh_weekly)   # redraw chart in new colours

    def _minute_tick(self):
        if date.today() != self.current_day:      # midnight rollover
            self.current_day = date.today()
            self._update_date_label()
            self.week_offset = 0
        if self.page == "today":
            self.refresh_today()
        self.after(60_000, self._minute_tick)

    # ------------------------------------------------------------------ #
    #  TODAY page
    # ------------------------------------------------------------------ #
    def _build_today_page(self):
        self.today_page = ctk.CTkFrame(self.page_holder, fg_color="transparent")

        self._build_flower_card(self.today_page)      # right side

        left = ctk.CTkFrame(self.today_page, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        add = self.card(left)
        add.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(add, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        entry_style = dict(
            height=38, font=self.f_body, corner_radius=10,
            fg_color=pair("bg"), border_color=pair("border"),
            text_color=pair("text"), placeholder_text_color=pair("muted"),
        )
        self.new_entry = ctk.CTkEntry(
            inner, placeholder_text="Write your own habit (e.g. Read Quran 1 page)",
            **entry_style,
        )
        self.new_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.new_time = ctk.CTkEntry(
            inner, width=100, placeholder_text="HH:MM", justify="center",
            **entry_style,
        )
        self.new_time.pack(side="left", padx=(0, 8))
        self.new_entry.bind("<Return>", lambda e: self.add_habit())
        self.new_time.bind("<Return>", lambda e: self.add_habit())
        self.button(inner, "+ Add", self.add_habit, width=80).pack(side="right")

        self.today_list = ctk.CTkScrollableFrame(
            left, fg_color="transparent",
            scrollbar_button_color=pair("border"),
            scrollbar_button_hover_color=pair("muted"),
        )
        self.today_list.pack(fill="both", expand=True)

    def add_habit(self):
        name = self.new_entry.get().strip()
        if not name:
            return
        raw_time = self.new_time.get().strip()
        habit_time = None
        if raw_time:
            m = TIME_RE.match(raw_time)
            if not m:
                messagebox.showinfo(
                    "Time format",
                    "Please write the time like 06:30 (24-hour), or leave it empty.",
                )
                return
            habit_time = f"{int(m.group(1)):02d}:{m.group(2)}"
        if len(name) > 50:
            messagebox.showinfo("Too long", "Please keep the habit name under 50 characters.")
            return
        if self.db.name_exists(name):
            messagebox.showinfo("Already exists", f'You already have a habit called "{name}".')
            return
        self.db.add_habit(name, habit_time)
        self.new_entry.delete(0, "end")
        self.new_time.delete(0, "end")
        self.refresh_all()

    def delete_habit(self, habit):
        ok = messagebox.askyesno(
            "Delete habit",
            f'Delete "{habit["name"]}"?\nIts history will also be removed.',
        )
        if ok:
            self.db.delete_habit(habit["id"])
            self.refresh_all()

    def toggle(self, habit_id, var):
        self.db.set_done(habit_id, date.today().isoformat(), bool(var.get()))
        self.after(10, self.refresh_all)

    def refresh_all(self):
        self.refresh_today()
        self.refresh_weekly()

    def save_time(self, habit, entry):
        try:
            raw = entry.get().strip()
        except Exception:
            return
        if raw == "" and habit["kind"] == "custom":     # time is optional
            if habit["time"]:
                self.db.set_time(habit["id"], None)
                habit["time"] = None
                self.after(10, self.refresh_today)
            return
        m = TIME_RE.match(raw)
        if not m:
            entry.delete(0, "end")
            entry.insert(0, habit["time"] or "")
            self.bell()
            return
        fixed = f"{int(m.group(1)):02d}:{m.group(2)}"
        entry.delete(0, "end")
        entry.insert(0, fixed)
        if fixed != habit["time"]:
            self.db.set_time(habit["id"], fixed)
            habit["time"] = fixed
            self.after(10, self.refresh_today)

    def _checkbox(self, parent, habit, done_set):
        var = ctk.BooleanVar(value=habit["id"] in done_set)
        cb = ctk.CTkCheckBox(
            parent, text=habit["name"], variable=var,
            onvalue=True, offvalue=False, font=self.f_body,
            checkbox_width=26, checkbox_height=26, corner_radius=7,
            border_width=2,
            fg_color=pair("accent"), hover_color=pair("accent_hover"),
            border_color=pair("muted"), checkmark_color=pair("on_accent"),
            text_color=pair("text"),
            command=lambda: self.toggle(habit["id"], var),
        )
        return cb

    def refresh_today(self):
        for w in self.today_list.winfo_children():
            w.destroy()

        habits = self.db.habits()
        done_set = self.db.done_on(date.today().isoformat())
        prayers = [h for h in habits if h["kind"] == "prayer"]
        customs = [h for h in habits if h["kind"] == "custom"]

        # ---- prayers card
        p_card = self.card(self.today_list)
        p_card.pack(fill="x", pady=(0, 12))
        p_done = sum(1 for h in prayers if h["id"] in done_set)

        top = ctk.CTkFrame(p_card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 4))
        self.label(top, "Prayers", self.f_head).pack(side="left")
        self.label(
            top, f"{p_done}/{len(prayers)} prayed", self.f_head
        ).pack(side="right")

        bar = ctk.CTkProgressBar(
            p_card, height=10, corner_radius=5,
            progress_color=pair("accent"), fg_color=pair("border"),
        )
        bar.pack(fill="x", padx=16, pady=(4, 6))
        bar.set(p_done / len(prayers) if prayers else 0)

        self.label(p_card, self._next_prayer_text(prayers, done_set),
                   self.f_small, muted=True).pack(anchor="w", padx=16, pady=(0, 6))

        for h in prayers:
            row = ctk.CTkFrame(p_card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=5)
            self._checkbox(row, h, done_set).pack(side="left")
            entry = ctk.CTkEntry(
                row, width=74, height=32, justify="center", font=self.f_body,
                fg_color=pair("bg"), border_color=pair("border"),
                text_color=pair("text"), corner_radius=8,
            )
            entry.insert(0, h["time"] or "")
            entry.pack(side="right")
            self.label(row, "time", self.f_small, muted=True).pack(side="right", padx=8)
            entry.bind("<Return>", lambda e, h=h, en=entry: self.save_time(h, en))
            entry.bind("<FocusOut>", lambda e, h=h, en=entry: self.save_time(h, en))
        ctk.CTkFrame(p_card, height=8, fg_color="transparent").pack()

        # ---- custom habits card
        c_card = self.card(self.today_list)
        c_card.pack(fill="x", pady=(0, 12))
        c_done = sum(1 for h in customs if h["id"] in done_set)

        top = ctk.CTkFrame(c_card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 8))
        self.label(top, "My habits", self.f_head).pack(side="left")
        if customs:
            self.label(
                top, f"{c_done}/{len(customs)} done", self.f_head
            ).pack(side="right")

        nxt = self._next_habit_text(customs, done_set)
        if nxt:
            self.label(c_card, nxt, self.f_small, muted=True).pack(
                anchor="w", padx=16, pady=(0, 6))

        if not customs:
            self.label(
                c_card,
                "No habits yet. Type one above and press Add habit.",
                muted=True,
            ).pack(anchor="w", padx=16, pady=(0, 16))
        else:
            for h in customs:
                row = ctk.CTkFrame(c_card, fg_color="transparent")
                row.pack(fill="x", padx=16, pady=5)
                self._checkbox(row, h, done_set).pack(side="left")
                ctk.CTkButton(
                    row, text="Delete", width=70, height=28, corner_radius=8,
                    font=self.f_small, fg_color="transparent",
                    border_width=1, border_color=pair("border"),
                    text_color=pair("muted"), hover_color=pair("border"),
                    command=lambda h=h: self.delete_habit(h),
                ).pack(side="right")
                t_entry = ctk.CTkEntry(
                    row, width=74, height=32, justify="center",
                    font=self.f_body, placeholder_text="--:--",
                    fg_color=pair("bg"), border_color=pair("border"),
                    text_color=pair("text"),
                    placeholder_text_color=pair("muted"), corner_radius=8,
                )
                if h["time"]:
                    t_entry.insert(0, h["time"])
                t_entry.pack(side="right", padx=(0, 8))
                t_entry.bind("<Return>", lambda e, h=h, en=t_entry: self.save_time(h, en))
                t_entry.bind("<FocusOut>", lambda e, h=h, en=t_entry: self.save_time(h, en))
            ctk.CTkFrame(c_card, height=8, fg_color="transparent").pack()

        # ---- flower follows today's progress (prayers + own habits)
        total = len(habits)
        done_n = sum(1 for h in habits if h["id"] in done_set)
        progress = done_n / total if total else 0.0
        self.set_flower_progress(progress)
        fname = self.flower_name.lower()
        if total and progress >= 1:
            msg = f"Your {fname} is fully bloomed. MashaAllah!"
        elif done_n == 0:
            msg = f"Complete a habit to start growing your {fname}."
        else:
            msg = f"{done_n}/{total} done today. Your {fname} is {round(progress * 100)}% bloomed."
        self.flower_label.configure(text=msg)

    @staticmethod
    def _next_prayer_text(prayers, done_set):
        pending = [h for h in prayers if h["id"] not in done_set]
        if not prayers:
            return ""
        if not pending:
            return "All prayers completed today, Alhamdulillah."
        now = datetime.now().strftime("%H:%M")
        upcoming = [h for h in pending if (h["time"] or "") >= now]
        if upcoming:
            nxt = upcoming[0]
            return f'Next: {nxt["name"]} at {nxt["time"]}'
        names = ", ".join(h["name"] for h in pending)
        return f"Still to pray: {names}"

    @staticmethod
    def _next_habit_text(customs, done_set):
        now = datetime.now().strftime("%H:%M")
        pending = [h for h in customs if h["time"] and h["id"] not in done_set]
        upcoming = [h for h in pending if h["time"] >= now]
        if upcoming:
            return f'Next: {upcoming[0]["name"]} at {upcoming[0]["time"]}'
        if pending:
            return "Time passed for: " + ", ".join(h["name"] for h in pending)
        return ""

    # ------------------------------------------------------------------ #
    #  FLOWER card
    # ------------------------------------------------------------------ #
    def _build_flower_card(self, parent):
        card = self.card(parent)
        card.pack(side="right", fill="y", padx=(12, 0))
        self.label(card, "Your flower", self.f_head).pack(pady=(14, 6))
        self.flower_menu = ctk.CTkOptionMenu(
            card, values=list(FLOWERS), command=self.on_flower_change,
            width=200, height=32, font=self.f_body, dropdown_font=self.f_body,
            fg_color=pair("bg"), button_color=pair("accent"),
            button_hover_color=pair("accent_hover"),
            text_color=pair("text"), dropdown_fg_color=pair("card"),
            dropdown_text_color=pair("text"),
            dropdown_hover_color=pair("border"),
        )
        self.flower_menu.set(self.flower_name)
        self.flower_menu.pack(pady=(0, 8))
        self.flower_canvas = tk.Canvas(
            card, width=CANVAS_W, height=CANVAS_H, highlightthickness=0, bd=0
        )
        self.flower_canvas.pack(padx=14)
        self.flower_label = self.label(
            card, "", self.f_body, wraplength=250, justify="center"
        )
        self.flower_label.pack(pady=(6, 14), padx=10)
        self._paint_flower()

    def on_flower_change(self, choice):
        self.flower_name = choice
        self.db.set_setting("flower", choice)
        self._paint_flower()
        self.refresh_today()          # updates the caption text

    def set_flower_progress(self, p):
        self.flower_target = max(0.0, min(1.0, p))
        if self.flower_job is None:
            self._animate_flower()

    def _animate_flower(self):
        diff = self.flower_target - self.flower_shown
        if abs(diff) < 0.004:
            self.flower_shown = self.flower_target
            self.flower_job = None
        else:
            step = min(abs(diff), max(0.012, abs(diff) * 0.12))
            self.flower_shown += step if diff > 0 else -step
            self.flower_job = self.after(30, self._animate_flower)
        self._paint_flower()

    def _paint_flower(self):
        pal = self.palette()
        self.flower_canvas.configure(bg=pal["card"])
        draw_flower(self.flower_canvas, self.flower_name, self.flower_shown, pal)

    # ------------------------------------------------------------------ #
    #  WEEKLY page
    # ------------------------------------------------------------------ #
    def _build_weekly_page(self):
        self.week_page = ctk.CTkFrame(self.page_holder, fg_color="transparent")

        nav = ctk.CTkFrame(self.week_page, fg_color="transparent")
        nav.pack(fill="x", pady=(0, 8))
        self.prev_btn = self.button(
            nav, "<", self._prev_week, width=40,
            fg_color=pair("card"), hover_color=pair("border"),
            text_color=pair("text"),
        )
        self.prev_btn.pack(side="left")
        self.week_title = self.label(nav, "", self.f_head)
        self.week_title.pack(side="left", padx=14)
        self.next_btn = self.button(
            nav, ">", self._next_week, width=40,
            fg_color=pair("card"), hover_color=pair("border"),
            text_color=pair("text"),
        )
        self.next_btn.pack(side="left")

        self.week_body = ctk.CTkScrollableFrame(
            self.week_page, fg_color="transparent",
            scrollbar_button_color=pair("border"),
            scrollbar_button_hover_color=pair("muted"),
        )
        self.week_body.pack(fill="both", expand=True)

    def _prev_week(self):
        self.week_offset += 1
        self.refresh_weekly()

    def _next_week(self):
        if self.week_offset > 0:
            self.week_offset -= 1
            self.refresh_weekly()

    def refresh_weekly(self):
        for w in self.week_body.winfo_children():
            w.destroy()
        self.chart_canvas = None

        end = date.today() - timedelta(days=7 * self.week_offset)
        start = end - timedelta(days=6)
        days = [start + timedelta(days=i) for i in range(7)]
        self.week_title.configure(
            text=f'{start.strftime("%d %b")} - {end.strftime("%d %b %Y")}'
        )
        self.next_btn.configure(state="normal" if self.week_offset > 0 else "disabled")

        habits = self.db.habits()
        if not habits:
            self.label(self.week_body, "Nothing to report yet.", muted=True).pack(pady=30)
            return
        marks = self.db.done_between(start.isoformat(), end.isoformat())

        def applies(h, d):
            return d.isoformat() >= h["created"]

        # per-day and total numbers
        day_pct, day_app, day_done = [], [], []
        for d in days:
            app = [h for h in habits if applies(h, d)]
            dn = [h for h in app if (h["id"], d.isoformat()) in marks]
            day_app.append(len(app))
            day_done.append(len(dn))
            day_pct.append(100 * len(dn) / len(app) if app else 0)

        tot_app, tot_done = sum(day_app), sum(day_done)
        overall = round(100 * tot_done / tot_app) if tot_app else 0

        pr_app = pr_done = 0
        for h in habits:
            if h["kind"] != "prayer":
                continue
            for d in days:
                if applies(h, d):
                    pr_app += 1
                    pr_done += (h["id"], d.isoformat()) in marks

        best = "-"
        scored = [(p, d) for p, d, a in zip(day_pct, days, day_app) if a]
        if scored and max(scored, key=lambda x: x[0])[0] > 0:
            best = max(scored, key=lambda x: x[0])[1].strftime("%A")

        # ---- summary cards
        row = ctk.CTkFrame(self.week_body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        for i in range(3):
            row.columnconfigure(i, weight=1, uniform="sum")
        stats = [
            ("Overall completion", f"{overall}%"),
            ("Prayers prayed", f"{pr_done}/{pr_app}" if pr_app else "-"),
            ("Best day", best),
        ]
        for i, (title, value) in enumerate(stats):
            c = self.card(row)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 2 else 6))
            self.label(c, title, self.f_small, muted=True).pack(pady=(12, 0))
            ctk.CTkLabel(
                c, text=value, font=ctk.CTkFont(size=24, weight="bold"),
                text_color=pair("accent"),
            ).pack(pady=(0, 12))

        # ---- chart
        chart_card = self.card(self.week_body)
        chart_card.pack(fill="x", pady=(0, 12))
        pal = self.palette()
        fig = Figure(figsize=(6.6, 2.5), dpi=100, facecolor=pal["card"])
        ax = fig.add_subplot(111)
        ax.set_facecolor(pal["card"])
        labels = [d.strftime("%a") for d in days]
        bars = ax.bar(labels, day_pct, color=pal["accent"], width=0.55)
        ax.set_ylim(0, 115)
        ax.set_yticks([0, 50, 100])
        ax.set_title("Daily completion (%)", color=pal["text"],
                     fontsize=11, loc="left")
        ax.tick_params(colors=pal["muted"], labelsize=9)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(pal["border"])
        for b, v, a in zip(bars, day_pct, day_app):
            if a:
                ax.text(b.get_x() + b.get_width() / 2, v + 3, f"{v:.0f}%",
                        ha="center", fontsize=8, color=pal["text"])
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=chart_card)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.configure(bg=pal["card"], highlightthickness=0)
        widget.pack(fill="x", padx=8, pady=8)
        self.chart_canvas = canvas

        # ---- table
        t_card = self.card(self.week_body)
        t_card.pack(fill="x", pady=(0, 12))
        grid = ctk.CTkFrame(t_card, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=14)
        grid.columnconfigure(0, weight=1, minsize=170)
        for c in range(1, 8):
            grid.columnconfigure(c, minsize=48)
        grid.columnconfigure(8, minsize=60)
        grid.columnconfigure(9, minsize=60)

        self.label(grid, "Habit", self.f_small, muted=True).grid(row=0, column=0, sticky="w")
        for i, d in enumerate(days):
            self.label(grid, d.strftime("%a\n%d"), self.f_small, muted=True).grid(
                row=0, column=i + 1, pady=(0, 6)
            )
        self.label(grid, "Done", self.f_small, muted=True).grid(row=0, column=8)
        self.label(grid, "%", self.f_small, muted=True).grid(row=0, column=9)

        for r, h in enumerate(habits, start=1):
            self.label(grid, h["name"]).grid(row=r, column=0, sticky="w", pady=3)
            n_app = n_done = 0
            for i, d in enumerate(days):
                if not applies(h, d):
                    txt, col = "·", "muted"
                elif (h["id"], d.isoformat()) in marks:
                    txt, col = "✓", "accent"
                    n_app += 1
                    n_done += 1
                else:
                    txt, col = "–", "muted"
                    n_app += 1
                ctk.CTkLabel(
                    grid, text=txt, text_color=pair(col),
                    font=ctk.CTkFont(size=16, weight="bold"),
                ).grid(row=r, column=i + 1)
            pct = round(100 * n_done / n_app) if n_app else 0
            self.label(grid, f"{n_done}/{n_app}" if n_app else "-",
                       self.f_small).grid(row=r, column=8)
            self.label(grid, f"{pct}%" if n_app else "-",
                       self.f_small).grid(row=r, column=9)


if __name__ == "__main__":
    App().mainloop()
