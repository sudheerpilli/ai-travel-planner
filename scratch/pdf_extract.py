"""
The PDF uses ASCII85Decode+FlateDecode. 
The raw text already contains plaintext data embedded in the annotation objects (URIs, etc.)
Let's search for annotation text and also try to decode the content streams properly.

ReportLab content streams use: /Filter [ /ASCII85Decode /FlateDecode ]
The streams contain PDF drawing operators, not plain text. Text is encoded as hex or rendered via Tj/TJ operators.
We need to parse the content streams properly OR validate via the Python data structures directly.
"""
import sys, re, zlib, struct
sys.path.insert(0, r'c:\Users\sudhe\Downloads\ai_travel_planning_chatbot')

from planner import create_comprehensive_itinerary
from services.pdf_service import generate_trip_pdf

trip = create_comprehensive_itinerary(
    'Visakhapatnam', 'Goa', '2026-12-06', '2026-12-09', 2, 25000,
    'total_group', 'INR', 'budget', 'budget_hotel', 'casual',
    ['beaches', 'historical'], 'Buses'
)
pdf_bytes = generate_trip_pdf(trip)
raw_text = pdf_bytes.decode('latin1', errors='ignore')

print(f"PDF size: {len(pdf_bytes):,} bytes")

# Find page count
page_m = re.search(r'/Count (\d+)', raw_text)
print(f"Pages: {page_m.group(1) if page_m else 'N/A'}")

# Check all /Filter lines
filters = re.findall(r'/Filter \[([^\]]+)\]', raw_text)
print(f"Filter types found: {set(filters[:5])}")

# Find stream boundaries and lengths
obj_stream_re = re.compile(r'(\d+) 0 obj\s*<<(.*?)>>\s*stream\r?\n', re.DOTALL)
all_decoded = []

for m in obj_stream_re.finditer(raw_text):
    obj_num = m.group(1)
    dict_text = m.group(2)
    start_pos = m.end()
    
    # Get length
    length_m = re.search(r'/Length (\d+)', dict_text)
    if not length_m:
        continue
    length = int(length_m.group(1))
    
    # Get the actual binary stream data
    stream_start = m.end()
    stream_data = pdf_bytes[stream_start:stream_start + length]
    
    # Determine filter
    filter_m = re.search(r'/Filter\s*\[([^\]]+)\]', dict_text)
    if not filter_m:
        filter_m = re.search(r'/Filter\s+(/\w+)', dict_text)
    
    filter_str = filter_m.group(1) if filter_m else ''
    
    decoded = None
    if 'ASCII85Decode' in filter_str:
        # ASCII85 decode
        def ascii85_decode(data):
            # Strip <~ ~> if present
            d = bytes(b if b > 32 else 0 for b in data)
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
        
        try:
            a85 = ascii85_decode(stream_data)
            if 'FlateDecode' in filter_str:
                decoded = zlib.decompress(a85)
            else:
                decoded = a85
        except Exception as e:
            pass
    elif 'FlateDecode' in filter_str:
        try:
            decoded = zlib.decompress(stream_data)
        except Exception:
            pass
    
    if decoded:
        # Extract text strings from PDF content stream
        # Look for Tj (show text) and TJ (show text array) operators
        text_content = decoded.decode('latin1', errors='ignore')
        # PDF text: (string) Tj  or  [(string)] TJ
        strings = re.findall(r'\(([^)]*)\)\s*Tj', text_content)
        tj_groups = re.findall(r'\[([^\]]+)\]\s*TJ', text_content)
        for g in tj_groups:
            strings.extend(re.findall(r'\(([^)]*)\)', g))
        if strings:
            all_decoded.extend(strings)
            print(f"  Obj {obj_num}: {len(strings)} text strings extracted")

combined = ' '.join(all_decoded)
print(f"\nTotal text strings: {len(all_decoded)}")
print(f"Combined text length: {len(combined)}")

if combined:
    print("\nSample text strings (first 20):")
    for s in all_decoded[:20]:
        if s.strip():
            print(f"  '{s}'")

# Key verifications
print("\n=== CONTENT VERIFICATION ===")
checks = [
    ('Visakhapatnam', 'Origin city'),
    ('Goa', 'Destination'),
    ('10,760', 'Bus round-trip ₹10,760'),
    ('5,380', 'Bus one-way ₹5,380'),
    ('8,472', 'Train round-trip ₹8,472'),
    ('26,888', 'Flight round-trip ₹26,888'),
    ('38,898', 'Taxi round-trip ₹38,898'),
    ('22,348', 'Car round-trip ₹22,348'),
    ('TOTAL ESTIMATED', 'Budget reconciliation row'),
    ('Reis Magos', 'Reis Magos Fort'),
    ('Basilica', 'Basilica of Bom Jesus'),
    ('Calangute', 'Calangute Beach'),
    ('Fort Aguada', 'Fort Aguada'),
]
for term, desc in checks:
    found = term in combined
    print(f"  {'PASS' if found else 'FAIL'} | {desc} | '{term}'")
