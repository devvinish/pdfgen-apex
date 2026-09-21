-- PDF Report Designer: the low-level PDF writer.
-- Draws text, lines, boxes, rounded boxes, ellipses and JPEG images on pages of any size, with the
-- 14 standard PDF fonts (Helvetica, Times, Courier; regular, bold, italic) in WinAnsi encoding, and the
-- look-alikes Arial, Arial Narrow and Arial Black made from Helvetica.
-- Coordinates are points (1/72 inch) from the TOP-LEFT corner of the page.
set define off

create or replace package pdf_writer authid definer as

  procedure init(p_title varchar2 default null, p_author varchar2 default null);

  -- adds a page and makes it the current one; returns its number (1, 2, ...)
  function  new_page(p_width number, p_height number) return pls_integer;
  -- makes an existing page the current one (to draw page headers / footers afterwards)
  procedure set_page(p_page pls_integer);
  function  current_page return pls_integer;
  function  page_count return pls_integer;
  function  page_width return number;
  function  page_height return number;

  -- p_font: helvetica | times | courier | arial | arialnarrow | arialblack
  -- (Arial has the letter widths of Helvetica; Arial Narrow is Helvetica at 82% width; Arial Black is
  --  Helvetica Bold, 110% wide, drawn with an outline of its own colour - no font files needed)
  function  text_width(p_text varchar2, p_font varchar2, p_bold boolean, p_italic boolean,
                       p_size number) return number;
  -- p_y is the BASELINE of the text
  procedure text(p_x number, p_y number, p_text varchar2, p_font varchar2, p_bold boolean,
                 p_italic boolean, p_size number, p_color varchar2 default '#000000');

  -- p_dash: solid | dashed | dotted
  procedure rect(p_x number, p_y number, p_w number, p_h number, p_fill varchar2 default null,
                 p_stroke varchar2 default null, p_line_width number default 1,
                 p_radius number default 0, p_dash varchar2 default null);
  procedure ellipse(p_x number, p_y number, p_w number, p_h number, p_fill varchar2 default null,
                    p_stroke varchar2 default null, p_line_width number default 1,
                    p_dash varchar2 default null);
  procedure line(p_x1 number, p_y1 number, p_x2 number, p_y2 number,
                 p_color varchar2 default '#000000', p_width number default 1,
                 p_dash varchar2 default null);

  -- a JPEG image; p_key identifies it so that it is embedded only once
  -- p_fit: stretch | contain
  procedure image(p_key varchar2, p_jpeg blob, p_x number, p_y number, p_w number, p_h number,
                  p_fit varchar2 default 'contain');
  procedure jpeg_info(p_jpeg blob, o_width out number, o_height out number, o_comps out number);

  -- everything drawn between clip_begin and clip_end is cut to the rectangle
  procedure clip_begin(p_x number, p_y number, p_w number, p_h number);
  procedure clip_end;

  function  finish return blob;

end pdf_writer;
/

create or replace package body pdf_writer as

  type t_page is record (w number, h number, content clob);
  type t_pages is table of t_page index by pls_integer;
  type t_image is record (res varchar2(10), data blob, w number, h number, comps number);
  type t_images is table of t_image index by varchar2(400);
  type t_widths is table of pls_integer index by pls_integer;
  type t_str is table of varchar2(40) index by varchar2(40);
  type t_offsets is table of number index by pls_integer;

  g_pages   t_pages;
  g_cur     pls_integer := 0;
  g_buf     varchar2(32767);
  g_images  t_images;
  g_fonts   t_str;          -- base font name -> resource name (F1, F2 ...)
  g_title   varchar2(4000);
  g_author  varchar2(4000);

  -- glyph widths (1/1000 em) of the characters 32..126
  w_helv    t_widths;
  w_helvb   t_widths;
  w_times   t_widths;
  w_timesb  t_widths;

  g_out     blob;
  g_offsets t_offsets;

  c_helv   constant varchar2(1000) := '278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,500,500,500,334,260,334,584';
  c_helvb  constant varchar2(1000) := '278,333,474,556,556,889,722,238,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,333,333,584,584,584,611,975,722,722,722,722,667,611,778,722,278,556,722,611,833,722,778,667,778,722,667,611,722,667,944,667,667,611,333,278,333,584,556,333,556,611,556,611,556,333,611,611,278,278,556,278,889,611,611,611,611,389,556,333,611,556,778,556,556,500,389,280,389,584';
  c_times  constant varchar2(1000) := '250,333,408,500,500,833,778,180,333,333,500,564,250,333,250,278,500,500,500,500,500,500,500,500,500,500,278,278,564,564,564,444,921,722,667,667,722,611,556,722,722,333,389,722,611,889,722,722,556,722,667,556,611,722,722,944,722,722,611,333,278,333,469,500,333,444,500,444,500,444,333,500,500,278,278,500,278,778,500,500,500,500,333,389,278,500,500,722,500,500,444,480,200,480,541';
  c_timesb constant varchar2(1000) := '250,333,555,500,500,1000,833,278,333,333,500,570,250,333,250,278,500,500,500,500,500,500,500,500,500,500,333,333,570,570,570,500,930,722,667,722,722,667,611,778,778,389,500,778,667,944,722,778,611,778,722,556,667,722,722,1000,722,722,667,333,278,333,581,500,333,500,556,444,556,444,333,500,556,278,333,556,278,833,556,500,556,556,444,389,333,556,500,722,500,500,444,394,220,394,520';

  procedure load_widths(p_list varchar2, p_tab in out nocopy t_widths) is
    l_pos pls_integer := 1;
    l_nxt pls_integer;
    l_chr pls_integer := 32;
  begin
    loop
      l_nxt := instr(p_list, ',', l_pos);
      p_tab(l_chr) := to_number(substr(p_list, l_pos, case when l_nxt = 0 then length(p_list) + 1 else l_nxt end - l_pos));
      exit when l_nxt = 0;
      l_pos := l_nxt + 1;
      l_chr := l_chr + 1;
    end loop;
  end;

  -- a number as PDF writes it: '.' decimal separator, at most 3 decimals
  function num(p number) return varchar2 is
  begin
    return to_char(round(nvl(p, 0), 3), 'TM9', 'NLS_NUMERIC_CHARACTERS=''.,''');
  end;

  -- '#RRGGBB' or '#RGB' -> 'r g b'
  function rgb(p_color varchar2) return varchar2 is
    l varchar2(20) := ltrim(trim(p_color), '#');
  begin
    if length(l) = 3 then
      l := substr(l, 1, 1) || substr(l, 1, 1) || substr(l, 2, 1) || substr(l, 2, 1) || substr(l, 3, 1) || substr(l, 3, 1);
    end if;
    if l is null or length(l) <> 6 or not regexp_like(l, '^[0-9A-Fa-f]{6}$') then
      return '0 0 0';
    end if;
    return num(to_number(substr(l, 1, 2), 'XX') / 255) || ' ' ||
           num(to_number(substr(l, 3, 2), 'XX') / 255) || ' ' ||
           num(to_number(substr(l, 5, 2), 'XX') / 255);
  end;

  function has_color(p_color varchar2) return boolean is
  begin
    return trim(p_color) is not null and lower(trim(p_color)) not in ('transparent', 'none');
  end;

  procedure flush is
  begin
    if g_cur > 0 and g_buf is not null then
      dbms_lob.writeappend(g_pages(g_cur).content, length(g_buf), g_buf);
    end if;
    g_buf := null;
  end;

  procedure put(p varchar2) is
  begin
    if nvl(length(g_buf), 0) + length(p) + 1 > 32000 then
      flush;
    end if;
    g_buf := g_buf || p || chr(10);
  end;

  -- y from the top of the page -> PDF y (from the bottom)
  function py(p_y number) return number is
  begin
    return g_pages(g_cur).h - p_y;
  end;

  procedure init(p_title varchar2 default null, p_author varchar2 default null) is
  begin
    for i in 1 .. g_pages.count loop
      if dbms_lob.istemporary(g_pages(i).content) = 1 then
        dbms_lob.freetemporary(g_pages(i).content);
      end if;
    end loop;
    g_pages.delete;
    g_images.delete;
    g_fonts.delete;
    g_offsets.delete;
    g_cur := 0;
    g_buf := null;
    g_title := p_title;
    g_author := p_author;
  end;

  function new_page(p_width number, p_height number) return pls_integer is
    l pls_integer;
  begin
    flush;
    l := g_pages.count + 1;
    g_pages(l).w := p_width;
    g_pages(l).h := p_height;
    dbms_lob.createtemporary(g_pages(l).content, true);
    g_cur := l;
    return l;
  end;

  procedure set_page(p_page pls_integer) is
  begin
    if p_page <> g_cur then
      flush;
      g_cur := p_page;
    end if;
  end;

  function current_page return pls_integer is begin return g_cur; end;
  function page_count return pls_integer is begin return g_pages.count; end;
  function page_width return number is begin return g_pages(g_cur).w; end;
  function page_height return number is begin return g_pages(g_cur).h; end;

  function base_font(p_font varchar2, p_bold boolean, p_italic boolean) return varchar2 is
    l_b boolean := nvl(p_bold, false);
    l_i boolean := nvl(p_italic, false);
  begin
    case lower(p_font)
      when 'arialblack' then
        return case when l_i then 'Helvetica-BoldOblique' else 'Helvetica-Bold' end;
      when 'times' then
        return case when l_b and l_i then 'Times-BoldItalic' when l_b then 'Times-Bold'
                    when l_i then 'Times-Italic' else 'Times-Roman' end;
      when 'courier' then
        return case when l_b and l_i then 'Courier-BoldOblique' when l_b then 'Courier-Bold'
                    when l_i then 'Courier-Oblique' else 'Courier' end;
      else
        return case when l_b and l_i then 'Helvetica-BoldOblique' when l_b then 'Helvetica-Bold'
                    when l_i then 'Helvetica-Oblique' else 'Helvetica' end;
    end case;
  end;

  function font_res(p_base varchar2) return varchar2 is
  begin
    if not g_fonts.exists(p_base) then
      g_fonts(p_base) := 'F' || (g_fonts.count + 1);
    end if;
    return g_fonts(p_base);
  end;

  function text_width(p_text varchar2, p_font varchar2, p_bold boolean, p_italic boolean,
                      p_size number) return number is
    l_total number := 0;
    l_c     pls_integer;
    l_def   pls_integer;
    l_font  varchar2(20) := lower(nvl(p_font, 'helvetica'));
    l_bold  boolean := nvl(p_bold, false);
    l_scale number := 1;
  begin
    -- the look-alikes of Arial: Helvetica metrics, scaled
    if l_font = 'arialnarrow' then
      l_scale := 0.82;
    elsif l_font = 'arialblack' then
      l_scale := 1.1;
      l_bold := true;
    end if;
    if l_font in ('arial', 'arialnarrow', 'arialblack') then
      l_font := 'helvetica';
    end if;
    if p_text is null then
      return 0;
    end if;
    if l_font = 'courier' then
      return length(p_text) * 600 * p_size / 1000;
    end if;
    l_def := case when l_font = 'times' then 500 else 556 end;
    for i in 1 .. length(p_text) loop
      l_c := ascii(substr(p_text, i, 1));
      if l_c between 32 and 126 then
        l_total := l_total + case
                               when l_font = 'times' and l_bold then w_timesb(l_c)
                               when l_font = 'times' then w_times(l_c)
                               when l_bold then w_helvb(l_c)
                               else w_helv(l_c)
                             end;
      else
        l_total := l_total + l_def;
      end if;
    end loop;
    return l_total * p_size / 1000 * l_scale;
  end;

  -- the text in WinAnsi (Windows-1252) bytes, as a PDF hex string
  function win_hex(p_text varchar2) return varchar2 is
    l varchar2(32767) := p_text;
  begin
    -- the rupee sign is not in WinAnsi
    l := replace(l, unistr('\20B9'), 'Rs.');
    return '<' || rawtohex(utl_i18n.string_to_raw(l, 'WE8MSWIN1252')) || '>';
  end;

  procedure text(p_x number, p_y number, p_text varchar2, p_font varchar2, p_bold boolean,
                 p_italic boolean, p_size number, p_color varchar2 default '#000000') is
  begin
    if p_text is null then
      return;
    end if;
    -- q .. Q: the scaling and the outline (text state) must not reach the text drawn after this one
    put(case when lower(p_font) in ('arialnarrow', 'arialblack') then 'q ' end ||
        'BT /' || font_res(base_font(p_font, p_bold, p_italic)) || ' ' || num(p_size) || ' Tf ' ||
        rgb(nvl(p_color, '#000000')) || ' rg ' ||
        case lower(p_font)
          -- horizontal scaling (Tz); Arial Black also strokes the letters (2 Tr) to make them heavier
          when 'arialnarrow' then '82 Tz '
          when 'arialblack' then '110 Tz 2 Tr ' || rgb(nvl(p_color, '#000000')) || ' RG ' || num(p_size * 0.045) || ' w '
        end ||
        num(p_x) || ' ' || num(py(p_y)) || ' Td ' || win_hex(p_text) || ' Tj ET' ||
        case when lower(p_font) in ('arialnarrow', 'arialblack') then ' Q' end);
  end;

  function dash_op(p_dash varchar2, p_width number) return varchar2 is
  begin
    return case lower(p_dash)
             when 'dashed' then '[' || num(3 * greatest(p_width, 1)) || ' ' || num(2 * greatest(p_width, 1)) || '] 0 d '
             when 'dotted' then '[' || num(greatest(p_width, 0.8)) || ' ' || num(1.6 * greatest(p_width, 1)) || '] 0 d '
             else ''
           end;
  end;

  -- starts q, sets the colours and the line style; returns the painting operator
  function paint_begin(p_fill varchar2, p_stroke varchar2, p_line_width number, p_dash varchar2)
    return varchar2 is
    l_fill   boolean := has_color(p_fill);
    l_stroke boolean := has_color(p_stroke) and nvl(p_line_width, 0) > 0;
  begin
    if not l_fill and not l_stroke then
      return null;
    end if;
    put('q ' || case when l_fill then rgb(p_fill) || ' rg ' end ||
        case when l_stroke then rgb(p_stroke) || ' RG ' || num(p_line_width) || ' w ' ||
                                dash_op(p_dash, p_line_width) end);
    return case when l_fill and l_stroke then 'B' when l_fill then 'f' else 'S' end;
  end;

  procedure rect(p_x number, p_y number, p_w number, p_h number, p_fill varchar2 default null,
                 p_stroke varchar2 default null, p_line_width number default 1,
                 p_radius number default 0, p_dash varchar2 default null) is
    l_op varchar2(2);
    r    number;
    k    number;
    x0   number := p_x;
    x1   number := p_x + p_w;
    y0   number := py(p_y + p_h);   -- bottom
    y1   number := py(p_y);         -- top
  begin
    l_op := paint_begin(p_fill, p_stroke, p_line_width, p_dash);
    if l_op is null then
      return;
    end if;
    r := least(nvl(p_radius, 0), p_w / 2, p_h / 2);
    if r <= 0 then
      put(num(x0) || ' ' || num(y0) || ' ' || num(p_w) || ' ' || num(p_h) || ' re ' || l_op || ' Q');
    else
      k := 0.5523 * r;
      put(num(x0 + r) || ' ' || num(y1) || ' m ' ||
          num(x1 - r) || ' ' || num(y1) || ' l ' ||
          num(x1 - r + k) || ' ' || num(y1) || ' ' || num(x1) || ' ' || num(y1 - r + k) || ' ' || num(x1) || ' ' || num(y1 - r) || ' c ' ||
          num(x1) || ' ' || num(y0 + r) || ' l ' ||
          num(x1) || ' ' || num(y0 + r - k) || ' ' || num(x1 - r + k) || ' ' || num(y0) || ' ' || num(x1 - r) || ' ' || num(y0) || ' c ' ||
          num(x0 + r) || ' ' || num(y0) || ' l ' ||
          num(x0 + r - k) || ' ' || num(y0) || ' ' || num(x0) || ' ' || num(y0 + r - k) || ' ' || num(x0) || ' ' || num(y0 + r) || ' c ' ||
          num(x0) || ' ' || num(y1 - r) || ' l ' ||
          num(x0) || ' ' || num(y1 - r + k) || ' ' || num(x0 + r - k) || ' ' || num(y1) || ' ' || num(x0 + r) || ' ' || num(y1) || ' c h ' ||
          l_op || ' Q');
    end if;
  end;

  procedure ellipse(p_x number, p_y number, p_w number, p_h number, p_fill varchar2 default null,
                    p_stroke varchar2 default null, p_line_width number default 1,
                    p_dash varchar2 default null) is
    l_op varchar2(2);
    rx number := p_w / 2;
    ry number := p_h / 2;
    cx number := p_x + p_w / 2;
    cy number := py(p_y + p_h / 2);
    kx number := 0.5523 * p_w / 2;
    ky number := 0.5523 * p_h / 2;
  begin
    l_op := paint_begin(p_fill, p_stroke, p_line_width, p_dash);
    if l_op is null then
      return;
    end if;
    put(num(cx + rx) || ' ' || num(cy) || ' m ' ||
        num(cx + rx) || ' ' || num(cy + ky) || ' ' || num(cx + kx) || ' ' || num(cy + ry) || ' ' || num(cx) || ' ' || num(cy + ry) || ' c ' ||
        num(cx - kx) || ' ' || num(cy + ry) || ' ' || num(cx - rx) || ' ' || num(cy + ky) || ' ' || num(cx - rx) || ' ' || num(cy) || ' c ' ||
        num(cx - rx) || ' ' || num(cy - ky) || ' ' || num(cx - kx) || ' ' || num(cy - ry) || ' ' || num(cx) || ' ' || num(cy - ry) || ' c ' ||
        num(cx + kx) || ' ' || num(cy - ry) || ' ' || num(cx + rx) || ' ' || num(cy - ky) || ' ' || num(cx + rx) || ' ' || num(cy) || ' c h ' ||
        l_op || ' Q');
  end;

  procedure line(p_x1 number, p_y1 number, p_x2 number, p_y2 number,
                 p_color varchar2 default '#000000', p_width number default 1,
                 p_dash varchar2 default null) is
    l_op varchar2(2);
  begin
    l_op := paint_begin(null, nvl(p_color, '#000000'), p_width, p_dash);
    if l_op is null then
      return;
    end if;
    put(num(p_x1) || ' ' || num(py(p_y1)) || ' m ' || num(p_x2) || ' ' || num(py(p_y2)) || ' l S Q');
  end;

  function byte_at(p_blob blob, p_pos number) return pls_integer is
  begin
    return to_number(rawtohex(dbms_lob.substr(p_blob, 1, p_pos)), 'XX');
  end;

  procedure jpeg_info(p_jpeg blob, o_width out number, o_height out number, o_comps out number) is
    l_len    number := dbms_lob.getlength(p_jpeg);
    l_pos    number := 3;
    l_marker pls_integer;
  begin
    if l_len < 4 or rawtohex(dbms_lob.substr(p_jpeg, 2, 1)) <> 'FFD8' then
      raise_application_error(-20501, 'The image is not a JPEG file.');
    end if;
    while l_pos < l_len loop
      if byte_at(p_jpeg, l_pos) <> 255 then
        raise_application_error(-20501, 'The JPEG image could not be read.');
      end if;
      l_marker := byte_at(p_jpeg, l_pos + 1);
      if l_marker in (192, 193, 194, 195, 197, 198, 199, 201, 202, 203, 205, 206, 207) then
        o_height := byte_at(p_jpeg, l_pos + 5) * 256 + byte_at(p_jpeg, l_pos + 6);
        o_width  := byte_at(p_jpeg, l_pos + 7) * 256 + byte_at(p_jpeg, l_pos + 8);
        o_comps  := byte_at(p_jpeg, l_pos + 9);
        return;
      elsif l_marker = 255 then
        l_pos := l_pos + 1;           -- fill byte
      else
        l_pos := l_pos + 2 + byte_at(p_jpeg, l_pos + 2) * 256 + byte_at(p_jpeg, l_pos + 3);
      end if;
    end loop;
    raise_application_error(-20501, 'The JPEG image has no size information.');
  end;

  procedure image(p_key varchar2, p_jpeg blob, p_x number, p_y number, p_w number, p_h number,
                  p_fit varchar2 default 'contain') is
    l_img  t_image;
    l_w    number := p_w;
    l_h    number := p_h;
    l_x    number := p_x;
    l_y    number := p_y;
    l_r    number;
  begin
    if p_jpeg is null or dbms_lob.getlength(p_jpeg) = 0 then
      return;
    end if;
    if not g_images.exists(p_key) then
      jpeg_info(p_jpeg, l_img.w, l_img.h, l_img.comps);
      l_img.res := 'I' || (g_images.count + 1);
      l_img.data := p_jpeg;
      g_images(p_key) := l_img;
    end if;
    l_img := g_images(p_key);
    if nvl(lower(p_fit), 'contain') = 'contain' and l_img.w > 0 and l_img.h > 0 then
      l_r := least(p_w / l_img.w, p_h / l_img.h);
      l_w := l_img.w * l_r;
      l_h := l_img.h * l_r;
      l_x := p_x + (p_w - l_w) / 2;
      l_y := p_y + (p_h - l_h) / 2;
    end if;
    put('q ' || num(l_w) || ' 0 0 ' || num(l_h) || ' ' || num(l_x) || ' ' || num(py(l_y + l_h)) ||
        ' cm /' || l_img.res || ' Do Q');
  end;

  procedure clip_begin(p_x number, p_y number, p_w number, p_h number) is
  begin
    put('q ' || num(p_x) || ' ' || num(py(p_y + p_h)) || ' ' || num(p_w) || ' ' || num(p_h) || ' re W n');
  end;

  procedure clip_end is
  begin
    put('Q');
  end;

  ------------------------------------------------------------------ output
  procedure wa(p varchar2) is
    l raw(32767) := utl_raw.cast_to_raw(p);
  begin
    dbms_lob.writeappend(g_out, utl_raw.length(l), l);
  end;

  procedure obj_begin(p_no pls_integer) is
  begin
    g_offsets(p_no) := dbms_lob.getlength(g_out);
    wa(p_no || ' 0 obj' || chr(10));
  end;

  function pdf_date return varchar2 is
  begin
    return to_char(sysdate, 'YYYYMMDDHH24MISS');
  end;

  function utf16_hex(p varchar2) return varchar2 is
  begin
    return '<FEFF' || rawtohex(utl_i18n.string_to_raw(p, 'AL16UTF16')) || '>';
  end;

  function finish return blob is
    l_font_base  pls_integer := 5;
    l_img_base   pls_integer;
    l_page_base  pls_integer;
    l_total      pls_integer;
    l_kids       varchar2(32767);
    l_res        varchar2(32767);
    l_key        varchar2(400);
    l_no         pls_integer;
    l_len        number;
    l_pos        number;
    l_chunk      varchar2(8000);
    l_xref       number;
  begin
    flush;
    if g_pages.count = 0 then
      l_no := new_page(595.28, 841.89);
      flush;
    end if;
    l_img_base  := l_font_base + g_fonts.count;
    l_page_base := l_img_base + g_images.count;
    l_total     := l_page_base + 2 * g_pages.count;   -- objects 1 .. l_total - 1

    dbms_lob.createtemporary(g_out, true);
    wa('%PDF-1.4' || chr(10));
    dbms_lob.writeappend(g_out, 6, hextoraw('25E2E3CFD30A'));   -- binary comment

    -- 1 catalog, 2 page tree
    obj_begin(1);
    wa('<< /Type /Catalog /Pages 2 0 R >>' || chr(10) || 'endobj' || chr(10));
    for i in 1 .. g_pages.count loop
      l_kids := l_kids || (l_page_base + 2 * (i - 1) + 1) || ' 0 R ';
    end loop;
    obj_begin(2);
    wa('<< /Type /Pages /Kids [' || l_kids || '] /Count ' || g_pages.count || ' >>' || chr(10) || 'endobj' || chr(10));

    -- 3 resources shared by every page
    l_res := '<< /ProcSet [/PDF /Text /ImageB /ImageC] /Font <<';
    l_key := g_fonts.first;
    while l_key is not null loop
      l_res := l_res || ' /' || g_fonts(l_key) || ' ' || (l_font_base + to_number(substr(g_fonts(l_key), 2)) - 1) || ' 0 R';
      l_key := g_fonts.next(l_key);
    end loop;
    l_res := l_res || ' >> /XObject <<';
    l_key := g_images.first;
    while l_key is not null loop
      l_res := l_res || ' /' || g_images(l_key).res || ' ' || (l_img_base + to_number(substr(g_images(l_key).res, 2)) - 1) || ' 0 R';
      l_key := g_images.next(l_key);
    end loop;
    l_res := l_res || ' >> >>';
    obj_begin(3);
    wa(l_res || chr(10) || 'endobj' || chr(10));

    -- 4 document information
    obj_begin(4);
    wa('<< /Producer (PDF Report Designer for Oracle APEX) /CreationDate (D:' || pdf_date || ')' ||
       case when g_title is not null then ' /Title ' || utf16_hex(g_title) end ||
       case when g_author is not null then ' /Author ' || utf16_hex(g_author) end ||
       ' >>' || chr(10) || 'endobj' || chr(10));

    -- fonts
    l_key := g_fonts.first;
    while l_key is not null loop
      obj_begin(l_font_base + to_number(substr(g_fonts(l_key), 2)) - 1);
      wa('<< /Type /Font /Subtype /Type1 /BaseFont /' || l_key ||
         case when l_key not in ('Symbol', 'ZapfDingbats') then ' /Encoding /WinAnsiEncoding' end ||
         ' >>' || chr(10) || 'endobj' || chr(10));
      l_key := g_fonts.next(l_key);
    end loop;

    -- images
    l_key := g_images.first;
    while l_key is not null loop
      obj_begin(l_img_base + to_number(substr(g_images(l_key).res, 2)) - 1);
      wa('<< /Type /XObject /Subtype /Image /Width ' || g_images(l_key).w || ' /Height ' || g_images(l_key).h ||
         ' /ColorSpace ' || case g_images(l_key).comps when 1 then '/DeviceGray' when 4 then '/DeviceCMYK /Decode [1 0 1 0 1 0 1 0]' else '/DeviceRGB' end ||
         ' /BitsPerComponent 8 /Filter /DCTDecode /Length ' || dbms_lob.getlength(g_images(l_key).data) ||
         ' >>' || chr(10) || 'stream' || chr(10));
      dbms_lob.append(g_out, g_images(l_key).data);
      wa(chr(10) || 'endstream' || chr(10) || 'endobj' || chr(10));
      l_key := g_images.next(l_key);
    end loop;

    -- pages: content stream, then the page
    for i in 1 .. g_pages.count loop
      l_no  := l_page_base + 2 * (i - 1);
      l_len := dbms_lob.getlength(g_pages(i).content);
      obj_begin(l_no);
      wa('<< /Length ' || l_len || ' >>' || chr(10) || 'stream' || chr(10));
      l_pos := 1;
      while l_pos <= l_len loop
        l_chunk := dbms_lob.substr(g_pages(i).content, 8000, l_pos);
        wa(l_chunk);
        l_pos := l_pos + 8000;
      end loop;
      wa(chr(10) || 'endstream' || chr(10) || 'endobj' || chr(10));
      obj_begin(l_no + 1);
      wa('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ' || num(g_pages(i).w) || ' ' || num(g_pages(i).h) ||
         '] /Resources 3 0 R /Contents ' || l_no || ' 0 R >>' || chr(10) || 'endobj' || chr(10));
    end loop;

    -- cross-reference table and trailer
    l_xref := dbms_lob.getlength(g_out);
    wa('xref' || chr(10) || '0 ' || l_total || chr(10) || '0000000000 65535 f ' || chr(10));
    for i in 1 .. l_total - 1 loop
      wa(lpad(g_offsets(i), 10, '0') || ' 00000 n ' || chr(10));
    end loop;
    wa('trailer' || chr(10) || '<< /Size ' || l_total || ' /Root 1 0 R /Info 4 0 R >>' || chr(10) ||
       'startxref' || chr(10) || l_xref || chr(10) || '%%EOF' || chr(10));
    return g_out;
  end;

begin
  load_widths(c_helv, w_helv);
  load_widths(c_helvb, w_helvb);
  load_widths(c_times, w_times);
  load_widths(c_timesb, w_timesb);
end pdf_writer;
/
