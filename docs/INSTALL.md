# Installing the PDF Report Designer

What a database and an APEX workspace need, for development and for production, with or without the
demo tables and data.

## Requirements

- **Oracle Database 19c or later.** The code uses `JSON_OBJECT_T`, `IS JSON` and `DEFAULT ... ON CONVERSION ERROR`.
- **Oracle APEX installed in that database.** The API uses APEX types and packages (`apex_t_varchar2`, `v()`,
  `apex_application`). Importing the application `dist/pdf_report_designer.sql` needs APEX 26.1 or later.
- **A schema that owns the objects**, with `CREATE SESSION, CREATE TABLE, CREATE VIEW, CREATE SEQUENCE,
  CREATE PROCEDURE` and a quota on its tablespace.

## Where the objects live

| | A schema of its own (`PDFGEN`) | The schema of your application |
|---|---|---|
| Set-up | Create the schema, add it to the APEX workspace; for every application schema that prints: `grant execute on pdfgen.pdf_api to <app_schema>;` and, as that schema, `create synonym pdf_api for pdfgen.pdf_api;` | Nothing more |
| Good for | Several applications sharing one designer and one set of reports | One application |
| Preview in the designer | Runs the queries as `PDFGEN`: grant it `select` on the tables your reports read (or give it views) | Sees your tables directly |

The queries of a report run as the schema that calls `pdf_api` (the API has invoker rights), so in your
applications they always see that application's own tables.

If a call fails with ORA-06598 (insufficient INHERIT PRIVILEGES), a DBA has removed a default privilege:
`grant inherit privileges on user <app_schema> to pdfgen;`

## The database objects

Run the scripts in `sql/` in the order of their numbers. Every script can run again safely.

| Script | Creates | Needed |
|---|---|---|
| `10_tables.sql` | tables `PDF_REPORTS`, `PDF_QUERIES`, `PDF_IMAGES`, `PDF_LOG` | always |
| `20_pdf_writer.sql` | package `PDF_WRITER` (writes the PDF file) | always |
| `30_pdf_engine.sql` | package `PDF_ENGINE` (lays out bands, tables, labels) | always |
| `40_pdf_api.sql` | packages `PDF_REPO` and `PDF_API` (the API your applications call) | always |
| `45_pdf_designer.sql` | package `PDF_DESIGNER` (the Ajax calls of the designer, report import/export) | where the designer application runs |
| `50_demo_data.sql` | tables `PDF_DEMO_CUSTOMERS`, `PDF_DEMO_PRODUCTS`, `PDF_DEMO_INVOICES`, `PDF_DEMO_INVOICE_LINES` with their rows, view `PDF_DEMO_INVOICE_LINES_V` | demo only |
| `60_samples.sql` | the sample reports `INVOICE`, `INVOICE_BATCH`, `PRODUCT_LABELS`, `CUSTOMER_STATEMENT` and the image `demo-logo` (added only when missing, never overwritten) | demo only: the samples read the demo tables |

The application `dist/pdf_report_designer.sql` carries the same seven scripts as its *supporting objects*.

## Development

### A. With the demo tables and data

1. Create the schema (or use your application's schema) and add it to the workspace.
2. App Builder > Import `dist/pdf_report_designer.sql`, parsing schema = that schema, and choose
   **Install Supporting Objects**. This runs all seven scripts.

You get the designer, the **Demo** menu (invoices, customers, products with their PDF dialogs) and the four
sample reports.

### B. Without the demo tables and data

1. Run `10`, `20`, `30`, `40` and `45` in SQL Developer / SQLcl as the owning schema.
2. Import `dist/pdf_report_designer.sql` **without** installing the supporting objects.

The application still contains the **Demo** menu and its pages (10, 11, 20, 21, 30, 31 and the PDF dialogs
92 to 96) and three lists of values (`DEMO_CUSTOMERS`, `DEMO_PRODUCTS`, `DEMO_CATEGORIES`) that read the
`PDF_DEMO_*` tables. Without the tables those pages fail when they are opened; the rest (Reports, the designer,
Try the API, Log, How to Use) works. Hide the *Demo* entry of the navigation menu or delete those pages.

## Production

Production usually needs the engine and your reports, not the designer.

1. **Objects:** run `10`, `20`, `30` and `40` (plus the grant and synonym when the objects have a schema of
   their own). Leave out `45` unless the designer application is deployed there too; leave out `50` and `60`.
2. **Report definitions:** either
   - **Export** a report as JSON on the *Reports* page of development, and **New Report > Import** it in the
     target (needs the designer application there, or a call to `pdf_designer.import_json(<json>)`, which
     needs `45`); or
   - copy the rows of `PDF_REPORTS` and `PDF_QUERIES` with your usual deployment tools (Data Pump, a merge
     script).
3. **Images:** the JSON export does not carry images; copy the rows of `PDF_IMAGES` (logos, stamps,
   signatures) as well.
4. **Your application:** its application processes or pages call `pdf_api.generate(...)` or
   `pdf_api.download(...)` (see the *How to Use* page of the designer). Nothing else is needed.

To run the designer in production too (for example so that users can change layouts there): add `45` and
import the application without supporting objects, as in *B* above.

## Checklist

| | Development with demo | Development without demo | Production |
|---|---|---|---|
| `10`, `20`, `30`, `40` | yes | yes | yes |
| `45_pdf_designer.sql` | yes | yes | only with the designer |
| `50_demo_data.sql`, `60_samples.sql` | yes | no | no |
| Designer application | yes, with supporting objects | yes, without supporting objects; hide *Demo* | optional |
| Grant + synonym per application schema | when in a schema of its own | when in a schema of its own | when in a schema of its own |
| Report rows (`PDF_REPORTS`, `PDF_QUERIES`) | made in the designer | made in the designer | exported / copied from development |
| Image rows (`PDF_IMAGES`) | uploaded in the designer | uploaded in the designer | copied from development |
