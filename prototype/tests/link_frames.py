from egobits.telemetry.prodj_link import MAGIC

def simulated_status(player=1, track_id=42, on_air=True):
    """Synthetic documented frame; never claims to be a recording of hardware."""
    data = bytearray(0xd4);data[:10]=MAGIC;data[10]=0x0a;data[12:20]=b'CDJ-TEST'
    data[0x21]=player;data[0x22:0x24]=(len(data)-0x24).to_bytes(2,'big')
    data[0x28]=player;data[0x29]=3;data[0x2a]=1;data[0x2c:0x30]=track_id.to_bytes(4,'big')
    data[0x7b]=3;data[0x89]=0x40 | (8 if on_air else 0);data[0x8d:0x90]=(0x100000).to_bytes(3,'big')
    data[0x92:0x94]=(12800).to_bytes(2,'big');data[0xa0:0xa4]=(129).to_bytes(4,'big');data[0xa6]=1
    return bytes(data)
