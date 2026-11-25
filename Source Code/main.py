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

Due Date: Nov 25, 2026


"""
from pyswip import *
from pyswip import Prolog




from tkinter import *
from tkinter.messagebox import showinfo, showerror
from tkinter.ttk import *
from pathlib import Path
import os
import re
import json
import math
from datetime import datetime


PENALTY_CONDITIONS = {"broken_cisterns", "deep_potholes"}
PENALTY_MINUTES = 5

COLUMNS = ("Source", "Destination", "Distance", "Time", "Type", "Special", "Status", "Direction")

# Dropdown values for the editable table (stored in Prolog format)
DROPDOWNS = {
    "Type": ["paved", "unpaved"],
    "Special": ["none", "broken_cisterns", "severely_damaged_road",
                "blocked_road", "deep_potholes", "falling_rocks",
                "seasonally_blocked"],
    "Status": ["open", "closed"],
    "Direction": ["two_way", "one_way"],
}



FACT_PATTERN = re.compile(
    r"location\(source\((.*?)\),destination\((.*?)\),distance\((.*?)\),"
    r"time\((.*?)\),type\((.*?)\),special\((.*?)\),status\((.*?)\)"
    r"(?:,bidirectional\((.*?)\))?\)\."
)

tree = None  # set when the Update Network tab is built

def fmt_time(t):
    return int(t) if float(t) == int(t) else float(t)

def load_road_data():
    rows = []
    if file_path.exists():
        with open(file_path) as f:
            for line in f:
                m = FACT_PATTERN.match(line.strip())
                if m:
                    # facts saved without a bidirectional part are two-way roads
                    row = list(m.groups())
                    row[7] = "one_way" if row[7] == "no" else "two_way"
                    rows.append(tuple(row))
    return rows


def row_to_fact(v):
    clean = lambda x: str(x).strip().lower().replace(" ", "_")
    return (
        f"location(source({clean(v[0])}),destination({clean(v[1])}),"
        f"distance({str(v[2]).strip()}),time({str(v[3]).strip()}),"
        f"type({clean(v[4])}),special({clean(v[5])}),status({clean(v[6])}),"
        f"bidirectional({'no' if str(v[7]) == 'one_way' else 'yes'}))."
    )


def refresh_table():
    if tree is None:
        return
    tree.delete(*tree.get_children())
    for row in load_road_data():
        tree.insert("", END, values=row)


def save_table():
    # Validate numbers first
    for iid in tree.get_children():
        v = tree.item(iid)["values"]
        try:
            float(v[2])
            float(v[3])
        except ValueError:
            showerror("Invalid data", f"Distance and Time must be numbers (row: {v[0]} -> {v[1]}).")
            return
    with open(file_path, "w") as f:
        for iid in tree.get_children():
            f.write(row_to_fact(tree.item(iid)["values"]) + "\n")
    # send the saved roads to Prolog so route finding uses them
    load_into_prolog()
    refresh_places()
    refresh_incident_roads()
    showinfo("Success", "Road network updated.")


def delete_selected():
    for iid in tree.selection():
        tree.delete(iid)


active_editor = None


def apply_special_change(iid, old_special, new_special):
    """Add/remove the 5-minute penalty when the Special condition changes."""
    # roads that are blocked or badly damaged are closed automatically
    if new_special in FORCE_CLOSED:
        tree.set(iid, "Status", "closed")
    try:
        t = float(tree.set(iid, "Time"))
    except ValueError:
        return
    if new_special in PENALTY_CONDITIONS and old_special not in PENALTY_CONDITIONS:
        t += PENALTY_MINUTES
    elif old_special in PENALTY_CONDITIONS and new_special not in PENALTY_CONDITIONS:
        t -= PENALTY_MINUTES
    tree.set(iid, "Time", fmt_time(max(t, 0)))


def close_editor(event=None):
    global active_editor
    if active_editor is not None and active_editor.winfo_exists():
        active_editor.destroy()
    active_editor = None


def on_double_click(event):
    global active_editor
    if tree.identify_region(event.x, event.y) != "cell":
        return
    close_editor()

    iid = tree.identify_row(event.y)
    col = tree.identify_column(event.x)
    name = COLUMNS[int(col[1:]) - 1]
    x, y, w, h = tree.bbox(iid, col)
    old = str(tree.set(iid, name)).strip()

    is_dropdown = name in DROPDOWNS
    if is_dropdown:
        editor = Combobox(tree, values=DROPDOWNS[name], state="readonly")
        editor.set(old)
    else:
        editor = Entry(tree)
        editor.insert(0, old)
        editor.select_range(0, END)

    active_editor = editor
    editor.place(x=x, y=y, width=w, height=h)
    editor.focus_set()

    def commit(e=None):
        if not editor.winfo_exists():
            return
        new = editor.get().strip()
        if name == "Special" and new != old:
            apply_special_change(iid, old, new)
        tree.set(iid, name, new)
        close_editor()

    editor.bind("<Return>", commit)
    editor.bind("<Escape>", close_editor)
    if is_dropdown:
        editor.bind("<<ComboboxSelected>>", commit)   # commit only on a real selection
    else:
        editor.bind("<FocusOut>", commit)             # text cells still commit on click-away

    def cancel(e=None):
        if editor.winfo_exists():
            editor.destroy()

    editor.bind("<Return>", commit)
    editor.bind("<FocusOut>", commit)
    editor.bind("<Escape>", cancel)
    if name in DROPDOWNS:
        editor.bind("<<ComboboxSelected>>", commit)


# Conditions that make a road unusable, so the road is closed automatically
FORCE_CLOSED = {"severely_damaged_road", "blocked_road", "seasonally_blocked"}

# Route criterion shown to the user -> criterion name used by find_route/6 in road_network.pl
CRITERIA = {
    "Shortest distance": "shortest_distance",
    "Fastest route": "fastest_route",
    "Avoid closed roads": "avoid_closed",
    "Avoid unpaved roads": "avoid_unpaved",
    "Avoid roads with broken cisterns": "avoid_broken_cisterns",
    "Avoid roads with deep potholes": "avoid_deep_potholes",
    "Fewest stops (BFS, ignores closures)": "loose_constraints",
}

# Algorithm that road_network.pl runs for each criterion (shown in the result)
ALGORITHMS = {
    "shortest_distance": "Dijkstra's algorithm",
    "fastest_route": "Dijkstra's algorithm",
    "avoid_closed": "Dijkstra's algorithm",
    "avoid_unpaved": "A* search",
    "avoid_broken_cisterns": "A* search",
    "avoid_deep_potholes": "A* search",
    "loose_constraints": "Breadth-first search",
}

# Incident types for the AI tab: label shown -> rule name used by assess_incident()
INCIDENT_TYPES = {
    "Pothole (enter depth in inches)": "pothole",
    "Falling rocks (enter risk level)": "falling_rocks",
    "Broken cistern": "broken_cistern",
    "Severely damaged road": "severe_damage",
    "Road blocked": "blocked",
    "Seasonal blockage": "seasonal_block",
    "Problem cleared / repaired": "cleared",
}

# Severity ranking so a minor report never replaces a worse condition
SEVERITY = {"none": 0, "broken_cisterns": 1, "deep_potholes": 1, "falling_rocks": 2,
            "severely_damaged_road": 3, "blocked_road": 3, "seasonally_blocked": 3}

# History of route requests and incident reports is kept here, not in road_network.pl
history_path = Path("road_history.json")

route_widgets = {}
incident_widgets = {}
history_trees = {}


# Turns user text such as "St Ann" into a valid Prolog atom (st_ann); returns "" if it cannot
def to_atom(text):
    atom = re.sub(r"\s+", "_", str(text).strip().lower())
    return atom if re.match(r"^[a-z][a-z0-9_]*$", atom) else ""


def pretty(atom):
    return str(atom).replace("_", " ").title()


# pyswip may hand back str, bytes or an Atom object; always return plain text
def text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if hasattr(value, "value") and not isinstance(value, (int, float, str)):
        return str(value.value)
    return str(value)


# Minutes to add or remove when a road's condition changes (the 5-minute rule)
def penalty_change(old, new):
    if new in PENALTY_CONDITIONS and old not in PENALTY_CONDITIONS:
        return PENALTY_MINUTES
    if old in PENALTY_CONDITIONS and new not in PENALTY_CONDITIONS:
        return -PENALTY_MINUTES
    return 0


# Save a list of rows to road_data.pl
def write_rows(rows):
    with open(file_path, "w") as f:
        for row in rows:
            f.write(row_to_fact(row) + "\n")


# True if a road between the two places exists already (same direction, or a two-way road the other way)
def road_exists(source, destination, bidirectional):
    for r in load_road_data():
        a, b, two_way = to_atom(r[0]), to_atom(r[1]), r[7] == "two_way"
        if (a, b) == (source, destination):
            return True
        if (b, a) == (source, destination) and (two_way or bidirectional == "yes"):
            return True
    return False


# Replace the roads held in Prolog with the roads saved in road_data.pl
def load_into_prolog():
    list(prolog.query("delallroad"))
    for r in load_road_data():
        atoms = [to_atom(r[0]), to_atom(r[1]), to_atom(r[4]), to_atom(r[5]), to_atom(r[6])]
        if not all(atoms):
            continue
        direction = "no" if r[7] == "one_way" else "yes"
        list(prolog.query(
            f"addroad({atoms[0]},{atoms[1]},{r[2]},{r[3]},{atoms[2]},{atoms[3]},{atoms[4]},{direction})"))


# Append one history record (kind is "routes" or "incidents") to road_history.json
def log_event(kind, record):
    record = dict(record, kind=kind, when=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with open(history_path, "a") as f:
        f.write(json.dumps(record) + "\n")


def read_events(kind):
    events = []
    if history_path.exists():
        with open(history_path) as f:
            for line in f:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if record.get("kind") == kind:
                    events.append(record)
    return events


# Warnings for the roads on a route: closed, unpaved or with a special condition
def route_notes(path, rows):
    notes = []
    for a, b in zip(path, path[1:]):
        for r in rows:
            forward = (to_atom(r[0]), to_atom(r[1])) == (a, b)
            backward = (to_atom(r[0]), to_atom(r[1])) == (b, a) and r[7] == "two_way"
            if forward or backward:
                if r[6] == "closed":
                    notes.append(f"WARNING: the road {pretty(a)} to {pretty(b)} is CLOSED.")
                if r[4] == "unpaved":
                    notes.append(f"Note: the road {pretty(a)} to {pretty(b)} is unpaved.")
                if r[5] != "none":
                    notes.append(f"Note: the road {pretty(a)} to {pretty(b)} has {r[5].replace('_', ' ')}.")
                break
    return notes


# Asks Prolog (find_route/6 in road_network.pl) for a route.
# Returns (status, path, distance, time, notes)
def run_route(criterion, source, destination):
    rows = load_road_data()
    places = {to_atom(r[0]) for r in rows} | {to_atom(r[1]) for r in rows}
    if source not in places or destination not in places:
        return "unknown_place", [], 0, 0, []
    if source == destination:
        return "same_place", [source], 0, 0, []
    found = list(prolog.query(
        f"find_route({criterion},{source},{destination},P,D,T)", maxresult=1))
    if found:
        path = [text(p) for p in found[0]["P"]]
        return ("found", path, fmt_time(round(float(found[0]["D"]), 2)),
                fmt_time(round(float(found[0]["T"]), 2)), route_notes(path, rows))
    loose = list(prolog.query(
        f"find_route(loose_constraints,{source},{destination},P,D,T)", maxresult=1))
    if loose:
        return "no_path", [], 0, 0, ["A route exists, but only through roads your criteria exclude."]
    return "no_path", [], 0, 0, ["No road connects these places in this direction (check one-way roads)."]


# Find Route tab: choose two places and one criterion, then show the route Prolog finds
def build_route_tab(frame):
    left = Frame(frame)
    left.pack(side="left", fill="y", padx=15, pady=15)
    right = Frame(frame)
    right.pack(side="left", fill="both", expand=True, padx=15, pady=15)

    Label(left, text="Starting point").pack(anchor="w")
    route_widgets["start"] = Combobox(left, state="readonly", width=28)
    route_widgets["start"].pack(pady=(0, 8))
    Label(left, text="Destination").pack(anchor="w")
    route_widgets["goal"] = Combobox(left, state="readonly", width=28)
    route_widgets["goal"].pack(pady=(0, 12))

    Label(left, text="Route criteria:", font=("Arial", 10, "bold")).pack(anchor="w")
    route_widgets["criterion"] = StringVar(value="Shortest distance")
    for label in CRITERIA:
        Radiobutton(left, text=label, value=label,
                    variable=route_widgets["criterion"]).pack(anchor="w")
    Button(left, text="Find Route", command=find_route_action).pack(fill="x", pady=(14, 4))
    Button(left, text="Swap start / destination", command=swap_places).pack(fill="x")

    route_widgets["banner"] = Label(right, text="Choose a start and destination, then press Find Route.",
                                    font=("Arial", 12, "bold"))
    route_widgets["banner"].pack(anchor="w")
    route_widgets["result"] = Text(right, height=14, wrap="word", state="disabled")
    route_widgets["result"].pack(fill="both", expand=True, pady=8)


def swap_places():
    start, goal = route_widgets["start"].get(), route_widgets["goal"].get()
    route_widgets["start"].set(goal)
    route_widgets["goal"].set(start)


# Refresh the place lists in Find Route after the network changes
def refresh_places():
    if "start" not in route_widgets:
        return
    rows = load_road_data()
    places = sorted({to_atom(r[0]) for r in rows} | {to_atom(r[1]) for r in rows})
    names = [pretty(p) for p in places]
    for key in ("start", "goal"):
        route_widgets[key]["values"] = names
        if route_widgets[key].get() not in names:
            route_widgets[key].set("")


def show_result(box, content):
    box.config(state="normal")
    box.delete("1.0", END)
    box.insert(END, content)
    box.config(state="disabled")


# Runs the route search, shows places / distance / time or the no-path notice, and stores the request
def find_route_action():
    source = to_atom(route_widgets["start"].get())
    destination = to_atom(route_widgets["goal"].get())
    if not source or not destination:
        showerror("Missing input", "Please choose both a starting point and a destination.")
        return

    criterion_label = route_widgets["criterion"].get()
    criterion = CRITERIA[criterion_label]
    status, path, distance, minutes, notes = run_route(criterion, source, destination)

    if status == "found":
        current_route["path"] = path
        route_widgets["banner"].config(
            text=f"Route found: {'  →  '.join(pretty(p) for p in path)}"
        )
        content = (
            "Places on the route:\n" + "  →  ".join(pretty(p) for p in path) +
            f"\n\nTotal distance: {distance} km"
            f"\nTotal travel time: {minutes} minutes"
            f"\nAlgorithm used: {ALGORITHMS[criterion]}"
        )
        if notes:
            content += "\n\n" + "\n".join(notes)
        show_result(route_widgets["result"], content)
    elif status == "no_path":
        current_route["path"] = []
        route_widgets["banner"].config(text="No path available")
        show_result(
            route_widgets["result"],
            f"There is no route from {pretty(source)} to {pretty(destination)} "
            f"with the chosen criteria.\n\n" + "\n".join(notes)
        )
        showinfo("No path available",
                 f"No route is available from {pretty(source)} to {pretty(destination)} "
                 "with the chosen criteria.")
    elif status == "same_place":
        current_route["path"] = path
        route_widgets["banner"].config(text="You are already at your destination")
        show_result(route_widgets["result"],
                    "Start and destination are the same place: 0 km, 0 minutes.")
    else:
        current_route["path"] = []
        route_widgets["banner"].config(text="Cannot search")
        show_result(route_widgets["result"],
                    "One of the places is not in the road network.")

    draw_map()
    log_event("routes", {"criterion": criterion, "start": source, "goal": destination,
                         "status": status, "distance": distance, "time": minutes})
    refresh_history()

# AI rule base: turns a reported incident into (new special condition, new status, explanation).
# None for either value means "leave unchanged". Returns None if the measurement is invalid.
def assess_incident(incident, measure):
    if incident == "pothole":
        try:
            depth = float(measure)
        except ValueError:
            return None
        if depth > 3:
            return ("deep_potholes", None, "Pothole deeper than 3 inches: marked as deep potholes (+5 minutes).")
        return (None, None, "Pothole of 3 inches or less is minor: road left unchanged.")
    if incident == "falling_rocks":
        if measure == "high":
            return ("falling_rocks", "closed", "High risk of falling rocks: road closed for safety.")
        if measure == "medium":
            return ("falling_rocks", None, "Medium risk of falling rocks: road stays open but is flagged.")
        if measure == "low":
            return (None, None, "Low risk of falling rocks: road left unchanged.")
        return None
    if incident == "broken_cistern":
        return ("broken_cisterns", None, "Broken cistern reported: flagged (+5 minutes).")
    if incident == "severe_damage":
        return ("severely_damaged_road", "closed", "Severely damaged road: closed until repaired.")
    if incident == "blocked":
        return ("blocked_road", "closed", "Road blocked: closed until cleared.")
    if incident == "seasonal_block":
        return ("seasonally_blocked", "closed", "Seasonal blockage: road closed for the season.")
    if incident == "cleared":
        return ("none", "open", "Problem cleared: road restored to normal and reopened.")
    return None


# Report Incident (AI) tab: the system decides the road's new condition and status from the report
def build_incident_tab(frame):
    Label(frame, text="Report an Incident - AI Assessment", font=("Arial", 16, "bold")).pack(pady=15)
    form = Frame(frame)
    form.pack()
    Label(form, text="Road:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
    incident_widgets["road"] = Combobox(form, state="readonly", width=34)
    incident_widgets["road"].grid(row=0, column=1, padx=8, pady=8)
    Label(form, text="What happened:").grid(row=1, column=0, sticky="w", padx=8, pady=8)
    incident_widgets["type"] = Combobox(form, state="readonly", width=34, values=list(INCIDENT_TYPES))
    incident_widgets["type"].grid(row=1, column=1, padx=8, pady=8)
    incident_widgets["type"].current(0)
    incident_widgets["type"].bind("<<ComboboxSelected>>", on_incident_type)
    incident_widgets["measure_label"] = Label(form, text="Depth (inches):")
    incident_widgets["measure_label"].grid(row=2, column=0, sticky="w", padx=8, pady=8)
    incident_widgets["measure"] = Combobox(form, width=34)
    incident_widgets["measure"].grid(row=2, column=1, padx=8, pady=8)
    Button(frame, text="Assess and Update Road", command=report_incident_action).pack(pady=10)
    incident_widgets["result"] = Text(frame, height=6, width=90, wrap="word", state="disabled")
    incident_widgets["result"].pack(pady=10)
    on_incident_type()


# Show the right measurement input for the chosen incident type
def on_incident_type(event=None):
    incident = INCIDENT_TYPES[incident_widgets["type"].get()]
    box = incident_widgets["measure"]
    if incident == "pothole":
        incident_widgets["measure_label"].config(text="Depth (inches):")
        box.config(state="normal", values=["1", "2", "3", "4", "5", "6", "8", "10"])
        box.set("4")
    elif incident == "falling_rocks":
        incident_widgets["measure_label"].config(text="Risk level:")
        box.config(state="readonly", values=["low", "medium", "high"])
        box.set("high")
    else:
        incident_widgets["measure_label"].config(text="Measurement:")
        box.config(state="normal", values=[])
        box.set("not needed")
        box.config(state="disabled")


def refresh_incident_roads():
    if "road" not in incident_widgets:
        return
    labels = [f"{pretty(to_atom(r[0]))} -> {pretty(to_atom(r[1]))}" for r in load_road_data()]
    incident_widgets["road"]["values"] = labels
    if incident_widgets["road"].get() not in labels:
        incident_widgets["road"].set("")


# Applies the AI assessment to the chosen road: updates its condition, status and time
# (including the 5-minute rule), saves it, reloads Prolog and stores the report
def report_incident_action():
    label = incident_widgets["road"].get()
    rows = [list(r) for r in load_road_data()]
    index = None
    for i, r in enumerate(rows):
        if f"{pretty(to_atom(r[0]))} -> {pretty(to_atom(r[1]))}" == label:
            index = i
    if index is None:
        showerror("Missing input", "Please choose a road.")
        return
    incident = INCIDENT_TYPES[incident_widgets["type"].get()]
    measure = incident_widgets["measure"].get().strip().lower() if incident in ("pothole", "falling_rocks") else "yes"
    outcome = assess_incident(incident, measure)
    if outcome is None:
        showerror("Invalid data", "Pothole needs a depth in inches; falling rocks needs low, medium or high.")
        return
    new_special, new_status, why = outcome

    row = rows[index]
    old_special, old_status, old_time = row[5], row[6], float(row[3])
    if incident == "cleared":
        special = "none"
    elif new_special and SEVERITY[new_special] >= SEVERITY.get(old_special, 0):
        special = new_special
    else:
        special = old_special
    status = new_status or old_status
    if special in FORCE_CLOSED:
        status = "closed"
    new_time = fmt_time(max(0, old_time + penalty_change(old_special, special)))
    row[3], row[5], row[6] = str(new_time), special, status

    write_rows(rows)
    load_into_prolog()
    refresh_table()
    refresh_places()
    show_result(incident_widgets["result"],
                f"AI assessment:\n{why}\nCondition: {old_special} -> {special}\n"
                f"Status: {old_status} -> {status}\nTime: {fmt_time(old_time)} -> {new_time} min")
    log_event("incidents", {"road": label, "incident": incident, "measure": measure,
                            "condition": special, "status": status})
    refresh_history()


# History tab: stored route requests and incident reports
def build_history_tab(frame):
    Label(frame, text="Route requests", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
    routes = ("When", "From", "To", "Criteria", "Outcome", "Km", "Mins")
    history_trees["routes"] = Treeview(frame, columns=routes, show="headings", height=7)
    incidents = ("When", "Road", "Incident", "Measure", "New condition", "New status")
    history_trees["incidents"] = Treeview(frame, columns=incidents, show="headings", height=7)
    for key, columns in (("routes", routes), ("incidents", incidents)):
        for c in columns:
            history_trees[key].heading(c, text=c)
            history_trees[key].column(c, width=110, anchor="center")
        history_trees[key].pack(fill="x", padx=10)
        if key == "routes":
            Label(frame, text="Incident reports", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 2))


def refresh_history():
    if "routes" not in history_trees:
        return
    for key in ("routes", "incidents"):
        history_trees[key].delete(*history_trees[key].get_children())
    for e in reversed(read_events("routes")):
        history_trees["routes"].insert("", END, values=(
            e["when"], pretty(e["start"]), pretty(e["goal"]), e["criterion"].replace("_", " "),
            e["status"].replace("_", " "), e["distance"], e["time"]))
    for e in reversed(read_events("incidents")):
        history_trees["incidents"].insert("", END, values=(
            e["when"], e["road"], e["incident"].replace("_", " "), e["measure"],
            e["condition"].replace("_", " "), e["status"]))


# run from this file's folder so road_network.pl and road_data.pl are found
os.chdir(Path(__file__).resolve().parent)
print(os.getcwd())
# File path
default_road_network_data = [
    "location(source(a),destination(b),distance(5),time(10),type(paved),special(none),status(open)).",
    "location(source(b),destination(c),distance(3),time(15),type(unpaved),special(broken_cisterns),status(open)).",
    "location(source(c),destination(d),distance(7),time(12),type(paved),special(deep_potholes),status(closed))."
]
# Roads added or edited in the app are saved here; road_network.pl is never written to
file_path = Path("road_data.pl")
rules_path = Path("road_network.pl")

# Check if the file exists
if file_path.exists():
    print("Loaded: Road Network Data")
else:
    with open(file_path, "w") as file:
        for line in default_road_network_data:
            file.write(line + "\n")
    print("Creation: Default Road Network Data")

# Start Prolog, load the unchanged road_network.pl rules, then copy the saved roads into it
prolog = Prolog()
prolog.consult(rules_path.as_posix())
load_into_prolog()

#Login Page
def login_window():
    # Create the main window
    parent = Tk()
    parent.geometry('800x500')
    parent.title("Login Form")

    # Create and place the username label and entry
    username_label = Label(parent, text="Userid:")
    username_label.pack()

    username_entry = Entry(parent)
    username_entry.pack()

    # Create and place the password label and entry
    password_label = Label(parent, text="Password:")
    password_label.pack()

    password_entry = Entry(parent, show="*")  # Show asterisks for password
    password_entry.pack()

    # Create and place the login button
    login_button = Button(parent, text="Login", command=lambda: login(username_entry.get(), password_entry.get(), parent))
    login_button.pack()

    # users find routes without a password
    user_button = Button(parent, text="Continue as User", command=lambda: user_login(parent))
    user_button.pack(pady=10)

    # Start the Tkinter event loop
    parent.mainloop()

# ---------------------------------------------------------------------------
# MAP-BASED USER INTERFACE
# ---------------------------------------------------------------------------

map_canvas = None
map_positions = {}
selection_text = None
map_labels_var = None
current_route = {"path": []}
main_root = None
mode_label = None


def road_style(row):
    """Return the map colour and line style for a road record."""
    road_type, status = str(row[4]).lower(), str(row[6]).lower()
    if status == "closed":
        return "#c0392b", "solid"
    if road_type == "unpaved":
        return "#bd842d", "dotted"
    return "#34845f", "solid"


def condition_marker(special):
    """Return a compact marker label and colour for a road condition."""
    markers = {
        "broken_cisterns": ("C", "#3689bd"),
        "deep_potholes": ("P", "#914caf"),
        "falling_rocks": ("R", "#e18a32"),
        "severely_damaged_road": ("D", "#8e2929"),
        "blocked_road": ("X", "#c0392b"),
        "seasonally_blocked": ("S", "#8e2929"),
    }
    return markers.get(str(special).lower())


def draw_map(event=None):
    """Draw all road connections and place nodes on the map canvas."""
    global map_positions
    if map_canvas is None or not map_canvas.winfo_exists():
        return

    map_canvas.delete("all")
    width = max(map_canvas.winfo_width(), 300)
    height = max(map_canvas.winfo_height(), 250)
    rows = load_road_data()
    places = sorted({to_atom(r[0]) for r in rows} | {to_atom(r[1]) for r in rows})
    if not places:
        map_positions = {}
        map_canvas.create_text(width / 2, height / 2,
                               text="No roads in the network",
                               fill="#667085", font=("Arial", 15))
        return

    # Circular auto-layout. The first place is placed at the top.
    cx, cy = width / 2, height / 2
    rx, ry = max(70, width * 0.37), max(70, height * 0.36)
    map_positions = {}
    count = len(places)
    for i, place in enumerate(places):
        angle = (-math.pi / 2) + (2 * math.pi * i / count)
        map_positions[place] = (cx + rx * math.cos(angle),
                                cy + ry * math.sin(angle))

    path = current_route.get("path", [])
    route_edges = set(zip(path, path[1:]))

    # Draw roads first so location nodes appear above them.
    for row in rows:
        a, b = to_atom(row[0]), to_atom(row[1])
        if a not in map_positions or b not in map_positions:
            continue
        x1, y1 = map_positions[a]
        x2, y2 = map_positions[b]
        colour, style = road_style(row)
        highlighted = (a, b) in route_edges or (
            row[7] == "two_way" and (b, a) in route_edges
        )
        map_canvas.create_line(
            x1, y1, x2, y2,
            fill="#1769aa" if highlighted else colour,
            width=5 if highlighted else 3,
            dash=(3, 3) if style == "dotted" else None,
            arrow="last" if row[7] == "one_way" else "none",
            arrowshape=(12, 15, 5),
            tags=("road",)
        )

        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if map_labels_var is None or map_labels_var.get():
            label = f"{row[2]} km  ·  {row[3]} min"
            map_canvas.create_rectangle(mx - 55, my - 12, mx + 55, my + 12,
                                        fill="#f7f7f4", outline="")
            map_canvas.create_text(mx, my, text=label,
                                   fill="#333333", font=("Arial", 9),
                                   tags=("road_label",))

        marker = condition_marker(row[5])
        if marker:
            marker_text, marker_colour = marker
            # Place the condition marker slightly above the road midpoint.
            map_canvas.create_oval(mx - 9, my - 28, mx + 9, my - 10,
                                   fill=marker_colour, outline="white", width=1)
            map_canvas.create_text(mx, my - 19, text=marker_text,
                                   fill="white", font=("Arial", 8, "bold"))

        if str(row[6]).lower() == "closed":
            map_canvas.create_text(mx - 14, my - 28, text="×",
                                   fill="#c0392b", font=("Arial", 12, "bold"))

    # Draw place nodes.
    for place, (x, y) in map_positions.items():
        map_canvas.create_oval(x - 19, y - 19, x + 19, y + 19,
                               fill="#244766", outline="white", width=3,
                               tags=("place", f"place:{place}"))
        map_canvas.create_oval(x - 5, y - 5, x + 5, y + 5,
                               fill="white", outline="white",
                               tags=("place", f"place:{place}"))
        map_canvas.create_text(x, y + 31, text=pretty(place),
                               fill="#202020", font=("Arial", 10),
                               tags=("place_label", f"place:{place}"))

    map_canvas.tag_bind("place", "<Button-1>", on_map_place_click)


def on_map_place_click(event):
    """Show information about the location nearest the user's click."""
    if not map_positions:
        return
    closest = min(map_positions, key=lambda p:
                  (map_positions[p][0] - event.x) ** 2 +
                  (map_positions[p][1] - event.y) ** 2)
    x, y = map_positions[closest]
    if (x - event.x) ** 2 + (y - event.y) ** 2 > 30 ** 2:
        return
    if selection_text is not None:
        selection_text.config(state="normal")
        selection_text.delete("1.0", END)
        selection_text.insert(
            END, f"Selected location: {pretty(closest)}\n\n"
                 "Connected roads:\n"
        )
        found = False
        for row in load_road_data():
            a, b = to_atom(row[0]), to_atom(row[1])
            if closest in (a, b):
                found = True
                selection_text.insert(
                    END, f"\n{pretty(a)} → {pretty(b)}\n"
                         f"Distance: {row[2]} km\n"
                         f"Travel time: {row[3]} min\n"
                         f"Type: {row[4]}\n"
                         f"Condition: {row[5].replace('_', ' ')}\n"
                         f"Status: {row[6]}\n"
                         f"Direction: {row[7].replace('_', ' ')}\n"
                )
        if not found:
            selection_text.insert(END, "No connected roads.")
        selection_text.config(state="disabled")


def clear_route():
    current_route["path"] = []
    if "banner" in route_widgets:
        route_widgets["banner"].config(text="Choose a start and destination.")
    if "result" in route_widgets:
        show_result(route_widgets["result"], "No route is currently displayed.")
    draw_map()


def fit_map():
    draw_map()


def auto_arrange():
    draw_map()


def reload_network():
    load_into_prolog()
    refresh_places()
    refresh_table()
    refresh_incident_roads()
    draw_map()
    showinfo("Reload", "Road network reloaded from road_data.pl and Prolog.")


def refresh_places():
    if "start" not in route_widgets:
        return
    rows = load_road_data()
    places = sorted({to_atom(r[0]) for r in rows} | {to_atom(r[1]) for r in rows})
    names = [pretty(p) for p in places]
    for key in ("start", "goal"):
        route_widgets[key]["values"] = names
        if route_widgets[key].get() not in names:
            route_widgets[key].set("")
    draw_map()


def show_legend(parent):
    legend = Frame(parent, padding=10)
    legend.pack(fill="both", expand=True)

    items = [
        ("#34845f", None, "Paved, open", None),
        ("#bd842d", (3, 3), "Unpaved, open", None),
        ("#c0392b", None, "Closed road", None),
        ("#555555", None, "One-way (arrow = direction)", "arrow"),
        ("#555555", None, "Two-way (no arrow)", None),
    ]
    for i, (colour, dash, label, arrow) in enumerate(items):
        sample = Canvas(legend, width=62, height=22, highlightthickness=0)
        sample.create_line(4, 11, 56, 11, fill=colour, width=3,
                           dash=dash, arrow="last" if arrow else "none")
        sample.grid(row=i, column=0, padx=5, pady=3)
        Label(legend, text=label).grid(row=i, column=1, sticky="w", padx=5)

    conditions = [
        ("#c0392b", "X", "Road closed"),
        ("#3689bd", "C", "Broken cisterns"),
        ("#914caf", "P", "Deep potholes"),
        ("#e18a32", "R", "Risk of falling rocks"),
        ("#8e2929", "D", "Severely damaged"),
    ]
    for j, (colour, letter, label) in enumerate(conditions, start=len(items)):
        sample = Canvas(legend, width=62, height=22, highlightthickness=0)
        sample.create_oval(23, 2, 41, 20, fill=colour, outline="white")
        sample.create_text(32, 11, text=letter, fill="white",
                           font=("Arial", 8, "bold"))
        sample.grid(row=j, column=0, padx=5, pady=3)
        Label(legend, text=label).grid(row=j, column=1, sticky="w", padx=5)

def admin_login_dialog():
    """Switch from user mode to the existing administrator interface."""
    if main_root is None:
        return
    dialog = Toplevel(main_root)
    dialog.title("Administrator login")
    dialog.transient(main_root)
    dialog.grab_set()
    dialog.resizable(False, False)
    box = Frame(dialog, padding=18)
    box.pack(fill="both", expand=True)
    Label(box, text="Administrator login",
          font=("Arial", 13, "bold")).grid(row=0, column=0, columnspan=2,
                                           pady=(0, 12))
    Label(box, text="User ID:").grid(row=1, column=0, sticky="w", pady=5)
    user_entry = Entry(box, width=24)
    user_entry.grid(row=1, column=1, pady=5)
    Label(box, text="Password:").grid(row=2, column=0, sticky="w", pady=5)
    pass_entry = Entry(box, width=24, show="*")
    pass_entry.grid(row=2, column=1, pady=5)

    def check_login():
        if user_entry.get() == "admin" and pass_entry.get() == "password":
            dialog.destroy()
            main_root.destroy()
            main_window("admin")
        else:
            showerror("Login failed", "Incorrect user ID or password.")

    Button(box, text="Login", command=check_login).grid(
        row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0)
    )
    user_entry.focus_set()


def main_window(role="user"):
    global tree, map_canvas, map_labels_var, selection_text
    global main_root, mode_label, entries

    entries = {}
    root = Tk()
    main_root = root
    root.title("Rural Roads Path-Finder | UTech Jamaica")
    root.geometry("1500x900")
    root.minsize(1050, 650)
    root.configure(bg="#eeeeee")

    # Top toolbar.
    toolbar = Frame(root, padding=(10, 8))
    toolbar.pack(side="top", fill="x")
    Button(toolbar, text="Reload from Prolog",
           command=reload_network).pack(side="left", padx=(0, 8))
    Button(toolbar, text="Fit to window", command=fit_map).pack(side="left", padx=4)
    Button(toolbar, text="Auto-arrange", command=auto_arrange).pack(side="left", padx=4)

    map_labels_var = BooleanVar(value=True)
    Checkbutton(toolbar, text="Show distance / time labels",
                variable=map_labels_var, command=draw_map).pack(side="left", padx=10)

    Button(toolbar, text="Clear route", command=clear_route).pack(side="right", padx=4)
    mode_label = Label(toolbar, text=f"Mode: {'Admin' if role == 'admin' else 'User'}",
                       font=("Arial", 9, "bold"), padding=(10, 5))
    mode_label.pack(side="right", padx=5)
    if role == "admin":
        Button(toolbar, text="User mode",
               command=lambda: (root.destroy(), main_window("user"))).pack(side="right", padx=4)
    else:
        Button(toolbar, text="Admin login",
               command=admin_login_dialog).pack(side="right", padx=4)

    # Main content: map/table on the left, route controls and details on the right.
    content = Frame(root, padding=(10, 0, 10, 10))
    content.pack(fill="both", expand=True)
    content.columnconfigure(0, weight=4)
    content.columnconfigure(1, weight=1)
    content.rowconfigure(0, weight=1)

    left_notebook = Notebook(content)
    left_notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    map_tab = Frame(left_notebook)
    roads_tab = Frame(left_notebook)
    left_notebook.add(map_tab, text="Map")
    left_notebook.add(roads_tab, text="Roads table")

    map_canvas = Canvas(map_tab, bg="#f7f7f4", highlightthickness=1,
                        highlightbackground="#dddddd")
    map_canvas.pack(fill="both", expand=True)
    map_canvas.bind("<Configure>", draw_map)

    # Roads table is available in both modes; editing is enabled for admins.
    table_frame = Frame(roads_tab, padding=8)
    table_frame.pack(fill="both", expand=True)
    tree = Treeview(table_frame, columns=COLUMNS, show="headings",
                    selectmode="extended")
    for col in COLUMNS:
        tree.heading(col, text=col)
        tree.column(col, width=105, anchor="center")
    scroll_y = Scrollbar(table_frame, orient="vertical", command=tree.yview)
    scroll_x = Scrollbar(table_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x.grid(row=1, column=0, sticky="ew")
    table_frame.rowconfigure(0, weight=1)
    table_frame.columnconfigure(0, weight=1)

    if role == "admin":
        tree.bind("<Double-1>", on_double_click)
        tree.bind("<Button-1>", close_editor, add="+")
        buttons = Frame(roads_tab, padding=8)
        buttons.pack(fill="x")
        Button(buttons, text="Save Changes", command=save_table).pack(side="left", padx=4)
        Button(buttons, text="Delete Selected", command=delete_selected).pack(side="left", padx=4)
        Button(buttons, text="Refresh", command=refresh_table).pack(side="left", padx=4)


    # Administrator-only network input form (kept from the original application).
    if role == "admin":
        input_tab = Frame(left_notebook)
        left_notebook.add(input_tab, text="Network input")
        Label(input_tab, text="Add a road to the network",
              font=("Arial", 15, "bold")).pack(pady=12)
        form_frame = Frame(input_tab, padding=10)
        form_frame.pack()
        fields = [
            "Source", "Destination", "Distance (In Kilometers)",
            "Travel Time (Mins)", "Road Type", "Special Condition",
            "Road Status", "Direction"
        ]
        options = {
            "Road Type": ["Paved", "Unpaved"],
            "Special Condition": [
                "None", "Broken Cisterns", "Severely Damaged Road",
                "Blocked Road", "Deep Potholes", "Falling Rocks",
                "Seasonally Blocked"
            ],
            "Road Status": ["Open", "Closed"],
            "Direction": ["Two-way", "One-way"],
        }
        for i, field in enumerate(fields):
            Label(form_frame, text=field + ":").grid(
                row=i, column=0, padx=10, pady=7, sticky="w"
            )
            if field in options:
                widget = Combobox(form_frame, values=options[field],
                                  width=32, state="readonly")
                widget.current(0)
            elif field == "Distance (In Kilometers)":
                widget = Spinbox(form_frame, from_=0.1, to=1000,
                                 increment=0.1, width=33)
            elif field == "Travel Time (Mins)":
                widget = Spinbox(form_frame, from_=1, to=1440,
                                 increment=1, width=33)
            else:
                widget = Entry(form_frame, width=35)
            widget.grid(row=i, column=1, padx=10, pady=7)
            entries[field] = widget
        Button(form_frame, text="Submit road", command=submit_form).grid(
            row=len(fields), column=1, pady=15, sticky="e"
        )

    # Right-hand route search panel.
    right = Frame(content, width=370)
    right.grid(row=0, column=1, sticky="nsew")
    right.grid_propagate(False)
    route_box = LabelFrame(right, text="Find a route", padding=12)
    route_box.pack(fill="x", pady=(0, 12))
    route_widgets["start"] = Combobox(route_box, state="readonly")
    route_widgets["goal"] = Combobox(route_box, state="readonly")
    route_widgets["criterion"] = Combobox(
        route_box, state="readonly", values=list(CRITERIA.keys())
    )
    route_widgets["criterion"].set("Shortest distance")

    Label(route_box, text="From").grid(row=0, column=0, sticky="w", pady=5)
    route_widgets["start"].grid(row=0, column=1, sticky="ew", pady=5)
    Label(route_box, text="To").grid(row=1, column=0, sticky="w", pady=5)
    route_widgets["goal"].grid(row=1, column=1, sticky="ew", pady=5)
    Label(route_box, text="Criteria").grid(row=2, column=0, sticky="w", pady=5)
    route_widgets["criterion"].grid(row=2, column=1, sticky="ew", pady=5)
    route_box.columnconfigure(1, weight=1)
    Button(route_box, text="Find route", command=find_route_action).grid(
        row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0)
    )

    detail_notebook = Notebook(right)
    detail_notebook.pack(fill="both", expand=True)
    selection_tab = Frame(detail_notebook)
    legend_tab = Frame(detail_notebook)
    detail_notebook.add(selection_tab, text="Selection")
    detail_notebook.add(legend_tab, text="Legend")

    route_widgets["banner"] = Label(selection_tab, text="Select a place or find a route.",
                                    anchor="w", justify="left",
                                    font=("Arial", 10, "bold"), wraplength=320)
    route_widgets["banner"].pack(fill="x", padx=8, pady=8)
    route_widgets["result"] = Text(selection_tab, height=12, wrap="word",
                                   state="disabled", relief="flat")
    route_widgets["result"].pack(fill="both", expand=True, padx=8, pady=5)
    selection_text = Text(selection_tab, height=10, wrap="word",
                          state="disabled", relief="flat")
    selection_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    show_legend(legend_tab)

    # Retain the incident and history tools for administrator mode.
    if role == "admin":
        admin_tab = Frame(detail_notebook)
        detail_notebook.add(admin_tab, text="Admin tools")
        admin_tools = Notebook(admin_tab)
        admin_tools.pack(fill="both", expand=True)
        incident_tab = Frame(admin_tools)
        history_tab = Frame(admin_tools)
        admin_tools.add(incident_tab, text="Incident")
        admin_tools.add(history_tab, text="History")
        build_incident_tab(incident_tab)
        build_history_tab(history_tab)

    refresh_table()
    refresh_places()
    refresh_incident_roads()
    refresh_history()
    draw_map()
    root.mainloop()

# Submit button
def submit_form():
    source = to_atom(entries["Source"].get())
    destination = to_atom(entries["Destination"].get())
    distance = entries["Distance (In Kilometers)"].get()
    travel_time = entries["Travel Time (Mins)"].get()
    road_type = entries["Road Type"].get().lower().replace(" ", "_")
    special = entries["Special Condition"].get().lower().replace(" ", "_")
    status = entries["Road Status"].get().lower()
    direction = entries["Direction"].get().lower().replace("-", "_")
    bidirectional = "no" if direction == "one_way" else "yes"

    # reject bad input and duplicates, add the 5-minute penalty and close unusable roads
    if not source or not destination:
        showerror("Invalid data", "Source and destination must be place names: start with a letter and use only letters, digits and spaces.")
        return
    if source == destination:
        showerror("Invalid data", "Source and destination must be different places.")
        return
    try:
        distance_value = float(distance)
        time_value = float(travel_time)
    except ValueError:
        showerror("Invalid data", "Distance and Time must be numbers.")
        return
    if distance_value <= 0 or time_value < 0:
        showerror("Invalid data", "Distance must be greater than 0 and Time cannot be negative.")
        return
    if road_exists(source, destination, bidirectional):
        showerror("Duplicate road", "That road already exists. Use Update Network to change it.")
        return
    extra = ""
    penalty = penalty_change("none", special)
    if penalty:
        extra += f"\n{penalty} minutes were added because of the road condition."
    if special in FORCE_CLOSED:
        status = "closed"
        extra += "\nThe road was set to closed because of its condition."
    distance = str(fmt_time(distance_value))
    travel_time = str(fmt_time(time_value + penalty))

    # Create Prolog fact
    fact = (
        f"location(source({source}),"
        f"destination({destination}),"
        f"distance({distance}),"
        f"time({travel_time}),"
        f"type({road_type}),"
        f"special({special}),"
        f"status({status}),"
        f"bidirectional({bidirectional}))."
    )

    # Write to file
    with open(file_path, "a") as file:
        file.write(fact + "\n")
    
    print("Successfully Added New Location: ", fact)

    # send the new road to Prolog and refresh the other tabs
    load_into_prolog()
    refresh_table()
    refresh_places()
    refresh_incident_roads()

    showinfo("Success", "Road network data saved." + extra)




def login(username, password, window):
    if (username == "admin" and password == "password"):
        showinfo("Login Successful", "Welcome, Admin!")
        window.destroy()
        main_window()
    else:
        showerror("Login Failed", "Incorrect user ID or password.")
        
# opens the app with only the Find Route tab
def user_login(window):
    window.destroy()
    main_window("user")


main_window("user")


