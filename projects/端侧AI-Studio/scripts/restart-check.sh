#!/usr/bin/env bash
# 给 verify.sh 用的四个动作。数据放在它给的临时目录里，写入不调用模型。
set -u
PRODUCT="$(cd "$(dirname "$0")/.." && pwd)"
ACTION="${1:-}"
DIR="${RESTART_CHECK_DIR:-}"
if [ -z "$DIR" ]; then echo "没有临时目录" >&2; exit 1; fi
PORT_FILE="$DIR/port"
PID_FILE="$DIR/pid"
COOKIE="$DIR/cookies.txt"

start_server() {
  local port=8765
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "端口 8765 已被占用" >&2
    exit 1
  fi
  mkdir -p "$DIR/files"
  local py="$PRODUCT/backend/.venv/bin/python"
  [ -x "$py" ] || py="$(command -v python3.12 || command -v python3)"
  (
    cd "$PRODUCT/backend" || exit 1
    export DATABASE_URL="sqlite:///$DIR/app.db"
    export DATA_DIR="$DIR/files"
    export INVITE_CODE="studio-demo"
    export SESSION_SECRET="change-me"
    export FAKE_MODELS="false"
    export DEEPSEEK_API_KEY=""
    export SENSETIME_API_KEYS=""
    nohup "$py" -m uvicorn app.main:app --host 127.0.0.1 --port "$port" >"$DIR/server.log" 2>&1 &
    echo $! >"$PID_FILE"
  )
  echo "$port" >"$PORT_FILE"
  local i
  for i in $(seq 1 50); do
    if curl -sf "http://127.0.0.1:$port/api/v1/health" >/dev/null; then
      cat "$PID_FILE"
      exit 0
    fi
    sleep 0.2
  done
  echo "服务没有起来" >&2
  cat "$DIR/server.log" >&2 || true
  exit 1
}

case "$ACTION" in
  start) start_server ;;
  write)
    python3 - "$DIR" "${2:-}" <<'PY'
import json, sys, urllib.request
folder, marker = sys.argv[1], sys.argv[2]
port = open(f"{folder}/port").read().strip()
base = f"http://127.0.0.1:{port}"
cookie = f"{folder}/cookies.txt"

def call(method, path, body=None, auth=False):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if auth:
        req.add_header("Cookie", open(cookie).read().strip())
    with urllib.request.urlopen(req, timeout=10) as res:
        raw = res.read()
        set_cookie = res.headers.get("Set-Cookie")
        return raw, set_cookie

_, set_cookie = call("POST", "/api/v1/auth/login", {"invite_code": "studio-demo"})
token = set_cookie.split(";", 1)[0] if set_cookie else ""
open(cookie, "w").write(token)
raw, _ = call("POST", "/api/v1/works", {"title": marker}, auth=True)
print(json.loads(raw)["id"])
PY
    ;;
  read)
    python3 - "$DIR" "${2:-}" <<'PY'
import json, sys, urllib.request
folder, work_id = sys.argv[1], sys.argv[2]
port = open(f"{folder}/port").read().strip()
cookie = open(f"{folder}/cookies.txt").read().strip()
req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/works/{work_id}")
req.add_header("Cookie", cookie)
with urllib.request.urlopen(req, timeout=10) as res:
    print(json.loads(res.read())["title"])
PY
    ;;
  stop)
    if [ -f "$PID_FILE" ]; then kill "$(cat "$PID_FILE")" >/dev/null 2>&1 || true; fi
    ;;
  *) echo "用法：restart-check.sh start|write|read|stop" >&2; exit 1 ;;
esac
