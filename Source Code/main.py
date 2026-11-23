"""
Project: Path-Finder for Rural Roads Network in Python/Prolog
Module Name: Artificial Intelligence
Module Code: CIT3003

Group Members:
Chevannese Ellis (2301109),
Jonathan Blackwood (2306822),
Daniel Lowe (2300734),
Jermaine Lewis (2307120),
Tianna Dillion (2205580)

Due Date: Week of Nov 16, 2026


"""

import math
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from prolog_bridge import RoadNetwork, pretty, to_atom
except ImportError as import_error:
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror(
        "Missing component",
        "Could not load the Prolog bridge.\n\n"
        "Install SWI-Prolog and run:  pip install pyswip\n\n"
        f"Details: {import_error}",
    )
    raise SystemExit(1)


BASE_DIR = Path(__file__).resolve().parent
RULES_FILE = BASE_DIR / "road_network.pl"
DATA_FILE = BASE_DIR / "road_data.pl"

ADMIN_USER = "admin"
ADMIN_PASSWORD = "password"


ALGORITHM_NAMES = {
    "dijkstra": "Dijkstra's algorithm",
    "astar": "A* search (terrain / hazard aware)",
    "bfs": "Breadth-first search (fewest roads)",
}


CRITERIA = {
    "Shortest distance": "shortest_distance",
    "Fastest route": "fastest_route",
    "Avoid closed roads": "avoid_closed",
    "Avoid unpaved roads": "avoid_unpaved",
    "Avoid roads with broken cisterns": "avoid_broken_cisterns",
    "Avoid roads with deep potholes": "avoid_deep_potholes",
    "Fewest stops (BFS, ignores closures)": "loose_constraints",
}


INCIDENT_TYPES = {
    "Pothole (enter depth in inches)": "pothole",
    "Falling rocks (enter risk level)": "falling_rocks",
    "Broken cistern": "broken_cistern",
    "Severely damaged road": "severe_damage",
    "Road blocked": "blocked",
    "Seasonal blockage": "seasonal_block",
    "Problem cleared / repaired": "cleared",
}

GREEN = "#1a7f37"
RED = "#b42318"


def fmt_num(value):
    return str(int(value)) if value == int(value) else repr(value)


def fmt_minutes(minutes):
    text = f"{minutes} minutes"
    if minutes >= 60:
        text += f" ({int(minutes // 60)} h {int(minutes % 60)} min)"
    return text


def make_tree(parent, columns, widths=None):
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(holder, columns=columns, show="headings",
                        selectmode="browse")
    for i, name in enumerate(columns):
        tree.heading(name, text=name)
        tree.column(name, width=(widths[i] if widths else 100), anchor="center")
    scroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


class RoadForm(ttk.Frame):

    TYPES = ["Paved", "Unpaved"]
    SPECIALS = ["None", "Broken Cisterns", "Deep Potholes", "Severely Damaged",
                "Falling Rocks"]
    STATUSES = ["Open", "Closed"]
    DIRECTIONS = {"Two-way (both directions)": "yes",
                  "One-way (Source to Destination)": "no"}

    def __init__(self, parent):
        super().__init__(parent)
        self.v_source = tk.StringVar()
        self.v_dest = tk.StringVar()
        self.v_dist = tk.StringVar()
        self.v_time = tk.StringVar()
        self.v_type = tk.StringVar()
        self.v_special = tk.StringVar()
        self.v_status = tk.StringVar()
        self.v_direction = tk.StringVar()

        self.e_source = ttk.Entry(self, textvariable=self.v_source, width=36)
        self.e_dest = ttk.Entry(self, textvariable=self.v_dest, width=36)
        rows = [
            ("Source", self.e_source),
            ("Destination", self.e_dest),
            ("Distance (km)", ttk.Spinbox(self, from_=0.1, to=1000, increment=0.1,
                                          textvariable=self.v_dist, width=34)),
            ("Travel time (mins)", ttk.Spinbox(self, from_=0, to=1440, increment=1,
                                               textvariable=self.v_time, width=34)),
            ("Road type", ttk.Combobox(self, textvariable=self.v_type,
                                       values=self.TYPES, state="readonly", width=33)),
            ("Special condition", ttk.Combobox(self, textvariable=self.v_special,
                                               values=self.SPECIALS, state="readonly",
                                               width=33)),
            ("Road status", ttk.Combobox(self, textvariable=self.v_status,
                                         values=self.STATUSES, state="readonly",
                                         width=33)),
            ("Direction", ttk.Combobox(self, textvariable=self.v_direction,
                                       values=list(self.DIRECTIONS), state="readonly",
                                       width=33)),
        ]
        for i, (label, widget) in enumerate(rows):
            ttk.Label(self, text=label + ":").grid(row=i, column=0, sticky="w",
                                                   padx=8, pady=6)
            widget.grid(row=i, column=1, padx=8, pady=6, sticky="w")

        ttk.Label(
            self, foreground="#57606a",
            text="Choosing Broken Cisterns or Deep Potholes automatically adds "
                 "5 minutes to the travel time."
        ).grid(row=len(rows), column=0, columnspan=2, padx=8, pady=(4, 0), sticky="w")
        self.clear()

    def clear(self):
        self.lock_places(False)
        for var in (self.v_source, self.v_dest, self.v_dist, self.v_time):
            var.set("")
        self.v_type.set(self.TYPES[0])
        self.v_special.set(self.SPECIALS[0])
        self.v_status.set(self.STATUSES[0])
        self.v_direction.set(next(iter(self.DIRECTIONS)))

    def lock_places(self, locked):
        state = "disabled" if locked else "normal"
        self.e_source.config(state=state)
        self.e_dest.config(state=state)

    def set_road(self, road):
        self.v_source.set(pretty(road["source"]))
        self.v_dest.set(pretty(road["destination"]))
        self.v_dist.set(str(road["distance"]))
        self.v_time.set(str(road["time"]))
        self.v_type.set(road["type"].title())
        self.v_special.set(road["special"].replace("_", " ").title())
        self.v_status.set(road["status"].title())
        for label, atom in self.DIRECTIONS.items():
            if atom == road["bidirectional"]:
                self.v_direction.set(label)

    def get_road(self):
        source = to_atom(self.v_source.get())
        dest = to_atom(self.v_dest.get())
        if not source or not dest:
            raise ValueError("Source and destination must be place names: start "
                             "with a letter and use only letters, digits and spaces.")
        if source == dest:
            raise ValueError("Source and destination must be different places.")
        try:
            dist = float(self.v_dist.get())
            mins = float(self.v_time.get())
        except ValueError:
            raise ValueError("Distance and travel time must be numbers.")
        if dist <= 0:
            raise ValueError("Distance must be greater than 0.")
        if mins < 0:
            raise ValueError("Travel time cannot be negative.")
        return {
            "source": source,
            "destination": dest,
            "distance": fmt_num(dist),
            "time": fmt_num(mins),
            "type": self.v_type.get().lower(),
            "special": self.v_special.get().lower().replace(" ", "_"),
            "status": self.v_status.get().lower(),
            "bidirectional": self.DIRECTIONS[self.v_direction.get()],
        }


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Rural Roads Path Finder")
        self.root.geometry("1050x680")
        self.root.minsize(900, 600)
        try:
            ttk.Style().theme_use("clam")
        except tk.TclError:
            pass

        self.net = None
        self.role = None
        self.frame = None
        self.road_lookup = {}
        self.selected_road = None
        self.show_login()

    def run(self):
        self.root.mainloop()


    def clear_screen(self):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = ttk.Frame(self.root)
        self.frame.pack(fill="both", expand=True)

    def connect(self):
        if self.net is not None:
            return True
        try:
            self.net = RoadNetwork(RULES_FILE, DATA_FILE)
            return True
        except Exception as exc:
            messagebox.showerror(
                "Cannot start Prolog",
                "The Prolog engine could not be started.\n\n"
                "Check that SWI-Prolog and pyswip are installed.\n\n"
                f"Details: {exc}")
            return False

    def call(self, function, *args, default=None):
        try:
            return function(*args)
        except Exception as exc:
            messagebox.showerror("System error", f"Something went wrong:\n{exc}")
            return default


    def show_login(self):
        self.clear_screen()
        box = ttk.Frame(self.frame)
        box.place(relx=0.5, rely=0.45, anchor="center")

        ttk.Label(box, text="Rural Roads Path Finder",
                  font=("Arial", 22, "bold")).pack(pady=(0, 4))
        ttk.Label(box, text="Find the best route through the road network",
                  foreground="#57606a").pack(pady=(0, 24))

        ttk.Button(box, text="Continue as User", width=30,
                   command=lambda: self.start("user")).pack(pady=4)

        ttk.Separator(box).pack(fill="x", pady=18)
        ttk.Label(box, text="Administrator login",
                  font=("Arial", 11, "bold")).pack()

        self.v_user = tk.StringVar()
        self.v_pass = tk.StringVar()
        ttk.Label(box, text="User ID:").pack(anchor="w", pady=(10, 0))
        user_entry = ttk.Entry(box, textvariable=self.v_user, width=32)
        user_entry.pack()
        ttk.Label(box, text="Password:").pack(anchor="w", pady=(8, 0))
        pass_entry = ttk.Entry(box, textvariable=self.v_pass, show="*", width=32)
        pass_entry.pack()
        ttk.Button(box, text="Login as Admin", width=30,
                   command=self.try_admin_login).pack(pady=14)
        pass_entry.bind("<Return>", lambda e: self.try_admin_login())
        user_entry.focus_set()

    def try_admin_login(self):
        if (self.v_user.get().strip() == ADMIN_USER
                and self.v_pass.get() == ADMIN_PASSWORD):
            self.start("admin")
        else:
            messagebox.showerror("Login failed", "Incorrect user ID or password.")
            self.v_pass.set("")

    def start(self, role):
        if not self.connect():
            return
        self.role = role
        self.show_main()


    def show_main(self):
        self.clear_screen()
        is_admin = self.role == "admin"

        header = ttk.Frame(self.frame)
        header.pack(fill="x", padx=10, pady=(8, 0))
        ttk.Label(header, text="Rural Roads Path Finder",
                  font=("Arial", 14, "bold")).pack(side="left")
        ttk.Button(header, text="Logout", command=self.show_login).pack(side="right")
        ttk.Label(header, text=f"Signed in as: {self.role.title()}",
                  foreground="#57606a").pack(side="right", padx=12)

        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_route = ttk.Frame(self.notebook)
        self.tab_roads = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_route, text="Find Route")
        self.notebook.add(self.tab_roads, text="Update Network" if is_admin
                          else "Road Network")
        self.build_route_tab()
        self.build_roads_tab(is_admin)

        if is_admin:
            self.tab_add = ttk.Frame(self.notebook)
            self.tab_incident = ttk.Frame(self.notebook)
            self.tab_history = ttk.Frame(self.notebook)
            self.notebook.insert(1, self.tab_add, text="Network Input Form")
            self.notebook.add(self.tab_incident, text="Report Incident (AI)")
            self.notebook.add(self.tab_history, text="History")
            self.build_add_tab()
            self.build_incident_tab()
            self.build_history_tab()

        self.refresh_all()


    def build_route_tab(self):
        tab = self.tab_route
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        left = ttk.Frame(tab)
        left.grid(row=0, column=0, sticky="ns", padx=12, pady=10)
        right = ttk.Frame(tab)
        right.grid(row=0, column=1, sticky="nsew", padx=12, pady=10)


        self.v_start = tk.StringVar()
        self.v_goal = tk.StringVar()
        ttk.Label(left, text="Starting point").pack(anchor="w")
        self.c_start = ttk.Combobox(left, textvariable=self.v_start,
                                    state="readonly", width=28)
        self.c_start.pack(pady=(0, 8))
        ttk.Label(left, text="Destination").pack(anchor="w")
        self.c_goal = ttk.Combobox(left, textvariable=self.v_goal,
                                   state="readonly", width=28)
        self.c_goal.pack(pady=(0, 12))

        ttk.Label(left, text="Route criteria:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.v_objective = tk.StringVar(value="Shortest distance")
        for label in CRITERIA:
            ttk.Radiobutton(left, text=label, value=label,
                            variable=self.v_objective).pack(anchor="w")

        ttk.Button(left, text="Find Route", command=self.on_find_route).pack(
            fill="x", pady=(16, 4))
        ttk.Button(left, text="Swap start / destination",
                   command=self.swap_places).pack(fill="x")


        self.banner = ttk.Label(right, text="Choose a start and destination, "
                                "then press Find Route.",
                                font=("Arial", 12, "bold"))
        self.banner.pack(anchor="w")

        self.result_box = tk.Text(right, height=10, wrap="word", state="disabled",
                                  relief="flat", background="#f6f8fa",
                                  font=("Arial", 10), padx=10, pady=8)
        self.result_box.pack(fill="x", pady=(6, 8))
        self.result_box.tag_configure("bold", font=("Arial", 10, "bold"))
        self.result_box.tag_configure("warn", foreground=RED)

        self.canvas = tk.Canvas(right, width=520, height=320, background="white",
                                highlightthickness=1, highlightbackground="#d0d7de")
        self.canvas.pack(fill="both", expand=True)
        ttk.Label(right, foreground="#57606a",
                  text="Map: blue = chosen route, red dashed = closed road, "
                       "arrow = one-way road.").pack(anchor="w", pady=(4, 0))

    def swap_places(self):
        start, goal = self.v_start.get(), self.v_goal.get()
        self.v_start.set(goal)
        self.v_goal.set(start)

    def write_result(self, lines):
        box = self.result_box
        box.config(state="normal")
        box.delete("1.0", "end")
        for text, tag in lines:
            box.insert("end", text, tag)
        box.config(state="disabled")

    def on_find_route(self):
        start = to_atom(self.v_start.get())
        goal = to_atom(self.v_goal.get())
        if not start or not goal:
            messagebox.showwarning("Missing input",
                                   "Please choose both a starting point and a destination.")
            return

        criterion = CRITERIA[self.v_objective.get()]

        result = self.call(self.net.find_route, criterion, start, goal)
        if result is None:
            return
        self.show_route_result(result, start, goal)
        if self.role == "admin":
            self.refresh_history()

    def show_route_result(self, res, start, goal):
        status = res["status"]
        notes = [n.replace("_", " ") for n in res["notes"]]
        self.draw_map(res["path"] if status == "found" else None)

        if status == "found":
            self.banner.config(text="Route found", foreground=GREEN)
            route = "  →  ".join(pretty(p) for p in res["path"])
            lines = [
                ("Places on the route:\n", "bold"), (route + "\n\n", ""),
                ("Total distance:  ", "bold"), (f"{res['distance']} km\n", ""),
                ("Total travel time:  ", "bold"), (fmt_minutes(res["time"]) + "\n", ""),
                ("Algorithm used:  ", "bold"),
                (ALGORITHM_NAMES.get(res["algorithm"], res["algorithm"]) + "\n", ""),
            ]
            if notes:
                lines.append(("\n", ""))
                lines += [(n + "\n", "warn" if n.startswith("WARNING") else "")
                          for n in notes]
            self.write_result(lines)

        elif status == "no_path":
            self.banner.config(text="No path available", foreground=RED)
            self.write_result(
                [(f"There is no route from {pretty(start)} to {pretty(goal)} "
                  "with the chosen criteria.\n\n", "warn")]
                + [(n + "\n", "") for n in notes])
            messagebox.showwarning(
                "No path available",
                f"No route is available from {pretty(start)} to {pretty(goal)} "
                "with the chosen criteria.")

        elif status == "same_place":
            self.banner.config(text="You are already there", foreground=GREEN)
            self.write_result([("The starting point and destination are the same "
                                "place: 0 km, 0 minutes.\n", "")])

        else:
            self.banner.config(text="Cannot search", foreground=RED)
            self.write_result([("One of the places is not in the road network.\n",
                                "warn")])


    def draw_map(self, path=None):
        canvas = self.canvas
        canvas.delete("all")
        places = self.call(self.net.places, default=[])
        roads = self.call(self.net.roads, default=[])
        if not places:
            return

        width = max(canvas.winfo_width(), 520)
        height = max(canvas.winfo_height(), 320)
        cx, cy = width / 2, height / 2
        radius = min(width, height) / 2 - 45
        position = {}
        for i, place in enumerate(places):
            angle = 2 * math.pi * i / len(places) - math.pi / 2
            position[place] = (cx + radius * math.cos(angle),
                               cy + radius * math.sin(angle))

        on_route = set()
        if path:
            for a, b in zip(path, path[1:]):
                on_route.add((a, b))
                on_route.add((b, a))

        for road in roads:
            s, d = road["source"], road["destination"]
            x1, y1 = position[s]
            x2, y2 = position[d]
            chosen = (s, d) in on_route
            colour = "#1f6feb" if chosen else (
                RED if road["status"] == "closed" else "#8b949e")
            options = {"fill": colour, "width": 4 if chosen else 2}
            if road["status"] == "closed":
                options["dash"] = (5, 3)
            options["arrow"] = tk.LAST if road["bidirectional"] == "no" else tk.NONE
            canvas.create_line(x1, y1, x2, y2, **options)
            canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2 - 8,
                               text=f"{road['distance']} km",
                               fill="#57606a", font=("Arial", 8))

        for place, (x, y) in position.items():
            canvas.create_oval(x - 16, y - 16, x + 16, y + 16, fill="#ffffff",
                               outline="#24292f", width=2)
            canvas.create_text(x, y, text=pretty(place), font=("Arial", 8, "bold"))


    def build_add_tab(self):
        ttk.Label(self.tab_add, text="Network Input Form",
                  font=("Arial", 16, "bold")).pack(pady=(16, 8))
        self.add_form = RoadForm(self.tab_add)
        self.add_form.pack()
        buttons = ttk.Frame(self.tab_add)
        buttons.pack(pady=14)
        ttk.Button(buttons, text="Submit", command=self.on_add_road).pack(
            side="left", padx=6)
        ttk.Button(buttons, text="Clear", command=self.add_form.clear).pack(
            side="left", padx=6)

    def on_add_road(self):
        try:
            road = self.add_form.get_road()
        except ValueError as exc:
            messagebox.showerror("Invalid data", str(exc))
            return
        result = self.call(self.net.add_road, road)
        if result == "ok":
            stored = self.find_stored_road(road["source"], road["destination"])
            extra = ""
            if stored and str(stored["time"]) != road["time"]:
                extra = (f"\n5 minutes were added automatically because of the "
                         f"road condition (stored time: {stored['time']} minutes).")
            messagebox.showinfo("Success", "Road added to the network." + extra)
            self.add_form.clear()
            self.refresh_all()
        elif result is not None:
            messagebox.showerror("Could not add road", result)

    def find_stored_road(self, source, destination):
        for road in self.call(self.net.roads, default=[]):
            if road["source"] == source and road["destination"] == destination:
                return road
        return None


    def build_roads_tab(self, is_admin):
        tab = self.tab_roads
        title = "Update Existing Road Network" if is_admin else "Road Network"
        ttk.Label(tab, text=title, font=("Arial", 16, "bold")).pack(pady=(12, 6))

        columns = ("Source", "Destination", "Distance (km)", "Time (mins)",
                   "Type", "Special", "Status", "Direction")
        self.road_tree = make_tree(tab, columns, (90, 90, 100, 90, 80, 150, 80, 90))
        self.road_tree.tag_configure("closed", foreground=RED)
        if not is_admin:
            return

        self.road_tree.bind("<<TreeviewSelect>>", self.on_road_selected)
        ttk.Label(tab, foreground="#57606a",
                  text="Select a road in the table, change its fields below, then "
                       "press Update Road.").pack(pady=(6, 0))
        self.edit_form = RoadForm(tab)
        self.edit_form.pack(pady=4)
        buttons = ttk.Frame(tab)
        buttons.pack(pady=8)
        ttk.Button(buttons, text="Update Road",
                   command=self.on_update_road).pack(side="left", padx=5)
        ttk.Button(buttons, text="Delete Road",
                   command=self.on_delete_road).pack(side="left", padx=5)
        ttk.Button(buttons, text="Restore Sample Network",
                   command=self.on_reset_roads).pack(side="left", padx=5)
        ttk.Button(buttons, text="Refresh",
                   command=self.refresh_all).pack(side="left", padx=5)

    def refresh_road_table(self):
        tree = self.road_tree
        tree.delete(*tree.get_children())
        for road in self.call(self.net.roads, default=[]):
            tags = ("closed",) if road["status"] == "closed" else ()
            tree.insert("", "end", tags=tags, values=(
                pretty(road["source"]), pretty(road["destination"]),
                road["distance"], road["time"], road["type"].title(),
                road["special"].replace("_", " ").title(),
                road["status"].title(),
                "Two-way" if road["bidirectional"] == "yes" else "One-way"))

    def on_road_selected(self, event=None):
        selection = self.road_tree.selection()
        if not selection:
            return
        values = self.road_tree.item(selection[0])["values"]
        source, destination = to_atom(values[0]), to_atom(values[1])
        road = self.find_stored_road(source, destination)
        if road:
            self.selected_road = (source, destination)
            self.edit_form.set_road(road)
            self.edit_form.lock_places(True)

    def on_update_road(self):
        if not self.selected_road:
            messagebox.showwarning("Nothing selected",
                                   "Select a road in the table first.")
            return
        try:
            road = self.read_edit_form()
        except ValueError as exc:
            messagebox.showerror("Invalid data", str(exc))
            return
        result = self.call(self.net.update_road, road)
        if result == "ok":
            stored = self.find_stored_road(road["source"], road["destination"])
            extra = ""
            if stored and str(stored["time"]) != road["time"]:
                extra = (f"\nThe 5 minute rule was applied automatically "
                         f"(stored time: {stored['time']} minutes).")
            messagebox.showinfo("Success", "Road network updated." + extra)
            self.refresh_all()
        elif result is not None:
            messagebox.showerror("Could not update road", result)

    def read_edit_form(self):
        form = self.edit_form
        form.lock_places(False)
        try:
            return form.get_road()
        finally:
            form.lock_places(True)

    def on_delete_road(self):
        if not self.selected_road:
            messagebox.showwarning("Nothing selected",
                                   "Select a road in the table first.")
            return
        source, destination = self.selected_road
        if not messagebox.askyesno(
                "Delete road",
                f"Delete the road {pretty(source)} → {pretty(destination)}?"):
            return
        result = self.call(self.net.delete_road, source, destination)
        if result == "ok":
            self.selected_road = None
            self.edit_form.clear()
            self.refresh_all()
        elif result is not None:
            messagebox.showerror("Could not delete road", result)

    def on_reset_roads(self):
        if messagebox.askyesno(
                "Restore sample network",
                "This replaces ALL roads with the original sample network.\n"
                "Continue?"):
            self.call(self.net.reset_roads)
            self.selected_road = None
            self.edit_form.clear()
            self.refresh_all()


    def build_incident_tab(self):
        tab = self.tab_incident
        ttk.Label(tab, text="Report an Incident - AI Assessment",
                  font=("Arial", 16, "bold")).pack(pady=(16, 4))
        ttk.Label(tab, foreground="#57606a", justify="center",
                  text="Describe what was seen on a road. The system's rules decide "
                       "the new condition and status, then update the network "
                       "automatically.").pack()

        form = ttk.Frame(tab)
        form.pack(pady=14)
        self.v_inc_road = tk.StringVar()
        self.v_inc_type = tk.StringVar(value=next(iter(INCIDENT_TYPES)))
        self.v_inc_measure = tk.StringVar()

        ttk.Label(form, text="Road:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.c_inc_road = ttk.Combobox(form, textvariable=self.v_inc_road,
                                       state="readonly", width=34)
        self.c_inc_road.grid(row=0, column=1, padx=8, pady=6)

        ttk.Label(form, text="What happened:").grid(row=1, column=0, sticky="w",
                                                    padx=8, pady=6)
        c_type = ttk.Combobox(form, textvariable=self.v_inc_type,
                              values=list(INCIDENT_TYPES), state="readonly", width=34)
        c_type.grid(row=1, column=1, padx=8, pady=6)
        c_type.bind("<<ComboboxSelected>>", self.on_incident_type_changed)

        self.l_measure = ttk.Label(form, text="Measurement:")
        self.l_measure.grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self.c_measure = ttk.Combobox(form, textvariable=self.v_inc_measure, width=34)
        self.c_measure.grid(row=2, column=1, padx=8, pady=6)

        ttk.Button(tab, text="Assess and Update Road",
                   command=self.on_report_incident).pack(pady=6)
        self.incident_box = tk.Text(tab, height=6, width=90, wrap="word",
                                    state="disabled", relief="flat",
                                    background="#f6f8fa", font=("Arial", 10),
                                    padx=10, pady=8)
        self.incident_box.pack(pady=10)
        self.on_incident_type_changed()

    def on_incident_type_changed(self, event=None):
        incident = INCIDENT_TYPES[self.v_inc_type.get()]
        if incident == "pothole":
            self.l_measure.config(text="Depth (inches):")
            self.c_measure.config(state="normal",
                                  values=["1", "2", "3", "4", "5", "6", "8", "10"])
            self.v_inc_measure.set("4")
        elif incident == "falling_rocks":
            self.l_measure.config(text="Risk level:")
            self.c_measure.config(state="readonly", values=["low", "medium", "high"])
            self.v_inc_measure.set("high")
        else:
            self.l_measure.config(text="Measurement:")
            self.v_inc_measure.set("not needed")
            self.c_measure.config(state="disabled", values=[])

    def on_report_incident(self):
        label = self.v_inc_road.get()
        if label not in self.road_lookup:
            messagebox.showwarning("Missing input", "Please choose a road.")
            return
        source, destination = self.road_lookup[label]
        incident = INCIDENT_TYPES[self.v_inc_type.get()]


        if incident == "pothole":
            try:
                measure = fmt_num(float(self.v_inc_measure.get()))
            except ValueError:
                messagebox.showerror("Invalid data",
                                     "Depth must be a number of inches.")
                return
        elif incident == "falling_rocks":
            measure = self.v_inc_measure.get().lower()
        else:
            measure = "yes"

        outcome = self.call(self.net.report_incident, source, destination,
                            incident, measure)
        if outcome is None:
            return
        result, explanation = outcome
        self.incident_box.config(state="normal")
        self.incident_box.delete("1.0", "end")
        if result == "ok":
            self.incident_box.insert("end", "AI assessment:\n" + explanation)
            self.refresh_all()
        else:
            self.incident_box.insert("end", "Could not assess the incident:\n" + result)
        self.incident_box.config(state="disabled")


    def build_history_tab(self):
        tab = self.tab_history
        ttk.Label(tab, text="Route requests", font=("Arial", 12, "bold")).pack(
            anchor="w", padx=10, pady=(10, 2))
        self.route_tree = make_tree(
            tab, ("When", "From", "To", "Criteria", "Algorithm",
                  "Outcome", "Km", "Mins"),
            (130, 70, 70, 220, 90, 90, 60, 60))
        ttk.Label(tab, text="Incident reports", font=("Arial", 12, "bold")).pack(
            anchor="w", padx=10, pady=(10, 2))
        self.incident_tree = make_tree(
            tab, ("When", "Road", "Incident", "Measure", "New condition",
                  "New status"),
            (130, 140, 120, 80, 150, 100))
        ttk.Button(tab, text="Clear History", command=self.on_clear_history).pack(
            pady=8)

    def refresh_history(self):
        self.route_tree.delete(*self.route_tree.get_children())
        for h in reversed(self.call(self.net.route_history, default=[])):
            self.route_tree.insert("", "end", values=(
                h["when"], pretty(h["start"]), pretty(h["goal"]),
                h["criterion"].replace("_", " "),
                h["algorithm"], h["status"].replace("_", " "),
                h["distance"], h["time"]))
        self.incident_tree.delete(*self.incident_tree.get_children())
        for h in reversed(self.call(self.net.incident_history, default=[])):
            self.incident_tree.insert("", "end", values=(
                h["when"], h["road"].title().replace("_", " "),
                h["incident"].replace("_", " "), h["measure"],
                h["condition"].replace("_", " "), h["status"]))

    def on_clear_history(self):
        if messagebox.askyesno("Clear history",
                               "Delete all stored route requests and incident reports?"):
            self.call(self.net.clear_history)
            self.refresh_history()


    def refresh_all(self):
        places = [pretty(p) for p in self.call(self.net.places, default=[])]
        self.c_start.config(values=places)
        self.c_goal.config(values=places)
        for var in (self.v_start, self.v_goal):
            if var.get() not in places:
                var.set("")

        self.refresh_road_table()
        self.draw_map()

        if self.role == "admin":
            roads = self.call(self.net.roads, default=[])
            self.road_lookup = {
                f"{pretty(r['source'])} → {pretty(r['destination'])}":
                    (r["source"], r["destination"]) for r in roads}
            self.c_inc_road.config(values=list(self.road_lookup))
            if self.v_inc_road.get() not in self.road_lookup:
                self.v_inc_road.set("")
            self.refresh_history()


if __name__ == "__main__":
    App().run()
