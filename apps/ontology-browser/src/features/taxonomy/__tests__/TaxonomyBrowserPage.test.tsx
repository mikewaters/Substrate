import userEvent from '@testing-library/user-event'
import {
  renderWithProviders,
  screen,
  waitFor,
  within,
} from '../../../test-utils/renderWithProviders'
import { TaxonomyBrowserPage } from '../pages/TaxonomyBrowserPage'

describe('TaxonomyBrowserPage', () => {
  it('loads topics after selecting a taxonomy and shows topic detail on selection', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TaxonomyBrowserPage />)

    const select = await screen.findByTestId('taxonomy-select')
    await user.click(select)

    const taxonomyOption = await screen.findByText('Taxonomy One')
    await user.click(taxonomyOption)

    const topicRow = await screen.findByText('Topic number one')
    expect(topicRow).toBeInTheDocument()

    // detail panel initially instructs user to select
    expect(
      screen.getByText(/select a topic to view/i),
    ).toBeInTheDocument()

    await user.click(topicRow)

    const detailPanel = screen.getByTestId('topic-detail-panel')
    await waitFor(() => {
      expect(
        within(detailPanel).getByText('Description text from topic one'),
      ).toBeInTheDocument()
    })
  })

  it('supports filtering by status', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TaxonomyBrowserPage />)

    const select = await screen.findByTestId('taxonomy-select')
    await user.click(select)
    const taxonomyOption = await screen.findByText('Taxonomy One')
    await user.click(taxonomyOption)

    // wait for table load
    await screen.findByText('Topic number one')

    const statusFilter = screen.getByTestId('status-filter')
    await user.click(statusFilter)
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')

    await waitFor(() => {
      expect(screen.queryByText('Topic number one')).not.toBeInTheDocument()
    })
    expect(
      screen.getByText('Topic number three'),
    ).toBeInTheDocument()
  })
})
