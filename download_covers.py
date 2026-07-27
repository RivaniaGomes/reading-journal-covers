import argparse
import csv
import os
import re
import sys
from io import BytesIO

import requests
from PIL import Image, ImageOps


def find_title_column(fieldnames):
    if not fieldnames:
        return None

    aliases = {"titulo", "title", "título", "livro", "nome"}
    for name in fieldnames:
        if name and name.strip().lower() in aliases:
            return name

    for name in fieldnames:
        if name:
            normalized = re.sub(r"[^a-z]", "", name.strip().lower())
            if normalized in {"titulo", "title", "titulo", "livro", "nome"}:
                return name
    return None


def load_titles(csv_path):
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            reader = csv.DictReader(handle, dialect=dialect)
        except csv.Error:
            handle.seek(0)
            reader = csv.DictReader(handle)

        title_column = find_title_column(reader.fieldnames)
        if not title_column:
            raise ValueError(
                "CSV inválido. Adicione uma coluna chamada 'titulo' ou 'title'."
            )

        titles = []
        for row in reader:
            title = (row.get(title_column) or "").strip()
            if title:
                titles.append(title)
        return titles


def search_cover_url_google(title):
    params = {"q": f"intitle:{title}", "maxResults": 1}
    response = requests.get(
        "https://www.googleapis.com/books/v1/volumes",
        params=params,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    data = response.json()

    items = data.get("items", [])
    if not items:
        return None

    volume_info = items[0].get("volumeInfo", {})
    image_links = volume_info.get("imageLinks", {})

    for key in ("thumbnail", "smallThumbnail", "medium", "large"):
        url = image_links.get(key)
        if url:
            return url

    return None


def search_cover_url_openlibrary(title):
    response = requests.get(
        "https://openlibrary.org/search.json",
        params={"q": title, "limit": 5, "fields": "cover_i,isbn,title"},
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    data = response.json()

    docs = data.get("docs", [])
    for doc in docs:
        if doc.get("cover_i"):
            return f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg"

        isbns = doc.get("isbn") or []
        if isbns:
            return f"https://covers.openlibrary.org/b/isbn/{isbns[0]}-L.jpg"

    return None


def search_cover_url(title):
    try:
        cover_url = search_cover_url_google(title)
        if cover_url:
            return cover_url
    except requests.RequestException as exc:
        print(f"  -> Google Books falhou: {exc}")

    try:
        cover_url = search_cover_url_openlibrary(title)
        if cover_url:
            return cover_url
    except requests.RequestException as exc:
        print(f"  -> Open Library falhou: {exc}")

    return None


def download_bytes(url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.content


def sanitize_filename(title):
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", title).strip("._")
    return clean or "capa"


def save_thumbnail(image_bytes, output_path, size):
    with Image.open(BytesIO(image_bytes)) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
        image.save(output_path, "JPEG", quality=95)


def build_output_path(output_dir, title, index):
    base_name = sanitize_filename(title)
    candidate = os.path.join(output_dir, f"{base_name}.jpg")
    if not os.path.exists(candidate):
        return candidate

    suffix = 2
    while True:
        candidate = os.path.join(output_dir, f"{base_name}_{suffix}.jpg")
        if not os.path.exists(candidate):
            return candidate
        suffix += 1


def main():
    parser = argparse.ArgumentParser(description="Baixa capas de livros a partir de um CSV")
    parser.add_argument("csv_path", nargs="?", default="livros.csv")
    parser.add_argument("--output-dir", default="capas")
    parser.add_argument("--width", type=int, default=300)
    parser.add_argument("--height", type=int, default=450)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"Arquivo não encontrado: {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    try:
        titles = load_titles(args.csv_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if not titles:
        print("Nenhum título encontrado no CSV.")
        return

    size = (args.width, args.height)
    print(f"Encontrados {len(titles)} títulos. Salvando em {args.output_dir}...")

    for index, title in enumerate(titles, start=1):
        print(f"[{index}/{len(titles)}] Buscando capa para: {title}")
        try:
            cover_url = search_cover_url(title)
            if not cover_url:
                print("  -> capa não encontrada")
                continue

            image_bytes = download_bytes(cover_url)
            output_path = build_output_path(args.output_dir, title, index)
            if os.path.exists(output_path) and not args.overwrite:
                print(f"  -> já existe: {os.path.basename(output_path)}")
                continue

            save_thumbnail(image_bytes, output_path, size)
            print(f"  -> salva em {output_path}")
        except requests.RequestException as exc:
            print(f"  -> erro na requisição: {exc}")
        except Exception as exc:
            print(f"  -> erro inesperado: {exc}")


if __name__ == "__main__":
    main()
