import time
import os
from PIL import ImageGrab

screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '截图')
os.makedirs(screenshot_dir, exist_ok=True)

print("=" * 50)
print("截图工具")
print("=" * 50)
print()
print("请确保程序窗口已打开并可见")
print()
print("5秒后截取第一张截图（主界面）...")
time.sleep(5)

screenshot1 = ImageGrab.grab()
screenshot1.save(os.path.join(screenshot_dir, '01_主界面.png'))
print("✓ 已保存: 01_主界面.png")

print()
print("请在程序中点击一个机构查看持仓详情")
print("10秒后截取第二张截图（持仓详情）...")
time.sleep(10)

screenshot2 = ImageGrab.grab()
screenshot2.save(os.path.join(screenshot_dir, '02_持仓详情.png'))
print("✓ 已保存: 02_持仓详情.png")

print()
print("请在程序中点击导出按钮")
print("10秒后截取第三张截图（导出功能）...")
time.sleep(10)

screenshot3 = ImageGrab.grab()
screenshot3.save(os.path.join(screenshot_dir, '03_导出功能.png'))
print("✓ 已保存: 03_导出功能.png")

print()
print("=" * 50)
print("所有截图已完成！")
print(f"保存位置: {screenshot_dir}")
print("=" * 50)
