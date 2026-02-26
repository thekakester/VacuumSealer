# Vacuum Sealer Controller – Raspberry Pi Pico (MicroPython)
# Outputs are ACTIVE-LOW: drive pin LOW to ENABLE, HIGH to DISABLE.

from machine import ADC, Pin
import time

# -------------------------
# Configuration constants
# -------------------------
DEBOUNCE_MS            = 50
COMPRESSOR_SPINDOWN_MS = 200    # Allowed blocking delay

# ---------------------------------------
# Potentiometer Setup
# for controlling vacuum and heat time
# ---------------------------------------
vacuum_time_dial = ADC(Pin(26)) #Pin(26, Pin.IN) # Solenoid + Compressor ON duration (GP26 = ADC0)
heater_time_dial = ADC(Pin(27)) #Pin(27, Pin.IN) # Heating ON duration (GP27 = ADC1)

# -------------------------
# Adjustable timings (variables, not constants)
# -------------------------
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

#Read analog pin (potentiometer) to decide how long to run the compressor for
#Returns time in milliseconds
def getCompressorTimeMS():
    compressorTime = 14000 #Max compressor time is 14 seconds
    compressorPotentiometer = vacuum_time_dial.read_u16() #Returns 0-65535
    print("POT: ", compressorPotentiometer)
    
    #Scaling linearly doesn't work that well.  2x the amount of time doesn't get you
    #2x the amount of seal.  After the first like 3-4 seconds, we're close to "max seal".
    #If you want to go beyond that, even by a tiny bit, you need to dramatically increase
    #compressor time.  Because of this, we'll take this to a power of 1.5
    normalized = compressorPotentiometer / 65535 #Returns 0.0-1.0
    multiplier = normalized * normalized #normalized^1.5, increase non-linearly up.  Still 0.0-1.0
    
    compressorTime = (compressorTime * multiplier);
    return compressorTime

#Read analog pin (potentiometer) to decide how long to run the heater for
#Returns time in milliseconds
def getHeaterTimeMS():
    heaterTime = 5000 #Max heater time is 5 seconds
    heaterPotentiometer = heater_time_dial.read_u16()
    heaterTime = (heaterTime * heaterPotentiometer) / 65535;
    return heaterTime

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
    
    vacuum_time_ms = getCompressorTimeMS();
    print("Compressor:", vacuum_time_ms, "ms");
    
    if not wait_with_cancel(vacuum_time_ms, "Waiting"):
        return  # canceled -> already safe


    # Compressor spin-down
    disable_compressor()
    disable_compressorSolenoid();
    time.sleep_ms(COMPRESSOR_SPINDOWN_MS)

    # Heating phase
    enable_heat()
    
    heater_time_ms = getHeaterTimeMS();
    print("Heater:", heater_time_ms, "ms");
    
    if not wait_with_cancel(heater_time_ms, "Waiting"):
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
