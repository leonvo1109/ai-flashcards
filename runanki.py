#!/usr/bin/env python3
import os
from pathlib import Path

# Laden der .env Datei für lokale Entwicklung
try:
    from dotenv import load_dotenv

    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    # Falls python-dotenv nicht installiert ist, ignorieren
    pass

import aqt

if not os.environ.get("ANKI_IMPORT_ONLY"):
    aqt.run()
