import os
import sys
import threading
import webbrowser
from pathlib import Path


def ensure_data_dir() -> Path:
   if getattr(sys, "frozen", False):
       d = Path(sys.executable).resolve().parent
   else:
       d = Path(__file__).resolve().parent
   d.mkdir(parents=True, exist_ok=True)
   return d

def main():
   ensure_data_dir()
   os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
   import django
   django.setup()
   from django.core.wsgi import get_wsgi_application
   app = get_wsgi_application()
   def open_browser():
        webbrowser.open("http://127.0.0.1:8000/")
        threading.Timer(1.0, open_browser).start()
        from waitress import serve
        
        serve(app, host="0.0.0.0", port=8000, threads=6)


if __name__ == "__main__":

    main()
