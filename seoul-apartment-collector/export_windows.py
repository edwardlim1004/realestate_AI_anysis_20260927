#!/usr/bin/env python3
import argparse,csv,gzip,os
from pathlib import Path
BASE=Path(__file__).resolve().parent
DEFAULT=Path(r'F:\01.LIM EDWARD\00. 아빠폴더(미래준비 및 취미)\2.부동산\2.부동산\1.서울아파트 매매전월세 거래 정보')
FOLDERS={'sale':'서울아파트매매','rent':'서울아파트전월세'}
LABEL={'sale':'매매','rent':'전월세'}
def run(root):
 if os.name=='nt' and not Path(root.anchor).exists():raise RuntimeError('F: drive not accessible')
 for kind in ('sale','rent'):
  parent=BASE/'data'/kind
  if not parent.exists():continue
  for year in sorted(parent.glob('[12][0-9][0-9][0-9]')):
   sources=sorted(year.glob('*/*.csv.gz'))
   if not sources:continue
   folder=root/FOLDERS[kind];folder.mkdir(parents=True,exist_ok=True)
   output=folder/f'서울아파트_{LABEL[kind]}_{year.name}.csv'
   tmp=output.with_suffix('.tmp');count=0
   with tmp.open('w',encoding='utf-8-sig',newline='') as f:
    writer=None
    for src in sources:
     with gzip.open(src,'rt',encoding='utf-8-sig',newline='') as stream:
      reader=csv.DictReader(stream)
      if writer is None:
       writer=csv.DictWriter(f,fieldnames=reader.fieldnames or []);writer.writeheader()
      for row in reader:writer.writerow(row);count+=1
   os.replace(tmp,output)
   print(f'{output} : {count:,} rows')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output-root',default=str(DEFAULT))
 run(Path(parser.parse_args().output_root))
