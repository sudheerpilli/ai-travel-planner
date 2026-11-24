"""
Inspect raw PDF structure and attempt comprehensive text extraction.
ReportLab 5.x uses ASCII85Decode+FlateDecode. 
We need to handle the case where /Length is BEFORE the stream keyword.
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

print("=== RAW PDF HEADER (first 2000 chars) ===")
print(raw_text[:2000])
