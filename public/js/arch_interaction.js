/* Architecture interaction — GSAP + physical motion response */
(function(){
  'use strict';
  // Preserve 3D world; add GSAP-driven architecture interactions
  const stages = document.querySelectorAll('.stage-card');
  const overlay = document.getElementById('arch-overlay');
  const inner = document.getElementById('arch-inner');
  let activeStage = null;

  // Hover motion: physical lift + purple glow transition (GSAP)
  stages.forEach(s => {
    s.addEventListener('mouseenter', () => {
      if(typeof gsap !== 'undefined'){
        gsap.to(s, { y: -6, borderColor: 'rgba(138,36,126,.85)', backgroundColor: 'rgba(138,36,126,.14)', duration: 0.35, ease: 'power2.out' });
      }
      // Subtle 3D world response: dim non-active nodes slightly, brighten connections
      if(typeof window.LOCUS_3D !== 'undefined' && window.LOCUS_3D.setPhase){
        try { window.LOCUS_3D.setPhase('orbit'); } catch(e){}
      }
    }, { passive: true });
    s.addEventListener('mouseleave', () => {
      if(typeof gsap !== 'undefined'){
        gsap.to(s, { y: 0, borderColor: 'rgba(242,239,233,.12)', backgroundColor: 'rgba(146,39,143,.04)', duration: 0.3, ease: 'power2.in' });
      }
      try { if(window.LOCUS_3D && window.LOCUS_3D.setPhase) window.LOCUS_3D.setPhase('wide'); } catch(e){}
    }, { passive: true });
  });

  // Click: open overlay + camera choreography
  // Clicking a stage opens the 2D overlay over the 3D world (not replacing it)
  // The 3D world remains visible behind (readability zone preserved)
})();
