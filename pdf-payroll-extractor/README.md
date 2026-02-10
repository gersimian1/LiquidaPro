# LiquidaPro

**Extractor de recibos de sueldo — PDF a Excel en 3 clicks**

Aplicación de escritorio que lee archivos de liquidación de haberes del sistema provincial de Córdoba, extrae los datos de cada empleado, consolida cargos duplicados y exporta a Excel/CSV con formato profesional.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/UI-PySide6-41cd52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey)

---

## Qué hace

| Entrada | Proceso | Salida |
|---------|---------|--------|
| PDF de liquidación (real o texto plano) | Extracción con regex + consolidación por empleado | Excel (.xlsx) con formato y totales / CSV |

- **Detecta automáticamente** si el archivo es un PDF real o texto plano con extensión `.pdf`
- **Extrae** por empleado: Nombre, Rem c/ Aporte, Líquido, Complemento Remunerativo, Ajuste APROSS, Desc. APROSS Familiares
- **Consolida** empleados con múltiples cargos/roles (suma automática)
- **Exporta** a Excel con encabezados, formato numérico, fila de totales y columnas autoajustadas

## Captura

<img width="1918" height="1035" alt="Captura de pantalla 2026-02-10 191404" src="https://github.com/user-attachments/assets/bfcc2467-6319-4499-b5b8-b7a613d37a5f" />

## Arquitectura

```
src/
├── main.py                  # Entry point
├── core/
│   ├── pdf_extractor.py     # Capa de extracción (regex sobre texto)
│   ├── data_processor.py    # Capa de negocio (consolidación, DataFrame)
│   └── excel_exporter.py    # Capa de exportación (xlsx/csv con formato)
└── ui/
    └── main_window.py       # Interfaz gráfica PySide6

tests/
└── test_extractor.py        # Test del pipeline completo
```

**Separación de responsabilidades clara:**

| Capa | Archivo | Responsabilidad |
|------|---------|-----------------|
| **Extracción** | `pdf_extractor.py` | Leer PDF/texto → parsear con regex → `RawEmployeeBlock` |
| **Negocio** | `data_processor.py` | Consolidar por nombre → filtrar columnas → `DataFrame` |
| **Exportación** | `excel_exporter.py` | DataFrame → Excel formateado / CSV |
| **UI** | `main_window.py` | Interfaz, flujo de usuario, threading |

## Decisiones técnicas

| Decisión | Justificación |
|----------|---------------|
| **PySide6** sobre Tkinter | UI moderna, soporte nativo de temas, mejor para portfolio |
| **pdfplumber** + fallback **pymupdf** | pdfplumber es más preciso en tablas, pymupdf como respaldo |
| **Detección por magic bytes** (`%PDF-`) | El sistema provincial genera archivos de texto con extensión `.pdf` — no se puede confiar en la extensión |
| **Regex compilados** | Performance: 325 registros parseados en <100ms |
| **QThread** para extracción | No bloquear la UI durante el procesamiento |
| **`defaultdict`** para consolidación | Suma automática de cargos múltiples sin pre-alocación |

## Instalación

### Requisitos
- Python 3.10+

### Pasos

```bash
# 1. Clonar
git clone https://github.com/GermanSimian/liquidapro.git
cd liquidapro

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar
python run.py
```

**Windows:** doble click en `run.bat`

## Uso

1. **Cargar** → Seleccioná uno o varios archivos `.pdf`
2. **Configurar** → Elegí columnas y orden (alfabético u original)
3. **Procesar** → Click en ⚡ PROCESAR
4. **Exportar** → Excel (.xlsx) o CSV

## Verificación con datos reales

```
Registros extraídos:    325
Empleados únicos:        79
Total Líquido:    $69.621.514,43 ✓ (coincide con total del archivo fuente)
```

## Mejoras futuras

- [ ] OCR para PDFs escaneados (Tesseract)
- [ ] Selección de conceptos individuales (DV/RT)
- [ ] Comparación entre liquidaciones de distintos meses
- [ ] Búsqueda/filtro en la tabla de resultados
- [ ] Gráficos de distribución salarial
- [ ] Empaquetado como `.exe` con PyInstaller

## Licencia

CC BY-NC 4.0 — ver [LICENSE](LICENSE)

Este proyecto no puede ser utilizado con fines comerciales.
