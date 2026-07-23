import React, { useState } from 'react';
import { MapPin, Navigation, Clock, Play, RotateCcw, AlertTriangle } from 'lucide-react';

export default function TripForm({ onSubmit, loading }) {
  const [currentLocation, setCurrentLocation] = useState('Chicago, IL');
  const [pickupLocation, setPickupLocation] = useState('Indianapolis, IN');
  const [dropoffLocation, setDropoffLocation] = useState('Columbus, OH');
  const [currentCycleUsed, setCurrentCycleUsed] = useState(12.5);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!currentLocation || !pickupLocation || !dropoffLocation) return;
    onSubmit({
      current_location: currentLocation,
      pickup_location: pickupLocation,
      dropoff_location: dropoffLocation,
      current_cycle_used: parseFloat(currentCycleUsed) || 0,
    });
  };

  const loadPreset = (preset) => {
    if (preset === 'short') {
      setCurrentLocation('Chicago, IL');
      setPickupLocation('Gary, IN');
      setDropoffLocation('South Bend, IN');
      setCurrentCycleUsed(5.0);
    } else if (preset === 'standard') {
      setCurrentLocation('Chicago, IL');
      setPickupLocation('Indianapolis, IN');
      setDropoffLocation('Columbus, OH');
      setCurrentCycleUsed(12.5);
    } else if (preset === 'long') {
      setCurrentLocation('Los Angeles, CA');
      setPickupLocation('Denver, CO');
      setDropoffLocation('Chicago, IL');
      setCurrentCycleUsed(52.0);
    }
  };

  return (
    <div className="trip-form-card">
      <div className="card-header">
        <div className="header-icon">
          <Navigation className="w-5 h-5 text-indigo-400" />
        </div>
        <div>
          <h3>Plan New Trip</h3>
          <p className="card-subtitle">Enter route locations & driver HOS cycle balance</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="trip-form">
        <div className="form-group">
          <label htmlFor="current_location">
            <MapPin className="field-icon text-cyan-400" />
            Current Location (Start)
          </label>
          <input
            id="current_location"
            type="text"
            value={currentLocation}
            onChange={(e) => setCurrentLocation(e.target.value)}
            placeholder="e.g. Chicago, IL"
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="pickup_location">
            <MapPin className="field-icon text-emerald-400" />
            Pickup Location
          </label>
          <input
            id="pickup_location"
            type="text"
            value={pickupLocation}
            onChange={(e) => setPickupLocation(e.target.value)}
            placeholder="e.g. Indianapolis, IN"
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="dropoff_location">
            <MapPin className="field-icon text-rose-400" />
            Dropoff Location
          </label>
          <input
            id="dropoff_location"
            type="text"
            value={dropoffLocation}
            onChange={(e) => setDropoffLocation(e.target.value)}
            placeholder="e.g. Columbus, OH"
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <div className="label-with-value">
            <label htmlFor="current_cycle_used">
              <Clock className="field-icon text-amber-400" />
              70-Hr / 8-Day Cycle Used
            </label>
            <span className="cycle-value-badge">{currentCycleUsed} hrs</span>
          </div>
          <div className="range-slider-container">
            <input
              id="current_cycle_used"
              type="range"
              min="0"
              max="70"
              step="0.5"
              value={currentCycleUsed}
              onChange={(e) => setCurrentCycleUsed(e.target.value)}
              disabled={loading}
              className="cycle-slider"
            />
            <div className="slider-ticks">
              <span>0h</span>
              <span>35h</span>
              <span>70h</span>
            </div>
          </div>
          {currentCycleUsed > 55 && (
            <div className="cycle-warning-note">
              <AlertTriangle className="w-3.5 h-3.5" />
              High cycle usage — 34-hr restart will be required early in trip.
            </div>
          )}
        </div>

        <div className="preset-buttons">
          <span className="preset-label">Quick Presets:</span>
          <button type="button" onClick={() => loadPreset('short')} className="preset-btn">
            Short (100mi)
          </button>
          <button type="button" onClick={() => loadPreset('standard')} className="preset-btn">
            Standard (350mi)
          </button>
          <button type="button" onClick={() => loadPreset('long')} className="preset-btn">
            Long (2,000mi+)
          </button>
        </div>

        <button type="submit" className="submit-btn" disabled={loading}>
          {loading ? (
            <>
              <RotateCcw className="w-4 h-4 animate-spin" />
              Calculating HOS Schedule...
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              Generate Compliant Trip Plan
            </>
          )}
        </button>
      </form>
    </div>
  );
}
