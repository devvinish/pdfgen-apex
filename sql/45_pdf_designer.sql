-- PDF Report Designer: the Ajax calls of the designer page (application processes of the designer app).
-- Every procedure writes a JSON answer with htp; an error comes back as {"problem": "..."}.
set define off

create or replace package pdf_designer authid definer as

  -- {"id","code","name","description","layout":{..},"queries":[{"alias","title","sql"}]}
  procedure load_report(p_report_id number);
  -- p_json: {"layout":{..},"queries":[{"alias","title","sql"}],"name":..,"description":..}
  procedure save_report(p_report_id number, p_json clob);
  -- {"columns":[..],"binds":[..]}
  procedure describe_query(p_sql clob);
  -- {"pdf":"<base64>","pages":n,"ms":n}
  procedure preview(p_json clob);
  -- [{"name","width","height","url"}]
  procedure list_images;
  -- p_data: a data URL or base64 of a JPEG
  procedure save_image(p_name varchar2, p_data clob);
  procedure delete_image(p_name varchar2);
  -- the image itself (for <img src>): GET application process with x01 = name
  procedure image(p_name varchar2);
  -- {"data": "data:image/jpeg;base64,..."}
  procedure image_data(p_name varchar2);

  -- a new report; returns its id (from the dialog "New Report")
  function create_report(p_code varchar2, p_name varchar2, p_description varchar2,
                         p_type varchar2 default 'report', p_size varchar2 default 'A4',
                         p_orientation varchar2 default 'portrait', p_copy_of varchar2 default null) return number;

  function base64(p_blob blob) return clob;
  function unbase64(p_data clob) return blob;

  -- the JSON of a report for export: its layout, queries and the images it uses
  function export_json(p_report_id number) return clob;
  -- its import; p_code: the code it gets here (null: the exported one);
  -- p_replace: Y replaces a report with that code, N raises an error when one exists
  function import_json(p_json clob, p_code varchar2 default null, p_replace varchar2 default 'N') return number;
  -- a SQL script that puts the reports (codes) and their images into another schema / database:
  -- run it there as the schema that owns the PDF_ tables. p_replace: Y replaces reports that exist
  -- there, N leaves them as they are
  function deploy_script(p_codes apex_t_varchar2, p_replace varchar2 default 'Y') return clob;

end pdf_designer;
/

create or replace package body pdf_designer as

  procedure print_clob(p clob) is
    l_len number := dbms_lob.getlength(p);
    l_pos number := 1;
  begin
    while l_pos <= l_len loop
      sys.htp.prn(dbms_lob.substr(p, 8000, l_pos));
      l_pos := l_pos + 8000;
    end loop;
  end;

  procedure json_header is
  begin
    sys.owa_util.mime_header('application/json', true, 'utf-8');
  end;

  procedure print_error(p_msg varchar2) is
    l json_object_t := json_object_t();
    l_msg varchar2(4000) := regexp_replace(p_msg, '^ORA-2[0-9]{4}: ', null);
  begin
    -- the first line only, without the error stack of the packages
    l_msg := regexp_replace(l_msg, chr(10) || 'ORA-06512.*$', null, 1, 0, 'n');
    l.put('problem', l_msg);
    print_clob(l.to_clob);
  end;

  function base64(p_blob blob) return clob is
  begin
    return pdf_repo.base64(p_blob);
  end;

  function unbase64(p_data clob) return blob is
  begin
    return pdf_repo.unbase64(p_data);
  end;

  function report_json(p_report_id number, p_with_id boolean, p_images boolean default false) return json_object_t is
    l_out  json_object_t := json_object_t();
    l_qs   json_array_t := json_array_t();
    l_q    json_object_t;
    l_imgs json_array_t := json_array_t();
    l_img  json_object_t;
  begin
    for r in (select * from pdf_reports where report_id = p_report_id) loop
      if p_with_id then
        l_out.put('id', r.report_id);
      end if;
      l_out.put('code', r.code);
      l_out.put('name', r.name);
      l_out.put('description', r.description);
      l_out.put('layout', json_object_t.parse(nvl(r.layout, '{}')));
    end loop;
    for q in (select alias, title, sql_text from pdf_queries where report_id = p_report_id order by seq, alias) loop
      l_q := json_object_t();
      l_q.put('alias', q.alias);
      l_q.put('title', q.title);
      l_q.put('sql', q.sql_text);
      l_qs.append(l_q);
    end loop;
    l_out.put('queries', l_qs);
    if p_images then
      -- the images the layout uses by name (not the images of a query: {Q1.PHOTO})
      for i in (select name, width, height, content
                  from pdf_images
                 where name in (select jt.src
                                  from pdf_reports r,
                                       json_table(r.layout, '$.bands.*.elements[*]'
                                                  columns (type varchar2(20) path '$.type',
                                                           src  varchar2(200) path '$.src')) jt
                                 where r.report_id = p_report_id and jt.type = 'image' and jt.src not like '{%')
                 order by name) loop
        l_img := json_object_t();
        l_img.put('name', i.name);
        l_img.put('width', i.width);
        l_img.put('height', i.height);
        l_img.put('data', base64(i.content));
        l_imgs.append(l_img);
      end loop;
      l_out.put('images', l_imgs);
    end if;
    return l_out;
  end;

  procedure load_report(p_report_id number) is
    l_n number;
  begin
    json_header;
    select count(*) into l_n from pdf_reports where report_id = p_report_id;
    if l_n = 0 then
      print_error('The report does not exist any more.');
      return;
    end if;
    print_clob(report_json(p_report_id, true).to_clob);
  exception
    when others then
      print_error(sqlerrm);
  end;

  procedure save_queries(p_report_id number, p_queries json_array_t) is
    l_q     json_object_t;
    l_alias varchar2(10);
    l_title varchar2(200);
    l_sql   clob;
  begin
    delete from pdf_queries where report_id = p_report_id;
    for i in 0 .. p_queries.get_size - 1 loop
      l_q := treat(p_queries.get(i) as json_object_t);
      l_alias := upper(l_q.get_string('alias'));
      l_title := substr(l_q.get_string('title'), 1, 200);
      l_sql := l_q.get_clob('sql');
      if trim(dbms_lob.substr(l_sql, 4000, 1)) is not null then
        insert into pdf_queries (report_id, alias, seq, title, sql_text)
        values (p_report_id, l_alias, i + 1, l_title, l_sql);
      end if;
    end loop;
  end;

  procedure save_report(p_report_id number, p_json clob) is
    l_in     json_object_t;
    l_out    json_object_t := json_object_t();
    l_layout clob;
    l_name   varchar2(200);
    l_desc   varchar2(4000);
    l_hasd   varchar2(1);
  begin
    json_header;
    -- (the methods of the JSON objects cannot be called inside SQL)
    l_in := json_object_t.parse(p_json);
    l_layout := l_in.get_object('layout').to_clob;
    l_name := substr(l_in.get_string('name'), 1, 200);
    l_desc := substr(l_in.get_string('description'), 1, 4000);
    l_hasd := case when l_in.has('description') then 'Y' else 'N' end;
    update pdf_reports
       set layout = l_layout,
           name = nvl(l_name, name),
           description = case when l_hasd = 'Y' then l_desc else description end,
           updated_by = coalesce(v('APP_USER'), user),
           updated_on = sysdate
     where report_id = p_report_id;
    if sql%rowcount = 0 then
      print_error('The report does not exist any more.');
      return;
    end if;
    save_queries(p_report_id, l_in.get_array('queries'));
    commit;
    l_out.put('ok', true);
    l_out.put('saved', to_char(sysdate, 'HH24:MI'));
    print_clob(l_out.to_clob);
  exception
    when others then
      rollback;
      print_error(sqlerrm);
  end;

  procedure describe_query(p_sql clob) is
  begin
    json_header;
    print_clob(pdf_api.describe(p_sql));
  exception
    when others then
      print_error(sqlerrm);
  end;

  procedure preview(p_json clob) is
    l_in    json_object_t := json_object_t.parse(p_json);
    l_pdf   blob;
    l_out   json_object_t := json_object_t();
    l_start number := dbms_utility.get_time;
    l_params clob;
  begin
    json_header;
    if l_in.has('params') and l_in.get('params').is_object then
      l_params := l_in.get_object('params').to_clob;
    end if;
    l_pdf := pdf_api.preview(l_in.get_object('layout').to_clob, l_in.get_array('queries').to_clob,
                             l_params, l_in.get_string('name'));
    l_out.put('pages', pdf_api.last_page_count);
    l_out.put('bytes', dbms_lob.getlength(l_pdf));
    l_out.put('ms', (dbms_utility.get_time - l_start) * 10);
    l_out.put('pdf', base64(l_pdf));
    print_clob(l_out.to_clob);
  exception
    when others then
      print_error(sqlerrm);
  end;

  procedure list_images is
    l_arr json_array_t := json_array_t();
    l_o   json_object_t;
  begin
    json_header;
    for i in (select name, width, height from pdf_images order by lower(name)) loop
      l_o := json_object_t();
      l_o.put('name', i.name);
      l_o.put('width', i.width);
      l_o.put('height', i.height);
      l_arr.append(l_o);
    end loop;
    print_clob(l_arr.to_clob);
  exception
    when others then
      print_error(sqlerrm);
  end;

  procedure save_image(p_name varchar2, p_data clob) is
    l_blob blob;
    l_w    number;
    l_h    number;
    l_c    number;
    l_out  json_object_t := json_object_t();
    l_name varchar2(200) := trim(substr(p_name, 1, 200));
  begin
    json_header;
    if l_name is null then
      print_error('Give the image a name.');
      return;
    end if;
    l_blob := unbase64(p_data);
    pdf_writer.jpeg_info(l_blob, l_w, l_h, l_c);
    merge into pdf_images i
    using (select l_name name from dual) s on (i.name = s.name)
    when matched then update set content = l_blob, width = l_w, height = l_h, mime_type = 'image/jpeg'
    when not matched then insert (name, mime_type, width, height, content) values (l_name, 'image/jpeg', l_w, l_h, l_blob);
    commit;
    l_out.put('name', l_name);
    l_out.put('width', l_w);
    l_out.put('height', l_h);
    print_clob(l_out.to_clob);
  exception
    when others then
      rollback;
      print_error(sqlerrm);
  end;

  procedure delete_image(p_name varchar2) is
  begin
    json_header;
    delete from pdf_images where name = p_name;
    commit;
    sys.htp.prn('{"ok":true}');
  exception
    when others then
      print_error(sqlerrm);
  end;

  procedure image(p_name varchar2) is
    l_blob blob;
  begin
    select content into l_blob from pdf_images where name = p_name;
    sys.owa_util.mime_header('image/jpeg', false);
    sys.htp.p('Content-Length: ' || dbms_lob.getlength(l_blob));
    sys.htp.p('Cache-Control: private, max-age=300');
    sys.owa_util.http_header_close;
    sys.wpg_docload.download_file(l_blob);
  exception
    when no_data_found then
      sys.owa_util.status_line(404, 'Not Found');
  end;

  procedure image_data(p_name varchar2) is
    l_blob blob;
    l_out  clob;
  begin
    json_header;
    select content into l_blob from pdf_images where name = p_name;
    l_out := '{"data":"data:image/jpeg;base64,';
    dbms_lob.append(l_out, base64(l_blob));
    dbms_lob.append(l_out, '"}');
    print_clob(l_out);
  exception
    when no_data_found then
      print_error('No image named ' || p_name);
  end;

  -- page sizes in points (portrait)
  procedure page_size(p_size varchar2, o_w out number, o_h out number) is
  begin
    case upper(p_size)
      when 'A3' then o_w := 841.89; o_h := 1190.55;
      when 'A5' then o_w := 419.53; o_h := 595.28;
      when 'LETTER' then o_w := 612; o_h := 792;
      when 'LEGAL' then o_w := 612; o_h := 1008;
      else o_w := 595.28; o_h := 841.89;
    end case;
  end;

  function create_report(p_code varchar2, p_name varchar2, p_description varchar2,
                         p_type varchar2 default 'report', p_size varchar2 default 'A4',
                         p_orientation varchar2 default 'portrait', p_copy_of varchar2 default null) return number is
    l_id     number;
    l_layout json_object_t;
    l_page   json_object_t := json_object_t();
    l_mar    json_object_t := json_object_t();
    l_bands  json_object_t := json_object_t();
    l_band   json_object_t;
    l_w      number;
    l_h      number;
    l_t      number;
    l_names  apex_t_varchar2 := apex_t_varchar2('pageHeader', 'reportHeader', 'body', 'summary', 'pageFooter');
    l_hts    apex_t_varchar2 := apex_t_varchar2('70', '0', '120', '80', '30');
    l_clob   clob;
  begin
    if p_copy_of is not null then
      -- p_copy_of: the code or the id of the report to copy
      for r in (select report_id, description, layout from pdf_reports
                 where code = upper(trim(p_copy_of))
                    or report_id = to_number(trim(p_copy_of) default null on conversion error)) loop
        insert into pdf_reports (code, name, description, layout)
        values (upper(trim(p_code)), p_name, nvl(p_description, r.description), r.layout)
        returning report_id into l_id;
        insert into pdf_queries (report_id, alias, seq, title, sql_text)
        select l_id, alias, seq, title, sql_text from pdf_queries where report_id = r.report_id;
      end loop;
      return l_id;
    end if;
    page_size(nvl(p_size, 'A4'), l_w, l_h);
    if lower(p_orientation) = 'landscape' then
      l_t := l_w; l_w := l_h; l_h := l_t;
    end if;
    l_page.put('size', nvl(p_size, 'A4'));
    l_page.put('orientation', lower(nvl(p_orientation, 'portrait')));
    l_page.put('width', l_w);
    l_page.put('height', l_h);
    l_page.put('unit', case when upper(p_size) in ('LETTER', 'LEGAL') then 'in' else 'mm' end);
    l_mar.put('top', 28.35); l_mar.put('right', 28.35); l_mar.put('bottom', 28.35); l_mar.put('left', 28.35);
    l_page.put('margin', l_mar);
    l_layout := json_object_t();
    l_layout.put('version', 1);
    l_layout.put('type', lower(nvl(p_type, 'report')));
    l_layout.put('repeat', '');
    l_layout.put('page', l_page);
    l_layout.put('font', json_object_t('{"family":"helvetica","size":9,"color":"#000000"}'));
    l_layout.put('params', json_object_t());
    if lower(p_type) = 'labels' then
      l_layout.put('labels', json_object_t('{"query":"Q1","across":3,"down":8,"width":180,"height":96,"gapX":7,"gapY":0,"outline":true}'));
      l_band := json_object_t();
      l_band.put('height', 96);
      l_band.put('elements', json_array_t());
      l_bands.put('label', l_band);
    else
      for i in 1 .. l_names.count loop
        l_band := json_object_t();
        l_band.put('height', to_number(l_hts(i)));
        if l_names(i) in ('pageHeader', 'pageFooter') then
          l_band.put('printOn', 'all');
        end if;
        l_band.put('elements', json_array_t());
        l_bands.put(l_names(i), l_band);
      end loop;
    end if;
    l_layout.put('bands', l_bands);
    l_clob := l_layout.to_clob;
    insert into pdf_reports (code, name, description, layout)
    values (upper(trim(p_code)), p_name, p_description, l_clob)
    returning report_id into l_id;
    return l_id;
  end;

  function export_json(p_report_id number) return clob is
    l json_object_t := report_json(p_report_id, false, true);
  begin
    l.put('format', 'pdf-report-designer');
    return l.to_clob;
  end;

  function import_json(p_json clob, p_code varchar2 default null, p_replace varchar2 default 'N') return number is
  begin
    return pdf_repo.import_report(p_json, p_code, p_replace);
  end;

  function deploy_script(p_codes apex_t_varchar2, p_replace varchar2 default 'Y') return clob is
    l_out   clob;
    l_json  clob;
    l_chunk varchar2(32767);
    l_q     varchar2(1);
    l_pos   number;
    l_len   number;
    l_n     pls_integer := 0;
    l_rep   boolean := upper(nvl(p_replace, 'Y')) in ('Y', 'YES', 'TRUE');
    c_step  constant pls_integer := 500;      -- short lines: SQL*Plus and SQLcl limit the line length
    procedure w(p varchar2) is
    begin
      dbms_lob.writeappend(l_out, nvl(length(p), 0) + 1, p || chr(10));
    end;
    -- JSON text in ASCII only: other characters as \uXXXX escapes, so the script reads the same in any
    -- client character set (SQL*Plus without NLS_LANG would change them)
    function ascii_json(p varchar2) return varchar2 is
      l_out varchar2(32767);
      l_ch  varchar2(8);
      l_hex varchar2(16);
    begin
      if p is null or not regexp_like(p, '[^' || chr(1) || '-' || chr(127) || ']') then
        return p;
      end if;
      for i in 1 .. length(p) loop
        l_ch := substr(p, i, 1);
        if ascii(l_ch) < 128 then
          l_out := l_out || l_ch;
        else
          l_hex := rawtohex(utl_i18n.string_to_raw(l_ch, 'AL16UTF16'));
          for j in 0 .. length(l_hex) / 4 - 1 loop
            l_out := l_out || '\u' || substr(l_hex, j * 4 + 1, 4);
          end loop;
        end if;
      end loop;
      return l_out;
    end;
  begin
    dbms_lob.createtemporary(l_out, true);
    w('-- VinAura / PDF Report Designer: reports for deployment');
    w('-- Made ' || to_char(sysdate, 'DD-MON-YYYY HH24:MI') || ' in schema ' || sys_context('USERENV', 'CURRENT_SCHEMA') ||
      ' by ' || coalesce(v('APP_USER'), user) || '.');
    w('--');
    w('-- Run it in SQL Developer (Run Script, F5) or SQLcl as the schema that owns the tables PDF_REPORTS,');
    w('-- PDF_QUERIES and PDF_IMAGES in the target database. It needs only the tables and packages of');
    w('-- 10_tables.sql to 40_pdf_api.sql there, not the designer application.');
    w('-- Reports that exist there already are ' || case when l_rep then 'replaced.' else 'left as they are.' end);
    w('-- The images the reports use (logos, stamps) come with them.');
    w('set define off');
    w('set serveroutput on');
    for c in (select r.report_id, r.code, r.name
                from pdf_reports r
                join table(p_codes) t on upper(trim(t.column_value)) = r.code
               order by r.code) loop
      l_n := l_n + 1;
      w(null);
      w('prompt ' || c.code || ' (' || ascii_json(replace(c.name, chr(10), ' ')) || ')');
      w('declare');
      w('  l_json clob;');
      w('  l_id   number;');
      w('  procedure a(p varchar2) is begin dbms_lob.writeappend(l_json, length(p), p); end;');
      w('begin');
      w('  dbms_lob.createtemporary(l_json, true);');
      l_json := export_json(c.report_id);
      l_len := dbms_lob.getlength(l_json);
      l_pos := 1;
      while l_pos <= l_len loop
        l_chunk := ascii_json(dbms_lob.substr(l_json, c_step, l_pos));
        -- a q'<c>...<c>' quote whose closing <c>' is not in the text
        l_q := null;
        for k in 1 .. 8 loop
          if instr(l_chunk, substr('~^!#|@%*', k, 1) || '''') = 0 then
            l_q := substr('~^!#|@%*', k, 1);
            exit;
          end if;
        end loop;
        w('  a(q''' || l_q || l_chunk || l_q || ''');');
        l_pos := l_pos + c_step;
      end loop;
      if l_rep then
        w('  l_id := pdf_repo.import_report(l_json, p_replace => ''Y'');');
        w('  dbms_output.put_line(''' || c.code || ': imported'');');
      else
        w('  begin');
        w('    l_id := pdf_repo.import_report(l_json, p_replace => ''N'');');
        w('    dbms_output.put_line(''' || c.code || ': imported'');');
        w('  exception');
        w('    when others then');
        w('      if sqlcode = -20511 then');
        w('        dbms_output.put_line(''' || c.code || ': exists already, left as it is'');');
        w('      else');
        w('        raise;');
        w('      end if;');
        w('  end;');
      end if;
      w('end;');
      w('/');
    end loop;
    w(null);
    w('commit;');
    w('prompt ' || l_n || ' report(s) done.');
    return l_out;
  end;

end pdf_designer;
/
