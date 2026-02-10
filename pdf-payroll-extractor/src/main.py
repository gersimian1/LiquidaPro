"""
Punto de entrada de la aplicación LiquidaPro.
"""
import sys
import logging
from pathlib import Path

# ═══════════════════════════════════════════════════
#  CRITICAL: Agregar src/ al path ANTES de importar
# ═══════════════════════════════════════════════════
current_dir = Path(__file__).parent.resolve()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui.main_window import MainWindow


def setup_logging():
    """Configura el sistema de logging"""
    log_dir = current_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'app.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def main():
    """Función principal"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=== Iniciando LiquidaPro ===")
    
    # Configurar high DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("LiquidaPro")
    app.setOrganizationName("LiquidaPro")
    
    window = MainWindow()
    window.show()
    
    logger.info("Ventana abierta. Esperando interacción del usuario...")
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
