# -*- coding: utf-8 -*-
"""Interface gráfica do Detector de Atos Oficiais."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import threading
import traceback

from detector_atos import processar_pdf, sanitizar_filename


class Aplicativo:
    def __init__(self, root):
        self.root = root
        self.root.title("Detector de Atos Oficiais")
        self.root.geometry("900x620")
        self.root.minsize(760, 500)

        self.pasta = None
        self.resultados = []

        topo = ttk.Frame(root, padding=16)
        topo.pack(fill="x")

        ttk.Label(
            topo,
            text="DETECTOR DE ATOS OFICIAIS",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            topo,
            text="Selecione uma pasta com PDFs para identificar e sugerir os nomes padronizados.",
        ).pack(anchor="w", pady=(4, 12))

        botoes = ttk.Frame(topo)
        botoes.pack(fill="x")

        ttk.Button(
            botoes,
            text="Selecionar pasta",
            command=self.selecionar_pasta,
        ).pack(side="left")

        self.btn_processar = ttk.Button(
            botoes,
            text="Analisar PDFs",
            command=self.iniciar,
            state="disabled",
        )
        self.btn_processar.pack(side="left", padx=8)

        self.btn_renomear = ttk.Button(
            botoes,
            text="Renomear resultados de alta confiança",
            command=self.renomear,
            state="disabled",
        )
        self.btn_renomear.pack(side="left")

        self.label_pasta = ttk.Label(topo, text="Nenhuma pasta selecionada")
        self.label_pasta.pack(anchor="w", pady=(10, 0))

        self.progresso = ttk.Progressbar(root, mode="determinate")
        self.progresso.pack(fill="x", padx=16, pady=(0, 8))

        self.status = ttk.Label(root, text="Pronto.")
        self.status.pack(anchor="w", padx=16)

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)

        colunas = ("arquivo", "tipo", "numero", "ano", "confianca", "nome")
        self.tabela = ttk.Treeview(frame, columns=colunas, show="headings")

        larguras = {
            "arquivo": 190,
            "tipo": 180,
            "numero": 70,
            "ano": 70,
            "confianca": 90,
            "nome": 430,
        }

        for coluna in colunas:
            self.tabela.heading(coluna, text=coluna.capitalize())
            self.tabela.column(coluna, width=larguras[coluna], anchor="w")

        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=self.tabela.yview)
        scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=self.tabela.xview)
        self.tabela.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tabela.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta com os PDFs")
        if not pasta:
            return

        self.pasta = Path(pasta)
        self.label_pasta.config(text=str(self.pasta))
        self.btn_processar.config(state="normal")
        self.status.config(text="Pasta selecionada. Clique em Analisar PDFs.")

    def iniciar(self):
        if not self.pasta:
            return

        self.btn_processar.config(state="disabled")
        self.btn_renomear.config(state="disabled")
        self.tabela.delete(*self.tabela.get_children())
        self.resultados = []

        threading.Thread(target=self.analisar, daemon=True).start()

    def analisar(self):
        arquivos = sorted(self.pasta.glob("*.pdf"))
        total = len(arquivos)

        self.root.after(0, lambda: self.progresso.config(maximum=max(total, 1), value=0))

        for i, pdf in enumerate(arquivos, 1):
            try:
                resultado = processar_pdf(pdf)
                self.resultados.append((pdf, resultado))

                self.root.after(
                    0,
                    lambda p=pdf, r=resultado: self.adicionar_linha(p, r),
                )
            except Exception as erro:
                self.root.after(
                    0,
                    lambda p=pdf, e=erro: self.adicionar_erro(p, e),
                )

            self.root.after(
                0,
                lambda i=i, total=total: self.atualizar_progresso(i, total),
            )

        self.root.after(0, self.finalizar_analise)

    def adicionar_linha(self, pdf, resultado):
        self.tabela.insert(
            "",
            "end",
            values=(
                pdf.name,
                resultado.tipo,
                resultado.numero or "-",
                resultado.ano or "-",
                resultado.confianca,
                resultado.nome_sugerido or "[REVISÃO NECESSÁRIA]",
            ),
        )

    def adicionar_erro(self, pdf, erro):
        self.tabela.insert(
            "",
            "end",
            values=(pdf.name, "ERRO", "-", "-", "baixa", str(erro)),
        )

    def atualizar_progresso(self, atual, total):
        self.progresso["value"] = atual
        self.status.config(text=f"Analisando {atual} de {total} PDF(s)...")

    def finalizar_analise(self):
        total = len(self.resultados)
        altas = sum(r.confianca == "alta" for _, r in self.resultados)

        self.status.config(
            text=f"Concluído: {total} PDF(s) analisado(s). {altas} resultado(s) de alta confiança."
        )
        self.btn_processar.config(state="normal")
        self.btn_renomear.config(
            state="normal" if altas else "disabled"
        )

    def renomear(self):
        if not self.resultados:
            return

        altas = [
            (pdf, r)
            for pdf, r in self.resultados
            if r.confianca == "alta" and r.nome_sugerido
        ]

        if not altas:
            messagebox.showinfo(
                "Nada para renomear",
                "Não há resultados de alta confiança para renomear.",
            )
            return

        confirmar = messagebox.askyesno(
            "Confirmar renomeação",
            f"{len(altas)} arquivo(s) serão renomeados.\n\n"
            "Arquivos de média ou baixa confiança não serão alterados.\n\n"
            "Deseja continuar?",
        )

        if not confirmar:
            return

        renomeados = 0
        erros = []

        for pdf, resultado in altas:
            try:
                destino = pdf.with_name(
                    sanitizar_filename(resultado.nome_sugerido)
                )
                if destino != pdf:
                    pdf.rename(destino)
                    renomeados += 1
            except Exception as erro:
                erros.append(f"{pdf.name}: {erro}")

        self.status.config(text=f"{renomeados} arquivo(s) renomeado(s).")

        if erros:
            messagebox.showwarning(
                "Renomeação concluída com avisos",
                "\n".join(erros[:10]),
            )
        else:
            messagebox.showinfo(
                "Concluído",
                f"{renomeados} arquivo(s) renomeado(s) com sucesso.",
            )


def main():
    root = tk.Tk()
    try:
        ttk.Style(root).theme_use("vista")
    except Exception:
        pass

    Aplicativo(root)
    root.mainloop()


if __name__ == "__main__":
    main()
