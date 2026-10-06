"""Change only PPTH bytes; preserve unknown tags and obfuscated PSSI verbatim."""
import struct
from ..core.models import PlanningError


def tags(data):
    if not 28<=len(data)<=32*1024*1024 or data[:4]!=b'PMAI':raise PlanningError('Cabecera ANLZ inválida')
    header,total=struct.unpack_from('>II',data,4)
    if not 28<=header<=len(data) or total!=len(data):raise PlanningError('Longitud ANLZ inválida')
    offset=header;result=[]
    while offset<len(data):
        if offset+12>len(data):raise PlanningError('Tag ANLZ truncado')
        h,n=struct.unpack_from('>II',data,offset+4)
        if not 12<=h<=n or offset+n>len(data):raise PlanningError('Longitud de tag ANLZ inválida')
        result.append((data[offset:offset+4],data[offset:offset+n]));offset+=n
    return header,result


def relocate(data,path):
    if not isinstance(path,str) or not path.startswith('/') or '\0' in path:raise PlanningError('Ruta ANLZ inválida')
    header,rows=tags(data);encoded=path.encode('utf-16-be')+b'\0\0';out=[];changed=0
    for kind,raw in rows:
        if kind==b'PPTH':
            if int.from_bytes(raw[4:8],'big')!=16:raise PlanningError('PPTH no compatible')
            out.append(b'PPTH'+struct.pack('>III',16,16+len(encoded),len(encoded))+encoded);changed+=1
        else:out.append(raw)
    if not changed:raise PlanningError('ANLZ sin ruta PPTH; no se puede exportar con seguridad')
    result=bytearray(data[:header]+b''.join(out));struct.pack_into('>I',result,8,len(result))
    _,check=tags(result)
    if [bytes(v) for k,v in check if k!=b'PPTH'] != [v for k,v in rows if k!=b'PPTH']:
        raise PlanningError('Se alteró análisis fuera de la ruta')
    return bytes(result)
