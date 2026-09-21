(function(){
  var root = document.getElementById('vinaura-lp');
  if (!root) return;
  root.classList.add('va-js');
  /* sit flush under the site header: clear the top spacing WordPress wrappers add above this block,
     climbing only while the block is the first thing inside each wrapper */
  (function(){
    var el = root;
    root.style.setProperty('margin-top', '0', 'important');
    var visible = function(n){ return n.nodeType === 1 && !/^(SCRIPT|STYLE|LINK|META|NOSCRIPT|TEMPLATE)$/.test(n.tagName) && (n.offsetHeight > 0 || n.offsetWidth > 0); };
    while (el.parentElement && el.parentElement !== document.body && el.parentElement !== document.documentElement) {
      var p = el.parentElement, first = null;
      for (var i = 0; i < p.children.length; i++) { if (visible(p.children[i])) { first = p.children[i]; break; } }
      if (first !== el) { el.style.setProperty('margin-top', '0', 'important'); break; }
      el.style.setProperty('margin-top', '0', 'important');
      p.style.setProperty('padding-top', '0', 'important');
      p.style.setProperty('border-top-width', '0', 'important');
      el = p;
    }
    el.style.setProperty('margin-top', '0', 'important');
    var bs = getComputedStyle(document.body);
    if (parseFloat(bs.marginTop) || parseFloat(bs.marginLeft)) document.body.style.setProperty('margin', '0', 'important');
  })();

  /* full width without the scrollbar, wherever the theme put the block */
  function fit(){
    var cw = document.documentElement.clientWidth, st = root.style, imp = 'important';
    st.setProperty('position', 'relative', imp);
    st.setProperty('left', '0', imp); st.setProperty('right', 'auto', imp);
    st.setProperty('margin-left', '0', imp); st.setProperty('margin-right', '0', imp);
    st.setProperty('max-width', '100vw', imp);
    st.setProperty('width', cw + 'px', imp);
    var x = root.getBoundingClientRect().left;
    st.setProperty('margin-left', (-x) + 'px', imp);
  }
  fit(); window.addEventListener('resize', fit); window.addEventListener('load', fit);
  if ('ResizeObserver' in window && root.parentElement) new ResizeObserver(function(){ fit(); }).observe(root.parentElement);
  var $ = function(s, c){ return (c || root).querySelector(s); };
  var $$ = function(s, c){ return Array.prototype.slice.call((c || root).querySelectorAll(s)); };
  /* pictures: from the media library on vinish.dev; anywhere else (a local copy of the page,
     or before they are uploaded) from the images folder next to the page */
  var MEDIA = 'https://vinish.dev/wp-content/uploads/';
  var localPic = function(url){ return 'images/' + url.split('/').pop(); };
  var useLocal = !/(^|\.)vinish\.dev$/.test(location.hostname);
  $$('img[src^="' + MEDIA + '"], [data-zoom^="' + MEDIA + '"]').forEach(function(el){
    var z = el.getAttribute('data-zoom');
    if (useLocal && z) el.setAttribute('data-zoom', localPic(z));
    if (el.tagName !== 'IMG') return;
    var toLocal = function(){ if (el.src.indexOf(MEDIA) === 0) el.src = localPic(el.src); };
    if (useLocal) toLocal();
    else {
      el.addEventListener('error', toLocal);
      if (el.complete && !el.naturalWidth) toLocal();
    }
  });
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* smooth scrolling that clears a sticky site header */
  root.addEventListener('click', function(e){
    var a = e.target.closest('a[href^="#va-"]');
    if (!a) return;
    var t = document.getElementById(a.getAttribute('href').slice(1));
    if (!t) return;
    e.preventDefault();
    var y = t.getBoundingClientRect().top + window.pageYOffset - 96;
    window.scrollTo({ top: y, behavior: reduce ? 'auto' : 'smooth' });
  });

  /* header: mega panels that grow out of the bar, menu button, shadow once scrolled */
  var nav = $('.va-nav'), bar = $('.va-bar', nav), burger = $('.va-burger', nav);
  var panels = $$('.va-panel', nav), triggers = $$('.va-nl[data-panel]', nav), current = null, hoverAt = 0, closeT = 0;
  var hover = window.matchMedia && window.matchMedia('(hover: hover)').matches;
  function show(name){
    clearTimeout(closeT);
    current = name;
    bar.classList.toggle('va-open', !!name);
    if (name) panels.forEach(function(p){ p.classList.toggle('va-on', p.getAttribute('data-panel') === name); });
    triggers.forEach(function(t){ var on = t.getAttribute('data-panel') === name; t.classList.toggle('va-act', on); t.setAttribute('aria-expanded', on); });
    burger.classList.toggle('va-x', name === 'all');
    burger.setAttribute('aria-expanded', name === 'all');
    burger.setAttribute('aria-label', name === 'all' ? 'Close menu' : 'Open menu');
  }
  panels.forEach(function(p){ $$('li, .va-pgroup h4', p).forEach(function(li, i){ li.style.setProperty('--d', i); }); });
  triggers.forEach(function(t){
    var name = t.getAttribute('data-panel');
    t.addEventListener('click', function(e){ e.stopPropagation(); if (Date.now() - hoverAt < 500) return; show(current === name ? null : name); });
    if (hover) t.addEventListener('mouseenter', function(){ if (current !== name) { hoverAt = Date.now(); show(name); } });
  });
  if (hover) {
    bar.addEventListener('mouseenter', function(){ clearTimeout(closeT); });
    bar.addEventListener('mouseleave', function(){ if (current && current !== 'all') closeT = setTimeout(function(){ show(null); }, 180); });
  }
  burger.addEventListener('click', function(e){ e.stopPropagation(); show(current === 'all' ? null : 'all'); });
  $$('.va-panel a', nav).forEach(function(a){ a.addEventListener('click', function(){ show(null); }); });
  document.addEventListener('click', function(e){ if (current && !bar.contains(e.target)) show(null); });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape' && current) show(null); });
  var onScroll = function(){ nav.classList.toggle('va-scrolled', window.pageYOffset > 24); };
  onScroll(); window.addEventListener('scroll', onScroll, { passive: true });

  /* reveal on scroll */
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(en){ if (en.isIntersecting) { en.target.classList.add('va-seen'); io.unobserve(en.target); } });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    $$('.va-reveal').forEach(function(el, i){ el.style.transitionDelay = (i % 3) * 80 + 'ms'; io.observe(el); });
  } else {
    $$('.va-reveal').forEach(function(el){ el.classList.add('va-seen'); });
  }

  /* "Inside VinAura" showcase: rotates between the screens until someone picks one */
  var showcase = $('.va-show');
  if (showcase) {
    var tabs = $$('.va-seg button', showcase), shots = $$('.va-show-stage img', showcase), cap = $('.va-show-cap', showcase), ttl = $('.va-show-title', showcase);
    var seg = $('.va-seg', showcase);
    var cur = 0, shotTimer = 0, autoOn = !reduce, inView = false, DUR = 5500;
    var go = function(i){
      cur = i;
      shots.forEach(function(im, k){ im.classList.toggle('va-on', k === i); });
      tabs.forEach(function(t, k){ t.classList.toggle('va-on', k === i); t.setAttribute('aria-selected', k === i); });
      if (ttl) ttl.textContent = shots[i].getAttribute('data-title');
      if (cap) cap.textContent = shots[i].getAttribute('data-cap');
      var t = tabs[i]; if (seg && seg.scrollWidth > seg.clientWidth) seg.scrollTo({ left: t.offsetLeft - (seg.clientWidth - t.offsetWidth) / 2, behavior: reduce ? 'auto' : 'smooth' });
    };
    var restartBar = function(){ var b = $('.va-show-bar i', showcase); showcase.classList.remove('va-auto'); void b.offsetWidth; if (autoOn && inView) showcase.classList.add('va-auto'); };
    var tick = function(){ clearTimeout(shotTimer); if (!autoOn || !inView) return; restartBar(); shotTimer = setTimeout(function(){ go((cur + 1) % shots.length); tick(); }, DUR); };
    showcase.style.setProperty('--dur', DUR + 'ms');
    tabs.forEach(function(t){ t.addEventListener('click', function(){ autoOn = false; clearTimeout(shotTimer); showcase.classList.remove('va-auto'); go(+t.getAttribute('data-show')); }); });
    $$('.va-show-stage img', showcase).forEach(function(im){ im.setAttribute('data-zoom', im.getAttribute('src')); });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function(en){ inView = en[0].isIntersecting; if (inView) tick(); else { clearTimeout(shotTimer); showcase.classList.remove('va-auto'); } }, { threshold: .4 }).observe(showcase);
    }
  }

  /* slabs settle into place as they arrive */
  if ('IntersectionObserver' in window && !reduce) {
    var slabIO = new IntersectionObserver(function(en){ en.forEach(function(e){ if (e.isIntersecting) { e.target.classList.add('va-in'); slabIO.unobserve(e.target); } }); }, { threshold: 0, rootMargin: '0px 0px -12% 0px' });
    $$('.va-slab').forEach(function(el){ slabIO.observe(el); });
  } else { $$('.va-slab').forEach(function(el){ el.classList.add('va-in'); }); }

  /* the call-out lights up word by word while it scrolls through */
  var wordsEl = $('.va-words');
  if (wordsEl) {
    var parts = wordsEl.textContent.trim().split(/\s+/);
    wordsEl.innerHTML = parts.map(function(w){ return '<span>' + w + '</span>'; }).join(' ');
    var spans = $$('span', wordsEl), ticking = false;
    var paint = function(){
      ticking = false;
      var r = wordsEl.getBoundingClientRect(), vh = window.innerHeight;
      var p = reduce ? 1 : Math.max(0, Math.min(1, (vh * 0.9 - r.top) / (vh * 0.55 + r.height * 0.6)));
      var lit = Math.round(p * spans.length);
      spans.forEach(function(sp, i){ sp.classList.toggle('va-lit', i < lit); });
    };
    window.addEventListener('scroll', function(){ if (!ticking) { ticking = true; requestAnimationFrame(paint); } }, { passive: true });
    paint();
  }

  /* hero: fawn on load, then brand blue */
  var heroEl = $('.va-hero');
  if (heroEl) setTimeout(function(){ heroEl.classList.add('va-lit'); }, reduce ? 0 : 650);

  /* footer word mark: sized to run the full width of the footer */
  var mark = $('.va-foot-mark'), markText = mark && $('span', mark);
  if (markText) {
    var FIT = 0.99;
    var fitMark = function(){
      mark.style.fontSize = '100px';
      var w = markText.getBoundingClientRect().width, box = mark.getBoundingClientRect().width;
      if (w && box) mark.style.fontSize = (100 * box * FIT / w) + 'px';
    };
    var offBy = function(){ return Math.abs(markText.getBoundingClientRect().width - mark.getBoundingClientRect().width * FIT); };
    fitMark();
    window.addEventListener('resize', fitMark);
    window.addEventListener('load', fitMark);
    if (document.fonts) {
      if (document.fonts.load) document.fonts.load('600 100px "Inter Tight"').then(fitMark, function(){});
      if (document.fonts.ready) document.fonts.ready.then(fitMark);
    }
    if ('ResizeObserver' in window) new ResizeObserver(function(){ if (offBy() > 2) fitMark(); }).observe(markText);
  }

  /* code blocks: a light PL/SQL colouring and a copy button */
  var KW = 'select|from|where|join|on|and|or|order|by|group|as|into|update|set|insert|values|delete|declare|begin|end|is|null|not|in|create|grant|execute|to|synonym|for|then|if|else|return|loop|distinct|round|nvl';
  var kwRe = new RegExp('^(' + KW + ')$', 'i');
  var esc = function(s){ return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); };
  function highlight(src){
    // comments, strings, binds, numbers and words, in one pass so nothing is coloured twice
    var re = /(--[^\n]*)|('(?:[^']|'')*')|(:[A-Za-z][\w$#]*)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][\w$#]*)/g, out = '', last = 0, m;
    while ((m = re.exec(src))) {
      out += esc(src.slice(last, m.index));
      if (m[1]) out += '<span class="c">' + esc(m[1]) + '</span>';
      else if (m[2]) out += '<span class="s">' + esc(m[2]) + '</span>';
      else if (m[3]) out += '<span class="b">' + esc(m[3]) + '</span>';
      else if (m[4]) out += '<span class="n">' + m[4] + '</span>';
      else out += kwRe.test(m[5]) ? '<span class="k">' + m[5] + '</span>' : esc(m[5]);
      last = re.lastIndex;
    }
    return out + esc(src.slice(last));
  }
  $$('.va-code pre code').forEach(function(c){
    var bar = c.closest('.va-code').querySelector('.va-code-bar span');
    if (bar && /url|attributes/i.test(bar.textContent)) return;   // a URL is not PL/SQL
    c.innerHTML = highlight(c.textContent);
  });
  $$('.va-copy').forEach(function(b){
    b.addEventListener('click', function(){
      var text = b.closest('.va-code').querySelector('pre').textContent, label = $('span', b);
      var done = function(){ b.classList.add('va-done'); label.textContent = 'Copied'; setTimeout(function(){ b.classList.remove('va-done'); label.textContent = 'Copy'; }, 1600); };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, function(){});
      else {
        var ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); done(); } catch(_){} document.body.removeChild(ta);
      }
    });
  });

  /* lightbox for screenshots and PDF pages */
  var lb = $('.va-lb');
  if (lb && lb.showModal) {
    var lbImg = $('img', lb), lbCap = $('p', lb);
    root.addEventListener('click', function(e){
      var z = e.target.closest('[data-zoom]');
      if (!z || !root.contains(z)) return;
      e.preventDefault();
      var img = z.tagName === 'IMG' ? z : $('img', z);
      lbImg.src = z.getAttribute('data-zoom');
      lbImg.alt = img ? img.alt : '';
      lbCap.textContent = z.getAttribute('data-cap') || '';
      lb.showModal();
    });
    $('.va-lb-close', lb).addEventListener('click', function(){ lb.close(); });
    lb.addEventListener('click', function(e){ if (e.target === lb) lb.close(); });
  }

})();
