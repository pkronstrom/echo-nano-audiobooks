"""Focused round-five artwork; accepted round-four selections are immutable."""
from icon_proposals import Pixels
from icon_proposals_v3 import outline, KINDS
from icon_proposals_v4 import draw as previous, bitmap

KEPT = {'library': ('C','Alternating lengths'), 'play': ('B','Compact soft play'),
        'shuffle': ('D','Open arrowheads'), 'meditation': ('A','Body one pixel slimmer')}
NAMES = {'files': ['Rounded outline folder', 'Rounded outline with seam', 'Soft open folder', 'Rounded heavy outline'],
         'musicsettings': ['Fine knobs · equal outer padding'],
         'books': ['Rounded spread · mirrored pages'],
         'settings': ['Compact cog', 'Broad cog', 'Diagonal open wrench', 'Horizontal open wrench']}

def draw(kind, variant):
    if kind in KEPT: return previous(kind, KEPT[kind][0])
    p=Pixels(); i='ABCD'.index(variant)
    if kind=='files':
        outline(p,[(3,3),(7,3),(9,5),(16,5),(17,6),(17,12),(16,13),(3,13),(2,12),(2,4)])
        if i==1: p.line(3,7,16,7)
        elif i==2:
            p.rect(2,8,16,6,0)
            outline(p,[(5,7),(17,7),(18,8),(15,13),(3,13),(2,12),(4,8)])
        elif i==3:
            p.line(3,5,3,11);p.line(16,7,16,11);p.line(4,12,15,12)
    elif kind=='musicsettings':
        # 3 pixels of clear space on both sides. Keep the fine 3x2 knobs.
        for x,y in [(4,5),(10,10),(15,4)]:
            p.line(x,2,x,13);p.rect(x-1,y-1,3,2)
    elif kind=='books':
        source=previous('books','C')
        for y,row in enumerate(source):
            for x in range(10):
                if row[x]=='1':p.dot(x,y);p.dot(19-x,y)
        p.line(9,5,9,13);p.line(10,5,10,13)
    elif kind=='settings':
        if i==0:
            bitmap(p,[
                '.....##.....','..#..##..#..','..########..','...######...',
                '..##....##..','####....####','####....####','..##....##..',
                '...######...','..########..','..#..##..#..','.....##.....'],4,2)
        elif i==1:
            bitmap(p,[
                '......##......','...#..##..#...','..##########..','..###....###..',
                '..##......##..','..##......##..','####......####','####......####',
                '..##......##..','..##......##..','..###....###..','..##########..',
                '...#..##..#...','......##......'],3,1)
        elif i==2:
            # Classic open-ended head with a diagonal shaft and pierced end.
            p.poly([(11,2),(14,1),(12,4),(14,6),(17,3),(17,6),(15,8),(12,8),
                    (7,13),(4,13),(3,12),(3,10),(9,5),(9,3)])
            p.dot(5,11,0)
        else:
            # Horizontal spanner: wide jaws, recessed mouth, straight shaft.
            p.poly([(3,3),(7,3),(7,5),(4,5),(4,9),(7,9),(7,11),(3,11),(1,9),(1,5)])
            p.rect(6,6,10,3);p.rect(15,5,3,5);p.dot(16,7,0)
    rows=p.rows()
    assert rows[0]==rows[-1]=='0'*20,(kind,variant)
    assert all(r[0]==r[-1]=='0' for r in rows),(kind,variant)
    return rows

def variants():
    result=[]
    for kind in KINDS:
        if kind in KEPT:
            letter,name=KEPT[kind]; opts=[dict(id=letter,symbol=name+' · approved v4',pixels=draw(kind,letter))]
        else: opts=[dict(id='ABCD'[i],symbol=name,pixels=draw(kind,'ABCD'[i])) for i,name in enumerate(NAMES[kind])]
        result.append(dict(id=kind,variants=opts))
    return result
