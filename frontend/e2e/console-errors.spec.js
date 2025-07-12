import { test, expect } from '@playwright/test'

test.describe('Console Error Detection', () => {
  test('should not have console errors on page load', async ({ page }) => {
    const consoleErrors = []
    const consoleWarnings = []
    
    // Listen for console messages
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      } else if (msg.type() === 'warning') {
        consoleWarnings.push(msg.text())
      }
    })
    
    // Listen for page errors
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message)
    })
    
    // Navigate to the home page
    await page.goto('/')
    
    // Wait for the page to load
    await page.waitForTimeout(2000)
    
    // Check for console errors
    if (consoleErrors.length > 0) {
      console.log('Console errors found:')
      consoleErrors.forEach((error, index) => {
        console.log(`${index + 1}: ${error}`)
      })
    }
    
    // Check for console warnings
    if (consoleWarnings.length > 0) {
      console.log('Console warnings found:')
      consoleWarnings.forEach((warning, index) => {
        console.log(`${index + 1}: ${warning}`)
      })
    }
    
    // Fail the test if there are console errors
    expect(consoleErrors, `Found ${consoleErrors.length} console errors`).toHaveLength(0)
  })
  
  test('should handle protected route access gracefully', async ({ page }) => {
    const consoleErrors = []
    
    // Listen for console messages
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })
    
    // Listen for page errors
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message)
    })
    
    // Navigate to a protected route
    await page.goto('/admin')
    
    // Wait for the page to load
    await page.waitForTimeout(2000)
    
    // Check for console errors
    if (consoleErrors.length > 0) {
      console.log('Console errors found on protected route:')
      consoleErrors.forEach((error, index) => {
        console.log(`${index + 1}: ${error}`)
      })
    }
    
    // Fail the test if there are console errors
    expect(consoleErrors, `Found ${consoleErrors.length} console errors on protected route`).toHaveLength(0)
  })
  
  test('should handle dashboard route access gracefully', async ({ page }) => {
    const consoleErrors = []
    
    // Listen for console messages
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })
    
    // Listen for page errors
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message)
    })
    
    // Navigate to dashboard
    await page.goto('/dashboard')
    
    // Wait for the page to load
    await page.waitForTimeout(2000)
    
    // Check for console errors
    if (consoleErrors.length > 0) {
      console.log('Console errors found on dashboard:')
      consoleErrors.forEach((error, index) => {
        console.log(`${index + 1}: ${error}`)
      })
    }
    
    // Fail the test if there are console errors
    expect(consoleErrors, `Found ${consoleErrors.length} console errors on dashboard`).toHaveLength(0)
  })
})