"""Reworked module for tests.conftest.py"""
from pathlib import Path
import sys
IMAGEMAGICK_BINARY = 'D:\\ImageMagick-7.1.2-Q16\\magick.exe'
sys.path.insert(0, str(Path(__file__).parent.parent))
