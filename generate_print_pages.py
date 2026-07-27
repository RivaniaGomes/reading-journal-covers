import argparse
from pathlib import Path

from PIL import Image, ImageOps

PAGE_SIZES_MM = {
    "a4": (210, 297),
    "a5": (148, 210),
    "caderno": (180, 230),
    "letter": (216, 279),
}


def mm_to_px(mm: float, dpi: int) -> int:
    return round(mm * dpi / 25.4)


def build_page_size(args):
    if args.page_size and args.page_size.lower() in PAGE_SIZES_MM:
        width_mm, height_mm = PAGE_SIZES_MM[args.page_size.lower()]
    else:
        width_mm = args.page_width_mm
        height_mm = args.page_height_mm

    if width_mm is None or height_mm is None:
        raise ValueError("Page size não definida corretamente.")

    return mm_to_px(width_mm, args.dpi), mm_to_px(height_mm, args.dpi)


def load_images(input_dir):
    files = (
        sorted(Path(input_dir).glob("*.jpg"))
        + sorted(Path(input_dir).glob("*.jpeg"))
        + sorted(Path(input_dir).glob("*.png"))
    )
    images = []
    for path in sorted(set(files)):
        try:
            image = Image.open(path)
            images.append((path.name, image.copy()))
            image.close()
        except Exception:
            continue
    return images


def create_pages(images, config):
    page_width, page_height = config["page_size"]
    margin = mm_to_px(config["margin_mm"], config["dpi"])
    spacing = mm_to_px(config["spacing_mm"], config["dpi"])

    columns = config["columns"]
    rows = config["rows"]

    available_width = page_width - margin * 2 - spacing * (columns - 1)
    available_height = page_height - margin * 2 - spacing * (rows - 1)

    cover_width_px = (
        mm_to_px(config["cover_width_mm"], config["dpi"])
        if config["cover_width_mm"]
        else None
    )
    cover_height_px = (
        mm_to_px(config["cover_height_mm"], config["dpi"])
        if config["cover_height_mm"]
        else None
    )

    cover_width = cover_width_px or (available_width // columns)
    cover_height = cover_height_px or (available_height // rows)

    # Garante que não ultrapasse o espaço disponível por coluna/linha
    cover_width = min(cover_width, available_width // columns)
    cover_height = min(cover_height, available_height // rows)

    cell_width = cover_width
    cell_height = cover_height

    page_images = []
    page = Image.new("RGB", (page_width, page_height), "white")
    x = margin
    y = margin
    placed = 0

    for name, image in images:
        thumb = ImageOps.exif_transpose(image)
        thumb = ImageOps.fit(
            thumb, (cell_width, cell_height), Image.Resampling.LANCZOS
        )
        page.paste(thumb, (x, y))

        placed += 1
        if placed % columns == 0:
            x = margin
            y += cell_height + spacing
        else:
            x += cell_width + spacing

        if placed == columns * rows:
            page_images.append(page)
            page = Image.new("RGB", (page_width, page_height), "white")
            x = margin
            y = margin
            placed = 0

    if placed != 0:
        page_images.append(page)

    return page_images


def save_pages(pages, output_path, output_format):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_format == "pdf":
        if not pages:
            raise ValueError("Nenhuma página gerada para salvar.")
        pages[0].save(
            output_path,
            "PDF",
            resolution=300,
            save_all=True,
            append_images=pages[1:],
        )
    else:
        for index, page in enumerate(pages, start=1):
            page.save(
                output_path.with_name(
                    f"{output_path.stem}_{index}{output_path.suffix}"
                ),
                format=output_format.upper(),
            )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Organiza capas em páginas prontas para impressão."
    )
    parser.add_argument(
        "--input-dir", default="capas", help="Pasta de imagens de capas."
    )
    parser.add_argument(
        "--output", default="print_pages.pdf", help="Arquivo de saída (PDF ou PNG)."
    )
    # 1. Ajuste a quantidade de figurinhas por folha Caderno (5x5 = 25 por página)
    parser.add_argument(
        "--columns", type=int, default=5, help="Número de colunas por página."
    )
    parser.add_argument(
        "--rows", type=int, default=5, help="Número de linhas por página."
    )
    parser.add_argument(
        "--page-size",
        default="caderno",
        choices=list(PAGE_SIZES_MM.keys()),
        help="Tamanho da página.",
    )
    parser.add_argument(
        "--page-width-mm",
        type=float,
        help="Largura da página em mm (usa page-size se omitido).",
    )
    parser.add_argument(
        "--page-height-mm",
        type=float,
        help="Altura da página em mm (usa page-size se omitido).",
    )
    parser.add_argument("--dpi", type=int, default=300, help="Resolução em DPI.")
    parser.add_argument(
        "--margin-mm", type=float, default=6.0, help="Margem externa em mm."
    )
    parser.add_argument(
        "--spacing-mm", type=float, default=6.0, help="Espaçamento entre capas em mm."
    )
    # Dimensões da capa já padronizadas em mm (3,5 cm x 5,0 cm)
    parser.add_argument(
        "--cover-width-mm",
        type=float,
        default=28.0,
        help="Largura da capa em mm (ex: 35 para 3,5 cm).",
    )
    parser.add_argument(
        "--cover-height-mm",
        type=float,
        default=42.0,
        help="Altura da capa em mm (ex: 50 para 5,0 cm).",
    )
    parser.add_argument(
        "--format",
        default="pdf",
        choices=["pdf", "png"],
        help="Formato de saída.",
    )
    
    return parser.parse_args()


def main():
    args = parse_args()
    images = load_images(args.input_dir)
    if not images:
        raise SystemExit(f"Nenhuma imagem encontrada em {args.input_dir}.")

    page_size = build_page_size(args)
    pages = create_pages(
        images,
        {
            "page_size": page_size,
            "margin_mm": args.margin_mm,
            "spacing_mm": args.spacing_mm,
            "columns": args.columns,
            "rows": args.rows,
            "cover_width_mm": args.cover_width_mm,
            "cover_height_mm": args.cover_height_mm,
            "dpi": args.dpi,
        },
    )

    save_pages(pages, args.output, args.format)
    print(f"Geradas {len(pages)} página(s) em {args.output}")


if __name__ == "__main__":
    main()