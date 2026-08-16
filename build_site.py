#!/usr/bin/env python3
"""
Getekend — site-generator
==========================
Leest een map met foto's, herkent automatisch de tekenaar/festival/type
op basis van de bestandsnaam, en bouwt de volledige index.html opnieuw op.

GEBRUIK
-------
1. Zet al je foto's (mét de originele bestandsnamen) in een map, bv. "raw_photos/"
2. Draai:  python3 build_site.py raw_photos/
3. Klaar: images/ en index.html worden (opnieuw) opgebouwd.

BESTANDSNAAM-CONVENTIE
-----------------------
  Achternaam__Voornaam.jpg
      -> portret, geen festival bekend

  Achternaam__Voornaam__Locatie__JJ_.jpg
      -> portret, genomen op Locatie in 20JJ

  Achternaam__Voornaam_-_Titel.jpg
      -> cover van boek "Titel"

  Achternaam__Voornaam_-_Titel_tek__Locatie__JJ_.jpg
      -> opdracht/tekening in "Titel", gemaakt op Locatie in 20JJ
         (het woordje "tek" ergens in de titel betekent: dit is een
          getekende opdracht, geen cover)

Onbekende of dubbelzinnige bestanden komen NIET verloren te gaan: ze
staan aan het eind in review.txt zodat je ze met de hand kunt nakijken.
"""

import os, re, sys, json, shutil
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    print("Dit script heeft Pillow nodig: pip install Pillow")
    sys.exit(1)

MAXDIM = 900
QUALITY = 68

LOC_YEAR_RE = re.compile(r'_{1,2}([A-Za-zÀ-ÿ]+(?:_[A-Za-zÀ-ÿ]+)*)_{1,2}(\d{2})_*$')


def clean_words(s):
    return re.sub(r'_+', ' ', s).strip()


def parse_filename(stem):
    """Return dict with achternaam, voornaam, type, titel, locatie, jaar — or None if unparseable."""
    if not stem:
        return None

    # 1. Strip a trailing __Locatie__JJ_ (or _Locatie_JJ_) suffix from the whole stem first.
    locatie = jaar = None
    m = LOC_YEAR_RE.search(stem)
    core = stem
    if m:
        locatie = clean_words(m.group(1))
        jaar = '20' + m.group(2)
        core = stem[:m.start()]

    # 2. Normalise alternative title-separators (a lone "-" got lost in some files,
    #    leaving a run of 3+ underscores instead) so both read the same way.
    core_norm = re.sub(r'_{3,}', '_-_', core)

    # 3. Split off the name part from an optional title part. Tolerate the dash
    #    touching a word directly (no underscore on one side), which happens
    #    in some of the older filenames.
    if '-' in core_norm:
        name_part, titel_raw = re.split(r'_*-_*', core_norm, maxsplit=1)
    else:
        name_part, titel_raw = core_norm, ''

    name_tokens = [t for t in re.split(r'_+', name_part) if t]
    if not name_tokens:
        return None
    achternaam = name_tokens[0]
    voornaam = ' '.join(name_tokens[1:])

    if titel_raw:
        has_tek = re.search(r'(^|_)tek(_|$)', titel_raw, re.IGNORECASE) is not None
        titel_clean = re.sub(r'(^|_)tek(_|$)', '_', titel_raw, flags=re.IGNORECASE)
        titel_clean = clean_words(titel_clean)
        soort = 'opdracht' if (has_tek or not titel_clean) else 'cover'
    else:
        titel_clean = None
        soort = 'portret'

    # A lone mononym (e.g. "Baba") is still worth keeping, even without a voornaam.
    return dict(achternaam=achternaam, voornaam=voornaam, soort=soort,
                 titel=titel_clean, locatie=locatie, jaar=jaar)


def slugify(s):
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'x'


def process_images(raw_dir, images_dir):
    raw_dir = Path(raw_dir)
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    artists = {}   # key -> {achternaam, voornaam, portret, opdrachten:[], covers:[], festivals:set}
    review = []

    files = sorted([f for f in raw_dir.iterdir() if f.suffix.lower() in ('.jpg', '.jpeg', '.png')])
    print(f"Gevonden: {len(files)} foto's in {raw_dir}")

    for f in files:
        stem = f.stem
        info = parse_filename(stem)
        if info is None:
            review.append(f"ONBEGRIJPELIJK: {f.name}")
            continue

        key = slugify(info['achternaam']) + '-' + slugify(info['voornaam'])
        if key not in artists:
            artists[key] = dict(
                achternaam=info['achternaam'], voornaam=info['voornaam'],
                portret=None, opdrachten=[], covers=[], festivals=[]
            )
        entry = artists[key]

        # target filename
        idx = len(entry['opdrachten']) + len(entry['covers']) + (1 if entry['portret'] else 0)
        out_name = f"{key}-{info['soort']}{'' if idx == 0 else '-' + str(idx)}.jpg"
        out_path = images_dir / out_name

        try:
            im = Image.open(f)
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            if max(w, h) > MAXDIM:
                scale = MAXDIM / max(w, h)
                im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            im.convert('RGB').save(out_path, quality=QUALITY, optimize=True)
        except Exception as e:
            review.append(f"KON NIET VERWERKEN ({e}): {f.name}")
            continue

        rel = f"images/{out_name}"
        if info['soort'] == 'portret':
            if entry['portret']:
                review.append(f"MEERDERE PORTRETTEN, extra genegeerd: {f.name}")
            else:
                entry['portret'] = rel
        elif info['soort'] == 'opdracht':
            entry['opdrachten'].append(dict(src=rel, titel=info['titel']))
        else:
            entry['covers'].append(dict(src=rel, titel=info['titel']))

        if info['locatie'] and info['jaar']:
            fest = f"{info['locatie']} {info['jaar']}"
            if fest not in entry['festivals']:
                entry['festivals'].append(fest)

    return artists, review


TEMPLATE_HEAD = """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Getekend — verzameling stripfestival-ontmoetingen</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,500&family=JetBrains+Mono:wght@400;500;700&family=Caveat:wght@500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --paper:#efe8d8; --paper-alt:#e6dcc6; --card:#faf7ee; --ink:#211d17;
    --ink-soft:#57503f; --red:#a9392a; --green:#33553f; --gold:#b6822b;
    --line:#c9bd9d; --tag-shadow: rgba(33,29,23,0.18);
  }
  *{box-sizing:border-box;}
  body{margin:0;background:radial-gradient(ellipse at top left, #f4efe0 0%, var(--paper) 55%),repeating-linear-gradient(0deg, transparent, transparent 27px, rgba(90,80,55,0.05) 28px);color:var(--ink);font-family:'Fraunces', serif;-webkit-font-smoothing:antialiased;}
  a{color:inherit;} ::selection{background:var(--gold); color:var(--card);}
  .hero{max-width:920px;margin:0 auto;padding:5.5rem 1.5rem 3rem;border-bottom:1px solid var(--line);}
  .hero .eyebrow{font-family:'JetBrains Mono', monospace;font-size:0.72rem;letter-spacing:0.14em;text-transform:uppercase;color:var(--red);display:inline-block;padding:0.25rem 0.6rem;border:1px solid var(--red);border-radius:2px;margin-bottom:1.4rem;}
  .hero h1{font-size:clamp(3rem, 9vw, 5.6rem);line-height:0.92;margin:0 0 0.3em 0;font-weight:600;letter-spacing:-0.01em;}
  .hero h1 em{font-style:italic;font-weight:500;color:var(--green);}
  .hero p{max-width:46ch;font-size:1.15rem;color:var(--ink-soft);line-height:1.55;}
  .hero .scrawl{font-family:'Caveat', cursive;font-size:1.6rem;color:var(--red);display:inline-block;margin-top:0.6rem;transform:rotate(-2deg);}
  .index-wrap{max-width:920px;margin:0 auto;padding:3rem 1.5rem 6rem;}
  .index-hint{font-family:'JetBrains Mono', monospace;font-size:0.78rem;color:var(--ink-soft);letter-spacing:0.03em;margin-bottom:2rem;}
  .letter-group{margin-bottom:1.2rem;}
  .letter-group > .letter{font-family:'Fraunces', serif;font-style:italic;font-weight:500;font-size:2.6rem;color:transparent;-webkit-text-stroke:1px var(--ink-soft);line-height:1;margin:0 0 0.6rem 0;user-select:none;}
  .entry{border-top:1px solid var(--line);}
  .entry:last-child{border-bottom:1px solid var(--line);}
  .entry-tag{display:flex;align-items:center;justify-content:space-between;gap:1rem;width:100%;background:none;border:none;text-align:left;cursor:pointer;padding:1.05rem 0.2rem;font-family:inherit;}
  .entry-tag:hover .name-plate{background:var(--card);transform:translateY(-2px) rotate(-0.4deg);box-shadow:0 6px 14px var(--tag-shadow);}
  .name-plate{font-family:'JetBrains Mono', monospace;font-weight:700;font-size:0.95rem;letter-spacing:0.02em;background:var(--paper-alt);padding:0.5rem 0.9rem;border-radius:3px;box-shadow:0 2px 5px var(--tag-shadow);transition:all 0.18s ease;white-space:nowrap;}
  .entry-meta{font-family:'JetBrains Mono', monospace;font-size:0.72rem;color:var(--ink-soft);flex:1;text-align:right;letter-spacing:0.02em;}
  .chev{font-size:1.1rem;color:var(--red);transition:transform 0.25s ease;flex-shrink:0;width:1.2em;text-align:center;}
  .entry.open .chev{transform:rotate(45deg);}
  .panel{max-height:0;overflow:hidden;transition:max-height 0.4s ease;}
  .entry.open .panel{max-height:2400px;}
  .panel-inner{padding:0.4rem 0.2rem 2.4rem;display:flex;gap:1.5rem;flex-wrap:wrap;align-items:flex-start;}
  .photo-card{background:var(--card);padding:0.6rem 0.6rem 0.9rem;box-shadow:0 8px 18px rgba(33,29,23,0.14);width:210px;cursor:zoom-in;transition:transform 0.2s ease;}
  .photo-card:nth-child(odd){transform:rotate(-1.4deg);}
  .photo-card:nth-child(even){transform:rotate(1.1deg);}
  .photo-card:hover{transform:scale(1.03) rotate(0deg); z-index:2;}
  .photo-card img{width:100%;display:block;background:#ddd;}
  .photo-card .cap{font-family:'Caveat', cursive;font-size:1.15rem;color:var(--ink-soft);padding-top:0.5rem;text-align:center;}
  .bio{flex:1;min-width:220px;padding-top:0.3rem;}
  .bio h3{font-size:1.5rem;font-weight:600;margin:0 0 0.3rem;}
  .bio .festivals{font-family:'JetBrains Mono', monospace;font-size:0.75rem;color:var(--green);letter-spacing:0.02em;line-height:1.8;}
  .bio .festivals span{display:inline-block;background:rgba(51,85,63,0.08);padding:0.15rem 0.5rem;border-radius:2px;margin:0 0.3rem 0.3rem 0;}
  .lightbox{position:fixed; inset:0;background:rgba(20,17,12,0.92);display:none;align-items:center;justify-content:center;z-index:50;padding:2rem;}
  .lightbox.show{display:flex;}
  .lightbox img{max-width:92vw;max-height:88vh;box-shadow:0 20px 60px rgba(0,0,0,0.5);}
  .lightbox-close{position:absolute;top:1.5rem; right:1.8rem;font-family:'JetBrains Mono', monospace;color:var(--paper);font-size:1.6rem;cursor:pointer;background:none;border:none;}
  footer{text-align:center;font-family:'JetBrains Mono', monospace;font-size:0.72rem;color:var(--ink-soft);padding:2.5rem 1.5rem 3.5rem;}
  .alpha-nav{position:sticky;top:0;z-index:10;background:var(--paper);border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;justify-content:center;gap:0.15rem;padding:0.7rem 1rem;font-family:'JetBrains Mono', monospace;font-size:0.85rem;font-weight:500;}
  .alpha-nav a, .alpha-nav span{width:1.7em;height:1.7em;display:flex;align-items:center;justify-content:center;border-radius:2px;text-decoration:none;}
  .alpha-nav a{color:var(--ink);background:var(--card);box-shadow:0 1px 3px var(--tag-shadow);transition:all 0.15s ease;}
  .alpha-nav a:hover{background:var(--red);color:var(--paper);transform:translateY(-1px);}
  .alpha-nav span{color:var(--line);}
  .search-wrap{max-width:920px;margin:1.5rem auto 0;padding:0 1.5rem;}
  .search-box{width:100%;font-family:'JetBrains Mono', monospace;font-size:0.95rem;padding:0.7rem 1rem;border:1px solid var(--line);border-radius:4px;background:var(--card);color:var(--ink);box-sizing:border-box;}
  .search-box:focus{outline:none;border-color:var(--red);}
  .search-box::placeholder{color:var(--ink-soft);}
  .no-results{display:none;padding:2rem 0.2rem;color:var(--ink-soft);font-style:italic;}
  .no-results.show{display:block;}
  @media (max-width:560px){.hero{padding:3.5rem 1.2rem 2rem;} .index-wrap{padding:2rem 1.2rem 4rem;} .entry-meta{display:none;} .photo-card{width:44%;}}
</style>
</head>
<body>

<section class="hero">
  <span class="eyebrow">Persoonlijk archief · signeersessies</span>
  <h1>Get<em>e</em>kend</h1>
  <p>Portretten, opdrachten en covers verzameld op stripfestivals.</p>
  <span class="scrawl">klik op een naam om de foto's te bekijken →</span>
</section>

<nav class="alpha-nav" id="alpha-nav"></nav>

<div class="search-wrap">
  <input type="text" class="search-box" id="search-box" placeholder="Zoek op naam…" oninput="filterEntries()">
</div>

<div class="index-wrap">
  <div class="index-hint">alfabetisch · {count} tekenaars · klik om te openen</div>
"""

TEMPLATE_TAIL = """  </div>
  <div class="no-results" id="no-results">Geen tekenaar gevonden.</div>
</div>

<footer>gearchiveerd voor Leon</footer>

<div class="lightbox" id="lightbox" onclick="closeLightbox(event)">
  <button class="lightbox-close" onclick="closeLightbox(event)">✕</button>
  <img id="lightbox-img" src="" alt="">
</div>

<script>
(function buildAlphaNav(){
  const nav = document.getElementById('alpha-nav');
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  for(const letter of alphabet){
    const target = document.getElementById('letter-' + letter);
    if(target){
      const a = document.createElement('a');
      a.href = '#letter-' + letter;
      a.textContent = letter;
      nav.appendChild(a);
    } else {
      const span = document.createElement('span');
      span.textContent = letter;
      nav.appendChild(span);
    }
  }
})();

function toggleEntry(btn){
  const entry = btn.closest('.entry');
  const wasOpen = entry.classList.contains('open');
  document.querySelectorAll('.entry.open').forEach(e => e.classList.remove('open'));
  if(!wasOpen){
    entry.classList.add('open');
    setTimeout(() => entry.scrollIntoView({behavior:'smooth', block:'nearest'}), 150);
  }
}
function openLightbox(src){
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lightbox').classList.add('show');
}
function closeLightbox(e){
  if(e.target.id === 'lightbox' || e.target.classList.contains('lightbox-close')){
    document.getElementById('lightbox').classList.remove('show');
  }
}
document.addEventListener('keydown', e => { if(e.key === 'Escape') document.getElementById('lightbox').classList.remove('show'); });

function filterEntries(){
  const q = document.getElementById('search-box').value.trim().toLowerCase();
  const groups = document.querySelectorAll('.letter-group');
  let anyVisible = false;
  groups.forEach(group => {
    let groupHasMatch = false;
    group.querySelectorAll('.entry').forEach(entry => {
      const name = entry.querySelector('.name-plate').textContent.toLowerCase();
      const match = q === '' || name.includes(q);
      entry.style.display = match ? '' : 'none';
      if(match) groupHasMatch = true;
    });
    group.style.display = groupHasMatch ? '' : 'none';
    if(groupHasMatch) anyVisible = true;
  });
  document.getElementById('no-results').classList.toggle('show', !anyVisible);
  document.querySelectorAll('.alpha-nav a').forEach(a => {
    const letter = a.textContent;
    const grp = document.getElementById('letter-' + letter);
    const visible = grp && grp.style.display !== 'none';
    a.style.opacity = (q === '' || visible) ? '1' : '0.35';
  });
}
</script>
</body>
</html>
"""


def render_entry(key, e):
    naam = f"{e['achternaam']}, {e['voornaam']}" if e['voornaam'] else e['achternaam']
    meta = ' · '.join(e['festivals']) if e['festivals'] else ''
    photos_html = ''
    if e['portret']:
        photos_html += f'''
          <div class="photo-card" onclick="openLightbox('{e['portret']}')">
            <img src="{e['portret']}" alt="{naam}, portret" loading="lazy">
            <div class="cap">portret</div>
          </div>'''
    for o in e['opdrachten']:
        cap = f"opdracht — {o['titel']}" if o['titel'] else "opdracht"
        photos_html += f'''
          <div class="photo-card" onclick="openLightbox('{o['src']}')">
            <img src="{o['src']}" alt="Opdracht van {naam}" loading="lazy">
            <div class="cap">{cap}</div>
          </div>'''
    for c in e['covers']:
        cap = f"cover — {c['titel']}" if c['titel'] else "cover"
        photos_html += f'''
          <div class="photo-card" onclick="openLightbox('{c['src']}')">
            <img src="{c['src']}" alt="Cover, {naam}" loading="lazy">
            <div class="cap">{cap}</div>
          </div>'''

    fest_spans = ''.join(f'<span>{f}</span>' for f in e['festivals'])

    return f'''
    <div class="entry" data-key="{key}">
      <button class="entry-tag" onclick="toggleEntry(this)">
        <span class="name-plate">{naam}</span>
        <span class="entry-meta">{meta}</span>
        <span class="chev">+</span>
      </button>
      <div class="panel">
        <div class="panel-inner">
          <div class="bio">
            <h3>{e['voornaam']} {e['achternaam']}</h3>
            <div class="festivals">{fest_spans}</div>
          </div>{photos_html}
        </div>
      </div>
    </div>'''


def build_html(artists):
    sorted_keys = sorted(artists.keys(), key=lambda k: (artists[k]['achternaam'].lower(), artists[k]['voornaam'].lower()))
    html = TEMPLATE_HEAD.replace('{count}', str(len(artists)))
    current_letter = None
    for key in sorted_keys:
        e = artists[key]
        letter = e['achternaam'][0].upper()
        if letter != current_letter:
            if current_letter is not None:
                html += '\n  </div>\n'
            html += f'\n  <div class="letter-group" id="letter-{letter}">\n    <div class="letter">{letter}</div>\n'
            current_letter = letter
        html += render_entry(key, e)
    if current_letter is not None:
        html += '\n  </div>\n'
    html += TEMPLATE_TAIL
    return html


def main():
    if len(sys.argv) < 2:
        print("Gebruik: python3 build_site.py <map_met_rauwe_fotos> [output_map]")
        sys.exit(1)
    raw_dir = sys.argv[1]
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('.')
    images_dir = out_dir / 'images'

    artists, review = process_images(raw_dir, images_dir)
    print(f"Herkend: {len(artists)} tekenaars")

    html = build_html(artists)
    (out_dir / 'index.html').write_text(html, encoding='utf-8')
    print(f"Geschreven: {out_dir/'index.html'}")

    if review:
        review_path = out_dir / 'review.txt'
        review_path.write_text('\n'.join(review), encoding='utf-8')
        print(f"LET OP: {len(review)} bestand(en) kon(den) niet automatisch herkend worden.")
        print(f"        Zie {review_path} voor de lijst.")
    else:
        print("Alle bestanden herkend, niets voor handmatige controle.")


if __name__ == '__main__':
    main()
