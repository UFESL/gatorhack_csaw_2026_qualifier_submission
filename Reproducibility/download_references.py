from pathlib import Path
import urllib.request
import urllib.parse
from html.parser import HTMLParser


class DownloadForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}

    def handle_starttag(self,tag,attrs):
        a = dict(attrs)
        if tag == 'form' and a.get('id') == 'download-form':
            self.action = a.get('action')
        if tag == 'input' and a.get('type') == 'hidden':
            self.fields[a['name']] = a.get('value','')

ROOT = Path(__file__).resolve().parent
URLS = {
    'Password.txt': 'https://drive.google.com/uc?export=download&id=1XYJIy7iUexTy1pYPGV2WKHRTqWgiJBcm',
    'Secret Company Files.zip': 'https://drive.google.com/uc?export=download&id=1PGAn3Lt5VQovrAWoDoqs4TYb11KO0eXT',
    '3DBenchy_reference.stl': 'https://raw.githubusercontent.com/CreativeTools/3DBenchy/master/Single-part/3DBenchy.stl',
}
for name,url in URLS.items():
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=40) as response:
            data = response.read()
            print(name,response.status,response.headers.get('Content-Type'),len(data),flush=True)
        if name.endswith('.zip') and data.lstrip().startswith(b'<!DOCTYPE html>'):
            form = DownloadForm()
            form.feed(data.decode('utf8'))
            assert form.action == 'https://drive.usercontent.google.com/download'
            url = form.action + '?' + urllib.parse.urlencode(form.fields)
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=40) as response:
                data = response.read()
            assert data.startswith(b'PK'), 'Expected a ZIP archive'
            print('Confirmed public ZIP download',len(data),flush=True)
        (ROOT/name).write_bytes(data)
        if name.endswith('.txt'):
            print(data.decode('utf-8'),flush=True)
    except Exception as exc:
        print(name,type(exc).__name__,str(exc),flush=True)
