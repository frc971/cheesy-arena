import argparse
import sys
import time

from nplc import NPLC


def render(red_status, blue_status, message):
    red_count = red_status.get("count", "?")
    red_state = red_status.get("state", "?")
    red_lights = red_status.get("lights", "?")
    blue_count = blue_status.get("count", "?")
    blue_state = blue_status.get("state", "?")
    blue_lights = blue_status.get("lights", "?")
    return (
        "NPLC Fuel Counter Display\n"
        "==========================\n"
        f"Red  Hub: {red_count}  [{red_state}]  lights={red_lights}\n"
        f"Blue Hub: {blue_count}  [{blue_state}]  lights={blue_lights}\n"
        "\n"
        "Controls:\n"
        "  1 start red   2 stop red   3 reset red\n"
        "  4 start blue  5 stop blue  6 reset blue\n"
        "  a start both  s stop both  d reset both\n"
        "  z lights red on   x lights red off\n"
        "  c lights blue on  v lights blue off\n"
        "  b lights both on  n lights both off\n"
        "  q quit\n"
        f"\nLast action: {message}\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Simple NPLC fuel counter display.")
    parser.add_argument(
        "--red",
        default="http://10.0.100.10:5000",
        help="Red hub base URL (default: http://10.0.100.10:5000)",
    )
    parser.add_argument(
        "--blue",
        default="http://10.0.100.11:5000",
        help="Blue hub base URL (default: http://10.0.100.11:5000)",
    )
    parser.add_argument("--rate", type=float, default=5.0, help="Polling rate in Hz (default: 5)")
    parser.add_argument("--timeout", type=float, default=2.0, help="HTTP timeout in seconds (default: 2)")
    args = parser.parse_args()

    nplc = NPLC(args.red, args.blue, timeout_sec=args.timeout)
    sleep_s = 1.0 / max(args.rate, 0.1)
    last_message = "none"

    def apply_command(key):
        nonlocal last_message
        if key == "1":
            nplc.start_hub_counting("red")
            last_message = "start red"
        elif key == "2":
            nplc.stop_hub_counting("red")
            last_message = "stop red"
        elif key == "3":
            nplc.reset_hub_count("red")
            last_message = "reset red"
        elif key == "4":
            nplc.start_hub_counting("blue")
            last_message = "start blue"
        elif key == "5":
            nplc.stop_hub_counting("blue")
            last_message = "stop blue"
        elif key == "6":
            nplc.reset_hub_count("blue")
            last_message = "reset blue"
        elif key == "a":
            nplc.start_hub_counting("red")
            nplc.start_hub_counting("blue")
            last_message = "start both"
        elif key == "s":
            nplc.stop_hub_counting("red")
            nplc.stop_hub_counting("blue")
            last_message = "stop both"
        elif key == "d":
            nplc.reset_hub_count("red")
            nplc.reset_hub_count("blue")
            last_message = "reset both"
        elif key == "z":
            nplc.turn_hub_lights_on("red")
            last_message = "lights red on"
        elif key == "x":
            nplc.turn_hub_lights_off("red")
            last_message = "lights red off"
        elif key == "c":
            nplc.turn_hub_lights_on("blue")
            last_message = "lights blue on"
        elif key == "v":
            nplc.turn_hub_lights_off("blue")
            last_message = "lights blue off"
        elif key == "b":
            nplc.turn_hub_lights_on("red")
            nplc.turn_hub_lights_on("blue")
            last_message = "lights both on"
        elif key == "n":
            nplc.turn_hub_lights_off("red")
            nplc.turn_hub_lights_off("blue")
            last_message = "lights both off"
        elif key:
            last_message = f"unknown command: {key}"

    try:
        while True:
            try:
                red_status = nplc.get_hub_status("red")
            except RuntimeError as exc:
                red_status = {"count": "ERR", "state": str(exc)}
            try:
                blue_status = nplc.get_hub_status("blue")
            except RuntimeError as exc:
                blue_status = {"count": "ERR", "state": str(exc)}

            sys.stdout.write("\x1b[2J\x1b[H")
            sys.stdout.write(render(red_status, blue_status, last_message))
            sys.stdout.write("\nEnter command (q to quit): ")
            sys.stdout.flush()

            key = input().strip().lower()
            if key == "q":
                break
            apply_command(key[:1] if key else "")
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()