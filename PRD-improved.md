# Project Requirements Document (PRD): Google Calendar Event Manager - Improved Version

## Executive Summary
Build a minimal React web application deployed via AWS CDK that allows authenticated users to create and manage a single dedicated calendar in their Google account with only two types of events: "start" and "end" events. The application stores NO user data and acts purely as a frontend interface to Google Calendar.

## Core Architecture Constraints
- **AWS CDK Infrastructure**: All infrastructure managed via AWS CDK (Python)
- **CloudFront + S3 + OAC**: Static site deployment using latest Origin Access Control
- **PKCE OAuth + Lambda@Edge**: JWT validation at CloudFront edge locations
- **Serverless Only**: No backend servers, API Gateway, or databases
- **Zero Data Storage**: Application stores absolutely no user calendar data

## Project Goals
- **Primary Goal**: Frontend to manage logged-in user's Google Calendar
- **Event Types**: Only "start" events and optional "end" events
- **Calendar Scope**: Single dedicated calendar ("SFLT Events") in user's Google account
- **Data Philosophy**: No data storage - pure frontend to user's own Google Calendar data
- **Authentication**: Google OAuth integration via AWS Cognito with PKCE flow

## Development Workstreams for Parallel Execution

### Stream A: AWS Infrastructure & Authentication
**Lead Persona**: backend, architect  
**Dependencies**: None (can start immediately)
**Working Directory**: `/Users/joshpeak/play/sflt-wt/aws-infrastructure`
**Branch**: `feature/aws-infrastructure`

**Deliverables**:
```
cdk/auth_stack.py - Enhanced Cognito configuration
cdk/lambda-edge/auth_handler.py.template - Calendar API JWT validation
scripts/generate_aws_exports.py - Calendar API configuration generation
Makefile - Updated deployment pipeline
```

**Tasks**:

#### A.1: Cognito OAuth Configuration Enhancement
- **A.1.1**: Add Google Calendar API scope (`https://www.googleapis.com/auth/calendar`) to existing Cognito OAuth configuration in `cdk/auth_stack.py`
- **A.1.2**: Update OAuth redirect URIs in Cognito to support CloudFront domain patterns
- **A.1.3**: Configure PKCE flow settings specifically for Calendar API access tokens
- **A.1.4**: Create unit test to verify OAuth configuration includes Calendar scope
- **A.1.5**: Add validation script to test OAuth flow grants Calendar permissions

#### A.2: Lambda@Edge JWT Validation Updates
- **A.2.1**: Modify `auth_handler.py.template` to extract Calendar API scopes from JWT claims
- **A.2.2**: Add validation logic to check for required Calendar API scope in JWT
- **A.2.3**: Implement error response (401) for requests missing Calendar permissions
- **A.2.4**: Add Calendar API access token verification logic to Lambda function
- **A.2.5**: Create unit tests for JWT validation with Calendar scopes
- **A.2.6**: Write deployment script to update Lambda@Edge function version

#### A.3: CDK Deployment Pipeline Enhancement
- **A.3.1**: Modify `generate_aws_exports.py` to add Calendar API configuration section
- **A.3.2**: Add Calendar API client ID and scopes to exported configuration
- **A.3.3**: Update `make deploy-converge` command to handle Calendar API settings
- **A.3.4**: Add configuration drift detection for Calendar API settings
- **A.3.5**: Create validation script to verify generated aws-exports.js includes Calendar config
- **A.3.6**: Write integration test for end-to-end CDK deployment with Calendar functionality

### Stream B: Google Calendar API Integration
**Lead Persona**: frontend
**Dependencies**: Can start with mock auth, real integration needs Stream A OAuth
**Working Directory**: `/Users/joshpeak/play/sflt-wt/calendar-api-integration`
**Branch**: `feature/calendar-api-integration`

**Deliverables**:
```
frontend/src/services/GoogleCalendarClient.js - API client wrapper
frontend/src/services/CalendarManager.js - Dedicated calendar operations
frontend/src/services/EventManager.js - Start/end event CRUD
frontend/src/utils/EventMetadata.js - Event linking utilities
frontend/src/hooks/useCalendarAPI.js - React hooks for Calendar operations
```

**Tasks**:

#### B.1: Google Calendar API Client Setup
- **B.1.1**: Install Google APIs JavaScript SDK (`gapi`) in React app via npm
- **B.1.2**: Create `GoogleCalendarClient.js` with initialization logic for gapi client
- **B.1.3**: Implement loadGoogleAPI function with proper error handling
- **B.1.4**: Add retry logic with exponential backoff for failed API requests
- **B.1.5**: Implement rate limiting to stay within Google Calendar API quotas
- **B.1.6**: Create mock Calendar API client for development/testing
- **B.1.7**: Add unit tests for API client initialization and error handling

#### B.2: Dedicated Calendar Management Functions
- **B.2.1**: Create `CalendarManager.js` with findCalendar function to search for "SFLT Events" calendar
- **B.2.2**: Implement createCalendar function to create "SFLT Events" calendar if not found
- **B.2.3**: Add getOrCreateCalendar function that combines find and create logic
- **B.2.4**: Implement validateCalendarPermissions function to check user has write access
- **B.2.5**: Add error handling for insufficient permissions scenarios
- **B.2.6**: Create getCalendarId helper function to cache calendar ID
- **B.2.7**: Write unit tests for all calendar management functions

#### B.3: Event CRUD Operations Implementation
- **B.3.1**: Create `EventManager.js` with createStartEvent function
- **B.3.2**: Implement event metadata structure for start events (type: "start", id: unique)
- **B.3.3**: Add createEndEvent function with linked start event ID in metadata
- **B.3.4**: Implement getEventsByType function to filter events by metadata type
- **B.3.5**: Create updateEvent function for editing existing events
- **B.3.6**: Add deleteEvent function with proper error handling
- **B.3.7**: Implement getLinkedEvents function to find end events for a start event
- **B.3.8**: Write unit tests for all CRUD operations

#### B.4: Event Metadata and Linking Utilities
- **B.4.1**: Create `EventMetadata.js` with metadata schema definition
- **B.4.2**: Implement generateEventId function for unique event identifiers
- **B.4.3**: Add parseEventMetadata function to extract custom metadata from events
- **B.4.4**: Create linkEvents function to establish start-end event relationships
- **B.4.5**: Implement validateEventLink function to ensure valid relationships
- **B.4.6**: Add metadata migration function for future schema changes
- **B.4.7**: Write unit tests for metadata operations

#### B.5: React Hooks for Calendar Operations
- **B.5.1**: Create `useCalendarAPI.js` with useCalendarClient hook
- **B.5.2**: Implement useCalendarEvents hook for real-time event fetching
- **B.5.3**: Add useEventMutations hook for create/update/delete operations
- **B.5.4**: Create useCalendarStatus hook for connection and permission status
- **B.5.5**: Implement error boundary integration for Calendar API failures
- **B.5.6**: Write hook tests using React Testing Library

#### B.6: Authentication Integration (depends on Stream A)
- **B.6.1**: Integrate useCalendarClient with Cognito PKCE OAuth tokens
- **B.6.2**: Implement token injection into Google API client requests
- **B.6.3**: Add token refresh logic when access token expires
- **B.6.4**: Create re-authentication flow for revoked permissions
- **B.6.5**: Implement logout cleanup for Calendar API client
- **B.6.6**: Write integration tests for auth flow

### Stream C: React UI Components
**Lead Persona**: frontend, design
**Dependencies**: Can work with mock data initially, real integration needs Stream B
**Working Directory**: `/Users/joshpeak/play/sflt-wt/react-ui-components`
**Branch**: `feature/react-ui-components`

**Deliverables**:
```
frontend/src/components/EventList.jsx - Simple list of start/end events
frontend/src/components/StartEventForm.jsx - Form for creating start events
frontend/src/components/EndEventForm.jsx - Form for creating end events linked to start
frontend/src/components/EventItem.jsx - Individual event display with edit/delete
frontend/src/components/AuthenticatedCalendarApp.jsx - Main calendar app container
frontend/src/hooks/useAuthState.js - Authentication state management
```

**Tasks**:

#### C.1: Event List Component Development
- **C.1.1**: Create `EventList.jsx` component structure with TypeScript interfaces
- **C.1.2**: Implement basic event list rendering with mock data
- **C.1.3**: Add event type filtering (show start events, end events, or both)
- **C.1.4**: Implement event sorting by date/time
- **C.1.5**: Add empty state UI when no events exist
- **C.1.6**: Create loading skeleton UI for async data loading
- **C.1.7**: Implement error state UI for failed data fetching
- **C.1.8**: Write component tests with mock data

#### C.2: Start Event Form Component
- **C.2.1**: Create `StartEventForm.jsx` with form structure
- **C.2.2**: Add title input field with validation (required, max length)
- **C.2.3**: Implement date picker component/integration
- **C.2.4**: Add time picker with 15-minute intervals
- **C.2.5**: Create form submission handler with loading state
- **C.2.6**: Add success notification on event creation
- **C.2.7**: Implement form reset after successful submission
- **C.2.8**: Write form validation and submission tests

#### C.3: End Event Form Component
- **C.3.1**: Create `EndEventForm.jsx` with form structure
- **C.3.2**: Add start event selector dropdown (required field)
- **C.3.3**: Implement title, date, and time fields similar to start form
- **C.3.4**: Add validation to ensure end time is after linked start time
- **C.3.5**: Create visual indicator showing linked start event details
- **C.3.6**: Implement form submission with event linking logic
- **C.3.7**: Add auto-population of end date based on start event
- **C.3.8**: Write component tests including link validation

#### C.4: Event Item Component
- **C.4.1**: Create `EventItem.jsx` with event display layout
- **C.4.2**: Add event type indicator (start/end badge or icon)
- **C.4.3**: Implement collapsible details section
- **C.4.4**: Add edit button that opens inline edit form
- **C.4.5**: Create delete button with confirmation dialog
- **C.4.6**: Show linked event information for end events
- **C.4.7**: Add visual link indicator between related events
- **C.4.8**: Write component tests for all interactions

#### C.5: Main Calendar App Container
- **C.5.1**: Create `AuthenticatedCalendarApp.jsx` as main container
- **C.5.2**: Implement tab/section navigation (Events, Create Start, Create End)
- **C.5.3**: Add authentication check and redirect logic
- **C.5.4**: Create layout with header showing user info and logout
- **C.5.5**: Implement responsive grid layout for components
- **C.5.6**: Add global error boundary for Calendar API errors
- **C.5.7**: Write integration tests for navigation flow

#### C.6: Authentication State Management
- **C.6.1**: Create `useAuthState.js` hook for auth status
- **C.6.2**: Implement isAuthenticated, user, and loading states
- **C.6.3**: Add login and logout action functions
- **C.6.4**: Create token storage/retrieval logic
- **C.6.5**: Implement automatic token refresh mechanism
- **C.6.6**: Add authentication error handling
- **C.6.7**: Write hook tests for auth flows

#### C.7: UI Polish and Accessibility
- **C.7.1**: Add CSS modules or styled-components setup
- **C.7.2**: Implement consistent color scheme and typography
- **C.7.3**: Add loading spinners for all async operations
- **C.7.4**: Create toast notifications for success/error messages
- **C.7.5**: Implement keyboard navigation for all interactive elements
- **C.7.6**: Add ARIA labels and roles for screen readers
- **C.7.7**: Create mobile-responsive layouts with breakpoints
- **C.7.8**: Write accessibility tests using jest-axe

### Stream D: Playwright E2E Testing
**Lead Persona**: qa
**Dependencies**: Extends existing Playwright framework, needs deployed app from other streams
**Working Directory**: `/Users/joshpeak/play/sflt-wt/playwright-testing`
**Branch**: `feature/playwright-testing`

**Deliverables**:
```
e2e/tests/calendar-authentication.spec.js - OAuth + Calendar API access tests
e2e/tests/event-management.spec.js - Start/end event CRUD tests
e2e/tests/calendar-integration.spec.js - Google Calendar API integration tests
e2e/tests/security-privacy.spec.js - Data privacy and security validation
e2e/helpers/calendar-test-utils.js - Shared test utilities
```

**Tasks**:

#### D.1: Authentication Flow E2E Tests
- **D.1.1**: Create `calendar-authentication.spec.js` test file structure
- **D.1.2**: Write test for Google OAuth login flow with Calendar scope
- **D.1.3**: Add test to verify Calendar API permissions granted
- **D.1.4**: Implement test for PKCE flow token exchange
- **D.1.5**: Create test for JWT validation at Lambda@Edge
- **D.1.6**: Add test for authentication persistence across page refreshes
- **D.1.7**: Write test for logout flow and token cleanup
- **D.1.8**: Implement test for re-authentication after token expiry

#### D.2: Event Management E2E Tests
- **D.2.1**: Create `event-management.spec.js` test file
- **D.2.2**: Write test for creating a start event
- **D.2.3**: Add test for creating an end event linked to start
- **D.2.4**: Implement test for editing existing events
- **D.2.5**: Create test for deleting events with confirmation
- **D.2.6**: Add test for event list display and filtering
- **D.2.7**: Write test for event validation errors
- **D.2.8**: Implement test for handling Calendar API errors

#### D.3: Calendar Integration Tests
- **D.3.1**: Create `calendar-integration.spec.js` test file
- **D.3.2**: Write test for automatic "SFLT Events" calendar creation
- **D.3.3**: Add test to verify events appear in Google Calendar
- **D.3.4**: Implement test for real-time synchronization
- **D.3.5**: Create test for handling calendar permission errors
- **D.3.6**: Add test for Calendar API quota handling
- **D.3.7**: Write test for event metadata persistence
- **D.3.8**: Implement test for linked events relationship

#### D.4: Security and Privacy Tests
- **D.4.1**: Create `security-privacy.spec.js` test file
- **D.4.2**: Write test to verify no data stored in S3/CloudFront logs
- **D.4.3**: Add network traffic audit test for data leakage
- **D.4.4**: Implement test for proper JWT token handling
- **D.4.5**: Create test for secure token storage in browser
- **D.4.6**: Add test for protected route access without auth
- **D.4.7**: Write test for XSS prevention in event data
- **D.4.8**: Implement test for CORS and CSP headers

#### D.5: Test Utilities Development
- **D.5.1**: Create `calendar-test-utils.js` with helper functions
- **D.5.2**: Implement mock OAuth flow helper
- **D.5.3**: Add event creation helper functions
- **D.5.4**: Create calendar API response mocking utilities
- **D.5.5**: Implement wait helpers for async operations
- **D.5.6**: Add screenshot capture for test failures
- **D.5.7**: Create test data generators for events
- **D.5.8**: Write cleanup utilities for test isolation

#### D.6: Cross-Browser and Performance Tests
- **D.6.1**: Configure Playwright for Chrome, Firefox, Safari testing
- **D.6.2**: Create browser-specific test configurations
- **D.6.3**: Write responsive design tests for mobile viewports
- **D.6.4**: Implement performance metric collection tests
- **D.6.5**: Add CloudFront caching verification tests
- **D.6.6**: Create tests for slow network conditions
- **D.6.7**: Write tests for large event list performance
- **D.6.8**: Implement accessibility audit tests

## Task Dependencies and Prerequisites

### Prerequisites by Stream

#### Stream A Prerequisites
- AWS account with appropriate IAM permissions
- AWS CDK CLI installed and bootstrapped
- Understanding of Cognito OAuth configuration
- Knowledge of Lambda@Edge constraints

#### Stream B Prerequisites
- Google Cloud Console project with Calendar API enabled
- Understanding of Google Calendar API v3
- Knowledge of OAuth 2.0 and PKCE flow
- JavaScript/React development environment

#### Stream C Prerequisites
- React development environment setup
- Understanding of React hooks and component lifecycle
- Basic knowledge of form validation
- CSS/styling framework decision made

#### Stream D Prerequisites
- Playwright installed with browsers
- Understanding of E2E testing best practices
- Access to deployed CloudFront URL
- Knowledge of async testing patterns

### Critical Path Dependencies

1. **B.6** (Authentication Integration) depends on **A.1** completion
2. **C.5** (Main App Container) depends on **C.6** (Auth State)
3. **C.3** (End Event Form) depends on **B.3** (Event CRUD)
4. **D.1-D.4** depend on at least one deployed feature from Streams A-C
5. **Integration testing** requires all streams to merge

## Success Criteria by Task

Each task should be considered complete when:
1. Code is written and passes linting
2. Unit tests are written and passing
3. Integration with mock data works
4. Code is committed to feature branch
5. Documentation/comments are added
6. Peer review feedback addressed

## Technical Architecture

```
User Browser
    ↓ (PKCE OAuth + Calendar Scopes)
Cognito + Google OAuth
    ↓ (JWT with Calendar API tokens)
CloudFront Distribution
    ↓ (JWT validation)
Lambda@Edge (auth_handler.py)
    ↓ (Static assets only)
S3 Bucket (React SPA)
    ↓ (Direct API calls)
Google Calendar API
```

## Infrastructure Constraints

- **AWS CDK (Python)**: All infrastructure as code
- **CloudFront + S3 + OAC**: Static site hosting with latest Origin Access Control  
- **Lambda@Edge**: JWT validation and route protection only
- **No backend servers**: No EC2, ECS, Lambda functions (except Lambda@Edge)
- **No databases**: No RDS, DynamoDB, or any data storage
- **No API Gateway**: Direct frontend to Google Calendar API integration
- **Cognito + PKCE**: OAuth flow with Google Calendar API scopes
- **Minimal UI**: Simple event list and forms, no complex calendar grids
- **Two event types only**: Start events and end events with metadata linking