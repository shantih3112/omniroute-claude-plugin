import sys,re
from PIL import Image
ch=sys.argv[1]; out=sys.argv[2]; sel=sys.argv[3] if len(sys.argv)>3 else None
order=re.findall(r'fig-\w+\.png', open(f'build/visuell-md/{ch}.md').read())
if sel: a,b=map(int,sel.split(':')); order=order[a:b]
ims=[Image.open('visuell/figurer/'+f) for f in order]
W=700; ims=[im.resize((W, int(im.height*W/im.width))) for im in ims]
cols=3; rows=[ims[i:i+cols] for i in range(0,len(ims),cols)]
H=sum(max(i.height for i in r) for r in rows)
c=Image.new('RGB',(W*cols,H),'#999'); y=0
for r in rows:
    for j,im in enumerate(r): c.paste(im,(j*W,y))
    y+=max(i.height for i in r)
c.thumbnail((1800,2600)); c.save(out); print(len(order), c.size)
