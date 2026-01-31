import { createTheme } from '@mantine/core'
import type { MantineColorsTuple } from '@mantine/core'

const brandColors: MantineColorsTuple = [
  '#f3f9ff',
  '#e0efff',
  '#bedbff',
  '#97c5ff',
  '#76b2ff',
  '#5ea5ff',
  '#519eff',
  '#4187e4',
  '#3676cb',
  '#2154a2',
]

export const mantineTheme = createTheme({
  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  headings: { fontFamily: 'Inter, "Segoe UI", sans-serif' },
  colors: {
    brand: brandColors,
  },
  primaryColor: 'brand',
  radius: {
    xs: '4px',
    sm: '6px',
    md: '8px',
    lg: '12px',
    xl: '16px',
  },
})
