"""Create only synthetic audio/XML, in a new isolated fixture directory."""
import hashlib
import json
import math
from pathlib import Path
import struct
import wave
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / 'output/closure/bridge-fixture-v2'
    target.mkdir(parents=True, exist_ok=False)
    root = ET.Element('DJ_PLAYLISTS', Version='1.0.0')
    ET.SubElement(root, 'PRODUCT', Name='EgoBits synthetic QA', Version='1', Company='EgoBits')
    collection = ET.SubElement(root, 'COLLECTION', Entries='3')
    playlist_root = ET.SubElement(ET.SubElement(root, 'PLAYLISTS'), 'NODE', Name='ROOT', Type='0', Count='1')
    playlist = ET.SubElement(playlist_root, 'NODE', Name='Ensayo', Type='1', KeyType='0', Entries='3')
    hashes = {}
    for number, title in enumerate(['Peña & Percusión', 'Noche 東京', 'Último <ritmo>'], 1):
        # Windows filenames cannot contain angle brackets; metadata deliberately can.
        filename = ['01 Peña & Percusión.wav', '02 Noche 東京.wav', '03 Último ritmo.wav'][number - 1]
        path = target / filename
        with wave.open(str(path), 'wb') as audio:
            audio.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
            audio.writeframes(b''.join(struct.pack('<h', int(1800 * math.sin(2 * math.pi * (220 + 55 * number) * i / 44100))) for i in range(8 * 44100)))
        uri = path.as_uri().replace('file:///', 'file://localhost/', 1)
        track = ET.SubElement(collection, 'TRACK', TrackID=str(number), Name=title, Artist=f'EgoBits ensayo ñ {number}',
            Genre='Test', AverageBpm=str(118 + number * 2), Tonality='Am', TotalTime='8',
            Kind='WAV File', Size=str(path.stat().st_size), SampleRate='44100', BitRate='705', Location=uri)
        ET.SubElement(track, 'TEMPO', Inizio='0', Bpm=str(118 + number * 2), Metro='4/4', Battito='1')
        ET.SubElement(track, 'POSITION_MARK', Name='Entrada ñ 東京', Type='0', Start='1.5', Num='0')
        ET.SubElement(playlist, 'TRACK', Key=str(number))
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    ET.ElementTree(root).write(target / 'template.xml', encoding='utf-8', xml_declaration=True)
    hashes['template.xml'] = hashlib.sha256((target / 'template.xml').read_bytes()).hexdigest()
    (target / 'fixture-hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
