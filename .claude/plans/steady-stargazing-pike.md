# Domain Transfer & Site Cutover Plan

## Context

**jaimeibrahim.com** is transferring from Squarespace (Tucows registrar) to Vercel. Transfer initiated 2026-02-12, auto-completes by **2026-02-17** (5 days). The new Next.js site in this repo is 95% built -- all routes, components, and styling are complete. The goal is zero-downtime cutover with SEO equity preserved.

**Current state:**
- Old site: Squarespace, 20 indexed URLs (11 project pages, 9 top-level pages)
- New site: Next.js 16 on Vercel, 23 pages, builds clean, Vercel project already linked (`prj_z74lBi7RngGXr9vnpznjY4jMbCI7`)
- Missing: real images (using placeholders), article body content, OG image
- No email on the domain (no MX records to preserve)

**Launch strategy:** Wait for real images before assigning the production domain. The domain transfer can complete and sit in Vercel's domain pool while we finish the image pipeline. Squarespace site will go offline when transfer completes, but the new site won't go live until images are ready -- accept a brief gap.

---

## Phase 1: Pre-Transfer Prep (Do NOW, before 2026-02-17)

### 1A. Add URL Redirects in `next.config.ts`

The old Squarespace slugs differ from the new slugs. Without redirects, Google-indexed URLs and any bookmarks/links will 404. Add permanent (308) redirects:

**File:** `next.config.ts`

```typescript
const nextConfig: NextConfig = {
  async redirects() {
    return [
      // Squarespace project slugs → new slugs
      { source: '/work/glgbrand', destination: '/work/glg-brand', permanent: true },
      { source: '/work/project-five-748cx-egbkj', destination: '/work/glg-video', permanent: true },
      { source: '/work/glgexplainer', destination: '/work/glg-explainer', permanent: true },
      { source: '/work/yearahead', destination: '/work/year-ahead', permanent: true },
      { source: '/work/tiaa-branding', destination: '/work/tiaa', permanent: true },
      { source: '/work/product-branding', destination: '/work', permanent: true },
      { source: '/work/eventbrand', destination: '/work/employee-brand', permanent: true },
      { source: '/work/opera-video', destination: '/work/opera', permanent: true },
      // Squarespace pages with no equivalent → redirect to closest match
      { source: '/contact', destination: '/about', permanent: true },
      { source: '/alt-work-section', destination: '/work', permanent: true },
      { source: '/presentation-design', destination: '/work', permanent: true },
      { source: '/digital-products-3-1', destination: '/work', permanent: true },
      { source: '/visual-brand', destination: '/work', permanent: true },
      { source: '/visual-brand-1', destination: '/work', permanent: true },
      { source: '/store', destination: '/', permanent: true },
      { source: '/cart', destination: '/', permanent: true },
    ];
  },
};
```

**Slugs that already match (no redirect needed):**
- `/work/battlebank` -> `/work/battlebank`
- `/work/liquidstock` -> `/work/liquidstock`
- `/work/construction` -> `/work/construction`
- `/about` -> `/about`
- `/work` -> `/work`

### 1B. Export DNS Records from Squarespace

**Before the transfer completes**, export/screenshot all current DNS records from the Squarespace domain settings. No email on the domain, so MX records are not a concern. Still check for:

- **TXT records** -- Google Search Console verification, SPF (if any)
- **CNAME records** -- any subdomains (www., etc.)

**Action:** Log into Squarespace Domains dashboard -> DNS Settings -> screenshot or copy all records. This is mostly precautionary since there's no email to protect.

### 1C. Pre-Generate SSL Certificate (Optional, Reduces Downtime)

Per Vercel docs, you can pre-generate SSL certs before DNS cutover:
- Add the domain to the Vercel project dashboard
- Vercel will provide a TXT record for domain verification
- Add that TXT record at Squarespace (while you still control DNS there)
- Vercel issues the SSL cert in advance

This prevents any HTTPS gap during propagation. See: https://vercel.com/docs/domains/pre-generating-ssl-certs

### 1D. Deploy Current Site to Vercel (Preview)

Ensure the latest code is pushed and a preview deployment exists:
```bash
npm run build && npx vercel
```
Verify the preview URL works correctly before assigning the production domain.

---

## Phase 2: Domain Transfer Completes (~2026-02-17)

When Tucows/Squarespace releases the domain to Vercel:

### 2A. Assign Domain to Vercel Project

In Vercel Dashboard -> Project Settings -> Domains:
1. Add `jaimeibrahim.com` (apex domain)
2. Add `www.jaimeibrahim.com` (redirect www -> apex, or vice versa)
3. Vercel will auto-configure DNS since it's now the registrar
4. SSL certificate auto-provisions (or is already ready from step 1C)

### 2B. Re-Add DNS Records (Minimal)

In Vercel Dashboard -> Domains -> `jaimeibrahim.com` -> DNS Records:
1. Re-add any **TXT records** (Google Search Console verification, if any)
2. Vercel auto-adds the A/AAAA records for the site itself
3. No MX records needed (no email on this domain)

### 2C. Production Deploy

```bash
npx vercel --prod
```

This assigns the production domain to the latest deployment.

---

## Phase 3: Post-Cutover Verification

### 3A. DNS Propagation Check
- Use `dig jaimeibrahim.com` or https://dnschecker.org to verify A record points to Vercel (`76.76.21.21`)
- Propagation typically takes 1-48 hours (usually under 1 hour with low TTL)

### 3B. Test All Redirects
Verify every old Squarespace URL redirects correctly:
```
curl -I https://jaimeibrahim.com/work/glgbrand        # -> 308 -> /work/glg-brand
curl -I https://jaimeibrahim.com/work/tiaa-branding    # -> 308 -> /work/tiaa
curl -I https://jaimeibrahim.com/contact               # -> 308 -> /about
curl -I https://jaimeibrahim.com/store                 # -> 308 -> /
# ... (all 16 redirects)
```

### 3C. SSL Verification
- Visit `https://jaimeibrahim.com` -- confirm padlock, no mixed content warnings
- Visit `https://www.jaimeibrahim.com` -- confirm redirect to apex (or vice versa)

### 3D. SEO Verification
- Submit new sitemap to Google Search Console (`https://jaimeibrahim.com/sitemap.xml`)
- Request re-indexing of key pages
- Verify `robots.txt` is accessible
- Check OG tags render correctly (use https://developers.facebook.com/tools/debug/)

---

## Phase 4: Content Completion (MUST happen before assigning production domain)

These are the remaining gaps that don't block the transfer but should be completed:

| Item | Status | Priority |
|------|--------|----------|
| Real project images (13 projects) | Placeholder colors | High |
| Portrait photo (About page) | Placeholder | High |
| OG image (`public/og-image.jpg`) | Missing | Medium |
| Article body content (4 articles) | Placeholder text | Medium |
| `scripts/optimize-images.mjs` | Not created | Medium |
| Aktiv Grotesk font license | Using Inter fallback | Low |
| IntroAnimation component | Not integrated | Low |

---

## Critical Timeline

| Date | Event | Action Required |
|------|-------|-----------------|
| 2026-02-12 | Transfer initiated | Done |
| **Now - 02-17** | **Prep window** | **Add redirects, export DNS, deploy preview** |
| ~2026-02-17 | Transfer auto-completes | Domain lands in Vercel account. **Don't assign to project yet.** Old Squarespace site goes offline. |
| 02-17 to ?? | **Image pipeline** | **Add real images, OG image, portrait. This is the blocker.** |
| When images ready | Assign domain + deploy | Assign domain to project, `npx vercel --prod`, verify |
| +1 day | Post-cutover | Test redirects, submit sitemap, verify SSL |

**Key insight:** There will be a gap between when the domain transfer completes (Squarespace goes offline) and when the new site goes live (images ready). This gap should be minimized -- ideally get images done before 02-17 so the cutover is seamless.

---

## Files to Modify

| File | Change |
|------|--------|
| `next.config.ts` | Add `redirects()` with 16 Squarespace URL mappings |
| `public/images/` | Add optimized project images (13 projects + portrait + OG) |
| (Vercel Dashboard) | Add domain, configure www redirect, re-add TXT records |
| (Google Search Console) | Submit new sitemap, verify ownership |

---

## Verification

1. `npm run build` -- confirm redirects don't break the build
2. `npx vercel` -- deploy preview, test redirect URLs on preview domain
3. After domain assignment: test all 20 old Squarespace URLs via curl/browser
4. Lighthouse audit on production domain
5. Google Search Console: check for crawl errors after 48 hours
