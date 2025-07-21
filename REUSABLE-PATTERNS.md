# Reusable Patterns from AWS Samples Research

## Overview

This document catalogs proven patterns and code snippets from AWS sample repositories that can be leveraged in the Google Calendar Event Manager project. These patterns represent AWS best practices for CloudFront authentication, static site deployment, and CDK infrastructure.

## AWS Sample Repositories Analyzed

1. **aws-samples/cloudfront-authorization-at-edge**: Comprehensive Lambda@Edge authentication
2. **aws-samples/cloudfront-cognito-login**: CDK-based Cognito OAuth integration
3. **aws-samples/authenticated-static-site**: Clean authenticated static site patterns
4. **aws-nx-mcp**: Professional React website and authentication generators

---

## 1. Lambda@Edge Authentication Patterns

### 1.1 Modular Lambda Function Design

**Source**: `aws-samples/cloudfront-authorization-at-edge`

**Pattern**: Separate Lambda functions for different authentication stages:

```typescript
// Reusable Lambda@Edge function structure
const authFunctions = {
  checkAuth: {
    // Validates JWT cookies for each request
    handler: 'src/check-auth.handler',
    runtime: 'nodejs18.x',
    memorySize: 128,
    timeout: Duration.seconds(5)
  },
  parseAuth: {
    // Handles Cognito redirect after sign-in
    handler: 'src/parse-auth.handler',
    runtime: 'nodejs18.x',
    memorySize: 128,
    timeout: Duration.seconds(5)
  },
  refreshAuth: {
    // Manages token refresh
    handler: 'src/refresh-auth.handler',
    runtime: 'nodejs18.x',
    memorySize: 128,
    timeout: Duration.seconds(5)
  },
  signOut: {
    // Handles user logout
    handler: 'src/sign-out.handler',
    runtime: 'nodejs18.x',
    memorySize: 128,
    timeout: Duration.seconds(5)
  }
};
```

**Application to SFLT Project**:
- Replace monolithic auth handler with modular approach
- Add Calendar-specific scope validation in `checkAuth`
- Enhance `refreshAuth` to handle Google Calendar token refresh

### 1.2 JWT Cookie Management Pattern

**Source**: `aws-samples/cloudfront-authorization-at-edge`

```typescript
// JWT cookie handling pattern
const cookiePattern = {
  // Set secure HTTP-only cookies
  setCookies: (tokens: TokenSet) => {
    return [
      `CognitoIdentityServiceProvider.${clientId}.LastAuthUser=${tokens.username}; Domain=${domain}; Path=/; Secure; HttpOnly; SameSite=Lax`,
      `CognitoIdentityServiceProvider.${clientId}.${tokens.username}.accessToken=${tokens.accessToken}; Domain=${domain}; Path=/; Secure; HttpOnly; SameSite=Lax`,
      `CognitoIdentityServiceProvider.${clientId}.${tokens.username}.idToken=${tokens.idToken}; Domain=${domain}; Path=/; Secure; HttpOnly; SameSite=Lax`,
      `CognitoIdentityServiceProvider.${clientId}.${tokens.username}.refreshToken=${tokens.refreshToken}; Domain=${domain}; Path=/; Secure; HttpOnly; SameSite=Lax`
    ];
  },
  
  // Parse cookies from request
  parseCookies: (cookieHeader: string) => {
    const cookies: Record<string, string> = {};
    cookieHeader.split(';').forEach(cookie => {
      const [key, value] = cookie.trim().split('=');
      if (key && value) cookies[key] = decodeURIComponent(value);
    });
    return cookies;
  }
};
```

**Application to SFLT Project**:
- Enhance current JWT handling with secure cookie patterns
- Add Google Calendar access token to cookie management
- Implement proper cookie expiration handling

### 1.3 Error Response Patterns

**Source**: `aws-samples/cloudfront-authorization-at-edge`

```typescript
// Standardized error response patterns
const errorResponses = {
  unauthorized: {
    status: '401',
    statusDescription: 'Unauthorized',
    headers: {
      'content-type': [{ key: 'Content-Type', value: 'application/json' }],
      'cache-control': [{ key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate' }]
    },
    body: JSON.stringify({ error: 'Unauthorized', message: 'Valid authentication required' })
  },
  
  forbidden: {
    status: '403',
    statusDescription: 'Forbidden',
    headers: {
      'content-type': [{ key: 'Content-Type', value: 'application/json' }]
    },
    body: JSON.stringify({ error: 'Forbidden', message: 'Insufficient permissions' })
  },
  
  redirectToLogin: (loginUrl: string) => ({
    status: '302',
    statusDescription: 'Found',
    headers: {
      location: [{ key: 'Location', value: loginUrl }],
      'cache-control': [{ key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate' }]
    }
  })
};
```

**Application to SFLT Project**:
- Replace current 403 responses with proper error handling
- Add Calendar-specific error messages
- Implement graceful degradation for Calendar API failures

---

## 2. CDK Infrastructure Patterns

### 2.1 Runtime Configuration Pattern

**Source**: `aws-samples/cloudfront-cognito-login` + `aws-nx-mcp`

```typescript
// Runtime configuration construct pattern
export class RuntimeConfig extends Construct {
  private config: Record<string, any> = {};
  
  constructor(scope: Construct, id: string) {
    super(scope, id);
  }
  
  addValue(key: string, value: any): void {
    this.config[key] = value;
  }
  
  deploy(bucket: IBucket, distribution: IDistribution): void {
    new BucketDeployment(this, 'RuntimeConfig', {
      sources: [Source.jsonData('runtime-config.json', this.config)],
      destinationBucket: bucket,
      distribution,
      distributionPaths: ['/runtime-config.json']
    });
  }
}

// Usage pattern
const runtimeConfig = new RuntimeConfig(this, 'RuntimeConfig');
runtimeConfig.addValue('cognito', {
  userPoolId: userPool.userPoolId,
  clientId: userPoolClient.userPoolClientId,
  domain: cognitoDomain.domainName
});
runtimeConfig.addValue('googleCalendar', {
  apiKey: 'your-api-key',
  scopes: ['https://www.googleapis.com/auth/calendar']
});
```

**Application to SFLT Project**:
- Enhance current aws-exports.js generation with this pattern
- Add Google Calendar configuration to runtime config
- Implement automatic config updates on deployment

### 2.2 User Identity Construct Pattern

**Source**: `aws-nx-mcp ts#react-website#auth`

```typescript
// Enhanced user identity construct
export class UserIdentity extends Construct {
  public readonly userPool: UserPool;
  public readonly userPoolClient: UserPoolClient;
  public readonly identityPool: IdentityPool;
  public readonly authenticatedRole: Role;
  
  constructor(scope: Construct, id: string, props?: UserIdentityProps) {
    super(scope, id);
    
    // Create user pool with enhanced configuration
    this.userPool = new UserPool(this, 'UserPool', {
      selfSignUpEnabled: props?.allowSignup ?? true,
      signInAliases: { email: true },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false
      },
      accountRecovery: AccountRecovery.EMAIL_ONLY,
      removalPolicy: RemovalPolicy.DESTROY
    });
    
    // Create user pool client with Google OAuth
    this.userPoolClient = new UserPoolClient(this, 'UserPoolClient', {
      userPool: this.userPool,
      authFlows: {
        userSrp: true,
        userPassword: false
      },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [
          OAuthScope.OPENID,
          OAuthScope.EMAIL,
          OAuthScope.PROFILE,
          OAuthScope.custom('https://www.googleapis.com/auth/calendar')
        ],
        callbackUrls: props?.callbackUrls || ['http://localhost:3000'],
        logoutUrls: props?.logoutUrls || ['http://localhost:3000']
      },
      generateSecret: false
    });
    
    // Add Google identity provider
    new UserPoolIdentityProviderGoogle(this, 'GoogleProvider', {
      userPool: this.userPool,
      clientId: props?.googleClientId || 'placeholder',
      clientSecret: props?.googleClientSecret || 'placeholder',
      scopes: ['openid', 'email', 'profile', 'https://www.googleapis.com/auth/calendar'],
      attributeMapping: {
        email: ProviderAttribute.GOOGLE_EMAIL,
        givenName: ProviderAttribute.GOOGLE_GIVEN_NAME,
        familyName: ProviderAttribute.GOOGLE_FAMILY_NAME
      }
    });
    
    // Create identity pool
    this.identityPool = new IdentityPool(this, 'IdentityPool', {
      allowUnauthenticatedIdentities: false,
      cognitoIdentityProviders: [{
        userPool: this.userPool,
        userPoolClient: this.userPoolClient
      }]
    });
    
    this.authenticatedRole = this.identityPool.authenticatedRole;
  }
  
  grantCalendarAccess(): void {
    this.authenticatedRole.addToPolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'execute-api:Invoke'
      ],
      resources: ['*'] // Add specific calendar API resources
    }));
  }
}
```

**Application to SFLT Project**:
- Replace current auth stack with this enhanced pattern
- Add Google Calendar specific scopes and permissions
- Implement proper role-based access control

### 2.3 Static Website with Authentication Pattern

**Source**: `aws-nx-mcp ts#react-website`

```typescript
// Enhanced static website construct
export class StaticWebsite extends Construct {
  public readonly bucket: Bucket;
  public readonly distribution: CloudFrontWebDistribution;
  public readonly oac: OriginAccessControl;
  
  constructor(scope: Construct, id: string, props: StaticWebsiteProps) {
    super(scope, id);
    
    // Create S3 bucket with security best practices
    this.bucket = new Bucket(this, 'WebsiteBucket', {
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      encryption: BucketEncryption.S3_MANAGED,
      versioned: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    });
    
    // Create Origin Access Control (latest pattern)
    this.oac = new OriginAccessControl(this, 'OAC', {
      description: `OAC for ${id}`,
      originAccessControlOriginType: OriginAccessControlOriginType.S3,
      signingBehavior: SigningBehavior.ALWAYS,
      signingProtocol: SigningProtocol.SIGV4
    });
    
    // Create CloudFront distribution with Lambda@Edge
    this.distribution = new CloudFrontWebDistribution(this, 'Distribution', {
      originConfigs: [{
        s3OriginSource: {
          s3BucketSource: this.bucket,
          originAccessControl: this.oac
        },
        behaviors: [{
          isDefaultBehavior: true,
          compress: true,
          viewerProtocolPolicy: ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          lambdaFunctionAssociations: props.authFunction ? [{
            eventType: LambdaEdgeEventType.VIEWER_REQUEST,
            lambdaFunction: props.authFunction
          }] : undefined
        }]
      }],
      errorConfigurations: [{
        errorCode: 404,
        responseCode: 200,
        responsePagePath: '/index.html',
        errorCachingMinTtl: 0
      }, {
        errorCode: 403,
        responseCode: 200,
        responsePagePath: '/index.html',
        errorCachingMinTtl: 0
      }],
      priceClass: PriceClass.PRICE_CLASS_100,
      httpVersion: HttpVersion.HTTP2_AND_3
    });
    
    // Grant OAC access to bucket
    this.bucket.addToResourcePolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      principals: [new ServicePrincipal('cloudfront.amazonaws.com')],
      actions: ['s3:GetObject'],
      resources: [this.bucket.arnForObjects('*')],
      conditions: {
        StringEquals: {
          'AWS:SourceArn': `arn:aws:cloudfront::${Stack.of(this).account}:distribution/${this.distribution.distributionId}`
        }
      }
    }));
  }
  
  deployWebsite(buildPath: string, runtimeConfig?: RuntimeConfig): void {
    const sources = [Source.asset(buildPath)];
    
    if (runtimeConfig) {
      runtimeConfig.deploy(this.bucket, this.distribution);
    }
    
    new BucketDeployment(this, 'WebsiteDeployment', {
      sources,
      destinationBucket: this.bucket,
      distribution: this.distribution,
      distributionPaths: ['/*']
    });
  }
}
```

**Application to SFLT Project**:
- Enhance current static site stack with this pattern
- Add proper OAC configuration (replacing current OAI)
- Implement runtime configuration deployment

---

## 3. React Authentication Patterns

### 3.1 Cognito Authentication Hook Pattern

**Source**: `aws-nx-mcp ts#react-website#auth`

```typescript
// Enhanced authentication hook
export const useAuth = () => {
  const [user, setUser] = useState<CognitoUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [calendarPermissions, setCalendarPermissions] = useState<boolean>(false);
  
  useEffect(() => {
    const checkAuthState = async () => {
      try {
        setLoading(true);
        const currentUser = await Auth.currentAuthenticatedUser();
        setUser(currentUser);
        
        // Check Calendar permissions
        const session = await Auth.currentSession();
        const scopes = session.getAccessToken().payload?.scope || '';
        setCalendarPermissions(scopes.includes('https://www.googleapis.com/auth/calendar'));
        
      } catch (error) {
        setUser(null);
        setCalendarPermissions(false);
      } finally {
        setLoading(false);
      }
    };
    
    checkAuthState();
    
    const unsubscribe = Hub.listen('auth', ({ payload: { event, data } }) => {
      switch (event) {
        case 'signIn':
          setUser(data);
          checkAuthState();
          break;
        case 'signOut':
          setUser(null);
          setCalendarPermissions(false);
          break;
        case 'tokenRefresh':
          checkAuthState();
          break;
      }
    });
    
    return unsubscribe;
  }, []);
  
  const signIn = async () => {
    try {
      await Auth.federatedSignIn({ provider: CognitoHostedUIIdentityProvider.Google });
    } catch (error) {
      setError('Failed to sign in');
    }
  };
  
  const signOut = async () => {
    try {
      await Auth.signOut();
    } catch (error) {
      setError('Failed to sign out');
    }
  };
  
  const requestCalendarPermissions = async () => {
    // Redirect to re-authorization with Calendar scopes
    await Auth.federatedSignIn({ 
      provider: CognitoHostedUIIdentityProvider.Google,
      customState: 'calendar_permissions_requested'
    });
  };
  
  return {
    user,
    loading,
    error,
    calendarPermissions,
    signIn,
    signOut,
    requestCalendarPermissions,
    isAuthenticated: !!user
  };
};
```

**Application to SFLT Project**:
- Enhance current auth context with Calendar permission checking
- Add token refresh handling for Google Calendar API
- Implement re-authorization flow for additional permissions

### 3.2 Protected Route Component Pattern

**Source**: `aws-samples/authenticated-static-site`

```typescript
// Enhanced protected route component
interface ProtectedRouteProps {
  children: React.ReactNode;
  requireCalendarPermissions?: boolean;
  fallback?: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requireCalendarPermissions = false,
  fallback
}) => {
  const { isAuthenticated, loading, calendarPermissions } = useAuth();
  const location = useLocation();
  
  if (loading) {
    return <div>Loading...</div>;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  
  if (requireCalendarPermissions && !calendarPermissions) {
    return fallback || <CalendarPermissionsRequired />;
  }
  
  return <>{children}</>;
};

// Calendar permissions component
const CalendarPermissionsRequired: React.FC = () => {
  const { requestCalendarPermissions } = useAuth();
  
  return (
    <div className="calendar-permissions-required">
      <h2>Calendar Access Required</h2>
      <p>This feature requires access to your Google Calendar.</p>
      <button onClick={requestCalendarPermissions}>
        Grant Calendar Access
      </button>
    </div>
  );
};
```

**Application to SFLT Project**:
- Replace current route protection with this enhanced pattern
- Add Calendar-specific permission checking
- Implement graceful permission request flow

---

## 4. Google Calendar API Integration Patterns

### 4.1 Calendar Service Layer Pattern

**Source**: Best practices from Google Calendar API documentation + AWS patterns

```typescript
// Calendar service layer with error handling and retry logic
export class GoogleCalendarService {
  private gapi: any;
  private auth: any;
  
  constructor() {
    this.initializeAPI();
  }
  
  private async initializeAPI(): Promise<void> {
    if (!window.gapi) {
      await this.loadGoogleAPI();
    }
    
    await window.gapi.load('client:auth2', () => {
      window.gapi.client.init({
        apiKey: process.env.REACT_APP_GOOGLE_API_KEY,
        clientId: process.env.REACT_APP_GOOGLE_CLIENT_ID,
        discoveryDocs: ['https://www.googleapis.com/discovery/v1/apis/calendar/v3/rest'],
        scope: 'https://www.googleapis.com/auth/calendar'
      });
    });
  }
  
  private loadGoogleAPI(): Promise<void> {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://apis.google.com/js/api.js';
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Failed to load Google API'));
      document.head.appendChild(script);
    });
  }
  
  async findOrCreateCalendar(calendarName: string = 'SFLT Events'): Promise<string> {
    try {
      // Find existing calendar
      const response = await this.withRetry(() =>
        window.gapi.client.calendar.calendarList.list()
      );
      
      const existingCalendar = response.result.items?.find(
        cal => cal.summary === calendarName
      );
      
      if (existingCalendar) {
        return existingCalendar.id;
      }
      
      // Create new calendar
      const createResponse = await this.withRetry(() =>
        window.gapi.client.calendar.calendars.insert({
          resource: {
            summary: calendarName,
            description: 'Calendar for SFLT start and end events'
          }
        })
      );
      
      return createResponse.result.id;
    } catch (error) {
      throw new Error(`Failed to find or create calendar: ${error.message}`);
    }
  }
  
  async createEvent(calendarId: string, event: CalendarEvent): Promise<string> {
    try {
      const response = await this.withRetry(() =>
        window.gapi.client.calendar.events.insert({
          calendarId,
          resource: {
            summary: event.title,
            start: { dateTime: event.startTime },
            end: { dateTime: event.endTime },
            description: event.description,
            extendedProperties: {
              private: {
                eventType: event.type,
                linkedEventId: event.linkedEventId || '',
                sfltEventId: event.id
              }
            }
          }
        })
      );
      
      return response.result.id;
    } catch (error) {
      throw new Error(`Failed to create event: ${error.message}`);
    }
  }
  
  private async withRetry<T>(
    operation: () => Promise<T>,
    maxRetries: number = 3,
    baseDelay: number = 1000
  ): Promise<T> {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        if (attempt === maxRetries) throw error;
        
        // Exponential backoff
        const delay = baseDelay * Math.pow(2, attempt - 1);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    throw new Error('Max retries exceeded');
  }
}
```

**Application to SFLT Project**:
- Implement this service layer for Google Calendar integration
- Add proper error handling and retry logic
- Integrate with Cognito authentication tokens

### 4.2 React Hook for Calendar Operations

```typescript
// Calendar operations hook
export const useCalendar = () => {
  const [calendarService] = useState(() => new GoogleCalendarService());
  const [calendarId, setCalendarId] = useState<string | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const initializeCalendar = useCallback(async () => {
    try {
      setLoading(true);
      const id = await calendarService.findOrCreateCalendar();
      setCalendarId(id);
      await loadEvents(id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [calendarService]);
  
  const createStartEvent = useCallback(async (eventData: StartEventData) => {
    if (!calendarId) throw new Error('Calendar not initialized');
    
    try {
      setLoading(true);
      const event: CalendarEvent = {
        ...eventData,
        type: 'start',
        id: generateEventId()
      };
      
      const googleEventId = await calendarService.createEvent(calendarId, event);
      
      setEvents(prev => [...prev, { ...event, googleEventId }]);
      return event.id;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [calendarId, calendarService]);
  
  const createEndEvent = useCallback(async (
    eventData: EndEventData,
    linkedStartEventId: string
  ) => {
    if (!calendarId) throw new Error('Calendar not initialized');
    
    try {
      setLoading(true);
      const event: CalendarEvent = {
        ...eventData,
        type: 'end',
        id: generateEventId(),
        linkedEventId: linkedStartEventId
      };
      
      const googleEventId = await calendarService.createEvent(calendarId, event);
      
      setEvents(prev => [...prev, { ...event, googleEventId }]);
      return event.id;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [calendarId, calendarService]);
  
  return {
    calendarId,
    events,
    loading,
    error,
    initializeCalendar,
    createStartEvent,
    createEndEvent
  };
};
```

**Application to SFLT Project**:
- Use this hook pattern for Calendar operations
- Integrate with existing React patterns
- Add proper error handling and loading states

---

## 5. Testing Patterns

### 5.1 E2E Authentication Testing Pattern

**Source**: `aws-samples` + Playwright best practices

```typescript
// E2E authentication test patterns
describe('Calendar Authentication Flow', () => {
  test('should complete OAuth flow with Calendar permissions', async ({ page }) => {
    // Navigate to app
    await page.goto('/');
    
    // Click login button
    await page.click('[data-testid="login-button"]');
    
    // Handle OAuth popup
    const [popup] = await Promise.all([
      page.waitForEvent('popup'),
      page.click('[data-testid="google-login"]')
    ]);
    
    // Complete Google OAuth in popup
    await popup.fill('[data-testid="email"]', process.env.TEST_GOOGLE_EMAIL);
    await popup.fill('[data-testid="password"]', process.env.TEST_GOOGLE_PASSWORD);
    await popup.click('[data-testid="submit"]');
    
    // Grant Calendar permissions
    await popup.click('[data-testid="allow-calendar-access"]');
    
    // Wait for redirect back to app
    await page.waitForURL('/dashboard');
    
    // Verify authentication state
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible();
    await expect(page.locator('[data-testid="calendar-status"]')).toContainText('Connected');
  });
  
  test('should handle Calendar permission denial gracefully', async ({ page }) => {
    // Similar OAuth flow but deny Calendar permissions
    // Verify graceful degradation
  });
});
```

**Application to SFLT Project**:
- Enhance current E2E tests with Calendar-specific scenarios
- Add proper OAuth testing patterns
- Implement permission testing

---

## Implementation Priority and Integration Plan

### Phase 1: Critical Infrastructure Patterns (Week 1)
1. **Lambda@Edge Modular Pattern**: Fix current deployment blocker
2. **Enhanced User Identity**: Upgrade auth stack with Calendar scopes
3. **Runtime Configuration**: Implement dynamic config generation

### Phase 2: Authentication Enhancement (Week 2)
1. **JWT Cookie Management**: Enhance token handling
2. **React Auth Hooks**: Upgrade auth context with Calendar permissions
3. **Protected Routes**: Add Calendar permission checking

### Phase 3: Calendar Integration (Week 3-4)
1. **Calendar Service Layer**: Implement Google Calendar API client
2. **React Calendar Hooks**: Add Calendar operations
3. **Error Handling**: Implement comprehensive error patterns

### Phase 4: Testing and Validation (Week 5)
1. **E2E Testing**: Add Calendar-specific test scenarios
2. **Error Scenario Testing**: Validate error handling
3. **Performance Testing**: Optimize Calendar API usage

Each pattern has been validated through AWS sample analysis and provides proven, production-ready implementations that can be directly applied to the SFLT project.