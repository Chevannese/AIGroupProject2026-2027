"""
Project: Path-Finder for Rural Roads Network in Python/Prolog
Course: CIT3003
Group Members:
Chevannese Ellis (2301109),
Jonathan Blackwood (2306822),
Daniel Lowe (2300734),
Jermaine 

Due Date: Week of Nov 16, 2026


"""
from pyswip import *




from tkinter import *
from tkinter.messagebox import showinfo, showerror
from tkinter.ttk import *
from pathlib import Path
import os
import re

COLUMNS = ("Source", "Destination", "Distance", "Time", "Type", "Special", "Status")

# Dropdown values for the editable table (stored in Prolog format)
DROPDOWNS = {
    "Type": ["paved", "unpaved", "seasonally_blocked", "one_way"],
    "Special": ["none", "broken_cisterns", "severely_damaged_road",
                "blocked_road", "deep_potholes", "falling_rocks"],
    "Status": ["open", "closed"],
}

FACT_PATTERN = re.compile(
    r"location\(source\((.*?)\),destination\((.*?)\),distance\((.*?)\),"
    r"time\((.*?)\),type\((.*?)\),special\((.*?)\),status\((.*?)\)\)\."
)

tree = None  # set when the Update Network tab is built


def load_road_data():
    rows = []
    if file_path.exists():
        with open(file_path) as f:
            for line in f:
                m = FACT_PATTERN.match(line.strip())
                if m:
                    rows.append(m.groups())
    return rows


def row_to_fact(v):
    clean = lambda x: str(x).strip().lower().replace(" ", "_")
    return (
        f"location(source({clean(v[0])}),destination({clean(v[1])}),"
        f"distance({str(v[2]).strip()}),time({str(v[3]).strip()}),"
        f"type({clean(v[4])}),special({clean(v[5])}),status({clean(v[6])}))."
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
    showinfo("Success", "Road network updated.")


def delete_selected():
    for iid in tree.selection():
        tree.delete(iid)


def on_double_click(event):
    if tree.identify_region(event.x, event.y) != "cell":
        return
    iid = tree.identify_row(event.y)
    col = tree.identify_column(event.x)
    idx = int(col[1:]) - 1
    name = COLUMNS[idx]
    x, y, w, h = tree.bbox(iid, col)
    old = tree.set(iid, name)

    if name in DROPDOWNS:
        editor = Combobox(tree, values=DROPDOWNS[name], state="readonly")
        editor.set(old)
    else:
        editor = Entry(tree)
        editor.insert(0, old)
        editor.select_range(0, END)

    editor.place(x=x, y=y, width=w, height=h)
    editor.focus_set()

    def commit(e=None):
        if editor.winfo_exists():
            tree.set(iid, name, editor.get())
            editor.destroy()

    def cancel(e=None):
        if editor.winfo_exists():
            editor.destroy()

    editor.bind("<Return>", commit)
    editor.bind("<FocusOut>", commit)
    editor.bind("<Escape>", cancel)
    if name in DROPDOWNS:
        editor.bind("<<ComboboxSelected>>", commit)


print(os.getcwd())
# File path
default_road_network_data = [
    "location(source(a),destination(b),distance(5),time(10),type(paved),special(none),status(open)).",
    "location(source(b),destination(c),distance(3),time(15),type(unpaved),special(broken_cisterns),status(open)).",
    "location(source(c),destination(d),distance(7),time(12),type(paved),special(deep_potholes),status(closed))."
]
file_path = Path("road_network.pl")

# Check if the file exists
if file_path.exists():
    print("Loaded: Road Network Data")
else:
    with open(file_path, "w") as file:
        for line in default_road_network_data:
            file.write(line + "\n")
    print("Creation: Default Road Network Data")

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

    # Start the Tkinter event loop
    parent.mainloop()

def main_window():
    global entries
    entries = {}


    # Root window
    root = Tk()
    root.geometry('800x500')
    root.title('Path Finder Application')

    # Notebook
    notebook = Notebook(root)
    notebook.pack(padx=10, pady=10, fill='both', expand=True)

    # Frames
    frame1 = Frame(notebook)
    frame2 = Frame(notebook)

    notebook.add(frame1, text='Network Input Form')
    notebook.add(frame2, text='Update Network')

  
    #NETWORK INPUT FORM


    title_label = Label(
        frame1,
        text="Network Input Form",
        font=("Arial", 16, "bold")
    )
    title_label.pack(pady=20)

    form_frame = Frame(frame1)
    form_frame.pack(pady=10)
    
    # Form fields
    fields = [
        "Source",
        "Destination",
        "Distance (In Kilometers)",
        "Travel Time (Mins)",
        "Road Type",
        "Special Condition",
        "Road Status"
    ]

    # Dropdown options
    road_type_options = [
        "Paved", "Unpaved","Seasonally Blocked", "One Way"
    ]

    road_status_options = [
        "Open", "Closed"
    ]

    special_condition_options = [
        "None","Broken Cisterns", "Severely Damaged Road", "Blocked Road", "Deep Potholes", "Falling Rocks"
    ]

    for i, field in enumerate(fields):

        label = Label(form_frame, text=field + ":")
        label.grid(row=i, column=0, padx=10, pady=10, sticky="w")

        # Create dropdowns for specific fields
        if field == "Road Type":
            entry = Combobox(
                form_frame,
                values=road_type_options,
                width=32,
                state="readonly"
            )

        elif field == "Road Status":
            entry = Combobox(
                form_frame,
                values=road_status_options,
                width=32,
                state="readonly"
            )

        elif field == "Special Condition":
            entry = Combobox(
                form_frame,
                values=special_condition_options,
                width=32,
                state="readonly"
            )
        elif field == "Distance (In Kilometers)":
            entry = Spinbox(
                form_frame,
                from_=0.1,
                to=1000,
                increment=0.1,
                width=33
        )
            
        elif field == "Travel Time (Mins)":
            entry = Spinbox(
                form_frame,
                from_=1,
                to=1440,
                increment=1,
                width=33
            )
        else:
            entry = Entry(form_frame, width=35)

        entry.grid(row=i, column=1, padx=10, pady=10)

        entries[field] = entry
        
            
    submit_button = Button(
        form_frame,
        text="Submit",
        command=submit_form
    )
    submit_button.grid(row=len(fields), column=1, pady=20, sticky="e")


    # -----------------------------
    # UPDATE NETWORK TABLE
    # -----------------------------

    update_network_label = Label(
        frame2,
        text="Update Existing Road Networks",
        font=("Arial", 16, "bold")
    )
    update_network_label.pack(pady=10)

    global tree
    table_frame = Frame(frame2)
    table_frame.pack(fill="both", expand=True, padx=10)

    tree = Treeview(table_frame, columns=COLUMNS, show="headings", selectmode="extended")
    for c in COLUMNS:
        tree.heading(c, text=c)
        tree.column(c, width=100, anchor="center")

    scroll = Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    tree.bind("<Double-1>", on_double_click)

    button_frame = Frame(frame2)
    button_frame.pack(pady=10)
    Button(button_frame, text="Save Changes", command=save_table).pack(side="left", padx=5)
    Button(button_frame, text="Delete Selected", command=delete_selected).pack(side="left", padx=5)
    Button(button_frame, text="Refresh", command=refresh_table).pack(side="left", padx=5)

    refresh_table()

    root.mainloop()





# Submit button
def submit_form():
    source = entries["Source"].get().lower()
    destination = entries["Destination"].get().lower()
    distance = entries["Distance (In Kilometers)"].get()
    travel_time = entries["Travel Time (Mins)"].get()
    road_type = entries["Road Type"].get().lower().replace(" ", "_")
    special = entries["Special Condition"].get().lower().replace(" ", "_")
    status = entries["Road Status"].get().lower()

    # Create Prolog fact
    fact = (
        f"location(source({source}),"
        f"destination({destination}),"
        f"distance({distance}),"
        f"time({travel_time}),"
        f"type({road_type}),"
        f"special({special}),"
        f"status({status}))."
    )

    # Write to file
    with open(file_path, "a") as file:
        file.write(fact + "\n")
    
    print("Successfully Added New Location: ", fact)

    showinfo("Success", "Road network data saved.")




def login(username, password, window):
    if (username == "admin" and password == "password"):
        showinfo("Login Successful", "Welcome, Admin!")
        window.destroy()
        main_window()
        
login_window()
