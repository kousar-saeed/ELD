# HOS Engine Constants (49 CFR Part 395)

MAX_DRIVE_HOURS = 11.0
MAX_WINDOW_HOURS = 14.0
BREAK_AFTER_HOURS = 8.0  # cumulative driving before 30-min break required
BREAK_DURATION = 0.5     # hours (30 mins)
CYCLE_MAX_HOURS = 70.0   # 70-hr / 8-day cycle limit
RESTART_HOURS = 34.0     # hours off-duty for full cycle restart
REST_HOURS = 10.0        # hours off-duty mandatory reset
FUEL_INTERVAL_MILES = 1000.0  # fuel stop inserted at least every 1000 driven miles
FUEL_DURATION = 0.5      # hours (30 mins) on-duty not driving
PICKUP_DROPOFF_HOURS = 1.0  # 1 hour on-duty at pickup and dropoff
