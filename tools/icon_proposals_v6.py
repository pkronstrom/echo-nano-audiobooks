"""Round six: settings only, with seven accepted icons retained exactly."""
from icon_proposals import Pixels
from icon_proposals_v4 import bitmap
from icon_proposals_v5 import draw as previous

KEPT = {'files':('B','Rounded outline with seam'),
        'library':('C','Alternating lengths'), 'play':('B','Compact soft play'),
        'musicsettings':('A','Fine knobs · equal outer padding'),
        'shuffle':('D','Open arrowheads'), 'books':('A','Rounded spread · mirrored pages'),
        'meditation':('A','Body one pixel slimmer')}
NAMES=['Eight-tooth cog','Fine eight-tooth cog','Slim upright wrench','Slim horizontal wrench']

def draw(kind,letter):
    if kind in KEPT:return previous(kind,KEPT[kind][0])
    p=Pixels();i='ABCD'.index(letter)
    if i<2:
        # A circular hub and eight short rectangular teeth, not pointed lobes.
        p.circle(9.5,7.5,4.8)
        for x,y,w,h in [(9,1,2,3),(9,12,2,3),(3,7,3,2),(14,7,3,2),
                         (5,3,2,2),(13,3,2,2),(5,11,2,2),(13,11,2,2)]:p.rect(x,y,w,h)
        p.circle(9.5,7.5,2.1 if i==0 else 3.0,0)
    elif i==2:
        bitmap(p,[
            '.#....#.','##....##','##....##','.##..##.',
            '..####..','...##...','...##...','...##...',
            '...##...','...##...','...##...','..####..',
            '..#..#..','..####..'],6,1)
    else:
        # Open mouth faces away from the shaft; exact top/bottom reflection.
        p.circle(5,7.5,4.5);p.circle(5,7.5,2.5,0)
        p.rect(1,5,5,6,0)
        p.rect(8,7,9,2)
        p.circle(16,7.5,2.1);p.circle(16,7.5,0.6,0)
    rows=p.rows()
    assert rows[0]==rows[-1]=='0'*20
    assert all(r[0]==r[-1]=='0' for r in rows)
    if i<3:assert all(r==r[::-1] for r in rows)
    if i in (0,1,3):assert rows==rows[::-1]
    return rows

def variants():
    groups=[dict(id='settings',variants=[dict(id=v,symbol=NAMES[i],pixels=draw('settings',v)) for i,v in enumerate('ABCD')])]
    for k,(v,name) in KEPT.items():groups.append(dict(id=k,variants=[dict(id=v,symbol=name+' · approved',pixels=draw(k,v))]))
    return groups
