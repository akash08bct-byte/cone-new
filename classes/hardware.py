import hashlib
import platform
import subprocess
from classes.logging import error_log


def run_command(cmd):
    try:
        return subprocess.check_output(
            cmd,
            shell=isinstance(cmd, str),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception as e:
        error_log("Error",e)
        return None


def get_motherboard_id():

    if platform.system() == "Windows":

        output = run_command("wmic baseboard get serialnumber")

        if output:
            lines = [x.strip() for x in output.splitlines() if x.strip()]
            if len(lines) >= 2:
                return lines[1]

    elif platform.system() == "Linux":

        output = run_command("/usr/sbin/dmidecode -s baseboard-serial-number")

        if output:
            return output

    return "UNKNOWN"


def get_hardware_id():

    board = get_motherboard_id()+"GRgT6OLFGe9ZksUL4RaPsgVl"

    return hashlib.sha256(board.encode()).hexdigest()

