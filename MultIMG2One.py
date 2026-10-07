import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image
import threading


# ─────────────────────────────────────────────
#  LOGIQUE DE FUSION
# ─────────────────────────────────────────────

def merge_webtoon(input_folder, output_folder, target_height, progress_callback=None):
    """
    Fusionne les images d'un dossier en pages de `target_height` pixels.
    Découpe les images source pour ne jamais dépasser la hauteur cible.
    """
    os.makedirs(output_folder, exist_ok=True)

    exts = ('png', 'jpg', 'jpeg', 'webp')
    image_files = sorted([
        f for f in os.listdir(input_folder)
        if f.lower().endswith(exts)
    ])

    if not image_files:
        raise ValueError("Aucune image trouvée dans le dossier source.")

    # Charger toutes les images (lazy : on garde juste les chemins + tailles)
    images = []
    for f in image_files:
        path = os.path.join(input_folder, f)
        with Image.open(path) as im:
            images.append({'path': path, 'width': im.width, 'height': im.height})

    # Largeur de référence = largeur de la première image
    ref_width = images[0]['width']

    # Format de sortie basé sur la première image
    first_ext = os.path.splitext(images[0]['path'])[1].lower()
    if first_ext in ('.png',):
        out_ext = 'png'
        canvas_mode = 'RGBA'
        save_kwargs = {'format': 'PNG', 'compress_level': 6}
    elif first_ext in ('.webp',):
        out_ext = 'png'
        canvas_mode = 'RGBA'
        save_kwargs = {'format': 'PNG', 'compress_level': 6}  # WebP limité à 16383px
    else:  # jpg / jpeg
        out_ext = 'jpg'
        canvas_mode = 'RGB'
        save_kwargs = {'format': 'JPEG', 'quality': 100, 'subsampling': 0}

    # ── Génération des pages ──────────────────
    page_index = 1
    # curseur dans la liste des images source
    src_idx = 0
    # décalage en pixels dans l'image source courante (depuis le haut)
    src_y = 0

    total_images = len(images)

    while src_idx < total_images:
        # Construire une page
        strips = []   # liste de (path, y_start, height_to_take)
        remaining = target_height

        while remaining > 0 and src_idx < total_images:
            img_info = images[src_idx]
            available = img_info['height'] - src_y

            if available <= remaining:
                # On prend toute la partie restante de cette image
                strips.append((img_info['path'], src_y, available))
                remaining -= available
                src_idx += 1
                src_y = 0
            else:
                # On ne prend qu'une tranche
                strips.append((img_info['path'], src_y, remaining))
                src_y += remaining
                remaining = 0

        if not strips:
            break

        # ── Composer la page ─────────────────
        page_height = sum(h for _, _, h in strips)
        page = Image.new(canvas_mode, (ref_width, page_height))
        y_offset = 0

        for ipath, y_start, h in strips:
            with Image.open(ipath) as im:
                # Redimensionner si nécessaire pour correspondre à ref_width
                if im.width != ref_width:
                    ratio = ref_width / im.width
                    new_h = int(im.height * ratio)
                    im = im.resize((ref_width, new_h), Image.LANCZOS)
                    y_start = int(y_start * ratio)
                    h = int(h * ratio)

                # Convertir au mode canvas si nécessaire
                if im.mode != canvas_mode:
                    im = im.convert(canvas_mode)

                strip = im.crop((0, y_start, im.width, y_start + h))
                page.paste(strip, (0, y_offset))
                y_offset += h

        out_name = f"{str(page_index).zfill(3)}.{out_ext}"
        page.save(os.path.join(output_folder, out_name), **save_kwargs)

        if progress_callback:
            progress_callback(page_index, src_idx, total_images)

        page_index += 1

    return page_index - 1


# ─────────────────────────────────────────────
#  INTERFACE GRAPHIQUE
# ─────────────────────────────────────────────

class WebtoonMergerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MultIMG2One")
        self.resizable(False, False)
        self.configure(bg="#0f0f13")

        self._build_ui()

    def _build_ui(self):
        PAD = 18
        BG = "#0f0f13"
        CARD = "#1a1a22"
        ACCENT = "#7c6af7"
        ACCENT2 = "#4ecdc4"
        FG = "#e8e8f0"
        FG2 = "#8888aa"
        ENTRY_BG = "#12121a"
        BORDER = "#2a2a3a"

        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TFrame', background=BG)
        style.configure('Card.TFrame', background=CARD)
        style.configure('TLabel', background=BG, foreground=FG,
                        font=('Courier New', 10))
        style.configure('Card.TLabel', background=CARD, foreground=FG,
                        font=('Courier New', 10))
        style.configure('Title.TLabel', background=BG, foreground=ACCENT,
                        font=('Courier New', 16, 'bold'))
        style.configure('Sub.TLabel', background=BG, foreground=FG2,
                        font=('Courier New', 9))
        style.configure('Accent.TButton',
                        background=ACCENT, foreground='white',
                        font=('Courier New', 10, 'bold'),
                        borderwidth=0, relief='flat')
        style.map('Accent.TButton',
                  background=[('active', '#9d8fff'), ('pressed', '#5a4fd4')])
        style.configure('Ghost.TButton',
                        background=CARD, foreground=ACCENT2,
                        font=('Courier New', 9),
                        borderwidth=1, relief='solid')
        style.map('Ghost.TButton',
                  background=[('active', '#1f1f2e')])
        style.configure('TProgressbar',
                        troughcolor=BORDER, background=ACCENT,
                        borderwidth=0, thickness=6)

        main = ttk.Frame(self, padding=PAD)
        main.pack(fill='both', expand=True)

        # ── Titre ────────────────────────────
        ttk.Label(main, text="MULTIMG2ONE", style='Title.TLabel').grid(
            row=0, column=0, columnspan=3, sticky='w', pady=(0, 2))
        ttk.Label(main, text="fusion d'images avec découpe pixel-perfect",
                  style='Sub.TLabel').grid(
            row=1, column=0, columnspan=3, sticky='w', pady=(0, PAD))

        # ── Dossier source ───────────────────
        self._make_folder_row(main, row=2, label="Dossier source",
                              attr='input_var', btn_cmd=self._browse_input,
                              CARD=CARD, ENTRY_BG=ENTRY_BG, FG=FG, FG2=FG2, BORDER=BORDER, ACCENT2=ACCENT2)

        # ── Dossier sortie ───────────────────
        self._make_folder_row(main, row=4, label="Dossier de sortie",
                              attr='output_var', btn_cmd=self._browse_output,
                              CARD=CARD, ENTRY_BG=ENTRY_BG, FG=FG, FG2=FG2, BORDER=BORDER, ACCENT2=ACCENT2)

        # ── Hauteur cible ────────────────────
        sep = ttk.Frame(main, height=1, style='TFrame')
        sep.grid(row=6, column=0, columnspan=3, sticky='ew', pady=PAD)

        ttk.Label(main, text="Hauteur cible par page (px)",
                  font=('Courier New', 9), foreground=FG2,
                  background=BG).grid(row=7, column=0, sticky='w')

        height_frame = ttk.Frame(main, style='TFrame')
        height_frame.grid(row=8, column=0, columnspan=3, sticky='ew', pady=(4, 0))

        self.height_var = tk.IntVar(value=20000)

        # Presets
        presets = [
            ("10 000", 10000),
            ("15 000", 15000),
            ("20 000", 20000),
            ("30 000", 30000),
        ]
        for i, (lbl, val) in enumerate(presets):
            btn = tk.Button(
                height_frame, text=lbl,
                bg=CARD, fg=ACCENT2, relief='flat',
                font=('Courier New', 9),
                bd=0, padx=10, pady=4,
                cursor='hand2',
                command=lambda v=val: self.height_var.set(v)
            )
            btn.grid(row=0, column=i, padx=(0, 6))

        # Champ personnalisé
        custom_frame = tk.Frame(height_frame, bg=ENTRY_BG,
                                highlightbackground=BORDER,
                                highlightthickness=1)
        custom_frame.grid(row=0, column=len(presets), padx=(10, 0))

        tk.Label(custom_frame, text="Custom:", bg=ENTRY_BG, fg=FG2,
                 font=('Courier New', 9)).pack(side='left', padx=(8, 4))
        self.height_entry = tk.Entry(
            custom_frame, textvariable=self.height_var,
            bg=ENTRY_BG, fg=FG, insertbackground=ACCENT,
            relief='flat', font=('Courier New', 10, 'bold'),
            width=7
        )
        self.height_entry.pack(side='left', padx=(0, 4), pady=4)
        tk.Label(custom_frame, text="px", bg=ENTRY_BG, fg=FG2,
                 font=('Courier New', 9)).pack(side='left', padx=(0, 8))

        # ── Aperçu estimation ─────────────────
        self.estimate_label = tk.Label(
            main, text="", bg=BG, fg=FG2,
            font=('Courier New', 9)
        )
        self.estimate_label.grid(row=9, column=0, columnspan=3,
                                 sticky='w', pady=(8, 0))

        self.height_var.trace_add('write', self._update_estimate)

        # ── Progress ─────────────────────────
        sep2 = ttk.Frame(main, height=1, style='TFrame')
        sep2.grid(row=10, column=0, columnspan=3, sticky='ew', pady=PAD)

        self.progress = ttk.Progressbar(main, style='TProgressbar',
                                        length=480, mode='determinate')
        self.progress.grid(row=11, column=0, columnspan=3, sticky='ew')

        self.status_label = tk.Label(
            main, text="En attente…", bg=BG, fg=FG2,
            font=('Courier New', 9)
        )
        self.status_label.grid(row=12, column=0, columnspan=2,
                               sticky='w', pady=(6, 0))

        # ── Bouton lancer ─────────────────────
        self.run_btn = tk.Button(
            main, text="▶  FUSIONNER",
            bg=ACCENT, fg='white',
            font=('Courier New', 11, 'bold'),
            relief='flat', bd=0,
            padx=24, pady=10,
            cursor='hand2',
            command=self._run
        )
        self.run_btn.grid(row=12, column=2, sticky='e', pady=(6, 0))

        main.columnconfigure(1, weight=1)

    def _make_folder_row(self, parent, row, label, attr, btn_cmd,
                         CARD, ENTRY_BG, FG, FG2, BORDER, ACCENT2):
        tk.Label(parent, text=label, bg="#0f0f13", fg=FG2,
                 font=('Courier New', 9)).grid(
            row=row, column=0, sticky='w', pady=(0, 2))

        var = tk.StringVar()
        setattr(self, attr, var)

        frame = tk.Frame(parent, bg=ENTRY_BG,
                         highlightbackground=BORDER,
                         highlightthickness=1)
        frame.grid(row=row + 1, column=0, columnspan=2,
                   sticky='ew', ipady=4, pady=(0, 10))

        entry = tk.Entry(frame, textvariable=var,
                         bg=ENTRY_BG, fg=FG, insertbackground=ACCENT2,
                         relief='flat', font=('Courier New', 9),
                         bd=0)
        entry.pack(side='left', fill='x', expand=True, padx=8)

        btn = tk.Button(parent, text="Parcourir",
                        bg=CARD, fg=ACCENT2, relief='flat',
                        font=('Courier New', 9),
                        bd=0, padx=12, pady=6,
                        cursor='hand2',
                        command=btn_cmd)
        btn.grid(row=row + 1, column=2, sticky='e', padx=(8, 0), pady=(0, 10))

        parent.columnconfigure(1, weight=1)

    def _browse_input(self):
        d = filedialog.askdirectory(title="Dossier source")
        if d:
            self.input_var.set(d)
            self._update_estimate()

    def _browse_output(self):
        d = filedialog.askdirectory(title="Dossier de sortie")
        if d:
            self.output_var.set(d)

    def _update_estimate(self, *_):
        folder = self.input_var.get()
        if not folder or not os.path.isdir(folder):
            self.estimate_label.config(text="")
            return
        try:
            exts = ('png', 'jpg', 'jpeg', 'webp')
            files = [f for f in os.listdir(folder) if f.lower().endswith(exts)]
            total_h = 0
            for f in files:
                with Image.open(os.path.join(folder, f)) as im:
                    total_h += im.height
            target = self.height_var.get()
            import math
            pages = math.ceil(total_h / target) if target > 0 else "?"
            self.estimate_label.config(
                text=f"↳ {len(files)} images · {total_h:,} px total → ~{pages} pages estimées"
            )
        except Exception:
            self.estimate_label.config(text="")

    def _run(self):
        src = self.input_var.get().strip()
        dst = self.output_var.get().strip()
        try:
            target = int(self.height_var.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("Erreur", "Hauteur cible invalide.")
            return

        if not src or not os.path.isdir(src):
            messagebox.showerror("Erreur", "Dossier source invalide.")
            return
        if not dst:
            messagebox.showerror("Erreur", "Choisissez un dossier de sortie.")
            return
        if target <= 0:
            messagebox.showerror("Erreur", "La hauteur doit être > 0.")
            return

        self.run_btn.config(state='disabled')
        self.progress['value'] = 0
        self.status_label.config(text="Démarrage…")

        # Compter les images pour la barre de progression
        exts = ('png', 'jpg', 'jpeg', 'webp')
        total = len([f for f in os.listdir(src) if f.lower().endswith(exts)])

        def progress_cb(page, processed, total_imgs):
            pct = (processed / total_imgs) * 100
            self.progress['value'] = pct
            self.status_label.config(
                text=f"Page {page} créée · {processed}/{total_imgs} images traitées"
            )
            self.update_idletasks()

        def task():
            try:
                pages = merge_webtoon(src, dst, target, progress_cb)
                self.progress['value'] = 100
                self.status_label.config(
                    text=f"✓ Terminé — {pages} pages créées dans « {os.path.basename(dst)} »"
                )
                messagebox.showinfo("Terminé",
                                    f"{pages} pages fusionnées avec succès !\n→ {dst}")
            except Exception as e:
                messagebox.showerror("Erreur", str(e))
                self.status_label.config(text="Erreur.")
            finally:
                self.run_btn.config(state='normal')

        threading.Thread(target=task, daemon=True).start()


# ─────────────────────────────────────────────
if __name__ == '__main__':
    app = WebtoonMergerApp()
    app.mainloop()