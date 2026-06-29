import os
import tkinter as tk
from tkinter import scrolledtext, ttk
import hardware


class AboutWindow(tk.Toplevel):

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("About Video Converter")
        self.geometry("500x420")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        main_frame = tk.Frame(self, padx=15, pady=12)
        main_frame.pack(fill="both", expand=True)

        # VIRŠUS: paveikslėlis + antraštė vienoje eilutėje
        header_frame = tk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))

        img_path = hardware.find_resource("converter.png")
        if img_path and os.path.exists(img_path):
            self.about_img = tk.PhotoImage(file=img_path)
            tk.Label(header_frame, image=self.about_img).pack(side="left", padx=(0, 12))
        else:
            placeholder = tk.Frame(header_frame, width=96, height=96, bg="#3b6ea8")
            placeholder.pack(side="left", padx=(0, 12))
            placeholder.pack_propagate(False)
            tk.Label(placeholder, text="CONV", bg="#3b6ea8", fg="white",
                     font=("Segoe UI", 14, "bold")).pack(expand=True)

        title_frame = tk.Frame(header_frame)
        title_frame.pack(side="left", anchor="w", padx=(100, 10))
        tk.Label(title_frame, text="Video Converter",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(title_frame, text="Version 1.0",
                 font=("Segoe UI", 8), fg="#555555").pack(anchor="w", pady=(2, 0))
        tk.Label(title_frame, text="Copyright © 2026 Kęstutis Butkus",
                 font=("Segoe UI", 8), fg="#555555").pack(anchor="w", pady=(2, 0))

        # SKIRTUKAI
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True, pady=(0, 10))

        # --- 1 SKIRTUKAS: Apie ---
        tab_about = tk.Frame(notebook)
        notebook.add(tab_about, text="  Apie  ")

        about_text = scrolledtext.ScrolledText(
            tab_about, font=("Segoe UI", 8), relief="solid",
            borderwidth=1, wrap="word", padx=8, pady=8,
            spacing1=1, spacing3=2
        )
        about_text.pack(fill="both", expand=True)

        about_text.tag_configure("heading", font=("Segoe UI", 9, "bold"), foreground="#1a5fa8", spacing1=6, spacing3=2)
        about_text.tag_configure("body",    font=("Segoe UI", 8), spacing3=2)
        about_text.tag_configure("bullet",  font=("Segoe UI", 8), lmargin1=8, lmargin2=16, spacing3=2)
        about_text.tag_configure("note",    font=("Segoe UI", 8, "italic"), foreground="#666666", spacing1=6)

        def ah(text): about_text.insert("end", text + "\n", "heading")
        def ab(text): about_text.insert("end", "•  " + text + "\n", "bullet")
        def an(text): about_text.insert("end", text + "\n", "note")

        ah("Apie programą")
        about_text.insert("end",
            "Galinga vaizdo failų konvertavimo programa, optimizuota masiniam "
            "ir vienetiniam apdorojimui naudojant techninės įrangos spartinimą.\n",
            "body")

        ah("Funkcijos")
        ab("Aparatinis spartinimas — NVIDIA NVENC/NVDEC (CUDA) ir AMD AMF (D3D11VA/DXVA2)")
        ab("Išmanusis mastelio keitimas — automatinis scale / scale_cuda perjungimas")
        ab("10-bit HEVC konversija — Main10 → 8-bit H.264 (yuv420p) tiesiogiai GPU viduje")
        ab("Kokybės režimai — fiksuota kokybė (CRF/CQ) arba tikslinis bitų srautas (VBR)")
        ab("Audio — automatinis aptikimas, AAC konvertavimas (96k / 128k / 192k) arba kopija")

        an("Išbandyta su NVIDIA GTX 1650. AMD palaikymas įtrauktas, bet netestuotas.")

        about_text.config(state="disabled")

        # --- 2 SKIRTUKAS: Patarimai ---
        tab_tips = tk.Frame(notebook)
        notebook.add(tab_tips, text="  Patarimai  ")

        tips_text = scrolledtext.ScrolledText(
            tab_tips, font=("Segoe UI", 8), relief="solid",
            borderwidth=1, wrap="word", padx=8, pady=8,
            spacing1=1, spacing3=2
        )
        tips_text.pack(fill="both", expand=True)

        tips_text.tag_configure("heading", font=("Segoe UI", 9, "bold"), foreground="#1a5fa8", spacing1=8, spacing3=2)
        tips_text.tag_configure("sub",     font=("Segoe UI", 8, "italic"), foreground="#666666", spacing3=3)
        tips_text.tag_configure("bullet",  font=("Segoe UI", 8), lmargin1=8, lmargin2=16, spacing3=2)
        tips_text.tag_configure("rec",     font=("Segoe UI", 9, "bold"), foreground="#2a7a2a", spacing1=10, spacing3=2)
        tips_text.tag_configure("rec_val", font=("Segoe UI", 8), foreground="#2a7a2a", lmargin1=8, lmargin2=16, spacing3=2)

        def h(text): tips_text.insert("end", text + "\n", "heading")
        def s(text): tips_text.insert("end", text + "\n", "sub")
        def b(text): tips_text.insert("end", "•  " + text + "\n", "bullet")
        def r(text): tips_text.insert("end", text + "\n", "rec")
        def rv(text): tips_text.insert("end", text + "\n", "rec_val")

        h("⚡ Greičiausias konvertavimas")
        s("Režimas: Bitų srautas (VBR)")
        b("Aparatinis enkoderis (NVENC / AMF) — GPU koduoja daug kartų greičiau nei CPU")
        b("Aukštesnis bitų srautas (6000–10000 kbps) — enkoderis dirba mažiau intensyviai")
        b("720p šaltiniai konvertuojami greičiausiai")
        b("Venkite filtrų (scale, deinterlace) — kiekvienas filtras prideda laiko")

        h("🎯 Geriausia kokybė")
        s("Režimas: Fiksuota kokybė (CQ)")
        b("NVENC CQ: 18–22 (žemesnė = geriau) — rekomenduojama: 20")
        b("H.265 (HEVC) koderį — ta pati kokybė, ~30–40 % mažesnis failas nei H.264")
        b("Audio: 192k AAC arba stream copy — originalas be nuostolių")

        h("📦 Mažiausias failas")
        s("Režimas: Bitų srautas (VBR) su žemu taikiniu")
        b("H.265 — gerokai efektyvesnis už H.264")
        b("Bitų srautas: 1500–3000 kbps 1080p (daug judesio — 3000+)")
        b("Audio: 96k AAC — pakanka dialogams ir foninei muzikai")
        b("720p raiška — dramatiškai mažina failo dydį")

        r("✅ Rekomenduojamas variantas")
        rv("NVENC H.265 (senesniems įrenginiams — H.264)")
        rv("1080p: CQ 26–30  ·  720p: CQ 25–28  ·  540p: CQ 24–26  ·  480p: CQ 22–25")
        rv("(didesnis CQ = mažesnis failas, bet kenčia kokybė)")
        rv("Audio: 128k AAC filmams  ·  96k AAC serialams")
        rv("→ Gera kokybė, ~75 % mažesnis failas, greitas konvertavimas")

        tips_text.config(state="disabled")

        # OK mygtukas
        tk.Button(
            main_frame, text="OK", font=("Segoe UI", 8, "bold"),
            width=12, padx=10, command=self.destroy
        ).pack(side="right")