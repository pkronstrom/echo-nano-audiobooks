"""Round-three alternatives, with a blank one-pixel perimeter on every icon."""
from icon_proposals import Pixels
import math

KINDS=['files','library','play','musicsettings','settings','shuffle','books','meditation']
NAMES={
'files':['Tabbed folder','Open folder','Folder with files','Solid folder'],
'library':['Music collection','Album sleeves','Library list','Record library'],
'play':['Sharp solid triangle','Sharp outline triangle','Play in a circle','Tall solid triangle'],
'musicsettings':['Crisp sliders','Horizontal sliders','Three faders','Sliders with round knobs'],
'settings':['Upright wrench','Diagonal wrench','Rounded cog','Screwdriver'],
'shuffle':['Short tails','Immediate crossing','Curved crossing','Open arrowheads'],
'books':['Open pages','Bold cover','Curved pages','Open book with bookmark'],
'meditation':['Slender candle','Pillar candle','Candle in a dish','Candle with wax drip']}

def outline(p,points,w=1):
    for a,b in zip(points,points[1:]+points[:1]):p.line(*a,*b,w)

def draw(kind,v):
    p=Pixels();i='ABCD'.index(v)
    if kind=='files':
        if i==0:
            outline(p,[(2,3),(7,3),(9,5),(17,5),(17,13),(2,13)])
        elif i==1:
            outline(p,[(2,11),(2,3),(7,3),(9,5),(16,5),(16,7)])
            outline(p,[(4,7),(18,7),(15,13),(2,13)])
        elif i==2:
            outline(p,[(2,5),(2,13),(17,13),(17,5)])
            p.rect(5,2,9,7);p.rect(7,3,5,5,0);p.line(8,5,10,5)
            p.line(2,9,17,9)
        else:
            p.rect(2,5,16,9);p.rect(2,3,6,3);p.rect(3,6,14,1,0)
    elif kind=='library':
        if i==0:
            p.line(3,3,3,13);p.line(6,2,6,13);p.line(9,3,9,13)
            p.rect(12,4,2,7);p.line(12,4,17,3,2);p.rect(16,4,2,7)
            p.circle(11.5,11.5,1.5);p.circle(15.5,10.5,1.5)
        elif i==1:
            outline(p,[(2,3),(13,3),(13,13),(2,13)])
            p.line(5,1,16,1);p.line(16,1,16,11)
            p.circle(7.5,8,3);p.circle(7.5,8,1,0)
        elif i==2:
            for y in (3,7,11):p.rect(2,y,2,2);p.line(7,y,17,y);p.line(7,y+1,14,y+1)
        else:
            p.circle(11,7.5,6);p.circle(11,7.5,4,0);p.circle(11,7.5,1)
            p.line(2,3,2,12);p.line(4,2,4,13)
    elif kind=='play':
        if i in (0,1,3):
            left,right,cy,height=(5,16,7,5) if i<2 else (6,15,7,6)
            for x in range(left,right+1):
                h=round((right-x)*height/(right-left))
                if i==1:
                    p.dot(x,cy-h);p.dot(x,cy+h)
                    if x==left:p.line(x,cy-height,x,cy+height)
                else:p.line(x,cy-h,x,cy+h)
        else:
            p.circle(9.5,7.5,6.4);p.circle(9.5,7.5,5.2,0)
            for x in range(8,14):
                h=(13-x)*3//5;p.line(x,8-h,x,8+h)
    elif kind=='musicsettings':
        if i in (0,2,3):
            for x,y in [(4,5),(10,10),(16,4)]:
                p.line(x,2,x,13)
                if i==0:p.rect(x-2,y-1,5,3);p.dot(x,y,0)
                elif i==2:
                    outline(p,[(x-2,y-1),(x+2,y-1),(x+2,y+2),(x-2,y+2)])
                    p.line(x,3,x,12)
                else:p.circle(x,y,2)
        else:
            for y,x in [(3,7),(8,13),(13,5)]:
                p.line(2,y,17,y);p.rect(x-1,y-1,3,3)
    elif kind=='settings':
        if i==0:
            # Both jaws and the complete handle are inside a generous margin.
            outline(p,[(6,2),(8,2),(8,5),(11,5),(11,2),(13,2),(13,7),(11,9),(11,13),(8,13),(8,9),(6,7)])
            p.line(9,8,9,12)
        elif i==1:
            # Open crescent head, short diagonal handle with a visible end.
            p.circle(12,5,4);p.circle(14,3,3,0)
            p.line(10,8,6,12,2);p.circle(6,12,2);p.dot(6,12,0)
        elif i==2:
            teeth=[]
            for n in range(8):
                for offset,radius in [(-11,4.8),(-11,6.4),(11,6.4),(11,4.8)]:
                    angle=math.radians(n*45+offset)
                    teeth.append((9.5+radius*math.cos(angle),7.5+radius*math.sin(angle)))
            p.poly(teeth);p.circle(9.5,7.5,2.1,0)
        else:
            p.rect(9,2,2,6);p.rect(8,1,4,2)
            outline(p,[(7,8),(12,8),(12,12),(11,14),(8,14),(7,12)])
            p.line(9,9,9,12)
    elif kind=='shuffle':
        # Keep the preferred tight crossing but reduce the two left rails.
        if i==0:points=[[(3,4),(5,4),(12,11),(15,11)],[(3,11),(5,11),(12,4),(15,4)]]
        elif i==1:points=[[(3,3),(13,11),(15,11)],[(3,12),(13,4),(15,4)]]
        elif i==2:points=[[(3,3),(5,3),(7,5),(10,10),(12,12),(15,12)],[(3,12),(5,12),(7,10),(10,5),(12,3),(15,3)]]
        else:points=[[(3,4),(5,4),(12,11),(15,11)],[(3,11),(5,11),(12,4),(15,4)]]
        for path in points:
            for a,b in zip(path,path[1:]):p.line(*a,*b,2 if i!=3 else 1)
        for y in ([3,12] if i==2 else [4,11]):
            if i==3:p.line(14,y-2,17,y);p.line(14,y+2,17,y)
            else:
                for x in range(14,18):
                    h=(17-x)*2//3;p.line(x,y-h,x,y+h)
    elif kind=='books':
        if i in (0,1,3):
            outline(p,[(2,3),(6,3),(9,5),(10,5),(13,3),(17,3),(17,12),(13,12),(10,14),(9,14),(6,12),(2,12)])
            p.line(9,5,9,13);p.line(10,5,10,13)
            if i==1:p.line(2,4,2,12,2);p.line(16,4,16,12,2);p.line(3,13,7,13);p.line(12,13,16,13)
            if i!=3:
                for y in (6,9):p.line(4,y,6,y+1);p.line(13,y+1,15,y)
            else:
                p.rect(13,3,2,5);p.dot(14,7,0)
                p.line(4,6,6,7);p.line(4,9,6,10)
        else:
            outline(p,[(2,3),(5,2),(8,3),(10,5),(12,3),(15,2),(17,3),(17,12),(14,11),(12,12),(10,14),(8,12),(5,11),(2,12)])
            p.line(10,5,10,13)
            p.line(4,5,7,6);p.line(4,8,7,9);p.line(13,6,15,5);p.line(13,9,15,8)
    elif kind=='meditation':
        # Every flame has a point, a separate wick and a recognizable wax body.
        p.dot(10,1);p.line(9,2,10,2);p.line(8,3,11,3);p.line(8,4,11,4);p.line(9,5,10,5)
        p.dot(9,6)
        if i==0:
            outline(p,[(7,7),(12,7),(12,13),(7,13)]);p.line(5,14,14,14)
        elif i==1:
            p.rect(6,7,8,7);p.line(8,8,8,12,1,0);p.line(5,14,14,14)
        elif i==2:
            p.rect(7,7,6,4);p.line(8,8,8,9,1,0)
            p.line(3,11,5,13);p.line(5,13,14,13);p.line(14,13,16,11);p.line(3,11,16,11)
        else:
            outline(p,[(6,7),(13,7),(13,13),(6,13)]);p.line(8,7,8,10);p.line(11,7,11,8);p.line(4,14,15,14)
    rows=p.rows()
    assert rows[0]==rows[-1]=='0'*20,(kind,v,'vertical edge')
    assert all(r[0]==r[-1]=='0' for r in rows),(kind,v,'horizontal edge')
    return rows

def variants():
    return [dict(id=k,variants=[dict(id=v,symbol=NAMES[k][i],pixels=draw(k,v)) for i,v in enumerate('ABCD')]) for k in KINDS]
