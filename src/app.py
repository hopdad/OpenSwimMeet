import customtkinter as ctk
from src.database import init_db, open_meet_db
from src.ui.main_window import MainWindow

class SwimMeetApp:
    def __init__(self, root):
        self.root = root
        self.root.configure(fg_color="#f0f0f0")
        ctk.set_appearance_mode("light")  # or "dark"
        ctk.set_default_color_theme("blue")

        self.current_meet_path = None
        self.db_conn = None

        self.show_welcome_screen()

    def show_welcome_screen(self):
        # Clear window
        for widget in self.root.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self.root)
        frame.pack(fill="both", expand=True, padx=40, pady=40)

        ctk.CTkLabel(frame, text="Welcome to OpenSwimMeet", font=("Arial", 28, "bold")).pack(pady=20)
        ctk.CTkLabel(frame, text="Offline swimming meet management – intuitive & Hy-Tek compatible", font=("Arial", 14)).pack(pady=10)

        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(pady=40)

        ctk.CTkButton(btn_frame, text="New Meet", width=200, height=60, command=self.new_meet).pack(pady=10)
        ctk.CTkButton(btn_frame, text="Open Existing Meet", width=200, height=60, command=self.open_meet).pack(pady=10)
        ctk.CTkButton(btn_frame, text="Import Entries Only (Away Team)", width=200, height=60, fg_color="green").pack(pady=10)

    def new_meet(self):
        # TODO: Wizard for meet name, date, pool, events
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("Meet Database", "*.db")])
        if path:
            self.current_meet_path = path
            self.db_conn = init_db(path)
            self.show_main_window()

    def open_meet(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("Meet Database", "*.db")])
        if path:
            self.current_meet_path = path
            self.db_conn = open_meet_db(path)
            self.show_main_window()

    def show_main_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        MainWindow(self.root, self.db_conn, self.current_meet_path)
