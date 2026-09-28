# -*- coding: utf-8 -*-
"""
DETECTOR DE ATOS OFICIAIS

Motor inicial para identificar atos oficiais em PDFs, extrair os campos
necessários e gerar o nome padronizado.

Fluxo:
PDF -> texto -> OCR se necessário -> identificação -> extração ->
validação -> nomenclatura.

Dependências:
    pip install pymupdf pytesseract pillow

O Tesseract OCR deve estar instalado no computador.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz
import pytesseract
from PIL import Image


# ============================================================
# CONFIGURAÇÃO OCR
# ============================================================

TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "").strip()

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
else:
    encontrado = shutil.which("tesseract")
    if encontrado:
        pytesseract.pytesseract.tesseract_cmd = encontrado


# ============================================================
# MODELO
# ============================================================

@dataclass
class Resultado:
    tipo: str
    numero: Optional[str] = None
    ano: Optional[str] = None
    pessoa: Optional[str] = None
    ementa: Optional[str] = None
    nome_sugerido: Optional[str] = None
    confianca: str = "baixa"
    usou_ocr: bool = False


# ============================================================
# FORMATAÇÃO
# ============================================================

PALAVRAS_MINUSCULAS = {
    "a", "o", "as", "os",
    "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas",
    "por", "para", "com", "sem",
    "e", "ou", "mas", "nem",
    "porém", "porem", "entretanto",
    "entre", "sobre", "ao", "aos", "à", "às",
}


def limpar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


ACRONIMOS = {"CNPJ","CPF","CNAE","CGM","SAMU","LDB","TCE","TCE-MA","FUNDEB","PNEERQ","PPP","MA"}

def formatar_titulo(texto: str) -> str:
    """
    Formatação oficial dos nomes:
    - palavras principais: Inicial Maiúscula;
    - artigos, preposições e conjunções: minúsculas;
    - siglas conhecidas: preservadas em maiúsculas.
    """
    texto = limpar_espacos(texto)
    if not texto:
        return ""

    palavras_minusculas = PALAVRAS_MINUSCULAS
    siglas = {x.lower(): x for x in ACRONIMOS}
    saida = []

    for indice, palavra in enumerate(texto.split()):
        m = re.match(r"^([^\wÀ-ÿ]*)(.*?)([^\wÀ-ÿ]*)$", palavra, re.UNICODE)
        if not m:
            saida.append(palavra)
            continue

        inicio, miolo, fim = m.groups()
        chave = miolo.lower()

        if not miolo:
            novo = ""
        elif chave in siglas:
            novo = siglas[chave]
        elif indice > 0 and chave in palavras_minusculas:
            novo = chave
        else:
            novo = miolo[:1].upper() + miolo[1:].lower()

        saida.append(inicio + novo + fim)

    return " ".join(saida)



def sanitizar_filename(nome: str) -> str:
    # Windows não aceita /, \, :, *, ?, ", <, > e |.
    nome = re.sub(r'[<>:"/\\|?*]', "-", nome)
    nome = re.sub(r"[\x00-\x1F]", "", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome.rstrip(". ")


# ============================================================
# TEXTO E OCR
# ============================================================

def extrair_texto_pdf(caminho: Path, max_paginas: int = 5) -> str:
    partes = []

    with fitz.open(caminho) as doc:
        for pagina in list(doc)[:max_paginas]:
            partes.append(pagina.get_text("text"))

    return limpar_espacos("\n".join(partes))


def fazer_ocr(caminho: Path, max_paginas: int = 3, dpi: int = 220) -> str:
    partes = []

    with fitz.open(caminho) as doc:
        for pagina in list(doc)[:max_paginas]:
            pix = pagina.get_pixmap(dpi=dpi, alpha=False)
            imagem = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples,
            )

            try:
                texto = pytesseract.image_to_string(imagem, lang="por")
            except Exception:
                texto = pytesseract.image_to_string(imagem)

            partes.append(texto)

    return limpar_espacos("\n".join(partes))


def obter_texto(caminho: Path) -> tuple[str, bool]:
    texto = extrair_texto_pdf(caminho)

    # Se o texto nativo parece completo, usa-o.
    # Caso contrário, também tenta OCR. Isso é importante para PDFs
    # mistos/digitalizados que possuem texto parcial ou incorreto.
    palavras = len(re.findall(r"\w+", texto, re.UNICODE))
    tem_sinal_ato = bool(re.search(
        r"\b(?:lei|decreto|portaria|resolução|resolucao|"
        r"indicação|indicacao|requerimento|pauta|ata)\b",
        texto,
        re.IGNORECASE,
    ))

    precisa_ocr = palavras < 20 or not tem_sinal_ato

    if precisa_ocr:
        try:
            ocr = fazer_ocr(caminho)
            if len(ocr) > len(texto) * 0.55:
                return ocr, True
        except Exception:
            pass

    return texto, False


# ============================================================
# NÚMERO E ANO
# ============================================================

def extrair_numero_ano(texto: str):
    """Extrai número e ano mesmo quando a data aparece por extenso."""
    cabecalho = texto[:9000]

    padroes = [
        r"\bN[º°o]\s*(\d{1,6})\s*,?\s*DE\s+.*?\b(19\d{2}|20\d{2})\b",
        r"\bN[º°o]\s*(\d{1,6})\s*[-/]\s*(\d{4})\b",
        r"\bN[º°o]\s*(\d{1,6})\s+DE\s+(\d{4})\b",
        r"\b(\d{1,6})\s*[-/]\s*(20\d{2}|19\d{2})\b",
    ]

    for padrao in padroes:
        m = re.search(padrao, cabecalho, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1), m.group(2)

    return None, None


# ============================================================
# EMENTA INTELIGENTE
# ============================================================

def extrair_ementa(texto: str, limite: int = 260) -> Optional[str]:
    """
    Extrai a ementa do bloco imediatamente posterior ao cabeçalho formal.
    Não cria resumo e nunca usa reticências.
    """
    texto = limpar_espacos(texto)

    cabecalho = re.compile(
        r"\b(?:LEI MUNICIPAL|LEI COMPLEMENTAR|PROJETO DE LEI|"
        r"PROJETO DE DECRETO|PROJETO DE RESOLUÇÃO|"
        r"DECRETO(?: MUNICIPAL)?|RESOLUÇÃO)\s+"
        r"N[º°o]\s*\d{1,6}\b",
        re.IGNORECASE,
    )

    matches = list(cabecalho.finditer(texto))
    if not matches:
        return None

    m = matches[0]
    depois = texto[m.end():m.end() + 1400]

    # Remove a data do cabeçalho: ", DE 19 DE FEVEREIRO DE 2025."
    depois = re.sub(
        r"^\s*,?\s*DE\s+.*?\b(?:19|20)\d{2}\b(?:\s*[—–-]\s*[^“\"]*)?",
        "",
        depois,
        count=1,
        flags=re.IGNORECASE,
    ).strip(" .:-")

    aspas = re.search(r"[“\"]\s*(.+?)\s*[”\"]", depois)
    if aspas:
        candidato = limpar_espacos(aspas.group(1))
    else:
        parada = re.search(
            r"\b(?:O PREFEITO|A PREFEITA|O PRESIDENTE|A PRESIDENTE|"
            r"RESOLVE:|DECRETA:|Art\.?\s*1º?)\b",
            depois,
            re.IGNORECASE,
        )
        candidato = depois[:parada.start()] if parada else depois
        candidato = limpar_espacos(candidato).strip(" -–—:;")

    if len(candidato) < 15:
        return None

    if len(candidato) <= limite:
        return candidato

    trecho = candidato[:limite]
    corte = max(trecho.rfind("."), trecho.rfind(";"), trecho.rfind(","))
    if corte >= 80:
        return trecho[:corte + 1].strip()

    return trecho.rsplit(" ", 1)[0].rstrip(" ,;:.")


# ============================================================
# AUTOR DE INDICAÇÃO / REQUERIMENTO
# ============================================================

def extrair_vereador(texto: str) -> Optional[str]:
    padroes = [
        r"(?:autor(?:a|ia)?|proponente|apresentad[oa]\s+por|"
        r"subscrito\s+por)\s*[:\-]?\s*"
        r"(?:ver\.?|vereador(?:a)?)?\s*"
        r"([A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]+(?:\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]+){1,7})",

        r"(?:ver\.?|vereador(?:a)?)\s+"
        r"([A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]+(?:\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]+){1,7})",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto)
        if m:
            nome = m.group(1).strip()
            nome = re.split(
                r"\b(?:presidente|gabinete|mesa diretora|solicita|requer)\b",
                nome,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()

            if len(nome.split()) >= 2:
                return formatar_titulo(nome)

    return None


# ============================================================
# PESSOA DE PORTARIA
# ============================================================

def extrair_pessoa_portaria(texto: str, verbos: tuple[str, ...]) -> Optional[str]:
    """
    Procura primeiro a pessoa no comando formal do ato (ex.: NOMEAR X,
    EXONERAR X) e depois na ementa. Evita capturar palavras do cargo.
    """
    padroes = []

    for verbo in verbos:
        padroes.extend([
            rf"\b{re.escape(verbo)}\b\s+(?:o|a)?\s*"
            rf"(?:Sr\.?|Sra\.?|Dr\.?|Dra\.?)?\s*"
            rf"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]+(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]+){{1,8}})",
        ])

    if "exonerar" in verbos:
        padroes.extend([
            r"\bexonera(?:ção|cao)\b\s+(?:de\s+)?(?:ofício\s+)?"
            r"(?:do|da)\s+(?:Sr\.?|Sra\.?|Dr\.?|Dra\.?)?\s*"
            r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]+(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]+){1,8})",
        ])

    palavras_parada = re.compile(
        r"\b(?:inscrito|inscrita|com|para|ao|à|no|na|ocupante|"
        r"cargo|função|funcao|servidor|servidora|CPF|matrícula|"
        r"matricula|lotado|lotada|exercício|exercicio|do quadro)\b",
        re.IGNORECASE,
    )

    for padrao in padroes:
        m = re.search(padrao, texto, re.IGNORECASE)
        if not m:
            continue

        nome = palavras_parada.split(m.group(1), maxsplit=1)[0].strip(" ,.-")

        # Evita capturar somente uma palavra.
        if len(nome.split()) >= 2:
            return formatar_titulo(nome)

    return None


# ============================================================
# DETECTOR
# ============================================================

def detectar(texto: str, usou_ocr: bool = False) -> Resultado:
    t = limpar_espacos(texto)
    tl = t.lower()

    # ----- ATAS -----
    if re.search(r"\bata\b", tl):
        if "sessão solene" in tl:
            return Resultado(
                "Ata de Sessão Solene",
                nome_sugerido="Ata de Sessão Solene.pdf",
                confianca="alta",
                usou_ocr=usou_ocr,
            )
        if "sessão extraordinária" in tl:
            return Resultado(
                "Ata de Sessão Extraordinária",
                nome_sugerido="Ata de Sessão Extraordinária.pdf",
                confianca="alta",
                usou_ocr=usou_ocr,
            )
        if "sessão ordinária" in tl:
            return Resultado(
                "Ata de Sessão Ordinária",
                nome_sugerido="Ata de Sessão Ordinária.pdf",
                confianca="alta",
                usou_ocr=usou_ocr,
            )

    # ----- PAUTAS -----
    if re.search(r"\bpauta\b", tl):
        if "sessão solene" in tl:
            return Resultado(
                "Pauta de Sessão Solene",
                nome_sugerido="Pauta de Sessão Solene.pdf",
                confianca="alta",
                usou_ocr=usou_ocr,
            )
        if "sessão extraordinária" in tl:
            return Resultado(
                "Pauta da Sessão Extraordinária",
                nome_sugerido="Pauta da Sessão Extraordinária.pdf",
                confianca="alta",
                usou_ocr=usou_ocr,
            )
        if "sessão ordinária" in tl:
            return Resultado(
                "Pauta da Sessão Ordinária",
                nome_sugerido="Pauta da Sessão Ordinária.pdf",
                confianca="alta",
                usou_ocr=usou_ocr,
            )

    # ----- LISTA DE PRESENÇA -----
    if (
        "lista de presença" in tl
        or "folha de presença" in tl
        or (
            "presença" in tl
            and "vereador" in tl
            and "assinatura" in tl
        )
    ):
        return Resultado(
            "Lista de Presença da Sessão",
            nome_sugerido="Lista de Presença da Sessão.pdf",
            confianca="alta",
            usou_ocr=usou_ocr,
        )

    # ----- INDICAÇÃO -----
    if re.search(r"\bindicação\b|\bindicacao\b", tl):
        numero, ano = extrair_numero_ano(t)
        pessoa = extrair_vereador(t)

        nome = None
        if numero and ano and pessoa:
            nome = f"INDICAÇÃO N° {numero}-{ano} - Ver. {pessoa}.pdf"

        return Resultado(
            "Indicação",
            numero=numero,
            ano=ano,
            pessoa=pessoa,
            nome_sugerido=sanitizar_filename(nome) if nome else None,
            confianca="alta" if nome else "média",
            usou_ocr=usou_ocr,
        )

    # ----- REQUERIMENTO -----
    if re.search(r"\brequerimento\b", tl):
        numero, ano = extrair_numero_ano(t)
        pessoa = extrair_vereador(t)

        nome = None
        if numero and ano and pessoa:
            nome = f"REQUERIMENTO N° {numero}-{ano} - Ver. {pessoa}.pdf"

        return Resultado(
            "Requerimento",
            numero=numero,
            ano=ano,
            pessoa=pessoa,
            nome_sugerido=sanitizar_filename(nome) if nome else None,
            confianca="alta" if nome else "média",
            usou_ocr=usou_ocr,
        )

    # ----- PORTARIAS -----
    if re.search(r"\bportaria\b", tl):
        numero, ano = extrair_numero_ano(t)

        # Sempre identificar o subtipo antes de procurar a pessoa.
        if any(x in tl for x in (
            "nomear", "nomeação", "nomeacao", "nomeado", "nomeada"
        )):
            pessoa = extrair_pessoa_portaria(
                t, ("nomear", "nomeia", "nomeado", "nomeada")
            )

            nome = None
            if numero and ano and pessoa:
                nome = f"PORTARIA Nº {numero}-{ano} - Nomear {pessoa}.pdf"

            return Resultado(
                "Portaria de Nomeação",
                numero=numero,
                ano=ano,
                pessoa=pessoa,
                nome_sugerido=sanitizar_filename(nome) if nome else None,
                confianca="alta" if nome else "média",
                usou_ocr=usou_ocr,
            )

        if any(x in tl for x in (
            "exonerar", "exoneração", "exoneracao",
            "exonera", "exonerado", "exonerada"
        )):
            pessoa = extrair_pessoa_portaria(
                t, ("exonerar", "exonera", "exonerado", "exonerada")
            )

            nome = None
            if numero and ano and pessoa:
                nome = f"PORTARIA Nº {numero}-{ano} - Exonerar {pessoa}.pdf"

            return Resultado(
                "Portaria de Exoneração",
                numero=numero,
                ano=ano,
                pessoa=pessoa,
                nome_sugerido=sanitizar_filename(nome) if nome else None,
                confianca="alta" if nome else "média",
                usou_ocr=usou_ocr,
            )

        # Subtipos que já fazem parte do manual; a descrição será refinada
        # com exemplos reais de cada Câmara.
        subtipo = None

        if "férias" in tl or "ferias" in tl:
            subtipo = "Portaria de Férias"
        elif "licença-prêmio" in tl or "licenca-prêmio" in tl:
            subtipo = "Portaria de Licença-Prêmio"
        elif "lotação" in tl or "lotacao" in tl:
            subtipo = "Portaria de Lotação"
        elif "tornar sem efeito" in tl:
            subtipo = "Portaria - Tornar sem efeito"

        if subtipo:
            descricao = extrair_ementa(t)
            nome = None

            if numero and ano and descricao:
                nome = (
                    f"PORTARIA Nº {numero}-{ano} - "
                    f"{formatar_titulo(descricao)}.pdf"
                )

            return Resultado(
                subtipo,
                numero=numero,
                ano=ano,
                ementa=descricao,
                nome_sugerido=sanitizar_filename(nome) if nome else None,
                confianca="média",
                usou_ocr=usou_ocr,
            )

        return Resultado(
            "Portaria",
            numero=numero,
            ano=ano,
            confianca="baixa",
            usou_ocr=usou_ocr,
        )

    # ----- ATOS COM NÚMERO + ANO + EMENTA -----
    tipos = [
        ("projeto de resolução", "PROJETO DE RESOLUÇÃO"),
        ("projeto de decreto", "PROJETO DE DECRETO"),
        ("projeto de lei", "PROJETO DE LEI"),
        ("lei complementar", "LEI COMPLEMENTAR"),
        ("lei municipal", "LEI MUNICIPAL"),
        ("decreto municipal", "DECRETO"),
        ("decreto", "DECRETO"),
        ("resolução", "RESOLUÇÃO"),
    ]

    for termo, rotulo in tipos:
        if re.search(rf"\b{re.escape(termo)}\b", tl):
            numero, ano = extrair_numero_ano(t)
            ementa = extrair_ementa(t)

            nome = None
            if numero and ano and ementa:
                nome = (
                    f"{rotulo} Nº {numero}-{ano} - "
                    f"{formatar_titulo(ementa)}.pdf"
                )

            return Resultado(
                rotulo,
                numero=numero,
                ano=ano,
                ementa=ementa,
                nome_sugerido=sanitizar_filename(nome) if nome else None,
                confianca="alta" if nome else "média",
                usou_ocr=usou_ocr,
            )

    # ----- FALLBACK -----
    return Resultado(
        "Outros Atos Administrativos",
        confianca="baixa",
        usou_ocr=usou_ocr,
    )


# ============================================================
# PROCESSAMENTO
# ============================================================

def processar_pdf(caminho: Path) -> Resultado:
    texto, usou_ocr = obter_texto(caminho)
    return detectar(texto, usou_ocr)


def main():
    parser = argparse.ArgumentParser(
        description="Detector de Atos Oficiais"
    )
    parser.add_argument(
        "entrada",
        help="PDF individual ou pasta com PDFs",
    )
    parser.add_argument(
        "--renomear",
        action="store_true",
        help="Renomeia apenas resultados de alta confiança.",
    )

    args = parser.parse_args()
    entrada = Path(args.entrada)

    if entrada.is_file():
        arquivos = [entrada]
    elif entrada.is_dir():
        arquivos = sorted(entrada.glob("*.pdf"))
    else:
        raise SystemExit("Entrada não encontrada.")

    for pdf in arquivos:
        try:
            resultado = processar_pdf(pdf)

            print("\n" + "=" * 72)
            print("ARQUIVO:", pdf.name)
            print("TIPO:", resultado.tipo)
            print("NÚMERO:", resultado.numero or "-")
            print("ANO:", resultado.ano or "-")
            print("PESSOA:", resultado.pessoa or "-")
            print("EMENTA:", resultado.ementa or "-")
            print("CONFIANÇA:", resultado.confianca)
            print("OCR:", "SIM" if resultado.usou_ocr else "NÃO")
            print(
                "NOME SUGERIDO:",
                resultado.nome_sugerido or "[REVISÃO NECESSÁRIA]",
            )

            if (
                args.renomear
                and resultado.nome_sugerido
                and resultado.confianca == "alta"
            ):
                destino = pdf.with_name(
                    sanitizar_filename(resultado.nome_sugerido)
                )

                if destino != pdf:
                    pdf.rename(destino)
                    print("RENOMEADO PARA:", destino.name)

        except Exception as erro:
            print("\nERRO:", pdf.name, "->", erro)


if __name__ == "__main__":
    main()
