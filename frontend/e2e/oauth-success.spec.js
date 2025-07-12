import { test, expect } from '@playwright/test';

test.describe('OAuth Success Verification', () => {
  test('should redirect to Cognito login WITHOUT error', async ({ page }) => {
    console.log('Testing OAuth flow with new client ID...');
    
    // Navigate to protected route
    await page.goto('/admin');
    
    // Wait for redirect to Cognito
    await page.waitForURL(/sflt-auth\.auth\.ap-southeast-2\.amazoncognito\.com/, { timeout: 10000 });
    
    // Take screenshot
    await page.screenshot({ path: 'cognito-success.png', fullPage: true });
    
    const currentUrl = page.url();
    console.log('Redirected to:', currentUrl);
    
    const urlObj = new URL(currentUrl);
    
    // Check for NO error parameter
    const error = urlObj.searchParams.get('error');
    if (error) {
      console.error('❌ Still getting error:', error);
      throw new Error(`OAuth error: ${error}`);
    }
    
    // Verify correct parameters
    const clientId = urlObj.searchParams.get('client_id');
    console.log('Client ID:', clientId);
    expect(clientId).toBe('2chnp95qkugngcet88uiokikpm');
    
    // Check we're on the login page (not error page)
    const pageContent = await page.content();
    const hasError = pageContent.includes('An error was encountered');
    expect(hasError).toBe(false);
    
    // Look for Google sign-in button
    const googleButton = page.locator('button:has-text("Sign in with Google"), a:has-text("Sign in with Google")');
    const buttonCount = await googleButton.count();
    console.log('Google sign-in button found:', buttonCount > 0);
    
    if (buttonCount > 0) {
      console.log('✅ OAuth flow working correctly! Google sign-in button is visible.');
    }
  });
});