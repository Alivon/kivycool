import socket  # 导入socket模块，用于网络通信
import threading  # 导入threading模块，用于多线程
import time  # 导入time模块，用于时间相关操作
import uuid  # 导入uuid模块，用于生成唯一标识符
# 导入zeroconf模块，用于服务注册和发现
from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser, ServiceStateChange, NonUniqueNameException
import zmq  # 导入zmq模块，用于消息队列通信
from kivy.app import App  # 导入Kivy的App类，用于创建应用程序
from kivy.clock import Clock  # 导入Kivy的Clock类，用于定时任务
from kivy.core.clipboard import Clipboard  # 导入Kivy的Clipboard类，用于剪贴板操作
from kivy.uix.label import Label  # 导入Kivy的Label类，用于显示文本
from kivy.uix.boxlayout import BoxLayout  # 导入Kivy的BoxLayout类，用于布局
from kivy.core.text import LabelBase  # 导入Kivy的LabelBase类，用于注册字体

PEER_PORT = 12345  # 定义一个常量，表示服务的端口号

# 全局变量存储自己的服务信息和本机IP地址
own_service_info = None  # 初始化自己的服务信息为None
client_name = socket.gethostname()  # 获取本机主机名
local_ip = socket.gethostbyname(client_name)  # 获取本机IP地址

# 维护已发现终端的列表
peers = set()  # 初始化已发现终端的列表为一个空集合

# 初始化一个列表来存储剪贴板历史记录
clipboard_history = []  # 初始化剪贴板历史记录列表为空


class ClipboardApp(App):  # 定义ClipboardApp类，继承自App类
    def build(self):  # 定义build方法，构建应用程序的界面
        return ClipboardLayout()  # 返回一个ClipboardLayout实例

    def on_start(self):  # 定义on_start方法，在应用程序启动时调用
        # 每0.5秒调用一次clipboard_listener方法
        Clock.schedule_interval(self.clipboard_listener, 0.5)

    def clipboard_listener(self, dt):  # 定义clipboard_listener方法，监听剪贴板内容变化
        recent_value = Clipboard.paste()  # 获取当前剪贴板内容
        # 如果剪贴板内容没有变化，则不做处理
        if clipboard_history and recent_value == clipboard_history[-1][0]:
            return

        clipboard_history.append((recent_value, client_name))  # 将剪贴板内容添加到历史记录中
        print(f"剪贴板更新: {recent_value} (复制自 {client_name})")  # 打印更新的剪贴板内容


class ClipboardLayout(BoxLayout):  # 定义ClipboardLayout类，继承自BoxLayout
    def show_clipboard_history(self):  # 定义show_clipboard_history方法，显示剪贴板历史记录
        history_text = "剪贴板历史记录：\n"  # 初始化历史记录文本
        for i, (content, comp_id) in enumerate(clipboard_history, 1):  # 遍历剪贴板历史记录
            # 添加每条记录到历史记录文本
            history_text += f"{i}. {content} (from {comp_id})\n"
        self.ids.history_label.text = history_text  # 设置历史记录标签的文本


def register_service():  # 定义register_service函数，注册服务到Zeroconf网络中
    global own_service_info  # 使用全局变量来存储服务信息
    zeroconf = Zeroconf()  # 创建一个Zeroconf对象，用于服务注册和发现
    ip = socket.inet_aton(local_ip)  # 获取本机IP地址，并转换为二进制格式
    unique_id = str(uuid.uuid4())  # 生成一个随机的UUID作为服务的唯一ID，确保服务名称唯一
    # 使用随机数生成唯一的服务名称
    service_name = f"{client_name} {unique_id}._http._tcp.local."
    own_service_info = ServiceInfo(
        "_http._tcp.local.",  # 服务类型，HTTP协议的TCP服务
        service_name,  # 服务名称
        addresses=[ip],  # 服务的IP地址
        port=PEER_PORT,  # 服务的端口号
        properties={},  # 服务的其他属性，这里为空
        server="my-service.local.",  # 服务的主机名
    )
    try:
        zeroconf.register_service(own_service_info)  # 注册服务
        print(f"广播服务注册成功: {own_service_info}")  # 输出服务注册的信息
    except NonUniqueNameException:  # 捕捉服务名称不唯一的异常
        print(f"{client_name} {service_name} 已被使用，尝试另一个名称。")  # 输出错误信息
        zeroconf.close()  # 关闭Zeroconf对象
        register_service()  # 重新尝试注册服务


# 定义on_service_state_change函数，处理服务状态变化的回调函数
def on_service_state_change(zeroconf, service_type, name, state_change):
    if state_change is ServiceStateChange.Added:  # 检查服务是否已添加
        info = zeroconf.get_service_info(service_type, name)  # 获取服务信息
        if info:  # 如果服务信息存在
            address = socket.inet_ntoa(info.addresses[0])  # 将二进制IP地址转换为字符串
            if address != local_ip:  # 如果是其他服务
                print(f"发现服务: {name} 地址: {address}:{info.port}")  # 输出发现的服务信息
                peers.add(address)  # 添加到已发现终端的列表
                threading.Thread(target=client, args=(
                    name, address), daemon=True).start()  # 启动一个线程与发现的对等设备通信


def discover_services():  # 定义discover_services函数，发现网络中的服务
    zeroconf = Zeroconf()  # 创建一个Zeroconf对象
    ServiceBrowser(zeroconf, "_http._tcp.local.", handlers=[
                   on_service_state_change])  # 创建一个ServiceBrowser对象，监视服务变化


def server():  # 定义server函数，启动一个ZeroMQ服务器，处理客户端请求
    context = zmq.Context()  # 创建一个ZeroMQ上下文
    socket = context.socket(zmq.PUB)  # 创建一个PUB（发布）套接字
    socket.bind(f"tcp://*:{PEER_PORT}")  # 绑定到指定端口
    history_state = 1  # 记录剪贴板历史记录的状态，初始值为1，表示从第2条记录开始
    print(f"广播服务已开始{client_name} {local_ip} 每隔5秒发布消息:")
    while True:
        if len(clipboard_history) > history_state:  # 如果有剪贴板历史记录
            history_state += 1  # 记录状态加1
            socket.send_string(
                # 发送剪贴板历史记录
                f"{clipboard_history[-1][0]} {clipboard_history[-1][1]}")


def client(peer_name, peer_address):  # 定义client函数，订阅指定的对等设备
    context = zmq.Context()  # 创建一个ZeroMQ上下文
    socket = context.socket(zmq.SUB)  # 创建一个SUB（订阅）套接字
    socket.connect(f"tcp://{peer_address}:{PEER_PORT}")  # 连接到指定的对等设备地址
    socket.setsockopt_string(zmq.SUBSCRIBE, "")  # 订阅所有消息
    while True:
        message = socket.recv_string()  # 接收消息
        sender_ip = peer_address
        context = message.rsplit(' ', 1)[0]
        if sender_ip != local_ip:  # 如果发送者不是自己，则输出消息
            print(f"从 {peer_name} {peer_address} 接收到消息: {context}")  # 输出接收到的消息
            Clipboard.copy(context)  # 将消息复制到剪贴板


if __name__ == '__main__':
    LabelBase.register(
        name="NotoSans", fn_regular="fonts/NotoSansCJKsc-VF.otf")  # 注册字体
    # 启动服务注册、发现和服务器线程
    threading.Thread(target=register_service, daemon=True).start()
    threading.Thread(target=discover_services, daemon=True).start()
    threading.Thread(target=server, daemon=True).start()
    ClipboardApp().run()  # 运行Kivy应用程序
