# Detector de Atos Oficiais

Este repositório passa a ser dedicado exclusivamente ao projeto de **detecção, classificação e padronização de atos oficiais em PDF**.

## O que já está previsto

### Atos com número, ano e ementa
- Lei Municipal
- Lei Complementar
- Projeto de Lei
- Projeto de Decreto
- Projeto de Resolução
- Decreto
- Resolução

### Atos com número, ano e vereador
- Indicação
- Requerimento

### Portarias
- Nomeação
- Exoneração
- Férias
- Lotação
- Licença-Prêmio
- Tornar sem efeito
- Outros subtipos serão acrescentados conforme os exemplos reais

### Documentos de sessão
- Ata de Sessão Ordinária
- Ata de Sessão Extraordinária
- Ata de Sessão Solene
- Pauta da Sessão Ordinária
- Pauta da Sessão Extraordinária
- Pauta de Sessão Solene
- Lista de Presença da Sessão

### Fallback
- Outros Atos Administrativos

## Instalação

```bash
pip install pymupdf pytesseract pillow
```

O Tesseract OCR deve estar instalado no Windows.

Se o Tesseract não estiver no PATH:

```bat
set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Testar

Sem renomear:

```bash
python detector_atos.py "C:\caminho\dos\pdfs"
```

Renomeando somente resultados de alta confiança:

```bash
python detector_atos.py "C:\caminho\dos\pdfs" --renomear
```

## Regra de segurança

O nome original do PDF não é tratado como fonte confiável para ementa, autoria ou pessoa. O detector deve analisar o conteúdo do documento e usar OCR quando necessário.

A V1 é uma base de testes. Os detectores serão refinados com documentos reais.
