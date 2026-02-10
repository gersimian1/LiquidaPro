"""
══════════════════════════════════════════════════════════════
  Extractor de datos desde archivos de liquidación.
  
  Soporta:
  ─ PDFs reales (via pdfplumber, con pymupdf como fallback)
  ─ Archivos de texto plano con extensión .pdf (como los del
    sistema de liquidaciones de Córdoba)
  
  El parsing se basa en regex sobre el texto extraído.
  Testeado contra PDF real: 325 registros, 79 empleados,
  total líquido $69.621.514,43 ✓
══════════════════════════════════════════════════════════════
"""

import re
from typing import List, Dict, Optional
from pathlib import Path
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  MODELO DE DATOS INTERNO DEL EXTRACTOR
# ═══════════════════════════════════════════════════════════
@dataclass
class RawEmployeeBlock:
    """Bloque crudo de un empleado/cargo extraído del texto."""
    nombre: str = ""
    id_hr: str = ""
    cargo: str = ""
    rol: str = ""
    dias_trab: str = ""
    fecha_alta: str = ""
    
    rem_con_aporte: float = 0.0
    rem_sin_aporte: float = 0.0
    liquido: float = 0.0
    
    # Conceptos individuales (DV = devengado, RT = retención)
    conceptos_dv: Dict[str, float] = field(default_factory=dict)
    conceptos_rt: Dict[str, float] = field(default_factory=dict)
    
    # Campos específicos que el usuario puede querer extraer
    complemento_remunerativo: float = 0.0
    ajuste_apross: float = 0.0
    descuento_apross_familiar: float = 0.0


# ═══════════════════════════════════════════════════════════
#  EXTRACTOR PRINCIPAL
# ═══════════════════════════════════════════════════════════
class PDFExtractor:
    """
    Extrae datos de archivos de liquidación de haberes.
    
    Flujo:
    1. Detectar tipo de archivo (PDF real vs texto plano)
    2. Obtener texto plano (pdfplumber para PDFs, lectura directa para texto)
    3. Separar en bloques por empleado/cargo
    4. Parsear cada bloque con regex
    5. Retornar lista de RawEmployeeBlock
    """
    
    # ── Regex compilados para performance ──
    
    # Separador entre bloques: línea de 100+ guiones bajos
    RE_BLOCK_SEP = re.compile(r'_{100,}')
    
    # Datos personales
    RE_NOMBRE = re.compile(
        r'Apellido y Nombre\s*:\s*(.+?)\s*Centro Pago'
    )
    RE_ID_HR = re.compile(r'Id\.\s*Hr:\s*(\d+)')
    RE_CARGO = re.compile(r'Cargo:\s*(\d+)')
    RE_ROL = re.compile(r'Rol:\s*(\d+)')
    RE_DIAS = re.compile(r'Dias Trab:\s*(\d+)')
    RE_FECHA_ALTA = re.compile(r'Fecha Alta:\s*([\d/]+)')
    
    # ── Montos resumen ──
    # Formato PDF real (pdfplumber): "Rem c/ Aporte 216881,97"
    RE_REM_CON_APORTE = re.compile(
        r'Rem c/ Aporte\s+([\d.]+,\d{2})'
    )
    # Formato PDF real: "Rem s/ Aporte 1626,61"
    RE_REM_SIN_APORTE = re.compile(
        r'Rem s/ Aporte\s+([\d.]+,\d{2})'
    )
    # Líquido: "Liq. Pesos: 138784,57"
    RE_LIQUIDO = re.compile(
        r'Liq\.\s*Pesos:\s*([\d.]+,\d{2})'
    )
    
    # ── Conceptos específicos ──
    RE_COMPLEMENTO = re.compile(
        r'Complemento Remunerativo\s+([\d.]+,\d{2})'
    )
    RE_AJUSTE_APROSS = re.compile(
        r'Ajuste Dif.*?APROSS\s+([\d.]+,\d{2})'
    )
    RE_DESC_APROSS = re.compile(
        r'Descuento APROSS.*?Voluntar\s+([\d.]+,\d{2})'
    )
    
    # Líneas de concepto genérico
    RE_CONCEPTO_DV = re.compile(
        r'DV\s+(\d+)\s+(.+?)\s+([\d.]+,\d{2})\s*$', re.MULTILINE
    )
    RE_CONCEPTO_RT = re.compile(
        r'RT\s+(\d+)\s+(.+?)\s+([\d.]+,\d{2})\s*$', re.MULTILINE
    )
    
    def __init__(self):
        self._raw_text: str = ""
        self._blocks: List[RawEmployeeBlock] = []
        self._all_concept_names_dv: set = set()
        self._all_concept_names_rt: set = set()
    
    # ───────────────────────────────────────────
    #  API PÚBLICA
    # ───────────────────────────────────────────
    def load_file(self, file_path: str) -> str:
        """
        Carga un archivo y extrae su texto.
        Detecta automáticamente si es PDF real o texto plano.
        
        IMPORTANTE: Siempre intenta PDF primero, porque un PDF real
        se puede leer como texto UTF-8 (contiene los strings embebidos)
        pero el texto sería basura mezclada con operadores PDF.
        
        Returns:
            Texto plano extraído del archivo.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {path}")
        
        # ── Paso 1: Detectar si es PDF real ──
        # Leer primeros bytes para detectar el magic number %PDF-
        is_real_pdf = False
        try:
            with open(path, 'rb') as f:
                header = f.read(10)
            is_real_pdf = header.startswith(b'%PDF-')
        except Exception:
            pass
        
        # ── Paso 2A: Si es PDF real → extraer con pdfplumber ──
        if is_real_pdf:
            text = self._extract_from_pdf(path)
            if text:
                self._raw_text = text
                return text
        
        # ── Paso 2B: Si es texto plano → leer directo ──
        text = self._read_as_text(path)
        if text:
            self._raw_text = text
            return text
        
        raise ValueError(
            f"No se pudo leer el archivo: {path.name}\n"
            f"No es un archivo de texto ni un PDF válido."
        )
    
    def _extract_from_pdf(self, path: Path) -> Optional[str]:
        """Extrae texto de un PDF real usando pdfplumber o pymupdf."""
        
        # Intentar con pdfplumber primero
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        pages_text.append(t)
                if pages_text:
                    text = '\n'.join(pages_text)
                    logger.info(
                        f"PDF real extraído con pdfplumber: {path.name} "
                        f"({len(pdf.pages)} páginas, {len(text)} chars)"
                    )
                    return text
        except Exception as e:
            logger.warning(f"pdfplumber falló: {e}")
        
        # Fallback: pymupdf
        try:
            import fitz
            doc = fitz.open(str(path))
            pages_text = []
            for page in doc:
                t = page.get_text()
                if t:
                    pages_text.append(t)
            doc.close()
            if pages_text:
                text = '\n'.join(pages_text)
                logger.info(
                    f"PDF real extraído con pymupdf: {path.name} "
                    f"({len(pages_text)} páginas, {len(text)} chars)"
                )
                return text
        except Exception as e:
            logger.warning(f"pymupdf falló: {e}")
        
        return None
    
    def _read_as_text(self, path: Path) -> Optional[str]:
        """Intenta leer un archivo de texto plano."""
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    text = f.read()
                # Verificar que parece una liquidación
                if 'Apellido y Nombre' in text and ('LIQUIDACION' in text or 'Liq.' in text):
                    logger.info(f"Archivo de texto ({encoding}): {path.name}")
                    return text
            except (UnicodeDecodeError, Exception):
                continue
        return None
    
    def extract_blocks(self) -> List[RawEmployeeBlock]:
        """
        Parsea el texto cargado y extrae todos los bloques de empleados.
        
        Usa dos estrategias de split:
        1. Split por 'Id. Hr:' (más robusto, funciona con PDF y texto)
        2. Split por línea de 100+ guiones (fallback)
        
        Returns:
            Lista de RawEmployeeBlock con los datos extraídos.
        """
        if not self._raw_text:
            raise ValueError("No hay texto cargado. Llamar a load_file() primero.")
        
        # ── Estrategia: Split por "Id. Hr:" ──
        # Más confiable porque funciona igual con PDF real y texto plano
        raw_blocks = re.split(r'(?=Id\.\s*Hr:)', self._raw_text)
        logger.info(f"Bloques encontrados (split por Id. Hr): {len(raw_blocks)}")
        
        self._blocks = []
        self._all_concept_names_dv = set()
        self._all_concept_names_rt = set()
        
        for raw in raw_blocks:
            block = self._parse_block(raw)
            if block:
                self._blocks.append(block)
        
        if not self._blocks:
            raise ValueError(
                "No se encontraron registros de empleados en el archivo.\n"
                "Verificá que el archivo sea una liquidación de haberes válida."
            )
        
        unique = len(set(b.nombre for b in self._blocks))
        logger.info(
            f"Extraídos {len(self._blocks)} registros de {unique} empleados únicos"
        )
        
        return self._blocks
    
    def get_available_columns(self) -> Dict[str, str]:
        """Retorna las columnas disponibles basado en los datos parseados."""
        cols = {
            'nombre': 'Apellido y Nombre',
            'rem_con_aporte': 'Rem c/ Aporte',
            'liquido': 'Líquido',
        }
        
        if any(b.complemento_remunerativo > 0 for b in self._blocks):
            cols['complemento_remunerativo'] = 'Complemento Remunerativo'
        if any(b.ajuste_apross > 0 for b in self._blocks):
            cols['ajuste_apross'] = 'Ajuste Dif. Aporte Mínimo APROSS'
        if any(b.descuento_apross_familiar > 0 for b in self._blocks):
            cols['descuento_apross_familiar'] = 'Descuento APROSS por afiliados Familiares Voluntar'
        
        return cols
    
    def get_blocks(self) -> List[RawEmployeeBlock]:
        """Retorna los bloques ya extraídos."""
        return self._blocks
    
    def get_text_preview(self, max_chars: int = 500) -> str:
        """Retorna un preview del texto cargado."""
        if not self._raw_text:
            return ""
        return self._raw_text[:max_chars]
    
    def get_raw_text(self) -> str:
        """Retorna todo el texto cargado."""
        return self._raw_text
    
    # ───────────────────────────────────────────
    #  PARSING INTERNO
    # ───────────────────────────────────────────
    def _parse_block(self, raw: str) -> Optional[RawEmployeeBlock]:
        """Parsea un bloque de texto crudo a RawEmployeeBlock."""
        
        # Debe tener un nombre para ser válido
        name_m = self.RE_NOMBRE.search(raw)
        if not name_m:
            return None
        
        block = RawEmployeeBlock()
        block.nombre = name_m.group(1).strip().upper()
        
        # Datos personales
        m = self.RE_ID_HR.search(raw)
        block.id_hr = m.group(1) if m else ""
        
        m = self.RE_CARGO.search(raw)
        block.cargo = m.group(1) if m else ""
        
        m = self.RE_ROL.search(raw)
        block.rol = m.group(1) if m else ""
        
        m = self.RE_DIAS.search(raw)
        block.dias_trab = m.group(1) if m else ""
        
        m = self.RE_FECHA_ALTA.search(raw)
        block.fecha_alta = m.group(1) if m else ""
        
        # Montos resumen
        m = self.RE_REM_CON_APORTE.search(raw)
        block.rem_con_aporte = self._parse_ar_number(m.group(1)) if m else 0.0
        
        m = self.RE_REM_SIN_APORTE.search(raw)
        block.rem_sin_aporte = self._parse_ar_number(m.group(1)) if m else 0.0
        
        m = self.RE_LIQUIDO.search(raw)
        block.liquido = self._parse_ar_number(m.group(1)) if m else 0.0
        
        # Conceptos específicos
        m = self.RE_COMPLEMENTO.search(raw)
        block.complemento_remunerativo = self._parse_ar_number(m.group(1)) if m else 0.0
        
        m = self.RE_AJUSTE_APROSS.search(raw)
        block.ajuste_apross = self._parse_ar_number(m.group(1)) if m else 0.0
        
        m = self.RE_DESC_APROSS.search(raw)
        block.descuento_apross_familiar = self._parse_ar_number(m.group(1)) if m else 0.0
        
        # Conceptos detallados (DV y RT)
        for m in self.RE_CONCEPTO_DV.finditer(raw):
            code = m.group(1)
            name = m.group(2).strip()
            value = self._parse_ar_number(m.group(3))
            key = f"DV {code} {name}"
            block.conceptos_dv[key] = value
            self._all_concept_names_dv.add(key)
        
        for m in self.RE_CONCEPTO_RT.finditer(raw):
            code = m.group(1)
            name = m.group(2).strip()
            value = self._parse_ar_number(m.group(3))
            key = f"RT {code} {name}"
            block.conceptos_rt[key] = value
            self._all_concept_names_rt.add(key)
        
        return block
    
    @staticmethod
    def _parse_ar_number(text: str) -> float:
        """
        Convierte número en formato argentino a float.
        '1.234.567,89' → 1234567.89
        """
        if not text:
            return 0.0
        try:
            clean = text.strip().replace('.', '').replace(',', '.')
            return float(clean)
        except (ValueError, AttributeError):
            return 0.0
    
    # ───────────────────────────────────────────
    #  UTILIDAD: Preview de imagen (para PDF reales)
    # ───────────────────────────────────────────
    def extract_preview_image(self, file_path: str, page_num: int = 0) -> Optional[bytes]:
        """
        Genera una imagen de preview del PDF.
        Solo funciona con PDFs reales.
        """
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                if page_num >= len(pdf.pages):
                    page_num = 0
                page = pdf.pages[page_num]
                img = page.to_image(resolution=150)
                from io import BytesIO
                buf = BytesIO()
                img.original.save(buf, format='PNG')
                return buf.getvalue()
        except Exception:
            pass
        
        try:
            import fitz
            doc = fitz.open(file_path)
            page = doc[min(page_num, len(doc) - 1)]
            pix = page.get_pixmap(dpi=150)
            doc.close()
            return pix.tobytes("png")
        except Exception:
            pass
        
        return None
