"""Entry point:  python -m snakenet.client --host 127.0.0.1 --port 5000 --name ana"""
import sys

from .ui import main

sys.exit(main())
