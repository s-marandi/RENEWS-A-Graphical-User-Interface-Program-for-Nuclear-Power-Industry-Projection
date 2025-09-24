import os
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk


class WelcomePage:
    def __init__(self, root, start_callback):
        self.root = root
        self.start_callback = start_callback
        self.root.geometry("1000x600")
        self.root.title("RENEWS: Reactor Expansion & Nuclear Employment Workforce Simulator")

        # Set window icon
        self.set_window_icon("Icon.png")

        # Style Configuration
        self.apply_styles()

        # Create a main frame
        self.frame = ttk.Frame(root, padding="20", style="Welcome.TFrame")
        self.frame.pack(expand=True, fill="both")

        # Add background styling
        self.add_background()

        # Add logo
        self.add_logo()

        # **Title**
        welcome_message = ttk.Label(
            self.frame, text="RENEWS", font=("Helvetica", 32, "bold"), anchor="center", style="Title.TLabel"
        )
        welcome_message.pack(pady=(20, 5))

        # **Subtitle**
        subtitle = ttk.Label(
            self.frame,
            text="Reactor Expansion & Nuclear Employment Workforce Simulator",
            font=("Helvetica", 16, "italic"),
            anchor="center",
            style="Subtitle.TLabel"
        )
        subtitle.pack(pady=(0, 20))

        # **Description**
        description = ttk.Label(
            self.frame,
            text=(
                "A simulation tool for analyzing nuclear reactor expansions, workforce demands, "
                "job categorization, uranium requirements, and future capacity trends."
            ),
            justify="center",
            font=("Arial", 14),
            wraplength=800,
            style="Body.TLabel",
            anchor="center"
        )
        description.pack(pady=(10, 30), fill="x", expand=True)

        # Buttons Section
        self.add_user_manual_button()
        self.add_contact_button()

        # **Start Button**
        start_button = ttk.Button(
            self.frame, text="Start Simulation", command=self.start_app, style="Start.TButton", width=20
        )
        start_button.pack(pady=20)

        # Footer Information
        self.add_developed_by()
        self.add_version_info()

    def apply_styles(self):
        style = ttk.Style()

        # **Start Button Styling - Improved Font Color**
        style.configure("Start.TButton", font=("Helvetica", 14, "bold"),
                        foreground="#00274C",  # Dark Blue Text (No White)
                        background="#007BFF",
                        padding=10, borderwidth=0)

        # **Hover Effect (Only Background Changes, Text Stays Same)**
        style.map("Start.TButton",
                  background=[("active", "#0056b3")])  # Darker blue on hover, no text color change

    def set_window_icon(self, icon_path):
        if os.path.exists(icon_path):
            icon_image = Image.open(icon_path)
            icon_photo = ImageTk.PhotoImage(icon_image)
            self.root.iconphoto(True, icon_photo)

    def add_background(self):
        """Adds a background image to the frame"""
        try:
            bg_image = Image.open("background_image.png")
            bg_image = bg_image.resize((1000, 600), Image.ANTIALIAS)
            bg_photo = ImageTk.PhotoImage(bg_image)

            bg_label = tk.Label(self.frame, image=bg_photo)
            bg_label.image = bg_photo
            bg_label.place(relwidth=1, relheight=1)
        except FileNotFoundError:
            pass

    def add_logo(self):
        """Adds a logo to the top of the welcome page"""
        if os.path.exists("logo.png"):
            logo_image = Image.open("logo.png").resize((120, 120), Image.ANTIALIAS)
            logo_photo = ImageTk.PhotoImage(logo_image)

            logo_label = ttk.Label(self.frame, image=logo_photo, background="#f5f5f5")
            logo_label.image = logo_photo
            logo_label.pack(pady=(10, 10))

    def add_contact_button(self):
        contact_button = ttk.Button(self.frame, text="📩 Contact Us", command=self.open_contact_form,
                                    style="Link.TButton")
        contact_button.pack(pady=(10, 0))

    def open_contact_form(self):
        messagebox.showinfo("Contact", "Please contact us at smarandi@umd.edu")

    def add_version_info(self):
        version_label = ttk.Label(self.frame, text="Version 1.0", font=("Arial", 10, "italic"), style="Body.TLabel")
        version_label.pack(side="bottom", pady=(5, 10))

    def add_developed_by(self):
        dev_label = ttk.Label(
            self.frame, text="Developed by University of Maryland - Center for Risk and Reliability",
            font=("Arial", 10, "italic"), style="Body.TLabel"
        )
        dev_label.pack(side="bottom", pady=(5, 10))

    def add_user_manual_button(self):
        manual_button = ttk.Button(self.frame, text="📖 User Manual", command=self.open_user_manual,
                                   style="Link.TButton")
        manual_button.pack(pady=(10, 0))

    def open_user_manual(self):
        filepath = "path_to_user_manual.pdf"
        if os.path.exists(filepath):
            os.system(f'start {filepath}')
        else:
            messagebox.showerror("Error", "User manual not found.")

    def start_app(self):
        self.frame.destroy()
        self.start_callback()
