from pymodbus.client.sync import ModbusTcpClient


# ---------------- PLC SETTINGS ----------------
PLC_IP = "192.168.1.5"
PLC_PORT = 502
UNIT_ID = 1

client = ModbusTcpClient(PLC_IP, port=PLC_PORT, timeout=2)

# ---------------- PLC READ ADDRESSES ----------------
MACHINE_STATUS_ADDR = 400

# SENSOR1_CONVEYOR = 512
# SENSOR2_ARRIVAL  = 525
# SENSOR3_FINAL    = 528

RESET_ADDR        = 470
MODE_ADDR    = 450
# EMERGENCY_ADDR    = 533
SENSOR_COUNT      = 468

# AIR_PRESSURE_ADDR = 531
# CONVEYOR_ADDR     = 600
# LOCK_CONE_ADDR    = 601
# PISTON_UP_ADDR    = 602
# ROTATE_ADDR       = 604
# PISTON_DOWN_ADDR  = 603

# PISTON_IDLE_ADDR  = 535

# UV_LIGHT_ADDR     = 605
# WHITE_LIGHT_ADDR  = 609

# GREEN_LIGHT_ADDR  = 606
# RED_LIGHT_ADDR    = 607
# BUZZER_ADDR       = 608

# PLC REQUEST ADDRESSES
WHITE_LIGHT_ADDR = 460
UV_LIGHT_ADDR = 462

# PLC RESULT ADDRESSES
WHITE_RESULT_ADDR = 420
UV_RESULT_ADDR = 422



# # -------- INPUTS --------
# def start_point_sensor():
#     return read_register(SENSOR1_CONVEYOR) == 1
    # return 1


# def mid_point_sensor():
#     return read_register(SENSOR2_ARRIVAL) == 1
    # return 1


# def end_point_sensor():
#     return read_register(SENSOR3_FINAL) == 1
    # return 1
    
# def air_pressure():
#     return read_register(AIR_PRESSURE_ADDR) == 1
    # return 1
    
def ensure_connected():
    """Connect to PLC if the socket is closed."""
    try:
        if client.is_socket_open():
            return True

        connected = client.connect()

        if connected:
            print(f"✅ PLC connected: {PLC_IP}:{PLC_PORT}")
        else:
            print(f"❌ PLC connection failed: {PLC_IP}:{PLC_PORT}")

        return bool(connected)

    except Exception as e:
        print(f"[PLC CONNECTION ERROR] {e}")
        return False


def read_register(address):
    try:
        if not ensure_connected():
            return None

        response = client.read_holding_registers(
            address=address,
            count=1,
            unit=UNIT_ID
        )

        if response.isError():
            print(
                f"[PLC READ ERROR] "
                f"Address={address}, Response={response}"
            )
            return None

        if not response.registers:
            print(f"[PLC READ ERROR] No value at address {address}")
            return None

        value = response.registers[0]

        print(
            f"[PLC READ] Address={address}, Value={value}"
        )

        return value

    except Exception as e:
        print(
            f"[PLC READ EXCEPTION] "
            f"Address={address}, Error={e}"
        )

        try:
            client.close()
        except Exception:
            pass

        return None


def write_register(address, value):
    try:
        if not ensure_connected():
            print("❌ PLC not connected")
            return False

        response = client.write_register(
            address=address,
            value=int(value),
            unit=UNIT_ID
        )

        if response.isError():
            print(
                f"[PLC WRITE ERROR] "
                f"Address={address}, "
                f"Value={value}, "
                f"Response={response}"
            )
            return False

        print(
            f"✅ [PLC WRITE] "
            f"Address={address}, Value={value}"
        )

        return True

    except Exception as e:
        print(
            f"❌ [PLC WRITE EXCEPTION] "
            f"Address={address}, "
            f"Value={value}, Error={e}"
        )

        try:
            client.close()
        except Exception:
            pass

        return False
            
def machine_status():
    value = read_register(MACHINE_STATUS_ADDR)

    if value is None:
        print("❌ Machine/PLC not connected")
        return False

    print(f"✅ Machine connected, status={value}")
    return value

def machine_reset():
    return read_register(RESET_ADDR)


def check_mode():
    value = read_register(MODE_ADDR)
    if value == 0:
        return "auto mode"
    elif value == 1:
        return "manual mode"
    return "False"

# def emergency_triggering():
#     value = read_register(EMERGENCY_ADDR)
#     # emergency pressed = 1
#     return value == 1

# -------- OUTPUTS --------

# def conveyor_on(): 
#     write_register(CONVEYOR_ADDR, 1)
# def conveyor_off(): 
#     write_register(CONVEYOR_ADDR, 0)


# def lock_cone(): 
#     write_register(LOCK_CONE_ADDR, 1)
# def unlock_cone(): 
#     write_register(LOCK_CONE_ADDR, 0)

# def piston_up(): 
#     write_register(PISTON_UP_ADDR, 1)
# def piston_up_stop(): 
#     write_register(PISTON_UP_ADDR, 0)
    
# def piston_idle_sensor():
#     return read_register(PISTON_IDLE_ADDR) == 1    
    
# def piston_down(): 
#     write_register(PISTON_DOWN_ADDR, 1)
# def piston_down_stop(): 
#     write_register(PISTON_DOWN_ADDR, 0)

# def piston_rotate(): 
#     write_register(ROTATE_ADDR, 1)
# def piston_rotate_stop(): 
#     write_register(ROTATE_ADDR, 0)


# def white_light_on(): 
#     write_register(WHITE_LIGHT_ADDR, 1)
# def white_light_off(): 
#     write_register(WHITE_LIGHT_ADDR, 0)

# def uv_light_on(): 
#     write_register(UV_LIGHT_ADDR, 1)
# def uv_light_off(): 
#     write_register(UV_LIGHT_ADDR, 0)

# def green_light_on(): 
#     write_register(GREEN_LIGHT_ADDR, 1)
# def green_light_off(): 
#     write_register(GREEN_LIGHT_ADDR, 0)

# def red_light_on(): 
#     write_register(RED_LIGHT_ADDR, 1)
# def red_light_off(): 
#     write_register(RED_LIGHT_ADDR, 0)

# def buzzer_on(): 
#     write_register(BUZZER_ADDR, 1)
# def buzzer_off(): 
#     write_register(BUZZER_ADDR, 0)

def count_sensor():
    try:
        return read_register(SENSOR_COUNT)
    except Exception as e:
        print(f"Sensor count read failed: {e}")
        return False


def white_light_signal(value=None):
    try:
        value = read_register(WHITE_LIGHT_ADDR)

        if value == 1:
            return True
        else:
            return False

    except Exception as e:
        print(f"White light signal read failed: {e}")
        return False


def uv_light_signal():
    try:
        value = read_register(UV_LIGHT_ADDR)

        if value == 1:
            return True
        else:
            return False

    except Exception as e:
        print(f"UV light signal read failed: {e}")
        return False

def white_light_result(result):
    try:
        write_register(WHITE_RESULT_ADDR, result)
        return True
    except Exception as e:
        print(f"White light result write failed: {e}")
        return False


def uv_light_result(result):
    try:
        write_register(UV_RESULT_ADDR, result)
        return True
    except Exception as e:
        print(f"UV light result write failed: {e}")
        return False
    

def close_clients():
    try:
        client.close()
    except:
        pass
    
# machine_status()
# result = 1
# print(uv_light_result(result))
# print(uv_light_signal())
# print(check_mode())