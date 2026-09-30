import network
import socket
from machine import Pin, PWM
import time

# ╔══════════════════════════════════════════════════════════╗
# ║  CONFIG — change these values to tune your rover         ║
# ╚══════════════════════════════════════════════════════════╝

# ── WiFi ──────────────────────────────────────────────────
SSID                = "YOUR_HOTSPOT_NAME"   # your phone hotspot name
PASSWORD            = "YOUR_HOTSPOT_PASS"   # your phone hotspot password
#
# NOTE: Pico W only supports 2.4GHz WiFi
# Do NOT use eduroam or university networks — use your phone hotspot

# ── Pin assignments ───────────────────────────────────────
AIN1_PIN  = 0      # left motor
AIN2_PIN  = 1
BIN1_PIN  = 2      # right motor
BIN2_PIN  = 3
STBY_PIN  = 4      # DRV8833 standby — MUST be pulled HIGH or motors won't move
SERVO_PIN = 15     # digger servo

# ── PWM frequencies ───────────────────────────────────────
MOTOR_FREQ = 1000  # Hz
SERVO_FREQ = 50    # Hz (20ms period, standard for servos)

# ── Motor speed tuning ────────────────────────────────────
PWM_MAX     = 65535  # hardware max — do not exceed
DRIVE_SPEED = 50000  # forward / back speed  (0 to 65535)
TURN_SPEED  = 50000  # left / right speed    (0 to 65535)

# ── Servo calibration ─────────────────────────────────────
SERVO_MIN_US    = 500    # pulse width at 0 degrees
SERVO_MAX_US    = 2400   # pulse width at 180 degrees
SERVO_PERIOD_US = 20000  # 50Hz = 20000 microsecond period
SERVO_MAX_ANGLE = 180

# ── Digger behaviour ──────────────────────────────────────
DIGGER_START = 90   # starting angle in degrees
DIGGER_STEP  = 10   # degrees moved per button press
DIGGER_MIN   = 0    # lower mechanical limit
DIGGER_MAX   = 180  # upper mechanical limit
#
# TIP: once your digger arm is built, adjust DIGGER_MIN and DIGGER_MAX
# to match your physical range so the servo doesn't over-rotate

# ── Web server ────────────────────────────────────────────
PORT      = 80
BACKLOG   = 5
RECV_SIZE = 1024

# ╔══════════════════════════════════════════════════════════╗
# ║  Hardware setup                                          ║
# ╚══════════════════════════════════════════════════════════╝

# Motor PWM pins
ain1 = PWM(Pin(AIN1_PIN)); ain1.freq(MOTOR_FREQ)
ain2 = PWM(Pin(AIN2_PIN)); ain2.freq(MOTOR_FREQ)
bin1 = PWM(Pin(BIN1_PIN)); bin1.freq(MOTOR_FREQ)
bin2 = PWM(Pin(BIN2_PIN)); bin2.freq(MOTOR_FREQ)

# Enable DRV8833 — without this the chip is in standby and nothing moves
stby = Pin(STBY_PIN, Pin.OUT)
stby.value(1)

# Servo
servo = PWM(Pin(SERVO_PIN))
servo.freq(SERVO_FREQ)

# Pre-compute servo duty cycle endpoints
SERVO_MIN_DUTY = int((SERVO_MIN_US / SERVO_PERIOD_US) * PWM_MAX)
SERVO_MAX_DUTY = int((SERVO_MAX_US / SERVO_PERIOD_US) * PWM_MAX)

# ╔══════════════════════════════════════════════════════════╗
# ║  Helper functions                                        ║
# ╚══════════════════════════════════════════════════════════╝

def set_servo(angle):
    """Move servo to a given angle (0 to SERVO_MAX_ANGLE)"""
    span = SERVO_MAX_DUTY - SERVO_MIN_DUTY
    servo.duty_u16(SERVO_MIN_DUTY + int((angle / SERVO_MAX_ANGLE) * span))

def motor(p1, p2, speed):
    """Drive a single motor. speed: negative=reverse, 0=stop, positive=forward"""
    if speed > 0:
        p1.duty_u16(speed)
        p2.duty_u16(0)
    elif speed < 0:
        p1.duty_u16(0)
        p2.duty_u16(-speed)
    else:
        p1.duty_u16(0)
        p2.duty_u16(0)

def drive(left, right):
    """Drive both motors. Values from -PWM_MAX to +PWM_MAX"""
    motor(ain1, ain2, left)
    motor(bin1, bin2, right)

def stop():
    drive(0, 0)

# ╔══════════════════════════════════════════════════════════╗
# ║  WiFi connection                                         ║
# ╚══════════════════════════════════════════════════════════╝

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

print("Connecting to WiFi", end="")
timeout = 20
while not wlan.isconnected() and timeout > 0:
    print(".", end="")
    time.sleep(0.5)
    timeout -= 1

if not wlan.isconnected():
    print("\nFailed to connect. Check SSID/password and make sure you are using a phone hotspot (2.4GHz).")
else:
    print("\nConnected! Open this address in your phone browser: http://" + wlan.ifconfig()[0])

# ╔══════════════════════════════════════════════════════════╗
# ║  Web page                                                ║
# ╚══════════════════════════════════════════════════════════╝

HTML = """<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rover Control</title>
  <style>
    body {
      background: #111;
      color: #eee;
      font-family: sans-serif;
      text-align: center;
      padding: 20px;
    }
    button {
      width: 90px;
      height: 90px;
      margin: 8px;
      font-size: 18px;
      font-weight: bold;
      background: #222;
      color: #eee;
      border: 2px solid #555;
      border-radius: 12px;
      touch-action: manipulation;
    }
    button:active { background: #444; }
    .row { margin: 4px; }
    hr { border-color: #333; margin: 24px 0; }
  </style>
</head>
<body>
  <h2>Rover Control</h2>

  <div class="row"><button onclick="cmd('fwd')">FWD</button></div>
  <div class="row">
    <button onclick="cmd('lft')">LEFT</button>
    <button onclick="cmd('stp')">STOP</button>
    <button onclick="cmd('rgt')">RIGHT</button>
  </div>
  <div class="row"><button onclick="cmd('bck')">BACK</button></div>

  <hr>

  <h2>Digger</h2>
  <button onclick="cmd('dig_up')">UP</button>
  <button onclick="cmd('dig_dn')">DOWN</button>

  <script>
    function cmd(action) {
      fetch('/cmd?a=' + action).catch(() => {});
    }
  </script>
</body>
</html>"""

# ╔══════════════════════════════════════════════════════════╗
# ║  Web server loop                                         ║
# ╚══════════════════════════════════════════════════════════╝

digger_angle = DIGGER_START
set_servo(digger_angle)

addr = socket.getaddrinfo("0.0.0.0", PORT)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(BACKLOG)
print("Listening for connections on port", PORT)

while True:
    try:
        cl, addr = s.accept()
        req = cl.recv(RECV_SIZE).decode()

        if "/cmd?" in req:
            a = req.split("a=")[1].split(" ")[0].strip()

            if   a == "fwd": drive( DRIVE_SPEED,  DRIVE_SPEED)
            elif a == "bck": drive(-DRIVE_SPEED, -DRIVE_SPEED)
            elif a == "lft": drive(-TURN_SPEED,   TURN_SPEED)
            elif a == "rgt": drive( TURN_SPEED,  -TURN_SPEED)
            elif a == "stp": stop()
            elif a == "dig_up":
                digger_angle = min(DIGGER_MAX, digger_angle + DIGGER_STEP)
                set_servo(digger_angle)
            elif a == "dig_dn":
                digger_angle = max(DIGGER_MIN, digger_angle - DIGGER_STEP)
                set_servo(digger_angle)

            cl.send("HTTP/1.1 200 OK\r\n\r\nOK")
        else:
            cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + HTML)

        cl.close()

    except Exception as e:
        print("Error:", e)
        stop()