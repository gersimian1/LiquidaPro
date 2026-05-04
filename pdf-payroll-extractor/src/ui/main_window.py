"""
LiquidaPro — Ventana Principal v3
Rediseño: sidebar fija + tabla completa
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QLabel, QFileDialog, QMessageBox, QProgressBar,
    QRadioButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QAbstractItemView, QListWidgetItem, QButtonGroup,
    QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QFont
from pathlib import Path
from typing import List, Dict, Optional
import logging

from core.pdf_extractor import PDFExtractor, RawEmployeeBlock
from core.data_processor import DataProcessor, DISPLAY_NAMES
from core.excel_exporter import ExcelExporter

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  TEMA — Claro, profesional, herramienta financiera/contable
# ═══════════════════════════════════════════════════════════
class T:
    BG           = "#EEEEF8"
    BG_SIDEBAR   = "#E2E2EE"
    BG_HOVER     = "#D8D8EE"
    BG_ACTIVE    = "#CECEE8"
    BG_ALT       = "#E8E8F4"
    BG_HDR_ROW   = "#DCDCEC"

    BORDER       = "#C8C8DC"
    BORDER_MED   = "#AAAAC4"

    TEXT         = "#18182C"
    TEXT2        = "#46466A"
    TEXT_MUTED   = "#8A8AAA"
    TEXT_DIS     = "#BCBCD0"

    ACCENT       = "#5046E4"
    ACCENT_H     = "#3F35CC"
    ACCENT_P     = "#3028B4"
    ACCENT_LIGHT = "#DDDAFF"
    ACCENT_DARK  = "#2E28A0"

    OK           = "#15803D"
    OK_BG        = "#F0FDF4"
    OK_BRD       = "#86EFAC"
    WARN         = "#B45309"
    WARN_BG      = "#FFFBEB"
    WARN_BRD     = "#FCD34D"
    ERR          = "#DC2626"
    ERR_BG       = "#FEF2F2"
    ERR_BRD      = "#FCA5A5"
    INF          = "#0369A1"
    INF_BG       = "#F0F9FF"
    INF_BRD      = "#7DD3FC"

    F  = "'Segoe UI Variable', 'Segoe UI', -apple-system, 'Helvetica Neue', sans-serif"
    FM = "'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace"


# ═══════════════════════════════════════════════════════════
#  THREAD DE PROCESAMIENTO
# ═══════════════════════════════════════════════════════════
class ProcessThread(QThread):
    # emite {path: List[RawEmployeeBlock]} — un entry por archivo
    finished = Signal(object)
    error    = Signal(str)
    progress = Signal(int, str)

    def __init__(self, file_paths: List[str]):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        results: Dict[str, list] = {}
        total = len(self.file_paths)
        try:
            for idx, path in enumerate(self.file_paths):
                name = Path(path).name
                self.progress.emit(
                    int((idx / total) * 80),
                    f"Leyendo {name}  ({idx+1}/{total})..."
                )
                extractor = PDFExtractor()
                extractor.load_file(path)
                self.progress.emit(
                    int(((idx + 0.5) / total) * 80),
                    f"Extrayendo datos de {name}..."
                )
                blocks = extractor.extract_blocks()
                results[path] = blocks
            total_blocks = sum(len(b) for b in results.values())
            self.progress.emit(90, f"Extracción completa: {total_blocks} registros")
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════════
#  VENTANA PRINCIPAL
# ═══════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    """
    Layout v3:
    ┌──────────────┬─────────────────────────────────────┐
    │  SIDEBAR     │  TOOLBAR (⚡ PROCESAR / CSV / Excel) │
    │  ─────────   ├─────────────────────────────────────┤
    │  Archivos    │                                     │
    │  + botones   │         TABLA (ocupa todo)          │
    │  lista       │                                     │
    │  ─────────   │                                     │
    │  Columnas    │                                     │
    │  [toggle]    │                                     │
    │  [toggle]    │                                     │
    │  ...         │                                     │
    │  ─────────   ├─────────────────────────────────────┤
    │  Ordenar     │  STATUS BAR                         │
    └──────────────┴─────────────────────────────────────┘
    """

    # Definición canónica de columnas
    COLUMNS = [
        ('nombre',                    'Apellido y Nombre',            True,  None),
        ('rem_con_aporte',            'Rem c/ Aporte',                True,  'liquido'),
        ('liquido',                   'Líquido',                      True,  'rem_con_aporte'),
        ('retroactivos_sin_aporte',   'Retroactivos s/ Aportes',      False, None),
        ('retroactivos_con_aporte',   'Retroactivos c/ Aportes',      False, None),
        ('complemento_remunerativo',  'Complemento Remunerativo',     False, None),
        ('ajuste_apross',             'Ajuste APROSS',                False, None),
        ('descuento_apross_familiar', 'Desc. APROSS Fam.',            False, None),
        ('pct_jub_ley11087',          '% Jub. Ley 11.087',           False, None),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiquidaPro — Extractor de Recibos de Sueldo")
        self.setMinimumSize(1100, 680)

        self.file_paths:          List[str]             = []
        self.raw_blocks_per_file: Dict[str, list]      = {}  # path → blocks
        self.results_per_file:    Dict[str, List[Dict]] = {}  # path → consolidated
        self.current_path:        Optional[str]         = None
        self.is_processed = False
        self.col_checks:   Dict[str, QPushButton] = {}

        self.processor = DataProcessor()
        self.exporter  = ExcelExporter()

        self._build_ui()
        self._apply_global_style()

    # ══════════════════════════════════════════════════════
    #  BUILD
    # ══════════════════════════════════════════════════════
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)

        lay.addWidget(self._make_sidebar())
        lay.addWidget(self._make_main_area(), stretch=1)

    # ══════════════════════════════════════════════════════
    #  SIDEBAR
    # ══════════════════════════════════════════════════════
    def _make_sidebar(self) -> QWidget:
        sb = QWidget()
        sb.setFixedWidth(288)
        sb.setStyleSheet(f"""
            QWidget {{
                background: {T.BG_SIDEBAR};
                border-right: 1px solid {T.BORDER};
            }}
        """)
        lay = QVBoxLayout(sb)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)

        # Brand
        lay.addWidget(self._make_brand())

        # Contenido scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 4px; border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: #C4C4D8; border-radius: 2px; min-height: 24px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        inner = QWidget()
        inner.setStyleSheet("QWidget { background: transparent; border: none; }")
        il = QVBoxLayout(inner)
        il.setSpacing(0)
        il.setContentsMargins(0, 0, 0, 0)

        il.addWidget(self._section_label("ARCHIVOS"))
        il.addWidget(self._make_file_section())
        il.addWidget(self._hdivider())

        il.addWidget(self._section_label("COLUMNAS A EXPORTAR"))
        il.addWidget(self._make_column_toggles())
        il.addWidget(self._hdivider())

        il.addWidget(self._section_label("ORDENAR POR"))
        il.addWidget(self._make_sort_section())
        il.addStretch()

        scroll.setWidget(inner)
        lay.addWidget(scroll, stretch=1)
        return sb

    def _make_brand(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(60)
        w.setStyleSheet(f"background: {T.BG_SIDEBAR}; border-bottom: 1px solid {T.BORDER};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(20, 0, 20, 0)

        col = QVBoxLayout()
        col.setSpacing(1)
        t = QLabel("LiquidaPro")
        t.setStyleSheet(f"""
            color: {T.ACCENT};
            font: 700 17px {T.F};
            letter-spacing: -0.3px;
            background: transparent; border: none;
        """)
        s = QLabel("Extractor de recibos de sueldo")
        s.setStyleSheet(f"color: {T.TEXT_MUTED}; font: 11px {T.F}; background: transparent; border: none;")
        col.addWidget(t)
        col.addWidget(s)
        lay.addLayout(col)
        lay.addStretch()
        return w

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            color: {T.TEXT_MUTED};
            font: 700 10px {T.F};
            letter-spacing: 0.9px;
            padding: 14px 20px 6px 20px;
            background: transparent; border: none;
        """)
        return lbl

    def _make_file_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setSpacing(6)
        lay.setContentsMargins(16, 4, 16, 14)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_load = self._ghost_btn("+ Archivo")
        self.btn_load.clicked.connect(self._on_load_single)
        row.addWidget(self.btn_load)

        self.btn_load_multi = self._ghost_btn("+ Múltiples")
        self.btn_load_multi.clicked.connect(self._on_load_multiple)
        row.addWidget(self.btn_load_multi)

        self.btn_clear = self._ghost_btn_danger("Limpiar")
        self.btn_clear.clicked.connect(self._on_clear)
        row.addWidget(self.btn_clear)
        lay.addLayout(row)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(108)
        self.file_list.setStyleSheet(f"""
            QListWidget {{
                background: {T.BG};
                border: 1px solid {T.BORDER};
                border-radius: 7px;
                font: 11px {T.FM};
                color: {T.TEXT2};
                padding: 2px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 5px 8px;
                border-radius: 4px;
                color: {T.TEXT2};
            }}
            QListWidget::item:selected {{
                background: {T.ACCENT_LIGHT};
                color: {T.ACCENT};
            }}
            QListWidget::item:hover {{ background: {T.BG_HOVER}; }}
        """)
        self._show_file_placeholder()
        self.file_list.currentRowChanged.connect(self._on_file_row_changed)
        lay.addWidget(self.file_list)
        return w

    def _show_file_placeholder(self):
        item = QListWidgetItem("  Sin archivos cargados")
        item.setForeground(QColor(T.TEXT_DIS))
        self.file_list.addItem(item)

    def _make_column_toggles(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setSpacing(3)
        lay.setContentsMargins(16, 4, 16, 14)

        for key, label, default, linked in self.COLUMNS:
            btn = QPushButton(f"  {label}")
            btn.setCheckable(True)
            btn.setChecked(default)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.setStyleSheet(self._col_toggle_style())

            if key == 'nombre':
                btn.setEnabled(False)

            if linked:
                btn.toggled.connect(
                    lambda checked, lk=linked: (
                        self.col_checks[lk].setChecked(checked)
                        if lk in self.col_checks else None
                    )
                )

            btn.toggled.connect(lambda _: self._on_column_changed())
            self.col_checks[key] = btn
            lay.addWidget(btn)

        return w

    def _make_sort_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setSpacing(2)
        lay.setContentsMargins(16, 4, 16, 14)

        self.radio_alpha    = QRadioButton("  Alfabético  (A → Z)")
        self.radio_original = QRadioButton("  Orden original del PDF")
        self.radio_alpha.setChecked(True)

        self._sort_group = QButtonGroup(self)
        self._sort_group.addButton(self.radio_alpha, 0)
        self._sort_group.addButton(self.radio_original, 1)
        self._sort_group.buttonClicked.connect(self._on_sort_changed)

        rs = self._radio_style()
        for r in [self.radio_alpha, self.radio_original]:
            r.setStyleSheet(rs)
            lay.addWidget(r)
        return w

    # ══════════════════════════════════════════════════════
    #  MAIN AREA
    # ══════════════════════════════════════════════════════
    def _make_main_area(self) -> QWidget:
        area = QWidget()
        area.setStyleSheet(f"background: {T.BG};")
        lay = QVBoxLayout(area)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)

        lay.addWidget(self._make_toolbar())

        # Barra de progreso (3px, pegada al toolbar)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background: {T.BORDER}; border: none; }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {T.ACCENT}, stop:1 #06B6D4);
            }}
        """)
        lay.addWidget(self.progress)

        lay.addWidget(self._make_table(), stretch=1)
        lay.addWidget(self._make_status_strip())
        return area

    def _make_toolbar(self) -> QWidget:
        tb = QWidget()
        tb.setFixedHeight(60)
        tb.setStyleSheet(f"""
            QWidget {{
                background: {T.BG};
                border-bottom: 1px solid {T.BORDER};
            }}
        """)
        lay = QHBoxLayout(tb)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(10)

        self.badge = QLabel("")
        self._set_badge("neutral", "Sin archivos cargados")
        lay.addWidget(self.badge)
        lay.addStretch()

        self.lbl_progress_msg = QLabel("")
        self.lbl_progress_msg.setStyleSheet(f"color: {T.TEXT_MUTED}; font: 12px {T.F}; background: transparent; border: none;")
        lay.addWidget(self.lbl_progress_msg)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(22)
        sep.setStyleSheet(f"background: {T.BORDER}; border: none;")
        lay.addWidget(sep)

        self.btn_process = QPushButton("⚡  PROCESAR")
        self.btn_process.setCursor(Qt.PointingHandCursor)
        self.btn_process.setFixedHeight(38)
        self.btn_process.setMinimumWidth(138)
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self._on_process)
        self.btn_process.setStyleSheet(f"""
            QPushButton {{
                background: {T.ACCENT};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 20px;
                font: 700 13px {T.F};
                letter-spacing: 0.2px;
            }}
            QPushButton:hover   {{ background: {T.ACCENT_H}; }}
            QPushButton:pressed {{ background: {T.ACCENT_P}; }}
            QPushButton:disabled {{
                background: {T.BG_ACTIVE};
                color: {T.TEXT_DIS};
            }}
        """)
        lay.addWidget(self.btn_process)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(22)
        sep2.setStyleSheet(f"background: {T.BORDER}; border: none;")
        lay.addWidget(sep2)

        self.btn_csv = self._outline_btn("CSV")
        self.btn_csv.clicked.connect(self._on_export_csv)
        self.btn_csv.setEnabled(False)
        lay.addWidget(self.btn_csv)

        self.btn_excel = self._solid_btn("Excel  .xlsx")
        self.btn_excel.clicked.connect(self._on_export_excel)
        self.btn_excel.setEnabled(False)
        lay.addWidget(self.btn_excel)

        self.btn_export_all = self._outline_btn("Exportar Todos")
        self.btn_export_all.setToolTip("Exporta cada archivo como un .xlsx separado en una carpeta")
        self.btn_export_all.clicked.connect(self._on_export_all)
        self.btn_export_all.setEnabled(False)
        lay.addWidget(self.btn_export_all)

        return tb

    def _make_table(self) -> QWidget:
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {T.BG};
                color: {T.TEXT};
                border: none;
                font: 13px {T.F};
                selection-background-color: {T.ACCENT_LIGHT};
                selection-color: {T.TEXT};
                outline: none;
                gridline-color: transparent;
            }}
            QTableWidget::item {{
                padding: 10px 16px;
                border-bottom: 1px solid {T.BORDER};
            }}
            QTableWidget::item:alternate {{ background: {T.BG_ALT}; }}
            QTableWidget::item:selected  {{ background: {T.ACCENT_LIGHT}; }}
            QHeaderView::section {{
                background: {T.BG_HDR_ROW};
                color: {T.TEXT2};
                font: 600 11px {T.F};
                letter-spacing: 0.4px;
                padding: 10px 16px;
                border: none;
                border-bottom: 2px solid {T.BORDER};
                border-right: 1px solid {T.BORDER};
            }}
            QHeaderView::section:last-child {{ border-right: none; }}
            QScrollBar:vertical {{
                background: {T.BG_SIDEBAR}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {T.BORDER_MED}; border-radius: 4px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {T.TEXT_MUTED}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar:horizontal {{
                background: {T.BG_SIDEBAR}; height: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {T.BORDER_MED}; border-radius: 4px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        """)
        self._reset_table_placeholder()
        return self.table

    def _make_status_strip(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(34)
        bar.setStyleSheet(f"""
            QWidget {{ background: {T.BG_SIDEBAR}; border-top: 1px solid {T.BORDER}; }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(16)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {T.TEXT_MUTED}; font: 11px {T.F}; background: transparent; border: none;")
        lay.addWidget(self.lbl_status)
        lay.addStretch()

        self.lbl_records = QLabel("")
        self.lbl_records.setStyleSheet(f"color: {T.TEXT_MUTED}; font: 11px {T.F}; background: transparent; border: none;")
        lay.addWidget(self.lbl_records)
        return bar

    # ══════════════════════════════════════════════════════
    #  ACCIONES
    # ══════════════════════════════════════════════════════
    def _on_load_single(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo", "",
            "Archivos de liquidación (*.pdf *.txt);;Todos (*)"
        )
        if path:
            self._add_files([path])

    def _on_load_multiple(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar archivos", "",
            "Archivos de liquidación (*.pdf *.txt);;Todos (*)"
        )
        if paths:
            self._add_files(paths)

    def _add_files(self, paths: List[str]):
        self.file_paths = paths
        self.is_processed = False
        self.results_per_file = {}
        self.raw_blocks_per_file = {}
        self.current_path = None

        self.file_list.clear()
        for p in paths:
            self.file_list.addItem(QListWidgetItem(f"  {Path(p).name}"))

        n = len(paths)
        self._set_badge("info", f"{n} archivo{'s' if n != 1 else ''} cargado{'s' if n != 1 else ''}")
        self.btn_process.setEnabled(True)
        self.btn_excel.setEnabled(False)
        self.btn_csv.setEnabled(False)
        self.btn_export_all.setEnabled(False)
        self._reset_table_placeholder()
        self.lbl_records.setText("")
        self.lbl_status.setText("")
        self.lbl_progress_msg.setText("")

    def _on_process(self):
        if not self.file_paths:
            return

        self.btn_process.setEnabled(False)
        self.btn_load.setEnabled(False)
        self.btn_load_multi.setEnabled(False)
        self.btn_excel.setEnabled(False)
        self.btn_csv.setEnabled(False)
        self.btn_export_all.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._set_badge("warn", "Procesando...")
        self.lbl_status.setText("Extrayendo datos...")

        self._thread = ProcessThread(self.file_paths)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished.connect(self._on_finished)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_progress(self, value: int, msg: str):
        self.progress.setValue(value)
        self.lbl_progress_msg.setText(msg)

    def _on_finished(self, results: dict):
        sort_alpha = self.radio_alpha.isChecked()
        self.raw_blocks_per_file = results
        self.results_per_file = {
            path: self.processor.consolidate(blocks, sort_alpha)
            for path, blocks in results.items()
        }
        self.is_processed = True

        n_files   = len(results)
        n_blocks  = sum(len(b) for b in results.values())
        n_emp_total = sum(len(v) for v in self.results_per_file.values())

        self.progress.setValue(100)
        self._set_badge("ok", f"✓  {n_files} archivo{'s' if n_files != 1 else ''} · {n_emp_total} empleados · {n_blocks} registros")
        self.lbl_progress_msg.setText("")
        self.lbl_status.setText(f"Listo — seleccioná un archivo en la lista para ver sus datos")
        self.lbl_status.setStyleSheet(f"color: {T.OK}; font: 11px {T.F}; background: transparent; border: none;")

        self.btn_process.setEnabled(True)
        self.btn_load.setEnabled(True)
        self.btn_load_multi.setEnabled(True)
        self.btn_excel.setEnabled(True)
        self.btn_csv.setEnabled(True)
        self.btn_export_all.setEnabled(n_files > 1)

        # Seleccionar el primer archivo automáticamente
        if self.file_paths:
            self.file_list.setCurrentRow(0)

        QTimer.singleShot(2200, lambda: self.progress.setVisible(False))

    def _on_error(self, msg: str):
        self.progress.setVisible(False)
        self._set_badge("err", "Error al procesar")
        self.lbl_progress_msg.setText("")
        self.lbl_status.setText(f"Error: {msg}")
        self.lbl_status.setStyleSheet(f"color: {T.ERR}; font: 11px {T.F}; background: transparent; border: none;")

        self.btn_process.setEnabled(True)
        self.btn_load.setEnabled(True)
        self.btn_load_multi.setEnabled(True)
        QMessageBox.critical(self, "Error al procesar", msg)

    def _on_column_changed(self):
        if self.is_processed:
            self._fill_table()

    def _on_file_row_changed(self, row: int):
        """Cambiar archivo seleccionado en la lista → actualizar tabla."""
        if not self.is_processed or row < 0 or row >= len(self.file_paths):
            return
        self.current_path = self.file_paths[row]
        name = Path(self.current_path).name
        consolidated = self.results_per_file.get(self.current_path, [])
        n = len(consolidated)
        self._set_badge("ok", f"✓  {name}  —  {n} empleados")
        self.lbl_records.setText(f"{n} empleados")
        self.lbl_status.setText(f"{self.current_path}")
        self._fill_table()

    def _on_sort_changed(self):
        if not self.is_processed or not self.raw_blocks_per_file:
            return
        sort_alpha = self.radio_alpha.isChecked()
        # Re-consolidar todos los archivos con el nuevo orden
        self.results_per_file = {
            path: self.processor.consolidate(blocks, sort_alpha)
            for path, blocks in self.raw_blocks_per_file.items()
        }
        self._fill_table()

    def _on_clear(self):
        self.file_paths           = []
        self.raw_blocks_per_file  = {}
        self.results_per_file     = {}
        self.current_path         = None
        self.is_processed         = False

        self.file_list.clear()
        self._show_file_placeholder()
        self._reset_table_placeholder()
        self.lbl_records.setText("")
        self.lbl_status.setText("")
        self.lbl_status.setStyleSheet(f"color: {T.TEXT_MUTED}; font: 11px {T.F}; background: transparent; border: none;")
        self.lbl_progress_msg.setText("")
        self._set_badge("neutral", "Sin archivos cargados")
        self.btn_process.setEnabled(False)
        self.btn_excel.setEnabled(False)
        self.btn_csv.setEnabled(False)
        self.btn_export_all.setEnabled(False)

    # ══════════════════════════════════════════════════════
    #  TABLA
    # ══════════════════════════════════════════════════════
    def _reset_table_placeholder(self):
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels([""])
        self.table.setRowCount(1)
        ph = QTableWidgetItem("Cargá un archivo y presioná  ⚡ PROCESAR  para ver los datos aquí")
        ph.setForeground(QColor(T.TEXT_MUTED))
        ph.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(0, 0, ph)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

    def _fill_table(self):
        consolidated = self.results_per_file.get(self.current_path, []) if self.current_path else []
        if not consolidated:
            return

        keys         = self._get_selected_keys()
        display_cols = [DISPLAY_NAMES.get(k, k) for k in keys]

        self.table.setColumnCount(len(display_cols))
        self.table.setHorizontalHeaderLabels(display_cols)
        self.table.setRowCount(len(consolidated))

        mono = QFont()
        mono.setFamilies(["Cascadia Code", "JetBrains Mono", "Consolas"])
        mono.setPointSize(11)

        for ri, rec in enumerate(consolidated):
            for ci, key in enumerate(keys):
                val = rec.get(key, 0.0)

                if key == 'nombre':
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    item.setForeground(QColor(T.TEXT))
                elif key == 'pct_jub_ley11087':
                    text = f"{int(round(val))} %" if isinstance(val, (int, float)) and val > 0 else "—"
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    item.setForeground(QColor(T.WARN))
                    item.setFont(mono)
                else:
                    if isinstance(val, (int, float)) and val > 0:
                        fmt = f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                        item = QTableWidgetItem(f"$ {fmt}")
                    else:
                        item = QTableWidgetItem("—")
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    item.setForeground(QColor(T.ACCENT_DARK))
                    item.setFont(mono)

                self.table.setItem(ri, ci, item)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(keys)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.lbl_records.setText(f"{len(consolidated)} empleados")

    def _get_selected_keys(self) -> List[str]:
        order = [k for k, *_ in self.COLUMNS]
        return [k for k in order if self.col_checks.get(k) and self.col_checks[k].isChecked()]

    # ══════════════════════════════════════════════════════
    #  EXPORTACIÓN
    # ══════════════════════════════════════════════════════
    def _current_consolidated(self) -> List[Dict]:
        return self.results_per_file.get(self.current_path, []) if self.current_path else []

    def _on_export_excel(self):
        if not self.is_processed or not self.current_path:
            return
        stem = Path(self.current_path).stem
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Excel", f"{stem}.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            keys   = self._get_selected_keys()
            df     = self.processor.to_dataframe(self._current_consolidated(), keys)
            totals = self.processor.calculate_totals(df)
            self.exporter.export_to_excel(df, path, totals, title=stem)
            self._set_badge("ok", f"✓  Exportado: {Path(path).name}")
            self.lbl_status.setText(f"Excel guardado — {path}")
        except Exception as e:
            logger.error(f"Error Excel: {e}")
            QMessageBox.critical(self, "Error al exportar", str(e))

    def _on_export_csv(self):
        if not self.is_processed or not self.current_path:
            return
        stem = Path(self.current_path).stem
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar CSV", f"{stem}.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            keys = self._get_selected_keys()
            df   = self.processor.to_dataframe(self._current_consolidated(), keys)
            self.exporter.export_to_csv(df, path)
            self._set_badge("ok", f"✓  Exportado: {Path(path).name}")
            self.lbl_status.setText(f"CSV guardado — {path}")
        except Exception as e:
            logger.error(f"Error CSV: {e}")
            QMessageBox.critical(self, "Error al exportar", str(e))

    def _on_export_all(self):
        """Exporta cada archivo como un .xlsx separado en una carpeta elegida."""
        if not self.is_processed or not self.results_per_file:
            return
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta de destino")
        if not folder:
            return

        keys = self._get_selected_keys()
        errors = []
        exported = 0

        for src_path, consolidated in self.results_per_file.items():
            stem = Path(src_path).stem
            dest = str(Path(folder) / f"{stem}.xlsx")
            try:
                df     = self.processor.to_dataframe(consolidated, keys)
                totals = self.processor.calculate_totals(df)
                self.exporter.export_to_excel(df, dest, totals, title=stem)
                exported += 1
            except Exception as e:
                errors.append(f"{stem}: {e}")

        if errors:
            QMessageBox.warning(
                self, "Exportación parcial",
                f"Se exportaron {exported} de {len(self.results_per_file)} archivos.\n\nErrores:\n" + "\n".join(errors)
            )
        else:
            self._set_badge("ok", f"✓  {exported} archivos exportados")
            self.lbl_status.setText(f"Todos los archivos exportados en {folder}")
            QMessageBox.information(
                self, "Exportación completa",
                f"Se exportaron {exported} archivo(s) en:\n{folder}"
            )

    # ══════════════════════════════════════════════════════
    #  BADGE
    # ══════════════════════════════════════════════════════
    def _set_badge(self, level: str, text: str):
        palettes = {
            "neutral": (T.TEXT_MUTED, T.BG_ACTIVE,  T.BORDER),
            "info":    (T.INF,        T.INF_BG,      T.INF_BRD),
            "ok":      (T.OK,         T.OK_BG,       T.OK_BRD),
            "warn":    (T.WARN,       T.WARN_BG,     T.WARN_BRD),
            "err":     (T.ERR,        T.ERR_BG,      T.ERR_BRD),
        }
        fg, bg, brd = palettes.get(level, palettes["neutral"])
        self.badge.setText(f"  {text}  ")
        self.badge.setStyleSheet(f"""
            color: {fg};
            background: {bg};
            border: 1px solid {brd};
            border-radius: 6px;
            font: 600 12px {T.F};
            padding: 3px 8px;
        """)

    # ══════════════════════════════════════════════════════
    #  ESTILOS DE WIDGETS
    # ══════════════════════════════════════════════════════
    def _col_toggle_style(self) -> str:
        return f"""
            QPushButton {{
                background: {T.BG};
                color: {T.TEXT2};
                border: 1.5px solid {T.BORDER};
                border-radius: 7px;
                padding: 0px 12px;
                font: 13px {T.F};
                text-align: left;
            }}
            QPushButton:checked {{
                background: {T.ACCENT_LIGHT};
                color: {T.ACCENT};
                border-color: {T.ACCENT};
                font-weight: 700;
            }}
            QPushButton:hover:!checked {{
                background: {T.BG_HOVER};
                border-color: {T.BORDER_MED};
            }}
            QPushButton:disabled {{
                background: {T.ACCENT_LIGHT};
                color: {T.ACCENT};
                border-color: {T.ACCENT};
                font-weight: 700;
            }}
        """

    def _radio_style(self) -> str:
        return f"""
            QRadioButton {{
                color: {T.TEXT2};
                font: 13px {T.F};
                padding: 5px 2px;
                spacing: 8px;
                background: transparent;
                border: none;
            }}
            QRadioButton::indicator {{
                width: 15px; height: 15px;
                border: 2px solid {T.BORDER_MED};
                border-radius: 8px;
                background: {T.BG};
            }}
            QRadioButton::indicator:checked {{
                background: {T.ACCENT};
                border-color: {T.ACCENT};
            }}
            QRadioButton::indicator:hover {{ border-color: {T.ACCENT}; }}
        """

    def _ghost_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(28)
        b.setStyleSheet(f"""
            QPushButton {{
                background: {T.BG};
                color: {T.TEXT2};
                border: 1px solid {T.BORDER};
                border-radius: 6px;
                padding: 0 10px;
                font: 600 12px {T.F};
            }}
            QPushButton:hover  {{ background: {T.BG_HOVER}; border-color: {T.BORDER_MED}; }}
            QPushButton:pressed {{ background: {T.BG_ACTIVE}; }}
            QPushButton:disabled {{ color: {T.TEXT_DIS}; }}
        """)
        return b

    def _ghost_btn_danger(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(28)
        b.setStyleSheet(f"""
            QPushButton {{
                background: {T.BG};
                color: {T.TEXT_MUTED};
                border: 1px solid {T.BORDER};
                border-radius: 6px;
                padding: 0 10px;
                font: 600 12px {T.F};
            }}
            QPushButton:hover  {{ background: {T.ERR_BG}; color: {T.ERR}; border-color: {T.ERR}; }}
            QPushButton:pressed {{ background: #FFE4E4; }}
        """)
        return b

    def _outline_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(36)
        b.setStyleSheet(f"""
            QPushButton {{
                background: {T.BG};
                color: {T.TEXT2};
                border: 1.5px solid {T.BORDER_MED};
                border-radius: 7px;
                padding: 0 14px;
                font: 600 13px {T.F};
            }}
            QPushButton:hover  {{ background: {T.BG_HOVER}; border-color: {T.TEXT_MUTED}; }}
            QPushButton:pressed {{ background: {T.BG_ACTIVE}; }}
            QPushButton:disabled {{ color: {T.TEXT_DIS}; border-color: {T.BORDER}; }}
        """)
        return b

    def _solid_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(36)
        b.setStyleSheet(f"""
            QPushButton {{
                background: {T.TEXT};
                color: white;
                border: none;
                border-radius: 7px;
                padding: 0 16px;
                font: 600 13px {T.F};
            }}
            QPushButton:hover  {{ background: {T.TEXT2}; }}
            QPushButton:pressed {{ background: #0A0A1A; }}
            QPushButton:disabled {{ background: {T.BG_ACTIVE}; color: {T.TEXT_DIS}; }}
        """)
        return b

    # ══════════════════════════════════════════════════════
    #  SEPARADOR
    # ══════════════════════════════════════════════════════
    def _hdivider(self) -> QFrame:
        f = QFrame()
        f.setFixedHeight(1)
        f.setStyleSheet(f"background: {T.BORDER}; border: none;")
        return f

    # ══════════════════════════════════════════════════════
    #  ESTILOS GLOBALES
    # ══════════════════════════════════════════════════════
    def _apply_global_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background: {T.BG}; }}
            QWidget      {{ background: {T.BG}; color: {T.TEXT}; }}
            QToolTip {{
                background: {T.TEXT};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 9px;
                font: 12px {T.F};
            }}
            QMessageBox {{ background: {T.BG}; }}
            QMessageBox QLabel {{ color: {T.TEXT}; font: 13px {T.F}; }}
            QMessageBox QPushButton {{
                background: {T.ACCENT};
                color: white;
                border: none;
                padding: 6px 22px;
                border-radius: 6px;
                font: 600 13px {T.F};
                min-width: 70px;
            }}
            QMessageBox QPushButton:hover {{ background: {T.ACCENT_H}; }}
        """)
