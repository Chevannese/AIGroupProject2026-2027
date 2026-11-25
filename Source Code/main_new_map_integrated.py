#!/usr/bin/env python3

"""
road_gui.py
-----------
Graphical interface for the Rural Roads Path-Finder.

All data and all path-finding live in Prolog (road_network.pl).  This
window only asks Prolog questions (with pyswip) and draws the answers.

  * Map tab     : places as nodes, roads as edges (colour = status/type,
                  dashes = unpaved, arrow = one-way, badges = conditions).
  * Table tab   : every road/8 fact.
  * Find a route: pick start, end and criteria -> Prolog's find_route/6
                  runs Dijkstra / A* / BFS and the route is highlighted.
  * Side tabs   : details of the clicked place/road, and a legend.

Roles
  * Regular user : view the network and find routes.
  * Administrator: log in with the button on the toolbar to unlock the
                   admin tools (add/edit data, drag places to reposition).

Run:  python road_gui.py
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox

from pathlib import Path

import os
import re
from dataclasses import dataclass

# TODO: REMOVE THIS
# from auth import authenticate

ROAD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "road_network.pl")

# The criteria find_route/6 understands:  (Prolog atom, label, algorithm used)
CRITERIA = [
    ("shortest_distance",     "Shortest distance",           "Dijkstra (by distance)"),
    ("fastest_route",         "Fastest route",               "Dijkstra (by time)"),
    ("avoid_closed",          "Avoid closed roads",          "Dijkstra (open roads only)"),
    ("avoid_unpaved",         "Avoid unpaved roads",         "A* (terrain + hazard penalties)"),
    ("avoid_broken_cisterns", "Avoid broken cisterns",       "A* (terrain + hazard penalties)"),
    ("avoid_deep_potholes",   "Avoid deep potholes",         "A* (terrain + hazard penalties)"),
    ("loose_constraints",     "Loose (BFS, closed allowed)", "BFS (fewest roads)"),
]


@dataclass
class Road:
    """One road(From, To, Distance, Time, Surface, Hazard, Status, Bidirectional) fact."""
    from_id: str
    to_id: str
    km: float
    mins: float
    road_type: str
    condition: str
    status: str
    bidirectional: str

    @property
    def oneway(self) -> bool:
        return self.bidirectional != "yes"

    @property
    def closed(self) -> bool:      # Prolog's strict mode only uses status = open
        return self.status != "open"


def text(value) -> str:
    """pyswip may return str, bytes or Atom objects; always give back str."""
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def quote(atom: str) -> str:
    """Quote a place name so it is safe inside a Prolog query."""
    return "'" + atom.replace("\\", "\\\\").replace("'", "\\'") + "'"


def circle_layout(nodes):
    """road_network.pl has no coordinates, so put the places on an ellipse."""
    n = len(nodes)
    if n == 1:
        return {nodes[0]: [450.0, 280.0]}
    return {v: [450 + 380 * math.cos(2 * math.pi * i / n - math.pi / 2),
                280 + 220 * math.sin(2 * math.pi * i / n - math.pi / 2)]
            for i, v in enumerate(nodes)}


# --------------------------------------------------------------------
# Visual constants
# --------------------------------------------------------------------
BG = "#f7f5ef"            # map background
NODE_R = 16               # node radius in pixels
MARGIN = 80               # space kept free around the map

COL_PAVED = "#2e7d5b"     # open + paved
COL_UNPAVED = "#b7791f"   # open + unpaved
COL_CLOSED = "#c0392b"    # closed (any type)
COL_NODE = "#24415f"
COL_SELECT = "#ffe08a"    # glow behind selected road / ring on selected node
COL_PATH_GLOW = "#93c5fd"
COL_PATH_NODE = "#2563eb"
COL_START = "#16a34a"
COL_END = "#7c3aed"

# condition -> (badge letter, badge colour, readable name)
CONDITIONS = {
    "broken_cisterns":  ("C", "#2b7bb9", "Broken cisterns"),
    "deep_potholes":    ("P", "#8e44ad", "Deep potholes"),
    "falling_rocks":    ("R", "#e67e22", "Risk of falling rocks"),
    "severely_damaged": ("D", "#7f1d1d", "Severely damaged"),
}
CLOSED_BADGE = ("X", COL_CLOSED, "Road closed")

# Preserve the old editor's five-minute adjustment when a road's hazard
# changes into or out of one of these conditions.
PENALTY_CONDITIONS = {"broken_cisterns", "deep_potholes"}
PENALTY_MINUTES = 5

ROAD_SURFACES = ("paved", "unpaved")
ROAD_CONDITIONS = (
    "none", "broken_cisterns", "deep_potholes", "falling_rocks",
    "severely_damaged",
)
ROAD_STATUSES = ("open", "closed")
ROAD_DIRECTIONS = ("yes", "no")

# Mode badge / admin toolbar colours
MODE_USER_BG, MODE_USER_FG = "#e5e7eb", "#374151"
MODE_ADMIN_BG, MODE_ADMIN_FG = "#d97706", "#ffffff"
ADMIN_BAR_BG = "#fff1d6"


def fmt(value) -> str:
    """5.0 -> '5', 5.5 -> '5.5'."""
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def pretty(text: str) -> str:
    """'broken_cisterns' -> 'Broken Cisterns',  'a' -> 'A'."""
    return " ".join(w[:1].upper() + w[1:] for w in text.replace("_", " ").split())


# --------------------------------------------------------------------
# Login dialog (modal)
# --------------------------------------------------------------------
class LoginDialog(tk.Toplevel):
    """Asks for admin credentials. `result` holds the username on success."""

    MAX_ATTEMPTS = 3

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Administrator login")
        self.resizable(False, False)
        self.transient(parent)
        self.result = None
        self._attempts = 0

        frm = ttk.Frame(self, padding=18)
        frm.pack()
        ttk.Label(frm, text="Administrator login",
                  font=("Helvetica", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.user_var, self.pw_var = tk.StringVar(), tk.StringVar()
        ttk.Label(frm, text="Username").grid(row=1, column=0, sticky="w", pady=4)
        self.user_entry = ttk.Entry(frm, textvariable=self.user_var, width=26)
        self.user_entry.grid(row=1, column=1, padx=(10, 0))
        ttk.Label(frm, text="Password").grid(row=2, column=0, sticky="w", pady=4)
        self.pw_entry = ttk.Entry(frm, textvariable=self.pw_var, show="*", width=26)
        self.pw_entry.grid(row=2, column=1, padx=(10, 0))

        self.msg = tk.StringVar()
        ttk.Label(frm, textvariable=self.msg, foreground=COL_CLOSED,
                  wraplength=260).grid(row=3, column=0, columnspan=2,
                                       sticky="w", pady=(6, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Log in",
                   command=self._submit).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _e: self._submit())
        self.bind("<Escape>", lambda _e: self.destroy())

        # Centre over the main window, then make it modal
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        self.user_entry.focus_set()
        self.wait_window(self)

    def _submit(self):
        username, password = self.user_var.get().strip(), self.pw_var.get()
        if not username or not password:
            self.msg.set("Please enter both a username and a password.")
            return
        if self.authenticate(username, password):
            self.result = username
            self.destroy()
            return
        self._attempts += 1
        self.pw_var.set("")
        left = self.MAX_ATTEMPTS - self._attempts
        if left <= 0:
            messagebox.showerror("Login failed", "Too many incorrect attempts.", parent=self)
            self.destroy()
        else:
            self.msg.set(f"Incorrect username or password "
                         f"({left} attempt{'s' if left != 1 else ''} left).")
            self.pw_entry.focus_set()
            
    def authenticate(self, username: str, password: str) -> bool:
        source_folder = Path(__file__).resolve().parent
        admin_file = source_folder / "admins.txt"
    
        with open(admin_file, "r") as file:
            for line in file:
                split = line.strip().split(",")
                if split[0] == username and split[1] == password:
                    return True
        return False


class RoadEditorDialog(tk.Toplevel):
    """Modal form used to add a road or edit an existing road/8 fact."""

    def __init__(self, parent, road=None):
        super().__init__(parent)
        self.title("Add road" if road is None else "Edit road")
        self.resizable(False, False)
        self.transient(parent)
        self.result = None
        self.original = road

        defaults = {
            "from_id": road.from_id if road else "",
            "to_id": road.to_id if road else "",
            "km": fmt(road.km) if road else "1",
            "mins": fmt(road.mins) if road else "1",
            "road_type": road.road_type if road else "paved",
            "condition": road.condition if road else "none",
            "status": road.status if road else "open",
            "bidirectional": road.bidirectional if road else "yes",
        }
        self.vars = {name: tk.StringVar(value=value)
                     for name, value in defaults.items()}

        form = ttk.Frame(self, padding=16)
        form.grid(row=0, column=0, sticky="nsew")
        form.columnconfigure(1, weight=1)

        fields = (
            ("from_id", "Source place", "entry", None),
            ("to_id", "Destination place", "entry", None),
            ("km", "Distance (km)", "entry", None),
            ("mins", "Travel time (minutes)", "entry", None),
            ("road_type", "Road surface", "choice", ROAD_SURFACES),
            ("condition", "Special condition", "choice", ROAD_CONDITIONS),
            ("status", "Road status", "choice", ROAD_STATUSES),
            ("bidirectional", "Bidirectional", "choice", ROAD_DIRECTIONS),
        )
        for row, (name, label, kind, choices) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=5)
            if kind == "choice":
                widget = ttk.Combobox(form, textvariable=self.vars[name],
                                      values=choices, state="readonly", width=25)
            else:
                widget = ttk.Entry(form, textvariable=self.vars[name], width=28)
            widget.grid(row=row, column=1, sticky="ew", padx=(14, 0), pady=5)

        hint = ("Use place IDs such as 'a' or 'new_kingston'. Spaces are converted "
                "to underscores. Bidirectional: yes / no.")
        ttk.Label(form, text=hint, foreground="#666666",
                  wraplength=350).grid(row=len(fields), column=0, columnspan=2,
                                       sticky="w", pady=(8, 2))

        buttons = ttk.Frame(form)
        buttons.grid(row=len(fields) + 1, column=0, columnspan=2,
                     sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Save road", command=self._save).pack(
            side="right", padx=(0, 8))

        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        self.focus_set()
        self.wait_window(self)

    @staticmethod
    def _place_id(value):
        return "_".join(value.strip().lower().split())

    @staticmethod
    def _number(value, label, minimum, maximum):
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a number.")
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise ValueError(f"{label} must be between {minimum} and {maximum}.")
        return int(number) if number.is_integer() else number

    def _save(self):
        source = self._place_id(self.vars["from_id"].get())
        destination = self._place_id(self.vars["to_id"].get())
        if not source or not destination:
            messagebox.showerror("Invalid road", "Enter both a source and destination place.", parent=self)
            return
        if source == destination:
            messagebox.showerror("Invalid road", "Source and destination must be different.", parent=self)
            return

        try:
            distance = self._number(self.vars["km"].get(), "Distance", 0.1, 1000)
            minutes = self._number(self.vars["mins"].get(), "Travel time", 1, 1440)
        except ValueError as exc:
            messagebox.showerror("Invalid road", str(exc), parent=self)
            return

        road_type = self.vars["road_type"].get()
        condition = self.vars["condition"].get()
        status = self.vars["status"].get()
        bidirectional = self.vars["bidirectional"].get()
        if not all((road_type, condition, status, bidirectional)):
            messagebox.showerror("Invalid road", "Choose a value for every road option.", parent=self)
            return

        # This preserves the old table editor's special-condition time rule.
        if self.original is not None:
            was_penalized = self.original.condition in PENALTY_CONDITIONS
            now_penalized = condition in PENALTY_CONDITIONS
            if now_penalized and not was_penalized:
                minutes += PENALTY_MINUTES
            elif was_penalized and not now_penalized:
                minutes = max(minutes - PENALTY_MINUTES, 0)

        self.result = Road(source, destination, distance, minutes, road_type,
                           condition, status, bidirectional)
        self.destroy()


# --------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------
class RoadNetworkApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Rural Roads Path-Finder  |  UTech Jamaica")
        self.geometry("1220x740")
        self.minsize(980, 600)

        self.prolog = None              # pyswip Prolog engine, created on first load
        self._prolog_loaded = False
        self.roads = []                 # list[Road] read from road/8
        self.nodes = []                 # every place named in a road
        self.source = ""
        self.positions = {}             # place id -> [x, y] (logical units)
        self.label_to_id = {}           # text shown in the dropdowns -> id
        self.selected_node = None       # place id
        self.selected_road = None       # index into self.roads
        self.path_nodes = []            # ordered place ids of a route
        self.path_roads = set()         # road indexes used by the route

        self.scale, self.off_x, self.off_y = 1.0, 0.0, 0.0
        self._drag_node = None
        self._moved = False
        self._press_xy = (0, 0)
        self._syncing = False           # stops table<->map selection loops
        self.show_labels = tk.BooleanVar(value=True)

        self.admin_user = None          # username while an admin is logged in
        self.mode_text = tk.StringVar(value="Mode: User")

        self.from_var = tk.StringVar()
        self.to_var = tk.StringVar()
        self.route_msg = tk.StringVar()

        self._build_ui()
        self.reload_network()

    # ----------------------------------------------------------------
    # UI construction
    # ----------------------------------------------------------------
    def _build_ui(self):
        # Main toolbar (regular features + login) ----------------------
        bar = ttk.Frame(self, padding=(8, 6))
        bar.pack(side="top", fill="x")
        self.toolbar = bar
        ttk.Button(bar, text="Reload from Prolog",
                   command=self.reload_network).pack(side="left")
        ttk.Button(bar, text="Fit to window",
                   command=self.fit_to_window).pack(side="left", padx=6)
        ttk.Button(bar, text="Auto-arrange",
                   command=self.auto_arrange).pack(side="left")
        ttk.Checkbutton(bar, text="Show distance / time labels",
                        variable=self.show_labels,
                        command=self.draw).pack(side="left", padx=10)

        # Right side (packed right-to-left): login button, mode badge, clear route
        self.auth_btn = ttk.Button(bar, text="Admin login",
                                   command=self.toggle_login)
        self.auth_btn.pack(side="right")
        self.mode_badge = tk.Label(bar, textvariable=self.mode_text,
                                   bg=MODE_USER_BG, fg=MODE_USER_FG,
                                   font=("Helvetica", 9, "bold"),
                                   padx=10, pady=3)
        self.mode_badge.pack(side="right", padx=8)
        ttk.Button(bar, text="Clear route",
                   command=self.clear_route).pack(side="right")

        # Admin toolbar: created now, only shown while an admin is logged in
        self.admin_bar = tk.Frame(self, bg=ADMIN_BAR_BG, padx=8, pady=5)
        tk.Label(self.admin_bar, text="Administrator tools:", bg=ADMIN_BAR_BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 10))
        for text, handler in (("Add road", self.admin_add_road),
                              ("Edit / close selected road", self.admin_edit_road),
                              ("Delete selected road", self.admin_delete_road)):
            ttk.Button(self.admin_bar, text=text,
                       command=handler).pack(side="left", padx=(0, 6))
        tk.Label(self.admin_bar, text="Tip: drag places on the map to reposition them.",
                 bg=ADMIN_BAR_BG, fg="#7c5a10",
                 font=("Helvetica", 9)).pack(side="left", padx=12)

        # Status bar
        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, relief="sunken",
                  anchor="w", padding=(8, 3)).pack(side="bottom", fill="x")

        # Right-hand panel: route finder on top, details/legend below -----
        side = ttk.Frame(self, padding=(0, 0, 8, 8))
        side.pack(side="right", fill="y")

        rf = ttk.LabelFrame(side, text="Find a route", padding=8)
        rf.pack(fill="x")
        rf.columnconfigure(1, weight=1)
        ttk.Label(rf, text="From").grid(row=0, column=0, sticky="w", pady=2)
        self.from_box = ttk.Combobox(rf, textvariable=self.from_var,
                                     state="readonly", width=26)
        self.from_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Label(rf, text="To").grid(row=1, column=0, sticky="w", pady=2)
        self.to_box = ttk.Combobox(rf, textvariable=self.to_var,
                                   state="readonly", width=26)
        self.to_box.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        ttk.Label(rf, text="Criteria").grid(row=2, column=0, sticky="w", pady=2)
        self.crit_box = ttk.Combobox(rf, state="readonly", width=26,
                                     values=[c[1] for c in CRITERIA])
        self.crit_box.current(0)
        self.crit_box.grid(row=2, column=1, sticky="ew", padx=(8, 0))
        ttk.Button(rf, text="Find route",
                   command=self.find_route).grid(row=3, column=0, columnspan=2,
                                                 sticky="ew", pady=(8, 4))
        self.route_label = tk.Label(rf, textvariable=self.route_msg,
                                    justify="left", anchor="w", wraplength=290,
                                    font=("Helvetica", 9))
        self.route_label.grid(row=4, column=0, columnspan=2, sticky="w")

        self.side_nb = ttk.Notebook(side)
        self.side_nb.pack(fill="both", expand=True, pady=(8, 0))
        self.sel_tab = ttk.Frame(self.side_nb, padding=8)
        self.side_nb.add(self.sel_tab, text="  Selection  ")
        self.details = tk.StringVar()
        ttk.Label(self.sel_tab, textvariable=self.details, justify="left",
                  wraplength=290).pack(anchor="nw")
        leg_tab = ttk.Frame(self.side_nb, padding=8)
        self.side_nb.add(leg_tab, text="  Legend  ")
        self.legend = tk.Canvas(leg_tab, width=290, height=262,
                                bg="white", highlightthickness=0)
        self.legend.pack()
        self._draw_legend()

        # Notebook: Map tab + Table tab
        nb = ttk.Notebook(self)
        nb.pack(side="left", fill="both", expand=True, padx=(8, 8), pady=(0, 8))

        self.canvas = tk.Canvas(nb, bg=BG, highlightthickness=0)
        nb.add(self.canvas, text="  Map  ")
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        tab = ttk.Frame(nb)
        nb.add(tab, text="  Roads table  ")
        cols = ("from", "to", "km", "mins", "type", "cond", "status", "dir")
        heads = ("From", "To", "Km", "Mins", "Type", "Condition",
                 "Status", "Direction")
        widths = (90, 90, 50, 55, 70, 130, 70, 80)
        self.table = ttk.Treeview(tab, columns=cols, show="headings",
                                  selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            self.table.heading(c, text=h)
            self.table.column(c, width=w, anchor="w")
        self.table.tag_configure("closed", foreground=COL_CLOSED)
        sb = ttk.Scrollbar(tab, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=sb.set)
        self.table.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.table.bind("<<TreeviewSelect>>", self._on_table_select)
        self.table.bind("<Double-1>", self._on_table_double_click)

    # ----------------------------------------------------------------
    # Loading (everything comes from Prolog)
    # ----------------------------------------------------------------
    def reload_network(self):
        """Consult road_network.pl and read every road/8 fact."""
        try:
            if self.prolog is None:
                from pyswip import Prolog
                self.prolog = Prolog()
            elif self._prolog_loaded:
                # Clear previously consulted/asserted road facts before reading
                # the file again, preventing duplicates on repeated reloads.
                list(self.prolog.query("delallroad"))
            self.prolog.consult(ROAD_FILE.replace("\\", "/"))
            self._prolog_loaded = True
            rows = list(self.prolog.query(
                "road(F, T, Km, Mins, Surface, Hazard, Status, Bi)"))
        except Exception as exc:
            messagebox.showerror(
                "Prolog error",
                "Could not load road_network.pl.\n\nCheck that SWI-Prolog is "
                "installed and that pyswip is installed (pip install pyswip).\n\n"
                f"{exc}", parent=self)
            self.status.set("Could not load road_network.pl - see the error message.")
            return

        self.roads = [Road(text(r["F"]), text(r["T"]), r["Km"], r["Mins"],
                           text(r["Surface"]), text(r["Hazard"]),
                           text(r["Status"]), text(r["Bi"])) for r in rows]
        self.nodes = sorted({r.from_id for r in self.roads} |
                            {r.to_id for r in self.roads})
        self.source = os.path.basename(ROAD_FILE)

        self.selected_node = self.selected_road = None
        self.clear_route(redraw=False)

        # Places the admin already moved keep their position; new ones get a slot.
        old = self.positions
        self.positions = {**circle_layout(self.nodes),
                          **{n: old[n] for n in self.nodes if n in old}}

        self._fill_table()
        self._refresh_place_lists()
        self.fit_to_window()
        self._show_hint()
        self._update_status()

    def _update_status(self):
        closed = sum(r.closed for r in self.roads)
        oneway = sum(r.oneway for r in self.roads)
        self.status.set(f"{len(self.nodes)} places  |  {len(self.roads)} roads "
                        f"({closed} closed, {oneway} one-way)  |  "
                        f"Source: {self.source} via SWI-Prolog")

    def _fill_table(self):
        self.table.delete(*self.table.get_children())
        for i, r in enumerate(self.roads):
            self.table.insert("", "end", iid=str(i),
                              tags=("closed",) if r.closed else (), values=(
                pretty(r.from_id), pretty(r.to_id), fmt(r.km), fmt(r.mins),
                pretty(r.road_type), pretty(r.condition), pretty(r.status),
                "One-way" if r.oneway else "Two-way"))

    def _refresh_place_lists(self):
        """Fill the From/To dropdowns with every place in the network."""
        labels = {}
        for n in self.nodes:
            label = pretty(n)
            if label in labels:          # two ids that look alike: show the raw id
                label = n
            labels[label] = n
        self.label_to_id = labels
        values = list(labels)
        self.from_box["values"] = values
        self.to_box["values"] = values
        for var in (self.from_var, self.to_var):
            if var.get() not in labels:
                var.set("")
        if values and not self.from_var.get():
            self.from_var.set(values[0])
        if len(values) > 1 and not self.to_var.get():
            self.to_var.set(values[-1])

    # ----------------------------------------------------------------
    # Route finding (the search itself runs in Prolog)
    # ----------------------------------------------------------------
    def find_route(self):
        if self.prolog is None or not self.nodes:
            self._set_route_msg("No road network is loaded.", ok=False)
            return
        start = self.label_to_id.get(self.from_var.get())
        goal = self.label_to_id.get(self.to_var.get())
        if start is None or goal is None:
            self._set_route_msg("Please choose a start and an end place.", ok=False)
            return
        if start == goal:
            self._set_route_msg("The start and end are the same place.", ok=False)
            return

        key, label, algorithm = CRITERIA[self.crit_box.current()]
        try:      # the search itself runs in Prolog: find_route/6
            rows = list(self.prolog.query(
                f"once(find_route({key}, {quote(start)}, {quote(goal)}, "
                f"Path, Dist, Time))"))
        except Exception as exc:
            messagebox.showerror("Prolog error", str(exc), parent=self)
            return

        if not rows:                      # find_route failed: no path exists
            self.clear_path()
            self._set_route_msg(f"No path is available from {pretty(start)} to "
                                f"{pretty(goal)}\nusing: {label}.", ok=False)
            return

        path = [text(n) for n in rows[0]["Path"]]
        self.highlight_path(path)
        lines = ["Route:  " + "  ->  ".join(pretty(p) for p in path),
                 f"Total distance: {fmt(rows[0]['Dist'])} km",
                 f"Total time: {fmt(rows[0]['Time'])} min",
                 f"Criteria: {label}",
                 f"Algorithm: {algorithm}"]
        warn = any(self.roads[i].closed for i in self.path_roads)
        if warn:
            lines.append("Warning: this route uses a CLOSED road.")
        self._set_route_msg("\n".join(lines), ok=True, warn=warn)

    def _set_route_msg(self, text, ok, warn=False):
        """ok -> green, warn -> amber (route found but uses a closed road),
        otherwise red (error / no path)."""
        self.route_msg.set(text)
        colour = "#b45309" if warn else "#14532d" if ok else "#b91c1c"
        self.route_label.configure(fg=colour)

    def highlight_path(self, place_ids):
        """Highlight a route given as an ordered list of place ids."""
        self.path_nodes = list(place_ids)
        self.path_roads = set()
        for a, b in zip(place_ids, place_ids[1:]):
            best = None
            for i, r in enumerate(self.roads):
                forward = r.from_id == a and r.to_id == b
                backward = r.from_id == b and r.to_id == a and not r.oneway
                if forward or backward:
                    if best is None or (self.roads[best].closed and not r.closed):
                        best = i
            if best is not None:
                self.path_roads.add(best)
        self.draw()

    def clear_path(self, redraw=True):
        """Remove the route highlight from the map."""
        self.path_nodes, self.path_roads = [], set()
        if redraw:
            self.draw()

    def clear_route(self, redraw=True):
        """Toolbar button: remove the highlight and the result text."""
        self.clear_path(redraw=redraw)
        self.route_msg.set("")

    # ----------------------------------------------------------------
    # Roles: regular user vs administrator
    # ----------------------------------------------------------------
    @property
    def is_admin(self) -> bool:
        return self.admin_user is not None

    def toggle_login(self):
        """The single Login / Log out button on the main toolbar."""
        if self.is_admin:
            self.logout()
        else:
            self.open_login()

    def open_login(self):
        dialog = LoginDialog(self)
        if dialog.result:
            self._enter_admin_mode(dialog.result)

    def logout(self):
        self._leave_admin_mode()

    def _enter_admin_mode(self, username):
        self.admin_user = username
        self.mode_text.set(f"Mode: Administrator ({username})")
        self.mode_badge.configure(bg=MODE_ADMIN_BG, fg=MODE_ADMIN_FG)
        self.auth_btn.configure(text="Log out")
        self.admin_bar.pack(side="top", fill="x", after=self.toolbar)
        if self.selected_node is None and self.selected_road is None:
            self._show_hint()

    def _leave_admin_mode(self):
        self.admin_user = None
        self._drag_node, self._moved = None, False
        self.mode_text.set("Mode: User")
        self.mode_badge.configure(bg=MODE_USER_BG, fg=MODE_USER_FG)
        self.auth_btn.configure(text="Admin login")
        self.admin_bar.pack_forget()
        if self.selected_node is None and self.selected_road is None:
            self._show_hint()

    def require_admin(self) -> bool:
        """Gate for every admin action (the buttons are hidden for regular
        users, but each handler checks again so nothing relies on that)."""
        if not self.is_admin:
            messagebox.showwarning("Administrator only",
                                   "Please log in as an administrator first.")
            return False
        return True

    # -- Road network editing -----------------------------------------
    @staticmethod
    def _prolog_number(value):
        """Return a numeric literal that keeps integers and floats distinct."""
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        number = float(value)
        return repr(number)

    @classmethod
    def _road_arguments(cls, road):
        """Build the eight arguments accepted by addroad/8 and delroad/8."""
        return ", ".join((
            quote(road.from_id),
            quote(road.to_id),
            cls._prolog_number(road.km),
            cls._prolog_number(road.mins),
            quote(road.road_type),
            quote(road.condition),
            quote(road.status),
            quote(road.bidirectional),
        ))

    @classmethod
    def _road_fact(cls, road):
        return f"road({cls._road_arguments(road)})."

    @staticmethod
    def _road_from_query_row(row):
        return Road(text(row["F"]), text(row["T"]), row["Km"], row["Mins"],
                    text(row["Surface"]), text(row["Hazard"]),
                    text(row["Status"]), text(row["Bi"]))

    def _write_roads_to_file(self, roads):
        """Replace only road/8 facts, leaving Prolog rules and comments intact."""
        path = Path(ROAD_FILE)
        if not path.is_file():
            raise FileNotFoundError(f"Could not find {path.name} beside the application.")

        original = path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        fact_line = re.compile(r"^\s*road\s*\(.*\)\s*\.\s*(?:%.*)?$")
        fact_indexes = [i for i, line in enumerate(lines)
                        if fact_line.match(line.rstrip("\r\n"))]
        new_facts = [self._road_fact(road) + "\n" for road in roads]

        if fact_indexes:
            first_fact = fact_indexes[0]
            fact_index_set = set(fact_indexes)
            output = []
            for i, line in enumerate(lines):
                if i == first_fact:
                    output.extend(new_facts)
                if i not in fact_index_set:
                    output.append(line)
            updated = "".join(output)
        else:
            updated = original
            if updated and not updated.endswith("\n"):
                updated += "\n"
            updated += "\n% Road facts maintained by the Python GUI.\n"
            updated += "".join(new_facts)

        temp_path = path.with_name(path.name + ".tmp")
        temp_path.write_text(updated, encoding="utf-8")
        os.replace(temp_path, path)

    def _restore_prolog_roads(self, roads):
        """Best-effort rollback if writing the updated file fails."""
        try:
            list(self.prolog.query("delallroad"))
            for road in roads:
                list(self.prolog.query(f"addroad({self._road_arguments(road)})"))
        except Exception:
            pass

    def _finish_network_change(self, old_roads, new_roads):
        """Persist a successful Prolog mutation and refresh the map/table."""
        try:
            self._write_roads_to_file(new_roads)
        except Exception:
            self._restore_prolog_roads(old_roads)
            raise
        self.reload_network()
        self.clear_route(redraw=False)
        self._show_hint()
        self.draw()

    def admin_add_road(self):
        if not self.require_admin():
            return
        dialog = RoadEditorDialog(self)
        if dialog.result is None:
            return

        new_road = dialog.result
        old_roads = list(self.roads)
        try:
            result = list(self.prolog.query(
                f"addroad({self._road_arguments(new_road)})"))
            if not result:
                raise RuntimeError("Prolog rejected the addroad/8 operation.")
            self._finish_network_change(old_roads, old_roads + [new_road])
        except Exception as exc:
            messagebox.showerror("Add road failed", str(exc), parent=self)

    def admin_edit_road(self):
        if not self.require_admin():
            return
        if self.selected_road is None or not 0 <= self.selected_road < len(self.roads):
            messagebox.showinfo("Edit road", "Click a road on the map (or a row "
                                "in the Roads table) first.", parent=self)
            return

        index = self.selected_road
        old_road = self.roads[index]
        dialog = RoadEditorDialog(self, old_road)
        if dialog.result is None:
            return

        new_road = dialog.result
        old_roads = list(self.roads)
        try:
            query = (f"delroad({self._road_arguments(old_road)}), "
                     f"addroad({self._road_arguments(new_road)})")
            result = list(self.prolog.query(query))
            if not result:
                raise RuntimeError("Prolog could not find the selected road to update.")
            updated_roads = list(old_roads)
            updated_roads[index] = new_road
            self._finish_network_change(old_roads, updated_roads)
        except Exception as exc:
            messagebox.showerror("Update road failed", str(exc), parent=self)

    def admin_delete_road(self):
        if not self.require_admin():
            return
        if self.selected_road is None or not 0 <= self.selected_road < len(self.roads):
            messagebox.showinfo("Delete road", "Click a road on the map (or a row "
                                "in the Roads table) first.", parent=self)
            return

        index = self.selected_road
        road = self.roads[index]
        if not messagebox.askyesno(
                "Delete road",
                f"Delete the road from {pretty(road.from_id)} to {pretty(road.to_id)}?",
                parent=self):
            return

        old_roads = list(self.roads)
        try:
            result = list(self.prolog.query(
                f"delroad({self._road_arguments(road)})"))
            if not result:
                raise RuntimeError("Prolog could not find the selected road to delete.")
            updated_roads = old_roads[:index] + old_roads[index + 1:]
            self._finish_network_change(old_roads, updated_roads)
        except Exception as exc:
            messagebox.showerror("Delete road failed", str(exc), parent=self)

    # ----------------------------------------------------------------
    # Coordinate handling
    # ----------------------------------------------------------------
    def fit_to_window(self):
        """Scale/centre the map so every place is visible."""
        if not self.positions:
            self.draw()
            return
        w = max(self.canvas.winfo_width(), 300)
        h = max(self.canvas.winfo_height(), 300)
        xs = [p[0] for p in self.positions.values()]
        ys = [p[1] for p in self.positions.values()]
        span_x = max(max(xs) - min(xs), 1)
        span_y = max(max(ys) - min(ys), 1)
        self.scale = min((w - 2 * MARGIN) / span_x, (h - 2 * MARGIN) / span_y, 1.6)
        self.off_x = (w - span_x * self.scale) / 2 - min(xs) * self.scale
        self.off_y = (h - span_y * self.scale) / 2 - min(ys) * self.scale
        self.draw()

    def auto_arrange(self):
        """Throw away manual positions and put the places back on the circle."""
        self.positions = circle_layout(self.nodes)
        self.fit_to_window()

    def _to_canvas(self, x, y):
        return x * self.scale + self.off_x, y * self.scale + self.off_y

    def _to_logical(self, cx, cy):
        return (cx - self.off_x) / self.scale, (cy - self.off_y) / self.scale

    def _pt(self, pid):
        """Canvas pixel position of a place."""
        x, y = self.positions[pid]
        return self._to_canvas(x, y)

    def _on_resize(self, _event):
        self.fit_to_window()

    # ----------------------------------------------------------------
    # Drawing
    # ----------------------------------------------------------------
    def draw(self):
        c = self.canvas
        c.delete("all")
        if not self.positions:
            c.create_text(c.winfo_width() / 2, c.winfo_height() / 2,
                          text="No roads loaded.", fill="#6b7280",
                          font=("Helvetica", 12))
            return
        self._draw_roads()
        self._draw_places()

    def _parallel_offsets(self):
        """Roads sharing the same pair of places are fanned out sideways."""
        groups = {}
        for i, r in enumerate(self.roads):
            groups.setdefault(frozenset((r.from_id, r.to_id)), []).append(i)
        offsets = {}
        for idxs in groups.values():
            n = len(idxs)
            for k, i in enumerate(idxs):
                offsets[i] = (k - (n - 1) / 2) * 16
        return offsets

    def _edge_ends(self, r, offset):
        """Pixel start/end of a road, shortened so arrows touch the nodes."""
        a, b = sorted((r.from_id, r.to_id))
        ax, ay = self._pt(a)
        bx, by = self._pt(b)
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        if length < 1:
            return None
        nx, ny = -dy / length, dx / length          # canonical normal
        x1, y1 = self._pt(r.from_id)
        x2, y2 = self._pt(r.to_id)
        x1, y1 = x1 + nx * offset, y1 + ny * offset
        x2, y2 = x2 + nx * offset, y2 + ny * offset
        vx, vy = x2 - x1, y2 - y1
        vl = math.hypot(vx, vy)
        if vl < 2 * NODE_R + 8:
            return None
        ux, uy = vx / vl, vy / vl
        return (x1 + ux * (NODE_R + 2), y1 + uy * (NODE_R + 2),
                x2 - ux * (NODE_R + 4), y2 - uy * (NODE_R + 4))

    def _road_colour(self, r):
        if r.closed:
            return COL_CLOSED
        return COL_UNPAVED if r.road_type == "unpaved" else COL_PAVED

    def _draw_roads(self):
        c = self.canvas
        offsets = self._parallel_offsets()

        for i, r in enumerate(self.roads):
            ends = self._edge_ends(r, offsets[i])
            if ends is None:
                continue
            x1, y1, x2, y2 = ends
            tag = f"road_{i}"
            on_path = i in self.path_roads

            if on_path:
                c.create_line(x1, y1, x2, y2, width=11, fill=COL_PATH_GLOW,
                              capstyle="round", tags=tag)
            if i == self.selected_road:
                c.create_line(x1, y1, x2, y2, width=9, fill=COL_SELECT,
                              capstyle="round", tags=tag)

            opts = dict(width=4 if on_path else 3, fill=self._road_colour(r),
                        arrow=tk.LAST if r.oneway else tk.NONE,
                        arrowshape=(13, 15, 5), capstyle="round", tags=tag)
            if r.road_type == "unpaved":
                opts["dash"] = (8, 5)
            c.create_line(x1, y1, x2, y2, **opts)

            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if self.show_labels.get():
                t = c.create_text(mx, my, text=f"{fmt(r.km)} km · {fmt(r.mins)} min",
                                  font=("Helvetica", 8), fill="#333", tags=tag)
                bb = c.bbox(t)
                bg = c.create_rectangle(bb[0] - 3, bb[1] - 1, bb[2] + 3, bb[3] + 1,
                                        fill=BG, outline="", tags=tag)
                c.tag_lower(bg, t)

            badges = []
            if r.closed:
                badges.append(CLOSED_BADGE)
            if r.condition in CONDITIONS:
                badges.append(CONDITIONS[r.condition])
            elif r.condition != "none":
                badges.append(("?", "#6b7280", pretty(r.condition)))
            for k, (letter, colour, _name) in enumerate(badges):
                bx = mx + (k - (len(badges) - 1) / 2) * 20
                self._badge(c, bx, my - 16, letter, colour, tag)

    @staticmethod
    def _badge(canvas, x, y, letter, colour, tag=""):
        canvas.create_oval(x - 8, y - 8, x + 8, y + 8, fill=colour,
                           outline="white", width=1.5, tags=tag)
        canvas.create_text(x, y, text=letter, fill="white",
                           font=("Helvetica", 8, "bold"), tags=tag)

    def _draw_places(self):
        c = self.canvas
        for pid in self.positions:
            x, y = self._pt(pid)
            fill = COL_NODE
            if pid in self.path_nodes:
                fill = COL_PATH_NODE
                if pid == self.path_nodes[0]:
                    fill = COL_START
                elif pid == self.path_nodes[-1]:
                    fill = COL_END
            if pid == self.selected_node:
                c.create_oval(x - NODE_R - 6, y - NODE_R - 6,
                              x + NODE_R + 6, y + NODE_R + 6,
                              fill=COL_SELECT, outline="")
            c.create_oval(x - NODE_R, y - NODE_R, x + NODE_R, y + NODE_R,
                          fill=fill, outline="white", width=2.5)
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill="white", outline="")
            lx, ly, anchor = self._label_spot(pid, x, y)
            t = c.create_text(lx, ly, text=pretty(pid), anchor=anchor,
                              font=("Helvetica", 10, "bold"), fill="#1b2430")
            bb = c.bbox(t)
            bg = c.create_rectangle(bb[0] - 3, bb[1], bb[2] + 3, bb[3],
                                    fill=BG, outline="")
            c.tag_lower(bg, t)

    def _label_spot(self, pid, x, y):
        """Pick below/above/right/left of the node, whichever side has the
        biggest angular gap between the roads touching it, so a name never
        sits on top of a road end or arrowhead."""
        angles = []
        for r in self.roads:
            other = r.to_id if r.from_id == pid else r.from_id if r.to_id == pid else None
            if other in self.positions:
                ox, oy = self._pt(other)
                if (ox, oy) != (x, y):
                    angles.append(math.atan2(oy - y, ox - x))

        def gap(a):
            return min((abs((a - b + math.pi) % (2 * math.pi) - math.pi)
                        for b in angles), default=math.pi)

        d = NODE_R + 5
        options = [                      # (angle, x, y, anchor, preference bonus)
            (math.pi / 2, x, y + d, "n", 0.4),
            (-math.pi / 2, x, y - d, "s", 0.4),
            (0.0, x + d + 2, y, "w", 0.0),
            (math.pi, x - d - 2, y, "e", 0.0),
        ]
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        text_w = len(pretty(pid)) * 7.5   # rough pixel width

        def score(o):
            _angle, ox, oy, anchor, bonus = o
            left = ox - text_w / 2 if anchor in "ns" else ox - (text_w if anchor == "e" else 0)
            right = left + text_w
            off_canvas = left < 4 or right > w - 4 or oy < 14 or oy > h - 14
            return gap(o[0]) + bonus - (10 if off_canvas else 0)

        best = max(options, key=score)
        return best[1], best[2], best[3]

    def _draw_legend(self):
        lg = self.legend
        lg.delete("all")
        font = ("Helvetica", 9)
        rows = [
            (COL_PAVED, False, False, "Paved, open"),
            (COL_UNPAVED, True, False, "Unpaved, open"),
            (COL_CLOSED, False, False, "Closed road"),
            ("#555", False, True, "One-way (arrow = direction)"),
            ("#555", False, False, "Two-way (no arrow)"),
        ]
        y = 14
        for colour, dashed, arrow, text in rows:
            opts = dict(width=3, fill=colour, arrowshape=(10, 12, 4),
                        arrow=tk.LAST if arrow else tk.NONE)
            if dashed:
                opts["dash"] = (6, 4)
            lg.create_line(10, y, 62, y, **opts)
            lg.create_text(72, y, text=text, anchor="w", font=font)
            y += 24
        y += 2
        for letter, colour, name in [CLOSED_BADGE] + list(CONDITIONS.values()):
            self._badge(lg, 24, y, letter, colour)
            lg.create_text(42, y, text=name, anchor="w", font=font)
            y += 22
        y += 2
        for colour, text in ((COL_START, "Route start"), (COL_PATH_NODE, "Route stop"),
                             (COL_END, "Route end")):
            lg.create_oval(16, y - 7, 30, y + 7, fill=colour, outline="")
            lg.create_text(42, y, text=text, anchor="w", font=font)
            y += 20

    # ----------------------------------------------------------------
    # Mouse interaction
    # ----------------------------------------------------------------
    def _node_at(self, cx, cy):
        for pid in self.positions:
            x, y = self._pt(pid)
            if math.hypot(cx - x, cy - y) <= NODE_R + 4:
                return pid
        return None

    def _road_at(self, cx, cy):
        for item in reversed(self.canvas.find_overlapping(cx - 5, cy - 5, cx + 5, cy + 5)):
            for t in self.canvas.gettags(item):
                if t.startswith("road_"):
                    return int(t[5:])
        return None

    def _on_press(self, e):
        self._press_xy = (e.x, e.y)
        # Moving places edits the map layout, so it is an admin-only action
        self._drag_node = self._node_at(e.x, e.y) if self.is_admin else None
        self._moved = False

    def _on_drag(self, e):
        if self._drag_node is None:
            return
        if not self._moved and math.hypot(e.x - self._press_xy[0],
                                          e.y - self._press_xy[1]) < 4:
            return
        self._moved = True
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        cx = min(max(e.x, NODE_R), w - NODE_R)
        cy = min(max(e.y, NODE_R), h - NODE_R)
        self.positions[self._drag_node][:] = self._to_logical(cx, cy)
        self.draw()

    def _on_release(self, e):
        if self._moved:
            self._drag_node = None
            return
        node = self._node_at(e.x, e.y)
        if node:
            self.select_node(node)
        else:
            road = self._road_at(e.x, e.y)
            self.select_road(road) if road is not None else self.clear_selection()

    def _on_table_select(self, _event):
        if self._syncing:
            return
        sel = self.table.selection()
        if sel:
            self.select_road(int(sel[0]), from_table=True)

    def _on_table_double_click(self, event):
        """Double-clicking a road opens the editor for administrators."""
        if not self.is_admin:
            return
        item = self.table.identify_row(event.y)
        if item:
            self.select_road(int(item), from_table=True)
            self.admin_edit_road()

    # ----------------------------------------------------------------
    # Selection + details panel
    # ----------------------------------------------------------------
    def select_node(self, pid):
        self.selected_node, self.selected_road = pid, None
        self._sync_table(None)
        lines = [pretty(pid), "", "Roads you can leave on:"]
        out = 0
        for r in self.roads:
            if r.from_id == pid:
                other = r.to_id
            elif r.to_id == pid and not r.oneway:
                other = r.from_id
            else:
                continue
            out += 1
            flag = "  [closed]" if r.closed else ""
            lines.append(f" -> {pretty(other)}: {fmt(r.km)} km, {fmt(r.mins)} min{flag}")
        if out == 0:
            lines.append(" (none)")
        self.details.set("\n".join(lines))
        self.side_nb.select(self.sel_tab)
        self.draw()

    def select_road(self, idx, from_table=False):
        self.selected_road, self.selected_node = idx, None
        if not from_table:
            self._sync_table(idx)
        r = self.roads[idx]
        arrow = "->" if r.oneway else "<->"
        self.details.set("\n".join([
            f"{pretty(r.from_id)} {arrow} {pretty(r.to_id)}", "",
            f"Direction : {'One-way' if r.oneway else 'Two-way'}",
            f"Distance  : {fmt(r.km)} km",
            f"Time      : {fmt(r.mins)} min",
            f"Type      : {pretty(r.road_type)}",
            f"Condition : {pretty(r.condition)}",
            f"Status    : {pretty(r.status)}",
        ]))
        self.side_nb.select(self.sel_tab)
        self.draw()

    def clear_selection(self):
        self.selected_node = self.selected_road = None
        self._sync_table(None)
        self._show_hint()
        self.draw()

    def _show_hint(self):
        hint = "Click a place or a road\nto see its details."
        if self.is_admin:
            hint += "\n\nAdmin: drag a place to move it."
        else:
            hint += "\n\nAdministrators can edit the network\nafter logging in."
        self.details.set(hint)

    def _sync_table(self, idx):
        self._syncing = True
        try:
            if idx is None:
                self.table.selection_remove(*self.table.selection())
            else:
                self.table.selection_set(str(idx))
                self.table.see(str(idx))
        finally:
            self._syncing = False


if __name__ == "__main__":
    RoadNetworkApp().mainloop()
