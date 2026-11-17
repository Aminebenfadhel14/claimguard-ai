"""Windows-friendly launcher; no PowerShell execution-policy changes required."""
import argparse
import json
import os
import socket
import subprocess
import sys
from dotenv import load_dotenv
from claimguard.settings import ROOT, load_profile
from claimguard.diagnostics import readiness


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8501)
    parser.add_argument('--profile',default=None)
    parser.add_argument('--check',action='store_true',help='Validate resources and port without starting the server')
    args=parser.parse_args()
    if not 1024<=args.port<=65535: parser.error('Port attendu entre 1024 et 65535.')
    load_dotenv(ROOT/'.env')
    profile=load_profile(ROOT,args.profile)
    status=readiness(ROOT,os.getenv('CLAIMGUARD_CORPUS','drip_r'),profile,verify=True)
    if 'rerank' not in status['available_modes']:
        parser.error('Modèles incomplets. Exécutez python scripts/prepare_models.py --profiles '+profile['name'])
    try:
        with socket.socket() as probe:
            if hasattr(socket,'SO_EXCLUSIVEADDRUSE'): probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            probe.bind(('127.0.0.1',args.port))
    except OSError:
        parser.error(f'Le port {args.port} est occupé ou indisponible. Ouvrez http://localhost:{args.port} ou choisissez --port 8502.')
    if args.check:
        print(json.dumps(status,indent=2,ensure_ascii=False))
        return 0
    environment=dict(os.environ,CLAIMGUARD_PROFILE=profile['name'])
    return subprocess.call([sys.executable,'-m','streamlit','run','app/Home.py','--server.address','127.0.0.1',
                            '--server.port',str(args.port),'--server.headless','true'],cwd=ROOT,env=environment)


if __name__=='__main__': raise SystemExit(main())
