"""Hand-drawn, monochrome 20x16 alternatives for the four reviewed activities."""
class Pixels:
    def __init__(self):self.g=[[0]*20 for _ in range(16)]
    def dot(self,x,y,v=1):
        if 0<=x<20 and 0<=y<16:self.g[y][x]=v
    def rect(self,x,y,w,h,v=1):
        for yy in range(y,y+h):
            for xx in range(x,x+w):self.dot(xx,yy,v)
    def line(self,x,y,xx,yy,width=1,v=1):
        n=max(abs(xx-x),abs(yy-y))
        for i in range(n+1):
            a=round(x+(xx-x)*i/max(n,1));b=round(y+(yy-y)*i/max(n,1))
            self.rect(a,b,width,width,v)
    def poly(self,points,v=1):
        for y in range(16):
            for x in range(20):
                inside=False;j=len(points)-1
                for i,(xi,yi) in enumerate(points):
                    xj,yj=points[j]
                    if (yi>y+.5)!=(yj>y+.5) and x+.5<(xj-xi)*(y+.5-yi)/(yj-yi)+xi:inside=not inside
                    j=i
                if inside:self.dot(x,y,v)
    def circle(self,cx,cy,r,v=1):
        for y in range(16):
            for x in range(20):
                if (x-cx)**2+(y-cy)**2<=r*r:self.dot(x,y,v)
    def rows(self):return [''.join(map(str,row)) for row in self.g]

def draw(kind,variant):
    p=Pixels()
    if kind=='settings':
        if variant=='A': # Open-ended spanner, diagonal shaft and hole at handle.
            p.poly([(11,1),(16,1),(13,4),(15,6),(18,3),(18,8),(15,10),(12,9),(7,14),(4,14),(3,12),(10,5),(10,2)])
            p.dot(5,12,0)
        elif variant=='B': # Eight projecting teeth, deliberately non-concentric.
            p.circle(9.5,7.5,5)
            for r in [(8,0,4,4),(8,12,4,4),(2,6,4,4),(14,6,4,4),(4,2,3,3),(13,2,3,3),(4,11,3,3),(13,11,3,3)]:p.rect(*r)
            p.circle(9.5,7.5,2.2,0)
        elif variant=='C': # Crossed open wrench and screwdriver.
            p.line(4,3,14,13,2);p.rect(2,1,4,3);p.rect(14,12,3,3)
            p.line(5,13,14,4,2);p.rect(12,1,6,5);p.rect(14,0,2,3,0);p.rect(4,12,3,3)
        else: # Broad horizontal wrench, jaws read at tiny size.
            p.poly([(2,5),(5,2),(8,2),(8,5),(5,5),(5,9),(8,9),(8,12),(5,12),(2,9)])
            p.rect(7,6,10,3);p.rect(16,5,3,5);p.dot(17,7,0)
    elif kind=='shuffle':
        if variant=='A':
            for a in [(2,3,5,3),(5,3,13,11),(13,11,15,11),(2,11,5,11),(5,11,13,3),(13,3,15,3)]:p.line(*a,2)
            p.poly([(14,1),(19,4),(14,7)]);p.poly([(14,9),(19,12),(14,15)])
        elif variant=='B': # Stepped crossing paths with a visible overpass.
            for a in [(2,3,6,3),(6,3,12,11),(12,11,15,11),(2,11,6,11),(6,11,12,3),(12,3,15,3)]:p.line(*a,2)
            p.line(8,7,10,5,1,0)
            for y in [4,12]:p.line(14,y-3,17,y,2);p.line(14,y+3,17,y,2)
        elif variant=='C': # Compact, solid crossed arrow shapes.
            p.poly([(1,2),(6,2),(14,10),(14,9),(19,12),(14,15),(14,13),(5,5),(1,5)])
            p.poly([(1,11),(5,11),(14,2),(14,1),(19,4),(14,7),(14,5),(6,14),(1,14)])
        else: # Longer horizontal leads and a tighter central crossing.
            for a in [(1,3,7,3),(7,3,12,11),(12,11,16,11),(1,11,7,11),(7,11,12,3),(12,3,16,3)]:p.line(*a,2)
            for y in [4,12]:p.poly([(15,y-3),(19,y),(15,y+3)])
    elif kind=='books':
        if variant=='A': # Closed hardback, cover, spine and page block.
            p.rect(4,1,12,14);p.rect(7,3,7,8,0);p.rect(6,12,9,2,0);p.rect(8,4,1,6);p.rect(9,3,3,2)
        elif variant=='B': # Open spread, sloping top edges, central spine.
            for a in [(1,2,5,2),(5,2,9,4),(10,4,14,2),(14,2,18,2),(1,2,1,12),(18,2,18,12),(1,12,5,12),(5,12,9,14),(10,14,14,12),(14,12,18,12),(9,4,9,14),(10,4,10,14)]:p.line(*a)
            for y in [5,8]:p.line(3,y,6,y+1);p.line(13,y+1,16,y)
        elif variant=='C': # Book with a strong enclosing headphone arch.
            p.line(2,6,2,11,2);p.line(16,6,16,11,2)
            p.line(3,4,6,1,2);p.line(6,1,12,1,2);p.line(12,1,16,5,2)
            p.rect(6,5,8,10);p.rect(8,7,4,5,0);p.rect(8,13,5,1,0)
        else: # Stacked bound books with distinct page stripes.
            p.rect(5,1,12,4);p.rect(7,3,8,1,0)
            p.rect(2,6,13,4);p.rect(4,8,9,1,0)
            p.rect(4,11,14,4);p.rect(6,13,10,1,0)
    else:
        if variant=='A': # Seated person: head, torso, arms and crossed legs.
            p.circle(9.5,2,1.8);p.rect(8,5,4,2);p.rect(9,7,2,3)
            p.line(7,6,4,10);p.line(12,6,15,10)
            for a in [(4,10,2,12),(2,12,6,14),(6,14,12,10),
                      (15,10,17,12),(17,12,13,14),(13,14,7,10)]:p.line(*a)
            p.rect(5,14,10,1)
        elif variant=='B': # Lotus flower: central pointed petal and open side petals.
            p.poly([(10,1),(13,6),(12,10),(10,12),(8,10),(7,6)])
            p.poly([(3,4),(7,6),(8,11),(5,10),(3,7)])
            p.poly([(17,4),(13,6),(12,11),(15,10),(17,7)])
            p.poly([(1,9),(5,10),(9,13),(5,14),(2,12)])
            p.poly([(19,9),(15,10),(11,13),(15,14),(18,12)])
            p.rect(7,14,6,1)
        elif variant=='C': # Headphones / guided listening; no ambiguous posture.
            for a in [(2,7,2,12),(2,7,4,3),(4,3,7,1),(7,1,12,1),(12,1,16,4),(16,4,17,8),(17,8,17,12)]:p.line(*a,2)
            p.rect(3,8,3,6);p.rect(14,8,3,6)
            p.line(8,8,11,8);p.line(8,11,11,11)
        else: # Candle, pointed flame, wick and base.
            p.poly([(10,0),(13,5),(11,7),(8,7),(7,5)])
            p.dot(10,5,0);p.rect(9,7,1,2);p.rect(6,9,8,5);p.rect(8,10,1,3,0);p.rect(4,14,12,1)
    return p.rows()

SETS=[
    dict(id='A',name='Practical',description='Open wrench · heavy crossing arrows · closed hardback · seated person',symbols=['Open wrench','Heavy crossed arrows','Closed hardback','Seated meditation']),
    dict(id='B',name='Classic',description='Toothed gear · outlined arrowheads · open book · lotus flower',symbols=['Eight-tooth gear','Stepped crossed arrows','Open book','Lotus flower']),
    dict(id='C',name='Audio',description='Crossed tools · solid arrows · book with headphones · guided listening',symbols=['Wrench + screwdriver','Solid crossed arrows','Book + headphones','Guided listening']),
    dict(id='D',name='Quiet',description='Horizontal wrench · long-lead arrows · book stack · candle',symbols=['Horizontal wrench','Tight crossed arrows','Stack of books','Candle'])
]
KINDS=['settings','shuffle','books','meditation']
def variants():
    return [{**s,'icons':[dict(kind=k,symbol=s['symbols'][i],pixels=draw(k,s['id'])) for i,k in enumerate(KINDS)]} for s in SETS]
