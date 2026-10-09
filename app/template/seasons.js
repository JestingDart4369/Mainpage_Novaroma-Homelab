/* Hidden seasons mode. Click the footer "© 2026 ..." line 5x to toggle.
   State is stored in the cookie "novaroma_seasons" (on/off). Default: off. */
(function () {
  var COOKIE = 'novaroma_seasons';
  var root = document.documentElement;

  function getCookie() {
    var m = document.cookie.match(new RegExp('(?:^|; )' + COOKIE + '=([^;]*)'));
    return m ? m[1] : 'off';
  }
  function setCookie(v) {
    document.cookie = COOKIE + '=' + v + '; max-age=31536000; path=/; SameSite=Lax' +
      (location.protocol === 'https:' ? '; Secure' : '');
  }
  function currentSeason() {
    var m = new Date().getMonth(); // northern hemisphere
    if (m >= 2 && m <= 4) return 'spring';
    if (m >= 5 && m <= 7) return 'summer';
    if (m >= 8 && m <= 10) return 'autumn';
    return 'winter';
  }

  var CFG = {
    spring: { chars: ['🌸', '🌱', '🌷'], speed: 1, drift: 1, count: 22, label: '🌸 Spring' },
    summer: { chars: ['☀️', '✨', '🦋'], speed: .6, drift: 1.4, count: 14, label: '☀️ Summer' },
    autumn: { chars: ['🍂', '🍁', '🍃'], speed: 1.2, drift: 1.6, count: 26, label: '🍂 Autumn' },
    winter: { chars: ['❄️', '❅', '❆'], speed: .9, drift: .8, count: 40, label: '❄️ Winter' }
  };

  var canvas, raf, parts = [];

  function startFx(season) {
    var c = CFG[season];
    canvas = document.createElement('canvas');
    canvas.id = 'season-fx';
    canvas.setAttribute('aria-hidden', 'true');
    document.body.appendChild(canvas);
    var ctx = canvas.getContext('2d');
    function resize() { canvas.width = innerWidth; canvas.height = innerHeight; }
    resize();
    addEventListener('resize', resize);
    parts = [];
    for (var i = 0; i < c.count; i++) {
      parts.push({
        x: Math.random() * innerWidth, y: Math.random() * innerHeight,
        s: 12 + Math.random() * 16, v: (.4 + Math.random() * .9) * c.speed,
        p: Math.random() * 6.28, ch: c.chars[i % c.chars.length]
      });
    }
    (function tick() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      parts.forEach(function (q) {
        q.y += q.v; q.p += .02;
        q.x += Math.sin(q.p) * c.drift * .6;
        if (q.y > canvas.height + 20) { q.y = -20; q.x = Math.random() * canvas.width; }
        ctx.font = q.s + 'px serif';
        ctx.fillText(q.ch, q.x, q.y);
      });
      raf = requestAnimationFrame(tick);
    })();
  }
  function stopFx() {
    cancelAnimationFrame(raf);
    if (canvas) { canvas.remove(); canvas = null; }
  }

  function apply(on) {
    if (on) {
      var s = currentSeason();
      root.setAttribute('data-season', s);
      if (document.body && !canvas && !matchMedia('(prefers-reduced-motion: reduce)').matches) startFx(s);
    } else {
      root.removeAttribute('data-season');
      stopFx();
    }
  }

  function toast(text) {
    var b = document.createElement('div');
    b.className = 'season-badge';
    b.textContent = text;
    document.body.appendChild(b);
    requestAnimationFrame(function () { b.classList.add('show'); });
    setTimeout(function () { b.classList.remove('show'); setTimeout(function () { b.remove(); }, 500); }, 2200);
  }

  // Set theme immediately (script runs in <head>) to avoid a flash.
  if (getCookie() === 'on') root.setAttribute('data-season', currentSeason());

  document.addEventListener('DOMContentLoaded', function () {
    if (getCookie() === 'on') apply(true);

    var el = document.querySelector('footer p');
    if (!el) return;
    var clicks = 0, timer;
    var live = document.createElement('div');
    live.setAttribute('role', 'status');
    live.setAttribute('aria-live', 'polite');
    live.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)';
    document.body.appendChild(live);
    function hit() {
      clicks++;
      clearTimeout(timer);
      timer = setTimeout(function () { clicks = 0; }, 1500);
      if (clicks >= 5) {
        clicks = 0;
        var on = getCookie() !== 'on';
        setCookie(on ? 'on' : 'off');
        apply(on);
        var msg = on ? CFG[currentSeason()].label + ' mode on' : 'Seasons mode off';
        toast(msg);
        live.textContent = msg;
      }
    }
    el.addEventListener('click', hit);
    // keyboard users: Enter / Space five times
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); hit(); }
    });
  });
})();
