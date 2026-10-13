"""Round four: focused refinements; approved shuffle retained byte-for-byte."""
from icon_proposals import Pixels
from icon_proposals_v3 import draw as previous, outline, KINDS

NAMES = {
    'files': ['Solid tab', 'Solid with lid seam', 'Rounded solid folder', 'Open solid folder'],
    'library': ['Even list', 'Compact list', 'Alternating lengths', 'Outlined bullets'],
    'play': ['Soft tall play', 'Compact soft play', 'Broad soft play', 'Trimmed corners'],
    'musicsettings': ['Knobs one pixel shorter', 'Knobs one pixel narrower', 'Shorter and narrower', 'Fine three-pixel knobs'],
    'settings': ['Block-tooth cog', 'Fine cog', 'Simple open wrench', 'Adjustment switches'],
    'shuffle': ['Open arrowheads · approved v3 D'],
    'books': ['Gentle curved pages', 'Curved pages without text', 'Rounded spread', 'Curved pages with cover'],
    'meditation': ['Body one pixel slimmer', 'Slim body and base', 'Slim body and flame', 'Slim filled wax'],
}

def bitmap(p, rows, x, y):
    for dy, row in enumerate(rows):
        for dx, bit in enumerate(row):
            if bit == '#': p.dot(x+dx, y+dy)

def draw(kind, v):
    p = Pixels(); i = 'ABCD'.index(v)
    if kind == 'shuffle': return previous('shuffle', 'D')
    if kind == 'files':
        p.rect(2,5,16,9); p.rect(2,3,6,3)
        if i == 1: p.rect(3,6,14,1,0)
        if i == 2:
            for x,y in [(2,3),(2,13),(17,5),(17,13)]: p.dot(x,y,0)
            p.dot(8,4)
        if i == 3:
            p.rect(2,6,16,8,0)
            p.poly([(5,7),(18,7),(15,14),(2,14)])
            p.line(3,6,16,6,1,0)
    elif kind == 'library':
        for n,y in enumerate((3,7,11)):
            if i == 3:
                outline(p,[(2,y),(4,y),(4,y+2),(2,y+2)])
                p.rect(7,y+1,11,1)
            else:
                p.rect(2,y,2,2)
                width = 11 if i == 0 else (9 if i == 1 else [11,8,10][n])
                p.rect(7,y,width,1 if i == 1 else 2)
    elif kind == 'play':
        # Row-designed wedges avoid both a long needle tip and a flat cutoff.
        shapes = [
            ['#','###','#####','######','########','#########','##########','#########','########','######','#####','###','#'],
            ['##','####','#####','#######','########','#########','########','#######','#####','####','##'],
            ['##','####','######','########','##########','###########','##########','########','######','####','##'],
            ['##','####','######','########','#########','#########','########','######','####','##'],
        ]
        rows = shapes[i]
        bitmap(p, rows, 6 if i < 2 else 5, 1 if i == 0 else 2)
        if i in (0,1,3):
            # Set the top/bottom corners inward to soften the upright edge.
            p.dot(6 if i<2 else 5,1 if i==0 else 2,0)
            p.dot(6 if i<2 else 5,(1 if i==0 else 2)+len(rows)-1,0)
            if i==0: p.dot(7,2); p.dot(7,12)
    elif kind == 'musicsettings':
        for x,y in [(4,5),(10,10),(16,4)]:
            p.line(x,2,x,13)
            w,h = [(5,2),(4,3),(4,2),(3,2)][i]
            p.rect(x-2 if w>=4 else x-1,y-1,w,h)
    elif kind == 'settings':
        if i < 2:
            rows = [
                '.....####.....', '.....####.....', '..##.####.##..', '..##########..',
                '...########...', '######..######', '#####....#####', '#####....#####',
                '######..######', '...########...', '..##########..', '..##.####.##..',
                '.....####.....', '.....####.....',
            ]
            bitmap(p, rows, 3, 1)
            if i == 1:
                # Larger aperture gives the teeth and hub a lighter silhouette.
                p.rect(8,5,4,6,0); p.rect(7,6,6,4,0)
        elif i == 2:
            bitmap(p, ['##....##','##....##','##....##','########','########','..####..','...##...','...##...','...##...','...##...','...##...','..####..','..####..'],6,1)
        else:
            for y,x in [(4,6),(10,13)]:
                outline(p,[(2,y-2),(17,y-2),(17,y+2),(2,y+2)])
                p.rect(x-1,y-1,3,3)
    elif kind == 'books':
        if i < 2:
            points=[(2,3),(5,2),(8,3),(10,5),(12,3),(15,2),(17,3),(17,12),(14,11),(12,12),(10,14),(8,12),(5,11),(2,12)]
        else:
            points=[(2,4),(3,3),(6,3),(9,4),(10,5),(11,4),(14,3),(16,3),(17,4),(17,12),(14,12),(11,13),(10,14),(9,13),(6,12),(2,12)]
        outline(p,points); p.line(10,5,10,13)
        if i != 1:
            for y in (6,9):
                p.line(4,y,6,y); p.dot(7,y+1)
                p.line(14,y,15,y); p.dot(13,y+1)
        if i == 3: p.line(2,13,6,13);p.line(14,13,17,13)
    elif kind == 'meditation':
        p.dot(10,1);p.line(9,2,10,2);p.line(8,3,11,3);p.line(8,4,11,4);p.line(9,5,10,5);p.dot(9,6)
        outline(p,[(6,7),(12,7),(12,13),(6,13)])
        p.line(8,7,8,10);p.line(11,7,11,8)
        p.line(4 if i==0 else 5,14,15 if i==0 else 14,14)
        if i==2:
            p.dot(8,3,0);p.dot(8,4,0)
        if i==3:
            p.rect(7,8,5,5);p.line(8,8,8,10,1,0);p.dot(11,8,0)
    rows=p.rows()
    assert rows[0]==rows[-1]=='0'*20,(kind,v)
    assert all(r[0]==r[-1]=='0' for r in rows),(kind,v)
    return rows

def variants():
    return [dict(id=k,variants=[dict(id=v,symbol=NAMES[k][i],pixels=draw(k,v))
            for i,v in enumerate('D' if k=='shuffle' else 'ABCD')]) for k in KINDS]
