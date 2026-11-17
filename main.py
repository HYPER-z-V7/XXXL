# -*- coding: utf-8 -*-
# ============================================================
#   main.py — RAIX CLASH SQUAD MASTERPIECE  (v5.0)
#   • শুধু CLASH SQUAD (mode 8) — লেভেল লাগে না, BR নেই
#   • CS-RANKED (410) ঐচ্ছিক, শুধু লেভেল ১২+ guest হলে
#   • STARTUP WATCHDOG: ইন-গেম না হলে 22s-এ ধরে রি-কিউ
#   • MAP ROTATION: বারবার স্টার্ট ফেইল হলে নিজে ম্যাপ বদলায়
#   • RAIX identity: RAIX-XXXXXX + "RAI X"
#   • TURBO login, token warm, 10s supervisor, exp backoff
# ============================================================
import sys, os, json, time, uuid, random, asyncio, base64, struct, socket
import itertools, traceback, ssl, hmac, hashlib, string, re, subprocess
import httpx
import aiohttp
import aiohttp.web
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from google_play_scraper import app as play_scraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser
from message_ids import MESSAGE_ID_TO_NAME
import thunderFF_pb2

try:
    import StartMatch_pb2
except Exception:
    StartMatch_pb2 = None

try:
    import reqClan_pb2
    _CLAN_PB_AVAILABLE = True
except Exception:
    _CLAN_PB_AVAILABLE = False

# ==================== CONFIG ====================
WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("PORT", 8080))

DATA_DIR = os.environ.get("DATA_DIR", ".").rstrip("/") or "."
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
TOKEN_CACHE_FILE = os.path.join(DATA_DIR, "token_cache.json")
DEVICES_FILE = os.path.join(DATA_DIR, "devices.json")
PANEL_DB_FILE = os.path.join(DATA_DIR, "panel_db.json")
TOKEN_CACHE_TTL = 1200

IDENTITY_PASSWORD = os.environ.get("FF_PASSWORD", "RAI X")
NICK_PREFIX = os.environ.get("FF_NICK_PREFIX", "RAIX")

# ==================== CLASH SQUAD ONLY ====================
CS_MODE = 8                 # 8 = CLASH SQUAD  (লেভেল লাগে না)
CS_RANKED = 410             # 410 = CS-RANKED  (guest-এ লেভেল ১২+)
CS_MODE_NAME = {8: "CLASH-SQUAD", 410: "CS-RANKED"}

CS_ALLOW_RANKED = os.environ.get("CS_ALLOW_RANKED", "0") == "1"
CS_RANKED_MIN_LEVEL = int(os.environ.get("CS_RANKED_MIN_LEVEL", "12"))

_ladder_env = [int(x) for x in os.environ.get("FF_MODES", "8").split(",") if x.strip()]
MODE_LADDER = _ladder_env or [CS_MODE]
if CS_ALLOW_RANKED and CS_RANKED not in MODE_LADDER:
    MODE_LADDER = [CS_RANKED] + MODE_LADDER

MAP_LADDER = [int(x) for x in os.environ.get("FF_MAPS", "1,2,3").split(",") if x.strip()] or [1]
_map_idx = 0

def _cur_map() -> int:
    return MAP_LADDER[_map_idx % len(MAP_LADDER)]

def _next_map() -> int:
    global _map_idx
    _map_idx = (_map_idx + 1) % len(MAP_LADDER)
    return _cur_map()

START_MATCH_INTERVAL = 5.0
MATCH_SEARCH_TIMEOUT = float(os.environ.get("CS_SEARCH_TIMEOUT", "90"))
STARTUP_TIMEOUT = float(os.environ.get("CS_STARTUP_TIMEOUT", "22"))
CS_QUICK_REQUEUE = float(os.environ.get("CS_REQUEUE_DELAY", "1.5"))
CS_ROOM_RESET_EVERY = int(os.environ.get("CS_ROOM_RESET_EVERY", "5"))

ANTI_AFK_MIN_INTERVAL  = 1.8
ANTI_AFK_MAX_INTERVAL  = 3.5
ENABLE_SPEED_MOVEMENT       = True
MOVEMENT_SPEED_MIN          = 1.0
MOVEMENT_SPEED_MAX          = 1.4
MOVEMENT_PATTERN            = "circle"
MOVEMENT_TICK_MS            = 240
MOVEMENT_RADIUS             = 180
MOVEMENT_UPDATE_SPEED_EVERY = 4.0
MOVEMENT_STATE_IDLE_CHANCE   = 0.10
MOVEMENT_STATE_WALK_CHANCE   = 0.28
MOVEMENT_STATE_RUN_CHANCE    = 0.32
MOVEMENT_STATE_SPRINT_CHANCE = 0.10
MOVEMENT_STATE_JUMP_CHANCE   = 0.08
MOVEMENT_STATE_CROUCH_CHANCE = 0.06
MOVEMENT_STATE_PRONE_CHANCE  = 0.06

ENABLE_HTTP_PING = True
PING_INTERVAL    = 20.0
PING_TIMEOUT     = 8.0
PING_URL         = "https://loginbp.ppmainecoonghj.com/Ping"
PING_REAL_IP     = "103.109.214.211"

NEW_MATCH_DELAY = 1.0
MAX_CONCURRENT_MATCHES = int(os.environ.get("MAX_MATCHES", "2"))
MAX_MATCH_DURATION = float(os.environ.get("MAX_MATCH_DURATION", "420"))
MATCH_IDLE_TIMEOUT  = 45.0

_accept_friend_request = True
DEBUG_ALL_PACKETS = False

TEAM_MODE = True
TEAM_SIZE = 2
TEAM_READY_DELAY = 6.0
TEAM_INVITE_WAIT = 2.5
CLAN_ID_DEFAULT = os.environ.get("CLAN_ID", "3033431593")

CLAN_HOST_OVERRIDE = os.environ.get("CLAN_HOST", "").strip()
CLAN_HOST_FALLBACK = [
    "https://clientbp.ppmainecoonghj.com",
    "https://loginbp.ppmainecoonghj.com",
    "https://client.ind.freefiremobile.com",
    "https://client.us.freefiremobile.com",
]
CLAN_REJOIN_EVERY = int(os.environ.get("CLAN_REJOIN_EVERY", "1800"))

SUPERVISOR_INTERVAL = float(os.environ.get("SUPERVISOR_INTERVAL", "10"))
STUCK_LIMIT = float(os.environ.get("STUCK_LIMIT", "180"))
LOGIN_CONCURRENCY = int(os.environ.get("LOGIN_CONCURRENCY", "10"))
CREATE_CONCURRENCY = int(os.environ.get("CREATE_CONCURRENCY", "4"))
CREATE_BATCH = int(os.environ.get("CREATE_BATCH", "4"))
TARGET_ACCOUNTS = int(os.environ.get("TARGET_ACCOUNTS", "0"))
AUTO_RESTART_ENABLED = os.environ.get("AUTO_RESTART", "1") == "1"
RESTART_AFTER_N = int(os.environ.get("RESTART_AFTER_N", "2"))
STATS_EVERY = 60.0
RECONNECT_BASE = float(os.environ.get("RECONNECT_BASE", "0.6"))
RECONNECT_MAX = float(os.environ.get("RECONNECT_MAX", "12"))
TOKEN_WARM_EVERY = float(os.environ.get("TOKEN_WARM_EVERY", "120"))

AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
KEYSTREAM = bytes([0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30])
HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
API_KEY = HEX_KEY.encode()

REGION_LANG = {"ME":"ar","IND":"hi","ID":"id","VN":"vi","TH":"th","BD":"bn",
               "PK":"ur","TW":"zh","RU":"ru","SAC":"es","BR":"pt","NA":"pt",
               "SG":"pt","US":"pt"}

os.makedirs(DATA_DIR, exist_ok=True)

def _write_json(path, data, indent=2):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except Exception as e:
        print(f"[JSON] write {path}: {e}")
        try:
            if os.path.exists(tmp): os.remove(tmp)
        except Exception:
            pass
        return False

# ==================== STATE ====================
class BotState:
    def __init__(self):
        self.accounts: Dict[str, dict] = {}
        self.account_credentials: Dict[str, dict] = {}
        self.account_workers: Dict[str, asyncio.Task] = {}
        self.auth_to_game_id: Dict[str, str] = {}
        self.game_to_auth_id: Dict[str, str] = {}
        self.paused: set = set()
        self.writers: Dict[str, list] = {}
        self.logs: List[dict] = []
        self.total_matches = 0
        self.matches_started = 0
        self.cs_in_game = 0
        self.cs_start_fail = 0
        self.cs_search_fail = 0
        self.cs_room_resets = 0
        self.total_exp_gained = 0
        self.create_progress: List[str] = []
        self.creating = False
        self.start_time = time.time()
        self._status_since: Dict[str, float] = {}
        self._writer_lock = asyncio.Lock()

    def log(self, msg, level="info"):
        try:
            t = datetime.now().strftime("%H:%M:%S")
            self.logs.append({"t": time.time(), "time": t, "message": str(msg), "level": level})
            if len(self.logs) > 500:
                self.logs = self.logs[-500:]
        except Exception:
            pass

    def register_account(self, uid, nickname, region="BD", level=1, exp=0,
                         likes=0, token=None, auth_uid=None):
        uid = str(uid)
        existing = self.accounts.get(uid, {})
        self.accounts[uid] = {
            "uid": uid, "nickname": nickname, "region": region,
            "level": level, "exp": exp, "likes": likes,
            "token": token, "auth_uid": auth_uid,
            "status": "ONLINE",
            "current_exp": exp,
            "initial_exp": existing.get("initial_exp", exp),
            "gained_exp": existing.get("gained_exp", 0),
            "matches": existing.get("matches", 0),
            "matches_played": existing.get("matches", 0),
            "active_matches": 0,
            "last_match_time": existing.get("last_match_time", "Running..."),
            "is_paused": False,
            "mode": _mode_for(level),
            "cs_only": True,
        }
        self._status_since[uid] = time.time()

    def update_status(self, uid, status, matches=0):
        uid = str(uid)
        if uid in self.accounts:
            if self.accounts[uid].get("status") != status:
                self._status_since[uid] = time.time()
            self.accounts[uid]["status"] = status
            self.accounts[uid]["active_matches"] = matches
            self.accounts[uid]["is_paused"] = (status == "PAUSED")

    def stuck_for(self, uid):
        return time.time() - self._status_since.get(str(uid), time.time())

    def update_exp(self, uid, exp, level=None):
        uid = str(uid)
        if uid in self.accounts:
            a = self.accounts[uid]
            old = a.get("current_exp", 0)
            if exp > old:
                a["gained_exp"] = a.get("gained_exp", 0) + (exp - old)
                self.total_exp_gained += (exp - old)
            a["current_exp"] = exp
            a["exp"] = exp
            if level: a["level"] = level

    def increment_match(self, uid):
        self.total_matches += 1
        uid = str(uid)
        if uid in self.accounts:
            m = self.accounts[uid].get("matches", 0) + 1
            self.accounts[uid]["matches"] = m
            self.accounts[uid]["matches_played"] = m
            self.accounts[uid]["last_match_time"] = datetime.now().strftime("%H:%M:%S")

    def increment_match_started(self):
        self.matches_started += 1

    def register_writer(self, uid, w):
        self.writers.setdefault(str(uid), []).append(w)

    def unregister_writer(self, uid, w):
        try: self.writers.get(str(uid), []).remove(w)
        except Exception: pass

    def close_writers_for_account(self, uid):
        for w in list(self.writers.get(str(uid), [])):
            try: w.close()
            except Exception: pass
        self.writers[str(uid)] = []

    def is_paused(self, uid):
        return str(uid) in self.paused

    def toggle_pause(self, uid, state):
        uid = str(uid)
        if state:
            self.paused.add(uid)
            if uid in self.accounts:
                self.accounts[uid]["is_paused"] = True
                self.accounts[uid]["status"] = "PAUSED"
        else:
            self.paused.discard(uid)
            if uid in self.accounts:
                self.accounts[uid]["is_paused"] = False
                if self.accounts[uid].get("status") == "PAUSED":
                    self.accounts[uid]["status"] = "ONLINE"

bot_state = BotState()

def _mode_for(level: int) -> int:
    """লেভেল অনুযায়ী বৈধ CS মোড। CS-Ranked guest-এ ১২+ ছাড়া কখনোই না।"""
    for m in MODE_LADDER:
        if m == CS_RANKED and int(level or 1) < CS_RANKED_MIN_LEVEL:
            continue
        return m
    return CS_MODE

_team_states: Dict[int, Dict[str, Any]] = {}

def get_team_state(squad_id: int) -> Dict[str, Any]:
    if squad_id not in _team_states:
        _team_states[squad_id] = {
            "peers": {},
            "leader_uid": None,
            "team_code": None,
            "member_ready": False,
            "mode": CS_MODE,
            "mode_idx": 0,
            "search_fails": 0,
            "start_fails": 0,
            "lock": asyncio.Lock(),
        }
    return _team_states[squad_id]

_team_state = get_team_state(0)

def get_account_index_for_uid(uid_str: str, account_data: dict = None) -> int:
    target_uids = [str(uid_str)]
    if account_data and account_data.get("auth_uid"):
        target_uids.append(str(account_data["auth_uid"]))
    if uid_str in bot_state.game_to_auth_id:
        target_uids.append(str(bot_state.game_to_auth_id[uid_str]))
    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                accs = json.load(f)
            uids = [str(a.get("uid", "")) for a in accs if isinstance(a, dict)]
            for tu in target_uids:
                if tu in uids:
                    return uids.index(tu)
    except Exception:
        pass
    return 0

def get_squad_id_for_uid(uid_str: str, account_data: dict = None) -> int:
    return get_account_index_for_uid(uid_str, account_data) // 2

def is_squad_leader_for_uid(uid_str: str, account_data: dict = None) -> bool:
    return (get_account_index_for_uid(uid_str, account_data) % 2) == 0

def get_squad_partner_info(account_index: int) -> Tuple[int, str]:
    partner_idx = account_index + 1 if account_index % 2 == 0 else account_index - 1
    partner_auth_uid = ""
    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                accs = json.load(f)
            if 0 <= partner_idx < len(accs):
                partner_auth_uid = str(accs[partner_idx].get("uid", ""))
    except Exception:
        pass
    return partner_idx, partner_auth_uid

def has_squad_partner(uid_str: str, account_data: dict = None) -> bool:
    idx = get_account_index_for_uid(uid_str, account_data)
    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return (idx ^ 1) < len(json.load(f))
    except Exception:
        pass
    return False

_restart_state = {"lock": asyncio.Lock(), "finished_bots": set(),
                  "target": None, "restarting": False}

# ==================== PANEL DB ====================
def _hash_pw(pw: str) -> str:
    return hashlib.sha256(("dgdrift_salt_" + str(pw)).encode("utf-8")).hexdigest()

class PanelDB:
    def __init__(self):
        self.users: Dict[str, dict] = {}
        self.sessions: Dict[str, str] = {}
        self.coupons: Dict[str, dict] = {}
        self.transactions: List[dict] = []
        self.groups: Dict[str, dict] = {}
        self.activity_log: List[dict] = []
        self.inbox: List[dict] = []
        self.notifications: Dict[str, List[dict]] = {}
        self.push_subscriptions: Dict[str, list] = {}
        self.active_alert: Optional[dict] = None
        self.settings = {
            "basic_credit_usd": 1.70,
            "premium_credit_usd": 20.00,
            "binance_pay_id": "854729104",
            "discord": "https://discord.gg/uFFd8c7B5A",
            "support": "https://discord.gg/uFFd8c7B5A",
            "vapid_public_key": "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U",
            "regions": [
                {"id": "ind", "region_name": "India", "code": "IND", "tier": "basic", "enabled": True},
                {"id": "bd",  "region_name": "Bangladesh", "code": "BD", "tier": "basic", "enabled": True},
                {"id": "pk",  "region_name": "Pakistan", "code": "PK", "tier": "basic", "enabled": True},
                {"id": "id",  "region_name": "Indonesia", "code": "ID", "tier": "basic", "enabled": True},
                {"id": "me",  "region_name": "Middle East", "code": "ME", "tier": "premium", "enabled": True},
                {"id": "br",  "region_name": "Brasil", "code": "BR", "tier": "premium", "enabled": True},
            ]
        }
        self.load()

    def load(self):
        if os.path.exists(PANEL_DB_FILE):
            try:
                with open(PANEL_DB_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                self.users = d.get("users", {})
                self.sessions = d.get("sessions", {})
                self.coupons = d.get("coupons", {})
                self.transactions = d.get("transactions", [])
                self.groups = d.get("groups", {})
                self.activity_log = d.get("activity_log", [])
                self.inbox = d.get("inbox", [])
                self.settings.update(d.get("settings", {}))
            except Exception as e:
                print(f"[PANEL-DB] Load error: {e}")

        if "admin" not in self.users:
            self.users["admin"] = {
                "username": "admin", "display_name": "Admin",
                "password_hash": _hash_pw("admin123"), "role": "admin",
                "basic_credits": 1000, "premium_credits": 1000,
                "max_groups": 20, "created_at": int(time.time()),
            }
            self.save()

    def save(self):
        _write_json(PANEL_DB_FILE, {
            "users": self.users, "sessions": self.sessions,
            "coupons": self.coupons, "transactions": self.transactions,
            "groups": self.groups, "activity_log": self.activity_log[-500:],
            "inbox": self.inbox[-200:], "settings": self.settings,
        })

    def log_activity(self, username, action, group_id="", clan_id="", details=""):
        self.activity_log.insert(0, {
            "id": uuid.uuid4().hex[:10], "username": username, "action": action,
            "group_id": str(group_id), "clan_id": str(clan_id), "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        self.save()

panel_db = PanelDB()

async def _mark_bot_match_finished(account_id):
    if not AUTO_RESTART_ENABLED:
        return
    async with _restart_state["lock"]:
        if _restart_state["restarting"]:
            return
        _restart_state["finished_bots"].add(str(account_id))
        n_done = len(_restart_state["finished_bots"])
        if _restart_state["target"] is None:
            _restart_state["target"] = max(1, RESTART_AFTER_N)
        target = _restart_state["target"]
        print_success(f"[RESTART] {account_id} match done → {n_done}/{target}")
        if n_done >= target:
            _restart_state["restarting"] = True
            print_warning(f"[RESTART] ✅ {target} bots finished → restart in 3s")
            asyncio.create_task(_schedule_restart())

async def _schedule_restart():
    await asyncio.sleep(3.0)
    print_warning("[RESTART] 🔄 process restart")
    try:
        sys.stdout.flush(); sys.stderr.flush()
    except Exception:
        pass
    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print_error(f"[RESTART] execv failed: {e}")
        try:
            subprocess.Popen([sys.executable] + sys.argv); os._exit(0)
        except Exception as e2:
            print_error(f"[RESTART] subprocess failed: {e2}"); os._exit(1)

# ==================== PRINT ====================
class C:
    GREEN='\033[92m'; FAIL='\033[91m'; WARNING='\033[93m'
    CYAN='\033[96m'; MAGENTA='\033[95m'; ENDC='\033[0m'

def print_success(t): print(f"{C.GREEN}[+] {t}{C.ENDC}"); bot_state.log(t, "success")
def print_error(t):   print(f"{C.FAIL}[-] {t}{C.ENDC}");   bot_state.log(t, "error")
def print_warning(t): print(f"{C.WARNING}[!] {t}{C.ENDC}"); bot_state.log(t, "warning")
def print_info(t):    print(f"{C.CYAN}[i] {t}{C.ENDC}");   bot_state.log(t, "info")

GGRE_RAW = bytes.fromhex(
    "47475245010101006d020000b260ee08e1f86b4c57f9c70f86bba26ed5d1436bcf52e142db3249d905eded757764991ca31a8373cdd26eab91b80f3f1f6f262f4f10b895d7b6937ddba30a27197453890e9da49373f736c679b8254e2f8e1623e91084a5fdd5374fe478ff99e010834553fddeb0bec4018d142e49df9bb236675b67e852f92a43586f7a7d4d0d7a197a1d4da32714dab4d069ad53214e2c33b3877420a12459738c4c619cbd815fa878bbd104776bb3e1ac7818d5397b04a666ac57f682763ff2df31bc2f846ddc7904f3dce1bda0c4b01f9698e9166f98c84f92640abe3f6317834a42e5c12573b46842c1a6ea8fe6ca9c006dca48a2087e1f983dfb5692771e4a0b15b337ad669b1d08b40862b176bace5331b49a767375b1a8469012aa70a67b55fe71b72478201d0b3ac7269c064c960361e92ee7ba8a42cc6b582bf9b965fb388fa9172ad44c4b073ac23c02080a6bcd106b691ffdf4c7cf71e42f2063fcf196e9bddc5e85be1fe5048eb1b31b460efbb46d76195eef9904c4cba326f2e17ff51fec17dd965aa06dadd4ab07d6966e4a7c38e8afd66dfde56c872bb87516a8f7313c797e4d80e5ad4a5f7afad95c1e0449254adae052e71a3fb98399f93ab30848e0d23252dd45e6fd41bc5fa7303dfb846a8fd713a0032a0b0ae96dfba1bbe41d20abd8099e2cb7fccc329d25bd153029139ef05d090a5093ea557693c0a8d491395b8a23ca844b3887dd5dfc29ac06f4b9be87883a793211b973465e2644c4f5de02b8ab01571401203fc2740423826858cc6da0194c195d27aac4ec4b9d23d506c1501d06440aca3fc180926d75d4a004d3dff21eb4ea1e8c86e6c9627248eff953e1d192d5c8efc006a7e512388ef2ebdb72ee3ad42d719f28e8f994e12ebf4c79f2ffe3abd7408ccd2236a7b89b2606247a732c10c4"
)

def _encode_proto_std(fields):
    out = b""
    for f in sorted(fields.keys()):
        v = fields[f]
        if isinstance(v, bool):
            out += encode_varint((f << 3) | 0) + encode_varint(int(v))
        elif isinstance(v, int):
            out += encode_varint((f << 3) | 0) + encode_varint(v)
        elif isinstance(v, (str, bytes)):
            if isinstance(v, str): v = v.encode()
            out += encode_varint((f << 3) | 2) + encode_varint(len(v)) + v
    return out

async def major_register(release_v, access_token, open_id, name, game_version,
                          login_url, lang_code="en"):
    field14 = bytes(ord(c) ^ KEYSTREAM[i % 32] for i, c in enumerate(open_id))
    fields = {1: name, 2: access_token, 3: open_id, 5: 102000007, 6: 4, 7: 1,
              13: 1, 14: field14, 15: lang_code, 16: 2, 20: game_version,
              21: 1, 22: GGRE_RAW}
    proto = _encode_proto_std(fields)
    payload = AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(proto, 16))
    url = f"{login_url.rstrip('/')}/MajorRegister"
    hdrs = {"Accept": "*/*", "Authorization": "Bearer ",
            "Content-Type": "application/x-www-form-urlencoded",
            "ReleaseVersion": f"{release_v}",
            "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "X-GA": "v1 1", "X-GA-SV": str(int(time.time())),
            "X-Unity-Version": "2018.4.12f1"}
    for attempt in range(3):
        try:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
                async with s.post(url, headers=hdrs, data=payload, ssl=ssl_ctx) as resp:
                    content = await resp.read()
                    print_info(f"[MAJOR-REG] status={resp.status} len={len(content)}")
                    if resp.status != 200 or not content:
                        await asyncio.sleep(0.8 + attempt)
                        continue
                    for off in [0, 64, 48, 32, 16]:
                        if off >= len(content): continue
                        try:
                            r = decode_protobuf_2(content[off:])
                            if r and 3 in r:
                                return {str(k): {"data": v} for k, v in r.items()}
                        except Exception: pass
                    if len(content) % 16 == 0:
                        try:
                            pt = AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(content)
                            pl = pt[-1]
                            if 1 <= pl <= 16 and all(b == pl for b in pt[-pl:]):
                                pt = pt[:-pl]
                            r = decode_protobuf_2(pt)
                            if r and 3 in r:
                                return {str(k): {"data": v} for k, v in r.items()}
                        except Exception: pass
                    return None
        except Exception as e:
            print_error(f"[MAJOR-REG] {e}")
            await asyncio.sleep(0.8 + attempt)
    return None

# ==================== DEVICE ====================
def _generate_new_device() -> dict:
    dl = [("Samsung","SM-G998B","Adreno (TM) 660","Android OS 12 / API-31"),
          ("Xiaomi","2201122G","Adreno (TM) 730","Android OS 13 / API-33"),
          ("Realme","RMX3700","Mali-G710","Android OS 14 / API-34"),
          ("OnePlus","CPH2451","Adreno (TM) 740","Android OS 13 / API-33"),
          ("OPPO","CPH2611","Adreno (TM) 720","Android OS 14 / API-34")]
    b, m, g, o = random.choice(dl)
    return {"unique_device_id": f"Google|{uuid.uuid4()}", "brand": b, "model": m,
            "gpu_renderer": g, "system_software": o,
            "screen_width": random.choice([1080,1440,720]),
            "screen_height": random.choice([2400,3200,1600]),
            "screen_dpi": str(random.randint(300,420)),
            "memory": random.randint(2800,6500)}

# ==================== DNS ====================
_DNS_CACHE: Dict[str, Tuple[str,float]] = {}
_DNS_CACHE_TTL = 300.0

async def resolve_host_cloudflare(hostname: str) -> str:
    if not hostname: return hostname
    parts = hostname.split('.')
    if len(parts) == 4 and all(p.isdigit() for p in parts): return hostname
    now = time.time()
    if hostname in _DNS_CACHE:
        ip, exp = _DNS_CACHE[hostname]
        if now < exp: return ip
    try:
        loop = asyncio.get_running_loop()
        info = await asyncio.wait_for(
            loop.getaddrinfo(hostname, None, family=socket.AF_INET), timeout=6)
        if info:
            ip = info[0][4][0]
            _DNS_CACHE[hostname] = (ip, now + _DNS_CACHE_TTL)
            return ip
    except Exception: pass
    return hostname

def optimize_tcp_socket(sock):
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
    except Exception: pass

def optimize_udp_socket(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
    except Exception: pass

async def safe_close_writer(writer):
    if not writer: return
    try:
        if not writer.is_closing(): writer.close()
        await asyncio.wait_for(writer.wait_closed(), timeout=1.5)
    except Exception: pass

client = httpx.AsyncClient(verify=False, timeout=15.0,
    limits=httpx.Limits(max_connections=500, max_keepalive_connections=250))
_LOGIN_SEMAPHORE = asyncio.Semaphore(LOGIN_CONCURRENCY)
_CREATE_SEMAPHORE = asyncio.Semaphore(CREATE_CONCURRENCY)

# ==================== CRYPTO ====================
CRC7_TABLE = bytes([
    0,9,18,27,36,45,54,63,72,65,90,83,108,101,126,119,25,16,11,2,61,52,47,38,
    81,88,67,74,117,124,103,110,50,59,32,41,22,31,4,13,122,115,104,97,94,87,76,69,
    43,34,57,48,15,6,29,20,99,106,113,120,71,78,85,92,100,109,118,127,64,73,82,91,
    44,37,62,55,8,1,26,19,125,116,111,102,89,80,75,66,53,60,39,46,17,24,3,10,
    86,95,68,77,114,123,96,105,30,23,12,5,58,51,40,33,79,70,93,84,107,98,121,112,
    7,14,21,28,35,42,49,56,65,72,83,90,101,108,119,126,9,0,27,18,45,36,63,54,
    88,81,74,67,124,117,110,103,16,25,2,11,52,61,38,47,115,122,97,104,87,94,69,76,
    59,50,41,32,31,22,13,4,106,99,120,113,78,71,92,85,34,43,48,57,6,15,20,29,
    37,44,55,62,1,8,19,26,109,100,127,118,73,64,91,82,60,53,46,39,24,17,10,3,
    116,125,102,111,80,89,66,75,23,30,5,12,51,58,33,40,95,86,77,68,123,114,105,96,
    14,7,28,21,42,35,56,49,70,79,84,93,98,107,112,121,
])
_DELTA = 0x9E3779B9
_ROUNDS = 16
_FIELD_SIZES = {0:1,1:2,2:2,3:1,4:2}
_FIELD_NAMES = {0:"sendOption",1:"cmd",2:"orderId",3:"flags",4:"length"}

def crc7_sync(data: bytes) -> int:
    c = 0
    for b in data:
        c = CRC7_TABLE[((2*(c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F

def encode_varint(n: int) -> bytes:
    out = bytearray()
    if n < 0: n &= 0xFFFFFFFFFFFFFFFF
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def _pb_varint(fn, val): return encode_varint((fn<<3)|0) + encode_varint(val)
def _pb_length(fn, val):
    enc = val.encode('utf-8') if isinstance(val, str) else val
    return encode_varint((fn<<3)|2) + encode_varint(len(enc)) + enc

def create_proto(fields) -> bytes:
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(field, str): field = int(field)
        if isinstance(value, dict):
            packet.extend(_pb_length(field, bytes(create_proto(value))))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    packet.extend(_pb_length(field, bytes(create_proto(item))))
                elif isinstance(item, str): packet.extend(_pb_length(field, item))
                elif isinstance(item, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(item)))
                elif isinstance(item, bool): packet.extend(_pb_varint(field, 1 if item else 0))
                elif isinstance(item, int): packet.extend(_pb_varint(field, item))
        elif isinstance(value, bool): packet.extend(_pb_varint(field, 1 if value else 0))
        elif isinstance(value, int): packet.extend(_pb_varint(field, value))
        elif isinstance(value, str): packet.extend(_pb_length(field, value))
        elif isinstance(value, (bytes, bytearray)): packet.extend(_pb_length(field, bytes(value)))
    return bytes(packet)

def encrypt_aes(hex_data: str) -> str:
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(
        pad(bytes.fromhex(hex_data), AES.block_size)).hex()

def decode_varint(data, offset):
    result = 0; shift = 0
    while offset < len(data):
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80): return result, offset
        shift += 7
    return None, offset

def decode_protobuf_2(data):
    result = {}; offset = 0; dl = len(data)
    while offset < dl:
        header, offset = decode_varint(data, offset)
        if header is None: break
        fn = header >> 3; wt = header & 0x7
        if wt == 0:
            v, offset = decode_varint(data, offset)
            if v is not None: result[fn] = v
        elif wt == 2:
            length, offset = decode_varint(data, offset)
            if length is None: break
            value = data[offset:offset+length]; offset += length
            try:
                s = value.decode('utf-8')
                result[fn] = s if s else value.hex()
            except UnicodeDecodeError:
                nested = decode_protobuf_2(value)
                result[fn] = nested if nested else value.hex()
        elif wt == 1: offset += 8
        elif wt == 3: offset += 4
        else: break
    return result

def extract_raw_fields(data: bytes) -> dict:
    result = {}; offset = 0; dl = len(data)
    while offset < dl:
        header, offset = decode_varint(data, offset)
        if header is None: break
        fn = header >> 3; wt = header & 0x7
        if wt == 0:
            v, offset = decode_varint(data, offset)
            if v is not None: result[fn] = v
        elif wt == 2:
            length, offset = decode_varint(data, offset)
            if length is None: break
            if offset + length > dl: break
            result[fn] = bytes(data[offset:offset+length]); offset += length
        elif wt == 1: offset += 8
        elif wt == 3: offset += 4
        else: break
    return result

def _parse_results_sync(results):
    out = {}
    for r in results:
        fd = {"wire_type": r.wire_type}
        if r.wire_type == "varint": fd["data"] = r.data
        elif r.wire_type in ("string","bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            if hasattr(r.data, "results"): fd["data"] = _parse_results_sync(r.data.results)
            elif isinstance(r.data, list): fd["data"] = _parse_results_sync(r.data)
            else: fd["data"] = str(r.data)
        out[str(r.field)] = fd
    return out

def decode_protobuf_dict(data: bytes) -> dict:
    try: return _parse_results_sync(Parser().parse(data))
    except Exception: return {}

async def decode_protobuf_async(data):
    try: return json.dumps(_parse_results_sync(Parser().parse(data)))
    except Exception: return "{}"

def zigzag_encode(n: int) -> bytes:
    return encode_varint((n << 1) if n >= 0 else ((-n) << 1) - 1)

def uleb_encode(n: int) -> bytes:
    return encode_varint(n)

def create_packet(Pk, N, K, V):
    if isinstance(K, str): K = bytes.fromhex(K) if len(K)==32 else K.encode()
    if isinstance(V, str): V = bytes.fromhex(V) if len(V)==32 else V.encode()
    PkEnc = AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(Pk),16)).hex()
    L = len(PkEnc)//2
    hexlen = hex(L)[2:]
    if len(hexlen) % 2 != 0: hexlen = '0'+hexlen
    tp = 12 - len(N) - len(hexlen)
    if tp < 0: tp = 0
    return bytes.fromhex(N + ('0'*tp) + hexlen + PkEnc)

# ==================== MOVEMENT ====================
def build_movement_packet_2001(key_bytes, msg_key, player_state, x, y, z,
                                tick, counter, move_state, account_uid,
                                room_code, phase="arena"):
    if phase == "game":
        TAIL = (b"\x00"*7 + b"\x93\xca\xd5\xf9\x0b" + b"\x8e\xfe\xfc\xf7\x0b"
                + b"\xf4\xe0\xfe\xf7\x03" + b"\x00\x00")
    else:
        TAIL = (b"\x00"*7 + b"\xbd\xb6\xe1\xf3\x03" + b"\x00"
                + b"\xc4\xb6\xe1\xfb\x0b" + b"\x00\x00")
    body = bytearray()
    body += uleb_encode(int(account_uid)); body += uleb_encode(int(player_state))
    body += zigzag_encode(int(x)); body += zigzag_encode(int(y)); body += zigzag_encode(int(z))
    body += b"\x00"; body += uleb_encode(int(move_state)); body += TAIL
    body += uleb_encode(int(tick)); body += b"\x00\x00\x00"; body += uleb_encode(int(counter))
    body = bytes(body)
    k = key_bytes[0]; v80 = ((k << 8) | k) & 0xFFFF
    h = bytearray()
    h.append(msg_key); h.append(0x00); h.append(0x00 ^ k)
    h += ((2001 ^ v80) & 0xFFFF).to_bytes(2, "little")
    h += (len(body) ^ v80).to_bytes(2, "little")
    h.append(0x00 ^ k)
    h[1] = crc7_sync(bytes(h[2:]) + body)
    return bytes(h) + body

class MovementTracker:
    PLAYER_STATE = {"idle":0,"walk":1,"run":2,"sprint":3,"jump":4,"crouch":5,"prone":6}
    def __init__(self, pattern="circle", radius=180):
        self.pattern = pattern; self.radius = int(radius)
        self.tick = 0; self.counter = 0
        self.angle = random.uniform(0, 6.2832)
        self.speed_multiplier = 1.0; self.dir_flip = 1
        self._next_speed_roll = time.time()
        self.state = "walk"; self.state_start = time.time()
        self.state_duration = random.uniform(2.0, 4.0)
        self._roll_new_speed()
    def _roll_new_speed(self):
        try:
            lo, hi = float(MOVEMENT_SPEED_MIN), float(MOVEMENT_SPEED_MAX)
            if hi < lo: lo, hi = hi, lo
            self.speed_multiplier = round(random.uniform(lo, hi), 2)
        except Exception: self.speed_multiplier = 1.0
        self._next_speed_roll = time.time() + MOVEMENT_UPDATE_SPEED_EVERY
    def _pick_next_state(self):
        r = random.random()
        ci = MOVEMENT_STATE_IDLE_CHANCE; cw = ci + MOVEMENT_STATE_WALK_CHANCE
        cr = cw + MOVEMENT_STATE_RUN_CHANCE; cs = cr + MOVEMENT_STATE_SPRINT_CHANCE
        cj = cs + MOVEMENT_STATE_JUMP_CHANCE; cc = cj + MOVEMENT_STATE_CROUCH_CHANCE
        if r < ci: return "idle", random.uniform(0.6,1.6)
        elif r < cw: return "walk", random.uniform(1.6,3.0)
        elif r < cr: return "run", random.uniform(2.0,4.0)
        elif r < cs: return "sprint", random.uniform(1.2,2.5)
        elif r < cj: return "jump", random.uniform(0.35,0.65)
        elif r < cc: return "crouch", random.uniform(1.2,2.5)
        return "prone", random.uniform(1.5,3.5)
    def _generate_movement(self):
        if (self.pattern or "circle").lower() == "circle":
            self.angle += 0.35 * self.dir_flip
            if self.angle > 6.2832: self.angle -= 6.2832
            elif self.angle < 0: self.angle += 6.2832
            x = int(self.radius * random.uniform(0.9,1.1) * (1.0 if self.angle % 3.14 < 1.57 else -1.0))
            y = int(self.radius * random.uniform(0.4,0.6))
            z = int(self.radius * random.uniform(0.9,1.1) * (1.0 if self.angle % 6.28 < 3.14 else -1.0))
            return x, y, z, 0x0F
        return (random.randint(-self.radius, self.radius), random.randint(-40,40),
                random.randint(-self.radius, self.radius),
                random.choice([0x01,0x02,0x04,0x08,0x0F]))
    def next(self):
        now = time.time()
        if now >= self._next_speed_roll: self._roll_new_speed()
        if now - self.state_start > self.state_duration:
            self.state, self.state_duration = self._pick_next_state()
            self.state_start = now
        self.tick = (self.tick + 1) & 0xFFFFFFFF
        self.counter = (self.counter + 1) & 0xFFFFFFFF
        ps = self.PLAYER_STATE.get(self.state, 1)
        if self.state in ("idle","crouch","prone"):
            x = y = z = 0; ms = 0
        else:
            x, y, z, ms = self._generate_movement()
        return ps, x, y, z, ms, self.tick, self.counter, self.speed_multiplier, self.state

async def movement_worker(sock, ip, port, udp_key_bytes, match_code,
                          account_id, stop_event, match_index):
    loop = asyncio.get_event_loop(); addr = (ip, port)
    tracker = MovementTracker(pattern=MOVEMENT_PATTERN, radius=MOVEMENT_RADIUS)
    sent = 0
    try:
        await asyncio.sleep(random.uniform(1.6, 2.4))
        while not stop_event.is_set():
            try:
                ps, x, y, z, ms, tick, cnt, sm, st = tracker.next()
                pkt = build_movement_packet_2001(udp_key_bytes, 0x6B, ps, x, y, z,
                                                 tick, cnt, ms, account_id, match_code)
                await loop.sock_sendto(sock, pkt, addr); sent += 1
                base = MOVEMENT_TICK_MS / 1000.0
                try: smx = max(0.7, min(float(sm), 1.6))
                except Exception: smx = 1.0
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=max(0.10, min(base/smx, 0.40)))
                    break
                except asyncio.TimeoutError: pass
            except asyncio.CancelledError: break
            except Exception: await asyncio.sleep(0.4)
    except asyncio.CancelledError: pass
    finally: print_info(f"[MOVE] #{match_index} stopped sent={sent}")

async def send_anti_afk_fire(sock, addr, udp_key_bytes, match_code, account_id):
    try:
        _, nr = await layouts_from_mask(match_code)
        try: pid = int(account_id)
        except Exception: pid = 0
        ts = int(time.time() * 1000) & 0xFFFFFFFF
        wid = random.choice([101,102,103,201,202])
        fp = await build_packet(0x68, nr, 0, 104, None, 0,
                                struct.pack("<IIHB", pid & 0xFFFFFFFF, ts, wid, 1),
                                udp_key_bytes, encrypted=False)
        loop = asyncio.get_event_loop()
        await loop.sock_sendto(sock, fp, addr)
        await asyncio.sleep(random.uniform(0.12, 0.26))
        sp = await build_packet(0x68, nr, 0, 105, None, 0,
                                struct.pack("<IIHB", pid & 0xFFFFFFFF, ts+200, wid, 0),
                                udp_key_bytes, encrypted=False)
        await loop.sock_sendto(sock, sp, addr)
        return True
    except Exception: return False

async def anti_afk_worker(sock, ip, port, udp_key_bytes, match_code,
                          account_id, stop_event, match_index):
    addr = (ip, port); fires = 0
    try:
        await asyncio.sleep(random.uniform(1.4, 2.2))
        while not stop_event.is_set():
            try:
                if await send_anti_afk_fire(sock, addr, udp_key_bytes, match_code, account_id):
                    fires += 1
                try:
                    await asyncio.wait_for(stop_event.wait(),
                        timeout=random.uniform(ANTI_AFK_MIN_INTERVAL, ANTI_AFK_MAX_INTERVAL))
                    break
                except asyncio.TimeoutError: pass
            except asyncio.CancelledError: break
            except Exception: await asyncio.sleep(0.9)
    except asyncio.CancelledError: pass
    finally:
        if fires: print_info(f"[AFK] #{match_index} fires={fires}")

async def send_ping(account_id, token, release_version, ping_url=None):
    try:
        try: acc = int(account_id)
        except Exception: acc = 0
        now_ms = int(time.time() * 1000)
        payload = struct.pack("<Q", acc & 0xFFFFFFFFFFFFFFFF) + \
                  struct.pack("<Q", now_ms & 0xFFFFFFFFFFFFFFFF)
        hdrs = {'accept':'*/*','accept-encoding':'deflate, gzip',
                'authorization':f'Bearer {token}',
                'content-type':'application/x-www-form-urlencoded',
                'releaseversion':release_version,'user-agent':'UnityPlayer/2018.4.12f1',
                'x-ga':'v1 1','x-ga-sv':str(int(time.time())),
                'x-real-ip':PING_REAL_IP,'x-request-start':str(now_ms),
                'x-unity-version':'2018.4.12f1'}
        r = await client.post(str(ping_url or PING_URL), headers=hdrs,
                              content=payload, timeout=PING_TIMEOUT)
        return r.status_code == 200
    except Exception: return False

async def ping_worker(account_id, token, release_version, region="BD", ping_url=None):
    if not ENABLE_HTTP_PING: return
    uid_str = str(account_id); ok_count = 0
    try:
        await asyncio.sleep(4.0 + random.uniform(0, 2.0))
        while True:
            if await send_ping(uid_str, token, release_version, ping_url): ok_count += 1
            await asyncio.sleep(max(5.0, PING_INTERVAL + random.uniform(-3.0, 3.0)))
    except asyncio.CancelledError: pass
    finally: print_info(f"[PING] stopped {uid_str} OK={ok_count}")

# ==================== TEAM PACKETS ====================
def create_team(key, iv, game_version="1.132.9", region="IND"):
    reg = str(region).upper() if region else "IND"
    fields = {1:1, 2:{2:bytes.fromhex("01"),3:1,4:3,5:"en",
              8:{1:"IDC3",2:123,3:reg},9:1,10:bytes.fromhex("01090a0b1219202729"),
              11:2,13:1,14:{1:"08FBA33B4BABE2790205390333330000009700050092005F72697EB2134DCBB2467625142201040e38e848dc0e748c3f6aa04d81000000ff1113090dcacfa16d",
              2:478,3:"7e585d55",4:"y[Z]",6:12,7:"15686677735a7506101c",8:str(game_version),
              9:3,10:1,11:"03626253513637754174"},19:329,21:bytes.fromhex("374f521955"),
              24:{1:21},27:"a_6534489873065906362"}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def team_fresh(account_id, key, iv):
    return create_packet(create_proto({1:72, 2:{1:int(account_id)}}).hex(), "0515", key, iv)

def leave_team(account_id, key, iv):
    return create_packet(create_proto({1:6, 2:{1:int(account_id)}}).hex(), "0515", key, iv)

def invite_player_in_team(target_uid, key, iv, region="BD"):
    return create_packet(create_proto({1:2, 2:{1:int(target_uid),2:str(region).upper(),4:1}}).hex(),
                         "0515", key, iv)

def accept_team_invite(inviter_uid, own_uid, group_id, key, iv, region="BD", game_version="1.132.9"):
    reg = str(region).upper()
    fields = {1:4, 2:{1:int(inviter_uid),3:int(own_uid),
              4:bytes.fromhex("0107090a0b120f19202729"),8:1,
              9:{1:"08FBA33B0522052002041B0222220007000C00010004000547E265AE1080779546762514110104076fa2e8770e748c3f6a68ed75000000ff08080500cacfa16d",
                 2:235,3:{14:80,11:86},4:"{Y\\R",6:13,7:{2:4},8:str(game_version),9:2,10:1,11:"0362625351"},
              10:str(group_id),11:{1:"IDC3",2:107,3:reg},13:"en",16:"374f5219",20:{1:21},
              23:"a_6534489873065906362",24:"https://dl-sg-production.freefiremobile.com/",
              27:{1:2,2:4}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def join_team_by_code(team_code, key, iv, region="BD", game_version="1.132.9"):
    reg = str(region).upper()
    fields = {1:3, 2:{1:str(team_code),4:bytes.fromhex("0107090a0b120f19202729"),5:"en",
              8:{1:"IDC3",2:107,3:reg},9:1,13:1,
              14:{1:"08FBA33B0522052002041B0222220007000C00010004000547E265AE1080779546762514110104076fa2e8770e748c3f6a68ed75000000ff08080500cacfa16d",
                  2:235,6:13,8:str(game_version),9:3,10:1}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def start_match_team(account_id, key, iv, region="BD", mode_id=None):
    """CS কিউ প্যাকেট — mode 8 ফিক্সড (লেভেল লাগে না)।"""
    mid = int(mode_id or CS_MODE)
    if mid not in CS_MODE_NAME: mid = CS_MODE
    fields = {1:9, 2:{1:int(account_id), 7:{1:"IDC3", 2:mid, 3:region}}}
    return create_packet(create_proto(fields).hex(), "0515", key, iv)

def ready_for_game(uid, key, iv):
    return create_packet(create_proto({1:15, 2:{1:int(uid), 2:1}}).hex(), "0519", key, iv)

def extract_team_code_from_proto(obj):
    if isinstance(obj, (int, str)):
        s = str(obj).strip()
        if s.isdigit() and len(s) in (6, 7): return s
    elif isinstance(obj, dict):
        for pk in [11,5,1,3,2,4,10,14,8,7,12,"11","5","1","3","2","4","10","14","8","7","12"]:
            if pk in obj:
                v = obj[pk]
                cand = extract_team_code_from_proto(v.get("data") if isinstance(v, dict) and "data" in v else v)
                if cand: return cand
        for k, v in obj.items():
            cand = extract_team_code_from_proto(v.get("data") if isinstance(v, dict) and "data" in v else v)
            if cand: return cand
    elif isinstance(obj, list):
        for item in obj:
            cand = extract_team_code_from_proto(item)
            if cand: return cand
    return None

def _extract_key_iv(res_json):
    if "__RAW_HEX__" in res_json and "__OFFSET__" in res_json:
        try:
            raw = bytes.fromhex(res_json["__RAW_HEX__"])
            rf = extract_raw_fields(raw[int(res_json["__OFFSET__"]):])
            for kf, vf in [(22,23),(24,25),(6,7)]:
                k = rf.get(kf); v = rf.get(vf)
                if isinstance(k,(bytes,bytearray)) and len(k)==16 and \
                   isinstance(v,(bytes,bytearray)) and len(v)==16:
                    return bytes(k), bytes(v)
        except Exception: pass
    found = {}
    for k, v in res_json.items():
        if str(k).startswith("__") or not isinstance(v, dict): continue
        data = v.get("data")
        if data is None: continue
        raw = None
        if isinstance(data,(bytes,bytearray)) and len(data)==16: raw = bytes(data)
        elif isinstance(data, str) and len(data)==32:
            try:
                c = bytes.fromhex(data)
                if len(c)==16: raw = c
            except Exception: pass
        if raw:
            try: found[int(k)] = raw
            except Exception: pass
    if len(found) < 2: return None, None
    for kf, vf in [(22,23),(24,25),(6,7)]:
        if kf in found and vf in found: return found[kf], found[vf]
    sk = sorted(found.keys())
    return found[sk[0]], found[sk[1]]

async def aes_encrypt(payload, key, iv):
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(payload, AES.block_size))

# ==================== VERSION / LOGIN ====================
_VER_CACHE = {"v": None, "t": 0.0}

def get_app_version():
    if _VER_CACHE["v"] and time.time() - _VER_CACHE["t"] < 1800:
        return _VER_CACHE["v"]
    try:
        v = play_scraper('com.dts.freefireth').get('version')
        if v:
            _VER_CACHE["v"] = v; _VER_CACHE["t"] = time.time()
            return v
    except Exception:
        pass
    return _VER_CACHE["v"] or "1.132.9"

async def version_config(region="BD"):
    app_version = get_app_version()
    lang = REGION_LANG.get(region.upper(), "en")
    urls = [
        (f"https://version.ggwhitehawk.com/live/ver.php?version={app_version}"
         f"&lang={lang}&device=android&channel=android&appstore=googleplay"
         f"&region={region.upper()}&whitelist_version=1.3.0&whitelist_sp_version=1.0.0"),
        (f"https://version.ppmainecoonghj.com/live/ver.php?version={app_version}"
         f"&lang={lang}&device=android&channel=android&appstore=googleplay"
         f"&region={region.upper()}&whitelist_version=1.3.0&whitelist_sp_version=1.0.0"),
    ]
    for url in urls:
        for attempt in range(2):
            try:
                r = await client.get(url, timeout=12.0)
                j = r.json()
                server_url = j.get("server_url")
                gops = [u.strip() for u in j.get("gop_url","").split(";") if u.strip()]
                if not server_url: break
                return (j.get("latest_release_version"), j.get("remote_version"), server_url,
                        gops[0] if gops else "https://ffmconnect.ppmainecoonghj.com", app_version)
            except Exception as e:
                if attempt == 0:
                    await asyncio.sleep(0.6)
                else:
                    print_error(f"[VERCONFIG] {type(e).__name__}")
    return None

async def get_access_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {"Host":"100067.connect.garena.com",
        "User-Agent":"Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)",
        "Content-Type":"application/x-www-form-urlencoded",
        "Accept-Encoding":"gzip, deflate, br","Connection":"close"}
    data = {"uid":str(uid),"password":password,"response_type":"token",
            "client_type":"2","client_secret":HEX_KEY,"client_id":"100067"}
    for i in range(5):
        try:
            r = await client.post(url, headers=hdrs, data=data)
            if r.status_code == 200:
                j = r.json()
                oid = j.get("open_id"); at = j.get("access_token")
                if oid and at: return oid, at, j.get("platform", 4)
        except Exception: pass
        await asyncio.sleep(0.5 + i * 0.4)
    return None

def generate_signature(payload_str):
    return hmac.new(API_KEY, payload_str.encode(), hashlib.sha256).hexdigest()

def _gop_headers(app_version, payload):
    return {"User-Agent": f"GarenaMSDK/4.0.44(SM-E135F ;Android 14;en;GB;app {app_version} 2019118525;)",
            "Authorization": f"Signature {generate_signature(payload)}",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8"}

async def register_account(password, gop_url, app_version):
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    payload = json.dumps({"app_id":100067,"client_type":2,"password":password,"source":2},
                         separators=(',',':'))
    for i in range(3):
        try:
            async with aiohttp.ClientSession(connector=connector) as s:
                async with s.post(f"{gop_url}/api/v2/oauth/guest:register",
                                  headers=_gop_headers(app_version, payload), data=payload,
                                  timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = json.loads(await resp.text())
                    if data.get("code") == 0: return data["data"]["uid"]
        except Exception as e:
            print_error(f"[REGISTER] {type(e).__name__}")
        await asyncio.sleep(0.7 + i * 0.5)
    return None

async def grant_token(uid, password, gop_url, app_version):
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    payload = json.dumps({"client_id":100067,"client_secret":HEX_KEY,"client_type":2,
                          "device_id":f"02-{uuid.uuid4()}","password":password,
                          "response_type":"token","uid":int(uid)}, separators=(',',':'))
    for i in range(3):
        try:
            async with aiohttp.ClientSession(connector=connector) as s:
                async with s.post(f"{gop_url}/api/v2/oauth/guest/token:grant",
                                  headers=_gop_headers(app_version, payload), data=payload,
                                  timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = json.loads(await resp.text())
                    if data.get("code") == 0: return data["data"]
        except Exception as e:
            print_error(f"[GRANT] {type(e).__name__}")
        await asyncio.sleep(0.7 + i * 0.5)
    return None

# ==================== PAYLOAD ====================
async def get_payload(access_token, open_id, platform, version, lang_code="en", region="BD"):
    device_id = f"Google|{uuid.uuid4()}"
    ml = {
        "3": str(datetime.now())[:-7], "4": "free fire", "5": 1, "7": f"{version}",
        "8": "Android OS 14 / API-34 (UP1A.231005.007/E135FXXSEEZE2)",
        "9": "Handheld", "11": "CarrierDataNetwork", "12": 1672, "13": 750, "14": "338",
        "15": "ARMv7 VFPv3 NEON | 2002 | 8", "16": 3702, "17": "Mali-G52",
        "18": "OpenGL ES 3.2 v1.r38p1-01bet0-mbs2v41_0.6d20ec041e51b2f2d25dfc265586ebe8",
        "19": device_id, "20": "104.28.197.151", "21": lang_code,
        "22": f"{open_id}", "23": f"{platform}", "24": "Handheld",
        "25": "samsung SM-E135F", "26": str(region).upper(),
        "29": f"{access_token}", "30": 1, "42": "Cellular",
        "57": "7428b253defc164018c604a1ebbfebdf",
        "60": 52037, "61": 5355, "62": 3723, "63": 3,
        "64": 5483, "65": 52037, "66": 5483, "67": 52037, "73": 2,
        "74": "/data/app/~~yACsV8QOk9OexgajWQP30A==/com.dts.freefireth-Bi_wPVrrhYM2nYncc29q7Q==/lib/arm",
        "76": 1,
        "77": "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~yACsV8QOk9OexgajWQP30A==/com.dts.freefireth-Bi_wPVrrhYM2nYncc29q7Q==/base.apk",
        "78": 3, "79": 1, "81": "32", "83": "2019121229",
        "86": "OpenGLES2", "87": 8191, "88": int(platform), "92": 16091, "93": "android",
        "94": "KqsHT3Yeqo3RLRl8efNiL3aL/1SHwlSrtK0DwNAqdkNBQz70TeVy+icaIwuR3UK4b65Uf3IG5xBFEv0uu+jQZI+rOYCmNCsXjJT4QcZaYgoaaUGG",
        "95": 111107, "96": "{\"cur_rate\":null,\"support_etc2\":false}",
        "97": 1, "98": 1, "99": f"{platform}", "100": f"{platform}",
        "102": "4503454457550c0766", "104": 53792, "105": 1,
        "106": "https://dl-bs.ppmainecoonghj.com/live/ABHotUpdates/|https://core-bs.ppmainecoonghj.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462",
        "107": "c8e41b7a93f02d56e1a94c7b8203f5d1",
    }
    gld = dict(ml); gld["90"] = "Khulna"; gld["91"] = "D"; gld["99"] = "0"; gld["103"] = 1
    return (bytes.fromhex(encrypt_aes(create_proto(ml).hex())),
            bytes.fromhex(encrypt_aes(create_proto(gld).hex())))

async def major_login(payload, login_url, release_version):
    url = f"{login_url.rstrip('/')}/MajorLogin"
    hdrs = {"Accept":"*/*","Authorization":"Bearer ",
            "Content-Type":"application/x-www-form-urlencoded",
            "ReleaseVersion":f"{release_version}",
            "User-Agent":"UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "X-GA":"v1 1","X-GA-SV":str(int(time.time())),
            "X-Unity-Version":"2018.4.12f1"}
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.post(url, headers=hdrs, data=payload, ssl=ssl_ctx) as r:
                content = await r.read()
                if r.status != 200 or len(content) < 200: return None
                best = None; best_score = -1; best_off = 0
                for offset in [64,0,48,32,80,16,128,8,96,60,56,40,24,20,12,4]:
                    if offset >= len(content): continue
                    cb = content[offset:]; cand = None
                    try: cand = decode_protobuf_dict(cb)
                    except Exception: pass
                    if not cand:
                        try:
                            c2 = decode_protobuf_2(cb)
                            if c2: cand = {str(k):{"data":v} for k,v in c2.items()}
                        except Exception: pass
                    if not cand: continue
                    keys = set(cand.keys())
                    score = len(cand) + (100 if ("8" in keys or 8 in keys) else 0) \
                            + (50 if ("10" in keys or 10 in keys) else 0)
                    if score > best_score: best, best_score, best_off = cand, score, offset
                    if ("8" in keys) and ("10" in keys): break
                if not best or (("8" not in best) and (8 not in best)): return None
                best["__RAW_HEX__"] = content.hex(); best["__OFFSET__"] = best_off
                return best
    except Exception as e:
        print_error(f"[MAJOR-LOGIN] {type(e).__name__}"); return None

async def get_login_data(payload, jwt_token, server_url, release_version):
    url = f"{server_url.rstrip('/')}/GetLoginData"
    hdrs = {"Accept":"*/*","Authorization":f"Bearer {jwt_token}",
            "Content-Type":"application/x-www-form-urlencoded",
            "ReleaseVersion":f"{release_version}",
            "User-Agent":"UnityPlayer/2018.4.12f1","X-GA":"v1 1",
            "X-GA-SV":str(int(time.time())),"X-Unity-Version":"2018.4.12f1"}
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
            async with s.post(url, headers=hdrs, data=payload, ssl=ssl_ctx) as r:
                if r.status != 200: return None
                content = await r.read()
                for off in [0,64,48,32,80,16,128,8,96]:
                    if off >= len(content): continue
                    try:
                        c = decode_protobuf_dict(content[off:])
                        if c and len(c) >= 3: return c
                    except Exception: pass
                for off in [0,64,48,32,80]:
                    if off >= len(content): continue
                    c = decode_protobuf_2(content[off:])
                    if c and len(c) >= 3: return {str(k):{"data":v} for k,v in c.items()}
        return None
    except Exception: return None

async def get_player_personal_show(target_uid, jwt_token, server_url, release_version):
    url = f"{server_url}/GetPlayerPersonalShow"
    payload = bytes.fromhex(encrypt_aes(create_proto({"1":int(target_uid)}).hex()))
    hdrs = {"authorization":f"Bearer {jwt_token}",
            "host":server_url.replace("https://","").split("/")[0],
            "x-ga":"v1 1","content-type":"application/x-www-form-urlencoded",
            "releaseversion":f"{release_version}",
            "user-agent":"UnityPlayer/2022.3.47f1","accept":"*/*",
            "x-unity-version":"2022.3.47f1"}
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
            async with s.post(url, headers=hdrs, data=payload, ssl=ssl_ctx) as r:
                if r.status != 200: return None
                return decode_protobuf_2(await r.read())
    except Exception: return None

# ==================== CLAN ====================
def _get_region_from_jwt(jwt_token):
    try:
        p = jwt_token.split('.')[1]; p += '=' * (-len(p) % 4)
        d = json.loads(base64.urlsafe_b64decode(p))
        return (d.get('lock_region') or d.get('noti_region') or 'BD').upper()
    except Exception: return "BD"

async def _clan_hosts(region=None, server_url=None):
    cands = []
    if CLAN_HOST_OVERRIDE: cands.append(CLAN_HOST_OVERRIDE.rstrip("/"))
    if server_url:
        cands.append(server_url.rstrip("/"))
        if "ggpolarbear.com" in server_url:
            cands.append(server_url.replace("ggpolarbear.com", "ppmainecoonghj.com").rstrip("/"))
    r = str(region or "BD").upper()
    if r == "IND": cands.append("https://client.ind.freefiremobile.com")
    elif r in ("BR","US","NA","SAC"): cands.append("https://client.us.freefiremobile.com")
    cands += CLAN_HOST_FALLBACK
    loop = asyncio.get_running_loop(); out, seen = [], set()
    for base in cands:
        if base in seen: continue
        seen.add(base)
        host = base.split("://", 1)[-1].split("/")[0]
        try:
            info = await asyncio.wait_for(loop.getaddrinfo(host, 443, family=socket.AF_INET), timeout=4)
            if info: out.append(base)
            else: print_warning(f"[CLAN] DNS empty → {host}")
        except Exception: print_warning(f"[CLAN] DNS dead → {host}")
    return out

def _create_clan_payload(clan_id):
    if _CLAN_PB_AVAILABLE:
        try:
            msg = reqClan_pb2.MyMessage(); msg.field_1 = int(clan_id)
            return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(
                pad(msg.SerializeToString(), AES.block_size))
        except Exception: pass
    try:
        return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(
            pad(create_proto({1: int(clan_id)}), AES.block_size))
    except Exception as e:
        print_error(f"[CLAN] payload: {e}"); return None

async def join_clan(jwt_token, clan_id, server_url=None, region=None, release_version=None):
    if not clan_id or str(clan_id).strip() in ("", "0"): return False
    region = region or _get_region_from_jwt(jwt_token)
    release_version = str(release_version or "1.132.9")
    payload = _create_clan_payload(clan_id)
    if not payload: return False
    hosts = await _clan_hosts(region, server_url)
    if not hosts:
        print_error("[CLAN] no reachable host"); return False
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
    for base in hosts:
        host = base.split("://", 1)[-1].split("/")[0]
        hdrs = {"Authorization": f"Bearer {jwt_token}", "Host": host,
                "X-GA": "v1 1", "X-GA-SV": str(int(time.time())),
                "X-Unity-Version": "2018.4.12f1", "ReleaseVersion": release_version,
                "Content-Type": "application/x-www-form-urlencoded", "Accept": "*/*",
                "Accept-Encoding": "deflate, gzip",
                "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
                "Connection": "Keep-Alive"}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
                async with s.post(base.rstrip("/") + "/RequestJoinClan",
                                  headers=hdrs, data=payload, ssl=ssl_ctx) as r:
                    body = await r.text(errors="replace")
                    if r.status == 200:
                        print_success(f"[CLAN] ✅ joined {clan_id} via {host}")
                        return True
                    print_warning(f"[CLAN] {host} → HTTP {r.status} {body[:150]}")
        except Exception as e:
            print_warning(f"[CLAN] {host} → {type(e).__name__}")
    return False

async def _auto_join_clan(ad, clan_id, tries=6):
    await asyncio.sleep(5)
    for i in range(tries):
        if await join_clan(ad["token"], clan_id, ad.get("server_url"),
                           ad.get("region"), ad.get("release_version")):
            return True
        await asyncio.sleep(3 + i * 3)
    print_warning(f"[CLAN] {ad.get('account_id')} gave up after {tries}")
    return False

async def _clan_keepalive(ad, clan_id):
    while True:
        await asyncio.sleep(CLAN_REJOIN_EVERY + random.uniform(-120, 120))
        try:
            await join_clan(ad["token"], clan_id, ad.get("server_url"),
                            ad.get("region"), ad.get("release_version"))
        except Exception: pass

# ==================== TCP ====================
async def build_tcp_startup_packet(account_id, token, server_time, key, iv, region="BD", typ='OnLine'):
    uid_hex = f"{int(account_id):016x}"; ts_hex = f"{int(server_time):08x}"
    enc = (await aes_encrypt(token.encode(), key, iv)).hex()
    enc_len = f"{len(enc)//2:08x}"
    reg = str(region).upper() if region else "BD"
    if typ == 'OnLine':
        pfx = '7219' if reg == 'BD' else ('7214' if reg == 'IND' else '7215')
        return f"{pfx}{uid_hex}{ts_hex}00000000{enc_len}{enc}"
    pfx = '8119' if reg == 'BD' else ('8114' if reg == 'IND' else '8115')
    return f"{pfx}{uid_hex}{ts_hex}{enc_len}{enc}"

async def send_keep_alive(region="BD"):
    reg = str(region).upper() if region else "BD"
    return bytes.fromhex("0219" if reg == "BD" else ("0214" if reg == "IND" else "0215"))

# ==================== UDP HELPERS ====================
async def has_ssan_zig(n):
    z = (n << 1) & 0xFFFFFFFFFFFFFFFF; out = bytearray()
    while z >= 0x80:
        out.append((z & 0x7F) | 0x80); z >>= 7
    out.append(z); return bytes(out)

async def uleb_async(n):
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

async def tea_enc(v0, v1, k0, k1, k2, k3):
    s = 0
    for _ in range(_ROUNDS):
        s = (s + _DELTA) & 0xFFFFFFFF
        v0 = (v0 + (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^ ((v1+s)&0xFFFFFFFF) ^
                     (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF
        v1 = (v1 + (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^ ((v0+s)&0xFFFFFFFF) ^
                     (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF
    return v0, v1

async def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (((((v0<<4)&0xFFFFFFFF)+k2)&0xFFFFFFFF ^ ((v0+s)&0xFFFFFFFF) ^
                     (((v0>>5)+k3)&0xFFFFFFFF)))) & 0xFFFFFFFF
        v0 = (v0 - (((((v1<<4)&0xFFFFFFFF)+k0)&0xFFFFFFFF ^ ((v1+s)&0xFFFFFFFF) ^
                     (((v1>>5)+k1)&0xFFFFFFFF)))) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1

async def tea_cbc_encrypt(padded, key_bytes):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0,4,8,12))
    out = bytearray(len(padded)); pc = bytearray(8); pi = bytearray(8)
    for i in range(0, len(padded), 8):
        x = bytearray(8)
        for j in range(8): x[j] = padded[i+j] ^ pc[j]
        e0,e1 = await tea_enc(struct.unpack_from("<I", x, 0)[0],
                              struct.unpack_from("<I", x, 4)[0], k0,k1,k2,k3)
        enc = bytearray(8)
        struct.pack_into("<I", enc, 0, e0); struct.pack_into("<I", enc, 4, e1)
        for j in range(8): out[i+j] = enc[j] ^ pi[j]
        pc[:] = out[i:i+8]; pi[:] = x
    return bytes(out)

async def tea_cbc_decrypt(body, key_bytes):
    k0,k1,k2,k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0,4,8,12))
    out = bytearray(len(body)); pi = bytearray(8); pc = bytearray(8)
    x = bytearray(8); dec = bytearray(8)
    for i in range(0, len(body), 8):
        for j in range(8): x[j] = body[i+j] ^ pi[j]
        d0,d1 = await tea_dec(struct.unpack_from("<I", x, 0)[0],
                              struct.unpack_from("<I", x, 4)[0], k0,k1,k2,k3)
        struct.pack_into("<I", dec, 0, d0); struct.pack_into("<I", dec, 4, d1)
        for j in range(8): out[i+j] = dec[j] ^ pc[j]
        pc[:] = body[i:i+8]; pi[:] = dec
    return bytes(out)

async def build_padded(content):
    pad_len = (8 - (len(content) + 10) % 8) % 8
    return bytes([pad_len,0,0]) + b"\x00"*pad_len + content + b"\x00"*7

async def encode_header(layout, so, cmd, oid, flags, length, k, v80):
    out = bytearray()
    for code in layout:
        val = {0:so,1:cmd,2:oid,3:flags,4:length}[code]
        if _FIELD_SIZES[code] == 1: out.append((val & 0xFF) ^ k)
        else:
            v = ((val & 0xFFFF) ^ v80) & 0xFFFF
            out.append(v & 0xFF); out.append((v >> 8) & 0xFF)
    return bytes(out)

async def crc7_buff(crc, buf):
    c = crc & 0x7F
    for b in buf: c = CRC7_TABLE[((2*(c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F

async def sv_frame(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]; v80 = ((k<<8)|k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    pkt = bytearray(bytearray([msg_key,0]) +
                    await encode_header(layout, so, cmd, oid, flags, len(body), k, v80) + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def build_match_startup_packets(token, udp_key, match_code, account_id, block_val,
                                      server_ip="", region="BD", client_version="1.132.9",
                                      client_version_code="2019121229",
                                      access_token="", mode_id=None, map_id=None):
    token = token.strip()
    udp_key = bytes.fromhex(udp_key)
    match_code = [int(ch) for ch in str(match_code).strip()]
    mode_id = int(mode_id or CS_MODE)
    if mode_id not in CS_MODE_NAME: mode_id = CS_MODE
    map_id = int(map_id if map_id is not None else _cur_map())
    thunder_jwt = token[:660] if len(token) > 660 else token
    sharma_jwt = token[660:] if len(token) > 660 else ""
    eth = thunder_jwt.encode() if isinstance(thunder_jwt, str) else thunder_jwt
    esh = sharma_jwt.encode() if isinstance(sharma_jwt, str) else sharma_jwt
    garena420 = await has_ssan_zig(len(eth)) + eth
    reg = str(region).upper() if region else "BD"
    csoversea = bytes.fromhex(
        "ca0163736f7665727365612e7374726f6e67686f6c642e66726565666972656d6f62696c652e636f6d"
        "3b302e302e302e303b33342e3132362e37362e34353b33342e38372e3137372e31343b33342e38372e"
        "3137302e3233303b33352e3138352e3138332e35370000000000000100000000000000000000000001"
        "00000800000100000000000100a8a2d7bebd8d8bdf110200")
    mid = bytes.fromhex('0000000001000102030101') + await has_ssan_zig(len(reg)) + reg.encode()
    mid += bytes.fromhex('0001030003000004')
    mid += await has_ssan_zig(len(client_version)) + client_version.encode()
    mid += await has_ssan_zig(len(client_version_code)) + client_version_code.encode()
    mid += csoversea
    clean_ip = server_ip.split(':')[0] if server_ip else "0.0.0.0"
    mid += await has_ssan_zig(len(clean_ip)) + clean_ip.encode()
    if access_token:
        at = access_token.strip()
        mid += await has_ssan_zig(len(at)) + at.encode()
    mid += await has_ssan_zig(len(esh)) + esh
    tg = (await uleb_async(int(account_id)) + await uleb_async(int(block_val)) +
          await uleb_async(1) + await uleb_async(mode_id) +
          await uleb_async(int(block_val)) + await uleb_async(map_id) + mid)
    return ((await sv_frame(0x5E, match_code, 2, 447, 0, 1, garena420, udp_key)).hex(),
            (await sv_frame(0x5A, match_code, 2, 448, 1, 1, tg, udp_key)).hex())

async def build_hello_packet(text, key, layout):
    data = text.encode("utf-8")
    if len(data) > 25: raise ValueError("too long")
    content = b"\x10\x00\x00\x00" + data + b"\x00" * (29 - 4 - len(data))
    k = key[0]; v80 = ((k<<8)|k) & 0xFFFF
    layout = [int(c) for c in str(layout).strip()] if isinstance(layout, str) else list(layout)
    enc_body = await tea_cbc_encrypt(await build_padded(content), key)
    pkt = bytearray([0x63, 0x00]) + await encode_header(layout, 1, 1, 0, 1, len(enc_body), k, v80) + enc_body
    pkt[1] = await crc7_buff(0, pkt[2:]) & 0x7F
    return bytes(pkt).hex()

async def classify(frame):
    n = MESSAGE_ID_TO_NAME.get(frame["cmd"], f"UNKNOWN_{frame['cmd']}")
    if n == "UDP_HELLO": return "HELLO"
    if n == "UDP_ACK": return "ACK"
    if n == "UDP_PING": return "PING"
    if n == "RUDP_JOIN_MATCH": return "JOIN_MATCH"
    return n

async def build_packet(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]; v80 = ((k<<8)|k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0])
    for code in layout:
        val = {0:so,1:cmd,2:oid,3:flags,4:len(body)}[code]
        if _FIELD_SIZES[code] == 1: hdr.append((val & 0xFF) ^ k)
        else:
            v = ((val & 0xFFFF) ^ v80) & 0xFFFF
            hdr.append(v & 0xFF); hdr.append((v >> 8) & 0xFF)
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)

async def layouts_from_mask(mask):
    ru = [int(c) for c in str(mask).strip()]
    return ru, [c for c in ru if c != 2]

async def reply_for(frame, key, mask, ack_key=0x68, ping_key=0x6D, hello_key=0x5B, ack_style="short"):
    ru, nr = await layouts_from_mask(mask)
    typ = await classify(frame)
    if typ == "HELLO":
        if ack_style == "echo":
            return typ, await build_packet(hello_key, nr, 1, 1, None, 1,
                                           frame["content"] or b"\x10\x00\x00\x00", key)
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x01\x00", key)
    if typ == "ACK":
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1,
                                       frame["content"] or b"\x01\x00", key)
    if typ == "PING":
        c = frame["content"]; counter = c[:4] if len(c) >= 4 else c
        return typ, await build_packet(ping_key, nr, 0, 3, None, 0,
                                       counter + b"\x00\x00\x00", key, encrypted=False)
    if typ == "JOIN_MATCH":
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x02\x00", key)
    return typ, None

async def keepalive_ping(sock, ip, port, key_bytes, mask, stop_event):
    nr = (await layouts_from_mask(mask))[1]
    keys = [0x66,0x6D,0x69,0x6C,0x6B,0x6E,0x6F,0x70]
    loop = asyncio.get_event_loop(); i = 0
    while not stop_event.is_set():
        pkt = await build_packet(keys[i % len(keys)], nr, 0, 3, None, 0,
                                 struct.pack("<I", int(time.time()*1000) & 0xFFFFFFFF) + b"\x00\x00\x00",
                                 key_bytes, encrypted=False)
        try: await loop.sock_sendto(sock, pkt, (ip, port))
        except Exception: pass
        i += 1
        try: await asyncio.wait_for(stop_event.wait(), timeout=2.5)
        except asyncio.TimeoutError: pass

async def try_header(buf, layout, k, v80):
    off = 2; out = {}
    for code in layout:
        size = _FIELD_SIZES[code]
        if off + size > len(buf): return None
        out[_FIELD_NAMES[code]] = (buf[off] ^ k) if size == 1 else \
            ((buf[off] | (buf[off+1] << 8)) ^ v80) & 0xFFFF
        off += size
    out["headerLen"] = off
    return out

async def oicq_unpad(padded):
    if not padded or len(padded) < 8: return None
    if not all(padded[-1-i] == 0 for i in range(7)): return None
    s = 3 + (padded[0] & 0x07); e = len(padded) - 7
    return padded[s:e] if s < e else b""

async def decode_packet(packet, key, mask=None):
    data = bytes(packet) if isinstance(packet, bytes) else bytes.fromhex(packet)
    if len(data) < 8: return None
    k = key[0]; v80 = ((k<<8)|k) & 0xFFFF
    crc_ok = (data[1] & 0x7F) == await crc7_buff(0, data[2:])
    cands = []
    if mask:
        ru, nr = await layouts_from_mask(mask)
        layouts = [("RUDP", ru), ("nonRUDP", nr)]
    else:
        layouts = [("RUDP", list(p)) for p in itertools.permutations([0,1,2,3,4])]
        layouts += [("nonRUDP", list(p)) for p in itertools.permutations([0,1,3,4])]
    for kind, layout in layouts:
        f = await try_header(data, layout, k, v80)
        if not f: continue
        if f["flags"] > 7 or f["sendOption"] > 7: continue
        if f["length"] != len(data) - f["headerLen"]: continue
        body = data[f["headerLen"]:f["headerLen"]+f["length"]]
        if f["flags"] & 1:
            if len(body) < 8 or len(body) % 8 != 0: continue
            content = await oicq_unpad(await tea_cbc_decrypt(body, key))
            if content is None: continue
        else: content = body
        cands.append({"kind":kind,"layout":layout,"headerLen":f["headerLen"],"msgKey":data[0],
                      "cmd":f["cmd"],"flags":f["flags"],"sendOption":f["sendOption"],
                      "orderId":f.get("orderId"),"length":f["length"],"content":content,
                      "crcOk":crc_ok,"score":(1 if crc_ok else 0) + (1 if content is not None else 0)})
    if not cands: return None
    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands[0]

# ==================== MATCH COUNTERS ====================
_match_counters: Dict[str, int] = {}
_match_counter_lock = asyncio.Lock()

async def _inc_match(uid):
    async with _match_counter_lock:
        _match_counters[uid] = _match_counters.get(uid, 0) + 1
        return _match_counters[uid]

async def _dec_match(uid):
    async with _match_counter_lock:
        if _match_counters.get(uid, 0) > 0: _match_counters[uid] -= 1
        return _match_counters.get(uid, 0)

async def _get_match_count(uid):
    async with _match_counter_lock:
        return _match_counters.get(uid, 0)

# ==================== TOKEN CACHE ====================
_token_cache_memo: Dict[str, Any] = {}
_token_cache_memo_time: float = 0.0
_TOKEN_CACHE_MEMO_TTL = 5.0

def _json_serializer(obj):
    if isinstance(obj, (bytes, bytearray)): return {"__bytes_hex__": bytes(obj).hex()}
    raise TypeError(f"Type {type(obj)} not serializable")

def _json_deserializer(obj):
    if isinstance(obj, dict):
        if "__bytes_hex__" in obj and len(obj) == 1:
            try: return bytes.fromhex(obj["__bytes_hex__"])
            except Exception: return b""
        return {k: _json_deserializer(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_json_deserializer(x) for x in obj]
    return obj

def _load_token_cache():
    global _token_cache_memo, _token_cache_memo_time
    now = time.time()
    if _token_cache_memo and (now - _token_cache_memo_time) < _TOKEN_CACHE_MEMO_TTL:
        return _token_cache_memo
    if not os.path.exists(TOKEN_CACHE_FILE): return {}
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f: c = f.read().strip()
        if not c: return {}
        p = _json_deserializer(json.loads(c))
        _token_cache_memo = p; _token_cache_memo_time = now
        return p
    except Exception:
        try: os.remove(TOKEN_CACHE_FILE)
        except Exception: pass
        return {}

def _save_token_cache(cache):
    global _token_cache_memo, _token_cache_memo_time
    try:
        _write_json(TOKEN_CACHE_FILE, cache)
        _token_cache_memo = cache; _token_cache_memo_time = time.time()
    except Exception as e: print_error(f"Cache save: {e}")

def cache_get(uid):
    e = _load_token_cache().get(str(uid))
    if not e: return None
    if time.time() - e.get("cached_at", 0) > TOKEN_CACHE_TTL:
        cache_invalidate(uid); return None
    if str(e.get("account_id","")).isdigit(): e["account_id"] = int(e["account_id"])
    if isinstance(e.get("login_payload_data"), str):
        try: e["login_payload_data"] = bytes.fromhex(e["login_payload_data"])
        except Exception: pass
    if not isinstance(e.get("login_payload_data"), (bytes, bytearray)):
        cache_invalidate(uid); return None
    return e

def cache_set(uid, data):
    cache = _load_token_cache()
    e = dict(data); e["cached_at"] = time.time()
    cache[str(uid)] = e; _save_token_cache(cache)

def cache_invalidate(uid):
    cache = _load_token_cache()
    if str(uid) in cache:
        del cache[str(uid)]; _save_token_cache(cache)

# ==================== PLAY GAME ====================
async def play_game(server_ip_port, thunder, sharma, udp_key, match_code,
                    account_id, player_region, client_version, key, iv, match_index,
                    mode_id=None, map_id=None,
                    on_match_complete=None, on_match_fail=None):
    t0 = time.time()
    ping_task = anti_task = move_task = None
    sock = None
    ping_stop = asyncio.Event(); anti_stop = asyncio.Event(); move_stop = asyncio.Event()
    uid_str = str(account_id)
    completed_cleanly = False
    in_game = False
    startup_deadline = time.time() + STARTUP_TIMEOUT
    mname = CS_MODE_NAME.get(int(mode_id or CS_MODE), "CS")
    try:
        ip, port = server_ip_port.split(":"); port = int(port)
        resolved_ip = await resolve_host_cloudflare(ip)
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: sock.bind(('0.0.0.0', 0))
        except Exception: pass
        optimize_udp_socket(sock); sock.setblocking(False)
        udp_key_bytes = bytes.fromhex(udp_key)
        await loop.sock_sendto(sock, bytes.fromhex(
            await build_hello_packet(f"{account_id}_2585", udp_key_bytes, match_code)),
            (resolved_ip, port))
        print_info(f"[CS #{match_index}] hello → {resolved_ip}:{port} | {mname} | map {map_id}")

        ack_state = "waiting_for_hello_reply"
        thunder_sent = False; join_match_received = False; local_closed = False
        send_lock = asyncio.Lock(); anti_started = False
        ping_task = asyncio.create_task(
            keepalive_ping(sock, resolved_ip, port, udp_key_bytes, match_code, ping_stop))
        last_activity = time.time()

        async def start_workers():
            nonlocal anti_task, move_task, anti_started
            if anti_started: return
            anti_started = True
            anti_task = asyncio.create_task(anti_afk_worker(
                sock, resolved_ip, port, udp_key_bytes, match_code, account_id, anti_stop, match_index))
            if ENABLE_SPEED_MOVEMENT:
                move_task = asyncio.create_task(movement_worker(
                    sock, resolved_ip, port, udp_key_bytes, match_code, account_id, move_stop, match_index))

        async def send_ts():
            nonlocal ack_state, thunder_sent
            if thunder_sent: return
            async with send_lock:
                if thunder_sent: return
                try:
                    await loop.sock_sendto(sock, bytes.fromhex(thunder), (resolved_ip, port))
                    thunder_sent = True
                    print_info(f"[CS #{match_index}] thunder sent")
                    await asyncio.sleep(0.28)
                    await loop.sock_sendto(sock, await build_packet(
                        0x68, (await layouts_from_mask(match_code))[1], 0, 2, None, 1,
                        b"\x01\x00", udp_key_bytes), (resolved_ip, port))
                    await asyncio.sleep(0.35)
                    await loop.sock_sendto(sock, bytes.fromhex(sharma), (resolved_ip, port))
                    ack_state = "thunder_sharma_sent"
                    print_info(f"[CS #{match_index}] sharma sent")
                    await start_workers()
                except Exception as e:
                    print_error(f"[CS #{match_index}] startup: {e}")

        while not local_closed:
            if time.time() - t0 > MAX_MATCH_DURATION:
                completed_cleanly = True
                print_info(f"[CS #{match_index}] max duration, back to lobby")
                break

            if not in_game and time.time() > startup_deadline:
                print_warning(f"[CS #{match_index}] ❌ startup timeout "
                              f"(state={ack_state}) → requeue")
                break

            try:
                response, server_addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), timeout=1.5)
                if response:
                    last_activity = time.time()
                    frame = await decode_packet(response, udp_key_bytes, match_code)
                    if frame:
                        ptype = await classify(frame)
                        if frame['cmd'] in (103, 107):
                            print_success(f"[★] CS #{match_index} END (cmd={frame['cmd']})")
                            completed_cleanly = True; local_closed = True; continue
                        if frame['cmd'] == 101:
                            try:
                                await loop.sock_sendto(sock, await build_packet(
                                    0x68, (await layouts_from_mask(match_code))[1], 0, 2, None, 1,
                                    b"\x01\x00", udp_key_bytes), server_addr)
                            except Exception: pass
                            continue
                        if ack_state == "thunder_sharma_sent" and not in_game:
                            in_game = True
                            bot_state.cs_in_game += 1
                            print_success(f"[CS #{match_index}] ✅ IN-GAME CONFIRMED | {uid_str} | {mname}")
                        if ptype in ("ACK","PING","HELLO","JOIN_MATCH"):
                            if ptype == "HELLO" and ack_state == "waiting_for_hello_reply":
                                _, reply = await reply_for(frame, udp_key_bytes, match_code)
                                if reply: await loop.sock_sendto(sock, reply, server_addr)
                                ack_state = "ack_sent_waiting"
                                print_info(f"[CS #{match_index}] hello-reply")
                            elif ptype == "ACK":
                                if ack_state in ("waiting_for_hello_reply","ack_sent_waiting"):
                                    if ack_state == "waiting_for_hello_reply":
                                        _, reply = await reply_for(frame, udp_key_bytes, match_code)
                                        if reply: await loop.sock_sendto(sock, reply, server_addr)
                                    ack_state = "ready_to_send_thunder"
                                    print_info(f"[CS #{match_index}] ack → ready")
                                else:
                                    _, reply = await reply_for(frame, udp_key_bytes, match_code)
                                    if reply: await loop.sock_sendto(sock, reply, server_addr)
                            elif ptype == "PING":
                                _, reply = await reply_for(frame, udp_key_bytes, match_code)
                                if reply: await loop.sock_sendto(sock, reply, server_addr)
                            elif ptype == "JOIN_MATCH" and not join_match_received:
                                _, reply = await reply_for(frame, udp_key_bytes, match_code)
                                if reply:
                                    await loop.sock_sendto(sock, reply, server_addr)
                                    join_match_received = True
            except asyncio.TimeoutError:
                if ack_state == "ready_to_send_thunder" and not thunder_sent:
                    await send_ts()
                elif ack_state == "waiting_for_hello_reply":
                    if (time.time() - last_activity) > 5.0:
                        try:
                            await loop.sock_sendto(sock, bytes.fromhex(await build_hello_packet(
                                f"{account_id}_2585", udp_key_bytes, match_code)), (resolved_ip, port))
                        except Exception: pass
                        last_activity = time.time()
                elif ack_state == "thunder_sharma_sent":
                    if (time.time() - last_activity) > MATCH_IDLE_TIMEOUT:
                        completed_cleanly = True; break
            except (BlockingIOError, OSError):
                await asyncio.sleep(0.3); continue
            except Exception:
                await asyncio.sleep(0.3); continue
            if ack_state == "ready_to_send_thunder" and not thunder_sent:
                await send_ts()
        return f"match #{match_index} finished"
    except Exception as e:
        print_error(f"[CS #{match_index}] {e}")
        return f"match #{match_index} error"
    finally:
        if completed_cleanly:
            try: bot_state.increment_match(uid_str)
            except Exception: pass
            print_success(f"[★] CS Match #{match_index} Complete | UID: {uid_str}")
            if on_match_complete:
                try: asyncio.create_task(on_match_complete())
                except Exception: pass
            async def _post(uid):
                for w in (4.0, 7.0, 11.0):
                    await asyncio.sleep(w)
                    await refresh_account_profile(uid)
            asyncio.create_task(_post(uid_str))
        elif not in_game:
            bot_state.cs_start_fail += 1
            if on_match_fail:
                try: asyncio.create_task(on_match_fail())
                except Exception: pass
        anti_stop.set(); move_stop.set(); ping_stop.set()
        for t in (anti_task, move_task):
            if t:
                try: await asyncio.wait_for(t, timeout=2.0)
                except Exception:
                    t.cancel()
                    try: await t
                    except Exception: pass
        if ping_task:
            ping_task.cancel()
            try: await ping_task
            except asyncio.CancelledError: pass
        if sock:
            try: sock.close()
            except Exception: pass
        remaining = await _dec_match(uid_str)
        try: bot_state.update_status(uid_str, "ONLINE" if remaining == 0 else "IN_MATCH", remaining)
        except Exception: pass

# ==================== CS SQUAD LOOP ====================
async def functional_lone_wolf(addrs, starter_packet, account_region, client_version,
                                key, iv, account_id="", account_data=None, max_reconnects=12):
    reconnects = 0
    ip, port = addrs.split(":")
    play_matches: List[asyncio.Task] = []
    uid_str = str(account_id)
    current_token = starter_packet; current_key = key; current_iv = iv
    current_account_data = account_data
    _writer_ref = {"w": None}
    _team_active = {"flag": True}
    squad_id = get_squad_id_for_uid(uid_str, current_account_data)
    is_leader = is_squad_leader_for_uid(uid_str, current_account_data)
    expected_squad_size = 2 if has_squad_partner(uid_str, current_account_data) else 1
    _team_state = get_team_state(squad_id)

    def _pick_mode(acc_level):
        m = _mode_for(acc_level)
        _team_state["mode"] = m
        return m

    def _advance_mode():
        _team_state["mode_idx"] = (_team_state.get("mode_idx", 0) + 1) % len(MODE_LADDER)
        print_warning(f"[CS-MODE {squad_id+1}] → "
                      f"{CS_MODE_NAME.get(MODE_LADDER[_team_state['mode_idx']])}")

    async def _on_start_fail():
        _team_state["start_fails"] = _team_state.get("start_fails", 0) + 1
        if _team_state["start_fails"] % 2 == 0:
            nm = _next_map()
            print_warning(f"[CS-MAP] rotate → map {nm}")

    async def _process_social_packet(raw_bytes, tag="MAIN"):
        try:
            hex_data = raw_bytes.hex(); candidates = []
            if len(raw_bytes) >= 6:
                plen = raw_bytes[4]
                if 0 < plen <= (len(raw_bytes) - 5):
                    try:
                        inner = bytes(raw_bytes[5:5+plen])
                        d0 = decode_protobuf_dict(inner) or \
                             {str(k):{"data":v} for k,v in (decode_protobuf_2(inner) or {}).items()}
                        if d0: candidates.append((5, d0))
                    except Exception: pass
            for off in [5,6,10,8,12,14,4,16,0]:
                if off >= len(hex_data): continue
                try: inner = bytes.fromhex(hex_data[off:])
                except Exception: continue
                d = decode_protobuf_dict(inner) or \
                    {str(k):{"data":v} for k,v in (decode_protobuf_2(inner) or {}).items()}
                if d: candidates.append((off, d))
            if not candidates: return
            candidates.sort(key=lambda it: len(it[1]) - (100 if ("0" in it[1] or 0 in it[1]) else 0)
                            + (6 if "5" in it[1] else 0) + (4 if "1" in it[1] else 0), reverse=True)
            decoded = candidates[0][1]

            def _v(c, k):
                if not isinstance(c, dict): return None
                v = c.get(k) if k in c else c.get(str(k))
                return v["data"] if isinstance(v, dict) and "data" in v else v

            f5w = decoded.get("5") or decoded.get(5)
            f5 = f5w["data"] if isinstance(f5w, dict) and "data" in f5w else f5w
            target_uid = None
            if isinstance(f5, dict):
                for fk in [1,2,3,4,6]:
                    c = _v(f5, fk)
                    if c and str(c).isdigit() and 6 <= len(str(c)) <= 15:
                        target_uid = str(c); break
            if not target_uid:
                for fk in [1,2,3]:
                    c = _v(decoded, fk)
                    if c and str(c).isdigit() and 6 <= len(str(c)) <= 15:
                        target_uid = str(c); break
            if not target_uid or not current_account_data: return
            if str(target_uid) == str(current_account_data.get("account_id","")): return
            jwt_l = current_account_data.get("token"); srv_l = current_account_data.get("server_url")
            rel_l = current_account_data.get("release_version"); own = current_account_data.get("account_id")
            if not (jwt_l and srv_l and rel_l and own): return
            payload = bytes.fromhex(encrypt_aes(create_proto({"1":int(target_uid),"2":int(own)}).hex()))
            hdrs = {"authorization":f"Bearer {jwt_l}",
                    "host":srv_l.replace("https://","").split("/")[0],"x-ga":"v1 1",
                    "content-type":"application/x-www-form-urlencoded","accept-encoding":"deflate, gzip",
                    "releaseversion":f"{rel_l}","accept":"*/*","x-unity-version":"2022.3.47f1",
                    "user-agent":"UnityPlayer/2022.3.47f1"}
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
                async with s.post(f"{srv_l.rstrip('/')}/ConfirmFriendRequest",
                                  headers=hdrs, data=payload, ssl=ssl_ctx) as r:
                    if r.status == 200:
                        print_success(f"[FRIEND-{tag}] ✅ {target_uid}")
        except Exception: pass

    async def _coordinator():
        try:
            if not is_leader: return
            waited = 0
            while True:
                async with _team_state["lock"]:
                    n = len(_team_state["peers"])
                if n >= expected_squad_size: break
                if bot_state.is_paused(uid_str): return
                waited += 1
                if waited % 16 == 0:
                    print_info(f"[SQUAD {squad_id+1}] ⏳ peers={n}/{expected_squad_size}")
                await asyncio.sleep(0.4)
            await asyncio.sleep(1.2)
            while await _get_match_count(uid_str) >= MAX_CONCURRENT_MATCHES:
                if bot_state.is_paused(uid_str): return
                await asyncio.sleep(2.0)

            async with _team_state["lock"]:
                _team_state["team_code"] = None
                _team_state["member_ready"] = False
            own_id_num = (current_account_data or {}).get("account_id") or int(uid_str or 0)

            try:
                w = _writer_ref["w"]
                if w and not w.is_closing():
                    w.write(create_team(current_key, current_iv, client_version, region=account_region))
                    await w.drain()
                    await asyncio.sleep(1.4)
                    w.write(team_fresh(int(own_id_num), current_key, current_iv))
                    await w.drain()
            except Exception as e:
                print_error(f"[SQUAD {squad_id+1}] room err: {e}")

            async def _invite(tuid, label=""):
                for _ in range(2):
                    try:
                        w = _writer_ref["w"]
                        if w and not w.is_closing():
                            w.write(invite_player_in_team(int(tuid), current_key, current_iv, account_region))
                            await w.drain()
                            print_info(f"[SQUAD {squad_id+1}] invite{label} → {tuid}")
                    except Exception: pass
                    await asyncio.sleep(0.5)

            acc_idx = get_account_index_for_uid(uid_str, current_account_data)
            _, partner_auth = get_squad_partner_info(acc_idx)
            targets = set()
            if partner_auth:
                targets.add(str(partner_auth))
                pg = bot_state.auth_to_game_id.get(partner_auth)
                if pg: targets.add(str(pg))
            async with _team_state["lock"]:
                for puid, pinfo in _team_state["peers"].items():
                    if puid == uid_str: continue
                    targets.add(str((pinfo.get("data") or {}).get("account_id") or puid))
            for t in targets:
                await _invite(t, " partner")

            await asyncio.sleep(TEAM_INVITE_WAIT + 3.0)
            try:
                w = _writer_ref["w"]
                if w and not w.is_closing():
                    w.write(team_fresh(int(own_id_num), current_key, current_iv)); await w.drain()
            except Exception: pass
            await asyncio.sleep(1.0)

            fails = 0
            while _team_active["flag"]:
                try:
                    if bot_state.is_paused(uid_str): break
                    async with _team_state["lock"]:
                        if _team_state["leader_uid"] != uid_str: break
                        tc = _team_state.get("team_code")
                        rdy_partner = bool(_team_state.get("member_ready", False))

                    if expected_squad_size > 1 and (not rdy_partner or not tc):
                        fails += 1
                        if fails % 4 == 0:
                            for t in targets: await _invite(t, " retry")
                        if fails < 30:
                            await asyncio.sleep(2.0); continue
                        print_warning(f"[SQUAD {squad_id+1}] partner timeout → solo CS")

                    fails = 0
                    own_id = (current_account_data or {}).get("account_id", own_id_num)
                    lvl = int((current_account_data or {}).get("level", 1) or 1)
                    mode = _pick_mode(lvl)
                    bot_state.accounts.setdefault(uid_str, {})["mode"] = mode

                    try:
                        w = _writer_ref["w"]
                        if w and not w.is_closing():
                            w.write(ready_for_game(int(own_id), current_key, current_iv)); await w.drain()
                            await asyncio.sleep(1.0)
                            w.write(start_match_team(int(own_id), current_key, current_iv,
                                                     region=account_region, mode_id=mode))
                            await w.drain()
                            print_success(f"[CS-SEARCH {squad_id+1}] queued "
                                          f"{CS_MODE_NAME.get(mode)} | Lvl {lvl} | map {_cur_map()}")
                    except Exception as e:
                        print_warning(f"[CS-SEARCH {squad_id+1}] queue err: {e}")

                    timeout = MATCH_SEARCH_TIMEOUT + random.uniform(-8, 8)
                    t_start = time.time(); beat = 0.0
                    while _team_active["flag"] and (time.time() - t_start < timeout):
                        if bot_state.is_paused(uid_str): break
                        el = time.time() - t_start
                        if el - beat >= 15.0:
                            beat = el
                            print_info(f"[CS-SEARCH {squad_id+1}] {int(el)}s...")
                        await asyncio.sleep(1.0)

                    if not _team_active["flag"]: break
                    fails += 1
                    bot_state.cs_search_fail += 1
                    print_warning(f"[CS-SEARCH {squad_id+1}] {int(timeout)}s no CS → fail {fails}")
                    _advance_mode()
                    await asyncio.sleep(CS_QUICK_REQUEUE + random.uniform(0, 0.8))

                    if fails % CS_ROOM_RESET_EVERY == 0:
                        bot_state.cs_room_resets += 1
                        print_warning(f"[CS-SEARCH {squad_id+1}] room reset")
                        try:
                            w = _writer_ref["w"]
                            if w and not w.is_closing():
                                w.write(leave_team(int(own_id), current_key, current_iv)); await w.drain()
                                await asyncio.sleep(2.0)
                                w.write(create_team(current_key, current_iv, client_version, region=account_region))
                                await w.drain(); await asyncio.sleep(2.0)
                                w.write(team_fresh(int(own_id), current_key, current_iv)); await w.drain()
                                for t in targets: await _invite(t, " reset")
                        except Exception: pass
                except Exception as e:
                    print_warning(f"[SQUAD {squad_id+1}] loop: {e}")
                    await asyncio.sleep(3.0)
        except asyncio.CancelledError: raise
        except Exception as e:
            print_error(f"[SQUAD {squad_id+1}] coordinator: {e}")

    async def _member_trigger():
        try:
            if is_leader: return
            await asyncio.sleep(TEAM_READY_DELAY + 4.0)
            my_id = (current_account_data or {}).get("account_id", uid_str)
            joined = False; readied = False
            while _team_active["flag"]:
                try:
                    if bot_state.is_paused(uid_str): break
                    if await _get_match_count(uid_str) >= MAX_CONCURRENT_MATCHES:
                        await asyncio.sleep(3.0); continue
                    w = _writer_ref["w"]
                    if w and not w.is_closing():
                        async with _team_state["lock"]:
                            tc = _team_state.get("team_code")
                            already = _team_state.get("member_ready", False)
                        if tc and not joined:
                            w.write(join_team_by_code(tc, current_key, current_iv,
                                                      region=account_region, game_version=client_version))
                            await w.drain(); joined = True
                            print_success(f"[SQUAD {squad_id+1}] 🔑 joined code {tc}")
                            await asyncio.sleep(1.2)
                        if (joined or already) and not readied:
                            w.write(ready_for_game(int(my_id), current_key, current_iv))
                            await w.drain(); readied = True
                            async with _team_state["lock"]:
                                _team_state["member_ready"] = True
                            print_success(f"[SQUAD {squad_id+1}] ✅ member READY (CS)")
                except Exception as e:
                    print_warning(f"[SQUAD {squad_id+1}] member: {e}")
                await asyncio.sleep(2.0)
        except asyncio.CancelledError: raise
        except Exception as e:
            print_warning(f"[SQUAD {squad_id+1}] member outer: {e}")

    try:
        while True:
            while bot_state.is_paused(uid_str):
                try: bot_state.update_status(uid_str, "PAUSED", 0)
                except Exception: pass
                await asyncio.sleep(1.0)
            writer = None; ka_task = None; coord_task = None; member_task = None
            try:
                if current_account_data:
                    fresh = None
                    if current_account_data.get("auth_type") == "guest" and current_account_data.get("auth_uid"):
                        fresh = cache_get(str(current_account_data["auth_uid"]))
                    if fresh:
                        current_account_data = fresh
                        current_key = fresh["aes_ak"]; current_iv = fresh["iv_i"]
                        current_token = await build_tcp_startup_packet(
                            fresh["account_id"], fresh["token"], fresh["server_time"],
                            current_key, current_iv, region=fresh.get("region", account_region))
                    elif not current_token or not current_key:
                        raise ConnectionError("Cache expired")

                resolved_ip = await resolve_host_cloudflare(ip)
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(resolved_ip, int(port)), timeout=20)
                bot_state.register_writer(uid_str, writer); _writer_ref["w"] = writer
                rs = writer.get_extra_info('socket')
                if rs: optimize_tcp_socket(rs)
                writer.write(bytes.fromhex(current_token)); await writer.drain()
                try:
                    ka = await send_keep_alive(account_region)
                    writer.write(ka); await asyncio.wait_for(writer.drain(), timeout=3)
                except Exception: pass

                async def _ka():
                    ka = await send_keep_alive(account_region)
                    while True:
                        await asyncio.sleep(5)
                        try:
                            if writer and not writer.is_closing():
                                writer.write(ka); await writer.drain()
                        except Exception: break
                ka_task = asyncio.create_task(_ka())
                print_success(f"[✓] Gateway OK | {uid_str} | CS-ONLY")
                reconnects = 0

                async with _team_state["lock"]:
                    _team_state["peers"][uid_str] = {"writer": writer, "data": current_account_data,
                                                     "key": current_key, "iv": current_iv}
                    if is_leader: _team_state["leader_uid"] = uid_str
                if is_leader: coord_task = asyncio.create_task(_coordinator())
                else: member_task = asyncio.create_task(_member_trigger())

                while True:
                    play_matches[:] = [m for m in play_matches if not m.done()]
                    if bot_state.is_paused(uid_str): break
                    try:
                        data = await asyncio.wait_for(reader.read(8192), timeout=0.5)
                    except asyncio.TimeoutError: continue
                    if not data: raise ConnectionError("closed")
                    hx = data.hex(); plen = len(data)

                    if hx.startswith("0600") and plen > 20:
                        await _process_social_packet(data); continue

                    if hx.startswith("0500") and plen > 10:
                        try:
                            dec = None
                            for off in (10,12,8,6,14,16):
                                if len(hx) <= off: continue
                                inner = bytes.fromhex(hx[off:])
                                cand = decode_protobuf_dict(inner) or \
                                       {str(k):{"data":v} for k,v in (decode_protobuf_2(inner) or {}).items()}
                                if cand and ("5" in cand or 5 in cand or len(cand) >= 2):
                                    dec = cand; break
                            if not dec: continue
                            tc = extract_team_code_from_proto(dec)
                            if tc:
                                async with _team_state["lock"]:
                                    if _team_state.get("team_code") != tc:
                                        _team_state["team_code"] = tc
                                        print_success(f"[SQUAD {squad_id+1}] 📢 code {tc}")
                            f5w = dec.get("5") or dec.get(5)
                            f5 = f5w["data"] if isinstance(f5w, dict) and "data" in f5w else (f5w or dec)

                            def _g(k):
                                if not isinstance(f5, dict): return None
                                v = f5.get(k) if k in f5 else f5.get(str(k))
                                return v["data"] if isinstance(v, dict) and "data" in v else v
                            gid = None
                            for gk in [8,10,9,2]:
                                g = _g(gk)
                                if isinstance(g,(str,int)) and len(str(g)) >= 8 and \
                                   not (str(g).isdigit() and len(str(g)) <= 12):
                                    gid = str(g); break
                            if not gid and _g(8) is not None: gid = str(_g(8))
                            own_acc = str((current_account_data or {}).get("account_id", uid_str))
                            inviter = None
                            for fk in [1,2,3,4,6,7,13,15,20]:
                                c = _g(fk)
                                if c and str(c).isdigit() and 6 <= len(str(c)) <= 15 and \
                                   str(c) not in (uid_str, own_acc):
                                    inviter = str(c); break
                            if inviter and gid and not is_leader:
                                for _ in range(2):
                                    try:
                                        writer.write(accept_team_invite(int(inviter), int(own_acc), gid,
                                                                        current_key, current_iv,
                                                                        region=account_region,
                                                                        game_version=client_version))
                                        await writer.drain()
                                    except Exception: pass
                                    await asyncio.sleep(0.4)
                                try:
                                    writer.write(ready_for_game(int(own_acc), current_key, current_iv))
                                    await writer.drain()
                                    async with _team_state["lock"]:
                                        _team_state["member_ready"] = True
                                except Exception: pass
                        except Exception: pass
                        continue

                    if hx.startswith("0300") and 10 < plen < 30:
                        print_info(f"[CS-QUEUE {squad_id+1}] searching... ({plen}B)")
                        continue

                    if hx.startswith("0300") and plen >= 250:
                        try:
                            res = json.loads(await decode_protobuf_async(hx[10:]))
                            token = udp_key = match_code = srv = None
                            acc_id_m = block = None
                            if "42" in res and "data" in res["42"]: match_code = res["42"]["data"]
                            if "5" in res and "data" in res["5"]:
                                rf5 = res["5"]["data"]
                                srv = rf5.get("2", {}).get("data")
                                udp_key = rf5.get("3", {}).get("data")
                                token = rf5.get("4", {}).get("data")
                                if "42" in rf5: match_code = rf5["42"]["data"]
                                block = rf5.get("1", {}).get("data")
                            if "1" in res and "data" in res["1"]: acc_id_m = res["1"]["data"]
                            eff = acc_id_m or account_id or "BD_BOT"
                            if token and udp_key and match_code and srv:
                                mode = _team_state.get("mode")
                                if mode not in CS_MODE_NAME: mode = CS_MODE
                                m_id = _cur_map()
                                print_success(f"[⚔] CS MATCH FOUND | {uid_str} → {srv} | "
                                              f"{CS_MODE_NAME.get(mode)} | map {m_id}")
                                for tk in (coord_task, member_task):
                                    if tk and not tk.done(): tk.cancel()
                                coord_task = member_task = None
                                _team_active["flag"] = False
                                acc_tok = (current_account_data or {}).get("access_token", "")
                                thunder, sharma = await build_match_startup_packets(
                                    token, udp_key, match_code, eff, block or 0, server_ip=srv,
                                    region=account_region, client_version=client_version,
                                    access_token=acc_tok, mode_id=mode, map_id=m_id)
                                mi = await _inc_match(uid_str)
                                try:
                                    bot_state.increment_match_started()
                                    bot_state.update_status(uid_str, "IN_MATCH", 1)
                                except Exception: pass
                                async with _team_state["lock"]:
                                    _team_state["peers"].pop(uid_str, None)
                                    _team_state["member_ready"] = False
                                    if is_leader: _team_state["team_code"] = None
                                play_matches.append(asyncio.create_task(
                                    play_game(srv, thunder, sharma, udp_key, match_code, eff,
                                              account_region, client_version, current_key, current_iv,
                                              match_index=mi, mode_id=mode, map_id=m_id,
                                              on_match_complete=lambda: _mark_bot_match_finished(uid_str),
                                              on_match_fail=_on_start_fail)))
                                try:
                                    writer.close(); await writer.wait_closed()
                                except Exception: pass
                                await asyncio.sleep(NEW_MATCH_DELAY)
                                break
                        except Exception as e:
                            print_warning(f"[CS-MATCH] {e}")
                        continue
            except asyncio.CancelledError: raise
            except Exception as e:
                if "Cache expired" in str(e): break
                reconnects += 1
                if reconnects > max_reconnects:
                    if current_account_data:
                        try:
                            if current_account_data.get("auth_uid"):
                                cache_invalidate(str(current_account_data["auth_uid"]))
                        except Exception: pass
                    reconnects = 0; break
                delay = min(RECONNECT_BASE * (2 ** (reconnects - 1)), RECONNECT_MAX)
                await asyncio.sleep(delay + random.uniform(0, 0.5))
            finally:
                _team_active["flag"] = False
                async with _team_state["lock"]:
                    _team_state["peers"].pop(uid_str, None)
                    _team_state["member_ready"] = False
                    if is_leader: _team_state["team_code"] = None
                for tk in (coord_task, member_task):
                    if tk and not tk.done():
                        tk.cancel()
                        try: await tk
                        except asyncio.CancelledError: pass
                if ka_task: ka_task.cancel()
                if writer:
                    bot_state.unregister_writer(uid_str, writer)
                    await safe_close_writer(writer)
                _team_active["flag"] = True
    except asyncio.CancelledError:
        raise
    finally:
        for m in play_matches:
            if not m.done(): m.cancel()

# ==================== INFORMATIONAL ====================
async def informational(addrs, starter_packet, key, iv, region="BD",
                        account_id="", max_reconnects=3, account_data=None):
    uid_str = str(account_id); reconnects = 0
    ip, port = addrs.split(":")
    while True:
        while uid_str and bot_state.is_paused(uid_str): await asyncio.sleep(1.0)
        writer = None; ping_task = None
        try:
            resolved_ip = await resolve_host_cloudflare(ip)
            reader, writer = await asyncio.open_connection(resolved_ip, int(port))
            if uid_str: bot_state.register_writer(uid_str, writer)
            rs = writer.get_extra_info('socket')
            if rs: optimize_tcp_socket(rs)
            writer.write(bytes.fromhex(starter_packet)); await writer.drain()
            reconnects = 0
            try:
                ka = await send_keep_alive(region)
                writer.write(ka); await asyncio.wait_for(writer.drain(), timeout=3)
            except Exception: pass
            async def _ka():
                ka = await send_keep_alive(region)
                while True:
                    await asyncio.sleep(5)
                    try:
                        if writer and not writer.is_closing():
                            writer.write(ka); await writer.drain()
                    except Exception: break
            ping_task = asyncio.create_task(_ka())
            while True:
                if uid_str and bot_state.is_paused(uid_str):
                    if ping_task: ping_task.cancel()
                    if uid_str: bot_state.unregister_writer(uid_str, writer)
                    await safe_close_writer(writer); writer = None
                    while bot_state.is_paused(uid_str): await asyncio.sleep(1.0)
                    break
                try:
                    data = await asyncio.wait_for(reader.read(8192), timeout=1.0)
                except asyncio.TimeoutError: continue
                if not data: raise ConnectionError("closed")
        except asyncio.CancelledError:
            if ping_task: ping_task.cancel()
            if uid_str: bot_state.unregister_writer(uid_str, writer)
            await safe_close_writer(writer); raise
        except Exception:
            if ping_task: ping_task.cancel()
            if uid_str: bot_state.unregister_writer(uid_str, writer)
            await safe_close_writer(writer)
            reconnects += 1
            await asyncio.sleep(2 if reconnects > max_reconnects else 1)
            if reconnects > max_reconnects: reconnects = 0

# ==================== ACCOUNT HELPERS ====================
def _register_credentials(ad):
    try:
        bot_state.account_credentials[str(ad["account_id"])] = ad
        if ad.get("auth_uid"): bot_state.account_credentials[str(ad["auth_uid"])] = ad
    except Exception: pass

async def refresh_account_profile(ad_or_uid):
    try:
        if isinstance(ad_or_uid, str):
            ad = bot_state.account_credentials.get(str(ad_or_uid))
        else: ad = ad_or_uid
        if not ad: return
        acc_id = ad.get("account_id"); srv = ad.get("server_url"); rel = ad.get("release_version")
        if not (ad.get("token") and acc_id and srv and rel): return
        data = await get_player_personal_show(int(acc_id), ad["token"], srv, rel)
        if not data: return
        pd = data.get(1, {}) if isinstance(data.get(1), dict) else {}
        exp = pd.get(7); lvl = pd.get(6); nick = pd.get(3)
        if exp is None: return
        try:
            exp = int(exp); lvl = int(lvl) if lvl else 1
        except Exception: return
        aid = str(acc_id)
        if aid not in bot_state.accounts:
            bot_state.register_account(aid, nick or f"Player_{aid}", region=ad.get("region","BD"),
                                       level=lvl, exp=exp, auth_uid=ad.get("auth_uid"))
            return
        old = bot_state.accounts[aid].get("current_exp", 0)
        bot_state.update_exp(aid, exp, lvl)
        if nick: bot_state.accounts[aid]["nickname"] = nick
        if exp > old: print_success(f"[★] +{exp-old:,} EXP | {aid}")
    except Exception: pass

async def process_account_uid_pass(uid, password, region_override=None):
    cached = cache_get(uid)
    if cached:
        aid = str(cached["account_id"])
        bot_state.register_account(aid, cached.get("nickname", f"Player_{aid}"),
            cached.get("region","BD"), cached.get("level",1), cached.get("exp",0),
            cached.get("likes",0), auth_uid=str(uid))
        _register_credentials(cached); return cached
    try:
        async with _LOGIN_SEMAPHORE:
            vc = await version_config(region_override or "BD")
            if not vc: return None
            release_version, client_version, server_url, gop_1, app_version = vc
            tg = await get_access_token(uid, password)
            if not tg: return None
            open_id, access_token, platform = tg
            mp, lp = await get_payload(access_token, open_id, platform, client_version,
                                       region=(region_override or "BD"))
            res = await major_login(mp, server_url, release_version)
            if not res: return None

            def _gd(k):
                v = res.get(str(k))
                if isinstance(v, dict) and "data" in v: return v["data"]
                return None
            acc_raw = _gd(1); jwt = _gd(8); srv_raw = _gd(10); stime = _gd(21)
            region_raw = _gd(2) or "BD"
            ak, ivv = _extract_key_iv(res)
            if not jwt or not srv_raw or not ak: return None
            gld = await get_login_data(lp, jwt, srv_raw, release_version)
            if not gld: return None

        def _gf(f, d=None):
            v = gld.get(str(f), {}).get("data")
            return v if v is not None else d
        level = int(_gf(6,1) or 1); exp = int(_gf(7,0) or 0); likes = int(_gf(8,0) or 0)
        nickname = _gf(4, f"Player_{acc_raw}") or f"Player_{acc_raw}"
        region = region_raw or "BD"; acc_id = str(acc_raw)
        bot_state.register_account(acc_id, nickname, region, level, exp, likes, auth_uid=str(uid))
        print_success(f"[✓] Login {acc_id} | {nickname} | Lvl {level} | mode={CS_MODE_NAME.get(_mode_for(level))}")
        ad = {"account_id":acc_raw,"nickname":nickname,"region":region,"level":level,"exp":exp,
              "likes":likes,"open_id":open_id,"access_token":access_token,"platform":str(platform),
              "token":jwt,"server_time":stime,"aes_ak":ak,"iv_i":ivv,
              "functional_addrs":_gf(14),"informational_addrs":_gf(32),
              "release_version":release_version,"client_version":client_version,
              "server_url":srv_raw,"login_payload_data":lp,
              "auth_type":"guest","auth_uid":uid,"auth_password":password}
        _register_credentials(ad); cache_set(uid, ad); return ad
    except Exception as e:
        print_error(f"login err: {e}"); return None

async def run_account_worker(ad, label, region_override=None, clan_override=None):
    acc_id = str(ad["account_id"])
    tasks = []
    try:
        reg = region_override or ad.get("region","BD")
        if not ad.get("functional_addrs") or not ad.get("informational_addrs"):
            raise ConnectionError("missing gateway addrs")
        tcp_online = await build_tcp_startup_packet(ad["account_id"], ad["token"], ad["server_time"],
                                                   ad["aes_ak"], ad["iv_i"], region=reg)
        tcp_chat = await build_tcp_startup_packet(ad["account_id"], ad["token"], ad["server_time"],
                                                 ad["aes_ak"], ad["iv_i"], region=reg, typ='ChaT')
        if clan_override:
            tasks.append(asyncio.create_task(_auto_join_clan(ad, str(clan_override))))
            tasks.append(asyncio.create_task(_clan_keepalive(ad, str(clan_override))))
        tasks.append(asyncio.create_task(informational(
            ad["informational_addrs"], tcp_chat, ad["aes_ak"], ad["iv_i"],
            region=reg, account_id=acc_id, account_data=ad)))
        async def _exp():
            while True:
                await asyncio.sleep(90 + random.uniform(-10, 10))
                f = bot_state.account_credentials.get(acc_id)
                if f: await refresh_account_profile(f)
        tasks.append(asyncio.create_task(_exp()))
        if ENABLE_HTTP_PING:
            try:
                ph = str(ad.get("server_url") or PING_URL).rstrip("/")
                purl = ph if ph.endswith("/Ping") else ph + "/Ping"
                tasks.append(asyncio.create_task(ping_worker(acc_id, ad["token"],
                                                             ad["release_version"], region=reg, ping_url=purl)))
            except Exception: pass
        await functional_lone_wolf(ad["functional_addrs"], tcp_online, reg, ad["client_version"],
                                   ad["aes_ak"], ad["iv_i"], account_id=acc_id, account_data=ad)
    except asyncio.CancelledError: raise
    except Exception as e:
        print_error(f"worker err {label}: {e}")
    finally:
        for t in tasks:
            if not t.done(): t.cancel()
        for t in tasks:
            try: await t
            except Exception: pass

async def account_loop_guest(uid, password, region_override=None, clan_override=None):
    uid_str = str(uid)
    bot_state.account_workers[uid_str] = asyncio.current_task()
    acc_id = None
    while True:
        try:
            bot_state.update_status(uid_str, "CONNECTING")
            ad = await process_account_uid_pass(uid_str, password, region_override)
            if not ad:
                await asyncio.sleep(12); continue
            acc_id = str(ad["account_id"])
            bot_state.account_workers[acc_id] = asyncio.current_task()
            bot_state.auth_to_game_id[uid_str] = acc_id
            bot_state.game_to_auth_id[acc_id] = uid_str
            await run_account_worker(ad, uid_str, region_override, clan_override)
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            try:
                bot_state.update_status(uid_str, "OFFLINE")
                if acc_id: bot_state.update_status(acc_id, "OFFLINE")
            except Exception: pass
            break
        except Exception as e:
            print_error(f"err {uid_str}: {e}"); await asyncio.sleep(8)

# ==================== CREATE ACCOUNTS (RAIX identity) ====================
def _gf_field(ld, key, default=None):
    if not ld: return default
    v = ld.get(str(key), {})
    return v.get("data", default) if isinstance(v, dict) else (v if v is not None else default)

def _raix_nick() -> str:
    return f"{NICK_PREFIX}-{random.randint(100000, 999999)}"

async def choose_region(region, jwt_token, login_url, release_version):
    payload = bytes.fromhex(encrypt_aes(create_proto({1: region.upper()}).hex()))
    hdrs = {"Accept-Encoding":"gzip","Authorization":f"Bearer {jwt_token}",
            "Connection":"Keep-Alive","Content-Type":"application/x-www-form-urlencoded",
            "ReleaseVersion":f"{release_version}",
            "User-Agent":"UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "X-GA":"v1 1","X-GA-SV":str(int(time.time())),"X-Unity-Version":"2018.4.12f1"}
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.post(f"{login_url.rstrip('/')}/ChooseRegion", data=payload,
                              headers=hdrs, ssl=ssl_ctx) as r:
                await r.read(); return r.status
    except Exception: return None

async def _create_one(region, clan_id, password, idx, total):
    async with _CREATE_SEMAPHORE:
        bot_state.create_progress.append(f"⌛ bot {idx}/{total}")
        try:
            vc = await version_config(region)
            if not vc: return None
            release_v, remote_v, login_url, gop_1, app_version = vc
            if not login_url.endswith("/"): login_url += "/"
            lang = REGION_LANG.get(region.upper(), "en")
            game_version = remote_v or app_version

            uid = await register_account(password, gop_1, app_version)
            if not uid: return None
            tok = await grant_token(uid, password, gop_1, app_version)
            if not tok: return None
            open_id = tok["open_id"]; access_token = tok["access_token"]
            platform = tok.get("platform", 4)
            mp, lp = await get_payload(access_token, open_id, platform, game_version, lang, region=region)
            nick = _raix_nick()
            if not await major_register(release_v, access_token, open_id, nick,
                                        game_version, login_url, lang):
                return None
            await asyncio.sleep(2.5)
            res = None
            for _ in range(4):
                mp, lp = await get_payload(access_token, open_id, platform, game_version, lang, region=region)
                res = await major_login(mp, login_url, release_v)
                if res and (("8" in res) or (8 in res)): break
                res = None; await asyncio.sleep(1.8)
            if not res: return None

            def _gd(k):
                v = res.get(str(k))
                if isinstance(v, dict) and "data" in v: return v["data"]
                return None
            jwt = _gd(8); srv = _gd(10); stime = _gd(21); acc = _gd(1)
            if not jwt: return None
            if not srv:
                if await choose_region(region, jwt, login_url, release_v) != 200: return None
                await asyncio.sleep(2.0)
                for _ in range(3):
                    mp, lp = await get_payload(access_token, open_id, platform, game_version, lang, region=region)
                    res = await major_login(mp, login_url, release_v)
                    if res and (("10" in res) or (10 in res)):
                        jwt = (res.get("8") or {}).get("data") or _gd(8)
                        srv = (res.get("10") or {}).get("data") or _gd(10)
                        stime = (res.get("21") or {}).get("data") or _gd(21)
                        acc = (res.get("1") or {}).get("data") or _gd(1)
                        break
                    res = None; await asyncio.sleep(2.0)
                if not srv: return None

            ak, ivv = _extract_key_iv(res)
            if not ak or not ivv: return None
            ld = await get_login_data(lp, jwt, srv, release_v)
            level = 1; exp = 0
            if ld:
                def _gf(f, d=None):
                    v = ld.get(str(f), {}).get("data")
                    return v if v is not None else d
                level = int(_gf(6, 1) or 1); exp = int(_gf(7, 0) or 0)
                nick = _gf(4, nick) or nick

            ad = {"account_id":acc,"nickname":nick,"region":region,"level":level,"exp":exp,
                  "likes":0,"open_id":open_id,"access_token":access_token,"platform":str(platform),
                  "token":jwt,"server_time":stime,"aes_ak":ak,"iv_i":ivv,
                  "functional_addrs":_gf_field(ld,14),"informational_addrs":_gf_field(ld,32),
                  "release_version":release_v,"client_version":game_version,"server_url":srv,
                  "login_payload_data":lp,"auth_type":"guest","auth_uid":uid,
                  "auth_password":password,"clan_id":clan_id}
            _register_credentials(ad); cache_set(uid, ad)
            bot_state.create_progress.append(f"✅ {nick} | UID {acc}")
            print_success(f"[CREATE] {nick} | UID {acc} | RAIX identity")
            return ad
        except Exception as e:
            bot_state.create_progress.append(f"❌ bot {idx}: {e}")
            print_error(f"[CREATE] {e}")
            return None

async def create_four_accounts(region: str, clan_id: str, count: int = 2, password: str = None):
    password = password or IDENTITY_PASSWORD
    if bot_state.creating: return []
    bot_state.creating = True
    bot_state.create_progress = []
    try:
        print_info(f"[CREATE] {count} bots | region {region} | identity {NICK_PREFIX} | CS-ONLY")
        created = [a for a in await asyncio.gather(
            *[_create_one(region, clan_id, password, i + 1, count) for i in range(count)]) if a]
        if not created: return []

        existing = []
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f) or []
                if not isinstance(existing, list): existing = []
            except Exception: existing = []
        have = {str(a.get("uid")) for a in existing if isinstance(a, dict)}
        for a in created:
            if str(a["auth_uid"]) not in have:
                existing.append({"uid": str(a["auth_uid"]), "password": a["auth_password"],
                                 "region": region, "clan_id": clan_id})
        _write_json(ACCOUNTS_FILE, existing)

        for a in created:
            t = asyncio.create_task(account_loop_guest(str(a["auth_uid"]), a["auth_password"],
                                                      region_override=region, clan_override=clan_id))
            bot_state.account_workers[str(a["auth_uid"])] = t
            await asyncio.sleep(0.3)
        return created
    except Exception as e:
        print_error(f"[CREATE] {e}"); return []
    finally:
        bot_state.creating = False

# ==================== SUPERVISOR ====================
async def _restart_worker_by_auth_uid(auth_uid):
    try:
        if not os.path.exists(ACCOUNTS_FILE): return False
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            accs = json.load(f)
        for a in accs:
            if str(a.get("uid")) == str(auth_uid) and a.get("password"):
                t = bot_state.account_workers.get(str(auth_uid))
                if t and not t.done(): t.cancel()
                cache_invalidate(str(auth_uid))
                nt = asyncio.create_task(account_loop_guest(
                    str(a["uid"]), a["password"],
                    region_override=a.get("region"), clan_override=a.get("clan_id")))
                bot_state.account_workers[str(a["uid"])] = nt
                return True
    except Exception: pass
    return False

async def _supervisor():
    while True:
        await asyncio.sleep(SUPERVISOR_INTERVAL)
        try:
            for uid, acc in list(bot_state.accounts.items()):
                if bot_state.is_paused(uid): continue
                task = bot_state.account_workers.get(uid)
                dead = task is None or task.done()
                stuck = acc.get("status") in ("CONNECTING", "SEARCHING") and bot_state.stuck_for(uid) > STUCK_LIMIT
                if dead or stuck:
                    auth = str(acc.get("auth_uid") or bot_state.game_to_auth_id.get(uid) or uid)
                    print_warning(f"[SUP] {uid} {'dead' if dead else 'stuck'} → restart")
                    await _restart_worker_by_auth_uid(auth)
                    await asyncio.sleep(1.0)
        except Exception as e:
            print_error(f"[SUP] {e}")

async def _token_warm_loop():
    while True:
        await asyncio.sleep(TOKEN_WARM_EVERY)
        try:
            cache = _load_token_cache()
            now = time.time()
            for uid, e in list(cache.items()):
                if now - e.get("cached_at", 0) < (TOKEN_CACHE_TTL - 240): continue
                pw = str(e.get("auth_password") or "").strip()
                if not pw: continue
                asyncio.create_task(process_account_uid_pass(str(uid), pw, e.get("region")))
                await asyncio.sleep(0.15)
        except Exception as e:
            print_error(f"[WARM] {e}")

async def _stats_loop():
    while True:
        await asyncio.sleep(STATS_EVERY)
        try:
            accs = list(bot_state.accounts.values())
            online = sum(1 for a in accs if a.get("status") == "ONLINE")
            inm = sum(1 for a in accs if a.get("status") == "IN_MATCH")
            print_info(f"[STATS] CS-ONLY total={len(accs)} online={online} in_match={inm} "
                       f"in_game={bot_state.cs_in_game} start_fail={bot_state.cs_start_fail} "
                       f"glory=+{bot_state.total_exp_gained}")
        except Exception: pass

async def _autocreate_loop():
    if TARGET_ACCOUNTS <= 0: return
    await asyncio.sleep(15)
    while True:
        try:
            have = len(bot_state.accounts)
            if have < TARGET_ACCOUNTS and not bot_state.creating:
                need = min(TARGET_ACCOUNTS - have, CREATE_BATCH)
                print_warning(f"[AUTO-CREATE] {have}/{TARGET_ACCOUNTS} → creating {need}")
                await create_four_accounts("BD", CLAN_ID_DEFAULT, need)
            await asyncio.sleep(40)
        except Exception as e:
            print_error(f"[AUTO-CREATE] {e}"); await asyncio.sleep(40)

# ==================== AUTOLOAD ====================
async def _autoload_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        print_warning(f"[BOOT] {ACCOUNTS_FILE} নেই"); return
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            accounts = json.load(f)
    except Exception as e:
        print_error(f"[BOOT] read fail: {e}"); return
    if not isinstance(accounts, list) or not accounts:
        print_warning("[BOOT] খালি বা ভুল ফরম্যাট"); return
    seen, loaded, skipped = set(), 0, 0
    print_success(f"[BOOT] {len(accounts)} রেকর্ড চেক করছি (CS-ONLY)")
    for i, a in enumerate(accounts, 1):
        try:
            if not isinstance(a, dict): skipped += 1; continue
            uid = str(a.get("uid", "")).strip()
            pw = str(a.get("password", "")).strip()
            region = str(a.get("region", "")).strip() or None
            clan = str(a.get("clan_id", "")).strip() or CLAN_ID_DEFAULT
            if not uid or not pw or uid in seen: skipped += 1; continue
            seen.add(uid)
            t = bot_state.account_workers.get(uid)
            if t and not t.done(): skipped += 1; continue
            bot_state.account_workers[uid] = asyncio.create_task(
                account_loop_guest(uid, pw, region_override=region, clan_override=clan))
            loaded += 1
            await asyncio.sleep(0.25)
        except Exception as e:
            print_error(f"[BOOT] rec {i}: {e}"); skipped += 1
    print_success(f"[BOOT] loaded={loaded} skipped={skipped} — সব CS ম্যাচে যাবে")

# ==================== FILE SERVING ====================
def _find_file(filename: str) -> Optional[str]:
    for cand in (filename, os.path.join("templates", filename), os.path.join("static", filename)):
        if os.path.exists(cand) and os.path.isfile(cand): return cand
    return None

_FALLBACK_PAGES = {
    "login.html": """<!doctype html><meta charset=utf-8><title>RAIX Login</title>
<style>body{font-family:system-ui;background:#111;color:#eee;padding:40px}input,button{padding:10px;margin:6px}
button{background:#2563eb;color:#fff;border:0;border-radius:6px}</style>
<h2>Login</h2><input id=u placeholder=username><input id=p type=password placeholder=password>
<button onclick="go()">Login</button><script>async function go(){const r=await fetch('/api/auth/login',{method:'POST',
headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u.value,password:p.value})});
const d=await r.json();d.ok?location.href='/bot':alert(d.error||'fail')}</script>""",
    "client.html": """<!doctype html><meta charset=utf-8><title>RAIX Client</title>
<style>body{font-family:system-ui;background:#111;color:#eee;padding:40px}input,select,button{padding:10px;margin:6px}
button{background:#059669;color:#fff;border:0;border-radius:6px}pre{background:#000;padding:12px}</style>
<h2>Launch (CLASH SQUAD ONLY)</h2><input id=c placeholder="Clan ID"><select id=r><option value=bd>BD</option>
<option value=ind>IND</option><option value=id>ID</option></select>
<button onclick="go()">Launch</button><pre id=o></pre>
<script>async function go(){o.textContent=await (await fetch('/api/client/launch',{method:'POST',
headers:{'Content-Type':'application/json'},body:JSON.stringify({clan_id:c.value,region:r.value})})).text()}</script>""",
    "admin.html": """<!doctype html><meta charset=utf-8><title>RAIX Admin</title>
<style>body{font-family:system-ui;background:#111;color:#eee;padding:40px}button{padding:10px;margin:6px;
background:#7c3aed;color:#fff;border:0;border-radius:6px}pre{background:#000;padding:12px}</style>
<h2>Admin</h2><button onclick="g('/api/admin/overview')">Overview</button>
<button onclick="g('/api/admin/users')">Users</button><button onclick="g('/api/glory')">Glory</button>
<pre id=o></pre><script>async function g(u){o.textContent=await (await fetch(u)).text()}</script>""",
}

async def serve_html_file(filename: str):
    p = _find_file(filename)
    if p:
        with open(p, "r", encoding="utf-8") as f:
            return aiohttp.web.Response(text=f.read(), content_type="text/html", charset="utf-8")
    b = _FALLBACK_PAGES.get(filename)
    if b: return aiohttp.web.Response(text=b, content_type="text/html", charset="utf-8")
    return aiohttp.web.Response(text=f"<h1>{filename} missing</h1>", content_type="text/html", status=404)

async def handle_root(r):  return await serve_html_file("index.html")
async def handle_ffglory(r): return await serve_html_file("ffglory.html")
async def handle_index(r): return await serve_html_file("index.html")
async def handle_admin(r): return await serve_html_file("admin.html")
async def handle_client(r): return await serve_html_file("client.html")
async def handle_login(r): return await serve_html_file("login.html")

async def handle_shared_css(r):
    p = _find_file("shared.css")
    if p:
        with open(p, "r", encoding="utf-8") as f:
            return aiohttp.web.Response(text=f.read(), content_type="text/css", charset="utf-8")
    return aiohttp.web.Response(text="", content_type="text/css")

async def handle_shared_js(r):
    p = _find_file("shared.js"); c = ""
    if p:
        with open(p, "r", encoding="utf-8") as f: c = f.read()
    return aiohttp.web.Response(text=c, content_type="application/javascript", charset="utf-8")

async def handle_login_js(r):
    p = _find_file("login.js")
    if p:
        with open(p, "r", encoding="utf-8") as f:
            return aiohttp.web.Response(text=f.read(), content_type="application/javascript", charset="utf-8")
    return aiohttp.web.Response(text="", content_type="application/javascript")

async def handle_sw_js(r):
    p = _find_file("sw.js")
    if p:
        with open(p, "r", encoding="utf-8") as f:
            return aiohttp.web.Response(text=f.read(), content_type="application/javascript", charset="utf-8")
    return aiohttp.web.Response(text="", content_type="application/javascript")

async def handle_logo(r):
    for c in ("static/logo.gif", "logo.gif", "templates/logo.gif"):
        if os.path.exists(c): return aiohttp.web.FileResponse(c)
    return aiohttp.web.Response(status=404, text="no logo")

# ==================== AUTH ====================
def _cur_user(req):
    tok = req.cookies.get("session_token")
    if not tok:
        a = req.headers.get("Authorization", "")
        if a.startswith("Bearer "): tok = a[7:].strip()
    if not tok: return None
    u = panel_db.sessions.get(tok)
    return panel_db.users.get(u) if u else None

def _need_user(req):
    u = _cur_user(req)
    return (None, aiohttp.web.json_response({"error":"Unauthorized"}, status=401)) if not u else (u, None)

def _need_admin(req):
    u = _cur_user(req)
    if not u or u.get("role") != "admin":
        return None, aiohttp.web.json_response({"error":"Admin required"}, status=403)
    return u, None

async def api_login(req):
    b = await req.json()
    un = str(b.get("username","")).strip().lower(); pw = str(b.get("password",""))
    u = panel_db.users.get(un)
    if not u or u.get("password_hash") != _hash_pw(pw):
        return aiohttp.web.json_response({"error":"Invalid credentials"}, status=401)
    tok = uuid.uuid4().hex; panel_db.sessions[tok] = un; panel_db.save()
    r = aiohttp.web.json_response({"ok":True,"username":u["username"],
                                   "display_name":u.get("display_name",un),"role":u.get("role","user")})
    r.set_cookie("session_token", tok, path="/", max_age=86400*30, httponly=True)
    return r

async def api_signup(req):
    b = await req.json()
    un = str(b.get("username","")).strip().lower(); pw = str(b.get("password",""))
    if len(un) < 3 or not re.match(r"^[a-z0-9_]+$", un):
        return aiohttp.web.json_response({"error":"Invalid username"}, status=400)
    if len(pw) < 6: return aiohttp.web.json_response({"error":"Password 6+ chars"}, status=400)
    if un in panel_db.users: return aiohttp.web.json_response({"error":"Exists"}, status=400)
    panel_db.users[un] = {"username":un,"display_name":un,"password_hash":_hash_pw(pw),
                          "role":"user","basic_credits":0,"premium_credits":0,
                          "max_groups":10,"created_at":int(time.time())}
    panel_db.save()
    return aiohttp.web.json_response({"ok":True,"success":True})

async def api_logout(req):
    t = req.cookies.get("session_token")
    if t and t in panel_db.sessions:
        del panel_db.sessions[t]; panel_db.save()
    r = aiohttp.web.json_response({"ok":True}); r.del_cookie("session_token", path="/")
    return r

async def api_chpw(req):
    u, e = _need_user(req)
    if e: return e
    b = await req.json()
    if u.get("password_hash") != _hash_pw(str(b.get("current_password",""))):
        return aiohttp.web.json_response({"error":"Wrong password"}, status=400)
    nw = str(b.get("new_password",""))
    if len(nw) < 6: return aiohttp.web.json_response({"error":"Min 6 chars"}, status=400)
    u["password_hash"] = _hash_pw(nw); panel_db.save()
    return aiohttp.web.json_response({"ok":True,"success":True})

async def api_me(req):
    u, e = _need_user(req)
    if e: return e
    return aiohttp.web.json_response({k: u.get(k, 0) for k in
        ("username","display_name","role","basic_credits","premium_credits","max_groups")})

# ==================== ADMIN API ====================
async def api_admin_overview(req):
    _, e = _need_admin(req)
    if e: return e
    bots = list(bot_state.accounts.values())
    return aiohttp.web.json_response({
        "total_users": len(panel_db.users),
        "bot_accounts": len(bots),
        "bot_online": sum(1 for b in bots if b.get("status") in ("ONLINE","IN_MATCH")),
        "total_matches": bot_state.total_matches,
        "in_game": bot_state.cs_in_game,
        "start_fail": bot_state.cs_start_fail,
        "total_glory": bot_state.total_exp_gained,
        "uptime": int(time.time() - bot_state.start_time),
        "mode": "CLASH_SQUAD_ONLY",
    })

async def api_admin_users(req):
    _, e = _need_admin(req)
    if e: return e
    return aiohttp.web.json_response([{k: u.get(k) for k in
        ("username","display_name","role","basic_credits","premium_credits","created_at")}
        for u in panel_db.users.values()])

async def api_admin_user_create(req):
    _, e = _need_admin(req)
    if e: return e
    b = await req.json()
    un = str(b.get("username","")).strip().lower(); pw = str(b.get("password",""))
    if not un or len(pw) < 6: return aiohttp.web.json_response({"error":"invalid"}, status=400)
    if un in panel_db.users: return aiohttp.web.json_response({"error":"exists"}, status=400)
    panel_db.users[un] = {"username":un,"display_name":un,"password_hash":_hash_pw(pw),
                          "role":b.get("role","user"),"basic_credits":int(b.get("basic_credits",0)),
                          "premium_credits":int(b.get("premium_credits",0)),"max_groups":10,
                          "created_at":int(time.time())}
    panel_db.save()
    return aiohttp.web.json_response({"ok":True})

async def api_admin_credits(req):
    _, e = _need_admin(req)
    if e: return e
    b = await req.json()
    u = panel_db.users.get(str(b.get("username","")).strip().lower())
    if not u: return aiohttp.web.json_response({"error":"not found"}, status=404)
    for k in ("basic_credits","premium_credits"):
        if b.get(k) is not None:
            u[k] = max(0, u.get(k,0) + int(b[k])) if b.get("mode","add") == "add" else max(0, int(b[k]))
    panel_db.save()
    return aiohttp.web.json_response({"ok":True,"basic_credits":u["basic_credits"],
                                       "premium_credits":u["premium_credits"]})

async def api_admin_user_delete(req):
    a, e = _need_admin(req)
    if e: return e
    un = str((await req.json()).get("username","")).strip().lower()
    if un == a["username"]: return aiohttp.web.json_response({"error":"self"}, status=400)
    panel_db.users.pop(un, None); panel_db.save()
    return aiohttp.web.json_response({"ok":True})

async def api_admin_bots(req):
    _, e = _need_admin(req)
    if e: return e
    return aiohttp.web.json_response(list(bot_state.accounts.values()))

async def api_admin_join_clan(req):
    _, e = _need_admin(req)
    if e: return e
    clan = str((await req.json()).get("clan_id","")).strip()
    if not clan: return aiohttp.web.json_response({"error":"clan_id required"}, status=400)
    seen, res = set(), []
    for ad in list(bot_state.account_credentials.values()):
        acc = str(ad.get("account_id",""))
        if not ad.get("token") or acc in seen: continue
        seen.add(acc)
        ok = await join_clan(ad["token"], clan, ad.get("server_url"),
                             ad.get("region"), ad.get("release_version"))
        res.append({"account_id":acc,"success":ok})
    return aiohttp.web.json_response({"total":len(res),
                                      "success":sum(1 for r in res if r["success"]), "results":res})

# ==================== CLIENT / BOT API ====================
async def api_pricing(req):
    return aiohttp.web.json_response({"basic_credit_usd":panel_db.settings["basic_credit_usd"],
        "premium_credit_usd":panel_db.settings["premium_credit_usd"],
        "binance_pay_id":panel_db.settings["binance_pay_id"],
        "regions":panel_db.settings["regions"]})

async def api_launch(req):
    u, e = _need_user(req)
    if e: return e
    b = await req.json()
    clan = str(b.get("clan_id","")).strip()
    if not clan: return aiohttp.web.json_response({"error":"clan_id required"}, status=400)
    region = str(b.get("region","bd")).lower()
    cfg = next((r for r in panel_db.settings["regions"] if r["id"] == region),
               {"tier":"basic","code":region.upper()})
    key = "premium_credits" if cfg.get("tier") == "premium" else "basic_credits"
    if u.get(key, 0) < 1:
        return aiohttp.web.json_response({"error":"Insufficient credits"}, status=400)
    u[key] -= 1
    gid = uuid.uuid4().hex[:8].upper()
    panel_db.groups[gid] = {"id":gid,"owner":u["username"],"region":cfg["code"],
                            "clan_id":clan,"tier":cfg.get("tier","basic"),
                            "status":"RUNNING","mode":"CS","created_at":int(time.time()),"gained_exp":0}
    panel_db.save()
    if bot_state.account_credentials:
        seen = set()
        for ad in list(bot_state.account_credentials.values()):
            acc = str(ad.get("account_id",""))
            if not ad.get("token") or acc in seen: continue
            seen.add(acc)
            asyncio.create_task(join_clan(ad["token"], clan, ad.get("server_url"),
                                          ad.get("region"), ad.get("release_version")))
    else:
        asyncio.create_task(create_four_accounts(cfg["code"], clan, 2))
    return aiohttp.web.json_response({"ok":True,"success":True,"mode":"CLASH_SQUAD_ONLY"})

async def api_groups(req):
    u, e = _need_user(req)
    if e: return e
    return aiohttp.web.json_response([g for g in panel_db.groups.values()
        if u.get("role") == "admin" or g.get("owner") == u["username"]])

async def api_glory(req):
    return aiohttp.web.json_response({
        "total_glory": bot_state.total_exp_gained,
        "matches": bot_state.total_matches,
        "matches_started": bot_state.matches_started,
        "in_game": bot_state.cs_in_game,
        "start_fail": bot_state.cs_start_fail,
        "accounts": len(bot_state.accounts),
        "uptime": int(time.time() - bot_state.start_time),
        "mode": "CLASH_SQUAD_ONLY",
    })

async def api_cs_status(req):
    return aiohttp.web.json_response({
        "mode": "CLASH_SQUAD_ONLY",
        "queue_mode": CS_MODE_NAME.get(CS_MODE),
        "maps": MAP_LADDER, "current_map": _cur_map(),
        "in_game": bot_state.cs_in_game,
        "start_fail": bot_state.cs_start_fail,
        "search_fail": bot_state.cs_search_fail,
        "room_resets": bot_state.cs_room_resets,
        "squads": [{"squad_id": sid + 1,
                    "mode": CS_MODE_NAME.get(st.get("mode"), st.get("mode")),
                    "team_code": st.get("team_code"),
                    "member_ready": st.get("member_ready"),
                    "start_fails": st.get("start_fails", 0)}
                   for sid, st in sorted(_team_states.items())],
    })

async def api_cs_map(req):
    try:
        b = await req.json()
        m = int(b.get("map"))
    except Exception:
        m = _next_map()
    return aiohttp.web.json_response({"ok": True, "current_map": m, "maps": MAP_LADDER})

async def api_health(req):
    accs = list(bot_state.accounts.values())
    return aiohttp.web.json_response({
        "ok": True, "engine": "RAIX", "mode": "CS-ONLY",
        "uptime": int(time.time() - bot_state.start_time),
        "accounts": len(accs),
        "online": sum(1 for a in accs if a.get("status") == "ONLINE"),
        "in_match": sum(1 for a in accs if a.get("status") == "IN_MATCH"),
        "in_game": bot_state.cs_in_game,
    })

async def api_ping(req):
    return aiohttp.web.json_response({"pong":True,"app":"RAIX","version":"5.0","mode":"CS-ONLY"})

async def api_stats(req):
    accs = list(bot_state.accounts.values())
    return aiohttp.web.Response(text=json.dumps({
        "accounts": accs,
        "logs": [{"time":l.get("time"),"message":l.get("message"),"level":l.get("level")}
                 for l in bot_state.logs[-200:]],
        "total_accounts": len(accs),
        "total_online": sum(1 for a in accs if a.get("status") == "ONLINE"),
        "total_matches": bot_state.total_matches,
        "total_matches_started": bot_state.matches_started,
        "in_game": bot_state.cs_in_game,
        "start_fail": bot_state.cs_start_fail,
        "search_fail": bot_state.cs_search_fail,
        "room_resets": bot_state.cs_room_resets,
        "mode": "CLASH_SQUAD_ONLY",
        "current_map": _cur_map(),
        "total_gained_exp": bot_state.total_exp_gained,
        "uptime": int(time.time() - bot_state.start_time),
        "creating": bot_state.creating,
        "create_progress": bot_state.create_progress[-40:],
        "team_size": sum(len(s["peers"]) for s in _team_states.values()),
        "restart_finished": len(_restart_state["finished_bots"]),
        "restart_target": _restart_state["target"],
    }, default=str, ensure_ascii=False), content_type="application/json", charset="utf-8")

async def api_logs(req):
    out = []
    for l in bot_state.logs[-150:]:
        lvl = l.get("level","info")
        col = "#34d399" if lvl == "success" else ("#ef4444" if lvl == "error" else
              ("#fbbf24" if lvl == "warning" else "#38bdf8"))
        out.append(f'<span style="color:{col}">[{l.get("time","")}]</span> {l.get("message","")}')
    return aiohttp.web.json_response({"logs": out})

async def api_logs_clear(req):
    bot_state.logs = []
    return aiohttp.web.json_response({"status":"ok"})

async def api_clanjoin(req):
    clan = str((await req.json()).get("clan_id", CLAN_ID_DEFAULT)).strip()
    seen = set()
    for ad in list(bot_state.account_credentials.values()):
        acc = str(ad.get("account_id",""))
        if not ad.get("token") or acc in seen: continue
        seen.add(acc)
        asyncio.create_task(join_clan(ad["token"], clan, ad.get("server_url"),
                                      ad.get("region"), ad.get("release_version")))
    return aiohttp.web.json_response({"status":"ok","clan_id":clan})

async def api_create_team(req):
    b = await req.json()
    region = str(b.get("region","BD")).upper()
    clan = str(b.get("clan_id","")).strip()
    count = max(1, min(28, int(b.get("count", 2))))
    if not clan: return aiohttp.web.json_response({"ok":False,"error":"clan_id required"})
    if bot_state.creating: return aiohttp.web.json_response({"ok":False,"error":"busy"})
    asyncio.create_task(create_four_accounts(region, clan, count, b.get("password")))
    return aiohttp.web.json_response({"ok":True,"msg":f"creating {count}","mode":"CS-ONLY"})

async def api_account_add(req):
    b = await req.json()
    uid = str(b.get("uid","")).strip(); pw = str(b.get("password","")).strip()
    if not uid or not pw: return aiohttp.web.json_response({"status":"error","error":"uid+password"})
    bot_state.account_workers[uid] = asyncio.create_task(account_loop_guest(uid, pw))
    return aiohttp.web.json_response({"status":"ok","mode":"CS-ONLY"})

async def api_account_delete(req):
    b = await req.json()
    for u in {str(b.get("uid","")).strip(), str(b.get("auth_uid","")).strip()} - {""}:
        t = bot_state.account_workers.pop(u, None)
        if t and not t.done(): t.cancel()
        bot_state.accounts.pop(u, None); cache_invalidate(u)
        bot_state.toggle_pause(u, False)
    return aiohttp.web.json_response({"status":"ok"})

async def api_account_pause(req):
    uid = str((await req.json()).get("uid","")).strip()
    ns = not bot_state.is_paused(uid)
    bot_state.toggle_pause(uid, ns)
    if ns: bot_state.close_writers_for_account(uid)
    return aiohttp.web.json_response({"status":"ok","is_paused":ns})

async def api_pause_all(req):
    accs = list(bot_state.accounts.keys())
    if not accs: return aiohttp.web.json_response({"status":"ok","all_paused":False})
    ns = not all(bot_state.is_paused(u) for u in accs)
    for u in accs:
        bot_state.toggle_pause(u, ns)
        if ns: bot_state.close_writers_for_account(u)
    return aiohttp.web.json_response({"status":"ok","all_paused":ns})

async def api_account_restart(req):
    uid = str((await req.json()).get("uid","")).strip()
    if not uid:
        for u in list(bot_state.accounts.keys()): bot_state.toggle_pause(u, False)
        return aiohttp.web.json_response({"status":"ok"})
    await _restart_worker_by_auth_uid(str(bot_state.game_to_auth_id.get(uid, uid)))
    return aiohttp.web.json_response({"status":"ok"})

async def api_squads(req):
    out = []
    for sid in sorted(_team_states.keys()):
        st = _team_states[sid]
        out.append({"squad_id":sid+1,"leader_uid":st.get("leader_uid"),
                    "team_code":st.get("team_code"),"member_ready":st.get("member_ready"),
                    "mode":st.get("mode"),"mode_name":CS_MODE_NAME.get(st.get("mode")),
                    "peers_count":len(st.get("peers",{}))})
    return aiohttp.web.json_response(out)

async def api_contact(req):
    return aiohttp.web.json_response({"telegram":panel_db.settings.get("telegram","https://t.me/dg_drift")})

async def api_vapid(req):
    return aiohttp.web.json_response({"publicKey":panel_db.settings.get("vapid_public_key","")})

async def api_noop(req):
    return aiohttp.web.json_response({"ok":True})

# ==================== SERVER ====================
@aiohttp.web.middleware
async def _logger(req, h):
    try:
        return await h(req)
    except aiohttp.web.HTTPException as e:
        if req.path.startswith("/api/"):
            return aiohttp.web.json_response({"ok":False,"error":e.reason or str(e)}, status=e.status)
        raise
    except Exception as e:
        traceback.print_exc()
        if req.path.startswith("/api/"):
            return aiohttp.web.json_response({"ok":False,"error":str(e)}, status=500)
        raise

async def start_web():
    app = aiohttp.web.Application(middlewares=[_logger])
    for p in ("/", "/index.html", "/bot"):
        app.router.add_get(p, handle_index)
    app.router.add_get("/ffglory", handle_ffglory)
    app.router.add_get("/admin", handle_admin)
    app.router.add_get("/client", handle_client)
    for p in ("/login", "/signup"):
        app.router.add_get(p, handle_login)
    app.router.add_get("/shared.css", handle_shared_css)
    app.router.add_get("/shared.js", handle_shared_js)
    app.router.add_get("/login.js", handle_login_js)
    app.router.add_get("/sw.js", handle_sw_js)
    for p in ("/logo.gif", "/favicon.ico", "/static/logo.gif"):
        app.router.add_get(p, handle_logo)
    if os.path.exists("static"): app.router.add_static("/static/", path="static")

    app.router.add_post("/api/auth/login", api_login)
    app.router.add_post("/api/auth/signup", api_signup)
    app.router.add_post("/api/auth/logout", api_logout)
    app.router.add_post("/api/logout", api_logout)
    app.router.add_post("/api/auth/change-password", api_chpw)
    app.router.add_get("/api/me", api_me)

    app.router.add_get("/api/admin/overview", api_admin_overview)
    app.router.add_get("/api/admin/users", api_admin_users)
    app.router.add_post("/api/admin/user/create", api_admin_user_create)
    app.router.add_post("/api/admin/user/credits", api_admin_credits)
    app.router.add_post("/api/admin/user/delete", api_admin_user_delete)
    app.router.add_get("/api/admin/bot-accounts", api_admin_bots)
    app.router.add_post("/api/admin/join-clan", api_admin_join_clan)

    app.router.add_get("/api/pricing", api_pricing)
    app.router.add_post("/api/client/launch", api_launch)
    app.router.add_get("/api/client/groups", api_groups)
    app.router.add_get("/api/glory", api_glory)
    app.router.add_get("/api/cs/status", api_cs_status)
    app.router.add_post("/api/cs/map", api_cs_map)
    app.router.add_get("/api/health", api_health)
    app.router.add_get("/api/public/contact-info", api_contact)
    app.router.add_get("/api/vapid-public-key", api_vapid)
    app.router.add_post("/api/push/subscribe", api_noop)
    app.router.add_get("/api/inbox/messages", api_noop)
    app.router.add_post("/api/inbox/mark-read", api_noop)
    app.router.add_post("/api/inbox/mark-all-read", api_noop)
    app.router.add_get("/api/notifications", api_noop)
    app.router.add_get("/api/client/active-alert", api_noop)
    app.router.add_post("/api/client/dismiss-alert", api_noop)

    app.router.add_get("/api/ping", api_ping)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_get("/api/logs", api_logs)
    app.router.add_post("/api/logs/clear", api_logs_clear)
    app.router.add_post("/api/clanjoin", api_clanjoin)
    app.router.add_post("/api/create_team", api_create_team)
    app.router.add_post("/api/account/add", api_account_add)
    app.router.add_post("/api/account/delete", api_account_delete)
    app.router.add_post("/api/account/pause", api_account_pause)
    app.router.add_post("/api/account/pause_all", api_pause_all)
    app.router.add_post("/api/account/restart", api_account_restart)
    app.router.add_get("/api/squads", api_squads)
    app.router.add_get("/api/guildinfo", api_glory)

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    await aiohttp.web.TCPSite(runner, WEB_HOST, WEB_PORT).start()
    print_success(f"[WEB] → http://localhost:{WEB_PORT}/  (CS-ONLY)")
    return runner

# ==================== MAIN ====================
async def main():
    print("\033[95m" + "╔══════════════════════════════════════════════════╗" + "\033[0m")
    print("\033[95m" + "║    👑  RAIX CLASH SQUAD MASTERPIECE v5.0  👑     ║" + "\033[0m")
    print("\033[96m" + f"║  mode=CLASH-SQUAD(8)  no-level-gate  maps={MAP_LADDER}" + "\033[0m")
    print("\033[96m" + f"║  identity={NICK_PREFIX}  startup_wd={STARTUP_TIMEOUT}s  sup={SUPERVISOR_INTERVAL}s" + "\033[0m")
    print("\033[95m" + "╚══════════════════════════════════════════════════╝" + "\033[0m")
    print_info(f"[CFG] password='{IDENTITY_PASSWORD}' data_dir={DATA_DIR} "
               f"restart_after={RESTART_AFTER_N} target={TARGET_ACCOUNTS} "
               f"ranked={CS_ALLOW_RANKED}")
    try:
        await start_web()
    except Exception as e:
        print_error(f"[WEB] {e}"); return
    asyncio.create_task(_supervisor())
    asyncio.create_task(_stats_loop())
    asyncio.create_task(_token_warm_loop())
    if TARGET_ACCOUNTS > 0:
        asyncio.create_task(_autocreate_loop())
    try:
        await _autoload_accounts()
    except Exception as e:
        print_error(f"[BOOT] {e}")
    try:
        while True: await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print_warning("shutting down")
        for t in list(bot_state.account_workers.values()): t.cancel()
        await asyncio.gather(*bot_state.account_workers.values(), return_exceptions=True)
        try: await client.aclose()
        except Exception: pass

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print_warning("stopped")