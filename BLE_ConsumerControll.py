# Implements a BLE HID Consumer Controll

from micropython import const
import struct
import bluetooth


def ble_irq(event, data):
    global conn_handle
    if event == 1:
        print("connect")
        conn_handle = data[0]
    else:
        print("event:", event, data)


ble = bluetooth.BLE()
ble.active(1)
ble.irq(ble_irq)

UUID = bluetooth.UUID

F_READ = bluetooth.FLAG_READ
F_WRITE = bluetooth.FLAG_WRITE
F_READ_WRITE = bluetooth.FLAG_READ | bluetooth.FLAG_WRITE
F_READ_NOTIFY = bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY

ATT_F_READ = 0x01
ATT_F_WRITE = 0x02

# 建立伺服器
hid_service = (
    UUID(0x1812),  # Human Interface Device            人機介面設備
    (
        (UUID(0x2A4A), F_READ),  # HID information     HID信息
        (UUID(0x2A4B), F_READ),  # HID report map      HID報告圖
        (UUID(0x2A4C), F_WRITE),  # HID control point  HID控制點
        (UUID(0x2A4D), F_READ_NOTIFY, ((UUID(0x2908), ATT_F_READ),)),  # HID report / reference
#         (UUID(0x2A4D), F_READ_WRITE, ((UUID(0x2908), ATT_F_READ),)),  # HID report / reference
        (UUID(0x2A4E), F_READ_WRITE),  # HID protocol mode
    ),
)

# fmt: off
HID_REPORT_MAP = bytes([
    0x05, 0x0C,     # Usage Page (Generic Desktop)
    0x09, 0x01,     # Usage (Keyboard)
    0xA1, 0x01,     # Collection (Application)
    0x85, 0x01,     #     Report ID (1)
    0x75, 0x10,     #     Report Size (1)
    0x95, 0x01,     #     Report Count (8)
    0x15, 0x01,     #     Logical Minimum (0)
    0x26,
    0x8C, 0x02,     #     Logical Maximum (1)
    0x19, 0x01,     #     Usage Minimum (224)
    0x2A,
    0x8C, 0x02,     #     Usage Maximum (231)
    0x81, 0x00,     #     Input (Data, Variable, Absolute); Modifier byte
    0xC0,           # End Collection
])
# fmt: on

# register services  註冊服務
ble.config(gap_name="MP-Vol")
handles = ble.gatts_register_services((hid_service,))
print(handles)
h_info, h_hid, _, h_rep, h_d1, h_proto = handles[0]

# set initial data
ble.gatts_write(h_info, b"\x01\x01\x00\x02")  # HID info: ver=1.1, country=0, flags=normal
ble.gatts_write(h_hid, HID_REPORT_MAP)  # HID report map
ble.gatts_write(h_d1, struct.pack("<BB", 1, 1))  # report: id=1, type=input
# ble.gatts_write(h_d2, struct.pack("<BB", 1, 2))  # report: id=1, type=output
ble.gatts_write(h_proto, b"\x01")  # protocol mode: report

# advertise 廣告
adv = (
    b"\x02\x01\x06"
    b"\x03\x03\x12\x18"  # complete list of 16-bit service UUIDs: 0x1812
    b"\x03\x19\x80\x01"  # appearance: keyboard
    b"\x07\x09MP-Vol"  # complete local name(要與上面的gap_name一樣)
)
conn_handle = None
ble.gap_advertise(100_000, adv)

# once connected use the following to send reports


def send_char(char):
    if char == " ":
        mod = 0
        code = 0x2C
    elif ord("a") <= ord(char) <= ord("z"):
        mod = 0
        code = 0x04 + ord(char) - ord("a")
    elif ord("A") <= ord(char) <= ord("Z"):
        mod = 2
        code = 0x04 + ord(char) - ord("A")
    else:
        assert 0

    ble.gatts_notify(conn_handle, h_rep, struct.pack("8B", mod, 0, code, 0, 0, 0, 0, 0))
    ble.gatts_notify(conn_handle, h_rep, b"\x00\x00\x00\x00\x00\x00\x00\x00")


def send_str(st):
    for c in st:
        send_char(c)

# 可以查看以下對照表
# https://circuitpython.readthedocs.io/projects/hid/en/latest/_modules/adafruit_hid/keycode.html
# https://www.usb.org/sites/default/files/documents/hut1_12v2.pdf
def screen_shot():   # 0x28:ENTER    0x46:Print Scrn
    ble.gatts_notify(conn_handle, h_rep, b"\xE9\x00")
    ble.gatts_notify(conn_handle, h_rep, b"\x00\x00")



from machine import Pin
import time

sta = False   # 是否按下按鈕

button = Pin(0, Pin.IN, Pin.PULL_UP)
while True:
    bv = button.value()
    if bv == 1:
        sta = False
    if(bv == 0 and sta == False):
        screen_shot()
        print("傳送")
        sta = True
    time.sleep(0.01)