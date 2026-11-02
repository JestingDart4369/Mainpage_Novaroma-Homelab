const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Exercise the actual page script, not a duplicate rendering function.
const html = fs.readFileSync(path.join(__dirname, '../app/template/Activity.html'), 'utf8');
const script = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].at(-1)[1];

async function render(message, fail = false) {
  const writes = [];
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
    document: {
      getElementById: id => id === 'commit-list' ? list : element('button'),
      createElement: element,
    },
    fetch: async () => ({ ok: !fail, json: async () => [{ commit: { message } }] }),
  });
  vm.runInContext(script.replace(/loadCommits\(\);\s*$/, ''), context);
  await vm.runInContext('loadCommits()', context);
  return { list, writes };
}

test('GitHub commit messages are rendered as literal text, never parsed HTML', async () => {
  const message = '<img src=x onerror="globalThis.pwned=true"> & <script>alert(1)</script>';
  const { list, writes } = await render(message + '\nsecond line');
  assert.deepEqual(writes, [], 'Untrusted commit text reached innerHTML');
  assert.equal(list.children.length, 3);
  for (const item of list.children) {
    assert.equal(item.className, 'commit-item');
    assert.equal(item.children[1].className, 'commit-msg');
    assert.equal(item.children[1].textContent, message);
  }
});

test('failed GitHub requests retain the existing fallback message and CSS classes', async () => {
  const { list, writes } = await render('', true);
  assert.deepEqual(writes, [], 'Fallback rendering should use the same safe DOM path');
  assert.equal(list.children.length, 3);
  for (const item of list.children) {
    assert.equal(item.children[0].className, 'commit-repo');
    assert.equal(item.children[1].textContent, 'Could not load commits.');
  }
});
