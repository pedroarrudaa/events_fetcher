import React, { useState, useEffect } from 'react';

// Use environment variable for API URL, fallback to localhost for development
const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://events-api-nprw.onrender.com';

const EventsPage = () => {
  const [events, setEvents] = useState([]);
  const [filteredEvents, setFilteredEvents] = useState([]);
  const [eventActions, setEventActions] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filter states - removed statusFilter
  const [typeFilter, setTypeFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');

  // Normalize location function
  const normalizeLocation = (location) => {
    if (!location) return 'N/A';
    
    // Replace Virtual/Online with Remote
    if (location.toLowerCase().includes('virtual') || location.toLowerCase().includes('online')) {
      return 'Remote';
    }
    
    // Convert all-uppercase to proper case
    if (location === location.toUpperCase() && location.length > 2) {
      return location.toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
    }
    
    return location;
  };

  // Fetch event actions for a given event ID
  const fetchEventAction = async (eventId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/event-action/${eventId}`);
      
      if (response.ok) {
        const data = await response.json();
        return data;
      } else if (response.status === 404) {
        return null; // No action found
      }
      
      return null;
    } catch (err) {
      console.error(`Error fetching action for event ${eventId}:`, err);
      return null;
    }
  };

  // Fetch events from API
  const fetchEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_BASE_URL}/events`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setEvents(data);
      setFilteredEvents(data);
      
      // Fetch actions for all events
      const actionsMap = {};
      await Promise.all(
        data.map(async (event) => {
          if (event.id) {
            const action = await fetchEventAction(event.id);
            if (action) {
              actionsMap[event.id] = action;
            }
          }
        })
      );
      setEventActions(actionsMap);
      
    } catch (err) {
      console.error('Error fetching events:', err);
      setError(`Failed to fetch events: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchEvents();
  }, []);

  // Filter events based on selected filters - removed status filtering
  useEffect(() => {
    let filtered = events;

    if (typeFilter) {
      filtered = filtered.filter(event => event.type === typeFilter);
    }

    if (locationFilter) {
      filtered = filtered.filter(event => 
        event.location && normalizeLocation(event.location).toLowerCase().includes(locationFilter.toLowerCase())
      );
    }

    setFilteredEvents(filtered);
  }, [events, typeFilter, locationFilter]);

  // Get unique values for filter dropdowns - removed uniqueStatuses
  const uniqueTypes = [...new Set(events.map(event => event.type))];

  // Format date for display - updated to handle invalid dates
  const formatDate = (dateString) => {
    if (!dateString) return '—';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) { // Check if date is valid
      return 'TBD';
    }
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  // Format action timestamp for display
  const formatActionTime = (timestamp) => {
    if (!timestamp) return '—';
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return '—';
    
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  // Get action badge color
  const getActionColor = (action) => {
    switch (action) {
      case 'archive': return 'bg-red-100 text-red-800';
      case 'reached_out': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // Get type badge color
  const getTypeColor = (type) => {
    switch (type) {
      case 'hackathon': return 'bg-blue-100 text-blue-800';
      case 'conference': return 'bg-purple-100 text-purple-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // Helper function to get a sortable Date object, with fallback for invalid/missing dates
  const getSortableDate = (dateString) => {
    if (!dateString) {
      return new Date('1900-01-01'); // Fallback for null, undefined, or empty string
    }
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      return new Date('1900-01-01'); // Fallback for invalid date strings
    }
    return date;
  };

  // Create a sorted version of filteredEvents before rendering
  const sortedFilteredEvents = [...filteredEvents].sort((a, b) => {
    const dateA = getSortableDate(a.start_date);
    const dateB = getSortableDate(b.start_date);
    return dateB.getTime() - dateA.getTime(); // Sort descending (most recent first)
  });

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading events...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center p-8 bg-white rounded-lg shadow-md max-w-md">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Error Loading Events</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button 
            onClick={fetchEvents}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Events Dashboard</h1>
              <p className="mt-1 text-gray-500">Hackathons and conferences from your database</p>
            </div>
            <button 
              onClick={fetchEvents}
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Filters - updated to 2 columns since status filter is removed */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Filters</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Type Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Type</label>
              <select 
                value={typeFilter} 
                onChange={(e) => setTypeFilter(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Types</option>
                {uniqueTypes.map(type => (
                  <option key={type} value={type}>
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            {/* Location Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Location</label>
              <input
                type="text"
                placeholder="Search by location..."
                value={locationFilter}
                onChange={(e) => setLocationFilter(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Events Table - removed status column */}
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">
              Events ({filteredEvents.length})
            </h2>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Title
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Location
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Start Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    End Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    URL
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Last Action
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Action Time
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {sortedFilteredEvents.map((event) => (
                  <tr key={event.id || event.title} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{event.title}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getTypeColor(event.type)}`}>
                        {event.type}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {normalizeLocation(event.location)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatDate(event.start_date)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatDate(event.end_date)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {event.url ? (
                        <a 
                          href={event.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          Visit
                        </a>
                      ) : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {eventActions[event.id]?.action ? (
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getActionColor(eventActions[event.id].action)}`}>
                          {eventActions[event.id].action}
                        </span>
                      ) : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {eventActions[event.id]?.timestamp ? formatActionTime(eventActions[event.id].timestamp) : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {filteredEvents.length === 0 && (
            <div className="text-center py-12">
              <div className="text-gray-400 text-6xl mb-4">📅</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">No events found</h3>
              <p className="text-gray-500">Try adjusting your filters or refresh the data.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default EventsPage; 