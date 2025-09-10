# Vacuum Sealer Controller – Raspberry Pi Pico (MicroPython)
# Outputs are ACTIVE-LOW: drive pin LOW to ENABLE, HIGH to DISABLE.

from machine import Pin
import time

# -------------------------
# Configuration constants
# -------------------------
DEBOUNCE_MS            = 50
COMPRESSOR_SPINDOWN_MS = 200    # Allowed blocking delay

# -------------------------
# Adjustable timings (variables, not constants)
# -------------------------
vacuum_time_ms   = 4500   # Solenoid + Compressor ON duration (cancelable)
heat_time_ms     = 2500   # Heating ON duration (cancelable)
cooldown_time_ms = 2000   # Cooldown after heater OFF (cancelable)

# -------------------------
# Button setup (active LOW with pull-up)
# -------------------------
BUTTON_PIN = 0
BUTTON_PRESSED_LEVEL = 0  # pressed = LOW
btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

# -------------------------
# Output pins (ACTIVE-LOW)
# -------------------------
# Start OFF = HIGH (1)
heat                 = Pin(1, Pin.OUT, value=1)
compressor           = Pin(3, Pin.OUT, value=1)
compressorSolenoid   = Pin(4, Pin.OUT, value=1)
depressurizeSolenoid = Pin(2, Pin.OUT, value=0)

# -------------------------
# Helpers
# -------------------------
def is_button_pressed() -> bool:
    return btn.value() == BUTTON_PRESSED_LEVEL

def enable_heat():
    if heat.value() != 0:
        print("Heating Element ENABLED")
        heat.value(0)

def disable_heat():
    if heat.value() == 0:
        print("Heating Element DISABLED")
        heat.value(1)
    else:
        heat.value(1)

def enable_compressor():
    if compressor.value() != 0:
        print("Compressor ENABLED")
        compressor.value(0)

def disable_compressor():
    if compressor.value() == 0:
        print("Compressor DISABLED")
        compressor.value(1)
    else:
        compressor.value(1)

def enable_compressorSolenoid():
    if compressorSolenoid.value() != 0:
        print("compressorSolenoid ENABLED")
        compressorSolenoid.value(0)

def disable_compressorSolenoid():
    if compressorSolenoid.value() == 0:
        print("compressorSolenoid DISABLED")
        compressorSolenoid.value(1)
    else:
        compressorSolenoid.value(1)

def enable_depressurizeSolenoid():
    if depressurizeSolenoid.value() != 0:
        print("Lid Closed depressurizeSolenoid ENABLED")
        depressurizeSolenoid.value(0)

def disable_depressurizeSolenoid():
    if depressurizeSolenoid.value() == 0:
        print("Lid Closed depressurizeSolenoid DISABLED")
        depressurizeSolenoid.value(1)
    else:
        depressurizeSolenoid.value(1)

def safe_state():
    """Turn everything OFF (HIGH for active-low outputs)."""
    disable_heat()
    disable_compressor()
    disable_compressorSolenoid()
    disable_depressurizeSolenoid()
    
def depressurize():
    safe_state();                  #Disable everything
    enable_depressurizeSolenoid()  #Start depressurization
    wait_for_lid_release()         #Wait until the lid fully opens, releasing the button
    disable_depressurizeSolenoid() #Make sure nothing is actively powered

def wait_with_cancel(duration_ms: int, label: str = "Waiting") -> bool:
    """
    Non-blocking wait that regularly checks the lid button.
    Returns True if full time elapsed while lid remained closed.
    Returns False if the lid was released (and puts system in safe state).
    """
    print("{} {}ms".format(label, duration_ms))
    t_start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t_start) < duration_ms:
        if not is_button_pressed():
            print("Cycle canceled — lid opened")
            safe_state()
            return False
        time.sleep_ms(5)
    return True

def wait_for_lid_release():
    """Block (in safe state) until the lid is released with debounce."""
    if not is_button_pressed():
        return
    print("Waiting for lid release...")
    while is_button_pressed():
        time.sleep_ms(10)
    time.sleep_ms(DEBOUNCE_MS)
    print("Lid released — ready for next cycle")

def run_cycle():
    """
    Sequence:
      - Enable compressorSolenoid + disable depressurizeSolenoid + compressor for vacuum_time_ms (cancelable)
      - Disable compressor, 100 ms block
      - Enable heater for heat_time_ms (cancelable)
      - Disable heater, cooldown for cooldown_time_ms (cancelable)
      - Safe state
    """
    # Vacuum phase
    enable_compressorSolenoid()
    disable_depressurizeSolenoid()
    enable_compressor()
    if not wait_with_cancel(vacuum_time_ms, "Waiting"):
        return  # canceled -> already safe


    # Compressor spin-down
    disable_compressor()
    disable_compressorSolenoid();
    time.sleep_ms(COMPRESSOR_SPINDOWN_MS)

    # Heating phase
    enable_heat()
    if not wait_with_cancel(heat_time_ms, "Waiting"):
        return  # canceled -> already safe

    # Cooldown phase (heater OFF, keep solenoid state until cooldown finishes)
    disable_heat()
    if not wait_with_cancel(cooldown_time_ms, "Cooling down"):
        return  # canceled -> already safe

# -------------------------
# Main loop
# -------------------------
safe_state()  # ensure known state on boot
print("Vacuum Sealer Controller READY (active-low outputs)")

while True:
    if is_button_pressed():
        # Debounce and confirm still pressed
        time.sleep_ms(DEBOUNCE_MS)
        if is_button_pressed():
            print("Lid closed detected — starting cycle")
            run_cycle()
            # After run (success or cancel), ensure safe and wait for release
            depressurize()
            safe_state()
        else:
            safe_state()
    else:
        safe_state()
    time.sleep_ms(10)
