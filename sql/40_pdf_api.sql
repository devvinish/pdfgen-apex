-- PDF Report Designer: the repository (definer rights) and the public API (invoker rights).
--
--   l_pdf := pdfgen.pdf_api.generate('INVOICE');                          -- page items from session state
--   l_pdf := pdfgen.pdf_api.generate('INVOICE', apex_t_varchar2('P11_INVOICE_ID', 1001));
--   pdfgen.pdf_api.download('INVOICE');                                   -- sends the PDF to the browser
--
-- The queries of a report run with the rights of the schema that calls the API (the parsing schema
-- of the calling application), so they see that schema's tables.
set define off

create or replace package pdf_repo authid definer as

  type t_query is record (alias varchar2(10), sql_text clob);
  type t_queries is table of t_query index by pls_integer;

  -- the report by code (or by id); raises -20404 when there is none
  procedure get_report(p_report varchar2, o_id out number, o_name out varchar2, o_layout out clob,
                       o_queries out t_queries);

  procedure log_run(p_code varchar2, p_params varchar2, p_pages number, p_bytes number,
                    p_elapsed_ms number, p_error varchar2);

end pdf_repo;
/

create or replace package body pdf_repo as

  procedure get_report(p_report varchar2, o_id out number, o_name out varchar2, o_layout out clob,
                       o_queries out t_queries) is
  begin
    begin
      select report_id, name, layout into o_id, o_name, o_layout
        from pdf_reports
       where code = upper(trim(p_report))
          or report_id = to_number(trim(p_report) default null on conversion error);
    exception
      when no_data_found then
        raise_application_error(-20404, 'PDF report "' || p_report || '" does not exist.');
    end;
    for q in (select alias, sql_text from pdf_queries where report_id = o_id order by seq, alias) loop
      o_queries(o_queries.count + 1).alias := q.alias;
      o_queries(o_queries.count).sql_text := q.sql_text;
    end loop;
  end;

  procedure log_run(p_code varchar2, p_params varchar2, p_pages number, p_bytes number,
                    p_elapsed_ms number, p_error varchar2) is
    pragma autonomous_transaction;
  begin
    insert into pdf_log (report_code, app_id, page_id, app_user, params, pages, bytes, elapsed_ms, error)
    values (substr(p_code, 1, 60), v('APP_ID'), v('APP_PAGE_ID'),
            coalesce(v('APP_USER'), sys_context('USERENV', 'SESSION_USER')),
            substr(p_params, 1, 4000), p_pages, p_bytes, p_elapsed_ms, substr(p_error, 1, 4000));
    -- keep 90 days
    delete from pdf_log where created_on < sysdate - 90 and rownum <= 500;
    commit;
  exception
    when others then
      rollback;
  end;

end pdf_repo;
/

create or replace package pdf_api authid current_user as

  -- the PDF of a report. p_params: name/value pairs, e.g. apex_t_varchar2('P11_INVOICE_ID', '1001').
  -- A bind variable of a query takes its value from p_params, else from APEX session state (V()).
  function generate(p_report varchar2, p_params apex_t_varchar2 default null) return blob;

  -- the PDF sent to the browser (for an Ajax callback / application process / Before Header process)
  -- p_inline: shown in the browser (true) or downloaded as a file (false)
  procedure download(p_report varchar2, p_params apex_t_varchar2 default null,
                     p_filename varchar2 default null, p_inline boolean default true);

  -- the designer: a layout that is not saved yet. p_queries: [{"alias":"Q1","sql":"select ..."}]
  -- p_params: {"P11_INVOICE_ID":"1001"}
  function preview(p_layout clob, p_queries clob, p_params clob default null,
                   p_title varchar2 default null) return blob;

  -- the columns and bind variables of a query, as JSON: {"columns":[{"name":..,"type":..}],"binds":[..]}
  function describe(p_sql clob) return clob;

  -- the bind variables of a statement (strings, quoted names and comments skipped)
  function bind_names(p_sql clob) return apex_t_varchar2;

  -- the pages of the PDF made last by this session
  function last_page_count return pls_integer;

end pdf_api;
/

create or replace package body pdf_api as

  c_max_rows constant pls_integer := 100000;
  g_last_pages pls_integer;

  -- only queries: DBMS_SQL.PARSE would run anything else at once
  function clean_query(p_sql clob) return clob is
    l_sql   clob := p_sql;
    l_head  varchar2(4000);
  begin
    l_sql := regexp_replace(l_sql, '[[:space:];/]+$', null);
    l_head := dbms_lob.substr(l_sql, 4000, 1);
    -- leading comments and white space
    loop
      l_head := ltrim(l_head, ' ' || chr(9) || chr(10) || chr(13));
      if substr(l_head, 1, 2) = '--' then
        l_head := substr(l_head, nvl(nullif(instr(l_head, chr(10)), 0), length(l_head)) + 1);
      elsif substr(l_head, 1, 2) = '/*' then
        l_head := substr(l_head, nvl(nullif(instr(l_head, '*/'), 0), length(l_head)) + 2);
      else
        exit;
      end if;
    end loop;
    if not regexp_like(l_head, '^(select|with)[[:space:](]', 'i') then
      raise_application_error(-20502, 'Only SELECT (or WITH ... SELECT) queries are allowed.');
    end if;
    return l_sql;
  end;

  function bind_names(p_sql clob) return apex_t_varchar2 is
    l_out   apex_t_varchar2 := apex_t_varchar2();
    l_len   pls_integer := dbms_lob.getlength(p_sql);
    l_s     varchar2(32767);
    l_i     pls_integer := 1;
    l_c     varchar2(1);
    l_name  varchar2(128);
    l_close varchar2(1);
    l_end   pls_integer;
    function seen(p varchar2) return boolean is
    begin
      for i in 1 .. l_out.count loop
        if l_out(i) = p then
          return true;
        end if;
      end loop;
      return false;
    end;
  begin
    if l_len > 32767 then
      l_len := 32767;
    end if;
    l_s := dbms_lob.substr(p_sql, l_len, 1);
    l_len := length(l_s);
    while l_i <= l_len loop
      l_c := substr(l_s, l_i, 1);
      if l_c in ('q', 'Q') and substr(l_s, l_i + 1, 1) = '''' and l_i < l_len - 2 then
        -- q'[ ... ]'
        l_close := translate(substr(l_s, l_i + 2, 1), '[{(<', ']})>');
        l_end := instr(l_s, l_close || '''', l_i + 3);
        l_i := case when l_end = 0 then l_len + 1 else l_end + 2 end;
      elsif l_c = '''' then
        l_end := l_i + 1;
        loop
          l_end := instr(l_s, '''', l_end);
          exit when l_end = 0 or substr(l_s, l_end + 1, 1) <> '''';
          l_end := l_end + 2;
        end loop;
        l_i := case when l_end = 0 then l_len + 1 else l_end + 1 end;
      elsif l_c = '"' then
        l_end := instr(l_s, '"', l_i + 1);
        l_i := case when l_end = 0 then l_len + 1 else l_end + 1 end;
      elsif l_c = '-' and substr(l_s, l_i + 1, 1) = '-' then
        l_end := instr(l_s, chr(10), l_i);
        l_i := case when l_end = 0 then l_len + 1 else l_end + 1 end;
      elsif l_c = '/' and substr(l_s, l_i + 1, 1) = '*' then
        l_end := instr(l_s, '*/', l_i + 2);
        l_i := case when l_end = 0 then l_len + 1 else l_end + 2 end;
      elsif l_c = ':' and regexp_like(substr(l_s, l_i + 1, 1), '[A-Za-z]') then
        l_name := upper(regexp_substr(l_s, '[A-Za-z][A-Za-z0-9_$#]*', l_i + 1));
        if not seen(l_name) then
          l_out.extend;
          l_out(l_out.count) := l_name;
        end if;
        l_i := l_i + 1 + length(l_name);
      else
        l_i := l_i + 1;
      end if;
    end loop;
    return l_out;
  end;

  function bind_value(p_name varchar2, p_params pdf_engine.t_params) return varchar2 is
  begin
    if p_params.exists(p_name) then
      return p_params(p_name);
    end if;
    return v(p_name);
  exception
    when others then
      return null;
  end;

  function run_query(p_alias varchar2, p_sql clob, p_params pdf_engine.t_params)
    return pdf_engine.t_dataset is
    l_ds     pdf_engine.t_dataset;
    l_cur    integer;
    l_desc   dbms_sql.desc_tab3;
    l_ncols  integer;
    l_binds  apex_t_varchar2;
    l_rc     integer;
    l_vc     varchar2(4000);
    l_num    number;
    l_date   date;
    l_ts     timestamp;
    l_clob   clob;
    l_blob   blob;
    l_row    pls_integer := 0;
    l_sql    clob;
  begin
    l_ds.alias := p_alias;
    l_sql := clean_query(p_sql);
    l_cur := dbms_sql.open_cursor;
    begin
      dbms_sql.parse(l_cur, l_sql, dbms_sql.native);
      l_binds := bind_names(l_sql);
      for i in 1 .. l_binds.count loop
        dbms_sql.bind_variable(l_cur, ':' || l_binds(i), bind_value(l_binds(i), p_params), 32767);
      end loop;
      dbms_sql.describe_columns3(l_cur, l_ncols, l_desc);
      for c in 1 .. l_ncols loop
        l_ds.names(c) := l_desc(c).col_name;
        case
          when l_desc(c).col_type in (2, 100, 101) then
            l_ds.types(c) := 'N';
            dbms_sql.define_column(l_cur, c, l_num);
          when l_desc(c).col_type = 12 then
            l_ds.types(c) := 'D';
            dbms_sql.define_column(l_cur, c, l_date);
          when l_desc(c).col_type in (180, 181, 231) then
            l_ds.types(c) := 'T';
            dbms_sql.define_column(l_cur, c, l_ts);
          when l_desc(c).col_type = 112 then
            l_ds.types(c) := 'L';
            dbms_sql.define_column(l_cur, c, l_clob);
          when l_desc(c).col_type = 113 then
            l_ds.types(c) := 'B';
            dbms_sql.define_column(l_cur, c, l_blob);
          else
            l_ds.types(c) := 'C';
            dbms_sql.define_column(l_cur, c, l_vc, 4000);
        end case;
      end loop;
      l_rc := dbms_sql.execute(l_cur);
      while dbms_sql.fetch_rows(l_cur) > 0 and l_row < c_max_rows loop
        l_row := l_row + 1;
        for c in 1 .. l_ncols loop
          case l_ds.types(c)
            when 'N' then
              dbms_sql.column_value(l_cur, c, l_num);
              l_ds.nums(l_row)(c) := l_num;
              l_ds.vals(l_row)(c) := null;
            when 'D' then
              dbms_sql.column_value(l_cur, c, l_date);
              l_ds.vals(l_row)(c) := to_char(l_date, 'YYYYMMDDHH24MISS');
            when 'T' then
              dbms_sql.column_value(l_cur, c, l_ts);
              l_ds.vals(l_row)(c) := to_char(l_ts, 'YYYYMMDDHH24MISS');
            when 'L' then
              dbms_sql.column_value(l_cur, c, l_clob);
              l_ds.vals(l_row)(c) := dbms_lob.substr(l_clob, 4000, 1);
            when 'B' then
              dbms_sql.column_value(l_cur, c, l_blob);
              l_ds.vals(l_row)(c) := null;
              if l_blob is not null then
                l_ds.blobs(l_row || ':' || c) := l_blob;
              end if;
            else
              dbms_sql.column_value(l_cur, c, l_vc);
              l_ds.vals(l_row)(c) := l_vc;
          end case;
          if l_ds.types(c) <> 'N' then
            l_ds.nums(l_row)(c) := null;
          end if;
        end loop;
      end loop;
      dbms_sql.close_cursor(l_cur);
    exception
      when others then
        if dbms_sql.is_open(l_cur) then
          dbms_sql.close_cursor(l_cur);
        end if;
        raise_application_error(-20503, p_alias || ': ' || sqlerrm, true);
    end;
    -- timestamps and clobs are shown like dates and text
    for c in 1 .. l_ncols loop
      if l_ds.types(c) = 'T' then
        l_ds.types(c) := 'D';
      elsif l_ds.types(c) = 'L' then
        l_ds.types(c) := 'C';
      end if;
    end loop;
    l_ds.row_count := l_row;
    return l_ds;
  end;

  -- one row of a dataset as a dataset of its own (a section of a repeated report)
  function one_row(p_ds pdf_engine.t_dataset, p_row pls_integer) return pdf_engine.t_dataset is
    l pdf_engine.t_dataset;
  begin
    l.alias := p_ds.alias;
    l.names := p_ds.names;
    l.types := p_ds.types;
    l.vals(1) := p_ds.vals(p_row);
    l.nums(1) := p_ds.nums(p_row);
    for c in 1 .. p_ds.names.count loop
      if p_ds.blobs.exists(p_row || ':' || c) then
        l.blobs('1:' || c) := p_ds.blobs(p_row || ':' || c);
      end if;
    end loop;
    l.row_count := 1;
    return l;
  end;

  function render(p_layout clob, p_queries pdf_repo.t_queries, p_params pdf_engine.t_params,
                  p_title varchar2) return blob is
    l_data    pdf_engine.t_data;
    l_master  pdf_engine.t_dataset;
    l_repeat  varchar2(10);
    l_params  pdf_engine.t_params;
  begin
    pdf_engine.doc_begin(p_layout, p_title);
    l_repeat := pdf_engine.repeat_query;
    if l_repeat is not null then
      for i in 1 .. p_queries.count loop
        if p_queries(i).alias = l_repeat then
          l_master := run_query(p_queries(i).alias, p_queries(i).sql_text, p_params);
        end if;
      end loop;
    end if;
    if l_repeat is null or l_master.alias is null then
      for i in 1 .. p_queries.count loop
        l_data(p_queries(i).alias) := run_query(p_queries(i).alias, p_queries(i).sql_text, p_params);
      end loop;
      pdf_engine.section(l_data, p_params);
    else
      -- one section per row of the master query; its columns are binds :Q1_COLUMN of the others
      for r in 1 .. l_master.row_count loop
        l_params := p_params;
        for c in 1 .. l_master.names.count loop
          l_params(upper(l_master.alias || '_' || l_master.names(c))) :=
            case l_master.types(c)
              when 'N' then to_char(l_master.nums(r)(c))
              when 'D' then to_char(to_date(l_master.vals(r)(c), 'YYYYMMDDHH24MISS'))
              else l_master.vals(r)(c)
            end;
        end loop;
        l_data.delete;
        l_data(l_master.alias) := one_row(l_master, r);
        for i in 1 .. p_queries.count loop
          if p_queries(i).alias <> l_master.alias then
            l_data(p_queries(i).alias) := run_query(p_queries(i).alias, p_queries(i).sql_text, l_params);
          end if;
        end loop;
        pdf_engine.section(l_data, l_params);
      end loop;
      if l_master.row_count = 0 then
        pdf_engine.section(l_data, p_params);
      end if;
    end if;
    g_last_pages := pdf_engine.page_count;
    return pdf_engine.doc_end;
  end;

  function to_params(p_params apex_t_varchar2) return pdf_engine.t_params is
    l pdf_engine.t_params;
    i pls_integer := 1;
  begin
    if p_params is not null then
      while i <= p_params.count loop
        l(upper(trim(p_params(i)))) := case when i + 1 <= p_params.count then p_params(i + 1) end;
        i := i + 2;
      end loop;
    end if;
    return l;
  end;

  function params_text(p_params apex_t_varchar2) return varchar2 is
    l varchar2(4000);
  begin
    if p_params is not null then
      for i in 1 .. p_params.count loop
        l := substr(l || case when mod(i, 2) = 1 then case when i > 1 then ', ' end || p_params(i) || '=' else p_params(i) end, 1, 4000);
      end loop;
    end if;
    return l;
  end;

  function generate(p_report varchar2, p_params apex_t_varchar2 default null) return blob is
    l_id      number;
    l_name    varchar2(200);
    l_layout  clob;
    l_queries pdf_repo.t_queries;
    l_pdf     blob;
    l_start   number := dbms_utility.get_time;
  begin
    pdf_repo.get_report(p_report, l_id, l_name, l_layout, l_queries);
    l_pdf := render(l_layout, l_queries, to_params(p_params), l_name);
    pdf_repo.log_run(p_report, params_text(p_params), g_last_pages, dbms_lob.getlength(l_pdf),
                     (dbms_utility.get_time - l_start) * 10, null);
    return l_pdf;
  exception
    when others then
      pdf_repo.log_run(p_report, params_text(p_params), null, null,
                       (dbms_utility.get_time - l_start) * 10, sqlerrm);
      raise;
  end;

  procedure download(p_report varchar2, p_params apex_t_varchar2 default null,
                     p_filename varchar2 default null, p_inline boolean default true) is
    l_pdf  blob := generate(p_report, p_params);
    l_file varchar2(400) := nvl(p_filename, lower(p_report) || '.pdf');
  begin
    sys.htp.init;
    sys.owa_util.mime_header('application/pdf', false);
    sys.htp.p('Content-Length: ' || dbms_lob.getlength(l_pdf));
    sys.htp.p('Content-Disposition: ' || case when p_inline then 'inline' else 'attachment' end ||
              '; filename="' || replace(l_file, '"') || '"');
    sys.htp.p('Cache-Control: no-store');
    sys.owa_util.http_header_close;
    sys.wpg_docload.download_file(l_pdf);
    apex_application.stop_apex_engine;
  end;

  function preview(p_layout clob, p_queries clob, p_params clob default null,
                   p_title varchar2 default null) return blob is
    l_arr     json_array_t := json_array_t.parse(nvl(p_queries, '[]'));
    l_obj     json_object_t;
    l_queries pdf_repo.t_queries;
    l_params  pdf_engine.t_params;
    l_keys    json_key_list;
    l_p       json_object_t;
  begin
    for i in 0 .. l_arr.get_size - 1 loop
      l_obj := treat(l_arr.get(i) as json_object_t);
      if trim(l_obj.get_clob('sql')) is not null then
        l_queries(l_queries.count + 1).alias := upper(l_obj.get_string('alias'));
        l_queries(l_queries.count).sql_text := l_obj.get_clob('sql');
      end if;
    end loop;
    if p_params is not null then
      l_p := json_object_t.parse(p_params);
      l_keys := l_p.get_keys;
      for i in 1 .. l_keys.count loop
        if not l_p.get(l_keys(i)).is_null and l_p.get_string(l_keys(i)) is not null then
          l_params(upper(l_keys(i))) := l_p.get_string(l_keys(i));
        end if;
      end loop;
    end if;
    return render(p_layout, l_queries, l_params, p_title);
  end;

  function describe(p_sql clob) return clob is
    l_cur   integer;
    l_desc  dbms_sql.desc_tab3;
    l_n     integer;
    l_out   json_object_t := json_object_t();
    l_cols  json_array_t := json_array_t();
    l_col   json_object_t;
    l_binds apex_t_varchar2;
    l_ba    json_array_t := json_array_t();
  begin
    l_cur := dbms_sql.open_cursor;
    begin
      dbms_sql.parse(l_cur, clean_query(p_sql), dbms_sql.native);
      dbms_sql.describe_columns3(l_cur, l_n, l_desc);
      dbms_sql.close_cursor(l_cur);
    exception
      when others then
        if dbms_sql.is_open(l_cur) then
          dbms_sql.close_cursor(l_cur);
        end if;
        raise;
    end;
    for c in 1 .. l_n loop
      l_col := json_object_t();
      l_col.put('name', l_desc(c).col_name);
      l_col.put('type', case
                          when l_desc(c).col_type in (2, 100, 101) then 'NUMBER'
                          when l_desc(c).col_type in (12, 180, 181, 231) then 'DATE'
                          when l_desc(c).col_type = 113 then 'BLOB'
                          when l_desc(c).col_type = 112 then 'CLOB'
                          else 'TEXT'
                        end);
      l_cols.append(l_col);
    end loop;
    l_binds := bind_names(p_sql);
    for i in 1 .. l_binds.count loop
      l_ba.append(l_binds(i));
    end loop;
    l_out.put('columns', l_cols);
    l_out.put('binds', l_ba);
    return l_out.to_clob;
  end;

  function last_page_count return pls_integer is
  begin
    return g_last_pages;
  end;

end pdf_api;
/

-- other schemas (the parsing schemas of your applications) call the API through a grant:
--   grant execute on pdfgen.pdf_api to <schema>;   create synonym <schema>.pdf_api for pdfgen.pdf_api;
