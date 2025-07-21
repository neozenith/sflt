# Implementation Roadmap: Google Calendar Event Manager with AWS Nx Plugin

## Executive Summary

This roadmap provides a comprehensive implementation strategy for completing the Google Calendar Event Manager project, integrating insights from AWS samples research, aws-nx-mcp capabilities, and current project analysis. The approach balances rapid feature delivery with architectural excellence.

## Strategic Decision: Hybrid Enhancement Approach

**Recommendation**: Proceed with **enhanced current architecture** rather than full Nx migration.

### Rationale
1. **Current infrastructure is 80% complete** and production-ready
2. **Lambda@Edge blocker requires resolution** regardless of architecture choice
3. **Google Calendar integration is the primary business objective**
4. **CloudScape enhancement can be added incrementally**
5. **Full Nx migration can be evaluated post-delivery**

### Implementation Strategy
- **Phase 1**: Resolve current blockers and add Calendar integration
- **Phase 2**: Enhance UI with CloudScape patterns (selective Nx adoption)
- **Phase 3**: Evaluate full Nx migration based on Phase 1-2 results

---

## Phase 1: Foundation Stabilization (2-3 weeks)

### Week 1: Critical Blocker Resolution

#### Epic 1.1: Lambda@Edge Deployment Fix
**Priority**: Critical | **Effort**: 1 week | **Status**: BLOCKED

**1.1.1 Investigate Cross-Region Export Conflicts**
```bash
# Analysis tasks
aws cloudformation describe-stacks --region us-east-1 --stack-name SfltStaticSiteStack
aws cloudformation describe-stacks --region ap-southeast-2 --stack-name SfltAuthStack
uv run scripts/analyze_lambda_edge_issue.py
```

**Root Cause Analysis**:
- CDK cross-region exports from ap-southeast-2 to us-east-1
- Lambda@Edge function references causing circular dependencies
- CloudFormation stack output dependencies

**1.1.2 Implement Stack Restructuring**
```python
# Proposed CDK fix pattern from AWS samples
class LambdaEdgeStack(Stack):
    def __init__(self, scope, id, **kwargs):
        # Move Lambda@Edge to independent stack in us-east-1
        super().__init__(scope, id, env=Environment(region='us-east-1'), **kwargs)
        
        # Use Parameter imports instead of cross-region exports
        user_pool_id = CfnParameter(self, 'UserPoolId')
        client_id = CfnParameter(self, 'ClientId')
        
        # Create Lambda function with parameters
        self.auth_function = Function(...)

class StaticSiteStack(Stack):
    def __init__(self, scope, id, lambda_function_arn, **kwargs):
        # Reference Lambda via ARN parameter
        auth_function = Function.from_function_arn(
            self, 'AuthFunction', lambda_function_arn
        )
```

**1.1.3 Deploy and Validate Fix**
```bash
# Sequential deployment approach
make deploy-lambda-edge  # Deploy Lambda@Edge first
make deploy-static-site  # Deploy CloudFront with Lambda reference
make test-e2e           # Validate complete flow
```

### Week 2: Google Calendar OAuth Enhancement

#### Epic 1.2: Cognito OAuth Scope Addition
**Priority**: High | **Effort**: 3-4 days

**1.2.1 Update Cognito Configuration**
```python
# Enhanced UserPoolClient with Calendar scope
user_pool_client = UserPoolClient(
    self, 'UserPoolClient',
    user_pool=user_pool,
    o_auth=OAuthSettings(
        flows=OAuthFlows(authorization_code_grant=True),
        scopes=[
            OAuthScope.OPENID,
            OAuthScope.EMAIL,
            OAuthScope.PROFILE,
            OAuthScope.custom('https://www.googleapis.com/auth/calendar')
        ],
        callback_urls=[f'https://{distribution.domain_name}'],
        logout_urls=[f'https://{distribution.domain_name}']
    )
)
```

**1.2.2 Enhance Lambda@Edge JWT Validation**
```typescript
// Apply patterns from aws-samples/cloudfront-authorization-at-edge
const validateCalendarScope = (jwt: any): boolean => {
  const scopes = jwt.scope || '';
  return scopes.includes('https://www.googleapis.com/auth/calendar');
};

export const handler = async (event: CloudFrontRequestEvent) => {
  // Extract and validate JWT
  const jwt = extractJWTFromCookies(event.Records[0].cf.request.headers);
  
  if (!validateCalendarScope(jwt)) {
    return {
      status: '401',
      statusDescription: 'Calendar Access Required',
      body: JSON.stringify({
        error: 'calendar_access_required',
        message: 'Google Calendar access is required'
      })
    };
  }
  
  // Continue with request
  return event.Records[0].cf.request;
};
```

#### Epic 1.3: Frontend Authentication Enhancement
**Priority**: High | **Effort**: 2-3 days

**1.3.1 Enhanced Auth Context**
```typescript
// Apply patterns from aws-nx-mcp research
interface AuthContextType {
  user: CognitoUser | null;
  isAuthenticated: boolean;
  calendarPermissions: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  requestCalendarPermissions: () => Promise<void>;
}

export const useAuth = (): AuthContextType => {
  const [calendarPermissions, setCalendarPermissions] = useState(false);
  
  const checkCalendarPermissions = async () => {
    try {
      const session = await Auth.currentSession();
      const scopes = session.getAccessToken().payload?.scope || '';
      setCalendarPermissions(scopes.includes('https://www.googleapis.com/auth/calendar'));
    } catch (error) {
      setCalendarPermissions(false);
    }
  };
  
  // ... rest of implementation
};
```

---

## Phase 2: Google Calendar Integration (3-4 weeks)

### Week 3-4: Calendar API Foundation

#### Epic 2.1: Google Calendar Service Layer
**Priority**: Critical | **Effort**: 2 weeks

**2.1.1 Calendar API Client Setup**
```typescript
// Apply Google Calendar API patterns
class GoogleCalendarService {
  private gapi: any;
  
  async initialize(): Promise<void> {
    await this.loadGoogleAPI();
    await this.initializeGAPIClient();
  }
  
  async findOrCreateCalendar(name: string = 'SFLT Events'): Promise<string> {
    const calendars = await this.listCalendars();
    const existing = calendars.find(cal => cal.summary === name);
    
    if (existing) return existing.id;
    
    return await this.createCalendar(name);
  }
  
  async createEvent(calendarId: string, event: EventData): Promise<string> {
    const response = await this.gapi.client.calendar.events.insert({
      calendarId,
      resource: {
        summary: event.title,
        start: { dateTime: event.startTime },
        end: { dateTime: event.endTime },
        extendedProperties: {
          private: {
            eventType: event.type,
            linkedEventId: event.linkedEventId,
            sfltEventId: event.id
          }
        }
      }
    });
    
    return response.result.id;
  }
}
```

**2.1.2 Event Management System**
```typescript
// Event data models with TypeScript
interface StartEvent {
  id: string;
  type: 'start';
  title: string;
  startTime: string;
  endTime: string;
  description?: string;
  googleEventId?: string;
}

interface EndEvent {
  id: string;
  type: 'end';
  title: string;
  startTime: string;
  endTime: string;
  description?: string;
  linkedStartEventId: string;
  googleEventId?: string;
}

type CalendarEvent = StartEvent | EndEvent;

class EventManager {
  constructor(private calendarService: GoogleCalendarService) {}
  
  async createStartEvent(data: Omit<StartEvent, 'id' | 'type'>): Promise<StartEvent> {
    const event: StartEvent = {
      ...data,
      id: generateEventId(),
      type: 'start'
    };
    
    const googleEventId = await this.calendarService.createEvent(
      this.calendarId,
      event
    );
    
    return { ...event, googleEventId };
  }
  
  async createEndEvent(
    data: Omit<EndEvent, 'id' | 'type' | 'linkedStartEventId'>,
    linkedStartEventId: string
  ): Promise<EndEvent> {
    const event: EndEvent = {
      ...data,
      id: generateEventId(),
      type: 'end',
      linkedStartEventId
    };
    
    const googleEventId = await this.calendarService.createEvent(
      this.calendarId,
      event
    );
    
    return { ...event, googleEventId };
  }
}
```

### Week 5-6: React Integration and UI

#### Epic 2.2: React Calendar Hooks
**Priority**: High | **Effort**: 1 week

**2.2.1 Calendar Operations Hook**
```typescript
export const useCalendar = () => {
  const [calendarService] = useState(() => new GoogleCalendarService());
  const [eventManager] = useState(() => new EventManager(calendarService));
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const initializeCalendar = async () => {
    try {
      setLoading(true);
      await calendarService.initialize();
      const calendarId = await calendarService.findOrCreateCalendar();
      eventManager.setCalendarId(calendarId);
      await loadEvents();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  return {
    events,
    loading,
    error,
    initializeCalendar,
    createStartEvent: eventManager.createStartEvent.bind(eventManager),
    createEndEvent: eventManager.createEndEvent.bind(eventManager)
  };
};
```

#### Epic 2.3: Enhanced UI Components
**Priority**: Medium | **Effort**: 1 week

**2.3.1 Event List Component (Enhanced)**
```tsx
// Enhanced with better UX patterns
const EventList: React.FC = () => {
  const { events, loading, error } = useCalendar();
  const [filter, setFilter] = useState<'all' | 'start' | 'end'>('all');
  const [sortBy, setSortBy] = useState<'date' | 'type'>('date');
  
  const filteredEvents = useMemo(() => {
    let filtered = events;
    
    if (filter !== 'all') {
      filtered = filtered.filter(event => event.type === filter);
    }
    
    return filtered.sort((a, b) => {
      if (sortBy === 'date') {
        return new Date(a.startTime).getTime() - new Date(b.startTime).getTime();
      }
      return a.type.localeCompare(b.type);
    });
  }, [events, filter, sortBy]);
  
  if (loading) return <div className="loading">Loading events...</div>;
  if (error) return <div className="error">Error: {error}</div>;
  
  return (
    <div className="event-list">
      <div className="event-list-controls">
        <select value={filter} onChange={(e) => setFilter(e.target.value as any)}>
          <option value="all">All Events</option>
          <option value="start">Start Events</option>
          <option value="end">End Events</option>
        </select>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}>
          <option value="date">Sort by Date</option>
          <option value="type">Sort by Type</option>
        </select>
      </div>
      
      <div className="event-list-items">
        {filteredEvents.map(event => (
          <EventItem key={event.id} event={event} />
        ))}
      </div>
    </div>
  );
};
```

**2.3.2 Event Forms (Start and End)**
```tsx
const StartEventForm: React.FC = () => {
  const { createStartEvent } = useCalendar();
  const [formData, setFormData] = useState({
    title: '',
    startTime: '',
    endTime: '',
    description: ''
  });
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createStartEvent(formData);
      setFormData({ title: '', startTime: '', endTime: '', description: '' });
      // Show success notification
    } catch (error) {
      // Show error notification
    }
  };
  
  return (
    <form onSubmit={handleSubmit} className="start-event-form">
      <div className="form-group">
        <label htmlFor="title">Event Title</label>
        <input
          id="title"
          type="text"
          value={formData.title}
          onChange={(e) => setFormData({...formData, title: e.target.value})}
          required
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="startTime">Start Time</label>
        <input
          id="startTime"
          type="datetime-local"
          value={formData.startTime}
          onChange={(e) => setFormData({...formData, startTime: e.target.value})}
          required
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="endTime">End Time</label>
        <input
          id="endTime"
          type="datetime-local"
          value={formData.endTime}
          onChange={(e) => setFormData({...formData, endTime: e.target.value})}
          required
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="description">Description</label>
        <textarea
          id="description"
          value={formData.description}
          onChange={(e) => setFormData({...formData, description: e.target.value})}
        />
      </div>
      
      <button type="submit">Create Start Event</button>
    </form>
  );
};

const EndEventForm: React.FC = () => {
  const { createEndEvent, events } = useCalendar();
  const [selectedStartEvent, setSelectedStartEvent] = useState<string>('');
  
  const startEvents = events.filter(event => event.type === 'start');
  
  // Similar form structure but with start event selector
  return (
    <form onSubmit={handleSubmit} className="end-event-form">
      <div className="form-group">
        <label htmlFor="linkedStartEvent">Link to Start Event</label>
        <select
          id="linkedStartEvent"
          value={selectedStartEvent}
          onChange={(e) => setSelectedStartEvent(e.target.value)}
          required
        >
          <option value="">Select a start event...</option>
          {startEvents.map(event => (
            <option key={event.id} value={event.id}>
              {event.title} - {new Date(event.startTime).toLocaleDateString()}
            </option>
          ))}
        </select>
      </div>
      
      {/* Rest of form fields similar to StartEventForm */}
      
      <button type="submit">Create End Event</button>
    </form>
  );
};
```

---

## Phase 3: Enhanced UI and CloudScape Integration (2-3 weeks)

### Week 7-8: CloudScape Component Integration

#### Epic 3.1: Selective CloudScape Adoption
**Priority**: Medium | **Effort**: 2 weeks

**3.1.1 CloudScape Dependencies**
```bash
# Add CloudScape to existing React app
cd frontend
npm install @cloudscape-design/components @cloudscape-design/global-styles
```

**3.1.2 Enhanced EventList with CloudScape Table**
```tsx
import { Table, Button, SpaceBetween, StatusIndicator } from '@cloudscape-design/components';

const CloudScapeEventList: React.FC = () => {
  const { events, loading } = useCalendar();
  
  const columnDefinitions = [
    {
      id: 'type',
      header: 'Type',
      cell: (event: CalendarEvent) => (
        <StatusIndicator type={event.type === 'start' ? 'success' : 'info'}>
          {event.type.toUpperCase()}
        </StatusIndicator>
      )
    },
    {
      id: 'title',
      header: 'Title',
      cell: (event: CalendarEvent) => event.title
    },
    {
      id: 'startTime',
      header: 'Start Time',
      cell: (event: CalendarEvent) => new Date(event.startTime).toLocaleString()
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: (event: CalendarEvent) => (
        <SpaceBetween direction="horizontal" size="xs">
          <Button variant="link">Edit</Button>
          <Button variant="link">Delete</Button>
        </SpaceBetween>
      )
    }
  ];
  
  return (
    <Table
      columnDefinitions={columnDefinitions}
      items={events}
      loading={loading}
      sortingDisabled={false}
      variant="full-page"
      header={
        <SpaceBetween direction="horizontal" size="m">
          <h2>Calendar Events</h2>
          <Button variant="primary">Create Event</Button>
        </SpaceBetween>
      }
    />
  );
};
```

**3.1.3 CloudScape Forms and Modals**
```tsx
import { Modal, Form, FormField, Input, Select, Textarea } from '@cloudscape-design/components';

const CloudScapeEventModal: React.FC = ({ visible, onDismiss, eventType }) => {
  return (
    <Modal
      visible={visible}
      onDismiss={onDismiss}
      header={`Create ${eventType} Event`}
      footer={
        <SpaceBetween direction="horizontal" size="xs">
          <Button variant="link" onClick={onDismiss}>Cancel</Button>
          <Button variant="primary" onClick={handleSubmit}>Create Event</Button>
        </SpaceBetween>
      }
    >
      <Form>
        <FormField label="Event Title" errorText={errors.title}>
          <Input
            value={formData.title}
            onChange={({ detail }) => updateFormData('title', detail.value)}
            placeholder="Enter event title"
          />
        </FormField>
        
        <FormField label="Start Time" errorText={errors.startTime}>
          <Input
            type="datetime-local"
            value={formData.startTime}
            onChange={({ detail }) => updateFormData('startTime', detail.value)}
          />
        </FormField>
        
        {eventType === 'end' && (
          <FormField label="Link to Start Event" errorText={errors.linkedEvent}>
            <Select
              selectedOption={selectedStartEvent}
              onChange={({ detail }) => setSelectedStartEvent(detail.selectedOption)}
              options={startEventOptions}
              placeholder="Select a start event"
            />
          </FormField>
        )}
        
        <FormField label="Description">
          <Textarea
            value={formData.description}
            onChange={({ detail }) => updateFormData('description', detail.value)}
            placeholder="Optional description"
          />
        </FormField>
      </Form>
    </Modal>
  );
};
```

---

## Phase 4: Testing and Production Optimization (2 weeks)

### Week 9: Comprehensive Testing

#### Epic 4.1: Enhanced E2E Testing
**Priority**: High | **Effort**: 1 week

**4.1.1 Calendar Integration E2E Tests**
```typescript
// Enhanced Playwright tests
describe('Google Calendar Integration', () => {
  test('should create and link start/end events', async ({ page }) => {
    // Login and verify Calendar permissions
    await authenticateWithCalendarPermissions(page);
    
    // Create start event
    await page.click('[data-testid="create-start-event"]');
    await page.fill('[data-testid="event-title"]', 'Test Start Event');
    await page.fill('[data-testid="start-time"]', '2024-01-01T10:00');
    await page.fill('[data-testid="end-time"]', '2024-01-01T11:00');
    await page.click('[data-testid="submit"]');
    
    // Verify event appears in list
    await expect(page.locator('[data-testid="event-list"]')).toContainText('Test Start Event');
    
    // Create linked end event
    await page.click('[data-testid="create-end-event"]');
    await page.selectOption('[data-testid="linked-start-event"]', 'Test Start Event');
    await page.fill('[data-testid="event-title"]', 'Test End Event');
    await page.click('[data-testid="submit"]');
    
    // Verify both events and their relationship
    await expect(page.locator('[data-testid="event-list"]')).toContainText('Test End Event');
    await expect(page.locator('[data-testid="event-relationship"]')).toBeVisible();
  });
  
  test('should handle Calendar API errors gracefully', async ({ page }) => {
    // Mock Calendar API failure
    await page.route('**/calendar/v3/**', route => {
      route.fulfill({ status: 500, body: 'Calendar API Error' });
    });
    
    await authenticateWithCalendarPermissions(page);
    await page.click('[data-testid="create-start-event"]');
    
    // Verify error handling
    await expect(page.locator('[data-testid="error-message"]')).toContainText('Calendar API Error');
    await expect(page.locator('[data-testid="retry-button"]')).toBeVisible();
  });
});
```

### Week 10: Performance and Production Readiness

#### Epic 4.2: Performance Optimization
**Priority**: Medium | **Effort**: 1 week

**4.2.1 Calendar API Optimization**
```typescript
// Implement caching and batching
class OptimizedCalendarService extends GoogleCalendarService {
  private eventCache = new Map<string, CalendarEvent[]>();
  private batchQueue: BatchOperation[] = [];
  
  async getEvents(calendarId: string): Promise<CalendarEvent[]> {
    if (this.eventCache.has(calendarId)) {
      return this.eventCache.get(calendarId)!;
    }
    
    const events = await this.fetchEventsFromAPI(calendarId);
    this.eventCache.set(calendarId, events);
    return events;
  }
  
  async batchCreateEvents(events: CalendarEvent[]): Promise<string[]> {
    // Batch multiple event creation operations
    const batch = this.gapi.client.newBatch();
    
    events.forEach(event => {
      batch.add(this.gapi.client.calendar.events.insert({
        calendarId: this.calendarId,
        resource: event
      }));
    });
    
    const results = await batch;
    return Object.values(results.result).map(r => r.result.id);
  }
}
```

**4.2.2 Production Monitoring**
```typescript
// Add CloudWatch metrics and logging
const logCalendarOperation = (operation: string, duration: number, success: boolean) => {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    operation,
    duration,
    success,
    service: 'calendar-api'
  }));
};

// Implement in service methods
async createEvent(calendarId: string, event: EventData): Promise<string> {
  const startTime = Date.now();
  try {
    const result = await this.gapi.client.calendar.events.insert({...});
    logCalendarOperation('createEvent', Date.now() - startTime, true);
    return result.result.id;
  } catch (error) {
    logCalendarOperation('createEvent', Date.now() - startTime, false);
    throw error;
  }
}
```

---

## Success Criteria and Validation

### Functional Requirements
- ✅ Users can authenticate with Google OAuth including Calendar permissions
- ✅ App creates/finds dedicated "SFLT Events" calendar
- ✅ Users can create start events with title, date, time
- ✅ Users can create end events linked to start events
- ✅ Events synchronize with Google Calendar in real-time
- ✅ Users can edit and delete events
- ✅ No user data stored by application (privacy compliance)

### Technical Requirements
- ✅ Lambda@Edge deployment blocker resolved
- ✅ End-to-end authentication flow working
- ✅ Google Calendar API integration complete
- ✅ Error handling and retry logic implemented
- ✅ Responsive UI with enhanced components
- ✅ Comprehensive E2E test coverage
- ✅ Performance optimization and monitoring

### Performance Targets
- **Load Time**: <3 seconds initial load
- **Calendar API Response**: <1 second for operations
- **Error Rate**: <1% for Calendar operations
- **Uptime**: >99.9% availability

## Risk Mitigation Strategy

### High-Risk Items
1. **Lambda@Edge Deployment**: Parallel development of Calendar features while fixing infrastructure
2. **Google Calendar API Rate Limits**: Implement caching and batching
3. **OAuth Token Management**: Comprehensive token refresh and error handling

### Monitoring and Alerting
- CloudWatch metrics for Lambda@Edge performance
- Calendar API operation success rates
- User authentication flow monitoring
- Error tracking and alerting

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| Phase 1 | 2-3 weeks | Lambda@Edge fix, OAuth enhancement |
| Phase 2 | 3-4 weeks | Google Calendar integration, React hooks |
| Phase 3 | 2-3 weeks | CloudScape UI enhancement |
| Phase 4 | 2 weeks | Testing, performance optimization |
| **Total** | **9-12 weeks** | **Complete Google Calendar Event Manager** |

This roadmap provides a clear path to completing the Google Calendar Event Manager while leveraging proven AWS patterns and maintaining the current architecture investment. The approach balances rapid feature delivery with architectural excellence and provides a foundation for future enhancements.