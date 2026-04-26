#!/usr/bin/env python3
"""
Prints a fast browser checklist for the Carlo puzzle flow.
"""

from __future__ import annotations


def main() -> None:
    print("Carlo puzzle verification checklist")
    print("=" * 36)
    print("1) Open https://carlodoroff.com/")
    print("2) Visit routes in SAME browser profile/tab session:")
    print("   - /rabbit")
    print("   - /cra-0004")
    print("   - /signal")
    print("3) Return to homepage, click blank page area, type:")
    print("   - SHIP")
    print("   - CARLO")
    print("4) Scroll near footer to Guestbook form")
    print("5) Fill required fields:")
    print("   - 'leave something nice' (message)")
    print("   - 'tell me what you built...' (solution)")
    print("6) Click 'send' (this is 'submit guestbook')")
    print()
    print("DevTools Console quick checks:")
    print("  JSON.parse(localStorage.getItem('cd_puzzle_state_v1') || '{}')")
    print("  // look for steps_completed and tokens")
    print()
    print("Expected keys usually include:")
    print("  L1_rabbit, L2_cra0004, L4_ship, L5_signal, L6_carlo")


if __name__ == "__main__":
    main()
