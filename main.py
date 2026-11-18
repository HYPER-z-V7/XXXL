# -*- coding: utf-8 -*-
# main.py — RAIX CS GLORY FARMER (short, headless)
# শুধু CLASH SQUAD(8) • RAIX-XXXXXX • clan join • auto-create • self-heal
import sys, os, json, time, uuid, random, asyncio, ssl, struct, socket, itertools, base64, hmac, hashlib, logging
from datetime import datetime
import aiohttp, aiohttp.web, httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser
from message_ids import MESSAGE_ID_TO_NAME
import thunderFF_pb2
try: import reqClan_pb2
except Exception: reqClan_pb2 = None

for _l in ("aiohttp.client","aiohttp.connector","asyncio"):
    logging.getLogger(_l).setLevel(logging.CRITICAL)

# ───────── config ─────────
DATA = os.environ.get("DATA_DIR", ".").rstrip("/") or "."
ACC_FILE = os.path.join(DATA, "accounts.json")
PASS = os.environ.get("FF_PASSWORD", "RAI X")
PREFIX = os.environ.get("FF_NICK_PREFIX", "RAIX")
CLAN = os.environ.get("CLAN_ID", "3033431593").strip()
TARGET = int(os.environ.get("TARGET_ACCOUNTS", "0"))
PORT = int(os.environ.get("PORT", 8080))
SEARCH_TO = float(os.environ.get("CS_SEARCH_TIMEOUT", "90"))
START_TO = float(os.environ.get("CS_STARTUP_TIMEOUT", "22"))
MAPS = [int(x) for x in os.environ.get("FF_MAPS", "1,2,3").split(",") if x.strip()] or [1]
MODE = 8
MAX_MATCH = int(os.environ.get("MAX_MATCHES", "2"))
CLAN_HOSTS = ["https://clientbp.ppmainecoonghj.com", "https://loginbp.ppmainecoonghj.com",
              "https://client.ind.freefiremobile.com"]
REGION = os.environ.get("FF_REGION", "BD").upper()
_mp = 0
def cur_map(): return MAPS[_mp % len(MAPS)]
def next_map():
    global _mp; _mp = (_mp + 1) % len(MAPS); return cur_map()

AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
KEYSTREAM = bytes([0x30,0x30,0x30,0x32,0x30,0x31,0x37]+[0x30]*8+[0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30])
REG_LANG = {"BD":"bn","IND":"hi","ID":"id","PK":"ur","ME":"ar","BR":"pt","US":"pt"}
GGRE = bytes.fromhex("47475245010101006d020000b260ee08e1f86b4c57f9c70f86bba26ed5d1436bcf52e142db3249d905eded757764991ca31a8373cdd26eab91b80f3f1f6f262f4f10b895d7b6937ddba30a27197453890e9da49373f736c679b8254e2f8e1623e91084a5fdd5374fe478ff99e010834553fddeb0bec4018d142e49df9bb236675b67e852f92a43586f7a7d4d0d7a197a1d4da32714dab4d069ad53214e2c33b3877420a12459738c4c619cbd815fa878bbd104776bb3e1ac7818d5397b04a666ac57f682763ff2df31bc2f846ddc7904f3dce1bda0c4b01f9698e9166f98c84f92640abe3f6317834a42e5c12573b46842c1a6ea8fe6ca9c006dca48a2087e1f983dfb5692771e4a0b15b337ad669b1d08b40862b176bace5331b49a767375b1a8469012aa70a67b55fe71b72478201d0b3ac7269c064c960361e92ee7ba8a42cc6b582bf9b965fb388fa9172ad44c4b073ac23c02080a6bcd106b691ffdf4c7cf71e42f2063fcf196e9bddc5e85be1fe5048eb1b31b460efbb46d76195eef9904c4cba326f2e17ff51fec17dd965aa06dadd4ab07d6966e4a7c38e8afd66dfde56c872bb87516a8f7313c797e4d80e5ad4a5f7afad95c1e0449254adae052e71a3fb98399f93ab30848e0d23252dd45e6fd41bc5fa7303dfb846a8fd713a0032a0b0ae96dfba1bbe41d20abd8099e2cb7fccc329d25bd153029139ef05d090a5093ea557693c0a8d491395b8a23ca844b3887dd5dfc29ac06f4b9be87883a793211b973465e2644c4f5de02b8ab01571401203fc2740423826858cc6da0194c195d27aac4ec4b9d23d506c1501d06440aca3fc180926d75d4a004d3dff21eb4ea1e8c86e6c9627248eff953e1d192d5c8efc006a7e512388ef2ebdb72ee3ad42d719f28e8f994e12ebf4c79f2ffe3abd7408ccd2236a7b89b2606247a732c10c4")

# ───────── state ─────────
ACC, AD, TASKS, PAUSED, WRITERS = {}, {}, {}, set(), {}
LOG, STAT = [], {"in_game":0,"start_fail":0,"search_fail":0,"joined":0,"fail":0,"matches":0}
START_T = time.time()
CLAN_ST, DEAD, HOSTC = {}, {}, {}
TEAMS = {}

def log(m, lv="i"):
    t = datetime.now().strftime("%H:%M:%S")
    LOG.append({"t":t,"m":str(m),"lv":lv}); LOG[:] = LOG[-300:]
    print(f"[{t}] {'+-x!'['iws e'.find(lv[0]) if lv[0] in 'iws e' else 0] if False else ''}[{lv}] {m}")

def _mode(lv): return MODE

# ───────── proto ─────────
def ev(n):
    if n < 0: n &= 0xFFFFFFFFFFFFFFFF
    o = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        o.append(b | (0x80 if n else 0))
        if not n: return bytes(o)

def proto(d):
    p = bytearray()
    for f, v in d.items():
        f = int(f)
        if isinstance(v, dict): p += ev((f<<3)|2) + ev(len(x:=proto(v))) + x
        elif isinstance(v, list):
            for i in v:
                if isinstance(i, dict): p += ev((f<<3)|2) + ev(len(x:=proto(i))) + x
                elif isinstance(i, (bytes, bytearray)): p += ev((f<<3)|2) + ev(len(i)) + bytes(i)
                elif isinstance(i, int): p += ev((f<<3)|0) + ev(i)
        elif isinstance(v, bool): p += ev((f<<3)|0) + ev(int(v))
        elif isinstance(v, int): p += ev((f<<3)|0) + ev(v)
        elif isinstance(v, str): b = v.encode(); p += ev((f<<3)|2) + ev(len(b)) + b
        elif isinstance(v, (bytes, bytearray)): p += ev((f<<3)|2) + ev(len(v)) + bytes(v)
    return bytes(p)

def enc_aes(h): return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(bytes.fromhex(h), 16)).hex()
def dvi(d, o):
    r = s = 0
    while o < len(d):
        b = d[o]; r |= (b & 0x7F) << s; o += 1
        if not b & 0x80: return r, o
        s += 7
    return None, o

def dpb(d):
    r, o = {}, 0
    while o < len(d):
        h, o = dvi(d, o)
        if h is None: break
        f, w = h >> 3, h & 7
        if w == 0: v, o = dvi(d, o); r[f] = v
        elif w == 2:
            n, o = dvi(d, o)
            if n is None: break
            v = d[o:o+n]; o += n
            try:
                s = v.decode(); r[f] = s if s else v.hex()
            except Exception:
                r[f] = dpb(v) or v.hex()
        elif w == 1: o += 8
        elif w == 5: o += 4
        else: break
    return r

def pbd(d):
    try: return {str(r.field): {"d": (pbd(r.data.results) if hasattr(r.data,"results") else r.data)} for r in Parser().parse(d)}
    except Exception: return {}

def crc7(data):
    c = 0
    for b in data: c = CRC7[((2*(c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c

CRC7 = bytes([0,9,18,27,36,45,54,63,72,65,90,83,108,101,126,119,25,16,11,2,61,52,47,38,81,88,67,74,117,124,103,110,50,59,32,41,22,31,4,13,122,115,104,97,94,87,76,69,43,34,57,48,15,6,29,20,99,106,113,120,71,78,85,92,100,109,118,127,64,73,82,91,44,37,62,55,8,1,26,19,125,116,111,102,89,80,75,66,53,60,39,46,17,24,3,10,86,95,68,77,114,123,96,105,30,23,12,5,58,51,40,33,79,70,93,84,107,98,121,112,7,14,21,28,35,42,49,56,65,72,83,90,101,108,119,126,9,0,27,18,45,36,63,54,88,81,74,67,124,117,110,103,16,25,2,11,52,61,38,47,115,122,97,104,87,94,69,76,59,50,41,32,31,22,13,4,106,99,120,113,78,71,92,85,34,43,48,57,6,15,20,29,37,44,55,62,1,8,19,26,109,100,127,118,73,64,91,82,60,53,46,39,24,17,10,3,116,125,102,111,80,89,66,75,23,30,5,12,51,58,33,40,95,86,77,68,123,114,105,96,14,7,28,21,42,35,56,49,70,79,84,93,98,107,112,121])

# ───────── TEA / packet ─────────
DELTA, ROUNDS, FS = 0x9E3779B9, 16, {0:1,1:2,2:2,3:1,4:2}
FN = {0:"so",1:"cmd",2:"oid",3:"fl",4:"ln"}

def tea_enc(v0, v1, k):
    s = 0
    for _ in range(ROUNDS):
        s = (s + DELTA) & 0xFFFFFFFF
        v0 = (v0 + ((((v1<<4)+k[0]) ^ (v1+s) ^ ((v1>>5)+k[1])) & 0xFFFFFFFF)) & 0xFFFFFFFF
        v1 = (v1 + ((((v0<<4)+k[2]) ^ (v0+s) ^ ((v0>>5)+k[3])) & 0xFFFFFFFF)) & 0xFFFFFFFF
    return v0, v1

def tea_dec(v0, v1, k):
    s = (DELTA * ROUNDS) & 0xFFFFFFFF
    for _ in range(ROUNDS):
        v1 = (v1 - ((((v0<<4)+k[2]) ^ (v0+s) ^ ((v0>>5)+k[3])) & 0xFFFFFFFF)) & 0xFFFFFFFF
        v0 = (v0 - ((((v1<<4)+k[0]) ^ (v1+s) ^ ((v1>>5)+k[1])) & 0xFFFFFFFF)) & 0xFFFFFFFF
        s = (s - DELTA) & 0xFFFFFFFF
    return v0, v1

def tea_cbc(pt, key, dec=False):
    k = struct.unpack("<4I", key[:16])
    out = bytearray(len(pt)); p1 = bytearray(8); p2 = bytearray(8)
    for i in range(0, len(pt), 8):
        x = bytearray(pt[i+j] ^ p1[j] for j in range(8))
        a, b = struct.unpack("<2I", bytes(x))
        if dec: a, b = tea_dec(a, b, k)
        else: a, b = tea_enc(a, b, k)
        y = bytearray(struct.pack("<2I", a, b))
        for j in range(8): out[i+j] = y[j] ^ p2[j]
        p1[:] = pt[i:i+8] if dec else out[i:i+8]
        p2[:] = y if dec else x
    return bytes(out)

def padded(c):
    n = (8 - (len(c) + 10) % 8) % 8
    return bytes([n,0,0]) + b"\0"*n + c + b"\0"*7

def unpad(p):
    if not p or len(p) < 8 or not all(p[-1-i] == 0 for i in range(7)): return None
    s = 3 + (p[0] & 7); e = len(p) - 7
    return p[s:e] if s < e else b""

def hdr(layout, so, cmd, oid, fl, ln, k, v):
    o = bytearray()
    for c in layout:
        val = {0:so,1:cmd,2:oid,3:fl,4:ln}[c]
        if FS[c] == 1: o.append((val & 0xFF) ^ k)
        else:
            x = ((val & 0xFFFF) ^ v) & 0xFFFF
            o += struct.pack("<H", x)
    return bytes(o)

def pkt(key, mk, layout, so, cmd, oid, fl, content, enc=True):
    k = key[0]; v = ((k<<8)|k) & 0xFFFF
    body = tea_cbc(padded(content), key) if enc else content
    p = bytearray([mk, 0]) + hdr(layout, so, cmd, oid, fl, len(body), k, v) + body
    p[1] = crc7(p[2:]) & 0x7F
    return bytes(p)

def mask(m):
    r = [int(c) for c in str(m)]
    return r, [c for c in r if c != 2]

def parse_frame(d, key, m=None):
    if len(d) < 8: return None
    k = key[0]; v = ((k<<8)|k) & 0xFFFF; best = None
    lays = [mask(m)[1], mask(m)[0]] if m else [list(p) for p in itertools.permutations([0,1,3,4])] + [list(p) for p in itertools.permutations([0,1,2,3,4])]
    for L in lays:
        o = 2; h = {}
        for c in L:
            if o + FS[c] > len(d): h = None; break
            h[FN[c]] = (d[o] ^ k) if FS[c] == 1 else struct.unpack_from("<H", d, o)[0] ^ v
            o += FS[c]
        if not h or h["fl"] > 7 or h["ln"] != len(d) - o: continue
        body = d[o:o+h["ln"]]
        if h["fl"] & 1:
            if len(body) % 8 or not body: continue
            body = unpad(tea_cbc(body, key, True))
            if body is None: continue
        f = {"cmd": h["cmd"], "content": body}
        if MESSAGE_ID_TO_NAME.get(h["cmd"]) == "UDP_HELLO": f["t"] = "HELLO"
        elif MESSAGE_ID_TO_NAME.get(h["cmd"]) == "UDP_ACK": f["t"] = "ACK"
        elif MESSAGE_ID_TO_NAME.get(h["cmd"]) == "UDP_PING": f["t"] = "PING"
        elif MESSAGE_ID_TO_NAME.get(h["cmd"]) == "RUDP_JOIN_MATCH": f["t"] = "JOIN"
        else: f["t"] = "X"
        return f
    return best

# ───────── team packets ─────────
def pk(k, iv, body): return bytes.fromhex("0515") + bytes.fromhex(enc_aes(proto(body).hex())) if False else None

def build(pkbody, N, k, iv):
    e = AES.new(k, AES.MODE_CBC, iv).encrypt(pad(proto(pkbody), 16)).hex()
    hl = hex(len(e)//2)[2:]
    if len(hl) % 2: hl = "0" + hl
    return bytes.fromhex(N + "0"*(12-len(N)-len(hl)) + hl + e)

def p_team(k, iv, gv="1.132.9"):
    return build({1:1,2:{2:b"\x01",3:1,4:3,5:"en",8:{1:"IDC3",2:123,3:REGION},9:1,10:bytes.fromhex("01090a0b1219202729"),11:2,13:1,
      14:{1:"08FBA33B4BABE2790205390333330000009700050092005F72697EB2134DCBB2467625142201040e38e848dc0e748c3f6aa04d81000000ff1113090dcacfa16d",2:478,3:"7e585d55",4:"y[Z]",6:12,7:"15686677735a7506101c",8:gv,9:3,10:1,11:"03626253513637754174"},19:329,21:bytes.fromhex("374f521955"),24:{1:21},27:"a_6534489873065906362"}, "0515", k, iv)

def p_fresh(uid, k, iv): return build({1:72,2:{1:int(uid)}}, "0515", k, iv)
def p_leave(uid, k, iv): return build({1:6,2:{1:int(uid)}}, "0515", k, iv)
def p_invite(t, k, iv): return build({1:2,2:{1:int(t),2:REGION,4:1}}, "0515", k, iv)
def p_ready(uid, k, iv): return build({1:15,2:{1:int(uid),2:1}}, "0519", k, iv)
def p_start(uid, k, iv): return build({1:9,2:{1:int(uid),7:{1:"IDC3",2:MODE,3:REGION}}}, "0515", k, iv)

def p_join(tc, k, iv, gv="1.132.9"):
    return build({1:3,2:{1:str(tc),4:bytes.fromhex("0107090a0b120f19202729"),5:"en",8:{1:"IDC3",2:107,3:REGION},9:1,13:1,
      14:{1:"08FBA33B0522052002041B0222220007000C00010004000547E265AE1080779546762514110104076fa2e8770e748c3f6a68ed75000000ff08080500cacfa16d",2:235,6:13,8:gv,9:3,10:1}}, "0515", k, iv)

def p_accept(inv, own, gid, k, iv, gv="1.132.9"):
    return build({1:4,2:{1:int(inv),3:int(own),4:bytes.fromhex("0107090a0b120f19202729"),8:1,
      9:{1:"08FBA33B0522052002041B0222220007000C00010004000547E265AE1080779546762514110104076fa2e8770e748c3f6a68ed75000000ff08080500cacfa16d",2:235,3:{14:80,11:86},4:"{Y\\R",6:13,7:{2:4},8:gv,9:2,10:1,11:"0362625351"},
      10:str(gid),11:{1:"IDC3",2:107,3:REGION},13:"en",16:"374f5219",20:{1:21},23:"a_6534489873065906362",24:"https://dl-sg-production.freefiremobile.com/",27:{1:2,2:4}}, "0515", k, iv)

def find_code(o):
    if isinstance(o, (int, str)):
        s = str(o)
        return s if s.isdigit() and len(s) in (6,7) else None
    if isinstance(o, dict):
        for kk in [11,5,1,3,2,4,10,14,8,7,12,"11","5","1","3"]:
            if kk in o:
                v = o[kk]; v = v.get("d") if isinstance(v, dict) else v
                r = find_code(v)
                if r: return r
    if isinstance(o, list):
        for i in o:
            r = find_code(i)
            if r: return r
    return None

# ───────── movement ─────────
def mv_pkt(key, ps, x, y, z, tick, cnt, ms, uid, code):
    body = ev(int(uid)) + ev(ps) + ev((x<<1) if x >= 0 else ((-x)<<1)-1) + ev((y<<1) if y >= 0 else ((-y)<<1)-1) + ev((z<<1) if z >= 0 else ((-z)<<1)-1)
    body += b"\0" + ev(ms) + b"\0"*7 + bytes.fromhex("bdb6e1f303") + b"\0" + bytes.fromhex("c4b6e1fb0b") + b"\0\0" + ev(tick) + b"\0\0\0" + ev(cnt)
    k = key[0]; v = ((k<<8)|k) & 0xFFFF
    h = bytearray([0x6B, 0, 0 ^ k]) + struct.pack("<H", (2001 ^ v) & 0xFFFF) + struct.pack("<H", (len(body) ^ v) & 0xFFFF) + bytes([k])
    h[1] = crc7(bytes(h[2:]) + body)
    return bytes(h) + body

async def mover(sock, addr, key, code, uid, stop):
    t = cnt = 0; ang = random.random()*6.28
    await asyncio.sleep(random.uniform(1.6,2.4))
    while not stop.is_set():
        try:
            ang += 0.35
            r = 180
            x = int(r*random.uniform(.9,1.1)*(1 if ang % 3.14 < 1.57 else -1))
            z = int(r*random.uniform(.9,1.1)*(1 if ang % 6.28 < 3.14 else -1))
            st = random.random()
            ps = 0 if st < .12 else (1 if st < .45 else (2 if st < .8 else (3 if st < .9 else 4)))
            t = (t+1) & 0xFFFFFFFF; cnt = (cnt+1) & 0xFFFFFFFF
            p = mv_pkt(key, ps, 0 if ps == 0 else x, 0 if ps == 0 else 30, 0 if ps == 0 else z, t, cnt, 0x0F if ps else 0, uid, code)
            await asyncio.get_event_loop().sock_sendto(sock, p, addr)
            await asyncio.wait_for(stop.wait(), timeout=random.uniform(.22,.4))
        except asyncio.TimeoutError: pass
        except asyncio.CancelledError: return
        except Exception: await asyncio.sleep(.4)

async def afk(sock, addr, key, code, uid, stop):
    nr = mask(code)[1]
    await asyncio.sleep(random.uniform(1.4,2.2))
    while not stop.is_set():
        try:
            ts = int(time.time()*1000) & 0xFFFFFFFF; wid = random.choice([101,102,201])
            pid = int(uid)
            await asyncio.get_event_loop().sock_sendto(sock, pkt(key, 0x68, nr, 0, 104, 0, 0, struct.pack("<IIHB", pid, ts, wid, 1), False), addr)
            await asyncio.sleep(.18)
            await asyncio.get_event_loop().sock_sendto(sock, pkt(key, 0x68, nr, 0, 105, 0, 0, struct.pack("<IIHB", pid, ts+200, wid, 0), False), addr)
            await asyncio.wait_for(stop.wait(), timeout=random.uniform(1.8,3.4))
        except asyncio.TimeoutError: pass
        except asyncio.CancelledError: return
        except Exception: await asyncio.sleep(1)

async def ka(sock, addr, key, code, stop):
    nr = mask(code)[1]
    while not stop.is_set():
        try: await asyncio.get_event_loop().sock_sendto(sock, pkt(key, 0x6D, nr, 0, 3, 0, 0, struct.pack("<I", int(time.time()*1000) & 0xFFFFFFFF) + b"\0\0\0", False), addr)
        except Exception: pass
        try: await asyncio.wait_for(stop.wait(), timeout=2.5)
        except asyncio.TimeoutError: pass

# ───────── match ─────────
def zig(n): return ev((n<<1) if n >= 0 else ((-n)<<1)-1)

def sframe(key, code, mk, so, cmd, oid, fl, c):
    k = key[0]; v = ((k<<8)|k) & 0xFFFF
    b = tea_cbc(padded(c), key)
    p = bytearray([mk,0]) + hdr(code, so, cmd, oid, fl, len(b), k, v) + b
    p[1] = crc7(p[2:]) & 0x7F
    return bytes(p)

def startup(token, ukey, code, uid, block, srv, gv, at):
    ukey = bytes.fromhex(ukey); code = [int(c) for c in str(code)]
    tj = token[:660]; sj = token[660:]
    mid = bytes.fromhex("0000000001000102030101") + zig(len(REGION)) + REGION.encode() + bytes.fromhex("0001030003000004")
    mid += zig(len(gv)) + gv.encode() + zig(10) + b"2019121229"
    mid += bytes.fromhex("ca0163736f7665727365612e7374726f6e67686f6c642e66726565666972656d6f62696c652e636f6d3b302e302e302e303b33342e3132362e37362e34353b33342e38372e3137372e31343b33342e38372e3137302e3233303b33352e3138352e3138332e3537000000000000010000000000000000000000000100000800000100000000000100a8a2d7bebd8d8bdf110200")
    ip = srv.split(":")[0]
    mid += zig(len(ip)) + ip.encode()
    if at: mid += zig(len(at)) + at.encode()
    mid += zig(len(sj)) + sj.encode()
    tg = ev(int(uid)) + ev(int(block)) + ev(1) + ev(MODE) + ev(int(block)) + ev(cur_map()) + mid
    return (sframe(ukey, code, 0x5E, 2, 447, 0, 1, zig(len(tj)) + tj.encode()).hex(),
            sframe(ukey, code, 0x5A, 2, 448, 1, 1, tg).hex())

async def play(srv, th, sh, ukey, code, uid, gv, k, iv, idx, at, on_done, on_fail):
    uid = str(uid); stop = asyncio.Event(); in_game = False; clean = False; t0 = time.time()
    sock = None; tasks = []
    try:
        ip, port = srv.split(":"); port = int(port)
        rip = await resolve(ip)
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(("0.0.0.0", 0))
        for o, v in ((socket.SO_RCVBUF,131072),(socket.SO_SNDBUF,131072)): sock.setsockopt(socket.SOL_SOCKET, o, v)
        sock.setblocking(False); addr = (rip, port); ukb = bytes.fromhex(ukey)
        hello = (b"\x10\0\0\0" + f"{uid}_2585".encode()).ljust(29, b"\0")
        nr = mask(code)[1]
        hk = ukb[0]; hv = ((hk<<8)|hk) & 0xFFFF
        hp = bytearray([0x63,0]) + hdr(code, 1, 1, 0, 1, len(tea_cbc(padded(hello), ukb)), hk, hv) + tea_cbc(padded(hello), ukb)
        hp[1] = crc7(hp[2:]) & 0x7F
        await loop.sock_sendto(sock, bytes(hp), addr)
        tasks.append(asyncio.create_task(ka(sock, addr, ukb, code, stop)))
        state = "hello"; sent = False; deadline = time.time() + START_TO
        while True:
            if time.time() - t0 > 420: clean = True; break
            if not in_game and time.time() > deadline: log(f"CS#{idx} startup timeout → requeue", "w"); break
            try:
                r, sa = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), timeout=1.5)
            except asyncio.TimeoutError:
                if state == "ready" and not sent:
                    sent = True
                    await loop.sock_sendto(sock, bytes.fromhex(th), addr); await asyncio.sleep(.28)
                    await loop.sock_sendto(sock, pkt(ukb, 0x68, nr, 0, 2, 0, 1, b"\x01\x00"), addr)
                    await asyncio.sleep(.35); await loop.sock_sendto(sock, bytes.fromhex(sh), addr)
                    state = "ingame"; tasks.append(asyncio.create_task(afk(sock, addr, ukb, code, uid, stop))); tasks.append(asyncio.create_task(mover(sock, addr, ukb, code, uid, stop)))
                elif state == "hello":
                    await loop.sock_sendto(sock, bytes(hp), addr)
                continue
            except (BlockingIOError, OSError): await asyncio.sleep(.3); continue
            except Exception: await asyncio.sleep(.3); continue
            f = parse_frame(r, ukb, code)
            if not f: continue
            if f["cmd"] in (103,107): log(f"CS#{idx} END", "s"); clean = True; break
            if f["cmd"] == 101:
                await loop.sock_sendto(sock, pkt(ukb, 0x68, nr, 0, 2, 0, 1, b"\x01\x00"), addr); continue
            if state == "ingame" and not in_game:
                in_game = True; STAT["in_game"] += 1; log(f"CS#{idx} IN-GAME {uid}", "s")
            if f["t"] == "HELLO": await loop.sock_sendto(sock, pkt(ukb, 0x68, nr, 0, 2, 0, 1, b"\x01\x00"), addr); state = "ack"
            elif f["t"] == "ACK":
                if state in ("hello","ack"): state = "ready"
                else: await loop.sock_sendto(sock, pkt(ukb, 0x68, nr, 0, 2, 0, 1, b"\x01\x00"), addr)
            elif f["t"] == "PING":
                c = f["content"][:4] if len(f["content"]) >= 4 else f["content"]
                await loop.sock_sendto(sock, pkt(ukb, 0x6D, nr, 0, 3, 0, 0, c + b"\0\0\0", False), addr)
            elif f["t"] == "JOIN": await loop.sock_sendto(sock, pkt(ukb, 0x68, nr, 0, 2, 0, 1, b"\x02\x00"), addr)
        return clean
    except Exception as e:
        log(f"CS#{idx} {e}", "e"); return False
    finally:
        if clean:
            STAT["matches"] += 1; on_done()
        elif not in_game: STAT["start_fail"] += 1; on_fail()
        stop.set()
        for t in tasks:
            t.cancel()
        if sock:
            try: sock.close()
            except Exception: pass

# ───────── http helpers ─────────
DNS = {}
async def resolve(h):
    if h.replace(".","").isdigit(): return h
    if h in DNS and DNS[h][1] > time.time(): return DNS[h][0]
    try:
        i = await asyncio.wait_for(asyncio.get_event_loop().getaddrinfo(h, None, family=socket.AF_INET), 6)
        DNS[h] = (i[0][4][0], time.time()+300); return i[0][4][0]
    except Exception: return h

cli = httpx.AsyncClient(verify=False, timeout=15)
def sig(p): return hmac.new(HEX_KEY.encode(), p.encode(), hashlib.sha256).hexdigest()
def gh(av, p): return {"User-Agent": f"GarenaMSDK/4.0.44(SM-E135F ;Android 14;en;GB;app {av} 2019118525;)", "Authorization": f"Signature {sig(p)}", "Content-Type": "application/json; charset=utf-8"}
def lh(tok, rel, host):
    h = {"Authorization": f"Bearer {tok}", "X-GA": "v1 1", "X-GA-SV": str(int(time.time())), "X-Unity-Version": "2018.4.12f1",
         "ReleaseVersion": str(rel), "Content-Type": "application/x-www-form-urlencoded", "Accept": "*/*", "User-Agent": "UnityPlayer/2018.4.12f1"}
    if host: h["Host"] = host
    return h

# ───────── login ─────────
async def vconf():
    try:
        import google_play_scraper as g
        av = g.app("com.dts.freefireth").get("version") or "1.132.9"
    except Exception: av = "1.132.9"
    u = (f"https://version.ggwhitehawk.com/live/ver.php?version={av}&lang=en&device=android&channel=android&appstore=googleplay"
         f"&region={REGION}&whitelist_version=1.3.0&whitelist_sp_version=1.0.0")
    for _ in range(3):
        try:
            j = (await cli.get(u)).json()
            gops = [x.strip() for x in j.get("gop_url","").split(";") if x.strip()]
            return j.get("latest_release_version"), j.get("remote_version"), j.get("server_url"), gops[0], av
        except Exception: await asyncio.sleep(1)
    return None

def payload(at, oid, plat, ver, lang):
    d = {"3":str(datetime.now())[:-7],"4":"free fire","5":1,"7":ver,"8":"Android OS 14 / API-34","9":"Handheld","11":"CarrierDataNetwork","12":1672,"13":750,"14":"338",
         "15":"ARMv7 VFPv3 NEON | 2002 | 8","16":3702,"17":"Mali-G52","18":"OpenGL ES 3.2","19":f"Google|{uuid.uuid4()}","20":"104.28.197.151","21":lang,
         "22":oid,"23":plat,"24":"Handheld","25":"samsung SM-E135F","26":REGION,"29":at,"30":1,"42":"Cellular","57":"7428b253defc164018c604a1ebbfebdf",
         "60":52037,"61":5355,"62":3723,"63":3,"64":5483,"65":52037,"66":5483,"67":52037,"73":2,
         "74":"/data/app/~~x==/lib/arm","76":1,"77":"b8e0cd5e295eee42f5860d3c86e483dd|/base.apk","78":3,"79":1,"81":"32","83":"2019121229",
         "86":"OpenGLES2","87":8191,"88":int(plat),"92":16091,"93":"android","95":111107,"97":1,"98":1,"99":plat,"100":plat,
         "102":"4503454457550c0766","104":53792,"105":1,"107":"c8e41b7a93f02d56e1a94c7b8203f5d1"}
    g = dict(d); g["90"] = "Khulna"; g["91"] = "D"; g["99"] = "0"; g["103"] = 1
    return bytes.fromhex(enc_aes(proto(d).hex())), bytes.fromhex(enc_aes(proto(g).hex()))

async def login(uid, pw):
    vc = await vconf()
    if not vc: return None
    rel, gv, srv, gop, av = vc
    try:
        p = json.dumps({"uid":str(uid),"password":pw,"response_type":"token","client_type":"2","client_secret":HEX_KEY,"client_id":"100067"})
        r = await cli.post("https://100067.connect.garena.com/oauth/guest/token/grant", data=p,
                           headers={"Content-Type":"application/x-www-form-urlencoded","User-Agent":"Dalvik/2.1.0"})
        j = r.json(); oid, at, plat = j["open_id"], j["access_token"], j.get("platform", 4)
    except Exception as e:
        log(f"token {uid}: {type(e).__name__}", "e"); return None
    mp, lp = payload(at, oid, str(plat), gv, REG_LANG.get(REGION, "en"))
    try:
        r = await cli.post(f"{srv}/MajorLogin", data=mp, headers=lh("", rel, None).__class__ and
            {"Accept":"*/*","Authorization":"Bearer ","Content-Type":"application/x-www-form-urlencoded","ReleaseVersion":rel,"X-GA":"v1 1","X-Unity-Version":"2018.4.12f1","User-Agent":"UnityPlayer/2018.4.12f1"})
        c = r.content
        if r.status_code != 200 or len(c) < 200: return None
        best = None
        for off in (64,0,48,32,16,8):
            if off >= len(c): continue
            d = pbd(c[off:])
            if "8" in d: best = d; break
        if not best: return None
        g = lambda kk: (best.get(str(kk)) or {}).get("d")
        jwt, srv2, stime, acc = g(8), g(10), g(21), g(1)
        if not jwt or not srv2: return None
        # AES key/iv
        ak = iv = None
        for a, b in ((22,23),(24,25),(6,7)):
            x, y = g(a), g(b)
            if isinstance(x, bytes) and isinstance(y, bytes) and len(x) == 16 and len(y) == 16: ak, iv = x, y; break
        if not ak:
            raw = c[int(best.get("__off", 0)):] if "__off" in best else c
            return None
        r2 = await cli.post(f"{srv2}/GetLoginData", data=lp, headers=lh(jwt, rel, srv2.replace("https://","").split("/")[0]))
        ld = dpb(r2.content[10:]) or dpb(r2.content)
        gl = lambda kk, d=None: (ld.get(kk, d) if isinstance(ld.get(kk), (str,int)) else d)
        return {"acc":str(acc), "nick":gl(4, f"P{acc}"), "lvl":int(gl(6,1) or 1), "token":jwt, "at":at,
                "gv":gv, "rel":rel, "srv":srv2, "k":ak, "iv":iv, "lp":lp, "stime":stime,
                "fadd":ld.get(14), "region":REGION, "auth":str(uid), "pw":pw}
    except Exception as e:
        log(f"login {uid}: {type(e).__name__}", "e"); return None

async def create(region=REGION):
    vc = await vconf()
    if not vc: return None
    rel, gv, srv, gop, av = vc
    try:
        p = json.dumps({"app_id":100067,"client_type":2,"password":PASS,"source":2})
        r = await cli.post(f"{gop}/api/v2/oauth/guest:register", data=p, headers=gh(av, p))
        uid = r.json()["data"]["uid"]
        p = json.dumps({"client_id":100067,"client_secret":HEX_KEY,"client_type":2,"device_id":f"02-{uuid.uuid4()}","password":PASS,"response_type":"token","uid":int(uid)})
        r = await cli.post(f"{gop}/api/v2/oauth/guest/token:grant", data=p, headers=gh(av, p))
        j = r.json()["data"]; oid, at = j["open_id"], j["access_token"]
        mp, lp = payload(at, oid, str(j.get("platform",4)), gv, "en")
        nick = f"{PREFIX}-{random.randint(100000,999999)}"
        rp = {"1":nick,"2":at,"3":oid,"5":102000007,"6":4,"7":1,"13":1,
              "14":bytes(ord(ch) ^ KEYSTREAM[i % 32] for i, ch in enumerate(oid)),"15":"en","16":2,"20":gv,"21":1,"22":GGRE}
        body = AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(proto(rp), 16))
        await cli.post(f"{srv}/MajorRegister", data=body,
                       headers={"Accept":"*/*","Authorization":"Bearer ","Content-Type":"application/x-www-form-urlencoded","ReleaseVersion":rel,"X-GA":"v1 1","X-Unity-Version":"2018.4.12f1","User-Agent":"UnityPlayer/2018.4.12f1"})
        await asyncio.sleep(3)
        ad = await login(uid, PASS)
        if ad: log(f"CREATE {ad['nick']} {ad['acc']}", "s")
        return ad
    except Exception as e:
        log(f"create: {type(e).__name__}", "e"); return None

# ───────── clan ─────────
def dead(h): return DEAD.get(h, 0) > time.time()

async def clan_hosts():
    out = []
    for b in CLAN_HOSTS:
        h = b.split("://")[1]
        if dead(b): continue
        try:
            await asyncio.wait_for(asyncio.get_event_loop().getaddrinfo(h, 443, family=socket.AF_INET), 4)
            out.append(b)
        except Exception:
            DEAD[b] = time.time() + 900; log(f"clan host dead {h}", "w")
    return out

async def join_clan(ad, cid=None, tries=5):
    cid = str(cid or CLAN).strip()
    if not cid.isdigit() or not ad.get("token"): return False
    hosts = await clan_hosts()
    if not hosts: return False
    pl = AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(proto({1:int(cid)}), 16))
    for i in range(tries):
        b = hosts[i % len(hosts)]
        h = b.split("://")[1]
        try:
            sslc = ssl.create_default_context(); sslc.check_hostname = False; sslc.verify_mode = ssl.CERT_NONE
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=sslc, family=socket.AF_INET)) as s:
                async with s.post(b + "/RequestJoinClan", data=pl, headers=lh(ad["token"], ad["rel"], h), timeout=aiohttp.ClientTimeout(total=14)) as r:
                    t = (await r.text(errors="replace")).lower()
                    if r.status == 200 and not any(x in t for x in ("full","invalid","not found","level")):
                        log(f"clan ✅ {cid} {ad['acc']}", "s"); STAT["joined"] += 1
                        ACC[ad["acc"]]["clan"] = True; return True
        except Exception:
            DEAD[b] = time.time() + 900
        await asyncio.sleep(min(4 + i*2.4, 16))
    STAT["fail"] += 1
    return False

# ───────── matchmaking (duo) ─────────
async def sq_leader(sid, uid, ad, w, stop):
    st = TEAMS.setdefault(sid, {"code":None,"ready":False,"peers":set()})
    while not stop.is_set():
        if uid in PAUSED: await asyncio.sleep(1); continue
        if len(st["peers"]) < 2:
            await asyncio.sleep(2); continue
        try:
            w.write(p_team(ad["k"], ad["iv"], ad["gv"])); await w.drain(); await asyncio.sleep(1.4)
            w.write(p_fresh(uid, ad["k"], ad["iv"])); await w.drain(); await asyncio.sleep(1.2)
            for p in st["peers"]:
                if p != uid:
                    for _ in range(2):
                        w.write(p_invite(p, ad["k"], ad["iv"])); await w.drain(); await asyncio.sleep(.6)
            await asyncio.sleep(6)
            if not st["ready"] or not st["code"]: await asyncio.sleep(4)
            w.write(p_ready(uid, ad["k"], ad["iv"])); await w.drain(); await asyncio.sleep(1)
            w.write(p_start(uid, ad["k"], ad["iv"])); await w.drain()
            log(f"SQUAD{sid} queued map{cur_map()}")
        except Exception as e: log(f"SQUAD{sid} {type(e).__name__}", "w")
        t0 = time.time()
        while not stop.is_set() and time.time() - t0 < SEARCH_TO + random.uniform(-8,8):
            await asyncio.sleep(1)
        if stop.is_set(): return
        STAT["search_fail"] += 1; log(f"SQUAD{sid} no CS → requeue", "w")
        next_map(); await asyncio.sleep(2)

async def sq_member(sid, uid, ad, w, stop):
    st = TEAMS.setdefault(sid, {"code":None,"ready":False,"peers":set()})
    await asyncio.sleep(9); done = False
    while not stop.is_set():
        if uid in PAUSED: await asyncio.sleep(1); continue
        try:
            if st.get("code") and not done:
                w.write(p_join(st["code"], ad["k"], ad["iv"], ad["gv"])); await w.drain(); done = True; await asyncio.sleep(1.2)
                w.write(p_ready(uid, ad["k"], ad["iv"])); await w.drain(); st["ready"] = True
        except Exception: pass
        await asyncio.sleep(2)

# ───────── account worker ─────────
async def worker(uid, pw):
    TASKS[uid] = asyncio.current_task(); acc = None
    while True:
        if uid in PAUSED: await asyncio.sleep(1); continue
        try:
            ad = await login(uid, pw)
            if not ad: await asyncio.sleep(12); continue
            acc = ad["acc"]
            if acc not in ACC: ACC[acc] = {"uid":acc,"nick":ad["nick"],"lvl":ad["lvl"],"st":"ON","clan":False,"m":0}
            ACC[acc]["st"] = "ON"
            if CLAN: asyncio.create_task(join_clan(ad))
            if not ad.get("fadd"): await asyncio.sleep(8); continue
            addr = ad["fadd"].decode() if isinstance(ad["fadd"], bytes) else ad["fadd"]
            host, port = addr.split(":")
            tok = AES.new(ad["k"], AES.MODE_CBC, ad["iv"]).encrypt(pad(ad["token"].encode(), 16)).hex()
            pre = "7219" if REGION == "BD" else ("7214" if REGION == "IND" else "7215")
            start = f"{pre}{int(acc):016x}{int(ad['stime']):08x}00000000{len(tok)//2:08x}{tok}"
            rip = await resolve(host)
            rd, w = await asyncio.wait_for(asyncio.open_connection(rip, int(port)), 20)
            w.write(bytes.fromhex(start)); await w.drain()
            log(f"ONLINE {acc} {ad['nick']}", "s")
            idx = int(acc) % 8
            stop = asyncio.Event()
            sid = idx // 2
            TEAMS.setdefault(sid, {"code":None,"ready":False,"peers":set()})["peers"].add(acc)
            t = asyncio.create_task(sq_leader(sid, acc, ad, w, stop) if idx % 2 == 0 else sq_member(sid, acc, ad, w, stop))
            while True:
                if uid in PAUSED: break
                try: d = await asyncio.wait_for(rd.read(8192), timeout=.5)
                except asyncio.TimeoutError: continue
                if not d: raise ConnectionError("closed")
                hx = d.hex()
                if hx.startswith("0500") and len(d) > 10:
                    dec = None
                    for off in (10,12,8,6,14):
                        if len(hx) <= off: continue
                        c = pbd(bytes.fromhex(hx[off:]))
                        if c: dec = c; break
                    if not dec: continue
                    tc = find_code(dec)
                    if tc: TEAMS[sid]["code"] = tc; log(f"SQUAD{sid} code {tc}")
                    f5 = (dec.get("5") or {}).get("d") or dec
                    gid = inv = None
                    for kk in (8,10,9):
                        v = f5.get(kk) if isinstance(f5, dict) else None
                        v = v.get("d") if isinstance(v, dict) else v
                        if v and str(v).isdigit() and len(str(v)) > 12: gid = str(v); break
                    for kk in (1,2,3,4,6):
                        v = f5.get(kk) if isinstance(f5, dict) else None
                        v = v.get("d") if isinstance(v, dict) else v
                        if v and str(v).isdigit() and 6 <= len(str(v)) <= 15 and str(v) != acc: inv = str(v); break
                    if inv and gid and idx % 2:
                        try:
                            w.write(p_accept(inv, acc, gid, ad["k"], ad["iv"], ad["gv"])); await w.drain()
                            w.write(p_ready(acc, ad["k"], ad["iv"])); await w.drain(); TEAMS[sid]["ready"] = True
                        except Exception: pass
                    continue
                if hx.startswith("0300") and len(d) >= 250:
                    try: res = pbd(d[10:])
                    except Exception: continue
                    tk = uk = mc = sv = bl = None
                    if "42" in res: mc = res["42"].get("d")
                    f5 = (res.get("5") or {}).get("d") or {}
                    if f5:
                        sv = (f5.get("2") or {}).get("d"); uk = (f5.get("3") or {}).get("d")
                        tk = (f5.get("4") or {}).get("d"); bl = (f5.get("1") or {}).get("d")
                        if "42" in f5: mc = f5["42"].get("d")
                    if not (tk and uk and mc and sv): continue
                    log(f"CS MATCH {acc}", "s")
                    th, sh = startup(tk, uk, mc, acc, bl or 0, sv, ad["gv"], ad["at"])
                    TEAMS[sid]["code"] = None; TEAMS[sid]["ready"] = False
                    t.cancel(); stop.set()
                    ACC[acc]["st"] = "MATCH"; ACC[acc]["m"] += 1
                    asyncio.create_task(play(sv, th, sh, uk, mc, acc, ad["gv"], ad["k"], ad["iv"], idx, ad["at"],
                        lambda: ACC[acc].__setitem__("st","ON"),
                        lambda: next_map()))
                    try: w.close()
                    except Exception: pass
                    await asyncio.sleep(1); break
                elif hx.startswith("0300") and len(d) < 30: pass
        except asyncio.CancelledError:
            if acc in ACC: ACC[acc]["st"] = "OFF"
            return
        except Exception as e:
            log(f"{uid} {type(e).__name__}", "e"); await asyncio.sleep(6)

# ───────── supervisor / autocreate ─────────
async def sup():
    while True:
        await asyncio.sleep(15)
        try:
            for uid in list(ACC.keys()):
                if uid in PAUSED: continue
                t = TASKS.get(uid)
                if t is None or t.done():
                    pw = next((a.get("pw") for a in AD.values() if a.get("acc") == uid), None)
                    if pw: TASKS[uid] = asyncio.create_task(worker(uid, pw))
            if CLAN:
                for a in list(AD.values()):
                    if a.get("acc") in ACC and not ACC[a["acc"]].get("clan"):
                        asyncio.create_task(join_clan(a, tries=2))
        except Exception as e: log(f"sup {e}", "e")

async def auto():
    if TARGET <= 0: return
    await asyncio.sleep(10)
    while True:
        try:
            if len(ACC) < TARGET:
                need = min(TARGET - len(ACC), 3)
                for _ in range(need):
                    ad = await create()
                    if ad:
                        AD[ad["auth"]] = ad
                        lst = json.load(open(ACC_FILE)) if os.path.exists(ACC_FILE) else []
                        lst.append({"uid": ad["auth"], "password": ad["pw"], "region": REGION, "clan_id": CLAN})
                        json.dump(lst, open(ACC_FILE, "w"), indent=1)
                        TASKS[ad["auth"]] = asyncio.create_task(worker(ad["auth"], ad["pw"]))
                        await asyncio.sleep(1)
            await asyncio.sleep(30)
        except Exception as e: log(f"auto {e}", "e"); await asyncio.sleep(30)

# ───────── web ─────────
async def w_health(r):
    return aiohttp.web.json_response({"ok": True, "acc": len(ACC), "on": sum(1 for a in ACC.values() if a["st"] == "ON"),
        "match": sum(1 for a in ACC.values() if a["st"] == "MATCH"), **STAT, "up": int(time.time()-START_T), "map": cur_map()})
async def w_stats(r):
    return aiohttp.web.json_response({"accounts": list(ACC.values()), "logs": LOG[-80:], **STAT})
async def w_start(r):
    b = await r.json() if r.can_read_body else {}
    for u, p in (b.get("accounts") or {}).items():
        if u not in TASKS or TASKS[u].done(): TASKS[u] = asyncio.create_task(worker(str(u), str(p)))
    return aiohttp.web.json_response({"ok": True})
async def w_stop(r):
    b = await r.json() if r.can_read_body else {}
    u = str(b.get("uid", ""))
    if u:
        PAUSED.add(u); PAUSED.discard(u) if b.get("resume") else None
        if b.get("resume"):
            TASKS[u] = asyncio.create_task(worker(u, b.get("password", PASS)))
    else: PAUSED.update(ACC.keys())
    return aiohttp.web.json_response({"ok": True})
async def w_clan(r):
    b = await r.json() if r.can_read_body else {}
    cid = str(b.get("clan_id", CLAN)); DEAD.clear()
    for a in list(AD.values()): asyncio.create_task(join_clan(a, cid, 3))
    return aiohttp.web.json_response({"ok": True, "clan": cid})
async def w_root(r):
    return aiohttp.web.Response(text="<h1>RAIX CS farmer</h1><p>/api/health /api/stats /api/clan</p>", content_type="text/html")

# ───────── main ─────────
async def main():
    print(f"\n=== RAIX CS GLORY FARMER ===\nclan={CLAN} target={TARGET} region={REGION}\n")
    app = aiohttp.web.Application()
    for p, h, m in (("/",w_root,"get"),("/api/health",w_health,"get"),("/api/stats",w_stats,"get"),
                    ("/api/start",w_start,"post"),("/api/stop",w_stop,"post"),("/api/clan",w_clan,"post")):
        app.router.add_route(m, p, h)
    run = aiohttp.web.AppRunner(app); await run.setup()
    await aiohttp.web.TCPSite(run, "0.0.0.0", PORT).start()
    log(f"web :{PORT}")
    if os.path.exists(ACC_FILE):
        for a in json.load(open(ACC_FILE)) or []:
            if a.get("uid") and a.get("password") and a["uid"] not in TASKS:
                TASKS[a["uid"]] = asyncio.create_task(worker(str(a["uid"]), str(a["password"])))
                await asyncio.sleep(.25)
    asyncio.create_task(sup()); asyncio.create_task(auto())
    while True: await asyncio.sleep(1)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass