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


def formatar_titulo(texto: str) -> str:
    """
    Palavras principais com inicial maiúscula.
    Artigos, preposições e conjunções ficam minúsculos.
    Nomes próprios recebem a mesma normalização.
    """
    texto = limpar_espacos(texto)
    if not texto:
        return ""

    saida = []

    for indice, palavra in enumerate(texto.split()):
        m = re.match(r"^([^\wÀ-ÿ]*)(.*?)([^\wÀ-ÿ]*)$", palavra, re.UNICODE)
        if not m:
            saida.append(palavra)
            continue

        inicio, miolo, fim = m.groups()
        chave = miolo.lower()

        if indice > 0 and chave in PALAVRAS_MINUSCULAS:
            novo = chave
        elif miolo.isupper() and len(miolo) > 1:
            novo = miolo
        elif miolo:
            novo = miolo[0].upper() + miolo[1:].lower()
        else:
            novo = miolo

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

    # Primeiro tenta texto nativo; OCR só quando necessário.
    if len(re.findall(r"\w+", texto, re.UNICODE)) >= 20:
        return texto, False

    try:
        ocr = fazer_ocr(caminho)
        if len(ocr) > len(texto):
            return ocr, True
    except Exception:
        pass

    return texto, False


# ============================================================
# NÚMERO E ANO
# ============================================================

def extrair_numero_ano(texto: str):
    """
    Procura o número/ano no próprio documento.
    O padrão final usa hífen, mesmo quando o PDF original usa barra.
    """
    cabecalho = texto[:7000]

    padroes = [
        r"\bN[º°o]\s*(\d{1,6})\s*[-/]\s*(\d{4})\b",
        r"\bN[º°o]\s*(\d{1,6})\s+DE\s+(\d{4})\b",
        r"\b(\d{1,6})\s*[-/]\s*(20\d{2}|19\d{2})\b",
    ]

    for padrao in padroes:
        m = re.search(padrao, cabecalho, re.IGNORECASE)
        if m:
            return m.group(1), m.group(2)

    return None, None


# ============================================================
# EMENTA INTELIGENTE
# ============================================================

def extrair_ementa(texto: str, limite: int = 300) -> Optional[str]:
    """
    Seleciona um trecho contínuo do texto original.
    Não cria resumo e não usa reticências.
    Para ementas longas, tenta encerrar em pontuação natural.
    """
    texto = limpar_espacos(texto)
    candidatos = []

    padrao_inicio = (
        r"\b(?:dispõe|institui|cria|autoriza|estabelece|"
        r"regulamenta|altera|fixa|concede|declara)\b"
    )

    for m in re.finditer(padrao_inicio, texto, re.IGNORECASE):
        trecho = texto[m.start():m.start() + 1000]
        finais = [x.end() for x in re.finditer(r"[.;!?]", trecho[:limite])]

        if finais:
            candidato = trecho[:finais[-1]].strip()
            if len(candidato) >= 45:
                candidatos.append(candidato)

    if not candidatos:
        return None

    # Procura uma descrição suficientemente informativa.
    candidatos.sort(key=lambda x: abs(len(x) - 180))
    escolhido = candidatos[0]

    if len(escolhido) > limite:
        trecho = escolhido[:limite]
        corte = max(trecho.rfind("."), trecho.rfind(";"), trecho.rfind(","))
        if corte >= 80:
            escolhido = trecho[:corte + 1].strip()

    return escolhido


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
    for verbo in verbos:
        padrao = (
            rf"\b{re.escape(verbo)}\b\s+(?:o|a)?\s*"
            rf"(?:Sr\.?|Sra\.?|Dr\.?|Dra\.?)?\s*"
            rf"([A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]+"
            rf"(?:\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]+){{1,8}})"
        )

        m = re.search(padrao, texto, re.IGNORECASE)
        if m:
            nome = re.split(
                r"\b(?:para|ao|à|no|na|ocupante|cargo|função|funcao)\b",
                m.group(1),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()

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
