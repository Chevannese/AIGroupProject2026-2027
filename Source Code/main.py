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


Prolog.assertz("location(source(a),destination(b),distance(5),time(10),type(paved),special(none),status(open))")
Prolog.assertz("location(source(b),destination(c),distance(3),time(15),type(unpaved),special(broken_cisterns),status(open))")
Prolog.assertz("location(source(c),destination(d),distance(7),time(12),type(paved),special(deep_potholes),status(closed))")

from tkinter import *
from tkinter.messagebox import showinfo
from tkinter.ttk import *



def login_window():
    # Create the main window
    parent = Tk()
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

    notebook.add(frame1, text='Network Input')
    notebook.add(frame2, text='Profile')

    # -----------------------------
    # NETWORK INPUT FORM
    # -----------------------------

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
    # PROFILE TAB
    # -----------------------------

    profile_label = ttk.Label(
        frame2,
        text="User Profile",
        font=("Arial", 16, "bold")
    )
    profile_label.pack(pady=20)


# Submit button
def submit_form():
    print("Network Information:")

    for field, entry in entries.items():
        print(field, ":", entry.get())


def login(username, password, window):
    if (username == "admin" and password == "password"):
        showinfo("Login Successful", "Welcome, Admin!")
        window.destroy()
        main_window()
        
login_window()
