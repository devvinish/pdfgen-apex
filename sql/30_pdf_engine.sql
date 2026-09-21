-- PDF Report Designer: the layout engine.
-- Turns a layout (JSON, made in the designer) plus the rows of its queries into PDF pages.
--
-- Bands, from top to bottom of a page:
--   pageHeader    every page (or first / not first page)       fixed at the top margin
--   reportHeader  once, at the start of the report
--   body          flows: its tables grow and continue on the next pages, the rest follows them
--   summary       once, after the body (totals, amount in words, signature); or at the page bottom
--   pageFooter    every page (or first / last / not last page)   fixed at the bottom margin
-- Labels layouts have one band, "label", repeated for every row of their query (across, then down), or
-- with labels.perPage one label per page, the page being the size of the label (label printers).
--
-- Text of any element may hold tokens:
--   {Q1.CUSTOMER_NAME}   a column of a query (the current row inside tables and labels, else row 1)
--   {Q2.AMOUNT|FM999G999G990D00}   with a format mask (numbers and dates)
--   {SUM(Q2.AMOUNT)}  {COUNT(Q2)}  {AVG(..)}  {MIN(..)}  {MAX(..)}   over all rows of a query
--   {PAGE} {PAGES} {TODAY} {TODAY|DD/MM/YYYY} {NOW} {APP_USER} {REPORT}
--   {P11_INVOICE_ID}     a parameter / page item
set define off

create or replace package pdf_engine authid definer as

  type t_strs     is table of varchar2(4000) index by pls_integer;
  type t_nums     is table of number index by pls_integer;
  type t_rows     is table of t_strs index by pls_integer;
  type t_numrows  is table of t_nums index by pls_integer;
  type t_blobs    is table of blob index by varchar2(100);
  type t_params   is table of varchar2(4000) index by varchar2(128);

  -- the rows of one query. types(c): N number, D date, C text, B blob
  -- vals(r)(c): text (C), YYYYMMDDHH24MISS (D); nums(r)(c): numbers; blobs('r:c'): blobs
  type t_dataset is record (
    alias     varchar2(10),
    names     t_strs,
    types     t_strs,
    vals      t_rows,
    nums      t_numrows,
    blobs     t_blobs,
    row_count pls_integer := 0);
  type t_data is table of t_dataset index by varchar2(10);

  procedure doc_begin(p_layout clob, p_title varchar2 default null);
  -- one document section: new page, all bands; page numbers restart for every section
  procedure section(p_data t_data, p_params t_params);
  function  doc_end return blob;
  function  page_count return pls_integer;

  -- the layout's setting (for the API): the query repeated per section, or null
  function  repeat_query return varchar2;
  function  layout_type return varchar2;

end pdf_engine;
/

create or replace package body pdf_engine as

  type t_idx      is table of pls_integer index by pls_integer;
  type t_map      is table of pls_integer index by varchar2(200);
  type t_lines    is table of varchar2(4000) index by pls_integer;
  type t_c128     is table of varchar2(7) index by pls_integer;

  g_c128       t_c128;      -- Code 128 bar patterns

  g_layout     json_object_t;
  g_bands      json_object_t;
  g_title      varchar2(4000);
  g_type       varchar2(20);
  g_repeat     varchar2(10);

  g_pw         number;      -- page width
  g_ph         number;      -- page height
  g_mt         number;      -- margins
  g_mr         number;
  g_mb         number;
  g_ml         number;
  g_cw         number;      -- content width

  g_font       varchar2(20);
  g_size       number;
  g_color      varchar2(20);

  g_data       t_data;
  g_params     t_params;
  g_cols       t_map;       -- 'Q1.COLUMN' -> column index
  g_cur_row    t_map;       -- alias -> current row
  g_images     t_blobs;     -- image name -> jpeg

  g_sec_first  pls_integer; -- writer page of the first page of the section
  g_sec_pages  pls_integer; -- pages of the section so far
  g_page_no    pls_integer; -- {PAGE}
  g_page_total pls_integer; -- {PAGES}
  g_y          number;      -- cursor (from the top of the page)
  g_top        number;      -- top of the content area of the current page
  g_bottom     number;      -- bottom of the content area

  ------------------------------------------------------------------ JSON helpers
  function js(o json_object_t, k varchar2, d varchar2 default null) return varchar2 is
  begin
    if o is null or not o.has(k) or o.get(k).is_null then
      return d;
    end if;
    return nvl(o.get_string(k), d);
  end;

  function jn(o json_object_t, k varchar2, d number default null) return number is
  begin
    if o is null or not o.has(k) or o.get(k).is_null then
      return d;
    end if;
    if o.get(k).is_string then
      return nvl(to_number(o.get_string(k) default null on conversion error, '9999999999D999999', 'NLS_NUMERIC_CHARACTERS=''.,'''), d);
    end if;
    return nvl(o.get_number(k), d);
  end;

  function jb(o json_object_t, k varchar2, d boolean default false) return boolean is
  begin
    if o is null or not o.has(k) or o.get(k).is_null then
      return d;
    end if;
    if o.get(k).is_boolean then
      return o.get_boolean(k);
    end if;
    return lower(o.get_string(k)) in ('true', 'y', 'yes', '1');
  end;

  function jo(o json_object_t, k varchar2) return json_object_t is
  begin
    if o is null or not o.has(k) or not o.get(k).is_object then
      return null;
    end if;
    return o.get_object(k);
  end;

  function ja(o json_object_t, k varchar2) return json_array_t is
  begin
    if o is null or not o.has(k) or not o.get(k).is_array then
      return json_array_t();
    end if;
    return o.get_array(k);
  end;

  function el(a json_array_t, i pls_integer) return json_object_t is
  begin
    return treat(a.get(i) as json_object_t);
  end;

  ------------------------------------------------------------------ data
  function has_ds(p_alias varchar2) return boolean is
  begin
    return p_alias is not null and g_data.exists(p_alias);
  end;

  function col_idx(p_alias varchar2, p_col varchar2) return pls_integer is
    l_key varchar2(200) := upper(p_alias) || '.' || upper(p_col);
  begin
    if g_cols.exists(l_key) then
      return g_cols(l_key);
    end if;
    return null;
  end;

  function cur_row(p_alias varchar2) return pls_integer is
  begin
    if g_cur_row.exists(p_alias) then
      return g_cur_row(p_alias);
    end if;
    return 1;
  end;

  function num_at(p_alias varchar2, p_row pls_integer, p_col pls_integer) return number is
  begin
    if p_row > g_data(p_alias).row_count then
      return null;
    end if;
    if g_data(p_alias).types(p_col) = 'N' then
      return g_data(p_alias).nums(p_row)(p_col);
    end if;
    return to_number(g_data(p_alias).vals(p_row)(p_col) default null on conversion error);
  end;

  function fmt_value(p_alias varchar2, p_row pls_integer, p_col pls_integer, p_mask varchar2)
    return varchar2 is
    l_type varchar2(1);
    l_v    varchar2(4000);
    l_n    number;
  begin
    if p_row < 1 or p_row > g_data(p_alias).row_count then
      return null;
    end if;
    l_type := g_data(p_alias).types(p_col);
    if l_type = 'N' then
      l_n := g_data(p_alias).nums(p_row)(p_col);
      if l_n is null then
        return null;
      end if;
      if p_mask is not null then
        return trim(to_char(l_n, p_mask));
      end if;
      return to_char(l_n);
    elsif l_type = 'D' then
      l_v := g_data(p_alias).vals(p_row)(p_col);
      if l_v is null then
        return null;
      end if;
      if p_mask is not null then
        return to_char(to_date(l_v, 'YYYYMMDDHH24MISS'), p_mask);
      end if;
      return to_char(to_date(l_v, 'YYYYMMDDHH24MISS'));
    elsif l_type = 'B' then
      return null;
    end if;
    l_v := g_data(p_alias).vals(p_row)(p_col);
    if p_mask is not null and l_v is not null then
      -- a number or a date held as text: format it when it converts
      l_n := to_number(l_v default null on conversion error);
      if l_n is not null then
        return trim(to_char(l_n, p_mask));
      end if;
    end if;
    return l_v;
  exception
    when others then
      return g_data(p_alias).vals(p_row)(p_col);
  end;

  function fmt_number(p_n number, p_mask varchar2) return varchar2 is
  begin
    if p_n is null then
      return null;
    end if;
    if p_mask is not null then
      return trim(to_char(p_n, p_mask));
    end if;
    return to_char(p_n);
  exception
    when others then
      return to_char(p_n);
  end;

  function aggregate(p_fn varchar2, p_alias varchar2, p_col pls_integer,
                     p_from pls_integer default 1, p_to pls_integer default null) return number is
    l_sum number := 0;
    l_cnt pls_integer := 0;
    l_min number;
    l_max number;
    l_n   number;
    l_to  pls_integer;
  begin
    if not has_ds(p_alias) then
      return null;
    end if;
    l_to := nvl(p_to, g_data(p_alias).row_count);
    if p_fn = 'COUNT' and p_col is null then
      return greatest(l_to - p_from + 1, 0);
    end if;
    for r in p_from .. l_to loop
      l_n := num_at(p_alias, r, p_col);
      if l_n is not null then
        l_sum := l_sum + l_n;
        l_cnt := l_cnt + 1;
        l_min := least(nvl(l_min, l_n), l_n);
        l_max := greatest(nvl(l_max, l_n), l_n);
      elsif p_fn = 'COUNT' and g_data(p_alias).vals(r)(p_col) is not null then
        l_cnt := l_cnt + 1;
      end if;
    end loop;
    return case p_fn
             when 'SUM' then l_sum
             when 'COUNT' then l_cnt
             when 'AVG' then case when l_cnt > 0 then l_sum / l_cnt end
             when 'MIN' then l_min
             when 'MAX' then l_max
           end;
  end;

  function param(p_name varchar2) return varchar2 is
    l_name varchar2(128) := upper(p_name);
  begin
    if g_params.exists(l_name) then
      return g_params(l_name);
    end if;
    return v(l_name);
  exception
    when others then
      return null;
  end;

  ------------------------------------------------------------------ tokens
  -- an amount in words, Indian numbering (thousand, lakh, crore) with paise:
  -- 1151506.5 -> Eleven Lakh Fifty-One Thousand Five Hundred Six and Fifty Paise
  -- p_style: the mask of {WORDS(..)|...}; INTL for million / billion
  function amount_words(p_amount number, p_style varchar2 default null) return varchar2 is
    l_int  number;
    l_frac number;
    l_out  varchar2(4000);
    function upto999(n number) return varchar2 is
    begin
      if n = 0 then
        return null;
      end if;
      return trim(to_char(to_date(n, 'J'), 'Jsp'));
    end;
    function part(n number, p_word varchar2) return varchar2 is
    begin
      return case when n > 0 then upto999(n) || ' ' || p_word || ' ' end;
    end;
  begin
    if p_amount is null then
      return null;
    end if;
    l_int := trunc(abs(p_amount));
    l_frac := round((abs(p_amount) - l_int) * 100);
    if upper(p_style) = 'INTL' then
      l_out := part(trunc(l_int / 1e9), 'Billion') || part(mod(trunc(l_int / 1e6), 1000), 'Million') ||
               part(mod(trunc(l_int / 1000), 1000), 'Thousand') || upto999(mod(l_int, 1000));
    else
      l_out := case when l_int >= 1e7 then amount_words(trunc(l_int / 1e7)) || ' Crore ' end ||
               part(mod(trunc(l_int / 1e5), 100), 'Lakh') || part(mod(trunc(l_int / 1000), 100), 'Thousand') ||
               upto999(mod(l_int, 1000));
    end if;
    l_out := nvl(trim(l_out), 'Zero');
    if l_frac > 0 then
      l_out := l_out || ' and ' || upto999(l_frac) || ' ' || case when upper(p_style) = 'INTL' then 'Cents' else 'Paise' end;
    end if;
    return case when p_amount < 0 then 'Minus ' end || l_out;
  end;

  function eval_token(p_token varchar2) return varchar2 is
    l_expr  varchar2(4000) := p_token;
    l_mask  varchar2(200);
    l_u     varchar2(4000);
    l_alias varchar2(10);
    l_col   varchar2(200);
    l_idx   pls_integer;
    l_fn    varchar2(10);
  begin
    if instr(l_expr, '|') > 0 then
      l_mask := trim(substr(l_expr, instr(l_expr, '|') + 1));
      l_expr := substr(l_expr, 1, instr(l_expr, '|') - 1);
    end if;
    l_u := upper(trim(l_expr));
    case l_u
      when 'PAGE' then return to_char(g_page_no);
      when 'PAGES' then return case when g_page_total is not null then to_char(g_page_total) end;
      when 'TODAY' then return case when l_mask is null then to_char(trunc(sysdate)) else to_char(sysdate, l_mask) end;
      when 'NOW' then return to_char(sysdate, nvl(l_mask, 'DD-MON-YYYY HH24:MI'));
      when 'APP_USER' then return coalesce(v('APP_USER'), sys_context('USERENV', 'SESSION_USER'));
      when 'REPORT' then return g_title;
      else null;
    end case;
    if regexp_like(l_u, '^(SUM|COUNT|AVG|MIN|MAX)\(\s*Q[0-9]+(\.[A-Z0-9_$#" ]+)?\s*\)$') then
      l_fn    := regexp_substr(l_u, '^[A-Z]+');
      l_alias := regexp_substr(l_u, 'Q[0-9]+');
      l_col   := trim(both '"' from trim(regexp_substr(l_u, '\.([^)]+)', 1, 1, null, 1)));
      if not has_ds(l_alias) then
        return null;
      end if;
      if l_col is not null then
        l_idx := col_idx(l_alias, l_col);
        if l_idx is null then
          return '#' || l_alias || '.' || l_col || '?';
        end if;
      end if;
      return fmt_number(aggregate(l_fn, l_alias, l_idx), l_mask);
    end if;
    if regexp_like(l_u, '^WORDS\(.+\)$') then
      l_expr := substr(trim(l_expr), 7, length(trim(l_expr)) - 7);
      return amount_words(to_number(eval_token(l_expr) default null on conversion error), l_mask);
    end if;
    if regexp_like(l_u, '^Q[0-9]+\.') then
      l_alias := substr(l_u, 1, instr(l_u, '.') - 1);
      l_col   := trim(both '"' from substr(l_u, instr(l_u, '.') + 1));
      if not has_ds(l_alias) then
        return null;
      end if;
      l_idx := col_idx(l_alias, l_col);
      if l_idx is null then
        return '#' || l_alias || '.' || l_col || '?';
      end if;
      return fmt_value(l_alias, cur_row(l_alias), l_idx, l_mask);
    end if;
    return param(l_u);
  end;

  function resolve(p_text varchar2) return varchar2 is
    l_out   varchar2(32767);
    l_pos   pls_integer := 1;
    l_open  pls_integer;
    l_close pls_integer;
  begin
    if p_text is null or instr(p_text, '{') = 0 then
      return p_text;
    end if;
    loop
      l_open := instr(p_text, '{', l_pos);
      if l_open = 0 then
        l_out := l_out || substr(p_text, l_pos);
        exit;
      end if;
      l_close := instr(p_text, '}', l_open);
      if l_close = 0 then
        l_out := l_out || substr(p_text, l_pos);
        exit;
      end if;
      l_out := l_out || substr(p_text, l_pos, l_open - l_pos) ||
               eval_token(substr(p_text, l_open + 1, l_close - l_open - 1));
      l_pos := l_close + 1;
    end loop;
    return l_out;
  end;

  -- "print when": {Q1.DISCOUNT}  /  {Q1.STATUS} = PAID  /  {SUM(Q2.AMOUNT)} > 1000
  function print_when(o json_object_t) return boolean is
    l_expr varchar2(4000) := trim(js(o, 'printWhen'));
    l_op   varchar2(3);
    l_a    varchar2(4000);
    l_b    varchar2(4000);
    l_na   number;
    l_nb   number;
    l_c    pls_integer;
  begin
    if l_expr is null then
      return true;
    end if;
    l_op := regexp_substr(l_expr, '(!=|<>|>=|<=|=|>|<)');
    if l_op is null then
      l_a := trim(resolve(l_expr));
      return l_a is not null and upper(l_a) not in ('0', 'N', 'NO', 'FALSE');
    end if;
    l_a := trim(resolve(substr(l_expr, 1, instr(l_expr, l_op) - 1)));
    l_b := trim(both '''' from trim(resolve(substr(l_expr, instr(l_expr, l_op) + length(l_op)))));
    l_na := to_number(l_a default null on conversion error);
    l_nb := to_number(l_b default null on conversion error);
    if l_na is not null and l_nb is not null then
      l_c := sign(l_na - l_nb);
    elsif nvl(l_a, chr(0)) = nvl(l_b, chr(0)) then
      l_c := 0;
    elsif nvl(l_a, chr(0)) < nvl(l_b, chr(0)) then
      l_c := -1;
    else
      l_c := 1;
    end if;
    return case l_op
             when '=' then l_c = 0
             when '!=' then l_c <> 0
             when '<>' then l_c <> 0
             when '>' then l_c > 0
             when '<' then l_c < 0
             when '>=' then l_c >= 0
             when '<=' then l_c <= 0
           end;
  end;

  ------------------------------------------------------------------ text
  function wrap_lines(p_text varchar2, p_width number, p_font varchar2, p_bold boolean,
                      p_italic boolean, p_size number, p_wrap boolean) return t_lines is
    l_out   t_lines;
    l_para  varchar2(4000);
    l_rest  varchar2(32767) := replace(p_text, chr(13));
    l_nl    pls_integer;
    l_line  varchar2(4000);
    l_word  varchar2(4000);
    l_sp    pls_integer;
    l_try   varchar2(4000);
    l_n     pls_integer;
  begin
    loop
      l_nl := nvl(instr(l_rest, chr(10)), 0);
      if l_nl > 0 then
        l_para := substr(l_rest, 1, l_nl - 1);
        l_rest := substr(l_rest, l_nl + 1);
      else
        l_para := l_rest;
        l_rest := null;
      end if;
      if not p_wrap or p_width <= 0 or pdf_writer.text_width(l_para, p_font, p_bold, p_italic, p_size) <= p_width then
        l_out(l_out.count + 1) := l_para;
      else
        l_line := null;
        l_para := l_para || ' ';
        while l_para is not null loop
          l_sp := instr(l_para, ' ');
          l_word := substr(l_para, 1, l_sp - 1);
          l_para := substr(l_para, l_sp + 1);
          l_try := case when l_line is null then l_word else l_line || ' ' || l_word end;
          if pdf_writer.text_width(l_try, p_font, p_bold, p_italic, p_size) <= p_width then
            l_line := l_try;
          else
            if l_line is not null then
              l_out(l_out.count + 1) := l_line;
            end if;
            -- a word longer than the line: cut it
            while pdf_writer.text_width(l_word, p_font, p_bold, p_italic, p_size) > p_width and length(l_word) > 1 loop
              l_n := length(l_word);
              while l_n > 1 and pdf_writer.text_width(substr(l_word, 1, l_n), p_font, p_bold, p_italic, p_size) > p_width loop
                l_n := l_n - 1;
              end loop;
              l_out(l_out.count + 1) := substr(l_word, 1, l_n);
              l_word := substr(l_word, l_n + 1);
            end loop;
            l_line := l_word;
          end if;
        end loop;
        if l_line is not null or l_out.count = 0 then
          l_out(l_out.count + 1) := l_line;
        end if;
      end if;
      exit when l_nl = 0;
    end loop;
    return l_out;
  end;

  function text_height(p_text varchar2, p_width number, p_font varchar2, p_bold boolean,
                       p_italic boolean, p_size number, p_wrap boolean, p_lh number) return number is
    l_lines t_lines;
  begin
    if p_text is null then
      return 0;
    end if;
    l_lines := wrap_lines(p_text, p_width, p_font, p_bold, p_italic, p_size, p_wrap);
    return l_lines.count * p_size * p_lh;
  end;

  procedure draw_text(p_x number, p_y number, p_w number, p_h number, p_text varchar2,
                      p_font varchar2, p_size number, p_bold boolean, p_italic boolean,
                      p_underline boolean, p_color varchar2, p_align varchar2, p_valign varchar2,
                      p_wrap boolean, p_pad number, p_lh number default 1.2, p_clip boolean default true) is
    l_lines t_lines;
    l_lh    number := p_size * nvl(p_lh, 1.2);
    l_start number;
    l_base  number;
    l_tw    number;
    l_x     number;
    l_iw    number := p_w - 2 * p_pad;
  begin
    if p_text is null then
      return;
    end if;
    l_lines := wrap_lines(p_text, l_iw, p_font, p_bold, p_italic, p_size, p_wrap);
    l_start := case lower(p_valign)
                 when 'middle' then p_y + (p_h - l_lines.count * l_lh) / 2
                 when 'bottom' then p_y + p_h - p_pad - l_lines.count * l_lh
                 else p_y + p_pad
               end;
    if p_clip then
      pdf_writer.clip_begin(p_x, p_y, p_w, p_h);
    end if;
    for i in 1 .. l_lines.count loop
      l_base := l_start + (i - 1) * l_lh + l_lh / 2 + p_size * 0.32;
      l_tw := pdf_writer.text_width(l_lines(i), p_font, p_bold, p_italic, p_size);
      l_x := case lower(p_align)
               when 'right' then p_x + p_w - p_pad - l_tw
               when 'center' then p_x + (p_w - l_tw) / 2
               else p_x + p_pad
             end;
      pdf_writer.text(l_x, l_base, l_lines(i), p_font, p_bold, p_italic, p_size, p_color);
      if p_underline and l_lines(i) is not null then
        pdf_writer.line(l_x, l_base + p_size * 0.12, l_x + l_tw, l_base + p_size * 0.12, p_color, p_size * 0.06);
      end if;
    end loop;
    if p_clip then
      pdf_writer.clip_end;
    end if;
  end;

  ------------------------------------------------------------------ elements
  function image_blob(p_src varchar2) return blob is
    l_blob  blob;
    l_alias varchar2(10);
    l_idx   pls_integer;
    l_key   varchar2(100);
  begin
    if regexp_like(p_src, '^\{\s*Q[0-9]+\.[^}]+\}$') then
      l_alias := upper(regexp_substr(p_src, 'Q[0-9]+', 1, 1, 'i'));
      if not has_ds(l_alias) then
        return null;
      end if;
      l_idx := col_idx(l_alias, trim(regexp_substr(p_src, '\.([^}]+)\}', 1, 1, null, 1)));
      l_key := cur_row(l_alias) || ':' || l_idx;
      if l_idx is not null and g_data(l_alias).blobs.exists(l_key) then
        return g_data(l_alias).blobs(l_key);
      end if;
      return null;
    end if;
    if not g_images.exists(p_src) then
      begin
        select content into l_blob from pdf_images where name = p_src;
      exception
        when no_data_found then
          l_blob := null;
      end;
      g_images(p_src) := l_blob;
    end if;
    return g_images(p_src);
  end;

  -- the key an image is embedded under: its name, or query:row:column for an image of a query
  function image_key(p_src varchar2) return varchar2 is
    l_alias varchar2(10);
  begin
    if regexp_like(p_src, '^\{\s*Q[0-9]+\.[^}]+\}$') then
      l_alias := upper(regexp_substr(p_src, 'Q[0-9]+', 1, 1, 'i'));
      return l_alias || ':' || cur_row(l_alias) || ':' || upper(p_src);
    end if;
    return p_src;
  end;

  procedure load_code128 is
    c constant varchar2(700) := '212222222122222221121223121322131222122213122312132212221213221312231212112232122132122231113222123122123221223211221132221231213212223112312131311222321122321221312212322112322211212123212321232121111323131123131321112313132113132311211313231113231311112133112331132131113123113321133121313121211331231131213113213311213131311123311321331121312113312311332111314111221411431111111224111422121124121421141122141221112214112412122114122411142112142211241211221114413111241112134111111242121142121241114212124112124211411212421112421211212141214121412121111143111341131141114113114311411113411311113141114131311141411131211412211214211232';
  begin
    for i in 0 .. 105 loop
      g_c128(i) := substr(c, i * 6 + 1, 6);
    end loop;
    g_c128(106) := '2331112';
  end;

  procedure draw_barcode(p_x number, p_y number, p_w number, p_h number, p_value varchar2,
                         p_color varchar2, p_show_text boolean, p_size number) is
    type t_codes is table of pls_integer index by pls_integer;
    l_codes  t_codes;
    l_sum    pls_integer;
    l_val    varchar2(4000) := p_value;
    l_mods   pls_integer := 0;
    l_mw     number;
    l_x      number;
    l_bar_h  number;
    l_pat    varchar2(7);
    l_c      pls_integer;
  begin
    if l_val is null then
      return;
    end if;
    if g_c128.count = 0 then
      load_code128;
    end if;
    if regexp_like(l_val, '^[0-9]+$') and mod(length(l_val), 2) = 0 and length(l_val) >= 4 then
      l_codes(1) := 105;    -- start C: pairs of digits
      for i in 1 .. length(l_val) / 2 loop
        l_codes(l_codes.count + 1) := to_number(substr(l_val, 2 * i - 1, 2));
      end loop;
    else
      l_codes(1) := 104;    -- start B
      for i in 1 .. length(l_val) loop
        l_c := ascii(substr(l_val, i, 1));
        l_codes(l_codes.count + 1) := case when l_c between 32 and 127 then l_c - 32 else 31 end;
      end loop;
    end if;
    l_sum := l_codes(1);
    for i in 2 .. l_codes.count loop
      l_sum := l_sum + l_codes(i) * (i - 1);
    end loop;
    l_codes(l_codes.count + 1) := mod(l_sum, 103);
    l_codes(l_codes.count + 1) := 106;
    l_mods := (l_codes.count - 1) * 11 + 13;
    l_mw := p_w / (l_mods + 20);                -- 10 modules of quiet zone on each side
    l_bar_h := p_h - case when p_show_text then p_size * 1.3 else 0 end;
    l_x := p_x + 10 * l_mw;
    for i in 1 .. l_codes.count loop
      l_pat := g_c128(l_codes(i));
      for j in 1 .. length(l_pat) loop
        if mod(j, 2) = 1 then
          pdf_writer.rect(l_x, p_y, to_number(substr(l_pat, j, 1)) * l_mw, l_bar_h, nvl(p_color, '#000000'));
        end if;
        l_x := l_x + to_number(substr(l_pat, j, 1)) * l_mw;
      end loop;
    end loop;
    if p_show_text then
      draw_text(p_x, p_y + l_bar_h, p_w, p_size * 1.3, l_val, 'helvetica', p_size, false, false, false,
                p_color, 'center', 'middle', false, 0, 1.2, false);
    end if;
  end;

  -- style of an element, with the layout's defaults
  function e_font(o json_object_t) return varchar2 is begin return lower(js(o, 'font', g_font)); end;
  function e_size(o json_object_t) return number is begin return jn(o, 'size', g_size); end;

  procedure draw_frame(o json_object_t, x number, y number, w number, h number) is
  begin
    pdf_writer.rect(x, y, w, h, js(o, 'bg'), case when jn(o, 'borderWidth', 0) > 0 then js(o, 'borderColor', '#000000') end,
                    jn(o, 'borderWidth', 0), jn(o, 'radius', 0), js(o, 'dash'));
  end;

  procedure draw_element(o json_object_t, p_ox number, p_oy number) is
    l_type varchar2(20) := lower(js(o, 'type'));
    x      number := p_ox + jn(o, 'x', 0);
    y      number := p_oy + jn(o, 'y', 0);
    w      number := jn(o, 'w', 0);
    h      number := jn(o, 'h', 0);
    l_txt  varchar2(32767);
  begin
    if not print_when(o) then
      return;
    end if;
    case l_type
      when 'text' then
        draw_frame(o, x, y, w, h);
        l_txt := js(o, 'text');
        -- a single token with the element's format mask: {Q1.AMOUNT} + format
        if js(o, 'format') is not null and regexp_like(l_txt, '^\{[^}|]+\}$') then
          l_txt := '{' || substr(l_txt, 2, length(l_txt) - 2) || '|' || js(o, 'format') || '}';
        end if;
        draw_text(x, y, w, h, resolve(l_txt), e_font(o), e_size(o), jb(o, 'bold'), jb(o, 'italic'),
                  jb(o, 'underline'), js(o, 'color', g_color), js(o, 'align', 'left'), js(o, 'valign', 'top'),
                  jb(o, 'wrap', true), jn(o, 'padding', 2), jn(o, 'lineHeight', 1.2));
      when 'box' then
        draw_frame(o, x, y, w, h);
      when 'ellipse' then
        pdf_writer.ellipse(x, y, w, h, js(o, 'bg'), case when jn(o, 'borderWidth', 1) > 0 then js(o, 'borderColor', '#000000') end,
                           jn(o, 'borderWidth', 1), js(o, 'dash'));
      when 'line' then
        pdf_writer.line(x, y, x + w, y + h, js(o, 'color', '#000000'), jn(o, 'lineWidth', 1), js(o, 'dash'));
      when 'image' then
        draw_frame(o, x, y, w, h);
        pdf_writer.image(image_key(js(o, 'src')), image_blob(js(o, 'src')), x, y, w, h, js(o, 'fit', 'contain'));
      when 'barcode' then
        draw_frame(o, x, y, w, h);
        draw_barcode(x, y, w, h, resolve(js(o, 'text')), js(o, 'color', '#000000'), jb(o, 'showText', true), jn(o, 'size', 8));
      else
        null;
    end case;
  end;

  ------------------------------------------------------------------ pages
  function band(p_name varchar2) return json_object_t is
  begin
    return jo(g_bands, p_name);
  end;

  function band_h(p_name varchar2) return number is
  begin
    return jn(band(p_name), 'height', 0);
  end;

  function band_on(p_name varchar2, p_page pls_integer, p_pages pls_integer) return boolean is
    l_on varchar2(20) := lower(js(band(p_name), 'printOn', 'all'));
  begin
    return case l_on
             when 'first' then p_page = 1
             when 'notfirst' then p_page > 1
             when 'last' then p_page = p_pages
             when 'notlast' then p_page < p_pages
             else true
           end;
  end;

  procedure new_page is
    l_page pls_integer;
  begin
    l_page := pdf_writer.new_page(g_pw, g_ph);
    g_sec_pages := g_sec_pages + 1;
    g_page_no := g_sec_pages;
    g_top := g_mt;
    -- the page header takes its place on the pages it prints on (first / not first known now)
    if band_h('pageHeader') > 0 and lower(js(band('pageHeader'), 'printOn', 'all')) in ('all', 'first', 'notfirst', 'last', 'notlast') then
      if not (lower(js(band('pageHeader'), 'printOn', 'all')) = 'first' and g_sec_pages > 1)
         and not (lower(js(band('pageHeader'), 'printOn', 'all')) = 'notfirst' and g_sec_pages = 1) then
        g_top := g_mt + band_h('pageHeader');
      end if;
    end if;
    g_bottom := g_ph - g_mb - band_h('pageFooter');
    g_y := g_top;
  end;

  procedure draw_band_at(b json_object_t, p_ox number, p_oy number) is
    l_els json_array_t := ja(b, 'elements');
  begin
    for i in 0 .. l_els.get_size - 1 loop
      if lower(js(el(l_els, i), 'type')) <> 'table' then
        draw_element(el(l_els, i), p_ox, p_oy);
      end if;
    end loop;
  end;

  -- the lowest point any element of the band reaches
  function band_used(b json_object_t) return number is
    l_els json_array_t := ja(b, 'elements');
    l_max number := 0;
  begin
    for i in 0 .. l_els.get_size - 1 loop
      l_max := greatest(l_max, jn(el(l_els, i), 'y', 0) + greatest(jn(el(l_els, i), 'h', 0), 0));
    end loop;
    return l_max;
  end;

  procedure static_band(p_name varchar2) is
    b      json_object_t := band(p_name);
    l_h    number;
    l_used number;
  begin
    if b is null then
      return;
    end if;
    l_h := jn(b, 'height', 0);
    if l_h <= 0 then
      return;
    end if;
    l_used := least(band_used(b), l_h);
    if lower(js(b, 'position')) = 'bottom' then
      -- anchored just above the page footer of the last page
      if g_y > g_bottom - l_h then
        new_page;
      end if;
      draw_band_at(b, g_ml, g_bottom - l_h);
      g_y := g_bottom;
      return;
    end if;
    if g_y + l_used > g_bottom and g_y > g_top then
      new_page;
    end if;
    draw_band_at(b, g_ml, g_y);
    g_y := g_y + l_h;
  end;

  ------------------------------------------------------------------ tables
  procedure render_table(o json_object_t, p_ox number) is
    type t_col is record (
      title  varchar2(4000), field varchar2(4000), w number, align varchar2(10),
      halign varchar2(10), fmt varchar2(200), total varchar2(10), idx pls_integer, token boolean);
    type t_cols is table of t_col index by pls_integer;
    l_cols    t_cols;
    l_arr     json_array_t := ja(o, 'columns');
    c         json_object_t;
    l_alias   varchar2(10) := upper(js(o, 'query'));
    l_x       number := p_ox + jn(o, 'x', 0);
    l_w       number := jn(o, 'w', 100);
    l_sumw    number := 0;
    l_font    varchar2(20) := e_font(o);
    l_size    number := e_size(o);
    l_color   varchar2(20) := js(o, 'color', g_color);
    l_pad     number := jn(o, 'padding', 3);
    l_rowh    number := jn(o, 'rowHeight', l_size * 1.2 + 2 * jn(o, 'padding', 3));
    l_lh      number := jn(o, 'lineHeight', 1.2);
    l_wrap    boolean := jb(o, 'wrap', true);
    l_grid    varchar2(20) := lower(js(o, 'grid', 'all'));
    l_gcolor  varchar2(20) := js(o, 'gridColor', '#999999');
    l_gw      number := jn(o, 'gridWidth', 0.5);
    l_zebra   varchar2(20) := js(o, 'zebra');
    l_hdr     json_object_t := jo(o, 'header');
    l_hshow   boolean := jb(l_hdr, 'show', true);
    l_hh      number := jn(l_hdr, 'height', l_rowh);
    l_hrepeat boolean := jb(l_hdr, 'repeat', true);
    l_tot     json_object_t := jo(o, 'totals');
    l_tshow   boolean := false;
    l_grp     varchar2(200) := upper(js(o, 'groupBy'));
    l_gidx    pls_integer;
    l_gval    varchar2(4000);
    l_gprev   varchar2(4000);
    l_gstart  pls_integer := 1;
    l_rows    pls_integer := 0;
    l_seg_top number;
    l_any_tot boolean := false;

    procedure cell_lines(p_x number, p_y number, p_w number, p_h number, p_text varchar2,
                         p_bold boolean, p_color varchar2, p_align varchar2, p_size number) is
    begin
      draw_text(p_x, p_y, p_w, p_h, p_text, l_font, p_size, p_bold, false, false, p_color, p_align,
                'middle', l_wrap, l_pad, l_lh);
    end;

    procedure row_frame(p_y number, p_h number, p_bg varchar2, p_from pls_integer default 0,
                        p_to pls_integer default 0) is
      l_cx number := l_x;
      l_mw number := 0;
    begin
      if p_bg is not null then
        pdf_writer.rect(l_x, p_y, l_w, p_h, p_bg);
      end if;
      if l_grid = 'all' then
        for i in 1 .. l_cols.count loop
          if i between p_from and p_to then
            -- merged cells: one frame
            l_mw := l_mw + l_cols(i).w;
            if i = p_to then
              pdf_writer.rect(l_cx - l_mw + l_cols(i).w, p_y, l_mw, p_h, null, l_gcolor, l_gw);
            end if;
          else
            pdf_writer.rect(l_cx, p_y, l_cols(i).w, p_h, null, l_gcolor, l_gw);
          end if;
          l_cx := l_cx + l_cols(i).w;
        end loop;
      elsif l_grid = 'horizontal' then
        pdf_writer.line(l_x, p_y + p_h, l_x + l_w, p_y + p_h, l_gcolor, l_gw);
      end if;
    end;

    procedure segment_end is
    begin
      if l_grid = 'outer' and l_seg_top is not null and g_y > l_seg_top then
        pdf_writer.rect(l_x, l_seg_top, l_w, g_y - l_seg_top, null, l_gcolor, l_gw);
      end if;
    end;

    procedure header_row is
      l_cx number := l_x;
    begin
      if not l_hshow then
        return;
      end if;
      row_frame(g_y, l_hh, js(l_hdr, 'bg'));
      if l_grid = 'horizontal' then
        pdf_writer.line(l_x, g_y, l_x + l_w, g_y, l_gcolor, l_gw);
      end if;
      for i in 1 .. l_cols.count loop
        cell_lines(l_cx, g_y, l_cols(i).w, l_hh, resolve(l_cols(i).title), jb(l_hdr, 'bold', true),
                   js(l_hdr, 'color', l_color), l_cols(i).halign, jn(l_hdr, 'size', l_size));
        l_cx := l_cx + l_cols(i).w;
      end loop;
      g_y := g_y + l_hh;
    end;

    procedure page_break is
    begin
      segment_end;
      new_page;
      l_seg_top := g_y;
      if l_hrepeat then
        header_row;
      end if;
    end;

    function cell_value(p_col pls_integer, p_row pls_integer) return varchar2 is
    begin
      if l_cols(p_col).token then
        return resolve(l_cols(p_col).field);
      elsif l_cols(p_col).idx is not null then
        return fmt_value(l_alias, p_row, l_cols(p_col).idx, l_cols(p_col).fmt);
      end if;
      return null;
    end;

    function row_height(p_texts t_strs, p_bold boolean default false) return number is
      l_h number := l_rowh;
    begin
      if l_wrap then
        for i in 1 .. l_cols.count loop
          l_h := greatest(l_h, text_height(p_texts(i), l_cols(i).w - 2 * l_pad, l_font, p_bold, false,
                                           l_size, true, l_lh) + 2 * l_pad);
        end loop;
      end if;
      -- a row never gets taller than a page
      return least(l_h, g_bottom - g_top - case when l_hshow and l_hrepeat then l_hh else 0 end);
    end;

    -- p_from .. p_to: cells merged into one (the label of a totals row)
    procedure draw_row(p_texts t_strs, p_bg varchar2, p_bold boolean, p_from pls_integer default 0,
                       p_to pls_integer default 0) is
      l_h  number := l_rowh;
      l_cx number := l_x;
      l_mw number := 0;
    begin
      if p_from > 0 then
        for i in p_from .. p_to loop
          l_mw := l_mw + l_cols(i).w;
        end loop;
        for i in 1 .. l_cols.count loop
          if i not between p_from and p_to and l_wrap then
            l_h := greatest(l_h, text_height(p_texts(i), l_cols(i).w - 2 * l_pad, l_font, p_bold, false, l_size, true, l_lh) + 2 * l_pad);
          end if;
        end loop;
      else
        l_h := row_height(p_texts, p_bold);
      end if;
      if g_y + l_h > g_bottom then
        page_break;
      end if;
      row_frame(g_y, l_h, p_bg, p_from, p_to);
      for i in 1 .. l_cols.count loop
        if i = p_from then
          cell_lines(l_cx, g_y, l_mw, l_h, p_texts(i), p_bold, l_color, 'left', l_size);
        elsif i not between p_from and p_to then
          cell_lines(l_cx, g_y, l_cols(i).w, l_h, p_texts(i), p_bold, l_color, l_cols(i).align, l_size);
        end if;
        l_cx := l_cx + l_cols(i).w;
      end loop;
      g_y := g_y + l_h;
    end;

    procedure totals_row(p_from pls_integer, p_to pls_integer, p_label varchar2, p_bg varchar2) is
      l_texts  t_strs;
      l_first  pls_integer := 0;
      l_last   pls_integer := 0;
    begin
      for i in 1 .. l_cols.count loop
        if l_cols(i).total is not null and l_cols(i).idx is not null then
          l_texts(i) := fmt_number(aggregate(l_cols(i).total, l_alias, l_cols(i).idx, p_from, p_to), l_cols(i).fmt);
        else
          l_texts(i) := null;
        end if;
      end loop;
      -- the label spans the first columns without a total
      for i in 1 .. l_cols.count loop
        if l_cols(i).total is null then
          if l_first = 0 then
            l_first := i;
            l_last := i;
          elsif l_last = i - 1 then
            l_last := i;
          end if;
        end if;
      end loop;
      if l_first > 0 then
        l_texts(l_first) := p_label;
      end if;
      draw_row(l_texts, p_bg, jb(l_tot, 'bold', true), l_first, l_last);
    end;

    procedure group_header(p_row pls_integer) is
      l_texts t_strs;
      l_h     number;
      l_label varchar2(4000);
    begin
      l_label := replace(nvl(js(o, 'groupLabel'), '{VALUE}'), '{VALUE}', l_gval);
      l_label := resolve(l_label);
      l_h := greatest(l_rowh, text_height(l_label, l_w - 2 * l_pad, l_font, true, false, l_size, l_wrap, l_lh) + 2 * l_pad);
      if g_y + l_h + l_rowh > g_bottom then
        page_break;
      end if;
      pdf_writer.rect(l_x, g_y, l_w, l_h, js(o, 'groupBg'),
                      case when l_grid in ('all', 'horizontal') then l_gcolor end, l_gw);
      draw_text(l_x, g_y, l_w, l_h, l_label, l_font, l_size, true, false, false, l_color, 'left', 'middle', l_wrap, l_pad, l_lh);
      g_y := g_y + l_h;
    end;

  begin
    if not print_when(o) then
      return;
    end if;
    -- columns
    for i in 0 .. l_arr.get_size - 1 loop
      c := el(l_arr, i);
      l_cols(i + 1).title  := js(c, 'title');
      l_cols(i + 1).field  := js(c, 'field');
      l_cols(i + 1).w      := jn(c, 'width', 60);
      l_cols(i + 1).align  := lower(js(c, 'align', 'left'));
      l_cols(i + 1).halign := lower(js(c, 'headerAlign', js(c, 'align', 'left')));
      l_cols(i + 1).fmt    := js(c, 'format');
      l_cols(i + 1).total  := upper(js(c, 'total'));
      if l_cols(i + 1).total = 'NONE' then
        l_cols(i + 1).total := null;
      end if;
      l_cols(i + 1).token  := instr(l_cols(i + 1).field, '{') > 0;
      if not l_cols(i + 1).token and has_ds(l_alias) then
        -- "AMOUNT" or "Q2.AMOUNT"
        l_cols(i + 1).idx := col_idx(l_alias, regexp_replace(l_cols(i + 1).field, '^Q[0-9]+\.', null, 1, 1, 'i'));
      end if;
      if l_cols(i + 1).total is not null then
        l_any_tot := true;
      end if;
      l_sumw := l_sumw + l_cols(i + 1).w;
    end loop;
    if l_cols.count = 0 then
      return;
    end if;
    -- the columns fill the width of the table
    if l_sumw > 0 and abs(l_sumw - l_w) > 0.5 then
      for i in 1 .. l_cols.count loop
        l_cols(i).w := l_cols(i).w * l_w / l_sumw;
      end loop;
    end if;
    l_tshow := jb(l_tot, 'show', l_any_tot);
    if has_ds(l_alias) then
      l_rows := g_data(l_alias).row_count;
    end if;
    if l_grp is not null and has_ds(l_alias) then
      l_gidx := col_idx(l_alias, regexp_replace(l_grp, '^Q[0-9]+\.', null, 1, 1, 'i'));
    end if;

    -- room for the header and one row, else start on the next page
    if g_y + (case when l_hshow then l_hh else 0 end) + l_rowh > g_bottom and g_y > g_top then
      new_page;
    end if;
    l_seg_top := g_y;
    header_row;

    if l_rows = 0 then
      if js(o, 'noData') is not null then
        if g_y + l_rowh > g_bottom then
          page_break;
        end if;
        pdf_writer.rect(l_x, g_y, l_w, l_rowh, null, case when l_grid <> 'none' then l_gcolor end, l_gw);
        draw_text(l_x, g_y, l_w, l_rowh, resolve(js(o, 'noData')), l_font, l_size, false, true, false,
                  l_color, 'center', 'middle', false, l_pad, l_lh);
        g_y := g_y + l_rowh;
      end if;
    end if;

    for r in 1 .. l_rows loop
      g_cur_row(l_alias) := r;
      if l_gidx is not null then
        l_gval := fmt_value(l_alias, r, l_gidx, null);
        if r = 1 or nvl(l_gval, chr(0)) <> nvl(l_gprev, chr(0)) then
          if r > 1 and l_any_tot and jb(o, 'groupTotals', true) then
            g_cur_row(l_alias) := r - 1;
            totals_row(l_gstart, r - 1, replace(nvl(js(o, 'groupTotalLabel'), 'Sub-total'), '{VALUE}', l_gprev), js(o, 'groupBg'));
            g_cur_row(l_alias) := r;
          end if;
          group_header(r);
          l_gstart := r;
          l_gprev := l_gval;
        end if;
      end if;
      declare
        l_texts t_strs;
      begin
        for i in 1 .. l_cols.count loop
          l_texts(i) := cell_value(i, r);
        end loop;
        draw_row(l_texts, case when l_zebra is not null and mod(r, 2) = 0 then l_zebra end, false);
      end;
    end loop;

    if l_gidx is not null and l_rows > 0 and l_any_tot and jb(o, 'groupTotals', true) then
      totals_row(l_gstart, l_rows, replace(nvl(js(o, 'groupTotalLabel'), 'Sub-total'), '{VALUE}', l_gprev), js(o, 'groupBg'));
    end if;
    if l_tshow and l_rows > 0 then
      totals_row(1, l_rows, resolve(js(l_tot, 'label', 'Total')), js(l_tot, 'bg'));
    end if;
    segment_end;
    if has_ds(l_alias) then
      g_cur_row.delete(l_alias);
    end if;
  end;

  ------------------------------------------------------------------ body
  procedure render_body is
    b       json_object_t := band('body');
    l_els   json_array_t;
    l_tabs  t_idx;          -- element indexes of the tables, top to bottom
    l_n     pls_integer := 0;
    l_tmp   pls_integer;
    l_start number;
    l_end   number;
    l_used  number;
    l_owner t_idx;          -- element index -> table order it belongs to (0 = none)
    o       json_object_t;
    t       json_object_t;
    l_ty    number;
    l_th    number;
    l_bh    number;
  begin
    if b is null then
      return;
    end if;
    l_els := ja(b, 'elements');
    l_bh := jn(b, 'height', 0);
    for i in 0 .. l_els.get_size - 1 loop
      if lower(js(el(l_els, i), 'type')) = 'table' then
        l_n := l_n + 1;
        l_tabs(l_n) := i;
      end if;
    end loop;
    -- tables by their top
    for i in 1 .. l_n loop
      for j in i + 1 .. l_n loop
        if jn(el(l_els, l_tabs(j)), 'y', 0) < jn(el(l_els, l_tabs(i)), 'y', 0) then
          l_tmp := l_tabs(i);
          l_tabs(i) := l_tabs(j);
          l_tabs(j) := l_tmp;
        end if;
      end loop;
    end loop;
    -- an element beside a table (overlapping its rows) is drawn with that table
    for i in 0 .. l_els.get_size - 1 loop
      l_owner(i) := 0;
      o := el(l_els, i);
      if lower(js(o, 'type')) <> 'table' then
        for k in 1 .. l_n loop
          t := el(l_els, l_tabs(k));
          if jn(o, 'y', 0) < jn(t, 'y', 0) + jn(t, 'h', 0) and jn(o, 'y', 0) + jn(o, 'h', 0) > jn(t, 'y', 0) then
            l_owner(i) := k;
            exit;
          end if;
        end loop;
      end if;
    end loop;

    for k in 0 .. l_n loop
      -- the stretch between table k and table k + 1 (0 = before the first table)
      if k = 0 then
        l_start := 0;
      else
        t := el(l_els, l_tabs(k));
        l_start := jn(t, 'y', 0) + jn(t, 'h', 0);
      end if;
      if k < l_n then
        l_end := jn(el(l_els, l_tabs(k + 1)), 'y', 0);
      else
        l_end := greatest(l_bh, l_start);
      end if;
      l_used := 0;
      for i in 0 .. l_els.get_size - 1 loop
        o := el(l_els, i);
        if lower(js(o, 'type')) <> 'table' and l_owner(i) = 0 and jn(o, 'y', 0) >= l_start and jn(o, 'y', 0) < l_end then
          l_used := greatest(l_used, jn(o, 'y', 0) + jn(o, 'h', 0) - l_start);
        end if;
      end loop;
      if l_used > 0 and g_y + l_used > g_bottom and g_y > g_top then
        new_page;
      end if;
      for i in 0 .. l_els.get_size - 1 loop
        o := el(l_els, i);
        if lower(js(o, 'type')) <> 'table' and l_owner(i) = 0 and jn(o, 'y', 0) >= l_start and jn(o, 'y', 0) < l_end then
          draw_element(o, g_ml, g_y - l_start);
        end if;
      end loop;
      g_y := g_y + greatest(l_end - l_start, 0);

      -- table k + 1 with the elements beside it
      if k < l_n then
        t := el(l_els, l_tabs(k + 1));
        l_ty := jn(t, 'y', 0);
        l_th := jn(t, 'h', 0);
        if g_y + least(l_th, 40) > g_bottom and g_y > g_top then
          new_page;
        end if;
        for i in 0 .. l_els.get_size - 1 loop
          if l_owner(i) = k + 1 then
            draw_element(el(l_els, i), g_ml, g_y - l_ty);
          end if;
        end loop;
        render_table(t, g_ml);
      end if;
    end loop;
  end;

  ------------------------------------------------------------------ labels
  procedure render_labels is
    l_lab    json_object_t := jo(g_layout, 'labels');
    b        json_object_t := band('label');
    l_alias  varchar2(10) := upper(js(l_lab, 'query', 'Q1'));
    l_across pls_integer := greatest(jn(l_lab, 'across', 1), 1);
    l_down   pls_integer := greatest(jn(l_lab, 'down', 1), 1);
    l_w      number := jn(l_lab, 'width', 180);
    l_h      number := jn(l_lab, 'height', 72);
    l_gx     number := jn(l_lab, 'gapX', 0);
    l_gy     number := jn(l_lab, 'gapY', 0);
    l_skip   pls_integer := greatest(nvl(to_number(param('LABEL_START') default null on conversion error), 1) - 1, 0);
    l_rows   pls_integer := 0;
    l_pos    pls_integer;
    l_x      number;
    l_y      number;
  begin
    if has_ds(l_alias) then
      l_rows := g_data(l_alias).row_count;
    end if;
    if jb(l_lab, 'perPage') then
      -- a label printer: every label is a page of its own, the size of the label
      g_pw := l_w;
      g_ph := l_h;
      if l_rows = 0 then
        new_page;
        return;
      end if;
      for r in 1 .. l_rows loop
        new_page;
        g_cur_row(l_alias) := r;
        if jb(l_lab, 'outline') then
          pdf_writer.rect(0.5, 0.5, l_w - 1, l_h - 1, null, '#BBBBBB', 0.3, 0, 'dashed');
        end if;
        draw_band_at(b, 0, 0);
      end loop;
      return;
    end if;
    if l_rows = 0 then
      new_page;
      return;
    end if;
    for r in 1 .. l_rows loop
      l_pos := mod(r - 1 + l_skip, l_across * l_down);
      if r = 1 or l_pos = 0 then
        new_page;
      end if;
      g_cur_row(l_alias) := r;
      l_x := g_ml + mod(l_pos, l_across) * (l_w + l_gx);
      l_y := g_mt + trunc(l_pos / l_across) * (l_h + l_gy);
      if jb(l_lab, 'outline') then
        pdf_writer.rect(l_x, l_y, l_w, l_h, null, '#BBBBBB', 0.3, 0, 'dashed');
      end if;
      draw_band_at(b, l_x, l_y);
    end loop;
  end;

  ------------------------------------------------------------------ document
  procedure doc_begin(p_layout clob, p_title varchar2 default null) is
    l_page json_object_t;
    l_mar  json_object_t;
    l_font json_object_t;
  begin
    g_layout := json_object_t.parse(nvl(p_layout, '{}'));
    g_bands  := nvl(jo(g_layout, 'bands'), json_object_t());
    g_title  := p_title;
    g_type   := lower(js(g_layout, 'type', 'report'));
    g_repeat := upper(js(g_layout, 'repeat'));
    l_page   := jo(g_layout, 'page');
    l_mar    := jo(l_page, 'margin');
    g_pw := jn(l_page, 'width', 595.28);
    g_ph := jn(l_page, 'height', 841.89);
    g_mt := jn(l_mar, 'top', 28.35);
    g_mr := jn(l_mar, 'right', 28.35);
    g_mb := jn(l_mar, 'bottom', 28.35);
    g_ml := jn(l_mar, 'left', 28.35);
    g_cw := g_pw - g_ml - g_mr;
    l_font  := jo(g_layout, 'font');
    g_font  := lower(js(l_font, 'family', 'helvetica'));
    g_size  := jn(l_font, 'size', 9);
    g_color := js(l_font, 'color', '#000000');
    g_images.delete;
    pdf_writer.init(p_title, null);
  end;

  procedure finish_section is
    l_hdr json_object_t := band('pageHeader');
    l_ftr json_object_t := band('pageFooter');
  begin
    g_page_total := g_sec_pages;
    for p in 1 .. g_sec_pages loop
      pdf_writer.set_page(g_sec_first + p - 1);
      g_page_no := p;
      if l_hdr is not null and band_h('pageHeader') > 0 and band_on('pageHeader', p, g_sec_pages) then
        draw_band_at(l_hdr, g_ml, g_mt);
      end if;
      if l_ftr is not null and band_h('pageFooter') > 0 and band_on('pageFooter', p, g_sec_pages) then
        draw_band_at(l_ftr, g_ml, g_ph - g_mb - band_h('pageFooter'));
      end if;
    end loop;
    g_page_total := null;
  end;

  procedure section(p_data t_data, p_params t_params) is
    l_alias varchar2(10);
  begin
    g_data := p_data;
    g_params := p_params;
    g_cur_row.delete;
    g_cols.delete;
    l_alias := g_data.first;
    while l_alias is not null loop
      for c in 1 .. g_data(l_alias).names.count loop
        g_cols(l_alias || '.' || upper(g_data(l_alias).names(c))) := c;
      end loop;
      l_alias := g_data.next(l_alias);
    end loop;
    g_sec_first := pdf_writer.page_count + 1;
    g_sec_pages := 0;
    if g_type = 'labels' then
      render_labels;
    else
      new_page;
      static_band('reportHeader');
      render_body;
      static_band('summary');
    end if;
    finish_section;
  end;

  function doc_end return blob is
  begin
    return pdf_writer.finish;
  end;

  function page_count return pls_integer is
  begin
    return pdf_writer.page_count;
  end;

  function repeat_query return varchar2 is
  begin
    return case when g_type <> 'labels' then g_repeat end;
  end;

  function layout_type return varchar2 is
  begin
    return g_type;
  end;

end pdf_engine;
/
