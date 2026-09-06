import requests
import json
from jinja2 import Template
from datetime import datetime
import os

USER_ID = os.getenv("WF_USER_ID", "")
WF_COOKIE = os.getenv("WF_COOKIE", "")
PLATFORM = "pc"

MR_THRESHOLDS = [
    0, 2500, 5750, 9750, 14500, 20000, 26250, 33250, 41000, 49500,
    58750, 68750, 79500, 91000, 103250, 116250, 130000, 144500, 159750, 175750
]

def get_item_source(item_name: str) -> str:
    name = item_name.lower()
    if "prime" in name:
        return "Prime"
    elif "kuva" in name:
        return "Kuva"
    elif "tenet" in name:
        return "Tenet"
    return "基础版/其他"

def safe_get(url, headers, timeout=15):
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.encoding = "utf-8"
        return resp
    except UnicodeEncodeError:
        safe_header = {"User-Agent": headers.get("User-Agent", "")}
        resp = requests.get(url, headers=safe_header, timeout=timeout)
        resp.encoding = "utf-8"
        return resp

os.makedirs("data", exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
if WF_COOKIE:
    headers["Cookie"] = WF_COOKIE

# 1.拉取公开物品库
item_list = []
try:
    resp_items = safe_get(f"https://api.warframestat.us/{PLATFORM}/items", headers=headers, timeout=15)
    raw = resp_items.json()
    if isinstance(raw, dict):
        item_list = raw.get("items") or raw.get("data") or []
    elif isinstance(raw, list):
        item_list = raw
except Exception as e:
    print(f"物品库请求失败：{e}")

# 2.拉取个人档案
profile_data = {}
owned_unique_names = set()
mastered_unique_names = set()

if WF_COOKIE and USER_ID:
    try:
        url = f"https://api.warframe.com/cdn/getProfileViewingData.php?playerId={USER_ID}"
        resp_profile = safe_get(url, headers=headers, timeout=20)
        ctype = resp_profile.headers.get("content-type", "")
        if ctype.startswith("application/json"):
            profile_data = resp_profile.json()
            print("✅成功获取真实个人档案")
            if "inventory" in profile_data:
                for entry in profile_data["inventory"]:
                    unique = entry.get("uniqueName")
                    if unique:
                        owned_unique_names.add(unique)
                        if entry.get("rank") == 30 or entry.get("mastered") is True:
                            mastered_unique_names.add(unique)
        else:
            print("⚠️Cookie失效，无法读取档案")
    except UnicodeEncodeError as uni_err:
        print(f"⚠️返回内容包含特殊Unicode字符，编码异常：{uni_err}")
    except Exception as e:
        print(f"档案请求异常：{e}")
else:
    print("ℹ️未配置鉴权Secret")

# 保存原始JSON
with open("data/raw_profile.json", "w", encoding="utf-8") as f:
    json.dump(profile_data, f, ensure_ascii=False, indent=2)
with open("data/raw_items.json", "w", encoding="utf-8") as f:
    json.dump(item_list, f, ensure_ascii=False, indent=2)

# 3.绑定拥有/精通状态 + 来源统计
source_stat = {
    "Prime": {"total": 0, "owned": 0, "mastered": 0, "xp_total": 0, "xp_mastered": 0},
    "Kuva": {"total": 0, "owned": 0, "mastered": 0, "xp_total": 0, "xp_mastered": 0},
    "Tenet": {"total": 0, "owned": 0, "mastered": 0, "xp_total": 0, "xp_mastered": 0},
    "基础版/其他": {"total": 0, "owned": 0, "mastered": 0, "xp_total": 0, "xp_mastered": 0},
}
parsed_items = []

for it in item_list:
    if not isinstance(it, dict):
        continue
    name = it.get("name", "未知")
    uname = it.get("uniqueName", "")
    xp = it.get("masteryReq", 0)
    src = get_item_source(name)

    owned = uname in owned_unique_names
    mastered = uname in mastered_unique_names

    source_stat[src]["total"] += 1
    source_stat[src]["xp_total"] += xp
    if owned:
        source_stat[src]["owned"] += 1
    if mastered:
        source_stat[src]["mastered"] += 1
        source_stat[src]["xp_mastered"] += xp

    parsed_items.append({
        "name": name,
        "uniqueName": uname,
        "source": src,
        "masteryXP": xp,
        "owned": owned,
        "mastered": mastered
    })

export_data = {
    "user_id": USER_ID,
    "update_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    "source_stat": source_stat,
    "item_list": parsed_items,
    "profile_available": bool(profile_data)
}
with open("data/mastery.json", "w", encoding="utf-8") as f:
    json.dump(export_data, f, ensure_ascii=False, indent=2)

# 4.渲染完整可视化页面
html_template = Template("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Warframe｜真实精通档案自动统计</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{box-sizing:border-box;font-family:system-ui}
body{max-width:1300px;margin:2rem auto;padding:0 1rem;background:#111;color:#eee}
h1{color:#f2c94c;text-align:center}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin:20px 0}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}
.card{border:1px solid #444;padding:16px;border-radius:8px;background:#1e1e1e}
.stat-line{display:flex;justify-content:space-between;padding:4px 0}
table{width:100%;border-collapse:collapse;margin-top:1rem}
th,td{border:1px solid #333;padding:8px 10px;text-align:left}
#search{width:100%;padding:10px;background:#222;border:1px solid #444;color:#fff;border-radius:6px;margin-bottom:12px}
.tag-prime{color:#ffd700}
.tag-kuva{color:#bb2222}
.tag-tenet{color:#6699ff}
.tag-normal{color:#aaa}
.status-yes{color:#4ade80}
.status-no{color:#777}
.success{color:#4ade80}
.warn{color:#ff6666}
</style>
</head>
<body>
<h1>⚔️ Warframe 个人精通追踪（自动拉取真实档案）</h1>
<div class="card">
    <p>用户ID：{{data.user_id}}</p>
    <p>更新时间：{{data.update_time}}</p>
    {% if data.profile_available %}
        <p class="success">✅鉴权成功，已加载真实个人档案</p>
    {% else %}
        <p class="warn">⚠️Cookie失效/未配置，仅展示全局物品库</p>
    {% endif %}
</div>

<div class="grid-3">
    <div class="card"><canvas id="chartTotal"></canvas></div>
    <div class="card"><canvas id="chartOwned"></canvas></div>
    <div class="card"><canvas id="chartMastered"></canvas></div>
</div>

<div class="card">
    <h2>📊分来源明细（已精通 / 持有 / 总数）</h2>
    {% for k,v in data.source_stat.items() %}
    <div class="stat-line">
        <span>{{k}}</span>
        <span>{{v.mastered}}精通 / {{v.owned}}持有 / {{v.total}}全部</span>
    </div>
    {% endfor %}
</div>

<input id="search" placeholder="搜索物品名称过滤..." oninput="render()">
<table>
<thead>
    <tr>
        <th>物品名称</th>
        <th>来源</th>
        <th>精通经验</th>
        <th>已拥有</th>
        <th>已满级精通</th>
    </tr>
</thead>
<tbody id="tableBody"></tbody>
</table>

<script>
const raw = {{data | tojson}};
const items = raw.item_list;
const stat = raw.source_stat;

// 三张环形图
new Chart(document.getElementById('chartTotal'),{
    type:'doughnut',
    data:{labels:Object.keys(stat),data:Object.values(stat).map(x=>x.total)},
    options:{plugins:{title:{display:true,text:"全物品分布"}}}
});
new Chart(document.getElementById('chartOwned'),{
    type:'doughnut',
    data:{labels:Object.keys(stat),data:Object.values(stat).map(x=>x.owned)},
    options:{plugins:{title:{display:true,text:"你已拥有"}}}
});
new Chart(document.getElementById('chartMastered'),{
    type:'doughnut',
    data:{labels:Object.keys(stat),data:Object.values(stat).map(x=>x.mastered)},
    options:{plugins:{title:{display:true,text:"你已精通"}}}
});

function render(){
    const kw = document.getElementById("search").value.toLowerCase();
    const tbody = document.getElementById("tableBody");
    tbody.innerHTML = "";
    items.filter(i=>i.name.toLowerCase().includes(kw)).forEach(it=>{
        const tr = document.createElement("tr");
        tr.innerHTML = `
        <td>${it.name}</td>
        <td><span class="${
            it.source==='Prime'?'tag-prime':
            it.source==='Kuva'?'tag-kuva':
            it.source==='Tenet'?'tag-tenet':'tag-normal'
        }">${it.source}</span></td>
        <td>${it.masteryXP}</td>
        <td class="${it.owned?'status-yes':'status-no'}">${it.owned?"是":"否"}</td>
        <td class="${it.mastered?'status-yes':'status-no'}">${it.mastered?"是":"否"}</td>
        `;
        tbody.appendChild(tr);
    })
}
render();
</script>
</body>
</html>
""")

render_html = html_template.render(data=export_data)
with open("index.html","w",encoding="utf-8") as f:
    f.write(render_html)

print("✅完整页面生成完毕，包含真实个人精通统计（编码容错修复）")
