from loguru import logger

from WechatAPI import WechatAPIClient
from utils.decorators import *
from utils.plugin_base import PluginBase
from bs4 import BeautifulSoup
import markdown
import tomllib
import json
import asyncio
import websockets
import asyncio
import ast
import base64


class MessageReceive:
    def __init__(self, message: dict , admin: bool , user: dict):
        self.bot_id = "XYBotV2"
        self.sender = Dictionary(user)
        self.bot_self_id = message["ToWxid"]
        self.msg_id  = str(message["MsgId"])
        self.user_type = "direct"
        if message["IsGroup"]:
            self.user_type = "group"
        self.group_id = message["FromWxid"]
        self.user_id = message["SenderWxid"]
        self.user_pm = 6
        if admin:
            self.user_pm = 1
        self.content = []
        self.content.append(Message(str(message["Content"]).replace('早柚 ', '')))


    def to_dict(self):
        return {
            'bot_id': self.bot_id,
            'sender': self.sender,
            'bot_self_id': self.bot_self_id,
            'msg_id': self.msg_id,
            'user_type': self.user_type,
            'group_id': self.group_id,
            'user_id': self.user_id,
            'user_pm': self.user_pm,
            'content': self.content
        }

        
class Message:
    def __init__(self, message: str):
        self.type  = "text"
        self.data = message


    def to_dict(self):
        return {
            'type': self.type,
            'data': self.data
        }

class Dictionary:
    def __init__(self, user: dict):
        self.age  = 0
        self.area = user.get("Country", "未知")
        self.card = user["NickName"]["string"]
        self.level = ""
        self.nickname = user["NickName"]["string"]
        self.role = "owner"
        self.sex = "男" if user["Sex"] == 1 else ("女" if user["Sex"] == 2 else "未知")
        self.title = ""
        self.user_id = 0
        self.avater = user["SmallHeadImgUrl"]



    def to_dict(self):
        return {
            'age': self.age,
            'area': self.area,
            'card': self.card,
            'level': self.level,
            'nickname': self.nickname,
            'role': self.role,
            'user_id': self.user_id,
            'sex': self.sex,
            'title': self.title,
            'user_id': self.user_id,
            'avater': self.avater
        }
       

class GsCoreAdapter(PluginBase):
    description = "GsCoreAdapter"
    author = "xuangeer"
    version = "0.0.1"


    # 同步初始化
    def __init__(self):
        super().__init__()
        self.websocket = None
        self.on_message_callback = None
        self.gscore_url = None
        self.enable = False
        self.bot = None
        with open("main_config.toml", "rb") as f:
            config = tomllib.load(f)
        self.admins = config["XYBot"]["admins"]
        
                
    
    async def send_message(self, message):
        if not self.websocket is None:
            try:
                MessageReceive = bytes(message, 'utf-8')
                await self.websocket.send(MessageReceive)
            except websockets.exceptions.ConnectionClosed as e:
                print(f"连接断开 重新连接")
                print(e)

    def deep_serialize(self , obj):
        """递归处理所有不可序列化的对象"""
        if isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, dict):
            return {k: deep_serialize(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple, set)):
            return [deep_serialize(item) for item in obj]
        elif isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        elif hasattr(obj, '__dict__'):
            return deep_serialize(vars(obj))
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return str(obj)  # 最后兜底方案：转为字符串

    async def receive_message(self):
        if not self.websocket is None:
            while True:
                try:
                    message = await self.websocket.recv()
                    await self.message_handler(message)
                except websockets.exceptions.ConnectionClosed:
                    print(f"连接断开 重新连接")
                    print("Connection closed")
#                    await self.reconnect()
                    break
                await asyncio.sleep(0)  # 让事件循环有机会处理其他任务


                
    def parse_markdown(self , md_text):
        html = markdown.markdown(md_text)
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        images = []
        for img in soup.find_all('img'):
            img_src = img.get('src')
            if img_src:
                images.append(img_src)
        return text, images


    
    #处理连接
    async def message_handler(self , message):
        if not self.bot:
            print("没有启动客户端")
            return
        message_str = message.decode('utf-8')
        message_json = json.loads(message_str)
        if message_json["bot_id"] != "XYBotV2":
            return
        fromWxid = message_json["target_id"]
        
        content = []
        content = message_json["content"]
        for msg in content:
            if not msg["type"]:
                print("消息为空")
                return
            if msg["type"] == "node":
                data = msg["data"]
                for node in data:
                    if node["type"] == "text":
                        await self.bot.send_text_message(fromWxid, node["data"])
                    if node["type"] == "image":
                        if node["type"] == "image" or node["type"] == "b64" or node["type"] == "url":
                            jpg = str(node["data"]).replace('base64://', 'data:image/jpg;base64,')
                            print(jpg)
                            try:
                                await self.bot.send_image_message(fromWxid,jpg)
                            except Exception as e:
                                print(e)
            
            if msg["type"] == "text":
                await self.bot.send_text_message(fromWxid, msg["data"])
            if msg["type"] == "markdown":
                text, images = self.parse_markdown(fromWxid, msg["data"])
                await self.bot.send_text_message(fromWxid , text)
                for img in images:
                    await self.bot.send_image_message(fromWxid,img)
            if msg["type"] == "image":
                jpg = str(msg["data"]).replace('base64://', 'data:image/jpg;base64,')
                await self.bot.send_image_message(fromWxid,jpg)
                    
        
        

    async def reconnect(self):
        # 重连函数
        print("正在尝试重连...")
        await self.close_connection()  # 先关闭现有连接
        await self.connect()  # 重新连接

    async def close_connection(self):
        # 关闭现有的 WebSocket 连接
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            print("连接已关闭")
        
    # 异步初始化
    async def async_init(self):
        with open("plugins/GsCoreAdapter/config.toml", "rb") as f:
            config = tomllib.load(f)
        plugin_config = config["GsCoreAdapter"]
        self.enable = plugin_config["enable"]
        self.gscore_url = plugin_config["gscore_url"]
        if self.gscore_url == "":
            print("gscore_url为空 拒绝加载")
            return False
        await self.connect()
        try:
            self.groups = []
            await self.queryall()
        except Exception as e:
            print(e)


        
    @on_text_message(priority=21)
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if message["SenderWxid"] not in self.admins:
            if "开启早柚" in message["Content"] or "关闭早柚" in message["Content"]:
                await bot.send_text_message(message["FromWxid"], "无管理员权限")
        if message["Content"] == "重连早柚":
            await self.reconnect()
        if message["Content"] == "开启早柚":
            if self.groups is None:
                self.groups = []
            if message["FromWxid"] in self.groups:
                await bot.send_text_message(message["FromWxid"], "早柚已开启")
            self.groups.append(message["FromWxid"])
            await bot.send_text_message(message["FromWxid"], "开启早柚成功")
        if message["Content"] == "关闭早柚":
            if self.groups and message["FromWxid"] in self.groups:
                self.groups.remove(message["FromWxid"])
            await bot.send_text_message(message["FromWxid"], "关闭早柚成功")
        await self.groupsSetall()
        

    async def groupsSetall(self):
        try:
            with open('plugins/GsCoreAdapter/db.json', 'w') as f:
                f.write(str(self.groups).replace("'", '"'))
        except Exception as e:
            print(f"写入文件时发生错误: {e}")
        
    async def connect(self):
        # 连接早柚
        try:
            self.websocket = await websockets.connect(self.gscore_url,max_size=10**7)
            print("连接成功")
            asyncio.create_task(self.receive_message())
        except Exception as e:
            print(e)
            print("连接失败 请检查路径是否正确")
            return False

    async def queryall(self):
       with open('plugins/GsCoreAdapter/db.json', 'r') as f:
            content = f.read().strip()
            data_str = ""
            if content:
                data_str = content
            if not data_str.strip():
                self.groups = []
            else:
                try:
                    self.groups = ast.literal_eval(data_str)
                except Exception as e:
                    self.groups = []

            
    @on_text_message(priority=20)
    async def handle_text1(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return
        if self.bot is None:
            self.bot = bot
        command = str(message["Content"]).strip().split(" ")
        if len(command) == 1 or command[0] != "早柚":  # 只是指令，但没请求内容
            return
        if  message["IsGroup"] and not message["FromWxid"] in self.groups:
            return
             
        try:
            user = await bot.get_contact(message["SenderWxid"])
            if not user:
                return
        except Exception as e:
            print(e)
            return
        try:
            admin = message["SenderWxid"] in self.admins
#            message = MessageReceive(message,admin, user ).__repr__()
            message_obj = MessageReceive(message, admin, user)
            json_str = json.dumps(message_obj.__dict__, default=lambda o: o.__dict__, indent=4)
        except Exception as e:
            print(e)
        try:
            await self.send_message(json_str)
        except Exception as e:
            print(e)
        
        