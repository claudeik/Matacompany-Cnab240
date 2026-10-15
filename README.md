# Matacompany — Portal DDA Itaú (Conversor CNAB 240)

Portal web e utilitário em Python da **Matacompany** para leitura de arquivos de **DDA do Banco Itaú (extensão `.DET`)**, identificação de códigos de barras de **44 dígitos** (Segmento G do CNAB 240) e tradução para **Linha Digitável de 47 dígitos**, com exportação dos dados **lado a lado em planilha Excel (.xlsx)**.

---

## 🚀 Funcionalidades Principais

1. **Leitura Automatizada de Arquivos DDA Itaú (.DET / CNAB 240):**
   - Reconhecimento dos registros de detalhe **Segmento G** (DDA / Bloquetos Eletrônicos Febraban/Itaú).
   - Reconhecimento de registros de pagamento **Segmento J**.
   - Reconhecimento de linhas com 44 posições numéricas ou sequências de códigos de barras.
   - Extração de metadados: **Beneficiário / Cedente**, **CNPJ/CPF**, **Data de Vencimento**, **Valor Nominal (R$)** e **Banco Emissor**.

2. **Conversão 44 ➔ 47 Dígitos (Especificação @Claudio - 14/10/2026):**
   - **Módulo 10:** Cálculo com pesos alternados 2, 1, 2, 1... para os dígitos verificadores dos campos 1, 2 e 3 da linha digitável.
   - **Módulo 11:** Validação estrita do DV Geral (posição 5 do código de barras) com pesos 2 a 9 da direita para a esquerda.
   - Formatação visual: `AAABC.CCCCD EEEEE.EEEEEF GGGGG.GGGGGH I JJJJKKKKKKKKKK`.
   - **Operação Inversa (47 ➔ 44 dígitos):** Valida os 3 DVs de campo e remonta o código de barras original.
   - Tratamento de Erros Oficial: Códigos **E01** a **E06** e Aviso **W01**.

3. **Exportação Excel (.xlsx) Lado a Lado Sem Dependências Externas:**
   - Gerador nativo OpenXML embutido (zero `pip`, zero dependências externas).
   - **Código de Barras (44)** e **Linha Digitável (47)** dispostos em colunas **lado a lado**.
   - Células configuradas explicitamente como **Texto (`inlineStr`)**, impedindo que o Excel suprima zeros à esquerda ou converta os números para notação científica.
   - Opção de exportação para **CSV** com BOM UTF-8 e separador `;` para compatibilidade imediata com o Excel brasileiro.

4. **Interface Web Intuitiva:**
   - Drag & Drop de arquivos `.DET`, `.txt`, `.rem`, `.ret`.
   - Botão para carregar arquivo de teste com 1 clique (`exemplo_itau_dda.DET`).
   - Cards de métricas: Total de Títulos, Boletos Válidos, Erros e Soma Financeira Total.
   - Tabela interativa com busca em tempo real, filtros por status e botões de cópia rápida.
   - Aba com Conversor Unitário Interativo e os casos de teste oficiais da especificação técnica.

---

## 📁 Estrutura do Projeto

```
CNAB240/
├── app.py                  # Servidor HTTP nativo com APIs REST (/api/parse, /api/export-excel, etc.)
├── converter.py            # Motor de conversão, módulo 10/11, parser CNAB e gerador Excel OpenXML
├── index.html              # Interface do Portal Web (Single Page Application responsiva)
├── cnab_cli.py             # Interface de linha de comando para automação em lote
├── test_suite.py           # Suíte de testes unitários com os vetores da especificação técnica
├── exemplo_itau_dda.DET    # Arquivo de exemplo DDA Itaú CNAB 240 com boletos reais e casos de teste
└── README.md               # Esta documentação
```

---

## 💻 Como Executar

### 1. Iniciar o Portal Web

Execute no terminal:

```bash
python3 app.py
```

Em seguida, abra seu navegador em:
👉 **[http://localhost:8000](http://localhost:8000)**

> No portal, você pode arrastar o arquivo `exemplo_itau_dda.DET` ou clicar em **"⚡ Carregar Exemplo DDA Itaú (.DET)"** para testar instantaneamente.

---

### 2. Executar via Linha de Comando (CLI)

Para converter um arquivo diretamente para Excel sem abrir o navegador:

```bash
python3 cnab_cli.py exemplo_itau_dda.DET resultado_dda.xlsx
```

---

### 3. Executar os Testes Automatizados

Para conferir a validação dos vetores de teste (Casos A, B, C, erros E01..E06 e operação inversa):

```bash
python3 test_suite.py
```

Resultado:
```
...............
----------------------------------------------------------------------
Ran 15 tests in 0.001s

OK
```

---

## 📋 Mapeamento de Colunas no Excel Gerado

| Coluna | Campo | Tipo | Observação |
| :---: | :--- | :---: | :--- |
| **A** | Item | Numérico | Número sequencial da linha |
| **B** | **Código de Barras (44 dígitos)** | **Texto** | Preserva zeros à esquerda (ex: `0019...`) |
| **C** | **Linha Digitável (47 dígitos)** | **Texto** | Disposta **lado a lado** com a coluna B |
| **D** | **Linha Digitável Formatada** | **Texto** | `AAABC.CCCCD EEEEE.EEEEEF GGGGG.GGGGGH I JJJJKKKKKKKKKK` |
| **E** | Status | Texto | `VÁLIDO` ou Código do Erro (`E01` a `E06`) |
| **F** | Banco Emissor | Texto | Código e Nome do banco (ex: `341 - Banco Itaú Unibanco S.A.`) |
| **G** | Beneficiário / Cedente | Texto | Razão social ou nome extraído do Segmento G |
| **H** | CNPJ / CPF Beneficiário | Texto | Formatado com máscara padrão |
| **I** | Valor (R$) | Texto | Valor nominal do título |
| **J** | Data de Vencimento | Texto | Extraída do CNAB ou calculada pelo fator |
| **K** | Fator de Vencimento | Texto | 4 dígitos do fator Febraban |
| **L** | Origem no Arquivo | Texto | `Segmento G (DDA)`, `Segmento J`, etc. |
| **M** | Mensagem / Observações | Texto | Detalhes de validação e eventuais avisos (`W01`) |
