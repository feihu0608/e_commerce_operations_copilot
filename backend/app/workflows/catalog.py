"""Workflow-specific prompt contracts and clearly labelled mock fixtures."""

from typing import Any


MOCK_OUTPUTS: dict[str, dict[str, Any]] = {
    "diagnosis": {
        "target_audience": "22–38 岁重视影像、续航与质感的城市用户，主要用于旅行、短视频和日常办公。",
        "price_analysis": "主销价位位于 4000–5000 元中高端区间，相比高价竞品有价格优势，需突出影像、续航与服务证据。",
        "selling_points": ["一英寸主摄与夜景算法", "5500mAh 电池与轻薄机身", "卫星通信与全场景信号增强"],
        "conversion_barriers": ["新品牌信任度不足", "与同价位旗舰参数差异不直观", "首发权益表达分散"],
        "actions": ["增加夜景样张对比", "用全天使用场景表达续航", "突出 30 天无忧换机服务"],
    },
    "creative": {
        "image_directions": [
            {"title": "夜色影像旗舰", "layout": "深蓝夜景与镜头模组特写", "copy": "把夜色，拍成主角", "selling_point": "一英寸主摄"},
            {"title": "一日续航挑战", "layout": "从清晨通勤到夜间拍摄的时间轴", "copy": "从早到晚，电量仍在线", "selling_point": "5500mAh 电池"},
            {"title": "旅行安全搭档", "layout": "雪山与城市双场景分屏", "copy": "远行，也始终在线", "selling_point": "卫星通信"},
        ],
        "video_scripts": [
            {"title": "3 秒夜景反转", "hook": "同一个夜晚，为什么他拍得更亮？", "shots": ["暗光街景对比", "镜头模组特写", "成片快速展示"], "voiceover": "让夜色保留真实层次。", "cta": "查看首发权益"},
            {"title": "全天续航记录", "hook": "早上 8 点满电出门，晚上还剩多少？", "shots": ["通勤导航", "午间游戏", "夜间录像"], "voiceover": "一台手机，撑住完整的一天。", "cta": "立即了解新品"},
            {"title": "旅行信号测试", "hook": "没有地面信号，消息还能发出去吗？", "shots": ["户外弱网", "卫星连接", "平安消息送达"], "voiceover": "远行不失联，关键时刻多一份安心。", "cta": "探索更多能力"},
        ],
    },
    "strategy": {
        "audience": "22–38 岁关注影像、续航和品质生活的数码兴趣人群",
        "channel": "信息流",
        "budget": 900,
        "period": "7 天",
        "creative_angle": "夜景影像、全天续航、旅行通信三组素材进行小预算 A/B 测试",
        "target_ctr": 3.2,
        "stop_roas": 1.5,
        "rationale": ["以已确认卖点拆分差异素材", "小预算先验证点击吸引力", "通过 ROAS 阈值控制演示风险"],
    },
    "review": {
        "executive_summary": "本轮曝光和点击表现可用于判断素材吸引力，但因缺少严格对照实验，只能形成观察结论，不能宣称因果。",
        "goal_vs_actual": {"comparison": "将批准方案目标与最新经营指标逐项比较", "conclusion": "保留达到目标的素材方向，未达项进入下一轮验证"},
        "observations": ["CTR 反映首屏素材的点击吸引力", "转化率需要结合详情页和价格证据判断"],
        "possible_causes": ["卖点表达与目标人群匹配程度可能影响点击", "服务承诺与真实样张可能影响支付转化"],
        "next_actions": ["补充真实样张和竞品对比", "强化无忧换机服务表达", "下一轮测试续航场景短视频"],
        "evidence_limitations": ["当前数据为演示经营数据且没有随机对照组"],
    },
}


WORKFLOW_REQUIREMENTS = {
    "diagnosis": "输出 target_audience、price_analysis、selling_points、conversion_barriers、actions。",
    "creative": "输出至少 3 个 image_directions 和至少 3 个 video_scripts。",
    "strategy": "输出 audience、channel、budget、period、creative_angle、target_ctr、stop_roas、rationale；不得生成外部广告执行指令。",
    "review": "输出 executive_summary、goal_vs_actual、observations、possible_causes、next_actions、evidence_limitations；区分观察、可能原因和验证建议。",
}
