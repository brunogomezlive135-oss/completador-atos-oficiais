# -*- coding: utf-8 -*-
"""Interface gráfica do Detector de Atos Oficiais."""

from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

from detector_atos import processar_pdf, sanitizar_filename

BG = "#0b1220"
CARD = "#111b2e"
CARD2 = "#16233a"
TEXT = "#eef4ff"
MUTED = "#9fb0c8"
ACCENT = "#2f81f7"
BORDER = "#263752"
GREEN = "#36c98f"
YELLOW = "#f2c14e"
RED = "#ef6b73"


class Aplicativo:
    def __init__(self, root):
        self.root = root
        self.root.title("Detector de Atos Oficiais")
        self.root.geometry("1280x760")
        self.root.minsize(980, 620)
        self.root.configure(bg=BG)

        self.arquivos = []
        self.resultados = []
        self.processando = False

        self.configurar_estilos()
        self.montar_interface()

    def configurar_estilos(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background=BG)
        style.configure("Title.TLabel", background=BG, foreground=TEXT,
                        font=("Segoe UI", 23, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED,
                        font=("Segoe UI", 10))
        style.configure("Primary.TButton", background=ACCENT, foreground="white",
                        borderwidth=0, padding=(18, 10),
                        font=("Segoe UI", 10, "bold"))
        style.map("Primary.TButton",
                  background=[("active", "#4b94ff"), ("disabled", "#253552")],
                  foreground=[("disabled", "#7f8da3")])
        style.configure("Secondary.TButton", background=CARD2, foreground=TEXT,
                        borderwidth=1, relief="flat", padding=(15, 9),
                        font=("Segoe UI", 10))
        style.map("Secondary.TButton",
                  background=[("active", "#20304c"), ("disabled", "#172238")],
                  foreground=[("disabled", "#66758c")])
        style.configure("Treeview", background=CARD, fieldbackground=CARD,
                        foreground=TEXT, rowheight=34, borderwidth=0,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background=CARD2, foreground=MUTED,
                        relief="flat", font=("Segoe UI", 9, "bold"), padding=8)
        style.map("Treeview", background=[("selected", "#214d83")],
                  foreground=[("selected", "white")])
        style.configure("Horizontal.TProgressbar", troughcolor=CARD2,
                        background=ACCENT, borderwidth=0, thickness=8)

    def montar_interface(self):
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=26, pady=22)

        header = tk.Frame(main, bg=BG)
        header.pack(fill="x", pady=(0, 18))

        logo = tk.Frame(header, bg=ACCENT, width=50, height=50)
        logo.pack(side="left", padx=(0, 13))
        logo.pack_propagate(False)
        tk.Label(logo, text="DA", bg=ACCENT, fg="white",
                 font=("Segoe UI", 15, "bold")).pack(expand=True)

        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left", fill="x", expand=True)
        ttk.Label(titles, text="Detector de Atos Oficiais",
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            titles,
            text="Classifique, extraia informações e padronize seus documentos automaticamente.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        entrada = tk.Frame(main, bg=CARD, highlightbackground=BORDER,
                           highlightthickness=1)
        entrada.pack(fill="x", pady=(0, 14))

        tk.Label(entrada, text="INSERIR DOCUMENTOS", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(15, 2))
        tk.Label(entrada, text="Adicione PDFs ou pastas", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=18)
        tk.Label(
            entrada,
            text="Você pode selecionar arquivos, selecionar uma pasta ou arrastar e soltar diretamente na área abaixo.",
            bg=CARD, fg=MUTED, font=("Segoe UI", 9)
        ).pack(anchor="w", padx=18, pady=(2, 12))

        botoes = tk.Frame(entrada, bg=CARD)
        botoes.pack(fill="x", padx=18, pady=(0, 12))

        self.btn_adicionar = ttk.Button(
            botoes, text="＋  Adicionar PDFs", style="Primary.TButton",
            command=self.adicionar_pdfs)
        self.btn_adicionar.pack(side="left")

        self.btn_pasta = ttk.Button(
            botoes, text="＋  Adicionar pasta", style="Secondary.TButton",
            command=self.adicionar_pasta)
        self.btn_pasta.pack(side="left", padx=8)

        self.btn_limpar = ttk.Button(
            botoes, text="Limpar", style="Secondary.TButton",
            command=self.limpar)
        self.btn_limpar.pack(side="right")

        self.drop_zone = tk.Frame(
            entrada, bg="#0e1a2d", highlightbackground="#2a4770",
            highlightthickness=1, height=72)
        self.drop_zone.pack(fill="x", padx=18, pady=(0, 16))
        self.drop_zone.pack_propagate(False)

        self.drop_label = tk.Label(
            self.drop_zone,
            text="⇩   Solte aqui seus PDFs ou pastas",
            bg="#0e1a2d", fg="#b8c8df",
            font=("Segoe UI", 11, "bold"))
        self.drop_label.pack(expand=True)

        if TkinterDnD is not None:
            for widget in (self.drop_zone, self.drop_label):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self.drop)

        resumo = tk.Frame(main, bg=BG)
        resumo.pack(fill="x", pady=(0, 14))
        self.card_arquivos = self.criar_card(resumo, "0", "PDFs na fila")
        self.card_arquivos.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.card_altas = self.criar_card(resumo, "0", "Alta confiança")
        self.card_altas.pack(side="left", fill="x", expand=True, padx=4)
        self.card_revisao = self.criar_card(resumo, "0", "Revisão necessária")
        self.card_revisao.pack(side="left", fill="x", expand=True, padx=(8, 0))

        painel = tk.Frame(main, bg=CARD, highlightbackground=BORDER,
                          highlightthickness=1)
        painel.pack(fill="both", expand=True)

        barra = tk.Frame(painel, bg=CARD)
        barra.pack(fill="x", padx=16, pady=(12, 8))
        tk.Label(barra, text="RESULTADOS DA ANÁLISE", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")

        self.btn_analisar = ttk.Button(
            barra, text="Analisar documentos", style="Primary.TButton",
            command=self.iniciar, state="disabled")
        self.btn_analisar.pack(side="right")

        tabela_frame = tk.Frame(painel, bg=CARD)
        tabela_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        colunas = ("arquivo", "tipo", "numero", "ano", "confianca", "nome")
        self.tabela = ttk.Treeview(tabela_frame, columns=colunas, show="headings")
        configuracoes = {
            "arquivo": ("Arquivo", 190),
            "tipo": ("Tipo", 175),
            "numero": ("Nº", 65),
            "ano": ("Ano", 65),
            "confianca": ("Confiança", 90),
            "nome": ("Nome sugerido", 650),
        }
        for coluna, (titulo, largura) in configuracoes.items():
            self.tabela.heading(coluna, text=titulo)
            self.tabela.column(coluna, width=largura, anchor="w")

        sy = ttk.Scrollbar(tabela_frame, orient="vertical",
                           command=self.tabela.yview)
        sx = ttk.Scrollbar(tabela_frame, orient="horizontal",
                           command=self.tabela.xview)
        self.tabela.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.tabela.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        tabela_frame.rowconfigure(0, weight=1)
        tabela_frame.columnconfigure(0, weight=1)

        self.tabela.tag_configure("alta", foreground=GREEN)
        self.tabela.tag_configure("media", foreground=YELLOW)
        self.tabela.tag_configure("baixa", foreground=RED)

        rodape = tk.Frame(main, bg=BG)
        rodape.pack(fill="x", pady=(10, 0))
        self.progresso = ttk.Progressbar(
            rodape, style="Horizontal.TProgressbar", mode="determinate")
        self.progresso.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.status = tk.Label(rodape, text="Pronto para começar.",
                               bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.status.pack(side="left", padx=(0, 12))

        self.btn_renomear = ttk.Button(
            rodape, text="Renomear alta confiança", style="Primary.TButton",
            command=self.renomear, state="disabled")
        self.btn_renomear.pack(side="right")

    def criar_card(self, parent, valor, texto):
        frame = tk.Frame(parent, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1, height=74)
        frame.pack_propagate(False)
        label = tk.Label(frame, text=valor, bg=CARD, fg=TEXT,
                         font=("Segoe UI", 19, "bold"))
        label.pack(anchor="w", padx=15, pady=(10, 0))
        tk.Label(frame, text=texto, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=15)
        frame.valor_label = label
        return frame

    def atualizar_cards(self):
        total = len(self.arquivos)
        altas = sum(r.confianca == "alta" for _, r in self.resultados)
        revisao = sum(r.confianca != "alta" for _, r in self.resultados)
        self.card_arquivos.valor_label.config(text=str(total))
        self.card_altas.valor_label.config(text=str(altas))
        self.card_revisao.valor_label.config(text=str(revisao))

    def drop(self, event):
        try:
            caminhos = self.root.tk.splitlist(event.data)
        except Exception:
            caminhos = [event.data]

        adicionados = 0
        for bruto in caminhos:
            caminho = Path(bruto)
            if caminho.is_file() and caminho.suffix.lower() == ".pdf":
                if caminho not in self.arquivos:
                    self.arquivos.append(caminho)
                    adicionados += 1
            elif caminho.is_dir():
                for pdf in sorted(caminho.rglob("*.pdf")):
                    if pdf not in self.arquivos:
                        self.arquivos.append(pdf)
                        adicionados += 1

        self.fila_atualizada(adicionados)

    def adicionar_pdfs(self):
        caminhos = filedialog.askopenfilenames(
            title="Selecione os PDFs",
            filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os arquivos", "*.*")]
        )
        adicionados = 0
        for caminho in caminhos:
            pdf = Path(caminho)
            if pdf.suffix.lower() == ".pdf" and pdf not in self.arquivos:
                self.arquivos.append(pdf)
                adicionados += 1
        self.fila_atualizada(adicionados)

    def adicionar_pasta(self):
        pasta = filedialog.askdirectory(title="Selecione uma pasta com PDFs")
        if not pasta:
            return
        adicionados = 0
        for pdf in sorted(Path(pasta).rglob("*.pdf")):
            if pdf not in self.arquivos:
                self.arquivos.append(pdf)
                adicionados += 1
        self.fila_atualizada(adicionados)

    def fila_atualizada(self, adicionados=0):
        self.atualizar_cards()
        if self.arquivos:
            self.btn_analisar.config(state="normal")
            self.status.config(
                text=f"{adicionados} PDF(s) adicionado(s) • {len(self.arquivos)} na fila."
                if adicionados else f"{len(self.arquivos)} PDF(s) na fila.")
        else:
            self.btn_analisar.config(state="disabled")
            self.status.config(text="Nenhum PDF na fila.")

    def limpar(self):
        if self.processando:
            return
        self.arquivos.clear()
        self.resultados.clear()
        self.tabela.delete(*self.tabela.get_children())
        self.progresso["value"] = 0
        self.btn_renomear.config(state="disabled")
        self.fila_atualizada()

    def iniciar(self):
        if not self.arquivos or self.processando:
            return

        self.processando = True
        for btn in (self.btn_adicionar, self.btn_pasta, self.btn_limpar,
                    self.btn_analisar, self.btn_renomear):
            btn.config(state="disabled")

        self.tabela.delete(*self.tabela.get_children())
        self.resultados.clear()
        total = len(self.arquivos)
        self.progresso.config(maximum=max(total, 1), value=0)
        self.status.config(text=f"Analisando 0 de {total} PDF(s)...")
        threading.Thread(
            target=self.analisar,
            args=(list(self.arquivos),),
            daemon=True
        ).start()

    def analisar(self, arquivos):
        total = len(arquivos)
        for i, pdf in enumerate(arquivos, 1):
            try:
                resultado = processar_pdf(pdf)
                self.resultados.append((pdf, resultado))
                self.root.after(0, lambda p=pdf, r=resultado:
                                self.adicionar_linha(p, r))
            except Exception as erro:
                self.root.after(0, lambda p=pdf, e=erro:
                                self.adicionar_erro(p, e))
            self.root.after(0, lambda i=i, total=total:
                            self.atualizar_progresso(i, total))
        self.root.after(0, self.finalizar_analise)

    def adicionar_linha(self, pdf, resultado):
        tag = resultado.confianca
        self.tabela.insert(
            "", "end",
            values=(
                pdf.name, resultado.tipo, resultado.numero or "-",
                resultado.ano or "-", resultado.confianca.capitalize(),
                resultado.nome_sugerido or "[REVISÃO NECESSÁRIA]"
            ),
            tags=(tag,)
        )

    def adicionar_erro(self, pdf, erro):
        self.tabela.insert(
            "", "end",
            values=(pdf.name, "ERRO", "-", "-", "Baixa", str(erro)),
            tags=("baixa",)
        )

    def atualizar_progresso(self, atual, total):
        self.progresso["value"] = atual
        self.status.config(text=f"Analisando {atual} de {total} PDF(s)...")

    def finalizar_analise(self):
        self.processando = False
        total = len(self.resultados)
        altas = sum(r.confianca == "alta" for _, r in self.resultados)
        revisao = total - altas
        self.atualizar_cards()
        self.status.config(
            text=f"Concluído: {total} PDF(s) • {altas} alta confiança • {revisao} para revisão."
        )
        for btn in (self.btn_adicionar, self.btn_pasta, self.btn_limpar):
            btn.config(state="normal")
        self.btn_analisar.config(state="normal" if self.arquivos else "disabled")
        self.btn_renomear.config(state="normal" if altas else "disabled")

    def renomear(self):
        altas = [
            (pdf, r) for pdf, r in self.resultados
            if r.confianca == "alta" and r.nome_sugerido
        ]
        if not altas:
            messagebox.showinfo("Nada para renomear",
                                "Não há resultados de alta confiança para renomear.")
            return

        if not messagebox.askyesno(
            "Confirmar renomeação",
            f"{len(altas)} arquivo(s) serão renomeados.\n\n"
            "Arquivos de média ou baixa confiança não serão alterados.\n\n"
            "Deseja continuar?"
        ):
            return

        renomeados, erros = 0, []
        for pdf, resultado in altas:
            try:
                destino = pdf.with_name(sanitizar_filename(resultado.nome_sugerido))
                if destino == pdf:
                    continue
                if destino.exists():
                    erros.append(f"{pdf.name}: o nome de destino já existe.")
                    continue
                pdf.rename(destino)
                renomeados += 1
            except Exception as erro:
                erros.append(f"{pdf.name}: {erro}")

        self.status.config(text=f"{renomeados} arquivo(s) renomeado(s).")
        if erros:
            messagebox.showwarning("Renomeação concluída com avisos",
                                   "\n".join(erros[:10]))
        else:
            messagebox.showinfo("Concluído",
                                f"{renomeados} arquivo(s) renomeado(s) com sucesso.")


def main():
    root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
    Aplicativo(root)
    root.mainloop()


if __name__ == "__main__":
    main()
