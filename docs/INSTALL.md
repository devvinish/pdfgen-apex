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

Nothing else to do. The **Demo** menu, its pages (10, 11, 20, 21, 30, 31, the PDF dialogs 92 to 96) and their
application processes are protected by the authorization scheme **Demo installed**, which is true only when the
four `PDF_DEMO_*` tables exist. Without them the Demo menu does not show, and a demo page opened by its URL
says *The demo is not installed*. Reports, the designer, Try the API, Log and How to Use work as usual.

To add the demo later, run `50_demo_data.sql` and `60_samples.sql`: the Demo menu appears on the next page.

## Installing into your application's own schema (for example an ERP)

No new schema, no grants, no synonyms: your application calls `pdf_api` directly and the designer's
preview sees your tables.

1. **No name clashes.** Every object is called `PDF_...`. As the application schema:
   ```sql
   select object_name, object_type from user_objects where object_name like 'PDF\_%' escape '\';
   ```
   must return nothing.
2. **The objects**, as the application schema, in this order: `10_tables.sql`, `20_pdf_writer.sql`,
   `30_pdf_engine.sql`, `40_pdf_api.sql`, and `45_pdf_designer.sql` where the designer will run. Leave out
   `50_demo_data.sql` and `60_samples.sql`: no demo tables or rows in your schema.
3. **The designer** (development): App Builder > Import `dist/pdf_report_designer.sql` into the same workspace,
   with a **free application ID** (not the id of your application), **Parsing Schema** = your application's
   schema, and **without** installing the supporting objects. Its *Demo* menu stays hidden (no demo tables).
   It is a second application beside yours, on the same schema; your users never see it.
4. **In your application:** the queries of your reports read your tables and use your page items as binds
   (`where invoice_id = :P25_INVOICE_ID`); then `pdf_api.generate('ERP_INVOICE')` returns the BLOB and
   `pdf_api.download('ERP_INVOICE')` in an application process shows it (see the *How to Use* page).
5. **Production:** the same scripts `10` to `40` in the production schema, then the report rows
   (`PDF_REPORTS`, `PDF_QUERIES`) and the images (`PDF_IMAGES`), as described below.

**Upgrades:** run the changed scripts again in the same schema. Tables are created only when missing and
packages are replaced, so your reports and images stay.

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
| Designer application | yes, with supporting objects | yes, without supporting objects (*Demo* hides itself) | optional |
| Grant + synonym per application schema | only when in a schema of its own (not needed in your application's schema) | same | same |
| Report rows (`PDF_REPORTS`, `PDF_QUERIES`) | made in the designer | made in the designer | exported / copied from development |
| Image rows (`PDF_IMAGES`) | uploaded in the designer | uploaded in the designer | copied from development |
