import argparse
import csv
import os
import random
import re
import sys
import time
from io import BytesIO

from dotenv import load_dotenv
from PIL import Image, ImageOps
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

load_dotenv()

def load_titles(csv_path):
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            reader = csv.DictReader(handle, dialect=dialect)
        except csv.Error:
            handle.seek(0)
            reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise ValueError("CSV inválido. O arquivo está vazio.")

        normalized_headers = [
            name.strip().lower() for name in reader.fieldnames
        ]
        if normalized_headers != ["titulo", "autor"]:
            raise ValueError(
                "Formato CSV inválido. Use apenas as colunas 'titulo' e 'autor'."
            )

        books = []
        for row in reader:
            title = (row.get("titulo") or "").strip()
            author = (row.get("autor") or "").strip()
            if title:
                books.append({"title": title, "author": author})
        return books


def normalize_text(value):
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def create_session():
    session = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = create_session()
GOOGLE_API_KEY = None


def choose_google_book_item(items, title, author=""):
    title_norm = normalize_text(title)
    author_norm = normalize_text(author)
    best_item = None
    best_score = -999

    for item in items:
        volume_info = item.get("volumeInfo", {})
        book_title = normalize_text(volume_info.get("title", ""))
        book_authors = [
            normalize_text(a) for a in volume_info.get("authors", []) if a
        ]
        language = volume_info.get("language", "")
        image_links = volume_info.get("imageLinks", {})
        has_cover = bool(
            image_links.get("thumbnail") or image_links.get("smallThumbnail")
        )
        published_date = volume_info.get("publishedDate", "9999")  # Ex: "2014-02-05"

        score = 0

        # 1. BÔNUS CRÍTICO: Idioma Português (Prioridade Máxima)
        if language == "pt":
            score += 300
        else:
            score -= 100  # Penaliza edições em inglês ou outros idiomas

        # 2. Match de Título
        if title_norm == book_title:
            score += 150
        elif title_norm in book_title or book_title in title_norm:
            score += 70

        # 3. Match de Autor
        if author_norm and book_authors:
            if author_norm in book_authors:
                score += 100
            elif any(
                author_norm in book_author or book_author in author_norm
                for book_author in book_authors
            ):
                score += 50

        # 4. Outros bônus
        if item.get("saleInfo", {}).get("country") == "BR":
            score += 20
        if has_cover:
            score += 50

        # 5. DESEMPATE PELA DATA: Dá uma pequena vantagem para publicações mais antigas (edição original)
        # Extrai o ano (primeiros 4 dígitos)
        year_match = re.match(r"^(\d{4})", published_date)
        if year_match:
            year = int(year_match.group(1))
            # Quanto mais antigo o ano, maior a pontuação extra
            score += (2030 - year) * 0.1

        if score > best_score:
            best_score = score
            best_item = item

    return best_item


def normalize_google_cover_url(url):
    if not url:
        return None

    url = url.replace("http://", "https://")
    if "zoom=1" in url:
        url = url.replace("zoom=1", "zoom=2")
    return url


def extract_google_cover_url(item):
    if not item:
        return None

    image_links = item.get("volumeInfo", {}).get("imageLinks", {})
    for key in ("extraLarge", "large", "medium", "thumbnail", "smallThumbnail"):
        url = image_links.get(key)
        if url:
            # Descarte imagens genéricas/placeholders do Google Books
            if "no_cover" in url or "gbs_preview_button" in url:
                continue
            return normalize_google_cover_url(url)
    return None


def build_google_query(title, author=""):
    title = title.strip()
    author = author.strip()
    parts = []
    if title:
        parts.append(f'intitle:"{title}"')
    if author:
        parts.append(f'inauthor:"{author}"')
    return "+".join(parts)


def search_cover_url_google(title, author=""):
    base_url = "https://www.googleapis.com/books/v1/volumes"

    def fetch_google_items(query_str):
        params = {
            "q": query_str,
            "langRestrict": "pt",
            "printType": "books",
            "maxResults": 5,
        }
        if GOOGLE_API_KEY:
            params["key"] = GOOGLE_API_KEY

        headers = {"User-Agent": "Mozilla/5.0"}
        resp = SESSION.get(
            base_url, params=params, timeout=20, headers=headers
        )

        if resp.status_code == 429:
            time.sleep(random.uniform(2.0, 4.0))  # Pausa maior para liberar o IP
            resp = SESSION.get(
                base_url, params=params, timeout=20, headers=headers
            )

        resp.raise_for_status()
        return resp.json().get("items", [])

    # 1. Tenta buscar por Título + Autor
    query = build_google_query(title, author)
    items = fetch_google_items(query)

    # 2. Fallback: Se não achou com o autor, tenta buscar apenas por Título
    if not items and author:
        query_fallback = build_google_query(title, author="")
        items = fetch_google_items(query_fallback)

    if not items:
        return None

    best_item = choose_google_book_item(items, title, author)
    return extract_google_cover_url(best_item)


def search_cover_url_openlibrary(title, author=""):
    query = f"{title} {author}".strip()
    response = SESSION.get(
        "https://openlibrary.org/search.json",
        params={"q": query, "limit": 5, "fields": "cover_i,isbn,title"},
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    if response.status_code == 429:
        time.sleep(random.uniform(1.0, 2.0))
        response = SESSION.get(
            "https://openlibrary.org/search.json",
            params={"q": query, "limit": 5, "fields": "cover_i,isbn,title"},
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


def search_cover_url_with_fallback(title, author=""):
    """Tenta baixar via Google; se falhar ou for placeholder, cai para Open Library."""
    # 1. Tenta via Google Books
    try:
        url = search_cover_url_google(title, author)
        if url:
            image_bytes = download_bytes(url)
            # Só aceita se NÃO for imagem genérica / placeholder
            with Image.open(BytesIO(image_bytes)) as img:
                if not is_placeholder_image(img):
                    return url, image_bytes
    except Exception:
        pass

    # 2. Fallback: Open Library
    try:
        url = search_cover_url_openlibrary(title, author)
        if url:
            image_bytes = download_bytes(url)
            with Image.open(BytesIO(image_bytes)) as img:
                if not is_placeholder_image(img):
                    return url, image_bytes
    except Exception:
        pass

    return None, None


def download_bytes(url):
    response = SESSION.get(
        url, timeout=20, headers={"User-Agent": "Mozilla/5.0"}
    )
    response.raise_for_status()
    return response.content


def is_placeholder_image(image):
    grayscale = image.convert("L")
    min_pixel, max_pixel = grayscale.getextrema()
    
    # Se quase não houver variação de tom (imagem lisa/cinza)
    if max_pixel - min_pixel < 15:
        return True

    # Se a imagem for extremamente pequena ou um recorte genérico de código de barras
    width, height = image.size
    if width < 50 or height < 50:
        return True

    return False


def sanitize_filename(title):
    # Mantém letras com acento, números, pontos e hífens
    clean = re.sub(r"[^\w\.-]+", "_", title, flags=re.UNICODE).strip("._")
    return clean or "capa"


def save_thumbnail(image_bytes, output_path, size):
    with Image.open(BytesIO(image_bytes)) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        if is_placeholder_image(image):
            raise ValueError("Imagem inválida ou placeholder detectado")
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
    global GOOGLE_API_KEY
    parser = argparse.ArgumentParser(
        description="Baixa capas de livros a partir de um CSV"
    )
    parser.add_argument("csv_path", nargs="?", default="livros.csv")
    parser.add_argument("--output-dir", default="capas")
    parser.add_argument("--width", type=int, default=300)
    parser.add_argument("--height", type=int, default=450)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--google-api-key",
        default=os.environ.get("GOOGLE_BOOKS_API_KEY"),
        help="Chave da API Google Books (opcional).",
    )
    args = parser.parse_args()
    GOOGLE_API_KEY = args.google_api_key

    if not os.path.exists(args.csv_path):
        print(f"Arquivo não encontrado: {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    try:
        books = load_titles(args.csv_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if not books:
        print("Nenhum livro encontrado no arquivo de entrada.")
        return

    size = (args.width, args.height)
    print(
        f"Encontrados {len(books)} títulos. Salvando em {args.output_dir}...\n"
    )

    # Contadores e Listas para o Relatório Final
    total_books = len(books)
    downloaded_count = 0
    already_existed_count = 0
    failed_books = []  # Armazena os livros que não tiveram capa baixada

    for index, book in enumerate(books, start=1):
        title = book["title"]
        author = book.get("author", "")
        search_label = f"{title} ({author})" if author else title
        print(f"[{index}/{total_books}] Processando: {search_label}")

        # 1. VERIFICAÇÃO ANTECIPADA: Prevê o nome do arquivo padrão (.jpg)
        base_name = sanitize_filename(title)
        expected_path = os.path.join(args.output_dir, f"{base_name}.jpg")

        if os.path.exists(expected_path) and not args.overwrite:
            print(f"  -> já existe localmente: {os.path.basename(expected_path)} (PULANDO BUSCA)")
            already_existed_count += 1
            continue

        # 2. BUSCA E DOWNLOAD
        try:
            cover_url, image_bytes = search_cover_url_with_fallback(title, author)
            
            if not cover_url or not image_bytes:
                print("  -> capa não encontrada ou imagem inválida nas APIs")
                failed_books.append(search_label)
                time.sleep(random.uniform(1.0, 2.0))
                continue

            output_path = build_output_path(args.output_dir, title, index)
            save_thumbnail(image_bytes, output_path, size)
            print(f"  -> salva em {output_path}")
            downloaded_count += 1

            time.sleep(random.uniform(1.0, 2.0))

        except requests.RequestException as exc:
            print(f"  -> erro na requisição: {exc}")
            failed_books.append(search_label)
        except Exception as exc:
            print(f"  -> erro inesperado: {exc}")
            failed_books.append(search_label)

    # ==========================================
    # RELATÓRIO FINAL / RESUMO
    # ==========================================
    print("\n" + "=" * 50)
    print("              RESUMO DA EXECUÇÃO             ")
    print("=" * 50)
    print(f"Total de livros processados : {total_books}")
    print(f"Novas capas baixadas       : {downloaded_count}")
    print(f"Já existentes localmente   : {already_existed_count}")
    print(f"Sem capa encontrada / erro : {len(failed_books)}")

    if failed_books:
        print("\n--------------------------------------------------")
        print("LIVROS QUE NÃO TIVERAM CAPA GERADA:")
        print("--------------------------------------------------")
        for item in failed_books:
            print(f" ❌ {item}")
    else:
        print("\n🎉 Sucesso total! Todos os livros têm capas salvas.")
    
    print("=" * 50)


if __name__ == "__main__":
    main()