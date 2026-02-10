"""
Script de arranque para la aplicación PDF Payroll Extractor.
Ejecuta este archivo para iniciar la aplicación.
"""
import sys
from pathlib import Path

# Agregar el directorio src al path para permitir imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Ahora podemos importar y ejecutar
from main import main

if __name__ == '__main__':
    main()
