import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { AppProviders } from './app/providers.tsx'
import './index.css'

async function enableMocking() {
  const shouldMock =
    import.meta.env.MODE === 'development' &&
    import.meta.env.VITE_ENABLE_API_MOCKS !== 'false'

  if (!shouldMock) return
  const { worker } = await import('./mocks/browser')
  await worker.start({
    onUnhandledRequest: 'bypass',
  })
}

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Root element with id "root" not found')
}

const root = createRoot(rootElement)

enableMocking().finally(() => {
  root.render(
    <StrictMode>
      <AppProviders>
        <App />
      </AppProviders>
    </StrictMode>,
  )
})
