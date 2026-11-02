#!/usr/bin/env bash
# 流程管家：站在产品经理和编码工具中间的看门人。
#   - 记住现在做哪个产品、第几阶段；
#   - 把本阶段任务写成 docs/本阶段任务.md，打开产品经理装的编码工具并贴好开场白；
#   - 工具关掉后自动跑 verify.sh；自检没过就不让进下一阶段；
#   - 自检过了，问产品经理"验收通过了吗"，y 才翻到下一阶段。
# 不碰模型、不花钱、不存密钥。规则本身仍在 AGENTS.md 和手册里，管家只保证"该交的交了、该停的停了"。
#
# 用法（产品经理一般只双击 开工.command，不用记这些）：
#   bash kit.sh                 正常走流程
#   bash kit.sh 状态            只看现在到哪了
#   bash kit.sh 换工具          下次开工重新选编码工具
#   bash kit.sh 回到 阶段2-1    管家记的阶段和实际不符时手动校正
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

say()  { printf '%s\n' "$*"; }
line() { say "────────────────────────────────────────────────────────"; }
ask()  { # ask "问题" → 回答存在 ANS
  printf '%s ' "$1"
  if ! IFS= read -r ANS; then say; say "没有收到输入，先到这里。下次双击开工继续。"; exit 1; fi
  ANS="$(printf '%s' "$ANS" | tr -d '[:space:]')"
}
ask_yn() { # ask_yn "问题" → 返回 0=y 1=n
  while :; do ask "$1 [y/n]"; case "$ANS" in y|Y|是) return 0;; n|N|否) return 1;; esac; say "请输入 y 或 n。"; done
}

# ---------- 选产品 ----------
PRODUCTS=()
for d in projects/*/; do [ -d "$d" ] && PRODUCTS+=("$(basename "$d")"); done
if [ "${#PRODUCTS[@]}" -eq 0 ]; then say "projects/ 下没有产品文件夹。先按 README 放好 PRD，或让 AI 新建产品。"; exit 2; fi
if [ "${#PRODUCTS[@]}" -eq 1 ]; then PRODUCT="${PRODUCTS[0]}"
else
  say "有多个产品，这次做哪个？"; i=1
  for p in "${PRODUCTS[@]}"; do
    st="还没开始"; [ -f "projects/$p/docs/流程状态.txt" ] && st="$(grep -m1 '^阶段=' "projects/$p/docs/流程状态.txt" | cut -d= -f2-)"
    say "  $i) $p（$st）"; i=$((i+1))
  done
  while :; do ask "输入编号："; if [[ "$ANS" =~ ^[0-9]+$ ]] && [ "$ANS" -ge 1 ] && [ "$ANS" -le "${#PRODUCTS[@]}" ]; then PRODUCT="${PRODUCTS[$((ANS-1))]}"; break; fi; done
fi
P="projects/$PRODUCT"
STATE="$P/docs/流程状态.txt"
HIST="$P/docs/流程历史.txt"
TASK="$P/docs/本阶段任务.md"
mkdir -p "$P/docs"

# ---------- 状态文件（key=value） ----------
sget() { [ -f "$STATE" ] && grep -m1 "^$1=" "$STATE" | cut -d= -f2- || true; }
sset() { local t; t="$(mktemp)"; { [ -f "$STATE" ] && grep -v "^$1=" "$STATE"; printf '%s=%s\n' "$1" "$2"; } > "$t" 2>/dev/null; mv "$t" "$STATE"; }
hist() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M')" "$*" >> "$HIST"; }

STAGES_ALL="阶段0 阶段1 阶段2-1 阶段3-0 阶段3-1 阶段4 阶段5"
if [ ! -f "$STATE" ]; then
  if [ -f "$P/docs/项目状态.md" ]; then
    say "这个产品以前做过，但管家还没记录过它。现在做到第几阶段？"
    say "  可填：阶段0、阶段1、阶段2-1、阶段2-2…、阶段3-0、阶段3-1…、阶段4、阶段5（直接回车 = 阶段0）"
    ask "阶段："; [ -z "$ANS" ] && ANS="阶段0"
    sset 阶段 "$ANS"
  else
    sset 阶段 阶段0
  fi
  sset 状态 待开工; hist "管家开始记录，起点 $(sget 阶段)"
fi

# ---------- 阶段信息（来自 AGENTS.md 第 7 节加载表） ----------
stage_info() { # 设置 READ OUT PM PASS NOCODE
  NOCODE=0
  case "$1" in
    阶段0) READ="AGENTS.md；docs/PRD/；通用手册第二节与《二之一、PRD 体检》"
           OUT="docs/阶段文档/阶段0-PRD补全清单.md；docs/evidence/阶段0/是否表.md；docs/项目状态.md（新建或更新）"
           PM="回答\"必须问\"的问题（一次不超过 5 个，可回复\"按推荐\"）"
           PASS="《PRD 补全清单》全部关闭"; NOCODE=1 ;;
    阶段1) READ="通用手册第一部分（一至六节）"
           OUT="docs/阶段文档/技术适配声明.md（含第 7 节子阶段规划）；决策台账初版；docs/evidence/阶段1/是否表.md"
           PM="确认三件事：理解和子阶段规划对不对 / 有没有新增费用·平台·范围 / 暂缓项影不影响验收"
           PASS="台账无影响本阶段的待定项"; NOCODE=1 ;;
    阶段2-*) READ="通用手册第二、三部分"
           OUT="docs/阶段文档/$1技术开发文档.md；代码；产品 README.md；证据包 docs/evidence/$1/（截图、照着做清单、是否表、verify-输出、冒烟记录）"
           PM="提供模型 Key；按\"照着做\"清单验收；对真实样例打分"
           PASS="证据包已交 + 是否表全\"是\"" ;;
    阶段3-0) READ="前端手册全文"
           OUT="docs/阶段文档/前端适配声明.md；docs/evidence/阶段3-0/是否表.md"
           PM="给视觉方向（或说\"中性风格\"）；确认前端适配声明"
           PASS="声明经产品经理确认"; NOCODE=1 ;;
    阶段3-*) READ="前端手册全文（重点第 22 节本子阶段对应部分）"
           OUT="docs/阶段文档/$1技术开发文档.md；前端代码；产品 README.md；证据包 docs/evidence/$1/"
           PM="看代表页反馈；用手机走一遍"
           PASS="证据包已交 + 是否表全\"是\"" ;;
    阶段4) READ="部署手册全文"
           OUT="docs/阶段文档/上线方案摘要.md（含费用与耗时估算）；部署；产品 README.md；证据包 docs/evidence/阶段4/"
           PM="注册腾讯云并实名、浏览器授权命令行登录、开通云开发环境并启用云托管、创建服务端 API Key 并点复制、确认费用、按验收清单验证"
           PASS="部署手册第六部分验收清单全过" ;;
    阶段5) READ="部署手册第五部分\"收尾\""
           OUT="产品 README.md；docs/项目状态.md 记录完成；退出本机命令行登录；服务端 API Key 到期提醒"
           PM="不删服务端 API Key；确认 AI 退出命令行登录后线上仍正常"
           PASS="状态文件记录完成"; NOCODE=1 ;;
    *) READ="（未知阶段）"; OUT=""; PM=""; PASS="" ;;
  esac
}

# ---------- 编码工具 ----------
# 启动方式：auto = 带开场白直接打开；semi = 打开工具，开场白已复制到剪贴板，产品经理粘贴一次；manual = 不打开，产品经理自己开工具再粘贴
tool_name() { case "$1" in
  claude) echo "Claude Code";; codex) echo "Codex";; pi) echo "Pi";; gemini) echo "Gemini CLI";; opencode) echo "OpenCode";;
  cursor) echo "Cursor 命令行版";; kimi) echo "Kimi Code";; mimo) echo "MiMo Code";; zcode) echo "Z Code";;
  other) echo "其他工具（Cursor、Windsurf、Trae 等带界面的）";; *) echo "$1";; esac; }
tool_mode() { case "$1" in claude|codex|pi|gemini|opencode|cursor) echo auto;; kimi|mimo|zcode) echo semi;; *) echo manual;; esac; }
tool_bin()  { case "$1" in cursor) command -v cursor-agent >/dev/null 2>&1 && echo cursor-agent || echo agent;; *) echo "$1";; esac; }
detect_tools() { FOUND=(); for t in claude codex pi gemini opencode cursor kimi mimo zcode; do command -v "$(tool_bin "$t")" >/dev/null 2>&1 && FOUND+=("$t"); done; }
choose_tool() {
  detect_tools
  if [ "${#FOUND[@]}" -eq 0 ]; then say "电脑上没找到我认识的编码工具，用通用模式。"; TOOL=other; return; fi
  say "电脑上装了这些编码工具："; i=1
  for t in "${FOUND[@]}"; do say "  $i) $(tool_name "$t")"; i=$((i+1)); done
  say "  $i) $(tool_name other)"
  while :; do ask "用哪个？输入编号（直接回车 = 1）："; [ -z "$ANS" ] && ANS=1
    if [[ "$ANS" =~ ^[0-9]+$ ]] && [ "$ANS" -ge 1 ] && [ "$ANS" -le "$i" ]; then
      if [ "$ANS" -eq "$i" ]; then TOOL=other; else TOOL="${FOUND[$((ANS-1))]}"; fi; break
    fi
  done
}
copy_clip() { if command -v pbcopy >/dev/null 2>&1; then printf '%s' "$1" | pbcopy; return 0; fi; return 1; }
launch_tool() { # $1 工具 $2 开场白
  local t="$1" prompt="$2" mode bin
  mode="$(tool_mode "$t")"; bin="$(tool_bin "$t")"
  case "$mode" in
    auto)
      say "正在打开 $(tool_name "$t")，开场白已经贴好。像平时一样和它对话；它说\"本阶段做完了\"你就关掉它（输入 /exit 或按两次 Ctrl+C），回到这个窗口。"
      line
      case "$t" in
        claude)   "$bin" "$prompt" ;;
        codex)    "$bin" "$prompt" ;;
        pi)       "$bin" "$prompt" ;;
        gemini)   "$bin" -i "$prompt" ;;
        opencode) "$bin" --prompt "$prompt" ;;
        cursor)   "$bin" "$prompt" ;;
      esac ;;
    semi)
      if copy_clip "$prompt"; then say "开场白已复制到剪贴板。"; else say "开场白如下（请复制）："; say "    $prompt"; fi
      say "正在打开 $(tool_name "$t")。打开后按 Command+V 粘贴开场白并回车；它说\"本阶段做完了\"你就关掉它，回到这个窗口。"
      line
      "$bin" ;;
    *)
      if copy_clip "$prompt"; then say "开场白已复制到剪贴板。"; else say "开场白如下（请复制）："; fi
      say "    $prompt"
      say "现在打开你的编码工具，让它打开工具包文件夹，粘贴上面这句并发送。它说\"本阶段做完了\"你就回到这个窗口。"
      ask "聊完后按回车继续："
      ;;
  esac
  line
}

# ---------- 本阶段任务文件 ----------
write_task() { # $1 阶段
  local st="$1" n lastfail=""
  stage_info "$st"
  n="$(sget 开工次数)"; n=$(( ${n:-0} + 1 )); sset 开工次数 "$n"
  if [ "$(sget 状态)" = "自检没过" ] && [ -f "$P/docs/evidence/$st/verify-输出.txt" ]; then
    lastfail="$( { grep -E '^(缺：|问题：|放错位置：)' "$P/docs/evidence/$st/verify-输出.txt"; sed -n '/汇总/,$p' "$P/docs/evidence/$st/verify-输出.txt" | grep -E '不通过|未配置|待验'; } | sort -u || true)"
  fi
  {
    say "# 本阶段任务（流程管家自动生成，每次开工覆盖；AI 不要改这个文件）"
    say
    say "- 产品：$PRODUCT（文件夹 projects/$PRODUCT/）"
    say "- 阶段：$st（本阶段第 $n 次开工）"
    say "- 生成时间：$(date '+%Y-%m-%d %H:%M')"
    say
    say "## 先做"
    say "1. 读工具包根目录的 AGENTS.md，按第 0 节启动流程处理这个产品（有 docs/项目状态.md 就是老项目，从它记录的地方接着做）。"
    say "2. 本阶段只读这些手册内容：$READ。读完按 AGENTS.md 第 7 节做一次对账（列出与十条底线冲突的句子，没有就说\"已对账，无冲突\"）。"
    say
    say "## 本阶段要交的"
    say "$OUT"
    say "证据包的固定文件见 AGENTS.md 第 5 节。"
    say
    say "## 产品经理这阶段要做的（由你翻译成\"去哪、点什么、填什么、看到什么算对\"）"
    say "$PM"
    say
    say "## 通过条件"
    say "$PASS"
    if [ -n "$lastfail" ]; then
      say
      say "## 上次自检没过的项（先解决这些）"
      say '```'
      say "$lastfail"
      say '```'
    fi
    say
    say "## 规矩"
    say "- 只做 $st，不做下一阶段的事。$( [ "$NOCODE" -eq 1 ] && say "这是无代码阶段，不要写代码、不要建 backend/ frontend/。" )"
    say "- 需要产品经理决定的事，用决策卡当面问他（一次不超过 5 个），记入 docs/项目状态.md。"
    say "- 做完后在工具包根目录运行 \`./verify.sh $PRODUCT $st\`，把六项结果抄进是否表。"
    say "- 不要修改 docs/本阶段任务.md、docs/流程状态.txt、docs/流程历史.txt，它们归流程管家。"
    say "- 全部做完后对产品经理说这句话：\"本阶段做完了，请关闭我，回到开工窗口看自检结果。\""
  } > "$TASK"
}

# ---------- 翻到下一阶段 ----------
next_stage() { # $1 当前 → 设置 NEXT（"完成" 表示结束）
  local cur="$1" n
  case "$cur" in
    阶段0) NEXT=阶段1 ;;
    阶段1) NEXT=阶段2-1 ;;
    阶段2-*) n="${cur#阶段2-}"
      if ask_yn "阶段 2 还有下一个子阶段吗？（看《技术适配声明》第 7 节子阶段规划）"; then NEXT="阶段2-$((n+1))"; else NEXT=阶段3-0; fi ;;
    阶段3-0) NEXT=阶段3-1 ;;
    阶段3-*) n="${cur#阶段3-}"
      if ask_yn "阶段 3 还有下一个子阶段吗？（看《技术适配声明》第 7 节子阶段规划）"; then NEXT="阶段3-$((n+1))"
      else
        say "阶段 3 过了就算合格。接下来："; say "  4) 上线（阶段 4，要注册腾讯云）"; say "  5) 直接收尾（阶段 5，这次做到合格为止）"
        while :; do ask "输入 4 或 5："; case "$ANS" in 4) NEXT=阶段4; break;; 5) NEXT=阶段5; break;; esac; done
      fi ;;
    阶段4) NEXT=阶段5 ;;
    阶段5) NEXT=完成 ;;
    *) NEXT=完成 ;;
  esac
}

# ---------- 显示状态 ----------
show_status() {
  local st status
  st="$(sget 阶段)"; status="$(sget 状态)"; stage_info "$st"
  line; say "产品：$PRODUCT"; say "阶段：$st　　状态：$status"
  [ -n "$(sget 工具)" ] && say "编码工具：$(tool_name "$(sget 工具)")"
  say "本阶段要交：$OUT"
  say "本阶段你要做：$PM"
  line
}

# ---------- 子命令 ----------
case "${1:-}" in
  状态) show_status; exit 0 ;;
  换工具) sset 工具 ""; say "好，下次开工会重新问用哪个工具。"; exit 0 ;;
  回到) [ -n "${2:-}" ] || { say "用法：bash kit.sh 回到 阶段2-1"; exit 1; }
       sset 阶段 "$2"; sset 状态 待开工; sset 开工次数 0; hist "手动校正到 $2"; say "已回到 $2。"; exit 0 ;;
  "") ;;
  *) say "不认识的参数：$1。可用：状态 / 换工具 / 回到 阶段X"; exit 1 ;;
esac

# ---------- 主流程 ----------
STAGE="$(sget 阶段)"; STATUS="$(sget 状态)"
if [ "$STAGE" = "完成" ]; then show_status; say "这个产品的流程已经走完。要再做改动，用 bash kit.sh 回到 阶段X 回到对应阶段。"; exit 0; fi
show_status

if [ "$STATUS" = "等验收" ]; then
  say "上次自检已通过，现在轮到你验收：按 docs/evidence/$STAGE/照着做清单.md 点一遍（无代码阶段就是看文档、确认该确认的事）。"
  if ask_yn "验收通过了吗？"; then
    next_stage "$STAGE"; hist "$STAGE 验收通过 → $NEXT"
    sset 阶段 "$NEXT"; sset 状态 待开工; sset 开工次数 0
    if [ "$NEXT" = "完成" ]; then say "全部完成！"; exit 0; fi
    say "已翻到 $NEXT。"
    if ! ask_yn "现在就开始做 $NEXT 吗？"; then say "好，下次双击开工继续。"; exit 0; fi
    STAGE="$NEXT"; STATUS=待开工; show_status
  else
    sset 状态 做中; hist "$STAGE 验收未通过，继续改"
    say "好，留在 $STAGE。把没通过的地方告诉 AI 去改。"
    if ! ask_yn "现在打开工具继续改吗？"; then exit 0; fi
  fi
fi

# 选工具
TOOL="$(sget 工具)"
if [ -z "$TOOL" ]; then choose_tool; sset 工具 "$TOOL"; fi
# 写任务、开工
write_task "$STAGE"; sset 状态 做中; hist "$STAGE 开工（第 $(sget 开工次数) 次，工具 $(tool_name "$TOOL")）"
PROMPT="请读取 projects/$PRODUCT/docs/本阶段任务.md，按其中要求做 $STAGE。"
launch_tool "$TOOL" "$PROMPT"

# 自检
say "工具已关闭，现在跑自检：bash verify.sh $PRODUCT $STAGE"
line
bash verify.sh "$PRODUCT" "$STAGE"; RC=$?
line
if [ "$RC" -eq 0 ]; then
  sset 状态 等验收; hist "$STAGE 自检通过"
  say "自检通过。下一步轮到你验收：按 docs/evidence/$STAGE/照着做清单.md 点一遍（无代码阶段就是看文档、确认该确认的事）。"
  if ask_yn "验收通过了吗？（还没看就先选 n，下次双击开工再回答）"; then
    next_stage "$STAGE"; hist "$STAGE 验收通过 → $NEXT"
    sset 阶段 "$NEXT"; sset 状态 待开工; sset 开工次数 0
    if [ "$NEXT" = "完成" ]; then say "全部完成！"; else say "已翻到 $NEXT。下次双击开工就从它开始。"; fi
  else
    say "好，留在 $STAGE 等验收。验收完再双击开工回答。"
  fi
else
  sset 状态 自检没过; hist "$STAGE 自检没过"
  say "自检没过（上面有哪几项）。不能进下一阶段。"
  say "下次双击开工，AI 会看到没过的项并补齐；也可以现在把上面的结果贴给它。"
fi
