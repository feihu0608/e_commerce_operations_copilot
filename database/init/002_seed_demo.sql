INSERT INTO products (id, name, category, price, status, image_url, summary, inventory, warning_threshold) VALUES
    (1, '曜石 X1 影像旗舰手机', '数码手机', 4699.00, 'on_sale', '/images/demo-phone.png', '一英寸主摄、5500mAh 电池与卫星通信，面向旅行影像与移动办公人群。', 186, 30),
    (2, '曜石 Buds Air 降噪耳机', '数码配件', 499.00, 'on_sale', '/images/demo-phone.png', '轻量真无线降噪耳机，支持空间音频。', 92, 25),
    (3, '曜石 65W 氮化镓充电器', '数码配件', 169.00, 'on_sale', '/images/demo-phone.png', '双口快充，小巧便携。', 18, 20)
ON CONFLICT (id) DO NOTHING;

INSERT INTO competitors (id, product_id, name, price, highlights) VALUES
    (1, 1, '极光 Pro 影像手机', 5299.00, '{"camera":"高像素潜望长焦","battery":"5100mAh","position":"影像旗舰"}'),
    (2, 1, '凌云 GT 性能手机', 3999.00, '{"chip":"旗舰性能芯片","charging":"100W 快充","position":"性能旗舰"}'),
    (3, 1, '远景 Ultra 商务手机', 5999.00, '{"signal":"卫星消息","service":"高端服务","position":"商务旗舰"}')
ON CONFLICT (id) DO NOTHING;

INSERT INTO content_documents (id, product_id, content_type, status, revision, payload) VALUES
    (1, 1, 'diagnosis', 'confirmed', 2,
     '{"target_audience":"22–38 岁重视影像、续航与质感的城市用户，主要用于旅行、短视频和日常办公。","price_analysis":"位于 4000–5000 元中高端价格带，对高价影像旗舰具有价格优势。","selling_points":["一英寸主摄与夜景算法","5500mAh 电池与轻薄机身","卫星通信与信号增强"],"conversion_barriers":["新品牌信任度不足","参数差异不直观","首发权益表达分散"],"actions":["增加夜景样张对比","用全天使用场景展示续航","突出 30 天无忧换机服务"]}'),
    (2, 1, 'creative', 'draft', 1,
     '{"image_directions":[{"title":"夜色影像旗舰","layout":"深蓝夜景与镜头模组特写","copy":"把夜色，拍成主角","selling_point":"一英寸主摄"},{"title":"一日续航挑战","layout":"清晨通勤至夜间拍摄时间轴","copy":"从早到晚，电量仍在线","selling_point":"5500mAh 电池"},{"title":"旅行安全搭档","layout":"雪山与城市双场景分屏","copy":"远行，也始终在线","selling_point":"卫星通信"}],"video_scripts":[{"title":"3 秒夜景反转","hook":"同一个夜晚，为什么他拍得更亮？","shots":["暗光街景对比","镜头模组特写","成片展示"],"voiceover":"曜石 X1，让夜色保留真实层次。","cta":"首发预约享无忧换机"},{"title":"全天续航记录","hook":"早上 8 点满电出门，晚上还剩多少？","shots":["通勤导航","午间游戏","夜间录像"],"voiceover":"一台手机，撑住完整的一天。","cta":"立即查看首发权益"},{"title":"旅行信号测试","hook":"没有地面信号，消息还能发出去吗？","shots":["户外弱网","卫星连接","平安消息送达"],"voiceover":"远行不失联，关键时刻多一份安心。","cta":"探索曜石 X1"}]}')
ON CONFLICT (id) DO NOTHING;

INSERT INTO experiments (id, product_id, title, status, strategy) VALUES
    (1, 1, '影像人群首发冷启动实验', 'submitted',
     '{"audience":"22–38 岁旅行摄影、短视频及数码兴趣人群","bid":"小预算分层出价，首日控制成本","ab_test":"夜色影像旗舰主图 vs 一日续航挑战主图","period":"7 天","targets":{"ctr":3.2,"conversion_rate":2.5}}')
ON CONFLICT (id) DO NOTHING;

INSERT INTO metric_records (id, product_id, period, impressions, clicks, paid_orders, gmv, ad_spend) VALUES
    (1, 1, '首发测试第 1–7 天', 120000, 4560, 96, 451104.00, 68500.00)
ON CONFLICT (id) DO NOTHING;

INSERT INTO generation_tasks (id, product_id, kind, title, status, progress, provider_mode, error_message, result_url) VALUES
    (1, 1, 'image', '夜色影像旗舰主图', 'succeeded', 100, 'mock', NULL, '/images/demo-phone.png'),
    (2, 1, 'video', '15 秒夜景短视频', 'failed', 42, 'mock', '演示任务：等待配置硅基流动 Key 后重试', NULL)
ON CONFLICT (id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('products','id'), GREATEST((SELECT MAX(id) FROM products), 1));
SELECT setval(pg_get_serial_sequence('competitors','id'), GREATEST((SELECT MAX(id) FROM competitors), 1));
SELECT setval(pg_get_serial_sequence('content_documents','id'), GREATEST((SELECT MAX(id) FROM content_documents), 1));
SELECT setval(pg_get_serial_sequence('experiments','id'), GREATEST((SELECT MAX(id) FROM experiments), 1));
SELECT setval(pg_get_serial_sequence('metric_records','id'), GREATEST((SELECT MAX(id) FROM metric_records), 1));
SELECT setval(pg_get_serial_sequence('generation_tasks','id'), GREATEST((SELECT MAX(id) FROM generation_tasks), 1));
