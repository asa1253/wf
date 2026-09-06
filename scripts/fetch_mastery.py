import requests
import json
from jinja2 import Template
from datetime import datetime
import os

USER_ID = "6509c147148f3c362c18bcd3"
PLATFORM = "pc"

# 段位经验门槛表
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

# 创建data文件夹
os.makedirs("data", exist_ok=True)

# 1. 获取warframestat物品列表（这个接口公开可用）
try:
    item_api = f"https://api.warframestat.us/{PLATFORM}/items"
    resp_items = requests.get(item_api, timeout=15)
    item_list = resp_items.json()
except Exception as e:
    print(f"物品接口请求失败: {e}")
    item_list = []

# 2. 获取玩家档案（DE接口匿名访问会失败，增加容错）
profile_data = {}
try:
    profile_api = f"https://api.warframe.com/cdn/getProfileViewingData.php?playerId={USER_ID}"
    resp_profile = requests.get(profile_api, timeout=15)
    # 判断返回是否为JSON
    if resp_profile.headers.get("content-type","").startswith("application/json"):
        profile_data = resp_profile.json()
    else:
        print("⚠️ DE个人档案接口无权限，返回非JSON内容，跳过玩家数据")
except Exception as e:
    print(f"⚠️ 玩家档案请求异常：{e}")

# 保存原始文件（即使是空的）
with open("data/raw_profile.json","w",encoding="utf-8") as f:
    json.dump(profile_data,f,ensure_ascii=False,indent=2)
with open("data/raw_items.json","w",encoding="utf-8") as f:
    json.dump(item_list,f,ensure_ascii=False,indent=2)

# 来源统计容器
source_stat = {
    "Prime": {"total":0,"owned":0,"mastered":0},
    "Kuva": {"total":0,"owned":0,"mastered":0},
    "Tenet": {"total":0,"owned":0,"mastered":0},
    "基础版/其他": {"total":0,"owned":0,"mastered":0},
}

parsed_items = []
for it in item_list:
    item_name = it.get("name","未知")
    source = get_item_source(item_name)
    source_stat[source]["total"] += 1

    item_info = {
        "name":item_name,
        "source":source,
        "masteryXP":it.get("masteryReq",0),
        "owned":False,
        "mastered":False
    }
    parsed_items.append(item_info)

export_data = {
    "user_id":USER_ID,
    "update_time":datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    "source_stat":source_stat,
    "item_list":parsed_items,
    "profile_available": bool(profile_data)
}
with open("data/mastery.json","w",encoding="utf-8") as f:
    json.dump(export_data,f,ensure_ascii=False,indent=2)

# HTML页面模板
html_template = Template("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Warframe精通进度追踪｜来源统计</title>
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
.warning{color:#ff6666}
</style>
</head>
<body>
<h1>⚔️ Warframe 精通进度追踪</h1>
<div class="card">
<p>账号ID：{{data.user_id}}</p>
<p>更新时间：{{data.update_time}}</p>
{% if not data.profile_available %}
<p class="warning">⚠️ 无法自动读取个人档案（DE接口需要登录Cookie），当前仅展示全游戏物品库统计</p>
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
with open("index.html","w",encoding="utf-8") as page:
    page.write(render_html)

print("✅ 页面生成完成 index.html（已增加异常容错）")
