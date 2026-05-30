import { describe, expect, it } from 'vitest'

import router from '@/router'

describe('router configuration', () => {
  it('redirects "/" to "/directories"', async () => {
    await router.push('/')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/directories')
  })

  it('resolves /directories to the "directories" named route', () => {
    const resolved = router.resolve('/directories')

    expect(resolved.name).toBe('directories')
  })

  it('resolves /directories/:id/files to the "files" named route with params', () => {
    const resolved = router.resolve('/directories/42/files')

    expect(resolved.name).toBe('files')
    expect(resolved.params.id).toBe('42')
  })

  it('resolves /files/:id to the "file-detail" named route with the id param', () => {
    const resolved = router.resolve('/files/7')

    expect(resolved.name).toBe('file-detail')
    expect(resolved.params.id).toBe('7')
  })

  it('resolves /scan to the "scan" named route', () => {
    const resolved = router.resolve('/scan')

    expect(resolved.name).toBe('scan')
  })

  it('builds /directories/:id/files from name+params (named navigation works)', () => {
    const resolved = router.resolve({ name: 'files', params: { id: 99 } })

    expect(resolved.href).toBe('/directories/99/files')
  })

  it('builds /files/:id from name+params (named navigation works)', () => {
    const resolved = router.resolve({ name: 'file-detail', params: { id: 42 } })

    expect(resolved.href).toBe('/files/42')
  })

  it('builds /scan from named route', () => {
    expect(router.resolve({ name: 'scan' }).href).toBe('/scan')
  })

  it('builds /directories from named route', () => {
    expect(router.resolve({ name: 'directories' }).href).toBe('/directories')
  })

  it('rejects non-numeric ids (path regex \\d+ guards the route)', () => {
    const resolved = router.resolve('/files/abc')

    // Non-matching path resolves but without the named route.
    expect(resolved.name).not.toBe('file-detail')
  })
})
