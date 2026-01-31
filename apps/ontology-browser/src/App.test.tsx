import { renderWithProviders, screen } from './test-utils/renderWithProviders'
import App from './App'

describe('App', () => {
  it('renders the taxonomy browser heading', () => {
    renderWithProviders(<App />)

    expect(screen.getByRole('heading', { name: /taxonomy browser/i })).toBeVisible()
  })
})
