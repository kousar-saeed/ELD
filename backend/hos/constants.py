# HOS Engine Constants (49 CFR Part 395 & FMCSA Driver's Guide to HOS)

MAX_DRIVE_HOURS = 11  # FMCSA Guide Section "11-Hour Driving Limit": Max 11 hours driving after 10 consecutive hours off-duty (49 CFR § 395.3(a)(1))
MAX_WINDOW_HOURS = 14  # FMCSA Guide Section "14-Hour Driving Window": Cannot drive beyond 14th consecutive hour after coming on duty (49 CFR § 395.3(a)(2))
BREAK_AFTER_HOURS = 8  # FMCSA Guide Section "30-Minute Rest Break": Requires break after 8 cumulative hours of driving without 30-min interruption (49 CFR § 395.3(a)(3)(ii))
BREAK_DURATION = 0.5  # FMCSA Guide Section "30-Minute Rest Break": Mandatory rest break duration of at least 30 consecutive minutes (49 CFR § 395.3(a)(3)(ii))
CYCLE_MAX_HOURS = 70  # FMCSA Guide Section "60/70-Hour Duty Limit": Cannot drive after 70 hours on-duty in 8 consecutive days (49 CFR § 395.3(b)(2))
RESTART_HOURS = 34  # FMCSA Guide Section "34-Hour Restart": Any 70-hr cycle resets after 34 consecutive hours off-duty (49 CFR § 395.3(d))
FUEL_INTERVAL_MILES = 1000  # FMCSA Assessment Brief / TRD §4: Mandatory fuel stop inserted at least every 1,000 driven miles
PICKUP_DROPOFF_HOURS = 1  # FMCSA Assessment Brief / TRD §4: Mandatory 1-hour on-duty time allocated at pickup and dropoff

REST_HOURS = 10  # FMCSA Guide Section "11-Hour Driving Limit": Mandatory 10 consecutive hours off-duty reset (49 CFR § 395.3(a)(1))
FUEL_DURATION = 0.5  # FMCSA Assessment Brief / TRD §4: Duration of 30 minutes on-duty for fuel stop
