import re,sys,glob
BOX=set('│┐┘┤┬┴┼║╗╝')
START=set('│┌└├┬┴┼║╔╚')
for f in sorted(glob.glob('kapitler/*.md')):
    lines=open(f).read().split('\n'); inb=False
    for n,l in enumerate(lines):
        if l.startswith('```'): inb=not inb; continue
        if not inb or n==0: continue
        p=lines[n-1]
        if p.startswith('```'): continue
        a,b=p.rstrip(),l.rstrip()
        if not a or not b: continue
        if a[-1] in BOX and b[-1] in BOX and len(a)!=len(b):
            sa=len(a)-len(a.lstrip()); sb=len(b)-len(b.lstrip())
            if sa==sb and a.lstrip()[0] in START and b.lstrip()[0] in START:
                print(f"{f}:{n+1}: {len(a)} vs {len(b)}")
