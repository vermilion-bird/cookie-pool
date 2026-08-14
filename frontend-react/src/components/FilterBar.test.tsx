import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FilterBar } from './FilterBar'

const options = [
  { label: 'All', value: 'ALL' },
  { label: 'Active', value: 'ACTIVE' },
]

describe('FilterBar', () => {
  it('renders all options', () => {
    render(<FilterBar options={options} value="ALL" onChange={() => {}} />)
    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('calls onChange with the clicked value', () => {
    const onChange = vi.fn()
    render(<FilterBar options={options} value="ALL" onChange={onChange} />)
    fireEvent.click(screen.getByText('Active'))
    expect(onChange).toHaveBeenCalledWith('ACTIVE')
  })
})
