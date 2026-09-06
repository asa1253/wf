# -*- coding: utf-8 -*-
"""Warframe 精通进度页面生成脚本
- 拉取 warframestat 玩家精通汇总数据
- 拉取 WFCD/warframe-items 全量物品清单
- 生成 index.html：精通卡片 + 「还没有的物品」交互对比清单
- 生成 mastery.json 数据备份
"""
import json
import os
from datetime import datetime

import requests

# ---------- 配置 ----------
RAW_BASE = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json"

# 类别 -> 单个物品可提供的精通经验（XP）
# 战甲/曲翼/哨兵：6000；主/副/近战武器：3000
ITEM_XP = {
    "Warframes": 6000,
    "Archwing": 6000,
    "Sentinels": 6000,
    "Primary": 3000,
    "Secondary": 3000,
    "Melee": 3000,
}
# 类别中文名
CAT_CN = {
    "Warframes": "战甲",
    "Primary": "主武器",
    "Secondary": "副武器",
    "Melee": "近战武器",
    "Sentinels": "哨兵",
    "Archwing": "曲翼",
}

ITEM_FILES = {
    "Warframes": "Warframes.json",
    "Primary": "Primary.json",
    "Secondary": "Secondary.json",
    "Melee": "Melee.json",
    "Sentinels": "Sentinels.json",
    "Archwing": "Archwing.json",
}


def fetch_items():
    """拉取并精简全量可精通物品清单"""
    items = []
    for cat, fname in ITEM_FILES.items():
        url = f"{RAW_BASE}/{fname}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        for it in resp.json():
            if not it.get("name"):
                continue
            items.append({
                "n": it["name"],
                "c": cat,
                "t": it.get("type") or it.get("productCategory") or "",
                "mr": it.get("masteryReq") or 0,
                "p": bool(it.get("isPrime")),
                "x": ITEM_XP.get(cat, 0),
            })
    # 排序：类别顺序 + 名称
    order = list(ITEM_XP.keys())
    items.sort(key=lambda x: (order.index(x["c"]), x["n"].lower()))
    return items


def fetch_profile():
    """拉取玩家精通汇总数据"""
    user_id = os.environ["USER_ID"]
    api_url = f"https://api.warframestat.us/profile/{user_id}"
    resp = requests.get(api_url, timeout=25)
    resp.raise_for_status()
    data = resp.json()
    display_name = data.get("displayName", "未知玩家")
    mastery_rank = data.get("masteryRank", 0)
    mastery_xp = data.get("masteryXP", 0)
    next_rank_xp = data.get("nextRankXP", 0)
    if next_rank_xp == 0:
        progress_pct = 100.0
        progress_text = "已满级"
        is_max = True
    else:
        progress_pct = round((mastery_xp / next_rank_xp) * 100, 2)
        progress_text = f"{progress_pct}%"
        is_max = False
    return {
        "display_name": display_name,
        "mastery_rank": mastery_rank,
        "mastery_xp": mastery_xp,
        "next_rank_xp": next_rank_xp,
        "progress_pct": progress_pct,
        "progress_text": progress_text,
        "is_max": is_max,
    }


def build_html(profile, items):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    items_json = json.dumps(items, ensure_ascii=False)
    cat_json = json.dumps(CAT_CN, ensure_ascii=False)

    p = profile
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Warframe 精通进度</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  background:#0f141e; color:#e2e8f0; min-height:100vh; padding:32px 14px;
}}
.container {{ max-width:760px; margin:0 auto; }}
.card {{
  background:#1a2230; border-radius:16px; padding:28px;
  box-shadow:0 10px 30px rgba(0,0,0,.45); border:1px solid #2c3a4f;
}}
h2 {{ text-align:center; color:#72c3ff; margin-bottom:22px; font-size:24px; letter-spacing:1px; }}
.info-row {{ display:flex; justify-content:space-between; padding:12px 0; border-bottom:1px solid #2c3a4f; font-size:16px; }}
.info-row:last-of-type {{ border-bottom:none; }}
.label {{ color:#94a3b8; }}
.value {{ font-weight:600; }}
.progress-wrap {{ margin-top:20px; }}
.progress-bar {{ height:24px; background:#273344; border-radius:12px; overflow:hidden; margin-bottom:10px; }}
.progress {{ height:100%; border-radius:12px; background:linear-gradient(90deg,#3b82f6,#22d3ee); width:{p['progress_pct']}%; transition:width .8s ease-out; }}
.progress-full {{ background:linear-gradient(90deg,#22c55e,#84cc16); }}
.progress-text {{ text-align:center; font-size:18px; font-weight:bold; }}
.tip-max {{ color:#4ade80; text-align:center; margin-top:8px; }}
.update-time {{ margin-top:24px; text-align:center; font-size:13px; color:#64748b; }}

/* ---- 物品对比模块 ---- */
.mastery {{
  margin-top:26px; background:#1a2230; border-radius:16px; padding:24px;
  border:1px solid #2c3a4f; box-shadow:0 10px 30px rgba(0,0,0,.45);
}}
.mastery h3 {{ color:#72c3ff; font-size:20px; margin-bottom:16px; }}
.stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:18px; }}
.stat {{ background:#121a28; border-radius:10px; padding:12px; text-align:center; border:1px solid #2c3a4f; }}
.stat .num {{ font-size:22px; font-weight:700; }}
.stat .num.have {{ color:#22c55e; }}
.stat .num.miss {{ color:#f59e0b; }}
.stat .num.total {{ color:#72c3ff; }}
.stat .lbl {{ font-size:12px; color:#94a3b8; margin-top:4px; }}
.toolbar {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:16px; align-items:center; }}
.tabs {{ display:flex; flex-wrap:wrap; gap:6px; }}
.tab {{ background:#273344; border:1px solid #2c3a4f; color:#cbd5e1; padding:6px 12px; border-radius:8px; cursor:pointer; font-size:13px; }}
.tab.active {{ background:#3b82f6; border-color:#3b82f6; color:#fff; }}
.search {{
  flex:1; min-width:180px; background:#121a28; border:1px solid #2c3a4f; color:#e2e8f0;
  border-radius:8px; padding:8px 12px; font-size:14px; outline:none;
}}
.search:focus {{ border-color:#3b82f6; }}
.list {{ max-height:520px; overflow:auto; border:1px solid #2c3a4f; border-radius:10px; }}
.row {{ display:flex; align-items:center; gap:10px; padding:9px 12px; border-bottom:1px solid #222d40; font-size:14px; }}
.row:last-child {{ border-bottom:none; }}
.row input {{ width:17px; height:17px; accent-color:#22c55e; cursor:pointer; flex:none; }}
.row .nm {{ flex:1; }}
.row .badge {{ font-size:11px; padding:2px 8px; border-radius:6px; flex:none; }}
.badge.prime {{ background:#7c3aed; color:#fff; }}
.badge.sub {{ background:#334155; color:#cbd5e1; }}
.badge.mr {{ background:#1d4ed8; color:#cfe; }}
.badge.xp {{ background:#14532d; color:#bbf7d0; }}
.row.miss .nm {{ color:#fcd34d; font-weight:600; }}
.row.owned .nm {{ color:#64748b; text-decoration:line-through; }}
.footnote {{ margin-top:14px; font-size:12px; color:#64748b; text-align:center; line-height:1.6; }}
</style>
</head>
<body>
<div class="container">

  <div class="card">
    <h2>Warframe 精通档案</h2>
    <div class="info-row"><span class="label">玩家昵称</span><span class="value">{p['display_name']}</span></div>
    <div class="info-row"><span class="label">精通段位</span><span class="value">{p['mastery_rank']}</span></div>
    <div class="info-row"><span class="label">当前精通经验</span><span class="value">{p['mastery_xp']:,}</span></div>
    <div class="info-row"><span class="label">下一段所需经验</span><span class="value">{p['next_rank_xp']:,}</span></div>
    <div class="progress-wrap">
      <div class="progress-bar"><div class="progress {'progress-full' if p['is_max'] else ''}"></div></div>
      <div class="progress-text">{p['progress_text']}</div>
      {('<div class="tip-max">已达到最高精通段位</div>' if p['is_max'] else '')}
    </div>
    <div class="update-time">数据更新时间：{now}</div>
  </div>

  <div class="mastery">
    <h3>精通物品对比 · 还没有的物品</h3>
    <div class="stats">
      <div class="stat"><div class="num total" id="stTotal">0</div><div class="lbl">可精通物品</div></div>
      <div class="stat"><div class="num have" id="stHave">0</div><div class="lbl">已拥有</div></div>
      <div class="stat"><div class="num miss" id="stMiss">0</div><div class="lbl">还没有 · 可获经验</div></div>
    </div>
    <div class="toolbar">
      <div class="tabs" id="tabs"></div>
      <input class="search" id="q" placeholder="搜索物品名称…" type="text">
    </div>
    <div class="list" id="list"></div>
    <div class="footnote">
      提示：勾选代表你已拥有/已精通该物品（自动保存在本浏览器）。剩下的就是「还没有的物品」，可为提升段位提供经验。数据来自社区物品库。
    </div>
  </div>

</div>

<script>
const CATS = {cat_json};
const ITEMS = {items_json};

// 类别顺序
const ORDER = ["Warframes","Primary","Secondary","Melee","Sentinels","Archwing"];
let curCat = "ALL";
let kw = "";

const STORE = "wf_owned_v1";
function loadOwned() {{
  try {{ return new Set(JSON.parse(localStorage.getItem(STORE) || "[]")); }}
  catch(e) {{ return new Set(); }}
}}
let owned = loadOwned();
function saveOwned() {{ localStorage.setItem(STORE, JSON.stringify([...owned])); }}

function renderStats() {{
  const total = ITEMS.length;
  const have = ITEMS.filter(i => owned.has(i.n)).length;
  const miss = ITEMS.filter(i => !owned.has(i.n)).length;
  const missXp = ITEMS.filter(i => !owned.has(i.n)).reduce((s,i) => s + i.x, 0);
  document.getElementById("stTotal").textContent = total;
  document.getElementById("stHave").textContent = have;
  document.getElementById("stMiss").textContent = miss + " · " + missXp.toLocaleString() + "XP";
}}

function renderTabs() {{
  const t = document.getElementById("tabs");
  t.innerHTML = "";
  const mk = (id, label) => {{
    const b = document.createElement("button");
    b.className = "tab" + (curCat === id ? " active" : "");
    b.textContent = label;
    b.onclick = () => {{ curCat = id; renderTabs(); renderList(); }};
    t.appendChild(b);
  }};
  mk("ALL", "全部");
  ORDER.forEach(c => mk(c, CATS[c]));
}}

function renderList() {{
  const list = document.getElementById("list");
  list.innerHTML = "";
  let arr = ITEMS;
  if (curCat !== "ALL") arr = arr.filter(i => i.c === curCat);
  if (kw) {{ const k = kw.toLowerCase(); arr = arr.filter(i => i.n.toLowerCase().includes(k)); }}
  if (arr.length === 0) {{
    list.innerHTML = '<div style="padding:20px;color:#64748b;text-align:center;">没有匹配的物品</div>';
    return;
  }}
  arr.forEach(i => {{
    const owned1 = owned.has(i.n);
    const row = document.createElement("div");
    row.className = "row" + (owned1 ? " owned" : " miss");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = owned1;
    cb.onchange = () => {{
      if (cb.checked) owned.add(i.n); else owned.delete(i.n);
      saveOwned(); renderStats(); renderList();
    }};
    const nm = document.createElement("span");
    nm.className = "nm";
    nm.textContent = i.n;
    const badges = document.createElement("span");
    badges.style.cssText = "display:flex;gap:6px;flex:none;flex-wrap:wrap;";
    if (i.p) badges.innerHTML += '<span class="badge prime">Prime</span>';
    badges.innerHTML += '<span class="badge sub">' + (i.t || CATS[i.c]) + '</span>';
    badges.innerHTML += '<span class="badge mr">MR ' + i.mr + '</span>';
    badges.innerHTML += '<span class="badge xp">' + i.x.toLocaleString() + 'XP</span>';
    row.appendChild(cb); row.appendChild(nm); row.appendChild(badges);
    list.appendChild(row);
  }});
}}

document.getElementById("q").addEventListener("input", e => {{ kw = e.target.value.trim(); renderList(); }});
renderTabs(); renderList(); renderStats();
</script>
</body>
</html>"""


def main():
    profile = fetch_profile()
    items = fetch_items()
    html = build_html(profile, items)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    result_data = {
        "user_id": os.environ.get("USER_ID", ""),
        **profile,
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "itemCount": len(items),
    }
    with open("mastery.json", "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"OK: index.html 生成完毕，共 {len(items)} 件可精通物品")


if __name__ == "__main__":
    main()
