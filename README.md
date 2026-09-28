# Detector de Atos Oficiais

Este repositório é dedicado exclusivamente à **detecção, classificação e padronização de atos oficiais em PDF**.

## Interface gráfica

Para abrir o programa no Windows, dê dois cliques em:

`iniciar_detector.bat`

Também é possível abrir pelo terminal:

```bat
python app.py
```

A interface permite selecionar uma pasta, analisar os PDFs, conferir o tipo, número, ano, confiança e nome sugerido e, somente depois, renomear os resultados de alta confiança.

## Instalação

```bash
pip install -r requirements.txt
```

O Tesseract OCR também precisa estar instalado no Windows.

Se o Tesseract não estiver no PATH:

```bat
set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Detectores previstos

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
- Novos subtipos conforme os exemplos reais

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

## Regra de segurança

A análise deve usar o conteúdo do documento, e não confiar no nome original do PDF como fonte da ementa, autoria ou pessoa.

A V1 é uma base de testes e será refinada com documentos reais.
