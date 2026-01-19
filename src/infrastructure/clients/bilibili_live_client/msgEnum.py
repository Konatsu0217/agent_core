
# see https://open-live.bilibili.com/document/f9ce25be-312e-1f4a-85fd-fef21f1637f8#h2-u5173u4E8Eu9000u51FAu623Fu95F4
# {
#   "data": {
#     "emoji_img_url": "",
#     "fans_medal_level": 0,
#     "fans_medal_name": "",
#     "fans_medal_wearing_status": false,
#     "guard_level": 0,
#     "msg": "2",
#     "timestamp": 1766496334,
#     "uid": 0,
#     "uname": "来夏",
#     "uface": "https://i0.hdslb.com/bfs/face/b1339d1f06f72bbf9af18065354dc80e1fc0a596.jpg",
#     "dm_type": 0,
#     "union_id": "",
#     "open_id": "8cc0b8e1af5a4143bcef07abd6875efe",
#     "is_admin": 0,
#     "glory_level": 7,
#     "reply_union_id": "",
#     "reply_open_id": "",
#     "reply_uname": "",
#     "msg_id": "5329143d-e5e9-4880-88a6-51831799cf56",
#     "room_id": 1836250
#   },
#   "cmd": "LIVE_OPEN_PLATFORM_DM"
# }

# enum 弹幕类型
DANMU_TYPE = {
    "LIVE_OPEN_PLATFORM_DM": "普通弹幕",
    "LIVE_OPEN_PLATFORM_SUPER_CHAT": "醒目留言",
    "LIVE_OPEN_PLATFORM_SEND_GIFT": "礼物",
    "LIVE_OPEN_PLATFORM_GUARD": "购买舰长"
}

# if danmu_type == "danmaku":
#     content = f'{uname}发送弹幕：{message}'
# elif danmu_type == "super_chat":
#     content = f'{uname}发送SuperChat：{message}'
# elif danmu_type == "gift":
#     content = f'{uname}发送礼物：{message}'
# elif danmu_type == "buy_guard":
#     content = f'{uname}购买舰长：{message}'
# else:
#     content = f'{uname}发送{danmu_type}：{message}'

# add_danmaku_inner(danmaku_data, danmaku_type)
# danmaku_data: {
#         'content': data.msg,
#         'danmu_type': DANMU_TYPE,
#         'timestamp': time.time()
#     }
