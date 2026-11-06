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
import pyswip
from pyswip import Prolog


Prolog.assertz("father(michael, john)")
Prolog.assertz("father(michael, gina)")




from tkinter import *
from tkinter import ttk

# Root window
root = Tk()
root.geometry('800x500')
root.title('Path Finder Application')

# Notebook
notebook = ttk.Notebook(root)
notebook.pack(padx=10, pady=10, fill='both', expand=True)

# Frames
frame1 = ttk.Frame(notebook)
frame2 = ttk.Frame(notebook)

notebook.add(frame1, text='Network Input')
notebook.add(frame2, text='Profile')

# -----------------------------
# NETWORK INPUT FORM
# -----------------------------

title_label = ttk.Label(
    frame1,
    text="Network Input Form",
    font=("Arial", 16, "bold")
)
title_label.pack(pady=20)

form_frame = ttk.Frame(frame1)
form_frame.pack(pady=10)

# Form fields
fields = [
    "Source",
    "Destination",
    "Distance (In Kilometers)",
    "Travel Time (Mins)",
    "Road Type",
    "Special Condition",
    "Road Status",
]

# Dropdown options
road_type_options = [
    "Paved", "Unpaved"
]

road_status_options = [
    "Open", "Closed"
]

special_condition_options = [
    "None","Broken Cisterns", "Deep Potholes"
]

entries = {}

for i, field in enumerate(fields):

    label = ttk.Label(form_frame, text=field + ":")
    label.grid(row=i, column=0, padx=10, pady=10, sticky="w")

    # Create dropdowns for specific fields
    if field == "Road Type":
        entry = ttk.Combobox(
            form_frame,
            values=road_type_options,
            width=32,
            state="readonly"
        )

    elif field == "Road Status":
        entry = ttk.Combobox(
            form_frame,
            values=road_status_options,
            width=32,
            state="readonly"
        )

    elif field == "Special Condition":
        entry = ttk.Combobox(
            form_frame,
            values=special_condition_options,
            width=32,
            state="readonly"
        )
    elif field == "Distance (In Kilometers)":
        entry = ttk.Spinbox(
            form_frame,
            from_=0.1,
            to=1000,
            increment=0.1,
            width=33
    )
        
    elif field == "Travel Time (Mins)":
        entry = ttk.Spinbox(
            form_frame,
            from_=1,
            to=1440,
            increment=1,
            width=33
        )
    else:
        entry = ttk.Entry(form_frame, width=35)

    entry.grid(row=i, column=1, padx=10, pady=10)

    entries[field] = entry


# Submit button
def submit_form():
    print("Network Information:")

    for field, entry in entries.items():
        print(field, ":", entry.get())


submit_button = ttk.Button(
    form_frame,
    text="Submit",
    command=submit_form
)
submit_button.grid(row=len(fields), column=1, pady=20, sticky="e")


# -----------------------------
# PROFILE TAB
# -----------------------------

profile_label = ttk.Label(
    frame2,
    text="User Profile",
    font=("Arial", 16, "bold")
)
profile_label.pack(pady=20)


root.mainloop()
