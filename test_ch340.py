"""
Utility script to exercise a CH340 USB-Serial adapter.

Features:
- Enumerate available serial ports so you can confirm the OS sees the adapter.
- Toggle DTR/RTS lines to see if indicator LEDs respond.
- Send a test pattern and wait for a loopback response (use a jumper between TX and RX).
- Provide verbose logging to help debug power and communication issues.

Example usage:
  python test_ch340.py --list-ports
  python test_ch340.py --port COM5 --baud 115200 --pulse-lines --loopback
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
        usb_info = f"USB VID:PID {port.vid:04X}:{port.pid:04X}" if port.vid and port.pid else "USB IDs not reported"
        print(f"  {port.device} -> {port.description} ({usb_info})")


def pulse_modem_lines(conn: serial.Serial, delay: float = 0.25) -> None:
    """Toggle DTR/RTS to check that LEDs light up and the chip responds."""
    print("Pulsing DTR/RTS lines...")
    for _ in range(3):
        conn.dtr = True
        conn.rts = True
        time.sleep(delay)
        conn.dtr = False
        conn.rts = False
        time.sleep(delay)
    print("Finished pulsing modem control lines.")


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
    parser.add_argument("--port", default="COM5", help="Serial port name (e.g., COM5 on Windows or /dev/ttyUSB0 on Linux)")
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate to open the port with")
    parser.add_argument("--timeout", type=float, default=2.0, help="Seconds to wait for loopback data")
    parser.add_argument("--pattern", default="CH340 loopback test", help="Text pattern to send during loopback")
    parser.add_argument("--pulse-lines", action="store_true", help="Toggle DTR/RTS to check LED and pin response")
    parser.add_argument("--loopback", action="store_true", help="Send/receive a loopback test (requires TX and RX tied together)")
    parser.add_argument("--list-ports", action="store_true", help="List detected serial ports and exit")
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
            print(f"DTR state: {conn.dtr}, RTS state: {conn.rts}, CTS: {conn.cts}, DSR: {conn.dsr}")

            if args.pulse_lines:
                pulse_modem_lines(conn)

            if args.loopback:
                pattern = args.pattern.encode("utf-8")
                success = exercise_loopback(conn, pattern, args.timeout)
                return 0 if success else 1

            print("No test selected. Use --pulse-lines and/or --loopback to run checks.")
            return 0
    except serial.SerialException as exc:
        print(f"Failed to open {args.port}: {exc}")
        print("Ensure the CH340 is connected, the correct driver is installed, and no other program is holding the port open.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
