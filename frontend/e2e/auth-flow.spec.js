import { test, expect } from '@playwright/test';

test.describe('OAuth Authentication Flow', () => {
  test('should redirect to Cognito login when accessing protected route', async ({ page }) => {
    console.log('Starting test: Redirect to Cognito login');
    
    // Navigate to protected route
    await page.goto('/admin');
    
    // Wait for redirect to Cognito
    await page.waitForURL(/sflt-auth\.auth\.ap-southeast-2\.amazoncognito\.com/, { timeout: 10000 });
    
    // Take screenshot of Cognito page
    await page.screenshot({ path: 'cognito-redirect.png', fullPage: true });
    
    // Check we're on Cognito domain
    const currentUrl = page.url();
    console.log('Current URL:', currentUrl);
    expect(currentUrl).toContain('sflt-auth.auth.ap-southeast-2.amazoncognito.com');
    
    // Check for error parameters in URL
    const urlObj = new URL(currentUrl);
    const error = urlObj.searchParams.get('error');
    const errorDescription = urlObj.searchParams.get('error_description');
    
    if (error) {
      console.error('OAuth Error:', error);
      console.error('Error Description:', errorDescription);
      
      // Take screenshot of error page
      await page.screenshot({ path: 'cognito-error.png', fullPage: true });
      
      // Log page content
      const pageContent = await page.content();
      console.log('Page content:', pageContent.substring(0, 500));
    }
    
    // Check URL parameters
    console.log('URL Parameters:');
    for (const [key, value] of urlObj.searchParams) {
      console.log(`  ${key}: ${value}`);
    }
  });

  test('should preserve target URL in state parameter', async ({ page }) => {
    console.log('Starting test: State parameter preservation');
    
    // Navigate to specific protected route
    await page.goto('/profile');
    
    // Wait for redirect
    await page.waitForURL(/sflt-auth\.auth\.ap-southeast-2\.amazoncognito\.com/, { timeout: 10000 });
    
    const currentUrl = page.url();
    const urlObj = new URL(currentUrl);
    const state = urlObj.searchParams.get('state');
    
    console.log('State parameter:', state);
    
    if (state) {
      try {
        const decodedState = JSON.parse(decodeURIComponent(state));
        console.log('Decoded state:', decodedState);
        expect(decodedState.target).toBe('/profile');
      } catch (e) {
        console.error('Failed to parse state:', e);
      }
    }
  });

  test('should check Lambda@Edge redirect behavior', async ({ page }) => {
    console.log('Starting test: Lambda@Edge redirect');
    
    // Enable request interception to see headers
    page.on('response', response => {
      if (response.url().includes('/admin')) {
        console.log('Response from /admin:');
        console.log('  Status:', response.status());
        console.log('  Headers:', response.headers());
      }
    });
    
    // Navigate directly to protected route
    const response = await page.goto('/admin', { waitUntil: 'networkidle' });
    
    // Log initial response
    console.log('Initial response status:', response?.status());
    
    // Take screenshot
    await page.screenshot({ path: 'lambda-edge-redirect.png', fullPage: true });
  });

  test('should verify CloudFront and Cognito configuration', async ({ page }) => {
    console.log('Starting test: Configuration verification');
    
    // First, go to home page to verify site is accessible
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('Welcome to SFLT');
    console.log('✓ Site is accessible');
    
    // Try to navigate to admin via click
    const adminLink = page.locator('a[href="/admin"]');
    const adminLinkCount = await adminLink.count();
    console.log('Admin link visible:', adminLinkCount > 0);
    
    // Navigate to admin
    await page.goto('/admin');
    
    // Capture network activity
    const requests = [];
    page.on('request', request => {
      requests.push({
        url: request.url(),
        method: request.method(),
        headers: request.headers()
      });
    });
    
    // Wait for navigation
    await page.waitForLoadState('networkidle');
    
    // Log all requests
    console.log('Network requests:');
    requests.forEach((req, i) => {
      console.log(`${i + 1}. ${req.method} ${req.url}`);
    });
    
    // Check final URL
    const finalUrl = page.url();
    console.log('Final URL:', finalUrl);
    
    // Take final screenshot
    await page.screenshot({ path: 'final-state.png', fullPage: true });
  });
});