# Project Requirements Document (PRD): Google Calendar Event Manager - Version 2.0

## Executive Summary
Build a minimal React web application using **AWS Nx Plugin** that allows authenticated users to create and manage a single dedicated calendar in their Google account with only two types of events: "start" and "end" events. The application stores NO user data and acts purely as a frontend interface to Google Calendar.

## Key Insights from AWS Samples Research

### Prior Art Analysis
Research of AWS sample repositories revealed several relevant patterns:

1. **aws-samples/cloudfront-authorization-at-edge**: Comprehensive Lambda@Edge authentication with JWT cookies
2. **aws-samples/cloudfront-cognito-login**: CDK-based deployment with Google OAuth integration  
3. **aws-samples/authenticated-static-site**: Clean pattern for authenticated static sites

### Reusable Patterns Identified
- Modular Lambda@Edge function design for different auth stages
- JWT token management via secure cookies
- Automated configuration generation for frontend
- CDK constructs for reusable infrastructure components
- Runtime configuration pattern for dynamic API URLs

### AWS Nx Plugin Integration Opportunities
- **ts#react-website**: Modern React app with CloudScape design system
- **ts#react-website#auth**: Cognito authentication integration
- **ts#infra**: CDK infrastructure project structure
- **api-connection**: Seamless API integration patterns

## Revised Architecture Using AWS Nx Plugin

### Technology Stack Enhancement
- **Infrastructure**: AWS CDK via Nx Plugin generators
- **Frontend**: React with CloudScape (via ts#react-website generator)
- **Authentication**: Cognito with Google OAuth (via ts#react-website#auth generator)
- **Package Management**: pnpm for monorepo structure
- **Build System**: Nx targets with optimized caching

### Core Architecture Constraints
- **Nx Monorepo**: All projects managed in single workspace
- **AWS Nx Plugin**: Leverage generators for rapid scaffolding
- **CloudFront + S3 + OAC**: Static site deployment using latest Origin Access Control
- **PKCE OAuth + Lambda@Edge**: JWT validation at CloudFront edge locations
- **Serverless Only**: No backend servers, API Gateway, or databases
- **Zero Data Storage**: Application stores absolutely no user calendar data

## Enhanced Development Workstreams

### Stream A: Nx Workspace & Infrastructure Setup
**Lead Persona**: architect, devops  
**Dependencies**: None (foundation for all streams)
**Working Directory**: `/Users/joshpeak/play/sflt-wt/nx-workspace-setup`
**Branch**: `feature/nx-workspace-setup`

**Enhanced Deliverables**:
```
packages/infra/ - CDK infrastructure project (ts#infra generator)
packages/calendar-app/ - React website (ts#react-website generator)
packages/common/constructs/ - Shared CDK constructs
nx.json - Nx workspace configuration
package.json - Root package management
```

**Tasks**:

#### A.1: Nx Workspace Initialization
- **A.1.1**: Create new Nx workspace using aws-nx-mcp: `pnpm nx g @aws/nx-plugin:create-workspace --name=sflt-calendar`
- **A.1.2**: Configure workspace with TypeScript, ESLint, and Prettier standards
- **A.1.3**: Set up pnpm workspace configuration for optimized dependency management
- **A.1.4**: Configure Nx caching for build, test, and lint targets
- **A.1.5**: Create workspace documentation and development guidelines

#### A.2: Infrastructure Project Setup
- **A.2.1**: Generate CDK infrastructure project: `pnpm nx g @aws/nx-plugin:ts#infra --name=infra`
- **A.2.2**: Configure CDK project for multi-stack deployment (auth stack + static site stack)
- **A.2.3**: Set up AWS CDK bootstrap command for Nx target
- **A.2.4**: Create base application stack structure with proper dependency injection
- **A.2.5**: Configure CDK context for environment-specific deployments

#### A.3: React Website Generation
- **A.3.1**: Generate React website: `pnpm nx g @aws/nx-plugin:ts#react-website --name=calendar-app --enableTanstackRouter`
- **A.3.2**: Configure CloudScape design system with calendar-specific theming
- **A.3.3**: Set up Vite configuration for Google Calendar API integration
- **A.3.4**: Configure TypeScript strict mode and import path aliases
- **A.3.5**: Set up testing framework with React Testing Library

#### A.4: Authentication Integration
- **A.4.1**: Add Cognito auth to website: `pnpm nx g @aws/nx-plugin:ts#react-website#auth --project=calendar-app --cognitoDomain=sflt-calendar`
- **A.4.2**: Configure Google OAuth provider in Cognito with Calendar API scopes
- **A.4.3**: Enhance UserIdentity construct to include Google Calendar permissions
- **A.4.4**: Set up Lambda@Edge authentication with Calendar API scope validation
- **A.4.5**: Configure runtime configuration for Google Calendar API endpoints

### Stream B: Google Calendar API Service Layer
**Lead Persona**: frontend, backend
**Dependencies**: Stream A (A.3 for project structure)
**Working Directory**: `/Users/joshpeak/play/sflt-wt/nx-workspace-setup`
**Branch**: `feature/calendar-api-service`

**Enhanced Deliverables**:
```
packages/calendar-app/src/services/ - Calendar API service layer
packages/calendar-app/src/hooks/ - React hooks for Calendar operations
packages/calendar-app/src/types/ - TypeScript types for Calendar entities
packages/calendar-app/src/utils/ - Calendar utility functions
```

**Tasks**:

#### B.1: Google Calendar API Client Foundation
- **B.1.1**: Install Google APIs JavaScript SDK in React project workspace
- **B.1.2**: Create GoogleCalendarClient service with proper TypeScript types
- **B.1.3**: Implement OAuth token integration with Cognito JWT tokens
- **B.1.4**: Add comprehensive error handling with retry logic and rate limiting
- **B.1.5**: Create mock service implementation for development and testing
- **B.1.6**: Set up unit tests using Vitest (from Nx React website generator)

#### B.2: Calendar Management Service
- **B.2.1**: Create CalendarManager service for dedicated calendar operations
- **B.2.2**: Implement findOrCreateCalendar function for "SFLT Events" calendar
- **B.2.3**: Add calendar validation and permission checking
- **B.2.4**: Create calendar metadata management for app-specific configuration
- **B.2.5**: Implement calendar cleanup and reset functionality
- **B.2.6**: Add comprehensive error handling for calendar access issues

#### B.3: Event Management with Enhanced Metadata
- **B.3.1**: Design event metadata schema for start/end event linking
- **B.3.2**: Create EventManager service with full CRUD operations
- **B.3.3**: Implement event type validation and business rules
- **B.3.4**: Add event querying and filtering by metadata
- **B.3.5**: Create event relationship management (start-end linking)
- **B.3.6**: Implement bulk operations for efficient Calendar API usage

#### B.4: React Integration Layer
- **B.4.1**: Create useCalendarAPI hook with TanStack Query integration
- **B.4.2**: Implement useEventManager hook for event CRUD operations
- **B.4.3**: Add useCalendarStatus hook for connection and permission monitoring
- **B.4.4**: Create error boundary integration for graceful error handling
- **B.4.5**: Implement optimistic updates with automatic rollback
- **B.4.6**: Add comprehensive hook testing with React Testing Library

### Stream C: CloudScape UI Components
**Lead Persona**: frontend, design
**Dependencies**: Stream A (A.3, A.4), Stream B (for service integration)
**Working Directory**: `/Users/joshpeak/play/sflt-wt/nx-workspace-setup`
**Branch**: `feature/cloudscape-ui`

**Enhanced Deliverables**:
```
packages/calendar-app/src/components/ - CloudScape component implementations
packages/calendar-app/src/routes/ - TanStack Router route components
packages/calendar-app/src/layouts/ - Application layout components
packages/calendar-app/src/styles/ - CloudScape theme customizations
```

**Tasks**:

#### C.1: CloudScape Layout Integration
- **C.1.1**: Enhance generated AppLayout for calendar application navigation
- **C.1.2**: Create calendar-specific navigation structure using CloudScape TopNavigation
- **C.1.3**: Implement responsive layout with CloudScape SideNavigation
- **C.1.4**: Add breadcrumb navigation for deep linking
- **C.1.5**: Create theme customization for calendar application branding

#### C.2: Event Management Components
- **C.2.1**: Create EventTable component using CloudScape Table with filtering
- **C.2.2**: Build StartEventModal using CloudScape Modal and Form components
- **C.2.3**: Implement EndEventModal with start event linking interface
- **C.2.4**: Create EventDetailPanel using CloudScape ExpandableSection
- **C.2.5**: Add bulk action components using CloudScape MultiSelect

#### C.3: TanStack Router Implementation
- **C.3.1**: Implement route structure: `/`, `/events`, `/events/create`, `/events/:id`
- **C.3.2**: Create route guards for authentication using TanStack Router
- **C.3.3**: Add route-based data loading with proper loading states
- **C.3.4**: Implement deep linking for event filtering and search
- **C.3.5**: Add route-based error boundaries with CloudScape Alert components

#### C.4: Authentication UI Integration
- **C.4.1**: Integrate Cognito authentication with CloudScape components
- **C.4.2**: Create authentication status indicator in TopNavigation
- **C.4.3**: Implement login/logout flows using generated auth components
- **C.4.4**: Add Calendar permission status display and re-authorization flow
- **C.4.5**: Create user profile display with Calendar connection status

### Stream D: Enhanced E2E Testing with Nx
**Lead Persona**: qa
**Dependencies**: All streams for comprehensive testing
**Working Directory**: `/Users/joshpeak/play/sflt-wt/nx-workspace-setup`
**Branch**: `feature/enhanced-e2e-testing`

**Enhanced Deliverables**:
```
packages/calendar-app-e2e/ - Dedicated E2E testing project
packages/calendar-app-e2e/src/support/ - Test utilities and fixtures
packages/calendar-app-e2e/src/e2e/ - E2E test specifications
packages/calendar-app-e2e/project.json - Nx E2E project configuration
```

**Tasks**:

#### D.1: Nx E2E Project Setup
- **D.1.1**: Generate E2E project: `pnpm nx g @nx/cypress:configuration --project=calendar-app`
- **D.1.2**: Configure Cypress for CloudScape component testing
- **D.1.3**: Set up test data management and cleanup utilities
- **D.1.4**: Create page object models for major application areas
- **D.1.5**: Configure cross-browser testing with different viewport sizes

#### D.2: Authentication and Authorization Testing
- **D.2.1**: Test complete Cognito OAuth flow with Google Calendar permissions
- **D.2.2**: Validate JWT token handling and automatic refresh
- **D.2.3**: Test authentication persistence across browser sessions
- **D.2.4**: Verify proper handling of expired or revoked tokens
- **D.2.5**: Test authorization failures and re-authentication flows

#### D.3: Calendar Integration Testing
- **D.3.1**: Test dedicated calendar creation and discovery
- **D.3.2**: Validate event creation and synchronization with Google Calendar
- **D.3.3**: Test event editing and deletion workflows
- **D.3.4**: Verify event metadata and linking functionality
- **D.3.5**: Test Calendar API error scenarios and recovery

#### D.4: CloudScape UI Testing
- **D.4.1**: Test responsive design across different screen sizes
- **D.4.2**: Validate CloudScape component accessibility compliance
- **D.4.3**: Test keyboard navigation and screen reader compatibility
- **D.4.4**: Verify CloudScape theming and visual consistency
- **D.4.5**: Test performance with large event datasets

## AWS Nx Plugin Leveraged Patterns

### Generator Usage Strategy
1. **Foundation Generators**: Use `ts#infra` and `ts#react-website` for base structure
2. **Enhancement Generators**: Apply `ts#react-website#auth` for authentication
3. **Connection Patterns**: Use patterns from `api-connection` for service integration
4. **Testing Integration**: Leverage Nx testing targets and configurations

### Nx Targets and Caching
- **Build Targets**: Optimized build caching across all projects
- **Test Targets**: Parallel test execution with dependency awareness
- **Lint Targets**: Shared linting rules across TypeScript and React projects
- **Deploy Targets**: CDK deployment with proper dependency ordering

### Shared Libraries Pattern
- **Common Constructs**: Reusable CDK constructs in `packages/common/constructs`
- **Shared Types**: TypeScript interfaces shared between frontend and infrastructure
- **Utility Libraries**: Common utilities for Calendar API integration

## Implementation Benefits

### From AWS Samples
- **Proven Patterns**: Lambda@Edge authentication patterns from AWS samples
- **CDK Best Practices**: Infrastructure as code patterns from sample repositories
- **Security Patterns**: JWT handling and secure token management

### From AWS Nx Plugin
- **Rapid Scaffolding**: 70%+ reduction in initial setup time
- **Built-in Best Practices**: CloudScape design system, proper TypeScript configuration
- **Monorepo Benefits**: Shared dependencies, optimized builds, coordinated testing
- **Runtime Configuration**: Automatic configuration generation for deployed resources

## Migration Strategy from Current Implementation

### Phase 1: Nx Workspace Migration
1. Create new Nx workspace alongside current implementation
2. Generate infrastructure and React projects using aws-nx-mcp
3. Migrate existing CDK code to new Nx infrastructure project
4. Port current React implementation to new CloudScape-based structure

### Phase 2: Service Layer Enhancement
1. Implement new Google Calendar API service layer
2. Add comprehensive error handling and retry logic
3. Create React hooks for optimal state management
4. Implement comprehensive testing suite

### Phase 3: UI Enhancement
1. Migrate to CloudScape components for professional appearance
2. Implement TanStack Router for improved navigation
3. Add comprehensive authentication integration
4. Enhance responsive design and accessibility

### Phase 4: Testing and Deployment
1. Implement comprehensive E2E testing with Nx patterns
2. Set up optimized build and deployment pipelines
3. Add monitoring and observability
4. Complete migration validation

## Success Criteria

1. **Nx Integration**: Successful workspace with optimized build caching and shared libraries
2. **CloudScape UI**: Professional-grade interface using AWS design system
3. **Enhanced Authentication**: Robust Cognito integration with Google Calendar permissions
4. **Calendar Management**: Seamless Google Calendar API integration with proper error handling
5. **Testing Coverage**: Comprehensive E2E testing with parallel execution
6. **Performance**: Sub-3s load times with optimized bundle sizes
7. **Developer Experience**: Rapid development iteration with Nx tooling
8. **Maintenance**: Clean architecture enabling easy feature additions

## Technical Architecture Enhanced

```
User Browser
    ↓ (PKCE OAuth + Calendar Scopes)
Cognito + Google OAuth (UserIdentity Construct)
    ↓ (JWT with Calendar API tokens)
CloudFront Distribution (StaticWebsite Construct)
    ↓ (JWT validation)
Lambda@Edge (Enhanced auth validation)
    ↓ (CloudScape React SPA)
S3 Bucket (Nx build artifacts)
    ↓ (Direct API calls with retry logic)
Google Calendar API (Service layer with hooks)
```

## File Structure with Nx

```
sflt-calendar/
├── nx.json                          # Nx workspace configuration
├── package.json                     # Root dependency management
├── packages/
│   ├── calendar-app/                # React website (ts#react-website)
│   │   ├── src/
│   │   │   ├── components/          # CloudScape components
│   │   │   ├── routes/              # TanStack Router routes  
│   │   │   ├── services/            # Google Calendar API layer
│   │   │   ├── hooks/               # React hooks for Calendar ops
│   │   │   └── types/               # TypeScript type definitions
│   │   └── project.json             # Nx project configuration
│   ├── calendar-app-e2e/            # E2E testing project
│   ├── infra/                       # CDK infrastructure (ts#infra)
│   │   ├── src/stacks/              # CDK stack definitions
│   │   └── project.json             # Nx project configuration
│   └── common/
│       └── constructs/              # Shared CDK constructs
│           ├── user-identity.ts     # Generated auth construct
│           └── static-website.ts    # Enhanced website construct
└── tools/                           # Nx workspace tools and scripts
```