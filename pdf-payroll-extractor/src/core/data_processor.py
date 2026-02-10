"""
══════════════════════════════════════════════════════════════
  Procesador de datos — Consolida y transforma registros
══════════════════════════════════════════════════════════════
"""

from typing import List, Dict
from collections import defaultdict
import pandas as pd
import logging

from core.pdf_extractor import RawEmployeeBlock

logger = logging.getLogger(__name__)


# Mapeo: clave interna → atributo del RawEmployeeBlock
FIELD_MAP = {
    'nombre':                    'nombre',
    'rem_con_aporte':            'rem_con_aporte',
    'liquido':                   'liquido',
    'complemento_remunerativo':  'complemento_remunerativo',
    'ajuste_apross':             'ajuste_apross',
    'descuento_apross_familiar': 'descuento_apross_familiar',
}

# Mapeo: clave interna → nombre para mostrar en columnas
DISPLAY_NAMES = {
    'nombre':                    'Apellido y Nombre',
    'rem_con_aporte':            'Rem c/ Aporte',
    'liquido':                   'Líquido',
    'complemento_remunerativo':  'Complemento Remunerativo',
    'ajuste_apross':             'Ajuste Dif. Aporte Mínimo APROSS',
    'descuento_apross_familiar': 'Descuento APROSS por afiliados Familiares Voluntar',
}


class DataProcessor:
    """Consolida registros de múltiples cargos/roles por empleado."""
    
    def consolidate(
        self,
        blocks: List[RawEmployeeBlock],
        sort_alpha: bool = True
    ) -> List[Dict[str, object]]:
        """
        Agrupa bloques por nombre de empleado, sumando montos.
        
        Un empleado puede tener múltiples cargos/roles → se suman.
        
        Returns:
            Lista de dicts con los datos consolidados.
        """
        accum = defaultdict(lambda: {
            'rem_con_aporte': 0.0,
            'liquido': 0.0,
            'complemento_remunerativo': 0.0,
            'ajuste_apross': 0.0,
            'descuento_apross_familiar': 0.0,
        })
        
        for b in blocks:
            name = b.nombre
            accum[name]['rem_con_aporte'] += b.rem_con_aporte
            accum[name]['liquido'] += b.liquido
            accum[name]['complemento_remunerativo'] += b.complemento_remunerativo
            accum[name]['ajuste_apross'] += b.ajuste_apross
            accum[name]['descuento_apross_familiar'] += b.descuento_apross_familiar
        
        names = sorted(accum.keys()) if sort_alpha else list(accum.keys())
        
        result = []
        for name in names:
            row = {'nombre': name}
            row.update(accum[name])
            result.append(row)
        
        logger.info(f"Consolidados {len(blocks)} bloques → {len(result)} empleados")
        return result
    
    def to_dataframe(
        self,
        consolidated: List[Dict[str, object]],
        selected_keys: List[str]
    ) -> pd.DataFrame:
        """
        Convierte datos consolidados a DataFrame con solo las columnas seleccionadas.
        
        Args:
            consolidated: Lista de dicts del método consolidate()
            selected_keys: Lista de claves internas (ej: ['nombre', 'liquido'])
            
        Returns:
            DataFrame con columnas renombradas a display names.
        """
        # Filtrar solo columnas seleccionadas
        rows = []
        for rec in consolidated:
            row = {}
            for key in selected_keys:
                display = DISPLAY_NAMES.get(key, key)
                row[display] = rec.get(key, 0.0 if key != 'nombre' else '')
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # Asegurar tipos numéricos
        for col in df.columns:
            if col != 'Apellido y Nombre':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        return df
    
    def calculate_totals(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calcula totales de columnas numéricas."""
        totals = {}
        for col in df.columns:
            if col != 'Apellido y Nombre' and pd.api.types.is_numeric_dtype(df[col]):
                totals[col] = df[col].sum()
        return totals
