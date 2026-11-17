"""Lance l'interface React + API FastAPI sur un seul port (http://127.0.0.1:8000).

    .\\.venv\\Scripts\\python.exe scripts\\run_web.py            # build React si absent, puis serveur
    .\\.venv\\Scripts\\python.exe scripts\\run_web.py --build    # force la reconstruction du frontend
    .\\.venv\\Scripts\\python.exe scripts\\run_web.py --api-only # API seule (frontend servi par npm run dev)
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'
sys.path.insert(0, str(ROOT / 'src'))


def build_frontend():
    npm = shutil.which('npm') or shutil.which('npm.cmd')
    if not npm:
        raise SystemExit('Node.js/npm introuvable. Installez Node.js 18+ (https://nodejs.org) ou utilisez --api-only.')
    if not (FRONTEND / 'node_modules').exists():
        print('Installation des dépendances du frontend (npm install)…')
        subprocess.check_call([npm, 'install', '--no-audit', '--no-fund'], cwd=FRONTEND)
    print('Construction du frontend React (npm run build)…')
    subprocess.check_call([npm, 'run', 'build'], cwd=FRONTEND)


def open_when_ready(url, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url + '/api/health', timeout=2)
            webbrowser.open(url)
            return
        except Exception:
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--build', action='store_true', help='Reconstruire le frontend React')
    parser.add_argument('--api-only', action='store_true', help='Ne pas construire ni servir le frontend')
    parser.add_argument('--no-browser', action='store_true', help='Ne pas ouvrir le navigateur')
    args = parser.parse_args()

    from dotenv import load_dotenv
    from claimguard.diagnostics import readiness
    from claimguard.settings import load_profile
    os.chdir(ROOT)
    load_dotenv(ROOT / '.env')
    os.environ['CLAIMGUARD_HOME'] = str(ROOT)

    profile = load_profile(ROOT)
    status = readiness(ROOT, 'drip_r', profile)
    if not status['available_modes']:
        print('Attention : modèles locaux absents. Exécutez d’abord :\n'
              f'  .\\.venv\\Scripts\\python.exe scripts\\prepare_models.py --profiles {profile["name"]}')

    if not args.api_only and (args.build or not (FRONTEND / 'dist/index.html').exists()):
        build_frontend()

    try:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', args.port))
    except OSError:
        raise SystemExit(f'Le port {args.port} est occupé. Choisissez --port 8001.')

    url = f'http://127.0.0.1:{args.port}'
    print(f'ClaimGuard AI : {url}  (API : {url}/docs)  —  Ctrl+C pour arrêter')
    if not args.no_browser and not args.api_only:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    import uvicorn
    uvicorn.run('claimguard.web:app', host='127.0.0.1', port=args.port, log_level='info')


if __name__ == '__main__':
    main()
