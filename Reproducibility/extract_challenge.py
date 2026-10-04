"""Open the supplied challenge archive using the answer to its supplied hint."""
from pathlib import Path
import zipfile
import json

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'reference_files'
OUT.mkdir(exist_ok=True)
with zipfile.ZipFile(ROOT/'Secret Company Files.zip') as archive:
    print(json.dumps([{'name':x.filename,'size':x.file_size,'flags':x.flag_bits,'compression':x.compress_type} for x in archive.infolist()],indent=2))
    # Accepted answer to the supplied conference-name hint, established during
    # analysis. This is a challenge reference archive, not an account credential.
    password = b'CSAW26'
    print('Conference-name hint answer: CSAW26')
    for item in archive.infolist():
        target = (OUT/item.filename).resolve()
        assert target.is_relative_to(OUT.resolve()), 'Unsafe archive path'
        if item.is_dir():
            target.mkdir(exist_ok=True,parents=True)
            continue
        data = archive.read(item,pwd=password)
        target.parent.mkdir(exist_ok=True,parents=True)
        target.write_bytes(data)
        print('Extracted',item.filename,len(data))
