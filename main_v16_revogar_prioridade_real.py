
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import fitz
import re

lista_pdfs=[]
pasta_atual=None

def formatar_nome(nome):
    """Converte para Title Case preservando partículas."""
    nome = re.sub(r"\s+", " ", nome.strip()).lower()
    particulas = {"da", "de", "do", "das", "dos", "e"}
    palavras = []
    for p in nome.split():
        if p in particulas:
            palavras.append(p)
        else:
            palavras.append(p.capitalize())
    return " ".join(palavras)

def identificar_documento(texto):
    texto = re.sub(r"\s+", " ", texto.upper())

    documentos = [
    "PROJETO DE RESOLUÇÃO",
    "PROJETO DE DECRETO",
    "PROJETO DE LEI",

    "LEI COMPLEMENTAR",

    "DECRETO MUNICIPAL",
    "DECRETO",

    "LEI MUNICIPAL",
    "LEI",

    "PORTARIA",

    "RESOLUÇÃO",

    "OFÍCIO",
    "OFICIO",

    "EDITAL",
    "REQUERIMENTO",
    "INDICAÇÃO",
    "INDICACAO",
    "MOÇÃO",
    "MOCAO",
    "ATA",
]

    for documento in documentos:
        if documento in texto:
         return (
    documento
    .replace("DECRETO MUNICIPAL", "DECRETO")
    .replace("LEI MUNICIPAL", "LEI")
    .replace("OFICIO", "OFÍCIO")
    .replace("INDICACAO", "INDICAÇÃO")
    .replace("MOCAO", "MOÇÃO")
)

    return None

def extrair_numero_ano(texto, documento):

    if not documento:
        return "-", "-"

    texto = re.sub(r"\s+", " ", texto)

    # Analisa somente o início do documento
    cabecalho = texto[:1500].upper()

    aliases = {
        "PORTARIA": [
            "PORTARIA"
        ],

        "DECRETO": [
            "DECRETO MUNICIPAL",
            "DECRETO"
        ],

        "LEI": [
            "LEI MUNICIPAL",
            "LEI"
        ],

        "LEI COMPLEMENTAR": [
            "LEI COMPLEMENTAR"
        ],

        "RESOLUÇÃO": [
            "RESOLUÇÃO"
        ],

        "PROJETO DE LEI": [
            "PROJETO DE LEI"
        ],

        "PROJETO DE DECRETO": [
            "PROJETO DE DECRETO"
        ],

        "PROJETO DE RESOLUÇÃO": [
            "PROJETO DE RESOLUÇÃO"
        ]
    }

    for titulo in aliases.get(documento, [documento]):

        titulo = re.escape(titulo)

        padrao = (
            rf"{titulo}"
            rf".{{0,40}}?"
            rf"N[º°o.]?\s*"
            rf"(\d{{1,6}})"
            rf"\s*/\s*"
            rf"(\d{{2,4}})"
        )

        m = re.search(padrao, cabecalho, re.I)

        if m:

            numero = m.group(1).zfill(3)

            ano = m.group(2)

            if len(ano) == 2:
                ano = "20" + ano

            return numero, ano

    return "-", "-"

def limpar_nome(nome):
    remover = [
        "Servidor","Servidora","Servidores","Servidoras",
        "Sr","Sr.","Sra","Sra.","Senhor","Senhora",
        "Portador","Portadora","Portadores","Portadoras"
    ]
    for palavra in remover:
        nome = re.sub(rf"\b{re.escape(palavra)}\b", "", nome, flags=re.I)
    nome = re.sub(r"\s+", " ", nome).strip(" ,.-")
    return nome

def extrair_nome(texto):
    texto = re.sub(r"\s+", " ", texto)

    padroes = [
        r"EXONERAR,\s*a\s+Sra\.?\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+?)(?=portadora|,)",
        r"EXONERAR,\s*o\s+Sr\.?\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+?)(?=portador|,)",
        r"EXONERAR,\s*a\s+pedido\s+da\s+servidora\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+?)(?=,)",
        r"EXONERAR,\s*a\s+pedido\s+do\s+servidor\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+?)(?=,)",
        r"NOMEAR\s+(?:a|o)?\s*(?:Sra\.?|Sr\.?)?\s*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+?)(?=,| para| no cargo)",
        r"DESIGNAR\s+(?:a|o)?\s*(?:Sra\.?|Sr\.?)?\s*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+?)(?=,| para| no cargo)",
        r"CONCEDER\s+(?:AO|AO|À|A|O)?\s*SERVIDORA?\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+?)(?=,|\s+PORTADOR|\s+PORTADORA|\s+CPF|\s+RG)",
        r"Art\.\s*0?1.?[^A-Z]{0,20}(?:EXONERAR|NOMEAR|DESIGNAR).*?(?:Sra\.?|Sr\.?)\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+?)(?=portador|portadora|,)",
    ]

    for p in padroes:
        m = re.search(p, texto, re.I)
        if m:
            nome = " ".join(m.group(1).split())
            if len(nome) > 3:
                return limpar_nome(nome)

    verbos=[
        "NOMEAR","NOMEIA","NOMEAÇÃO",
        "EXONERAR","EXONERA","EXONERAÇÃO",
        "DESIGNAR","DESIGNA","DESIGNAÇÃO",
        "CONCEDER"
    ]

    texto_up = texto.upper()

    for verbo in verbos:
        pos = texto_up.find(verbo)
        if pos == -1:
            continue

        trecho = texto[pos:].replace("\n"," ")

        blocos = re.findall(
            r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{2,}(?:\s+(?:DE|DA|DO|DAS|DOS|E|[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{2,}))+",
            trecho
        )

        ignorar = {
            "SERVIDOR","SERVIDORA","SERVIDORES","SERVIDORAS",
            "PÚBLICO","PUBLICO","PÚBLICA","PUBLICA",
            "EFETIVO","EFETIVA","COMISSIONADO","COMISSIONADA",
            "CONTRATADO","CONTRATADA","MUNICIPAL","PREFEITA","PREFEITO","ESTADO","MARANHÃO","MARANHAO",
            "MUNICÍPIO","MUNICIPIO","SECRETARIA","SAÚDE","SAUDE","EDUCAÇÃO",
            "EDUCACAO","REMUNERAÇÃO","REMUNERACAO"
        }

        melhor = None
        for bloco in blocos:
            palavras = bloco.split()
            while palavras and palavras[0] in ignorar:
                palavras.pop(0)
            if len(palavras) >= 2:
                melhor = " ".join(palavras)

        if melhor:
            return limpar_nome(melhor)

    return "-"



def extrair_revogacao(texto):
    texto = re.sub(r"\s+", " ", texto)

    # Captura tudo após "REVOGAR" até a sigla da secretaria (SEM...)
    m = re.search(
        r"REVOGAR\s*,?\s*(.*?\bSEM[A-Z]+\b)",
        texto,
        re.I | re.S
    )
    if not m:
        return None

    trecho = re.sub(r"\s+", " ", m.group(1)).strip()
    return "Revogar, " + trecho

def extrair_tipo(texto):
    rev = extrair_revogacao(texto)
    if rev:
        return rev
    n = texto.upper()
    if ("NOMEAR" in n or "NOMEIA" in n) and "REVOGAR" not in n:
        return "Nomear"
    if "EXONERAR" in n or "EXONERA" in n or "EXONERAÇÃO" in n:
        return "Exonerar"
    if "DESIGNAR" in n or "DESIGNA" in n or "DESIGNAÇÃO" in n:
        return "Designar"
    if "CONCEDER" in n:
        if "SERVIDORA" in n:
            return "Conceder Licença Prêmio à Servidora"
        if "SERVIDOR" in n:
            return "Conceder Licença Prêmio ao Servidor"
        return "Conceder"
    return "Não identificado"

def carregar_lista():
    lista.delete(0,tk.END)
    for p in lista_pdfs:
        lista.insert(tk.END,p.name)
    lbl_total.config(text=f"{len(lista_pdfs)} PDF(s) encontrado(s)")

def selecionar_pasta():
    global lista_pdfs,pasta_atual
    pasta=filedialog.askdirectory()
    if not pasta: return
    pasta_atual=Path(pasta)
    lista_pdfs=sorted(pasta_atual.glob("*.pdf"))
    lbl_pasta.config(text=str(pasta_atual))
    carregar_lista()

def nome_disponivel(dest):
    if not dest.exists():
        return dest
    i=2
    while True:
        novo=dest.with_name(f"{dest.stem} ({i}){dest.suffix}")
        if not novo.exists():
            return novo
        i+=1
def dados_pdf(pdf):
    doc = fitz.open(pdf)
    texto = "".join(p.get_text() for p in doc)
    doc.close()
    
    if not texto.strip():
    return None, "-", "-", "", ""
    
    documento = identificar_documento(texto)
    numero, ano = extrair_numero_ano(texto, documento)

    # Se não conseguiu identificar o documento
    if documento is None:
        return None, numero, ano, "-", "-"

    # Fluxo específico para Portarias
    if documento == "PORTARIA":

        if "REVOGAR" in texto.upper():
            tipo = extrair_revogacao(texto)
            return documento, numero, ano, "", tipo

        tipo = extrair_tipo(texto)
        nome = extrair_nome(texto)

        return documento, numero, ano, nome, tipo

    # Todos os demais documentos
    return documento, numero, ano, "", ""

def ler_pdf(event=None):
    sel=lista.curselection()
    if not sel:return
    pdf=lista_pdfs[sel[0]]
    try:
        documento, numero, ano, nome, tipo = dados_pdf(pdf)
        lbl_numero.config(text=f"Número: {numero}")
        lbl_ano.config(text=f"Ano: {ano}")
        lbl_tipo.config(text=f"Tipo: {tipo}")
        lbl_nome.config(text=f"Nome: {nome}")

        documento = "PORTARIA"

        lbl_novo.config(
            text=f"{documento} Nº {numero}-{ano} - {tipo}{(' ' + formatar_nome(nome)) if nome else ''}.pdf"
        )
    except Exception as e:
        messagebox.showerror("Erro", str(e))

def renomear_todos():
    global lista_pdfs

    if not lista_pdfs:
        return

    erros = []
    barra["maximum"] = len(lista_pdfs)
    ren = 0

    for i, pdf in enumerate(lista_pdfs, 1):

        try:

            documento, numero, ano, nome, tipo = dados_pdf(pdf)

            if documento is None:
                continue
            if numero == "-" or ano == "-":
                raise Exception("Número ou ano não encontrado")

            # ===== PORTARIAS =====
            if documento == "PORTARIA":

                novo_nome = (
                    f"PORTARIA Nº {numero}-{ano}"
                    f"{(' - ' + tipo) if tipo else ''}"
                    f"{(' ' + formatar_nome(nome)) if nome else ''}.pdf"
                )

            # ===== TODOS OS DEMAIS =====
            else:

                novo_nome = f"{documento} Nº {numero}-{ano}.pdf"

            destino = nome_disponivel(pdf.with_name(novo_nome))
            pdf.rename(destino)

            ren += 1

        except Exception as e:
            erros.append(f"{pdf.name} -> {e}")

        barra["value"] = i
        lbl_prog.config(text=f"{i}/{len(lista_pdfs)}")
        janela.update_idletasks()

    if pasta_atual:
        lista_pdfs = sorted(pasta_atual.glob("*.pdf"))
        carregar_lista()

    msg = f"Renomeados: {ren}"

    if erros:
        msg += "\n\nErros:\n" + "\n".join(erros)

    messagebox.showinfo("Concluído", msg)
janela=tk.Tk()
janela.title("Completador de Portarias")
janela.geometry("950x850")
tk.Label(janela,text="COMPLETADOR DE PORTARIAS",font=("Segoe UI",18,"bold")).pack(pady=10)
tk.Button(janela,text="Selecionar Pasta",command=selecionar_pasta,width=25).pack()
lbl_pasta=tk.Label(janela);lbl_pasta.pack()
lbl_total=tk.Label(janela,text="0 PDF(s)");lbl_total.pack()
lista=tk.Listbox(janela,width=110,height=18)
lista.pack(pady=10)
lista.bind("<Double-Button-1>",ler_pdf)
tk.Button(janela,text="RENOMEAR TODOS",font=("Segoe UI",11,"bold"),command=renomear_todos,bg="#1e88e5",fg="white").pack(pady=10)
barra=ttk.Progressbar(janela,length=500,mode="determinate")
barra.pack()
lbl_prog=tk.Label(janela,text="0/0")
lbl_prog.pack(pady=(0,10))

frame=tk.LabelFrame(janela,text="Informações extraídas")
frame.pack(fill="x",padx=15,pady=5)
lbl_numero=tk.Label(frame,text="Número: -");lbl_numero.pack(anchor="w")
lbl_ano=tk.Label(frame,text="Ano: -");lbl_ano.pack(anchor="w")
lbl_tipo=tk.Label(frame,text="Tipo: -");lbl_tipo.pack(anchor="w")
lbl_nome=tk.Label(frame,text="Nome: -");lbl_nome.pack(anchor="w")
tk.Label(janela,text="Novo nome do arquivo",font=("Segoe UI",10,"bold")).pack()
lbl_novo=tk.Label(janela,text="-",fg="blue");lbl_novo.pack()
janela.mainloop()
