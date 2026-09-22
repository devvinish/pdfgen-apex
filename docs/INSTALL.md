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
| `40_pdf_api.sql` | packages `PDF_REPO` (also the report import that deploy scripts use) and `PDF_API` (the API your applications call) | always |
| `45_pdf_designer.sql` | package `PDF_DESIGNER` (the Ajax calls of the designer, report export/import, deploy scripts) | where the designer application runs |
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
5. **Production:** the same scripts `10` to `40` in the production schema, then your reports with a
   deploy script (see *Moving reports from development to production*).

**Upgrades:** run the changed scripts again in the same schema. Tables are created only when missing and
packages are replaced, so your reports and images stay.

## Production

Production usually needs the engine and your reports, not the designer.

1. **Objects:** run `10`, `20`, `30` and `40` (plus the grant and synonym when the objects have a schema of
   their own). Leave out `45` unless the designer application is deployed there too; leave out `50` and `60`.
2. **Your reports and their images:** bring them from development as described in the next section.
3. **Your application:** its application processes or pages call `pdf_api.generate(...)` or
   `pdf_api.download(...)` (see the *How to Use* page of the designer). Nothing else is needed.

To run the designer in production too (for example so that users can change layouts there): add `45` and
import the application without supporting objects, as in *B* above.

## Moving reports from development to production

A report is its layout, its queries (`PDF_REPORTS`, `PDF_QUERIES`) and the images it uses (`PDF_IMAGES`:
logos, stamps, signatures). Both ways below carry all three. The target can be another schema, another
workspace or another database.

### Way 1: a deploy script (no designer application in production)

The usual way for production: one SQL file with the reports you choose.

1. **Development:** open **Deploy** in the designer's menu.
2. Tick the reports to move, for example `INVOICE`, `CUSTOMER_STATEMENT` and `PRODUCT_LABELS`.
3. Choose what happens to reports that exist in the target already:
   - **Replace them**, for an updated layout;
   - **Leave them as they are**, to add only the new ones.
4. **Download Script.** You get `vinaura_reports_<date>.sql`.
5. **Production:** open the script in **SQL Developer** (*Run Script*, F5) or **SQLcl**. Connect as the
   schema that **owns** the VinAura tables, and run it:
   - **Your application's schema,** when VinAura is installed into it;
   - **The VinAura schema** (for example `PDFGEN`), when it has one of its own.

   For every report it prints `INVOICE: imported`, or `INVOICE: exists already, left as it is`, and it
   commits at the end.

The script needs only the tables and packages of `10` to `40` in production: no designer application and
no `45`. It is plain ASCII text, so it can go into your version control and your release process like any
other deployment script.

### Way 2: export and import one report (the designer application on both sides)

For a single report, or when the designer application runs in the target too.

1. **Development:** on **Reports**, click **JSON** in the *Export* column of the report. You get
   `<code>.pdfreport.json`, with the report's images inside.
2. **Target:** in the designer application there, click **Import** on the *Reports* page. A dialog opens:
   1. Choose the `.json` file. For a small report you can paste its text instead.
   2. **Code of the new report:** leave it empty to keep the code of the export. If that code is taken,
      give a new one, for example `INVOICE_V2`.
   3. **Update the report if this code exists:** leave it off, and the import only adds reports: when the
      code is taken it stops with a message, so nothing is overwritten. Turn it on to update that report.
   4. **Import.** The dialog closes and the designer opens with the imported report.

The same import from PL/SQL, as the schema that owns the tables:

```sql
declare
  l_id number;
begin
  l_id := pdf_repo.import_report(p_json => :json_of_the_export, p_code => null, p_replace => 'N');
  commit;
end;
```

### Good to know

- **Same image names, one image.** Images are shared by name: importing a report whose logo is called
  `company-logo` updates the `company-logo` of the target, and every report that uses that name shows it.
- **An image from a query,** for example `{Q1.PHOTO}`, is data: it stays in your tables and does not travel
  with the report.
- **Queries run as the calling schema.** A report's queries read the tables of the schema that calls
  `pdf_api`, so check that production has the same tables and columns as development.
- **Copying rows with your own tools** (Data Pump, a merge script) works too: take `PDF_REPORTS`,
  `PDF_QUERIES` and `PDF_IMAGES`.

## Checklist

| | Development with demo | Development without demo | Production |
|---|---|---|---|
| `10`, `20`, `30`, `40` | yes | yes | yes |
| `45_pdf_designer.sql` | yes | yes | only with the designer |
| `50_demo_data.sql`, `60_samples.sql` | yes | no | no |
| Designer application | yes, with supporting objects | yes, without supporting objects (*Demo* hides itself) | optional |
| Grant + synonym per application schema | only when in a schema of its own (not needed in your application's schema) | same | same |
| Report rows (`PDF_REPORTS`, `PDF_QUERIES`) | made in the designer | made in the designer | a deploy script from development |
| Image rows (`PDF_IMAGES`) | uploaded in the designer | uploaded in the designer | in the same deploy script |
