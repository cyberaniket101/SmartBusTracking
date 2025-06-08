# Smart Bus Tracking System - Mobile Integration

## Mobile API Documentation

This document describes the API endpoints available for the mobile application to integrate with the Smart Bus Tracking System backend.

### Base URL

All API endpoints are available under the following base URL:
```
/api/mobile
```

### Authentication

Most endpoints require authentication. The mobile app should:
1. Register users via the `/api/mobile/user/register` endpoint
2. Log in users via the `/api/mobile/user/login` endpoint
3. Include authentication cookies in subsequent requests

### Available Endpoints

#### Bus Information

- `GET /api/mobile/buses` - Get all active buses with current location and status
- `GET /api/mobile/buses/{bus_id}/telemetry?hours=1` - Get historical telemetry data for a specific bus (past 1-24 hours)

#### Routes and Stops

- `GET /api/mobile/routes` - Get all active routes with their stops
- `GET /api/mobile/stops/{stop_id}/eta` - Get ETAs for all buses arriving at a specific stop

#### User Management

- `POST /api/mobile/user/register` - Register a new user account
  - Required: `username`, `email`, `password`
  - Optional: `fcm_token` (for push notifications)

- `POST /api/mobile/user/login` - Log in an existing user
  - Required: `username`, `password`
  - Optional: `fcm_token`

- `GET /api/mobile/user/subscriptions` - Get all bus subscriptions for the current user (requires login)

- `POST /api/mobile/user/subscribe` - Subscribe to receive notifications for a bus at a stop (requires login)
  - Required: `bus_id`, `stop_id`
  - Optional: `notify_on_approach`, `notify_on_delay`, `approach_distance_km`

- `DELETE /api/mobile/user/unsubscribe/{subscription_id}` - Unsubscribe from bus notifications (requires login)

- `POST /api/mobile/user/update-token` - Update FCM token for push notifications (requires login)
  - Required: `fcm_token`

### Push Notifications

The system supports two types of push notifications:
1. **Approach notifications**: When a bus is approaching a stop within the configured distance
2. **Delay notifications**: When a bus is delayed beyond the configured threshold

To receive push notifications, the mobile app must:
1. Register the user with an FCM token
2. Subscribe the user to specific bus/stop combinations
3. Handle incoming FCM notifications in the app

### Data Formats

All responses are in JSON format. Here's an example of a bus object:

```json
{
  "id": 1,
  "bus_number": "B001",
  "latitude": 19.8762,
  "longitude": 75.3433,
  "speed": 25.5,
  "heading": 90,
  "last_updated": "2025-05-25T17:15:30Z",
  "route": {
    "id": 3,
    "route_number": "R103",
    "name": "City Center to East End"
  },
  "next_stop": {
    "id": 7,
    "name": "East Market",
    "code": "EM01",
    "latitude": 19.8800,
    "longitude": 75.3500,
    "eta": "2025-05-25T17:20:00Z",
    "is_delayed": false,
    "delay_minutes": 0
  },
  "capacity": 50,
  "license_plate": "MH-20 AB 1234"
}
```

## Mobile App Development Guidelines

When developing the mobile app to connect to this backend:

1. **Implement Real-time Updates**:
   - Poll the bus locations every 5-10 seconds for real-time tracking
   - Use WebSockets for future real-time updates implementation

2. **Handle Authentication**:
   - Securely store user credentials
   - Implement auto-login functionality 
   - Handle token refresh and session expiration

3. **Offline Support**:
   - Cache route and stop information for offline use
   - Store user preferences locally

4. **Push Notifications**:
   - Integrate Firebase Cloud Messaging (FCM)
   - Handle notification permissions properly
   - Display notification content appropriately

5. **Map Integration**:
   - Use Google Maps or another mapping solution
   - Display bus locations, routes, and stops
   - Implement real-time updates on the map

6. **Error Handling**:
   - Implement proper error handling for API failures
   - Show user-friendly error messages
   - Add retry mechanisms for unreliable network conditions