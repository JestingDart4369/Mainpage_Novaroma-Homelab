const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Exercise the actual page script, not a duplicate rendering function.
const script = fs.readFileSync(path.join(__dirname, '../app/template/activity.js'), 'utf8');
const data = JSON.parse(fs.readFileSync(path.join(__dirname, '../app/template/site-data.json'), 'utf8'));
const repoCount = data.repos.length;

async function render(message, { fail = false } = {}) {
  const writes = [];
  const requested = [];
  function element(tag) {
    return {
      tag, children: [], classList: { toggle() {} },
      textContent: '', addEventListener() {},
      appendChild(child) { this.children.push(child); },
      set innerHTML(value) { if (value) writes.push(value); },
    };
  }
  const list = element('div');
  const context = vm.createContext({
    module: { exports: {} },
    document: {
      getElementById: id => id === 'commit-list' ? list : element('button'),
      createElement: element,
    },
    fetch: async url => {
      requested.push(url);
      if (url === '/site-data.json') return { ok: true, json: async () => data };
      return { ok: !fail, json: async () => [{ commit: { message, committer: { date: '2026-11-01T10:00:00Z' } } }] };
    },
  });
  vm.runInContext(script, context);
  await context.module.exports.loadCommits();
  return { list, writes, requested };
}

test('every repo in site-data.json is queried, not a hardcoded subset', async () => {
  const { requested } = await render('hello');
  const commitRequests = requested.filter(u => u.includes('/commits'));
  assert.equal(commitRequests.length, repoCount);
  for (const r of data.repos) {
    assert.ok(commitRequests.some(u => u.startsWith(`/github/repos/${r.owner}/${r.name}/commits`)), r.name);
  }
});

test('GitHub commit messages are rendered as literal text, never parsed HTML', async () => {
  const message = '<img src=x onerror="globalThis.pwned=true"> & <script>alert(1)</script>';
  const { list, writes } = await render(message + '\nsecond line');
  assert.deepEqual(writes, [], 'Untrusted commit text reached innerHTML');
  assert.equal(list.children.length, repoCount);
  for (const item of list.children) {
    assert.equal(item.className, 'commit-item');
    assert.equal(item.children[1].className, 'commit-msg');
    assert.equal(item.children[1].textContent, message);
  }
});

test('failed GitHub requests retain the existing fallback message and CSS classes', async () => {
  const { list } = await render('', { fail: true });
  assert.equal(list.children.length, repoCount);
  for (const item of list.children) {
    assert.equal(item.children[0].className, 'commit-repo');
    assert.equal(item.children[1].textContent, 'Could not load commits.');
  }
});
