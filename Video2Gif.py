#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video → GIF (qualité max) — Application Tkinter

• Utilise FFmpeg/FFprobe (doivent être installés et accessibles dans le PATH)
• Palette optimisée (palettegen/paletteuse) + mise à l’échelle Lanczos
• Options : FPS, largeur, couleurs max (jusqu'à 256), dithering, loop infini, trim

"""

import os
import sys
import shlex
import tempfile
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ------------------------- Utilitaires FFmpeg ------------------------- #

def _run(cmd):
    """Exécute une commande en renvoyant (retcode, stdout+stderr)."""
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return proc.returncode, proc.stdout
    except FileNotFoundError as e:
        return 127, str(e)


def ffmpeg_available():
    code, _ = _run(["ffmpeg", "-version"])  # type: ignore[arg-type]
    return code == 0


def ffprobe_available():
    code, _ = _run(["ffprobe", "-version"])  # type: ignore[arg-type]
    return code == 0


def probe_dimensions(input_path):
    """Retourne (width, height) via ffprobe ou (None, None) si indisponible."""
    if not ffprobe_available():
        return None, None
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        input_path,
    ]
    code, out = _run(cmd)
    if code != 0:
        return None, None
    line = out.strip().splitlines()[-1] if out.strip() else ""
    if "x" in line:
        try:
            w, h = line.split("x")
            return int(w), int(h)
        except Exception:
            return None, None
    return None, None


def build_filter_complex(fps, width, max_colors, dither, stats_mode="single", add_scale=True):
    """Construit la chaîne filter_complex pour palettegen/paletteuse.
    Si add_scale=False, on omet scale= et on laisse la taille d'origine.
    """
    scale_part = f",scale={width}:-1:flags=lanczos" if add_scale else ""
    # split -> palettegen -> paletteuse
    fc = (
        f"fps={fps}{scale_part},split [a][b];"
        f"[a]palettegen=max_colors={max_colors}:stats_mode={stats_mode}[p];"
        f"[b][p]paletteuse=dither={dither}:diff_mode=rectangle"
    )
    return fc


def quote_path(p):
    # subprocess avec liste gère déjà correctement, mais utile pour logs
    return f'"{p}"'


def convert_to_gif(input_path, output_path, fps=15, width=None, max_colors=256, dither="sierra2_4a", loop_forever=True, start_ts=None, duration_ts=None, log_callback=None):
    """Conversion vidéo → GIF via FFmpeg en un seul passage (split/palettegen/paletteuse)."""
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg n'est pas disponible dans le PATH.")

    # Validation
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Fichier introuvable : {input_path}")

    # Déterminer si on applique un scale
    add_scale = True
    if width is None or str(width).strip() == "":
        add_scale = False

    # Construire filter_complex
    fc = build_filter_complex(fps=int(fps), width=int(width) if add_scale else 0, max_colors=int(max_colors), dither=dither, stats_mode="single", add_scale=add_scale)

    cmd = ["ffmpeg", "-y"]

    # Trim optionnel (mettre -ss avant -i pour rapidité)
    if start_ts and start_ts.strip():
        cmd += ["-ss", start_ts.strip()]

    cmd += ["-i", input_path]

    if duration_ts and duration_ts.strip():
        cmd += ["-t", duration_ts.strip()]

    cmd += [
        "-filter_complex", fc,
        "-gifflags", "+transdiff",
    ]

    # Loop infini
    if loop_forever:
        cmd += ["-loop", "0"]

    # Forcer format GIF
    cmd += ["-f", "gif", output_path]

    # Exécution avec retour progressif dans le Text widget
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output_lines = []
    while True:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line and proc.poll() is not None:
            break
        if line:
            output_lines.append(line)
            if log_callback:
                log_callback(line.rstrip())

    ret = proc.wait()
    if ret != 0:
        raise RuntimeError("FFmpeg a échoué.\n\n" + "".join(output_lines[-50:]))

    return output_path


# ------------------------- Interface Tkinter ------------------------- #

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video → GIF")
        self.geometry("760x540")
        self.minsize(700, 520)
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True)

        # Ligne fichier entrée
        row = 0
        ttk.Label(frm, text="Vidéo d'entrée :").grid(row=row, column=0, sticky="w", **pad)
        self.in_var = tk.StringVar()
        ent_in = ttk.Entry(frm, textvariable=self.in_var)
        ent_in.grid(row=row, column=1, sticky="ew", **pad)
        btn_in = ttk.Button(frm, text="Parcourir…", command=self._browse_in)
        btn_in.grid(row=row, column=2, sticky="w", **pad)

        # Ligne fichier sortie
        row += 1
        ttk.Label(frm, text="GIF de sortie :").grid(row=row, column=0, sticky="w", **pad)
        self.out_var = tk.StringVar()
        ent_out = ttk.Entry(frm, textvariable=self.out_var)
        ent_out.grid(row=row, column=1, sticky="ew", **pad)
        btn_out = ttk.Button(frm, text="Enregistrer sous…", command=self._browse_out)
        btn_out.grid(row=row, column=2, sticky="w", **pad)

        # Options de base
        row += 1
        sep1 = ttk.Separator(frm)
        sep1.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)

        row += 1
        ttk.Label(frm, text="FPS :").grid(row=row, column=0, sticky="w", **pad)
        self.fps_var = tk.IntVar(value=15)
        fps_spin = ttk.Spinbox(frm, from_=1, to=60, textvariable=self.fps_var, width=8)
        fps_spin.grid(row=row, column=1, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="Largeur cible (px) :").grid(row=row, column=0, sticky="w", **pad)
        self.width_var = tk.StringVar(value="480")
        width_ent = ttk.Entry(frm, textvariable=self.width_var, width=10)
        width_ent.grid(row=row, column=1, sticky="w", **pad)
        ttk.Label(frm, text="(laisser vide = taille d'origine)").grid(row=row, column=2, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="Couleurs max :").grid(row=row, column=0, sticky="w", **pad)
        self.colors_var = tk.IntVar(value=256)
        colors_spin = ttk.Spinbox(frm, from_=2, to=256, textvariable=self.colors_var, width=8)
        colors_spin.grid(row=row, column=1, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="Dithering :").grid(row=row, column=0, sticky="w", **pad)
        self.dither_var = tk.StringVar(value="sierra2_4a")
        dither_cb = ttk.Combobox(frm, textvariable=self.dither_var, width=18, state="readonly",
                                 values=["sierra2_4a", "bayer", "floyd_steinberg", "none"])
        dither_cb.grid(row=row, column=1, sticky="w", **pad)

        row += 1
        self.loop_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="Boucle infinie (loop=0)", variable=self.loop_var).grid(row=row, column=0, columnspan=2, sticky="w", **pad)

        # Trim
        row += 1
        sep2 = ttk.Separator(frm)
        sep2.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)

        row += 1
        ttk.Label(frm, text="Début (ss ou hh:mm:ss[.ms]) :").grid(row=row, column=0, sticky="w", **pad)
        self.start_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.start_var, width=16).grid(row=row, column=1, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="Durée (ss ou hh:mm:ss[.ms]) :").grid(row=row, column=0, sticky="w", **pad)
        self.dur_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.dur_var, width=16).grid(row=row, column=1, sticky="w", **pad)

        # Boutons d'action
        row += 1
        sep3 = ttk.Separator(frm)
        sep3.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)

        row += 1
        btn_test = ttk.Button(frm, text="Tester FFmpeg", command=self._test_ffmpeg)
        btn_test.grid(row=row, column=0, sticky="w", **pad)
        btn_go = ttk.Button(frm, text="Convertir en GIF", command=self._on_convert)
        btn_go.grid(row=row, column=1, sticky="w", **pad)
        btn_open = ttk.Button(frm, text="Ouvrir le dossier de sortie", command=self._open_out_dir)
        btn_open.grid(row=row, column=2, sticky="w", **pad)

        # Zone de log
        row += 1
        sep4 = ttk.Separator(frm)
        sep4.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)

        row += 1
        ttk.Label(frm, text="Journal FFmpeg :").grid(row=row, column=0, sticky="w", **pad)
        self.log = tk.Text(frm, height=10)
        self.log.grid(row=row, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0,10))

        # Configuration grid
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(row, weight=1)

    # ----------------- Callbacks UI ----------------- #
    def _browse_in(self):
        path = filedialog.askopenfilename(title="Choisir une vidéo",
                                          filetypes=[
                                              ("Vidéos", "+".join(["*.mp4", "*.mov", "*.mkv", "*.avi", "*.webm", "*.m4v"])) ,
                                              ("Tous les fichiers", "*.*")
                                          ])
        if path:
            self.in_var.set(path)
            # Proposer un nom de sortie par défaut
            base, _ = os.path.splitext(path)
            self.out_var.set(base + ".gif")

            # Si largeur vide, récupérer la largeur d'origine
            if not self.width_var.get().strip():
                w, _ = probe_dimensions(path)
                if w:
                    self.width_var.set(str(w))

    def _browse_out(self):
        path = filedialog.asksaveasfilename(title="Enregistrer sous",
                                            defaultextension=".gif",
                                            filetypes=[("GIF", "*.gif"), ("Tous les fichiers", "*.*")])
        if path:
            self.out_var.set(path)

    def _test_ffmpeg(self):
        ok_ff = ffmpeg_available()
        ok_fp = ffprobe_available()
        msg = "FFmpeg: OK\nFFprobe: OK" if (ok_ff and ok_fp) else f"FFmpeg: {'OK' if ok_ff else 'NON'}\nFFprobe: {'OK' if ok_fp else 'NON'}"
        messagebox.showinfo("Vérification", msg)

    def _open_out_dir(self):
        out = self.out_var.get().strip()
        if not out:
            messagebox.showinfo("Infos", "Aucun fichier de sortie défini.")
            return
        folder = os.path.dirname(out) or os.getcwd()
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _append_log(self, line):
        self.log.insert(tk.END, line + "\n")
        self.log.see(tk.END)
        self.update_idletasks()

    def _on_convert(self):
        inp = self.in_var.get().strip()
        out = self.out_var.get().strip()
        if not inp:
            messagebox.showwarning("Manque", "Veuillez choisir une vidéo d'entrée.")
            return
        if not out:
            messagebox.showwarning("Manque", "Veuillez choisir un GIF de sortie.")
            return
        try:
            fps = int(float(str(self.fps_var.get()).replace(",", ".")))
            fps = max(1, min(60, fps))
        except Exception:
            messagebox.showwarning("FPS invalide", "FPS doit être un nombre entre 1 et 60.")
            return
        width_txt = self.width_var.get().strip()
        width_val = None
        if width_txt:
            try:
                width_val = int(width_txt)
                if width_val < 16:
                    raise ValueError
            except Exception:
                messagebox.showwarning("Largeur invalide", "La largeur doit être un entier ≥ 16, ou vide pour la taille d'origine.")
                return
        try:
            colors = int(self.colors_var.get())
            if not (2 <= colors <= 256):
                raise ValueError
        except Exception:
            messagebox.showwarning("Couleurs invalides", "Couleurs max doit être entre 2 et 256.")
            return
        dither = self.dither_var.get()
        loop_inf = bool(self.loop_var.get())
        start_ts = self.start_var.get().strip()
        dur_ts = self.dur_var.get().strip()
        if not start_ts:
            start_ts = None
        if not dur_ts:
            dur_ts = None

        self.log.delete("1.0", tk.END)
        self._append_log("⏳ Conversion en cours…")
        self.after(50, self._do_convert, inp, out, fps, width_val, colors, dither, loop_inf, start_ts, dur_ts)

    def _do_convert(self, inp, out, fps, width, colors, dither, loop_inf, start_ts, dur_ts):
        try:
            convert_to_gif(
                input_path=inp,
                output_path=out,
                fps=fps,
                width=width,
                max_colors=colors,
                dither=dither,
                loop_forever=loop_inf,
                start_ts=start_ts,
                duration_ts=dur_ts,
                log_callback=self._append_log,
            )
        except Exception as e:
            self._append_log("")
            self._append_log("❌ Erreur :" )
            self._append_log(str(e))
            messagebox.showerror("Erreur conversion", str(e))
            return
        self._append_log("")
        self._append_log("✅ Terminé !")
        messagebox.showinfo("Succès", f"GIF généré :\n{out}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
