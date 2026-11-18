# clanjoin.py — RAIX clan auto-join (main.py এর পাশে রাখো, আলাদা চালাও)
import os, json, time, ssl, socket, asyncio, hashlib, hmac, uuid
from datetime import datetime
import httpx, aiohttp
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

DATA = os.environ.get("DATA_DIR", ".").rstrip("/") or "."
ACC_FILE = os.path.join(DATA, "accounts.json")
CLAN = os.environ.get("CLAN_ID", "3033431593").strip()
REGION = os.environ.get("FF_REGION", "BD").upper()
EVERY = int(os.environ.get("CLAN_EVERY", "180"))      # সেকেন্ড
HOSTS = ["https://clientbp.ppmainecoonghj.com", "https://loginbp.ppmainecoonghj.com",
         "https://client.ind.freefiremobile.com"]
DEAD, OKD = {}, {}

AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
HEX = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
cli = httpx.AsyncClient(verify=False, timeout=15)

def p(m): print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)
def ev(n):
    o = bytearray()
    while True:
        b = n & 0x7F; n >>= 7; o.append(b | (0x80 if n else 0))
        if not n: return bytes(o)
def proto(d):
    o = bytearray()
    for f, v in d.items():
        f = int(f)
        if isinstance(v, int): o += ev((f << 3) | 0) + ev(v)
        else:
            b = v.encode() if isinstance(v, str) else v
            o += ev((f << 3) | 2) + ev(len(b)) + b
    return bytes(o)
def aes(h): return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(bytes.fromhex(h), 16)).hex()
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
            v = d[o:o + n]; o += n
            try: r[f] = v.decode()
            except Exception: r[f] = v
        elif w == 1: o += 8
        elif w == 5: o += 4
        else: break
    return r
def pbd(d):
    from protobuf_decoder.protobuf_decoder import Parser
    try:
        return {str(x.field): (pbd(x.data.results) if hasattr(x.data, "results") else x.data) for x in Parser().parse(d)}
    except Exception: return {}

def payload(at, oid, plat, ver):
    d = {"3": str(datetime.now())[:-7], "4": "free fire", "5": 1, "7": ver, "8": "Android OS 14 / API-34",
         "9": "Handheld", "11": "CarrierDataNetwork", "12": 1672, "13": 750, "14": "338", "15": "ARMv7 VFPv3 NEON | 2002 | 8",
         "16": 3702, "17": "Mali-G52", "18": "OpenGL ES 3.2", "19": f"Google|{uuid.uuid4()}", "20": "104.28.197.151",
         "21": "en", "22": oid, "23": plat, "24": "Handheld", "25": "samsung SM-E135F", "26": REGION, "29": at,
         "30": 1, "42": "Cellular", "57": "7428b253defc164018c604a1ebbfebdf", "60": 52037, "61": 5355, "62": 3723,
         "63": 3, "64": 5483, "65": 52037, "66": 5483, "67": 52037, "73": 2, "74": "/data/app/~~x==/lib/arm", "76": 1,
         "77": "b8e0cd5e295eee42f5860d3c86e483dd|/base.apk", "78": 3, "79": 1, "81": "32", "83": "2019121229",
         "86": "OpenGLES2", "87": 8191, "88": int(plat), "92": 16091, "93": "android", "95": 111107, "97": 1,
         "98": 1, "99": plat, "100": plat, "102": "4503454457550c0766", "104": 53792, "105": 1,
         "107": "c8e41b7a93f02d56e1a94c7b8203f5d1"}
    g = dict(d); g.update({"90": "Khulna", "91": "D", "99": "0", "103": 1})
    return bytes.fromhex(aes(proto(d).hex())), bytes.fromhex(aes(proto(g).hex()))

def lh(tok, rel, host=None):
    h = {"Authorization": f"Bearer {tok}", "X-GA": "v1 1", "X-GA-SV": str(int(time.time())),
         "X-Unity-Version": "2018.4.12f1", "ReleaseVersion": str(rel),
         "Content-Type": "application/x-www-form-urlencoded", "Accept": "*/*",
         "User-Agent": "UnityPlayer/2018.4.12f1"}
    if host: h["Host"] = host
    return h

async def vconf():
    try:
        import google_play_scraper as g
        av = g.app("com.dts.freefireth").get("version") or "1.132.9"
    except Exception: av = "1.132.9"
    u = (f"https://version.ggwhitehawk.com/live/ver.php?version={av}&lang=en&device=android"
         f"&channel=android&appstore=googleplay&region={REGION}&whitelist_version=1.3.0&whitelist_sp_version=1.0.0")
    for _ in range(3):
        try:
            j = (await cli.get(u)).json()
            gops = [x.strip() for x in j.get("gop_url", "").split(";") if x.strip()]
            return j.get("latest_release_version"), j.get("remote_version"), j.get("server_url"), gops[0], av
        except Exception: await asyncio.sleep(1)
    return None

async def get_token(uid, pw):
    vc = await vconf()
    if not vc: return None
    rel, gv, srv, gop, av = vc
    try:
        p1 = json.dumps({"uid": str(uid), "password": pw, "response_type": "token",
                         "client_type": "2", "client_secret": HEX, "client_id": "100067"})
        j = (await cli.post("https://100067.connect.garena.com/oauth/guest/token/grant", data=p1,
                            headers={"Content-Type": "application/x-www-form-urlencoded"})).json()
        oid, at, plat = j["open_id"], j["access_token"], str(j.get("platform", 4))
    except Exception as e:
        p(f"token fail {uid}: {type(e).__name__}"); return None
    mp, lp = payload(at, oid, plat, gv)
    try:
        r = await cli.post(f"{srv}/MajorLogin", data=mp, headers=lh("", rel))
        c = r.content
        if r.status_code != 200 or len(c) < 200: return None
        best, boff = None, 0
        for off in (64, 0, 48, 32, 16, 8):
            if off >= len(c): continue
            d = pbd(c[off:])
            if "8" in d: best, boff = d, off; break
        if not best: return None
        g = lambda k: best.get(str(k))
        jwt, srv2 = g(8), g(10)
        if not jwt or not srv2: return None
        return {"uid": str(uid), "token": jwt, "rel": rel, "srv": srv2}
    except Exception as e:
        p(f"login fail {uid}: {type(e).__name__}"); return None

async def doh(host):
    try:
        r = await cli.get("https://cloudflare-dns.com/dns-query", params={"name": host, "type": "A"},
                          headers={"accept": "application/dns-json"}, timeout=6)
        for a in (r.json().get("Answer") or []):
            ip = a.get("data", "")
            if a.get("type") == 1 and ip.count(".") == 3: return ip
    except Exception: pass
    return None

async def ipof(host):
    try:
        i = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host, 443, family=socket.AF_INET), 4)
        if i: return i[0][4][0]
    except Exception: pass
    return await doh(host)

def dead(h): return DEAD.get(h, 0) > time.time()

async def join(ad, cid):
    pl = AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(proto({1: int(cid)}), 16))
    for i in range(8):
        base = HOSTS[i % len(HOSTS)]
        if dead(base): continue
        host = base.split("://")[1]
        ip = await ipof(host)
        if not ip:
            DEAD[base] = time.time() + 900; p(f"dns dead {host}"); continue
        try:
            ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
            conn = aiohttp.TCPConnector(ssl=ctx, family=socket.AF_INET, force_close=True)
            async with aiohttp.ClientSession(connector=conn, timeout=aiohttp.ClientTimeout(total=14)) as s:
                async with s.post(f"{base.replace(host, ip, 1)}/RequestJoinClan", data=pl,
                                  headers=lh(ad["token"], ad["rel"], host)) as r:
                    t = (await r.text(errors="replace")).lower()
                    if r.status == 200 and not any(x in t for x in ("full", "invalid", "not found", "level")):
                        OKD[ad["uid"]] = time.time() + 3600
                        p(f"✅ {ad['uid']} joined {cid} ({host})"); return True
                    if "already" in t:
                        OKD[ad["uid"]] = time.time() + 3600
                        p(f"✅ {ad['uid']} already in {cid}"); return True
                    p(f"  {host} → {r.status} {t[:70]}")
        except Exception as e:
            DEAD[base] = time.time() + 900; p(f"  {host} → {type(e).__name__}")
        await asyncio.sleep(min(4 + i * 2, 14))
    p(f"❌ {ad['uid']} fail {cid}")
    return False

async def main():
    cid = CLAN
    p(f"clan-join engine | clan={cid} | every {EVERY}s | {ACC_FILE}")
    while True:
        try:
            lst = json.load(open(ACC_FILE)) if os.path.exists(ACC_FILE) else []
        except Exception: lst = []
        if not lst: p("accounts.json নেই/খালি — অপেক্ষা"); await asyncio.sleep(20); continue
        for a in lst:
            u, pw = str(a.get("uid", "")).strip(), str(a.get("password", "")).strip()
            if not u or not pw: continue
            if OKD.get(u, 0) > time.time(): continue
            ad = await get_token(u, pw)
            if not ad: await asyncio.sleep(3); continue
            await join(ad, cid)
            await asyncio.sleep(2)
        await asyncio.sleep(EVERY)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass