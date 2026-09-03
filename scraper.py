#!/usr/bin/env python3
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from src.cli.commands import app

if __name__ == "__main__":
    app()


