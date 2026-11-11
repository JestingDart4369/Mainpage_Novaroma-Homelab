// Activity page: menu toggle + latest commits for every repo listed in site-data.json.
(function (root) {
  var PER_REPO = 3;
  var MAX_ITEMS = 24;

  function commitItem(repo, message, date) {
    var item = document.createElement('div');
    item.className = 'commit-item';
    var name = document.createElement('p');
    name.className = 'commit-repo';
    name.textContent = date ? repo.split('/')[1] + ' • ' + date : repo.split('/')[1];
    var text = document.createElement('p');
    text.className = 'commit-msg';
    text.textContent = message;
    item.appendChild(name);
    item.appendChild(text);
    return item;
  }

  function formatDate(iso) {
    var d = new Date(iso);
    return isNaN(d) ? '' : d.toISOString().slice(0, 10);
  }

  async function fetchRepo(repo) {
    var res = await fetch('/github/repos/' + repo + '/commits?per_page=' + PER_REPO);
    if (!res.ok) throw new Error('commit request failed');
    var commits = await res.json();
    return commits.map(function (c) {
      var when = (c.commit.committer || c.commit.author || {}).date || '';
      return { repo: repo, message: c.commit.message.split('\n')[0], when: when };
    });
  }

  async function loadCommits() {
    var list = document.getElementById('commit-list');
    var repos;
    try {
      var res = await fetch('/site-data.json');
      if (!res.ok) throw new Error('site data request failed');
      repos = (await res.json()).repos.map(function (r) { return r.owner + '/' + r.name; });
    } catch (e) {
      list.innerHTML = '';
      list.appendChild(commitItem('github', 'Could not load commits.'));
      return;
    }
    var results = await Promise.all(repos.map(function (repo) {
      return fetchRepo(repo).catch(function () { return { failed: repo }; });
    }));
    list.innerHTML = '';
    var commits = [];
    results.forEach(function (r) {
      if (r.failed) list.appendChild(commitItem(r.failed, 'Could not load commits.'));
      else commits = commits.concat(r);
    });
    commits.sort(function (a, b) { return b.when < a.when ? -1 : b.when > a.when ? 1 : 0; });
    commits.slice(0, MAX_ITEMS).forEach(function (c) {
      list.appendChild(commitItem(c.repo, c.message, formatDate(c.when)));
    });
  }

  function init() {
    var btn = document.getElementById('menu-btn');
    btn.addEventListener('click', function () {
      document.getElementById('nav-links').classList.toggle('open');
      btn.classList.toggle('open');
    });
    loadCommits();
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { loadCommits: loadCommits, commitItem: commitItem };
  else init();
})(this);
