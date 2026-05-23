import { describe, expect, it } from 'vitest'

import router from '@/router'

describe('router configuration', () => {
  it('resolves /files/:id to the "file-detail" named route with the id param', () => {
    const resolved = router.resolve('/files/7')

    expect(resolved.name).toBe('file-detail')
    expect(resolved.params.id).toBe('7')
  })

  it('builds /files/:id from name+params (named navigation works)', () => {
    const resolved = router.resolve({ name: 'file-detail', params: { id: 42 } })

    expect(resolved.href).toBe('/files/42')
  })

  it('rejects non-numeric ids (path regex \\d+ guards the route)', () => {
    const resolved = router.resolve('/files/abc')

    // Non-matching path resolves but without the named route.
    expect(resolved.name).not.toBe('file-detail')
  })
})
