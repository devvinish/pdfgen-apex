# VinAura landing page for WordPress

VinAura is the product name of this project: *Visual PDF Report Designer for Oracle APEX*.
The landing page goes on vinish.dev. Its form sends each request to you by e-mail. You answer with a PayPal invoice, and after payment you send the zip.

| File | What it is |
|---|---|
| `vinaura-landing.html` | **The page.** Paste the whole file into one **Custom HTML** block. |
| `images/vinaura-*.webp` | The screenshots and PDF pages. Upload all of them to the media library. |
| `preview.html` | The same page with local pictures. Open it with `python3 -m http.server` from this folder. |
| `src/` | The sources: `body.html`, `base.css`, `extra.css`, `icons.svg`, `script.js`. |

Edit the sources, not the built files. After a change, rebuild:

```bash
python3 tools/build_landing.py
```

Retake the screenshots from the test application 2099 with `tools/shots/shoot.mjs` (shot list: `tools/shots/landing.mjs`). They use the sample reports as designed. Nothing is saved.

## Put it on WordPress

1. **Pictures.** Media > Add New: upload every file of `images/`. Upload them in the same month (2026/09), so their addresses are `https://vinish.dev/wp-content/uploads/2026/09/vinaura-….webp`. If they land in another month, change `MEDIA` in `tools/build_landing.py` and rebuild.
2. **Plugin.** The form uses the Rounds lead mailer. **Version 2.1.0** added the `product`, `company`, `country` and `licence` fields.
   - Update the plugin: Plugins > Add New > Upload Plugin > `hospora-landing/rounds-hms-lead-mailer.zip` > Replace current with uploaded.
   - The Resend settings in `wp-config.php` stay as they are.
   - The e-mail subject reads `VinAura request: <company>, <country>`.
3. **Page.**
   - Create a page with a **full-width / no sidebar** template.
   - Add a **Custom HTML** block, paste `vinaura-landing.html` into it and publish.
   - Suggested settings:
     - Slug: `vinaura`
     - SEO title: `VinAura: Visual PDF Report Designer for Oracle APEX`
     - Meta description: `Design invoices, statements and labels on a canvas, bind them to SQL queries and page items, and get the PDF with one PL/SQL call. No BI Publisher, no print server.`
   - If the slug is not `vinaura`, change `PAGE_URL` in the build script. It is used only in the JSON-LD.
4. **Cache.** LiteSpeed Cache > Purge All.
5. **Test.** Send the form on the live page and check your inbox (and spam).

## Selling: price on request

1. A request arrives by e-mail. Reply with a PayPal invoice: PayPal > Invoicing > Create invoice, with the customer's company and licence.
2. When it is paid, send the zip. `tools/make_zip.sh 1.0` builds `release/vinaura-1.0.zip`, which contains the application export, `sql/`, `docs/INSTALL.md` and `README.md`. `release/` is not committed.

## Settings on the first lines of the page

```html
<div id="vinaura-lp" class="alignfull"
     data-endpoint="/wp-json/rounds/v1/lead"   ← leave as is (the plugin's address)
     data-fallback-email="">                   ← optional: shown if the form cannot be sent
```

## Notes

- Only an Administrator (or a user with `unfiltered_html`) can save the `<script>` of a Custom HTML block.
- All CSS is scoped to `#vinaura-lp`, and every class starts with `va-`. It does not touch the theme or the Rounds page.
- Spam protection is the plugin's own: a honeypot field, a minimum time before sending, and a rate limit.
