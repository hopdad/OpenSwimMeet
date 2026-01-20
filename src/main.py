import tkinter as tk
from customtkinter import CTk  # Modern look
from src.app import SwimMeetApp

if __name__ == "__main__":
    root = CTk()
    root.title("OpenSwimMeet - Open Source Swim Meet Manager")
    root.geometry("1200x800")
    root.iconbitmap("resources/icons/app.ico")  # Add your icon

    app = SwimMeetApp(root)
    root.mainloop()
