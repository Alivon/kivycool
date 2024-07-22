import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.core.clipboard import Clipboard


class ClipboardApp(App):
    def build(self):
        self.title = "剪贴板 App"

        # 获取字体文件的绝对路径
        self.font_path = os.path.join(os.path.dirname(
            __file__), 'fonts', 'NotoSansCJKsc-VF.otf')

        # 返回布局
        return ClipboardLayout()


class ClipboardLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10

    def copy_to_clipboard(self):
        text = self.ids.text_input.text
        Clipboard.copy(text)
        self.ids.clipboard_label.text = f"已复制: {text}"

    def paste_from_clipboard(self):
        text = Clipboard.paste()
        self.ids.text_output.text = text
        self.ids.clipboard_label.text = f"已粘贴: {text}"


if __name__ == '__main__':
    ClipboardApp().run()
