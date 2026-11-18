# -*- coding: utf-8 -*-
# ============================================================
#  main.py — RAIX CLASH SQUAD GLORY FARMER (v7.0)
#  • শুধু CLASH SQUAD (mode 8) — লেভেল লাগে না
#  • CLAN: ggpolarbear বাদ → ppmainecoonghj, DoH fallback,
#    dead-host 15m guard, auto retry + sweeper (কখনো হাল ছাড়ে না)
#  • STARTUP WATCHDOG + MAP ROTATION + anti-AFK + movement
#  • RAIX identity, token cache, supervisor, auto-create
#  • বিল্ট-ইন প্যানেল (inline HTML) — কোনো templates লাগে না
# ============================================================
import sys, os, json, time, uuid, random, asyncio, base64, struct, socket, ssl, itertools, hmac, hashlib, logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import aiohttp, aiohttp.web, httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser
from message_ids import MESSAGE_ID_TO_NAME
import thunderFF_pb2
try:
    import reqClan_pb2
except Exception:
    reqClan_pb2 = None

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
for _l in ("aiohttp.client", "aiohttp.connector", "aiohttp.server", "asyncio"):
    logging.getLogger(_l).setLevel(logging.CRITICAL)

# ═══════════════ CONFIG ═══════════════
DATA = os.environ.get("DATA_DIR", ".").rstrip("/") or "."
ACC_FILE = os.path.join(DATA, "accounts.json")
TOK_FILE = os.path.join(DATA, "token_cache.json")
PORT = int(os.environ.get("PORT", 8080))
PANEL_TOKEN = os.environ.get("PANEL_TOKEN", "").strip()

PASS = os.environ.get("FF_PASSWORD", "RAI X")
PREFIX = os.environ.get("FF_NICK_PREFIX", "RAIX")
CLAN = os.environ.get("CLAN_ID", "3033431593").strip()
REGION = os.environ.get("FF_REGION", "BD").upper()
TARGET = int(os.environ.get("TARGET_ACCOUNTS", "0"))
MAX_MATCH = int(os.environ.get("MAX_MATCHES", "2"))
SEARCH_TO = float(os.environ.get("CS_SEARCH_TIMEOUT", "90"))
START_TO = float(os.environ.get("CS_STARTUP_TIMEOUT", "22"))
MAPS = [int(x) for x in os.environ.get("FF_MAPS", "1,2,3").split(",") if x.strip()] or [1]
CLAN_TRIES = int(os.environ.get("CLAN_TRIES", "6"))
CLAN_DEAD_TTL = float(os.environ.get("CLAN_DEAD_TTL", "900"))
TOK_TTL = 1200
MODE = 8

CLAN_HOSTS = ["https://clientbp.ppmainecoonghj.com", "https://loginbp.ppmainecoonghj.com",
              "https://client.ind.freefiremobile.com", "https://client.us.freefiremobile.com"]
CLAN_HOST_OVERRIDE = os.environ.get("CLAN_HOST", "").strip()

AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
KEYSTREAM = bytes([0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30])
REG_LANG = {"BD": "bn", "IND": "hi", "ID": "id", "PK": "ur", "ME": "ar", "BR": "pt", "US": "pt"}
GGRE = bytes.fromhex("47475245010101006d020000b260ee08e1f86b4c57f9c70f86bba26ed5d1436bcf52e142db3249d905eded757764991ca31a8373cdd26eab91b80f3f1f6f262f4f10b895d7b6937ddba30a27197453890e9da49373f736c679b8254e2f8e1623e91084a5fdd5374fe478ff99e010834553fddeb0bec4018d142e49df9bb236675b67e852f92a43586f7a7d4d0d7a197a1d4da32714dab4d069ad53214e2c33b3877420a12459738c4c619cbd815fa878bbd104776bb3e1ac7818d5397b04a666ac57f682763ff2df31bc2f846ddc7904f3dce1bda0c4b01f9698e9166f98c84f92640abe3f6317834a42e5c12573b46842c1a6ea8fe6ca9c006dca48a2087e1f983dfb5692771e4a0b15b337ad669b1d08b40862b176bace5331b49a767375b1a8469012aa70a67b55fe71b72478201d0b3ac7269c064c960361e92ee7ba8a42cc6b582bf9b965fb388fa9172ad44c4b073ac23c02080a6bcd106b691ffdf4c7cf71e42f2063fcf196e9bddc5e85be1fe5048eb1b31b460efbb46d76195eef9904c4cba326f2e17ff51fec17dd965aa06dadd4ab07d6966e4a7c38e8afd66dfde56c872bb87516a8f7313c797e4d80e5ad4a5f7afad95c1e0449254adae052e71a3fb98399f93ab30848e0d23252dd45e6fd41bc5fa7303dfb846a8fd713a0032a0b0ae96dfba1bbe41d20abd8099e2cb7fccc329d25bd153029139ef05d090a5093ea557693c0a8d491395b8a23ca844b3887dd5dfc29ac06f4b9be87883a793211b973465e2644c4f5de02b8ab01571401203fc2740423826858cc6da0194c195d27aac4ec4b9d23d506c1501d06440aca3fc180926d75d4a004d3dff21eb4ea1e8c86e6c9627248eff953e1d192d5c8efc006a7e512388ef2ebdb72ee3ad42d719f28e8f994e12ebf4c79f2ffe3abd7408ccd2236a7b89b2606247a732c10c4")

os.makedirs(DATA, exist_ok=True)

# ═══════════════ STATE ═══════════════
ACC: Dict[str, dict] = {}
AD: Dict[str, dict] = {}
TASKS: Dict[str, asyncio.Task] = {}
PAUSED: set = set()
WRITERS: Dict[str, list] = {}
LOG: List[dict] = []
STAT = {"in_game": 0, "start_fail": 0, "search_fail": 0, "clan_ok": 0, "clan_fail": 0,
        "matches": 0, "created": 0}
TEAMS: Dict[int, dict] = {}
CLAN_DEAD: Dict[str, float] = {}
CLAN_ST: Dict[str, dict] = {}
START_T = time.time()
_mp = 0

def cur_map() -> int: return MAPS[_mp % len(MAPS)]
def next_map() -> int:
    global _mp
    _mp = (_mp + 1) % len(MAPS)
    return cur_map()

def log(m, lv="i"):
    t = datetime.now().strftime("%H:%M:%S")
    LOG.append({"t": t, "m": str(m), "lv": lv})
    LOG[:] = LOG[-400:]
    col = {"s": "\033[92m", "w": "\033[93m", "e": "\033[91m"}.get(lv, "\033[96m")
    print(f"{col}[{t}] [{lv}] {m}\033[0m")

def ok(m): log(m, "s")
def wn(m): log(m, "w")
def er(m): log(m, "e")

# ═══════════════ PROTO ═══════════════
def ev(n):
    if n < 0: n &= 0xFFFFFFFFFFFFFFFF
    o = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        o.append(b | (0x80 if n else 0))
        if not n: return bytes