# Reading Journal Covers

Este projeto baixa capas de livros a partir de um arquivo CSV, redimensiona as imagens e gera um arquivo PDF organizado e pronto para impressão.

<p align="center">
  <img src="assets/preview.png" alt="Preview do PDF Gerado" width="500">
</p>

---

## Estrutura do Projeto

* `livros.csv` — Arquivo de entrada contendo a lista de livros.
* `main.py` — **Script principal** que executa o fluxo completo (download das capas + geração do PDF).
* `download_covers.py` — Módulo encarregado de buscar e baixar as capas (Google Books / Open Library).
* `generate_print_pages.py` — Módulo responsável por montar as páginas do PDF para impressão.
* `capas/` — Pasta onde as imagens baixadas são salvas individualmente.
* `print_pages.pdf` — Arquivo PDF final gerado para impressão.

---

## Formato do CSV (`livros.csv`)

O arquivo deve estar salvo na raiz do projeto com a codificação UTF-8 e exatamente com estas colunas:

```csv
titulo,autor
O amor nos tempos do cólera,Gabriel García Márquez
A menina que roubava livros,Markus Zusak
```

* `titulo`: Nome do livro (obrigatório)
* `autor`: Nome do autor (opcional, ajuda na precisão da busca)

---

## Como Executar (Fluxo Completo)

Para rodar todo o processo de uma só vez usando as configurações padrão:

```bash
python main.py
```

### O que o `main.py` faz

1. **Lê o arquivo `livros.csv`** e verifica quais capas já existem na pasta `capas/` (evitando downloads repetidos).
2. **Baixa as capas ausentes** buscando no Google Books e Open Library.
3. Exibe um **resumo detalhado** com o status de cada livro (baixados, existentes e falhas).
4. **Gera o arquivo `print_pages.pdf`** contendo todas as capas organizadas em grid.

---

## Execução Individual e Opções Avançadas

Se preferir rodar cada etapa separadamente para customizar parâmetros (como tamanho das imagens, número de colunas, chave de API, etc.), utilize os módulos individuais:

### 1. Baixar apenas as capas

```bash
python download_covers.py livros.csv --output-dir capas
```

#### Opções úteis de download

* `--output-dir`: Pasta onde as imagens serão salvas (padrão: `capas`).

* `--width` e `--height`: Tamanho final das miniaturas das imagens em pixels.
* `--overwrite`: Sobrescreve arquivos de imagem já existentes.
* `--google-api-key`: Chave da API do Google Books (opcional, para aumentar o limite de requisições).

### 2. Gerar apenas o PDF para impressão

```bash
python generate_print_pages.py --input-dir capas --output print_pages.pdf --columns 5 --rows 5 --page-size caderno
```

#### Opções úteis de geração do PDF

* `--input-dir`: Pasta onde as capas salvas estão localizadas.

* `--output`: Nome do arquivo PDF gerado (padrão: `print_pages.pdf`).
* `--columns`: Número de colunas no grid por página (ex: `3`, `5`).
* `--rows`: Número de linhas no grid por página (ex: `3`, `5`).
* `--page-size`: Formato da página para impressão (ex: `caderno`, `a4`, `letter`).

---

## Requisitos do Sistema

Instale as dependências necessárias antes de rodar:

```bash
C:/Python314/python.exe -m pip install -r requirements.txt
```

### Principais dependências

* `Pillow` (Processamento de imagem e montagem do PDF)
* `requests` (Download das imagens via API)
* `python-dotenv` (Gerenciamento de variáveis de ambiente, opcional para chave do Google API)
