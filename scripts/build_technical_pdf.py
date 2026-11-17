"""Build the technical reference PDF from the versioned manuscript and evidence."""
import html
import json
import re
import textwrap
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image, Preformatted, KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/pdf/Policy_Desk_Technical_Document.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
FONT = Path('C:/Windows/Fonts')
for name, file in [('Body','segoeui.ttf'),('Bold','segoeuib.ttf'),('Mono','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Body',boldItalic='Bold')
GREEN=colors.HexColor('#176A58'); INK=colors.HexColor('#172C37'); MUTED=colors.HexColor('#61746E'); PALE=colors.HexColor('#E8F0EC')
W,H=A4; CW=W-100
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyCopy',fontName='Body',fontSize=10,leading=15,spaceAfter=9,textColor=INK))
styles.add(ParagraphStyle(name='Chapter',fontName='Bold',fontSize=19,leading=25,spaceAfter=20,textColor=GREEN,keepWithNext=True))
styles.add(ParagraphStyle(name='Subhead',fontName='Bold',fontSize=12,leading=17,spaceBefore=12,spaceAfter=8,textColor=INK,keepWithNext=True))
styles.add(ParagraphStyle(name='Cell',fontName='Body',fontSize=8,leading=11,textColor=INK,wordWrap='CJK'))
styles.add(ParagraphStyle(name='CellHead',parent=styles['Cell'],fontName='Bold',textColor=colors.white))
styles.add(ParagraphStyle(name='Caption',fontName='Body',fontSize=8,leading=11,spaceBefore=7,spaceAfter=15,textColor=MUTED))
styles.add(ParagraphStyle(name='CodeBlock',fontName='Mono',fontSize=8,leading=11,backColor=colors.HexColor('#F1F4F3'),borderPadding=10,spaceBefore=8,spaceAfter=15))

def clean(s):
    return s.replace('\u2011','-').replace('\u2013','-').replace('\u2014','-').replace('\u2192',' -> ')

def rich(s):
    s=html.escape(clean(s))
    s=re.sub(r'`([^`]+)`',r'<font name="Mono">\1</font>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
    return s

def para(s,style='BodyCopy'):
    return Paragraph(rich(s),styles[style])

def table(rows,widths=None):
    n=len(rows[0]); widths=widths or ([CW/n]*n)
    data=[[para(str(v),'CellHead' if i==0 else 'Cell') for v in row] for i,row in enumerate(rows)]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),GREEN),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F2F6F4')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,GREEN),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#DCE3E1'))]))
    return [KeepTogether([t]) if len(rows)<=9 else t,Spacer(1,14)]

def box(d,x,y,w,h,title,sub=''):
    d.add(Rect(x,y,w,h,rx=7,ry=7,fillColor=PALE,strokeColor=GREEN,strokeWidth=.7))
    d.add(String(x+w/2,y+h/2+4 if sub else y+h/2-3,title,fontName='Bold',fontSize=10,textAnchor='middle',fillColor=INK))
    if sub:d.add(String(x+w/2,y+12,sub,fontName='Body',fontSize=8,textAnchor='middle',fillColor=MUTED))

def arrow(d,x1,y1,x2,y2):
    d.add(Line(x1,y1,x2,y2,strokeColor=GREEN,strokeWidth=1))
    import math
    angle=math.atan2(y2-y1,x2-x1);size=5
    points=[x2,y2,x2-size*math.cos(angle-.5),y2-size*math.sin(angle-.5),x2-size*math.cos(angle+.5),y2-size*math.sin(angle+.5)]
    d.add(Polygon(points,fillColor=GREEN,strokeColor=GREEN))

def architecture():
    d=Drawing(CW,295)
    box(d,150,240,195,45,'Browser workspace','Hospital Staff / Claims Reviewer')
    box(d,150,170,195,45,'FastAPI','Sessions, validation, cases, review')
    box(d,0,90,145,48,'PostgreSQL','Durable cases, runs and history')
    box(d,175,90,145,48,'Redis / ARQ','Bounded queue and global locks')
    box(d,350,90,145,48,'Telemetry','Prometheus / Grafana / Jaeger')
    box(d,80,0,155,52,'Processing worker','Graph + FAISS / BM25 / MiniLM')
    box(d,280,0,155,52,'Windows Ollama','Qwen3 4B / one inference slot')
    arrow(d,247,240,247,215);arrow(d,195,170,75,138);arrow(d,247,170,247,138);arrow(d,345,190,422,138);arrow(d,230,90,160,52);arrow(d,235,25,280,25)
    return [d,para('Figure 1. Logical component boundaries in the active Windows/WSL profile. Host Ollama is outside the container stack.','Caption')]

def workflow():
    d=Drawing(CW,245)
    for y,title,sub in [(195,'Hospital submits a case','Revision + durable processing run'),(125,'Research, verify and assess','Policy evidence + structured AI recommendation'),(55,'Evaluate guarded precedent reuse','Human authorization, exact facts, semantic match')]:
        box(d,90,y,315,40,title,sub)
    arrow(d,247,195,247,165);arrow(d,247,125,247,95)
    box(d,0,0,215,35,'Human review / clarification');box(d,280,0,215,35,'Precedent-based final decision')
    arrow(d,170,55,110,35);arrow(d,330,55,390,35)
    return [d,para('Figure 2. First-time and exceptional cases reach a reviewer; only eligible equivalent cases can reuse human authority.','Caption')]

def chart():
    d=Drawing(CW,215); x0=48;y0=35; plotw=410;ph=150
    for value in [0,10,20,30,40,50]:
        y=y0+value/50*ph;d.add(Line(x0,y,x0+plotw,y,strokeColor=colors.HexColor('#DCE3E1')));d.add(String(x0-8,y-3,str(value),fontName='Body',fontSize=8,textAnchor='end'))
    for i,(users,p95) in enumerate([(2,7.1),(4,10),(8,23),(16,47)]):
        x=x0+25+i*100;bh=p95/50*ph
        d.add(Rect(x,y0,52,bh,fillColor=GREEN if users<16 else colors.HexColor('#B56837'),strokeColor=None))
        d.add(String(x+26,y0+bh+6,str(p95)+'s',fontName='Bold',fontSize=9,textAnchor='middle'))
        d.add(String(x+26,17,str(users)+' users',fontName='Body',fontSize=9,textAnchor='middle'))
    d.add(Line(x0,y0+90,x0+plotw,y0+90,strokeColor=colors.HexColor('#B56837'),strokeDashArray=[4,3]))
    d.add(String(485, y0+94,'30s target',fontName='Body',fontSize=8,textAnchor='end',fillColor=colors.HexColor('#B56837')))
    d.add(String(x0,202,'Machine-assessment p95 (seconds)',fontName='Bold',fontSize=10,fillColor=INK))
    return [d,para('Figure 3. Single-worker real-model p95 by workload. Sixteen users miss the target despite only a small throughput increase.','Caption')]

def data_table(kind):
    base=ROOT/'loadtest/results/desk'
    if kind=='loadtable':
        rows=[['Users / workers','N / errors','p50 s','p95 s','p99 s','Assess/s']]
        for users in [2,4,8,16]:
            r=json.loads((base/'2026-11-17-freed'/f'workers1-users{users}.json').read_text());a=r['assessment']
            rows.append([f'{users} / 1',f"{a['Request Count']} / {a['Failure Count']}",*[f'{float(a[k])/1000:g}' for k in ['50%','95%','99%']],f"{float(a['Requests/s']):.3f}"])
        return table(rows,[100,85,65,65,65,CW-380])
    rows=[['Phase','N','p50 s','p95 s','p99 s']]
    for r in json.loads((base/'2026-11-17-soak5/workers1-soak-phases.json').read_text())['phases']:
        rows.append([r['phase'].replace('_seconds','').replace('_',' '),str(r['observations']),*[f'{r[k]:.4f}' for k in ['p50_seconds','p95_seconds','p99_seconds']]])
    return table(rows,[195,45,85,85,CW-410])

def figure(path,caption):
    im=Image(str(ROOT/path)); scale=min(CW/im.imageWidth,390/im.imageHeight)
    im.drawWidth=im.imageWidth*scale;im.drawHeight=im.imageHeight*scale
    return [im,para(caption,'Caption')]

class Doc(BaseDocTemplate):
    def __init__(self):
        super().__init__(str(OUT),pagesize=A4,leftMargin=50,rightMargin=50,topMargin=58,bottomMargin=52,title='Policy Desk - Technical Design and Evaluation',author='Policy Desk project',pageCompression=1)
        self.addPageTemplates(PageTemplate(id='main',frames=Frame(50,52,CW,H-110,id='body',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0),onPage=self.decorate))
    def decorate(self,canvas,doc):
        canvas.saveState()
        if doc.page>1:
            canvas.setFont('Bold',8);canvas.setFillColor(GREEN);canvas.drawString(50,H-31,'POLICY DESK / TECHNICAL REFERENCE')
            canvas.setStrokeColor(colors.HexColor('#DCE3E1'));canvas.line(50,H-39,W-50,H-39)
        canvas.setFont('Body',8);canvas.setFillColor(MUTED);canvas.drawString(50,29,'17 November 2026  |  Synthetic demonstration  |  Version 1.0');canvas.drawRightString(W-50,29,str(doc.page));canvas.restoreState()
    def afterFlowable(self,f):
        if isinstance(f,Paragraph) and f.style.name=='Chapter' and f.getPlainText()!='Contents':
            key='chapter-'+str(self.seq.nextf('chapter'));self.canv.bookmarkPage(key);self.canv.addOutlineEntry(f.getPlainText(),key,0,False);self.notify('TOCEntry',(0,f.getPlainText(),self.page,key))

def build():
    story=[Spacer(1,85),Paragraph('POLICY DESK',ParagraphStyle('kicker',fontName='Bold',fontSize=13,textColor=GREEN,spaceAfter=24)),Paragraph('Health Insurance<br/>Pre-Authorisation Desk',ParagraphStyle('cover',fontName='Bold',fontSize=34,leading=43,textColor=INK,spaceAfter=28)),Paragraph('Technical design, implementation<br/>and measured evaluation',ParagraphStyle('subtitle',fontName='Body',fontSize=18,leading=27,textColor=MUTED,spaceAfter=35)),para('Hospital Staff  /  Claims Reviewer  /  Local AI'),Spacer(1,28),para('Version 1.0 | 17 November 2026'),para('A source-grounded reference to the implemented internal workspace, its operating procedures, verification evidence and measured limits.'),Spacer(1,35),table([['DOCUMENT BOUNDARY'],['Synthetic demonstration only. The five-minute stability run is not long-duration reliability evidence. Real clinical or insurer use has not been validated.']])[0],PageBreak(),para('Contents','Chapter')]
    toc=TableOfContents();toc.levelStyles=[ParagraphStyle('toc',fontName='Body',fontSize=9,leading=13,spaceBefore=4,textColor=INK)];story+=[toc]
    lines=(ROOT/'docs/TECHNICAL_DOCUMENT.md').read_text(encoding='utf-8').splitlines();i=0
    while i<len(lines) and not lines[i].startswith('## '):i+=1
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('## '):
            title=line[3:]
            start_page=bool(re.match(r'^(1|6|10|16|20)\.',title)) or title.startswith('Appendix')
            story.extend([PageBreak() if start_page else Spacer(1,18),para(title,'Chapter')]);i+=1;continue
        if line.startswith('### '):story.append(para(line[4:],'Subhead'));i+=1;continue
        if line.startswith('```'):
            code=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):
                code.extend(textwrap.wrap(clean(lines[i]),width=92,replace_whitespace=False,drop_whitespace=False) or ['']);i+=1
            story.append(Preformatted('\n'.join(code),styles['CodeBlock']));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+',x) for x in row):rows.append(row)
                i+=1
            widths=None
            if len(rows[0])==3:widths=[CW*.25,CW*.38,CW*.37]
            story.extend(table(rows,widths));continue
        if line.startswith('[['):
            kind=line.strip('[]')
            if kind=='architecture':story.extend(architecture())
            elif kind=='workflow':story.extend(workflow())
            elif kind=='latencychart':story.extend(chart())
            elif kind in ['loadtable','phasetable']:story.extend(data_table(kind))
            elif kind=='loginimage':story.extend(figure('docs/evidence/demo-login.png','Figure 4. Verified role shortcuts on the sign-in page.'))
            elif kind=='reviewerimage':
                story.extend(figure('docs/evidence/reviewer-suggestion-approved.png','Figure 6. Reviewer summary and human decision assistance; interface overview.'))
                evidence=json.loads((ROOT/'docs/evidence/reviewer-suggestion.json').read_text())
                story.append(para('Verified display example: '+evidence['cases'][0]['summary']))
            elif kind=='sampleimage':story.extend(figure('docs/evidence/sample-claim.png','Figure 5. Sample hospital request form; refer to Chapter 5 for field-level constraints.'))
            i+=1;continue
        parts=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```','[[')):
            parts.append(lines[i].strip());i+=1
        story.append(para(' '.join(parts)))
    Doc().multiBuild(story)
    print(OUT)

if __name__=='__main__':build()
