import argparse
from pathlib import Path
from claimguard.datasets.drip_r import prepare

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--home',type=Path,default=Path('.'))
    parser.add_argument('--download',action='store_true'); args=parser.parse_args()
    audit=prepare(args.home,args.download)
    print({k:audit[k] for k in ('scenario_count','task_count','persona_count','unique_policy_count','revision')})
