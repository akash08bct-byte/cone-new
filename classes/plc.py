
import random

values = [0, 1, 0, 1, 0, 0, 0]

data = 0
value = 0


def plc_check():
    return True


def white_light_signal():
    global data, value

    value = random.choice(values)
    print("White Light PLC:", value)

    # Detect White Light ON only once
    if value and data == 0:
        data = 1
        return 1

    return 0


def uv_light_signal():
    global data, value

    # Detect White Light OFF after it was ON
    if data == 1 and value == 0:
        data = 0
        print("White Light OFF - UV stage ready")
        return 1

    return 0


if __name__ == "__main__":

    for i in range(20):

        white = white_light_signal()

        if white:
            print("CAPTURE WHITE LIGHT IMAGE")

        uv = uv_light_signal()

        if uv:
            print("CAPTURE UV LIGHT IMAGE")
