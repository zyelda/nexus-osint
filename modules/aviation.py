from FlightRadar24 import FlightRadar24API

def scan_aircraft(tail_number):
    """
    Melacak Pesawat berdasarkan Nomor Ekor (Tail Number/Registration).
    Contoh: PK-GIAA, N12345
    """
    fr_api = FlightRadar24API()
    results = {}
    tail_number = tail_number.upper().strip() 

    try:
        flights = fr_api.get_flights()
        target_flight = None
        
        for f in flights:
            if f.registration == tail_number:
                target_flight = f
                break
        
        results['Registration'] = tail_number
        
        if target_flight:
            results['Status'] = "AIRBORNE (Sedang Terbang) ✈️"
            results['Flight Number'] = target_flight.callsign
            results['Aircraft Model'] = target_flight.aircraft_code
            results['Airline'] = target_flight.airline_icao
            results['Altitude'] = f"{target_flight.altitude} ft"
            results['Ground Speed'] = f"{target_flight.ground_speed} kts"
            results['Heading'] = f"{target_flight.heading}°"
            results['Origin Airport'] = target_flight.origin_airport_iata
            results['Destination Airport'] = target_flight.destination_airport_iata
            
            results['GPS Coordinates'] = f"{target_flight.latitude},{target_flight.longitude}"
            results['Google Maps Link'] = f"https://www.google.com/maps?q={target_flight.latitude},{target_flight.longitude}"
        else:
            results['Status'] = "GROUNDED / NOT FOUND (Tidak sedang mengudara atau jangkauan radar off)."

        prefix = tail_number.split('-')[0] if '-' in tail_number else tail_number[:1]
        country_codes = {
            'PK': 'Indonesia', 'VH': 'Australia', '9M': 'Malaysia', 
            'HS': 'Thailand', 'JA': 'Japan', 'N': 'USA', 'B': 'China/Taiwan'
        }
        results['Country of Origin'] = country_codes.get(prefix, "Unknown / International")
        
        results['Photo Gallery'] = f"https://www.jetphotos.com/registration/{tail_number}"

    except Exception as e:
        results['Error'] = f"Gagal melacak pesawat: {str(e)}"

    return results