# Project Requirements Document (PRD): Google Calendar Event Manager

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
1. **Cognito OAuth Enhancement**
   - Add `https://www.googleapis.com/auth/calendar` scope to Cognito OAuth configuration
   - Update OAuth redirect URIs for CloudFront domain
   - Configure PKCE flow for Calendar API access tokens
   - Test OAuth flow grants Calendar permissions

2. **Lambda@Edge JWT Validation**
   - Update `auth_handler.py.template` to validate Calendar API scopes in JWT
   - Add proper error responses for missing Calendar permissions
   - Implement Calendar API access token verification
   - Deploy and test Lambda@Edge function at CloudFront edge

3. **CDK Deployment Pipeline**
   - Update `generate_aws_exports.py` to include Calendar API configuration
   - Enhance `make deploy-converge` for Calendar API settings
   - Test end-to-end CDK deployment with Calendar functionality
   - Verify configuration drift detection includes Calendar API settings

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
1. **Google Calendar API Client**
   - Set up Google APIs JavaScript SDK in React app
   - Create Calendar API service layer with error handling
   - Implement retry logic for failed API requests
   - Add rate limiting and quota management

2. **Dedicated Calendar Management**
   - Create function to find existing "SFLT Events" calendar
   - Add functionality to create dedicated calendar if none exists
   - Implement calendar validation and permission checking
   - Handle calendar creation/access errors gracefully

3. **Event CRUD Operations**
   - Implement start event creation with metadata tagging
   - Add end event creation linked to start events via metadata
   - Build event editing and deletion functionality
   - Create event querying by type using Google Calendar metadata

4. **Authentication Integration** (depends on Stream A)
   - Integrate with Cognito PKCE OAuth tokens
   - Handle Calendar API authentication using JWT tokens
   - Implement token refresh logic for expired access
   - Add proper error handling for authentication failures

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
1. **Core UI Components** (with mock data)
   - Build simple EventList component showing start/end events
   - Create StartEventForm (title, date, time fields)
   - Create EndEventForm (title, date, time, linked start event selector)
   - Add EventItem component with edit/delete buttons
   - Implement basic loading states and error messages

2. **Authentication UI Integration** (depends on Stream A)
   - Integrate with Cognito PKCE OAuth flow
   - Add login/logout functionality
   - Handle authentication errors and re-authentication
   - Create protected route for calendar functionality

3. **Calendar API Integration** (depends on Stream B)
   - Connect UI components to Calendar API service
   - Implement real-time event data loading and updates
   - Add proper error handling for Calendar API failures
   - Create event linking UI showing start/end relationships

4. **UI Polish & Accessibility**
   - Add loading spinners and success/error notifications
   - Implement basic responsive design for mobile
   - Add keyboard navigation and ARIA labels
   - Create simple, clean visual design

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
1. **Authentication Flow Testing**
   - Extend existing Playwright tests for Calendar API OAuth
   - Test PKCE flow includes Calendar permissions
   - Verify Lambda@Edge JWT validation with Calendar scopes
   - Test authentication error scenarios

2. **Event Management Testing**
   - Test start event creation, editing, deletion
   - Test end event creation linked to start events
   - Verify event metadata and linking functionality
   - Test event list display and navigation

3. **Calendar API Integration Testing**
   - Test dedicated calendar creation/discovery
   - Verify events appear correctly in user's Google Calendar
   - Test Calendar API error handling and recovery
   - Validate real-time synchronization

4. **Security & Privacy Testing**
   - Verify no calendar data is stored in AWS services
   - Test that data only exists in user's Google Calendar
   - Audit network requests for data leakage
   - Validate proper token handling and expiration

5. **Cross-Browser & Performance Testing**
   - Test across Chrome, Firefox, Safari
   - Validate mobile responsiveness
   - Test performance with large numbers of events
   - Verify CloudFront caching and performance

## Parallel Execution Strategy

### Phase 1: Foundation (Week 1)
**Parallel Streams**:
- **Stream A**: Complete OAuth and Lambda@Edge setup
- **Stream B**: Build Calendar API client with mock auth
- **Stream C**: Build UI components with mock data
- **Stream D**: Prepare Playwright test framework extensions

### Phase 2: Integration (Week 2)
**Dependencies**:
- Stream A OAuth → Stream B real authentication
- Stream B API client → Stream C real data integration
- Streams A+B+C → Stream D full testing

### Phase 3: Testing & Polish (Week 3)
**Parallel Streams**:
- **Stream D**: Comprehensive Playwright testing
- **All Streams**: Bug fixes and performance optimization

## Claude Code Subagent Commands

### Stream A: AWS Infrastructure & Authentication
```bash
cd /Users/joshpeak/play/sflt-wt/aws-infrastructure
export AWS_PROFILE=sflt
```

**Claude Code Prompt**:
```
I am working on Stream A: AWS Infrastructure & Authentication for the Google Calendar project. 
Working directory: /Users/joshpeak/play/sflt-wt/aws-infrastructure
Branch: feature/aws-infrastructure

Tasks:
1. Update Cognito OAuth configuration to include Google Calendar API scopes
2. Enhance Lambda@Edge JWT validation for Calendar API tokens  
3. Update CDK deployment pipeline for Calendar API configuration
4. Test OAuth flow with Calendar permissions

Follow the PRD requirements for AWS CDK, CloudFront+S3+OAC, and PKCE OAuth with Lambda@Edge JWT validation.
```

### Stream B: Google Calendar API Integration
```bash
cd /Users/joshpeak/play/sflt-wt/calendar-api-integration
export AWS_PROFILE=sflt
```

**Claude Code Prompt**:
```
I am working on Stream B: Google Calendar API Integration for the minimal event manager.
Working directory: /Users/joshpeak/play/sflt-wt/calendar-api-integration  
Branch: feature/calendar-api-integration

Tasks:
1. Set up Google Calendar API client (frontend-only, no backend)
2. Implement dedicated calendar management (create/find 'SFLT Events' calendar)
3. Build start/end event CRUD operations with metadata linking
4. Integration with Cognito PKCE OAuth tokens

Use mock authentication initially, integrate real OAuth tokens when Stream A completes.
```

### Stream C: React UI Components  
```bash
cd /Users/joshpeak/play/sflt-wt/react-ui-components
export AWS_PROFILE=sflt
```

**Claude Code Prompt**:
```
I am working on Stream C: React UI Components for the minimal Calendar event manager.
Working directory: /Users/joshpeak/play/sflt-wt/react-ui-components
Branch: feature/react-ui-components

Tasks:
1. Build minimal event list UI (simple list, no calendar grid)
2. Create start event and end event forms
3. Add authentication integration with Cognito PKCE
4. Connect to Calendar API service from Stream B

Start with mock data, integrate real API when Stream B completes. Focus on minimal, functional UI.
```

### Stream D: Playwright E2E Testing
```bash
cd /Users/joshpeak/play/sflt-wt/playwright-testing
export AWS_PROFILE=sflt
```

**Claude Code Prompt**:
```
I am working on Stream D: Playwright E2E Testing for the Google Calendar integration.
Working directory: /Users/joshpeak/play/sflt-wt/playwright-testing
Branch: feature/playwright-testing

Tasks:
1. Extend existing Playwright framework for Calendar API OAuth testing
2. Add E2E tests for start/end event management
3. Test Google Calendar API integration and data privacy
4. Validate Lambda@Edge JWT validation with Calendar scopes

Build on existing e2e/ framework. Test against deployed CloudFront distribution.
```

## Integration & Coordination

### Daily Sync Commands
```bash
# Each worktree runs this to stay current:
cd /Users/joshpeak/play/sflt-wt/{branch-name}
git fetch origin
git merge origin/main
```

### Integration Testing
```bash
# When streams are ready to integrate:
cd /Users/joshpeak/play/sflt
git checkout -b integration/calendar-functionality

# Merge completed streams
git merge feature/aws-infrastructure
git merge feature/calendar-api-integration  
git merge feature/react-ui-components
git merge feature/playwright-testing

# Test integration
make install
make build
make deploy-converge
make test-e2e
```

### File Ownership by Stream
**Stream A**: `cdk/`, `scripts/generate_aws_exports.py`, `Makefile`
**Stream B**: `frontend/src/services/`, `frontend/src/hooks/`, Calendar API utilities
**Stream C**: `frontend/src/components/`, `frontend/src/pages/`, UI and authentication
**Stream D**: `e2e/tests/`, test utilities and Playwright extensions

## Success Criteria

1. **Authentication**: Users can successfully authenticate with Google OAuth and grant Calendar API permissions
2. **Calendar Management**: App creates/finds dedicated "SFLT Events" calendar automatically  
3. **Event Creation**: Users can create start events and optional linked end events
4. **Event Management**: Users can edit and delete their events
5. **Data Privacy**: Zero user calendar data stored by the application
6. **AWS CDK Deployment**: Full application deploys via CDK to CloudFront with S3 and OAC
7. **PKCE OAuth**: JWT validation at Lambda@Edge includes Calendar API scope verification
8. **Playwright Testing**: All functionality passes comprehensive E2E tests
9. **Performance**: Calendar operations perform well through CloudFront distribution

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