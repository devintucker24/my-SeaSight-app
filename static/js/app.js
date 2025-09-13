// Maritime Route Optimizer - Frontend JavaScript
// Handles map interactions, API calls, and real-time updates

// Global variables
let map;
let routeLayer;
let vesselMarkers = [];
let weatherMarkers = [];
let currentRoute = null;
let websocket = null;
let isConnected = false;
let weatherMap = null;
let vesselsMap = null;

// Initialize the application
async function initApp() {
    console.log('🚢 Initializing Maritime Route Optimizer...');

    // Initialize map
    initMap();

    // Load initial data
    await loadWeather();
    await loadVessels();
    await loadSystemStatus();
    
    // Load vessels on main map
    await loadVesselsOnMainMap();

    // Setup WebSocket connection
    setupWebSocket();

    // Setup form handlers
    setupFormHandlers();

    // Setup periodic updates
    setInterval(updateData, 30000); // Update every 30 seconds

    console.log('✅ Maritime Route Optimizer initialized!');
}

// Initialize Leaflet map
function initMap() {
    console.log('🗺️ Initializing map...');

    // Create map centered on San Francisco Bay
    map = L.map('map').setView([37.7749, -122.4194], 8);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18,
    }).addTo(map);

    // Add nautical chart overlay (if available)
    try {
        L.tileLayer('https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png', {
            attribution: 'OpenSeaMap',
            opacity: 0.7
        }).addTo(map);
    } catch (e) {
        console.log('Nautical charts not available');
    }

    // Add scale control
    L.control.scale().addTo(map);

    // Add click handler for waypoint selection
    map.on('click', function(e) {
        handleMapClick(e);
    });

    // Initialize route layer
    routeLayer = L.layerGroup().addTo(map);

    console.log('✅ Map initialized!');
}

// Setup WebSocket connection
function setupWebSocket() {
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/updates`;

        websocket = new WebSocket(wsUrl);

        websocket.onopen = function(event) {
            isConnected = true;
            updateConnectionStatus(true);
            console.log('🔗 WebSocket connected');
        };

        websocket.onmessage = function(event) {
            handleWebSocketMessage(event);
        };

        websocket.onclose = function(event) {
            isConnected = false;
            updateConnectionStatus(false);
            console.log('🔌 WebSocket disconnected');

            // Attempt to reconnect after 5 seconds
            setTimeout(setupWebSocket, 5000);
        };

        websocket.onerror = function(error) {
            console.error('WebSocket error:', error);
        };

    } catch (error) {
        console.error('WebSocket setup failed:', error);
    }
}

// Handle WebSocket messages
function handleWebSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);

        switch (data.type) {
            case 'route_optimized':
                handleRouteUpdate(data.data);
                break;
            case 'data_refreshed':
                handleDataRefresh(data);
                break;
            case 'vessel_update':
                handleVesselUpdate(data.data);
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    } catch (error) {
        console.error('Error handling WebSocket message:', error);
    }
}

// Update connection status display
function updateConnectionStatus(connected) {
    const statusElement = document.getElementById('connection-status');
    if (connected) {
        statusElement.className = 'badge bg-success';
        statusElement.innerHTML = '<i class="fas fa-circle me-1"></i>Connected';
    } else {
        statusElement.className = 'badge bg-danger';
        statusElement.innerHTML = '<i class="fas fa-circle me-1"></i>Disconnected';
    }
}

// Setup form event handlers
function setupFormHandlers() {
    const routeForm = document.getElementById('route-form');
    routeForm.addEventListener('submit', handleRouteFormSubmit);
}

// Handle route form submission
async function handleRouteFormSubmit(event) {
    event.preventDefault();

    const formData = new FormData(event.target);
    const routeRequest = {
        start_lat: parseFloat(document.getElementById('start-lat').value),
        start_lon: parseFloat(document.getElementById('start-lon').value),
        end_lat: parseFloat(document.getElementById('end-lat').value),
        end_lon: parseFloat(document.getElementById('end-lon').value),
        priority: document.getElementById('priority').value,
        vessel_type: document.getElementById('vessel-type').value
    };

    // Show loading modal
    showLoadingModal();

    try {
        const response = await fetch('/api/routes/optimize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(routeRequest)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        // Update UI with results
        updateRouteResults(result);
        displayRouteOnMap(result.route);

        // Add to route history
        addToRouteHistory(result);

        console.log('✅ Route optimized successfully:', result);

    } catch (error) {
        console.error('❌ Route optimization failed:', error);
        showAlert('Error optimizing route: ' + error.message, 'danger');
    } finally {
        hideLoadingModal();
    }
}

// Update route results display
function updateRouteResults(result) {
    document.getElementById('route-distance').textContent = result.total_distance_nm.toFixed(1);
    document.getElementById('route-time').textContent = result.estimated_time_hours.toFixed(1);
    document.getElementById('route-fuel').textContent = result.estimated_fuel_tons.toFixed(1);
    document.getElementById('route-waypoints').textContent = result.waypoints_count;

    // Show results card
    document.getElementById('route-results').style.display = 'block';

    // Scroll to results
    document.getElementById('route-results').scrollIntoView({ behavior: 'smooth' });
}

// Display route on map
function displayRouteOnMap(route) {
    // Clear existing route
    routeLayer.clearLayers();

    if (route && route.length > 0) {
        // Create route polyline
        const routeLine = L.polyline(route, {
            color: '#007bff',
            weight: 4,
            opacity: 0.8
        });

        // Add route to map
        routeLine.addTo(routeLayer);

        // Add waypoint markers
        route.forEach((point, index) => {
            const marker = L.marker(point, {
                icon: L.divIcon({
                    html: `<div class="waypoint-marker">${index + 1}</div>`,
                    className: 'waypoint-icon'
                })
            });

            marker.bindPopup(`Waypoint ${index + 1}<br>Lat: ${point[0].toFixed(4)}<br>Lon: ${point[1].toFixed(4)}`);
            marker.addTo(routeLayer);
        });

        // Fit map to route
        map.fitBounds(routeLine.getBounds(), { padding: [20, 20] });
    }
}

// Handle route updates from WebSocket
function handleRouteUpdate(routeData) {
    console.log('📡 Route update received:', routeData);
    updateRouteResults(routeData);
    displayRouteOnMap(routeData.route);
}

// Load weather data
async function loadWeather(lat = 37.7749, lon = -122.4194) {
    try {
        const response = await fetch(`/api/weather/current?lat=${lat}&lon=${lon}`);
        const weather = await response.json();

        // Update weather display
        document.getElementById('wind-speed').textContent = `${weather.wind_speed_kts.toFixed(1)}`;
        document.getElementById('wave-height').textContent = `${weather.wave_height_m.toFixed(1)}`;
        document.getElementById('temperature').textContent = `${weather.temperature_c.toFixed(1)}`;
        document.getElementById('wind-direction').textContent = `${weather.wind_direction_deg.toFixed(0)}°`;

        console.log('✅ Weather data loaded:', weather);

    } catch (error) {
        console.error('❌ Failed to load weather:', error);
    }
}

// Load nearby vessels
async function loadVessels(lat = 37.7749, lon = -122.4194, radius = 50) {
    try {
        const response = await fetch(`/api/vessels/nearby?lat=${lat}&lon=${lon}&radius_nm=${radius}`);
        const data = await response.json();

        updateVesselsDisplay(data.vessels);
        console.log(`✅ Loaded ${data.count} nearby vessels`);

    } catch (error) {
        console.error('❌ Failed to load vessels:', error);
    }
}

// Update vessels display
function updateVesselsDisplay(vessels) {
    const container = document.getElementById('vessels-list');

    if (vessels.length === 0) {
        container.innerHTML = '<div class="text-center text-muted"><small>No vessels found nearby</small></div>';
        return;
    }

    container.innerHTML = vessels.map(vessel => `
        <div class="vessel-item">
            <div class="vessel-info">
                <h6>${vessel.name || `MMSI: ${vessel.mmsi}`}</h6>
                <div class="vessel-details">
                    Speed: ${vessel.speed.toFixed(1)} kts<br>
                    Course: ${vessel.course.toFixed(0)}°
                </div>
            </div>
            <div class="vessel-distance">${vessel.distance_nm.toFixed(1)} nm</div>
        </div>
    `).join('');
}

// Load system status
async function loadSystemStatus() {
    try {
        const response = await fetch('/api/health');
        const status = await response.json();

        document.getElementById('ml-status').innerHTML =
            status.models_loaded ?
            '<i class="fas fa-check-circle text-success"></i>' :
            '<i class="fas fa-times-circle text-danger"></i>';

        document.getElementById('weather-points').textContent = status.weather_data_points;
        document.getElementById('ais-vessels').textContent = status.ais_vessels;
        document.getElementById('active-connections').textContent = status.active_connections || 0;

        console.log('✅ System status loaded:', status);

    } catch (error) {
        console.error('❌ Failed to load system status:', error);
    }
}

// Handle map clicks for waypoint selection
function handleMapClick(e) {
    const { lat, lng } = e.latlng;

    // For now, just show coordinates
    console.log(`Map clicked at: ${lat.toFixed(4)}, ${lng.toFixed(4)}`);

    // In future: allow users to set waypoints by clicking
    // showWaypointDialog(lat, lng);
}

// Add route to history
function addToRouteHistory(routeData) {
    const historyContainer = document.getElementById('route-history');

    // Validate route data
    if (!routeData || !routeData.route || !Array.isArray(routeData.route) || routeData.route.length < 2) {
        console.error('Invalid route data for history:', routeData);
        return;
    }

    // Extract start and end coordinates from the route array
    const startPoint = routeData.route[0];
    const endPoint = routeData.route[routeData.route.length - 1];

    // Validate coordinates
    if (!startPoint || !endPoint || startPoint.length < 2 || endPoint.length < 2) {
        console.error('Invalid route coordinates:', { startPoint, endPoint });
        return;
    }

    const routeItem = document.createElement('div');
    routeItem.className = 'route-item';
    routeItem.innerHTML = `
        <strong>${startPoint[0].toFixed(2)}, ${startPoint[1].toFixed(2)}</strong> →
        <strong>${endPoint[0].toFixed(2)}, ${endPoint[1].toFixed(2)}</strong>
        <br><small>${routeData.total_distance_nm?.toFixed(1) || 'N/A'} nm | ${routeData.estimated_time_hours?.toFixed(1) || 'N/A'} hrs</small>
    `;

    historyContainer.insertBefore(routeItem, historyContainer.firstChild);

    // Keep only last 5 routes
    while (historyContainer.children.length > 5) {
        historyContainer.removeChild(historyContainer.lastChild);
    }
}

// Refresh all data
async function refreshData() {
    console.log('🔄 Refreshing all data...');

    try {
        const response = await fetch('/api/data/refresh', { method: 'POST' });
        const result = await response.json();

        if (result.status === 'success') {
            showAlert('Data refreshed successfully!', 'success');
            await loadWeather();
            await loadVessels();
            await loadSystemStatus();
        } else {
            throw new Error(result.message || 'Refresh failed');
        }

    } catch (error) {
        console.error('❌ Data refresh failed:', error);
        showAlert('Failed to refresh data: ' + error.message, 'danger');
    }
}

// Periodic data updates
async function updateData() {
    if (!isConnected) return;

    try {
        await loadWeather();
        await loadVessels();
    } catch (error) {
        console.error('❌ Periodic update failed:', error);
    }
}

// Handle data refresh from WebSocket
function handleDataRefresh(data) {
    console.log('📡 Data refresh notification:', data);
    showAlert('Data has been refreshed!', 'info');
}

// Handle vessel updates from WebSocket
function handleVesselUpdate(vesselData) {
    console.log('📡 Vessel update:', vesselData);
    // Update vessel positions on map
    loadVessels();
}

// Toggle vessel visibility
function toggleVessels() {
    // Implementation for toggling vessel markers on map
    console.log('Toggle vessels');
}

// Toggle weather overlay
function toggleWeather() {
    // Implementation for toggling weather overlays
    console.log('Toggle weather');
}

// Show loading modal
function showLoadingModal() {
    const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
    modal.show();
}

// Hide loading modal
function hideLoadingModal() {
    const modal = bootstrap.Modal.getInstance(document.getElementById('loadingModal'));
    if (modal) {
        modal.hide();
    }
}

// Show alert message
function showAlert(message, type = 'info') {
    // Simple alert implementation
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alertDiv);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Tab switching functionality
function showTab(tabName) {
    // Hide all tabs
    const tabs = document.querySelectorAll('.tab-pane');
    tabs.forEach(tab => {
        tab.style.display = 'none';
    });

    // Remove active class from all nav links
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.classList.remove('active');
    });

    // Show selected tab
    const selectedTab = document.getElementById(tabName + '-tab');
    if (selectedTab) {
        selectedTab.style.display = 'block';
    }

    // Add active class to clicked nav link
    const activeLink = document.querySelector(`[onclick="showTab('${tabName}')"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }

    // Initialize maps for specific tabs
    if (tabName === 'weather' && !weatherMap) {
        initWeatherMap();
    } else if (tabName === 'vessels' && !vesselsMap) {
        initVesselsMap();
    }

    console.log(`Switched to ${tabName} tab`);
}

// Initialize weather map
function initWeatherMap() {
    if (weatherMap) return;
    
    weatherMap = L.map('weather-map').setView([37.7749, -122.4194], 8);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18,
    }).addTo(weatherMap);

    // Add weather data visualization
    loadWeatherOverlay();
}

// Initialize vessels map
function initVesselsMap() {
    if (vesselsMap) return;
    
    vesselsMap = L.map('vessels-map').setView([37.7749, -122.4194], 8);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18,
    }).addTo(vesselsMap);

    // Load and display vessels
    loadVesselsOnMap();
}

// Load weather overlay on weather map
async function loadWeatherOverlay() {
    if (!weatherMap) return;
    
    try {
        const response = await fetch('/api/weather/current');
        const weather = await response.json();
        
        // Add weather marker
        const weatherIcon = L.divIcon({
            html: `<div class="weather-marker">
                <i class="fas fa-cloud-sun"></i>
                <div class="weather-info">
                    <div>Wind: ${weather.wind_speed_kts.toFixed(1)} kts</div>
                    <div>Waves: ${weather.wave_height_m.toFixed(1)}m</div>
                </div>
            </div>`,
            className: 'weather-icon',
            iconSize: [40, 40]
        });
        
        L.marker([37.7749, -122.4194], { icon: weatherIcon })
            .addTo(weatherMap)
            .bindPopup(`
                <strong>Current Weather</strong><br>
                Wind: ${weather.wind_speed_kts.toFixed(1)} kts @ ${weather.wind_direction_deg.toFixed(0)}°<br>
                Waves: ${weather.wave_height_m.toFixed(1)}m<br>
                Temp: ${weather.temperature_c.toFixed(1)}°C
            `);
            
    } catch (error) {
        console.error('Failed to load weather overlay:', error);
    }
}

// Load vessels on vessels map
async function loadVesselsOnMap() {
    if (!vesselsMap) return;
    
    try {
        const response = await fetch('/api/vessels/nearby');
        const data = await response.json();
        
        // Clear existing vessel markers
        vesselMarkers.forEach(marker => vesselsMap.removeLayer(marker));
        vesselMarkers = [];
        
        // Add vessel markers with different icons based on type
        data.vessels.forEach(vessel => {
            const vesselIcon = getVesselIcon(vessel);
            const marker = L.marker([vessel.latitude, vessel.longitude], { icon: vesselIcon })
                .addTo(vesselsMap)
                .bindPopup(`
                    <strong>${vessel.name || `MMSI: ${vessel.mmsi}`}</strong><br>
                    Speed: ${vessel.speed.toFixed(1)} kts<br>
                    Course: ${vessel.course.toFixed(0)}°<br>
                    Distance: ${vessel.distance_nm.toFixed(1)} nm
                `);
            
            vesselMarkers.push(marker);
        });
        
        // Fit map to show all vessels
        if (vesselMarkers.length > 0) {
            const group = new L.featureGroup(vesselMarkers);
            vesselsMap.fitBounds(group.getBounds().pad(0.1));
        }
        
    } catch (error) {
        console.error('Failed to load vessels on map:', error);
    }
}

// Get appropriate vessel icon based on vessel type
function getVesselIcon(vessel) {
    const vesselType = vessel.name ? vessel.name.toLowerCase() : '';
    let iconClass = 'fas fa-ship'; // Default
    
    if (vesselType.includes('tanker') || vesselType.includes('oil')) {
        iconClass = 'fas fa-oil-can';
    } else if (vesselType.includes('container') || vesselType.includes('cargo')) {
        iconClass = 'fas fa-box';
    } else if (vesselType.includes('ferry') || vesselType.includes('passenger')) {
        iconClass = 'fas fa-users';
    } else if (vesselType.includes('fishing')) {
        iconClass = 'fas fa-fish';
    }
    
    return L.divIcon({
        html: `<div class="vessel-marker ${iconClass}">
            <i class="${iconClass}"></i>
        </div>`,
        className: 'vessel-icon',
        iconSize: [30, 30]
    });
}

// Update vessel visualization on main map
function updateVesselMarkersOnMainMap(vessels) {
    // Clear existing vessel markers
    vesselMarkers.forEach(marker => map.removeLayer(marker));
    vesselMarkers = [];
    
    // Add new vessel markers
    vessels.forEach(vessel => {
        const vesselIcon = getVesselIcon(vessel);
        const marker = L.marker([vessel.latitude, vessel.longitude], { icon: vesselIcon })
            .addTo(map)
            .bindPopup(`
                <strong>${vessel.name || `MMSI: ${vessel.mmsi}`}</strong><br>
                Speed: ${vessel.speed.toFixed(1)} kts<br>
                Course: ${vessel.course.toFixed(0)}°<br>
                Distance: ${vessel.distance_nm.toFixed(1)} nm
            `);
        
        vesselMarkers.push(marker);
    });
}

// Load vessels on main map
async function loadVesselsOnMainMap() {
    try {
        const response = await fetch('/api/vessels/nearby');
        const data = await response.json();
        
        // Clear existing vessel markers
        vesselMarkers.forEach(marker => map.removeLayer(marker));
        vesselMarkers = [];
        
        // Add vessel markers with corrected positions (on water)
        data.vessels.forEach(vessel => {
            // Ensure vessel is positioned on water
            const correctedPosition = ensureWaterPosition(vessel.latitude, vessel.longitude);
            
            const vesselIcon = getVesselIcon(vessel);
            const marker = L.marker([correctedPosition.lat, correctedPosition.lon], { icon: vesselIcon })
                .addTo(map)
                .bindPopup(`
                    <strong>${vessel.name || `MMSI: ${vessel.mmsi}`}</strong><br>
                    Speed: ${vessel.speed.toFixed(1)} kts<br>
                    Course: ${vessel.course.toFixed(0)}°<br>
                    Distance: ${vessel.distance_nm.toFixed(1)} nm
                `);
            
            vesselMarkers.push(marker);
        });
        
        console.log(`✅ Loaded ${data.count} vessels on main map`);
        
    } catch (error) {
        console.error('❌ Failed to load vessels on main map:', error);
    }
}

// Ensure vessel position is on water
function ensureWaterPosition(lat, lon) {
    // Simple check: if vessel is too close to land, move it offshore
    
    // Check if position is in San Francisco Bay area
    if (lat > 37.7 && lat < 37.9 && lon > -122.5 && lon < -122.3) {
        // Move to center of bay if too close to shore
        if (lat > 37.8 || lon > -122.4) {
            return { lat: 37.7749, lon: -122.4194 };
        }
    }
    
    // Check if position is in LA area
    if (lat > 33.6 && lat < 34.0 && lon > -118.5 && lon < -118.0) {
        // Move to offshore position
        if (lat > 33.8 || lon > -118.3) {
            return { lat: 33.6846, lon: -118.2376 };
        }
    }
    
    // Default: return original position
    return { lat: lat, lon: lon };
}

// Update the loadVessels function to also update map markers
async function loadVessels(lat = 37.7749, lon = -122.4194, radius = 50) {
    try {
        const response = await fetch(`/api/vessels/nearby?lat=${lat}&lon=${lon}&radius_nm=${radius}`);
        const data = await response.json();

        updateVesselsDisplay(data.vessels);
        await loadVesselsOnMainMap();
        console.log(`✅ Loaded ${data.count} nearby vessels`);

    } catch (error) {
        console.error('❌ Failed to load vessels:', error);
    }
}

// Export functions for global access
window.initApp = initApp;
window.refreshData = refreshData;
window.loadWeather = loadWeather;
window.loadVessels = loadVessels;
window.toggleVessels = toggleVessels;
window.toggleWeather = toggleWeather;
window.showTab = showTab;
