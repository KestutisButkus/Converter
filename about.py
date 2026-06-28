import os
import tkinter as tk
from tkinter import scrolledtext
import hardware


class AboutWindow(tk.Toplevel):

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("About Video Converter")
        self.geometry("500x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        main_frame = tk.Frame(self, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        # KAIRĖ PUSĖ: Logotipo sritis
        left_frame = tk.Frame(main_frame, width=130, height=240, bg="#f0f0f0")
        left_frame.pack(side="left", anchor="n", padx=(0, 15))
        left_frame.pack_propagate(False)

        img_path = hardware.find_resource("converter.png")
        if img_path and os.path.exists(img_path):
            self.about_img = tk.PhotoImage(file=img_path)
            tk.Label(left_frame, image=self.about_img, bg="#f0f0f0").pack(expand=True)
        else:
            left_frame.config(bg="#3b6ea8")
            tk.Label(left_frame, text="video", bg="#3b6ea8", fg="#000000", font=("Segoe UI", 12)).pack(pady=(40, 0))
            tk.Label(left_frame, text="CONV", bg="#3b6ea8", fg="#172033", font=("Segoe UI", 16, "bold")).pack()

        # DEŠINĖ PUSĖ: Informacija
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side="left", fill="both", expand=True)

        tk.Label(right_frame, text="Video Converter", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(right_frame, text="Version 1.0", font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))
        tk.Label(right_frame, text="Copyright © 2026 Kęstutis Butkus", font=("Segoe UI", 8)).pack(anchor="w", pady=(10, 15))

        desc_text = scrolledtext.ScrolledText(
            right_frame, height=8, font=("Segoe UI", 8), relief="solid",
            borderwidth=1, wrap="word", padx=5, pady=5
        )
        desc_text.pack(fill="both", expand=True, pady=(0, 15))

        content = (
            "Vaizdo failų konvertavimo programa.\n"
            "Efektyvus techninės įrangos spartinimas (NVIDIA NVENC, AMD AMF).\n"
            "Išbandyta su NVIDIA GTX1650 grafikos plokšte.\n"
            "--------------------------------------------------\n"
            "Video conversion software.\n"
            "Efficient hardware acceleration (NVIDIA NVENC, AMD AMF).\n"
            "Tested with NVIDIA GTX1650 graphics card."
        )
        desc_text.insert("end", content)
        desc_text.config(state="disabled")

        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(side="bottom", fill="x")

        tk.Button(btn_frame, text="OK", font=("Segoe UI", 8, "bold"), width=12, padx=10, command=self.destroy).pack(
            side="right")