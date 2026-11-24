"""
Generates fresh Thailand itinerary for 8–14 December 2026 and inspects all days and PDF pages.
Pure-Python PDF text extraction using ASCII85 + Flate stream decoding.
"""

import sys
import os
import re
import zlib
import struct
from datetime import date

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from planner import create_comprehensive_itinerary
from services.pdf_service import generate_trip_pdf


def decode_pdf_text(pdf_bytes: bytes) -> tuple[int, list[str]]:
    """Decodes all text strings from ReportLab PDF streams."""
    raw_text = pdf_bytes.decode('latin1', errors='ignore')
    page_count_m = re.search(r'/Count (\d+)', raw_text)
    num_pages = int(page_count_m.group(1)) if page_count_m else 1

    obj_stream_re = re.compile(r'(\d+) 0 obj\s*<<(.*?)>>\s*stream\r?\n', re.DOTALL)
    all_strings = []

    def ascii85_decode(data):
        d = re.sub(rb'\s+', b'', data)
        if d.startswith(b'<~'): d = d[2:]
        if d.endswith(b'~>'): d = d[:-2]
        result = bytearray()
        i = 0
        while i < len(d):
            if d[i:i+1] == b'z':
                result += b'\x00\x00\x00\x00'
                i += 1
                continue
            chunk = d[i:i+5]
            padding = max(0, 5 - len(chunk))
            chunk = chunk + b'u' * padding
            try:
                n = 0
                for c in chunk:
                    n = n * 85 + (c - 33)
                b4 = struct.pack('>I', n)
                result += b4[:4-padding]
            except Exception:
                pass
            i += 5
        return bytes(result)

    for m in obj_stream_re.finditer(raw_text):
        dict_text = m.group(2)
        length_m = re.search(r'/Length (\d+)', dict_text)
        if not length_m:
            continue
        length = int(length_m.group(1))
        stream_start = m.end()
        stream_data = pdf_bytes[stream_start:stream_start + length]

        filter_m = re.search(r'/Filter\s*\[([^\]]+)\]', dict_text)
        if not filter_m:
            filter_m = re.search(r'/Filter\s+(/\w+)', dict_text)
        filter_str = filter_m.group(1) if filter_m else ''

        decoded = None
        if 'ASCII85Decode' in filter_str:
            try:
                a85 = ascii85_decode(stream_data)
                if 'FlateDecode' in filter_str:
                    decoded = zlib.decompress(a85)
                else:
                    decoded = a85
            except Exception:
                pass
        elif 'FlateDecode' in filter_str:
            try:
                decoded = zlib.decompress(stream_data)
            except Exception:
                pass

        if decoded:
            text_content = decoded.decode('latin1', errors='ignore')
            # Extract PDF strings accounting for escaped parentheses
            str_pattern = re.compile(r'\(((?:[^()\\]|\\.)*)\)')
            strings = str_pattern.findall(text_content)
            # Unescape PDF string escapes
            unescaped_strings = [
                s.replace(r'\(', '(').replace(r'\)', ')').replace(r'\n', '\n').replace(r'\r', '\r').replace(r'\\', '\\')
                for s in strings
            ]
            if unescaped_strings:
                all_strings.extend(unescaped_strings)

    return num_pages, all_strings


def main():
    print("=== 1. GENERATING THAILAND 7-DAY ITINERARY (8-14 DEC 2026) ===")
    trip = create_comprehensive_itinerary(
        start_location="Visakhapatnam",
        destination="Thailand",
        start_date="2026-12-08",
        end_date="2026-12-14",
        travelers=1,
        budget=100000,
        currency="INR"
    )

    itin = trip.get("itinerary", [])
    print(f"Total days generated: {len(itin)}")
    print(f"Unique attractions count reported: {trip.get('unique_attractions_count')}")

    all_attraction_names = []
    part_n_pattern = re.compile(r"\bPart\s+\d+\b", re.IGNORECASE)

    for day in itin:
        d_num = day["day_number"]
        d_date = day["date"]
        d_fmt = day["date_formatted"]
        is_rest = day.get("is_rest_day", False)

        m = day["morning"]
        a = day["afternoon"]
        e = day["evening"]

        print(f"\n--- Day {d_num}: {d_fmt} ({d_date}) [Rest/Leisure: {is_rest}] ---")
        print(f"  Morning   ({m.get('time')}): {m.get('name')} [{m.get('category')}] | Mode: {m.get('travel_mode')} | Fee: {m.get('entry_fee_total')}")
        print(f"  Afternoon ({a.get('time')}): {a.get('name')} [{a.get('category')}] | Mode: {a.get('travel_mode')} | Fee: {a.get('entry_fee_total')}")
        print(f"  Evening   ({e.get('time')}): {e.get('name')} [{e.get('category')}] | Mode: {e.get('travel_mode')} | Fee: {e.get('entry_fee_total')}")
        print(f"  Route M->A: {day.get('route_morning_to_afternoon', {}).get('mode')} (~{day.get('route_morning_to_afternoon', {}).get('distance_km')} km, {day.get('route_morning_to_afternoon', {}).get('duration_formatted')})")
        print(f"  Route A->E: {day.get('route_afternoon_to_evening', {}).get('mode')} (~{day.get('route_afternoon_to_evening', {}).get('distance_km')} km, {day.get('route_afternoon_to_evening', {}).get('duration_formatted')})")

        for slot in [m, a, e]:
            name = slot.get("name")
            if not slot.get("is_leisure"):
                all_attraction_names.append(name)
            # Check for Part N
            if part_n_pattern.search(name):
                print(f"  [ERROR] Part N pattern found: {name}")
                sys.exit(1)

            # Check Chatuchak schedule
            if "chatuchak" in name.lower():
                d_obj = date.fromisoformat(d_date)
                weekday_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][d_obj.weekday()]
                print(f"  -> Chatuchak scheduled on {weekday_name} (Weekday index {d_obj.weekday()})")
                assert d_obj.weekday() in (5, 6), f"Chatuchak scheduled on weekday: {weekday_name}!"

    print("\n=== 2. AUDITING FOR DUPLICATES ===")
    print(f"Total non-leisure attraction visits: {len(all_attraction_names)}")
    unique_names = set(all_attraction_names)
    print(f"Total unique attraction names: {len(unique_names)}")
    if len(all_attraction_names) != len(unique_names):
        duplicates = [n for n in all_attraction_names if all_attraction_names.count(n) > 1]
        print(f"[FAIL] Duplicate attractions found: {set(duplicates)}")
        sys.exit(1)
    else:
        print("[PASS] ZERO duplicate attractions across all days!")

    print("\n=== 3. GENERATING PDF ===")
    pdf_bytes = generate_trip_pdf(trip)
    pdf_path = "scratch/Thailand_7Day_Verified_Dec2026.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"Saved PDF to {pdf_path} ({len(pdf_bytes):,} bytes)")

    print("\n=== 4. INSPECTING EVERY PDF TEXT STREAM ===")
    num_pages, strings = decode_pdf_text(pdf_bytes)
    print(f"Total PDF pages: {num_pages}")
    print(f"Total text strings extracted: {len(strings):,}")

    combined_text = " ".join(strings)
    print(f"Combined text character count: {len(combined_text):,}")

    # Check for Part N
    matches = part_n_pattern.findall(combined_text)
    if matches:
        print(f"[ERROR] Part N found in PDF text streams: {matches}")
        sys.exit(1)
    else:
        print("[PASS] ZERO 'Part N' generic labels found in PDF!")

    # Verify critical Thailand content in PDF
    key_checks = [
        ("The Grand Palace", "Grand Palace Bangkok"),
        ("Wat Arun", "Wat Arun Temple of Dawn"),
        ("Wat Pho", "Wat Pho Reclining Buddha"),
        ("Chatuchak Weekend Market", "Chatuchak Market"),
        ("Ayutthaya Historical Park", "Ayutthaya Historical Park"),
        ("Chiang Mai Doi Suthep", "Chiang Mai Doi Suthep Temple"),
        ("Elephant Nature Park", "Elephant Nature Park Chiang Mai"),
        ("Railay Beach", "Railay Beach Krabi"),
        ("Phi Phi Islands", "Phi Phi Islands Andaman"),
        ("Visakhapatnam", "Starting Location"),
        ("Thailand", "Destination"),
    ]

    print("\n=== 5. KEY ATTRACTIONS & VERIFICATION IN PDF ===")
    for term, label in key_checks:
        found = term in combined_text
        print(f"  {'[PASS]' if found else '[FAIL]'} {label}: '{term}' present in PDF: {found}")
        assert found, f"Expected '{term}' to be in PDF text streams!"

    print("\n[SUCCESS] Fresh Thailand 8-14 Dec 2026 PDF generation and inspection fully verified!")

if __name__ == "__main__":
    main()
