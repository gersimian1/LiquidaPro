"""
Tests para el extractor de liquidaciones.
Ejecutar: python -m pytest tests/ -v
"""
import sys
from pathlib import Path

# Setup path
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

from core.pdf_extractor import PDFExtractor
from core.data_processor import DataProcessor
from core.excel_exporter import ExcelExporter


def test_full_pipeline(pdf_path: str):
    """Test completo del pipeline de extracción."""
    print(f"\n{'='*60}")
    print(f"  TEST: Pipeline completo")
    print(f"  Archivo: {Path(pdf_path).name}")
    print(f"{'='*60}\n")
    
    # 1. Cargar archivo
    extractor = PDFExtractor()
    text = extractor.load_file(pdf_path)
    assert len(text) > 0, "No se extrajo texto"
    print(f"✓ Archivo cargado: {len(text):,} caracteres")
    
    # 2. Extraer bloques
    blocks = extractor.extract_blocks()
    assert len(blocks) > 0, "No se encontraron bloques"
    print(f"✓ Bloques extraídos: {len(blocks)}")
    
    # 3. Consolidar
    processor = DataProcessor()
    consolidated = processor.consolidate(blocks, sort_alpha=True)
    assert len(consolidated) > 0, "No se consolidaron datos"
    print(f"✓ Empleados únicos: {len(consolidated)}")
    
    # 4. DataFrame
    keys = ['nombre', 'rem_con_aporte', 'liquido']
    df = processor.to_dataframe(consolidated, keys)
    totals = processor.calculate_totals(df)
    print(f"✓ DataFrame: {df.shape}")
    print(f"  Totales: {totals}")
    
    # 5. Exportar
    exporter = ExcelExporter()
    out_xlsx = Path("/tmp/test_liquidapro.xlsx")
    out_csv = Path("/tmp/test_liquidapro.csv")
    
    exporter.export_to_excel(df, str(out_xlsx), totals)
    exporter.export_to_csv(df, str(out_csv))
    
    assert out_xlsx.exists(), "Excel no generado"
    assert out_csv.exists(), "CSV no generado"
    print(f"✓ Excel: {out_xlsx}")
    print(f"✓ CSV: {out_csv}")
    
    print(f"\n{'='*60}")
    print(f"  ✅ TODOS LOS TESTS PASARON")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python test_extractor.py <ruta_al_pdf>")
        print("Ejemplo: python test_extractor.py ../datos/liquidacion.pdf")
        sys.exit(1)
    
    test_full_pipeline(sys.argv[1])
