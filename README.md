# Reading Journal Covers

Este projeto baixa capas de livros a partir de um CSV e salva imagens em tamanho configurável.

## Requisitos

```bash
C:/Python314/python.exe -m pip install -r requirements.txt
```

## Uso

1. Edite o arquivo livros.csv e coloque os títulos em uma coluna chamada `titulo`.
2. Execute:

```bash
C:/Python314/python.exe download_covers.py livros.csv --output-dir capas --width 300 --height 450
```

- `--output-dir`: pasta onde as imagens serão salvas
- `--width` e `--height`: tamanho final das miniaturas
- `--overwrite`: sobrescreve arquivos já existentes
