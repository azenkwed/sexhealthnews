# Flesh Pulse — Legal & Compliance

This document covers the legal considerations specific to running a news aggregator in the sexuality/adult content space. Flesh Pulse is a **news aggregator** — it links to articles, not host explicit content — but the topic area has specific regulatory exposure.

---

## What Flesh Pulse is (and is not)

**Is**: A news aggregator that indexes publicly available articles about sexuality, sexual health, sex work, and the adult industry. All content links back to the original publisher.

**Is not**: A pornography host, an escort directory, a cam site, a dating platform, or anything that facilitates commercial sexual services.

This distinction matters enormously for legal exposure.

---

## FOSTA-SESTA (US)

The Allow States and Victims to Fight Online Sex Trafficking Act (2018) creates civil and criminal liability for platforms that "facilitate" sex trafficking.

**Risk level for Flesh Pulse: Low.** The law targets platforms that host or enable solicitation ads. Aggregating journalism about sex work policy is protected editorial activity, not facilitation.

**What to avoid**: Do not add any feature that allows users to post ads, listings, or contact requests. Do not aggregate escort directories or adult classifieds. Stick to journalism and research.

---

## CSAM — Zero tolerance

18 U.S.C. § 2256 and equivalent laws in every jurisdiction make CSAM absolutely illegal with severe penalties.

**Flesh Pulse must**:
- Never ingest sources that could produce content sexualizing minors
- Vet all RSS sources before adding them — inspect 20+ articles manually before adding a new source
- The AI curation prompt must explicitly reject any article involving minors in a sexual context
- Add this as a hard rejection rule in the curator prompt: `"Any content involving minors in a sexual context must be scored 0.0 and rejected regardless of other factors."`
- Have a reporting mechanism (contact form minimum) for users to flag inappropriate content

---

## Age verification

Several US states (Louisiana, Utah, Texas, others) have passed laws requiring age verification for sites with "substantial" adult content. UK's Online Safety Act has similar provisions.

**Current risk for Flesh Pulse: Low.** A news aggregator linking to journalism is unlikely to be classified as a pornographic site under these laws.

**Watch**: If the site's category mix shifts heavily toward adult industry content, reconsider.

**Mitigation**: Add a terms-of-service acknowledgment at registration stating users confirm they are 18+.

---

## GDPR / Privacy (EU)

If any EU users register:
- Privacy policy required — document what data is collected and why
- Right to deletion — users can request account deletion
- Cookie consent — JWT cookies are functional (no consent required), but analytics cookies require opt-in
- Data processing agreement with Resend (email provider)

The existing Panoptiqa privacy policy template covers most of this. Update it for Flesh Pulse.

---

## Hosting terms of service

Check that your host allows adult-adjacent content:

| Provider | Adult content policy |
|---|---|
| **Fly.io** | Permitted as long as it's legal. Explicit pornographic hosting is not permitted, but news aggregation is fine. |
| **AWS / GCP / Azure** | Permitted with ToS compliance. Sexual content hosting requires content moderation. Aggregation is fine. |
| **Cloudflare** | CDN/proxy is fine. They have an Acceptable Use Policy but news aggregation is not restricted. |
| **Vercel / Netlify** | May have stricter policies — read ToS carefully before deploying there. |

---

## Payment processors

Stripe, PayPal, and most payment processors have restrictions on "adult content" businesses. However, the restriction is on businesses that **sell pornographic content**, not on news aggregators.

- Register as a media/publishing business, not as an adult content business
- Stripe works fine for media subscriptions — Panoptiqa already uses it
- Avoid "high-risk" merchant category codes (MCCs) — use standard publishing MCC

---

## DMCA safe harbor

As an aggregator, Flesh Pulse qualifies for DMCA safe harbor (17 U.S.C. § 512) provided:
- You have a registered DMCA agent (file with US Copyright Office, ~$6/year)
- You have a published DMCA takedown procedure
- You respond promptly to valid takedown notices
- You do not have actual knowledge of infringement

Linking to articles does not create infringement liability. Displaying a headline and excerpt is generally fair use for news aggregation (see *Perfect 10 v. Amazon*).

---

## Defamation

Aggregating articles that are themselves defamatory: Section 230 (Communications Decency Act) provides immunity to platforms for third-party content. Flesh Pulse does not author the articles it aggregates.

**Exception**: AI-generated summaries are authored by Flesh Pulse. Keep summaries factual and descriptive. Do not have Claude editorialize or make claims not supported by the source article.

---

## Summary checklist before launch

- [ ] Privacy policy published (covers data collection, cookies, third parties)
- [ ] Terms of service published (18+ acknowledgment, acceptable use)
- [ ] Contact/DMCA email address published
- [ ] DMCA agent registered with US Copyright Office
- [ ] All RSS sources manually vetted — no CSAM risk
- [ ] Curator prompt includes hard rejection for any minor-related sexual content
- [ ] Hosting provider ToS confirmed compatible
- [ ] Payment processor category confirmed (media/publishing, not adult)
