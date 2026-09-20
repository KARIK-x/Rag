from playwright.sync_api import sync_playwright

def capture():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        # Inject console listener
        page.evaluate('''() => {
            window.__consoleLogs = [];
            const orig = {error: console.error, warn: console.warn, info: console.info, log: console.log};
            ['error','warn','info','log'].forEach(t => {
                console[t] = function(...args) {
                    window.__consoleLogs.push({type: t, time: Date.now(), args: args.map(x => (x && x.stack) ? x.stack : String(x))});
                    orig[t].apply(console, args);
                };
            });
        }''')
        page.goto('http://localhost:8000', wait_until='networkidle', timeout=15000)
        results = {}
        for label, delta in [('2s', 2000), ('5s', 3000), ('8s', 3000)]:
            page.wait_for_timeout(delta)
            # Capture loader
            loader_el = page.locator('#loader')
            loader_present = loader_el.count() > 0
            loader_display = loader_el.evaluate('e => getComputedStyle(e).display') if loader_present else 'N/A'
            loader_opacity = loader_el.evaluate('e => getComputedStyle(e).opacity') if loader_present else 'N/A'
            loader_visibility = loader_el.evaluate('e => getComputedStyle(e).visibility') if loader_present else 'N/A'
            loader_z = loader_el.evaluate('e => getComputedStyle(e).zIndex') if loader_present else 'N/A'
            # Main visible sections
            main = page.locator('main')
            # Search input
            query = page.locator('#evidence-query')
            query_visible = page.evaluate('e => document.querySelector("#evidence-query") ? getComputedStyle(document.querySelector("#evidence-query")).display !== "none" && getComputedStyle(document.querySelector("#evidence-query")).visibility !== "hidden" : false')
            query_interactable = page.evaluate('() => { const el = document.querySelector("#evidence-query"); return el ? el.tabIndex >= 0 && el.offsetParent !== null : false }')
            # World canvas
            canvas = page.locator('#world-canvas')
            canvas_present = canvas.count() > 0
            canvas_visible = canvas.is_visible() if canvas_present else False
            # Sections visible in main by id
            sections = page.evaluate('''() => {
                const ids = [];
                document.querySelectorAll('main section, main div, main article').forEach(el => {
                    if (el.id) ids.push(el.id);
                });
                return ids;
            }''')
            # Network info: check resources for logo, 3d_world.js, gsap
            # We'll check via page.request or just evaluate loaded resources
            # Instead use page.evaluate to inspect document and script tags
            network_status = page.evaluate('''() => {
                const out = {};
                performance.getEntriesByType('resource').forEach(r => {
                    const url = r.name;
                    out[url] = r.responseStatus || 'loaded';
                });
                return out;
            }''')
            # JS state
            js_state = page.evaluate('''() => ({
                THREE: typeof window.THREE,
                LOCUS_3D: typeof window.LOCUS_3D,
                gsap_timeline_exists: typeof window.gsap !== 'undefined' && typeof window.gsap.timeline === 'function',
                loader_timeline_started: window.__loaderTimelineStarted || false,
                loader_hidden: document.querySelector('#loader') ? (getComputedStyle(document.querySelector('#loader')).display === 'none') : 'no loader element'
            })''')
            # Console errors so far
            logs = page.evaluate('window.__consoleLogs || []')
            results[label] = {
                'loader_present': loader_present,
                'loader_display': loader_display,
                'loader_opacity': loader_opacity,
                'loader_visibility': loader_visibility,
                'loader_z_index': loader_z,
                'main_sections': sections,
                'search_visible': query_visible,
                'search_interactable': query_interactable,
                'canvas_present': canvas_present,
                'canvas_visible': canvas_visible,
                'js_state': js_state,
                'console_errors': [l for l in logs if l['type']=='error' or l['type']=='warn'],
                'network_keys': list(network_status.keys()),
            }
        # After 8s, read console fully and network details
        full_logs = page.evaluate('window.__consoleLogs || []')
        # Network: check if assets/img/A MAIN_LOGO.png loaded
        # Check via image element complete / src
        logo_loaded = page.evaluate('''() => {
            const imgs = document.querySelectorAll('img');
            for (const img of imgs) {
                if (img.src && img.src.includes('A MAIN_LOGO')) return {complete: img.complete, naturalWidth: img.naturalWidth, src: img.src};
            }
            return null;
        }''')
        # Check 3d_world.js script tag loaded
        world_script = page.evaluate('''() => {
            const s = document.querySelector('script[src*="3d_world.js"]');
            if (!s) return null;
            return {loaded: s.getAttribute('data-loaded') === 'true', src: s.src};
        }''')
        results['final_network'] = {
            'logo_loaded': logo_loaded,
            'world_script': world_script,
            'console_errors_all': full_logs,
        }
        print("RESULTS:")
        for k,v in results.items():
            print(f"--- {k} ---")
            for kk, vv in v.items():
                print(f"  {kk}: {vv}")
        b.close()

if __name__ == '__main__':
    capture()
