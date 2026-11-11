// Shared page behaviour: mobile menu toggle and the API status indicator.
(function () {
  var API_HEALTH_URL = 'https://api.novaroma-homelab.uk/health';

  var menuBtn = document.getElementById('menu-btn');
  var navLinks = document.getElementById('nav-links');
  if (menuBtn && navLinks) {
    menuBtn.addEventListener('click', function () {
      navLinks.classList.toggle('open');
    });
  }

  var status = document.getElementById('api-status');
  if (status) {
    fetch(API_HEALTH_URL, { cache: 'no-store' })
      .then(function (res) {
        status.textContent = res.ok ? 'Online — API responding: ' + res.status : 'Offline';
      })
      .catch(function () {
        status.textContent = 'Offline';
      });
  }
})();
