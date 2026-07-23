import React, { useState, useEffect } from 'react';
import { planTrip } from './api/client';
import TripForm from './components/TripForm';
import RouteMap from './components/RouteMap';
import LogSheetStack from './components/LogSheetStack';
import LoadingState from './components/LoadingState';
import ErrorState from './components/ErrorState';
import { Truck, ShieldCheck, MapPin, Compass, Clock, Award } from 'lucide-react';
import './App.css';

function App() {
  const [tripPlan, setTripPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastSubmitted, setLastSubmitted] = useState(null);

  const handlePlanTrip = async (inputs) => {
    setLoading(true);
    setError(null);
    setLastSubmitted(inputs);

    try {
      const result = await planTrip(inputs);
      setTripPlan(result);
    } catch (err) {
      console.error('Trip planning error:', err);
      setError(err.message || 'Failed to calculate HOS trip plan');
    } finally {
      setLoading(false);
    }
  };

  // Automatically plan default trip on initial mount
  useEffect(() => {
    handlePlanTrip({
      current_location: 'Chicago, IL',
      pickup_location: 'Indianapolis, IN',
      dropoff_location: 'Columbus, OH',
      current_cycle_used: 12.5,
    });
  }, []);

  return (
    <div className="app-container">
      {/* Top Header Navbar */}
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-logo">
            <Truck className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <h1 className="brand-title">ELD Planner & Log Generator</h1>
            <p className="brand-subtitle">
              FMCSA 49 CFR Part 395 HOS Compliance Engine
            </p>
          </div>
        </div>

        <div className="header-badges">
          <span className="status-pill green">
            <ShieldCheck className="w-3.5 h-3.5" />
            70-Hr / 8-Day Cycle Rules
          </span>
          <span className="status-pill blue">
            <Award className="w-3.5 h-3.5" />
            FMCSA Worked Examples Verified
          </span>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="app-main">
        {/* Error Banner if any */}
        {error && (
          <ErrorState
            error={error}
            onRetry={lastSubmitted ? () => handlePlanTrip(lastSubmitted) : null}
          />
        )}

        <div className="dashboard-grid">
          {/* Left Column: Trip Form */}
          <div className="col-form">
            <TripForm onSubmit={handlePlanTrip} loading={loading} />
          </div>

          {/* Right Column: Key Stats & Map */}
          <div className="col-map">
            {/* Quick Metrics Bar */}
            {tripPlan && (
              <div className="metrics-grid">
                <div className="metric-card">
                  <div className="metric-icon text-cyan-400">
                    <Compass className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="metric-label">Total Distance</span>
                    <h4 className="metric-value">{tripPlan.route.distance_miles} mi</h4>
                  </div>
                </div>

                <div className="metric-card">
                  <div className="metric-icon text-emerald-400">
                    <Clock className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="metric-label">Total Driving Time</span>
                    <h4 className="metric-value">{tripPlan.route.duration_hours} hrs</h4>
                  </div>
                </div>

                <div className="metric-card">
                  <div className="metric-icon text-purple-400">
                    <MapPin className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="metric-label">Required Stops</span>
                    <h4 className="metric-value">{tripPlan.stops.length} stops</h4>
                  </div>
                </div>
              </div>
            )}

            {/* Interactive Leaflet Route Map */}
            {tripPlan ? (
              <RouteMap route={tripPlan.route} stops={tripPlan.stops} />
            ) : (
              <div className="map-placeholder-card">
                <p>Submit a trip to generate interactive map & route markers</p>
              </div>
            )}
          </div>
        </div>

        {/* Full-width HOS Daily Logs Section */}
        {tripPlan && (
          <div className="logs-section">
            <LogSheetStack
              dailyLogs={tripPlan.daily_logs}
              warnings={tripPlan.warnings}
            />
          </div>
        )}
      </main>

      {/* Loading Overlay */}
      {loading && <LoadingState />}

      {/* Footer */}
      <footer className="app-footer">
        <p>
          ELD Trip Planner & Log Generator • Built for Full Stack Take-Home Assessment •
          Property-carrying CMV 70-hr/8-day rules (49 CFR Part 395)
        </p>
      </footer>
    </div>
  );
}

export default App;
