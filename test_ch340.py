"""
Utility script to exercise a CH340 USB-Serial adapter and use DTR/RTS as simple outputs.

Features:
- Enumerate available serial ports so you can confirm the OS sees the adapter.
- Toggle DTR/RTS lines to see if indicator LEDs or attached hardware respond.
- Control DTR/RTS as "backlight" and "LED" outputs (on/off/blink).
- Send a test pattern and wait for a loopback response (use a jumper between TX and RX).
- Provide verbose logging to help debug power and communication issues.

Example usage:
  python test_ch340.py --list-ports
  python test_ch340.py --port COM5 --pulse-lines
  python test_ch340.py --port COM5 --backlight on --led off
  python test_ch340.py --port COM5 --backlight blink --led blink
  python test_ch340.py --port COM5 --loopback --pattern "hello" --timeout 2
"""

import argparse
import sys
import time

import serial
from serial.tools import list_ports


def list_available_ports() -> None:
    """Print the serial ports detected by pyserial."""
    ports = list_ports.comports()
    if not ports:
        print("No serial ports detected. Verify the CH340 is plugged in and drivers are installed.")
        return

    print("Available serial ports:")
    for port in ports:
        usb_info = (
            f"USB VID:PID {port.vid:04X}:{port.pid:04X}"
            if port.vid and port.pid
            else "USB IDs not reported"
        )
        print(f"  {port.device} -> {port.description} ({usb_info})")


def pulse_modem_lines(conn: serial.Serial, delay: float = 0.5, cycles: int = 3) -> None:
    """Toggle DTR/RTS to check that LEDs / controller inputs respond."""
    print(f"Pulsing DTR/RTS lines for {cycles} cycles (delay={delay}s)...")
    for i in range(cycles):
        conn.dtr = True
        conn.rts = True
        print(f"  Cycle {i + 1}: DTR=1, RTS=1")
        time.sleep(delay)

        conn.dtr = False
        conn.rts = False
        print(f"  Cycle {i + 1}: DTR=0, RTS=0")
        time.sleep(delay)

    print(f"Finished pulsing. Final states: DTR={conn.dtr}, RTS={conn.rts}")


def set_backlight_and_led(
    conn: serial.Serial,
    backlight_mode: str | None,
    led_mode: str | None,
    blink_delay: float = 0.25,
    blink_cycles: int = 5,
) -> None:
    """
    Control DTR/RTS as "backlight" and "LED" outputs.

    We arbitrarily map:
      - backlight -> DTR
      - LED       -> RTS

    Modes:
      - 'on'    : set line high (True)
      - 'off'   : set line low (False)
      - 'blink' : toggle line a few times
    """
    if backlight_mode is None and led_mode is None:
        return

    print("Controlling lights via modem lines:")
    print(f"  Backlight (DTR) mode: {backlight_mode}")
    print(f"  LED       (RTS) mode: {led_mode}")

    def apply_mode(line_name: str, get, set, mode: str | None) -> None:
        if mode is None:
            return

        if mode == "on":
            print(f"  {line_name} -> ON (1)")
            set(True)
        elif mode == "off":
            print(f"  {line_name} -> OFF (0)")
            set(False)
        elif mode == "blink":
            print(f"  {line_name} -> BLINK ({blink_cycles} cycles)")
            initial = get()
            for i in range(blink_cycles):
                set(True)
                print(f"    {line_name} cycle {i + 1}: 1")
                time.sleep(blink_delay)
                set(False)
                print(f"    {line_name} cycle {i + 1}: 0")
                time.sleep(blink_delay)
            # Restore initial state (optional)
            set(initial)
            print(f"  {line_name} restored to initial state ({int(initial)})")
        else:
            print(f"  Unknown mode '{mode}' for {line_name}, ignoring.")

    # Map: backlight -> DTR, LED -> RTS
    apply_mode("Backlight/DTR", lambda: conn.dtr, lambda v: setattr(conn, "dtr", v), backlight_mode)
    apply_mode("LED/RTS", lambda: conn.rts, lambda v: setattr(conn, "rts", v), led_mode)

    print(f"Final states after light control: DTR={conn.dtr}, RTS={conn.rts}")


def exercise_loopback(conn: serial.Serial, pattern: bytes, timeout: float) -> bool:
    """Send a pattern and check if the same data is read back (requires TX-RX jumper)."""
    print(f"Sending {len(pattern)} bytes: {pattern!r}")
    conn.reset_input_buffer()
    conn.reset_output_buffer()
    written = conn.write(pattern)
    conn.flush()
    if written != len(pattern):
        print(f"Only wrote {written} bytes, expected {len(pattern)}.")

    end_time = time.monotonic() + timeout
    received = bytearray()
    while time.monotonic() < end_time and len(received) < len(pattern):
        if conn.in_waiting:
            received.extend(conn.read(conn.in_waiting))
        else:
            time.sleep(0.01)

    if received == pattern:
        print("Loopback successful: received exact match.")
        return True

    if not received:
        print("No bytes were read. Check power, wiring, and that TX and RX are jumpered.")
    else:
        print(f"Received {len(received)} bytes: {bytes(received)!r} (expected {pattern!r})")
    return False


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test and debug a CH340 USB-Serial adapter")
    parser.add_argument(
        "--port",
        default="COM5",
        help="Serial port name (e.g., COM5 on Windows or /dev/ttyUSB0 on Linux)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=9600,
        help="Baud rate to open the port with",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Seconds to wait for loopback data",
    )
    parser.add_argument(
        "--pattern",
        default="CH340 loopback test",
        help="Text pattern to send during loopback",
    )

    # Existing tests
    parser.add_argument(
        "--pulse-lines",
        action="store_true",
        help="Toggle DTR/RTS to check LED and pin response",
    )
    parser.add_argument(
        "--loopback",
        action="store_true",
        help="Send/receive a loopback test (requires TX and RX tied together)",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List detected serial ports and exit",
    )

    # NEW: "light" controls mapped to DTR/RTS
    parser.add_argument(
        "--backlight",
        choices=["on", "off", "blink"],
        help="Control backlight via DTR: on/off/blink",
    )
    parser.add_argument(
        "--led",
        choices=["on", "off", "blink"],
        help="Control LED via RTS: on/off/blink",
    )

    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.list_ports:
        list_available_ports()
        return 0

    print(f"Opening {args.port} at {args.baud} baud...")
    try:
        with serial.Serial(port=args.port, baudrate=args.baud, timeout=0.1) as conn:
            print(f"Opened {conn.name}. USB-SERIAL chip reports: {conn.portstr}")
            print(
                f"Initial states -> DTR: {conn.dtr}, RTS: {conn.rts}, "
                f"CTS: {conn.cts}, DSR: {conn.dsr}"
            )

            # Control backlight/LED if requested
            if args.backlight or args.led:
                set_backlight_and_led(conn, args.backlight, args.led)

            # Optional generic pulse test
            if args.pulse_lines:
                pulse_modem_lines(conn)

            # Optional loopback test
            if args.loopback:
                pattern = args.pattern.encode("utf-8")
                success = exercise_loopback(conn, pattern, args.timeout)
                return 0 if success else 1

            # If nothing else was asked for, just leave it at that.
            if not (args.backlight or args.led or args.pulse_lines or args.loopback):
                print(
                    "No test selected. Use --backlight/--led and/or "
                    "--pulse-lines/--loopback to run checks."
                )

            return 0
    except serial.SerialException as exc:
        print(f"Failed to open {args.port}: {exc}")
        print(
            "Ensure the CH340 is connected, the correct driver is installed, "
            "and no other program is holding the port open."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
