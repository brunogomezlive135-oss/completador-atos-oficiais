# Manual de Regras — Detector de Atos Oficiais

## 1. Regra geral

PDF → texto → OCR quando necessário → identificação do tipo → extração dos campos → validação → nomenclatura.

Por padrão, procurar número e ano, salvo quando o tipo tiver regra explícita sem esses campos.

## 2. Ementa inteligente

- Se a ementa for curta e fizer sentido, usar inteira.
- Se for longa, selecionar um trecho contínuo que identifique o objeto.
- Encerrar em ponto natural.
- Não cortar no meio de uma ideia.
- Não terminar com reticências.
- Não inventar uma nova ementa.
- Não usar o nome original do arquivo como fonte da ementa.

Aplicável a leis, projetos, decretos, resoluções e portarias que tenham objeto/ementa.

## 3. Formatação

- Palavras principais com inicial maiúscula.
- Artigos, preposições e conjunções normalmente minúsculos: a, o, as, os, de, do, da, dos, das, para, em, no, na, e, ou, entre outros.
- Nomes próprios preservam capitalização.
- Siglas permanecem em maiúsculas.
- Número/ano usam hífen: 04-2023.
- Não usar barra no nome final.

## 4. Indicação

INDICAÇÃO N° {número}-{ano} - Ver. {nome do vereador}.pdf

Não usar "Gabinete do Vereador" no nome final.

## 5. Requerimento

REQUERIMENTO N° {número}-{ano} - Ver. {nome do vereador}.pdf

## 6. Portarias

Primeiro identificar o subtipo. Depois extrair número, ano e a pessoa/informação correspondente.

Nomeação:
PORTARIA Nº {número}-{ano} - Nomear {pessoa}.pdf

Exoneração:
PORTARIA Nº {número}-{ano} - Exonerar {pessoa}.pdf

## 7. Atas

Ata de Sessão Ordinária.pdf
Ata de Sessão Extraordinária.pdf
Ata de Sessão Solene.pdf

## 8. Pautas

Pauta da Sessão Ordinária.pdf
Pauta da Sessão Extraordinária.pdf
Pauta de Sessão Solene.pdf

## 9. Presença

Lista de Presença da Sessão.pdf

O layout pode variar; o detector deve reconhecer a finalidade pelo conteúdo.

## 10. Fallback

Documentos que não correspondam aos detectores conhecidos entram inicialmente em Outros Atos Administrativos.

Novos tipos serão adicionados conforme forem apresentados exemplos reais.
