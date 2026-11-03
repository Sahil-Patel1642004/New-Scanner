import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveApiBase } from './apiBase.js';

test('uses localhost only for an unconfigured development build', () => {
  assert.equal(resolveApiBase('', false), 'http://localhost:8000/api/v1');
});

test('normalizes a Render service host to the HTTPS API prefix', () => {
  assert.equal(resolveApiBase('scanora-api.onrender.com', true), 'https://scanora-api.onrender.com/api/v1');
});

test('preserves an explicitly configured API prefix', () => {
  assert.equal(resolveApiBase('https://api.example.com/api/v1/', true), 'https://api.example.com/api/v1');
});

test('rejects missing or insecure production API configuration', () => {
  assert.throws(() => resolveApiBase('', true), /Set VITE_API_BASE_URL/);
  assert.throws(() => resolveApiBase('http://api.example.com/api/v1', true), /must use HTTPS/);
});

test('rejects URLs outside the API prefix and URLs with credentials', () => {
  assert.throws(() => resolveApiBase('https://api.example.com/admin', true), /\/api\/v1/);
  assert.throws(() => resolveApiBase('https://user:password@api.example.com/api/v1', true), /credentials/);
});
