"""
══════════════════════════════════════════════════════════════
  LiquidaPro — Ventana Principal v2
  
  Flujo correcto:
  1. Cargar archivo(s) → aparecen en lista + preview de texto
  2. Configurar columnas y orden
  3. Presionar PROCESAR → extrae, consolida, muestra en tabla
  4. Exportar a Excel / CSV
══════════════════════════════════════════════════════════════
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QLabel, QCheckBox, QFileDialog,
    QMessageBox, QProgressBar, QSplitter, QRadioButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QScrollArea, QAbstractItemView, QListWidgetItem,
    QTextEdit, QSizePolicy, QButtonGroup
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont
from pathlib import Path
from typing import List, Dict, Optional
import logging

from core.pdf_extractor import PDFExtractor, RawEmployeeBlock
from core.data_processor import DataProcessor, DISPLAY_NAMES
from core.excel_exporter import ExcelExporter

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  TEMA
# ═══════════════════════════════════════════════════════════
class T:
    """Paleta de colores y fuentes. Cambiar aquí afecta todo."""
    
    BG0 = "#0f0f1a"      # Más oscuro (header/footer)
    BG1 = "#1a1a2e"      # Fondo principal
    BG2 = "#222240"      # Tarjetas
    BG3 = "#2a2a4a"      # Inputs / elevated
    BGH = "#333360"      # Hover
    BGA = "#1e1e38"      # Filas alternadas
    
    FG  = "#f0f0f5"      # Texto principal (ratio 12:1)
    FG2 = "#b8b8d0"      # Texto secundario (7:1)
    FGM = "#8888aa"      # Muted (4.5:1 AA)
    FGD = "#505070"      # Disabled
    
    ACC = "#00d4aa"      # Accent
    ACH = "#00e8bc"      # Accent hover
    ACP = "#00b090"      # Accent pressed
    
    WARN = "#ffb347"
    ERR  = "#ff6b6b"
    OK   = "#51cf66"
    INF  = "#74c0fc"
    
    BRD  = "#3a3a5c"     # Bordes
    
    F  = "'Segoe UI', 'SF Pro Display', 'Helvetica Neue', sans-serif"
    FM = "'Cascadia Code', 'Fira Code', 'Consolas', monospace"


# ═══════════════════════════════════════════════════════════
#  THREAD DE PROCESAMIENTO
# ═══════════════════════════════════════════════════════════
class ProcessThread(QThread):
    """
    Thread que ejecuta: cargar archivos → extraer bloques.
    La consolidación se hace después en el main thread (es rápida).
    """
    finished = Signal(list)          # Lista de RawEmployeeBlock
    error = Signal(str)
    progress = Signal(int, str)      # (porcentaje, mensaje)
    
    def __init__(self, file_paths: List[str]):
        super().__init__()
        self.file_paths = file_paths
    
    def run(self):
        all_blocks = []
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
                all_blocks.extend(blocks)
            
            self.progress.emit(90, f"Extracción completa: {len(all_blocks)} registros")
            self.finished.emit(all_blocks)
            
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════════
#  VENTANA PRINCIPAL
# ═══════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    """
    Flujo:
    ┌─ PASO 1: Cargar ─────────────────────────────┐
    │  [Cargar PDF]  [Cargar Múltiples]  [Limpiar]  │
    │  Lista de archivos cargados                   │
    ├─ PASO 2: Configurar ──────┬─ Preview ────────┤
    │  ◉ Orden alfabético       │  Vista previa    │
    │  ☑ Rem c/ Aporte          │  del texto del   │
    │  ☑ Líquido                │  archivo         │
    │  ☐ Complemento            │                  │
    │                           │                  │
    │  [████ PROCESAR ████]     │                  │
    ├───────────────────────────┴──────────────────┤
    │  PASO 3: Tabla de resultados                  │
    ├──────────────────────────────────────────────┤
    │  PASO 4:  [Exportar CSV]  [Exportar Excel]   │
    └──────────────────────────────────────────────┘
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiquidaPro — Extractor de Recibos de Sueldo")
        self.setMinimumSize(1280, 860)
        
        # ── Estado ──
        self.file_paths: List[str] = []
        self.raw_blocks: List[RawEmployeeBlock] = []
        self.consolidated: List[Dict] = []
        self.is_processed = False
        
        # ── Core ──
        self.processor = DataProcessor()
        self.exporter = ExcelExporter()
        
        self._build_ui()
        self._apply_styles()
    
    # ═══════════════════════════════════════════════
    #  CONSTRUCCIÓN DE UI
    # ═══════════════════════════════════════════════
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)
        
        # Header
        root.addWidget(self._make_header())
        
        # Contenido
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setSpacing(16)
        body_lay.setContentsMargins(24, 20, 24, 20)
        
        # PASO 1: Carga
        body_lay.addWidget(self._make_step_label("PASO 1", "Cargar archivo(s) de liquidación"))
        body_lay.addWidget(self._make_file_section())
        
        # PASO 2: Config + Preview en splitter
        body_lay.addWidget(self._make_step_label("PASO 2", "Configurar extracción y procesar"))
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {T.BRD}; margin: 0 8px; }}")
        splitter.addWidget(self._make_config_panel())
        splitter.addWidget(self._make_preview_panel())
        splitter.setSizes([480, 660])
        body_lay.addWidget(splitter, stretch=1)
        
        # PASO 3: Tabla
        body_lay.addWidget(self._make_step_label("PASO 3", "Revisar datos extraídos"))
        body_lay.addWidget(self._make_data_table())
        
        root.addWidget(body, stretch=1)
        
        # Footer
        root.addWidget(self._make_footer())
    
    # ─── HEADER ───────────────────────────────
    def _make_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(70)
        w.setStyleSheet(f"""
            QWidget {{ background: {T.BG0}; border-bottom: 1px solid {T.BRD}; }}
        """)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(28, 0, 28, 0)
        
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel("LiquidaPro")
        t.setStyleSheet(f"color: {T.ACC}; font: 800 22px {T.F}; letter-spacing: 1px;")
        s = QLabel("Extractor de Recibos de Sueldo  ·  PDF → Excel")
        s.setStyleSheet(f"color: {T.FGM}; font: 12px {T.F}; letter-spacing: 0.8px;")
        col.addWidget(t)
        col.addWidget(s)
        lay.addLayout(col)
        lay.addStretch()
        
        self.badge = QLabel("  Sin archivos cargados")
        self._set_badge("info", "Sin archivos cargados")
        lay.addWidget(self.badge)
        
        return w
    
    def _set_badge(self, level: str, text: str):
        colors = {
            "info": (T.INF, "#1a2a40"), "ok": (T.OK, "#1a3020"),
            "warn": (T.WARN, "#3a2a10"), "err": (T.ERR, "#3a1a1a"),
        }
        fg, bg = colors.get(level, colors["info"])
        self.badge.setText(f"  {text}")
        self.badge.setStyleSheet(f"""
            color: {fg}; font: 600 12px {T.F};
            padding: 6px 14px; border-radius: 12px;
            background: {bg}; border: 1px solid {fg}40;
        """)
    
    def _make_step_label(self, step: str, desc: str) -> QLabel:
        lbl = QLabel(f"  {step}  ›  {desc}")
        lbl.setStyleSheet(f"""
            color: {T.FG}; font: 700 14px {T.F};
            padding: 4px 0;
        """)
        return lbl
    
    # ─── PASO 1: ARCHIVOS ─────────────────────
    def _make_file_section(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(8)
        lay.setContentsMargins(0, 0, 0, 0)
        
        row = QHBoxLayout()
        row.setSpacing(10)
        
        self.btn_load = self._accent_btn("📄  Cargar Archivo")
        self.btn_load.clicked.connect(self._on_load_single)
        row.addWidget(self.btn_load)
        
        self.btn_load_multi = self._secondary_btn("📁  Cargar Múltiples")
        self.btn_load_multi.clicked.connect(self._on_load_multiple)
        row.addWidget(self.btn_load_multi)
        
        self.btn_clear = self._danger_btn("🗑  Limpiar Todo")
        self.btn_clear.clicked.connect(self._on_clear)
        row.addWidget(self.btn_clear)
        
        row.addStretch()
        
        self.lbl_file_count = QLabel("0 archivos")
        self.lbl_file_count.setStyleSheet(f"color: {T.FGM}; font: 12px {T.FM};")
        row.addWidget(self.lbl_file_count)
        
        lay.addLayout(row)
        
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(72)
        self.file_list.setStyleSheet(f"""
            QListWidget {{
                background: {T.BG3}; color: {T.FG};
                border: 1px solid {T.BRD}; border-radius: 8px;
                padding: 4px; font: 12px {T.FM}; outline: none;
            }}
            QListWidget::item {{ padding: 3px 8px; border-radius: 4px; color: {T.FG}; }}
            QListWidget::item:selected {{ background: {T.ACC}30; color: {T.ACC}; }}
            QListWidget::item:hover {{ background: {T.BGH}; }}
        """)
        lay.addWidget(self.file_list)
        
        return w
    
    # ─── PASO 2: CONFIG ───────────────────────
    def _make_config_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setSpacing(10)
        lay.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setSpacing(12)
        inner_lay.setContentsMargins(0, 0, 12, 0)
        
        # ── Card: Ordenamiento ──
        card1 = self._card("↕  Ordenamiento")
        c1 = card1.layout()
        self.radio_original = QRadioButton("  Mantener orden original del PDF")
        self.radio_alpha = QRadioButton("  Ordenar alfabéticamente (A → Z)")
        self.radio_alpha.setChecked(True)
        
        # QButtonGroup garantiza exclusividad dentro del scroll area
        self._sort_group = QButtonGroup(self)
        self._sort_group.addButton(self.radio_original, 0)
        self._sort_group.addButton(self.radio_alpha, 1)
        self._sort_group.buttonClicked.connect(self._on_sort_changed)
        
        for r in [self.radio_original, self.radio_alpha]:
            r.setStyleSheet(self._radio_style())
            c1.addWidget(r)
        inner_lay.addWidget(card1)
        
        # ── Card: Columnas ──
        card2 = self._card("☰  Columnas a Exportar")
        c2 = card2.layout()
        
        # Info
        info = QFrame()
        info.setStyleSheet(f"background: {T.INF}15; border: 1px solid {T.INF}40; border-radius: 8px;")
        il = QVBoxLayout(info)
        il.setContentsMargins(12, 8, 12, 8)
        il.setSpacing(3)
        for txt in ["ℹ️  'Apellido y Nombre' siempre se incluye",
                     "ℹ️  'Rem c/ Aporte' y 'Líquido' se vinculan"]:
            lb = QLabel(txt)
            lb.setStyleSheet(f"color: {T.INF}; font: 500 12px {T.F}; background: transparent; border: none;")
            il.addWidget(lb)
        c2.addWidget(info)
        c2.addSpacing(4)
        
        # Checkboxes
        self.col_checks: Dict[str, QCheckBox] = {}
        cs = self._chk_style()
        
        # Obligatorio
        chk_n = QCheckBox("  Apellido y Nombre")
        chk_n.setChecked(True)
        chk_n.setEnabled(False)
        chk_n.setStyleSheet(cs)
        self.col_checks['nombre'] = chk_n
        c2.addWidget(chk_n)
        c2.addWidget(self._sep())
        
        # Vinculados
        lnk = QLabel("  ⛓  Vinculados:")
        lnk.setStyleSheet(f"color: {T.WARN}; font: 600 11px {T.F}; background: transparent; border: none;")
        c2.addWidget(lnk)
        
        chk_r = QCheckBox("  Rem c/ Aporte")
        chk_r.setChecked(True)
        chk_r.setStyleSheet(cs)
        chk_r.toggled.connect(lambda checked: self.col_checks['liquido'].setChecked(checked))
        self.col_checks['rem_con_aporte'] = chk_r
        c2.addWidget(chk_r)
        
        chk_l = QCheckBox("  Líquido")
        chk_l.setChecked(True)
        chk_l.setStyleSheet(cs)
        chk_l.toggled.connect(lambda checked: self.col_checks['rem_con_aporte'].setChecked(checked))
        self.col_checks['liquido'] = chk_l
        c2.addWidget(chk_l)
        c2.addWidget(self._sep())
        
        # Opcionales
        opt = QLabel("  Opcionales:")
        opt.setStyleSheet(f"color: {T.FG2}; font: 600 11px {T.F}; background: transparent; border: none;")
        c2.addWidget(opt)
        
        for key, display in [
            ('complemento_remunerativo', 'Complemento Remunerativo'),
            ('ajuste_apross', 'Ajuste Dif. Aporte Mínimo APROSS'),
            ('descuento_apross_familiar', 'Desc. APROSS Familiares Voluntarios'),
            ('pct_jub_ley11087', '% Aporte Jub. Ley 11.087'),
        ]:
            chk = QCheckBox(f"  {display}")
            chk.setChecked(False)
            chk.setStyleSheet(cs)
            self.col_checks[key] = chk
            c2.addWidget(chk)
        
        inner_lay.addWidget(card2)
        
        # ══════════════════════════════════════════
        #  BOTÓN PROCESAR — El más importante
        # ══════════════════════════════════════════
        inner_lay.addSpacing(8)
        
        self.btn_process = QPushButton("⚡  PROCESAR")
        self.btn_process.setCursor(Qt.PointingHandCursor)
        self.btn_process.setMinimumHeight(52)
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self._on_process)
        self.btn_process.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {T.ACC}, stop:1 #00b8d4);
                color: {T.BG0};
                border: none;
                padding: 14px 32px;
                border-radius: 10px;
                font: 800 16px {T.F};
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {T.ACH}, stop:1 #00d0e8);
            }}
            QPushButton:pressed {{
                background: {T.ACP};
            }}
            QPushButton:disabled {{
                background: {T.BG3};
                color: {T.FGD};
            }}
        """)
        inner_lay.addWidget(self.btn_process)
        
        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background: {T.BG3}; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {T.ACC}, stop:1 {T.INF});
                border-radius: 3px;
            }}
        """)
        inner_lay.addWidget(self.progress)
        
        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet(f"color: {T.FGM}; font: 12px {T.F};")
        inner_lay.addWidget(self.lbl_progress)
        
        inner_lay.addStretch()
        
        scroll.setWidget(inner)
        lay.addWidget(scroll)
        return panel
    
    # ─── PREVIEW ──────────────────────────────
    def _make_preview_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setSpacing(6)
        lay.setContentsMargins(0, 0, 0, 0)
        
        lbl = QLabel("  👁  Vista Previa del Archivo")
        lbl.setStyleSheet(f"color: {T.FG}; font: 700 14px {T.F}; padding: 4px 0;")
        lay.addWidget(lbl)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Cargue un archivo para ver su contenido aquí...")
        self.preview_text.setStyleSheet(f"""
            QTextEdit {{
                background: {T.BG3};
                color: {T.FG2};
                border: 1px solid {T.BRD};
                border-radius: 10px;
                padding: 12px;
                font: 11px {T.FM};
                selection-background-color: {T.ACC}30;
                selection-color: {T.ACC};
            }}
        """)
        lay.addWidget(self.preview_text, stretch=1)
        
        return panel
    
    # ─── TABLA DE DATOS ───────────────────────
    def _make_data_table(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(6)
        lay.setContentsMargins(0, 0, 0, 0)
        
        row = QHBoxLayout()
        self.lbl_records = QLabel("")
        self.lbl_records.setStyleSheet(f"color: {T.FGM}; font: 12px {T.FM};")
        row.addStretch()
        row.addWidget(self.lbl_records)
        lay.addLayout(row)
        
        self.table = QTableWidget()
        self.table.setMinimumHeight(200)
        self.table.setMaximumHeight(320)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {T.BG3}; color: {T.FG};
                border: 1px solid {T.BRD}; border-radius: 10px;
                font: 12px {T.FM};
                selection-background-color: {T.ACC}30;
                selection-color: {T.ACC};
                outline: none; gridline-color: transparent;
            }}
            QTableWidget::item {{
                padding: 8px 12px;
                border-bottom: 1px solid {T.BG2};
            }}
            QTableWidget::item:alternate {{ background: {T.BGA}; }}
            QHeaderView::section {{
                background: {T.BG0}; color: {T.ACC};
                font: 700 12px {T.F};
                padding: 10px 12px; border: none;
                border-bottom: 2px solid {T.ACC}60;
            }}
            QScrollBar:vertical {{
                background: {T.BG1}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {T.FGM}; border-radius: 4px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        
        # Placeholder
        self._reset_table_placeholder()
        lay.addWidget(self.table)
        
        return w
    
    def _reset_table_placeholder(self):
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Apellido y Nombre", "Rem c/ Aporte", "Líquido"])
        self.table.setRowCount(1)
        ph = QTableWidgetItem("⏳  Procesá un archivo para ver datos aquí...")
        ph.setForeground(QColor(T.FGM))
        ph.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(0, 0, ph)
        self.table.setSpan(0, 0, 1, 3)
    
    # ─── FOOTER ───────────────────────────────
    def _make_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(70)
        w.setStyleSheet(f"background: {T.BG0}; border-top: 1px solid {T.BRD};")
        
        lay = QHBoxLayout(w)
        lay.setContentsMargins(28, 0, 28, 0)
        lay.setSpacing(12)
        
        step4 = QLabel("  PASO 4  ›  Exportar resultados")
        step4.setStyleSheet(f"color: {T.FG}; font: 700 13px {T.F};")
        lay.addWidget(step4)
        
        lay.addStretch()
        
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {T.FGM}; font: 12px {T.F};")
        lay.addWidget(self.lbl_status)
        
        self.btn_csv = self._secondary_btn("📋  Exportar CSV")
        self.btn_csv.clicked.connect(self._on_export_csv)
        self.btn_csv.setEnabled(False)
        lay.addWidget(self.btn_csv)
        
        self.btn_excel = self._accent_btn("📊  Exportar Excel (.xlsx)")
        self.btn_excel.clicked.connect(self._on_export_excel)
        self.btn_excel.setEnabled(False)
        lay.addWidget(self.btn_excel)
        
        return w
    
    # ═══════════════════════════════════════════════
    #  ACCIONES DEL USUARIO
    # ═══════════════════════════════════════════════
    
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
        """Agrega archivos a la lista y muestra preview."""
        self.file_paths = paths
        self.is_processed = False
        
        # Actualizar lista visual
        self.file_list.clear()
        for p in paths:
            self.file_list.addItem(QListWidgetItem(f"  📄  {Path(p).name}"))
        
        n = len(paths)
        self.lbl_file_count.setText(f"{n} archivo{'s' if n != 1 else ''}")
        self._set_badge("info", f"{n} archivo{'s' if n != 1 else ''} cargado{'s' if n != 1 else ''}")
        
        # Habilitar botón procesar
        self.btn_process.setEnabled(True)
        
        # Deshabilitar export (hay que procesar primero)
        self.btn_excel.setEnabled(False)
        self.btn_csv.setEnabled(False)
        self._reset_table_placeholder()
        self.lbl_records.setText("")
        
        # Mostrar preview del primer archivo
        self._show_text_preview(paths[0])
    
    def _show_text_preview(self, path: str):
        """Muestra las primeras líneas del archivo en el panel de preview."""
        try:
            # Intentar UTF-8
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    text = f.read(5000)
            except UnicodeDecodeError:
                with open(path, 'r', encoding='latin-1') as f:
                    text = f.read(5000)
            
            # Limpiar un poco para que se lea mejor
            lines = text.split('\n')
            clean = []
            for line in lines[:120]:
                stripped = line.rstrip('\r')
                # Acortar líneas de puros guiones
                if len(stripped) > 40 and all(c == '_' for c in stripped):
                    clean.append("─" * 60)
                else:
                    clean.append(stripped)
            
            self.preview_text.setPlainText('\n'.join(clean))
            
        except Exception as e:
            self.preview_text.setPlainText(f"No se pudo leer el archivo:\n{str(e)}")
    
    def _on_process(self):
        """El usuario presionó PROCESAR."""
        if not self.file_paths:
            QMessageBox.warning(self, "Sin archivos", "Cargá al menos un archivo primero.")
            return
        
        # Deshabilitar controles durante el procesamiento
        self.btn_process.setEnabled(False)
        self.btn_load.setEnabled(False)
        self.btn_load_multi.setEnabled(False)
        self.btn_excel.setEnabled(False)
        self.btn_csv.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._set_badge("warn", "Procesando...")
        self.lbl_progress.setText("Iniciando extracción...")
        self.lbl_progress.setStyleSheet(f"color: {T.WARN}; font: 12px {T.F};")
        
        # Lanzar thread
        self._thread = ProcessThread(self.file_paths)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished.connect(self._on_finished)
        self._thread.error.connect(self._on_error)
        self._thread.start()
    
    def _on_progress(self, value: int, msg: str):
        self.progress.setValue(value)
        self.lbl_progress.setText(msg)
    
    def _on_finished(self, blocks: List[RawEmployeeBlock]):
        """Extracción exitosa → consolidar y mostrar en tabla."""
        self.raw_blocks = blocks
        
        # Leer configuración de ordenamiento
        sort_alpha = self.radio_alpha.isChecked()
        logger.info(f"Ordenamiento: {'Alfabético' if sort_alpha else 'Original del PDF'}")
        
        # Consolidar
        self.consolidated = self.processor.consolidate(blocks, sort_alpha)
        
        self.is_processed = True
        self.progress.setValue(100)
        self.progress.setVisible(False)
        
        n_blocks = len(blocks)
        n_emp = len(self.consolidated)
        
        self._set_badge("ok", f"✓  {n_blocks} registros → {n_emp} empleados")
        self.lbl_progress.setText(f"✅  {n_blocks} registros extraídos, {n_emp} empleados únicos")
        self.lbl_progress.setStyleSheet(f"color: {T.OK}; font: 12px {T.F};")
        
        # Habilitar controles
        self.btn_process.setEnabled(True)
        self.btn_load.setEnabled(True)
        self.btn_load_multi.setEnabled(True)
        self.btn_excel.setEnabled(True)
        self.btn_csv.setEnabled(True)
        
        # Llenar tabla
        self._fill_table()
        
        QMessageBox.information(
            self, "Procesamiento Completo",
            f"Se extrajeron {n_blocks} registros de {len(self.file_paths)} archivo(s).\n"
            f"Consolidados en {n_emp} empleados únicos.\n\n"
            f"Podés exportar a Excel o CSV con los botones del pie de página."
        )
    
    def _on_error(self, msg: str):
        """Error durante la extracción."""
        self.progress.setVisible(False)
        self._set_badge("err", "Error en procesamiento")
        self.lbl_progress.setText(f"❌  {msg}")
        self.lbl_progress.setStyleSheet(f"color: {T.ERR}; font: 12px {T.F};")
        
        self.btn_process.setEnabled(True)
        self.btn_load.setEnabled(True)
        self.btn_load_multi.setEnabled(True)
        
        QMessageBox.critical(self, "Error", f"Error al procesar:\n\n{msg}")
    
    def _fill_table(self):
        """Llena la tabla con los datos consolidados."""
        if not self.consolidated:
            return
        
        keys = self._get_selected_keys()
        display_cols = [DISPLAY_NAMES.get(k, k) for k in keys]
        
        self.table.setColumnCount(len(display_cols))
        self.table.setHorizontalHeaderLabels(display_cols)
        
        # Mostrar max 100 filas en preview
        data = self.consolidated[:100]
        self.table.setRowCount(len(data))
        
        for ri, rec in enumerate(data):
            for ci, key in enumerate(keys):
                val = rec.get(key, 0.0)
                
                if key == 'nombre':
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    item.setForeground(QColor(T.FG))
                elif key == 'pct_jub_ley11087':
                    # Porcentaje: mostrar como entero con %
                    if isinstance(val, (int, float)) and val > 0:
                        item = QTableWidgetItem(f"{int(round(val))} %")
                    else:
                        item = QTableWidgetItem("—")
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    item.setForeground(QColor(T.WARN))
                else:
                    # Formato argentino
                    if isinstance(val, (int, float)) and val > 0:
                        fmt = f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                        item = QTableWidgetItem(f"$ {fmt}")
                    else:
                        item = QTableWidgetItem("—")
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    item.setForeground(QColor(T.ACC))
                
                self.table.setItem(ri, ci, item)
        
        # Ajustar columnas
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(keys)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        total = len(self.consolidated)
        if total > 100:
            self.lbl_records.setText(f"Mostrando 100 de {total} empleados")
        else:
            self.lbl_records.setText(f"{total} empleados")
    
    def _get_selected_keys(self) -> List[str]:
        """Retorna las claves internas de columnas seleccionadas, en orden."""
        keys = ['nombre']  # Siempre
        
        # Orden fijo para consistencia
        order = ['rem_con_aporte', 'liquido', 'complemento_remunerativo',
                 'ajuste_apross', 'descuento_apross_familiar', 'pct_jub_ley11087']
        
        for k in order:
            chk = self.col_checks.get(k)
            if chk and chk.isChecked():
                keys.append(k)
        
        return keys
    
    # ─── EXPORTACIÓN ──────────────────────────
    def _on_export_excel(self):
        if not self.is_processed:
            QMessageBox.warning(self, "Sin datos", "Procesá un archivo primero.")
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Excel", "liquidaciones.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        
        try:
            keys = self._get_selected_keys()
            df = self.processor.to_dataframe(self.consolidated, keys)
            totals = self.processor.calculate_totals(df)
            self.exporter.export_to_excel(df, path, totals)
            
            self._set_badge("ok", f"✓  Exportado: {Path(path).name}")
            self.lbl_status.setText(f"Excel guardado ✓")
            self.lbl_status.setStyleSheet(f"color: {T.OK}; font: 12px {T.F};")
            
            QMessageBox.information(self, "Exportación Exitosa", f"Guardado en:\n{path}")
        except Exception as e:
            logger.error(f"Error Excel: {e}")
            QMessageBox.critical(self, "Error", f"Error al exportar:\n{str(e)}")
    
    def _on_export_csv(self):
        if not self.is_processed:
            QMessageBox.warning(self, "Sin datos", "Procesá un archivo primero.")
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar CSV", "liquidaciones.csv", "CSV (*.csv)"
        )
        if not path:
            return
        
        try:
            keys = self._get_selected_keys()
            df = self.processor.to_dataframe(self.consolidated, keys)
            self.exporter.export_to_csv(df, path)
            
            self._set_badge("ok", f"✓  Exportado: {Path(path).name}")
            self.lbl_status.setText(f"CSV guardado ✓")
            self.lbl_status.setStyleSheet(f"color: {T.OK}; font: 12px {T.F};")
            
            QMessageBox.information(self, "Exportación Exitosa", f"Guardado en:\n{path}")
        except Exception as e:
            logger.error(f"Error CSV: {e}")
            QMessageBox.critical(self, "Error", f"Error al exportar:\n{str(e)}")
    
    def _on_sort_changed(self):
        """Re-ordena datos cuando el usuario cambia el radio, sin re-procesar."""
        if not self.is_processed or not self.raw_blocks:
            return
        
        sort_alpha = self.radio_alpha.isChecked()
        logger.info(f"Re-ordenando: {'Alfabético' if sort_alpha else 'Original del PDF'}")
        
        self.consolidated = self.processor.consolidate(self.raw_blocks, sort_alpha)
        self._fill_table()
        
        order_name = "alfabético" if sort_alpha else "original del PDF"
        self._set_badge("ok", f"✓  {len(self.consolidated)} empleados · Orden {order_name}")
    
    def _on_clear(self):
        self.file_paths = []
        self.raw_blocks = []
        self.consolidated = []
        self.is_processed = False
        
        self.file_list.clear()
        self.lbl_file_count.setText("0 archivos")
        self.preview_text.clear()
        self._reset_table_placeholder()
        self.lbl_records.setText("")
        self.lbl_progress.setText("")
        self.lbl_status.setText("")
        self._set_badge("info", "Sin archivos cargados")
        
        self.btn_process.setEnabled(False)
        self.btn_excel.setEnabled(False)
        self.btn_csv.setEnabled(False)
    
    # ═══════════════════════════════════════════════
    #  FÁBRICAS DE WIDGETS + ESTILOS
    # ═══════════════════════════════════════════════
    
    def _accent_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(42)
        b.setStyleSheet(f"""
            QPushButton {{
                background: {T.ACC}; color: {T.BG0}; border: none;
                padding: 10px 24px; border-radius: 8px;
                font: 700 13px {T.F};
            }}
            QPushButton:hover {{ background: {T.ACH}; }}
            QPushButton:pressed {{ background: {T.ACP}; }}
            QPushButton:disabled {{ background: {T.BG3}; color: {T.FGD}; }}
        """)
        return b
    
    def _secondary_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(40)
        b.setStyleSheet(f"""
            QPushButton {{
                background: {T.BG3}; color: {T.FG};
                border: 1px solid {T.BRD}; padding: 9px 20px;
                border-radius: 8px; font: 600 13px {T.F};
            }}
            QPushButton:hover {{ background: {T.BGH}; border-color: {T.FGM}; }}
            QPushButton:pressed {{ background: {T.BG1}; }}
            QPushButton:disabled {{ background: {T.BG2}; color: {T.FGD}; border-color: {T.BG2}; }}
        """)
        return b
    
    def _danger_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(40)
        b.setStyleSheet(f"""
            QPushButton {{
                background: #4a2030; color: {T.ERR};
                border: 1px solid {T.ERR}40; padding: 9px 20px;
                border-radius: 8px; font: 600 13px {T.F};
            }}
            QPushButton:hover {{ background: #6a2040; border-color: {T.ERR}80; }}
            QPushButton:pressed {{ background: #801030; }}
        """)
        return b
    
    def _card(self, title: str) -> QWidget:
        c = QWidget()
        c.setStyleSheet(f"background: {T.BG2}; border: 1px solid {T.BRD}; border-radius: 10px;")
        lay = QVBoxLayout(c)
        lay.setSpacing(4)
        lay.setContentsMargins(16, 14, 16, 14)
        t = QLabel(title)
        t.setStyleSheet(f"color: {T.FG}; font: 700 13px {T.F}; border: none; background: transparent;")
        lay.addWidget(t)
        return c
    
    def _sep(self) -> QFrame:
        s = QFrame()
        s.setFixedHeight(1)
        s.setStyleSheet(f"background: {T.BRD}; border: none;")
        return s
    
    def _radio_style(self) -> str:
        return f"""
            QRadioButton {{
                color: {T.FG}; font: 13px {T.F}; padding: 6px 4px; spacing: 10px;
            }}
            QRadioButton::indicator {{
                width: 18px; height: 18px;
                border: 2px solid {T.FGM}; border-radius: 10px; background: {T.BG3};
            }}
            QRadioButton::indicator:checked {{ background: {T.ACC}; border-color: {T.ACC}; }}
            QRadioButton::indicator:hover {{ border-color: {T.ACC}; }}
        """
    
    def _chk_style(self) -> str:
        return f"""
            QCheckBox {{
                color: {T.FG}; font: 13px {T.F}; padding: 7px 4px; spacing: 10px;
            }}
            QCheckBox::indicator {{
                width: 20px; height: 20px;
                border: 2px solid {T.FGM}; border-radius: 4px; background: {T.BG3};
            }}
            QCheckBox::indicator:checked {{ background: {T.ACC}; border-color: {T.ACC}; }}
            QCheckBox::indicator:hover {{ border-color: {T.ACC}; }}
            QCheckBox:disabled {{ color: {T.FG2}; }}
            QCheckBox::indicator:disabled {{ background: {T.ACC}80; border-color: {T.ACC}80; }}
        """
    
    # ─── ESTILOS GLOBALES ─────────────────────
    def _apply_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background: {T.BG1}; }}
            QWidget {{ background: {T.BG1}; }}
            QToolTip {{
                background: {T.BG2}; color: {T.FG};
                border: 1px solid {T.BRD}; border-radius: 6px;
                padding: 6px 10px; font: 12px {T.F};
            }}
            QMessageBox {{ background: {T.BG2}; color: {T.FG}; }}
            QMessageBox QLabel {{ color: {T.FG}; font: 13px {T.F}; }}
            QMessageBox QPushButton {{
                background: {T.ACC}; color: {T.BG0}; border: none;
                padding: 8px 24px; border-radius: 6px;
                font: 700 13px {T.F}; min-width: 80px;
            }}
            QMessageBox QPushButton:hover {{ background: {T.ACH}; }}
            QScrollBar:vertical {{
                background: {T.BG1}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {T.FGM}; border-radius: 4px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {T.FG2}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
