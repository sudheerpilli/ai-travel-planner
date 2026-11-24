import sys
sys.path.insert(0, r'c:\Users\sudhe\Downloads\ai_travel_planning_chatbot')
from services.transport_service import compare_transportation_modes

# Check if per-person prices are consistent for different traveller counts
print("=" * 100)
print("TRANSPORT PRICING AUDIT: Visakhapatnam -> Goa (1, 2, 4 travellers)")
print("=" * 100)

results = {}
for n in [1, 2, 4]:
    tc = compare_transportation_modes("Visakhapatnam", "Goa", travelers=n, currency="INR")
    results[n] = tc
    print(f"\n--- {n} TRAVELLER(S) ---")
    hdr = f"  {'Mode':<20} {'Type':<12} {'OW/pax':>8} {'RT/pax':>8} {'OW_group':>10} {'RT_group':>10}"
    print(hdr)
    print("  " + "-" * 72)
    for opt in tc["options"]:
        ow = opt["one_way_total_inr"]
        rt = opt["return_total_inr"]
        pp_ow = opt.get("fare_per_person_inr", 0)
        pp_rt = opt.get("return_fare_per_person_inr", round(rt / n) if n else rt)
        ptype = opt.get("pricing_type", "?")
        print(f"  {opt['mode']:<20} {ptype:<12} {pp_ow:>8,.0f} {pp_rt:>8,.0f} {ow:>10,.0f} {rt:>10,.0f}")

# Arithmetic verification
print("\n" + "=" * 100)
print("ARITHMETIC VERIFICATION")
print("=" * 100)

# Bus: should be per-person, so group total = per_person * travelers
for n in [1, 2, 4]:
    tc = results[n]
    bus = next(o for o in tc["options"] if o["mode"] == "Buses")
    pp_ow = bus["fare_per_person_inr"]
    expected_ow_group = pp_ow * n
    expected_rt_group = pp_ow * n * 2
    actual_ow = bus["one_way_total_inr"]
    actual_rt = bus["return_total_inr"]
    ow_ok = actual_ow == expected_ow_group
    rt_ok = actual_rt == expected_rt_group
    print(f"\nBuses ({n} traveller(s)):")
    print(f"  fare_per_person:         Rs{pp_ow:,.0f}")
    print(f"  Expected OW group:       Rs{expected_ow_group:,.0f}  Actual: Rs{actual_ow:,.0f}  {'OK' if ow_ok else 'MISMATCH!'}")
    print(f"  Expected RT group (2x OW): Rs{expected_rt_group:,.0f}  Actual: Rs{actual_rt:,.0f}  {'OK' if rt_ok else 'MISMATCH!'}")

# Train same check
print()
for n in [1, 2, 4]:
    tc = results[n]
    tr = next(o for o in tc["options"] if o["mode"] == "Trains")
    pp_ow = tr["fare_per_person_inr"]
    expected_ow_group = pp_ow * n
    expected_rt_group = pp_ow * n * 2
    actual_ow = tr["one_way_total_inr"]
    actual_rt = tr["return_total_inr"]
    ow_ok = actual_ow == expected_ow_group
    rt_ok = actual_rt == expected_rt_group
    print(f"Trains ({n} traveller(s)): fare_per_person=Rs{pp_ow:,.0f} | OW_group=Rs{actual_ow:,.0f} [{'OK' if ow_ok else 'BAD'}] | RT_group=Rs{actual_rt:,.0f} [{'OK' if rt_ok else 'BAD'}]")

# Taxi: vehicle pricing - group total should NOT change with traveller count (same vehicle)
print()
for n in [1, 2, 4]:
    tc = results[n]
    cab = next(o for o in tc["options"] if o["mode"] == "Outstation Taxi")
    pp_ow = cab.get("fare_per_person_inr", 0)
    actual_ow = cab["one_way_total_inr"]
    actual_rt = cab["return_total_inr"]
    pp_expected = round(actual_ow / n)
    pp_ok = pp_ow == pp_expected
    print(f"Taxi ({n} traveller(s)): vehicle_OW=Rs{actual_ow:,.0f} vehicle_RT=Rs{actual_rt:,.0f} | pp_ow=Rs{pp_ow:,.0f} [{'OK' if pp_ok else 'BAD: expected Rs'+str(pp_expected)}]")

# Summary: Is 2-traveller bus RT of Rs10,760 correct?
print("\n" + "=" * 100)
print("CONCLUSION: IS Rs10,760 CORRECT FOR 2-TRAVELLER BUS ROUND-TRIP?")
print("=" * 100)
tc2 = results[2]
bus2 = next(o for o in tc2["options"] if o["mode"] == "Buses")
tc1 = results[1]
bus1 = next(o for o in tc1["options"] if o["mode"] == "Buses")
print(f"  1-traveller bus OW: Rs{bus1['one_way_total_inr']:,.0f}, RT: Rs{bus1['return_total_inr']:,.0f}")
print(f"  2-traveller bus OW: Rs{bus2['one_way_total_inr']:,.0f}, RT: Rs{bus2['return_total_inr']:,.0f}")
print(f"  2x 1-traveller RT:  Rs{bus1['return_total_inr']*2:,.0f}")
ratio = bus2["one_way_total_inr"] / bus1["one_way_total_inr"]
print(f"  Ratio (2-traveller OW / 1-traveller OW) = {ratio:.2f}")
if abs(ratio - 2.0) < 0.01:
    expected_rt = bus1["return_total_inr"] * 2
    actual_rt = bus2["return_total_inr"]

    print("  CONFIRMED: Bus pricing is correctly per-person.")
    print(f"  Expected 2-traveller round trip: Rs{expected_rt:,.0f}")
    print(f"  Actual 2-traveller round trip:   Rs{actual_rt:,.0f}")

    if actual_rt == expected_rt:
        print("  PASS: Two-traveller pricing is mathematically consistent.")
    else:
        print("  FAIL: Two-traveller pricing does not match expected amount.")
else:
    print(f"  WARNING: Unexpected ratio {ratio:.2f} - investigate pricing.")
