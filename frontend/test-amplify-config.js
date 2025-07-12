// Test Amplify configuration directly
import { Amplify } from 'aws-amplify'

const testConfig = {
  Auth: {
    Cognito: {
      userPoolId: 'ap-southeast-2_u6zH1Pbty',
      userPoolClientId: '2chnp95qkugngcet88uiokikpm',
      identityPoolId: 'ap-southeast-2:f1c9fbd0-085a-4639-93eb-309b62d03e08',
      loginWith: {
        oauth: {
          domain: 'sflt-auth.auth.ap-southeast-2.amazoncognito.com',
          scopes: ['email', 'openid', 'profile'],
          redirectSignIn: ['https://d36x1wqi58k1n5.cloudfront.net/', 'http://localhost:5173/'],
          redirectSignOut: ['https://d36x1wqi58k1n5.cloudfront.net/', 'http://localhost:5173/'],
          responseType: 'code',
        },
        email: true,
      },
    },
  },
}

try {
  console.log('Attempting to configure Amplify...')
  Amplify.configure(testConfig)
  console.log('Amplify configured successfully!')
} catch (error) {
  console.error('Error configuring Amplify:', error)
  console.error('Error message:', error.message)
  console.error('Stack trace:', error.stack)
}