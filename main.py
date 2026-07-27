import sys
import download_covers
import generate_print_pages

def run_pipeline():
    print("=" * 50)
    print(" [1/2] BAIXANDO E VERIFICANDO CAPAS DE LIVROS ")
    print("=" * 50)
    
    # 1. Executa a busca/download das capas
    sys.argv = ["download_covers.py", "livros.csv", "--output-dir", "capas"]
    try:
        download_covers.main()
    except Exception as e:
        print(f"\n❌ Erro durante o download das capas: {e}")
        return

    print("\n" + "=" * 50)
    print(" [2/2] GERANDO PÁGINAS PARA IMPRESSÃO (PDF) ")
    print("=" * 50)

    # 2. Executa a montagem do PDF
    sys.argv = [
        "generate_print_pages.py",
        "--input-dir", "capas",
        "--output", "print_pages.pdf"
    ]
    try:
        generate_print_pages.main()
    except Exception as e:
        print(f"\n❌ Erro durante a geração do PDF: {e}")
        return

    print("\n🎉 Processo concluído com sucesso! O arquivo 'print_pages.pdf' está pronto.")

if __name__ == "__main__":
    run_pipeline()