import glob
TOPS='┌'; ENDS='┐'
for f in sorted(glob.glob('kapitler/*.md')):
    lines=open(f).read().split('\n'); inb=False; changed=0
    for n,l in enumerate(lines):
        if l.startswith('```'): inb=not inb; continue
        if not inb: continue
        s=l.rstrip(); ind=len(s)-len(s.lstrip())
        if not s.strip() or s.lstrip()[0] not in '│├└' or s[-1] not in '│┤┘': continue
        # find nearest previous top border at same indent
        tgt=None
        for m in range(n-1,max(-1,n-40),-1):
            p=lines[m].rstrip()
            if p.startswith('```'): break
            if len(p)-len(p.lstrip())==ind and p.strip() and p.lstrip()[0]=='┌' and p[-1]=='┐':
                tgt=len(p); break
        if tgt is None or len(s)==tgt: continue
        body,last=s[:-1],s[-1]
        fill='─' if s.lstrip()[0] in '├└' else ' '
        d=tgt-len(s)
        if d>0: body=body+fill*d
        else:
            if body.endswith(fill*(-d)): body=body[:d]
            else: print('KAN IKKE',f,n+1); continue
        lines[n]=body+last; changed+=1
    if changed:
        open(f,'w').write('\n'.join(lines)); print(f,changed)
