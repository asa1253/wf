import requests
import json
from jinja2 import Template
from datetime import datetime
import os

# 从环境变量读取密钥（不在代码硬编码）
USER_ID = os.getenv("WF_USER_ID","")
WF_COOKIE = os.getenv("WF_COOKIE","")
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

os.makedirs("data", exist_ok=True)

# 请求头配置：携带登录Cookie
headers = {}
if WF_COOKIE:
    headers["Cookie"] = WF_COOKIE
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 拉取公开物品列表
item_list = []
try:
    item_api = f"https://api.warframestat.us/{PLATFORM}/items"
    resp_items = requests.get(item_api, timeout=15)
    raw = resp_items.json()
    if isinstance(raw, dict):
        item_list = raw.get("items") or raw.get("data") or []
    elif isinstance(raw, list):
        item_list = raw
except Exception as e:
    print(f"⚠️ 物品接口请求失败: {e}")
    item_list = []

# 使用Cookie请求个人档案
profile_data = {}
if USER_ID and WF_COOKIE:
    try:
        profile_api = f"https://api.warframe.com/cdn/getProfileViewingData.php?playerId={USER_ID}"
        resp_profile = requests.get(profile_api, headers=headers, timeout=15)
        ctype = resp_profile.headers.get("content-type", "")
        if ctype.startswith("application/json"):
            profile_data = resp_profile.json()
            print("✅ 成功获取DE个人档案数据")
        else:
            print("⚠️ Cookie失效 / 权限不足，返回非JSON")
    except Exception as e:
        print(f"⚠️ 玩家档案请求异常：{e}")
else:
    print("ℹ️ 未配置WF_COOKIE或WF_USER_ID，跳过个人档案拉取")

with open("data/raw_profile.json", "w", encoding="utf-8") as f:
    json.dump(profile_data, f, ensure_ascii=False, indent=2)
with open("data/raw_items.json", "w", encoding="utf-8") as f:
    json.dump(item_list, f, ensure_ascii=False, indent=2)

source_stat = {
    "Prime": {"total": 0, "owned": 0, "mastered": 0},
    "Kuva": {"total": 0, "owned": 0, "mastered": 0},
    "Tenet": {"total": 0, "owned": 0, "mastered": 0},
    "基础版/其他": {"total": 0, "owned": 0, "mastered": 0},
}

parsed_items = []
for it in item_list:
    if not isinstance(it, dict):
        continue
    item_name = it.get("name", "未知")
    source = get_item_source(item_name)
    source_stat[source]["total"] += 1
    parsed_items.append({
        "name": item_name,
        "source": source,
        "masteryXP": it.get("masteryReq", 0),
        "owned": False,
        "mastered": False
    })

export_data = {
    "user_id": USER_ID if USER_ID else "未填写",
    "update_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    "source_stat": source_stat,
    "item_list": parsed_items,
    "profile_available": bool(profile_data)
}
with open("data/mastery.json", "w", encoding="utf-8") as f:
    json.dump(export_data, f, ensure_ascii=False, indent=2)

html_template = Template("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Warframe精通进度追踪｜Cookie鉴权版</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{box-sizing:border-box;font-family:system-ui,-apple-system}
body{max-width:1280px;margin:2rem auto;padding:0 1rem;background:#111;color:#eee}
h1{color:#f2c94c;text-align:center}
.grid-row{display:grid;grid-template-columns: 1fr 1fr;gap:16px;margin:20px 0}
.card{border:1px solid #444;padding:16px;border-radius:8px;background:#1e1e1e}
.stat-card{display:flex;justify-content:space-between;padding:4px 0}
table{width:100%;border-collapse:collapse;margin-top:1rem}
th,td{border:1px solid #333;padding:8px 12px;text-align:left}
input{width:100%;padding:8px;background:#222;border:1px solid #444;color:#fff;border-radius:4px;margin-bottom:12px}
.tag-prime{color:#ffd700}
.tag-kuva{color:#bb2222}
.tag-tenet{color:#6699ff}
.tag-normal{color:#aaaaaa}
.success{color:#4ade80}
.warning{color:#ff6666}
</style>
</head>
<body>
<h1>⚔️ Warframe 精通进度追踪（Cookie鉴权）</h1>
<div class="card">
<p>账号ID：{{data.user_id}}</p>
<p>更新时间：{{data.update_time}}</p>
{% if data.profile_available %}
<p class="success">✅ Cookie鉴权成功，读取个人档案</p>
{% else %}
<p class="warning">⚠️ Cookie无效或未配置，仅展示公开物品库</p>
{% endif %}
</div>

<div class="grid-row">
    <div class="card">
        <h2>📊 物品来源分布统计（全游戏）</h2>
        {% for key,val in data.source_stat.items() %}
        <div class="stat-card">
            <span>{{key}}</span>
            <span>{{val.total}} 件</span>
        </div>
        {% endfor %}
    </div>
    <div class="card">
        <canvas id="sourceChart"></canvas>
    </div>
</div>

<input id="searchInput" placeholder="搜索物品名称..." onkeyup="filterTable()">
<table id="itemTable">
<thead>
    <tr>
        <th>物品名称</th>
        <th>来源类型</th>
        <th>精通经验</th>
    </tr>
</thead>
<tbody>
{% for item in data.item_list %}
<tr>
    <td>{{item.name}}</td>
    <td>
    {% if item.source == "Prime" %}<span class="tag-prime">{{item.source}}</span>
    {% elif item.source == "Kuva" %}<span class="tag-kuva">{{item.source}}</span>
    {% elif item.source == "Tenet" %}<span class="tag-tenet">{{item.source}}</span>
    {% else %}<span class="tag-normal">{{item.source}}</span>
    {% endif %}
    </td>
    <td>{{item.masteryXP}}</td>
</tr>
{% endfor %}
</tbody>
</table>

<script>
const stat = {{data.source_stat | tojson}};
const ctx = document.getElementById('sourceChart').getContext('2d');
new Chart(ctx,{
    type:'doughnut',
    data:{
        labels:Object.keys(stat),
        data:Object.values(stat).map(s=>s.total),
        backgroundColor:["#ffd700","#bb2222","#6699ff","#777777"]
    },
    options:{plugins:{title:{display:true,text:"全游戏物品来源占比"}}}
});

function filterTable(){
    const kw = document.getElementById("searchInput").value.toLowerCase();
    document.querySelectorAll("#itemTable tbody tr").forEach(row=>{
        const name = row.children[0].innerText.toLowerCase();
        row.style.display = name.includes(kw)?"":"none";
    })
}
</script>
</body>
</html>
""")

render_html = html_template.render(data=export_data)
with open("index.html", "w", encoding="utf-8") as page:
    page.write(render_html)

print("✅ 页面生成完成")
