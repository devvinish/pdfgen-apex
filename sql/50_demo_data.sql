-- PDF Report Designer: demo tables and rows for the sample reports (invoice, batch invoices, labels).
-- Idempotent: the tables are created once and filled only when empty.
set define off

declare
  procedure run(p_sql varchar2) is
  begin
    execute immediate p_sql;
  exception
    when others then
      if sqlcode not in (-955) then
        raise;
      end if;
  end;
begin
  run(q'[create table pdf_demo_customers (
    customer_id number primary key,
    name        varchar2(200) not null,
    address     varchar2(400),
    city        varchar2(100),
    state       varchar2(100),
    pincode     varchar2(10),
    gstin       varchar2(20),
    phone       varchar2(30),
    email       varchar2(200))]');
  run(q'[create table pdf_demo_products (
    product_id  number primary key,
    sku         varchar2(30) not null,
    name        varchar2(200) not null,
    category    varchar2(100),
    hsn         varchar2(10),
    unit        varchar2(10),
    price       number(12,2),
    tax_rate    number(5,2))]');
  run(q'[create table pdf_demo_invoices (
    invoice_id   number primary key,
    invoice_no   varchar2(30) not null,
    invoice_date date not null,
    due_date     date,
    customer_id  number not null references pdf_demo_customers,
    status       varchar2(20),
    notes        varchar2(1000))]');
  run(q'[create table pdf_demo_invoice_lines (
    invoice_id   number not null references pdf_demo_invoices,
    line_no      number not null,
    product_id   number not null references pdf_demo_products,
    description  varchar2(400),
    qty          number(10,2),
    unit_price   number(12,2),
    discount_pct number(5,2) default 0,
    constraint pdf_demo_invoice_lines_pk primary key (invoice_id, line_no))]');
end;
/

declare
  l number;
begin
  select count(*) into l from pdf_demo_customers;
  if l > 0 then
    return;
  end if;
  insert into pdf_demo_customers values (1, 'Apollo Care Clinics Pvt. Ltd.', '4th Floor, Sigma Tech Park, Whitefield Main Road', 'Bengaluru', 'Karnataka', '560066', '29AACCA1234K1Z2', '+91 80 4123 5500', 'accounts@apollocare.example');
  insert into pdf_demo_customers values (2, 'Sunrise Diagnostics', '22 Park Street', 'Kolkata', 'West Bengal', '700016', '19AAFCS8821L1ZQ', '+91 33 2229 1010', 'billing@sunrise.example');
  insert into pdf_demo_customers values (3, 'Green Valley Hospital', 'NH-44, Sector 12', 'Panipat', 'Haryana', '132103', '06AABCG4455M1Z9', '+91 180 266 7788', 'purchase@greenvalley.example');
  insert into pdf_demo_customers values (4, 'MediPlus Pharmacy', 'Shop 7, Linking Road, Bandra West', 'Mumbai', 'Maharashtra', '400050', '27AAKFM9090P1Z4', '+91 22 2640 3030', 'orders@mediplus.example');
  insert into pdf_demo_customers values (5, 'City Heart Institute', '15 Anna Salai', 'Chennai', 'Tamil Nadu', '600002', '33AACCC7788Q1Z1', '+91 44 2852 6000', 'finance@cityheart.example');

  insert into pdf_demo_products values (101, 'NW-GLV-100', 'Nitrile examination gloves (box of 100)', 'Consumables', '4015', 'BOX', 420, 12);
  insert into pdf_demo_products values (102, 'NW-MSK-050', 'Surgical face masks, 3-ply (box of 50)', 'Consumables', '6307', 'BOX', 180, 5);
  insert into pdf_demo_products values (103, 'NW-SYR-005', 'Disposable syringe 5 ml (pack of 100)', 'Consumables', '9018', 'PCK', 650, 12);
  insert into pdf_demo_products values (104, 'NW-BPM-200', 'Digital blood pressure monitor', 'Equipment', '9018', 'NOS', 2450, 12);
  insert into pdf_demo_products values (105, 'NW-OXI-010', 'Fingertip pulse oximeter', 'Equipment', '9018', 'NOS', 1150, 12);
  insert into pdf_demo_products values (106, 'NW-THR-020', 'Infrared thermometer', 'Equipment', '9025', 'NOS', 1890, 18);
  insert into pdf_demo_products values (107, 'NW-SAN-500', 'Hand sanitiser 500 ml', 'Consumables', '3808', 'BTL', 210, 18);
  insert into pdf_demo_products values (108, 'NW-BND-075', 'Crepe bandage 7.5 cm', 'Consumables', '3005', 'NOS', 55, 12);
  insert into pdf_demo_products values (109, 'NW-CTN-500', 'Absorbent cotton roll 500 g', 'Consumables', '3005', 'ROL', 240, 12);
  insert into pdf_demo_products values (110, 'NW-GWN-001', 'Disposable isolation gown', 'Consumables', '6210', 'NOS', 95, 12);
  insert into pdf_demo_products values (111, 'NW-STH-300', 'Dual-head stethoscope', 'Equipment', '9018', 'NOS', 1350, 12);
  insert into pdf_demo_products values (112, 'NW-NEB-400', 'Compressor nebuliser', 'Equipment', '9019', 'NOS', 2890, 12);
  insert into pdf_demo_products values (113, 'NW-GLU-110', 'Glucometer with 25 strips', 'Equipment', '9027', 'NOS', 990, 12);
  insert into pdf_demo_products values (114, 'NW-STR-050', 'Glucometer strips (pack of 50)', 'Consumables', '3822', 'PCK', 780, 12);
  insert into pdf_demo_products values (115, 'NW-IVS-001', 'IV infusion set', 'Consumables', '9018', 'NOS', 38, 12);
  insert into pdf_demo_products values (116, 'NW-CAN-020', 'IV cannula 20G', 'Consumables', '9018', 'NOS', 42, 12);
  insert into pdf_demo_products values (117, 'NW-WCH-500', 'Folding wheelchair', 'Equipment', '8713', 'NOS', 7800, 5);
  insert into pdf_demo_products values (118, 'NW-STR-900', 'Aluminium stretcher', 'Equipment', '9402', 'NOS', 9400, 18);
  insert into pdf_demo_products values (119, 'NW-ECG-060', 'ECG electrodes (pack of 60)', 'Consumables', '9018', 'PCK', 560, 12);
  insert into pdf_demo_products values (120, 'NW-DRS-010', 'Sterile gauze dressing 10x10 cm (pack of 100)', 'Consumables', '3005', 'PCK', 320, 12);

  insert into pdf_demo_invoices values (1001, 'NW/2026-27/0418', date '2026-09-02', date '2026-10-02', 1, 'PAID', 'Delivered to the central store, Whitefield. Payment received by NEFT, ref. UTR 2026090245512.');
  insert into pdf_demo_invoices values (1002, 'NW/2026-27/0419', date '2026-09-05', date '2026-10-05', 2, 'DUE', 'Please quote the invoice number with your payment.');
  insert into pdf_demo_invoices values (1003, 'NW/2026-27/0420', date '2026-09-09', date '2026-10-09', 3, 'DUE', 'Quarterly supply for the new wing. Goods once sold will not be taken back.');
  insert into pdf_demo_invoices values (1004, 'NW/2026-27/0421', date '2026-09-12', date '2026-10-12', 4, 'PAID', null);
  insert into pdf_demo_invoices values (1005, 'NW/2026-27/0422', date '2026-09-18', date '2026-10-18', 5, 'DUE', 'Installation and demonstration of the equipment included.');

  -- 1001: a short invoice
  insert into pdf_demo_invoice_lines values (1001, 1, 104, null, 4, 2450, 0);
  insert into pdf_demo_invoice_lines values (1001, 2, 105, null, 10, 1150, 5);
  insert into pdf_demo_invoice_lines values (1001, 3, 101, null, 25, 420, 0);
  insert into pdf_demo_invoice_lines values (1001, 4, 107, 'Hand sanitiser 500 ml - fragrance free, for the ICU', 40, 210, 0);
  insert into pdf_demo_invoice_lines values (1001, 5, 111, null, 6, 1350, 0);
  -- 1002 .. 1005
  insert into pdf_demo_invoice_lines values (1002, 1, 113, null, 12, 990, 0);
  insert into pdf_demo_invoice_lines values (1002, 2, 114, null, 30, 780, 2.5);
  insert into pdf_demo_invoice_lines values (1002, 3, 119, null, 20, 560, 0);
  insert into pdf_demo_invoice_lines values (1004, 1, 102, null, 60, 180, 0);
  insert into pdf_demo_invoice_lines values (1004, 2, 108, null, 200, 55, 0);
  insert into pdf_demo_invoice_lines values (1004, 3, 109, null, 50, 240, 0);
  insert into pdf_demo_invoice_lines values (1005, 1, 112, null, 3, 2890, 0);
  insert into pdf_demo_invoice_lines values (1005, 2, 117, null, 2, 7800, 0);
  insert into pdf_demo_invoice_lines values (1005, 3, 118, null, 1, 9400, 0);
  insert into pdf_demo_invoice_lines values (1005, 4, 106, null, 5, 1890, 0);
  -- 1003: a long invoice that runs over several pages
  for i in 1 .. 46 loop
    insert into pdf_demo_invoice_lines
    select 1003, i, product_id,
           case when mod(i, 7) = 0 then name || ' - batch ' || to_char(2600 + i) || ', expiry 03/2029, stored at 2-8 C in the pharmacy cold room' end,
           mod(i * 7, 23) + 2, price, case when mod(i, 5) = 0 then 5 else 0 end
      from pdf_demo_products where product_id = 101 + mod(i * 3, 20);
  end loop;
  commit;
end;
/

-- more demo rows for the demo screens (added once: customers 6..12, invoices 1006..1035)
declare
  l number;
  l_inv number;
  l_lines number;
begin
  select count(*) into l from pdf_demo_customers where customer_id >= 6;
  if l > 0 then
    return;
  end if;
  insert into pdf_demo_customers values (6, 'Lotus Multispeciality Hospital', '88 Ring Road, Near Bus Stand', 'Surat', 'Gujarat', '395002', '24AACCL5566R1Z8', '+91 261 245 0011', 'stores@lotus.example');
  insert into pdf_demo_customers values (7, 'Care and Cure Clinic', '3 Gandhi Nagar, 2nd Cross', 'Mysuru', 'Karnataka', '570009', '29AAKFC1122S1Z3', '+91 821 241 7788', 'admin@carecure.example');
  insert into pdf_demo_customers values (8, 'Sanjeevani Nursing Home', 'Civil Lines', 'Jaipur', 'Rajasthan', '302006', '08AAFFS3344T1Z6', '+91 141 222 3344', 'accounts@sanjeevani.example');
  insert into pdf_demo_customers values (9, 'Metro Diagnostics Lab', 'B-12, Sector 18', 'Noida', 'Uttar Pradesh', '201301', '09AAHCM7788U1Z2', '+91 120 451 9900', 'lab@metrodx.example');
  insert into pdf_demo_customers values (10, 'Sunshine Children''s Hospital', '14 Banjara Hills Road No. 3', 'Hyderabad', 'Telangana', '500034', '36AACCS9900V1Z5', '+91 40 2335 6677', 'purchase@sunshinekids.example');
  insert into pdf_demo_customers values (11, 'Kerala Ayur Wellness', 'MG Road, Ernakulam', 'Kochi', 'Kerala', '682016', '32AAKFK2211W1Z7', '+91 484 236 5500', 'office@ayurwell.example');
  insert into pdf_demo_customers values (12, 'Northeast Medical Centre', 'GS Road, Christian Basti', 'Guwahati', 'Assam', '781005', '18AACCN4433X1Z4', '+91 361 234 8800', 'billing@nemc.example');

  for i in 1 .. 30 loop
    l_inv := 1005 + i;
    insert into pdf_demo_invoices values (
      l_inv, 'NW/2026-27/' || to_char(422 + i, 'FM0000'),
      date '2026-08-01' + trunc((i - 1) * 1.7),
      date '2026-08-01' + trunc((i - 1) * 1.7) + 30,
      mod(i * 5, 12) + 1,
      case when mod(i, 3) = 0 then 'DUE' when mod(i, 7) = 0 then 'CANCELLED' else 'PAID' end,
      case mod(i, 4) when 0 then 'Delivered by courier. Please quote the invoice number with your payment.'
                     when 1 then 'Goods once sold will not be taken back.' end);
    l_lines := mod(i * 7, 9) + 2;
    for n in 1 .. l_lines loop
      insert into pdf_demo_invoice_lines
      select l_inv, n, product_id, null, mod(i * n * 3, 17) + 1, price, case when mod(i + n, 6) = 0 then 5 else 0 end
        from pdf_demo_products where product_id = 101 + mod(i * 7 + n * 3, 20);
    end loop;
  end loop;
  commit;
end;
/

-- the lines of an invoice with their amounts (the grid of the invoice screen reads it; it saves to the table)
create or replace view pdf_demo_invoice_lines_v as
select l.invoice_id || ':' || l.line_no line_key,
       l.invoice_id, l.line_no, l.product_id, l.description, l.qty, l.unit_price, l.discount_pct,
       p.sku, p.hsn, p.tax_rate,
       round(l.qty * l.unit_price * (1 - nvl(l.discount_pct, 0) / 100), 2) taxable,
       round(l.qty * l.unit_price * (1 - nvl(l.discount_pct, 0) / 100) * (1 + p.tax_rate / 100), 2) amount
  from pdf_demo_invoice_lines l
  join pdf_demo_products p on p.product_id = l.product_id
/
